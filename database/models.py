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

    def update_position(self, session):
        position = session.query(Position).filter_by(balance_id=self.balance_id, symbol=self.symbol).first()
        if position:
            position.quantity += self.quantity if self.order_type.lower() == 'buy' else -self.quantity
            position.latest_price = self.executed_price
        else:
            session.add(Position(balance_id=self.balance_id, symbol=self.symbol, quantity=self.quantity, latest_price=self.executed_price))
        session.commit()

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, unique=True)
    value = Column(Float)

    def prevent_day_trading(self, session):
        last_trade = session.query(Trade).filter_by(broker=self.broker).order_by(Trade.timestamp.desc()).first()
        if last_trade and (datetime.utcnow() - last_trade.timestamp).total_seconds() < 86400:
            raise Exception("Day trading is not allowed")

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


In the rewritten code, I have added a method `update_position` to the `Trade` class to streamline position updates in trading logic. I have also added a method `prevent_day_trading` to the `AccountInfo` class to enhance broker functionality with day trading prevention.