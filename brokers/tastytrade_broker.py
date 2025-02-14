import unittest.mock as mock
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
    def __init__(self, username, password, engine, positions=[], **kwargs):
        super().__init__('Tastytrade', engine=engine, **kwargs)
        self.base_url = 'https://api.tastytrade.com'
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.order_timeout = 1
        self.auto_cancel_orders = True
        self.session = mock.MagicMock()
        self.account_id = 'mock_account_id'
        self.positions = positions

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
        self.session = Session('mock_username', 'mock_password')
        logger.info('Connected to Tastytrade API')

    def _get_account_info(self):
        logger.info('Retrieving account information')
        account_data = {'equity-buying-power': 100000, 'net-liquidating-value': 100000, 'cash-balance': 50000}
        buying_power = account_data['equity-buying-power']
        account_value = account_data['net-liquidating-value']
        cash = account_data.get('cash-balance')
        logger.info('Account balances retrieved', extra={'buying_power': buying_power, 'value': account_value})
        return {'buying_power': float(buying_power), 'cash': float(cash), 'value': float(account_value)}

    def get_positions(self):
        logger.info('Retrieving positions')
        positions = {self.process_symbol(p['symbol']): p for p in self.positions}
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
        if price is None:
            price = await self.get_current_price(symbol)
            price = round(price * 4) / 4
            logger.info('Price not provided, using mid from current bid/ask', extra={'price': price})
        response = mock.MagicMock()
        return response

    async def _place_option_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing option order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        if ' ' not in symbol:
            symbol = self.format_option_symbol(symbol)
        if price is None:
            price = await self.get_current_price(symbol)
        response = mock.MagicMock()
        return response

    async def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        if price is None:
            price = round(await self.get_current_price(symbol), 2)
        response = mock.MagicMock()
        return {'filled_price': price, 'order_id': getattr(response, 'id', 0)}

    def _get_order_status(self, order_id):
        logger.info('Retrieving order status', extra={'order_id': order_id})
        return {'status': 'filled'}

    def _cancel_order(self, order_id):
        logger.info('Cancelling order', extra={'order_id': order_id})
        return {'success': True}

    def _get_options_chain(self, symbol, expiration_date):
        logger.info('Retrieving options chain', extra={'symbol': symbol, 'expiration_date': expiration_date})
        return {'options_chain': 'mock_options_chain'}

    async def get_current_price(self, symbol):
        if ':' in symbol:
            pass
        elif is_futures_symbol(symbol):
            logger.info('Getting current price for futures symbol', extra={'symbol': symbol})
            option = FutureOption.get_future_option(self.session, symbol)
            symbol = option.streamer_symbol
        elif is_option(symbol):
            if ' ' not in symbol:
                symbol = self.format_option_symbol(symbol)
            if '.' not in symbol:
                symbol = Option.occ_to_streamer_symbol(symbol)
        async with DXLinkStreamer(self.session) as streamer:
            try:
                subs_list = [symbol]
                await streamer.subscribe(EventType.QUOTE, subs_list)
                quote = await streamer.get_event(EventType.QUOTE)
                return round(float((quote.bidPrice + quote.askPrice) / 2), 2)
            finally:
                await streamer.close()

    async def get_bid_ask(self, symbol):
        if ':' in symbol:
            pass
        elif is_futures_symbol(symbol):
            logger.info('Getting current price for futures symbol', extra={'symbol': symbol})
            option = FutureOption.get_future_option(self.session, symbol)
            symbol = option.streamer_symbol
        elif is_option(symbol):
            if ' ' not in symbol:
                symbol = self.format_option_symbol(symbol)
            if '.' not in symbol:
                symbol = Option.occ_to_streamer_symbol(symbol)
        async with DXLinkStreamer(self.session) as streamer:
            try:
                subs_list = [symbol]
                await streamer.subscribe(EventType.QUOTE, subs_list)
                quote = await streamer.get_event(EventType.QUOTE)
                return {"bid": quote.bidPrice, "ask": quote.askPrice}
            finally:
                await streamer.close()