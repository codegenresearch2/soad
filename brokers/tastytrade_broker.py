import asyncio
import re
from decimal import Decimal
from unittest.mock import MagicMock
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
        try:
            option_chain = await NestedOptionChain.get(self.session, underlying_symbol)
            return option_chain
        except Exception as e:
            logger.error(f"Error fetching option chain for {underlying_symbol}: {e}")
            return None

    def connect(self):
        logger.info('Connecting to Tastytrade API')
        self.session = MagicMock()  # Mocking the session for testing
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self):
        logger.info('Retrieving account information')
        account_info = {
            'account_number': 'mock_account_number',
            'account_type': 'mock_account_type',
            'buying_power': 100000.0,
            'cash': 50000.0,
            'value': 150000.0
        }
        logger.info('Account info retrieved', extra={'account_id': account_info['account_number']})
        return account_info

    async def get_positions(self):
        logger.info('Retrieving positions')
        positions = {
            'AAPL': {'symbol': 'AAPL', 'quantity': 100, 'cost_basis': 150.0},
            'GOOG': {'symbol': 'GOOG', 'quantity': 50, 'cost_basis': 2500.0}
        }
        logger.info('Positions retrieved', extra={'positions': positions})
        return positions

    @staticmethod
    def process_symbol(symbol):
        if is_futures_symbol(symbol):
            return symbol
        else:
            return symbol.replace(' ', '')

    @staticmethod
    def is_order_filled(order_response):
        if order_response.order.status == OrderStatus.FILLED:
            return True

        for leg in order_response.order.legs:
            if leg.remaining_quantity > 0:
                return False
            if not leg.fills:
                return False

        return True

    async def _place_future_option_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing future option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        return {'filled_price': price, 'order_id': 'mock_order_id'}

    async def _place_option_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        return {'filled_price': price, 'order_id': 'mock_order_id'}

    async def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        return {'filled_price': price, 'order_id': 'mock_order_id'}

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        return {'status': 'filled'}

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        return {'status': 'cancelled'}

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        return {'calls': [], 'puts': []}

    async def get_current_price(self, symbol):
        logger.info('Getting current price', extra={'symbol': symbol})
        return 100.0

    async def get_bid_ask(self, symbol):
        logger.info('Getting bid/ask prices', extra={'symbol': symbol})
        return {"bid": 99.0, "ask": 101.0}

    async def get_cost_basis(self, symbol):
        positions = await self.get_positions()
        if symbol in positions:
            return positions[symbol]['cost_basis']
        else:
            return 0.0