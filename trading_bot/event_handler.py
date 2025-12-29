# trading_bot/event_handler.py
from typing import Callable, Dict
from pubsub import pub  # pip install pypubsub

class EventHandler:
    """Event-driven handler for rules/logic. Pub-Sub pattern."""
    def __init__(self):
        self.rules: Dict[str, Callable] = {}  # event_type -> handler

    def register(self, event_type: str, handler: Callable):
        self.rules[event_type] = handler
        pub.subscribe(handler, event_type)

    def trigger(self, event_type: str, data: Dict):
        pub.sendMessage(event_type, data=data)

# Example usage: handler.register('market_vol_spike', lambda data: print("Handle spike"))