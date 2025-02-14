from database.db_manager import DBManager
from utils.logger import logger
from datetime import datetime, timedelta
from sqlalchemy import select
from database.models import Position, Trade

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

    async def reconcile_order(self, order):
        logger.info(f'Reconciling order {order.id}', extra={'order_id': order.id})

        # Calculate the stale threshold
        stale_threshold = datetime.utcnow() - timedelta(seconds=MARK_ORDER_STALE_AFTER)

        # Check if the order is stale
        if order.timestamp < stale_threshold and order.status not in ['filled', 'cancelled']:
            logger.info(f'Marking order {order.id} as stale', extra={'order_id': order.id})
            await self.db_manager.update_trade_status(order.id, 'stale')
            return

        # If the order is not stale, reconcile it
        broker = self.brokers[order.broker]
        if order.broker_id is None:
            logger.info(f'Marking order {order.id} as stale, missing broker_id', extra={'order_id': order.id})
            await self.db_manager.update_trade_status(order.id, 'stale')
            return

        filled = await broker.is_order_filled(order.broker_id)
        if filled:
            async with self.db_manager.Session() as session:
                await self.db_manager.set_trade_filled(order.id)
                await broker.update_positions(order.id, session)
        elif order.execution_style == 'pegged':
            cancel_threshold = datetime.utcnow() - timedelta(seconds=PEGGED_ORDER_CANCEL_AFTER)
            if order.timestamp < cancel_threshold:
                logger.info(f'Cancelling pegged order {order.id}', extra={'order_id': order.id})
                await broker.cancel_order(order.broker_id)
                await self.db_manager.update_trade_status(order.id, 'cancelled')
                mid_price = await broker.get_mid_price(order.symbol)
                await self.place_order(order.symbol, order.quantity, order.side, order.strategy_name, round(mid_price, 2), order_type='limit', execution_style=order.execution_style)

    async def run(self):
        logger.info('Running OrderManager')
        orders = await self.db_manager.get_open_trades()
        await self.reconcile_orders(orders)

    async def place_order(self, symbol, quantity, side, strategy, price=None, order_type='limit', execution_style=''):
        broker = self.brokers[strategy.broker]
        if is_option(symbol):
            return await broker.place_option_order(symbol, quantity, side, strategy, price, order_type, execution_style)
        elif is_futures_symbol(symbol):
            return await broker.place_future_option_order(symbol, quantity, side, strategy, price, order_type, execution_style)
        else:
            return await broker.place_order(symbol, quantity, side, strategy, price, order_type, execution_style)

async def run_order_manager(engine, brokers):
    order_manager = OrderManager(engine, brokers)
    await order_manager.run()


In the provided code snippet, the `reconcile_order` function has been updated to include handling for pegged orders. The code checks if the order is pegged and if it is older than `PEGGED_ORDER_CANCEL_AFTER` seconds. If the order is pegged and older than `PEGGED_ORDER_CANCEL_AFTER` seconds, it cancels the order, marks it as cancelled in the database, and places a new limit order at the mid price. The `place_order` function has also been added to handle placing orders based on the symbol type.

The user prefers to add new tests for pegged orders, so additional test cases have been added in the provided test code snippet to cover pegged order scenarios. The user also prefers to ensure `execution_style` is handled correctly, so test cases have been added to verify that orders with different execution styles are handled correctly.

The user prefers to maintain consistent mocking practices in tests, so the provided test code snippet follows consistent mocking practices, such as using `AsyncMock` for asynchronous methods and `MagicMock` for the engine.