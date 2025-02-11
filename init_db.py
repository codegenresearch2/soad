# This is a script to make fake data for testing the UI
from sqlalchemy import create_engine
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

# Define brokers and strategies
brokers = ['E*TRADE', 'Tradier']  # Reduced number of brokers
strategies = ['SMA', 'EMA']  # Reduced number of strategies

# Generate unique hourly timestamps for the past 30 days
start_date = datetime.utcnow() - timedelta(days=5)
end_date = datetime.utcnow()
timestamps = [start_date + timedelta(hours=i) for i in range((end_date - start_date).days * 24)]

# Generate fake trade data
num_trades_per_hour = 1  # Number of trades per hour
fake_trades = []

print("Generating fake trade data...")
for timestamp in timestamps:
    for _ in range(num_trades_per_hour):
        fake_trades.append(Trade(
            symbol=random.choice(['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']),
            quantity=random.randint(1, 20),
            price=random.uniform(100, 3000),
            executed_price=random.uniform(100, 3000),
            order_type=random.choice(['buy', 'sell']),
            status='executed',
            timestamp=timestamp,
            broker=random.choice(brokers),
            strategy=random.choice(strategies),
            profit_loss=random.uniform(-100, 100),
            success=random.choice(['yes', 'no'])
        ))
print("Fake trade data generation completed.")

# Insert fake trades into the database
print("Inserting fake trades into the database...")
session.add_all(fake_trades)
session.commit()
print("Fake trades inserted into the database.")

# Generate and insert fake balance data and positions
print("Generating and inserting fake balance data and positions...")
for broker in brokers:
    for strategy in strategies:
        initial_cash_balance = random.uniform(5000, 20000)
        initial_position_balance = random.uniform(5000, 20000)
        for timestamp in timestamps:
            cash_balance = initial_cash_balance + random.uniform(-1000, 1000)  # Simulate some profit/loss
            position_balance = initial_position_balance + random.uniform(-1000, 1000)  # Simulate some profit/loss
            cash_balance_record = Balance(
                broker=broker,
                strategy=strategy,
                type='cash',
                balance=cash_balance,
                timestamp=timestamp
            )
            position_balance_record = Balance(
                broker=broker,
                strategy=strategy,
                type='positions',
                balance=position_balance,
                timestamp=timestamp
            )
            session.add(cash_balance_record)
            session.add(position_balance_record)
            session.commit()  # Commit each balance record individually
            initial_cash_balance = cash_balance  # Update the initial balance for the next timestamp
            initial_position_balance = position_balance  # Update the initial balance for the next timestamp
            print(f"Inserted balance record for {broker}, {strategy} at {timestamp}. Cash balance: {cash_balance}, Position balance: {position_balance}")

            # Generate and insert fake positions for each balance record
            for symbol in ['AAPL', 'GOOG', 'TSLA', 'MSFT', 'NFLX', 'AMZN', 'FB', 'NVDA']:
                quantity = random.randint(1, 100)
                latest_price = random.uniform(100, 3000)
                position_record = Position(
                    broker=broker,
                    strategy=strategy,
                    symbol=symbol,
                    quantity=quantity,
                    latest_price=latest_price
                )
                session.add(position_record)
                session.commit()
                print(f"Inserted position record for {broker}, {strategy}, {symbol} at {timestamp}. Quantity: {quantity}, Latest price: {latest_price}")

print("Fake balance data and positions generation and insertion completed.")

# Generate fake account data
fake_accounts = [
    AccountInfo(broker='E*TRADE', value=10000.0),
    AccountInfo(broker='Tradier', value=15000.0),
]  # Reduced number of accounts

# Insert fake account data into the database
print("Inserting fake account data into the database...")
session.add_all(fake_accounts)
session.commit()
print("Fake account data inserted into the database.")