import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from strategies.base_strategy import BaseStrategy
from sqlalchemy import select
from database.models import Balance, Position
from sqlalchemy.ext.asyncio import AsyncSession

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker, execution_style='limit'):
        super().__init__(broker, 'test_strategy', 10000, execution_style)
        self.expiration_time = timedelta(minutes=30)
        return

    async def rebalance(self):
        await self.cancel_expired_trades()
        await super().rebalance()

    async def cancel_expired_trades(self):
        open_orders = await self.broker.get_open_orders()
        for order in open_orders:
            if datetime.utcnow() - order.created_at > self.expiration_time:
                await self.broker.cancel_order(order.id)

@pytest.fixture
def broker():
    broker = MagicMock()
    broker.get_account_info = AsyncMock()
    broker.get_account_info.return_value = {'buying_power': 20000}
    session_mock = MagicMock()
    broker.Session.return_value.__enter__.return_value = session_mock
    balance_mock = MagicMock()
    balance_mock.balance = 10000
    session_mock.query.return_value.filter_by.return_value.first.return_value = balance_mock
    return broker

@pytest.fixture
def strategy(broker):
    return TestBaseStrategy(broker, execution_style='market')

# The rest of the code remains the same as it does not need to be modified according to the rules provided.