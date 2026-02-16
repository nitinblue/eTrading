"""
Position Repository - Data access for positions
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime
import logging

from trading_cotrader.repositories.base import BaseRepository, DuplicateEntityError
from trading_cotrader.core.database.schema import PositionORM, SymbolORM
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class PositionRepository(BaseRepository[dm.Position, PositionORM]):
    """Repository for Position entities"""
    
    def __init__(self, session: Session):
        super().__init__(session, PositionORM)
        self.symbol_repo = SymbolRepository(session)
    
    def create_from_domain(self, position: dm.Position, portfolio_id: str) -> Optional[dm.Position]:
        """
        Create position from domain model
        
        Args:
            position: Domain position model
            portfolio_id: Portfolio ID
            
        Returns:
            Created position or None on error
        """
        try:
            # Get or create symbol
            symbol_orm = self.symbol_repo.get_or_create_from_domain(position.symbol)
            if not symbol_orm:
                logger.error(f"Failed to get/create symbol for position")
                return None
            
            # Create ORM instance
            position_orm = PositionORM(
                id=position.id,
                portfolio_id=portfolio_id,
                symbol_id=symbol_orm.id,
                quantity=position.quantity,
                entry_price=position.entry_price,
                total_cost=position.total_cost,
                current_price=position.current_price,
                market_value=position.market_value,
                broker_position_id=position.broker_position_id,
                trade_ids=position.trade_ids or [],
            )
            
            # Add Greeks if available
            if position.greeks:
                position_orm.delta = position.greeks.delta
                position_orm.gamma = position.greeks.gamma
                position_orm.theta = position.greeks.theta
                position_orm.vega = position.greeks.vega
                position_orm.rho = position.greeks.rho
                position_orm.greeks_updated_at = position.greeks.timestamp
            
            # Create
            created = self.create(position_orm)
            if not created:
                return None
            
            # Convert back to domain model
            return self.to_domain(created)
            
        except IntegrityError as e:
            self.rollback()
            logger.error(f"Duplicate position: {e}")
            raise DuplicateEntityError(f"Position already exists: {position.broker_position_id}")
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating position: {e}")
            logger.exception("Full trace:")
            return None
    
    def get_by_portfolio(self, portfolio_id: str) -> List[dm.Position]:
        """Get all positions for a portfolio"""
        try:
            positions_orm = self.session.query(PositionORM).filter_by(
                portfolio_id=portfolio_id
            ).all()
            
            return [self.to_domain(p) for p in positions_orm]
        except Exception as e:
            logger.error(f"Error getting positions for portfolio {portfolio_id}: {e}")
            return []
    
    def get_by_symbol(self, portfolio_id: str, ticker: str) -> List[dm.Position]:
        """Get positions by symbol ticker"""
        try:
            positions_orm = self.session.query(PositionORM).join(SymbolORM).filter(
                PositionORM.portfolio_id == portfolio_id,
                SymbolORM.ticker == ticker
            ).all()
            
            return [self.to_domain(p) for p in positions_orm]
        except Exception as e:
            logger.error(f"Error getting positions for {ticker}: {e}")
            return []
    
    def get_by_broker_id(self, portfolio_id: str, broker_position_id: str) -> Optional[dm.Position]:
        """Get position by broker position ID"""
        try:
            position_orm = self.session.query(PositionORM).filter_by(
                portfolio_id=portfolio_id,
                broker_position_id=broker_position_id
            ).first()
            
            return self.to_domain(position_orm) if position_orm else None
        except Exception as e:
            logger.error(f"Error getting position by broker ID {broker_position_id}: {e}")
            return None
    
    def update_from_domain(self, position: dm.Position) -> Optional[dm.Position]:
        """Update position from domain model"""
        try:
            position_orm = self.get_by_id(position.id)
            if not position_orm:
                logger.error(f"Position {position.id} not found for update")
                return None
            
            # Update fields
            position_orm.quantity = position.quantity
            position_orm.average_price = position.average_price
            position_orm.total_cost = position.total_cost
            position_orm.current_price = position.current_price
            position_orm.market_value = position.market_value
            position_orm.trade_ids = position.trade_ids
            position_orm.last_updated = datetime.utcnow()
            
            # Update Greeks
            if position.greeks:
                position_orm.delta = position.greeks.delta
                position_orm.gamma = position.greeks.gamma
                position_orm.theta = position.greeks.theta
                position_orm.vega = position.greeks.vega
                position_orm.rho = position.greeks.rho
                position_orm.greeks_updated_at = position.greeks.timestamp
            
            updated = self.update(position_orm)
            return self.to_domain(updated) if updated else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating position {position.id}: {e}")
            return None
    
    def delete_by_portfolio(self, portfolio_id: str) -> int:
        """Delete all positions for a portfolio"""
        try:
            count = self.session.query(PositionORM).filter_by(
                portfolio_id=portfolio_id
            ).delete()
            self.flush()
            logger.info(f"Deleted {count} positions for portfolio {portfolio_id}")
            return count
        except Exception as e:
            self.rollback()
            logger.error(f"Error deleting positions for portfolio {portfolio_id}: {e}")
            return 0
    
    def to_domain(self, position_orm: PositionORM) -> dm.Position:
        """Convert ORM to domain model"""
        # Convert symbol
        symbol = self.symbol_repo.to_domain(position_orm.symbol)
        
        # Convert Greeks
        greeks = None
        if position_orm.delta is not None:
            greeks = dm.Greeks(
                delta=position_orm.delta,
                gamma=position_orm.gamma or 0,
                theta=position_orm.theta or 0,
                vega=position_orm.vega or 0,
                rho=position_orm.rho or 0,
                timestamp=position_orm.greeks_updated_at or datetime.utcnow()
            )
        
        return dm.Position(
            id=position_orm.id,
            symbol=symbol,
            quantity=position_orm.quantity,
            entry_price=position_orm.entry_price,
            total_cost=position_orm.total_cost,
            current_price=position_orm.current_price,
            market_value=position_orm.market_value,         
            trade_ids=position_orm.trade_ids or [],
            broker_position_id=position_orm.broker_position_id,
            last_updated=position_orm.last_updated,
            greeks=greeks
        )


class SymbolRepository(BaseRepository[dm.Symbol, SymbolORM]):
    """Repository for Symbol entities (cached to avoid duplicates)"""
    
    def __init__(self, session: Session):
        super().__init__(session, SymbolORM)
    
    def get_or_create_from_domain(self, symbol: dm.Symbol) -> Optional[SymbolORM]:
        """
        Get existing symbol or create new one.
        Uses savepoint so IntegrityError on duplicate doesn't
        roll back the outer transaction.
        """
        try:
            # Build query
            query = self.session.query(SymbolORM).filter_by(
                ticker=symbol.ticker,
                asset_type=symbol.asset_type.value
            )

            # Add option-specific filters
            if symbol.asset_type == dm.AssetType.OPTION:
                # Normalize expiration: DB stores datetime, domain may pass date
                exp = symbol.expiration
                if exp and isinstance(exp, date) and not isinstance(exp, datetime):
                    exp = datetime(exp.year, exp.month, exp.day)

                query = query.filter_by(
                    option_type=symbol.option_type.value,
                    strike=symbol.strike,
                    expiration=exp
                )

            # Try to find existing
            existing = query.first()
            if existing:
                return existing

            # Create new — use savepoint so IntegrityError only
            # rolls back this insert, not the entire session
            symbol_orm = SymbolORM(
                id=str(dm.uuid.uuid4()),
                ticker=symbol.ticker,
                asset_type=symbol.asset_type.value,
                option_type=symbol.option_type.value if symbol.option_type else None,
                strike=symbol.strike,
                expiration=symbol.expiration,
                description=symbol.description,
                multiplier=symbol.multiplier
            )

            try:
                nested = self.session.begin_nested()
                self.session.add(symbol_orm)
                nested.commit()
                return symbol_orm
            except IntegrityError:
                nested.rollback()
                # Another transaction created it — fetch and return
                return query.first()

        except Exception as e:
            logger.error(f"Error getting/creating symbol {symbol.ticker}: {e}")
            return None
    
    def to_domain(self, symbol_orm: SymbolORM) -> dm.Symbol:
        """Convert ORM to domain model"""
        return dm.Symbol(
            ticker=symbol_orm.ticker,
            asset_type=dm.AssetType(symbol_orm.asset_type),
            option_type=dm.OptionType(symbol_orm.option_type) if symbol_orm.option_type else None,
            strike=symbol_orm.strike,
            expiration=symbol_orm.expiration,
            description=symbol_orm.description,
            multiplier=symbol_orm.multiplier
        )