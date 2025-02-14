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
        self.engine = engine
        self.db_manager = DBManager(engine)
        self.brokers = brokers

    async def reconcile_orders(self, orders):
        for order in orders:
            await self.reconcile_order(order)

    async def reconcile_order(self, order):
        stale_threshold = datetime.utcnow() - timedelta(seconds=MARK_ORDER_STALE_AFTER)
        if order.timestamp < stale_threshold and order.status not in ['filled', 'cancelled']:
            try:
                await self.db_manager.update_trade_status(order.id, 'stale')
                return
            except Exception as e:
                logger.error(f'Error marking order {order.id} as stale', extra={'error': str(e)})
                return

        broker = self.brokers[order.broker]
        if order.broker_id is None:
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
                    await broker.cancel_order(order.broker_id)
                    await self.db_manager.update_trade_status(order.id, 'cancelled')
                    mid_price = await broker.get_mid_price(order.symbol)
                    await self.place_order(
                        order.symbol, order.quantity, order.side, order.strategy_name, round(mid_price, 2), order_type='limit', execution_style=order.execution_style
                    )
                except Exception as e:
                    logger.error(f'Error cancelling pegged order {order.id}', extra={'error': str(e)})

    async def run(self):
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

@pytest.mark.asyncio
async def test_reconcile_order_pegged_expired(order_manager, mock_db_manager, mock_broker):
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

    order_manager.place_order = AsyncMock()

    await order_manager.reconcile_order(pegged_order)

    mock_broker.cancel_order.assert_called_once_with("123")
    mock_db_manager.update_trade_status.assert_called_once_with(1, "cancelled")
    order_manager.place_order.assert_called_once_with(
        "AAPL", 10, "buy", "test_strategy", 100.0, order_type='limit', execution_style='pegged'
    )

@pytest.mark.asyncio
async def test_reconcile_order_pegged_not_expired(order_manager, mock_db_manager, mock_broker):
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

    mock_broker.cancel_order.assert_not_called()
    mock_db_manager.update_trade_status.assert_not_called()
    order_manager.place_order.assert_not_called()

@pytest.mark.asyncio
async def test_reconcile_order_with_execution_style(order_manager, mock_db_manager, mock_broker):
    recent_order = Trade(
        id=2,
        broker="dummy_broker",
        broker_id="456",
        symbol="TSLA",
        quantity=5,
        side="sell",
        strategy="test_strategy",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style="some_custom_style"
    )
    mock_broker.is_order_filled.return_value = False

    await order_manager.reconcile_order(recent_order)

    mock_db_manager.set_trade_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()

@pytest.mark.asyncio
async def test_reconcile_order_stale(order_manager, mock_db_manager, mock_broker):
    stale_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id=None,
        timestamp=datetime.utcnow() - timedelta(days=3),
        status="open",
        execution_style="pegged"
    )

    await order_manager.reconcile_order(stale_order)

    mock_db_manager.update_trade_status.assert_called_once_with(1, "stale")
    mock_broker.is_order_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()

@pytest.mark.asyncio
async def test_reconcile_order_filled(order_manager, mock_db_manager, mock_broker):
    filled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style="pegged"
    )
    mock_broker.is_order_filled.return_value = True

    await order_manager.reconcile_order(filled_order)

    mock_db_manager.set_trade_filled.assert_called_once_with(1)
    mock_broker.update_positions.assert_called_once_with(1, mock_db_manager.Session().__aenter__.return_value)

@pytest.mark.asyncio
async def test_reconcile_order_not_filled(order_manager, mock_db_manager, mock_broker):
    unfilled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style="pegged"
    )
    mock_broker.is_order_filled.return_value = False

    await order_manager.reconcile_order(unfilled_order)

    mock_db_manager.set_trade_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()