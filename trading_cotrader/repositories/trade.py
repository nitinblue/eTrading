"""
Trade Repository - Data access for trades and legs

Updated for enhanced domain.py with:
- TradeType, TradeStatus enums
- Entry/current/exit state tracking
- P&L attribution fields
- Lifecycle methods
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging

from trading_cotrader.repositories.position import SymbolRepository
from trading_cotrader.repositories.base import BaseRepository
from trading_cotrader.core.database.schema import TradeORM, LegORM, StrategyORM
import trading_cotrader.core.models.domain as dm

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
            
            # Handle field mapping between enhanced domain and ORM
            # Enhanced domain uses: created_at, trade_type, trade_status
            # ORM uses: opened_at, trade_type, trade_status
            
            # Get opened_at - try multiple field names for compatibility
            opened_at = getattr(trade, 'created_at', None) or getattr(trade, 'opened_at', None) or datetime.utcnow()
            
            # Get trade_type and trade_status
            trade_type = 'real'
            if hasattr(trade, 'trade_type') and trade.trade_type:
                trade_type = trade.trade_type.value if hasattr(trade.trade_type, 'value') else str(trade.trade_type)
            
            trade_status = 'intent'
            if hasattr(trade, 'trade_status') and trade.trade_status:
                trade_status = trade.trade_status.value if hasattr(trade.trade_status, 'value') else str(trade.trade_status)
            
            # Compute is_open from trade_status (never from domain property/field)
            is_open = trade_status in ('executed', 'partial')
            
            # Create trade ORM
            trade_orm = TradeORM(
                id=trade.id,
                portfolio_id=portfolio_id,
                strategy_id=strategy_id,
                underlying_symbol=trade.underlying_symbol,
                
                # Type and status
                trade_type=trade_type,
                trade_status=trade_status,
                
                # Timestamps
                opened_at=opened_at,
                created_at=getattr(trade, 'created_at', None) or datetime.utcnow(),
                intent_at=getattr(trade, 'intent_at', None),
                evaluated_at=getattr(trade, 'evaluated_at', None),
                submitted_at=getattr(trade, 'submitted_at', None),
                executed_at=getattr(trade, 'executed_at', None),
                closed_at=getattr(trade, 'closed_at', None),
                
                # Entry state
                entry_price=getattr(trade, 'entry_price', None),
                entry_underlying_price=getattr(trade, 'entry_underlying_price', None),
                entry_iv=getattr(trade, 'entry_iv', None),
                
                # Entry Greeks
                entry_delta=self._get_greek(trade, 'entry_greeks', 'delta'),
                entry_gamma=self._get_greek(trade, 'entry_greeks', 'gamma'),
                entry_theta=self._get_greek(trade, 'entry_greeks', 'theta'),
                entry_vega=self._get_greek(trade, 'entry_greeks', 'vega'),
                
                # Current state
                current_price=getattr(trade, 'current_price', None),
                current_underlying_price=getattr(trade, 'current_underlying_price', None),
                current_iv=getattr(trade, 'current_iv', None),
                
                # Current Greeks
                current_delta=self._get_greek(trade, 'current_greeks', 'delta'),
                current_gamma=self._get_greek(trade, 'current_greeks', 'gamma'),
                current_theta=self._get_greek(trade, 'current_greeks', 'theta'),
                current_vega=self._get_greek(trade, 'current_greeks', 'vega'),
                
                # Exit state
                exit_price=getattr(trade, 'exit_price', None),
                exit_reason=getattr(trade, 'exit_reason', None),
                
                # Risk management
                planned_entry=getattr(trade, 'planned_entry', None),
                stop_loss=getattr(trade, 'stop_loss', None),
                profit_target=getattr(trade, 'profit_target', None),
                max_risk=getattr(trade, 'max_risk', None),
                
                # Execution tracking
                actual_entry=getattr(trade, 'actual_entry', None),
                actual_exit=getattr(trade, 'actual_exit', None),
                slippage=getattr(trade, 'slippage', None),
                
                # Linkage
                intent_trade_id=getattr(trade, 'intent_trade_id', None),
                executed_trade_id=getattr(trade, 'executed_trade_id', None),
                rolled_from_id=getattr(trade, 'rolled_from_id', None),
                rolled_to_id=getattr(trade, 'rolled_to_id', None),
                
                # Source tracking
                trade_source=self._get_trade_source(trade),
                recommendation_id=getattr(trade, 'recommendation_id', None),

                # State
                is_open=is_open,
                notes=getattr(trade, 'notes', ''),
                tags=getattr(trade, 'tags', []) or [],
                
                # Broker mapping
                broker_trade_id=getattr(trade, 'broker_trade_id', None),
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
    
    def _get_trade_source(self, trade) -> str:
        """Extract trade_source value as a string."""
        source = getattr(trade, 'trade_source', None)
        if source is None:
            return 'manual'
        if hasattr(source, 'value'):
            return source.value
        return str(source)

    def _get_greek(self, trade, greeks_attr: str, greek_name: str):
        """Safely get a Greek value from a trade's Greeks object"""
        greeks = getattr(trade, greeks_attr, None)
        if greeks:
            return getattr(greeks, greek_name, None)
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
    
    def get_by_type(self, trade_type: str, portfolio_id: Optional[str] = None) -> List[dm.Trade]:
        """Get trades by type (real, paper, what_if, etc.)"""
        try:
            query = self.session.query(TradeORM).filter_by(trade_type=trade_type)
            
            if portfolio_id:
                query = query.filter_by(portfolio_id=portfolio_id)
            
            trades_orm = query.all()
            return [self.to_domain(t) for t in trades_orm]
            
        except Exception as e:
            logger.error(f"Error getting trades by type {trade_type}: {e}")
            return []
    
    def get_by_status(self, trade_status: str, portfolio_id: Optional[str] = None) -> List[dm.Trade]:
        """Get trades by status (intent, pending, executed, closed, etc.)"""
        try:
            query = self.session.query(TradeORM).filter_by(trade_status=trade_status)
            
            if portfolio_id:
                query = query.filter_by(portfolio_id=portfolio_id)
            
            trades_orm = query.all()
            return [self.to_domain(t) for t in trades_orm]
            
        except Exception as e:
            logger.error(f"Error getting trades by status {trade_status}: {e}")
            return []
    
    def update_from_domain(self, trade: dm.Trade) -> Optional[dm.Trade]:
        """Update trade from domain model"""
        try:
            trade_orm = self.get_by_id(trade.id)
            if not trade_orm:
                logger.error(f"Trade {trade.id} not found for update")
                return None
            
            # Update type and status
            if hasattr(trade, 'trade_type') and trade.trade_type:
                trade_orm.trade_type = trade.trade_type.value if hasattr(trade.trade_type, 'value') else str(trade.trade_type)
            
            if hasattr(trade, 'trade_status') and trade.trade_status:
                trade_orm.trade_status = trade.trade_status.value if hasattr(trade.trade_status, 'value') else str(trade.trade_status)
            
            # Update timestamps
            trade_orm.evaluated_at = getattr(trade, 'evaluated_at', trade_orm.evaluated_at)
            trade_orm.submitted_at = getattr(trade, 'submitted_at', trade_orm.submitted_at)
            trade_orm.executed_at = getattr(trade, 'executed_at', trade_orm.executed_at)
            trade_orm.closed_at = getattr(trade, 'closed_at', trade_orm.closed_at)
            
            # Update entry state
            trade_orm.entry_price = getattr(trade, 'entry_price', trade_orm.entry_price)
            trade_orm.entry_underlying_price = getattr(trade, 'entry_underlying_price', trade_orm.entry_underlying_price)
            trade_orm.entry_iv = getattr(trade, 'entry_iv', trade_orm.entry_iv)
            
            # Update current state
            trade_orm.current_price = getattr(trade, 'current_price', trade_orm.current_price)
            trade_orm.current_underlying_price = getattr(trade, 'current_underlying_price', trade_orm.current_underlying_price)
            trade_orm.current_iv = getattr(trade, 'current_iv', trade_orm.current_iv)
            
            # Update exit state
            trade_orm.exit_price = getattr(trade, 'exit_price', trade_orm.exit_price)
            trade_orm.exit_reason = getattr(trade, 'exit_reason', trade_orm.exit_reason)
            
            # Update risk management
            trade_orm.planned_entry = getattr(trade, 'planned_entry', trade_orm.planned_entry)
            trade_orm.stop_loss = getattr(trade, 'stop_loss', trade_orm.stop_loss)
            trade_orm.profit_target = getattr(trade, 'profit_target', trade_orm.profit_target)
            
            # Update execution
            trade_orm.actual_entry = getattr(trade, 'actual_entry', trade_orm.actual_entry)
            trade_orm.actual_exit = getattr(trade, 'actual_exit', trade_orm.actual_exit)
            trade_orm.slippage = getattr(trade, 'slippage', trade_orm.slippage)
            
            # Compute is_open from trade_status (always derived, never from domain)
            trade_orm.is_open = trade_orm.trade_status in ('executed', 'partial')
            
            # Update metadata
            trade_orm.notes = getattr(trade, 'notes', trade_orm.notes)
            trade_orm.tags = getattr(trade, 'tags', trade_orm.tags)
            trade_orm.last_updated = datetime.utcnow()
            
            updated = self.update(trade_orm)
            return self.to_domain(updated) if updated else None
            
        except Exception as e:
            self.rollback()
            logger.error(f"Error updating trade {trade.id}: {e}")
            return None
    
    def close_trade(self, trade_id: str, exit_price=None, exit_reason: str = None) -> bool:
        """Mark trade as closed"""
        try:
            trade_orm = self.get_by_id(trade_id)
            if not trade_orm:
                return False
            
            trade_orm.is_open = False
            trade_orm.trade_status = 'closed'
            trade_orm.closed_at = datetime.utcnow()
            trade_orm.exit_price = exit_price
            trade_orm.exit_reason = exit_reason
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
            
            # Get side value
            side_value = leg.side.value if leg.side and hasattr(leg.side, 'value') else str(leg.side) if leg.side else 'buy'
            
            leg_orm = LegORM(
                id=leg.id,
                trade_id=trade_id,
                symbol_id=symbol_orm.id,
                quantity=leg.quantity,
                side=side_value,
                
                # Entry state
                entry_price=leg.entry_price,
                entry_time=leg.entry_time,
                entry_underlying_price=getattr(leg, 'entry_underlying_price', None),
                entry_iv=getattr(leg, 'entry_iv', None),
                
                # Exit state
                exit_price=leg.exit_price,
                exit_time=leg.exit_time,
                
                # Current state
                current_price=leg.current_price,
                current_underlying_price=getattr(leg, 'current_underlying_price', None),
                current_iv=getattr(leg, 'current_iv', None),
                
                # Costs
                fees=leg.fees,
                commission=leg.commission,
                broker_leg_id=leg.broker_leg_id
            )
            
            # Add entry Greeks if available
            entry_greeks = getattr(leg, 'entry_greeks', None)
            if entry_greeks:
                leg_orm.entry_delta = getattr(entry_greeks, 'delta', None)
                leg_orm.entry_gamma = getattr(entry_greeks, 'gamma', None)
                leg_orm.entry_theta = getattr(entry_greeks, 'theta', None)
                leg_orm.entry_vega = getattr(entry_greeks, 'vega', None)
            
            # Add current Greeks - check both 'greeks' and 'current_greeks'
            current_greeks = getattr(leg, 'current_greeks', None) or getattr(leg, 'greeks', None)
            if current_greeks:
                leg_orm.delta = getattr(current_greeks, 'delta', None)
                leg_orm.gamma = getattr(current_greeks, 'gamma', None)
                leg_orm.theta = getattr(current_greeks, 'theta', None)
                leg_orm.vega = getattr(current_greeks, 'vega', None)
            
            return leg_orm
            
        except Exception as e:
            logger.error(f"Error creating leg ORM: {e}")
            logger.exception("Full trace:")
            return None
    
    def to_domain(self, trade_orm: TradeORM) -> dm.Trade:
        """Convert ORM to domain model"""
        # Convert legs
        legs = []
        for leg_orm in trade_orm.legs:
            symbol = self.symbol_repo.to_domain(leg_orm.symbol)
            
            # Build entry Greeks
            entry_greeks = None
            if hasattr(leg_orm, 'entry_delta') and leg_orm.entry_delta is not None:
                entry_greeks = dm.Greeks(
                    delta=leg_orm.entry_delta or 0,
                    gamma=leg_orm.entry_gamma or 0,
                    theta=leg_orm.entry_theta or 0,
                    vega=leg_orm.entry_vega or 0
                )
            
            # Build current Greeks
            current_greeks = None
            if leg_orm.delta is not None:
                current_greeks = dm.Greeks(
                    delta=leg_orm.delta or 0,
                    gamma=leg_orm.gamma or 0,
                    theta=leg_orm.theta or 0,
                    vega=leg_orm.vega or 0
                )
            
            # Build leg - use enhanced fields if available
            leg_kwargs = dict(
                id=leg_orm.id,
                symbol=symbol,
                quantity=leg_orm.quantity,
                side=dm.OrderSide(leg_orm.side) if leg_orm.side else None,
                entry_price=leg_orm.entry_price,
                entry_time=leg_orm.entry_time,
                exit_price=leg_orm.exit_price,
                exit_time=leg_orm.exit_time,
                current_price=leg_orm.current_price,
                broker_leg_id=leg_orm.broker_leg_id,
                fees=leg_orm.fees or 0,
                commission=leg_orm.commission or 0
            )
            
            # Add enhanced fields if they exist in domain
            if hasattr(dm.Leg, 'entry_greeks'):
                leg_kwargs['entry_greeks'] = entry_greeks
                leg_kwargs['current_greeks'] = current_greeks
                leg_kwargs['entry_underlying_price'] = getattr(leg_orm, 'entry_underlying_price', None)
                leg_kwargs['entry_iv'] = getattr(leg_orm, 'entry_iv', None)
                leg_kwargs['current_underlying_price'] = getattr(leg_orm, 'current_underlying_price', None)
                leg_kwargs['current_iv'] = getattr(leg_orm, 'current_iv', None)
            else:
                # Old domain - use 'greeks' field
                leg_kwargs['greeks'] = current_greeks
            
            leg = dm.Leg(**leg_kwargs)
            legs.append(leg)
        
        # Convert strategy
        strategy = None
        if trade_orm.strategy:
            strategy = self.strategy_repo.to_domain(trade_orm.strategy)
        
        # Build trade kwargs - handle both old and new domain
        trade_kwargs = dict(
            id=trade_orm.id,
            legs=legs,
            strategy=strategy,
            underlying_symbol=trade_orm.underlying_symbol,
            closed_at=trade_orm.closed_at,
            planned_entry=trade_orm.planned_entry,
            stop_loss=trade_orm.stop_loss,
            profit_target=trade_orm.profit_target,
            notes=trade_orm.notes or '',
            tags=trade_orm.tags or [],
            broker_trade_id=trade_orm.broker_trade_id
        )
        
        # is_open is a @property on the domain Trade (computed from trade_status)
        # — never pass it as a kwarg

        # Add enhanced fields if available in domain
        if hasattr(dm.Trade, 'trade_type'):
            # Enhanced domain
            trade_type = dm.TradeType.REAL
            if trade_orm.trade_type:
                try:
                    trade_type = dm.TradeType(trade_orm.trade_type)
                except ValueError:
                    trade_type = dm.TradeType.REAL
            trade_kwargs['trade_type'] = trade_type
        
        if hasattr(dm.Trade, 'trade_status'):
            trade_status = dm.TradeStatus.INTENT
            if trade_orm.trade_status:
                try:
                    trade_status = dm.TradeStatus(trade_orm.trade_status)
                except ValueError:
                    trade_status = dm.TradeStatus.INTENT
            trade_kwargs['trade_status'] = trade_status
        
        if hasattr(dm.Trade, 'created_at'):
            trade_kwargs['created_at'] = trade_orm.created_at or trade_orm.opened_at
        
        if hasattr(dm.Trade, 'opened_at'):
            trade_kwargs['opened_at'] = trade_orm.opened_at
        
        # Add timestamp fields
        for field in ['intent_at', 'evaluated_at', 'submitted_at', 'executed_at']:
            if hasattr(dm.Trade, field):
                trade_kwargs[field] = getattr(trade_orm, field, None)
        
        # Add entry/current/exit state
        for field in ['entry_price', 'entry_underlying_price', 'entry_iv',
                      'current_price', 'current_underlying_price', 'current_iv',
                      'exit_price', 'exit_reason']:
            if hasattr(dm.Trade, field):
                trade_kwargs[field] = getattr(trade_orm, field, None)
        
        # Add execution tracking
        for field in ['actual_entry', 'actual_exit', 'slippage', 'max_risk']:
            if hasattr(dm.Trade, field):
                trade_kwargs[field] = getattr(trade_orm, field, None)
        
        # Add linkage fields
        for field in ['intent_trade_id', 'executed_trade_id', 'rolled_from_id', 'rolled_to_id', 'portfolio_id']:
            if hasattr(dm.Trade, field):
                trade_kwargs[field] = getattr(trade_orm, field, None)

        # Add source tracking
        if hasattr(dm.Trade, 'trade_source') and hasattr(trade_orm, 'trade_source'):
            source_val = getattr(trade_orm, 'trade_source', 'manual') or 'manual'
            try:
                trade_kwargs['trade_source'] = dm.TradeSource(source_val)
            except (ValueError, AttributeError):
                trade_kwargs['trade_source'] = dm.TradeSource.MANUAL
        if hasattr(dm.Trade, 'recommendation_id') and hasattr(trade_orm, 'recommendation_id'):
            trade_kwargs['recommendation_id'] = getattr(trade_orm, 'recommendation_id', None)
        
        # Build entry Greeks if available
        if hasattr(dm.Trade, 'entry_greeks') and hasattr(trade_orm, 'entry_delta'):
            if trade_orm.entry_delta is not None:
                trade_kwargs['entry_greeks'] = dm.Greeks(
                    delta=trade_orm.entry_delta or 0,
                    gamma=trade_orm.entry_gamma or 0,
                    theta=trade_orm.entry_theta or 0,
                    vega=trade_orm.entry_vega or 0
                )
        
        # Build current Greeks if available
        if hasattr(dm.Trade, 'current_greeks') and hasattr(trade_orm, 'current_delta'):
            if trade_orm.current_delta is not None:
                trade_kwargs['current_greeks'] = dm.Greeks(
                    delta=trade_orm.current_delta or 0,
                    gamma=trade_orm.current_gamma or 0,
                    theta=trade_orm.current_theta or 0,
                    vega=trade_orm.current_vega or 0
                )
        
        return dm.Trade(**trade_kwargs)


class StrategyRepository(BaseRepository[dm.Strategy, StrategyORM]):
    """Repository for Strategy entities"""
    
    def __init__(self, session: Session):
        super().__init__(session, StrategyORM)
    
    def get_or_create_from_domain(self, strategy: dm.Strategy) -> Optional[StrategyORM]:
        """Get existing strategy or create new one"""
        try:
            strategy_type_value = strategy.strategy_type.value if hasattr(strategy.strategy_type, 'value') else str(strategy.strategy_type)
            
            # Try to find existing
            existing = self.session.query(StrategyORM).filter_by(
                name=strategy.name,
                strategy_type=strategy_type_value
            ).first()
            
            if existing:
                return existing
            
            # Create new
            # Convert risk_category enum to string value
            risk_category = getattr(strategy, 'risk_category', None)
            if risk_category and hasattr(risk_category, 'value'):
                risk_category = risk_category.value
            
            strategy_orm = StrategyORM(
                id=strategy.id,
                name=strategy.name,
                strategy_type=strategy_type_value,
                risk_category=risk_category,
                max_profit=strategy.max_profit,
                max_loss=strategy.max_loss,
                breakeven_points=[float(bp) for bp in strategy.breakeven_points] if strategy.breakeven_points else None,
                probability_of_profit=getattr(strategy, 'probability_of_profit', None),
                expected_value=getattr(strategy, 'expected_value', None),
                target_delta=strategy.target_delta,
                max_gamma=strategy.max_gamma,
                target_theta=getattr(strategy, 'target_theta', None),
                profit_target_pct=getattr(strategy, 'profit_target_pct', 50),
                stop_loss_pct=getattr(strategy, 'stop_loss_pct', 200),
                dte_exit=getattr(strategy, 'dte_exit', 7),
                description=strategy.description
            )

            try:
                nested = self.session.begin_nested()
                self.session.add(strategy_orm)
                nested.commit()
                return strategy_orm
            except IntegrityError:
                nested.rollback()
                return self.session.query(StrategyORM).filter_by(
                    name=strategy.name,
                    strategy_type=strategy_type_value
                ).first()
            
        except Exception as e:
            logger.error(f"Error getting/creating strategy {strategy.name}: {e}")
            logger.exception("Full trace:")
            return None
    
    def to_domain(self, strategy_orm: StrategyORM) -> dm.Strategy:
        """Convert ORM to domain model"""
        from decimal import Decimal
        
        breakeven_points = []
        if strategy_orm.breakeven_points:
            breakeven_points = [Decimal(str(bp)) for bp in strategy_orm.breakeven_points]
        
        strategy_kwargs = dict(
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
        
        # Add enhanced fields if available
        if hasattr(dm.Strategy, 'risk_category') and hasattr(strategy_orm, 'risk_category'):
            if strategy_orm.risk_category:
                try:
                    strategy_kwargs['risk_category'] = dm.RiskCategory(strategy_orm.risk_category)
                except (ValueError, AttributeError):
                    pass
        
        for field in ['probability_of_profit', 'expected_value', 'target_theta',
                      'profit_target_pct', 'stop_loss_pct', 'dte_exit']:
            if hasattr(dm.Strategy, field) and hasattr(strategy_orm, field):
                strategy_kwargs[field] = getattr(strategy_orm, field, None)
        
        return dm.Strategy(**strategy_kwargs)
