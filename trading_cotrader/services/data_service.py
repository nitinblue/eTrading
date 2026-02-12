"""
Data Service - Syncs data from broker to database and refreshes containers

This is the main integration point between:
- TastyTrade broker adapter (live data with Greeks from DXLink)
- SQLite database (persistence via repositories)
- Containers (in-memory for UI)

Design:
- sync_from_broker(): Pull from TastyTrade, persist to DB, refresh containers
- refresh_containers(): Load containers from DB
- get_what_if_trades(): Get what-if trades from DB for what-if portfolio
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from trading_cotrader.config.settings import get_settings
from trading_cotrader.core.database.session import session_scope, Session
from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.repositories.position import PositionRepository
from trading_cotrader.repositories.trade import TradeRepository
from trading_cotrader.services.position_sync import PositionSyncService
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    portfolio_id: Optional[str] = None
    positions_count: int = 0
    whatif_trades_count: int = 0
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class DataService:
    """
    Central data service that:
    - Syncs from TastyTrade broker to SQLite
    - Loads containers from database
    - Provides what-if portfolio from DB trades

    NO MOCK DATA - all data comes from broker or database.
    """

    def __init__(self, container_manager=None):
        self.settings = get_settings()
        self.broker: Optional[TastytradeAdapter] = None
        self.container_manager = container_manager
        self._is_connected = False
        self._portfolio_id: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.broker is not None

    def connect_broker(self) -> bool:
        """Connect to TastyTrade broker"""
        try:
            logger.info("Connecting to TastyTrade broker...")

            self.broker = TastytradeAdapter(
                account_number=self.settings.tastytrade_account_number,
                is_paper=self.settings.is_paper_trading
            )

            if not self.broker.authenticate():
                logger.error("Failed to authenticate with TastyTrade")
                return False

            self._is_connected = True
            logger.info(f"Connected to TastyTrade account: {self.broker.account_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to broker: {e}")
            self._is_connected = False
            return False

    async def sync_from_broker(self) -> SyncResult:
        """
        Full sync from TastyTrade broker to database.

        Steps:
        1. Get account balance from broker
        2. Get positions with Greeks from broker (DXLink streaming)
        3. Persist to SQLite via repositories
        4. Refresh containers from database
        5. Count what-if trades for what-if portfolio

        Returns:
            SyncResult with success/failure info
        """
        if not self.is_connected:
            if not self.connect_broker():
                return SyncResult(success=False, error="Not connected to broker")

        try:
            with session_scope() as session:
                # Get or create portfolio
                portfolio = self._get_or_create_portfolio(session)
                if not portfolio:
                    return SyncResult(success=False, error="Failed to get/create portfolio")

                self._portfolio_id = portfolio.id

                # Sync balance
                balance = self.broker.get_account_balance()
                if balance:
                    portfolio.cash_balance = balance.get('cash_balance', Decimal('0'))
                    portfolio.buying_power = balance.get('buying_power', Decimal('0'))
                    portfolio.total_equity = balance.get('net_liquidating_value', Decimal('0'))

                    portfolio_repo = PortfolioRepository(session)
                    portfolio_repo.update_from_domain(portfolio)
                    logger.info(f"Balance synced: ${portfolio.cash_balance:,.2f}")

                # Sync positions (Greeks come from DXLink streaming)
                # get_positions() is sync but handles async internally
                broker_positions = self.broker.get_positions()
                logger.info(f"Got {len(broker_positions)} positions from broker")

                position_sync = PositionSyncService(session)
                sync_result = position_sync.sync_positions(portfolio.id, broker_positions)

                # Update portfolio Greeks from positions
                self._update_portfolio_greeks(session, portfolio)

                # Get what-if trades count
                trade_repo = TradeRepository(session)
                whatif_trades = trade_repo.get_by_type('what_if')

                # Refresh containers if available
                if self.container_manager:
                    self._refresh_containers(session)

                return SyncResult(
                    success=True,
                    portfolio_id=portfolio.id,
                    positions_count=sync_result.get('final_count', len(broker_positions)),
                    whatif_trades_count=len(whatif_trades),
                )

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            logger.exception("Full trace:")
            return SyncResult(success=False, error=str(e))

    def refresh_from_database(self) -> SyncResult:
        """
        Refresh containers from database only (no broker sync).
        Use this for quick refreshes when data is already in DB.
        """
        try:
            with session_scope() as session:
                # Get portfolio
                portfolio_repo = PortfolioRepository(session)
                portfolios = portfolio_repo.get_all_portfolios()

                if not portfolios:
                    return SyncResult(success=False, error="No portfolio in database")

                portfolio = portfolios[0]
                self._portfolio_id = portfolio.id

                # Get positions count
                position_repo = PositionRepository(session)
                positions = position_repo.get_by_portfolio(portfolio.id)

                # Get what-if trades
                trade_repo = TradeRepository(session)
                whatif_trades = trade_repo.get_by_type('what_if')

                # Refresh containers
                if self.container_manager:
                    self._refresh_containers(session)

                return SyncResult(
                    success=True,
                    portfolio_id=portfolio.id,
                    positions_count=len(positions),
                    whatif_trades_count=len(whatif_trades),
                )

        except Exception as e:
            logger.error(f"Database refresh failed: {e}")
            return SyncResult(success=False, error=str(e))

    def get_portfolios_data(self) -> Dict[str, Any]:
        """
        Get both real portfolio and what-if portfolio data for UI.

        Returns dict with:
        - real_portfolio: Actual positions from broker/DB
        - whatif_portfolio: Aggregated from what-if trades in DB
        """
        try:
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                position_repo = PositionRepository(session)
                trade_repo = TradeRepository(session)

                # Get real portfolio
                portfolios = portfolio_repo.get_all_portfolios()
                if not portfolios:
                    return {'error': 'No portfolio found'}

                real_portfolio = portfolios[0]

                # Get real positions
                positions = position_repo.get_by_portfolio(real_portfolio.id)

                # Get what-if trades
                whatif_trades = trade_repo.get_by_type('what_if')

                return {
                    'real_portfolio': self._portfolio_to_dict(real_portfolio, positions),
                    'whatif_portfolio': self._whatif_trades_to_portfolio(whatif_trades),
                    'positions': [self._position_to_dict(p) for p in positions],
                    'whatif_trades': [self._trade_to_dict(t) for t in whatif_trades],
                }

        except Exception as e:
            logger.error(f"Failed to get portfolios data: {e}")
            return {'error': str(e)}

    def _get_or_create_portfolio(self, session: Session) -> Optional[dm.Portfolio]:
        """Get existing portfolio or create new one"""
        portfolio_repo = PortfolioRepository(session)

        portfolio = portfolio_repo.get_by_account(
            broker="tastytrade",
            account_id=self.broker.account_id
        )

        if portfolio:
            return portfolio

        # Create new
        portfolio = dm.Portfolio(
            name=f"Tastytrade {self.broker.account_id}",
            broker="tastytrade",
            account_id=self.broker.account_id,
            portfolio_type=dm.PortfolioType.REAL if hasattr(dm, 'PortfolioType') else 'real'
        )

        return portfolio_repo.create_from_domain(portfolio)

    def _update_portfolio_greeks(self, session: Session, portfolio: dm.Portfolio):
        """Calculate and update portfolio Greeks from positions"""
        position_repo = PositionRepository(session)
        portfolio_repo = PortfolioRepository(session)

        positions = position_repo.get_by_portfolio(portfolio.id)

        total_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
        total_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in positions)
        total_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
        total_vega = sum(p.greeks.vega if p.greeks else 0 for p in positions)

        portfolio.portfolio_greeks = dm.Greeks(
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega
        )

        # Calculate P&L
        portfolio.total_pnl = sum(p.unrealized_pnl() for p in positions)

        portfolio_repo.update_from_domain(portfolio)
        logger.info(f"Portfolio Greeks updated: Delta={total_delta:.2f}, Theta={total_theta:.2f}")

    def _refresh_containers(self, session: Session):
        """Refresh all containers from database"""
        if not self.container_manager:
            return

        portfolio_repo = PortfolioRepository(session)
        position_repo = PositionRepository(session)
        trade_repo = TradeRepository(session)

        # Load portfolio
        portfolios = portfolio_repo.get_all_portfolios()
        if portfolios:
            # Load into container using ORM objects directly
            from trading_cotrader.core.database.schema import PortfolioORM
            portfolio_orm = session.query(PortfolioORM).filter_by(id=portfolios[0].id).first()
            if portfolio_orm:
                self.container_manager.portfolio.load_from_orm(portfolio_orm)

        # Load positions
        if self._portfolio_id:
            from trading_cotrader.core.database.schema import PositionORM
            positions_orm = session.query(PositionORM).filter_by(
                portfolio_id=self._portfolio_id
            ).all()
            self.container_manager.positions.load_from_orm_list(positions_orm)

            # Aggregate risk factors
            self.container_manager.risk_factors.aggregate_from_positions(
                self.container_manager.positions
            )

        logger.info("Containers refreshed from database")

    def _portfolio_to_dict(self, portfolio: dm.Portfolio, positions: List[dm.Position]) -> Dict[str, Any]:
        """Convert portfolio to dict for UI"""
        greeks = portfolio.portfolio_greeks if portfolio.portfolio_greeks else dm.Greeks()

        return {
            'id': portfolio.id,
            'name': portfolio.name,
            'type': 'real',
            'account_id': portfolio.account_id,
            'total_equity': float(portfolio.total_equity or 0),
            'cash_balance': float(portfolio.cash_balance or 0),
            'buying_power': float(portfolio.buying_power or 0),
            'delta': float(greeks.delta or 0),
            'gamma': float(greeks.gamma or 0),
            'theta': float(greeks.theta or 0),
            'vega': float(greeks.vega or 0),
            'total_pnl': float(portfolio.total_pnl or 0),
            'position_count': len(positions),
        }

    def _whatif_trades_to_portfolio(self, trades: List[dm.Trade]) -> Dict[str, Any]:
        """Aggregate what-if trades into a portfolio view"""
        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')

        for trade in trades:
            # Use current_greeks if available, else entry_greeks
            greeks = getattr(trade, 'current_greeks', None) or getattr(trade, 'entry_greeks', None)
            if greeks:
                total_delta += greeks.delta or Decimal('0')
                total_gamma += greeks.gamma or Decimal('0')
                total_theta += greeks.theta or Decimal('0')
                total_vega += greeks.vega or Decimal('0')

        return {
            'id': 'whatif',
            'name': 'What-If Portfolio',
            'type': 'what_if',
            'delta': float(total_delta),
            'gamma': float(total_gamma),
            'theta': float(total_theta),
            'vega': float(total_vega),
            'trade_count': len(trades),
        }

    def _position_to_dict(self, position: dm.Position) -> Dict[str, Any]:
        """Convert position to dict for UI"""
        symbol = position.symbol
        greeks = position.greeks if position.greeks else dm.Greeks()

        return {
            'id': position.id,
            'symbol': symbol.ticker,
            'underlying': symbol.ticker,
            'type': symbol.option_type.value if symbol.option_type else 'STOCK',
            'strike': float(symbol.strike) if symbol.strike else None,
            'expiry': symbol.expiration.strftime('%Y-%m-%d') if symbol.expiration else None,
            'dte': symbol.dte() if hasattr(symbol, 'dte') and symbol.expiration else None,
            'qty': position.quantity,
            'entry': float(position.entry_price or 0),
            'mark': float(position.current_price or 0),
            'delta': float(greeks.delta or 0),
            'gamma': float(greeks.gamma or 0),
            'theta': float(greeks.theta or 0),
            'vega': float(greeks.vega or 0),
            'pnl': float(position.unrealized_pnl() if hasattr(position, 'unrealized_pnl') else 0),
        }

    def _trade_to_dict(self, trade: dm.Trade) -> Dict[str, Any]:
        """Convert trade to dict for UI"""
        greeks = getattr(trade, 'current_greeks', None) or getattr(trade, 'entry_greeks', None) or dm.Greeks()

        trade_type = getattr(trade, 'trade_type', None)
        trade_type_str = trade_type.value if trade_type and hasattr(trade_type, 'value') else str(trade_type) if trade_type else 'real'

        trade_status = getattr(trade, 'trade_status', None)
        trade_status_str = trade_status.value if trade_status and hasattr(trade_status, 'value') else str(trade_status) if trade_status else 'intent'

        return {
            'id': trade.id,
            'underlying': trade.underlying_symbol,
            'type': trade_type_str,
            'status': trade_status_str,
            'delta': float(greeks.delta or 0),
            'gamma': float(greeks.gamma or 0),
            'theta': float(greeks.theta or 0),
            'vega': float(greeks.vega or 0),
            'legs_count': len(trade.legs) if trade.legs else 0,
            'notes': trade.notes or '',
        }
