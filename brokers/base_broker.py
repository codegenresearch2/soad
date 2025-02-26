from abc import ABC, abstractmethod
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import and_
from database.db_manager import DBManager
from database.models import Trade, AccountInfo, Balance, Position
from datetime import datetime

class BaseBroker(ABC):
    def __init__(self, api_key, secret_key, broker_name, engine, prevent_day_trading=False):
        self.api_key = api_key
        self.secret_key = secret_key
        self.broker_name = broker_name
        self.db_manager = DBManager(engine)
        self.Session = sessionmaker(bind=engine)
        self.account_id = None
        self.prevent_day_trading = False

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def _get_account_info(self):
        pass

    @abstractmethod
    def _place_order(self, symbol, quantity, order_type, price=None):
        pass

    @abstractmethod
    def _get_order_status(self, order_id):
        pass

    @abstractmethod
    def _cancel_order(self, order_id):
        pass

    @abstractmethod
    def _get_options_chain(self, symbol, expiration_date):
        pass

    @abstractmethod
    def get_current_price(self, symbol):
        pass

    def get_account_info(self):
        account_info = self._get_account_info()
        self.db_manager.add_account_info(AccountInfo(broker=self.broker_name, value=account_info['value']))
        return account_info

    def has_bought_today(self, symbol):
        today = datetime.now().date()
        with self.Session() as session:
            trades = session.query(Trade).filter(
                and_(
                    Trade.symbol == symbol,
                    Trade.broker == self.broker_name,
                    Trade.order_type == 'buy',
                    Trade.timestamp >= today
                )
            ).all()
            return len(trades) > 0

    def update_positions(self, session, trade):
        position = session.query(Position).filter_by(symbol=trade.symbol, broker=self.broker_name, strategy=trade.strategy).first()

        if trade.order_type == 'buy':
            if position:
                position.quantity += trade.quantity
                position.latest_price = trade.executed_price
                position.timestamp = datetime.now()
            else:
                position = Position(
                    broker=self.broker_name,
                    strategy=trade.strategy,
                    symbol=trade.symbol,
                    quantity=trade.quantity,
                    latest_price=trade.executed_price,
                )
                session.add(position)
        elif trade.order_type == 'sell':
            if position:
                position.quantity -= trade.quantity
                position.latest_price = trade.executed_price
                if position.quantity < 0:
                    raise ValueError("Sell quantity exceeds current position quantity.")

        session.commit()

    def place_order(self, symbol, quantity, order_type, strategy, price=None):
        # Check for day trading
        if self.prevent_day_trading and order_type == 'sell':
            if self.has_bought_today(symbol):
                raise ValueError("Day trading is not allowed. Cannot sell positions opened today.")

        response = self._place_order(symbol, quantity, order_type, price)
        
        trade = Trade(
            symbol=symbol,
            quantity=quantity,
            price=price,
            executed_price=response['filled_price'],
            order_type=order_type,
            status='filled',
            timestamp=datetime.now(),
            broker=self.broker_name,
            strategy=strategy,
            profit_loss=0,
            success='yes'
        )
        
        with self.Session() as session:
            session.add(trade)
            session.commit()

        # Update positions
        self.update_positions(session, trade, order_type)

        return response

    def get_order_status(self, order_id):
        order_status = self._get_order_status(order_id)
        with self.Session() as session:
            trade = session.query(Trade).filter_by(id=order_id).first()
            if trade:
                self.update_trade(session, trade.id, order_status)
        return order_status

    def cancel_order(self, order_id):
        cancel_status = self._cancel_order(order_id)
        with self.Session() as session:
            trade = session.query(Trade).filter_by(id=order_id).first()
            if trade:
                self.update_trade(session, trade.id, cancel_status)
        return cancel_status

    def get_options_chain(self, symbol, expiration_date):
        return self._get_options_chain(symbol, expiration_date)

    def update_trade(self, session, trade_id, order_info):
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if not trade:
            return

        executed_price = order_info.get('filled_price', trade.price)  # Match the correct key
        if executed_price is None:
            executed_price = trade.price  # Ensure we have a valid executed price

        trade.executed_price = executed_price
        profit_loss = self.db_manager.calculate_profit_loss(trade)
        success = "success" if profit_loss > 0 else "failure"

        trade.executed_price = executed_price
        trade.success = success
        trade.profit_loss = profit_loss
        session.commit()
