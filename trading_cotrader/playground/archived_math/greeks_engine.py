"""
Greeks Engine - Real-Time Calculation & Arbitrage Detection

Architecture:
1. Calculate Greeks from first principles (Black-Scholes + refinements)
2. Compare with broker Greeks → detect mispricing
3. Real-time updates via market data feed
4. Alert on arbitrage opportunities

Key insight: Your Greeks are your competitive advantage
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import logging

logger = logging.getLogger(__name__)


@dataclass
class GreeksCalculation:
    """Complete Greeks calculation with metadata"""
    
    # Standard Greeks
    delta: Decimal
    gamma: Decimal
    theta: Decimal
    vega: Decimal
    rho: Decimal
    
    # Extended Greeks (for advanced strategies)
    vanna: Decimal = Decimal('0')  # dDelta/dIV
    charm: Decimal = Decimal('0')  # dDelta/dTime
    vomma: Decimal = Decimal('0')  # dVega/dIV
    
    # Calculation metadata
    calculated_iv: Decimal = Decimal('0')  # IV we calculated from price
    broker_iv: Optional[Decimal] = None    # IV broker provided
    iv_discrepancy: Decimal = Decimal('0')  # Difference
    
    timestamp: datetime = None
    calculation_method: str = "black_scholes"
    confidence: float = 1.0  # 0-1, how confident we are
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class GreeksEngine:
    """
    Calculate Greeks from first principles
    
    This is your competitive advantage:
    - Real-time calculations
    - Compare vs broker (find mispricings)
    - Detect arbitrage opportunities
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
        self.calculation_count = 0
        self.arbitrage_alerts = []
    
    def calculate_greeks(
        self,
        option_type: str,  # 'call' or 'put'
        spot_price: float,
        strike: float,
        time_to_expiry: float,  # Years
        volatility: float,
        dividend_yield: float = 0.0,
        broker_greeks: Optional[Dict] = None
    ) -> GreeksCalculation:
        """
        Calculate complete Greeks using Black-Scholes-Merton model
        
        This is the atomic function - everything else builds on this
        """
        
        try:
            # Validate inputs
            if time_to_expiry <= 0:
                logger.warning(f"Option expired or about to expire: {time_to_expiry}")
                return self._create_expired_greeks()
            
            if volatility <= 0:
                logger.error(f"Invalid volatility: {volatility}")
                volatility = 0.01  # Floor at 1%
            
            # Calculate d1 and d2 (core of Black-Scholes)
            d1 = self._calculate_d1(spot_price, strike, time_to_expiry, volatility, dividend_yield)
            d2 = d1 - volatility * np.sqrt(time_to_expiry)
            
            # Standard normal CDF and PDF
            N_d1 = norm.cdf(d1)
            N_d2 = norm.cdf(d2)
            n_d1 = norm.pdf(d1)  # PDF for gamma, vega
            
            # Calculate Greeks based on option type
            if option_type.lower() == 'call':
                delta = np.exp(-dividend_yield * time_to_expiry) * N_d1
                theta = self._calculate_call_theta(
                    spot_price, strike, time_to_expiry, volatility, 
                    dividend_yield, n_d1, N_d1, N_d2
                )
            else:  # put
                delta = np.exp(-dividend_yield * time_to_expiry) * (N_d1 - 1)
                theta = self._calculate_put_theta(
                    spot_price, strike, time_to_expiry, volatility,
                    dividend_yield, n_d1, N_d1, N_d2
                )
            
            # Greeks that are same for calls and puts
            gamma = (np.exp(-dividend_yield * time_to_expiry) * n_d1) / \
                    (spot_price * volatility * np.sqrt(time_to_expiry))
            
            vega = spot_price * np.exp(-dividend_yield * time_to_expiry) * \
                   n_d1 * np.sqrt(time_to_expiry) / 100  # Per 1% vol change
            
            rho = self._calculate_rho(
                option_type, strike, time_to_expiry, N_d1, N_d2
            ) / 100  # Per 1% rate change
            
            # Extended Greeks for advanced analysis
            vanna = self._calculate_vanna(vega, d1, d2, volatility, time_to_expiry)
            charm = self._calculate_charm(option_type, spot_price, time_to_expiry, 
                                         volatility, dividend_yield, d1, d2, n_d1)
            vomma = self._calculate_vomma(vega, d1, d2, volatility)
            
            # Create result
            result = GreeksCalculation(
                delta=Decimal(str(delta)),
                gamma=Decimal(str(gamma)),
                theta=Decimal(str(theta)),
                vega=Decimal(str(vega)),
                rho=Decimal(str(rho)),
                vanna=Decimal(str(vanna)),
                charm=Decimal(str(charm)),
                vomma=Decimal(str(vomma)),
                calculated_iv=Decimal(str(volatility)),
                timestamp=datetime.utcnow()
            )
            
            # Compare with broker Greeks if provided
            if broker_greeks:
                self._compare_with_broker(result, broker_greeks)
            
            self.calculation_count += 1
            return result
            
        except Exception as e:
            logger.error(f"Greeks calculation failed: {e}")
            logger.exception("Full trace:")
            return self._create_zero_greeks()
    
    def calculate_implied_volatility(
        self,
        option_type: str,
        market_price: float,
        spot_price: float,
        strike: float,
        time_to_expiry: float,
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculate implied volatility from market price
        
        This is CRITICAL for arbitrage detection:
        If calculated_IV != broker_IV → mispricing exists
        """
        
        try:
            # Use Brent's method to find IV that matches market price
            def objective(vol):
                theoretical_price = self._black_scholes_price(
                    option_type, spot_price, strike, time_to_expiry,
                    vol, dividend_yield
                )
                return theoretical_price - market_price
            
            # IV must be between 1% and 500%
            iv = brentq(objective, 0.01, 5.0, xtol=0.0001)
            return iv
            
        except Exception as e:
            logger.warning(f"Could not calculate IV: {e}")
            return 0.30  # Default to 30% if calculation fails
    
    def detect_arbitrage_opportunities(
        self,
        calculated_greeks: GreeksCalculation,
        broker_greeks: Dict,
        position_quantity: int,
        thresholds: Dict = None
    ) -> List[Dict]:
        """
        Detect mispricing by comparing calculated vs broker Greeks
        
        Returns list of arbitrage opportunities
        """
        
        if thresholds is None:
            thresholds = {
                'iv_difference': 0.03,      # 3% IV difference
                'delta_difference': 0.10,    # 0.10 delta difference
                'theta_difference': 5.0,     # $5/day theta difference
                'vega_difference': 0.05      # 0.05 vega difference
            }
        
        opportunities = []
        
        # IV Arbitrage
        if calculated_greeks.broker_iv:
            iv_diff = float(calculated_greeks.calculated_iv - calculated_greeks.broker_iv)
            
            if abs(iv_diff) > thresholds['iv_difference']:
                opportunities.append({
                    'type': 'IV_MISPRICING',
                    'severity': 'HIGH' if abs(iv_diff) > 0.05 else 'MEDIUM',
                    'description': f"IV discrepancy: Calculated={calculated_greeks.calculated_iv:.1%}, "
                                 f"Broker={calculated_greeks.broker_iv:.1%}",
                    'difference': iv_diff,
                    'potential_profit': self._estimate_iv_arb_profit(iv_diff, position_quantity),
                    'action': 'SELL' if iv_diff > 0 else 'BUY',
                    'confidence': calculated_greeks.confidence
                })
        
        # Delta Arbitrage (directional risk mismatch)
        if 'delta' in broker_greeks:
            delta_diff = float(calculated_greeks.delta) - float(broker_greeks['delta'])
            
            if abs(delta_diff) > thresholds['delta_difference']:
                opportunities.append({
                    'type': 'DELTA_MISMATCH',
                    'severity': 'HIGH',
                    'description': f"Hidden directional risk: Δ_calc={calculated_greeks.delta:.2f}, "
                                 f"Δ_broker={broker_greeks['delta']:.2f}",
                    'difference': delta_diff,
                    'hedge_needed': -delta_diff * position_quantity * 100,  # Shares needed
                    'action': 'HEDGE_DELTA',
                    'confidence': 0.95
                })
        
        # Theta Decay Rate (P&L bleeding)
        if 'theta' in broker_greeks:
            theta_diff = float(calculated_greeks.theta) - float(broker_greeks['theta'])
            
            if abs(theta_diff) > thresholds['theta_difference']:
                # Calculate 30-day hidden loss
                hidden_pnl_30d = theta_diff * 30 * position_quantity
                
                opportunities.append({
                    'type': 'THETA_DISCREPANCY',
                    'severity': 'MEDIUM',
                    'description': f"Hidden theta decay: Θ_calc={calculated_greeks.theta:.2f}, "
                                 f"Θ_broker={broker_greeks['theta']:.2f}",
                    'difference': theta_diff,
                    'hidden_30d_loss': hidden_pnl_30d,
                    'action': 'MONITOR' if abs(hidden_pnl_30d) < 100 else 'CLOSE_POSITION',
                    'confidence': 0.90
                })
        
        if opportunities:
            logger.warning(f"🚨 Detected {len(opportunities)} arbitrage opportunities!")
            self.arbitrage_alerts.extend(opportunities)
        
        return opportunities
    
    # Helper methods
    
    def _calculate_d1(self, S, K, T, sigma, q):
        """Calculate d1 term in Black-Scholes"""
        return (np.log(S / K) + (self.risk_free_rate - q + 0.5 * sigma**2) * T) / \
               (sigma * np.sqrt(T))
    
    def _calculate_call_theta(self, S, K, T, sigma, q, n_d1, N_d1, N_d2):
        """Calculate theta for call option (per day)"""
        term1 = -(S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
        term2 = q * S * N_d1 * np.exp(-q * T)
        term3 = -self.risk_free_rate * K * np.exp(-self.risk_free_rate * T) * N_d2
        return (term1 + term2 + term3) / 365  # Convert to per-day
    
    def _calculate_put_theta(self, S, K, T, sigma, q, n_d1, N_d1, N_d2):
        """Calculate theta for put option (per day)"""
        term1 = -(S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
        term2 = -q * S * (1 - N_d1) * np.exp(-q * T)
        term3 = self.risk_free_rate * K * np.exp(-self.risk_free_rate * T) * (1 - N_d2)
        return (term1 + term2 + term3) / 365
    
    def _calculate_rho(self, option_type, K, T, N_d1, N_d2):
        """Calculate rho"""
        if option_type.lower() == 'call':
            return K * T * np.exp(-self.risk_free_rate * T) * N_d2
        else:
            return -K * T * np.exp(-self.risk_free_rate * T) * (1 - N_d2)
    
    def _calculate_vanna(self, vega, d1, d2, sigma, T):
        """Calculate vanna (dDelta/dIV)"""
        return -vega * d2 / sigma
    
    def _calculate_charm(self, option_type, S, T, sigma, q, d1, d2, n_d1):
        """Calculate charm (dDelta/dTime)"""
        term1 = q * np.exp(-q * T) * norm.cdf(d1 if option_type.lower() == 'call' else -d1)
        term2 = np.exp(-q * T) * n_d1 * \
                (2 * (self.risk_free_rate - q) * T - d2 * sigma * np.sqrt(T)) / \
                (2 * T * sigma * np.sqrt(T))
        return term1 - term2
    
    def _calculate_vomma(self, vega, d1, d2, sigma):
        """Calculate vomma (dVega/dIV)"""
        return vega * d1 * d2 / sigma
    
    def _black_scholes_price(self, option_type, S, K, T, sigma, q):
        """Calculate theoretical option price"""
        d1 = self._calculate_d1(S, K, T, sigma, q)
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type.lower() == 'call':
            price = S * np.exp(-q * T) * norm.cdf(d1) - \
                    K * np.exp(-self.risk_free_rate * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-self.risk_free_rate * T) * norm.cdf(-d2) - \
                    S * np.exp(-q * T) * norm.cdf(-d1)
        
        return price
    
    def _compare_with_broker(self, calculated: GreeksCalculation, broker: Dict):
        """Compare calculated Greeks with broker Greeks"""
        
        if 'implied_volatility' in broker:
            calculated.broker_iv = Decimal(str(broker['implied_volatility']))
            calculated.iv_discrepancy = calculated.calculated_iv - calculated.broker_iv
            
            if abs(float(calculated.iv_discrepancy)) > 0.03:  # 3% difference
                logger.warning(
                    f"⚠️  IV Discrepancy: Calculated={calculated.calculated_iv:.1%}, "
                    f"Broker={calculated.broker_iv:.1%}"
                )
    
    def _estimate_iv_arb_profit(self, iv_diff: float, quantity: int) -> float:
        """Estimate potential profit from IV arbitrage"""
        # Simplified: 1% IV difference = ~$50 per contract for ATM options
        return abs(iv_diff) * 50 * quantity
    
    def _create_zero_greeks(self) -> GreeksCalculation:
        """Return zero Greeks for error cases"""
        return GreeksCalculation(
            delta=Decimal('0'),
            gamma=Decimal('0'),
            theta=Decimal('0'),
            vega=Decimal('0'),
            rho=Decimal('0'),
            confidence=0.0
        )
    
    def _create_expired_greeks(self) -> GreeksCalculation:
        """Return Greeks for expired options"""
        return GreeksCalculation(
            delta=Decimal('0'),
            gamma=Decimal('0'),
            theta=Decimal('0'),
            vega=Decimal('0'),
            rho=Decimal('0'),
            confidence=1.0,
            calculation_method="expired"
        )


# Example usage
if __name__ == "__main__":
    engine = GreeksEngine()
    
    # Calculate Greeks for IWM $210 call
    greeks = engine.calculate_greeks(
        option_type='call',
        spot_price=209.50,
        strike=210.00,
        time_to_expiry=0.123,  # ~45 days
        volatility=0.28,        # 28% IV
        dividend_yield=0.015
    )
    
    print(f"Delta: {greeks.delta:.4f}")
    print(f"Gamma: {greeks.gamma:.6f}")
    print(f"Theta: {greeks.theta:.2f} per day")
    print(f"Vega: {greeks.vega:.4f}")
    
    # Calculate IV from market price
    iv = engine.calculate_implied_volatility(
        option_type='call',
        market_price=3.50,
        spot_price=209.50,
        strike=210.00,
        time_to_expiry=0.123
    )
    print(f"\nImplied Volatility: {iv:.1%}")
