# trading_bot/positions.py
from typing import List, Dict
from trading_bot.brokers.abstract_broker import Broker  # Absolute

class Position:
    def __init__(self, symbol: str, quantity: int, entry_price: float, current_price: float, greeks: Dict):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = current_price
        self.greeks = greeks or {}

    def calculate_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity * 100

class PositionsManager:
    def __init__(self, broker: Broker):
        self.broker = broker
        self.positions: List[Position] = []

    def refresh(self):
        raw_positions = self.broker.get_positions()
        self.positions = [Position(**pos) for pos in raw_positions]

    def get_by_symbol(self, symbol: str) -> List[Position]:
        return [p for p in self.positions if p.symbol == symbol]