import unittest
from unittest.mock import patch, MagicMock
from brokers.tastytrade_broker import TastytradeBroker

class TestTastytradeBroker(unittest.TestCase):

    def setUp(self):
        self.broker = TastytradeBroker('api_key', 'secret_key')

    @patch('brokers.tastytrade_broker.requests.post')
    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_response

    @patch('brokers.tastytrade_broker.requests.post')
    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_account_info(self, mock_get, mock_post):
        self.mock_connect(mock_post)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }
        mock_get.return_value = mock_response

        self.broker.connect()
        account_info = self.broker.get_account_info()
        self.assertEqual(account_info, {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        })
        self.assertTrue(hasattr(self.broker, 'session_token'))
        self.assertTrue(hasattr(self.broker, 'headers'))

    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_order_status(self, mock_get):
        self.mock_connect()
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})
        self.assertTrue(hasattr(self.broker, 'session_token'))

    @patch('brokers.tastytrade_broker.requests.post')
    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_place_order(self, mock_post_place_order, mock_get_account_info, mock_post_connect):
        self.mock_connect(mock_post_connect)
        mock_get_account_info.return_value = MagicMock(json=MagicMock(return_value={
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }))
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'filled', 'filled_price': 155.00}
        mock_post_place_order.return_value = mock_response

        self.broker.connect()
        self.broker.get_account_info()
        order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled', 'filled_price': 155.00})
        self.assertTrue(hasattr(self.broker, 'session_token'))

if __name__ == '__main__':
    unittest.main()