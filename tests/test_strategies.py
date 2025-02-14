import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from strategies.base_strategy import BaseStrategy
from sqlalchemy import select
from database.models import Balance, Position
from sqlalchemy.ext.asyncio import AsyncSession

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker, execution_style=None):
        super().__init__(broker, 'test_strategy', 10000, execution_style=execution_style)

    async def rebalance(self):
        pass

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
def strategy(broker, execution_style=None):
    return TestBaseStrategy(broker, execution_style=execution_style)

@pytest.mark.asyncio
async def test_initialize_starting_balance_existing(strategy):
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session
    mock_balance = MagicMock()
    mock_balance.balance = 1000
    mock_result = MagicMock()
    mock_result.scalar.return_value = mock_balance
    mock_session.execute.return_value = mock_result
    await strategy.initialize_starting_balance()
    expected_query = select(Balance).filter_by(strategy=strategy.strategy_name, broker=strategy.broker.broker_name, type='cash').order_by(Balance.timestamp.desc())
    mock_session.execute.assert_called_once()
    actual_query = str(mock_session.execute.call_args[0][0])
    expected_query_str = str(expected_query)
    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_initialize_starting_balance_new(strategy):
    mock_session = AsyncMock()
    strategy.broker.Session.return_value.__aenter__.return_value = mock_session
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_session.execute.return_value = mock_result
    await strategy.initialize_starting_balance()
    expected_query = select(Balance).filter_by(strategy=strategy.strategy_name, broker=strategy.broker.broker_name, type='cash').order_by(Balance.timestamp.desc())
    mock_session.execute.assert_called_once()
    actual_query = str(mock_session.execute.call_args[0][0])
    expected_query_str = str(expected_query)
    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
@patch('strategies.base_strategy.datetime')
@patch('strategies.base_strategy.asyncio.iscoroutinefunction')
@patch('strategies.base_strategy.BaseStrategy.should_own')
async def test_sync_positions_with_broker(mock_should_own, mock_iscoroutinefunction, mock_datetime, strategy):
    mock_should_own.return_value = 5
    mock_datetime.utcnow.return_value = datetime(2023, 1, 1)
    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}
    strategy.broker.get_current_price.return_value = 150
    strategy.get_db_positions = AsyncMock(return_value=[])
    mock_iscoroutinefunction.return_value = False
    mock_position = MagicMock()
    mock_position.strategy = None
    mock_position.symbol = 'AAPL'
    session_mock = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [mock_position, None]
    mock_result.scalars.return_value.all.return_value = []
    session_mock.execute.return_value = mock_result
    strategy.broker.Session.return_value.__aenter__.return_value = session_mock
    await strategy.sync_positions_with_broker()
    session_mock.add.assert_called_once()
    session_mock.commit.assert_called_once()

def test_calculate_target_balances(strategy):
    total_balance = 10000
    cash_percentage = 0.2
    target_cash_balance, target_investment_balance = strategy.calculate_target_balances(total_balance, cash_percentage)
    assert target_cash_balance == 2000
    assert target_investment_balance == 8000

@pytest.mark.asyncio
@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
async def skip_test_fetch_current_db_positions(strategy):
    session_mock = strategy.broker.Session.return_value.__enter__.return_value
    session_mock.query.return_value.filter_by.return_value.all.return_value = [MagicMock(symbol='AAPL', quantity=10)]
    positions = await strategy.fetch_current_db_positions()
    assert positions == {'AAPL': 10}

@pytest.mark.asyncio
@patch('strategies.base_strategy.is_market_open', return_value=True)
@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)
async def test_place_order(mock_iscoroutinefunction, mock_is_market_open, strategy):
    strategy.broker.place_order = AsyncMock()
    execution_style = strategy.execution_style if strategy.execution_style else 'limit'
    await strategy.place_order('AAPL', 10, 'buy', 150)
    strategy.broker.place_order.assert_called_once_with('AAPL', 10, 'buy', strategy.strategy_name, 150, execution_style)