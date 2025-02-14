import pytest
import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from strategies.base_strategy import BaseStrategy
from sqlalchemy import select
from database.models import Balance, Position
from sqlalchemy.ext.asyncio import AsyncSession

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, 'test_strategy', 10000)
        self.logger = logging.getLogger(__name__)
        return

    async def rebalance(self):
        self.logger.info("Rebalancing strategy")
        # Implement new order reconciliation features here
        pass

    async def initialize_starting_balance(self):
        async with self.broker.Session() as session:
            query = select(Balance).filter_by(
                strategy=self.strategy_name,
                broker=self.broker.broker_name,
                type='cash'
            ).order_by(Balance.timestamp.desc())
            result = await session.execute(query)
            balance = result.scalar()

            if balance is None:
                self.logger.info("Starting balance not found, initializing")
                balance = Balance(
                    strategy=self.strategy_name,
                    broker=self.broker.broker_name,
                    type='cash',
                    balance=self.starting_capital
                )
                session.add(balance)
                await session.commit()
            else:
                self.logger.info("Starting balance found, no initialization needed")

    def calculate_target_balances(self, total_balance, cash_percentage):
        target_cash_balance = total_balance * cash_percentage
        target_investment_balance = total_balance * (1 - cash_percentage)
        self.logger.debug(f"Target cash balance: {target_cash_balance}, Target investment balance: {target_investment_balance}")
        return target_cash_balance, target_investment_balance

    async def fetch_current_db_positions(self):
        async with self.broker.Session() as session:
            positions = await session.execute(select(Position).filter_by(strategy=self.strategy_name))
            return {position.symbol: position.quantity for position in positions.scalars().all()}

    async def place_order(self, symbol, quantity, action, price):
        if await self.is_market_open():
            self.logger.info(f"Placing order: {symbol}, {quantity}, {action}, {price}")
            await self.broker.place_order(symbol, quantity, action, self.strategy_name, price, 'limit')
        else:
            self.logger.warning("Market is closed, order not placed")

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

# Test cases remain the same, but now with improved logging and code organization