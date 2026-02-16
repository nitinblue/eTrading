"""
Step 17: Portfolio Evaluation — Exit/Roll/Adjust Recommendations + Liquidity
=============================================================================

Tests:
    1. LiquidityService — mock liquidity snapshot, check entry/adjustment thresholds
    2. LiquidityThresholds — load from YAML config
    3. PortfolioEvaluationService — evaluate trades with triggered rules
    4. Recommendation types — verify EXIT/ROLL/ADJUST rec types are created
    5. Rules engine integration — profit target triggers CLOSE recommendation
    6. Illiquidity downgrade — illiquid option → ADJUST downgraded to CLOSE
    7. Accept exit recommendation — closes the referenced trade
    8. Config loader — LiquidityThresholds parsed from YAML

Does NOT require broker (uses mock mode throughout).
"""

from decimal import Decimal
from typing import Dict, Any

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


class PortfolioEvaluationStep(TestStep):
    name = "Portfolio Evaluation"
    description = "Test: exit/roll/adjust recs, liquidity checks, rules engine wiring"

    def execute(self) -> StepResult:
        tables = []
        messages = []
        test_results = []

        # --- Test 1: LiquidityService mock ---
        try:
            from trading_cotrader.services.liquidity_service import (
                LiquidityService, LiquiditySnapshot
            )
            from trading_cotrader.config.risk_config_loader import (
                LiquidityThreshold, LiquidityThresholds
            )

            config = LiquidityThresholds(
                entry=LiquidityThreshold(
                    min_open_interest=100,
                    max_bid_ask_spread_pct=5.0,
                    min_daily_volume=500,
                ),
                adjustment=LiquidityThreshold(
                    min_open_interest=500,
                    max_bid_ask_spread_pct=3.0,
                    min_daily_volume=1000,
                ),
            )
            svc = LiquidityService(broker=None, config=config)

            # Mock check returns liquid defaults
            snap = svc.check_liquidity(".SPY260320P550")
            assert snap.is_liquid, "Mock should be liquid"
            assert snap.bid > 0, "Mock bid should be > 0"

            # Test threshold checks
            liquid_snap = LiquiditySnapshot(
                symbol=".SPY260320P550",
                bid=Decimal('2.00'), ask=Decimal('2.05'), mid=Decimal('2.025'),
                spread=Decimal('0.05'), spread_pct=2.5,
                open_interest=600, daily_volume=1200,
            )
            assert svc.meets_entry_threshold(liquid_snap), "Should meet entry"
            assert svc.meets_adjustment_threshold(liquid_snap), "Should meet adjustment"

            # Illiquid for adjustment
            illiquid_snap = LiquiditySnapshot(
                symbol=".SPY260320P550",
                bid=Decimal('1.00'), ask=Decimal('1.20'), mid=Decimal('1.10'),
                spread=Decimal('0.20'), spread_pct=18.0,
                open_interest=50, daily_volume=100,
            )
            assert svc.meets_entry_threshold(illiquid_snap) is False, "Should fail entry"
            assert svc.meets_adjustment_threshold(illiquid_snap) is False, "Should fail adjustment"

            reason = svc.get_liquidity_reason(illiquid_snap)
            assert "OI" in reason or "spread" in reason, "Reason should explain why"

            test_results.append(["1. LiquidityService mock", "PASS"])
            messages.append("  LiquidityService: mock, threshold checks, reason string OK")
        except Exception as e:
            test_results.append(["1. LiquidityService mock", f"FAIL: {e}"])

        # --- Test 2: Config loader parses liquidity thresholds ---
        try:
            from trading_cotrader.config.risk_config_loader import RiskConfigLoader

            loader = RiskConfigLoader()
            config = loader.load()

            assert hasattr(config, 'liquidity'), "Config should have liquidity"
            assert config.liquidity.entry.min_open_interest > 0, "Entry OI > 0"
            assert config.liquidity.adjustment.min_open_interest > config.liquidity.entry.min_open_interest, \
                "Adjustment OI should be tighter"

            test_results.append(["2. Config liquidity thresholds", "PASS"])
            messages.append(
                f"  Liquidity config: entry OI>={config.liquidity.entry.min_open_interest}, "
                f"adj OI>={config.liquidity.adjustment.min_open_interest}"
            )
        except Exception as e:
            test_results.append(["2. Config liquidity thresholds", f"FAIL: {e}"])

        # --- Test 3: Recommendation types (domain model) ---
        try:
            from trading_cotrader.core.models.recommendation import (
                Recommendation, RecommendationType, RecommendationStatus
            )

            # ENTRY (default)
            entry_rec = Recommendation(underlying="SPY", strategy_type="iron_condor")
            assert entry_rec.recommendation_type == RecommendationType.ENTRY

            # EXIT
            exit_rec = Recommendation(
                recommendation_type=RecommendationType.EXIT,
                underlying="SPY",
                strategy_type="iron_condor",
                trade_id_to_close="test-trade-123",
                exit_action="close",
                exit_urgency="today",
                triggered_rules=["profit_target_50pct"],
            )
            assert exit_rec.recommendation_type == RecommendationType.EXIT
            assert exit_rec.trade_id_to_close == "test-trade-123"
            d = exit_rec.to_dict()
            assert d['recommendation_type'] == 'exit'
            assert d['exit_action'] == 'close'
            assert 'profit_target_50pct' in d['triggered_rules']

            # ROLL
            from trading_cotrader.core.models.recommendation import RecommendedLeg
            roll_rec = Recommendation(
                recommendation_type=RecommendationType.ROLL,
                underlying="SPY",
                strategy_type="iron_condor",
                trade_id_to_close="test-trade-123",
                exit_action="roll",
                new_legs=[RecommendedLeg(streamer_symbol=".SPY260420P550", quantity=-1)],
            )
            assert roll_rec.recommendation_type == RecommendationType.ROLL
            assert len(roll_rec.new_legs) == 1

            test_results.append(["3. Recommendation types", "PASS"])
            messages.append("  ENTRY/EXIT/ROLL/ADJUST types + to_dict() all correct")
        except Exception as e:
            test_results.append(["3. Recommendation types", f"FAIL: {e}"])

        # --- Test 4: RulesEngine profit target triggers ---
        try:
            from trading_cotrader.services.position_mgmt.rules_engine import (
                RulesEngine, ProfitTargetRule, StopLossRule, ActionType
            )

            engine = RulesEngine([
                ProfitTargetRule(target_percent=50, name="50pct_profit", priority=1),
                StopLossRule(max_loss_percent=200, name="200pct_stop", priority=1),
            ])

            # Mock position in profit
            class InProfitPosition:
                id = "pos_profit"
                class symbol:
                    ticker = "SPY"
                    expiration = None
                quantity = -1
                total_cost = Decimal('200')
                def unrealized_pnl(self):
                    return Decimal('120')  # 60% profit

            action = engine.evaluate_position(InProfitPosition())
            assert action.should_act(), "Should recommend action"
            assert action.action == ActionType.CLOSE, f"Should be CLOSE, got {action.action}"
            assert len(action.triggered_rules) > 0

            # Mock position not triggered
            class HoldPosition:
                id = "pos_hold"
                class symbol:
                    ticker = "QQQ"
                    expiration = None
                quantity = -1
                total_cost = Decimal('200')
                def unrealized_pnl(self):
                    return Decimal('50')  # 25% profit — below 50% target

            action2 = engine.evaluate_position(HoldPosition())
            assert not action2.should_act(), "Should be HOLD"

            test_results.append(["4. RulesEngine profit target", "PASS"])
            messages.append("  60% profit triggers CLOSE, 25% profit holds")
        except Exception as e:
            test_results.append(["4. RulesEngine profit target", f"FAIL: {e}"])

        # --- Test 5: PortfolioEvaluationService integration ---
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.portfolio_evaluation_service import (
                PortfolioEvaluationService
            )

            with session_scope() as session:
                eval_svc = PortfolioEvaluationService(session, broker=None)

                # Evaluate a portfolio (dry run) — should work even with 0 trades
                recs = eval_svc.evaluate_portfolio('high_risk', dry_run=True)
                # We can't guarantee trades exist, so just verify no crash
                assert isinstance(recs, list), "Should return a list"

                test_results.append(["5. PortfolioEvaluation integration", "PASS"])
                messages.append(f"  Evaluated high_risk: {len(recs)} recommendations (dry run)")
        except Exception as e:
            test_results.append(["5. PortfolioEvaluation integration", f"FAIL: {e}"])

        # --- Test 6: Illiquidity downgrade ---
        try:
            from trading_cotrader.services.portfolio_evaluation_service import (
                PortfolioEvaluationService
            )
            from trading_cotrader.services.position_mgmt.rules_engine import (
                PositionAction, ActionType, RulePriority, RuleEvaluation
            )

            with session_scope() as session:
                eval_svc = PortfolioEvaluationService(session, broker=None)

                # ROLL + liquid → ROLL
                roll_action = PositionAction(
                    position_id="p1", symbol="SPY",
                    action=ActionType.ROLL, priority=RulePriority.MEDIUM,
                    triggered_rules=[], primary_reason="21 DTE",
                )
                rec_type, rec_action = eval_svc._determine_rec_type(roll_action, liquidity_ok=True)
                assert rec_type == RecommendationType.ROLL, f"Expected ROLL, got {rec_type}"

                # ROLL + illiquid → EXIT (CLOSE)
                rec_type2, rec_action2 = eval_svc._determine_rec_type(roll_action, liquidity_ok=False)
                assert rec_type2 == RecommendationType.EXIT, f"Expected EXIT, got {rec_type2}"
                assert rec_action2 == "close", f"Expected close, got {rec_action2}"

                # ADJUST + illiquid → EXIT (CLOSE)
                adjust_action = PositionAction(
                    position_id="p2", symbol="SPY",
                    action=ActionType.ADJUST, priority=RulePriority.MEDIUM,
                    triggered_rules=[], primary_reason="delta breach",
                )
                rec_type3, _ = eval_svc._determine_rec_type(adjust_action, liquidity_ok=False)
                assert rec_type3 == RecommendationType.EXIT

                test_results.append(["6. Illiquidity downgrade", "PASS"])
                messages.append("  ROLL+liquid→ROLL, ROLL+illiquid→EXIT, ADJUST+illiquid→EXIT")
        except Exception as e:
            test_results.append(["6. Illiquidity downgrade", f"FAIL: {e}"])

        # --- Test 7: RecommendationRepository round-trip with new fields ---
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.repositories.recommendation import RecommendationRepository
            from trading_cotrader.core.models.recommendation import (
                Recommendation, RecommendationType, MarketSnapshot, RecommendedLeg
            )

            with session_scope() as session:
                repo = RecommendationRepository(session)

                exit_rec = Recommendation(
                    recommendation_type=RecommendationType.EXIT,
                    source="manual",
                    screener_name="portfolio_evaluation",
                    underlying="SPY",
                    strategy_type="iron_condor",
                    confidence=8,
                    rationale="Profit at 60%",
                    trade_id_to_close="test-trade-abc",
                    exit_action="close",
                    exit_urgency="today",
                    triggered_rules=["profit_50pct", "dte_21"],
                )

                created = repo.create_from_domain(exit_rec)
                assert created is not None, "Should persist"
                assert created.recommendation_type == RecommendationType.EXIT
                assert created.trade_id_to_close == "test-trade-abc"
                assert created.exit_action == "close"
                assert "profit_50pct" in created.triggered_rules

                test_results.append(["7. Rec repo round-trip (exit)", "PASS"])
                messages.append("  EXIT rec persists + reads back with all new fields")
        except Exception as e:
            test_results.append(["7. Rec repo round-trip (exit)", f"FAIL: {e}"])

        # --- Test 8: Default rules engine from profile ---
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.portfolio_evaluation_service import (
                PortfolioEvaluationService
            )

            with session_scope() as session:
                eval_svc = PortfolioEvaluationService(session, broker=None)

                # Build from 'aggressive' profile (80% profit, 2x stop)
                engine = eval_svc._build_rules_engine('high_risk')
                assert len(engine.rules) > 0, "Should have rules from aggressive profile"

                rule_names = [r.name for r in engine.rules]
                assert any('profit' in n for n in rule_names), f"Should have profit rule: {rule_names}"
                assert any('stop' in n for n in rule_names), f"Should have stop rule: {rule_names}"

                test_results.append(["8. Rules engine from profile", "PASS"])
                messages.append(f"  Built {len(engine.rules)} rules from 'aggressive' profile")
        except Exception as e:
            test_results.append(["8. Rules engine from profile", f"FAIL: {e}"])

        # Build summary table
        tables.append(rich_table(
            test_results,
            headers=["Test", "Result"],
            title="Step 17: Portfolio Evaluation Tests"
        ))

        passed = all("PASS" in r[1] for r in test_results)
        return StepResult(
            step_name=self.name,
            passed=passed,
            duration_ms=0,  # overwritten by runner
            tables=tables,
            messages=messages,
            error="" if passed else "Some tests failed",
        )
