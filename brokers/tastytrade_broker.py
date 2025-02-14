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
from database.models import Balance, Trade
from sqlalchemy.orm.exc import NoResultFound

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
            cash = account_data.get('cash-balance')

            logger.info('Account balances retrieved', extra={'buying_power': buying_power, 'value': account_value})
            return {
                'account_number': self.account_id,
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
            positions = {self.process_symbol(p['symbol']): {'quantity': p['quantity'], 'cost_basis': p['cost-basis']} for p in positions_data}
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
        if is_futures_symbol(symbol):
            return symbol
        else:
            return symbol.replace(' ', '')

    async def _place_order(self, symbol, quantity, order_type, price=None, strategy_name=None):
        logger.info('Placing order', extra={'symbol': symbol, 'quantity': quantity, 'order_type': order_type, 'price': price, 'strategy_name': strategy_name})
        try:
            last_price = await self.get_current_price(symbol)

            if price is None:
                price = round(last_price, 2)

            quantity = Decimal(quantity)
            price = Decimal(price)

            if order_type.lower() == 'buy':
                action = OrderAction.BUY_TO_OPEN
                price_effect = PriceEffect.DEBIT
            elif order_type.lower() == 'sell':
                action = OrderAction.SELL_TO_CLOSE
                price_effect = PriceEffect.CREDIT
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            account = Account.get_account(self.session, self.account_id)
            symbol = Equity.get_equity(self.session, symbol)
            leg = symbol.build_leg(quantity, action)

            order = NewOrder(
                time_in_force=OrderTimeInForce.DAY,
                order_type=OrderType.LIMIT,
                legs=[leg],
                price=price,
                price_effect=price_effect
            )

            response = account.place_order(self.session, order, dry_run=False)

            if getattr(response, 'errors', None):
                logger.error('Order placement failed with no order ID', extra={'response': str(response)})
                return {'filled_price': None }
            else:
                if self.is_order_filled(response):
                    logger.info('Order filled', extra={'response': str(response)})
                    self.update_balance(symbol.symbol, quantity, price, order_type, strategy_name)
                    self.update_trade(symbol.symbol, quantity, price, order_type, strategy_name)
                else:
                    logger.info('Order likely still open', extra={'order_data': response})
                return {'filled_price': price, 'order_id': getattr(response, 'id', 0) }

        except Exception as e:
            logger.error('Failed to place order', extra={'error': str(e)})
            return {'filled_price': None }

    def update_balance(self, symbol, quantity, price, order_type, strategy_name):
        with self.engine.connect() as connection:
            try:
                balance = connection.execute(Balance.select().where(
                    (Balance.strategy == strategy_name) &
                    (Balance.broker == self.broker_name) &
                    (Balance.type == 'cash')
                ).order_by(Balance.timestamp.desc()).limit(1)).fetchone()

                if not balance:
                    logger.error(f"Strategy balance not initialized for {strategy_name} strategy on {self.broker_name}.")
                    raise NoResultFound(f"Strategy balance not initialized for {strategy_name} strategy on {self.broker_name}.")

                if order_type.lower() == 'buy':
                    new_balance = balance.balance - (quantity * price)
                elif order_type.lower() == 'sell':
                    new_balance = balance.balance + (quantity * price)

                connection.execute(Balance.insert().values(
                    strategy=strategy_name,
                    broker=self.broker_name,
                    type='cash',
                    balance=new_balance
                ))

            except Exception as e:
                logger.error('Failed to update balance', extra={'error': str(e)})

    def update_trade(self, symbol, quantity, price, order_type, strategy_name):
        with self.engine.connect() as connection:
            try:
                connection.execute(Trade.insert().values(
                    broker=self.broker_name,
                    symbol=symbol,
                    strategy=strategy_name,
                    order_type=order_type,
                    price=price,
                    quantity=quantity
                ))

            except Exception as e:
                logger.error('Failed to update trade', extra={'error': str(e)})

    # Other methods remain the same