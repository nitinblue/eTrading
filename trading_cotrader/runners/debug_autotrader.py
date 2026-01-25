"""
AutoTrader Debugger - Find where auto_trader stops

CORRECT ORDER:
1. Imports
2. Connect to Broker
3. Sync Portfolio (refresh from broker)
4. Take Snapshot (capture for ML - AFTER sync)
5. Event Logging
6. Event Analytics
7. Risk Checking
8. Trade Queries
9. Data Validation

Uses YOUR actual services:
- services.portfolio_sync.PortfolioSyncService (sync from broker)
- services.snapshot_service.SnapshotService (capture for ML)
- services.risk_manager.RiskManager
- services.real_risk_check.RealRiskChecker  
- services.event_logger.EventLogger

Usage:
    python -m runners.debug_autotrader              # Full test with broker sync
    python -m runners.debug_autotrader --skip-sync  # Skip broker sync (use existing data)
"""

import sys
import logging
import traceback
import argparse
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope

logger = logging.getLogger(__name__)

# Global to store portfolio for later steps
_portfolio = None
_skip_sync = False


def test_step(name: str, func):
    """Run a step with full error catching"""
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print('='*60)
    
    try:
        result = func()
        if result:
            print(f"✓ {name} PASSED")
            return True
        else:
            print(f"❌ {name} FAILED (returned False)")
            return False
    except Exception as e:
        print(f"❌ {name} EXCEPTION: {type(e).__name__}")
        print(f"   Message: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("\n>>> This is where auto_trader is stopping! <<<")
        return False


def step1_imports():
    """Test all imports - using YOUR actual file names"""
    print("Testing imports...")
    
    # Core imports
    from services.event_logger import EventLogger
    print("  ✓ EventLogger")
    
    from services.snapshot_service import SnapshotService
    print("  ✓ SnapshotService")
    
    from services.portfolio_sync import PortfolioSyncService
    print("  ✓ PortfolioSyncService")
    
    # YOUR actual risk services
    from services.risk_manager import RiskManager, RiskCheckResult
    print("  ✓ RiskManager (from services.risk_manager)")
    
    from services.real_risk_check import RealRiskChecker
    print("  ✓ RealRiskChecker (from services.real_risk_check)")
    
    # Broker adapter
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
    print("  ✓ TastytradeAdapter")
    
    # Repositories
    from repositories.portfolio import PortfolioRepository
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    from repositories.event import EventRepository
    print("  ✓ All repositories")
    
    # Domain models
    import core.models.domain as dm
    import core.models.events as events
    print("  ✓ Domain models")
    
    # Check for TradeType and TradeStatus (might not exist)
    if hasattr(dm, 'TradeType'):
        print(f"  ✓ TradeType exists: {[e.value for e in dm.TradeType]}")
    else:
        print("  ⚠️  TradeType NOT FOUND in domain.py (OK if not used)")
    
    if hasattr(dm, 'TradeStatus'):
        print(f"  ✓ TradeStatus exists: {[e.value for e in dm.TradeStatus]}")
    else:
        print("  ⚠️  TradeStatus NOT FOUND in domain.py (OK if not used)")
    
    # Check StrategyType
    if hasattr(dm, 'StrategyType'):
        print(f"  ✓ StrategyType exists")
    else:
        print("  ⚠️  StrategyType NOT FOUND in domain.py")
    
    return True


def step2_connect_broker():
    """Test broker connection"""
    global _skip_sync
    
    if _skip_sync:
        print("  ⏭️  Skipping broker connection (--skip-sync)")
        return True
    
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
    settings = get_settings()
    
    print(f"  Mode: {'PAPER' if settings.is_paper_trading else 'LIVE'}")
    
    try:
        broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if broker.authenticate():
            print(f"  ✓ Connected to account: {broker.account_id}")
            # Store for later use
            step2_connect_broker.broker = broker
            return True
        else:
            print("  ❌ Authentication failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

step2_connect_broker.broker = None


def step3_sync_portfolio():
    """Test portfolio sync from broker (refresh positions/balances)"""
    global _portfolio, _skip_sync
    
    if _skip_sync:
        print("  ⏭️  Skipping sync (--skip-sync), loading existing portfolio...")
        from repositories.portfolio import PortfolioRepository
        
        with session_scope() as session:
            repo = PortfolioRepository(session)
            portfolios = repo.get_all_portfolios()
            
            if not portfolios:
                print("  ❌ No existing portfolio found - run without --skip-sync first")
                return False
            
            _portfolio = portfolios[0]
            print(f"  ✓ Using existing portfolio: {_portfolio.name}")
            print(f"    Positions will be from last sync")
            return True
    
    from services.portfolio_sync import PortfolioSyncService
    from repositories.portfolio import PortfolioRepository
    
    broker = step2_connect_broker.broker
    if not broker:
        print("  ❌ No broker connection")
        return False
    
    try:
        with session_scope() as session:
            sync_service = PortfolioSyncService(session, broker)
            result = sync_service.sync_portfolio()
            
            if result.success:
                print(f"  ✓ Portfolio synced from broker")
                print(f"    Positions synced: {result.positions_synced}")
                print(f"    Failed: {result.positions_failed}")
                
                # Load portfolio for later steps
                portfolio_repo = PortfolioRepository(session)
                _portfolio = portfolio_repo.get_by_id(result.portfolio_id)
                
                if _portfolio:
                    print(f"    Portfolio: {_portfolio.name}")
                    print(f"    Equity: ${_portfolio.total_equity:,.2f}")
                    if _portfolio.portfolio_greeks:
                        print(f"    Delta: {_portfolio.portfolio_greeks.delta:.2f}")
                
                return True
            else:
                print(f"  ❌ Sync failed: {result.error}")
                return False
                
    except Exception as e:
        print(f"  ❌ Sync error: {e}")
        traceback.print_exc()
        return False


def step4_take_snapshot():
    """Test snapshot capture for ML (MUST run AFTER sync)"""
    global _portfolio
    
    if not _portfolio:
        print("  ❌ No portfolio - sync must run first")
        return False
    
    from services.snapshot_service import SnapshotService
    from repositories.position import PositionRepository
    
    print("  NOTE: Snapshot captures current state for ML training")
    print("        This should run AFTER sync to capture fresh data")
    
    try:
        with session_scope() as session:
            position_repo = PositionRepository(session)
            positions = position_repo.get_by_portfolio(_portfolio.id)
            
            print(f"  Portfolio: {_portfolio.name}")
            print(f"  Positions to snapshot: {len(positions)}")
            
            # Capture snapshot
            snapshot_svc = SnapshotService(session)
            success = snapshot_svc.capture_daily_snapshot(_portfolio, positions)
            
            if success:
                print(f"  ✓ Snapshot captured for ML")
            else:
                print(f"  ⚠️  Snapshot already exists for today (or failed)")
            
            # Show summary stats
            stats = snapshot_svc.get_summary_stats(_portfolio.id, days=30)
            if stats:
                print(f"\n  📊 Summary Stats (last {stats.get('days_tracked', 0)} days):")
                print(f"    Total snapshots: {stats.get('days_tracked', 0)}")
                print(f"    Avg delta: {stats.get('avg_delta', 0):.2f}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Snapshot error: {e}")
        traceback.print_exc()
        return False


def step5_event_logging():
    """Test event logging"""
    from services.event_logger import EventLogger
    
    print("  Testing EventLogger.log_trade_opened...")
    
    with session_scope() as session:
        event_logger = EventLogger(session)
        
        # Check method exists
        if not hasattr(event_logger, 'log_trade_opened'):
            print("  ❌ log_trade_opened method not found!")
            return False
        
        # Check signature
        import inspect
        sig = inspect.signature(event_logger.log_trade_opened)
        print(f"  Method signature: log_trade_opened{sig}")
        
        # Call it
        result = event_logger.log_trade_opened(
            underlying="DEBUG",
            strategy="iron_condor",
            rationale="Debug test - checking event logging",
            outlook="neutral",
            confidence=5,
            max_risk=100.0
        )
        
        print(f"  Result type: {type(result)}")
        print(f"  Success: {result.success}")
        
        if not result.success:
            print(f"  Error: {result.error}")
            return False
        
        print(f"  Trade ID: {result.trade_id}")
        print(f"  Event ID: {result.event_id}")
        
        return True


def step6_event_analytics():
    """Test event analytics"""
    from repositories.event import EventRepository
    import core.models.events as events
    
    with session_scope() as session:
        event_repo = EventRepository(session)
        
        # Test get_recent_events
        recent = event_repo.get_recent_events(days=30)
        print(f"  Recent events (30 days): {len(recent)}")
        
        # Test get_by_type
        opened = event_repo.get_by_type(events.EventType.TRADE_OPENED)
        print(f"  Trade opened events: {len(opened)}")
        
        # Show sample
        if opened:
            event = opened[-1]
            print(f"  Latest event:")
            print(f"    ID: {event.event_id}")
            print(f"    Symbol: {event.underlying_symbol}")
            if event.decision_context:
                rationale = event.decision_context.rationale[:50] if event.decision_context.rationale else "None"
                print(f"    Rationale: {rationale}...")
        
        return True


def step7_risk_checking():
    """Test risk checking - using YOUR RiskManager/RealRiskChecker"""
    import core.models.domain as dm
    
    print("  Testing RiskManager...")
    
    # Test RiskManager directly
    try:
        from services.risk_manager import RiskManager, RiskCheckResult
        
        # Try to find risk_limits.yaml
        risk_manager = RiskManager("risk_limits.yaml")
        print(f"  ✓ RiskManager loaded risk_limits.yaml")
        
        # Show some limits
        limits = risk_manager.limits
        print(f"    Max portfolio delta: ±{limits['greeks']['max_portfolio_delta']}")
        print(f"    Max single trade risk: {limits['portfolio']['max_single_trade_risk_percent']}%")
        
    except FileNotFoundError as e:
        print(f"  ⚠️  risk_limits.yaml not found: {e}")
        print("     Make sure risk_limits.yaml is in services/ or config/")
        return False
    except Exception as e:
        print(f"  ❌ RiskManager error: {e}")
        return False
    
    print("\n  Testing RealRiskChecker...")
    
    # Test RealRiskChecker
    try:
        from services.real_risk_check import RealRiskChecker
        
        risk_checker = RealRiskChecker()
        print(f"  ✓ RealRiskChecker created")
        
        # Load portfolio state
        if risk_checker.load_portfolio_state():
            print(f"  ✓ Portfolio state loaded")
            print(f"    Portfolio: {risk_checker.portfolio.name}")
            print(f"    Positions: {len(risk_checker.positions)}")
            
            # Create simple test trade
            test_trade = dm.Trade(
                underlying_symbol="TEST",
                legs=[]
            )
            
            # Run risk check
            result = risk_checker.check_proposed_trade(test_trade)
            print(f"  ✓ Risk check completed")
            print(f"    Passed: {result.passed}")
            print(f"    Violations: {len(result.violations)}")
            print(f"    Blocking: {len(result.blocking_violations)}")
            print(f"    Warnings: {len(result.warnings)}")
            
        else:
            print(f"  ⚠️  Could not load portfolio state")
            
    except Exception as e:
        print(f"  ❌ RealRiskChecker error: {e}")
        traceback.print_exc()
        return False
    
    return True


def step8_trade_queries():
    """Test trade queries"""
    global _portfolio
    
    from repositories.trade import TradeRepository
    from repositories.portfolio import PortfolioRepository
    import core.models.domain as dm
    
    with session_scope() as session:
        # Use global portfolio or load fresh
        if not _portfolio:
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            if not portfolios:
                print("  ⚠️  No portfolio")
                return False
            portfolio = portfolios[0]
        else:
            portfolio = _portfolio
        
        trade_repo = TradeRepository(session)
        
        # Get all trades
        all_trades = trade_repo.get_by_portfolio(portfolio.id)
        print(f"  Total trades: {len(all_trades)}")
        
        # Get open trades
        open_trades = trade_repo.get_by_portfolio(portfolio.id, open_only=True)
        print(f"  Open trades: {len(open_trades)}")
        
        # Check for intent trades (if TradeStatus exists)
        if hasattr(dm, 'TradeStatus'):
            intent_trades = [t for t in all_trades 
                           if hasattr(t, 'trade_status') and t.trade_status == dm.TradeStatus.INTENT]
            print(f"  Intent trades: {len(intent_trades)}")
        else:
            print("  ⚠️  TradeStatus not in domain.py - skipping intent count")
        
        return True


def step9_data_validation():
    """Validate data integrity"""
    global _portfolio
    
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    from repositories.event import EventRepository
    from repositories.portfolio import PortfolioRepository
    
    with session_scope() as session:
        # Use global portfolio or load fresh
        if not _portfolio:
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            if not portfolios:
                print("  ⚠️  No portfolio")
                return False
            portfolio = portfolios[0]
        else:
            portfolio = _portfolio
        
        position_repo = PositionRepository(session)
        trade_repo = TradeRepository(session)
        event_repo = EventRepository(session)
        
        # Check positions
        positions = position_repo.get_by_portfolio(portfolio.id)
        print(f"  Positions in DB: {len(positions)}")
        
        # Check trades
        trades = trade_repo.get_by_portfolio(portfolio.id)
        print(f"  Trades in DB: {len(trades)}")
        
        # Check events
        all_events = event_repo.get_recent_events(days=365)
        print(f"  Events in DB: {len(all_events)}")
        
        # Validate Greeks consistency
        if positions and portfolio.portfolio_greeks:
            expected_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
            actual_delta = portfolio.portfolio_greeks.delta
            delta_diff = abs(expected_delta - actual_delta)
            
            if delta_diff < 1:
                print(f"  ✓ Greeks consistent: Δ={actual_delta:.2f}")
            else:
                print(f"  ⚠️  Greeks mismatch: expected={expected_delta:.2f}, actual={actual_delta:.2f}")
        
        return True


def main():
    """Run all diagnostic steps"""
    global _skip_sync
    
    parser = argparse.ArgumentParser(description="AutoTrader Debugger")
    parser.add_argument('--skip-sync', action='store_true', 
                       help='Skip broker sync, use existing data')
    args = parser.parse_args()
    
    _skip_sync = args.skip_sync
    
    setup_logging()
    
    print("\n" + "=" * 80)
    print("AUTO_TRADER DEBUGGER")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Skip Sync: {_skip_sync}")
    print("=" * 80)
    
    steps = [
        ("Step 1: Imports", step1_imports),
        ("Step 2: Connect Broker", step2_connect_broker),
        ("Step 3: Sync Portfolio (from broker)", step3_sync_portfolio),
        ("Step 4: Take Snapshot (for ML)", step4_take_snapshot),
        ("Step 5: Event Logging", step5_event_logging),
        ("Step 6: Event Analytics", step6_event_analytics),
        ("Step 7: Risk Checking", step7_risk_checking),
        ("Step 8: Trade Queries", step8_trade_queries),
        ("Step 9: Data Validation", step9_data_validation),
    ]
    
    passed = 0
    failed = 0
    
    for name, func in steps:
        if test_step(name, func):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("DEBUG SUMMARY")
    print("=" * 80)
    print(f"✓ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print("\nCheck the first failure above - that's where auto_trader is stopping.")
        print("Common issues:")
        print("  - Broker credentials not configured")
        print("  - risk_limits.yaml not found in services/ or config/")
        print("  - TradeType/TradeStatus enums missing from domain.py")
    else:
        print("\n✅ All steps passed! auto_trader should work now.")
    
    print("\nUsage tips:")
    print("  python -m runners.debug_autotrader              # Full test with broker sync")
    print("  python -m runners.debug_autotrader --skip-sync  # Test with existing data")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())