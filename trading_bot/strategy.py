# trading_bot/strategy.py
# trading_bot/strategy.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from trading_bot.market_data.abstract_market_data import MarketDataProvider
from .trade_execution import TradeExecutor
from .order_model import UniversalOrder, OrderLeg, OrderAction, OrderType, PriceEffect  # Import from new file


import logging


logger = logging.getLogger(__name__)

class Strategy(ABC):
    def __init__(self, market_data: MarketDataProvider, executor: TradeExecutor, config: Dict):
        self.market_data = market_data
        self.executor = executor
        self.config = config

    @abstractmethod
    def evaluate_entry(self, data: Dict) -> bool:
        pass

    @abstractmethod
    def evaluate_exit(self, position: Dict) -> bool:
        pass

    @abstractmethod
    def generate_order(self, data: Dict) -> UniversalOrder:
        pass

    def execute_entry(self, data: Dict, account_id: Optional[str] = None) -> Dict:
        if self.evaluate_entry(data):
            order = self.generate_order(data)
            logger.info(f"Executing entry for {self.__class__.__name__}")
            return self.executor.execute(self.__class__.__name__, order, account_id)
        return {"status": "entry_not_met"}

class ShortPutStrategy(Strategy):
    def evaluate_entry(self, data: Dict) -> bool:
        iv = data['iv']
        delta = data['delta']
        return iv > self.config['min_iv'] and abs(delta) < self.config['max_delta']

    def evaluate_exit(self, position: Dict) -> bool:
        pnl = position['pnl']
        return pnl >= self.config['target_profit'] or pnl <= -self.config['max_loss']

    def generate_order(self, data: Dict) -> UniversalOrder:
        symbol = data.get('symbol', '.AAPL260117P00190000')
        quantity = data.get('quantity', 1)
        limit_price = data.get('limit_price', None)
        legs = [
            OrderLeg(symbol=symbol, quantity=quantity, action=OrderAction.SELL_TO_OPEN)
        ]
        return UniversalOrder(
            legs=legs,
            price_effect=PriceEffect.CREDIT,
            order_type=OrderType.LIMIT if limit_price else OrderType.MARKET,
            limit_price=limit_price,
            time_in_force="DAY",
            dry_run=self.config.get('dry_run', True)
        )