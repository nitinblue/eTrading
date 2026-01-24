"""
Portfolio Repository - Data access for portfolios
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from trading_cotrader.repositories.base import BaseRepository
from trading_cotrader.core.database.schema import PortfolioORM
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class PortfolioRepository(BaseRepository[dm.Portfolio, PortfolioORM]):
    """Repository for Portfolio entities"""
    
    def __init__(self, session: Session):
        super().__init__(session, PortfolioORM)
    
    def get_by_id(self, id: str) -> Optional[dm.Portfolio]:
        """Get portfolio by ID, returns domain model"""
        try:
            portfolio_orm = self.session.query(PortfolioORM).filter_by(id=id).first()
            return self.to_domain(portfolio_orm) if portfolio_orm else None
        except Exception as e:
            logger.error(f"Error getting portfolio by id {id}: {e}")
            return None
    
    def create_from_domain(self, portfolio: dm.Portfolio) -> Optional[dm.Portfolio]:
        """Create portfolio from domain model"""
        try:
            portfolio_orm = PortfolioORM(
                id=portfolio.id,
                name=portfolio.name,
                broker=portfolio.broker,
                account_id=portfolio.account_id,
                cash_balance=portfolio.cash_balance,
                buying_power=portfolio.buying_power,
                total_equity=portfolio.total_equity,
                total_pnl=portfolio.total_pnl,
                daily_pnl=portfolio.daily_pnl,
                created_at=portfolio.created_at,
                last_updated=portfolio.last_updated
            )
            
            # Add Greeks if available
            if portfolio.portfolio_greeks:
                portfolio_orm.portfolio_delta = portfolio.portfolio_greeks.delta
                portfolio_orm.portfolio_gamma = portfolio.portfolio_greeks.gamma
                portfolio_orm.portfolio_theta = portfolio.portfolio_greeks.theta
                portfolio_orm.portfolio_vega = portfolio.portfolio_greeks.vega
                portfolio_orm.portfolio_rho = portfolio.portfolio_greeks.rho
            
            created = self.create(portfolio_orm)
            return self.to_domain(created) if created else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error creating portfolio: {e}")
            logger.exception("Full trace:")
            return None
    
    def get_by_account(self, broker: str, account_id: str) -> Optional[dm.Portfolio]:
        """Get portfolio by broker and account ID"""
        try:
            portfolio_orm = self.session.query(PortfolioORM).filter_by(
                broker=broker,
                account_id=account_id
            ).first()
            
            return self.to_domain(portfolio_orm) if portfolio_orm else None
            
        except Exception as e:
            logger.error(f"Error getting portfolio for {broker} {account_id}: {e}")
            return None
    
    def get_all_portfolios(self) -> List[dm.Portfolio]:
        """Get all portfolios"""
        try:
            portfolios_orm = self.session.query(PortfolioORM).all()
            return [self.to_domain(p) for p in portfolios_orm]
            
        except Exception as e:
            logger.error(f"Error getting all portfolios: {e}")
            return []
    
    def update_from_domain(self, portfolio: dm.Portfolio) -> Optional[dm.Portfolio]:
        """Update portfolio from domain model"""
        try:
            # Get the ORM object by ID
            portfolio_orm = self.session.query(PortfolioORM).filter_by(id=portfolio.id).first()
            
            if not portfolio_orm:
                logger.error(f"Portfolio {portfolio.id} not found for update")
                return None
            
            # Update ORM fields
            portfolio_orm.name = portfolio.name
            portfolio_orm.cash_balance = portfolio.cash_balance
            portfolio_orm.buying_power = portfolio.buying_power
            portfolio_orm.total_equity = portfolio.total_equity
            portfolio_orm.total_pnl = portfolio.total_pnl
            portfolio_orm.daily_pnl = portfolio.daily_pnl
            portfolio_orm.last_updated = datetime.utcnow()
            
            # Update Greeks
            if portfolio.portfolio_greeks:
                portfolio_orm.portfolio_delta = portfolio.portfolio_greeks.delta
                portfolio_orm.portfolio_gamma = portfolio.portfolio_greeks.gamma
                portfolio_orm.portfolio_theta = portfolio.portfolio_greeks.theta
                portfolio_orm.portfolio_vega = portfolio.portfolio_greeks.vega
                portfolio_orm.portfolio_rho = portfolio.portfolio_greeks.rho
            
            # Flush - DON'T call self.update()
            self.session.flush()
            
            # Return domain model
            return self.to_domain(portfolio_orm)
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating portfolio {portfolio.id}: {e}")
            return None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating portfolio {portfolio.id}: {e}")
            return None
    
    def to_domain(self, portfolio_orm: PortfolioORM) -> dm.Portfolio:
        """Convert ORM to domain model"""
        # Convert Greeks
        greeks = None
        if portfolio_orm.portfolio_delta is not None:
            greeks = dm.Greeks(
                delta=portfolio_orm.portfolio_delta,
                gamma=portfolio_orm.portfolio_gamma or 0,
                theta=portfolio_orm.portfolio_theta or 0,
                vega=portfolio_orm.portfolio_vega or 0,
                rho=portfolio_orm.portfolio_rho or 0
            )
        
        return dm.Portfolio(
            id=portfolio_orm.id,
            name=portfolio_orm.name,
            broker=portfolio_orm.broker,
            account_id=portfolio_orm.account_id,
            cash_balance=portfolio_orm.cash_balance,
            buying_power=portfolio_orm.buying_power,
            portfolio_greeks=greeks,
            total_equity=portfolio_orm.total_equity,
            total_pnl=portfolio_orm.total_pnl,
            daily_pnl=portfolio_orm.daily_pnl,
            last_updated=portfolio_orm.last_updated,
            created_at=portfolio_orm.created_at
        )