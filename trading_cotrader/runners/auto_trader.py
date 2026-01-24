"""
AutoTrader - End-to-End Orchestrator

Master file that tests ALL features of the trading system.
Update this file whenever you add new capabilities.

Usage:
    python -m runners.autotrader                    # Full cycle
    python -m runners.autotrader --mode sync-only   # Just sync
    python -m runners.autotrader --mode test        # Test without broker
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from decimal import Decimal
from trading_cotrader.services.snapshot_service import SnapshotService

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope
from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter

# Services
from services.portfolio_sync import PortfolioSyncService
from services.event_logger import EventLogger
from services.risk_checker import RiskChecker

# Repositories
from repositories.portfolio import PortfolioRepository
from repositories.position import PositionRepository
from repositories.event import EventRepository
from repositories.trade import TradeRepository

import core.models.domain as dm
import core.models.events as events

logger = logging.getLogger(__name__)


class AutoTrader:
    """
    Main orchestrator for the trading system
    
    This is the master test file - it exercises ALL features.
    """
        
    def __init__(self):
        self.settings = get_settings()
        self.broker = None
        self.portfolio = None
    
    def take_portfolio_snapshot(self):
        self._take_portfolio_snapshot()
        
    def run_full_cycle(self) -> bool:
        """
        Run the complete trading cycle - tests EVERYTHING
        """
        
        print("\n" + "=" * 80)
        print("AUTOTRADER - Full Trading Cycle Test")
        print("=" * 80)
        print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Mode: {'PAPER' if self.settings.is_paper_trading else 'LIVE'}")
        print("=" * 80)
        print()
        
        steps_passed = 0
        steps_failed = 0
        
        print("STEP 1: Connect to Broker")
        print("-" * 80)
        # Step 1: Connect
        if self._connect_broker():
            steps_passed += 1
        else:
            steps_failed += 1
            return False
        
        # Step 2: Sync portfolio
        print("STEP 2: Sync portfolio")
        print("-" * 80)
        if self._sync_portfolio():
            steps_passed += 1
        else:
            steps_failed += 1
            return False
        
        # Step 2a: Take portfolio portfolio snapshot for ML
        print("STEP 3:  Take portfolio portfolio snapshot for ML")
        print("-" * 80)
        if self._take_portfolio_snapshot():
            steps_passed += 1
        else:
            steps_failed += 1
            return False
        
        # Step 4: Display portfolio       
        print("STEP 4:  Display Portfolio")
        print("-" * 80)
        
        self._display_portfolio()
        steps_passed += 1
        
        # Step 5: Test event logging
        print("STEP 5:  Test Event Logging")
        print("-" * 80)
        if self._test_event_logging():
            steps_passed += 1
        else:
            steps_failed += 1
        
        print("STEP 6:  Test Event Analytics")
        print("-" * 80)
        # Step 6: Test event analytics
        if self._test_event_analytics():
            steps_passed += 1
        else:
            steps_failed += 1
        
        # Step 6: Test risk checking
        print("STEP 7:  Test Risk Limit check")
        print("-" * 80)
        if self._test_risk_checking():
            steps_passed += 1
        else:
            steps_failed += 1

        print("STEP 8:  Test trade queries")
        print("-" * 80)
        # Step 7: Test trade queries
        if self._test_trade_queries():
            steps_passed += 1
        else:
            steps_failed += 1
        
        # Step 8: Validate data integrity
        print("STEP 9:  Validate data integrity")
        print("-" * 80)
        if self._validate_data():
            steps_passed += 1
        else:
            steps_failed += 1
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✓ Passed: {steps_passed}")
        print(f"✗ Failed: {steps_failed}")
        print("=" * 80)
        print()
        
        return steps_failed == 0
    
    def run_sync_only(self) -> bool:
        """Just sync portfolio from broker"""
        
        print("\n" + "=" * 80)
        print("AUTOTRADER - Sync Only Mode")
        print("=" * 80)
        print()
        
        if not self._connect_broker():
            return False
        
        if not self._sync_portfolio():
            return False
        
        self._display_portfolio()
        
        print("\n✅ Sync complete")
        return True
    
    def run_test_mode(self) -> bool:
        """
        Test mode - runs through all services without broker connection
        Uses existing data in database
        """
        
        print("\n" + "=" * 80)
        print("AUTOTRADER - Test Mode (No Broker)")
        print("=" * 80)
        print()
        
        with session_scope() as session:
            portfolio_repo = PortfolioRepository(session)
            portfolios = portfolio_repo.get_all_portfolios()
            
            if not portfolios:
                print("❌ No portfolio found in database")
                print("   Run sync first: python -m runners.autotrader --mode sync-only")
                return False
            
            self.portfolio = portfolios[0]
            print(f"✓ Using portfolio: {self.portfolio.name}")
            print()
        
        # Test all features with existing data
        steps_passed = 0
        steps_failed = 0
        
        self._display_portfolio()
        steps_passed += 1
        
        if self._test_event_logging():
            steps_passed += 1
        else:
            steps_failed += 1
        
        if self._test_event_analytics():
            steps_passed += 1
        else:
            steps_failed += 1
        
        if self._test_risk_checking():
            steps_passed += 1
        else:
            steps_failed += 1
        
        if self._test_trade_queries():
            steps_passed += 1
        else:
            steps_failed += 1
        
        if self._validate_data():
            steps_passed += 1
        else:
            steps_failed += 1
        
        print(f"\n✅ Test mode complete: {steps_passed} passed, {steps_failed} failed")
        return steps_failed == 0
    
    # ========================================================================
    # Step Implementations
    # ========================================================================
    
    def _connect_broker(self) -> bool:
        
        """Step 1: Connect to Tastytrade"""
        print("connect to broker")
        
        try:
            self.broker = TastytradeAdapter(
                account_number=self.settings.tastytrade_account_number,
                is_paper=self.settings.is_paper_trading
            )
            
            if not self.broker.authenticate():
                print("❌ Authentication failed")
                return False
            
            print(f"✓ Connected to {self.broker.account_id}")
            print()
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            logger.exception("Connection error:")
            print()
            return False
    
    def _sync_portfolio(self) -> bool:
        """Step 2: Sync portfolio from broker"""
        
        print("STEP 2: Sync Portfolio")
        print("-" * 80)
        
        try:
            with session_scope() as session:
                sync_service = PortfolioSyncService(session, self.broker)
                result = sync_service.sync_portfolio()
                
                if result.success:
                    print(f"✓ Portfolio synced")
                    print(f"  Positions: {result.positions_synced}")
                    print(f"  Failed: {result.positions_failed}")
                    
                    # Load portfolio for later use
                    portfolio_repo = PortfolioRepository(session)
                    self.portfolio = portfolio_repo.get_by_id(result.portfolio_id)
                    
                    print()
                    return True
                else:
                    print(f"❌ Sync failed: {result.error}")
                    print()
                    return False
                    
        except Exception as e:
            print(f"❌ Sync error: {e}")
            logger.exception("Sync error:")
            print()
            return False
    
    def _take_portfolio_snapshot(self):
        
        """Step 2a. : Take Portfolio Snapshot for ML"""
        
        print("STEP 2A:  Take Portfolio Snapshot for ML")
        print("-" * 80)
        with session_scope() as session:
            position_repo = PositionRepository(session)
            # Capture snapshot
            snapshot_service = SnapshotService(session)
            success = snapshot_service.capture_daily_snapshot(self.portfolio, position_repo.get_by_portfolio(self.portfolio.id))
            if success:
                print("\n✅ Snapshot captured successfully!")
            
            # Show summary stats
            stats = snapshot_service.get_summary_stats(self.portfolio.id, days=30)
            if stats:
                print(f"\n📊 Summary Stats (last {stats['days_tracked']} days):")
                print(f"  Total P&L: ${stats['total_pnl']:,.2f}")
                print(f"  Avg Daily P&L: ${stats['avg_daily_pnl']:,.2f}")
                print(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
                print(f"  Avg Delta: {stats['avg_delta']:.2f}")
                
                
    def _display_portfolio(self):
        

        """Step 3: Display portfolio status"""
        
        print("STEP 3: Portfolio Status")
        print("-" * 80)
        
        if not self.portfolio:
            print("⚠️  No portfolio loaded")
            print()
            return
        
        print(f"Portfolio: {self.portfolio.name}")
        print(f"  Account: {self.portfolio.account_id}")
        print(f"  Cash: ${self.portfolio.cash_balance:,.2f}")
        print(f"  Buying Power: ${self.portfolio.buying_power:,.2f}")
        print(f"  Total Equity: ${self.portfolio.total_equity:,.2f}")
        print(f"  Total P&L: ${self.portfolio.total_pnl:,.2f}")
        
        if self.portfolio.portfolio_greeks:
            print(f"\n  Portfolio Greeks:")
            print(f"    Δ = {self.portfolio.portfolio_greeks.delta:,.2f}")
            print(f"    Γ = {self.portfolio.portfolio_greeks.gamma:,.4f}")
            print(f"    Θ = {self.portfolio.portfolio_greeks.theta:,.2f}")
            print(f"    V = {self.portfolio.portfolio_greeks.vega:,.2f}")
        
        # Show positions
        with session_scope() as session:
            position_repo = PositionRepository(session)
            positions = position_repo.get_by_portfolio(self.portfolio.id)
            
            print(f"\n  Positions ({len(positions)}):")
            
            if positions:
                # Group by underlying
                by_underlying = {}
                for pos in positions:
                    underlying = pos.symbol.ticker
                    if underlying not in by_underlying:
                        by_underlying[underlying] = []
                    by_underlying[underlying].append(pos)
                
                for underlying, pos_list in list(by_underlying.items())[:5]:  # Show first 5
                    total_delta = sum(p.greeks.delta if p.greeks else 0 for p in pos_list)
                    total_value = sum(p.market_value for p in pos_list)
                    print(f"    {underlying}: {len(pos_list)} position(s), "
                          f"Δ={total_delta:.2f}, Value=${total_value:,.2f}")
            else:
                print("    (no positions)")
        
        print()
    
    def _test_event_logging(self) -> bool:
        """Step 4: Test event logging"""
        
        print("STEP 4: Event Logging")
        print("-" * 80)
        
        try:
            with session_scope() as session:
                event_logger = EventLogger(session)
                
                # Log a test trade intent
                result = event_logger.log_trade_opened(
                    underlying="SPY",
                    strategy="iron_condor",
                    rationale="AutoTrader test - verifying event logging system",
                    outlook="neutral",
                    confidence=7,
                    max_risk=500.0
                )
                
                if result.success:
                    print(f"✓ Intent logged")
                    print(f"  Trade ID: {result.trade_id}")
                    print(f"  Event ID: {result.event_id}")
                    print(f"  Status: {result.trade.trade_status.value}")
                    print()
                    return True
                else:
                    print(f"❌ Failed to log intent: {result.error}")
                    print()
                    return False
                    
        except Exception as e:
            print(f"❌ Event logging error: {e}")
            logger.exception("Event error:")
            print()
            return False
    
    def _test_event_analytics(self) -> bool:
        """Step 5: Test event analytics"""
        
        print("STEP 5: Event Analytics")
        print("-" * 80)
        
        try:
            with session_scope() as session:
                event_repo = EventRepository(session)
                
                # Get recent events
                recent = event_repo.get_recent_events(days=30)
                print(f"✓ Recent events (30 days): {len(recent)}")
                
                # Get by type
                opened = event_repo.get_by_type(events.EventType.TRADE_OPENED)
                print(f"✓ Trade opened events: {len(opened)}")
                
                # Show sample events
                if opened:
                    print(f"\n  Recent trade intents:")
                    for event in opened[-3:]:  # Last 3
                        print(f"    - {event.underlying_symbol}: {event.decision_context.rationale[:40]}...")
                        print(f"      Confidence: {event.decision_context.confidence_level}/10, "
                              f"Outlook: {event.decision_context.market_outlook.value}")
                
                print()
                return True
                
        except Exception as e:
            print(f"❌ Event analytics error: {e}")
            logger.exception("Analytics error:")
            print()
            return False
    
    def _test_risk_checking(self) -> bool:
        """Step 6: Test risk checking"""
        
        print("STEP 6: Risk Checking")
        print("-" * 80)
        
        if not self.portfolio:
            print("⚠️  No portfolio - skipping risk check")
            print()
            return False
        
        try:
            # Create a small test trade that should pass
            test_trade = dm.Trade(
                id="autotrader_risk_test",
                underlying_symbol="TEST",
                trade_type=dm.TradeType.RESEARCH,
                trade_status=dm.TradeStatus.INTENT,
                strategy=dm.Strategy(
                    name="Test Strategy",
                    strategy_type=dm.StrategyType.CUSTOM,
                    max_loss=Decimal('100')  # Small risk
                ),
                max_risk=Decimal('100'),
                legs=[]
            )
            
            # Run risk check
            with session_scope() as session:
                risk_checker = RiskChecker(self.portfolio, self.settings)
                result = risk_checker.check(test_trade)
                
                print(f"{'✓' if result.approved else '❌'} Risk check: "
                      f"{'APPROVED' if result.approved else 'REJECTED'}")
                
                # Show key metrics
                if result.risk_metrics:
                    pos_size = result.risk_metrics.get('position_size_pct', 0)
                    max_loss = result.risk_metrics.get('max_loss_pct', 0)
                    print(f"  Position size: {pos_size:.2f}% of portfolio")
                    print(f"  Max loss: {max_loss:.2f}% of portfolio")
                
                # Show warnings/rejections
                if result.warnings:
                    print(f"  Warnings: {len(result.warnings)}")
                if result.rejections:
                    print(f"  Rejections: {len(result.rejections)}")
                    for rejection in result.rejections[:2]:  # Show first 2
                        print(f"    - {rejection}")
                
                print()
                return True
                        
        except Exception as e:
            print(f"❌ Risk check error: {e}")
            logger.exception("Risk check error:")
            print()
            return False
    
    def _test_trade_queries(self) -> bool:
        """Step 7: Test trade repository queries"""
        
        print("STEP 7: Trade Queries")
        print("-" * 80)
        
        if not self.portfolio:
            print("⚠️  No portfolio - skipping trade queries")
            print()
            return False
        
        try:
            with session_scope() as session:
                trade_repo = TradeRepository(session)
                
                # Get all trades
                all_trades = trade_repo.get_by_portfolio(self.portfolio.id)
                print(f"✓ Total trades: {len(all_trades)}")
                
                # Get open trades
                open_trades = trade_repo.get_by_portfolio(self.portfolio.id, open_only=True)
                print(f"✓ Open trades: {len(open_trades)}")
                
                # Get intent trades
                intent_trades = [t for t in all_trades if t.trade_status == dm.TradeStatus.INTENT]
                print(f"✓ Intent trades: {len(intent_trades)}")
                
                # Show recent intents
                if intent_trades:
                    print(f"\n  Recent intents:")
                    for trade in intent_trades[-3:]:  # Last 3
                        print(f"    - {trade.underlying_symbol}: {trade.notes[:40] if trade.notes else 'No notes'}...")
                        print(f"      Max risk: ${trade.max_risk}, Status: {trade.trade_status.value}")
                
                print()
                return True
                
        except Exception as e:
            print(f"❌ Trade query error: {e}")
            logger.exception("Query error:")
            print()
            return False
    
    def _validate_data(self) -> bool:
        """Step 8: Validate data integrity"""
        
        print("STEP 8: Data Validation")
        print("-" * 80)
        
        if not self.portfolio:
            print("⚠️  No portfolio - skipping validation")
            print()
            return False
        
        try:
            with session_scope() as session:
                position_repo = PositionRepository(session)
                trade_repo = TradeRepository(session)
                event_repo = EventRepository(session)
                
                # Check positions
                positions = position_repo.get_by_portfolio(self.portfolio.id)
                print(f"✓ Positions in DB: {len(positions)}")
                
                # Check trades
                trades = trade_repo.get_by_portfolio(self.portfolio.id)
                print(f"✓ Trades in DB: {len(trades)}")
                
                # Check events
                all_events = event_repo.get_recent_events(days=365)
                print(f"✓ Events in DB: {len(all_events)}")
                
                # Validate Greeks consistency
                if positions:
                    expected_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
                    actual_delta = self.portfolio.portfolio_greeks.delta if self.portfolio.portfolio_greeks else 0
                    delta_diff = abs(expected_delta - actual_delta)
                    
                    if delta_diff < 1:
                        print(f"✓ Greeks consistent: Δ={actual_delta:.2f}")
                    else:
                        print(f"⚠️  Greeks mismatch: expected={expected_delta:.2f}, actual={actual_delta:.2f}, diff={delta_diff:.2f}")
                
                print()
                return True
                    
        except Exception as e:
            print(f"❌ Validation error: {e}")
            logger.exception("Validation error:")
            print()
            return False


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """
    Main entry point
    
    Usage:
        python -m runners.autotrader                    # Full cycle
        python -m runners.autotrader --mode sync-only   # Just sync
        python -m runners.autotrader --mode test        # Test with existing data
    """
    
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoTrader - End-to-End Orchestrator")
    parser.add_argument(
        '--mode',
        choices=['full', 'sync-only', 'test'],
        default='full',
        help='Execution mode'
    )
    
    args = parser.parse_args()
    
    # Setup
    setup_logging()
    
    try:
        autotrader = AutoTrader()
        
        if args.mode == 'full':
            success = autotrader.run_full_cycle()
        elif args.mode == 'sync-only':
            success = autotrader.run_sync_only()
        elif args.mode == 'test':
            success = autotrader.run_test_mode()
        else:
            print(f"Unknown mode: {args.mode}")
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"AutoTrader failed: {e}")
        logger.exception("Full error:")
        return 1


if __name__ == "__main__":
    sys.exit(main())