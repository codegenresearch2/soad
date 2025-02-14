import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from database.models import Trade
from order_manager.manager import OrderManager

MARK_ORDER_STALE_AFTER = 60 * 60 * 24 * 2 # 2 days
PEGGED_ORDER_CANCEL_AFTER = 15 # 15 seconds

class OrderManager:
    def __init__(self, engine, brokers):
        logger.info('Initializing OrderManager')
        self.engine = engine
        self.db_manager = DBManager(engine)
        self.brokers = brokers

    async def reconcile_orders(self, orders):
        logger.info('Reconciling orders', extra={'orders': orders})
        for order in orders:
            await self.reconcile_order(order)
        # Commit the transaction

    async def reconcile_order(self, order):
        logger.info(f'Reconciling order {order.id}', extra={
            'order_id': order.id,
            'broker_id': order.broker_id,
            'broker': order.broker,
            'symbol': order.symbol,
            'quantity': order.quantity,
            'price': order.price,
            'side': order.side,
            'status': order.status
        })

        # Calculate the stale threshold
        stale_threshold = datetime.utcnow() - timedelta(seconds=MARK_ORDER_STALE_AFTER)

        # Check if the order is stale
        if order.timestamp < stale_threshold and order.status not in ['filled', 'cancelled']:
            try:
                logger.info(f'Marking order {order.id} as stale', extra={'order_id': order.id})
                await self.db_manager.update_trade_status(order.id, 'stale')
                return  # Exit early if the order is stale
            except Exception as e:
                logger.error(f'Error marking order {order.id} as stale', extra={'error': str(e)})
                return

        # If the order is not stale, reconcile it
        broker = self.brokers[order.broker]
        if order.broker_id is None:
            # If the order has no broker_id, mark it as stale
            logger.info(f'Marking order {order.id} as stale, missing broker_id', extra={'order_id': order.id})
            await self.db_manager.update_trade_status(order.id, 'stale')
            return
        filled = await broker.is_order_filled(order.broker_id)
        if filled:
            try:
                async with self.db_manager.Session() as session:
                    await self.db_manager.set_trade_filled(order.id)
                    await broker.update_positions(order.id, session)
            except Exception as e:
                logger.error(f'Error reconciling order {order.id}', extra={'error': str(e)})
        elif order.execution_style == 'pegged':
            cancel_threshold = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER)
            if order.timestamp < cancel_threshold:
                try:
                    logger.info(f'Cancelling pegged order {order.id}', extra={'order_id': order.id})
                    await broker.cancel_order(order.broker_id)
                    await self.db_manager.update_trade_status(order.id, 'cancelled')
                    mid_price = await broker.get_mid_price(order.symbol)
                    await self.place_order(
                        order.symbol, order.quantity, order.side, order.strategy_name, round(mid_price, 2), order_type='limit', execution_style=order.execution_style
                    )
                except Exception as e:
                    logger.error(f'Error cancelling pegged order {order.id}', extra={'error': str(e)})

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

async def run_order_manager(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()

@pytest.mark.asyncio
async def test_reconcile_order_pegged_expired(order_manager, mock_db_manager, mock_broker):
    """\n    Test that a pegged order older than PEGGED_ORDER_CANCEL_AFTER is canceled\n    and a new limit order is placed at the mid price.\n    """
    old_timestamp = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER + 1)
    pegged_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        symbol="AAPL",
        quantity=10,
        side="buy",
        strategy="test_strategy",
        timestamp=old_timestamp,
        status="open",
        execution_style="pegged"
    )

    # Mock placing a new order after cancellation
    # Assume place_order returns a Trade object or something similar
    order_manager.brokers['dummy_broker'].place_order = AsyncMock()

    await order_manager.reconcile_order(pegged_order)

    # The pegged order should be canceled
    mock_broker.cancel_order.assert_called_once_with("123")
    # The status should be updated to 'cancelled'
    mock_db_manager.update_trade_status.assert_called_once_with(1, "cancelled")

    # A new order should be placed using the mid_price (mocked as 100.00)
    order_manager.brokers['dummy_broker'].place_order.assert_called_once()
    args, kwargs = order_manager.brokers['dummy_broker'].place_order.call_args
    assert kwargs['symbol'] == 'AAPL'
    assert kwargs['quantity'] == 10
    assert kwargs['side'] == 'buy'
    # TODO: Check that the price is the mid price
    # (need to mock the mid price func return)
    # assert kwargs['price'] == 100.00
    assert kwargs['order_type'] == 'limit'
    assert kwargs['execution_style'] == 'pegged'


@pytest.mark.asyncio
async def test_reconcile_order_pegged_not_expired(order_manager, mock_db_manager, mock_broker):
    """\n    Test that a pegged order that is not yet expired does not get cancelled\n    and no new order is placed.\n    """
    recent_timestamp = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER - 5)
    pegged_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        symbol="AAPL",
        quantity=10,
        side="buy",
        strategy="test_strategy",
        timestamp=recent_timestamp,
        status="open",
        execution_style="pegged"
    )

    order_manager.place_order = AsyncMock()

    await order_manager.reconcile_order(pegged_order)

    # The pegged order should not be cancelled or replaced because it's not old enough\n    mock_broker.cancel_order.assert_not_called()\n    mock_db_manager.update_trade_status.assert_not_called()\n    order_manager.place_order.assert_not_called()