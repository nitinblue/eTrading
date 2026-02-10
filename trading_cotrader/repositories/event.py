"""
Event Repository - Store and retrieve trading events for AI learning
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from trading_cotrader.repositories.base import BaseRepository
from trading_cotrader.core.database.schema import TradeEventORM, RecognizedPatternORM
import trading_cotrader.core.models.events as events

logger = logging.getLogger(__name__)


class EventRepository(BaseRepository[events.TradeEvent, TradeEventORM]):
    """Repository for trade events (AI learning data)"""
    
    def __init__(self, session: Session):
        super().__init__(session, TradeEventORM)
    
    def create_from_domain(self, event: events.TradeEvent) -> Optional[events.TradeEvent]:
        """Create event from domain model"""
        try:
            event_orm = TradeEventORM(
                event_id=event.event_id,
                trade_id=event.trade_id,
                event_type=event.event_type.value,
                timestamp=event.timestamp,
                market_context=event.market_context.to_dict(),
                decision_context=event.decision_context.to_dict(),
                strategy_type=event.strategy_type,
                underlying_symbol=event.underlying_symbol,
                net_credit_debit=event.net_credit_debit,
                entry_delta=event.entry_delta,
                entry_gamma=event.entry_gamma,
                entry_theta=event.entry_theta,
                entry_vega=event.entry_vega,
                outcome=event.outcome.to_dict() if event.outcome else None,
                tags=event.tags or []
            )
            
            created = self.create(event_orm)
            return self.to_domain(created) if created else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating event: {e}")
            logger.exception("Full trace:")
            return None
    
    def get_by_trade(self, trade_id: str) -> List[events.TradeEvent]:
        """Get all events for a trade"""
        try:
            events_orm = self.session.query(TradeEventORM).filter_by(
                trade_id=trade_id
            ).order_by(TradeEventORM.timestamp).all()
            
            return [self.to_domain(e) for e in events_orm]
            
        except Exception as e:
            logger.error(f"Error getting events for trade {trade_id}: {e}")
            return []
    
    def get_by_type(self, event_type: events.EventType, 
                   start_date: Optional[datetime] = None) -> List[events.TradeEvent]:
        """Get events by type"""
        try:
            query = self.session.query(TradeEventORM).filter_by(
                event_type=event_type.value
            )
            
            if start_date:
                query = query.filter(TradeEventORM.timestamp >= start_date)
            
            events_orm = query.order_by(TradeEventORM.timestamp.desc()).all()
            return [self.to_domain(e) for e in events_orm]
            
        except Exception as e:
            logger.error(f"Error getting events by type {event_type}: {e}")
            return []
    
    def get_by_underlying(self, underlying_symbol: str, 
                         start_date: Optional[datetime] = None) -> List[events.TradeEvent]:
        """Get events for an underlying"""
        try:
            query = self.session.query(TradeEventORM).filter_by(
                underlying_symbol=underlying_symbol
            )
            
            if start_date:
                query = query.filter(TradeEventORM.timestamp >= start_date)
            
            events_orm = query.order_by(TradeEventORM.timestamp.desc()).all()
            return [self.to_domain(e) for e in events_orm]
            
        except Exception as e:
            logger.error(f"Error getting events for {underlying_symbol}: {e}")
            return []
    
    def get_recent_events(self, days: int = 30, 
                         event_type: Optional[events.EventType] = None) -> List[events.TradeEvent]:
        """Get recent events"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = self.session.query(TradeEventORM).filter(
                TradeEventORM.timestamp >= cutoff
            )
            
            if event_type:
                query = query.filter_by(event_type=event_type.value)
            
            events_orm = query.order_by(TradeEventORM.timestamp.desc()).all()
            return [self.to_domain(e) for e in events_orm]
            
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []
    
    def update_outcome(self, event_id: str, outcome: events.TradeOutcomeData) -> bool:
        """Update event outcome (when trade closes)"""
        try:
            event_orm = self.get_by_id(event_id)
            if not event_orm:
                logger.error(f"Event {event_id} not found")
                return False
            
            event_orm.outcome = outcome.to_dict()
            self.update(event_orm)
            return True
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating event outcome {event_id}: {e}")
            return False
    
    def get_events_for_learning(self, min_events: int = 5) -> List[events.TradeEvent]:
        """
        Get events suitable for AI learning
        Returns completed events (with outcomes)
        """
        try:
            events_orm = self.session.query(TradeEventORM).filter(
                TradeEventORM.outcome.isnot(None)
            ).order_by(TradeEventORM.timestamp.desc()).all()
            
            return [self.to_domain(e) for e in events_orm]
            
        except Exception as e:
            logger.error(f"Error getting events for learning: {e}")
            return []
    
    def to_domain(self, event_orm: TradeEventORM) -> events.TradeEvent:
        """Convert ORM to domain model"""
        # Reconstruct market context
        market_ctx = events.MarketContext(**event_orm.market_context)
        
        # Reconstruct decision context
        decision_ctx = events.DecisionContext(**event_orm.decision_context)
        
        # Reconstruct outcome if present
        outcome = None
        if event_orm.outcome:
            outcome = events.TradeOutcomeData(**event_orm.outcome)
        
        return events.TradeEvent(
            event_id=event_orm.event_id,
            timestamp=event_orm.timestamp,
            event_type=events.EventType(event_orm.event_type),
            trade_id=event_orm.trade_id,
            market_context=market_ctx,
            decision_context=decision_ctx,
            strategy_type=event_orm.strategy_type,
            underlying_symbol=event_orm.underlying_symbol,
            net_credit_debit=event_orm.net_credit_debit,
            entry_delta=event_orm.entry_delta,
            entry_gamma=event_orm.entry_gamma,
            entry_theta=event_orm.entry_theta,
            entry_vega=event_orm.entry_vega,
            outcome=outcome,
            tags=event_orm.tags or []
        )


class PatternRepository(BaseRepository[events.RecognizedPattern, RecognizedPatternORM]):
    """Repository for recognized trading patterns"""
    
    def __init__(self, session: Session):
        super().__init__(session, RecognizedPatternORM)
    
    def create_from_domain(self, pattern: events.RecognizedPattern) -> Optional[events.RecognizedPattern]:
        """Create pattern from domain model"""
        try:
            pattern_orm = RecognizedPatternORM(
                pattern_id=pattern.pattern_id,
                pattern_type=pattern.pattern_type,
                description=pattern.description,
                conditions=pattern.conditions,
                occurrences=pattern.occurrences,
                success_rate=pattern.success_rate,
                avg_pnl=pattern.avg_pnl,
                confidence_score=pattern.confidence_score,
                discovered_at=pattern.discovered_at,
                last_seen=pattern.last_seen
            )
            
            created = self.create(pattern_orm)
            return self.to_domain(created) if created else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating pattern: {e}")
            return None
    
    def get_by_type(self, pattern_type: str) -> List[events.RecognizedPattern]:
        """Get patterns by type"""
        try:
            patterns_orm = self.session.query(RecognizedPatternORM).filter_by(
                pattern_type=pattern_type
            ).order_by(RecognizedPatternORM.confidence_score.desc()).all()
            
            return [self.to_domain(p) for p in patterns_orm]
            
        except Exception as e:
            logger.error(f"Error getting patterns by type {pattern_type}: {e}")
            return []
    
    def get_high_confidence_patterns(self, min_confidence: float = 0.7) -> List[events.RecognizedPattern]:
        """Get patterns with high confidence scores"""
        try:
            patterns_orm = self.session.query(RecognizedPatternORM).filter(
                RecognizedPatternORM.confidence_score >= min_confidence
            ).order_by(RecognizedPatternORM.confidence_score.desc()).all()
            
            return [self.to_domain(p) for p in patterns_orm]
            
        except Exception as e:
            logger.error(f"Error getting high confidence patterns: {e}")
            return []
    
    def update_pattern_stats(self, pattern_id: str, occurrences: int, 
                            success_rate: float, avg_pnl: float) -> bool:
        """Update pattern statistics"""
        try:
            pattern_orm = self.get_by_id(pattern_id)
            if not pattern_orm:
                return False
            
            pattern_orm.occurrences = occurrences
            pattern_orm.success_rate = success_rate
            pattern_orm.avg_pnl = avg_pnl
            pattern_orm.last_seen = datetime.utcnow()
            
            self.update(pattern_orm)
            return True
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating pattern stats {pattern_id}: {e}")
            return False
    
    def to_domain(self, pattern_orm: RecognizedPatternORM) -> events.RecognizedPattern:
        """Convert ORM to domain model"""
        from decimal import Decimal
        
        return events.RecognizedPattern(
            pattern_id=pattern_orm.pattern_id,
            pattern_type=pattern_orm.pattern_type,
            description=pattern_orm.description,
            conditions=pattern_orm.conditions,
            occurrences=pattern_orm.occurrences,
            success_rate=pattern_orm.success_rate,
            avg_pnl=Decimal(str(pattern_orm.avg_pnl)),
            confidence_score=pattern_orm.confidence_score,
            discovered_at=pattern_orm.discovered_at,
            last_seen=pattern_orm.last_seen
        )