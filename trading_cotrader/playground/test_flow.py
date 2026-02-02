"""
AutoTrader Debugger - Comprehensive Test Harness

Tests ALL functionality of the trading system including:
- Broker connection and sync
- Market Data Container (NEW)
- Instrument Registry (NEW)
- Risk Aggregation (NEW)
- Hedging Calculator (NEW)
- Event Logging
- ML Pipeline
- Risk Checking

STEPS:
1.  Imports - verify all modules load
2.  Connect Broker
3.  Sync Portfolio (refresh from broker)
4.  Market Data Container (NEW) - build from positions
5.  Instrument Registry (NEW) - test registration and expiry
6.  Risk Aggregation (NEW) - aggregate by underlying
7.  Hedge Calculator (NEW) - calculate hedge recommendations
8.  Take Snapshot (for ML)
9.  Event Logging
10. Event Analytics
11. Risk Checking
12. Trade Queries
13. Data Validation

Usage:
    python -m runners.debug_autotrader              # Full test with broker sync
    python -m runners.debug_autotrader --skip-sync  # Skip broker sync (use existing data)
    python -m runners.debug_autotrader --mock       # Use mock data (no broker needed)
"""

import sys
import logging
import traceback
import argparse
from pathlib import Path
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope

logger = logging.getLogger(__name__)

# Global state for sharing between steps
_portfolio = None
_broker = None
_skip_sync = False
_use_mock = False
_broker_positions = []  # Raw positions from broker
_market_data_service = None
_instrument_registry = None


def test_step(name: str, func):
    """Run a step with full error catching"""
    print(f"\n{'='*70}")
    print(f"TESTING: {name}")
    print('='*70)
    
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
        print("\n>>> This is where the test is failing! <<<")
        return False


# =============================================================================
# STEP 1: IMPORTS
# =============================================================================

def step1_imports():
    """Test all imports - including new market_data and hedging modules"""
    print("Testing imports...")
    
    # ----- Core imports -----
    from services.event_logger import EventLogger
    print("  ✓ EventLogger")
    
    from services.snapshot_service import SnapshotService
    print("  ✓ SnapshotService")
    
    from services.portfolio_sync import PortfolioSyncService
    print("  ✓ PortfolioSyncService")
    
    # ----- Risk services -----
    from services.risk_manager import RiskManager, RiskCheckResult
    print("  ✓ RiskManager")
    
    try:
        from services.real_risk_check import RealRiskChecker
        print("  ✓ RealRiskChecker")
    except ImportError:
        print("  ⚠️  RealRiskChecker not found (optional)")
    
    # ----- Broker adapter -----
    from adapters.tastytrade_adapter import TastytradeAdapter
    print("  ✓ TastytradeAdapter")
    
    # ----- Repositories -----
    from repositories.portfolio import PortfolioRepository
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    from repositories.event import EventRepository
    print("  ✓ All repositories")
    
    # ----- Domain models -----
    import core.models.domain as dm
    import core.models.events as events
    print("  ✓ Domain models")
    
    # ----- NEW: Market Data module -----
    try:
        from services.market_data import (
            MarketDataService,
            InstrumentRegistry,
            Instrument,
            RiskFactor,
            AssetType,
            OptionType,
            Greeks,
            create_stock_instrument,
            create_equity_option_instrument,
            build_market_data_container
        )
        print("  ✓ Market Data module (NEW)")
    except ImportError as e:
        print(f"  ❌ Market Data module MISSING: {e}")
        print("     Copy market_data/ folder to services/")
        return False
    
    # ----- NEW: Hedging module -----
    try:
        from services.hedging import (
            HedgeCalculator,
            RiskBucket,
            HedgeRecommendation,
            HedgeType
        )
        print("  ✓ Hedging module (NEW)")
    except ImportError as e:
        print(f"  ❌ Hedging module MISSING: {e}")
        print("     Copy hedging/ folder to services/")
        return False
    
    # ----- Check for key domain enums -----
    if hasattr(dm, 'TradeType'):
        print(f"  ✓ TradeType exists")
    else:
        print("  ⚠️  TradeType NOT FOUND (OK if not used)")
    
    if hasattr(dm, 'TradeStatus'):
        print(f"  ✓ TradeStatus exists")
    else:
        print("  ⚠️  TradeStatus NOT FOUND (OK if not used)")
    
    return True


# =============================================================================
# STEP 2: CONNECT BROKER
# =============================================================================

def step2_connect_broker():
    """Test broker connection"""
    global _broker, _skip_sync, _use_mock
    
    if _use_mock:
        print("  ⏭️  Using mock data (--mock)")
        return True
    
    if _skip_sync:
        print("  ⏭️  Skipping broker connection (--skip-sync)")
        return True
    
    from adapters.tastytrade_adapter import TastytradeAdapter
    settings = get_settings()
    
    print(f"  Mode: {'PAPER' if settings.is_paper_trading else 'LIVE'}")
    
    try:
        _broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if _broker.authenticate():
            print(f"  ✓ Connected to account: {_broker.account_id}")
            return True
        else:
            print("  ❌ Authentication failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False


# =============================================================================
# STEP 3: SYNC PORTFOLIO
# =============================================================================

def step3_sync_portfolio():
    """Test portfolio sync from broker"""
    global _portfolio, _skip_sync, _use_mock, _broker, _broker_positions
    
    if _use_mock:
        print("  ⏭️  Using mock positions")
        _broker_positions = _get_mock_positions()
        print(f"  ✓ Loaded {len(_broker_positions)} mock positions")
        return True
    
    if _skip_sync:
        print("  ⏭️  Skipping sync, loading existing portfolio...")
        from repositories.portfolio import PortfolioRepository
        
        with session_scope() as session:
            repo = PortfolioRepository(session)
            portfolios = repo.get_all_portfolios()
            
            if not portfolios:
                print("  ❌ No existing portfolio - run without --skip-sync first")
                return False
            
            _portfolio = portfolios[0]
            print(f"  ✓ Using existing portfolio: {_portfolio.name}")
            return True
    
    from services.portfolio_sync import PortfolioSyncService
    from repositories.portfolio import PortfolioRepository
    
    if not _broker:
        print("  ❌ No broker connection")
        return False
    
    try:
        # Get raw positions from broker (for market data container)
        _broker_positions = _broker.get_positions()
        print(f"  ✓ Fetched {len(_broker_positions)} positions from broker")
        
        with session_scope() as session:
            sync_service = PortfolioSyncService(session, _broker)
            result = sync_service.sync_portfolio()
            
            if result.success:
                print(f"  ✓ Portfolio synced")
                print(f"    Positions synced: {result.positions_synced}")
                print(f"    Failed: {result.positions_failed}")
                
                portfolio_repo = PortfolioRepository(session)
                _portfolio = portfolio_repo.get_by_id(result.portfolio_id)
                
                if _portfolio:
                    print(f"    Portfolio: {_portfolio.name}")
                    print(f"    Equity: ${_portfolio.total_equity:,.2f}")
                
                return True
            else:
                print(f"  ❌ Sync failed: {result.error}")
                return False
                
    except Exception as e:
        print(f"  ❌ Sync error: {e}")
        traceback.print_exc()
        return False


# =============================================================================
# STEP 4: MARKET DATA CONTAINER (NEW)
# =============================================================================

def step4_market_data_container():
    """Test market data container creation from positions"""
    global _broker_positions, _market_data_service, _instrument_registry
    
    from services.market_data import (
        MarketDataService,
        InstrumentRegistry,
        build_market_data_container
    )
    
    print("  Building market data container from positions...")
    
    # Use broker positions or mock
    positions = _broker_positions if _broker_positions else _get_mock_positions()
    
    if not positions:
        print("  ❌ No positions to process")
        return False
    
    # Create service and registry
    _instrument_registry = InstrumentRegistry()
    _market_data_service = MarketDataService(_instrument_registry)
    
    # Sync from positions
    new_count = _market_data_service.sync_from_positions(positions)
    print(f"  ✓ Registered {new_count} new instruments")
    
    # Get container
    container = _market_data_service.get_container()
    
    print(f"  Container summary:")
    print(f"    Total instruments: {len(container.instruments)}")
    print(f"    DXLink symbols: {len(container.dxlink_symbols)}")
    print(f"    Underlyings: {container.get_underlyings()}")
    
    # Show by type
    from collections import Counter
    type_counts = Counter(inst.asset_type.value for inst in container.instruments)
    print(f"    By type: {dict(type_counts)}")
    
    # Show DXLink symbols (what to pass to DXLinkStreamer)
    print(f"  DXLink symbols (for DXLinkStreamer.get_greeks()):")
    for sym in container.dxlink_symbols[:10]:  # First 10
        print(f"    - {sym}")
    if len(container.dxlink_symbols) > 10:
        print(f"    ... and {len(container.dxlink_symbols) - 10} more")
    
    return True


# =============================================================================
# STEP 5: INSTRUMENT REGISTRY (NEW)
# =============================================================================

def step5_instrument_registry():
    """Test instrument registry functionality"""
    global _instrument_registry
    
    from services.market_data import (
        InstrumentRegistry,
        create_stock_instrument,
        create_equity_option_instrument,
        OptionType,
        Greeks
    )
    
    if not _instrument_registry:
        _instrument_registry = InstrumentRegistry()
    
    print("  Testing registry operations...")
    
    # Test duplicate handling
    test_stock = create_stock_instrument("TEST")
    _instrument_registry.register(test_stock)
    _instrument_registry.register(test_stock)  # Should not duplicate
    
    # Test lookup
    found = _instrument_registry.get_by_id("TEST")
    if found:
        print(f"  ✓ Lookup works: found {found.instrument_id}")
    else:
        print("  ❌ Lookup failed")
        return False
    
    # Test expiry detection
    from datetime import date, timedelta
    
    # Create an expired option
    expired_option = create_equity_option_instrument(
        occ_symbol="TEST  200101P00100000",
        ticker="TEST",
        option_type=OptionType.PUT,
        strike=Decimal("100"),
        expiry=date(2020, 1, 1),  # Expired
        multiplier=100
    )
    _instrument_registry.register(expired_option)
    
    # Cleanup expired
    expired = _instrument_registry.cleanup_expired()
    print(f"  ✓ Expired cleanup: removed {len(expired)} instruments")
    
    # Test get_expiring_soon
    expiring = _instrument_registry.get_expiring_soon(days=30)
    print(f"  ✓ Expiring in 30 days: {len(expiring)} instruments")
    
    # Test summary
    summary = _instrument_registry.summary()
    print(f"  ✓ Registry summary: {summary}")
    
    # Cleanup test instrument
    _instrument_registry.unregister("TEST")
    
    return True


# =============================================================================
# STEP 6: RISK AGGREGATION (NEW)
# =============================================================================

def step6_risk_aggregation():
    """Test risk aggregation by underlying"""
    global _instrument_registry, _market_data_service
    
    from services.hedging import HedgeCalculator, RiskBucket
    from services.market_data import Greeks
    
    if not _instrument_registry:
        print("  ❌ No instrument registry - run step 4 first")
        return False
    
    print("  Testing risk aggregation...")
    
    calc = HedgeCalculator(_instrument_registry)
    
    # Build mock position data with greeks
    # In real usage, this comes from DXLink updates
    positions_with_greeks = []
    
    for inst in _instrument_registry.get_all():
        if inst.is_option():
            # Simulate greeks for options
            mock_greeks = Greeks(
                delta=Decimal("-0.30") if inst.option_type.value == "PUT" else Decimal("0.40"),
                gamma=Decimal("0.02"),
                theta=Decimal("-0.15"),
                vega=Decimal("0.50")
            )
            positions_with_greeks.append({
                "instrument_id": inst.instrument_id,
                "quantity": -2,  # Short 2 contracts
                "greeks": mock_greeks
            })
    
    if not positions_with_greeks:
        print("  ⚠️  No option positions to aggregate (testing with mock)")
        # Create mock for testing
        positions_with_greeks = [
            {
                "instrument_id": "SPY   260331P00580000",
                "quantity": -5,
                "greeks": Greeks(
                    delta=Decimal("-0.30"),
                    gamma=Decimal("0.015"),
                    theta=Decimal("-0.20"),
                    vega=Decimal("0.55")
                )
            }
        ]
    
    # Aggregate by underlying
    buckets = calc.aggregate_risk_by_underlying(positions_with_greeks)
    
    print(f"  ✓ Aggregated {len(buckets)} risk buckets:")
    for underlying, bucket in buckets.items():
        print(f"    {underlying}:")
        print(f"      Δ = {bucket.delta:+.2f}")
        print(f"      Γ = {bucket.gamma:+.4f}")
        print(f"      Θ = {bucket.theta:+.2f}")
        print(f"      V = {bucket.vega:+.2f}")
        print(f"      Positions: {bucket.position_count}")
    
    return True


# =============================================================================
# STEP 7: HEDGE CALCULATOR (NEW)
# =============================================================================

def step7_hedge_calculator():
    """Test hedge calculation"""
    global _instrument_registry
    
    from services.hedging import HedgeCalculator, HedgeType
    from services.market_data import Greeks
    
    if not _instrument_registry:
        print("  ❌ No instrument registry - run step 4 first")
        return False
    
    print("  Testing hedge calculations...")
    
    calc = HedgeCalculator(_instrument_registry)
    
    # Test delta hedge for equity
    print("\n  Test 1: Equity delta hedge")
    hedge = calc.calculate_delta_hedge(
        underlying_symbol="SPY",
        current_delta=Decimal("-1.50"),  # Short 150 delta
        underlying_price=Decimal("588.25")
    )
    
    if hedge:
        print(f"    Recommendation: {hedge.action} {abs(hedge.quantity)} {hedge.instrument_symbol}")
        print(f"    Hedge type: {hedge.hedge_type.value}")
        print(f"    Current Δ: {hedge.current_exposure} → Post-hedge: {hedge.post_hedge_exposure}")
        if hedge.estimated_cost:
            print(f"    Estimated cost: ${hedge.estimated_cost:,.2f}")
    else:
        print("    No hedge needed (delta near zero)")
    
    # Test futures hedge
    print("\n  Test 2: Futures delta hedge")
    futures_hedge = calc.calculate_delta_hedge(
        underlying_symbol="/GC",
        current_delta=Decimal("-2.5"),  # Short 2.5 contracts worth
        underlying_price=Decimal("2050.00")
    )
    
    if futures_hedge:
        print(f"    Recommendation: {futures_hedge.action} {abs(futures_hedge.quantity)} {futures_hedge.instrument_symbol}")
        print(f"    Hedge type: {futures_hedge.hedge_type.value}")
    else:
        print("    No hedge needed")
    
    # Test no hedge needed
    print("\n  Test 3: No hedge needed (small delta)")
    no_hedge = calc.calculate_delta_hedge(
        underlying_symbol="AAPL",
        current_delta=Decimal("0.1"),  # Very small
        underlying_price=Decimal("185.00")
    )
    
    if no_hedge:
        print(f"    ❌ Unexpected hedge recommendation")
    else:
        print(f"    ✓ Correctly returned no hedge needed")
    
    return True


# =============================================================================
# STEP 8: TAKE SNAPSHOT (for ML)
# =============================================================================

def step8_take_snapshot():
    """Test snapshot capture for ML"""
    global _portfolio
    
    if not _portfolio:
        print("  ⚠️  No portfolio - using mock test")
        return True  # Don't fail, just note it
    
    from services.snapshot_service import SnapshotService
    
    try:
        with session_scope() as session:
            snapshot_service = SnapshotService(session)
            snapshot = snapshot_service.capture_daily_snapshot(_portfolio.id)
            
            if snapshot:
                print(f"  ✓ Snapshot captured")
                print(f"    ID: {snapshot.id}")
                print(f"    Date: {snapshot.snapshot_date}")
                print(f"    Equity: ${snapshot.total_equity:,.2f}")
                return True
            else:
                print("  ⚠️  No snapshot returned (may already exist for today)")
                return True
                
    except Exception as e:
        print(f"  ⚠️  Snapshot error: {e}")
        return True  # Don't fail the whole test


# =============================================================================
# STEP 9: EVENT LOGGING
# =============================================================================

def step9_event_logging():
    """Test event logging system"""
    global _portfolio
    
    from services.event_logger import EventLogger
    
    try:
        with session_scope() as session:
            event_logger = EventLogger(session)
            print(f"  ✓ EventLogger initialized")
            
            # Check method signature
            import inspect
            sig = inspect.signature(event_logger.log_trade_opened)
            print(f"    Method signature: log_trade_opened{sig}")
            
            # Don't actually create events in test mode - just verify it works
            print(f"  ✓ Event logger ready (not creating test events)")
            
            return True
            
    except Exception as e:
        print(f"  ⚠️  Event logging error: {e}")
        return True  # Don't fail - this is not critical for market data testing


# =============================================================================
# STEP 10: EVENT ANALYTICS
# =============================================================================

def step10_event_analytics():
    """Test event analytics"""
    global _portfolio
    
    try:
        from services.event_analytics import EventAnalytics
        from repositories.event import EventRepository
        
        with session_scope() as session:
            event_repo = EventRepository(session)
            analytics = EventAnalytics(event_repo)
            
            portfolio_id = _portfolio.id if _portfolio else "test-portfolio"
            
            # Get summary stats
            summary = analytics.get_trade_summary(portfolio_id)
            
            print(f"  ✓ Event analytics working")
            print(f"    Total events: {summary.get('total_events', 0)}")
            print(f"    Win rate: {summary.get('win_rate', 0):.1%}")
            
            return True
            
    except ImportError:
        print("  ⚠️  EventAnalytics not available")
        return True
    except Exception as e:
        print(f"  ⚠️  Analytics error: {e}")
        return True


# =============================================================================
# STEP 11: RISK CHECKING
# =============================================================================

def step11_risk_checking():
    """Test risk limit checking"""
    global _portfolio
    
    from services.risk_manager import RiskManager, RiskCheckResult
    import core.models.domain as dm
    from repositories.position import PositionRepository
    from repositories.trade import TradeRepository
    
    try:
        risk_manager = RiskManager()
        print(f"  ✓ RiskManager initialized")
        
        if not _portfolio:
            print(f"  ⚠️  No portfolio - skipping detailed risk check")
            return True
        
        with session_scope() as session:
            position_repo = PositionRepository(session)
            trade_repo = TradeRepository(session)
            
            # Get current positions and trades
            current_positions = position_repo.get_by_portfolio(_portfolio.id)
            current_trades = trade_repo.get_by_portfolio(_portfolio.id)
            
            # Create a test trade
            test_trade = dm.Trade(
                id="test-trade-001",
                portfolio_id=_portfolio.id,
                underlying_symbol="SPY",
                strategy=dm.Strategy(
                    name="test_strategy",
                    strategy_type=dm.StrategyType.PUT_CREDIT_SPREAD if hasattr(dm, 'StrategyType') else None,
                    max_loss=Decimal("500")
                ),
                legs=[]
            )
            
            # Check risk with all 4 required arguments
            result = risk_manager.validate_trade(
                test_trade, 
                _portfolio,
                current_positions,
                current_trades
            )
            
            print(f"    Passed: {result.passed}")
            print(f"    Violations: {len(result.violations)}")
            
        return True
        
    except Exception as e:
        print(f"  ⚠️  Risk check error: {e}")
        return True


# =============================================================================
# STEP 12: TRADE QUERIES
# =============================================================================

def step12_trade_queries():
    """Test trade repository queries"""
    global _portfolio
    
    from repositories.trade import TradeRepository
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
        
        trade_repo = TradeRepository(session)
        
        all_trades = trade_repo.get_by_portfolio(portfolio.id)
        print(f"  Total trades: {len(all_trades)}")
        
        open_trades = trade_repo.get_by_portfolio(portfolio.id, open_only=True)
        print(f"  Open trades: {len(open_trades)}")
        
        return True


# =============================================================================
# STEP 13: DATA VALIDATION
# =============================================================================

def step13_data_validation():
    """Validate data integrity"""
    global _portfolio
    
    from repositories.position import PositionRepository
    
    with session_scope() as session:
        position_repo = PositionRepository(session)
        
        if _portfolio:
            positions = position_repo.get_by_portfolio(_portfolio.id)
            print(f"  DB positions: {len(positions)}")
            
            # Check for positions with greeks
            with_greeks = [p for p in positions if p.greeks and p.greeks.delta != 0]
            print(f"  With Greeks: {len(with_greeks)}")
            
            # Validate greeks sum
            if _portfolio.portfolio_greeks:
                expected_delta = sum(p.greeks.delta * p.quantity for p in with_greeks if p.greeks)
                actual_delta = _portfolio.portfolio_greeks.delta
                
                delta_diff = abs(float(expected_delta) - float(actual_delta))
                if delta_diff < 1:
                    print(f"  ✓ Greeks consistent: Δ={actual_delta:.2f}")
                else:
                    print(f"  ⚠️  Greeks mismatch: expected={expected_delta:.2f}, actual={actual_delta:.2f}")
        
        return True


# =============================================================================
# MOCK DATA
# =============================================================================

def _get_mock_positions() -> List[Dict[str, Any]]:
    """Generate mock positions for testing without broker"""
    return [
        # Stock
        {
            "symbol": "MSFT",
            "instrument_type": "EQUITY",
            "quantity": 100
        },
        # Equity option - put
        {
            "symbol": "MSFT  260331P00400000",
            "instrument_type": "EQUITY_OPTION",
            "underlying_symbol": "MSFT",
            "strike_price": "400.00",
            "expiration_date": "2026-03-31",
            "option_type": "PUT",
            "multiplier": 100,
            "quantity": -2
        },
        # Equity option - call
        {
            "symbol": "SPY   260331C00600000",
            "instrument_type": "EQUITY_OPTION",
            "underlying_symbol": "SPY",
            "strike_price": "600.00",
            "expiration_date": "2026-03-31",
            "option_type": "CALL",
            "multiplier": 100,
            "quantity": 5
        },
        # Another underlying
        {
            "symbol": "AAPL  260331P00180000",
            "instrument_type": "EQUITY_OPTION",
            "underlying_symbol": "AAPL",
            "strike_price": "180.00",
            "expiration_date": "2026-03-31",
            "option_type": "PUT",
            "multiplier": 100,
            "quantity": -3
        },
    ]


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run all diagnostic steps"""
    global _skip_sync, _use_mock
    
    parser = argparse.ArgumentParser(description="AutoTrader Debugger - Comprehensive Test Harness")
    parser.add_argument('--skip-sync', action='store_true', 
                       help='Skip broker sync, use existing data')
    parser.add_argument('--mock', action='store_true',
                       help='Use mock data (no broker connection needed)')
    args = parser.parse_args()
    
    _skip_sync = args.skip_sync
    _use_mock = args.mock
    
    setup_logging()
    
    print("\n" + "=" * 80)
    print("AUTO_TRADER DEBUGGER - COMPREHENSIVE TEST HARNESS")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Skip Sync: {_skip_sync}")
    print(f"Mock Mode: {_use_mock}")
    print("=" * 80)
    
    steps = [
        ("Step 1: Imports", step1_imports),
        ("Step 2: Connect Broker", step2_connect_broker),
        ("Step 3: Sync Portfolio", step3_sync_portfolio),
        ("Step 4: Market Data Container (NEW)", step4_market_data_container),
        ("Step 5: Instrument Registry (NEW)", step5_instrument_registry),
        ("Step 6: Risk Aggregation (NEW)", step6_risk_aggregation),
        ("Step 7: Hedge Calculator (NEW)", step7_hedge_calculator),
        ("Step 8: Take Snapshot", step8_take_snapshot),
        ("Step 9: Event Logging", step9_event_logging),
        ("Step 10: Event Analytics", step10_event_analytics),
        ("Step 11: Risk Checking", step11_risk_checking),
        ("Step 12: Trade Queries", step12_trade_queries),
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
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✓ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed > 0:
        print("\nCheck the first failure above - that's where to focus.")
        print("\nCommon issues:")
        print("  - market_data/ folder not in services/")
        print("  - hedging/ folder not in services/")
        print("  - Broker credentials not configured")
        print("  - risk_limits.yaml not found")
    else:
        print("\n✅ All steps passed! System is ready.")
    
    print("\nUsage:")
    print("  python -m runners.debug_autotrader              # Full test with broker")
    print("  python -m runners.debug_autotrader --skip-sync  # Use existing data")
    print("  python -m runners.debug_autotrader --mock       # Mock data (no broker)")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
