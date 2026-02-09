"""
Risk Factor Models - 2D Matrix Structure
========================================

Core Concept from institutional_trading_v4.py:
- Y-axis: Unique instruments (keyed by streamer_symbol)
- X-axis: Greeks per underlying (Delta_MSFT, Gamma_MSFT, Delta_SPY, etc.)

Each instrument can have exposure to MULTIPLE underlyings:
- MSFT Call → exposes to MSFT price
- Gold/Silver Spread → exposes to Gold AND Silver prices
- SPY Put → exposes to SPY price

Aggregation: Sum each column to get total exposure per risk factor.
Then hedge each risk factor independently.

Change in P&L = Sensitivity × Position × Change in Market Data
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskFactorType(Enum):
    """Types of risk factors - each Greek is a sensitivity to a risk factor"""
    DELTA = "delta"      # Sensitivity to underlying price
    GAMMA = "gamma"      # Sensitivity of delta to price (convexity)
    THETA = "theta"      # Sensitivity to time decay
    VEGA = "vega"        # Sensitivity to implied volatility
    RHO = "rho"          # Sensitivity to interest rates


@dataclass
class InstrumentRiskRow:
    """
    One row in the risk matrix - represents ONE instrument's sensitivities.
    
    Key: streamer_symbol (unique identifier for DXLink subscription)
    
    Structure matches institutional_trading_v4.py portfolio_risks:
    {
        'Instrument': 'MSFT_Call',
        'Total_Delta_MSFT': 65.48,
        'Total_Gamma_MSFT': 1.46,
        'Total_Theta': -44.44,
        'Total_Vega_MSFT': 25.34,
        'Total_Rho_MSFT': 10.28
    }
    
    One instrument can have exposure to multiple underlyings:
    {
        'Instrument': 'Gold_Silver_Spread',
        'Total_Delta_Gold': 10,
        'Total_Delta_Silver': -10,
        ...
    }
    """
    # Primary key - must be unique, used for DXLink subscription
    streamer_symbol: str
    
    # Human-readable description
    description: str = ""
    
    # Position info
    position_quantity: int = 0
    multiplier: int = 100
    
    # Sensitivities by underlying: Dict[underlying, Dict[greek_type, value]]
    # Example: {'MSFT': {'delta': 0.65, 'gamma': 0.015, ...}, 'SPY': {...}}
    sensitivities: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)
    
    def add_sensitivity(
        self, 
        underlying: str,
        delta: Decimal = Decimal('0'),
        gamma: Decimal = Decimal('0'),
        theta: Decimal = Decimal('0'),
        vega: Decimal = Decimal('0'),
        rho: Decimal = Decimal('0'),
    ):
        """Add or update sensitivity to an underlying."""
        # Scale by position and multiplier
        scale = Decimal(str(self.position_quantity * self.multiplier))
        
        self.sensitivities[underlying] = {
            'delta': delta * scale,
            'gamma': gamma * scale,
            'theta': theta * scale,
            'vega': vega * scale,
            'rho': rho * scale,
        }
    
    def get_total_delta(self, underlying: str) -> Decimal:
        """Get total delta for specific underlying."""
        return self.sensitivities.get(underlying, {}).get('delta', Decimal('0'))
    
    def get_total_gamma(self, underlying: str) -> Decimal:
        """Get total gamma for specific underlying."""
        return self.sensitivities.get(underlying, {}).get('gamma', Decimal('0'))
    
    def get_total_theta(self) -> Decimal:
        """Get total theta (summed across all underlyings - time decay is universal)."""
        return sum(
            s.get('theta', Decimal('0')) 
            for s in self.sensitivities.values()
        )
    
    def get_total_vega(self, underlying: str) -> Decimal:
        """Get total vega for specific underlying."""
        return self.sensitivities.get(underlying, {}).get('vega', Decimal('0'))
    
    def get_total_rho(self, underlying: str) -> Decimal:
        """Get total rho for specific underlying."""
        return self.sensitivities.get(underlying, {}).get('rho', Decimal('0'))
    
    def get_underlyings(self) -> List[str]:
        """Get list of underlyings this instrument is exposed to."""
        return list(self.sensitivities.keys())
    
    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dict for DataFrame/display.
        
        Output format matches institutional_trading_v4.py:
        {
            'Instrument': 'MSFT_Call',
            'Total_Delta_MSFT': 65.48,
            'Total_Gamma_MSFT': 1.46,
            'Total_Theta': -44.44,
            ...
        }
        """
        result = {
            'Instrument': self.streamer_symbol,
            'Position': self.position_quantity,
        }
        
        total_theta = Decimal('0')
        
        for underlying, greeks in self.sensitivities.items():
            result[f'Delta_{underlying}'] = float(greeks.get('delta', 0))
            result[f'Gamma_{underlying}'] = float(greeks.get('gamma', 0))
            result[f'Vega_{underlying}'] = float(greeks.get('vega', 0))
            result[f'Rho_{underlying}'] = float(greeks.get('rho', 0))
            total_theta += greeks.get('theta', Decimal('0'))
        
        result['Total_Theta'] = float(total_theta)
        
        return result


@dataclass
class AggregatedRiskFactor:
    """
    Aggregated sensitivity for ONE underlying across ALL instruments.
    
    This is what we hedge against.
    Example: Total MSFT Delta = sum of all Delta_MSFT across portfolio
    """
    underlying: str
    
    total_delta: Decimal = Decimal('0')
    total_gamma: Decimal = Decimal('0')
    total_vega: Decimal = Decimal('0')
    total_rho: Decimal = Decimal('0')
    
    # Count of instruments contributing to this factor
    instrument_count: int = 0
    contributing_instruments: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'underlying': self.underlying,
            'delta': float(self.total_delta),
            'gamma': float(self.total_gamma),
            'vega': float(self.total_vega),
            'rho': float(self.total_rho),
            'instruments': self.instrument_count,
        }


@dataclass 
class RiskFactorMatrix:
    """
    The 2D Risk Matrix - THE core data structure.
    
    Structure:
        Y-axis (rows): Instruments keyed by streamer_symbol
        X-axis (cols): Greeks per underlying (Delta_MSFT, Gamma_MSFT, etc.)
    
    Usage:
        matrix = RiskFactorMatrix()
        
        # Add instruments
        matrix.add_instrument(
            streamer_symbol="MSFT  260321C00400000",
            description="MSFT Mar21 400 Call",
            position_quantity=100,
            multiplier=100,
            underlying="MSFT",
            delta=Decimal("0.65"),
            gamma=Decimal("0.015"),
            theta=Decimal("-0.44"),
            vega=Decimal("0.25"),
        )
        
        # Get aggregated risk factors
        aggregated = matrix.get_aggregated_risk_factors()
        # {'MSFT': AggregatedRiskFactor(...), 'SPY': ...}
        
        # Get portfolio totals
        totals = matrix.get_portfolio_totals()
        # {'delta': 150.5, 'gamma': 2.3, 'theta': -45.0, ...}
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # The matrix: Dict[streamer_symbol, InstrumentRiskRow]
    instruments: Dict[str, InstrumentRiskRow] = field(default_factory=dict)
    
    # All unique underlyings in the matrix
    _underlyings: Set[str] = field(default_factory=set)
    
    def add_instrument(
        self,
        streamer_symbol: str,
        description: str = "",
        position_quantity: int = 0,
        multiplier: int = 100,
        underlying: str = "",
        delta: Decimal = Decimal('0'),
        gamma: Decimal = Decimal('0'),
        theta: Decimal = Decimal('0'),
        vega: Decimal = Decimal('0'),
        rho: Decimal = Decimal('0'),
    ) -> InstrumentRiskRow:
        """
        Add an instrument to the matrix.
        
        If instrument exists, updates the sensitivities for the given underlying.
        """
        if streamer_symbol not in self.instruments:
            self.instruments[streamer_symbol] = InstrumentRiskRow(
                streamer_symbol=streamer_symbol,
                description=description,
                position_quantity=position_quantity,
                multiplier=multiplier,
            )
        
        row = self.instruments[streamer_symbol]
        
        # Update position if provided
        if position_quantity != 0:
            row.position_quantity = position_quantity
        if multiplier != 100:
            row.multiplier = multiplier
        
        # Add sensitivity for this underlying
        if underlying:
            row.add_sensitivity(underlying, delta, gamma, theta, vega, rho)
            self._underlyings.add(underlying)
        
        return row
    
    def add_instrument_row(self, row: InstrumentRiskRow):
        """Add a pre-built instrument row."""
        self.instruments[row.streamer_symbol] = row
        self._underlyings.update(row.get_underlyings())
    
    def get_instrument(self, streamer_symbol: str) -> Optional[InstrumentRiskRow]:
        """Get instrument by streamer symbol."""
        return self.instruments.get(streamer_symbol)
    
    def get_all_instruments(self) -> List[InstrumentRiskRow]:
        """Get all instrument rows."""
        return list(self.instruments.values())
    
    def get_underlyings(self) -> List[str]:
        """Get list of all unique underlyings."""
        return sorted(self._underlyings)
    
    def get_aggregated_risk_factors(self) -> Dict[str, AggregatedRiskFactor]:
        """
        Aggregate sensitivities by underlying.
        
        This is the key aggregation step from institutional_trading_v4.py:
        Sum each column (Delta_MSFT, Gamma_MSFT, etc.) across all rows.
        """
        aggregated: Dict[str, AggregatedRiskFactor] = {}
        
        for underlying in self._underlyings:
            agg = AggregatedRiskFactor(underlying=underlying)
            
            for row in self.instruments.values():
                if underlying in row.sensitivities:
                    sens = row.sensitivities[underlying]
                    agg.total_delta += sens.get('delta', Decimal('0'))
                    agg.total_gamma += sens.get('gamma', Decimal('0'))
                    agg.total_vega += sens.get('vega', Decimal('0'))
                    agg.total_rho += sens.get('rho', Decimal('0'))
                    agg.instrument_count += 1
                    agg.contributing_instruments.append(row.streamer_symbol)
            
            aggregated[underlying] = agg
        
        return aggregated
    
    def get_total_theta(self) -> Decimal:
        """Get total theta across all instruments (time decay is universal)."""
        return sum(row.get_total_theta() for row in self.instruments.values())
    
    def get_portfolio_totals(self) -> Dict[str, Decimal]:
        """
        Get portfolio-level totals.
        
        Returns:
            {
                'delta': total delta across all underlyings,
                'gamma': total gamma,
                'theta': total theta,
                'vega': total vega,
                'rho': total rho,
            }
        """
        aggregated = self.get_aggregated_risk_factors()
        
        return {
            'delta': sum(a.total_delta for a in aggregated.values()),
            'gamma': sum(a.total_gamma for a in aggregated.values()),
            'theta': self.get_total_theta(),
            'vega': sum(a.total_vega for a in aggregated.values()),
            'rho': sum(a.total_rho for a in aggregated.values()),
        }
    
    def get_factors_needing_hedge(
        self,
        delta_threshold: Decimal = Decimal('100'),
        gamma_threshold: Decimal = Decimal('10'),
        vega_threshold: Decimal = Decimal('500'),
    ) -> List[AggregatedRiskFactor]:
        """Get risk factors exceeding thresholds."""
        needs_hedge = []
        
        for agg in self.get_aggregated_risk_factors().values():
            if (abs(agg.total_delta) > delta_threshold or
                abs(agg.total_gamma) > gamma_threshold or
                abs(agg.total_vega) > vega_threshold):
                needs_hedge.append(agg)
        
        return needs_hedge
    
    def to_dataframe_rows(self) -> List[Dict[str, Any]]:
        """
        Convert to list of flat dicts for DataFrame display.
        
        Matches institutional_trading_v4.py portfolio_risks_df format.
        """
        return [row.to_flat_dict() for row in self.instruments.values()]
    
    def to_aggregated_table(self) -> List[Dict[str, Any]]:
        """
        Get aggregated risk factors as table rows.
        
        Matches institutional_trading_v4.py aggregated_data format:
        [
            {'Risk_Factor': 'MSFT_Delta', 'Aggregated_Value': 65.48, ...},
            {'Risk_Factor': 'MSFT_Gamma', 'Aggregated_Value': 1.46, ...},
            ...
        ]
        """
        rows = []
        aggregated = self.get_aggregated_risk_factors()
        
        for underlying, agg in sorted(aggregated.items()):
            rows.append({
                'Risk_Factor': f'{underlying}_Delta',
                'Aggregated_Value': float(agg.total_delta),
                'Instruments': agg.instrument_count,
            })
            rows.append({
                'Risk_Factor': f'{underlying}_Gamma',
                'Aggregated_Value': float(agg.total_gamma),
                'Instruments': agg.instrument_count,
            })
            rows.append({
                'Risk_Factor': f'{underlying}_Vega',
                'Aggregated_Value': float(agg.total_vega),
                'Instruments': agg.instrument_count,
            })
            rows.append({
                'Risk_Factor': f'{underlying}_Rho',
                'Aggregated_Value': float(agg.total_rho),
                'Instruments': agg.instrument_count,
            })
        
        # Add total theta (not per-underlying)
        rows.append({
            'Risk_Factor': 'Total_Theta',
            'Aggregated_Value': float(self.get_total_theta()),
            'Instruments': len(self.instruments),
        })
        
        return rows


# =============================================================================
# Factory functions
# =============================================================================

def create_risk_matrix_from_positions(positions: List[Any]) -> RiskFactorMatrix:
    """
    Create RiskFactorMatrix from list of positions.
    
    Args:
        positions: List of position objects with:
            - symbol (with ticker, asset_type, option_type, strike, expiration)
            - quantity
            - greeks (delta, gamma, theta, vega, rho)
    
    Returns:
        Populated RiskFactorMatrix
    """
    matrix = RiskFactorMatrix()
    
    for pos in positions:
        symbol = pos.symbol
        greeks = pos.greeks
        
        # Determine streamer symbol (unique key)
        if hasattr(symbol, 'get_option_symbol') and callable(symbol.get_option_symbol):
            streamer_symbol = symbol.get_option_symbol()
        else:
            streamer_symbol = symbol.ticker
        
        # Extract Greeks
        delta = Decimal(str(greeks.delta)) if greeks and greeks.delta else Decimal('0')
        gamma = Decimal(str(greeks.gamma)) if greeks and greeks.gamma else Decimal('0')
        theta = Decimal(str(greeks.theta)) if greeks and greeks.theta else Decimal('0')
        vega = Decimal(str(greeks.vega)) if greeks and greeks.vega else Decimal('0')
        rho = Decimal(str(greeks.rho)) if greeks and hasattr(greeks, 'rho') and greeks.rho else Decimal('0')
        
        # Get underlying
        underlying = symbol.ticker
        
        # Get multiplier
        multiplier = symbol.multiplier if hasattr(symbol, 'multiplier') and symbol.multiplier else 100
        
        matrix.add_instrument(
            streamer_symbol=streamer_symbol,
            description=f"{underlying} option",
            position_quantity=pos.quantity,
            multiplier=multiplier,
            underlying=underlying,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )
    
    return matrix


# =============================================================================
# Backward compatibility aliases
# =============================================================================

# For code that imports the old names
RiskFactorType_OLD = RiskFactorType
RiskFactor = AggregatedRiskFactor  # Old RiskFactor is now AggregatedRiskFactor
InstrumentSensitivity = InstrumentRiskRow  # Old name
RiskFactorContainer = RiskFactorMatrix  # Old name


def create_underlying_price_factor(underlying: str) -> AggregatedRiskFactor:
    """Factory for backward compatibility."""
    return AggregatedRiskFactor(underlying=underlying)
