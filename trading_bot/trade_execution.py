# trading_bot/trade_execution.py
from typing import Optional
from .broker import Broker, NeutralOrder
import logging

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Handles trade execution using neutral orders. Configurable with validators."""
    def __init__(self, broker: Broker):
        self.broker = broker

    def execute(self, strategy_name: str, order: NeutralOrder, account_id: Optional[str] = None) -> Dict:
        # Pre-execution hooks (e.g., validate risk; add your RiskManager check here)
        logger.info(f"Executing {strategy_name} on account {account_id or 'default'}: {order.to_dict()}")
        
        # Delegate to broker
        response = self.broker.execute_order(order, account_id)
        
        # Post-execution: Log, update positions (optional)
        return response