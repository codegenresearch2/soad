from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

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
    strategy = Column(String, nullable=True)
    profit_loss = Column(Float, nullable=True)
    success = Column(String, nullable=True)
    balance_id = Column(Integer, ForeignKey('balances.id'))

class AccountInfo(Base):
    __tablename__ = 'account_info'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, unique=True)
    value = Column(Float)

class Balance(Base):
    __tablename__ = 'balances'
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String, nullable=False)
    strategy = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    type = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    trades = relationship('Trade', backref='balance')
    positions = relationship("Position", back_populates="balance", foreign_keys='[Position.balance_id]', primaryjoin='Balance.id == Position.balance_id and Position.type == "positions"')

class Position(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    balance_id = Column(Integer, ForeignKey('balances.id'), nullable=False)
    strategy = Column(String, nullable=True)
    broker = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    latest_price = Column(Float, nullable=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    balance = relationship("Balance", back_populates="positions")

def drop_then_init_db(engine):
    Base.metadata.drop_all(engine)  # Drop existing tables
    Base.metadata.create_all(engine)  # Create new tables

def init_db(engine):
    Base.metadata.create_all(engine)  # Create new tables