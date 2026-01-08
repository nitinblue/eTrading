# trading_bot/agents/strategy_dude.py
"""
StrategyDude: Suggests and models strategies.
- Registry for multiple strategies (Wheel, ORB, etc.).
- Each strategy has its own handler with state machine.
- Safe dict access to avoid errors.
- Returns suggestion dict always.
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Import handlers (add more as needed)
# from trading_bot.strategies.wheel_handler import WheelHandler
# from trading_bot.strategies.orb_handler import ORBHandler

def strategy_dude(state: Dict) -> Dict:
    logger.info("StrategyDude: Processing strategy request...")
    
    # Safe defaults
    underlying = state.get('underlying', 'MSFT')
    strategy_type = state.get('strategy_type', 'wheel').lower()

    # Registry for strategies
    registry = {
        'wheel': WheelHandler,
        'orb': ORBHandler,
        # Add more: 'iron_condor': IronCondorHandler,
    }

    handler_class = registry.get(strategy_type)
    if not handler_class:
        logger.warning(f"Unknown strategy: {strategy_type}")
        state['strategy_suggestion'] = {
            "error": f"Unknown strategy '{strategy_type}'",
            "available_strategies": list(registry.keys())
        }
        return state

    # Create handler instance (each has its own state file)
    try:
        handler = handler_class(underlying)
        suggestion = handler.run(state.copy())  # Use copy to avoid side effects
    except Exception as e:
        logger.error(f"Strategy handler {strategy_type} failed: {e}")
        suggestion = {"error": str(e)}

    # Ensure suggestion is always a dict
    if not isinstance(suggestion, dict):
        suggestion = {"raw_suggestion": suggestion}

    state['strategy_suggestion'] = suggestion
    logger.info(f"Strategy suggestion for {underlying} ({strategy_type}): {suggestion}")
    return state

# Existing WheelHandler (from previous)
class WheelHandler:
    states = ['idle', 'selling_put', 'assigned', 'selling_call']

    def __init__(self, underlying):
        self.underlying = underlying
        self.state_file = f"wheel_{underlying}_state.json"

        # State machine
        self.machine = Machine(model=self, states=WheelHandler.states, initial='idle')

        self.machine.add_transition('sell_put', 'idle', 'selling_put', conditions='can_sell_put')
        self.machine.add_transition('assign', 'selling_put', 'assigned')
        self.machine.add_transition('sell_call', 'assigned', 'selling_call', conditions='can_sell_call')
        self.machine.add_transition('call_away', 'selling_call', 'idle')

        self.load_state()

    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.state = data.get('state', 'idle')
        except FileNotFoundError:
            self.state = 'idle'

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump({'state': self.state}, f)

    def can_sell_put(self, state):
        # Check AnalyticsDude signal
        if state.get('analysis', {}).get('rsi', 50) > 70:
            return False
        return True

    def can_sell_call(self, state):
        # Check PortfolioDude for stock holding
        if 'positions' in state.get('portfolio', {}):
            return True
        return False

    def run(self, state: Dict) -> Dict:
        logger.info(f"Wheel for {self.underlying}: Current state {self.state}")

        if self.state == 'idle':
            self.sell_put(state)
        elif self.state == 'selling_put':
            if 'assigned' in state.get('portfolio', {}):  # From PortfolioDude
                self.assign()
        elif self.state == 'assigned':
            self.sell_call(state)
        elif self.state == 'selling_call':
            if 'called_away' in state.get('portfolio', {}):
                self.call_away()

        self.save_state()

        return {"strategy": "Wheel", "current_state": self.state, "suggestion": "Sell put if idle"}

# New ORBHandler (full implementation)
class ORBHandler:
    states = ['idle', 'monitoring_or', 'breakout_detected', 'trade_executed']

    def __init__(self, underlying):
        self.underlying = underlying
        self.state_file = f"orb_{underlying}_state.json"

        # State machine for ORB
        self.machine = Machine(model=self, states=ORBHandler.states, initial='idle')

        self.machine.add_transition('start_monitoring', 'idle', 'monitoring_or', conditions='market_open')
        self.machine.add_transition('detect_breakout', 'monitoring_or', 'breakout_detected', conditions='breakout_condition')
        self.machine.add_transition('execute_trade', 'breakout_detected', 'trade_executed', after='place_spread')
        self.machine.add_transition('reset', '*', 'idle')

        self.load_state()

    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.state = data.get('state', 'idle')
                self.or_high = data.get('or_high', 0.0)
                self.or_low = data.get('or_low', 0.0)
        except FileNotFoundError:
            self.state = 'idle'
            self.or_high = 0.0
            self.or_low = 0.0

    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump({'state': self.state, 'or_high': self.or_high, 'or_low': self.or_low}, f)

    def market_open(self, state):
        # Check if market is open (simulated - use real time check)
        return True

    def breakout_condition(self, state):
        current_price = state.get('data', {}).get('price', 0.0)
        if current_price > self.or_high:
            self.direction = "bullish"
            return True
        elif current_price < self.or_low:
            self.direction = "bearish"
            return True
        return False

    def place_spread(self, state):
        logger.info(f"Placing {self.direction} credit spread for ORB")
        # Simulated trade - integrate with TraderDude via state
        state['trade_order'] = {"type": "credit_spread", "direction": self.direction, "underlying": self.underlying}
        # Real code: Call TradeExecutor with order details

    def run(self, state: Dict) -> Dict:
        logger.info(f"ORB for {self.underlying}: Current state {self.state}")

        if self.state == 'idle':
            self.start_monitoring(state)
        elif self.state == 'monitoring_or':
            self.calculate_or(state)
            self.detect_breakout(state)
        elif self.state == 'breakout_detected':
            self.execute_trade(state)
        elif self.state == 'trade_executed':
            self.reset()

        self.save_state()

        return {"strategy": "ORB", "current_state": self.state, "suggestion": "Monitor OR if idle", "direction": getattr(self, 'direction', 'none')}

    def calculate_or(self, state: Dict):
        # Simulated OR calculation (replace with real from DataDude)
        current_price = state.get('data', {}).get('price', 425.0)
        self.or_high = current_price * 1.002
        self.or_low = current_price * 0.998
        logger.info(f"Calculated OR: High {self.or_high:.2f}, Low {self.or_low:.2f}")