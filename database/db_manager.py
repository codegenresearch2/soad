import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class DBManager:
    def __init__(self, engine):
        self.Session = sessionmaker(bind=engine)

    def add_account_info(self, account_info):
        with self.Session() as session:
            existing_info = session.query(AccountInfo).filter_by(broker=account_info.broker).first()
            if existing_info:
                existing_info.value = account_info.value
            else:
                session.add(account_info)
            session.commit()

    def add_account_info(self, account_info):
        session = self.Session()
        try:
            existing_info = session.query(AccountInfo).first()
            if existing_info:
                session.delete(existing_info)
                session.commit()
            session.add(account_info)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_trade(self, trade_id):
        session = self.Session()
        try:
            return session.query(Trade).filter_by(id=trade_id).first()
        finally:
            session.close()

    def get_all_trades(self):
        session = self.Session()
        try:
            return session.query(Trade).all()
        finally:
            session.close()

    def calculate_profit_loss(self, trade):
        current_price = trade.executed_price
        if current_price is None:
            raise ValueError("Executed price is None, cannot calculate profit/loss")
        if trade.order_type.lower() == 'buy':
            return (current_price - trade.price) * trade.quantity
        elif trade.order_type.lower() == 'sell':
            return (trade.price - current_price) * trade.quantity

    def update_trade_status(self, trade_id, executed_price, success, profit_loss):
        session = self.Session()
        try:
            trade = session.query(Trade).filter_by(id=trade_id).first()
            if trade:
                trade.executed_price = executed_price
                trade.success = success
                trade.profit_loss = profit_loss
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
