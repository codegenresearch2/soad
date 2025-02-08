from abc import ABC, abstractmethod\\\\nfrom database.models import Balance\\\\n\\\\nclass BaseStrategy(ABC):\\\\n    def __init__(self, broker):\\\\n        self.broker = broker\\\\n        self.initialize_starting_balance()\\\\n\\\\n    @abstractmethod\\\\n    def rebalance(self):\\\\n        pass\\\\n\\\\n    def initialize_starting_balance(self):\\\\n        account_info = self.broker.get_account_info()\\\\n        buying_power = account_info.get('buying_power')\\\n\\\\n        if buying_power < self.starting_capital:\\\\n            raise ValueError("Not enough cash available to initialize the strategy with the desired starting capital.")\\\n\\\\n        with self.broker.Session() as session:\\\\n            strategy_balance = session.query(Balance).filter_by(\\\n                strategy=self.strategy_name,\\\n                broker=self.broker.broker_name,\\\n                type='cash'\\\\\n            ).first()\\\\n            if strategy_balance is None:\\\\n                strategy_balance = Balance(\\\n                    strategy=self.strategy_name,\\\n                    broker=self.broker.broker_name,\\\n                    total_balance=self.starting_capital,\\\n                    type='cash'\\\\\n                )\\\n                session.add(strategy_balance)\\\n                session.commit()\\\\n    }