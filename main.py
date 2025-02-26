import argparse
import time
from datetime import datetime, timedelta
from database.models import init_db
from ui.app import create_app
from utils.config import parse_config, initialize_brokers, initialize_strategies
from sqlalchemy import create_engine


def create_db_engine(config):
    if 'database' in config and 'url' in config['database']:
        return create_engine(config['database']['url'])
    else:
        return create_engine('sqlite:///default_trading_system.db')


def start_trading_system(config_path):
    # Parse the configuration file
    config = parse_config(config_path)
    engine = create_db_engine(config)
    # Initialize the database
    init_db(engine)
    # Initialize the brokers
    brokers = initialize_brokers(config)
    # Connect to each broker
    for broker in brokers.values():
        broker.connect()
    # Initialize the strategies
    strategies = initialize_strategies(brokers, config)
    # Execute the strategies loop
    rebalance_intervals = [timedelta(minutes=s.rebalance_interval_minutes) for s in strategies]
    last_rebalances = [datetime.min for _ in strategies]
    while True:
        now = datetime.now()
        for i, strategy in enumerate(strategies):
            if now - last_rebalances[i] >= rebalance_intervals[i]:
                strategy.rebalance()
                last_rebalances[i] = now
        time.sleep(60)  # Check every minute


def start_api_server(config_path=None):
    if config_path is None:
        config = {}
    else:
        config = parse_config(config_path)
    engine = create_db_engine(config)
    # Initialize the database
    init_db(engine)
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)


def main():
    parser = argparse.ArgumentParser(description="Run trading strategies or start API server based on YAML configuration.")
    parser.add_argument('--mode', choices=['trade', 'api'], required=True, help='Mode to run the system in: "trade" or "api"')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')
    args = parser.parse_args()
    if args.mode == 'trade':
        if not args.config:
            parser.error('--config is required when mode is "trade"')
        start_trading_system(args.config)
    elif args.mode == 'api':
        start_api_server()

if __name__ == "__main__":
    main()