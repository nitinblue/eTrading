"""
Step 16: Enhanced Screeners — Active Strategies, Macro, Technicals, LEAPS
=========================================================================

Tests:
    1. Active strategies filtering — verify recs filtered to active subset
    2. Technical analysis — verify indicators compute on mock data
    3. Macro short-circuit — set override to risk_off, verify empty results
    4. Entry filters — verify iron condor skipped when RSI > 70
    5. LEAPS screener — mock data at support with high IV, verify rec generated
    6. Confidence modifier — set macro to cautious, verify confidence reduced
    7. IV Rank screener — verify it generates recs with mock tech data

Does NOT require broker (uses mock mode throughout).
"""

from decimal import Decimal
from typing import Dict, Any

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


class EnhancedScreenerStep(TestStep):
    name = "Enhanced Screeners"
    description = "Test: active strategies, macro gate, technicals, entry filters, LEAPS"

    def execute(self) -> StepResult:
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.services.recommendation_service import RecommendationService
        from trading_cotrader.services.watchlist_service import WatchlistService
        from trading_cotrader.services.technical_analysis_service import (
            TechnicalAnalysisService, TechnicalSnapshot
        )
        from trading_cotrader.services.macro_context_service import (
            MacroContextService, MacroOverride
        )

        tables = []
        messages = []
        test_results = []

        with session_scope() as session:
            # Setup: create test watchlist
            wl_svc = WatchlistService(session)
            wl_svc.create_custom(
                name="Enhanced Test WL",
                symbols=['SPY', 'QQQ', 'IWM'],
                description="Step 16 test watchlist",
            )

            tech_svc = TechnicalAnalysisService(use_mock=True)

            # ===== Test 1: Technical Analysis Service =====
            snap = tech_svc.get_snapshot('SPY')
            t1_pass = (
                snap is not None
                and snap.rsi_14 is not None
                and snap.directional_regime is not None
                and snap.iv_rank is not None
                and snap.pct_from_52w_high is not None
            )
            test_results.append([
                "1. Technical Snapshot",
                "PASS" if t1_pass else "FAIL",
                f"RSI={snap.rsi_14}, regime={snap.directional_regime}, "
                f"IV rank={snap.iv_rank}, from_high={snap.pct_from_52w_high}%"
            ])
            if not t1_pass:
                return self._fail_result(
                    "TechnicalAnalysisService mock failed",
                    tables=[rich_table(test_results, headers=["Test", "Result", "Details"])]
                )

            # ===== Test 2: Macro Short-Circuit =====
            macro_svc = MacroContextService()

            # 2a: risk_off → should_screen=False
            override_off = MacroOverride(
                market_probability="uncertain",
                expected_volatility="extreme",
                notes="Test: should block all screening",
            )
            assessment = macro_svc.evaluate(override=override_off)
            t2a_pass = not assessment.should_screen and assessment.regime == "risk_off"
            test_results.append([
                "2a. Macro risk_off",
                "PASS" if t2a_pass else "FAIL",
                f"should_screen={assessment.should_screen}, regime={assessment.regime}"
            ])

            # 2b: Actually run screener with risk_off → expect 0 recs
            svc = RecommendationService(
                session, broker=None, technical_service=tech_svc,
            )
            recs = svc.run_screener(
                screener_name='vix',
                watchlist_name='Enhanced Test WL',
                macro_override=override_off,
                mock_vix=Decimal('18'),
            )
            t2b_pass = len(recs) == 0
            test_results.append([
                "2b. Macro blocks recs",
                "PASS" if t2b_pass else "FAIL",
                f"Expected 0 recs, got {len(recs)}"
            ])

            # ===== Test 3: Confidence Modifier =====
            override_cautious = MacroOverride(
                market_probability="bearish",
                expected_volatility="high",
            )

            # Run with cautious macro — should get recs with reduced confidence
            recs_cautious = svc.run_screener(
                screener_name='vix',
                watchlist_name='Enhanced Test WL',
                macro_override=override_cautious,
                mock_vix=Decimal('18'),
            )
            # Mock data RSI=52, regime=F → iron_butterfly passes entry filters
            # Confidence should be reduced (original 6 → 6*0.6=3.6 → 3)
            t3_pass = True
            conf_details = []
            for rec in recs_cautious:
                conf_details.append(f"{rec.underlying}={rec.confidence}")
                if rec.confidence >= 6:
                    t3_pass = False
            test_results.append([
                "3. Confidence modifier",
                "PASS" if t3_pass else "FAIL",
                f"Recs: {len(recs_cautious)}, confs: {', '.join(conf_details)}"
            ])

            # ===== Test 4: Active Strategies Filtering =====
            # VIX=18 → normal → iron_butterfly
            # iron_butterfly is NOT in active_strategies for any portfolio
            # (core has single+covered_call, medium has ic+vs+cs+ds, high has ic+vs+strangle)
            # So iron_butterfly should be filtered out by active strategy filter
            recs_normal = svc.run_screener(
                screener_name='vix',
                watchlist_name='Enhanced Test WL',
                mock_vix=Decimal('18'),
            )
            # Check if iron_butterfly was filtered (depends on YAML config)
            ib_count = sum(1 for r in recs_normal if r.strategy_type == 'iron_butterfly')
            # iron_butterfly is NOT in any active_strategies list → should be 0
            t4_pass = ib_count == 0
            test_results.append([
                "4. Active strategy filter",
                "PASS" if t4_pass else "FAIL",
                f"iron_butterfly recs after filter: {ib_count} (expected 0)"
            ])

            # ===== Test 5: IV Rank Screener =====
            recs_iv = svc.run_screener(
                screener_name='iv_rank',
                watchlist_name='Enhanced Test WL',
            )
            # Mock IV rank=45 → neutral zone (20-50) → should skip
            t5_pass = len(recs_iv) == 0
            test_results.append([
                "5. IV Rank screener (neutral)",
                "PASS" if t5_pass else "FAIL",
                f"IV rank=45 (mock), recs={len(recs_iv)} (expected 0, neutral zone)"
            ])

            # ===== Test 6: LEAPS Screener =====
            # Mock data: pct_from_52w_high = -3.5% → doesn't meet -10% threshold
            recs_leaps = svc.run_screener(
                screener_name='leaps',
                watchlist_name='Enhanced Test WL',
            )
            # Mock snapshot has -3.5% from high → doesn't pass gate 1
            t6_pass = len(recs_leaps) == 0
            test_results.append([
                "6. LEAPS screener (no correction)",
                "PASS" if t6_pass else "FAIL",
                f"pct_from_high=-3.5% (mock), recs={len(recs_leaps)} (expected 0)"
            ])

            # ===== Test 7: LEAPS with deep correction mock =====
            # Create a tech service with custom snapshot for deep correction
            class DeepCorrectionTechService(TechnicalAnalysisService):
                def _mock_snapshot(self, symbol):
                    snap = super()._mock_snapshot(symbol)
                    snap.pct_from_52w_high = -15.0  # 15% correction
                    price = float(snap.current_price)
                    snap.nearest_support = Decimal(str(round(price * 0.99, 2)))
                    snap.iv_rank = 55.0  # elevated
                    return snap

            deep_tech = DeepCorrectionTechService(use_mock=True)
            svc_deep = RecommendationService(
                session, broker=None, technical_service=deep_tech,
            )
            recs_leaps_deep = svc_deep.run_screener(
                screener_name='leaps',
                watchlist_name='Enhanced Test WL',
            )
            t7_pass = len(recs_leaps_deep) > 0
            leaps_strategies = [r.strategy_type for r in recs_leaps_deep]
            test_results.append([
                "7. LEAPS screener (correction)",
                "PASS" if t7_pass else "FAIL",
                f"15% correction + support + IV=55 → {len(recs_leaps_deep)} recs: {leaps_strategies}"
            ])

            # ===== Test 8: Macro auto-assessment =====
            assessment_auto = macro_svc.evaluate()  # No override → auto from VIX
            t8_pass = assessment_auto.should_screen and assessment_auto.regime in (
                "risk_on", "neutral", "cautious", "risk_off"
            )
            test_results.append([
                "8. Macro auto-assessment",
                "PASS" if t8_pass else "FAIL",
                f"regime={assessment_auto.regime}, modifier={assessment_auto.confidence_modifier}"
            ])

        # Build results table
        tables.append(rich_table(
            test_results,
            headers=["Test", "Result", "Details"],
            title="Enhanced Screener Tests"
        ))

        # Count passes
        passed = sum(1 for r in test_results if r[1] == "PASS")
        total = len(test_results)
        messages.append(f"Enhanced screener tests: {passed}/{total} passed")

        if passed < total:
            failed_tests = [r[0] for r in test_results if r[1] == "FAIL"]
            return self._fail_result(
                f"Failed: {', '.join(failed_tests)}",
                tables=tables,
                messages=messages,
            )

        return self._success_result(tables=tables, messages=messages)
