import requests
import time
import json
import re
from decimal import Decimal
from brokers.base_broker import BaseBroker
from utils.logger import logger
from utils.utils import extract_underlying_symbol, is_ticker, is_option, is_futures_symbol
from tastytrade import Session, DXLinkStreamer, Account
from tastytrade.instruments import Equity, NestedOptionChain, Option, Future, FutureOption
from tastytrade.dxfeed import EventType
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType, PriceEffect, OrderStatus

class TastytradeBroker(BaseBroker):
    def __init__(self, username, password, engine, **kwargs):
        super().__init__(username, password, 'Tastytrade', engine=engine, **kwargs)
        self.base_url = 'https://api.tastytrade.com'
        self.username = username
        self.password = password
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.order_timeout = 1
        self.auto_cancel_orders = True
        logger.info('Initialized TastytradeBroker', extra={'base_url': self.base_url})
        self.session = None
        self.connect()
        self._get_account_info()

    @staticmethod
    def format_option_symbol(option_symbol):
        match = re.match(r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$', option_symbol)
        if not match:
            raise ValueError("Invalid option symbol format")

        underlying = match.group(1)
        rest_of_symbol = ''.join(match.groups()[1:])
        formatted_symbol = f"{underlying:<6}{rest_of_symbol}"
        return formatted_symbol

    async def get_option_chain(self, underlying_symbol):
        """\n        Fetch the option chain for a given underlying symbol.\n\n        Args:\n            underlying_symbol: The underlying symbol for which to fetch the option chain.\n\n        Returns:\n            An OptionChain object containing the option chain data.\n        """
        try:
            option_chain = await NestedOptionChain.get(self.session, underlying_symbol)
            return option_chain
        except Exception as e:
            logger.error(f"Error fetching option chain for {underlying_symbol}: {e}")
            return None

    def connect(self):
        logger.info('Connecting to Tastytrade API')
        auth_data = {
            "login": self.username,
            "password": self.password,
            "remember-me": True
        }
        response = requests.post(f"{self.base_url}/sessions", json=auth_data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        auth_response = response.json().get('data')
        self.auth = auth_response['session-token']
        self.headers["Authorization"] = self.auth
        # Refresh the session
        self.session = Session(self.username, self.password)
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self, retry=True):
        logger.info('Retrieving account information')
        try:
            response = requests.get(f"{self.base_url}/customers/me/accounts", headers=self.headers)
            response.raise_for_status()
            account_info = response.json()
            account_id = account_info['data']['items'][0]['account']['account-number']
            self.account_id = account_id
            logger.info('Account info retrieved', extra={'account_id': self.account_id})

            response = requests.get(f"{self.base_url}/accounts/{self.account_id}/balances", headers=self.headers)
            response.raise_for_status()
            account_data = response.json().get('data')

            if not account_data:
                logger.error("Invalid account info response")

            buying_power = account_data['equity-buying-power']
            account_value = account_data['net-liquidating-value']
            account_type = None

            # TODO: is this redundant? Can we collapse/remove the above API calls?
            cash = account_data.get('cash-balance')

            logger.info('Account balances retrieved', extra={'account_type': account_type, 'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
                'account_type': account_type,
                'buying_power': float(buying_power),
                'cash': float(cash),
                'value': float(account_value)
            }
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})
            if retry:
                logger.info('Trying to authenticate again')
                self.connect()
                return self._get_account_info(retry=False)

    def get_positions(self, retry=True):
        logger.info('Retrieving positions')
        url = f"{self.base_url}/accounts/{self.account_id}/positions"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            positions_data = response.json()['data']['items']
            positions = {self.process_symbol(p['symbol']): p for p in positions_data}
            logger.info('Positions retrieved', extra={'positions': positions})
            return positions
        except requests.RequestException as e:
            logger.error('Failed to retrieve positions', extra={'error': str(e)})
            if retry:
                logger.info('Trying to authenticate again')
                self.connect()
                return self.get_positions(retry=False)

    @staticmethod
    def process_symbol(symbol):
        # NOTE: Tastytrade API returns options positions with spaces in the symbol.
        # Standardize them here. However this is not worth doing for futures options,
        # since they're the only current broker that supports them.\n        if is_futures_symbol(symbol):\n            return symbol\n        else:\n            return symbol.replace(' ', '')  # Remove spaces from the symbol\n\n    @staticmethod\n    def is_order_filled(order_response):\n        if order_response.order.status == OrderStatus.FILLED:\n            return True\n\n        for leg in order_response.order.legs:\n            if leg.remaining_quantity > 0:\n                return False\n            if not leg.fills:\n                return False\n\n        return True\n\n    async def _place_future_option_order(self, symbol, quantity, order_type, price=None):\n        ticker = extract_underlying_symbol(symbol)\n        logger.info('Placing future option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})\n        option = FutureOption.get_future_option(self.session, symbol)\n        if price is None:\n            price = await self.get_current_price(symbol)\n            price = round(price * 4) / 4\n            logger.info('Price not provided, using mid from current bid/ask', extra={'price': price})\n        if order_type == 'buy':\n            action = OrderAction.BUY_TO_OPEN\n            effect = PriceEffect.DEBIT\n        elif order_type == 'sell':\n            action = OrderAction.SELL_TO_CLOSE\n            effect = PriceEffect.CREDIT\n        account = Account.get_account(self.session, self.account_id)\n        leg = option.build_leg(quantity, action)\n        order = NewOrder(\n            time_in_force=OrderTimeInForce.DAY,\n            order_type=OrderType.LIMIT,\n            legs=[leg],\n            price=Decimal(price),\n            price_effect=effect\n        )\n        response = account.place_order(self.session, order, dry_run=False)\n        return response\n\n    async def _place_option_order(self, symbol, quantity, order_type, price=None):\n        ticker = extract_underlying_symbol(symbol)\n        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})\n        if ' ' not in symbol:\n            symbol = self.format_option_symbol(symbol)\n        if price is None:\n            price = await self.get_current_price(symbol)\n        if order_type == 'buy':\n            action = OrderAction.BUY_TO_OPEN\n            effect = PriceEffect.DEBIT\n        elif order_type == 'sell':\n            action = OrderAction.SELL_TO_CLOSE\n            effect = PriceEffect.CREDIT\n        account = Account.get_account(self.session, self.account_id)\n        option = Option.get_option(self.session, symbol)\n        leg = option.build_leg(quantity, action)\n        order = NewOrder(\n            time_in_force=OrderTimeInForce.DAY,\n            order_type=OrderType.LIMIT,\n            legs=[leg],\n            price=Decimal(price),\n            price_effect=effect\n        )\n        response = account.place_order(self.session, order, dry_run=False)\n        return response\n\n    async def _place_order(self, symbol, quantity, order_type, price=None):\n        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})\n        try:\n            last_price = await self.get_current_price(symbol)\n\n            if price is None:\n                price = round(last_price, 2)\n\n            # Convert to Decimal\n            quantity = Decimal(quantity)\n            price = Decimal(price)\n\n            # Map order_type to OrderAction\n            if order_type.lower() == 'buy':\n                action = OrderAction.BUY_TO_OPEN\n                price_effect = PriceEffect.DEBIT\n            elif order_type.lower() == 'sell':\n                action = OrderAction.SELL_TO_CLOSE\n                price_effect = PriceEffect.CREDIT\n            else:\n                raise ValueError(f"Unsupported order type: {order_type}")\n\n            account = Account.get_account(self.session, self.account_id)\n            symbol = Equity.get_equity(self.session, symbol)\n            leg = symbol.build_leg(quantity, action)\n\n            order = NewOrder(\n                time_in_force=OrderTimeInForce.DAY,  # Changed to DAY from IOC\n                order_type=OrderType.LIMIT,\n                legs=[leg],\n                price=price,\n                price_effect=price_effect\n            )\n\n            response = account.place_order(self.session, order, dry_run=False)\n\n            if getattr(response, 'errors', None):\n                logger.error('Order placement failed with no order ID', extra={'response': str(response)})\n                return {'filled_price': None }\n            else:\n                if self.is_order_filled(response):\n                    logger.info('Order filled', extra={'response': str(response)})\n                else:\n                    logger.info('Order likely still open', extra={'order_data': response})\n                return {'filled_price': price, 'order_id': getattr(response, 'id', 0) }\n\n        except Exception as e:\n            logger.error('Failed to place order', extra={'error': str(e)})\n            return {'filled_price': None }\n\n    def _get_order_status(self, order_id):\n        logger.info('Retrieving order status', extra={'order_id': order_id})\n        try:\n            response = requests.get(f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}", headers=self.headers)\n            response.raise_for_status()\n            order_status = response.json()\n            logger.info('Order status retrieved', extra={'order_status': order_status})\n            return order_status\n        except requests.RequestException as e:\n            logger.error('Failed to retrieve order status', extra={'error': str(e)})\n\n    def _cancel_order(self, order_id):\n        logger.info('Cancelling order', extra={'order_id': order_id})\n        try:\n            response = requests.put(f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}/cancel", headers=self.headers)\n            response.raise_for_status()\n            cancellation_response = response.json()\n            logger.info('Order cancelled successfully', extra={'cancellation_response': cancellation_response})\n            return cancellation_response\n        except requests.RequestException as e:\n            logger.error('Failed to cancel order', extra={'error': str(e)})\n\n    def _get_options_chain(self, symbol, expiration_date):\n        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})\n        try:\n            response = requests.get(f"{self.base_url}/markets/options/chains", params={"symbol": symbol, "expiration": expiration_date}, headers=self.headers)\n            response.raise_for_status()\n            options_chain = response.json()\n            logger.info('Options chain retrieved', extra={'options_chain': options_chain})\n            return options_chain\n        except requests.RequestException as e:\n            logger.error('Failed to retrieve options chain', extra={'error': str(e)})\n\n    async def get_current_price(self, symbol):\n        if ':' in symbol:\n            # Looks like this is already a streamer symbol\n            pass\n        elif is_futures_symbol(symbol):\n            logger.info('Getting current price for futures symbol', extra={'symbol': symbol})\n            option = FutureOption.get_future_option(self.session, symbol)\n            symbol = option.streamer_symbol\n        elif is_option(symbol):\n            # Convert to streamer symbol\n            if ' ' not in symbol:\n                symbol = self.format_option_symbol(symbol)\n            if '.' not in symbol:\n                symbol = Option.occ_to_streamer_symbol(symbol)\n        async with DXLinkStreamer(self.session) as streamer:\n            try:\n                subs_list = [symbol]\n                await streamer.subscribe(EventType.QUOTE, subs_list)\n                quote = await streamer.get_event(EventType.QUOTE)\n                return round(float((quote.bidPrice + quote.askPrice) / 2), 2)\n            finally:\n                await streamer.close()\n\n    async def get_bid_ask(self, symbol):\n        if ':' in symbol:\n            # Looks like this is already a streamer symbol\n            pass\n        elif is_futures_symbol(symbol):\n            logger.info('Getting current price for futures symbol', extra={'symbol': symbol})\n            option = FutureOption.get_future_option(self.session, symbol)\n            symbol = option.streamer_symbol\n        elif is_option(symbol):\n            # Convert to streamer symbol\n            if ' ' not in symbol:\n                symbol = self.format_option_symbol(symbol)\n            if '.' not in symbol:\n                symbol = Option.occ_to_streamer_symbol(symbol)\n        async with DXLinkStreamer(self.session) as streamer:\n            try:\n                subs_list = [symbol]\n                await streamer.subscribe(EventType.QUOTE, subs_list)\n                quote = await streamer.get_event(EventType.QUOTE)\n                return { "bid": quote.bidPrice, "ask": quote.askPrice }\n            finally:\n                await streamer.close()