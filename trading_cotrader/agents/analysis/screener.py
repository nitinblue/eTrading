"""
Screener Agent — Runs screeners for today's cadences and generates recommendations.

Wraps RecommendationService. Reads cadences from context and runs
appropriate screeners against the watchlist.

Enriches context with:
    - pending_recommendations: list of recommendation dicts
"""

from typing import List
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)

# Map cadence names to screener names
_CADENCE_TO_SCREENERS = {
    '0dte': ['vix'],
    'weekly': ['vix', 'iv_rank'],
    'monthly': ['vix', 'iv_rank'],
    'leaps': ['leaps'],
}


class ScreenerAgent:
    """Runs screeners based on today's cadences."""

    name = "screener"

    def __init__(self, broker=None):
        self.broker = broker

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Run screeners for today's cadences.

        Reads 'cadences' and 'watchlist_symbols' from context.
        Writes 'pending_recommendations' to context.
        """
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.recommendation_service import RecommendationService
            from trading_cotrader.services.macro_context_service import MacroOverride

            cadences = context.get('cadences', [])
            symbols = context.get('watchlist_symbols', ['SPY', 'QQQ', 'IWM'])
            macro_data = context.get('macro_assessment', {})

            # Determine which screeners to run based on cadences
            screener_names = set()
            for cadence in cadences:
                for s in _CADENCE_TO_SCREENERS.get(cadence, []):
                    screener_names.add(s)

            if not screener_names:
                context['pending_recommendations'] = []
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.COMPLETED,
                    data={'recommendation_count': 0},
                    messages=["No screeners to run for today's cadences"],
                )

            all_recs = []
            messages = []

            with session_scope() as session:
                svc = RecommendationService(session, broker=self.broker)

                # Create ad-hoc watchlist name
                watchlist_name = f"workflow_{','.join(symbols)}"

                # Ensure watchlist exists
                from trading_cotrader.services.watchlist_service import WatchlistService
                ws = WatchlistService(session, broker=self.broker)
                try:
                    ws.create_custom(watchlist_name, symbols)
                except Exception:
                    pass  # already exists

                for screener_name in sorted(screener_names):
                    try:
                        recs = svc.run_screener(
                            screener_name=screener_name,
                            watchlist_name=watchlist_name,
                        )
                        all_recs.extend(recs)
                        messages.append(f"{screener_name}: {len(recs)} recs")
                    except Exception as e:
                        logger.warning(f"Screener {screener_name} failed: {e}")
                        messages.append(f"{screener_name}: FAILED ({e})")

            # Convert to serializable dicts
            rec_dicts = []
            for rec in all_recs:
                rec_dicts.append({
                    'id': rec.id,
                    'type': rec.recommendation_type.value if hasattr(rec.recommendation_type, 'value') else str(rec.recommendation_type),
                    'underlying': rec.underlying,
                    'strategy_type': rec.strategy_type,
                    'confidence': rec.confidence,
                    'rationale': rec.rationale,
                    'source': rec.source,
                    'suggested_portfolio': rec.suggested_portfolio,
                })

            context['pending_recommendations'] = rec_dicts

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'recommendation_count': len(rec_dicts)},
                messages=messages or ["Screeners complete"],
            )

        except Exception as e:
            logger.error(f"ScreenerAgent failed: {e}")
            context['pending_recommendations'] = []
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Screener error: {e}"],
            )
