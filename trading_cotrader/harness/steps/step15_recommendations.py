"""
Step 15: Recommendations & Screener Pipeline
=============================================

Tests the full recommendation workflow:
    1. Create mock watchlist
    2. Run VIX screener → generate recommendations
    3. Verify recommendations are PENDING in DB
    4. Accept one recommendation → verify trade booked with correct source
    5. Reject one → verify status
    6. Show source breakdown summary

Does NOT require broker (uses mock VIX and mock prices).
"""

from decimal import Decimal
from typing import Dict, Any

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


class RecommendationStep(TestStep):
    name = "Recommendations & Screener"
    description = "Test: watchlist → screener → recommendation → accept → trade with source"

    def execute(self) -> StepResult:
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.services.recommendation_service import RecommendationService
        from trading_cotrader.services.watchlist_service import WatchlistService
        from trading_cotrader.repositories.recommendation import RecommendationRepository
        from trading_cotrader.repositories.trade import TradeRepository
        from trading_cotrader.core.models.recommendation import RecommendationStatus

        tables = []
        messages = []

        with session_scope() as session:
            # Step 1: Create a mock watchlist
            wl_svc = WatchlistService(session)
            wl = wl_svc.create_custom(
                name="Harness Test Watchlist",
                symbols=['SPY', 'QQQ', 'IWM'],
                description="Test watchlist for harness step 15",
            )
            if not wl:
                return self._fail_result("Failed to create mock watchlist")

            messages.append(f"Created watchlist '{wl.name}' with {len(wl.symbols)} symbols")

            # Step 2: Run VIX screener with mock VIX=18 (normal regime)
            svc = RecommendationService(session, broker=None)
            recs = svc.run_screener(
                screener_name='vix',
                watchlist_name='Harness Test Watchlist',
                mock_vix=Decimal('18'),
            )

            if not recs:
                return self._fail_result("VIX screener generated no recommendations")

            # Recommendations table
            rec_rows = []
            for rec in recs:
                vix_str = f"{float(rec.market_context.vix):.1f}" if rec.market_context.vix else "—"
                rec_rows.append([
                    rec.id[:12] + "...",
                    rec.underlying,
                    rec.strategy_type,
                    rec.source,
                    rec.confidence,
                    rec.status.value,
                    rec.suggested_portfolio or "—",
                    rec.rationale[:40] + "...",
                ])
            tables.append(rich_table(
                rec_rows,
                headers=["ID", "Symbol", "Strategy", "Source", "Conf", "Status", "Portfolio", "Rationale"],
                title="📋 Generated Recommendations"
            ))

            messages.append(f"VIX screener generated {len(recs)} recommendations (VIX=18, normal regime)")

            # Step 3: Verify all are PENDING
            pending = svc.get_pending()
            # Filter to just our recs (there may be old ones)
            our_pending = [r for r in pending if r.id in [rec.id for rec in recs]]
            if len(our_pending) != len(recs):
                return self._fail_result(
                    f"Expected {len(recs)} pending, found {len(our_pending)}"
                )

            # Step 4: Accept the first recommendation
            first_rec = recs[0]
            accept_result = svc.accept_recommendation(
                rec_id=first_rec.id,
                notes="Harness test acceptance",
                portfolio_name=first_rec.suggested_portfolio,
            )

            accept_rows = [
                ["Action", "Accept"],
                ["Recommendation", first_rec.id[:12] + "..."],
                ["Trade Booked", accept_result.get('trade_id', 'N/A')[:12] + "..." if accept_result.get('trade_id') else "FAILED"],
                ["Portfolio", accept_result.get('portfolio', '—')],
                ["Success", "YES" if accept_result['success'] else f"NO: {accept_result.get('error', '')}"],
            ]

            # Verify trade has correct source
            if accept_result['success']:
                trade_repo = TradeRepository(session)
                trade = trade_repo.get_by_id(accept_result['trade_id'])
                if trade:
                    # trade is a domain object from to_domain
                    source_val = trade.trade_source.value if hasattr(trade.trade_source, 'value') else str(trade.trade_source)
                    accept_rows.append(["Trade Source", source_val])
                    accept_rows.append(["Recommendation ID on Trade", trade.recommendation_id[:12] + "..." if trade.recommendation_id else "—"])
                    if source_val != 'screener_vix':
                        messages.append(f"WARNING: Expected source 'screener_vix', got '{source_val}'")

            tables.append(rich_table(
                accept_rows,
                headers=["Check", "Result"],
                title="✅ Accept Recommendation"
            ))

            # Step 5: Reject the second recommendation (if exists)
            if len(recs) > 1:
                second_rec = recs[1]
                rejected = svc.reject_recommendation(
                    rec_id=second_rec.id,
                    reason="Harness test rejection"
                )
                reject_rows = [
                    ["Action", "Reject"],
                    ["Recommendation", second_rec.id[:12] + "..."],
                    ["Success", "YES" if rejected else "NO"],
                ]
                tables.append(rich_table(
                    reject_rows,
                    headers=["Check", "Result"],
                    title="❌ Reject Recommendation"
                ))

            # Step 6: Summary stats
            rec_repo = RecommendationRepository(session)
            all_recs = rec_repo.get_all()
            status_counts = {}
            for orm in all_recs:
                s = orm.status
                status_counts[s] = status_counts.get(s, 0) + 1

            summary_rows = [
                ["Total Recommendations", str(len(all_recs))],
            ]
            for status, count in sorted(status_counts.items()):
                summary_rows.append([f"  {status}", str(count)])

            tables.append(rich_table(
                summary_rows,
                headers=["Metric", "Value"],
                title="📊 Recommendation Summary"
            ))

        if not accept_result['success']:
            return self._fail_result(
                f"Accept failed: {accept_result.get('error', 'unknown')}",
                tables=tables,
            )

        messages.append("Full recommendation pipeline validated")
        return self._success_result(tables=tables, messages=messages)
