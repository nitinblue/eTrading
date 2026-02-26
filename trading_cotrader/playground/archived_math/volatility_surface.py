"""
Volatility Term Structure - Professional Implementation

Key Insight: Volatility is NOT a single number - it's a surface

Dimensions:
1. Strike (volatility smile/skew)
2. Expiration (term structure)
3. Time (volatility changes over time)

This is foundational for:
- Accurate Greeks calculation
- Volatility arbitrage detection
- Risk modeling
- Hedge recommendations
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from decimal import Decimal
import numpy as np
from scipy.interpolate import griddata, RBFInterpolator
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PART 1: Volatility Surface Data Structures
# ============================================================================

@dataclass(frozen=True)
class VolatilityPoint:
    """Single point on the volatility surface"""
    
    strike: Decimal
    expiration: date
    implied_volatility: Decimal
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "market"  # 'market', 'model', 'interpolated'
    bid_iv: Optional[Decimal] = None
    ask_iv: Optional[Decimal] = None
    
    def moneyness(self, spot: Decimal) -> float:
        """Strike / Spot (for normalization)"""
        return float(self.strike / spot)
    
    def days_to_expiry_from(self, as_of: date) -> int:
        """Days until expiration"""
        return (self.expiration - as_of).days
    
    def time_to_expiry_from(self, as_of: date) -> float:
        """Time to expiration in years"""
        return self.days_to_expiry_from(as_of) / 365.25


@dataclass
class VolatilitySurface:
    """
    Complete volatility surface for an underlying
    
    This is THE data structure for professional options trading
    """
    
    underlying: str
    spot_price: Decimal
    as_of_date: datetime
    
    # The actual surface data
    points: List[VolatilityPoint] = field(default_factory=list)
    
    # Interpolator (built on-demand)
    _interpolator: Optional[Any] = field(default=None, repr=False, compare=False)
    
    def add_point(self, strike: Decimal, expiration: date, iv: Decimal, source: str = "market"):
        """Add a point to the surface"""
        point = VolatilityPoint(
            strike=strike,
            expiration=expiration,
            implied_volatility=iv,
            timestamp=self.as_of_date,
            source=source
        )
        self.points.append(point)
        self._interpolator = None  # Invalidate cache
    
    def get_iv(self, strike: Decimal, expiration: date, interpolate: bool = True) -> Decimal:
        """
        Get implied volatility for a specific strike/expiration
        
        Args:
            strike: Option strike
            expiration: Option expiration
            interpolate: If True, interpolate if exact point not found
        
        Returns:
            Implied volatility (annualized)
        """
        
        # Try exact match first
        for point in self.points:
            if point.strike == strike and point.expiration == expiration:
                return point.implied_volatility
        
        if not interpolate:
            logger.warning(f"No exact IV match for {strike}/{expiration}")
            return self._get_fallback_iv()
        
        # Interpolate
        try:
            return self._interpolate_iv(strike, expiration)
        except Exception as e:
            logger.warning(f"Interpolation failed: {e}, using fallback")
            return self._get_fallback_iv()
    
    def _interpolate_iv(self, strike: Decimal, expiration: date) -> Decimal:
        """
        Interpolate IV from surface
        
        Uses 2D interpolation: (moneyness, time_to_expiry) → IV
        """
        
        if len(self.points) < 4:
            logger.warning(f"Not enough points for interpolation: {len(self.points)}")
            return self._get_fallback_iv()
        
        # Build interpolator if needed
        if self._interpolator is None:
            self._build_interpolator()
        
        # Calculate query point
        moneyness = float(strike) / float(self.spot_price)
        dte = (expiration - self.as_of_date.date()).days / 365.25
        
        # Interpolate
        try:
            iv = self._interpolator([moneyness, dte])[0]
            return Decimal(str(max(0.01, iv)))  # Floor at 1%
        except Exception as e:
            logger.error(f"Interpolation error: {e}")
            return self._get_fallback_iv()
    
    def _build_interpolator(self):
        """Build 2D interpolator from points"""
        
        # Extract points
        moneyness = []
        time_to_expiry = []
        ivs = []
        
        for point in self.points:
            moneyness.append(point.moneyness(self.spot_price))
            time_to_expiry.append(point.time_to_expiry_from(self.as_of_date.date()))
            ivs.append(float(point.implied_volatility))
        
        # Create grid
        points_array = np.array([moneyness, time_to_expiry]).T
        values_array = np.array(ivs)
        
        # Use RBF interpolator (smooth, handles irregular grids)
        self._interpolator = RBFInterpolator(
            points_array,
            values_array,
            kernel='thin_plate_spline',
            smoothing=0.1
        )
        
        logger.info(f"Built IV interpolator with {len(self.points)} points")
    
    def _get_fallback_iv(self) -> Decimal:
        """Fallback IV when interpolation fails"""
        if self.points:
            # Use median of all points
            ivs = [float(p.implied_volatility) for p in self.points]
            return Decimal(str(np.median(ivs)))
        
        # Ultimate fallback: 30%
        return Decimal('0.30')
    
    def get_term_structure(self, strike: Optional[Decimal] = None) -> List[Tuple[date, Decimal]]:
        """
        Get volatility term structure for a specific strike (or ATM)
        
        Returns list of (expiration, IV) tuples sorted by expiration
        """
        
        if strike is None:
            # Use ATM strike
            strike = self.spot_price
        
        # Get unique expirations
        expirations = sorted(set(p.expiration for p in self.points))
        
        # Get IV for each expiration
        term_structure = []
        for exp in expirations:
            iv = self.get_iv(strike, exp)
            term_structure.append((exp, iv))
        
        return term_structure
    
    def get_volatility_smile(self, expiration: date) -> List[Tuple[Decimal, Decimal]]:
        """
        Get volatility smile for a specific expiration
        
        Returns list of (strike, IV) tuples sorted by strike
        """
        
        # Filter points for this expiration
        exp_points = [p for p in self.points if p.expiration == expiration]
        
        if not exp_points:
            logger.warning(f"No points for expiration {expiration}")
            return []
        
        # Sort by strike
        exp_points.sort(key=lambda p: p.strike)
        
        return [(p.strike, p.implied_volatility) for p in exp_points]
    
    def get_skew(self, expiration: date) -> Decimal:
        """
        Calculate volatility skew for an expiration
        
        Skew = IV(90% strike) - IV(110% strike)
        Positive skew = puts more expensive (typical)
        """
        
        atm = self.spot_price
        otm_put_strike = atm * Decimal('0.90')
        otm_call_strike = atm * Decimal('1.10')
        
        put_iv = self.get_iv(otm_put_strike, expiration)
        call_iv = self.get_iv(otm_call_strike, expiration)
        
        return put_iv - call_iv
    
    def summary(self) -> Dict:
        """Get summary statistics"""
        
        if not self.points:
            return {'error': 'No data'}
        
        ivs = [float(p.implied_volatility) for p in self.points]
        expirations = set(p.expiration for p in self.points)
        strikes = set(p.strike for p in self.points)
        
        atm_exp = min(expirations)
        
        return {
            'underlying': self.underlying,
            'spot': float(self.spot_price),
            'num_points': len(self.points),
            'num_expirations': len(expirations),
            'num_strikes': len(strikes),
            'iv_range': (min(ivs), max(ivs)),
            'atm_iv': float(self.get_iv(self.spot_price, atm_exp)),
            'as_of': self.as_of_date.isoformat()
        }


# ============================================================================
# PART 2: Volatility Surface Builder
# ============================================================================

class VolatilitySurfaceBuilder:
    """Build volatility surface from market data"""
    
    @staticmethod
    def from_option_chain(
        underlying: str,
        spot_price: Decimal,
        option_chain: List[Dict]
    ) -> VolatilitySurface:
        """
        Build surface from option chain data
        
        Args:
            underlying: Underlying symbol
            spot_price: Current spot price
            option_chain: List of option quotes with IV
                         [{'strike': 210, 'expiration': date(2026,2,21), 'iv': 0.28}, ...]
        
        Returns:
            VolatilitySurface
        """
        
        surface = VolatilitySurface(
            underlying=underlying,
            spot_price=spot_price,
            as_of_date=datetime.utcnow()
        )
        
        for option in option_chain:
            if 'iv' in option and option['iv']:
                surface.add_point(
                    strike=Decimal(str(option['strike'])),
                    expiration=option['expiration'],
                    iv=Decimal(str(option['iv'])),
                    source='market'
                )
        
        logger.info(f"Built surface for {underlying} with {len(surface.points)} points")
        return surface
    
    @staticmethod
    def from_positions(
        underlying: str,
        spot_price: Decimal,
        positions: List,
        greeks_engine
    ) -> VolatilitySurface:
        """
        Build surface from your current positions
        
        This extracts IV from your position prices
        """
        from trading_cotrader.core.models.domain import AssetType
        
        surface = VolatilitySurface(
            underlying=underlying,
            spot_price=spot_price,
            as_of_date=datetime.utcnow()
        )
        
        for pos in positions:
            if pos.symbol.asset_type != AssetType.OPTION:
                continue
            
            if pos.symbol.ticker != underlying:
                continue
            
            # Extract IV from position price
            try:
                time_to_expiry = (pos.symbol.expiration - datetime.utcnow()).total_seconds() / (365.25 * 24 * 3600)
                
                if time_to_expiry > 0 and pos.current_price and pos.current_price > 0:
                    iv = greeks_engine.calculate_implied_volatility(
                        option_type=pos.symbol.option_type.value,
                        market_price=float(pos.current_price),
                        spot_price=float(spot_price),
                        strike=float(pos.symbol.strike),
                        time_to_expiry=time_to_expiry
                    )
                    
                    surface.add_point(
                        strike=pos.symbol.strike,
                        expiration=pos.symbol.expiration.date(),
                        iv=Decimal(str(iv)),
                        source='position'
                    )
            except Exception as e:
                logger.debug(f"Could not extract IV from {pos.symbol.ticker}: {e}")
                continue
        
        return surface


if __name__ == "__main__":
    from decimal import Decimal
    from datetime import date

    surface = VolatilitySurface('TEST', Decimal('100'), datetime.now())
    surface.add_point(Decimal('100'), date(2026, 2, 21), Decimal('0.30'))
    print('✓ Volatility surface works')
