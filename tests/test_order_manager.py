import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from database.models import Trade
from order_manager.manager import OrderManager, MARK_ORDER_STALE_AFTER, PEGGED_ORDER_CANCEL_AFTER


@pytest_asyncio.fixture
def mock_db_manager():
    """Mock the DBManager."""
    return AsyncMock()


@pytest_asyncio.fixture
def mock_broker():
    """Mock a broker."""
    broker = AsyncMock()
    broker.is_order_filled.return_value = False
    broker.update_positions.return_value = None
    broker.cancel_order.return_value = None
    broker.place_order.return_value = None
    return broker


@pytest_asyncio.fixture
def order_manager(mock_db_manager, mock_broker):
    """Create an instance of OrderManager with mocked dependencies."""
    engine = MagicMock()
    brokers = {"dummy_broker": mock_broker}
    order_manager = OrderManager(engine, brokers)
    order_manager.db_manager = mock_db_manager
    return order_manager


@pytest.mark.asyncio
async def test_reconcile_orders(order_manager, mock_db_manager):
    """Test the reconcile_orders method."""
    # Mock trades
    trades = [
        Trade(id=1, broker="dummy_broker", broker_id="123", status="open"),
        Trade(id=2, broker="dummy_broker", broker_id="456", status="open"),
    ]
    order_manager.reconcile_order = AsyncMock()

    await order_manager.reconcile_orders(trades)

    # Verify that reconcile_order is called for each trade
    order_manager.reconcile_order.assert_any_call(trades[0])
    order_manager.reconcile_order.assert_any_call(trades[1])
    assert order_manager.reconcile_order.call_count == len(trades)


@pytest.mark.asyncio
async def test_reconcile_order_stale(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for stale orders."""
    stale_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id=None,
        timestamp=datetime.utcnow() - timedelta(days=3),
        status="open",
    )

    await order_manager.reconcile_order(stale_order)

    # Verify that the order is marked as stale
    mock_db_manager.update_trade_status.assert_called_once_with(1, "stale")
    mock_broker.is_order_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_order_filled(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for filled orders."""
    filled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style='standard'
    )
    mock_broker.is_order_filled.return_value = True

    await order_manager.reconcile_order(filled_order)

    # Verify that the order is marked as filled and positions are updated
    mock_db_manager.set_trade_filled.assert_called_once_with(1)
    mock_broker.update_positions.assert_called_once_with(1, mock_db_manager.Session().__aenter__.return_value)
    mock_broker.is_order_filled.assert_called_once_with("123")


@pytest.mark.asyncio
async def test_reconcile_order_not_filled(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for orders that are not filled."""
    unfilled_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow(),
        status="open",
        execution_style='pegged'
    )
    mock_broker.is_order_filled.return_value = False

    await order_manager.reconcile_order(unfilled_order)

    # Verify that no changes are made for unfilled orders
    mock_db_manager.set_trade_filled.assert_not_called()
    mock_broker.update_positions.assert_not_called()
    mock_broker.cancel_order.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_order_pegged_cancel(order_manager, mock_db_manager, mock_broker):
    """Test the reconcile_order method for pegged orders that are cancelled."""
    pegged_order = Trade(
        id=1,
        broker="dummy_broker",
        broker_id="123",
        timestamp=datetime.utcnow() - timedelta(seconds=20),
        status="open",
        execution_style='pegged'
    )
    mock_broker.is_order_filled.return_value = False
    mock_broker.cancel_order.return_value = None
    mock_broker.get_mid_price.return_value = 150

    await order_manager.reconcile_order(pegged_order)

    # Verify that the order is cancelled and a new order is placed
    mock_broker.cancel_order.assert_called_once_with("123")
    mock_db_manager.update_trade_status.assert_called_once_with(1, "cancelled")
    mock_broker.place_order.assert_called_once_with(
        symbol=pegged_order.symbol,
        quantity=pegged_order.quantity,
        side=pegged_order.side,
        strategy=pegged_order.strategy,
        price=150,
        order_type='limit',
        execution_style='pegged'
    )


@pytest.mark.asyncio
async def test_run(order_manager, mock_db_manager):
    """Test the run method."""
    trades = [
        Trade(id=1, broker="dummy_broker", broker_id="123", status="open"),
        Trade(id=2, broker="dummy_broker", broker_id="456", status="open"),
    ]
    mock_db_manager.get_open_trades.return_value = trades
    order_manager.reconcile_orders = AsyncMock()

    await order_manager.run()

    # Verify that open trades are fetched and reconciled
    mock_db_manager.get_open_trades.assert_called_once()
    order_manager.reconcile_orders.assert_called_once_with(trades)