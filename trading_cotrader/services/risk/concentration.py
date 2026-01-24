"""
Concentration Risk Checker

Monitor and enforce concentration limits:
- Single underlying exposure
- Strategy type concentration
- Directional exposure (long/short/neutral)
- Expiration concentration
- Sector concentration
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConcentrationType(Enum):
    """Types of concentration to check"""
    UNDERLYING = "underlying"
    STRATEGY = "strategy"
    DIRECTION = "direction"
    EXPIRATION = "expiration"
    SECTOR = "sector"


class Direction(Enum):
    """Directional exposure classification"""
    LONG = "long"       # Positive delta
    SHORT = "short"     # Negative delta
    NEUTRAL = "neutral" # Near-zero delta


@dataclass
class ConcentrationLimit:
    """Definition of a concentration limit"""
    name: str
    concentration_type: ConcentrationType
    max_percent: float  # Maximum % of portfolio
    warning_percent: float  # Warning threshold
    description: str = ""


@dataclass
class ConcentrationViolation:
    """A concentration limit violation"""
    limit: ConcentrationLimit
    current_percent: float
    excess_percent: float
    symbol_or_category: str
    is_warning: bool  # vs breach


@dataclass
class ConcentrationResult:
    """Result of concentration analysis"""
    by_underlying: Dict[str, float] = field(default_factory=dict)
    by_strategy: Dict[str, float] = field(default_factory=dict)
    by_direction: Dict[str, float] = field(default_factory=dict)
    by_expiration: Dict[str, float] = field(default_factory=dict)
    by_sector: Dict[str, float] = field(default_factory=dict)
    
    max_underlying: Tuple[str, float] = ("", 0.0)
    max_strategy: Tuple[str, float] = ("", 0.0)
    
    violations: List[ConcentrationViolation] = field(default_factory=list)
    passes_all_limits: bool = True
    diversification_score: float = 0.0


DEFAULT_LIMITS = [
    ConcentrationLimit("Single Underlying", ConcentrationType.UNDERLYING, 20.0, 15.0),
    ConcentrationLimit("Strategy Type", ConcentrationType.STRATEGY, 40.0, 30.0),
    ConcentrationLimit("Directional Exposure", ConcentrationType.DIRECTION, 60.0, 50.0),
    ConcentrationLimit("Single Expiration", ConcentrationType.EXPIRATION, 50.0, 40.0),
]


class ConcentrationChecker:
    """Check and enforce concentration limits."""
    
    def __init__(self, limits: List[ConcentrationLimit] = None):
        self.limits = limits or DEFAULT_LIMITS
    
    def check_concentration(
        self,
        positions: List,
        portfolio_value: Decimal
    ) -> ConcentrationResult:
        """Check all concentration limits."""
        result = ConcentrationResult()
        
        if portfolio_value == 0:
            return result
        
        result.by_underlying = self._calc_underlying(positions, portfolio_value)
        if result.by_underlying:
            max_ticker = max(result.by_underlying, key=result.by_underlying.get)
            result.max_underlying = (max_ticker, result.by_underlying[max_ticker])
        
        result.by_strategy = self._calc_strategy(positions, portfolio_value)
        result.by_direction = self._calc_direction(positions, portfolio_value)
        result.by_expiration = self._calc_expiration(positions, portfolio_value)
        
        for limit in self.limits:
            result.violations.extend(self._check_limit(limit, result))
        
        result.passes_all_limits = not any(not v.is_warning for v in result.violations)
        result.diversification_score = self._calc_diversification(result)
        
        return result
    
    def _calc_underlying(self, positions: List, portfolio_value: Decimal) -> Dict[str, float]:
        by_underlying = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(float(getattr(pos, 'market_value', Decimal('0'))))
            by_underlying[ticker] = by_underlying.get(ticker, 0) + value
        total = float(portfolio_value)
        return {k: (v / total * 100) for k, v in by_underlying.items()}
    
    def _calc_strategy(self, positions: List, portfolio_value: Decimal) -> Dict[str, float]:
        by_strategy = {}
        for pos in positions:
            symbol = getattr(pos, 'symbol', None)
            asset_type = getattr(symbol, 'asset_type', None)
            strategy = asset_type.value if asset_type and hasattr(asset_type, 'value') else 'equity'
            value = abs(float(getattr(pos, 'market_value', Decimal('0'))))
            by_strategy[strategy] = by_strategy.get(strategy, 0) + value
        total = float(portfolio_value)
        return {k: (v / total * 100) for k, v in by_strategy.items()}
    
    def _calc_direction(self, positions: List, portfolio_value: Decimal) -> Dict[str, float]:
        long_val, short_val, neutral_val = Decimal('0'), Decimal('0'), Decimal('0')
        for pos in positions:
            greeks = getattr(pos, 'greeks', None)
            delta = float(getattr(greeks, 'delta', 0)) if greeks else 0
            value = abs(getattr(pos, 'market_value', Decimal('0')))
            if delta > 5:
                long_val += value
            elif delta < -5:
                short_val += value
            else:
                neutral_val += value
        total = float(portfolio_value)
        if total == 0:
            return {}
        return {
            'long': float(long_val) / total * 100,
            'short': float(short_val) / total * 100,
            'neutral': float(neutral_val) / total * 100
        }
    
    def _calc_expiration(self, positions: List, portfolio_value: Decimal) -> Dict[str, float]:
        by_exp = {}
        for pos in positions:
            exp = getattr(getattr(pos, 'symbol', None), 'expiration', None)
            week_key = exp.strftime("%Y-W%W") if exp else "no_expiration"
            value = abs(float(getattr(pos, 'market_value', Decimal('0'))))
            by_exp[week_key] = by_exp.get(week_key, 0) + value
        total = float(portfolio_value)
        return {k: (v / total * 100) for k, v in by_exp.items()}
    
    def _check_limit(self, limit: ConcentrationLimit, result: ConcentrationResult) -> List[ConcentrationViolation]:
        violations = []
        data_map = {
            ConcentrationType.UNDERLYING: result.by_underlying,
            ConcentrationType.STRATEGY: result.by_strategy,
            ConcentrationType.DIRECTION: result.by_direction,
            ConcentrationType.EXPIRATION: result.by_expiration,
        }
        data = data_map.get(limit.concentration_type, {})
        for category, pct in data.items():
            if pct > limit.max_percent:
                violations.append(ConcentrationViolation(limit, pct, pct - limit.max_percent, category, False))
            elif pct > limit.warning_percent:
                violations.append(ConcentrationViolation(limit, pct, 0, category, True))
        return violations
    
    def _calc_diversification(self, result: ConcentrationResult) -> float:
        if not result.by_underlying:
            return 0.0
        hhi = sum((pct/100)**2 for pct in result.by_underlying.values())
        score = 1 - hhi
        penalty = len([v for v in result.violations if not v.is_warning]) * 0.1
        return max(0, score - penalty)
