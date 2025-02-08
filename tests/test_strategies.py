import pytest\nimport asyncio\nfrom unittest.mock import MagicMock, patch, AsyncMock\nfrom datetime import datetime\nfrom strategies.base_strategy import BaseStrategy\nfrom sqlalchemy import select\nfrom database.models import Balance, Position\nfrom sqlalchemy.ext.asyncio import AsyncSession\n\nclass TestBaseStrategy(BaseStrategy):\n    def __init__(self, broker):\n        super().__init__(broker, 'test_strategy', 10000)\n        return\n\n    async def rebalance(self):\n        pass\n\n@pytest.fixture\ndef broker():\n    broker = MagicMock()\n\n    # Mock get_account_info to return a dictionary with an integer buying_power\n    broker.get_account_info = AsyncMock()\n    broker.get_account_info.return_value = {'buying_power': 20000}\n\n    # Mock Session and its return value\n    session_mock = MagicMock()\n    broker.Session.return_value.__enter__.return_value = session_mock\n\n    # Mock query result for Balance\n    balance_mock = MagicMock()\n    balance_mock.balance = 10000\n    session_mock.query.return_value.filter_by.return_value.first.return_value = balance_mock\n\n    return broker\n\n@pytest.fixture\ndef strategy(broker):\n    return TestBaseStrategy(broker)\n\n@pytest.mark.asyncio\nasync def test_initialize_starting_balance_existing(strategy):\n    # Mock the async session\n    mock_session = AsyncMock()\n    strategy.broker.Session.return_value.__aenter__.return_value = mock_session\n\n    # Create a mock balance object\n    mock_balance = MagicMock()\n    mock_balance.balance = 1000  # Set an example balance\n\n    # Simulate session.execute() returning a mock result\n    mock_result = MagicMock()\n    mock_result.scalar.return_value = mock_balance\n    mock_session.execute.return_value = mock_result\n\n    # Call the initialize_starting_balance method\n    await strategy.initialize_starting_balance()\n\n    # Build the expected query\n    expected_query = select(Balance).filter_by(\n        strategy=strategy.strategy_name,\n        broker=strategy.broker.broker_name,\n        type='cash'\n    ).order_by(Balance.timestamp.desc())\n\n    # Verify that execute() was called with the correct query using SQL string comparison\n    mock_session.execute.assert_called_once()\n\n    # Compare the SQL representation\n    actual_query = str(mock_session.execute.call_args[0][0])\n    expected_query_str = str(expected_query)\n\n    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"\n\n    # Ensure that the balance was not re-added since it already exists\n    mock_session.add.assert_not_called()\n    mock_session.commit.assert_not_called()\n\n@pytest.mark.asyncio\nasync def test_initialize_starting_balance_new(strategy):\n    # Mock the async session\n    mock_session = AsyncMock()\n    strategy.broker.Session.return_value.__aenter__.return_value = mock_session\n\n    # Simulate session.execute() returning a mock result\n    mock_result = MagicMock()\n    mock_result.scalar.return_value = None\n    mock_session.execute.return_value = mock_result\n\n    # Call the initialize_starting_balance method\n    await strategy.initialize_starting_balance()\n\n    # Build the expected query\n    expected_query = select(Balance).filter_by(\n        strategy=strategy.strategy_name,\n        broker=strategy.broker.broker_name,\n        type='cash'\n    ).order_by(Balance.timestamp.desc())\n\n    # Verify that execute() was called with the correct query using SQL string comparison\n    mock_session.execute.assert_called_once()\n\n    # Compare the SQL representation\n    actual_query = str(mock_session.execute.call_args[0][0])\n    expected_query_str = str(expected_query)\n\n    assert actual_query == expected_query_str, f"Expected query: {expected_query_str}, but got: {actual_query}"\n\n    # Ensure that the balance was not re-added since it already exists\n    mock_session.add.assert_called_once()\n    mock_session.commit.assert_called_once()\n\n@pytest.mark.asyncio\n@patch('strategies.base_strategy.datetime')\n@patch('strategies.base_strategy.asyncio.iscoroutinefunction')\n@patch('strategies.base_strategy.BaseStrategy.should_own')\nasync def test_sync_positions_with_broker(mock_should_own, mock_iscoroutinefunction, mock_datetime, strategy):\n    # Mock method return values\n    mock_should_own.return_value = 5\n    mock_datetime.utcnow.return_value = datetime(2023, 1, 1)\n    strategy.broker.get_positions.return_value = {'AAPL': {'quantity': 10}}\n    strategy.broker.get_current_price.return_value = 150\n    # Mock strategy.get_db_positions to return an empty list\n    strategy.get_db_positions = AsyncMock(return_value=[])\n    mock_iscoroutinefunction.return_value = False\n\n    # Create a mock Position object\n    mock_position = MagicMock()\n    mock_position.strategy = None\n    mock_position.symbol = 'AAPL'\n    # Mock the AsyncSession and session.execute() behavior\n    session_mock = AsyncMock(spec=AsyncSession)\n    # Mock the result of session.execute().scalar() to return the mock_position on the first call\n    mock_result = MagicMock()\n    # Setup the side_effect for scalar() to simulate returning the Position and None on subsequent calls\n    mock_result.scalar.side_effect = [mock_position, None]\n    # Mock the result of scalars().all() to return an empty list\n    mock_result.scalars.return_value.all.return_value = []\n    # Mock session.execute to return the mock result\n    session_mock.execute.return_value = mock_result\n    # Set strategy.broker.Session to return this mocked session\n    strategy.broker.Session.return_value.__aenter__.return_value = session_mock\n\n    # Call the sync_positions_with_broker method\n    await strategy.sync_positions_with_broker()\n\n    # Verify that session.add() and session.commit() are called correctly\n    session_mock.add.assert_called_once()\n    session_mock.commit.assert_called_once()\n\ndef test_calculate_target_balances(strategy):\n    total_balance = 10000\n    cash_percentage = 0.2\n    target_cash_balance, target_investment_balance = strategy.calculate_target_balances(total_balance, cash_percentage)\n    assert target_cash_balance == 2000\n    assert target_investment_balance == 8000\n\n@pytest.mark.asyncio\n@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)\nasync def skip_test_fetch_current_db_positions(strategy):\n    session_mock = strategy.broker.Session.return_value.__enter__.return_value\n    session_mock.query.return_value.filter_by.return_value.all.return_value = [\n        MagicMock(symbol='AAPL', quantity=10)\n    ]\n    positions = await strategy.fetch_current_db_positions()\n    assert positions == {'AAPL': 10}\n\n@pytest.mark.asyncio\n@patch('strategies.base_strategy.is_market_open', return_value=True)\n@patch('strategies.base_strategy.asyncio.iscoroutinefunction', return_value=False)\nasync def test_place_order(mock_iscoroutinefunction, mock_is_market_open, strategy):\n    strategy.broker.place_order = AsyncMock()\n    await strategy.place_order('AAPL', 10, 'buy', 150)\n    strategy.broker.place_order.assert_called_once_with('AAPL', 10, 'buy', strategy.strategy_name, 150, 'limit')\n