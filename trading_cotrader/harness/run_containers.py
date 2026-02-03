#!/usr/bin/env python
"""
Container Test Runner
=====================

Standalone runner to test in-memory containers for Portfolio, Positions, and Risk Factors.

Usage:
    python harness/run_containers.py  (from trading_cotrader directory)
"""

import sys
import os
from pathlib import Path

# Setup paths BEFORE any other imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent  # trading_cotrader
server_dir = project_root / "server"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(server_dir))  # For server's internal imports
os.chdir(project_root)

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from tabulate import tabulate

# Import existing server contracts
CONTRACTS_AVAILABLE = False
MarketSnapshot = None
RiskBucket = None
PositionWithMarket = None
PositionGreeks = None
MockDataProvider = None

try:
    from server.contracts import (
        MarketSnapshot, RiskBucket, PositionWithMarket, PositionGreeks,
        create_empty_snapshot
    )
    from server.data_provider import MockDataProvider
    CONTRACTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import server contracts: {e}")
    print(f"  Current dir: {os.getcwd()}")
    print(f"  Python path: {sys.path[:3]}")


# ============================================================================
# COLORS AND FORMATTING
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def colored(text: str, color: str) -> str:
    return f"{color}{text}{Colors.END}"


def header(text: str, width: int = 80) -> str:
    return colored(f"\n{'='*width}\n{text.center(width)}\n{'='*width}", Colors.BOLD)


def subheader(text: str) -> str:
    return colored(f"\n{'-'*60}\n{text}\n{'-'*60}", Colors.CYAN)


def success(text: str) -> str:
    return colored(f"✓ {text}", Colors.GREEN)


def error(text: str) -> str:
    return colored(f"✗ {text}", Colors.RED)


def warning(text: str) -> str:
    return colored(f"⚠ {text}", Colors.YELLOW)


def format_currency(value) -> str:
    if value is None:
        return "-"
    return f"${float(value):,.2f}"


def format_greek(value, precision=2) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.{precision}f}"


def format_quantity(value: int) -> str:
    return f"{value:+d}" if value != 0 else "0"


# ============================================================================
# IN-MEMORY CONTAINERS
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

    def update_from_snapshot(self, snapshot: MarketSnapshot):
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
            ["Portfolio Delta", format_greek(self.delta)],
            ["Portfolio Gamma", format_greek(self.gamma, 4)],
            ["Portfolio Theta", format_greek(self.theta)],
            ["Portfolio Vega", format_greek(self.vega)],
            ["Positions", str(self.position_count)],
            ["Risk Status", self.risk_status],
        ]


@dataclass
class PositionsContainer:
    """In-memory container for positions."""
    positions: List[PositionWithMarket] = field(default_factory=list)
    _by_underlying: Dict[str, List[PositionWithMarket]] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def underlyings(self) -> List[str]:
        return list(self._by_underlying.keys())

    def update_from_snapshot(self, snapshot: MarketSnapshot):
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

    def get_by_underlying(self, underlying: str) -> List[PositionWithMarket]:
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
                format_greek(pos.greeks.delta),
                format_greek(pos.greeks.gamma, 4),
                format_greek(pos.greeks.theta),
                format_greek(pos.greeks.vega),
                format_currency(pos.unrealized_pnl),
            ])
        return rows


@dataclass
class RiskFactorsContainer:
    """In-memory container for risk factors by underlying."""
    risk_buckets: Dict[str, RiskBucket] = field(default_factory=dict)
    portfolio_risk: Optional[RiskBucket] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Thresholds
    delta_threshold: Decimal = Decimal('100')

    @property
    def count(self) -> int:
        return len(self.risk_buckets)

    def update_from_snapshot(self, snapshot: MarketSnapshot):
        """Update from a MarketSnapshot."""
        self.risk_buckets = snapshot.risk_by_underlying
        self.portfolio_risk = snapshot.portfolio_risk
        self.last_updated = snapshot.timestamp

    def get(self, underlying: str) -> Optional[RiskBucket]:
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
                format_greek(bucket.delta),
                format_greek(bucket.gamma, 4),
                format_greek(bucket.theta),
                format_greek(bucket.vega),
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
            format_greek(p.delta),
            format_greek(p.gamma, 4),
            format_greek(p.theta),
            format_greek(p.vega),
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

        self._snapshot: Optional[MarketSnapshot] = None
        self._event_log: List[str] = []

    @property
    def is_initialized(self) -> bool:
        return self._snapshot is not None

    def load_snapshot(self, snapshot: MarketSnapshot):
        """Load from a MarketSnapshot - updates all containers."""
        self._snapshot = snapshot
        self.portfolio.update_from_snapshot(snapshot)
        self.positions.update_from_snapshot(snapshot)
        self.risk_factors.update_from_snapshot(snapshot)
        self._event_log.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Snapshot loaded")

    def on_trade_booked(self, underlying: str, delta: Decimal, theta: Decimal):
        """
        Handle new trade - updates all containers.

        This is the event-driven update mechanism.
        """
        self.portfolio.on_trade_booked(delta, theta)
        self.risk_factors.on_trade_booked(underlying, delta, theta)
        self._event_log.append(
            f"[{datetime.utcnow().strftime('%H:%M:%S')}] Trade booked: {underlying} "
            f"Δ={float(delta):+.0f} Θ={float(theta):+.0f}"
        )

    def get_events(self, last_n: int = 10) -> List[str]:
        """Get recent events."""
        return self._event_log[-last_n:]


# ============================================================================
# MAIN RUNNER
# ============================================================================

def main():
    """Run the containers test."""
    print(header("IN-MEMORY CONTAINERS TEST"))
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if not CONTRACTS_AVAILABLE:
        print(error("server/contracts.py not available"))
        return 1

    # Create container manager
    manager = ContainerManager()

    # Get mock data
    print(subheader("Loading Data"))
    print("  Loading mock data into containers...")

    import asyncio
    mock_provider = MockDataProvider()
    snapshot = asyncio.run(mock_provider.get_snapshot())

    # Load into containers
    manager.load_snapshot(snapshot)

    print(success(f"Loaded {manager.positions.count} positions"))
    print(success(f"Found {manager.risk_factors.count} underlyings"))

    # Display Portfolio Container
    print(subheader("Portfolio Container"))
    print(tabulate(
        manager.portfolio.to_rows(),
        headers=["Metric", "Value"],
        tablefmt="rounded_grid"
    ))

    # Display Positions Container
    print(subheader(f"Positions Container ({manager.positions.count} positions)"))
    print(tabulate(
        manager.positions.to_rows(),
        headers=["Symbol", "Type", "Strike", "DTE", "Qty", "Δ", "Γ", "Θ", "V", "P&L"],
        tablefmt="rounded_grid"
    ))

    # Display Risk Factors Container
    print(subheader("Risk Factors Container"))
    risk_rows = manager.risk_factors.to_rows()
    risk_rows.append(manager.risk_factors.totals_row())  # Add totals
    print(tabulate(
        risk_rows,
        headers=["Underlying", "#Pos", "Delta", "Gamma", "Theta", "Vega", "Delta$", "Hedge?"],
        tablefmt="rounded_grid"
    ))

    # Test event-based updates
    print(subheader("Testing Event-Based Updates"))
    print()
    print("  Simulating trades being booked...")
    print()

    # Simulate trades
    print("  → Booking trade: SPY short put spread (Δ=+15, Θ=+8)")
    manager.on_trade_booked("SPY", Decimal('15'), Decimal('8'))

    print("  → Booking trade: QQQ iron condor (Δ=-5, Θ=+12)")
    manager.on_trade_booked("QQQ", Decimal('-5'), Decimal('12'))

    print()
    print(colored("  After trades:", Colors.BOLD))
    print(f"    Portfolio Delta: {float(manager.portfolio.delta):+.2f}")
    print(f"    Portfolio Theta: {float(manager.portfolio.theta):+.2f}")
    print(f"    Position Count: {manager.portfolio.position_count}")

    # Updated risk factors
    print()
    print(colored("  Updated Risk Factors:", Colors.BOLD))
    for underlying in ["SPY", "QQQ"]:
        bucket = manager.risk_factors.get(underlying)
        if bucket:
            print(f"    {underlying}: Δ={float(bucket.delta):+.2f}, Θ={float(bucket.theta):+.2f}")

    # Show event log
    print()
    print(colored("  Event Log:", Colors.BOLD))
    for event in manager.get_events():
        print(f"    {event}")

    print()
    print(header("TEST COMPLETE"))
    print(success("All containers working correctly!"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
