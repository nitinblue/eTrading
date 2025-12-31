# trading_bot/screener.py
from typing import Any, List, Dict
from trading_bot.market_data import MarketDataProvider
import logging

logger = logging.getLogger(__name__)

class OptionScreener:
    def __init__(self, market_data: MarketDataProvider, session: Any):
        self.market_data = market_data
        self.session = session

    def screen_short_put(self, underlying: str, min_iv: float = 30, max_delta: float = 0.25, min_dte: int = 30, max_dte: int = 60) -> List[Dict]:
        """Dynamic screener for short put opportunities."""
        screen_results = []
        chain = self.market_data.get_option_chain(underlying, self.session)  # Assume added method
        for expiry, strikes in chain.items():
            dte = (expiry - datetime.today()).days
            if min_dte <= dte <= max_dte:
                for opt in strikes:
                    if opt.option_type == 'put':
                        greeks = self.market_data.get_option_greeks(underlying, str(expiry.date()), opt.strike_price, 'put', self.session)
                        iv = greeks.get('implied_volatility', 0) * 100
                        delta = greeks.get('delta', 0)
                        if iv >= min_iv and abs(delta) <= max_delta:
                            screen_results.append({
                                'expiry': expiry,
                                'strike': opt.strike_price,
                                'iv': iv,
                                'delta': delta,
                                'premium': opt.ask or opt.last_price  # Approx
                            })
        logger.info(f"Screened {len(screen_results)} short put opportunities for {underlying}")
        return screen_results

    # Add more: screen_iron_condor, screen_straddle, etc.
    def screen_iron_condor(self, underlying: str, min_iv: float = 25, target_delta: float = 0.2, dte_range: tuple = (45, 90)) -> List[Dict]:
        # Similar logic, find 4 legs with criteria
        pass  # Implement as needed