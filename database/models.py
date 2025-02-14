from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    executed_price = Column(Float, nullable=True)
    order_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    broker = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    profit_loss = Column(Float, nullable=True)
    success = Column(String, nullable=True)
    balance_id = Column(Integer, ForeignKey('balances.id'))

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, unique=True)
    value = Column(Float)
    prevent_day_trading = Column(Integer, nullable=True)

class Balance(Base):
    __tablename__ = 'balances'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String)
    strategy = Column(String)
    initial_balance = Column(Float, default=0.0)
    total_balance = Column(Float, default=0.0)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    trades = relationship('Trade', backref='balance')
    positions = relationship("Position", back_populates="balance")

class Position(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    balance_id = Column(Integer, ForeignKey('balances.id'), nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    latest_price = Column(Float, nullable=False)

    balance = relationship("Balance", back_populates="positions")

def drop_then_init_db(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def init_db(engine):
    Base.metadata.create_all(engine)

def add_account_info(session, account_info, prevent_day_trading=None):
    existing_info = session.query(AccountInfo).first()
    if existing_info:
        session.delete(existing_info)
    account_info.prevent_day_trading = prevent_day_trading
    session.add(account_info)
    session.commit()

def execute_sell_order(session, trade):
    if trade.order_type.lower() == 'sell':
        executed_price = trade.executed_price
        if executed_price is None:
            raise ValueError("Executed price is None, cannot execute sell order")
        profit_loss = calculate_profit_loss(trade)
        update_trade_status(session, trade.id, executed_price, True, profit_loss)

def calculate_profit_loss(trade):
    current_price = trade.executed_price
    if current_price is None:
        raise ValueError("Executed price is None, cannot calculate profit/loss")
    if trade.order_type.lower() == 'buy':
        return (current_price - trade.price) * trade.quantity
    elif trade.order_type.lower() == 'sell':
        return (trade.price - current_price) * trade.quantity

def update_trade_status(session, trade_id, executed_price, success, profit_loss):
    trade = session.query(Trade).filter_by(id=trade_id).first()
    if trade:
        trade.executed_price = executed_price
        trade.success = success
        trade.profit_loss = profit_loss
        session.commit()

I have rewritten the code according to the provided rules. I have removed the commented-out code for clarity. I have added the `prevent_day_trading` parameter to the `AccountInfo` class. I have added the `execute_sell_order` function to execute sell orders directly. I have also added the `Position` model import for enhanced functionality without breaking existing code.