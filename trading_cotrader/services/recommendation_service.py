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
    Recommendation, RecommendationStatus, RecommendationType
)
from trading_cotrader.core.models.domain import TradeSource
from trading_cotrader.repositories.recommendation import RecommendationRepository
from trading_cotrader.services.watchlist_service import WatchlistService
from trading_cotrader.services.screeners.screener_base import ScreenerBase
from trading_cotrader.services.screeners.vix_regime_screener import VixRegimeScreener
from trading_cotrader.services.screeners.iv_rank_screener import IvRankScreener
from trading_cotrader.services.screeners.leaps_entry_screener import LeapsEntryScreener
from trading_cotrader.services.macro_context_service import (
    MacroContextService, MacroOverride, MacroAssessment
)

logger = logging.getLogger(__name__)

# Registry of available screeners
_SCREENER_REGISTRY = {
    'vix': VixRegimeScreener,
    'iv_rank': IvRankScreener,
    'leaps': LeapsEntryScreener,
}


class RecommendationService:
    """Orchestrates screeners, manages recommendation lifecycle."""

    def __init__(self, session: Session, broker=None, technical_service=None):
        """
        Args:
            session: SQLAlchemy session.
            broker: TastytradeAdapter (authenticated). None = mock mode.
            technical_service: TechnicalAnalysisService instance (optional).
        """
        self.session = session
        self.broker = broker
        self.technical_service = technical_service
        self.rec_repo = RecommendationRepository(session)
        self.watchlist_svc = WatchlistService(session, broker=broker)

    def run_screener(
        self,
        screener_name: str,
        watchlist_name: str,
        macro_override: Optional[MacroOverride] = None,
        **screener_kwargs,
    ) -> List[Recommendation]:
        """
        Run a screener against a watchlist and persist recommendations.

        Pipeline:
            1. Macro short-circuit check
            2. Run screener
            3. Auto-suggest portfolio
            4. Filter by active strategies
            5. Apply confidence modifier
            6. Persist to DB

        Args:
            screener_name: Key in screener registry ('vix', 'iv_rank', 'leaps', 'all').
            watchlist_name: Name of watchlist to screen.
            macro_override: Optional macro context override.
            **screener_kwargs: Extra kwargs passed to screener constructor.

        Returns:
            List of Recommendation objects (PENDING status, saved to DB).
        """
        # Step 1: Macro short-circuit
        macro_svc = MacroContextService(broker=self.broker)
        assessment = macro_svc.evaluate(override=macro_override)
        logger.info(f"Macro assessment: {assessment.regime} — {assessment.rationale}")

        if not assessment.should_screen:
            logger.warning(
                f"MACRO SHORT-CIRCUIT: {assessment.rationale} — "
                f"skipping all screeners"
            )
            return []

        # Handle 'all' screener — run all registered screeners
        if screener_name == 'all':
            return self._run_all_screeners(
                watchlist_name, assessment, macro_override, **screener_kwargs
            )

        # Get screener
        screener_cls = _SCREENER_REGISTRY.get(screener_name)
        if not screener_cls:
            logger.error(f"Unknown screener: {screener_name}. Available: {list(_SCREENER_REGISTRY.keys())}")
            return []

        screener = screener_cls(
            broker=self.broker,
            technical_service=self.technical_service,
            **screener_kwargs,
        )

        # Get watchlist
        watchlist = self.watchlist_svc.get_or_fetch(watchlist_name)
        if not watchlist:
            logger.error(f"Watchlist '{watchlist_name}' not found")
            return []

        logger.info(
            f"Running {screener.name} on '{watchlist_name}' "
            f"({len(watchlist.symbols)} symbols)"
        )

        # Step 2: Run screener
        recommendations = screener.screen(watchlist.symbols)

        # Step 3: Auto-suggest portfolio for each recommendation
        self._auto_suggest_portfolios(recommendations)

        # Step 4: Filter by active strategies for the suggested portfolio
        recommendations = self._filter_by_active_strategies(recommendations)

        # Step 5: Apply confidence modifier from macro assessment
        if assessment.confidence_modifier < 1.0:
            for rec in recommendations:
                original = rec.confidence
                rec.confidence = max(1, int(rec.confidence * assessment.confidence_modifier))
                if rec.confidence != original:
                    rec.rationale += f" [macro: {assessment.regime}, conf {original}→{rec.confidence}]"

        # Step 6: Persist to DB
        saved = []
        for rec in recommendations:
            created = self.rec_repo.create_from_domain(rec)
            if created:
                saved.append(created)

        logger.info(f"Saved {len(saved)} recommendations to DB")
        return saved

    def _run_all_screeners(
        self,
        watchlist_name: str,
        assessment: MacroAssessment,
        macro_override: Optional[MacroOverride],
        **screener_kwargs,
    ) -> List[Recommendation]:
        """Run all registered screeners and combine results."""
        all_recs = []
        for name in _SCREENER_REGISTRY:
            logger.info(f"Running '{name}' screener as part of 'all'...")
            recs = self.run_screener(
                screener_name=name,
                watchlist_name=watchlist_name,
                macro_override=macro_override,
                **screener_kwargs,
            )
            all_recs.extend(recs)
        return all_recs

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
        Accept a recommendation and execute it.

        For ENTRY: books a new WhatIf trade.
        For EXIT: closes the referenced trade.
        For ROLL: closes the referenced trade + books a new one with linkage.
        For ADJUST: (future) modifies the existing trade.

        Args:
            rec_id: Recommendation ID.
            notes: User's rationale for accepting.
            portfolio_name: Override portfolio (uses suggested if None).

        Returns:
            Dict with 'success', 'trade_id', 'error', and type-specific fields.
        """
        rec = self.get_by_id(rec_id)
        if not rec:
            return {'success': False, 'error': f'Recommendation {rec_id} not found'}

        if rec.status != RecommendationStatus.PENDING:
            return {'success': False, 'error': f'Recommendation is {rec.status.value}, not pending'}

        # Route to the appropriate handler based on recommendation type
        if rec.recommendation_type == RecommendationType.EXIT:
            return self._accept_exit(rec, notes, portfolio_name)
        elif rec.recommendation_type == RecommendationType.ROLL:
            return self._accept_roll(rec, notes, portfolio_name)
        elif rec.recommendation_type == RecommendationType.ADJUST:
            return self._accept_exit(rec, notes, portfolio_name)  # adjust = close for now
        else:
            return self._accept_entry(rec, notes, portfolio_name)

    def _accept_entry(
        self, rec: Recommendation, notes: str, portfolio_name: Optional[str]
    ) -> Dict:
        """Accept an ENTRY recommendation — book a new WhatIf trade."""
        target_portfolio = portfolio_name or rec.suggested_portfolio

        try:
            from trading_cotrader.services.trade_booking_service import (
                TradeBookingService, LegInput
            )

            leg_inputs = [
                LegInput(
                    streamer_symbol=leg.streamer_symbol,
                    quantity=leg.quantity,
                )
                for leg in rec.legs
            ]

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
                rec.accept(
                    notes=notes,
                    trade_id=result.trade_id,
                    portfolio_name=target_portfolio or '',
                )
                self.rec_repo.update_from_domain(rec)

                logger.info(
                    f"Accepted ENTRY rec {rec.id[:8]}... → Trade {result.trade_id[:8]}..."
                )
                return {
                    'success': True,
                    'trade_id': result.trade_id,
                    'portfolio': target_portfolio,
                    'action': 'entry',
                }
            else:
                return {'success': False, 'error': result.error}

        except Exception as e:
            logger.error(f"Failed to accept entry recommendation {rec.id}: {e}")
            return {'success': False, 'error': str(e)}

    def _accept_exit(
        self, rec: Recommendation, notes: str, portfolio_name: Optional[str]
    ) -> Dict:
        """
        Accept an EXIT recommendation — close the referenced trade.

        Close = mark the original trade as closed with exit reason.
        """
        if not rec.trade_id_to_close:
            return {'success': False, 'error': 'No trade_id_to_close on exit recommendation'}

        try:
            from trading_cotrader.repositories.trade import TradeRepository
            trade_repo = TradeRepository(self.session)

            closed = trade_repo.close_trade(
                trade_id=rec.trade_id_to_close,
                exit_reason=notes or rec.rationale,
            )

            if closed:
                rec.accept(
                    notes=notes,
                    trade_id=rec.trade_id_to_close,
                    portfolio_name=portfolio_name or rec.suggested_portfolio or '',
                )
                self.rec_repo.update_from_domain(rec)

                logger.info(
                    f"Accepted EXIT rec {rec.id[:8]}... → "
                    f"Closed trade {rec.trade_id_to_close[:8]}..."
                )
                return {
                    'success': True,
                    'trade_id': rec.trade_id_to_close,
                    'action': 'exit',
                    'closed_trade_id': rec.trade_id_to_close,
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to close trade {rec.trade_id_to_close}',
                }

        except Exception as e:
            logger.error(f"Failed to accept exit recommendation {rec.id}: {e}")
            return {'success': False, 'error': str(e)}

    def _accept_roll(
        self, rec: Recommendation, notes: str, portfolio_name: Optional[str]
    ) -> Dict:
        """
        Accept a ROLL recommendation — close original + book new with linkage.

        1. Close the original trade (mark_rolled)
        2. Book a new trade with rolled_from_id pointing to the original
        """
        if not rec.trade_id_to_close:
            return {'success': False, 'error': 'No trade_id_to_close on roll recommendation'}

        target_portfolio = portfolio_name or rec.suggested_portfolio

        try:
            from trading_cotrader.repositories.trade import TradeRepository
            from trading_cotrader.services.trade_booking_service import (
                TradeBookingService, LegInput
            )

            trade_repo = TradeRepository(self.session)

            # Step 1: Close original trade as "rolled"
            original_orm = trade_repo.get_by_id(rec.trade_id_to_close)
            if not original_orm:
                return {
                    'success': False,
                    'error': f'Original trade {rec.trade_id_to_close} not found',
                }

            # Step 2: Book new trade with the new legs (if provided)
            new_legs = rec.new_legs if rec.new_legs else rec.legs
            if not new_legs:
                return {
                    'success': False,
                    'error': 'No legs provided for the new rolled trade',
                }

            leg_inputs = [
                LegInput(
                    streamer_symbol=leg.streamer_symbol,
                    quantity=leg.quantity,
                )
                for leg in new_legs
            ]

            try:
                trade_source = TradeSource(rec.source)
            except ValueError:
                trade_source = TradeSource.MANUAL

            service = TradeBookingService(broker=self.broker)
            result = service.book_whatif_trade(
                underlying=rec.underlying,
                strategy_type=rec.strategy_type,
                legs=leg_inputs,
                notes=f"Rolled from {rec.trade_id_to_close[:8]}... — {notes or rec.rationale}",
                rationale=notes or rec.rationale,
                confidence=rec.confidence,
                portfolio_name=target_portfolio,
                trade_source=trade_source,
                recommendation_id=rec.id,
            )

            if result.success:
                # Mark original as rolled with linkage
                original_orm.trade_status = 'rolled'
                original_orm.is_open = False
                from datetime import datetime
                original_orm.closed_at = datetime.utcnow()
                original_orm.exit_reason = f"Rolled to {result.trade_id[:8]}..."
                original_orm.rolled_to_id = result.trade_id
                original_orm.last_updated = datetime.utcnow()
                self.session.flush()

                # Update recommendation
                rec.accept(
                    notes=notes,
                    trade_id=result.trade_id,
                    portfolio_name=target_portfolio or '',
                )
                self.rec_repo.update_from_domain(rec)

                logger.info(
                    f"Accepted ROLL rec {rec.id[:8]}... → "
                    f"Closed {rec.trade_id_to_close[:8]}... → "
                    f"New trade {result.trade_id[:8]}..."
                )
                return {
                    'success': True,
                    'trade_id': result.trade_id,
                    'action': 'roll',
                    'closed_trade_id': rec.trade_id_to_close,
                    'new_trade_id': result.trade_id,
                    'portfolio': target_portfolio,
                }
            else:
                return {'success': False, 'error': result.error}

        except Exception as e:
            logger.error(f"Failed to accept roll recommendation {rec.id}: {e}")
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

    def _filter_by_active_strategies(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """Filter out recs whose strategy is not active in the suggested portfolio."""
        try:
            from trading_cotrader.services.portfolio_manager import PortfolioManager
            pm = PortfolioManager(self.session)

            filtered = []
            for rec in recommendations:
                if not rec.suggested_portfolio:
                    # No portfolio suggestion — keep it
                    filtered.append(rec)
                    continue

                if pm.is_strategy_active(rec.suggested_portfolio, rec.strategy_type):
                    filtered.append(rec)
                else:
                    logger.info(
                        f"Filtered out {rec.underlying} {rec.strategy_type} — "
                        f"not active in '{rec.suggested_portfolio}'"
                    )

            if len(filtered) < len(recommendations):
                logger.info(
                    f"Active strategy filter: {len(recommendations)} → {len(filtered)} recommendations"
                )
            return filtered
        except Exception as e:
            logger.warning(f"Active strategy filter failed, keeping all recs: {e}")
            return recommendations

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
