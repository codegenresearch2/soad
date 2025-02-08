import argparse\\\\\\nimport time\\\\\\\\\nfrom datetime import datetime, timedelta\\\\\\\\\nfrom database.models import init_db\\\\\\\\\nfrom ui.app import create_app\\\\\\\\\nfrom utils.config import parse_config, initialize_brokers, initialize_strategies\\\\\\\\\nfrom sqlalchemy import create_engine\\\\\\\\\n\\\\\\\\\\ndef start_trading_system(config_path):\\\\\\\\\n    # Parse the configuration file\\\\\\\\\n    config = parse_config(config_path)\\\\\\\\\n    \\\\\\\\\n    # Initialize the brokers\\\\\\\\\n    brokers = initialize_brokers(config)\\\\\\\\\n    \\\\\\\\\n    # Initialize the database\\\\\\\\\n    database_url = config['database']['url'] if 'database' in config and 'url' in config['database'] else 'sqlite:///default_trading_system.db'\\\\\\\\\n    engine = create_engine(database_url)\\\\\\\\\n    init_db(engine)\\\\\\\\\n    \\\\\\\\\n    # Connect to each broker\\\\\\\\\n    for broker in brokers.values():\\\\\\\\\n        broker.connect()\\\\\\\\\n    \\\\\\\\\n    # Initialize the strategies\\\\\\\\\n    strategies = initialize_strategies(brokers, config)\\\\\\\\\n    \\\\\\\\\n    # Execute the strategies loop\\\\\\\\\n    rebalance_intervals = [timedelta(minutes=s.rebalance_interval_minutes) for s in strategies]\\\\\\\\\n    last_rebalances = [datetime.min for _ in strategies]\\\\\\\\\n    \\\\\\\\\n    while True:\\\\\\\\\n        now = datetime.now()\\\\\\\\\n        for i, strategy in enumerate(strategies):\\\\\\\\\n            if now - last_rebalances[i] >= rebalance_intervals[i]:\\\\\\\\\n                strategy.rebalance()\\\\\\\\\n                last_rebalances[i] = now\\\\\\\\\n        time.sleep(60)  # Check every minute\\\\\\\\\n\\\\\\\\\\ndef start_api_server(config_path=None, local_testing=False):\\\\\\\\\n    if config_path is None:\\\\\\\\\n        config = {}\\\\\\\\\n    else:\\\\\\\\\n        config = parse_config(config_path)\\\\\\\\\n    \\\\\\\\\n    # Initialize the brokers\\\\\\\\\n    brokers = initialize_brokers(config) if not local_testing else {}\\\\\\\\\n    \\\\\\\\\n    # Initialize the database\\\\\\\\\n    database_url = config['database']['url'] if 'database' in config and 'url' in config['database'] else 'sqlite:///default_trading_system.db'\\\\\\\\\n    engine = create_engine(database_url)\\\\\\\\\n    init_db(engine)\\\\\\\\\n    \\\\\\\\\n    app = create_app(engine)\\\\\\\\\n    app.run(host='0.0.0.0', port=8000, debug=True)\\\\\\\\\n\\\\\\\\\\ndef main():\\\\\\\\\n    parser = argparse.ArgumentParser(description='Run trading strategies or start API server based on YAML configuration.')\\\\\\\\\n    parser.add_argument('--mode', choices=['trade', 'api'], required=True, help='Mode to run the system in: trade or api')\\\\\\\\\n    parser.add_argument('--config', type=str, help='Path to the YAML configuration file.')\\\\\\\\\n    parser.add_argument('--local_testing', action='store_true', help='Enable local testing mode.')\\\\\\\\\n    args = parser.parse_args()\\\\\\\\\n    \\\\\\\\\n    if args.mode == 'trade':\\\\\\\\\n        if not args.config:\\\\\\\\\n            parser.error('--config is required when mode is trade')\\\\\\\\\n        start_trading_system(args.config)\\\\\\\\\n    elif args.mode == 'api':\\\\\\\\\n        start_api_server(args.config, args.local_testing)\\\\\\\\\n\\\\\\\\\\nif __name__ == '__main__':\\\\\\\\\n    main()\\\\\\\\\n