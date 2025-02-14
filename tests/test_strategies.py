import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import logging
from strategies.base_strategy import BaseStrategy
from sqlalchemy import select
from database.models import Balance, Position
from sqlalchemy.ext.asyncio import AsyncSession

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, 'test_strategy', 10000)
        self.logger = logging.getLogger(__name__)

    async def rebalance(self):
        self.logger.info('Rebalancing...')
        # Add new order reconciliation features here

    async def initialize_starting_balance(self):
        async with self.broker.Session() as session:
            query = select(Balance).filter_by(strategy=self.strategy_name, broker=self.broker.broker_name, type='cash').order_by(Balance.timestamp.desc())
            result = await session.execute(query)
            balance = result.scalar()

            if not balance:
                self.logger.info('Starting balance not found in database. Adding...')
                new_balance = Balance(strategy=self.strategy_name, broker=self.broker.broker_name, type='cash', balance=self.starting_capital)
                session.add(new_balance)
                await session.commit()
            else:
                self.logger.info('Starting balance found in database.')

    def calculate_target_balances(self, total_balance, cash_percentage):
        self.logger.debug(f'Calculating target balances with total balance {total_balance} and cash percentage {cash_percentage}')
        target_cash_balance = total_balance * cash_percentage
        target_investment_balance = total_balance * (1 - cash_percentage)
        return target_cash_balance, target_investment_balance

    async def sync_positions_with_broker(self):
        self.logger.info('Syncing positions with broker...')
        async with self.broker.Session() as session:
            broker_positions = await self.broker.get_positions()
            db_positions = await self.get_db_positions()

            for symbol, data in broker_positions.items():
                if symbol not in db_positions:
                    self.logger.info(f'Position for {symbol} not found in database. Adding...')
                    new_position = Position(strategy=self.strategy_name, symbol=symbol, quantity=data['quantity'])
                    session.add(new_position)
                else:
                    self.logger.info(f'Position for {symbol} found in database.')

            await session.commit()

    async def place_order(self, symbol, quantity, action, price):
        self.logger.info(f'Placing {action} order for {symbol} with quantity {quantity} at price {price}')
        await self.broker.place_order(symbol, quantity, action, self.strategy_name, price, 'limit')

@pytest.fixture
def broker():
    broker = MagicMock()
    broker.get_account_info = AsyncMock(return_value={'buying_power': 20000})
    session_mock = MagicMock()
    broker.Session.return_value.__enter__.return_value = session_mock
    balance_mock = MagicMock()
    balance_mock.balance = 10000
    session_mock.query.return_value.filter_by.return_value.first.return_value = balance_mock
    return broker

@pytest.fixture
def strategy(broker):
    return TestBaseStrategy(broker)

@pytest.mark.asyncio
async def test_initialize_starting_balance(strategy):
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session
    mock_balance = MagicMock()
    mock_balance.balance = 1000
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result
    await strategy.initialize_starting_balance()

@pytest.mark.asyncio
async def test_sync_positions_with_broker(strategy):
    mock_datetime = AsyncMock()
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
    strategy.broker.get_current_price.return_value = 150
    strategy.get_db_positions = AsyncMock(return_value=[])
    session_mock = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    session_mock.execute.return_value = mock_result
    strategy.broker.Session.return_value.__aenter__.return_value = session_mock
    await strategy.sync_positions_with_broker()

@pytest.mark.asyncio
async def test_place_order(strategy):
    strategy.broker.place_order = AsyncMock()
    await strategy.place_order('AAPL', 10, 'buy', 150)