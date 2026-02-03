#!/usr/bin/env python
"""
Container Test Runner - Raw Broker Data
========================================

Connects to broker and populates containers with RAW data only.
No calculated fields - just what the broker provides.

Usage:
    python harness/run_containers.py           # Uses mock data
    python harness/run_containers.py --live    # Connects to real broker
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Setup paths BEFORE any other imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent  # trading_cotrader
server_dir = project_root / "server"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(server_dir))
os.chdir(project_root)

from tabulate import tabulate


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
    DIM = '\033[2m'
    END = '\033[0m'


def colored(text: str, color: str) -> str:
    return f"{color}{text}{Colors.END}"


def header(text: str, width: int = 90) -> str:
    return colored(f"\n{'='*width}\n{text.center(width)}\n{'='*width}", Colors.BOLD)


def subheader(text: str) -> str:
    return colored(f"\n{'-'*80}\n  {text}\n{'-'*80}", Colors.CYAN)


def success(text: str) -> str:
    return colored(f"✓ {text}", Colors.GREEN)


def error(text: str) -> str:
    return colored(f"✗ {text}", Colors.RED)


def warning(text: str) -> str:
    return colored(f"⚠ {text}", Colors.YELLOW)


def dim(text: str) -> str:
    return colored(text, Colors.DIM)


def fmt_currency(value) -> str:
    if value is None:
        return "-"
    return f"${float(value):,.2f}"


def fmt_pct(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}%"


def fmt_greek(value, precision=4) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.{precision}f}"


def fmt_qty(value: int) -> str:
    return f"{value:+d}" if value != 0 else "0"


def fmt_date(d) -> str:
    if d is None:
        return "-"
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


# ============================================================================
# RAW DATA CONTAINERS - No Calculated Fields
# ============================================================================

@dataclass
class PortfolioContainer:
    """
    Portfolio-level data from broker.

    All fields are RAW from broker - no calculations.
    """
    # Identity
    account_id: str = ""
    broker_name: str = ""
    account_type: str = ""  # LIVE / PAPER

    # Capital - RAW from broker
    net_liquidating_value: Decimal = Decimal('0')
    cash_balance: Decimal = Decimal('0')
    equity_buying_power: Decimal = Decimal('0')
    derivative_buying_power: Decimal = Decimal('0')
    day_trading_buying_power: Decimal = Decimal('0')

    # Margin - RAW from broker
    maintenance_requirement: Decimal = Decimal('0')
    maintenance_excess: Decimal = Decimal('0')
    margin_equity: Decimal = Decimal('0')
    option_buying_power: Decimal = Decimal('0')

    # Counts
    position_count: int = 0
    open_order_count: int = 0

    # Timestamps
    last_sync: Optional[datetime] = None

    def to_rows(self) -> List[List]:
        """All raw fields as rows."""
        return [
            ["Account ID", self.account_id],
            ["Broker", self.broker_name],
            ["Account Type", self.account_type],
            ["", ""],
            [colored("CAPITAL", Colors.BOLD), ""],
            ["Net Liquidating Value", fmt_currency(self.net_liquidating_value)],
            ["Cash Balance", fmt_currency(self.cash_balance)],
            ["Equity Buying Power", fmt_currency(self.equity_buying_power)],
            ["Derivative Buying Power", fmt_currency(self.derivative_buying_power)],
            ["Day Trading Buying Power", fmt_currency(self.day_trading_buying_power)],
            ["", ""],
            [colored("MARGIN", Colors.BOLD), ""],
            ["Maintenance Requirement", fmt_currency(self.maintenance_requirement)],
            ["Maintenance Excess", fmt_currency(self.maintenance_excess)],
            ["Margin Equity", fmt_currency(self.margin_equity)],
            ["Option Buying Power", fmt_currency(self.option_buying_power)],
            ["", ""],
            [colored("COUNTS", Colors.BOLD), ""],
            ["Position Count", str(self.position_count)],
            ["Open Orders", str(self.open_order_count)],
            ["", ""],
            ["Last Sync", fmt_date(self.last_sync)],
        ]


@dataclass
class PositionEntry:
    """
    Single position with ALL raw fields from broker.
    """
    # Identity
    position_id: str = ""
    broker_position_id: str = ""

    # Instrument
    symbol: str = ""
    underlying_symbol: str = ""
    instrument_type: str = ""  # EQUITY, EQUITY_OPTION, FUTURE, etc.

    # Option details (if applicable)
    option_type: Optional[str] = None  # CALL / PUT
    strike: Optional[Decimal] = None
    expiration: Optional[date] = None
    multiplier: int = 100

    # Position
    quantity: int = 0
    quantity_direction: str = ""  # Long / Short

    # Prices - RAW from broker
    average_open_price: Decimal = Decimal('0')
    close_price: Decimal = Decimal('0')
    mark: Decimal = Decimal('0')

    # Value - RAW from broker (no recalculation)
    market_value: Decimal = Decimal('0')
    cost_basis: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    unrealized_pnl_pct: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')

    # Greeks - RAW from broker (via DXLink)
    delta: Optional[Decimal] = None
    gamma: Optional[Decimal] = None
    theta: Optional[Decimal] = None
    vega: Optional[Decimal] = None
    rho: Optional[Decimal] = None
    iv: Optional[Decimal] = None

    # Capital usage
    maintenance_requirement: Decimal = Decimal('0')
    buying_power_effect: Decimal = Decimal('0')

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def dte(self) -> Optional[int]:
        if self.expiration:
            return (self.expiration - date.today()).days
        return None


@dataclass
class PositionsContainer:
    """
    All positions with raw broker data.
    """
    positions: List[PositionEntry] = field(default_factory=list)
    _by_underlying: Dict[str, List[PositionEntry]] = field(default_factory=dict)
    last_sync: Optional[datetime] = None

    @property
    def count(self) -> int:
        return len(self.positions)

    @property
    def underlyings(self) -> List[str]:
        return list(self._by_underlying.keys())

    def add_position(self, pos: PositionEntry):
        self.positions.append(pos)
        underlying = pos.underlying_symbol or pos.symbol
        if underlying not in self._by_underlying:
            self._by_underlying[underlying] = []
        self._by_underlying[underlying].append(pos)

    def clear(self):
        self.positions.clear()
        self._by_underlying.clear()

    def get_by_underlying(self, underlying: str) -> List[PositionEntry]:
        return self._by_underlying.get(underlying, [])

    def to_summary_rows(self) -> List[List]:
        """Summary table with key fields."""
        rows = []
        for pos in sorted(self.positions, key=lambda p: (p.underlying_symbol or p.symbol, str(p.expiration or ''))):
            rows.append([
                pos.underlying_symbol or pos.symbol,
                pos.instrument_type[:6],
                pos.option_type or "-",
                f"{float(pos.strike):.0f}" if pos.strike else "-",
                str(pos.dte) if pos.dte else "-",
                fmt_qty(pos.quantity),
                fmt_currency(pos.average_open_price),
                fmt_currency(pos.mark),
                fmt_currency(pos.market_value),
                fmt_currency(pos.unrealized_pnl),
                fmt_pct(pos.unrealized_pnl_pct),
            ])
        return rows

    def to_greeks_rows(self) -> List[List]:
        """Greeks table."""
        rows = []
        for pos in sorted(self.positions, key=lambda p: (p.underlying_symbol or p.symbol, str(p.expiration or ''))):
            rows.append([
                pos.underlying_symbol or pos.symbol,
                pos.option_type or "STOCK",
                f"{float(pos.strike):.0f}" if pos.strike else "-",
                str(pos.dte) if pos.dte else "-",
                fmt_qty(pos.quantity),
                fmt_greek(pos.delta, 2),
                fmt_greek(pos.gamma, 4),
                fmt_greek(pos.theta, 2),
                fmt_greek(pos.vega, 2),
                fmt_pct(float(pos.iv) * 100 if pos.iv else None),
            ])
        return rows

    def to_capital_rows(self) -> List[List]:
        """Capital usage table."""
        rows = []
        for pos in sorted(self.positions, key=lambda p: abs(float(p.market_value)), reverse=True):
            rows.append([
                pos.underlying_symbol or pos.symbol,
                pos.option_type or "STOCK",
                fmt_qty(pos.quantity),
                fmt_currency(pos.cost_basis),
                fmt_currency(pos.market_value),
                fmt_currency(pos.maintenance_requirement),
                fmt_currency(pos.buying_power_effect),
            ])
        return rows


@dataclass
class RiskFactorEntry:
    """
    Risk factor = underlying-level aggregation of raw Greeks.
    """
    underlying: str = ""
    position_count: int = 0

    # Aggregated raw Greeks (sum from broker data)
    total_delta: Decimal = Decimal('0')
    total_gamma: Decimal = Decimal('0')
    total_theta: Decimal = Decimal('0')
    total_vega: Decimal = Decimal('0')

    # Market data (if available)
    underlying_price: Optional[Decimal] = None
    underlying_iv: Optional[Decimal] = None

    # Exposure
    total_market_value: Decimal = Decimal('0')
    total_cost_basis: Decimal = Decimal('0')
    total_unrealized_pnl: Decimal = Decimal('0')


@dataclass
class RiskFactorsContainer:
    """
    Risk factors by underlying - raw aggregated data.
    """
    risk_factors: Dict[str, RiskFactorEntry] = field(default_factory=dict)
    last_sync: Optional[datetime] = None

    @property
    def count(self) -> int:
        return len(self.risk_factors)

    def build_from_positions(self, positions: PositionsContainer):
        """Build risk factors by aggregating positions."""
        self.risk_factors.clear()

        for underlying in positions.underlyings:
            pos_list = positions.get_by_underlying(underlying)

            rf = RiskFactorEntry(
                underlying=underlying,
                position_count=len(pos_list),
            )

            for pos in pos_list:
                rf.total_delta += pos.delta or Decimal('0')
                rf.total_gamma += pos.gamma or Decimal('0')
                rf.total_theta += pos.theta or Decimal('0')
                rf.total_vega += pos.vega or Decimal('0')
                rf.total_market_value += pos.market_value
                rf.total_cost_basis += pos.cost_basis
                rf.total_unrealized_pnl += pos.unrealized_pnl

            self.risk_factors[underlying] = rf

        self.last_sync = datetime.utcnow()

    def to_rows(self) -> List[List]:
        """Risk factors table."""
        rows = []
        for underlying, rf in sorted(self.risk_factors.items(), key=lambda x: abs(float(x[1].total_delta)), reverse=True):
            rows.append([
                underlying,
                rf.position_count,
                fmt_greek(rf.total_delta, 2),
                fmt_greek(rf.total_gamma, 4),
                fmt_greek(rf.total_theta, 2),
                fmt_greek(rf.total_vega, 2),
                fmt_currency(rf.total_market_value),
                fmt_currency(rf.total_unrealized_pnl),
            ])
        return rows

    def totals_row(self) -> List:
        """Portfolio totals."""
        total_delta = sum(rf.total_delta for rf in self.risk_factors.values())
        total_gamma = sum(rf.total_gamma for rf in self.risk_factors.values())
        total_theta = sum(rf.total_theta for rf in self.risk_factors.values())
        total_vega = sum(rf.total_vega for rf in self.risk_factors.values())
        total_mv = sum(rf.total_market_value for rf in self.risk_factors.values())
        total_pnl = sum(rf.total_unrealized_pnl for rf in self.risk_factors.values())

        return [
            colored("TOTAL", Colors.BOLD),
            sum(rf.position_count for rf in self.risk_factors.values()),
            fmt_greek(total_delta, 2),
            fmt_greek(total_gamma, 4),
            fmt_greek(total_theta, 2),
            fmt_greek(total_vega, 2),
            fmt_currency(total_mv),
            fmt_currency(total_pnl),
        ]


# ============================================================================
# CONTAINER MANAGER
# ============================================================================

class ContainerManager:
    """
    Manages all containers and loads from broker.
    """

    def __init__(self):
        self.portfolio = PortfolioContainer()
        self.positions = PositionsContainer()
        self.risk_factors = RiskFactorsContainer()
        self._broker = None

    def load_from_broker(self, broker, is_paper: bool = False):
        """Load all data from real broker."""
        self._broker = broker

        # 1. Load account/portfolio data
        balances = broker.get_account_balance()

        self.portfolio.account_id = broker.account_id
        self.portfolio.broker_name = "TastyTrade"
        self.portfolio.account_type = "PAPER" if is_paper else "LIVE"

        self.portfolio.net_liquidating_value = balances.get('net_liquidating_value', Decimal('0'))
        self.portfolio.cash_balance = balances.get('cash_balance', Decimal('0'))
        self.portfolio.equity_buying_power = balances.get('equity_buying_power', Decimal('0'))
        self.portfolio.derivative_buying_power = balances.get('buying_power', Decimal('0'))
        self.portfolio.maintenance_excess = balances.get('maintenance_excess', Decimal('0'))

        # 2. Load positions
        broker_positions = broker.get_positions()
        self._load_positions(broker_positions)

        self.portfolio.position_count = self.positions.count
        self.portfolio.last_sync = datetime.utcnow()

        # 3. Build risk factors from positions
        self.risk_factors.build_from_positions(self.positions)

    def _load_positions(self, broker_positions):
        """Convert broker positions to container entries."""
        self.positions.clear()

        for pos in broker_positions:
            symbol = pos.symbol

            # Calculate position-level Greeks (raw * qty * multiplier)
            greeks = pos.greeks if hasattr(pos, 'greeks') else None
            qty = pos.quantity
            mult = symbol.multiplier if symbol else 100

            entry = PositionEntry(
                position_id=str(pos.id) if hasattr(pos, 'id') else "",
                broker_position_id=pos.broker_position_id or "",
                symbol=symbol.ticker if symbol else "",
                underlying_symbol=symbol.ticker if symbol else "",
                instrument_type=symbol.asset_type.value.upper() if symbol else "EQUITY",
                option_type=symbol.option_type.value.upper() if symbol and symbol.option_type else None,
                strike=symbol.strike if symbol else None,
                expiration=symbol.expiration.date() if symbol and symbol.expiration else None,
                multiplier=mult,
                quantity=qty,
                quantity_direction="Long" if qty > 0 else "Short",
                average_open_price=pos.entry_price,
                close_price=pos.current_price or Decimal('0'),
                mark=pos.current_price or Decimal('0'),
                market_value=pos.market_value,
                cost_basis=pos.total_cost,
                unrealized_pnl=pos.market_value - pos.total_cost if pos.market_value else Decimal('0'),
                unrealized_pnl_pct=((pos.market_value - pos.total_cost) / abs(pos.total_cost) * 100) if pos.total_cost else Decimal('0'),
                # Raw Greeks from broker (already position-level from adapter)
                delta=greeks.delta if greeks else None,
                gamma=greeks.gamma if greeks else None,
                theta=greeks.theta if greeks else None,
                vega=greeks.vega if greeks else None,
                rho=greeks.rho if greeks else None,
                updated_at=datetime.utcnow(),
            )

            self.positions.add_position(entry)

        self.positions.last_sync = datetime.utcnow()

    def load_mock_data(self):
        """Load mock data for testing."""
        # Mock portfolio
        self.portfolio.account_id = "MOCK-12345"
        self.portfolio.broker_name = "MockBroker"
        self.portfolio.account_type = "PAPER"
        self.portfolio.net_liquidating_value = Decimal('125000')
        self.portfolio.cash_balance = Decimal('45000')
        self.portfolio.equity_buying_power = Decimal('90000')
        self.portfolio.derivative_buying_power = Decimal('85000')
        self.portfolio.day_trading_buying_power = Decimal('180000')
        self.portfolio.maintenance_requirement = Decimal('15000')
        self.portfolio.maintenance_excess = Decimal('70000')
        self.portfolio.margin_equity = Decimal('80000')
        self.portfolio.option_buying_power = Decimal('85000')
        self.portfolio.last_sync = datetime.utcnow()

        # Mock positions
        mock_positions = [
            # SPY Iron Condor
            PositionEntry(
                position_id="1", symbol="SPY 260131C600", underlying_symbol="SPY",
                instrument_type="EQUITY_OPTION", option_type="CALL",
                strike=Decimal('600'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=-1, quantity_direction="Short",
                average_open_price=Decimal('0.85'), close_price=Decimal('0.42'), mark=Decimal('0.42'),
                market_value=Decimal('42'), cost_basis=Decimal('85'),
                unrealized_pnl=Decimal('43'), unrealized_pnl_pct=Decimal('50.59'),
                delta=Decimal('-8'), gamma=Decimal('-1.0'), theta=Decimal('4'), vega=Decimal('-6'),
                maintenance_requirement=Decimal('500'), buying_power_effect=Decimal('500'),
            ),
            PositionEntry(
                position_id="2", symbol="SPY 260131C605", underlying_symbol="SPY",
                instrument_type="EQUITY_OPTION", option_type="CALL",
                strike=Decimal('605'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=1, quantity_direction="Long",
                average_open_price=Decimal('0.45'), close_price=Decimal('0.18'), mark=Decimal('0.18'),
                market_value=Decimal('18'), cost_basis=Decimal('45'),
                unrealized_pnl=Decimal('-27'), unrealized_pnl_pct=Decimal('-60'),
                delta=Decimal('3'), gamma=Decimal('0.5'), theta=Decimal('-2'), vega=Decimal('3'),
                maintenance_requirement=Decimal('0'), buying_power_effect=Decimal('45'),
            ),
            PositionEntry(
                position_id="3", symbol="SPY 260131P570", underlying_symbol="SPY",
                instrument_type="EQUITY_OPTION", option_type="PUT",
                strike=Decimal('570'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=-1, quantity_direction="Short",
                average_open_price=Decimal('0.95'), close_price=Decimal('0.55'), mark=Decimal('0.55'),
                market_value=Decimal('55'), cost_basis=Decimal('95'),
                unrealized_pnl=Decimal('40'), unrealized_pnl_pct=Decimal('42.11'),
                delta=Decimal('6'), gamma=Decimal('-1.0'), theta=Decimal('5'), vega=Decimal('-7'),
                maintenance_requirement=Decimal('500'), buying_power_effect=Decimal('500'),
            ),
            PositionEntry(
                position_id="4", symbol="SPY 260131P565", underlying_symbol="SPY",
                instrument_type="EQUITY_OPTION", option_type="PUT",
                strike=Decimal('565'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=1, quantity_direction="Long",
                average_open_price=Decimal('0.60'), close_price=Decimal('0.30'), mark=Decimal('0.30'),
                market_value=Decimal('30'), cost_basis=Decimal('60'),
                unrealized_pnl=Decimal('-30'), unrealized_pnl_pct=Decimal('-50'),
                delta=Decimal('-2'), gamma=Decimal('0.4'), theta=Decimal('-2'), vega=Decimal('3'),
                maintenance_requirement=Decimal('0'), buying_power_effect=Decimal('60'),
            ),
            # QQQ Put Spread
            PositionEntry(
                position_id="5", symbol="QQQ 260131P495", underlying_symbol="QQQ",
                instrument_type="EQUITY_OPTION", option_type="PUT",
                strike=Decimal('495'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=-1, quantity_direction="Short",
                average_open_price=Decimal('1.80'), close_price=Decimal('0.95'), mark=Decimal('0.95'),
                market_value=Decimal('95'), cost_basis=Decimal('180'),
                unrealized_pnl=Decimal('85'), unrealized_pnl_pct=Decimal('47.22'),
                delta=Decimal('10'), gamma=Decimal('-1.0'), theta=Decimal('6'), vega=Decimal('-9'),
                maintenance_requirement=Decimal('500'), buying_power_effect=Decimal('500'),
            ),
            PositionEntry(
                position_id="6", symbol="QQQ 260131P490", underlying_symbol="QQQ",
                instrument_type="EQUITY_OPTION", option_type="PUT",
                strike=Decimal('490'), expiration=date(2026, 2, 21), multiplier=100,
                quantity=1, quantity_direction="Long",
                average_open_price=Decimal('0.30'), close_price=Decimal('0.10'), mark=Decimal('0.10'),
                market_value=Decimal('10'), cost_basis=Decimal('30'),
                unrealized_pnl=Decimal('-20'), unrealized_pnl_pct=Decimal('-66.67'),
                delta=Decimal('-2'), gamma=Decimal('0.3'), theta=Decimal('-1'), vega=Decimal('2'),
                maintenance_requirement=Decimal('0'), buying_power_effect=Decimal('30'),
            ),
            # MSFT Stock
            PositionEntry(
                position_id="7", symbol="MSFT", underlying_symbol="MSFT",
                instrument_type="EQUITY", option_type=None,
                strike=None, expiration=None, multiplier=1,
                quantity=100, quantity_direction="Long",
                average_open_price=Decimal('400'), close_price=Decimal('415'), mark=Decimal('415'),
                market_value=Decimal('41500'), cost_basis=Decimal('40000'),
                unrealized_pnl=Decimal('1500'), unrealized_pnl_pct=Decimal('3.75'),
                delta=Decimal('100'), gamma=Decimal('0'), theta=Decimal('0'), vega=Decimal('0'),
                maintenance_requirement=Decimal('10000'), buying_power_effect=Decimal('40000'),
            ),
        ]

        for pos in mock_positions:
            self.positions.add_position(pos)

        self.portfolio.position_count = self.positions.count

        # Build risk factors
        self.risk_factors.build_from_positions(self.positions)


# ============================================================================
# MAIN RUNNER
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Container Test Runner")
    parser.add_argument('--live', action='store_true', help='Connect to live broker')
    parser.add_argument('--paper', action='store_true', help='Connect to paper trading')
    args = parser.parse_args()

    use_live = args.live or args.paper
    is_paper = args.paper

    print(header("IN-MEMORY CONTAINERS - RAW BROKER DATA"))
    print(f"  Mode: {'LIVE BROKER' if args.live else 'PAPER BROKER' if args.paper else 'MOCK DATA'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    manager = ContainerManager()

    if use_live:
        # Connect to real broker
        print(subheader("Step 1: Broker Connection"))
        try:
            from adapters.tastytrade_adapter import TastytradeAdapter
            from config.settings import get_settings

            settings = get_settings()
            broker = TastytradeAdapter(
                account_number=settings.tastytrade_account_number,
                is_paper=is_paper
            )

            if not broker.authenticate():
                print(error("Authentication failed"))
                return 1

            print(success(f"Connected to {broker.account_id}"))

            print(subheader("Step 2: Loading Data from Broker"))
            manager.load_from_broker(broker, is_paper=is_paper)
            print(success(f"Loaded {manager.positions.count} positions"))

        except Exception as e:
            print(error(f"Broker connection failed: {e}"))
            print("  Falling back to mock data...")
            manager.load_mock_data()
    else:
        print(subheader("Loading Mock Data"))
        manager.load_mock_data()
        print(success(f"Loaded {manager.positions.count} mock positions"))

    # Display Portfolio Container
    print(subheader("PORTFOLIO CONTAINER (Raw Broker Data)"))
    print(tabulate(
        manager.portfolio.to_rows(),
        headers=["Field", "Value"],
        tablefmt="rounded_grid"
    ))

    # Display Positions - Summary
    print(subheader(f"POSITIONS CONTAINER - Summary ({manager.positions.count} positions)"))
    print(tabulate(
        manager.positions.to_summary_rows(),
        headers=["Under", "Type", "C/P", "Strike", "DTE", "Qty", "Entry", "Mark", "Mkt Val", "P&L", "P&L%"],
        tablefmt="rounded_grid"
    ))

    # Display Positions - Greeks
    print(subheader("POSITIONS CONTAINER - Greeks (Raw from Broker)"))
    print(tabulate(
        manager.positions.to_greeks_rows(),
        headers=["Under", "C/P", "Strike", "DTE", "Qty", "Delta", "Gamma", "Theta", "Vega", "IV"],
        tablefmt="rounded_grid"
    ))

    # Display Positions - Capital Usage
    print(subheader("POSITIONS CONTAINER - Capital Usage"))
    print(tabulate(
        manager.positions.to_capital_rows(),
        headers=["Under", "C/P", "Qty", "Cost Basis", "Mkt Value", "Maint Req", "BP Effect"],
        tablefmt="rounded_grid"
    ))

    # Display Risk Factors
    print(subheader("RISK FACTORS CONTAINER (Aggregated by Underlying)"))
    risk_rows = manager.risk_factors.to_rows()
    risk_rows.append(["─" * 8] * 8)  # Separator
    risk_rows.append(manager.risk_factors.totals_row())
    print(tabulate(
        risk_rows,
        headers=["Under", "#Pos", "Delta", "Gamma", "Theta", "Vega", "Mkt Val", "P&L"],
        tablefmt="rounded_grid"
    ))

    print()
    print(header("CONTAINERS LOADED SUCCESSFULLY"))
    print(success("All raw broker data populated - no calculated fields"))
    print(dim("  Next: Add calculated fields (risk metrics, scenarios, etc.)"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
