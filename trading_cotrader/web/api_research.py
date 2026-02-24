"""
Research API Router — Serves unified research data from ResearchContainer.

Data population is owned by QuantResearchAgent.populate().
This router reads from the container and delegates refreshes to the agent.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import logging

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from trading_cotrader.services.strategy_builder import build_strategy_proposals

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)

# Standalone fallback when engine.container_manager is None (e.g. --no-broker)
_standalone_container = None


def _get_research_container(engine: 'WorkflowEngine'):
    """Get ResearchContainer from engine, or create a standalone fallback."""
    global _standalone_container
    cm = engine.container_manager
    if cm is not None:
        return cm.research
    # No container_manager — use standalone container
    if _standalone_container is None:
        from trading_cotrader.containers.research_container import ResearchContainer
        _standalone_container = ResearchContainer()
        logger.info("Using standalone ResearchContainer (no container_manager)")
    return _standalone_container


def _load_watchlist() -> list:
    """Load market_watchlist.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'market_watchlist.yaml'
    if not config_path.exists():
        return []
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    return cfg.get('watchlist', [])


def _save_watchlist(items: list) -> None:
    """Save watchlist back to market_watchlist.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'market_watchlist.yaml'
    with open(config_path, 'w') as f:
        yaml.dump({'watchlist': items}, f, default_flow_style=False, sort_keys=False)


class AddWatchlistTickerRequest(BaseModel):
    ticker: str
    name: str = ''
    asset_class: str = 'equity'


def _save_container_to_db(container) -> None:
    """Persist container state to DB (fire-and-forget)."""
    try:
        from trading_cotrader.core.database.session import session_scope
        with session_scope() as session:
            container.save_to_db(session)
    except Exception as e:
        logger.warning(f"Failed to persist research to DB: {e}")


def create_research_router(engine: 'WorkflowEngine') -> APIRouter:
    """Create the research API router wired to the workflow engine."""

    router = APIRouter()

    # ------------------------------------------------------------------
    # GET /research — full research grid (all watchlist symbols)
    # ------------------------------------------------------------------

    @router.get("/research")
    async def get_research(
        refresh: bool = Query(False, description="Force refresh even if data is fresh"),
        skip_fundamentals: bool = Query(False, description="Skip slow fundamentals fetch"),
    ):
        """
        Full research grid: all watchlist symbols with technicals, regime,
        fundamentals, and macro context.

        Data is cached in ResearchContainer. Auto-refreshes if stale (>5min).
        Pass ?refresh=true to force refresh.
        """
        container = _get_research_container(engine)

        # Load watchlist config if not loaded
        if not container.watchlist_config:
            items = _load_watchlist()
            container.load_watchlist_config(items)

        tickers = container.symbols

        if not tickers:
            return {
                'data': [],
                'macro': container.get_macro().to_dict(),
                'count': 0,
                'populated_at': None,
                'from_db': False,
            }

        # Check if container has any populated data
        has_data = any(entry.timestamp is not None for entry in container.get_all().values())

        # If empty, try loading from DB first (fast — no library calls)
        if not has_data and not container.loaded_from_db:
            try:
                from trading_cotrader.core.database.session import session_scope
                with session_scope() as session:
                    db_count = container.load_from_db(session)
                if db_count:
                    has_data = True
                    logger.info(f"Research: loaded {db_count} entries from DB on first request")
            except Exception as e:
                logger.warning(f"Research DB load failed: {e}")

        # Only block-populate on explicit ?refresh=true (user-initiated)
        # Delegate to agent.populate() instead of old utility function
        populate_stats = None
        if refresh:
            try:
                agent = engine.scout
                result = agent.populate({
                    'skip_fundamentals': skip_fundamentals,
                })
                populate_stats = result.data if result else None
            except Exception as e:
                logger.error(f"Research population failed: {e}")
                populate_stats = {'error': str(e)}

        return {
            'data': container.to_grid_rows(),
            'macro': container.get_macro().to_dict(),
            'count': container.count,
            'populated_at': datetime.utcnow().isoformat(),
            'populate_stats': populate_stats,
            'from_db': has_data and not refresh and populate_stats is None,
        }

    # ------------------------------------------------------------------
    # POST /research/refresh — force refresh all or specific tickers
    # ------------------------------------------------------------------

    @router.post("/research/refresh")
    async def refresh_research(body: Optional[dict] = None):
        """
        Force refresh research data.

        Body (optional): {"tickers": ["SPY", "QQQ"]}
        If no tickers specified, refreshes entire watchlist.
        """
        container = _get_research_container(engine)

        # Load watchlist config if not loaded
        if not container.watchlist_config:
            items = _load_watchlist()
            container.load_watchlist_config(items)

        tickers = (body or {}).get('tickers')
        if not tickers:
            tickers = container.symbols

        if not tickers:
            return {'status': 'no_tickers', 'count': 0}

        tickers = [t.upper() for t in tickers]
        skip_fund = (body or {}).get('skip_fundamentals', False)

        # Delegate to agent
        agent = engine.scout
        stats = agent._populate_from_library(tickers, skip_fundamentals=skip_fund)
        agent._save_to_db()

        return {
            'status': 'refreshed',
            'count': container.count,
            'stats': stats,
            'refreshed_at': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # GET /research/watchlist — just the watchlist config
    # NOTE: Must be defined BEFORE /research/{ticker} to avoid
    # FastAPI matching "watchlist" as a ticker path parameter.
    # ------------------------------------------------------------------

    @router.get("/research/watchlist")
    async def get_research_watchlist():
        """Return the watchlist configuration."""
        items = _load_watchlist()
        return {'watchlist': items, 'count': len(items)}

    # ------------------------------------------------------------------
    # POST /research/watchlist — add ticker to watchlist
    # ------------------------------------------------------------------

    @router.post("/research/watchlist")
    async def add_watchlist_ticker(body: AddWatchlistTickerRequest):
        """Add a ticker to the watchlist YAML config."""
        ticker = body.ticker.upper().strip()
        if not ticker:
            raise HTTPException(400, "Ticker is required")

        items = _load_watchlist()

        # Check for duplicate
        existing = [i['ticker'] for i in items]
        if ticker in existing:
            raise HTTPException(409, f"{ticker} is already in the watchlist")

        # Resolve name if not provided
        name = body.name.strip()
        if not name:
            name = ticker

        new_item = {
            'name': name,
            'ticker': ticker,
            'asset_class': body.asset_class.strip() or 'equity',
        }
        items.append(new_item)
        _save_watchlist(items)

        # Update container so the new ticker appears immediately
        container = _get_research_container(engine)
        container.load_watchlist_config(items)

        logger.info(f"Watchlist: added {ticker} ({name})")
        return {'status': 'added', 'ticker': ticker, 'watchlist': items, 'count': len(items)}

    # ------------------------------------------------------------------
    # DELETE /research/watchlist/{ticker} — remove ticker from watchlist
    # ------------------------------------------------------------------

    @router.delete("/research/watchlist/{ticker}")
    async def remove_watchlist_ticker(ticker: str):
        """Remove a ticker from the watchlist YAML config."""
        ticker = ticker.upper().strip()
        items = _load_watchlist()

        original_count = len(items)
        items = [i for i in items if i['ticker'] != ticker]

        if len(items) == original_count:
            raise HTTPException(404, f"{ticker} not found in watchlist")

        _save_watchlist(items)

        # Update container
        container = _get_research_container(engine)
        container.load_watchlist_config(items)

        logger.info(f"Watchlist: removed {ticker}")
        return {'status': 'removed', 'ticker': ticker, 'watchlist': items, 'count': len(items)}

    # ------------------------------------------------------------------
    # GET /research/{ticker} — single ticker full research
    # NOTE: Must be AFTER all /research/<literal> routes (watchlist, etc.)
    # ------------------------------------------------------------------

    @router.get("/research/{ticker}")
    async def get_research_ticker(ticker: str):
        """
        Single ticker research entry from container.
        Populates on-demand if not already in container.
        """
        container = _get_research_container(engine)
        symbol = ticker.upper()

        entry = container.get(symbol)
        if entry and entry.timestamp and not container.is_stale:
            return entry.to_dict()

        # Populate just this ticker via agent
        try:
            agent = engine.scout
            agent._populate_from_library([symbol])
            agent._save_to_db()
        except Exception as e:
            logger.error(f"Research population failed for {symbol}: {e}")
            raise HTTPException(500, f"Research population failed: {e}")

        entry = container.get(symbol)
        if not entry:
            raise HTTPException(404, f"No research data for {symbol}")

        return entry.to_dict()

    # ------------------------------------------------------------------
    # GET /research/{ticker}/strategies — ranked strategy proposals
    # ------------------------------------------------------------------

    @router.get("/research/{ticker}/strategies")
    async def get_strategy_proposals(
        ticker: str,
        portfolio: str = Query("tastytrade_real", description="Portfolio for fitness checks"),
    ):
        """
        Generate ranked strategy proposals for a ticker.

        Uses ResearchEntry data (regime, opportunities, levels) to determine
        applicable strategies, constructs legs, computes payoff, checks fitness.
        """
        container = _get_research_container(engine)
        symbol = ticker.upper()

        entry = container.get(symbol)
        if not entry or entry.timestamp is None:
            # Try to populate on-demand
            try:
                agent = engine.scout
                agent._populate_from_library([symbol])
                agent._save_to_db()
                entry = container.get(symbol)
            except Exception as e:
                logger.error(f"Research population failed for {symbol}: {e}")
                raise HTTPException(500, f"Research population failed: {e}")

        if not entry:
            raise HTTPException(404, f"No research data for {symbol}")

        spot = entry.current_price or 0
        # Use ATR% as rough IV proxy if no IV available
        iv = (entry.atr_pct or 25) / 100
        if iv < 0.05:
            iv = 0.20  # sane default

        # Get portfolio state for fitness check
        portfolio_state = {}
        risk_limits = {}
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import PortfolioORM, PositionORM
            with session_scope() as session:
                port = session.query(PortfolioORM).filter(
                    PortfolioORM.name == portfolio,
                ).first()
                if port:
                    equity = float(port.total_equity or 0)
                    positions = session.query(PositionORM).filter(
                        PositionORM.portfolio_id == port.id,
                    ).all()
                    net_delta = sum(float(p.delta or 0) for p in positions)
                    portfolio_state = {
                        'net_delta': net_delta,
                        'total_equity': equity,
                        'buying_power': float(port.buying_power or 0),
                        'margin_used': equity - float(port.cash_balance or 0),
                        'var_1d_95': float(port.var_1d_95 or 0),
                        'open_positions': len(positions),
                        'exposure_by_underlying': {},
                    }
                    risk_limits = {
                        'max_delta': float(port.max_portfolio_delta or 500),
                        'max_positions': 50,
                        'max_var_pct': 2.0,
                        'max_concentration_pct': float(port.max_concentration_pct or 25),
                        'max_margin_pct': 50.0,
                    }
        except Exception as e:
            logger.warning(f"Portfolio state fetch failed: {e}")

        proposals, diagnostics = build_strategy_proposals(
            ticker=symbol,
            research_entry=entry,
            spot=spot,
            iv=iv,
            portfolio_state=portfolio_state,
            risk_limits=risk_limits,
        )

        return {
            'ticker': symbol,
            'spot': spot,
            'iv': round(iv, 4),
            'regime': entry.hmm_regime_label,
            'direction': entry.levels_direction,
            'strategy_count': len(proposals),
            'strategies': proposals,
            'diagnostics': diagnostics,
        }

    return router
