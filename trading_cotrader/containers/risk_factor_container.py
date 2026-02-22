"""
Risk Factor Container - Aggregated risk by underlying

Aggregates positions by underlying to provide:
- Greeks totals per underlying
- Exposure metrics
- Risk limit monitoring
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskFactorState:
    """Aggregated risk for one underlying"""
    underlying: str

    # Aggregated Greeks
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')

    # Dollar exposure
    delta_dollars: Decimal = Decimal('0')
    gamma_dollars: Decimal = Decimal('0')

    # Position counts
    position_count: int = 0
    long_count: int = 0
    short_count: int = 0

    # Exposure
    gross_exposure: Decimal = Decimal('0')
    net_exposure: Decimal = Decimal('0')

    # Market data
    spot_price: Decimal = Decimal('0')
    spot_change_pct: Decimal = Decimal('0')

    # P&L
    unrealized_pnl: Decimal = Decimal('0')
    daily_pnl: Decimal = Decimal('0')

    # Limits
    delta_limit: Decimal = Decimal('200')
    delta_utilization_pct: Decimal = Decimal('0')

    # Status
    risk_status: str = "OK"

    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'underlying': self.underlying,
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'delta_dollars': float(self.delta_dollars),
            'gamma_dollars': float(self.gamma_dollars),
            'position_count': self.position_count,
            'long_count': self.long_count,
            'short_count': self.short_count,
            'gross_exposure': float(self.gross_exposure),
            'net_exposure': float(self.net_exposure),
            'spot_price': float(self.spot_price),
            'spot_change_pct': float(self.spot_change_pct),
            'unrealized_pnl': float(self.unrealized_pnl),
            'daily_pnl': float(self.daily_pnl),
            'delta_limit': float(self.delta_limit),
            'delta_utilization_pct': float(self.delta_utilization_pct),
            'risk_status': self.risk_status,
            'last_updated': self.last_updated.isoformat(),
        }


class RiskFactorContainer:
    """
    In-memory container for aggregated risk factors.

    Aggregates position data by underlying for risk monitoring.
    """

    def __init__(self):
        self._risk_factors: Dict[str, RiskFactorState] = {}
        self._previous_states: Dict[str, Dict[str, Any]] = {}
        self._change_listeners: List[Callable] = []
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def underlyings(self) -> List[str]:
        return list(self._risk_factors.keys())

    def add_change_listener(self, callback: Callable):
        self._change_listeners.append(callback)

    def remove_change_listener(self, callback: Callable):
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_changes(self, underlying: str, changes: Dict[str, Any]):
        for listener in self._change_listeners:
            try:
                listener('risk_factor', {'underlying': underlying, 'changes': changes})
            except Exception as e:
                logger.error(f"Error in change listener: {e}")

    def get(self, underlying: str) -> Optional[RiskFactorState]:
        return self._risk_factors.get(underlying)

    def get_all(self) -> List[RiskFactorState]:
        return list(self._risk_factors.values())

    def aggregate_from_positions(self, position_container) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate risk factors from position container.
        Returns dict of {underlying: changes}.
        """
        from .position_container import PositionContainer

        # Capture previous states
        self._previous_states = {u: rf.to_dict() for u, rf in self._risk_factors.items()}

        # Clear and reaggregate
        self._risk_factors.clear()

        for underlying in position_container.underlyings:
            positions = position_container.get_by_underlying(underlying)

            rf = RiskFactorState(underlying=underlying)

            for pos in positions:
                rf.delta += pos.delta
                rf.gamma += pos.gamma
                rf.theta += pos.theta
                rf.vega += pos.vega
                rf.position_count += 1
                rf.unrealized_pnl += pos.unrealized_pnl

                if pos.quantity > 0:
                    rf.long_count += 1
                else:
                    rf.short_count += 1

                # Track exposure
                pos_value = abs(pos.market_value)
                rf.gross_exposure += pos_value
                rf.net_exposure += pos.market_value

                # Pick up underlying spot price from any position that has it
                if rf.spot_price == 0 and hasattr(pos, 'underlying_price') and pos.underlying_price:
                    rf.spot_price = pos.underlying_price
                # For stock positions, current_price IS the spot price
                if rf.spot_price == 0 and not getattr(pos, 'is_option', True) and pos.current_price:
                    rf.spot_price = pos.current_price

            # Calculate dollar exposures
            if rf.spot_price > 0:
                rf.delta_dollars = rf.delta * rf.spot_price
                rf.gamma_dollars = rf.gamma * rf.spot_price * rf.spot_price * Decimal('0.01')

            # Calculate utilization
            if rf.delta_limit > 0:
                rf.delta_utilization_pct = abs(rf.delta) / rf.delta_limit * 100

            # Set risk status
            if rf.delta_utilization_pct > 100:
                rf.risk_status = "BREACH"
            elif rf.delta_utilization_pct > 80:
                rf.risk_status = "WARNING"
            else:
                rf.risk_status = "OK"

            rf.last_updated = datetime.utcnow()
            self._risk_factors[underlying] = rf

        self._initialized = True
        return self._detect_all_changes()

    def load_from_snapshot_risk(self, risk_by_underlying: Dict) -> Dict[str, Dict[str, Any]]:
        """
        Load from MarketSnapshot risk_by_underlying (RiskBucket objects).
        """
        self._previous_states = {u: rf.to_dict() for u, rf in self._risk_factors.items()}
        self._risk_factors.clear()

        for underlying, bucket in risk_by_underlying.items():
            rf = RiskFactorState(
                underlying=underlying,
                delta=bucket.delta,
                gamma=bucket.gamma,
                theta=bucket.theta,
                vega=bucket.vega,
                delta_dollars=bucket.delta_dollars,
                gamma_dollars=bucket.gamma_dollars,
                position_count=bucket.position_count,
                long_count=bucket.long_count,
                short_count=bucket.short_count,
                gross_exposure=bucket.gross_exposure,
                net_exposure=bucket.net_exposure,
                last_updated=datetime.utcnow(),
            )
            self._risk_factors[underlying] = rf

        self._initialized = True
        return self._detect_all_changes()

    def _detect_all_changes(self) -> Dict[str, Dict[str, Any]]:
        all_changes = {}

        for underlying, rf in self._risk_factors.items():
            current = rf.to_dict()
            previous = self._previous_states.get(underlying, {})

            changes = {}
            for key, new_value in current.items():
                old_value = previous.get(key)
                if old_value != new_value:
                    changes[key] = {'old': old_value, 'new': new_value}

            if changes:
                all_changes[underlying] = changes
                self._notify_changes(underlying, changes)

        return all_changes

    def update_spot_price(self, underlying: str, price: Decimal, change_pct: Decimal = Decimal('0')) -> Dict[str, Any]:
        """Update spot price for an underlying"""
        rf = self._risk_factors.get(underlying)
        if not rf:
            return {}

        old_price = rf.spot_price
        rf.spot_price = price
        rf.spot_change_pct = change_pct

        # Recalculate dollar exposures
        rf.delta_dollars = rf.delta * price
        rf.gamma_dollars = rf.gamma * price * price * Decimal('0.01')
        rf.last_updated = datetime.utcnow()

        changes = {
            'spot_price': {'old': float(old_price), 'new': float(price)},
            'delta_dollars': {'old': None, 'new': float(rf.delta_dollars)},
        }
        self._notify_changes(underlying, changes)
        return changes

    def to_grid_rows(self) -> List[Dict[str, Any]]:
        """Convert to AG Grid row format"""
        rows = []
        for rf in sorted(self._risk_factors.values(), key=lambda r: r.underlying):
            rows.append({
                'id': rf.underlying,
                'underlying': rf.underlying,
                'spot': float(rf.spot_price),
                'spot_chg': float(rf.spot_change_pct),
                'delta': float(rf.delta),
                'gamma': float(rf.gamma),
                'theta': float(rf.theta),
                'vega': float(rf.vega),
                'delta_$': float(rf.delta_dollars),
                'gamma_$': float(rf.gamma_dollars),
                'positions': rf.position_count,
                'long': rf.long_count,
                'short': rf.short_count,
                'pnl': float(rf.unrealized_pnl),
                'limit_used': float(rf.delta_utilization_pct),
                'status': rf.risk_status,
            })
        return rows
