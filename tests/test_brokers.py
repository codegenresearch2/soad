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
        return {'status': 'filled', 'filled_price': 150.0}

    def _get_order_status(self, order_id):
        return {'status': 'completed'}

    def _cancel_order(self, order_id):
        return {'status': 'cancelled'}

    def _get_options_chain(self, symbol, expiration_date):
        return {'options': 'chain'}

    def get_current_price(self, symbol):
        return 150.0

    def execute_trade(self, session, trade_data):
        if 'symbol' not in trade_data or 'quantity' not in trade_data or 'executed_price' not in trade_data or 'order_type' not in trade_data or 'status' not in trade_data or 'timestamp' not in trade_data or 'broker' not in trade_data or 'strategy' not in trade_data or 'profit_loss' not in trade_data or 'success' not in trade_data:
            raise ValueError('Invalid trade data')

        order_info = self._place_order(trade_data['symbol'], trade_data['quantity'], trade_data['order_type'], trade_data['price'])

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

        balance = session.query(Balance).filter_by(broker=trade_data['broker'], strategy=trade_data['strategy']).first()
        if balance:
            balance.total_balance = balance.total_balance + (trade_data['quantity'] * order_info['filled_price'])
        else:
            balance = Balance(broker=trade_data['broker'], strategy=trade_data['strategy'], total_balance=(trade_data['quantity'] * order_info['filled_price']))
            session.add(balance)
        session.commit()

class TestTrading(BaseTest):
    def setUp(self):
        super().setUp()  # Call the setup from BaseTest

        additional_fake_trades = [
            Trade(symbol='MSFT', quantity=8, price=200.0, executed_price=202.0, order_type='buy', status='executed', timestamp=datetime.utcnow(), broker='Tastytrade', strategy='RSI', profit_loss=16.0, success='yes'),
        ]
        self.session.add_all(additional_fake_trades)
        self.session.commit()

    @patch('brokers.base_broker.MockBroker.execute_trade', new_callable=MagicMock)
    def test_execute_trade(self, mock_execute_trade):
        trade_data = {
            'symbol': 'AAPL',
            'quantity': 10,
            'executed_price': 151.0,
            'order_type': 'buy',
            'status': 'executed',
            'timestamp': datetime.utcnow(),
            'broker': 'E*TRADE',
            'strategy': 'SMA',
            'profit_loss': 10.0,
            'success': 'yes'
        }

        broker = MockBroker('api_key', 'secret_key', 'E*TRADE', engine=self.engine)
        broker.execute_trade(self.session, trade_data)

        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        balance = self.session.query(Balance).filter_by(broker='E*TRADE', strategy='SMA').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 1510.0)

if __name__ == '__main__':
    unittest.main()