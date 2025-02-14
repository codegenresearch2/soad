import unittest
from unittest.mock import patch, MagicMock
import requests
from brokers.tastytrade_broker import TastytradeBroker

class TestTastytradeBroker(unittest.TestCase):

    def setUp(self):
        self.broker = TastytradeBroker('api_key', 'secret_key')

    @patch('brokers.tastytrade_broker.requests.post')
    def test_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_response

        with self.broker:
            self.broker.connect()
            self.assertIsNotNone(self.broker.session_token)
            self.assertIsNotNone(self.broker.headers)

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_account_info(self, mock_post, mock_get):
        mock_connect_response = MagicMock()
        mock_connect_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_connect_response

        mock_account_response = MagicMock()
        mock_account_response.json.return_value = {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }
        mock_get.return_value = mock_account_response

        with self.broker:
            self.broker.connect()
            account_info = self.broker.get_account_info()
            self.assertEqual(account_info, mock_account_response.json.return_value)
            self.assertEqual(self.broker.account_id, '12345')

    @patch('brokers.tastytrade_broker.requests.post')
    @patch('brokers.tastytrade_broker.requests.get')
    def test_place_order(self, mock_get, mock_post):
        mock_account_response = MagicMock()
        mock_account_response.json.return_value = {
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }
        mock_get.return_value = mock_account_response

        mock_order_response = MagicMock()
        mock_order_response.json.return_value = {'status': 'filled', 'filled_price': 155.00}
        mock_post.return_value = mock_order_response

        with self.broker:
            self.broker.connect()
            self.broker.get_account_info()
            order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
            self.assertEqual(order_info, mock_order_response.json.return_value)

    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_order_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        with self.broker:
            self.broker.connect()
            order_status = self.broker.get_order_status('order_id')
            self.assertEqual(order_status, mock_response.json.return_value)

    @patch('brokers.tastytrade_broker.requests.delete')
    def test_cancel_order(self, mock_delete):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        with self.broker:
            self.broker.connect()
            cancel_status = self.broker.cancel_order('order_id')
            self.assertEqual(cancel_status, mock_response.json.return_value)

    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_options_chain(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        with self.broker:
            self.broker.connect()
            options_chain = self.broker.get_options_chain('AAPL', '2024-12-20')
            self.assertEqual(options_chain, mock_response.json.return_value)

if __name__ == '__main__':
    unittest.main()