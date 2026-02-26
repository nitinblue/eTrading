"""
Diagnose broker → DB → container pipeline.

Runs the exact same steps as run_workflow.py to find where data gets lost.

Usage:
    python -m trading_cotrader.scripts.diagnose_broker
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("BROKER -> DB -> CONTAINER DIAGNOSTIC")
    print("=" * 60)

    # Step 1: Load .env (same as run_workflow.py)
    print("\n[1] Loading settings (triggers .env load)...")
    from trading_cotrader.config.settings import setup_logging
    setup_logging()
    print("    OK")

    # Step 2: Create adapter (same as run_workflow.py)
    print("\n[2] Creating TastytradeAdapter...")
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
    adapter = TastytradeAdapter()
    print(f"    is_paper={adapter.is_paper}")
    print(f"    account_id={adapter.account_id!r}")
    print(f"    client_secret length={len(getattr(adapter, 'client_secret', ''))}")
    print(f"    refresh_token length={len(getattr(adapter, 'refresh_token', ''))}")

    # Step 3: Authenticate
    print("\n[3] Authenticating...")
    auth_ok = adapter.authenticate()
    print(f"    authenticate() returned: {auth_ok}")
    if not auth_ok:
        print("    FAILED — broker auth did not succeed. Check credentials/network.")
        return 1
    print(f"    session: {adapter.session is not None}")
    print(f"    account: {adapter.account is not None}")
    print(f"    account_id: {adapter.account_id}")
    print(f"    accounts: {list(adapter.accounts.keys())}")

    # Step 4: Get positions directly
    print("\n[4] Getting positions from broker...")
    positions = adapter.get_positions()
    print(f"    {len(positions)} positions returned")
    for p in positions:
        sym = p.symbol
        print(f"    {sym.ticker:8s} {sym.asset_type.value:12s} qty={p.quantity}")

    # Step 5: Sync to DB
    print("\n[5] Syncing to DB via PortfolioSyncService...")
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.services.portfolio_sync import PortfolioSyncService

    with session_scope() as session:
        sync_svc = PortfolioSyncService(session, adapter)
        result = sync_svc.sync_portfolio()
    print(f"    success={result.success}")
    print(f"    positions_synced={result.positions_synced}")
    print(f"    portfolio_id={result.portfolio_id}")
    if result.error:
        print(f"    ERROR: {result.error}")
    if result.warnings:
        for w in result.warnings:
            print(f"    WARNING: {w}")

    # Step 6: Check DB directly
    print("\n[6] Checking DB...")
    from trading_cotrader.core.database.schema import PortfolioORM, PositionORM
    with session_scope() as session:
        portfolios = session.query(PortfolioORM).all()
        print(f"    {len(portfolios)} portfolios in DB:")
        for p in portfolios:
            pos_count = session.query(PositionORM).filter_by(portfolio_id=p.id).count()
            print(f"      {p.name:30s} broker={p.broker:12s} account={p.account_id:15s} positions={pos_count}")

    # Step 7: Init ContainerManager (same as engine)
    print("\n[7] Initializing ContainerManager...")
    from trading_cotrader.containers.container_manager import ContainerManager
    from trading_cotrader.config.risk_config_loader import get_risk_config

    cm = ContainerManager()
    risk_config = get_risk_config()
    cm.initialize_bundles(risk_config.portfolios)
    print(f"    {len(cm.get_all_bundles())} bundles created:")
    for b in cm.get_all_bundles():
        print(f"      {b.config_name:20s} broker={b.broker_firm:12s} account={b.account_number}")

    # Step 8: Load bundles from DB
    print("\n[8] Loading bundles from DB...")
    with session_scope() as session:
        cm.load_all_bundles(session)

    print("    Bundle states after load:")
    for b in cm.get_all_bundles():
        pstate = b.portfolio.state
        pos_count = b.positions.count
        has_state = pstate is not None
        equity = float(pstate.total_equity) if pstate else 0
        print(f"      {b.config_name:20s} has_state={has_state} positions={pos_count} equity={equity:.2f}")

    # Step 9: Check tastytrade bundle specifically
    print("\n[9] Tastytrade bundle detail...")
    bundle = cm.get_bundle('tastytrade')
    if bundle:
        pstate = bundle.portfolio.state
        positions_in_container = bundle.positions.get_all()
        print(f"    portfolio_ids: {bundle.portfolio_ids}")
        print(f"    positions in container: {len(positions_in_container)}")
        for p in positions_in_container:
            print(f"      {p.symbol:20s} {p.underlying:8s} qty={p.quantity} delta={p.delta}")
    else:
        print("    BUNDLE NOT FOUND!")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
