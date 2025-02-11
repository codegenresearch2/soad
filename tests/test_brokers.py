import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from brokers.base_broker import BaseBroker
from database.models import Trade, Balance

class MockBroker(BaseBroker):
    def __init__(self, api_key, secret_key, broker_name, engine):
        super().__init__(api_key, secret_key, broker_name, engine)

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
        trade = Trade(
            symbol=trade_data['symbol'],
            quantity=trade_data['quantity'],
            price=trade_data['price'],
            executed_price=trade_data['executed_price'],
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
            balance.total_balance = balance.total_balance + (trade_data['quantity'] * trade_data['executed_price'])
        else:
            balance = Balance(
                broker=trade_data['broker'],
                strategy=trade_data['strategy'],
                total_balance=trade_data['quantity'] * trade_data['executed_price']
            )
            session.add(balance)
        session.commit()

class TestTrading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        init_db(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.session = self.Session()
        # Additional setup for fake trades
        fake_trades = [
            Trade(symbol='MSFT', quantity=8, price=200.0, executed_price=202.0, order_type='buy', status='executed', timestamp=datetime.utcnow(), broker='Tastytrade', strategy='RSI', profit_loss=16.0, success='yes'),
        ]
        self.session.add_all(fake_trades)
        self.session.commit()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    @patch('requests.post')
    @patch('requests.get')
    def test_execute_trade_updates_trade_and_balance(self, mock_get, mock_post):
        # Example trade data
        trade_data = {
            'symbol': 'AAPL',
            'quantity': 10,
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
        broker = MockBroker('api_key', 'secret_key', 'E*TRADE', self.engine)
        broker.execute_trade(self.session, trade_data)

        # Verify the trade was inserted
        trade = self.session.query(Trade).filter_by(symbol='AAPL').first()
        self.assertIsNotNone(trade)

        # Verify the balance was updated
        balance = self.session.query(Balance).filter_by(broker='E*TRADE', strategy='SMA').first()
        self.assertIsNotNone(balance)
        self.assertEqual(balance.total_balance, 1510.0)

if __name__ == '__main__':
    unittest.main()