import logging

class TestBaseStrategy(BaseStrategy):
    def __init__(self, broker):
        super().__init__(broker, 'test_strategy', 10000)
        self.logger = logging.getLogger('test_strategy')
        self.logger.info("Logger initialized successfully")


This revised code snippet includes the necessary import statement for the `logging` module at the beginning of the file. This ensures that the `logging` module is available when the logger is instantiated in the `TestBaseStrategy` class, thus resolving the `NameError` and allowing the tests to run without encountering the error.