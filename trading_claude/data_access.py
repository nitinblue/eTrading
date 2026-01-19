# ============================================================================
# REPOSITORY LAYER - Data Access Objects
# ============================================================================

from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import data_model as dm
# Assume imports from previous artifacts
# from core_models import *
# from database_models import *


class BaseRepository:
    """Base repository with common operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def commit(self):
        """Commit changes to database"""
        self.session.commit()
    
    def rollback(self):
        """Rollback changes"""
        self.session.rollback()


class PortfolioRepository(BaseRepository):
    """Repository for Portfolio operations"""
    
    def create(self, portfolio: dm.Portfolio) -> dm.Portfolio:
        """Create new portfolio"""
        portfolio_orm = self._to_orm(portfolio)
        self.session.add(portfolio_orm)
        self.commit()
        return self._to_model(portfolio_orm)
    
    def get_by_id(self, portfolio_id: str) -> Optional[dm.Portfolio]:
        """Get portfolio by ID"""
        portfolio_orm = self.session.query(PortfolioORM).filter_by(id=portfolio_id).first()
        return self._to_model(portfolio_orm) if portfolio_orm else None
    
    def get_by_account(self, broker: str, account_id: str) -> Optional[dm.Portfolio]:
        """Get portfolio by broker and account ID"""
        portfolio_orm = self.session.query(PortfolioORM).filter_by(
            broker=broker, 
            account_id=account_id
        ).first()
        return self._to_model(portfolio_orm) if portfolio_orm else None
    
    def get_all(self) -> List[dm.Portfolio]:
        """Get all portfolios"""
        portfolios_orm = self.session.query(dm.PortfolioORM).all()
        return [self._to_model(p) for p in portfolios_orm]
    
    def update(self, portfolio: dm.Portfolio) -> dm.Portfolio:
        """Update portfolio"""
        portfolio_orm = self.session.query(dm.PortfolioORM).filter_by(id=portfolio.id).first()
        if portfolio_orm:
            self._update_orm(portfolio_orm, portfolio)
            self.commit()
            return self._to_model(portfolio_orm)
        return None
    
    def delete(self, portfolio_id: str) -> bool:
        """Delete portfolio"""
        portfolio_orm = self.session.query(dm.PortfolioORM).filter_by(id=portfolio_id).first()
        if portfolio_orm:
            self.session.delete(portfolio_orm)
            self.commit()
            return True
        return False
    
    def _to_orm(self, portfolio: dm.Portfolio) -> dm.PortfolioORM:
        """Convert domain model to ORM"""
        return dm.PortfolioORM(
            id=portfolio.id,
            name=portfolio.name,
            broker=portfolio.broker,
            account_id=portfolio.account_id,
            cash_balance=portfolio.cash_balance,
            buying_power=portfolio.buying_power,
            portfolio_delta=portfolio.portfolio_delta,
            portfolio_gamma=portfolio.portfolio_gamma,
            portfolio_theta=portfolio.portfolio_theta,
            portfolio_vega=portfolio.portfolio_vega,
            total_equity=portfolio.total_equity,
            total_pnl=portfolio.total_pnl,
            last_updated=portfolio.last_updated
        )
    
    def _to_model(self, portfolio_orm: dm.PortfolioORM) -> dm.Portfolio:
        """Convert ORM to domain model"""
        portfolio = dm.Portfolio(
            id=portfolio_orm.id,
            name=portfolio_orm.name,
            broker=portfolio_orm.broker,
            account_id=portfolio_orm.account_id,
            cash_balance=portfolio_orm.cash_balance,
            buying_power=portfolio_orm.buying_power,
            portfolio_delta=portfolio_orm.portfolio_delta,
            portfolio_gamma=portfolio_orm.portfolio_gamma,
            portfolio_theta=portfolio_orm.portfolio_theta,
            portfolio_vega=portfolio_orm.portfolio_vega,
            total_equity=portfolio_orm.total_equity,
            total_pnl=portfolio_orm.total_pnl,
            last_updated=portfolio_orm.last_updated
        )
        return portfolio
    
    def _update_orm(self, portfolio_orm: dm.PortfolioORM, portfolio: dm.Portfolio):
        """Update ORM from domain model"""
        portfolio_orm.name = portfolio.name
        portfolio_orm.cash_balance = portfolio.cash_balance
        portfolio_orm.buying_power = portfolio.buying_power
        portfolio_orm.portfolio_delta = portfolio.portfolio_delta
        portfolio_orm.portfolio_gamma = portfolio.portfolio_gamma
        portfolio_orm.portfolio_theta = portfolio.portfolio_theta
        portfolio_orm.portfolio_vega = portfolio.portfolio_vega
        portfolio_orm.total_equity = portfolio.total_equity
        portfolio_orm.total_pnl = portfolio.total_pnl
        portfolio_orm.last_updated = datetime.utcnow()


class TradeRepository(BaseRepository):
    """Repository for Trade operations"""
    
    def create(self, trade: dm.Trade, portfolio_id: str) -> dm.Trade:
        """Create new trade"""
        # First create/get symbols
        symbol_repo = SymbolRepository(self.session)
        
        # Create legs
        legs_orm = []
        for leg in trade.legs:
            symbol_orm = symbol_repo.get_or_create(leg.symbol)
            leg_orm = dm.LegORM(
                id=leg.id,
                symbol_id=symbol_orm.id,
                quantity=leg.quantity,
                side=leg.side,
                entry_price=leg.entry_price,
                entry_time=leg.entry_time,
                exit_price=leg.exit_price,
                exit_time=leg.exit_time,
                current_price=leg.current_price,
                broker_leg_id=leg.broker_leg_id,
                fees=leg.fees
            )
            legs_orm.append(leg_orm)
        
        # Create strategy if exists
        strategy_orm = None
        if trade.strategy:
            strategy_repo = StrategyRepository(self.session)
            strategy_orm = strategy_repo.get_or_create(trade.strategy)
        
        # Create trade
        trade_orm = dm.TradeORM(
            id=trade.id,
            portfolio_id=portfolio_id,
            strategy_id=strategy_orm.id if strategy_orm else None,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
            underlying_symbol=trade.underlying_symbol,
            planned_entry=trade.planned_entry,
            planned_exit=trade.planned_exit,
            stop_loss=trade.stop_loss,
            is_open=trade.is_open,
            notes=trade.notes,
            tags=trade.tags,
            broker_trade_id=trade.broker_trade_id
        )
        
        self.session.add(trade_orm)
        for leg_orm in legs_orm:
            leg_orm.trade_id = trade_orm.id
            self.session.add(leg_orm)
        
        self.commit()
        return self._to_model(trade_orm)
    
    def get_by_id(self, trade_id: str) -> Optional[dm.Trade]:
        """Get trade by ID"""
        trade_orm = self.session.query(dm.TradeORM).filter_by(id=trade_id).first()
        return self._to_model(trade_orm) if trade_orm else None
    
    def get_by_portfolio(self, portfolio_id: str, open_only: bool = False) -> List[dm.Trade]:
        """Get all trades for a portfolio"""
        query = self.session.query(dm.TradeORM).filter_by(portfolio_id=portfolio_id)
        if open_only:
            query = query.filter_by(is_open=True)
        trades_orm = query.order_by(desc(dm.TradeORM.opened_at)).all()
        return [self._to_model(t) for t in trades_orm]
    
    def get_by_underlying(self, underlying: str, portfolio_id: Optional[str] = None) -> List[dm.Trade]:
        """Get trades by underlying symbol"""
        query = self.session.query(dm.TradeORM).filter_by(underlying_symbol=underlying)
        if portfolio_id:
            query = query.filter_by(portfolio_id=portfolio_id)
        trades_orm = query.all()
        return [self._to_model(t) for t in trades_orm]
    
    def update(self, trade: dm.Trade) -> dm.Trade:
        """Update trade"""
        trade_orm = self.session.query(dm.TradeORM).filter_by(id=trade.id).first()
        if trade_orm:
            self._update_orm(trade_orm, trade)
            self.commit()
            return self._to_model(trade_orm)
        return None
    
    def close_trade(self, trade_id: str) -> bool:
        """Mark trade as closed"""
        trade_orm = self.session.query(dm.TradeORM).filter_by(id=trade_id).first()
        if trade_orm:
            trade_orm.is_open = False
            trade_orm.closed_at = datetime.utcnow()
            self.commit()
            return True
        return False
    
    def _to_model(self, trade_orm: dm.TradeORM) -> dm.Trade:
        """Convert ORM to domain model"""
        # Load legs
        legs = []
        for leg_orm in trade_orm.legs:
            symbol = dm.Symbol(
                ticker=leg_orm.symbol.ticker,
                asset_type=leg_orm.symbol.asset_type,
                option_type=leg_orm.symbol.option_type,
                strike=leg_orm.symbol.strike,
                expiration=leg_orm.symbol.expiration,
                multiplier=leg_orm.symbol.multiplier
            )
            
            leg = dm.Leg(
                id=leg_orm.id,
                symbol=symbol,
                quantity=leg_orm.quantity,
                side=leg_orm.side,
                entry_price=leg_orm.entry_price,
                entry_time=leg_orm.entry_time,
                exit_price=leg_orm.exit_price,
                exit_time=leg_orm.exit_time,
                current_price=leg_orm.current_price,
                broker_leg_id=leg_orm.broker_leg_id,
                fees=leg_orm.fees
            )
            legs.append(leg)
        
        # Load strategy if exists
        strategy = None
        if trade_orm.strategy:
            strategy = dm.Strategy(
                id=trade_orm.strategy.id,
                name=trade_orm.strategy.name,
                strategy_type=trade_orm.strategy.strategy_type,
                max_profit=trade_orm.strategy.max_profit,
                max_loss=trade_orm.strategy.max_loss,
                breakeven_points=trade_orm.strategy.breakeven_points or [],
                delta=trade_orm.strategy.delta,
                gamma=trade_orm.strategy.gamma,
                theta=trade_orm.strategy.theta,
                vega=trade_orm.strategy.vega
            )
        
        trade = dm.Trade(
            id=trade_orm.id,
            legs=legs,
            strategy=strategy,
            opened_at=trade_orm.opened_at,
            closed_at=trade_orm.closed_at,
            underlying_symbol=trade_orm.underlying_symbol,
            planned_entry=trade_orm.planned_entry,
            planned_exit=trade_orm.planned_exit,
            stop_loss=trade_orm.stop_loss,
            is_open=trade_orm.is_open,
            notes=trade_orm.notes,
            tags=trade_orm.tags or [],
            broker_trade_id=trade_orm.broker_trade_id
        )
        
        return trade
    
    def _update_orm(self, trade_orm: dm.TradeORM, trade: dm.Trade):
        """Update ORM from domain model"""
        trade_orm.closed_at = trade.closed_at
        trade_orm.planned_entry = trade.planned_entry
        trade_orm.planned_exit = trade.planned_exit
        trade_orm.stop_loss = trade.stop_loss
        trade_orm.is_open = trade.is_open
        trade_orm.notes = trade.notes
        trade_orm.tags = trade.tags


class PositionRepository(BaseRepository):
    """Repository for Position operations"""
    
    def create(self, position: dm.Position, portfolio_id: str) -> dm.Position:
        """Create new position"""
        symbol_repo = SymbolRepository(self.session)
        symbol_orm = symbol_repo.get_or_create(position.symbol)
        
        position_orm = dm.PositionORM(
            id=position.id,
            portfolio_id=portfolio_id,
            symbol_id=symbol_orm.id,
            quantity=position.quantity,
            average_price=position.average_price,
            total_cost=position.total_cost,
            current_price=position.current_price,
            market_value=position.market_value,
            trade_ids=position.trade_ids,
            delta=position.delta,
            gamma=position.gamma,
            theta=position.theta,
            vega=position.vega,
            broker_position_id=position.broker_position_id
        )
        
        self.session.add(position_orm)
        self.commit()
        return self._to_model(position_orm)
    
    def get_by_portfolio(self, portfolio_id: str) -> List[dm.Position]:
        """Get all positions for portfolio"""
        positions_orm = self.session.query(dm.PositionORM).filter_by(
            portfolio_id=portfolio_id
        ).all()
        return [self._to_model(p) for p in positions_orm]
    
    def get_by_symbol(self, portfolio_id: str, ticker: str) -> List[dm.Position]:
        """Get positions by symbol"""
        positions_orm = self.session.query(dm.PositionORM).join(dm.SymbolORM).filter(
            and_(
                dm.PositionORM.portfolio_id == portfolio_id,
                dm.SymbolORM.ticker == ticker
            )
        ).all()
        return [self._to_model(p) for p in positions_orm]
    
    def update(self, position: dm.Position) -> dm.Position:
        """Update position"""
        position_orm = self.session.query(dm.PositionORM).filter_by(id=position.id).first()
        if position_orm:
            self._update_orm(position_orm, position)
            self.commit()
            return self._to_model(position_orm)
        return None
    
    def delete(self, position_id: str) -> bool:
        """Delete position"""
        position_orm = self.session.query(dm.PositionORM).filter_by(id=position_id).first()
        if position_orm:
            self.session.delete(position_orm)
            self.commit()
            return True
        return False
    
    def _to_model(self, position_orm: dm.PositionORM) -> dm.Position:
        """Convert ORM to domain model"""
        symbol = dm.Symbol(
            ticker=position_orm.symbol.ticker,
            asset_type=position_orm.symbol.asset_type,
            option_type=position_orm.symbol.option_type,
            strike=position_orm.symbol.strike,
            expiration=position_orm.symbol.expiration,
            multiplier=position_orm.symbol.multiplier
        )
        
        return dm.Position(
            id=position_orm.id,
            symbol=symbol,
            quantity=position_orm.quantity,
            average_price=position_orm.average_price,
            total_cost=position_orm.total_cost,
            current_price=position_orm.current_price,
            market_value=position_orm.market_value,
            trade_ids=position_orm.trade_ids or [],
            delta=position_orm.delta,
            gamma=position_orm.gamma,
            theta=position_orm.theta,
            vega=position_orm.vega,
            broker_position_id=position_orm.broker_position_id
        )
    
    def _update_orm(self, position_orm: dm.PositionORM, position: dm.Position):
        """Update ORM from domain model"""
        position_orm.quantity = position.quantity
        position_orm.average_price = position.average_price
        position_orm.total_cost = position.total_cost
        position_orm.current_price = position.current_price
        position_orm.market_value = position.market_value
        position_orm.trade_ids = position.trade_ids
        position_orm.delta = position.delta
        position_orm.gamma = position.gamma
        position_orm.theta = position.theta
        position_orm.vega = position.vega


class OrderRepository(BaseRepository):
    """Repository for Order operations"""
    
    def create(self, order: dm.Order, portfolio_id: str) -> dm.Order:
        """Create new order"""
        # Create legs
        legs_orm = []
        symbol_repo = SymbolRepository(self.session)
        
        for leg in order.legs:
            symbol_orm = symbol_repo.get_or_create(leg.symbol)
            leg_orm = dm.LegORM(
                id=leg.id,
                symbol_id=symbol_orm.id,
                quantity=leg.quantity,
                side=leg.side,
                broker_leg_id=leg.broker_leg_id,
                fees=leg.fees
            )
            legs_orm.append(leg_orm)
        
        order_orm = dm.OrderORM(
            id=order.id,
            portfolio_id=portfolio_id,
            trade_id=order.trade_id,
            order_type=order.order_type,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            status=order.status,
            created_at=order.created_at,
            filled_at=order.filled_at,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
            time_in_force=order.time_in_force,
            broker_order_id=order.broker_order_id
        )
        
        self.session.add(order_orm)
        for leg_orm in legs_orm:
            leg_orm.order_id = order_orm.id
            self.session.add(leg_orm)
        
        self.commit()
        return self._to_model(order_orm)
    
    def get_by_portfolio(self, portfolio_id: str, status: Optional[dm.OrderStatus] = None) -> List[dm.Order]:
        """Get orders for portfolio"""
        query = self.session.query(dm.OrderORM).filter_by(portfolio_id=portfolio_id)
        if status:
            query = query.filter_by(status=status)
        orders_orm = query.order_by(desc(dm.OrderORM.created_at)).all()
        return [self._to_model(o) for o in orders_orm]
    
    def update_status(self, order_id: str, status: dm.OrderStatus, 
                     filled_quantity: Optional[int] = None,
                     average_fill_price: Optional[Decimal] = None) -> bool:
        """Update order status"""
        order_orm = self.session.query(dm.OrderORM).filter_by(id=order_id).first()
        if order_orm:
            order_orm.status = status
            if filled_quantity is not None:
                order_orm.filled_quantity = filled_quantity
            if average_fill_price is not None:
                order_orm.average_fill_price = average_fill_price
            if status == dm.OrderStatus.FILLED:
                order_orm.filled_at = datetime.utcnow()
            self.commit()
            return True
        return False
    
    def _to_model(self, order_orm: dm.OrderORM) -> dm.Order:
        """Convert ORM to domain model"""
        legs = []
        for leg_orm in order_orm.legs:
            symbol = dm.Symbol(
                ticker=leg_orm.symbol.ticker,
                asset_type=leg_orm.symbol.asset_type,
                option_type=leg_orm.symbol.option_type,
                strike=leg_orm.symbol.strike,
                expiration=leg_orm.symbol.expiration,
                multiplier=leg_orm.symbol.multiplier
            )
            
            leg = dm.Leg(
                id=leg_orm.id,
                symbol=symbol,
                quantity=leg_orm.quantity,
                side=leg_orm.side,
                broker_leg_id=leg_orm.broker_leg_id,
                fees=leg_orm.fees
            )
            legs.append(leg)
        
        return dm.Order(
            id=order_orm.id,
            legs=legs,
            order_type=order_orm.order_type,
            limit_price=order_orm.limit_price,
            stop_price=order_orm.stop_price,
            status=order_orm.status,
            created_at=order_orm.created_at,
            filled_at=order_orm.filled_at,
            filled_quantity=order_orm.filled_quantity,
            average_fill_price=order_orm.average_fill_price,
            time_in_force=order_orm.time_in_force,
            broker_order_id=order_orm.broker_order_id,
            trade_id=order_orm.trade_id
        )


class SymbolRepository(BaseRepository):
    """Repository for Symbol operations"""
    
    def get_or_create(self, symbol: dm.Symbol) -> dm.SymbolORM:
        """Get existing symbol or create new one"""
        # Try to find existing
        query = self.session.query(dm.SymbolORM).filter_by(
            ticker=symbol.ticker,
            asset_type=symbol.asset_type
        )
        
        if symbol.asset_type == dm.AssetType.OPTION:
            query = query.filter_by(
                option_type=symbol.option_type,
                strike=symbol.strike,
                expiration=symbol.expiration
            )
        
        symbol_orm = query.first()
        
        if symbol_orm:
            return symbol_orm
        
        # Create new
        symbol_orm = dm.SymbolORM(
            id=str(dm.uuid.uuid4()),
            ticker=symbol.ticker,
            asset_type=symbol.asset_type,
            option_type=symbol.option_type,
            strike=symbol.strike,
            expiration=symbol.expiration,
            description=symbol.description,
            multiplier=symbol.multiplier
        )
        
        self.session.add(symbol_orm)
        return symbol_orm


class StrategyRepository(BaseRepository):
    """Repository for Strategy operations"""
    
    def get_or_create(self, strategy: dm.Strategy) -> dm.StrategyORM:
        """Get existing strategy or create new one"""
        strategy_orm = self.session.query(dm.StrategyORM).filter_by(
            name=strategy.name,
            strategy_type=strategy.strategy_type
        ).first()
        
        if strategy_orm:
            return strategy_orm
        
        strategy_orm = dm.StrategyORM(
            id=strategy.id,
            name=strategy.name,
            strategy_type=strategy.strategy_type,
            max_profit=strategy.max_profit,
            max_loss=strategy.max_loss,
            breakeven_points=strategy.breakeven_points,
            delta=strategy.delta,
            gamma=strategy.gamma,
            theta=strategy.theta,
            vega=strategy.vega,
            description=strategy.description
        )
        
        self.session.add(strategy_orm)
        return strategy_orm