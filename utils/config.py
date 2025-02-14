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
from order_manager.order_manager import OrderManager  # New import for order management
from tests.test_order_reconciliation import test_order_reconciliation  # New import for testing order reconciliation logic
from .logger import logger

# Mapping of broker types to their constructors
BROKER_MAP = {
    'tradier': TradierBroker,
    'tastytrade': TastytradeBroker,
    'alpaca': AlpacaBroker,
    'kraken': KrakenBroker
}

# Mapping of strategy types to their constructors
STRATEGY_MAP = {
    'constant_percentage': ConstantPercentageStrategy,
    'random_yolo_hedge': RandomYoloHedge,
    'simple': SimpleStrategy,
    'black_swan': BlackSwanStrategy,
    'custom': load_custom_strategy
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
        file_path = config['file_path']
        class_name = config['class_name']
        starting_capital = config['starting_capital']
        rebalance_interval_minutes = config['rebalance_interval_minutes']
        strategy_class = load_strategy_class(file_path, class_name)
        logger.info(f"Initializing custom strategy '{class_name}' with config: {config}")
        return strategy_class(broker, strategy_name, starting_capital, rebalance_interval_minutes, **config.get('strategy_params', {}))
    except Exception as e:
        logger.error(f"Error initializing custom strategy '{config['class_name']}': {e}")
        raise

def parse_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def initialize_brokers(config):
    brokers = {}
    for broker_name, broker_config in config['brokers'].items():
        try:
            broker_class = BROKER_MAP[broker_name]
            logger.debug(f"Initializing broker '{broker_name}' with config: {broker_config}")
            brokers[broker_name] = broker_class(**broker_config)
        except Exception as e:
            logger.error(f"Error initializing broker '{broker_name}': {e}")
            continue

    return brokers

async def initialize_strategy(strategy_name, strategy_type, broker, config):
    constructor = STRATEGY_MAP.get(strategy_type)
    if constructor is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    strategy = constructor(broker, strategy_name, config)
    if hasattr(strategy, 'initialize') and asyncio.iscoroutinefunction(strategy.initialize):
        await strategy.initialize()
    return strategy

async def initialize_strategies(brokers, config):
    strategies_config = config['strategies']
    strategies = {}
    for strategy_name in strategies_config:
        try:
            strategy_config = strategies_config[strategy_name]
            strategy_type = strategy_config['type']
            broker_name = strategy_config['broker']
            broker = brokers[broker_name]
            if strategy_type in STRATEGY_MAP:
                strategy = await initialize_strategy(strategy_name, strategy_type, broker, strategy_config)
                strategies[strategy_name] = strategy
            else:
                logger.error(f"Unknown strategy type: {strategy_type}")
        except Exception as e:
            logger.error(f"Error initializing strategy '{strategy_name}': {e}")
    return strategies

def create_database_engine(config, local_testing=False):
    if local_testing:
        return create_async_engine('sqlite+aiosqlite:///trading.db')
    if type(config) == str:
        return create_async_engine(config)
    if 'database' in config and 'url' in config['database']:
        return create_async_engine(config['database']['url'])
    return create_async_engine(os.environ.get("DATABASE_URL", 'sqlite+aiosqlite:///default_trading_system.db'))

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
        for strategy in config['rename_strategies']:
            try:
                DBManager(engine).rename_strategy(strategy['broker'], strategy['old_strategy_name'], strategy['new_strategy_name'])
            except Exception as e:
                logger.error('Failed to rename strategy', extra={'error': str(e), 'renameStrategyConfig': strategy}, exc_info=True)
                raise
    # Initialize the brokers and strategies
    try:
        brokers, strategies = await initialize_system_components(config)
    except Exception as e:
        logger.error('Failed to initialize brokers', extra={'error': str(e)}, exc_info=True)
        return

    # Initialize the strategies
    try:
        strategies = await initialize_strategies(brokers, config)
        logger.info('Strategies initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize strategies', extra={'error': str(e)}, exc_info=True)
        return

    # Initialize the order manager
    try:
        order_manager = OrderManager(engine, brokers)
        logger.info('Order manager initialized successfully')
    except Exception as e:
        logger.error('Failed to initialize order manager', extra={'error': str(e)}, exc_info=True)
        return

    return brokers, strategies, order_manager

# Added test function for order reconciliation logic
def run_order_reconciliation_tests():
    test_order_reconciliation()


In this rewritten code, I have added the OrderManager class for order management and the test_order_reconciliation function for testing order reconciliation logic. I have also simplified the BROKER_MAP and STRATEGY_MAP to directly map to the broker and strategy classes, and removed the need for passing the engine to the brokers during initialization. Additionally, I have updated the initialize_brokers_and_strategies function to initialize the order manager along with the brokers and strategies.