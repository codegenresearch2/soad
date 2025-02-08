import json\\nfrom sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON\\nfrom sqlalchemy.ext.declarative import declarative_base\\nfrom sqlalchemy.orm import sessionmaker\\nfrom datetime import datetime\\n\\nDATABASE_URL = "sqlite:///trades.db"\\n\\nBase = declarative_base()\\n\\nengine = create_engine(DATABASE_URL)\\nSession = sessionmaker(bind=engine)\\n\\nclass Trade(Base):\\n    __tablename__ = 'trades'\\n    \\n    id = Column(Integer, primary_key=True)\\n    symbol = Column(String, nullable=False)\\n    quantity = Column(Integer, nullable=False)\\n    price = Column(Float, nullable=False)\\n    executed_price = Column(Float, nullable=True)  # Added field for executed price\\n    order_type = Column(String, nullable=False)\\n    status = Column(String, nullable=False)\\n    timestamp = Column(DateTime, nullable=False)\\n    brokerage = Column(String, nullable=False)\\n    strategy = Column(String, nullable=False)\\n    profit_loss = Column(Float, nullable=True)  # Added field for P/L\\n    success = Column(String, nullable=True)     # Added field for success/failure\\n\\nclass AccountInfo(Base):\\n    __tablename__ = 'account_info'\\n    \\n    id = Column(Integer, primary_key=True)\\n    data = Column(String, nullable=False)\\n\\nclass DBManager:\\n    def __init__(self):\\n        self.engine = engine\\n        self.Session = Session\\n\\n    def add_trade(self, trade):\\n        session = self.Session()\\n        try:\\n            session.add(trade)\\n            session.commit()\\n        except Exception as e:\\n            session.rollback()\\n            raise e\\n        finally:\\n            session.close()\\n\\n    def add_account_info(self, account_info):\\n        session = self.Session()\\n        try:\\n            existing_info = session.query(AccountInfo).first()\\n            if existing_info:\\n                session.delete(existing_info)\\n                session.commit()\\n            account_info.data = json.dumps(account_info.data)  # Serialize data to JSON\\n            session.add(account_info)\\n            session.commit()\\n        except Exception as e:\\n            session.rollback()\\n            raise e\\n        finally:\\n            session.close()\\n\\n    def get_trade(self, trade_id):\\n        session = self.Session()\\n        try:\\n            return session.query(Trade).filter_by(id=trade_id).first()\\n        finally:\\n            session.close()\\n\\n    def get_all_trades(self):\\n        session = self.Session()\\n        try:\\n            return session.query(Trade).all()\\n        finally:\\n            session.close()\\n\\n    def calculate_profit_loss(self, trade):\\n        current_price = trade.executed_price\\n        if current_price is None:\\n            raise ValueError("Executed price is not set")\\n        if trade.order_type.lower() == 'buy':\\n            return (current_price - trade.price) * trade.quantity\\n        elif trade.order_type.lower() == 'sell':\\n            return (trade.price - current_price) * trade.quantity\\n\\n    def update_trade_status(self, trade_id, executed_price, success, profit_loss):\\n        session = self.Session()\\n        try:\\n            trade = session.query(Trade).filter_by(id=trade_id).first()\\n            if trade:\\n                trade.executed_price = executed_price\\n                trade.success = success\\n                trade.profit_loss = profit_loss\\n                session.commit()\\n        except Exception as e:\\n            session.rollback()\\n            raise e\\n        finally:\\n            session.close()\\n