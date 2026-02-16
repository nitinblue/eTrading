"""
CLI: Load Stallion Asset portfolio from PDF data
=================================================

Loads 29 equity holdings + cash from Stallion Core Fund (SACF5925).
Data extracted from Stallion.pdf (as of 31/01/2026).

Smart lifecycle:
    - Matches existing positions by (portfolio_id, underlying_symbol, is_open)
    - New positions → creates trade
    - Existing positions → skips (no duplicate)
    - Updates cash_balance and total_equity on portfolio

Usage:
    python -m trading_cotrader.cli.load_stallion
    python -m trading_cotrader.cli.load_stallion --dry-run
"""

import argparse
import sys
import logging
import uuid
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

# Stallion Core Fund holdings as of 31/01/2026 (from PDF)
# Format: (symbol/name, sector, market_value_inr, pct_of_assets)
STALLION_HOLDINGS = [
    ("JEENA SIKHO LIFECARE LTD", "PHARMACEUTICALS", 186682, 3.91),
    ("SKY GOLD AND DIAMONDS LTD", "GEMS JEWELLERY AND WATCHES", 59535, 1.25),
    ("TIMEX GROUP INDIA LTD", "GEMS JEWELLERY AND WATCHES", 16626, 0.35),
    ("INTERGLOBE AVIATION LTD", "AIRLINES", 179264, 3.76),
    ("BLACKBUCK LTD", "TRANSPORT RELATED SERVICES", 185937, 3.90),
    ("INVENTURUS KNOWLEDGE SOLUTIONS LTD", "IT ENABLED SERVICES", 96218, 2.02),
    ("POLYCAB INDIA LTD", "CABLES ELECTRICALS", 301580, 6.32),
    ("GODFREY PHILLIPS INDIA LTD", "CIGARETTES TOBACCO PRODUCTS", 20355, 0.43),
    ("ICICI PRUDENTIAL ASSET MANAGEMENT COMPANY LTD", "ASSET MANAGEMENT COMPANY", 169438, 3.55),
    ("NIPPON LIFE INDIA ASSET MANAGEMENT LTD", "ASSET MANAGEMENT COMPANY", 109762, 2.30),
    ("SHAILY ENGINEERING PLASTICS LTD", "PLASTIC PRODUCTS INDUSTRIAL", 24878, 0.52),
    ("VARUN BEVERAGES LTD", "OTHER BEVERAGES", 156926, 3.29),
    ("APOLLO HOSPITALS ENTERPRISES LTD", "HOSPITAL", 90486, 1.90),
    ("CARTRADE TECH LTD", "E-RETAIL E-COMMERCE", 58285, 1.22),
    ("ETERNAL LTD", "E-RETAIL E-COMMERCE", 479074, 10.04),
    ("FSN E-COMMERCE VENTURES LTD", "E-RETAIL E-COMMERCE", 94762, 1.99),
    ("MEESHO LTD", "E-RETAIL E-COMMERCE", 175717, 3.68),
    ("VISHAL MEGA MART LTD", "DIVERSIFIED RETAIL", 222176, 4.66),
    ("BLS INTERNATIONAL SERVICES LTD", "TOUR TRAVEL RELATED SERVICES", 116625, 2.44),
    ("LE TRAVENUES TECHNOLOGY LIMITED", "TOUR TRAVEL RELATED SERVICES", 54234, 1.14),
    ("MUTHOOT FINANCE LTD", "NON BANKING FINANCIAL COMPANY", 222117, 4.65),
    ("COFORGE LTD", "COMPUTERS SOFTWARE CONSULTING", 99228, 2.08),
    ("RATEGAIN TRAVEL TECHNOLOGIES LTD", "COMPUTERS SOFTWARE CONSULTING", 63046, 1.32),
    ("MAHINDRA AND MAHINDRA LTD", "PASSENGER CARS UTILITY VEHICLES", 295135, 6.18),
    ("ADITYA VISION LTD", "SPECIALITY RETAIL", 62500, 1.31),
    ("TRENT LTD", "SPECIALITY RETAIL", 45426, 0.95),
    ("V2 RETAIL LTD", "SPECIALITY RETAIL", 95789, 2.01),
    ("BSE LTD", "EXCHANGE AND DATA PLATFORM", 374798, 7.85),
    ("MULTI COMMODITY EXCHANGE OF INDIA LTD", "EXCHANGE AND DATA PLATFORM", 235104, 4.93),
]

CASH_AND_EQUIVALENT = Decimal('479815')
DIVIDEND_RECEIVABLE = Decimal('1086')
PORTFOLIO_VALUE = Decimal('4772604')
CONTRIBUTION = Decimal('5000000')
PROFIT_LOSS = Decimal('-227396')
INCEPTION_DATE = "2025-08-28"


def main():
    parser = argparse.ArgumentParser(description="Load Stallion portfolio from PDF data")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be loaded')
    args = parser.parse_args()

    print("=" * 70)
    print("  STALLION CORE FUND — LOAD HOLDINGS")
    print("=" * 70)
    print(f"  Account: SACF5925 (Stallion Asset)")
    print(f"  As of: 31/01/2026")
    print(f"  Contribution: INR {CONTRIBUTION:,.0f}")
    print(f"  Portfolio Value: INR {PORTFOLIO_VALUE:,.0f}")
    print(f"  P&L: INR {PROFIT_LOSS:,.0f}")
    print(f"  Holdings: {len(STALLION_HOLDINGS)}")
    print(f"  Cash: INR {CASH_AND_EQUIVALENT:,.0f}")
    print()

    # Show holdings
    print(f"  {'#':>3} {'Security':45s} {'Sector':35s} {'Value':>12s} {'%':>6s}")
    print(f"  {'---':>3} {'-'*45} {'-'*35} {'-'*12} {'-'*6}")
    for i, (name, sector, value, pct) in enumerate(STALLION_HOLDINGS, 1):
        print(f"  {i:3d} {name:45s} {sector:35s} {value:>12,d} {pct:>5.2f}%")
    print(f"  {'':3s} {'Cash and Equivalent':45s} {'':35s} {int(CASH_AND_EQUIVALENT):>12,d} {10.05:>5.2f}%")
    print(f"  {'':3s} {'Dividend/Interest receivable':45s} {'':35s} {int(DIVIDEND_RECEIVABLE):>12,d} {0.02:>5.2f}%")
    print(f"  {'':3s} {'-'*45} {'':35s} {'-'*12} {'-'*6}")
    print(f"  {'':3s} {'TOTAL':45s} {'':35s} {int(PORTFOLIO_VALUE):>12,d} {'100%':>6s}")
    print()

    if args.dry_run:
        print("  DRY RUN — no changes made.")
        return 0

    # Load into DB
    import trading_cotrader.core.models.domain as dm
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.services.portfolio_manager import PortfolioManager
    from trading_cotrader.repositories.trade import TradeRepository
    from trading_cotrader.repositories.portfolio import PortfolioRepository

    with session_scope() as session:
        pm = PortfolioManager(session)
        portfolio = pm.get_portfolio_by_name('stallion')

        if not portfolio:
            print("  Portfolio 'stallion' not found in DB. Run init_portfolios first.")
            print("  Running: python -m trading_cotrader.cli.init_portfolios")
            portfolios = pm.initialize_portfolios()
            portfolio = pm.get_portfolio_by_name('stallion')
            if not portfolio:
                print("  FAILED: Could not create stallion portfolio.")
                return 1
            print(f"  Created portfolio: {portfolio.name} (id={portfolio.id})")

        trade_repo = TradeRepository(session)
        portfolio_repo = PortfolioRepository(session)

        # Check existing open trades
        existing = trade_repo.get_by_portfolio(portfolio.id, open_only=True)
        existing_symbols = {t.underlying_symbol for t in existing}

        new_count = 0
        skip_count = 0

        for name, sector, value, pct in STALLION_HOLDINGS:
            # Use shortened symbol for DB (first word or known ticker)
            symbol_key = name  # Store full name as underlying

            if symbol_key in existing_symbols:
                print(f"    SKIP {name[:40]:40s} (already in DB)")
                skip_count += 1
                continue

            trade_id = str(uuid.uuid4())
            mkt_value = Decimal(str(value))

            sym = dm.Symbol(
                ticker=symbol_key,
                asset_type=dm.AssetType.EQUITY,
                description=f"{sector}",
                multiplier=1,
            )
            leg = dm.Leg(
                id=f"{trade_id}_leg_0",
                symbol=sym,
                quantity=1,  # managed fund — we track value, not shares
                side=dm.OrderSide.BUY_TO_OPEN,
                entry_price=mkt_value,
                current_price=mkt_value,
            )

            inception = datetime.strptime(INCEPTION_DATE, '%Y-%m-%d')

            trade = dm.Trade(
                id=trade_id,
                legs=[leg],
                strategy=dm.Strategy(
                    name='Long Stock',
                    strategy_type=dm.StrategyType.SINGLE,
                    risk_category=dm.RiskCategory.DEFINED,
                ),
                trade_type=dm.TradeType.REAL,
                trade_status=dm.TradeStatus.EXECUTED,
                underlying_symbol=symbol_key,
                entry_price=mkt_value,
                current_price=mkt_value,
                entry_greeks=dm.Greeks(delta=Decimal('1')),
                current_greeks=dm.Greeks(delta=Decimal('1')),
                trade_source=dm.TradeSource.MANUAL,
                notes=f"Stallion Core Fund | {sector} | {pct}% of portfolio | INR {value:,}",
                tags=['stallion', 'india', sector.lower().replace(' ', '_')],
                executed_at=inception,
            )

            created = trade_repo.create_from_domain(trade, portfolio.id)
            if created:
                print(f"    NEW  {name[:40]:40s} INR {value:>12,d}")
                new_count += 1
            else:
                print(f"    FAIL {name[:40]:40s}")

        # Update portfolio cash and equity
        portfolio.cash_balance = CASH_AND_EQUIVALENT + DIVIDEND_RECEIVABLE
        portfolio.total_equity = PORTFOLIO_VALUE
        portfolio.initial_capital = CONTRIBUTION
        portfolio_repo.update_from_domain(portfolio)

        print()
        print(f"  Results:")
        print(f"    New positions: {new_count}")
        print(f"    Skipped (existing): {skip_count}")
        print(f"    Cash balance: INR {CASH_AND_EQUIVALENT + DIVIDEND_RECEIVABLE:,.0f}")
        print(f"    Total equity: INR {PORTFOLIO_VALUE:,.0f}")

    print()
    print("=" * 70)
    print("  Done.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
