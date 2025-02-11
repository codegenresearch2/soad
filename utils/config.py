import asyncio
import yaml
import os
import importlib.util
from brokers.tradier_broker import TradierBroker
from brokers.tastytrade_broker import TastytradeBroker
from brokers.alpaca_broker import AlpacaBroker
from brokers.kraken_broker import KrakenBroker
from database.models import init_db
from database.db_manager import DBManager
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine
from strategies.constant_percentage_strategy import ConstantPercentageStrategy
from strategies.random_yolo_hedge_strategy import RandomYoloHedge
from strategies.black_swan_strategy import BlackSwanStrategy
from strategies.simple_strategy import SimpleStrategy
from .logger import logger

# Constants for configurable values
BROKER_MAP = {
    'tradier': lambda config, engine: TradierBroker(
        api_key=os.environ.get('TRADIER_API_KEY', config.get('api_key', 'default_key')),
        secret_key=None,
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'tastytrade': lambda config, engine: TastytradeBroker(
        username=os.environ.get('TASTYTRADE_USERNAME', config.get('username', 'default_username')),
        password=os.environ.get('TASTYTRADE_PASSWORD', config.get('password', 'default_password')),
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'alpaca': lambda config, engine: AlpacaBroker(
        api_key=os.environ.get('ALPACA_API_KEY', config.get('api_key', 'default_key')),
        secret_key=os.environ.get('ALPACA_SECRET_KEY', config.get('secret_key', 'default_secret_key')),
        engine=engine,
        prevent_day_trading=config.get('prevent_day_trading', False)
    ),
    'kraken': lambda config, engine: KrakenBroker(
        api_key=os.environ.get('KRAKEN_API_KEY', config.get('api_key', 'default_key')),
        secret_key=os.environ.get('KRAKEN_SECRET_KEY', config.get('secret_key', 'default_secret_key')),
        engine=engine
    )
}

STRATEGY_MAP = {
    'constant_percentage': lambda broker, strategy_name, config: ConstantPercentageStrategy(
        broker=broker,
        strategy_name=strategy_name,
        stock_allocations=config.get('stock_allocations', {}),
        cash_percentage=config.get('cash_percentage', 0.2),
        rebalance_interval_minutes=config.get('rebalance_interval_minutes', 60),
        starting_capital=config.get('starting_capital', 10000),
        buffer=config.get('rebalance_buffer', 0.1)
    ),
    'random_yolo_hedge': lambda broker, strategy_name, config: RandomYoloHedge(
        broker=broker,
        strategy_name=strategy_name,
        rebalance_interval_minutes=config.get('rebalance_interval_minutes', 60),
        starting_capital=config.get('starting_capital', 10000),
        max_spread_percentage=config.get('max_spread_percentage', 0.25),
        bet_percentage=config.get('bet_percentage', 0.2),
    ),
    'simple': lambda broker, strategy_name, config: SimpleStrategy(
        broker=broker,
        buy_threshold=config.get('buy_threshold', 0),
        sell_threshold=config.get('sell_threshold', 0)
    ),
    'black_swan': lambda broker, strategy_name, config: BlackSwanStrategy(
        broker=broker,
        strategy_name=strategy_name,
        rebalance_interval_minutes=config.get('rebalance_interval_minutes', 60),
        starting_capital=config.get('starting_capital', 10000),
        symbol=config.get('symbol', 'SPY'),
        otm_percentage=config.get('otm_percentage', 0.05),
        expiry_days=config.get('expiry_days', 30),
        bet_percentage=config.get('bet_percentage', 0.1),
        holding_period_days=config.get('holding_period_days', 14),
        spike_percentage=config.get('spike_percentage', 500)
    ),
    'custom': lambda broker, strategy_name, config: load_custom_strategy(broker, strategy_name, config)
}

def load_strategy_class(file_path, class_name):
    logger.info(f"Attempting to load strategy class '{class_name}' from file '{file_path}'")
    try:
        spec = importlib.util.spec_from_file_location(class_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        strategy_class = getattr(module, class_name)
        logger.info(f"Successfully loaded strategy class '{class_name}' from file '{file_path}'")
        return strategy_class
    except Exception as e:
        logger.error(f"Failed to load strategy class '{class_name}' from file '{file_path}': {e}")
        raise

def load_custom_strategy(broker, strategy_name, config):
    try:
        file_path = config.get('file_path', 'default_strategy_file.py')
        class_name = config.get('class_name', 'DefaultCustomStrategy')
        starting_capital = config.get('starting_capital', 10000)
        rebalance_interval_minutes = config.get('rebalance_interval_minutes', 60)
        execution_style = config.get('execution_style', 'default')
        strategy_class = load_strategy_class(file_path, class_name)
        logger.info(f"Initializing custom strategy '{class_name}' with config: {config}")
        return strategy_class(broker, strategy_name, starting_capital, rebalance_interval_minutes, execution_style, **config.get('strategy_params', {}))
    except Exception as e:
        logger.error(f"Error initializing custom strategy '{config.get('class_name', 'DefaultCustomStrategy')}': {e}")
        raise

def parse_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def initialize_brokers(config):
    if 'database' not in config:
        logger.error("'database' key is missing in the configuration")
        raise KeyError("'database' key is missing in the configuration")
    engine = create_async_engine(config['database']['url'])
    brokers = {}
    for broker_name, broker_config in config['brokers'].items():
        try:
            brokers[broker_name] = BROKER_MAP[broker_name](broker_config, engine)
        except Exception as e:
            logger.error(f"Error initializing broker '{broker_name}': {e}")
            continue
    return brokers

async def initialize_strategy(strategy_name, strategy_type, broker, config):
    constructor = STRATEGY_MAP.get(strategy_type)
    if constructor is None:
        logger.error(f"Unknown strategy type: {strategy_type}")
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    strategy = constructor(broker, strategy_name, config)
    if asyncio.iscoroutinefunction(strategy.initialize):
        await strategy.initialize()
        return strategy
    elif callable(strategy.initialize):
        strategy.initialize()
        return strategy
    else:
        return strategy

async def initialize_strategies(brokers, config):
    strategies_config = config.get('strategies', {})
    strategies = {}
    for strategy_name in strategies_config:
        try:
            strategy_config = strategies_config[strategy_name]
            strategy_type = strategy_config.get('type', 'default_strategy_type')
            broker_name = strategy_config.get('broker', 'default_broker')
            broker = brokers.get(broker_name)
            if broker is None:
                logger.error(f"Broker '{broker_name}' not found in initialized brokers")
                continue
            if strategy_type in STRATEGY_MAP:
                strategy = await initialize_strategy(strategy_name, strategy_type, broker, strategy_config)
                strategies[strategy_name] = strategy
            else:
                logger.error(f"Unknown strategy type: {strategy_type}")
        except Exception as e:
            logger.error(f"Error initializing strategy '{strategy_name}': {e}")
    return strategies

def create_api_database_engine(config, local_testing=False):
    if local_testing:
        return create_engine('sqlite:///trading.db')
    database_url = config.get('database', {}).get('url', os.environ.get("DATABASE_URL", 'sqlite:///default_trading_system.db'))
    return create_engine(database_url)

def create_database_engine(config, local_testing=False):
    if local_testing:
        return create_async_engine('sqlite+aiosqlite:///trading.db')
    database_url = config.get('database', {}).get('url', os.environ.get("DATABASE_URL", 'sqlite+aiosqlite:///default_trading_system.db'))
    return create_async_engine(database_url)

async def initialize_database(engine):
    try:
        await init_db(engine)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize database', extra={'error': str(e)}, exc_info=True)
        raise

async def initialize_system_components(config):
    try:
        brokers = initialize_brokers(config)
        logger.info('Brokers initialized successfully')
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
        return brokers, strategies
    except Exception as e:
        logger.error('Failed to initialize system components', extra={'error': str(e)}, exc_info=True)
        raise

async def initialize_brokers_and_strategies(config):
    engine = create_database_engine(config)
    if config.get('rename_strategies'):
        for strategy in config.get('rename_strategies', []):
            try:
                DBManager(engine).rename_strategy(strategy['broker'], strategy['old_strategy_name'], strategy['new_strategy_name'])
            except Exception as e:
                logger.error('Failed to rename strategy', extra={'error': str(e), 'renameStrategyConfig': strategy}, exc_info=True)
                raise
    try:
        brokers, strategies = await initialize_system_components(config)
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)}, exc_info=True)
        return
    try:
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize strategies', extra={'error': str(e)}, exc_info=True)
        return
    return brokers, strategies