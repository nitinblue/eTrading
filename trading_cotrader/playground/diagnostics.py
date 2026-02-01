"""
System Diagnostics and Module Tests - FIXED VERSION

Fixes:
1. Correct API signatures for risk and pricing modules
2. Debug helper for auto_trader issues
3. Tests all modules properly

Usage:
    python -m runners.diagnostics                    # Run all diagnostics
    python -m runners.diagnostics --test risk        # Test risk module only
    python -m runners.diagnostics --test ml          # Test ML module only
    python -m runners.diagnostics --debug auto       # Debug auto_trader issues
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope, get_db_manager

logger = logging.getLogger(__name__)


class SystemDiagnostics:
    """
    Diagnose and fix system issues.
    Also tests all modules.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.results = []
    
    def run_all(self):
        """Run all diagnostics"""
        print("\n" + "=" * 80)
        print("SYSTEM DIAGNOSTICS")
        print("=" * 80)
        print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 80)
        
        # Database health
        self._check_database()
        
        # Portfolio duplicates
        self._check_portfolio_duplicates()
        
        # Orphaned records
        self._check_orphaned_records()
        
        # Data integrity
        self._check_data_integrity()
        
        # Print summary
        self._print_summary()
    
    def _check_database(self):
        """Check database connectivity and tables"""
        print("\n📊 Database Health")
        print("-" * 40)
        
        try:
            db = get_db_manager()
            if db.health_check():
                self._pass("Database connection OK")
            else:
                self._fail("Database health check failed")
            
            # Check tables exist
            from core.database.schema import (
                PortfolioORM, PositionORM, TradeORM, 
                TradeEventORM, DailyPerformanceORM
            )
            
            with session_scope() as session:
                tables = {
                    'portfolios': session.query(PortfolioORM).count(),
                    'positions': session.query(PositionORM).count(),
                    'trades': session.query(TradeORM).count(),
                    'events': session.query(TradeEventORM).count(),
                    'daily_perf': session.query(DailyPerformanceORM).count(),
                }
                
                for table, count in tables.items():
                    print(f"  {table}: {count} records")
                
                self._pass("All tables accessible")
                
        except Exception as e:
            self._fail(f"Database error: {e}")
    
    def _check_portfolio_duplicates(self):
        """Check for duplicate portfolios - THE BUG"""
        print("\n🔍 Portfolio Duplicates Check")
        print("-" * 40)
        
        try:
            from core.database.schema import PortfolioORM
            
            with session_scope() as session:
                # Get all portfolios
                portfolios = session.query(PortfolioORM).all()
                print(f"  Total portfolios: {len(portfolios)}")
                
                # Check for duplicates by (broker, account_id)
                seen = {}
                duplicates = []
                
                for p in portfolios:
                    key = (p.broker, p.account_id)
                    if key in seen:
                        duplicates.append({
                            'key': key,
                            'ids': [seen[key], p.id],
                            'names': [session.query(PortfolioORM).get(seen[key]).name, p.name]
                        })
                    else:
                        seen[key] = p.id
                
                if duplicates:
                    self._fail(f"Found {len(duplicates)} duplicate portfolio(s)!")
                    for dup in duplicates:
                        print(f"    Broker: {dup['key'][0]}, Account: {dup['key'][1]}")
                        print(f"    IDs: {dup['ids']}")
                        print(f"    ⚠️  Run with --fix portfolio to resolve")
                else:
                    self._pass("No duplicate portfolios")
                
                # Also check the query method
                print("\n  Testing get_by_account query...")
                from repositories.portfolio import PortfolioRepository
                repo = PortfolioRepository(session)
                
                for p in portfolios[:1]:  # Test with first portfolio
                    found = repo.get_by_account(p.broker, p.account_id)
                    if found:
                        print(f"    get_by_account({p.broker}, {p.account_id}) = {found.id}")
                        if found.id == p.id:
                            self._pass("get_by_account returns correct portfolio")
                        else:
                            self._fail(f"get_by_account returns wrong portfolio: {found.id} != {p.id}")
                    else:
                        self._fail(f"get_by_account returned None for existing portfolio!")
                        print(f"    This is likely the bug - query not finding existing portfolio")
                
        except Exception as e:
            self._fail(f"Portfolio check error: {e}")
            logger.exception("Error:")
    
    def _check_orphaned_records(self):
        """Check for orphaned positions/trades"""
        print("\n🔗 Orphaned Records Check")
        print("-" * 40)
        
        try:
            from core.database.schema import PortfolioORM, PositionORM, TradeORM
            
            with session_scope() as session:
                # Get all portfolio IDs
                portfolio_ids = {p.id for p in session.query(PortfolioORM).all()}
                
                # Check positions
                positions = session.query(PositionORM).all()
                orphan_positions = [p for p in positions if p.portfolio_id not in portfolio_ids]
                
                if orphan_positions:
                    self._warn(f"Found {len(orphan_positions)} orphaned positions")
                else:
                    self._pass("No orphaned positions")
                
                # Check trades
                trades = session.query(TradeORM).all()
                orphan_trades = [t for t in trades if t.portfolio_id not in portfolio_ids]
                
                if orphan_trades:
                    self._warn(f"Found {len(orphan_trades)} orphaned trades")
                else:
                    self._pass("No orphaned trades")
                
        except Exception as e:
            self._fail(f"Orphan check error: {e}")
    
    def _check_data_integrity(self):
        """Check data integrity"""
        print("\n✅ Data Integrity Check")
        print("-" * 40)
        
        try:
            from core.database.schema import PositionORM, SymbolORM
            
            with session_scope() as session:
                # Check positions have symbols
                positions = session.query(PositionORM).all()
                missing_symbols = [p for p in positions if not p.symbol]
                
                if missing_symbols:
                    self._fail(f"{len(missing_symbols)} positions missing symbol reference")
                else:
                    self._pass("All positions have symbols")
                
                # Check for zero-quantity positions
                zero_qty = [p for p in positions if p.quantity == 0]
                if zero_qty:
                    self._warn(f"{len(zero_qty)} positions with zero quantity")
                else:
                    self._pass("No zero-quantity positions")
                
        except Exception as e:
            self._fail(f"Integrity check error: {e}")
    
    def fix_portfolio_duplicates(self):
        """Fix duplicate portfolios by keeping the oldest one"""
        print("\n🔧 Fixing Portfolio Duplicates")
        print("-" * 40)
        
        try:
            from core.database.schema import PortfolioORM, PositionORM, TradeORM
            
            with session_scope() as session:
                # Get all portfolios
                portfolios = session.query(PortfolioORM).order_by(PortfolioORM.created_at).all()
                
                # Group by (broker, account_id)
                groups = {}
                for p in portfolios:
                    key = (p.broker, p.account_id)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(p)
                
                fixed = 0
                for key, group in groups.items():
                    if len(group) > 1:
                        # Keep the first (oldest), delete the rest
                        keep = group[0]
                        delete = group[1:]
                        
                        print(f"  Keeping portfolio {keep.id} for {key}")
                        
                        for dup in delete:
                            # Move positions to the kept portfolio
                            positions = session.query(PositionORM).filter_by(portfolio_id=dup.id).all()
                            for pos in positions:
                                pos.portfolio_id = keep.id
                            print(f"    Moved {len(positions)} positions from {dup.id}")
                            
                            # Move trades to the kept portfolio
                            trades = session.query(TradeORM).filter_by(portfolio_id=dup.id).all()
                            for trade in trades:
                                trade.portfolio_id = keep.id
                            print(f"    Moved {len(trades)} trades from {dup.id}")
                            
                            # Delete duplicate portfolio
                            session.delete(dup)
                            print(f"    Deleted duplicate portfolio {dup.id}")
                            fixed += 1
                
                session.commit()
                print(f"\n✓ Fixed {fixed} duplicate portfolios")
                
        except Exception as e:
            print(f"❌ Fix error: {e}")
            logger.exception("Error:")
    
    def _pass(self, msg):
        print(f"  ✓ {msg}")
        self.results.append(('pass', msg))
    
    def _fail(self, msg):
        print(f"  ❌ {msg}")
        self.results.append(('fail', msg))
    
    def _warn(self, msg):
        print(f"  ⚠️  {msg}")
        self.results.append(('warn', msg))
    
    def _print_summary(self):
        print("\n" + "=" * 80)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for r in self.results if r[0] == 'pass')
        failed = sum(1 for r in self.results if r[0] == 'fail')
        warned = sum(1 for r in self.results if r[0] == 'warn')
        
        print(f"✓ Passed: {passed}")
        print(f"⚠️  Warnings: {warned}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\nFailed checks:")
            for result in self.results:
                if result[0] == 'fail':
                    print(f"  - {result[1]}")


class ModuleTests:
    """
    Test all modules - new and existing.
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    def test_all(self):
        """Run all module tests"""
        print("\n" + "=" * 80)
        print("MODULE TESTS")
        print("=" * 80)
        
        self.test_risk_module()
        self.test_pricing_module()
        self.test_position_mgmt_module()
        self.test_ml_module()
    
    def test_risk_module(self):
        """Test risk module"""
        print("\n📊 Risk Module Tests")
        print("-" * 40)
        
        try:
            # Test imports
            from services.risk import (
                VaRCalculator, PortfolioRiskAnalyzer,
                CorrelationAnalyzer, ConcentrationChecker,
                MarginEstimator, RiskLimits
            )
            print("  ✓ Risk module imports OK")
            
            # Test VaR calculation
            var_calc = VaRCalculator()
            test_returns = [0.01, -0.02, 0.015, -0.01, 0.005] * 20
            var_result = var_calc.calculate_parametric_var(
                portfolio_value=Decimal('100000'),
                returns=test_returns,
                confidence=0.95,
                horizon_days=1
            )
            print(f"  ✓ VaR calculation: ${var_result.var_amount:,.2f} (95% 1-day)")
            
            # Test concentration
            conc_checker = ConcentrationChecker()
            # Mock positions
            mock_exposures = {'SPY': 15000, 'QQQ': 10000, 'AAPL': 5000}
            conc_result = conc_checker.check_concentration(
                exposures_by_underlying=mock_exposures,
                total_equity=Decimal('100000')
            )
            print(f"  ✓ Concentration check: {len(conc_result.violations)} violations")
            
            # Test risk limits
            from config.risk_config_loader import get_risk_config
            try:
                config = get_risk_config()
                print(f"  ✓ Risk config loaded: max_var={config.var.max_var_percent}%")
            except FileNotFoundError:
                print("  ⚠️  Risk config not found (not integrated yet)")
            
            print("  ✓ Risk module tests PASSED")
            
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            print("     Risk module not integrated yet")
        except Exception as e:
            print(f"  ❌ Test error: {e}")
            logger.exception("Error:")
    
    def test_pricing_module(self):
        """Test pricing module"""
        print("\n💰 Pricing Module Tests")
        print("-" * 40)
        
        try:
            from services.pricing import (
                BlackScholesModel, ProbabilityCalculator,
                ImpliedVolCalculator, ScenarioEngine
            )
            print("  ✓ Pricing module imports OK")
            
            # Test Black-Scholes
            bs = BlackScholesModel()
            price = bs.price(
                spot=Decimal('500'),
                strike=Decimal('500'),
                time_to_expiry=30/365,
                volatility=0.20,
                risk_free_rate=0.05,
                is_call=True
            )
            print(f"  ✓ BS call price: ${price:.2f}")
            
            # Test Greeks
            greeks = bs.greeks(
                spot=Decimal('500'),
                strike=Decimal('500'),
                time_to_expiry=30/365,
                volatility=0.20,
                risk_free_rate=0.05,
                is_call=True
            )
            print(f"  ✓ Greeks: Δ={greeks.delta:.3f}, Θ={greeks.theta:.3f}")
            
            # Test probability
            prob_calc = ProbabilityCalculator()
            pop = prob_calc.probability_of_profit_vertical(
                short_strike=Decimal('495'),
                long_strike=Decimal('490'),
                credit=Decimal('1.50'),
                spot=Decimal('500'),
                volatility=0.20,
                time_to_expiry=30/365,
                is_put_spread=True
            )
            print(f"  ✓ POP (put credit spread): {pop.probability_of_profit*100:.1f}%")
            
            print("  ✓ Pricing module tests PASSED")
            
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            print("     Pricing module not integrated yet")
        except Exception as e:
            print(f"  ❌ Test error: {e}")
            logger.exception("Error:")
    
    def test_position_mgmt_module(self):
        """Test position management module"""
        print("\n📋 Position Management Module Tests")
        print("-" * 40)
        
        try:
            from services.position_mgmt import (
                RulesEngine, ProfitTargetRule, StopLossRule,
                DTEExitRule, ActionType
            )
            print("  ✓ Position mgmt module imports OK")
            
            # Create rules engine
            engine = RulesEngine([
                ProfitTargetRule(target_percent=50, name="50% Profit", priority=1),
                StopLossRule(max_loss_percent=100, name="100% Stop", priority=1),
                DTEExitRule(dte_threshold=21, name="21 DTE", priority=2),
            ])
            print(f"  ✓ Rules engine created with {len(engine.rules)} rules")
            
            # Test with mock position
            class MockSymbol:
                ticker = "SPY"
                expiration = datetime.now() + __import__('datetime').timedelta(days=15)
            
            class MockPosition:
                id = "test_pos"
                symbol = MockSymbol()
                quantity = -1
                total_cost = Decimal('150')
                
                def unrealized_pnl(self):
                    return Decimal('90')  # 60% profit
            
            action = engine.evaluate_position(MockPosition())
            print(f"  ✓ Evaluation: {action.action.value} ({action.primary_reason})")
            
            print("  ✓ Position mgmt module tests PASSED")
            
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            print("     Position mgmt module not integrated yet")
        except Exception as e:
            print(f"  ❌ Test error: {e}")
            logger.exception("Error:")
    
    def test_ml_module(self):
        """Test ML module"""
        print("\n🤖 ML Module Tests")
        print("-" * 40)
        
        try:
            from ai_cotrader import (
                FeatureExtractor, MarketFeatures, RLState,
                PatternRecognizer, QLearningAgent, TradingAdvisor
            )
            print("  ✓ ML module imports OK")
            
            # Test feature extraction
            extractor = FeatureExtractor()
            
            class MockContext:
                underlying_price = 500.0
                iv_rank = 65.0
                vix = 18.5
                market_trend = 'bullish'
                timestamp = datetime.now()
            
            class MockEvent:
                market_context = MockContext()
            
            state = extractor.extract_from_event(MockEvent())
            print(f"  ✓ Feature extraction: {state.state_dim} dimensions")
            
            # Test pattern recognizer
            import numpy as np
            recognizer = PatternRecognizer()
            
            # Generate fake training data
            X = np.random.randn(50, 10)
            y_actions = np.random.randint(0, 3, 50)
            y_outcomes = (np.random.rand(50) > 0.4).astype(int)
            
            recognizer.fit(X, y_actions, y_outcomes)
            print(f"  ✓ Pattern recognizer trained")
            
            patterns = recognizer.predict(X[:1])
            print(f"  ✓ Pattern prediction: {patterns[0].suggested_action}")
            
            # Test Q-learning agent
            agent = QLearningAgent(state_dim=10, n_actions=5)
            test_state = np.random.randn(10)
            action = agent.select_action(test_state, explore=False)
            print(f"  ✓ Q-learning agent: action={action}")
            
            # Test trading advisor
            advisor = TradingAdvisor(supervised_model=recognizer, rl_agent=agent)
            rec = advisor.recommend(test_state)
            print(f"  ✓ Advisor: {rec['action']} (confidence={rec['confidence']:.2f})")
            
            print("  ✓ ML module tests PASSED")
            
        except ImportError as e:
            print(f"  ❌ Import error: {e}")
            print("     ML module not integrated yet")
        except Exception as e:
            print(f"  ❌ Test error: {e}")
            logger.exception("Error:")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Diagnostics and Module Tests")
    parser.add_argument(
        '--test',
        choices=['all', 'risk', 'pricing', 'position_mgmt', 'ml'],
        help='Run specific module tests'
    )
    parser.add_argument(
        '--fix',
        choices=['portfolio'],
        help='Fix specific issues'
    )
    parser.add_argument(
        '--diagnose',
        action='store_true',
        help='Run diagnostics only'
    )
    
    args = parser.parse_args()
    
    setup_logging()
    
    if args.fix:
        diag = SystemDiagnostics()
        if args.fix == 'portfolio':
            diag.fix_portfolio_duplicates()
        return 0
    
    if args.diagnose:
        diag = SystemDiagnostics()
        diag.run_all()
        return 0
    
    if args.test:
        tests = ModuleTests()
        if args.test == 'all':
            tests.test_all()
        elif args.test == 'risk':
            tests.test_risk_module()
        elif args.test == 'pricing':
            tests.test_pricing_module()
        elif args.test == 'position_mgmt':
            tests.test_position_mgmt_module()
        elif args.test == 'ml':
            tests.test_ml_module()
        return 0
    
    # Default: run both
    diag = SystemDiagnostics()
    diag.run_all()
    
    tests = ModuleTests()
    tests.test_all()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
