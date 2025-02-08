import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from data.sync_worker import PositionService, BalanceService, BrokerService, _get_async_engine, _run_sync_worker_iteration, _fetch_and_update_positions, _reconcile_brokers_and_update_balances
from database.models import Position, Balance

# Mock data for testing
MOCK_POSITIONS = [
    Position(symbol='AAPL', broker='tradier', latest_price=0, last_updated=datetime.now(), underlying_volatility=None),
    Position(symbol='GOOG', broker='tastytrade', latest_price=0, last_updated=datetime.now(), underlying_volatility=None),
]

MOCK_BALANCE = Balance(broker='tradier', strategy='RSI', type='cash', balance=10000.0, timestamp=datetime.now())

@pytest.mark.asyncio
async def test_update_position_prices_and_volatility():
    # Mock the broker service
    mock_broker_service = AsyncMock()
    mock_broker_service.get_latest_price = AsyncMock(return_value=150.0)  # Ensure it's async

    # Initialize PositionService with the mocked broker service
    position_service = PositionService(mock_broker_service)

    # Mock session and positions
    mock_session = AsyncMock(spec=AsyncSession)
    mock_positions = MOCK_POSITIONS

    # Test the method
    timestamp = datetime.now(timezone.utc)
    await position_service.update_position_prices_and_volatility(mock_session, mock_positions, timestamp)

    # Assert that the broker service was called to get the latest price for each position
    mock_broker_service.get_latest_price.assert_any_call('tradier', 'AAPL')
    mock_broker_service.get_latest_price.assert_any_call('tastytrade', 'GOOG')

    # Assert that the session commit was called
    assert mock_session.commit.called

@pytest.fixture
def broker_service():
    brokers = {
        'mock_broker': MagicMock()
    }
    return BrokerService(brokers)

@pytest.fixture
def position_service(broker_service):
    return PositionService(broker_service)

@pytest.fixture
def balance_service(broker_service):
    return BalanceService(broker_service)

@pytest.mark.asyncio
async def test_get_broker_instance(broker_service):
    broker_instance = await broker_service.get_broker_instance('mock_broker')
    assert broker_instance == broker_service.brokers['mock_broker']

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_get_latest_price_async(mock_logger, broker_service):
    mock_broker = MagicMock()
    mock_broker.get_current_price = AsyncMock(return_value=100)
    broker_service.get_broker_instance = AsyncMock(return_value=mock_broker)
    price = await broker_service.get_latest_price('mock_broker', 'AAPL')
    assert price == 100
    mock_broker.get_current_price.assert_awaited_once_with('AAPL')

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_position_price(mock_logger, position_service):
    mock_session = AsyncMock(spec=AsyncSession)
    mock_position = Position(symbol='AAPL', broker='mock_broker', quantity=10)
    position_service.broker_service.get_latest_price = AsyncMock(return_value=150)
    position_service._get_underlying_symbol = MagicMock(return_value='AAPL')
    position_service._calculate_historical_volatility = AsyncMock(return_value=0.2)
    await position_service._update_position_price(mock_session, mock_position, datetime.now())
    assert mock_position.latest_price == 150
    assert mock_position.underlying_volatility == 0.2
    assert mock_session.commit.called

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_strategy_balance(mock_logger, balance_service):
    mock_session = AsyncMock(spec=AsyncSession)
    await balance_service.update_strategy_balance(mock_session, 'mock_broker', 'strategy1', datetime.now())
    assert mock_session.add.called  # Check that session.add was called to add a new balance record
    assert mock_session.commit.called

@pytest.mark.asyncio
@patch('data.sync_worker.logger')
async def test_update_uncategorized_balances(mock_logger, balance_service):
    mock_session = AsyncMock(spec=AsyncSession)
    balance_service.broker_service.get_account_info = AsyncMock(return_value={'value': 1000})
    balance_service._sum_all_strategy_balances = AsyncMock(return_value=800)
    await balance_service.update_uncategorized_balances(mock_session, 'mock_broker', datetime.now())
    assert mock_session.add.called  # Check that a new balance record was added
    assert mock_session.commit.called  # Ensure the session was committed
