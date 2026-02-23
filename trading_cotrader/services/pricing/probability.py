"""
Probability Calculations for Options

Calculate:
- Probability of Profit (POP)
- Probability In-The-Money (ITM)
- Expected Move
- Expected Value of trades
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple, List
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProbabilityResult:
    """Result of probability calculation"""
    probability_of_profit: float
    probability_max_profit: float
    probability_max_loss: float
    probability_breakeven: float

    expected_value: float
    expected_return_percent: float

    # Breakeven points
    breakeven_prices: List[float]

    # Max profit / loss (positive numbers; inf for undefined risk)
    max_profit: float = 0.0
    max_loss: float = 0.0


class ProbabilityCalculator:
    """
    Calculate probabilities for options trades.
    
    Usage:
        calc = ProbabilityCalculator()
        
        # Probability of single option being ITM
        p_itm = calc.probability_itm(strike=100, spot=95, vol=0.25, days=30, opt_type='put')
        
        # Expected move
        low, high = calc.expected_move(spot=100, vol=0.25, days=30)
        
        # Probability of profit for a trade
        pop = calc.probability_of_profit(trade, spot=100, vol=0.25)
    """
    
    def probability_itm(
        self,
        strike: float,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        option_type: str,  # 'call' or 'put'
        rate: float = 0.05
    ) -> float:
        """
        Calculate probability option expires in-the-money.
        
        Uses lognormal distribution assumption.
        
        Args:
            strike: Strike price
            spot: Current underlying price
            volatility: Implied volatility (annualized)
            days_to_expiry: Days until expiration
            option_type: 'call' or 'put'
            rate: Risk-free rate
            
        Returns:
            Probability (0-1) of expiring ITM
        """
        if days_to_expiry <= 0:
            if option_type.lower() == 'call':
                return 1.0 if spot > strike else 0.0
            else:
                return 1.0 if spot < strike else 0.0
        
        time_to_expiry = days_to_expiry / 365
        sqrt_t = math.sqrt(time_to_expiry)
        
        # Use risk-neutral probability (d2 from Black-Scholes)
        d2 = (
            math.log(spot / strike) + 
            (rate - 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * sqrt_t)
        
        if option_type.lower() == 'call':
            return self._norm_cdf(d2)
        else:
            return self._norm_cdf(-d2)
    
    def probability_otm(
        self,
        strike: float,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        option_type: str,
        rate: float = 0.05
    ) -> float:
        """Probability option expires out-of-the-money."""
        return 1 - self.probability_itm(strike, spot, volatility, days_to_expiry, option_type, rate)
    
    def probability_between(
        self,
        low_price: float,
        high_price: float,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        rate: float = 0.05
    ) -> float:
        """
        Probability underlying ends between two prices at expiration.
        
        Useful for iron condors, strangles, etc.
        """
        if days_to_expiry <= 0:
            return 1.0 if low_price <= spot <= high_price else 0.0
        
        time_to_expiry = days_to_expiry / 365
        sqrt_t = math.sqrt(time_to_expiry)
        
        def calc_d2(strike):
            return (
                math.log(spot / strike) + 
                (rate - 0.5 * volatility ** 2) * time_to_expiry
            ) / (volatility * sqrt_t)
        
        d2_low = calc_d2(low_price)
        d2_high = calc_d2(high_price)
        
        # Probability of ending above low AND below high
        p_above_low = self._norm_cdf(d2_low)
        p_below_high = self._norm_cdf(-d2_high)
        
        return p_above_low - (1 - p_below_high)
    
    def expected_move(
        self,
        spot: float,
        volatility: float,
        days: int,
        confidence: float = 0.68  # 1 standard deviation
    ) -> Tuple[float, float]:
        """
        Calculate expected price range.
        
        Args:
            spot: Current price
            volatility: Implied volatility (annualized)
            days: Number of days
            confidence: Confidence level (0.68 = 1 sigma, 0.95 = 2 sigma)
            
        Returns:
            Tuple of (low_price, high_price)
        """
        time_to_expiry = days / 365
        
        # Calculate number of standard deviations for confidence level
        if confidence == 0.68:
            num_sigma = 1.0
        elif confidence == 0.95:
            num_sigma = 1.96
        elif confidence == 0.99:
            num_sigma = 2.576
        else:
            # Inverse of normal CDF
            num_sigma = self._norm_inv((1 + confidence) / 2)
        
        # Expected move (using lognormal)
        expected_move = spot * volatility * math.sqrt(time_to_expiry) * num_sigma
        
        return (spot - expected_move, spot + expected_move)
    
    def expected_move_dollars(
        self,
        spot: float,
        volatility: float,
        days: int
    ) -> float:
        """
        Get expected dollar move (1 sigma).
        
        This is what the market is pricing in for the expected move.
        """
        time_to_expiry = days / 365
        return spot * volatility * math.sqrt(time_to_expiry)
    
    def expected_value(
        self,
        max_profit: float,
        max_loss: float,
        probability_of_profit: float
    ) -> float:
        """
        Calculate expected value of a trade.
        
        EV = (POP × Max Profit) - ((1-POP) × Max Loss)
        
        Args:
            max_profit: Maximum profit (positive number)
            max_loss: Maximum loss (positive number)
            probability_of_profit: Probability of profit (0-1)
            
        Returns:
            Expected value (can be negative)
        """
        return (probability_of_profit * max_profit) - ((1 - probability_of_profit) * max_loss)
    
    def probability_of_profit_vertical(
        self,
        short_strike: float,
        long_strike: float,
        premium_received: float,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        is_put_spread: bool = True,
        rate: float = 0.05
    ) -> ProbabilityResult:
        """
        Calculate POP for a vertical spread.
        
        For credit spreads, profit = premium received if OTM at expiration.
        For debit spreads, need to reach breakeven.
        
        Args:
            short_strike: Strike of short option
            long_strike: Strike of long option
            premium_received: Net premium (positive for credit, negative for debit)
            spot: Current underlying price
            volatility: Implied volatility
            days_to_expiry: Days until expiration
            is_put_spread: True for put spread, False for call spread
            rate: Risk-free rate
            
        Returns:
            ProbabilityResult with all probability metrics
        """
        # Determine if credit or debit spread
        is_credit = premium_received > 0
        
        # Calculate breakeven
        if is_put_spread:
            if is_credit:  # Bull put spread
                breakeven = short_strike - premium_received
            else:  # Bear put spread (debit)
                breakeven = long_strike - abs(premium_received)
        else:
            if is_credit:  # Bear call spread
                breakeven = short_strike + premium_received
            else:  # Bull call spread (debit)
                breakeven = long_strike + abs(premium_received)
        
        # Calculate width
        width = abs(short_strike - long_strike)
        
        # Max profit and loss
        if is_credit:
            max_profit = premium_received
            max_loss = width - premium_received
        else:
            max_profit = width - abs(premium_received)
            max_loss = abs(premium_received)
        
        # Calculate probabilities
        if is_put_spread:
            # For put spreads, profit if above breakeven
            pop = 1 - self.probability_itm(breakeven, spot, volatility, days_to_expiry, 'put', rate)
            p_max_profit = 1 - self.probability_itm(short_strike, spot, volatility, days_to_expiry, 'put', rate)
            p_max_loss = self.probability_itm(long_strike, spot, volatility, days_to_expiry, 'put', rate)
        else:
            # For call spreads, profit if below breakeven
            pop = 1 - self.probability_itm(breakeven, spot, volatility, days_to_expiry, 'call', rate)
            p_max_profit = 1 - self.probability_itm(short_strike, spot, volatility, days_to_expiry, 'call', rate)
            p_max_loss = self.probability_itm(long_strike, spot, volatility, days_to_expiry, 'call', rate)
        
        ev = self.expected_value(max_profit, max_loss, pop)
        
        return ProbabilityResult(
            probability_of_profit=pop,
            probability_max_profit=p_max_profit,
            probability_max_loss=p_max_loss,
            probability_breakeven=0.5,  # By definition at breakeven
            expected_value=ev,
            expected_return_percent=(ev / max_loss * 100) if max_loss > 0 else 0,
            breakeven_prices=[breakeven],
            max_profit=max_profit,
            max_loss=max_loss,
        )
    
    def probability_of_profit_iron_condor(
        self,
        put_long_strike: float,
        put_short_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        premium_received: float,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        rate: float = 0.05
    ) -> ProbabilityResult:
        """
        Calculate POP for an iron condor.
        
        Profit if price stays between short strikes minus premium.
        """
        # Breakevens
        lower_breakeven = put_short_strike - premium_received
        upper_breakeven = call_short_strike + premium_received
        
        # Width
        put_width = put_short_strike - put_long_strike
        call_width = call_long_strike - call_short_strike
        max_width = max(put_width, call_width)
        
        max_profit = premium_received
        max_loss = max_width - premium_received
        
        # POP = probability of staying between breakevens
        pop = self.probability_between(
            lower_breakeven, upper_breakeven,
            spot, volatility, days_to_expiry, rate
        )
        
        # Probability of max profit = staying between short strikes
        p_max_profit = self.probability_between(
            put_short_strike, call_short_strike,
            spot, volatility, days_to_expiry, rate
        )
        
        ev = self.expected_value(max_profit, max_loss, pop)
        
        return ProbabilityResult(
            probability_of_profit=pop,
            probability_max_profit=p_max_profit,
            probability_max_loss=1 - pop - (p_max_profit - pop) * 0.5,  # Rough estimate
            probability_breakeven=0.5,
            expected_value=ev,
            expected_return_percent=(ev / max_loss * 100) if max_loss > 0 else 0,
            breakeven_prices=[lower_breakeven, upper_breakeven],
            max_profit=max_profit,
            max_loss=max_loss,
        )
    
    def compute_trade_payoff(
        self,
        legs: List[dict],
        spot: float,
        iv: float,
        dte: int,
        premium: Optional[float] = None,
        rate: float = 0.05,
    ) -> ProbabilityResult:
        """
        Compute payoff for any multi-leg options trade.

        Detects strategy type from legs and delegates to the correct calculator.

        Args:
            legs: List of dicts with keys: strike, option_type, quantity, side
            spot: Current underlying price
            iv: Implied volatility (annualized, e.g. 0.25)
            dte: Days to expiration
            premium: Net premium received (positive=credit). If None, estimated.
            rate: Risk-free rate

        Returns:
            ProbabilityResult with POP, EV, breakevens, max profit/loss
        """
        if not legs:
            return ProbabilityResult(
                probability_of_profit=0, probability_max_profit=0,
                probability_max_loss=1, probability_breakeven=0.5,
                expected_value=0, expected_return_percent=0,
                breakeven_prices=[],
            )

        # Classify legs
        puts = [l for l in legs if l.get('option_type', '').lower() == 'put']
        calls = [l for l in legs if l.get('option_type', '').lower() == 'call']
        short_legs = [l for l in legs if l.get('quantity', 0) < 0 or l.get('side', '').lower() in ('sell', 'sell_to_open')]
        long_legs = [l for l in legs if l.get('quantity', 0) > 0 or l.get('side', '').lower() in ('buy', 'buy_to_open')]

        # Iron condor: 4 legs, both puts and calls
        if len(legs) == 4 and len(puts) == 2 and len(calls) == 2:
            return self._payoff_iron_condor(puts, calls, spot, iv, dte, premium, rate)

        # Vertical spread: 2 legs, same option type
        if len(legs) == 2 and (len(puts) == 2 or len(calls) == 2):
            return self._payoff_vertical(legs, spot, iv, dte, premium, rate)

        # Single leg
        if len(legs) == 1:
            return self._payoff_single(legs[0], spot, iv, dte, premium, rate)

        # Strangle: 2 legs, 1 put + 1 call
        if len(legs) == 2 and len(puts) == 1 and len(calls) == 1:
            return self._payoff_strangle(puts[0], calls[0], spot, iv, dte, premium, rate)

        # Fallback: treat as custom multi-leg, estimate from outer strikes
        return self._payoff_fallback(legs, spot, iv, dte, premium, rate)

    def _payoff_iron_condor(
        self, puts, calls, spot, iv, dte, premium, rate
    ) -> ProbabilityResult:
        put_strikes = sorted([float(l['strike']) for l in puts])
        call_strikes = sorted([float(l['strike']) for l in calls])
        put_long, put_short = put_strikes[0], put_strikes[1]
        call_short, call_long = call_strikes[0], call_strikes[1]

        width = max(put_short - put_long, call_long - call_short)
        if premium is None:
            premium = width * 0.33  # rough estimate: 1/3 of width

        return self.probability_of_profit_iron_condor(
            put_long_strike=put_long,
            put_short_strike=put_short,
            call_short_strike=call_short,
            call_long_strike=call_long,
            premium_received=abs(premium),
            spot=spot, volatility=iv, days_to_expiry=dte, rate=rate,
        )

    def _payoff_vertical(
        self, legs, spot, iv, dte, premium, rate
    ) -> ProbabilityResult:
        strikes = sorted([float(l['strike']) for l in legs])
        option_type = legs[0].get('option_type', 'put').lower()
        is_put = option_type == 'put'

        width = strikes[1] - strikes[0]
        # Determine credit/debit from leg sides
        short_leg = next(
            (l for l in legs if l.get('quantity', 0) < 0 or l.get('side', '').lower() in ('sell', 'sell_to_open')),
            None,
        )
        if short_leg:
            short_strike = float(short_leg['strike'])
        else:
            # Default: higher strike is short for puts, lower for calls
            short_strike = strikes[1] if is_put else strikes[0]

        long_strike = strikes[0] if short_strike == strikes[1] else strikes[1]

        if premium is None:
            premium = width * 0.30  # rough estimate

        return self.probability_of_profit_vertical(
            short_strike=short_strike,
            long_strike=long_strike,
            premium_received=abs(premium),
            spot=spot, volatility=iv, days_to_expiry=dte,
            is_put_spread=is_put, rate=rate,
        )

    def _payoff_single(
        self, leg, spot, iv, dte, premium, rate
    ) -> ProbabilityResult:
        strike = float(leg['strike'])
        opt_type = leg.get('option_type', 'put').lower()
        is_short = leg.get('quantity', 0) < 0 or leg.get('side', '').lower() in ('sell', 'sell_to_open')

        if premium is None:
            premium = spot * iv * math.sqrt(dte / 365) * 0.4  # rough BS estimate

        if is_short:
            pop = self.probability_otm(strike, spot, iv, dte, opt_type, rate)
            max_profit = abs(premium)
            max_loss = float('inf')  # undefined risk
            ev = self.expected_value(max_profit, max_profit * 2, pop)  # cap at 2x for EV
        else:
            pop = self.probability_itm(strike, spot, iv, dte, opt_type, rate)
            max_profit = float('inf')
            max_loss = abs(premium)
            ev = self.expected_value(max_loss * 2, max_loss, pop)  # target 2:1

        breakeven = strike - abs(premium) if opt_type == 'put' else strike + abs(premium)
        if is_short:
            breakeven = strike + abs(premium) if opt_type == 'call' else strike - abs(premium)

        return ProbabilityResult(
            probability_of_profit=pop,
            probability_max_profit=pop * 0.5,  # rough estimate
            probability_max_loss=1 - pop,
            probability_breakeven=0.5,
            expected_value=ev,
            expected_return_percent=(ev / max_loss * 100) if max_loss and max_loss != float('inf') else 0,
            breakeven_prices=[breakeven],
            max_profit=max_profit,
            max_loss=max_loss,
        )

    def _payoff_strangle(
        self, put_leg, call_leg, spot, iv, dte, premium, rate
    ) -> ProbabilityResult:
        put_strike = float(put_leg['strike'])
        call_strike = float(call_leg['strike'])
        is_short = put_leg.get('quantity', 0) < 0 or put_leg.get('side', '').lower() in ('sell', 'sell_to_open')

        if premium is None:
            premium = spot * iv * math.sqrt(dte / 365) * 0.6

        if is_short:
            lower_be = put_strike - abs(premium)
            upper_be = call_strike + abs(premium)
            pop = self.probability_between(lower_be, upper_be, spot, iv, dte, rate)
            max_profit = abs(premium)
            max_loss = float('inf')  # undefined
            ev = self.expected_value(max_profit, max_profit * 3, pop)
        else:
            lower_be = put_strike - abs(premium)
            upper_be = call_strike + abs(premium)
            pop = 1 - self.probability_between(lower_be, upper_be, spot, iv, dte, rate)
            max_profit = float('inf')
            max_loss = abs(premium)
            ev = self.expected_value(max_loss * 3, max_loss, pop)

        return ProbabilityResult(
            probability_of_profit=pop,
            probability_max_profit=pop * 0.3,
            probability_max_loss=1 - pop,
            probability_breakeven=0.5,
            expected_value=ev,
            expected_return_percent=(ev / max_loss * 100) if max_loss and max_loss != float('inf') else 0,
            breakeven_prices=[lower_be, upper_be],
            max_profit=max_profit,
            max_loss=max_loss,
        )

    def _payoff_fallback(
        self, legs, spot, iv, dte, premium, rate
    ) -> ProbabilityResult:
        """Fallback for complex multi-leg trades: use outer strikes as bounds."""
        strikes = sorted([float(l['strike']) for l in legs if l.get('strike')])
        if len(strikes) < 2:
            return ProbabilityResult(
                probability_of_profit=0.5, probability_max_profit=0.25,
                probability_max_loss=0.25, probability_breakeven=0.5,
                expected_value=0, expected_return_percent=0,
                breakeven_prices=strikes,
            )
        pop = self.probability_between(strikes[0], strikes[-1], spot, iv, dte, rate)
        width = strikes[-1] - strikes[0]
        est_premium = width * 0.25 if premium is None else abs(premium)
        max_profit = est_premium
        max_loss = width - est_premium
        ev = self.expected_value(max_profit, max_loss, pop)

        return ProbabilityResult(
            probability_of_profit=pop,
            probability_max_profit=pop * 0.5,
            probability_max_loss=1 - pop,
            probability_breakeven=0.5,
            expected_value=ev,
            expected_return_percent=(ev / max_loss * 100) if max_loss > 0 else 0,
            breakeven_prices=[strikes[0] + est_premium, strikes[-1] - est_premium],
            max_profit=max_profit,
            max_loss=max_loss,
        )

    def _norm_cdf(self, x: float) -> float:
        """Cumulative distribution function for standard normal."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    def _norm_inv(self, p: float) -> float:
        """Inverse of normal CDF (approximate)."""
        # Rational approximation for inverse normal
        if p <= 0:
            return float('-inf')
        if p >= 1:
            return float('inf')
        
        # Coefficients
        a = [
            -3.969683028665376e+01,
            2.209460984245205e+02,
            -2.759285104469687e+02,
            1.383577518672690e+02,
            -3.066479806614716e+01,
            2.506628277459239e+00
        ]
        b = [
            -5.447609879822406e+01,
            1.615858368580409e+02,
            -1.556989798598866e+02,
            6.680131188771972e+01,
            -1.328068155288572e+01
        ]
        c = [
            -7.784894002430293e-03,
            -3.223964580411365e-01,
            -2.400758277161838e+00,
            -2.549732539343734e+00,
            4.374664141464968e+00,
            2.938163982698783e+00
        ]
        d = [
            7.784695709041462e-03,
            3.224671290700398e-01,
            2.445134137142996e+00,
            3.754408661907416e+00
        ]
        
        p_low = 0.02425
        p_high = 1 - p_low
        
        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
                   (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
        else:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                    ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    calc = ProbabilityCalculator()
    
    # Example: SPY at $500, 30-day options, 15% IV
    spot = 500
    vol = 0.15
    days = 30
    
    # Expected move
    low, high = calc.expected_move(spot, vol, days)
    print(f"Expected Move (1σ): ${low:.2f} - ${high:.2f}")
    print(f"Expected Move Dollars: ${calc.expected_move_dollars(spot, vol, days):.2f}")
    
    # Probability ITM for a put at $490
    p_itm = calc.probability_itm(strike=490, spot=spot, volatility=vol, days_to_expiry=days, option_type='put')
    print(f"\n$490 Put P(ITM): {p_itm*100:.1f}%")
    
    # Bull put spread: short 490, long 485, $1.50 credit
    result = calc.probability_of_profit_vertical(
        short_strike=490,
        long_strike=485,
        premium_received=1.50,
        spot=spot,
        volatility=vol,
        days_to_expiry=days,
        is_put_spread=True
    )
    print(f"\nBull Put Spread 490/485:")
    print(f"  POP: {result.probability_of_profit*100:.1f}%")
    print(f"  P(Max Profit): {result.probability_max_profit*100:.1f}%")
    print(f"  Expected Value: ${result.expected_value:.2f}")
    print(f"  Breakeven: ${result.breakeven_prices[0]:.2f}")
