from datetime import timedelta\nfrom strategies.base_strategy import BaseStrategy\nfrom database.models import Balance\n\nclass ConstantPercentageStrategy(BaseStrategy):\n    def __init__(self, broker, stock_allocations, cash_percentage, rebalance_interval_minutes, starting_capital):\n        self.stock_allocations = stock_allocations\n        self.rebalance_interval_minutes = rebalance_interval_minutes\n        self.cash_percentage = cash_percentage\n        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)\n        self.starting_capital = starting_capital\n        self.strategy_name = 'constant_percentage'\n        super().__init__(broker)\n\n    def rebalance(self):\n        account_info = self.broker.get_account_info()\n        cash_balance = account_info.get('cash_available')\n        total_balance = self.get_total_balance()\n\n        target_cash_balance = total_balance * self.cash_percentage\n        target_investment_balance = total_balance - target_cash_balance\n\n        current_positions = self.get_current_positions()\n\n        for stock, allocation in self.stock_allocations.items():\n            target_balance = target_investment_balance * allocation\n            current_position = current_positions.get(stock, 0)\n            current_price = self.broker.get_current_price(stock)\n            target_quantity = target_balance // current_price\n            if current_position < target_quantity:\n                self.broker.place_order(stock, target_quantity - current_position, 'buy', self.strategy_name)\n            elif current_position > target_quantity:\n                self.broker.place_order(stock, current_position - target_quantity, 'sell', self.strategy_name)\n\n    def get_current_positions(self):\n        positions = self.broker.get_positions()\n        return {position['symbol']: position['quantity'] for position in positions}\n\n    def get_total_balance(self):\n        with self.broker.Session() as session:\n            balance = session.query(Balance).filter_by(strategy=self.strategy_name, broker=self.broker.broker_name, type='cash').first()\n            if balance is None:\n                raise ValueError(f"Strategy balance not initialized for {self.strategy_name} strategy on {self.broker}.")\n            return balance.balance