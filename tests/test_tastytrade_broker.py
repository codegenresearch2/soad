import unittest
from unittest.mock import patch, MagicMock
from brokers.tastytrade_broker import TastytradeBroker

class TestTastytradeBroker(unittest.TestCase):

    def setUp(self):
        self.broker = TastytradeBroker('api_key', 'secret_key')

    def mock_connect(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'session-token': 'token'}}
        mock_post.return_value = mock_response

    @patch('brokers.tastytrade_broker.requests.post')
    def test_connect(self, mock_post):
        self.mock_connect(mock_post)
        self.broker.connect()
        self.assertTrue(hasattr(self.broker, 'session_token'))
        self.assertTrue(hasattr(self.broker, 'headers'))

    @patch('brokers.tastytrade_broker.requests.get')
    @patch('brokers.tastytrade_broker.requests.post')
    def test_get_account_info(self, mock_post, mock_get):
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
        self.assertEqual(self.broker.account_id, '12345')

    @patch('brokers.tastytrade_broker.requests.post')
    @patch('brokers.tastytrade_broker.requests.get')
    def test_place_order(self, mock_get, mock_post):
        self.mock_connect(mock_post)
        mock_get.return_value = MagicMock(json=MagicMock(return_value={
            'data': {'items': [{'account': {'account_number': '12345'}}]}
        }))
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'filled', 'filled_price': 155.00}
        mock_post.side_effect = [mock_response]

        self.broker.connect()
        self.broker.get_account_info()
        order_info = self.broker.place_order('AAPL', 10, 'buy', 'example_strategy', 150.00)
        self.assertEqual(order_info, {'status': 'filled', 'filled_price': 155.00})

    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_order_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'completed'}
        mock_get.return_value = mock_response

        self.broker.connect()
        order_status = self.broker.get_order_status('order_id')
        self.assertEqual(order_status, {'status': 'completed'})

    @patch('brokers.tastytrade_broker.requests.delete')
    def test_cancel_order(self, mock_delete):
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'cancelled'}
        mock_delete.return_value = mock_response

        self.broker.connect()
        cancel_status = self.broker.cancel_order('order_id')
        self.assertEqual(cancel_status, {'status': 'cancelled'})

    @patch('brokers.tastytrade_broker.requests.get')
    def test_get_options_chain(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {'options': 'chain'}
        mock_get.return_value = mock_response

        self.broker.connect()
        options_chain = self.broker.get_options_chain('AAPL', '2024-12-20')
        self.assertEqual(options_chain, {'options': 'chain'})

if __name__ == '__main__':
    unittest.main()