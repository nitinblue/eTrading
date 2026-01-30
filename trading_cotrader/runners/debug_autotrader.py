"""
AutoTrader Debugger - Enhanced with WhatIf Support

Tests ALL features including:
- Portfolio sync from broker
- Snapshot capture for ML
- Event logging
- Risk checking
- WhatIf trades and portfolios
- P&L Attribution

Usage:
    python -m runners.debug_autotrader                    # Full test with broker sync
    python -m runners.debug_autotrader --skip-sync        # Skip broker sync (use existing data)
    python -m runners.debug_autotrader --mode what-if     # Test what-if features only
"""

import sys
import logging
import traceback
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope

logger = logging.getLogger(__name__)

# Global state
_portfolio = None
_positions = []
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
        print("\n>>> This is where the test is stopping! <<<")
        return False


# ============================================================================
# STEP 1: Imports
# ============================================================================

def step1_imports():
    """Test all imports including enhanced domain"""
    print("Testing imports...")
    
    # Core domain models
    import core.models.domain as dm
    print("  ✓ core.models.domain")
    
    # Check for enhanced enums
    if hasattr(dm, 'PortfolioType'):
        print(f"  ✓ PortfolioType: {[e.value for e in dm.PortfolioType]}")
    else:
        print("  ⚠️  PortfolioType NOT FOUND - using original domain.py?")
    
    if hasattr(dm, 'TradeType'):
        values = [e.value for e in dm.TradeType]
        has_what_if = 'what_if' in values
        print(f"  ✓ TradeType: {values}")
        if has_what_if:
            print("    ✓ WHAT_IF trade type available")
        else:
            print("    ⚠️  WHAT_IF not in TradeType - using original?")
    
    if hasattr(dm, 'TradeStatus'):
        print(f"  ✓ TradeStatus: {[e.value for e in dm.TradeStatus]}")
    
    # Check for enhanced classes
    if hasattr(dm, 'PnLAttribution'):
        print("  ✓ PnLAttribution class available")
    else:
        print("  ⚠️  PnLAttribution NOT FOUND")
    
    if hasattr(dm, 'MarketData'):
        print("  ✓ MarketData class available")
    else:
        print("  ⚠️  MarketData NOT FOUND")
    
    if hasattr(dm, 'RiskMetrics'):
        print("  ✓ RiskMetrics class available")
    else:
        print("  ⚠️  RiskMetrics NOT FOUND")
    
    # Check Portfolio factory methods
    if hasattr(dm.Portfolio, 'create_what_if'):
        print("  ✓ Portfolio.create_what_if() method available")
    else:
        print("  ⚠️  Portfolio.create_what_if() NOT FOUND")
    
    # Check Trade factory methods
    if hasattr(dm.Trade, 'create_what_if'):
        print("  ✓ Trade.create_what_if() method available")
    else:
        print("  ⚠️  Trade.create_what_if() NOT FOUND")
    
    # Services
    from services.event_logger import EventLogger
    print("  ✓ EventLogger")
    
    from services.snapshot_service import SnapshotService
    print("  ✓ SnapshotService")
    
    from services.portfolio_sync import PortfolioSyncService
    print("  ✓ PortfolioSyncService")
    
    from services.risk_manager import RiskManager, RiskCheckResult
    print("  ✓ RiskManager")
    
    from services.real_risk_check import RealRiskChecker
    print("  ✓ RealRiskChecker")
    
    # WhatIf
    try:
        from core.models.what_if import WhatIfScenario, WhatIfEngine
        print("  ✓ WhatIfScenario, WhatIfEngine")
    except ImportError as e:
        print(f"  ⚠️  WhatIf imports failed: {e}")
    
    # Repositories
    from repositories.portfolio import PortfolioRepository
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    from repositories.event import EventRepository
    print("  ✓ All repositories")
    
    # Broker adapter
    from adapters.tastytrade_adapter import TastytradeAdapter
    print("  ✓ TastytradeAdapter")
    
    return True


# ============================================================================
# STEP 2: Connect Broker
# ============================================================================

def step2_connect_broker():
    """Test broker connection"""
    global _skip_sync
    
    if _skip_sync:
        print("  ⏭️  Skipping broker connection (--skip-sync)")
        return True
    
    from adapters.tastytrade_adapter import TastytradeAdapter
    settings = get_settings()
    
    print(f"  Mode: {'PAPER' if settings.is_paper_trading else 'LIVE'}")
    
    try:
        broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if broker.authenticate():
            print(f"  ✓ Connected to account: {broker.account_id}")
            step2_connect_broker.broker = broker
            return True
        else:
            print("  ❌ Authentication failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

step2_connect_broker.broker = None


# ============================================================================
# STEP 3: Sync Portfolio
# ============================================================================

def step3_sync_portfolio():
    """Test portfolio sync from broker"""
    global _portfolio, _positions, _skip_sync
    
    if _skip_sync:
        print("  ⏭️  Skipping sync (--skip-sync), loading existing portfolio...")
        from repositories.portfolio import PortfolioRepository
        from repositories.position import PositionRepository
        
        with session_scope() as session:
            repo = PortfolioRepository(session)
            portfolios = repo.get_all_portfolios()
            
            if not portfolios:
                print("  ❌ No existing portfolio found - run without --skip-sync first")
                return False
            
            _portfolio = portfolios[0]
            
            pos_repo = PositionRepository(session)
            _positions = pos_repo.get_by_portfolio(_portfolio.id)
            
            print(f"  ✓ Using existing portfolio: {_portfolio.name}")
            print(f"    Positions: {len(_positions)}")
            return True
    
    from services.portfolio_sync import PortfolioSyncService
    from repositories.portfolio import PortfolioRepository
    from repositories.position import PositionRepository
    
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
                
                portfolio_repo = PortfolioRepository(session)
                _portfolio = portfolio_repo.get_by_id(result.portfolio_id)
                
                pos_repo = PositionRepository(session)
                _positions = pos_repo.get_by_portfolio(_portfolio.id)
                
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


# ============================================================================
# STEP 4: Take Snapshot
# ============================================================================

def step4_take_snapshot():
    """Test snapshot capture for ML (AFTER sync)"""
    global _portfolio, _positions
    
    if not _portfolio:
        print("  ❌ No portfolio - sync must run first")
        return False
    
    from services.snapshot_service import SnapshotService
    
    print("  NOTE: Snapshot captures current state for ML training")
    
    try:
        with session_scope() as session:
            print(f"  Portfolio: {_portfolio.name}")
            print(f"  Positions to snapshot: {len(_positions)}")
            
            snapshot_svc = SnapshotService(session)
            success = snapshot_svc.capture_daily_snapshot(_portfolio, _positions)
            
            if success:
                print(f"  ✓ Snapshot captured for ML")
            else:
                print(f"  ⚠️  Snapshot already exists for today (or failed)")
            
            stats = snapshot_svc.get_summary_stats(_portfolio.id, days=30)
            if stats:
                print(f"\n  📊 Summary Stats:")
                print(f"    Total snapshots: {stats.get('days_tracked', 0)}")
            
            return True
            
    except Exception as e:
        print(f"  ❌ Snapshot error: {e}")
        traceback.print_exc()
        return False


# ============================================================================
# STEP 5: Event Logging
# ============================================================================

def step5_event_logging():
    """Test event logging"""
    from services.event_logger import EventLogger
    
    print("  Testing EventLogger.log_trade_opened...")
    
    with session_scope() as session:
        event_logger = EventLogger(session)
        
        result = event_logger.log_trade_opened(
            underlying="DEBUG",
            strategy="iron_condor",
            rationale="Debug test - checking event logging",
            outlook="neutral",
            confidence=5,
            max_risk=100.0
        )
        
        print(f"  Success: {result.success}")
        
        if not result.success:
            print(f"  Error: {result.error}")
            return False
        
        print(f"  Trade ID: {result.trade_id}")
        print(f"  Event ID: {result.event_id}")
        
        return True


# ============================================================================
# STEP 6: Event Analytics
# ============================================================================

def step6_event_analytics():
    """Test event analytics"""
    from repositories.event import EventRepository
    import core.models.events as events
    
    with session_scope() as session:
        event_repo = EventRepository(session)
        
        recent = event_repo.get_recent_events(days=30)
        print(f"  Recent events (30 days): {len(recent)}")
        
        opened = event_repo.get_by_type(events.EventType.TRADE_OPENED)
        print(f"  Trade opened events: {len(opened)}")
        
        if opened:
            event = opened[-1]
            print(f"  Latest event:")
            print(f"    ID: {event.event_id}")
            print(f"    Symbol: {event.underlying_symbol}")
        
        return True


# ============================================================================
# STEP 7: Risk Checking
# ============================================================================

def step7_risk_checking():
    """Test risk checking"""
    import core.models.domain as dm
    
    print("  Testing RiskManager...")
    
    try:
        from services.risk_manager import RiskManager
        
        risk_manager = RiskManager("risk_limits.yaml")
        print(f"  ✓ RiskManager loaded")
        
        limits = risk_manager.limits
        print(f"    Max portfolio delta: ±{limits['greeks']['max_portfolio_delta']}")
        
    except Exception as e:
        print(f"  ❌ RiskManager error: {e}")
        return False
    
    print("\n  Testing RealRiskChecker...")
    
    try:
        from services.real_risk_check import RealRiskChecker
        
        risk_checker = RealRiskChecker()
        print(f"  ✓ RealRiskChecker created")
        
        if risk_checker.load_portfolio_state():
            print(f"  ✓ Portfolio state loaded")
            
            # Create test trade
            test_trade = dm.Trade(
                underlying_symbol="TEST",
                legs=[]
            )
            
            result = risk_checker.check_proposed_trade(test_trade)
            print(f"  ✓ Risk check completed")
            print(f"    Passed: {result.passed}")
            print(f"    Violations: {len(result.violations)}")
            
        else:
            print(f"  ⚠️  Could not load portfolio state")
            
    except Exception as e:
        print(f"  ❌ RealRiskChecker error: {e}")
        traceback.print_exc()
        return False
    
    return True


# ============================================================================
# STEP 8: Trade Queries
# ============================================================================

def step8_trade_queries():
    """Test trade queries"""
    global _portfolio
    
    from repositories.trade import TradeRepository
    from repositories.portfolio import PortfolioRepository
    import core.models.domain as dm
    
    with session_scope() as session:
        if not _portfolio:
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            if not portfolios:
                print("  ⚠️  No portfolio")
                return True  # Don't fail, just skip
            portfolio = portfolios[0]
        else:
            portfolio = _portfolio
        
        trade_repo = TradeRepository(session)
        
        all_trades = trade_repo.get_by_portfolio(portfolio.id)
        print(f"  Total trades: {len(all_trades)}")
        
        open_trades = trade_repo.get_by_portfolio(portfolio.id, open_only=True)
        print(f"  Open trades: {len(open_trades)}")
        
        # Check trade types if TradeType exists
        if hasattr(dm, 'TradeType') and all_trades:
            by_type = {}
            for t in all_trades:
                if hasattr(t, 'trade_type') and t.trade_type:
                    type_val = t.trade_type.value if hasattr(t.trade_type, 'value') else str(t.trade_type)
                    by_type[type_val] = by_type.get(type_val, 0) + 1
            
            if by_type:
                print(f"  By type: {by_type}")
        
        return True


# ============================================================================
# STEP 9: WhatIf Portfolio
# ============================================================================

def step9_whatif_portfolio():
    """Test creating a what-if portfolio"""
    import core.models.domain as dm
    
    print("  Testing What-If Portfolio creation...")
    
    # Check if enhanced domain is available
    if not hasattr(dm, 'PortfolioType'):
        print("  ⚠️  PortfolioType not available - skipping what-if test")
        print("     (You may be using original domain.py)")
        return True
    
    if not hasattr(dm.Portfolio, 'create_what_if'):
        print("  ⚠️  Portfolio.create_what_if() not available")
        return True
    
    try:
        # Create a what-if portfolio for 0DTE strategies
        whatif_portfolio = dm.Portfolio.create_what_if(
            name="0DTE Test Portfolio",
            capital=Decimal('10000'),
            description="Testing 0DTE iron condors",
            risk_limits={
                'max_delta': 50,
                'max_position_pct': 20,
                'max_trade_risk_pct': 10
            }
        )
        
        print(f"  ✓ Created what-if portfolio: {whatif_portfolio.name}")
        print(f"    Type: {whatif_portfolio.portfolio_type.value}")
        print(f"    Capital: ${whatif_portfolio.total_equity:,.2f}")
        print(f"    Max Delta: {whatif_portfolio.max_portfolio_delta}")
        print(f"    Max Trade Risk: {whatif_portfolio.max_single_trade_risk_pct}%")
        
        return True
        
    except Exception as e:
        print(f"  ❌ What-if portfolio error: {e}")
        traceback.print_exc()
        return False


# ============================================================================
# STEP 10: WhatIf Trade
# ============================================================================

def step10_whatif_trade():
    """Test creating a what-if trade"""
    import core.models.domain as dm
    
    print("  Testing What-If Trade creation...")
    
    # Check if enhanced domain is available
    if not hasattr(dm, 'TradeType'):
        print("  ⚠️  TradeType not available - skipping")
        return True
    
    # Check for WHAT_IF in TradeType
    if not hasattr(dm.TradeType, 'WHAT_IF'):
        print("  ⚠️  TradeType.WHAT_IF not available")
        return True
    
    try:
        # Create a what-if trade
        if hasattr(dm.Trade, 'create_what_if'):
            # Use factory method
            whatif_trade = dm.Trade.create_what_if(
                underlying="SPY",
                strategy_type=dm.StrategyType.IRON_CONDOR,
                legs=[],
                portfolio_id="test-portfolio-id"
            )
        else:
            # Manual creation
            whatif_trade = dm.Trade(
                underlying_symbol="SPY",
                trade_type=dm.TradeType.WHAT_IF,
                trade_status=dm.TradeStatus.INTENT,
                legs=[]
            )
        
        print(f"  ✓ Created what-if trade")
        print(f"    Underlying: {whatif_trade.underlying_symbol}")
        print(f"    Type: {whatif_trade.trade_type.value}")
        print(f"    Status: {whatif_trade.trade_status.value}")
        
        # Test lifecycle methods if available
        if hasattr(whatif_trade, 'mark_evaluated'):
            whatif_trade.mark_evaluated()
            print(f"    After evaluate: {whatif_trade.trade_status.value}")
        
        if hasattr(whatif_trade, 'mark_executed'):
            whatif_trade.mark_executed(
                fill_price=Decimal('2.50'),
                underlying_price=Decimal('590')
            )
            print(f"    After execute: {whatif_trade.trade_status.value}")
            print(f"    Entry price: ${whatif_trade.entry_price}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ What-if trade error: {e}")
        traceback.print_exc()
        return False


# ============================================================================
# STEP 11: WhatIf Scenario
# ============================================================================

def step11_whatif_scenario():
    """Test WhatIfScenario from what_if.py"""
    
    print("  Testing WhatIfScenario...")
    
    try:
        from core.models.what_if import WhatIfScenario, WhatIfEngine
        
        # Create a put credit spread what-if
        what_if = WhatIfScenario.create_put_credit_spread(
            underlying='SPY',
            short_strike=580,
            long_strike=575,
            expiration=datetime.now() + timedelta(days=30),
            credit=1.50
        )
        
        print(f"  ✓ Created WhatIfScenario: {what_if.name}")
        print(f"    Strategy: {what_if.inputs.strategy_type}")
        print(f"    Credit: ${what_if.inputs.net_credit}")
        
        # Create engine and evaluate
        engine = WhatIfEngine()
        
        # Mock portfolio for testing
        class MockPortfolio:
            total_equity = Decimal('100000')
            buying_power = Decimal('50000')
            portfolio_greeks = None
        
        engine.evaluate(what_if, MockPortfolio(), [])
        
        print(f"  ✓ Evaluated what-if scenario")
        print(f"    Max Profit: ${what_if.outputs.max_profit}")
        print(f"    Max Loss: ${what_if.outputs.max_loss}")
        print(f"    Status: {what_if.outputs.status.value}")
        
        proceed, reason = what_if.should_proceed()
        print(f"    Should proceed: {proceed}")
        print(f"    Reason: {reason}")
        
        return True
        
    except ImportError as e:
        print(f"  ⚠️  WhatIf module not available: {e}")
        return True  # Don't fail, just skip
    except Exception as e:
        print(f"  ❌ WhatIfScenario error: {e}")
        traceback.print_exc()
        return False


# ============================================================================
# STEP 12: P&L Attribution
# ============================================================================

def step12_pnl_attribution():
    """Test P&L attribution"""
    import core.models.domain as dm
    
    print("  Testing P&L Attribution...")
    
    if not hasattr(dm, 'PnLAttribution'):
        print("  ⚠️  PnLAttribution not available - skipping")
        return True
    
    try:
        # Create a position with Greeks for P&L attribution
        if hasattr(dm, 'Greeks'):
            entry_greeks = dm.Greeks(
                delta=Decimal('-0.30'),
                gamma=Decimal('0.02'),
                theta=Decimal('0.05'),
                vega=Decimal('0.15')
            )
            print(f"  ✓ Created entry Greeks")
        
        # Check if Position has get_pnl_attribution method
        if hasattr(dm.Position, 'get_pnl_attribution'):
            print("  ✓ Position.get_pnl_attribution() method available")
        else:
            print("  ⚠️  Position.get_pnl_attribution() not available")
        
        # Check if Leg has get_pnl_attribution method
        if hasattr(dm.Leg, 'get_pnl_attribution'):
            print("  ✓ Leg.get_pnl_attribution() method available")
        else:
            print("  ⚠️  Leg.get_pnl_attribution() not available")
        
        # Create a test PnLAttribution directly
        pnl_attr = dm.PnLAttribution(
            delta_pnl=Decimal('150'),
            gamma_pnl=Decimal('25'),
            theta_pnl=Decimal('50'),
            vega_pnl=Decimal('-30'),
            unexplained_pnl=Decimal('5'),
            actual_pnl=Decimal('200')
        )
        
        print(f"  ✓ Created PnLAttribution")
        print(f"    Delta P&L: ${pnl_attr.delta_pnl}")
        print(f"    Theta P&L: ${pnl_attr.theta_pnl}")
        print(f"    Unexplained: ${pnl_attr.unexplained_pnl}")
        print(f"    Total Model: ${pnl_attr.total_model_pnl}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ P&L Attribution error: {e}")
        traceback.print_exc()
        return False


# ============================================================================
# STEP 13: Data Validation
# ============================================================================

def step13_data_validation():
    """Validate data integrity"""
    global _portfolio
    
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    from repositories.event import EventRepository
    from repositories.portfolio import PortfolioRepository
    
    with session_scope() as session:
        if not _portfolio:
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            if not portfolios:
                print("  ⚠️  No portfolio")
                return True
            portfolio = portfolios[0]
        else:
            portfolio = _portfolio
        
        position_repo = PositionRepository(session)
        trade_repo = TradeRepository(session)
        event_repo = EventRepository(session)
        
        positions = position_repo.get_by_portfolio(portfolio.id)
        print(f"  Positions in DB: {len(positions)}")
        
        trades = trade_repo.get_by_portfolio(portfolio.id)
        print(f"  Trades in DB: {len(trades)}")
        
        all_events = event_repo.get_recent_events(days=365)
        print(f"  Events in DB: {len(all_events)}")
        
        # Validate Greeks consistency
        if positions and portfolio.portfolio_greeks:
            sum_delta = sum(
                float(p.greeks.delta) if p.greeks else 0 
                for p in positions
            )
            portfolio_delta = float(portfolio.portfolio_greeks.delta)
            delta_diff = abs(sum_delta - portfolio_delta)
            
            if delta_diff < 5:  # Allow small difference
                print(f"  ✓ Greeks consistent: Δ={portfolio_delta:.2f}")
            else:
                print(f"  ⚠️  Greeks mismatch: sum={sum_delta:.2f}, portfolio={portfolio_delta:.2f}")
        
        return True


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run all diagnostic steps"""
    global _skip_sync
    
    parser = argparse.ArgumentParser(description="AutoTrader Debugger")
    parser.add_argument('--skip-sync', action='store_true', 
                       help='Skip broker sync, use existing data')
    parser.add_argument('--mode', choices=['full', 'what-if', 'quick'],
                       default='full', help='Test mode')
    args = parser.parse_args()
    
    _skip_sync = args.skip_sync
    
    setup_logging()
    
    print("\n" + "=" * 80)
    print("AUTO_TRADER DEBUGGER - Enhanced with WhatIf Support")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")
    print(f"Skip Sync: {_skip_sync}")
    print("=" * 80)
    
    # Define steps based on mode
    if args.mode == 'what-if':
        steps = [
            ("Step 1: Imports", step1_imports),
            ("Step 2: WhatIf Portfolio", step9_whatif_portfolio),
            ("Step 3: WhatIf Trade", step10_whatif_trade),
            ("Step 4: WhatIf Scenario", step11_whatif_scenario),
            ("Step 5: P&L Attribution", step12_pnl_attribution),
        ]
    elif args.mode == 'quick':
        steps = [
            ("Step 1: Imports", step1_imports),
            ("Step 2: Load Portfolio", step3_sync_portfolio),
            ("Step 3: Risk Checking", step7_risk_checking),
        ]
    else:  # full
        steps = [
            ("Step 1: Imports", step1_imports),
            ("Step 2: Connect Broker", step2_connect_broker),
            ("Step 3: Sync Portfolio", step3_sync_portfolio),
            ("Step 4: Take Snapshot", step4_take_snapshot),
            ("Step 5: Event Logging", step5_event_logging),
            ("Step 6: Event Analytics", step6_event_analytics),
            ("Step 7: Risk Checking", step7_risk_checking),
            ("Step 8: Trade Queries", step8_trade_queries),
            ("Step 9: WhatIf Portfolio", step9_whatif_portfolio),
            ("Step 10: WhatIf Trade", step10_whatif_trade),
            ("Step 11: WhatIf Scenario", step11_whatif_scenario),
            ("Step 12: P&L Attribution", step12_pnl_attribution),
            ("Step 13: Data Validation", step13_data_validation),
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
        print("\nCheck the first failure above - that's where the issue is.")
        print("\nCommon issues:")
        print("  - Enhanced domain.py not installed (missing PortfolioType, PnLAttribution)")
        print("  - Broker credentials not configured")
        print("  - risk_limits.yaml not found")
    else:
        print("\n✅ All steps passed!")
    
    print("\nUsage:")
    print("  python -m runners.debug_autotrader                 # Full test")
    print("  python -m runners.debug_autotrader --skip-sync     # Skip broker")
    print("  python -m runners.debug_autotrader --mode what-if  # WhatIf only")
    print("  python -m runners.debug_autotrader --mode quick    # Quick test")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())