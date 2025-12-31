# trading_bot/positions.py
from typing import List, Dict
from trading_bot.brokers.abstract_broker import Broker
from datetime import datetime

class Position:
    def __init__(self, symbol: str, quantity: int, entry_price: float, current_price: float, greeks: Dict, opening_greeks: Dict, opening_iv: float, opening_rate: float, opening_time: datetime, opening_underlying_price: float, trade_id: str, leg_id: str, strategy: str, current_iv: float, current_rate: float, current_underlying_price: float):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = current_price
        self.greeks = greeks
        self.opening_greeks = opening_greeks
        self.opening_iv = opening_iv
        self.opening_rate = opening_rate
        self.opening_time = opening_time
        self.opening_underlying_price = opening_underlying_price
        self.trade_id = trade_id
        self.leg_id = leg_id
        self.strategy = strategy
        self.current_iv = current_iv  # Add
        self.current_rate = current_rate  # Add
        self.current_underlying_price = current_underlying_price  # Add

    def calculate_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity * 100

class PositionsManager:
    def __init__(self, broker: Broker):
        self.broker = broker
        self.positions: List[Position] = []

    def refresh(self):
        raw_positions = self.broker.get_positions()
        # Map raw to Position with opening/current data (fetch/add as needed)
        self.positions = [Position(**pos, opening_greeks=pos.get('opening_greeks', {}), opening_iv=0.3, opening_rate=0.05, opening_time=datetime.now(), opening_underlying_price=200.0, trade_id="T001", leg_id="L1", strategy="short put", current_iv=0.35, current_rate=0.055, current_underlying_price=205.0) for pos in raw_positions]  # Example; fetch real