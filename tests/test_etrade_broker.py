import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import sessionmaker
from brokers.etrade_broker import EtradeBroker, db

class TestEtradeBroker(unittest.TestCase):

    def setUp(self):
        self.Session = sessionmaker(bind=db.engine)
        self.session = self.Session()
        self.broker = EtradeBroker('api_key', 'secret_key', self.session)

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_response

    @patch('brokers.etrade_broker.requests.get')
    def test_connect_success(self, mock_get):
        self.broker.connect()
        self.assertTrue(hasattr(self.broker, 'auth'))

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_account_info_success(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        }
        mock_get.return_value = mock_response

        self.broker.connect()
        account_info = self.broker.get_account_info()
        self.assertEqual(account_info, {
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        })
        self.assertEqual(self.broker.account_id, '12345')

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_account_info_no_account(self, mock_post, mock_get):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'accountListResponse': {'accounts': []}
        }
        mock_get.return_value = mock_response

        self.broker.connect()
        account_info = self.broker.get_account_info()
        self.assertIsNone(account_info)
        self.assertIsNone(self.broker.account_id)

    @patch('brokers.etrade_broker.requests.post')
    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_place_order_success(self, mock_post_place_order, mock_get_account_info, mock_post_connect):
        self.mock_connect(mock_post_connect)
        mock_get_account_info.return_value = MagicMock(json=MagicMock(return_value={
            'accountListResponse': {'accounts': [{'accountId': '12345'}]}
        }))
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'filled', 'filled_price': 155.00}
        mock_post_place_order.side_effect = [mock_post_connect.return_value, mock_response]

        self.broker.connect()
        self.broker.get_account_info()
        order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled', 'filled_price': 155.00})

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_order_status_success(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_order_status_no_order(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertIsNone(order_status)

    @patch('brokers.etrade_broker.requests.put')
    @patch('brokers.etrade_broker.requests.post')
    def test_cancel_order_success(self, mock_post_connect, mock_put):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_put.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.etrade_broker.requests.put')
    @patch('brokers.etrade_broker.requests.post')
    def test_cancel_order_no_order(self, mock_post_connect, mock_put):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_put.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker.cancel_order('order_id')
        self.assertIsNone(cancel_status)

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_options_chain_success(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        self.broker.connect()
        options_chain = self.broker.get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'options': 'chain'})

    @patch('brokers.etrade_broker.requests.get')
    @patch('brokers.etrade_broker.requests.post')
    def test_get_options_chain_no_chain(self, mock_post_connect, mock_get):
        self.mock_connect(mock_post_connect)
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        self.broker.connect()
        options_chain = self.broker.get_options_chain('AAPL', '2024-12-20')
        self.assertIsNone(options_chain)

    def tearDown(self):
        self.session.close()

if __name__ == '__main__':
    unittest.main()