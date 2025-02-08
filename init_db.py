from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime\"from sqlalchemy.ext.declarative import declarative_base\"from sqlalchemy.orm import sessionmaker\"from datetime import datetime, timedelta\"import random\\nDATABASE_URL = "sqlite:///trading.db"\"engine = create_engine(DATABASE_URL)\"Session = sessionmaker(bind=engine)\"Base = declarative_base()\"\n\nclass Trade(Base):\"__tablename__ = 'trades'\"id = Column(Integer, primary_key=True)\"symbol = Column(String, nullable=False)\"quantity = Column(Integer, nullable=False)\"price = Column(Float, nullable=False)\"executed_price = Column(Float, nullable=True)\"order_type = Column(String, nullable=False)\"status = Column(String, nullable=False)\"timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\"broker = Column(String, nullable=False)\"strategy = Column(String, nullable=False)\"profit_loss = Column(Float, nullable=True)\"success = Column(String, nullable=True)\"\nclass Balance(Base):\"__tablename__ = 'balances'\"id = Column(Integer, primary_key=True, autoincrement=True)\"broker = Column(String)\"strategy = Column(String)\"initial_balance = Column(Float, default=0.0)\"total_balance = Column(Float, default=0.0)\"timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\"trades = relationship('Trade', backref='balance')\"positions = relationship('Position', back_populates='balance')\"\nclass Position(Base):\"__tablename__ = 'positions'\"id = Column(Integer, primary_key=True, autoincrement=True)\"balance_id = Column(Integer, ForeignKey('balances.id'), nullable=True)\"strategy = Column(String)\"broker = Column(String, nullable=False)\"symbol = Column(String, nullable=False)\"quantity = Column(Float, nullable=False)\"latest_price = Column(Float, nullable=False)\"last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)\"balance = relationship('Balance', back_populates='positions')\"\nclass AccountInfo(Base):\"__tablename__ = 'account_info'\"id = Column(Integer, primary_key=True, autoincrement=True)\"broker = Column(String, unique=True)\"value = Column(Float)\"\n\n# Function to initialize the database\ndef init_db(engine):\"Base.metadata.create_all(engine)\"\n\n# Initialize the database with fresh data\ninit_db(engine)\n\n# Define brokers and strategies\nbrokers = ['E*TRADE', 'Tradier', 'Tastytrade']\nstrategies = ['SMA', 'EMA', 'RSI', 'Bollinger Bands', 'MACD', 'VWAP', 'Ichimoku']\n\n# Generate unique hourly timestamps for the past 5 days\nstart_date = datetime.utcnow() - timedelta(days=5)\nend_date = datetime.utcnow()\ntimestamps = [start_date + timedelta(hours=i) for i in range((end_date - start_date).days * 24)]\n\n# Generate fake trade data\nnum_trades_per_hour = 1  # Number of trades per hour\nfake_trades = []\n\nprint("Generating fake trade data...")\nfor timestamp in timestamps:\n for _ in range(num_trades_per_hour):\n fake_trades.append(Trade(\n symbol=random.choice(['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']), \n quantity=random.randint(1, 20), \n price=random.uniform(100, 3000), \n executed_price=random.uniform(100, 3000), \n order_type=random.choice(['buy', 'sell']), \n status='executed', \n timestamp=timestamp, \n broker=random.choice(brokers), \n strategy=random.choice(strategies), \n profit_loss=random.uniform(-100, 100), \n success=random.choice(['yes', 'no'])\n ))\nprint('Fake trade data generation completed.')\n\n# Insert fake trades into the database\nprint('Inserting fake trades into the database...') \nsession = Session()\nsession.add_all(fake_trades)\nsession.commit()\nprint('Fake trades inserted into the database.')\n\n# Generate and insert fake balance data and positions\nprint('Generating and inserting fake balance data and positions...') \nfor broker in brokers:\n for strategy in strategies:\n initial_balance = random.uniform(5000, 20000)\n for timestamp in timestamps:\n total_balance = initial_balance + random.uniform(-1000, 1000)  # Simulate some profit/loss\n balance_record = Balance(\n broker=broker,\n strategy=strategy,\n initial_balance=initial_balance,\n total_balance=total_balance,\n timestamp=timestamp\n )\n session.add(balance_record)\n session.commit()  # Commit each balance record individually\n initial_balance = total_balance  # Update the initial balance for the next timestamp\n print(f\