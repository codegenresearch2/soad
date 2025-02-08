class ConstantPercentageStrategy(BaseStrategy):\n    def __init__(self, broker, stock_allocations, cash_percentage, rebalance_interval_minutes, starting_capital):\n        super().__init__(broker)\n        self.stock_allocations = stock_allocations\n        self.cash_percentage = cash_percentage\n        self.rebalance_interval_minutes = rebalance_interval_minutes\n        self.rebalance_interval = timedelta(minutes=rebalance_interval_minutes)\n        self.starting_capital = starting_capital\n\n    def rebalance(self):\n        account_info = self.broker.get_account_info()\n        cash_balance = account_info.get('cash_available')\n        with self.broker.Session() as session:\n            balance = session.query(Balance).filter_by(\n                strategy='constant_percentage',\n                broker=self.broker.broker_name\n            ).first()\n            if balance is None:\n                raise ValueError(f'Strategy balance not initialized for constant_percentage strategy on {self.broker.broker_name}.')\n            total_balance = balance.total_balance\n\n        target_cash_balance = total_balance * self.cash_percentage\n        target_investment_balance = total_balance - target_cash_balance\n\n        current_positions = self.get_current_positions()\n\n        for stock, allocation in self.stock_allocations.items():\n            target_balance = target_investment_balance * allocation\n            current_position = current_positions.get(stock, 0)\n            current_price = self.broker.get_current_price(stock)\n            target_quantity = target_balance // current_price\n            if current_position < target_quantity:\n                self.broker.place_order(stock, target_quantity - current_position, 'buy', 'constant_percentage')\n            elif current_position > target_quantity:\n                self.broker.place_order(stock, current_position - target_quantity, 'sell', 'constant_percentage')\n\n    def get_current_positions(self):\n        positions = self.broker.get_positions()\n        return {position['symbol']: position['quantity'] for position in positions}