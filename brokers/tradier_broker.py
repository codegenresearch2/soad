import requests
import time
from brokers.base_broker import BaseBroker
from utils.logger import logger  # Import the logger
from utils.utils import extract_underlying_symbol

class TradierBroker(BaseBroker):
    def __init__(self, api_key, secret_key, engine, **kwargs):
        super().__init__(api_key, secret_key, 'Tradier', engine=engine, **kwargs)
        self.base_url = 'https://api.tradier.com/v1'
        self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
        }
        self.order_timeout = 1
        self.auto_cancel_orders = True
        logger.info('Initialized TradierBroker', extra={'base_url': self.base_url})
        self._get_account_info()

    def connect(self):
        logger.info('Connecting to Tradier API')
        # Placeholder for actual connection logic
        pass

    def _get_account_info(self):
        logger.info('Retrieving account information')
        try:
            response = requests.get(f"{self.base_url}/user/profile", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            self.account_id = account_info['profile']['account']['account_number']
            logger.info('Account info retrieved', extra={'account_id': self.account_id})

            url = f'{self.base_url}/accounts/{self.account_id}/balances'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            account_balances = response.json().get('balances')

            if not account_balances:
                logger.error("Invalid account info response")

            self.account_type = self._determine_account_type(account_balances)
            self.buying_power = self._get_buying_power(account_balances)
            self.account_value = self._get_account_value(account_balances)
            self.cash = self._get_cash(account_balances)

            logger.info('Account balances retrieved', extra={'account_type': self.account_type, 'buying_power': self.buying_power, 'value': self.account_value})
            return {
                'account_number': self.account_id,
                'account_type': self.account_type,
                'buying_power': self.buying_power,
                'cash': self.cash,
                'value': self.account_value
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})

    def _determine_account_type(self, account_balances):
        if account_balances['cash']:
            return 'cash'
        elif account_balances['margin']:
            return 'margin'
        elif account_balances['pdt']:
            return 'pdt'
        else:
            return 'unknown'

    def _get_buying_power(self, account_balances):
        if self.account_type == 'cash':
            return account_balances['cash']['cash_available']
        elif self.account_type == 'margin':
            return account_balances['margin']['stock_buying_power']
        elif self.account_type == 'pdt':
            return account_balances['pdt']['stock_buying_power']
        else:
            return 0

    def _get_account_value(self, account_balances):
        return account_balances['total_equity']

    def _get_cash(self, account_balances):
        return account_balances['total_cash']

    def get_positions(self):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['positions']['position']

            if not isinstance(positions_data, list):
                positions_data = [positions_data]
            positions = {p['symbol']: p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})

    def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            if price is None:
                quote_url = f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['quotes']['quote']
                price = round((quote['bid'] + quote['ask']) / 2, 2)

            order_data = {
                "class": "equity",
                "symbol": symbol,
                "quantity": quantity,
                "side": order_type.upper(),
                "type": "limit",
                "duration": "day",
                "price": price
            }

            response = requests.post(f"{self.base_url}/accounts/{self.account_id}/orders", json=order_data, headers=self.headers)
            response.raise_for_status()

            order_id = response.json()['order']['id']
            logger.info('Order placed', extra={'order_id': order_id})
            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['order']['status']

                if order_status != 'filled':
                    try:
                        cancel_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.put(cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={'order_id': order_id})
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            data = response.json()
            if data.get('filled_price') is None:
                data['filled_price'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _place_future_option_order(self, symbol, quantity, order_type, price=None):
        logger.error('Future options not supported by Tradier', extra={'symbol': symbol})
        raise NotImplementedError

    def _place_option_order(self, symbol, quantity, order_type, price=None):
        ticker = extract_underlying_symbol(symbol)
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        if order_type.lower() == 'buy':
            order_type = 'buy_to_open'
        elif order_type.lower() == 'sell':
            order_type = 'sell_to_close'
        try:
            if price is None:
                quote_url = f"https://api.tradier.com/v1/markets/quotes?symbols={symbol}"
                quote_response = requests.get(quote_url, headers=self.headers)
                quote_response.raise_for_status()
                quote = quote_response.json()['quotes']['quote']
                price = round((quote['bid'] + quote['ask']) / 2, 2)

            order_data = {
                "class": "option",
                "symbol": ticker,
                "option_symbol": symbol,
                "quantity": quantity,
                "side": order_type.upper(),
                "type": "limit",
                "duration": "day",
                "price": price
            }

            response = requests.post(f"{self.base_url}/accounts/{self.account_id}/orders", json=order_data, headers=self.headers)
            response.raise_for_status()

            order_id = response.json()['order']['id']
            logger.info('Order placed', extra={'order_id': order_id})

            if self.auto_cancel_orders:
                time.sleep(self.order_timeout)
                order_status_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}"
                status_response = requests.get(order_status_url, headers=self.headers)
                status_response.raise_for_status()
                order_status = status_response.json()['order']['status']

                if order_status != 'filled':
                    try:
                        cancel_url = f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel"
                        cancel_response = requests.put(cancel_url, headers=self.headers)
                        cancel_response.raise_for_status()
                        logger.info('Order cancelled', extra={'order_id': order_id})
                        return None
                    except requests.RequestException as e:
                        logger.error('Failed to cancel order', extra={'order_id': order_id})

            data = response.json()
            if data.get('filled_price') is None:
                data['filled_price'] = price
            logger.info('Order execution complete', extra={'order_data': data})
            return data
        except requests.RequestException as e:
            logger.error('Failed to place order', extra={'error': str(e)})

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        try:
            response = requests.get(f"{self.base_url}/accounts/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            order_status = response.json()
            logger.info('Order status retrieved', extra={'order_status': order_status})
            return order_status
        except requests.RequestException as e:
            logger.error('Failed to retrieve order status', extra={'error': str(e)})

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        try:
            response = requests.delete(f"{self.base_url}/accounts/orders/{order_id}", headers=self.headers)
            response.raise_for_status()
            cancellation_response = response.json()
            logger.info('Order cancelled successfully', extra={'cancellation_response': cancellation_response})
            return cancellation_response
        except requests.RequestException as e:
            logger.error('Failed to cancel order', extra={'error': str(e)})

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        try:
            response = requests.get(f"{self.base_url}/markets/options/chains?symbol={symbol}&expiration={expiration_date}", headers=self.headers)
            response.raise_for_status()
            options_chain = response.json()
            logger.info('Options chain retrieved', extra={'options_chain': options_chain})
            return options_chain
        except requests.RequestException as e:
            logger.error('Failed to retrieve options chain', extra={'error': str(e)})

    def get_current_price(self, symbol):
        logger.info('Retrieving current price', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}/markets/quotes?symbols={symbol}", headers=self.headers)
            response.raise_for_status()
            last_price = response.json().get('quotes').get('quote').get('last')
            logger.info('Current price retrieved', extra={'symbol': symbol, 'last_price': last_price})
            return last_price
        except requests.RequestException as e:
            logger.error('Failed to retrieve current price', extra={'error': str(e)})

    def get_bid_ask(self, symbol):
        logger.info('Retrieving bid/ask', extra={'symbol': symbol})
        try:
            response = requests.get(f"{self.base_url}/markets/quotes?symbols={symbol}", headers=self.headers)
            response.raise_for_status()
            quote = response.json().get('quotes').get('quote')
            bid = quote.get('bid')
            ask = quote.get('ask')
            logger.info('Bid/ask retrieved', extra={'symbol': symbol, 'bid': bid, 'ask': ask})
            return { 'bid': bid, 'ask': ask }
        except requests.RequestException as e:
            logger.error('Failed to retrieve bid/ask', extra={'error': str(e)})