"""
Trade Repository - Data access for trades and legs
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from repositories.base import BaseRepository
from repositories.position import SymbolRepository
from core.database.schema import TradeORM, LegORM, StrategyORM
import core.models.domain as dm

logger = logging.getLogger(__name__)


class TradeRepository(BaseRepository[dm.Trade, TradeORM]):
    """Repository for Trade entities"""
    
    def __init__(self, session: Session):
        super().__init__(session, TradeORM)
        self.symbol_repo = SymbolRepository(session)
        self.strategy_repo = StrategyRepository(session)
    
    def create_from_domain(self, trade: dm.Trade, portfolio_id: str) -> Optional[dm.Trade]:
        """Create trade from domain model"""
        try:
            # Create strategy if exists
            strategy_id = None
            if trade.strategy:
                strategy_orm = self.strategy_repo.get_or_create_from_domain(trade.strategy)
                if strategy_orm:
                    strategy_id = strategy_orm.id
            
            # Create trade ORM
            trade_orm = TradeORM(
                id=trade.id,
                portfolio_id=portfolio_id,
                strategy_id=strategy_id,
                underlying_symbol=trade.underlying_symbol,
                opened_at=trade.opened_at,
                closed_at=trade.closed_at,
                planned_entry=trade.planned_entry,
                planned_exit=trade.planned_exit,
                stop_loss=trade.stop_loss,
                profit_target=trade.profit_target,
                is_open=trade.is_open,
                notes=trade.notes,
                tags=trade.tags or [],
                broker_trade_id=trade.broker_trade_id
            )
            
            # Create trade
            created_trade = self.create(trade_orm)
            if not created_trade:
                return None
            
            # Create legs
            for leg in trade.legs:
                leg_orm = self._create_leg_orm(leg, trade.id)
                if leg_orm:
                    self.session.add(leg_orm)
            
            self.flush()
            
            # Convert back to domain
            return self.to_domain(created_trade)
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating trade: {e}")
            logger.exception("Full trace:")
            return None
    
    def get_by_portfolio(self, portfolio_id: str, open_only: bool = False) -> List[dm.Trade]:
        """Get trades for a portfolio"""
        try:
            query = self.session.query(TradeORM).filter_by(portfolio_id=portfolio_id)
            
            if open_only:
                query = query.filter_by(is_open=True)
            
            trades_orm = query.order_by(TradeORM.opened_at.desc()).all()
            return [self.to_domain(t) for t in trades_orm]
            
        except Exception as e:
            logger.error(f"Error getting trades for portfolio {portfolio_id}: {e}")
            return []
    
    def get_by_underlying(self, underlying: str, portfolio_id: Optional[str] = None) -> List[dm.Trade]:
        """Get trades by underlying symbol"""
        try:
            query = self.session.query(TradeORM).filter_by(underlying_symbol=underlying)
            
            if portfolio_id:
                query = query.filter_by(portfolio_id=portfolio_id)
            
            trades_orm = query.all()
            return [self.to_domain(t) for t in trades_orm]
            
        except Exception as e:
            logger.error(f"Error getting trades for {underlying}: {e}")
            return []
    
    def update_from_domain(self, trade: dm.Trade) -> Optional[dm.Trade]:
        """Update trade from domain model"""
        try:
            trade_orm = self.get_by_id(trade.id)
            if not trade_orm:
                logger.error(f"Trade {trade.id} not found for update")
                return None
            
            # Update fields
            trade_orm.closed_at = trade.closed_at
            trade_orm.planned_entry = trade.planned_entry
            trade_orm.planned_exit = trade.planned_exit
            trade_orm.stop_loss = trade.stop_loss
            trade_orm.profit_target = trade.profit_target
            trade_orm.is_open = trade.is_open
            trade_orm.notes = trade.notes
            trade_orm.tags = trade.tags
            trade_orm.last_updated = datetime.utcnow()
            
            updated = self.update(trade_orm)
            return self.to_domain(updated) if updated else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating trade {trade.id}: {e}")
            return None
    
    def close_trade(self, trade_id: str) -> bool:
        """Mark trade as closed"""
        try:
            trade_orm = self.get_by_id(trade_id)
            if not trade_orm:
                return False
            
            trade_orm.is_open = False
            trade_orm.closed_at = datetime.utcnow()
            trade_orm.last_updated = datetime.utcnow()
            
            self.update(trade_orm)
            return True
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error closing trade {trade_id}: {e}")
            return False
    
    def _create_leg_orm(self, leg: dm.Leg, trade_id: str) -> Optional[LegORM]:
        """Create leg ORM instance"""
        try:
            symbol_orm = self.symbol_repo.get_or_create_from_domain(leg.symbol)
            if not symbol_orm:
                return None
            
            leg_orm = LegORM(
                id=leg.id,
                trade_id=trade_id,
                symbol_id=symbol_orm.id,
                quantity=leg.quantity,
                side=leg.side.value,
                entry_price=leg.entry_price,
                entry_time=leg.entry_time,
                exit_price=leg.exit_price,
                exit_time=leg.exit_time,
                current_price=leg.current_price,
                fees=leg.fees,
                commission=leg.commission,
                broker_leg_id=leg.broker_leg_id
            )
            
            # Add Greeks if available
            if leg.greeks:
                leg_orm.delta = leg.greeks.delta
                leg_orm.gamma = leg.greeks.gamma
                leg_orm.theta = leg.greeks.theta
                leg_orm.vega = leg.greeks.vega
            
            return leg_orm
            
        except Exception as e:
            logger.error(f"Error creating leg ORM: {e}")
            return None
    
    def to_domain(self, trade_orm: TradeORM) -> dm.Trade:
        """Convert ORM to domain model"""
        # Convert legs
        legs = []
        for leg_orm in trade_orm.legs:
            symbol = self.symbol_repo.to_domain(leg_orm.symbol)
            
            greeks = None
            if leg_orm.delta is not None:
                greeks = dm.Greeks(
                    delta=leg_orm.delta,
                    gamma=leg_orm.gamma or 0,
                    theta=leg_orm.theta or 0,
                    vega=leg_orm.vega or 0
                )
            
            leg = dm.Leg(
                id=leg_orm.id,
                symbol=symbol,
                quantity=leg_orm.quantity,
                side=dm.OrderSide(leg_orm.side),
                entry_price=leg_orm.entry_price,
                entry_time=leg_orm.entry_time,
                exit_price=leg_orm.exit_price,
                exit_time=leg_orm.exit_time,
                current_price=leg_orm.current_price,
                greeks=greeks,
                broker_leg_id=leg_orm.broker_leg_id,
                fees=leg_orm.fees,
                commission=leg_orm.commission
            )
            legs.append(leg)
        
        # Convert strategy
        strategy = None
        if trade_orm.strategy:
            strategy = self.strategy_repo.to_domain(trade_orm.strategy)
        
        return dm.Trade(
            id=trade_orm.id,
            legs=legs,
            strategy=strategy,
            opened_at=trade_orm.opened_at,
            closed_at=trade_orm.closed_at,
            underlying_symbol=trade_orm.underlying_symbol,
            planned_entry=trade_orm.planned_entry,
            planned_exit=trade_orm.planned_exit,
            stop_loss=trade_orm.stop_loss,
            profit_target=trade_orm.profit_target,
            is_open=trade_orm.is_open,
            notes=trade_orm.notes,
            tags=trade_orm.tags or [],
            broker_trade_id=trade_orm.broker_trade_id
        )


class StrategyRepository(BaseRepository[dm.Strategy, StrategyORM]):
    """Repository for Strategy entities"""
    
    def __init__(self, session: Session):
        super().__init__(session, StrategyORM)
    
    def get_or_create_from_domain(self, strategy: dm.Strategy) -> Optional[StrategyORM]:
        """Get existing strategy or create new one"""
        try:
            # Try to find existing
            existing = self.session.query(StrategyORM).filter_by(
                name=strategy.name,
                strategy_type=strategy.strategy_type.value
            ).first()
            
            if existing:
                return existing
            
            # Create new
            strategy_orm = StrategyORM(
                id=strategy.id,
                name=strategy.name,
                strategy_type=strategy.strategy_type.value,
                max_profit=strategy.max_profit,
                max_loss=strategy.max_loss,
                breakeven_points=[float(bp) for bp in strategy.breakeven_points] if strategy.breakeven_points else None,
                target_delta=strategy.target_delta,
                max_gamma=strategy.max_gamma,
                description=strategy.description
            )
            
            created = self.create(strategy_orm)
            return created
            
        except Exception as e:
            logger.error(f"Error getting/creating strategy {strategy.name}: {e}")
            return None
    
    def to_domain(self, strategy_orm: StrategyORM) -> dm.Strategy:
        """Convert ORM to domain model"""
        from decimal import Decimal
        
        breakeven_points = []
        if strategy_orm.breakeven_points:
            breakeven_points = [Decimal(str(bp)) for bp in strategy_orm.breakeven_points]
        
        return dm.Strategy(
            id=strategy_orm.id,
            name=strategy_orm.name,
            strategy_type=dm.StrategyType(strategy_orm.strategy_type),
            max_profit=strategy_orm.max_profit,
            max_loss=strategy_orm.max_loss,
            breakeven_points=breakeven_points,
            target_delta=strategy_orm.target_delta,
            max_gamma=strategy_orm.max_gamma,
            description=strategy_orm.description
        )