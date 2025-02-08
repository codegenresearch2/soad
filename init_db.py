from sqlalchemy import create_engine, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker
from database.models import Trade, AccountInfo, Balance, Position, drop_then_init_db
from datetime import datetime, timedelta
import random

DATABASE_URL = "sqlite:///trading.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Initialize the database
drop_then_init_db(engine)

# Define constants
BROKERS = ['E*TRADE', 'Tradier', 'Tastytrade']
STRATEGIES = ['SMA', 'EMA', 'RSI', 'Bollinger Bands', 'MACD', 'VWAP', 'Ichimoku']
NUM_TRADES_PER_HOUR = 1
START_DATE = datetime.utcnow() - timedelta(days=5)
END_DATE = datetime.utcnow()

# Generate unique hourly timestamps for the past 5 days
TIMESTAMPS = [START_DATE + timedelta(hours=i) for i in range((END_DATE - START_DATE).days * 24)]

# Generate fake trade data
FAKE_TRADES = []

print("Generating fake trade data...")  # Use f-string for formatted strings
for timestamp in TIMESTAMPS:
    for _ in range(NUM_TRADES_PER_HOUR):
        FAKE_TRADES.append(Trade(
            symbol=random.choice(['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']),
            quantity=random.randint(1, 20),
            price=random.uniform(100, 3000),
            executed_price=random.uniform(100, 3000),
            order_type=random.choice(['buy', 'sell']),
            status='executed',
            timestamp=timestamp,
            broker=random.choice(BROKERS),
            strategy=random.choice(STRATEGIES),
            profit_loss=random.uniform(-100, 100),
            success=random.choice(['yes', 'no'])
        ))  # Use f-string for formatted strings
print("Fake trade data generation completed.")  # Use f-string for formatted strings

# Insert fake trades into the database
print("Inserting fake trades into the database...")  # Use f-string for formatted strings
session.add_all(FAKE_TRADES)  # Use f-string for formatted strings
session.commit()  # Use f-string for formatted strings
print("Fake trades inserted into the database.")  # Use f-string for formatted strings

# Generate and insert fake balance data and positions
print("Generating and inserting fake balance data and positions...")  # Use f-string for formatted strings
for broker in BROKERS:
    for strategy in STRATEGIES:
        cash_balance = random.uniform(5000, 20000)
        position_balance = random.uniform(5000, 20000)
        for timestamp in TIMESTAMPS:
            cash_balance_record = Balance(
                broker=broker,
                strategy=strategy,
                type='cash',
                balance=cash_balance,
                timestamp=timestamp
            )
            session.add(cash_balance_record)
            cash_balance += random.uniform(-1000, 1000)  # Update cash balance based on profit/loss

            position_balance_record = Balance(
                broker=broker,
                strategy=strategy,
                type='positions',
                balance=position_balance,
                timestamp=timestamp
            )
            session.add(position_balance_record)
            position_balance += random.uniform(-1000, 1000)  # Update position balance based on profit/loss

            # Generate and insert fake positions for each balance record
            for symbol in ['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']:
                QUANTITY = random.randint(1, 100)  # Use f-string for formatted strings
                LATEST_PRICE = random.uniform(100, 3000)  # Use f-string for formatted strings
                position_record = Position(
                    broker=broker,
                    strategy=strategy,
                    symbol=symbol,
                    quantity=QUANTITY,
                    latest_price=LATEST_PRICE
                )
                session.add(position_record)
                session.commit()
                print(f"Inserted position record for {broker}, {strategy}, {symbol} at {timestamp}. Quantity: {QUANTITY}, Latest price: {LATEST_PRICE}")  # Use f-string for formatted strings

print("Fake balance data and positions generation and insertion completed.")  # Use f-string for formatted strings

# Generate fake account data
FAKE_ACCOUNTS = [
    AccountInfo(broker='E*TRADE', value=10000.0),
    AccountInfo(broker='Tradier', value=15000.0),
    AccountInfo(broker='Tastytrade', value=20000.0),
]

# Insert fake account data into the database
print("Inserting fake account data into the database...")  # Use f-string for formatted strings
session.add_all(FAKE_ACCOUNTS)  # Use f-string for formatted strings
session.commit()  # Use f-string for formatted strings
print("Fake account data inserted into the database.")  # Use f-string for formatted strings
