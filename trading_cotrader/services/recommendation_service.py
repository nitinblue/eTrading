"""
Recommendation Service — Orchestrates screeners, recommendations, and acceptance.

Pipeline: Watchlist → Screener → Recommendations → (User review) → WhatIf Trade

Recommendations are first-class objects. They do NOT auto-add to any portfolio.
User must explicitly accept with rationale, at which point a WhatIf trade
is booked via TradeBookingService with source tracking.

Usage:
    from trading_cotrader.services.recommendation_service import RecommendationService
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        svc = RecommendationService(session, broker=broker)
        recs = svc.run_screener('vix', 'My Watchlist')
        svc.accept_recommendation(recs[0].id, notes="Looks good")
"""

from typing import List, Optional, Dict
import logging

from sqlalchemy.orm import Session

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendationStatus
)
from trading_cotrader.core.models.domain import TradeSource
from trading_cotrader.repositories.recommendation import RecommendationRepository
from trading_cotrader.services.watchlist_service import WatchlistService
from trading_cotrader.services.screeners.screener_base import ScreenerBase
from trading_cotrader.services.screeners.vix_regime_screener import VixRegimeScreener
from trading_cotrader.services.screeners.iv_rank_screener import IvRankScreener

logger = logging.getLogger(__name__)

# Registry of available screeners
_SCREENER_REGISTRY = {
    'vix': VixRegimeScreener,
    'iv_rank': IvRankScreener,
}


class RecommendationService:
    """Orchestrates screeners, manages recommendation lifecycle."""

    def __init__(self, session: Session, broker=None):
        """
        Args:
            session: SQLAlchemy session.
            broker: TastytradeAdapter (authenticated). None = mock mode.
        """
        self.session = session
        self.broker = broker
        self.rec_repo = RecommendationRepository(session)
        self.watchlist_svc = WatchlistService(session, broker=broker)

    def run_screener(
        self,
        screener_name: str,
        watchlist_name: str,
        **screener_kwargs,
    ) -> List[Recommendation]:
        """
        Run a screener against a watchlist and persist recommendations.

        Args:
            screener_name: Key in screener registry ('vix', 'iv_rank').
            watchlist_name: Name of watchlist to screen.
            **screener_kwargs: Extra kwargs passed to screener constructor.

        Returns:
            List of Recommendation objects (PENDING status, saved to DB).
        """
        # Get screener
        screener_cls = _SCREENER_REGISTRY.get(screener_name)
        if not screener_cls:
            logger.error(f"Unknown screener: {screener_name}. Available: {list(_SCREENER_REGISTRY.keys())}")
            return []

        screener = screener_cls(broker=self.broker, **screener_kwargs)

        # Get watchlist
        watchlist = self.watchlist_svc.get_or_fetch(watchlist_name)
        if not watchlist:
            logger.error(f"Watchlist '{watchlist_name}' not found")
            return []

        logger.info(
            f"Running {screener.name} on '{watchlist_name}' "
            f"({len(watchlist.symbols)} symbols)"
        )

        # Run screener
        recommendations = screener.screen(watchlist.symbols)

        # Auto-suggest portfolio for each recommendation
        self._auto_suggest_portfolios(recommendations)

        # Persist to DB
        saved = []
        for rec in recommendations:
            created = self.rec_repo.create_from_domain(rec)
            if created:
                saved.append(created)

        logger.info(f"Saved {len(saved)} recommendations to DB")
        return saved

    def get_pending(self) -> List[Recommendation]:
        """Get all pending recommendations."""
        return self.rec_repo.get_pending()

    def get_by_id(self, rec_id: str) -> Optional[Recommendation]:
        """Get a recommendation by ID."""
        orm = self.rec_repo.get_by_id(rec_id)
        if orm:
            return self.rec_repo.to_domain(orm)
        return None

    def accept_recommendation(
        self,
        rec_id: str,
        notes: str = "",
        portfolio_name: Optional[str] = None,
    ) -> Dict:
        """
        Accept a recommendation and book a WhatIf trade.

        Args:
            rec_id: Recommendation ID.
            notes: User's rationale for accepting.
            portfolio_name: Override portfolio (uses suggested if None).

        Returns:
            Dict with 'success', 'trade_id', 'error'.
        """
        rec = self.get_by_id(rec_id)
        if not rec:
            return {'success': False, 'error': f'Recommendation {rec_id} not found'}

        if rec.status != RecommendationStatus.PENDING:
            return {'success': False, 'error': f'Recommendation is {rec.status.value}, not pending'}

        # Determine portfolio
        target_portfolio = portfolio_name or rec.suggested_portfolio

        # Book the trade via TradeBookingService
        try:
            from trading_cotrader.services.trade_booking_service import (
                TradeBookingService, LegInput
            )

            # Convert recommendation legs to LegInputs
            leg_inputs = [
                LegInput(
                    streamer_symbol=leg.streamer_symbol,
                    quantity=leg.quantity,
                )
                for leg in rec.legs
            ]

            # Resolve TradeSource
            try:
                trade_source = TradeSource(rec.source)
            except ValueError:
                trade_source = TradeSource.MANUAL

            service = TradeBookingService(broker=self.broker)
            result = service.book_whatif_trade(
                underlying=rec.underlying,
                strategy_type=rec.strategy_type,
                legs=leg_inputs,
                notes=notes or rec.rationale,
                rationale=notes or rec.rationale,
                confidence=rec.confidence,
                portfolio_name=target_portfolio,
                trade_source=trade_source,
                recommendation_id=rec.id,
            )

            if result.success:
                # Update recommendation status
                rec.accept(
                    notes=notes,
                    trade_id=result.trade_id,
                    portfolio_name=target_portfolio or '',
                )
                self.rec_repo.update_from_domain(rec)

                logger.info(
                    f"Accepted recommendation {rec_id[:8]}... → "
                    f"Trade {result.trade_id[:8]}..."
                )
                return {
                    'success': True,
                    'trade_id': result.trade_id,
                    'portfolio': target_portfolio,
                }
            else:
                return {'success': False, 'error': result.error}

        except Exception as e:
            logger.error(f"Failed to accept recommendation {rec_id}: {e}")
            return {'success': False, 'error': str(e)}

    def reject_recommendation(self, rec_id: str, reason: str = "") -> bool:
        """Reject a recommendation."""
        rec = self.get_by_id(rec_id)
        if not rec:
            return False

        if rec.status != RecommendationStatus.PENDING:
            return False

        rec.reject(reason=reason)
        self.rec_repo.update_from_domain(rec)
        logger.info(f"Rejected recommendation {rec_id[:8]}...")
        return True

    def expire_old_recommendations(self, max_age_hours: int = 24) -> int:
        """Expire recommendations older than max_age_hours."""
        count = self.rec_repo.expire_old(max_age_hours)
        if count > 0:
            logger.info(f"Expired {count} old recommendations")
        return count

    def _auto_suggest_portfolios(self, recommendations: List[Recommendation]) -> None:
        """Auto-suggest the best portfolio for each recommendation."""
        try:
            from trading_cotrader.services.portfolio_manager import PortfolioManager
            pm = PortfolioManager(self.session)

            for rec in recommendations:
                suggested = pm.get_portfolio_for_strategy(rec.strategy_type)
                if suggested:
                    rec.suggested_portfolio = suggested
        except Exception as e:
            logger.warning(f"Failed to auto-suggest portfolios: {e}")
