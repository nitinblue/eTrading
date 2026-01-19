# ============================================================================
# SERVICE LAYER - Business Logic
# ============================================================================

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from data_access import PortfolioRepository, TradeRepository, PositionRepository, OrderRepository
#from trading_claude.broker_adapters import BrokerAdapter, BrokerFactory
from broker_adapters import TastytradeAdapter, BrokerAdapter
import data_model as dm

# Assume imports from previous artifacts
# from core_models import *
# from broker_adapters import BrokerAdapter
# from repositories import *

logger = logging.getLogger(__name__)


class PortfolioService:
    """Main service for portfolio management"""
    
    def __init__(self, session: Session, broker_adapter: BrokerAdapter):
        self.session = session
        self.broker = broker_adapter
        
        # Initialize repositories
        self.portfolio_repo = PortfolioRepository(session)
        self.trade_repo = TradeRepository(session)
        self.position_repo = PositionRepository(session)
        self.order_repo = OrderRepository(session)
    
    def sync_from_broker(self, portfolio_id: str) -> dm.Portfolio:
        """Sync portfolio data from broker"""
        logger.info(f"Syncing portfolio {portfolio_id} from broker")
        
        # Get portfolio
        portfolio = self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Sync account balance
        balance = self.broker.get_account_balance()
        portfolio.cash_balance = balance.get('cash_balance', Decimal('0'))
        portfolio.buying_power = balance.get('buying_power', Decimal('0'))
        
        # Sync positions
        broker_positions = self.broker.get_positions()
        self._sync_positions(portfolio, broker_positions)
        
        # Sync orders
        broker_orders = self.broker.get_orders()
        self._sync_orders(portfolio, broker_orders)
        
        # Recalculate portfolio metrics
        self._recalculate_portfolio_metrics(portfolio)
        
        # Save changes
        portfolio.last_updated = datetime.utcnow()
        self.portfolio_repo.update(portfolio)
        
        logger.info(f"Portfolio sync complete. {len(broker_positions)} positions, {len(broker_orders)} orders")
        return portfolio
    
    def create_portfolio_from_broker(self, broker_name: str, account_id: str, name: str) -> dm.Portfolio:
        """Create a new portfolio and sync from broker"""
        # Check if portfolio already exists
        existing = self.portfolio_repo.get_by_account(broker_name, account_id)
        if existing:
            logger.info(f"Portfolio already exists for {broker_name} {account_id}")
            return self.sync_from_broker(existing.id)
        
        # Create new portfolio
        portfolio = dm.Portfolio(
            name=name,
            broker=broker_name,
            account_id=account_id
        )
        
        portfolio = self.portfolio_repo.create(portfolio)
        logger.info(f"Created new portfolio {portfolio.id}")
        
        # Initial sync
        return self.sync_from_broker(portfolio.id)
    
    def _sync_positions(self, portfolio: dm.Portfolio, broker_positions: List[dm.Position]):
        """Sync positions from broker"""
        # Get existing positions
        existing_positions = self.position_repo.get_by_portfolio(portfolio.id)
        existing_map = {p.broker_position_id: p for p in existing_positions if p.broker_position_id}
        
        synced_ids = set()
        
        for broker_pos in broker_positions:
            broker_id = broker_pos.broker_position_id
            
            if broker_id in existing_map:
                # Update existing position
                existing = existing_map[broker_id]
                existing.quantity = broker_pos.quantity
                existing.current_price = broker_pos.current_price
                existing.market_value = broker_pos.market_value
                existing.delta = broker_pos.delta
                existing.gamma = broker_pos.gamma
                existing.theta = broker_pos.theta
                existing.vega = broker_pos.vega
                
                self.position_repo.update(existing)
                synced_ids.add(broker_id)
            else:
                # Create new position
                self.position_repo.create(broker_pos, portfolio.id)
                if broker_id:
                    synced_ids.add(broker_id)
        
        # Remove positions that no longer exist at broker
        for pos in existing_positions:
            if pos.broker_position_id and pos.broker_position_id not in synced_ids:
                logger.info(f"Removing position {pos.id} - no longer at broker")
                self.position_repo.delete(pos.id)
    
    def _sync_orders(self, portfolio: dm.Portfolio, broker_orders: List[dm.Order]):
        """Sync orders from broker"""
        # Get existing orders
        existing_orders = self.order_repo.get_by_portfolio(portfolio.id)
        existing_map = {o.broker_order_id: o for o in existing_orders if o.broker_order_id}
        
        for broker_order in broker_orders:
            broker_id = broker_order.broker_order_id
            
            if broker_id in existing_map:
                # Update existing order
                existing = existing_map[broker_id]
                if existing.status != broker_order.status:
                    self.order_repo.update_status(
                        existing.id,
                        broker_order.status,
                        broker_order.filled_quantity,
                        broker_order.average_fill_price
                    )
            else:
                # Create new order
                self.order_repo.create(broker_order, portfolio.id)
    
    def _recalculate_portfolio_metrics(self, portfolio: dm.Portfolio):
        """Recalculate portfolio-level metrics"""
        positions = self.position_repo.get_by_portfolio(portfolio.id)
        
        # Sum up Greeks
        portfolio.portfolio_delta = sum(p.delta for p in positions)
        portfolio.portfolio_gamma = sum(p.gamma for p in positions)
        portfolio.portfolio_theta = sum(p.theta for p in positions)
        portfolio.portfolio_vega = sum(p.vega for p in positions)
        
        # Calculate equity
        total_market_value = sum(p.market_value for p in positions)
        portfolio.total_equity = portfolio.cash_balance + total_market_value
        
        # Calculate unrealized PnL
        portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)
    
    def get_portfolio_summary(self, portfolio_id: str) -> Dict:
        """Get portfolio summary with key metrics"""
        portfolio = self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            return {}
        
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        trades = self.trade_repo.get_by_portfolio(portfolio_id)
        open_trades = [t for t in trades if t.is_open]
        closed_trades = [t for t in trades if not t.is_open]
        
        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "broker": portfolio.broker,
            "account_id": portfolio.account_id,
            "cash_balance": float(portfolio.cash_balance),
            "buying_power": float(portfolio.buying_power),
            "total_equity": float(portfolio.total_equity),
            "total_pnl": float(portfolio.total_pnl),
            "positions_count": len(positions),
            "open_trades_count": len(open_trades),
            "closed_trades_count": len(closed_trades),
            "greeks": {
                "delta": float(portfolio.portfolio_delta),
                "gamma": float(portfolio.portfolio_gamma),
                "theta": float(portfolio.portfolio_theta),
                "vega": float(portfolio.portfolio_vega)
            },
            "last_updated": portfolio.last_updated.isoformat()
        }
    
    def get_positions_summary(self, portfolio_id: str) -> List[Dict]:
        """Get detailed position information"""
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        
        summary = []
        for pos in positions:
            summary.append({
                "symbol": pos.symbol.ticker,
                "asset_type": pos.symbol.asset_type.value,
                "quantity": pos.quantity,
                "average_price": float(pos.average_price),
                "current_price": float(pos.current_price) if pos.current_price else None,
                "market_value": float(pos.market_value),
                "unrealized_pnl": float(pos.unrealized_pnl()),
                "pnl_percent": float(pos.unrealized_pnl() / pos.total_cost * 100) if pos.total_cost else 0,
                "greeks": {
                    "delta": float(pos.delta),
                    "gamma": float(pos.gamma),
                    "theta": float(pos.theta),
                    "vega": float(pos.vega)
                }
            })
        
        return summary
    
    def get_trades_summary(self, portfolio_id: str, open_only: bool = False) -> List[Dict]:
        """Get detailed trade information"""
        trades = self.trade_repo.get_by_portfolio(portfolio_id, open_only)
        
        summary = []
        for trade in trades:
            summary.append({
                "trade_id": trade.id,
                "underlying": trade.underlying_symbol,
                "strategy": trade.strategy.name if trade.strategy else "Single",
                "strategy_type": trade.strategy.strategy_type.value if trade.strategy else "single",
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                "is_open": trade.is_open,
                "legs_count": len(trade.legs),
                "net_cost": float(trade.net_cost()),
                "current_pnl": float(trade.total_pnl()),
                "pnl_percent": float(trade.total_pnl() / trade.net_cost() * 100) if trade.net_cost() else 0,
                "tags": trade.tags
            })
        
        return summary
    
    def submit_order(self, portfolio_id: str, order: dm.Order) -> str:
        """Submit order through broker"""
        try:
            # Submit to broker
            broker_order_id = self.broker.submit_order(order)
            order.broker_order_id = broker_order_id
            order.status = dm.OrderStatus.PENDING
            
            # Save to database
            self.order_repo.create(order, portfolio_id)
            
            logger.info(f"Order submitted: {broker_order_id}")
            return broker_order_id
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        order_orm = self.session.query(dm.OrderORM).filter_by(id=order_id).first()
        if not order_orm or not order_orm.broker_order_id:
            return False
        
        # Cancel at broker
        success = self.broker.cancel_order(order_orm.broker_order_id)
        
        if success:
            # Update in database
            self.order_repo.update_status(order_id, dm.OrderStatus.CANCELLED)
        
        return success


class RiskAnalysisService:
    """Service for risk analysis and management"""
    
    def __init__(self, session: Session):
        self.session = session
        self.position_repo = PositionRepository(session)
        self.trade_repo = TradeRepository(session)
    
    def calculate_portfolio_risk(self, portfolio_id: str) -> Dict:
        """Calculate comprehensive risk metrics"""
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        
        # Greeks exposure
        total_delta = sum(p.delta for p in positions)
        total_gamma = sum(p.gamma for p in positions)
        total_theta = sum(p.theta for p in positions)
        total_vega = sum(p.vega for p in positions)
        
        # Concentration risk
        position_values = [float(p.market_value) for p in positions]
        total_value = sum(position_values)
        
        concentration = {}
        for pos in positions:
            if total_value > 0:
                weight = float(pos.market_value) / total_value
                concentration[pos.symbol.ticker] = weight
        
        # Find largest positions
        largest_positions = sorted(
            concentration.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            "greeks": {
                "delta": float(total_delta),
                "gamma": float(total_gamma),
                "theta": float(total_theta),
                "vega": float(total_vega)
            },
            "concentration": dict(largest_positions),
            "total_positions": len(positions),
            "positions_at_risk": len([p for p in positions if p.unrealized_pnl() < 0])
        }
    
    def get_expiring_positions(self, portfolio_id: str, days: int = 7) -> List[Dict]:
        """Get positions expiring within N days"""
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        
        expiring = []
        for pos in positions:
            if pos.symbol.asset_type == dm.AssetType.OPTION and pos.symbol.expiration:
                if pos.symbol.expiration <= cutoff_date:
                    expiring.append({
                        "symbol": pos.symbol.get_option_symbol(),
                        "expiration": pos.symbol.expiration.isoformat(),
                        "days_to_expiry": (pos.symbol.expiration - datetime.utcnow()).days,
                        "quantity": pos.quantity,
                        "current_value": float(pos.market_value)
                    })
        
        return sorted(expiring, key=lambda x: x["days_to_expiry"])
    
    def calculate_var(self, portfolio_id: str, confidence: float = 0.95) -> Decimal:
        """Calculate Value at Risk (simplified)"""
        # This is a simplified VaR calculation
        # In production, you'd want more sophisticated models
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        
        # Use delta as a proxy for directional risk
        total_delta = sum(abs(p.delta) for p in positions)
        
        # Assume 1% market move, scaled by confidence level
        market_move = Decimal('0.01') * Decimal(str(1 / (1 - confidence)))
        var = total_delta * market_move
        
        return abs(var)


# ============================================================================
# STRATEGY BUILDER SERVICE
# ============================================================================

class StrategyBuilder:
    """Helper to build common option strategies"""
    
    @staticmethod
    def iron_condor(
        underlying: str,
        expiration: datetime,
        put_short_strike: Decimal,
        put_long_strike: Decimal,
        call_short_strike: Decimal,
        call_long_strike: Decimal,
        quantity: int = 1
    ) -> dm.Trade:
        """Build an Iron Condor trade"""
        
        legs = [
            # Put spread
            Leg(
                symbol=Symbol(underlying, dm.AssetType.OPTION,dm. OptionType.PUT, put_long_strike, expiration, multiplier=100),
                quantity=quantity,
                side=dm.OrderSide.BUY_TO_OPEN
            ),
            Leg(
                symbol=dm.Symbol(underlying, dm.AssetType.OPTION, dm.OptionType.PUT, put_short_strike, expiration, multiplier=100),
                quantity=-quantity,
                side=dm.OrderSide.SELL_TO_OPEN
            ),
            # Call spread
            Leg(
                symbol=dm.Symbol(underlying, dm.AssetType.OPTION, dm.OptionType.CALL, call_short_strike, expiration, multiplier=100),
                quantity=-quantity,
                side=OrderSide.SELL_TO_OPEN
            ),
            Leg(
                symbol=dm.Symbol(underlying, dm.AssetType.OPTION, dm.OptionType.CALL, call_long_strike, expiration, multiplier=100),
                quantity=quantity,
                side=dm.OrderSide.BUY_TO_OPEN
            )
        ]
        
        strategy = dm.Strategy(
            name=f"{underlying} Iron Condor",
            strategy_type=dm.StrategyType.IRON_CONDOR,
            max_profit=(call_short_strike - put_short_strike) - (call_long_strike - call_short_strike) - (put_short_strike - put_long_strike),
            max_loss=(call_long_strike - call_short_strike),
            breakeven_points=[put_short_strike, call_short_strike]
        )
        
        trade = dm.Trade(
            legs=legs,
            strategy=strategy,
            underlying_symbol=underlying
        )
        
        return trade
    
    @staticmethod
    def vertical_spread(
        underlying: str,
        expiration: datetime,
        option_type: dm.OptionType,
        long_strike: Decimal,
        short_strike: Decimal,
        quantity: int = 1
    ) -> dm.Trade:
        """Build a vertical spread (credit or debit)"""
        
        legs = [
            Leg(
                symbol=dm.Symbol(underlying, dm.AssetType.OPTION, option_type, long_strike, expiration, multiplier=100),
                quantity=quantity,
                side=dm.OrderSide.BUY_TO_OPEN
            ),
            dm.Leg(
                symbol=dm.Symbol(underlying, dm.AssetType.OPTION, option_type, short_strike, expiration, multiplier=100),
                quantity=-quantity,
                side=dm.OrderSide.SELL_TO_OPEN
            )
        ]
        
        strategy = dm.Strategy(
            name=f"{underlying} Vertical Spread",
            strategy_type=dm.StrategyType.VERTICAL_SPREAD
        )
        
        trade = dm.Trade(
            legs=legs,
            strategy=strategy,
            underlying_symbol=underlying
        )
        
        return trade


# Example usage
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Setup
    engine = create_engine("sqlite:///portfolio.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create broker adapter (you'd use real credentials)
    
    config = load_tastytrade_config()
    adapter = create_tastytrade_from_config(config)
    adapter.authenticate()
    print(f"Connected to account: {adapter.account_id}")
    
    
    from broker_adapters import TastytradeAdapter
    broker = TastytradeAdapter("account123", "username", "password")
    broker.authenticate()
    
    # Create service
    service = PortfolioService(session, broker)
    
    # Create and sync portfolio
    portfolio = service.create_portfolio_from_broker(
        broker_name="tastytrade",
        account_id="account123",
        name="My Trading Portfolio"
    )
    
    # Get summary
    summary = service.get_portfolio_summary(portfolio.id)
    print(f"Portfolio: {summary['name']}")
    print(f"Total Equity: ${summary['total_equity']:,.2f}")
    print(f"Total P&L: ${summary['total_pnl']:,.2f}")
    print(f"Positions: {summary['positions_count']}")