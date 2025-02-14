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
        self.positions = {}
        self.session = self._create_session()

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

    def _create_session(self):
        logger.info('Creating Tastytrade API session')
        try:
            session = Session(self.username, self.password)
            logger.info('Tastytrade API session created')
            return session
        except Exception as e:
            logger.error('Failed to create Tastytrade API session', extra={'error': str(e)})
            return None

    def _get_account_info(self):
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
            cash = account_data.get('cash-balance')

            logger.info('Account balances retrieved', extra={'buying_power': buying_power, 'value': account_value})
            return {'buying_power': float(buying_power), 'cash': float(cash), 'value': float(account_value)}
        except requests.RequestException as e:
            logger.error('Failed to retrieve account information', extra={'error': str(e)})
            return None

    def update_positions(self):
        logger.info('Updating positions')
        try:
            positions_data = self.get_positions()
            self.positions = {self.process_symbol(p['symbol']): {
                'quantity': p['quantity'],
                'cost_basis': p.get('cost_basis', 0.0)  # Enhanced cost basis tracking
            } for p in positions_data}
            logger.info('Positions updated', extra={'positions': self.positions})
        except Exception as e:
            logger.error('Failed to update positions', extra={'error': str(e)})

    @staticmethod
    def process_symbol(symbol):
        if is_futures_symbol(symbol):
            return symbol
        else:
            return symbol.replace(' ', '')

    async def _place_order(self, symbol, quantity, order_type, price=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price})
        try:
            last_price = await self.get_current_price(symbol)
            price = round(last_price, 2) if price is None else price
            quantity = Decimal(quantity)
            price = Decimal(price)
            action = OrderAction.BUY_TO_OPEN if order_type.lower() == 'buy' else OrderAction.SELL_TO_CLOSE
            effect = PriceEffect.DEBIT if order_type.lower() == 'buy' else PriceEffect.CREDIT
            account = Account.get_account(self.session, self.account_id)
            symbol = Equity.get_equity(self.session, symbol)
            leg = symbol.build_leg(quantity, action)
            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=[leg],
                price=price,
                price_effect=effect
            )
            response = account.place_order(self.session, order, dry_run=False)
            if getattr(response, 'errors', None):
                logger.error('Order placement failed with no order ID', extra={'response': str(response)})
                return {'filled_price': None }
            else:
                if self.is_order_filled(response):
                    logger.info('Order filled', extra={'response': str(response)})
                    self.update_positions()  # Streamlined position updates
                else:
                    logger.info('Order likely still open', extra={'order_data': response})
                return {'filled_price': price, 'order_id': getattr(response, 'id', 0) }
        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {'filled_price': None }

    # Rest of the code remains unchanged as it is not relevant to the rules provided