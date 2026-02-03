"""
Step 11: In-Memory Containers Test
==================================

Tests the in-memory container system for Portfolio, Positions, and Risk Factors.
Uses existing server/data_provider.py and server/contracts.py.

The containers:
- Hold current state in memory (MarketSnapshot)
- Update on events (trade booked, Greeks updated)
- Provide fast lookups and aggregations
"""

import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_quantity, success, warning, error, Colors, colored, header, subheader
)

# Import existing server contracts
try:
    from server.contracts import (
        MarketSnapshot, RiskBucket, PositionWithMarket, PositionGreeks,
        create_empty_snapshot
    )
    from server.data_provider import RiskAggregator, MockDataProvider
    CONTRACTS_AVAILABLE = True
except ImportError:
    CONTRACTS_AVAILABLE = False


# ============================================================================
# SIMPLE IN-MEMORY CONTAINERS (wrapping existing contracts)
# ============================================================================

@dataclass
class PortfolioContainer:
    """In-memory container for portfolio state."""
    portfolio_id: str = "default"
    total_equity: Decimal = Decimal('0')
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')

    # Aggregated Greeks
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')

    # Counts
    position_count: int = 0

    # Risk status
    risk_status: str = "OK"

    last_updated: datetime = field(default_factory=datetime.utcnow)

    def update_from_snapshot(self, snapshot: 'MarketSnapshot'):
        """Update from a MarketSnapshot."""
        self.total_equity = snapshot.account_value
        self.buying_power = snapshot.buying_power

        risk = snapshot.portfolio_risk
        self.delta = risk.delta
        self.gamma = risk.gamma
        self.theta = risk.theta
        self.vega = risk.vega
        self.position_count = risk.position_count

        # Determine risk status from breaches
        if any(b.severity == "critical" for b in snapshot.breaches):
            self.risk_status = "CRITICAL"
        elif any(b.severity == "breach" for b in snapshot.breaches):
            self.risk_status = "WARNING"
        else:
            self.risk_status = "OK"

        self.last_updated = snapshot.timestamp

    def on_trade_booked(self, delta: Decimal, theta: Decimal):
        """Update on new trade."""
        self.delta += delta
        self.theta += theta
        self.position_count += 1
        self.last_updated = datetime.utcnow()

    def to_rows(self) -> List[List]:
        return [
            ["Total Equity", format_currency(self.total_equity)],
            ["Buying Power", format_currency(self.buying_power)],
            ["Portfolio Delta", f"{float(self.delta):+.2f}"],
            ["Portfolio Gamma", f"{float(self.gamma):+.4f}"],
            ["Portfolio Theta", f"{float(self.theta):+.2f}"],
            ["Portfolio Vega", f"{float(self.vega):+.2f}"],
            ["Positions", str(self.position_count)],
            ["Risk Status", self.risk_status],
        ]


@dataclass
class PositionsContainer:
    """In-memory container for positions."""
    positions: List['PositionWithMarket'] = field(default_factory=list)
    _by_underlying: Dict[str, List['PositionWithMarket']] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def underlyings(self) -> List[str]:
        return list(self._by_underlying.keys())

    def update_from_snapshot(self, snapshot: 'MarketSnapshot'):
        """Update from a MarketSnapshot."""
        self.positions = snapshot.positions
        self._rebuild_index()
        self.last_updated = snapshot.timestamp

    def _rebuild_index(self):
        """Rebuild underlying index."""
        self._by_underlying.clear()
        for pos in self.positions:
            if pos.symbol not in self._by_underlying:
                self._by_underlying[pos.symbol] = []
            self._by_underlying[pos.symbol].append(pos)

    def get_by_underlying(self, underlying: str) -> List['PositionWithMarket']:
        return self._by_underlying.get(underlying, [])

    def to_rows(self) -> List[List]:
        """Convert to table rows."""
        rows = []
        for pos in sorted(self.positions, key=lambda p: (p.symbol, str(p.expiry or ''))):
            rows.append([
                pos.symbol,
                pos.option_type or "STOCK",
                f"{float(pos.strike):.0f}" if pos.strike else "-",
                str(pos.dte) if pos.dte else "-",
                format_quantity(pos.quantity),
                f"{float(pos.greeks.delta):+.2f}",
                f"{float(pos.greeks.gamma):+.4f}",
                f"{float(pos.greeks.theta):+.2f}",
                f"{float(pos.greeks.vega):+.2f}",
                format_currency(pos.unrealized_pnl),
            ])
        return rows


@dataclass
class RiskFactorsContainer:
    """In-memory container for risk factors by underlying."""
    risk_buckets: Dict[str, 'RiskBucket'] = field(default_factory=dict)
    portfolio_risk: Optional['RiskBucket'] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Thresholds
    delta_threshold: Decimal = Decimal('100')

    @property
    def count(self) -> int:
        return len(self.risk_buckets)

    def update_from_snapshot(self, snapshot: 'MarketSnapshot'):
        """Update from a MarketSnapshot."""
        self.risk_buckets = snapshot.risk_by_underlying
        self.portfolio_risk = snapshot.portfolio_risk
        self.last_updated = snapshot.timestamp

    def get(self, underlying: str) -> Optional['RiskBucket']:
        return self.risk_buckets.get(underlying)

    def needs_hedge(self, underlying: str) -> bool:
        bucket = self.risk_buckets.get(underlying)
        if not bucket:
            return False
        return abs(bucket.delta) > self.delta_threshold

    def on_trade_booked(self, underlying: str, delta: Decimal, theta: Decimal):
        """Update on new trade."""
        if underlying in self.risk_buckets:
            self.risk_buckets[underlying].delta += delta
            self.risk_buckets[underlying].theta += theta
        self.last_updated = datetime.utcnow()

    def to_rows(self) -> List[List]:
        """Convert to table rows."""
        rows = []
        for underlying, bucket in sorted(self.risk_buckets.items(),
                                         key=lambda x: abs(x[1].delta), reverse=True):
            hedge_status = "⚠️" if self.needs_hedge(underlying) else "✓"
            rows.append([
                underlying,
                bucket.position_count,
                f"{float(bucket.delta):+.2f}",
                f"{float(bucket.gamma):+.4f}",
                f"{float(bucket.theta):+.2f}",
                f"{float(bucket.vega):+.2f}",
                format_currency(bucket.delta_dollars),
                hedge_status,
            ])
        return rows

    def totals_row(self) -> List:
        """Get totals row."""
        if not self.portfolio_risk:
            return ["TOTAL", 0, "0", "0", "0", "0", "$0", ""]
        p = self.portfolio_risk
        return [
            "TOTAL",
            p.position_count,
            f"{float(p.delta):+.2f}",
            f"{float(p.gamma):+.4f}",
            f"{float(p.theta):+.2f}",
            f"{float(p.vega):+.2f}",
            format_currency(p.delta_dollars),
            "",
        ]


class ContainerManager:
    """
    Central manager for all containers.

    Holds MarketSnapshot and provides container views.
    Updates all containers on events.
    """

    def __init__(self):
        self.portfolio = PortfolioContainer()
        self.positions = PositionsContainer()
        self.risk_factors = RiskFactorsContainer()

        self._snapshot: Optional['MarketSnapshot'] = None
        self._event_log: List[str] = []

    @property
    def is_initialized(self) -> bool:
        return self._snapshot is not None

    def load_snapshot(self, snapshot: 'MarketSnapshot'):
        """Load from a MarketSnapshot - updates all containers."""
        self._snapshot = snapshot
        self.portfolio.update_from_snapshot(snapshot)
        self.positions.update_from_snapshot(snapshot)
        self.risk_factors.update_from_snapshot(snapshot)
        self._event_log.append(f"[{datetime.utcnow().isoformat()}] Snapshot loaded")

    def on_trade_booked(self, underlying: str, delta: Decimal, theta: Decimal):
        """
        Handle new trade - updates all containers.

        This is the event-driven update mechanism.
        """
        self.portfolio.on_trade_booked(delta, theta)
        self.risk_factors.on_trade_booked(underlying, delta, theta)
        self._event_log.append(
            f"[{datetime.utcnow().isoformat()}] Trade booked: {underlying} "
            f"Δ={float(delta):+.0f} Θ={float(theta):+.0f}"
        )

    def get_events(self, last_n: int = 10) -> List[str]:
        """Get recent events."""
        return self._event_log[-last_n:]


# ============================================================================
# TEST STEP
# ============================================================================

class ContainersTestStep(TestStep):
    """Test the in-memory container system."""

    name = "Step 11: In-Memory Containers"
    description = "Test Portfolio, Positions, and RiskFactors containers with event updates"

    def execute(self) -> StepResult:
        tables = []
        messages = []

        if not CONTRACTS_AVAILABLE:
            return self._fail_result("server/contracts.py not available")

        # Create container manager
        manager = ContainerManager()

        # Get mock data
        messages.append("Loading mock data into containers...")

        import asyncio
        mock_provider = MockDataProvider()
        snapshot = asyncio.run(mock_provider.get_snapshot())

        # Load into containers
        manager.load_snapshot(snapshot)

        messages.append(f"✓ Loaded {manager.positions.count} positions")
        messages.append(f"✓ Found {manager.risk_factors.count} underlyings")

        # Display Portfolio Container
        tables.append(rich_table(
            manager.portfolio.to_rows(),
            headers=["Metric", "Value"],
            title="💼 Portfolio Container"
        ))

        # Display Positions Container
        tables.append(rich_table(
            manager.positions.to_rows(),
            headers=["Symbol", "Type", "Strike", "DTE", "Qty", "Δ", "Γ", "Θ", "V", "P&L"],
            title=f"📋 Positions Container ({manager.positions.count} positions)"
        ))

        # Display Risk Factors Container
        risk_rows = manager.risk_factors.to_rows()
        risk_rows.append(manager.risk_factors.totals_row())  # Add totals
        tables.append(rich_table(
            risk_rows,
            headers=["Underlying", "#Pos", "Delta", "Gamma", "Theta", "Vega", "Delta$", "Hedge?"],
            title="⚠️ Risk Factors Container"
        ))

        # Test event-based updates
        messages.append("")
        messages.append("Testing event-based updates...")

        # Simulate a trade being booked
        messages.append("  → Booking trade: SPY short put spread (Δ=+15, Θ=+8)")
        manager.on_trade_booked("SPY", Decimal('15'), Decimal('8'))

        messages.append("  → Booking trade: QQQ iron condor (Δ=-5, Θ=+12)")
        manager.on_trade_booked("QQQ", Decimal('-5'), Decimal('12'))

        # Show updated portfolio
        messages.append("")
        messages.append("After trades:")
        messages.append(f"  Portfolio Delta: {float(manager.portfolio.delta):+.2f}")
        messages.append(f"  Portfolio Theta: {float(manager.portfolio.theta):+.2f}")
        messages.append(f"  Position Count: {manager.portfolio.position_count}")

        # Show event log
        messages.append("")
        messages.append("Event Log:")
        for event in manager.get_events():
            messages.append(f"  {event}")

        return self._success_result(tables=tables, messages=messages)


# ============================================================================
# STANDALONE RUNNER
# ============================================================================

def run_containers_test():
    """Run the containers test standalone."""
    print(header("IN-MEMORY CONTAINERS TEST"))
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Ensure imports work
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    # Run the step
    context = {}
    step = ContainersTestStep(context)
    result = step.run()

    # Print results
    for table in result.tables:
        print(table)
        print()

    for msg in result.messages:
        print(f"  {msg}")

    print()
    if result.passed:
        print(success(f"PASSED ({result.duration_ms:.0f}ms)"))
    else:
        print(error(f"FAILED: {result.error}"))

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(run_containers_test())
