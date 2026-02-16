"""
Recommendation Repository - CRUD for trade recommendations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from trading_cotrader.repositories.base import BaseRepository
from trading_cotrader.core.database.schema import RecommendationORM
from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendationStatus, RecommendationType,
    RecommendedLeg, MarketSnapshot
)

logger = logging.getLogger(__name__)


class RecommendationRepository(BaseRepository[Recommendation, RecommendationORM]):
    """Repository for Recommendation entities."""

    def __init__(self, session: Session):
        super().__init__(session, RecommendationORM)

    def create_from_domain(self, rec: Recommendation) -> Optional[Recommendation]:
        """Create recommendation from domain model."""
        try:
            orm = RecommendationORM(
                id=rec.id,
                recommendation_type=rec.recommendation_type.value,
                source=rec.source,
                screener_name=rec.screener_name,
                underlying=rec.underlying,
                strategy_type=rec.strategy_type,
                legs=[l.to_dict() for l in rec.legs],
                market_context=rec.market_context.to_dict(),
                confidence=rec.confidence,
                rationale=rec.rationale,
                risk_category=rec.risk_category,
                suggested_portfolio=rec.suggested_portfolio,
                status=rec.status.value,
                created_at=rec.created_at,
                trade_id_to_close=rec.trade_id_to_close,
                exit_action=rec.exit_action,
                exit_urgency=rec.exit_urgency,
                triggered_rules=rec.triggered_rules if rec.triggered_rules else None,
                new_legs=[l.to_dict() for l in rec.new_legs] if rec.new_legs else None,
            )
            created = self.create(orm)
            return self.to_domain(created) if created else None
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating recommendation: {e}")
            return None

    def get_pending(self) -> List[Recommendation]:
        """Get all pending recommendations."""
        try:
            orms = (
                self.session.query(RecommendationORM)
                .filter_by(status='pending')
                .order_by(RecommendationORM.created_at.desc())
                .all()
            )
            return [self.to_domain(o) for o in orms]
        except Exception as e:
            logger.error(f"Error getting pending recommendations: {e}")
            return []

    def get_by_status(self, status: str) -> List[Recommendation]:
        """Get recommendations by status."""
        try:
            orms = (
                self.session.query(RecommendationORM)
                .filter_by(status=status)
                .order_by(RecommendationORM.created_at.desc())
                .all()
            )
            return [self.to_domain(o) for o in orms]
        except Exception as e:
            logger.error(f"Error getting recommendations by status {status}: {e}")
            return []

    def get_by_source(self, source: str) -> List[Recommendation]:
        """Get recommendations by source."""
        try:
            orms = (
                self.session.query(RecommendationORM)
                .filter_by(source=source)
                .order_by(RecommendationORM.created_at.desc())
                .all()
            )
            return [self.to_domain(o) for o in orms]
        except Exception as e:
            logger.error(f"Error getting recommendations by source {source}: {e}")
            return []

    def update_from_domain(self, rec: Recommendation) -> Optional[Recommendation]:
        """Update recommendation from domain model."""
        try:
            orm = self.session.query(RecommendationORM).filter_by(id=rec.id).first()
            if not orm:
                logger.error(f"Recommendation {rec.id} not found")
                return None

            orm.status = rec.status.value
            orm.reviewed_at = rec.reviewed_at
            orm.accepted_notes = rec.accepted_notes
            orm.trade_id = rec.trade_id
            orm.portfolio_name = rec.portfolio_name
            orm.rejection_reason = rec.rejection_reason

            self.session.flush()
            return self.to_domain(orm)
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating recommendation {rec.id}: {e}")
            return None

    def expire_old(self, max_age_hours: int = 24) -> int:
        """Expire pending recommendations older than max_age_hours."""
        try:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            count = (
                self.session.query(RecommendationORM)
                .filter(RecommendationORM.status == 'pending')
                .filter(RecommendationORM.created_at < cutoff)
                .update({'status': 'expired', 'reviewed_at': datetime.utcnow()})
            )
            self.session.flush()
            return count
        except Exception as e:
            self.rollback()
            logger.error(f"Error expiring old recommendations: {e}")
            return 0

    def to_domain(self, orm: RecommendationORM) -> Recommendation:
        """Convert ORM to domain model."""
        # Reconstruct legs
        legs = []
        if orm.legs:
            for leg_dict in orm.legs:
                from decimal import Decimal
                legs.append(RecommendedLeg(
                    streamer_symbol=leg_dict.get('streamer_symbol', ''),
                    quantity=leg_dict.get('quantity', 0),
                    delta_target=Decimal(str(leg_dict['delta_target'])) if leg_dict.get('delta_target') else None,
                    strike=Decimal(str(leg_dict['strike'])) if leg_dict.get('strike') else None,
                    option_type=leg_dict.get('option_type'),
                    expiration=leg_dict.get('expiration'),
                ))

        # Reconstruct market context
        market_ctx = MarketSnapshot()
        if orm.market_context:
            from decimal import Decimal
            mc = orm.market_context
            market_ctx = MarketSnapshot(
                vix=Decimal(str(mc['vix'])) if mc.get('vix') else None,
                iv_rank=Decimal(str(mc['iv_rank'])) if mc.get('iv_rank') else None,
                underlying_price=Decimal(str(mc['underlying_price'])) if mc.get('underlying_price') else None,
                rsi=Decimal(str(mc['rsi'])) if mc.get('rsi') else None,
                market_trend=mc.get('market_trend'),
            )

        try:
            status = RecommendationStatus(orm.status)
        except ValueError:
            status = RecommendationStatus.PENDING

        try:
            rec_type = RecommendationType(getattr(orm, 'recommendation_type', 'entry') or 'entry')
        except ValueError:
            rec_type = RecommendationType.ENTRY

        # Reconstruct new_legs for ROLL recommendations
        new_legs = []
        orm_new_legs = getattr(orm, 'new_legs', None)
        if orm_new_legs:
            for leg_dict in orm_new_legs:
                from decimal import Decimal
                new_legs.append(RecommendedLeg(
                    streamer_symbol=leg_dict.get('streamer_symbol', ''),
                    quantity=leg_dict.get('quantity', 0),
                    delta_target=Decimal(str(leg_dict['delta_target'])) if leg_dict.get('delta_target') else None,
                    strike=Decimal(str(leg_dict['strike'])) if leg_dict.get('strike') else None,
                    option_type=leg_dict.get('option_type'),
                    expiration=leg_dict.get('expiration'),
                ))

        return Recommendation(
            id=orm.id,
            recommendation_type=rec_type,
            source=orm.source or '',
            screener_name=orm.screener_name or '',
            underlying=orm.underlying,
            strategy_type=orm.strategy_type,
            legs=legs,
            market_context=market_ctx,
            confidence=orm.confidence or 5,
            rationale=orm.rationale or '',
            risk_category=orm.risk_category or 'defined',
            suggested_portfolio=orm.suggested_portfolio,
            status=status,
            created_at=orm.created_at,
            reviewed_at=orm.reviewed_at,
            accepted_notes=orm.accepted_notes or '',
            trade_id=orm.trade_id,
            portfolio_name=orm.portfolio_name,
            rejection_reason=orm.rejection_reason or '',
            trade_id_to_close=getattr(orm, 'trade_id_to_close', None),
            exit_action=getattr(orm, 'exit_action', None),
            exit_urgency=getattr(orm, 'exit_urgency', None),
            triggered_rules=getattr(orm, 'triggered_rules', None) or [],
            new_legs=new_legs,
        )
