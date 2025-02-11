import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from database.models import Trade, Balance
from .base_test import BaseTest
from brokers.base_broker import BaseBroker

class MockBroker(BaseBroker):
    def connect(self):
        pass

    def _get_account_info(self):
        return {'profile': {'account': {'account_number': '12345', 'value': 10000.0}}}

    def _place_order(self, symbol, quantity, order_type, price=None):
        return {'status': 'filled', 'filled_price': 151.0}

    def _get_order_status(self, order_id):
        return {'status': 'completed'}

    def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}

    def get_current_price(self, symbol):
        return 150.0

    def execute_trade(self, session, trade_data):
        # Day trading prevention logic
        if trade_data['quantity'] > 5:
            raise ValueError("Day trading limit exceeded")

        # Place the order
        order_info = self._place_order(trade_data['symbol'], trade_data['quantity'], trade_data['order_type'], trade_data['price'])

        # Insert the trade into the database
        trade = Trade(
            symbol=trade_data['symbol'],
            quantity=trade_data['quantity'],
            price=trade_data['price'],
            executed_price=order_info['filled_price'],
            order_type=trade_data['order_type'],
            status=trade_data['status'],
            timestamp=trade_data['timestamp'],
            broker=trade_data['broker'],
            strategy=trade_data['strategy'],
            profit_loss=trade_data['profit_loss'],
            success=trade_data['success']
        )
        session.add(trade)
        session.commit()

        # Update the balance
        balance = session.query(Balance).filter_by(broker=trade_data['broker'], strategy=trade_data['strategy']).first()
        if balance:
            balance.total_balance += trade_data['quantity'] * order_info['filled_price']
        else:
            balance = Balance(
                broker=trade_data['broker'],
                strategy=trade_data['strategy'],
                total_balance=trade_data['quantity'] * order_info['filled_price']
            )
            session.add(balance)
        session.commit()

class TestTrading(BaseTest):
    def setUp(self):
        super().setUp()  # Call the setup from BaseTest
        self.broker = MockBroker('api_key', 'secret_key', 'E*TRADE', engine=self.engine)

    @patch('brokers.base_broker.BaseBroker._place_order', return_value={'status': 'filled', 'filled_price': 151.0})
    @patch('brokers.base_broker.BaseBroker._get_account_info', return_value={'profile': {'account': {'account_number': '12345', 'value': 10000.0}}})
    def test_execute_trade_with_correct_balance_update(self, mock_get_account_info, mock_place_order):
        # Example trade data
        trade_data = {
            'symbol': 'AAPL',
            'quantity': 5,
            'price': 150.0,
            'executed_price': 151.0,
            'order_type': 'buy',
            'status': 'executed',
            'timestamp': datetime.utcnow(),
            'broker': 'E*TRADE',
            'strategy': 'SMA',
            'profit_loss': 10.0,
            'success': 'yes'
        }

        # Execute the trade
        self.broker.execute_trade(self.session, trade_data)

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated correctly
        balance = self.session.query(Balance).filter_by(broker='E*TRADE', strategy='SMA').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 755.0)  # Expected balance after the trade

if __name__ == '__main__':
    unittest.main()