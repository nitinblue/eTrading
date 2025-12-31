# trading_bot/trade_execution.py
from typing import Optional, Dict
from trading_bot.brokers.abstract_broker import Broker  # From new abstract file
from trading_bot.order_model import UniversalOrder  # Import from new file
import logging

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, broker: Broker):
        self.broker = broker

    def execute(self, strategy_name: str, order: UniversalOrder, account_id: Optional[str] = None) -> Dict:
        logger.info(f"Executing {strategy_name} on account {account_id or 'default'}: {order.to_dict()}")
        response = self.broker.execute_order(order, account_id)
        return response