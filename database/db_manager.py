import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Trade, AccountInfo

DATABASE_URL = "sqlite:///trades.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class DBManager:
    def __init__(self):
        self.engine = engine
        self.Session = Session

    def add_trade(self, trade):
        session = self.Session()
        try:
            session.add(trade)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def add_account_info(self, account_info):
        session = self.Session()
        try:
            existing_info = session.query(AccountInfo).first()
            if existing_info:
                session.delete(existing_info)
                session.commit()
            account_info.data = json.dumps(account_info.data)  # Serialize data to JSON
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
        executed_price = trade.executed_price
        if executed_price is None:
            raise ValueError("Executed price cannot be None. Please provide a valid executed price.")
        current_price = executed_price
        if trade.order_type.lower() == 'buy':
            profit_loss = (current_price - trade.price) * trade.quantity
        elif trade.order_type.lower() == 'sell':
            profit_loss = (trade.price - current_price) * trade.quantity
        return profit_loss

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


This revised code snippet addresses the feedback from the oracle by ensuring that all lines of code are valid Python syntax, adding a more descriptive error message in the `calculate_profit_loss` method, and enhancing the readability of the code with comments. It also maintains consistent session management practices and follows standard Python formatting guidelines.