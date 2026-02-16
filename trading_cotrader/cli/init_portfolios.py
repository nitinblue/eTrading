"""
CLI: Initialize portfolios from risk_config.yaml
=================================================

Creates 5 real + 5 WhatIf portfolios from config.
Existing portfolios (matched by broker+account) are kept.
Old 'cotrader/*' portfolios are tagged deprecated (not deleted).

Usage:
    python -m trading_cotrader.cli.init_portfolios
    python -m trading_cotrader.cli.init_portfolios --dry-run
"""

import argparse
import sys
import logging

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.services.portfolio_manager import PortfolioManager
from trading_cotrader.config.risk_config_loader import RiskConfigLoader
from trading_cotrader.config.broker_config_loader import load_broker_registry
from trading_cotrader.repositories.portfolio import PortfolioRepository

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Initialize portfolios from config")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created')
    args = parser.parse_args()

    # Load configs
    loader = RiskConfigLoader()
    risk_config = loader.load()
    broker_registry = load_broker_registry()

    portfolios_config = risk_config.portfolios
    real = portfolios_config.get_real_portfolios()
    whatif = portfolios_config.get_whatif_portfolios()

    print("=" * 70)
    print("  PORTFOLIO INITIALIZATION")
    print("=" * 70)
    print(f"  Config: {len(real)} real + {len(whatif)} whatif = {len(real) + len(whatif)} total")
    print()

    # Show what will be created
    print("  REAL PORTFOLIOS:")
    for pc in real:
        bc = broker_registry.get_by_name(pc.broker_firm)
        api_tag = "API" if (bc and bc.has_api) else "MANUAL"
        print(f"    {pc.name:25s} {pc.broker_firm:12s} {pc.account_number:15s} "
              f"{pc.currency} {pc.initial_capital:>12,.0f} [{api_tag}]")

    print()
    print("  WHATIF MIRRORS:")
    for pc in whatif:
        print(f"    {pc.name:25s} mirrors={pc.mirrors_real:20s} "
              f"{pc.currency} {pc.initial_capital:>12,.0f}")

    print()

    if args.dry_run:
        print("  DRY RUN — no changes made.")
        return 0

    # Create portfolios
    with session_scope() as session:
        # Tag old cotrader portfolios as deprecated
        repo = PortfolioRepository(session)
        all_existing = repo.get_all_portfolios()
        deprecated_count = 0
        for p in all_existing:
            if p.broker == 'cotrader':
                # Check if this is an old-style portfolio
                config_name = portfolios_config.get_config_name_for(p.broker, p.account_id)
                if not config_name:
                    # Old portfolio not in new config — tag it
                    if 'deprecated' not in (p.tags or []):
                        tags = list(p.tags or [])
                        tags.append('deprecated')
                        p.tags = tags
                        repo.update_from_domain(p)
                        print(f"  Tagged deprecated: {p.name} (broker=cotrader, account_id={p.account_id})")
                        deprecated_count += 1

        if deprecated_count:
            print(f"  {deprecated_count} old cotrader portfolios tagged deprecated")
            print()

        # Initialize new portfolios
        pm = PortfolioManager(session, config=portfolios_config, broker_registry=broker_registry)
        created = pm.initialize_portfolios()

    print(f"\n  Result: {len(created)} portfolios initialized")
    print()

    # Summary table
    print(f"  {'Name':25s} {'Broker':12s} {'Account':15s} {'Type':8s} {'Currency':8s} {'Capital':>12s}")
    print(f"  {'-'*25} {'-'*12} {'-'*15} {'-'*8} {'-'*8} {'-'*12}")
    for p in created:
        pc = portfolios_config.get_config_name_for(p.broker, p.account_id)
        config = portfolios_config.get_by_name(pc) if pc else None
        ptype = config.portfolio_type if config else "?"
        currency = config.currency if config else "?"
        capital = float(p.total_equity or p.initial_capital or 0)
        print(f"  {p.name:25s} {p.broker:12s} {p.account_id:15s} "
              f"{ptype:8s} {currency:8s} {capital:>12,.0f}")

    print()
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
