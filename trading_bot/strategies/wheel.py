# trading_bot/strategies/wheel.py
"""
Wheel Strategy with state machine, technical entry triggers (RSI, MA), PNL/breakeven tracking, and tabular lifecycle display.
"""

from transitions import Machine
from trading_bot.utils.trade_utils import print_option_chain  # Optional
from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, OrderType, PriceEffect
from trading_bot.trade_execution import TradeExecutor
from tabulate import tabulate
from tastytrade.instruments import get_option_chain
from polygon import RESTClient
import pandas as pd
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)

class WheelStrategy:
    states = ['idle', 'selling_put', 'assigned', 'selling_call']

    def __init__(self, broker_session, config, risk_manager, underlying: str):
        self.session = broker_session
        self.risk_manager = risk_manager
        self.executor = TradeExecutor(broker_session)
        self.underlying = underlying

        # Config access (assuming config is Pydantic — use getattr)
        strategies_config = getattr(config, 'strategies', {})
        self.config = strategies_config.get('wheel', {})
        if not self.config:
            raise ValueError("wheel strategy not configured in config.yaml")

        self.state_file = f"wheel_{underlying}_state.json"

        # Tracking
        self.history = []  # Events: {'event': 'Put Sold', 'credit': 2.50, 'debit': 0, 'cum_pnl': 2.50, 'breakeven': 97.50, 'timestamp': datetime.now()}
        self.cum_pnl = 0.0
        self.cost_basis = 0.0
        self.net_premiums = 0.0

        # State machine
        self.machine = Machine(model=self, states=WheelStrategy.states, initial='idle')

        self.machine.add_transition('start', 'idle', 'selling_put', conditions='can_sell_put', after='on_sell_put')
        self.machine.add_transition('assign', 'selling_put', 'assigned', after='on_assign')
        self.machine.add_transition('sell_call', 'assigned', 'selling_call', conditions='can_sell_call', after='on_sell_call')
        self.machine.add_transition('call_away', 'selling_call', 'idle', after='on_call_away')

        # Load state
        self.load_state()

    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.state = data.get('state', 'idle')
                self.history = data.get('history', [])
                self.cum_pnl = data.get('cum_pnl', 0.0)
                self.cost_basis = data.get('cost_basis', 0.0)
                self.net_premiums = data.get('net_premiums', 0.0)
            logger.info(f"Loaded state for {self.underlying}: {self.state}")
        except FileNotFoundError:
            logger.info(f"No state for {self.underlying} — starting idle")
            self.state = 'idle'

    def save_state(self):
        data = {
            'state': self.state,
            'history': self.history,
            'cum_pnl': self.cum_pnl,
            'cost_basis': self.cost_basis,
            'net_premiums': self.net_premiums
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f)
        logger.info(f"Saved state for {self.underlying}: {self.state}")

    def get_technical_indicators(self):
        """Fetch historical data and calculate RSI and 200-day MA."""
        client = RESTClient()  # API key configured in environment

        # Fetch 1-year historical daily closes
        from_date = (datetime.now().date() - timedelta(days=365)).isoformat()
        to_date = datetime.now().date().isoformat()

        aggs = client.get_aggs(ticker=self.underlying, multiplier=1, timespan="day", from_=from_date, to=to_date)

        if not aggs:
            logger.warning(f"No historical data for {self.underlying}")
            return {'rsi': 50, 'ma200': 0.0}

        closes = [agg.close for agg in aggs]

        df = pd.DataFrame({'close': closes})

        # RSI (14 period)
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 200-day SMA
        df['ma200'] = df['close'].rolling(window=200).mean()

        current_rsi = df['rsi'].iloc[-1]
        current_ma200 = df['ma200'].iloc[-1]
        current_price = df['close'].iloc[-1]

        logger.info(f"Technical indicators for {self.underlying}: RSI {current_rsi:.1f}, 200-day MA ${current_ma200:.2f}, Price ${current_price:.2f}")

        return {
            'rsi': current_rsi,
            'ma200': current_ma200,
            'price': current_price
        }

    def can_sell_put(self):
        """Check technical levels for entry (RSI oversold, price above MA)."""
        ind = self.get_technical_indicators()
        if ind['rsi'] >= 30 or ind['price'] <= ind['ma200']:
            logger.info(f"Entry not met for {self.underlying}: RSI {ind['rsi']:.1f} (not oversold), Price ${ind['price']:.2f} (not above MA ${ind['ma200']:.2f})")
            return False

        # Find suitable put
        chain = get_option_chain(self.session, self.underlying)
        selected_expiry = min(chain.keys(), key=lambda d: abs((d - datetime.now().date()).days + self.config.get('max_dte', 45)))

        puts = [o for o in chain[selected_expiry] if o.option_type == 'put']
        puts = sorted(puts, key=lambda x: x.greeks.delta)

        put = next((p for p in puts if abs(p.greeks.delta - self.config.get('put_delta_target', -0.16)) < 0.05), None)
        if not put:
            logger.info("No suitable put found")
            return False

        premium = put.bid_price or put.mid_price
        if premium < self.config.get('min_premium', 1.50):
            logger.info(f"Premium too low (${premium:.2f})")
            return False

        # Risk check
        risk = (put.strike_price - premium) * 100 * self.config.get('quantity', 1)
        if risk > self.risk_manager.max_loss * self.risk_manager.capital:
            logger.info("Risk exceeds max")
            return False

        # Sell put
        legs = [OrderLeg(symbol=put.symbol, quantity=self.config.get('quantity', 1), action=OrderAction.SELL_TO_OPEN)]
        order = UniversalOrder(legs=legs, price_effect=PriceEffect.CREDIT, order_type=OrderType.LIMIT, limit_price=premium * 0.9, dry_run=self.config.get('dry_run', True))
        result = self.executor.execute("Wheel Put Sell", order)
        if result.get('status') != 'success':
            return False

        logger.info(f"Sold put: {put.symbol} for ${premium:.2f}")
        return True

    # ... (rest of the class unchanged)

# Integrate in main.py as before

    def on_sell_put(self):
        """Action after selling put — update tracking."""
        # Simulated credit (replace with real order result)
        credit = 2.50  # From order
        self.net_premiums += credit
        self.cum_pnl += credit
        self.history.append({
            'event': 'Put Sold',
            'credit': credit,
            'debit': 0,
            'cum_pnl': self.cum_pnl,
            'breakeven': 97.50,  # Strike - credit
            'timestamp': datetime.now()
        })
        self.save_state()

    def on_assign(self):
        """Action on assignment — update cost basis."""
        # Simulated debit (strike * 100)
        debit = 10000  # Strike $100 * 100 shares
        self.cost_basis = debit - self.net_premiums * 100
        self.cum_pnl -= debit
        self.history.append({
            'event': 'Assigned',
            'credit': 0,
            'debit': debit,
            'cum_pnl': self.cum_pnl,
            'breakeven': self.cost_basis / 100,
            'timestamp': datetime.now()
        })
        self.save_state()

    def on_sell_call(self):
        """Action after selling call."""
        credit = 1.50  # Simulated
        self.net_premiums += credit
        self.cum_pnl += credit
        self.cost_basis -= credit * 100  # Adjust breakeven down
        self.history.append({
            'event': 'Call Sold',
            'credit': credit,
            'debit': 0,
            'cum_pnl': self.cum_pnl,
            'breakeven': self.cost_basis / 100,
            'timestamp': datetime.now()
        })
        self.save_state()

    def on_call_away(self):
        """Action on call away — realize PNL."""
        # Simulated credit (strike * 100)
        credit = 10500  # Strike $105 * 100 shares
        pnl = credit - self.cost_basis
        self.cum_pnl += pnl
        self.history.append({
            'event': 'Called Away',
            'credit': credit,
            'debit': 0,
            'cum_pnl': self.cum_pnl,
            'breakeven': 0.0,  # Reset
            'timestamp': datetime.now()
        })
        self.net_premiums = 0.0
        self.cost_basis = 0.0
        self.save_state()

    def display_history(self):
        """Display lifecycle events in tabular format."""
        if not self.history:
            logger.info("No history to display")
            return

        table = tabulate(self.history, headers="keys", tablefmt="grid")
        logger.info(f"\nWheel Lifecycle for {self.underlying}:\n{table}")

    def run(self):
        logger.info(f"Running Wheel for {self.underlying} — state: {self.state}")

        if self.state == 'idle':
            self.start()
        elif self.state == 'selling_put':
            if self.is_assigned():
                self.assign()
        elif self.state == 'assigned':
            self.sell_call()
        elif self.state == 'selling_call':
            if self.is_called_away():
                self.call_away()

        self.display_history()
        self.save_state()

    # ... other methods (can_sell_put, can_sell_call, is_assigned, is_called_away)