# trading_bot/command_center.py
from .event_handler import EventHandler
from .portfolio import Portfolio
from .trade_execution import TradeExecutor

class CommandCenter:
    """Central control for kill switches, scenarios."""
    def __init__(self, event_handler: EventHandler, portfolio: Portfolio, executor: TradeExecutor):
        self.event_handler = event_handler
        self.portfolio = portfolio
        self.executor = executor
        self.kill_switch_active = False

    def activate_kill_switch(self):
        self.kill_switch_active = True
        # Close all positions
        for pos in self.portfolio.positions_manager.positions:
            legs = [{'symbol': pos.symbol, 'quantity': -pos.quantity, 'action': 'BUY_TO_CLOSE' if pos.quantity > 0 else 'SELL_TO_CLOSE'}]
            self.executor.execute('emergency_close', legs, PriceEffect.DEBIT)

    def handle_extreme_scenario(self, scenario_type: str):
        if scenario_type == 'market_crash':
            self.event_handler.trigger('vol_spike', {'level': 'high'})
        # Configurable responses