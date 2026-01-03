# trading_bot/strategies/orb_0dte.py
"""
0DTE Opening Range Breakout (ORB) Credit Spread Strategy.
- Calculates simulated Opening Range
- Detects breakout
- Sells credit spread in breakout direction
- Dry-run by default
"""

from datetime import datetime
from tastytrade.instruments import get_option_chain
from tastytrade.dxfeed.quote import Quote
from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.trade_execution import TradeExecutor
import logging

logger = logging.getLogger(__name__)

class ORB0DTEStrategy:
    def __init__(self, broker_session, config):
        self.session = broker_session
        self.strategies_config = getattr(config, 'strategies', {})
        self.config = self.strategies_config.get('orb_0dte', {})
        if not self.config:
            raise ValueError("orb_0dte strategy not configured in config.yaml")

        self.underlying = self.config.get('underlying', 'SPX')
        self.or_minutes = self.config.get('or_minutes', 30)
        self.spread_width = self.config.get('spread_width', 5)
        self.min_credit = self.config.get('min_credit', 1.50)
        self.quantity = self.config.get('quantity', 1)
        self.dry_run = self.config.get('dry_run', True)

        self.executor = TradeExecutor(broker_session)

    def get_current_price(self):
        """Get current underlying price."""
        try:
            quote = Quote.get_quote(self.session, self.underlying)
            price = quote.last_price or quote.close_price or quote.bid_price or quote.ask_price
            return float(price) if price else 0.0
        except Exception as e:
            logger.error(f"Failed to get price for {self.underlying}: {e}")
            return 0.0

    def calculate_opening_range(self):
        """Simulate Opening Range (replace with real data later)."""
        current_price = self.get_current_price()
        if current_price == 0:
            raise ValueError("Could not get underlying price for OR calculation")

        # Simulated OR: ±0.2% of current price
        or_high = current_price * 1.002
        or_low = current_price * 0.998
        logger.info(f"Simulated Opening Range for {self.underlying}: High ${or_high:.2f}, Low ${or_low:.2f}")
        return or_high, or_low

    def find_credit_spread(self, direction: str, reference_price: float):
        """Find credit spread for breakout."""
        chain = get_option_chain(self.session, self.underlying)
        today = datetime.now().date()
        zero_dte_expiry = next((exp for exp in chain if exp.date() == today), None)
        if not zero_dte_expiry:
            raise ValueError("No 0DTE expiry found today")

        options = chain[zero_dte_expiry]
        calls = sorted([o for o in options if o.option_type == 'call'], key=lambda x: x.strike_price)
        puts = sorted([o for o in options if o.option_type == 'put'], key=lambda x: x.strike_price, reverse=True)

        if direction == "bullish":
            candidates = [p for p in puts if p.strike_price <= reference_price]
            candidates = sorted(candidates, key=lambda x: x.strike_price, reverse=True)
        else:
            candidates = [c for c in calls if c.strike_price >= reference_price]
            candidates = sorted(candidates, key=lambda x: x.strike_price)

        if len(candidates) < 2:
            return None

        short_opt = candidates[0]
        # Find long leg at spread_width away
        target_long = short_opt.strike_price - self.spread_width if direction == "bullish" else short_opt.strike_price + self.spread_width
        long_opt = next((o for o in candidates if o.strike_price == target_long), None)
        if not long_opt:
            return None

        # Get quotes
        short_quote = short_opt.get_quote(self.session)
        long_quote = long_opt.get_quote(self.session)
        credit = short_quote.mid_price - long_quote.mid_price

        if credit < self.min_credit:
            return None

        legs = [
            OrderLeg(symbol=short_opt.symbol, quantity=self.quantity, action=OrderAction.SELL_TO_OPEN),
            OrderLeg(symbol=long_opt.symbol, quantity=self.quantity, action=OrderAction.BUY_TO_OPEN),
        ]

        return {
            'legs': legs,
            'credit': credit,
            'short_strike': short_opt.strike_price,
            'long_strike': long_opt.strike_price,
            'direction': direction
        }

    def run(self):
        """Main strategy execution."""
        if not self.config.get('enabled', False):
            logger.info("0DTE ORB strategy disabled")
            return

        logger.info("Running 0DTE ORB strategy")

        or_high, or_low = self.calculate_opening_range()
        current_price = self.get_current_price()

        direction = None
        trigger_level = None
        if current_price > or_high:
            direction = "bullish"
            trigger_level = or_high
        elif current_price < or_low:
            direction = "bearish"
            trigger_level = or_low

        if not direction:
            logger.info("No breakout — waiting")
            return

        logger.info(f"{direction.upper()} breakout at ${trigger_level:.2f}")

        spread = self.find_credit_spread(direction, trigger_level)
        if not spread:
            logger.info("No suitable spread found")
            return

        logger.info(f"Found {direction} credit spread: Short {spread['short_strike']}, Long {spread['long_strike']}, Credit ${spread['credit']:.2f}")

        order = UniversalOrder(
            legs=spread['legs'],
            price_effect=PriceEffect.CREDIT,
            order_type=OrderType.LIMIT,
            limit_price=spread['credit'] * 0.9,
            time_in_force="DAY",
            dry_run=self.dry_run
        )

        result = self.executor.execute("0DTE ORB Credit Spread", order)
        logger.info(f"ORB Trade Result: {result}")