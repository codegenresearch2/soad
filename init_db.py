from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, PrimaryKeyConstraint\\nfrom sqlalchemy.ext.declarative import declarative_base\\\nfrom sqlalchemy.orm import sessionmaker, relationship\\\nfrom datetime import datetime, timedelta\\\nimport random\\\\nDATABASE_URL = "sqlite:///trading.db"\\\\\nengine = create_engine(DATABASE_URL)\\\\\nSession = sessionmaker(bind=engine)\\\\\nsession = Session()\\\\nBase = declarative_base()\\\\nclass Trade(Base):\\n    __tablename__ = 'trades'\\n    id = Column(Integer, primary_key=True)\\n    symbol = Column(String, nullable=False)\\n    quantity = Column(Integer, nullable=False)\\n    price = Column(Float, nullable=False)\\n    executed_price = Column(Float, nullable=True)\\n    order_type = Column(String, nullable=False)\\n    status = Column(String, nullable=False)\\n    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\\n    broker = Column(String, nullable=False)\\n    strategy = Column(String, nullable=True)\\n    profit_loss = Column(Float, nullable=True)\\n    success = Column(String, nullable=True)\\\\\nclass AccountInfo(Base):\\n    __tablename__ = 'account_info'\\n    id = Column(Integer, primary_key=True, autoincrement=True)\\n    broker = Column(String, unique=True)\\n    value = Column(Float)\\\\\nclass Balance(Base):\\n    __tablename__ = 'balances'\\n    id = Column(Integer, primary_key=True, autoincrement=True)\\n    broker = Column(String, nullable=False)\\n    strategy = Column(String, nullable=True)\\n    type = Column(String, nullable=False)  # 'cash' or 'positions'\\n    balance = Column(Float, default=0.0)\\n    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\\\\\n    __table_args__ = (PrimaryKeyConstraint('id', name='balance_pk'),)\\\\\nclass Position(Base):\\n    __tablename__ = 'positions'\\n    id = Column(Integer, primary_key=True, autoincrement=True)\\n    broker = Column(String, nullable=False)\\n    strategy = Column(String, nullable=True)\\n    balance_id = Column(Integer, ForeignKey('balances.id'), nullable=True)\\n    symbol = Column(String, nullable=False)\\n    quantity = Column(Float, nullable=False)\\n    latest_price = Column(Float, nullable=False)\\n    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)\\\\\n    balance = relationship('Balance', back_populates='positions', foreign_keys=[balance_id])\\\\\ndef drop_then_init_db(engine):\\n    Base.metadata.drop_all(engine)  # Drop existing tables\\n    Base.metadata.create_all(engine)  # Create new tables\\\\ndef init_db(engine):\\n    Base.metadata.create_all(engine)  # Create new tables\\\\n# Initialize the database\\ndrop_then_init_db(engine)\\\\\n# Define brokers and strategies\\nbrokers = ['E*TRADE', 'Tradier', 'Tastytrade']\\nstrategies = ['SMA', 'EMA', 'RSI', 'Bollinger Bands', 'MACD', 'VWAP', 'Ichimoku']\\\n# Generate unique hourly timestamps for the past 30 days\\nstart_date = datetime.utcnow() - timedelta(days=5)\\\\\nend_date = datetime.utcnow()\\ntimestamps = [start_date + timedelta(hours=i) for i in range((end_date - start_date).days * 24)]\\\\n# Generate fake trade data\\nnum_trades_per_hour = 1  # Number of trades per hour\\nfake_trades = []\\nprint("Generating fake trade data...")\\\\\nfor timestamp in timestamps:\\n    for _ in range(num_trades_per_hour):\\n        fake_trades.append(Trade(\\n           symbol=random.choice(['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']),\\n            quantity=random.randint(1, 20),\\n            price=random.uniform(100, 3000),\\n            executed_price=random.uniform(100, 3000),\\n            order_type=random.choice(['buy', 'sell']),\\n            status='executed',\\n            timestamp=timestamp,\\n            broker=random.choice(brokers),\\n            strategy=random.choice(strategies),\\n            profit_loss=random.uniform(-100, 100),\\n            success=random.choice(['yes', 'no'])\\n        ))\\nprint("Fake trade data generation completed.")\\\\\n# Insert fake trades into the database\\nprint("Inserting fake trades into the database...")\\\\\nsession.add_all(fake_trades)\\\\\nsession.commit()\\nprint("Fake trades inserted into the database.")\\\\\n# Generate and insert fake balance data and positions\\nprint("Generating and inserting fake balance data and positions...")\\\\\nfor broker in brokers:\\n    for strategy in strategies:\\n        initial_cash_balance = random.uniform(5000, 20000)\\\\\n        initial_position_balance = random.uniform(10000, 30000)\\\\\n        for timestamp in timestamps:\\n            total_cash_balance = initial_cash_balance + random.uniform(-1000, 1000)  # Simulate some profit/loss\\n            total_position_balance = initial_position_balance + random.uniform(-1000, 1000)  # Simulate some profit/loss\\n            cash_balance_record = Balance(\\n                broker=broker,\\n                strategy=strategy,\\n                type='cash',\\n                balance=total_cash_balance,\\n                timestamp=timestamp\\n            )\\n            position_balance_record = Balance(\\n                broker=broker,\\n                strategy=strategy,\\n                type='positions',\\n                balance=total_position_balance,\\n                timestamp=timestamp\\n            )\\n            session.add(cash_balance_record)\\\\\n            session.add(position_balance_record)\\\\\n            session.commit()  # Commit each balance record individually\\n            initial_cash_balance = total_cash_balance  # Update the initial balance for the next timestamp\\n            initial_position_balance = total_position_balance  # Update the initial balance for the next timestamp\\n            print(f"Inserted cash balance record for {broker}, {strategy} at {timestamp}. Total cash balance: {total_cash_balance}")\\\\\n            print(f"Inserted position balance record for {broker}, {strategy} at {timestamp}. Total position balance: {total_position_balance}")\\\\\n            # Generate and insert fake positions for each balance record\\n        for symbol in ['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']:\\n            quantity = random.randint(1, 100)\\\\\n            latest_price = random.uniform(100, 3000)\\\\\n            position_record = Position(\\n                broker=broker,\\n                strategy=strategy,\\n                symbol=symbol,\\n                quantity=quantity,\\n                latest_price=latest_price\\n            )\\n            session.add(position_record)\\\\\n            session.commit()\\n            print(f"Inserted position record for {broker}, {strategy}, {symbol} at {timestamp}. Quantity: {quantity}, Latest price: {latest_price}")\\\\\nprint("Fake balance data and positions generation and insertion completed.")\\\\\n# Generate fake account data\\nfake_accounts = [\\n    AccountInfo(broker='E*TRADE', value=10000.0),\\n    AccountInfo(broker='Tradier', value=15000.0),\\n    AccountInfo(broker='Tastytrade', value=20000.0),\\n]\\\\n# Insert fake account data into the database\\nprint("Inserting fake account data into the database...")\\\\\nsession.add_all(fake_accounts)\\\\\nsession.commit()\\nprint("Fake account data inserted into the database.")\\\\\n