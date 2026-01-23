# trading_bot/positions.py
from decimal import Decimal
from typing import List, Dict
from trading_bot.brokers.abstract_broker import Broker
from datetime import datetime

# trading_bot/positions.py
class Position:
    def __init__(self, **kwargs):
        self.symbol = kwargs.get('symbol')
        self.quantity = kwargs.get('quantity', 0)
        self.entry_price = kwargs.get('entry_price', 0.0)
        self.current_price = kwargs.get('current_price', 0.0)
        self.greeks = kwargs.get('greeks', {})
        self.trade_id = kwargs.get('trade_id', 'N/A')
        self.leg_id = kwargs.get('leg_id', 'N/A')
        self.strategy = kwargs.get('strategy', 'Unknown')
        # New fields
        self.volume = kwargs.get('volume', 0)  # Daily volume
        self.open_interest = kwargs.get('open_interest', 0)
        self.stop_loss = kwargs.get('stop_loss')  # Price level
        self.take_profit = kwargs.get('take_profit')  # Price level

    def calculate_pnl(self) -> float:
        return (Decimal(self.current_price) - Decimal(self.entry_price)) * Decimal(self.quantity) * 100

    def is_stop_hit(self, current_price: float) -> bool:
        if self.quantity > 0:  # Long
            return current_price <= self.stop_loss if self.stop_loss else False
        else:  # Short
            return current_price >= self.stop_loss if self.stop_loss else False

    def is_tp_hit(self, current_price: float) -> bool:
        if self.quantity > 0:  # Long
            return current_price >= self.take_profit if self.take_profit else False
        else:  # Short
            return current_price <= self.take_profit if self.take_profit else False

class PositionsManager:
    def __init__(self, broker: Broker):
        self.broker = broker
        self.positions: List[Position] = []

    def refresh(self):
        raw_positions = self.broker.get_positions()
        # Map raw to Position with opening/current data (fetch/add as needed)
        self.positions = [Position(**pos, opening_greeks=pos.get('opening_greeks', {}), opening_iv=0.3, opening_rate=0.05, opening_time=datetime.now(), opening_underlying_price=200.0, trade_id="T001", leg_id="L1", strategy="short put", current_iv=0.35, current_rate=0.055, current_underlying_price=205.0) for pos in raw_positions]  # Example; fetch real