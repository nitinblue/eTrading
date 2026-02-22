"""
Research API Router — Serves unified research data from ResearchContainer.

Single endpoint returns all watchlist symbols with technicals, regime,
fundamentals, and macro context. Data is fetched from the market_regime
library and cached in the ResearchContainer.

The Research agent owns:
- config/market_watchlist.yaml (symbol universe)
- ResearchContainer (in ContainerManager)
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import logging

import yaml
from fastapi import APIRouter, HTTPException, Query

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


def _get_regime_service():
    """Lazy-init RegimeService singleton (reuses api_v2 holder if available)."""
    from market_regime import RegimeService, DataService
    if not hasattr(_get_regime_service, '_svc'):
        data_svc = DataService()
        _get_regime_service._svc = RegimeService(data_service=data_svc)
    return _get_regime_service._svc


def _save_container_to_db(container) -> None:
    """Persist container state to DB (fire-and-forget)."""
    try:
        from trading_cotrader.core.database.session import session_scope
        with session_scope() as session:
            container.save_to_db(session)
    except Exception as e:
        logger.warning(f"Failed to persist research to DB: {e}")


def _populate_research_container(container, tickers: list, skip_fundamentals: bool = False) -> dict:
    """
    Populate ResearchContainer from market_regime library for given tickers.

    Returns summary dict with counts of what was populated.
    """
    svc = _get_regime_service()
    stats = {'technicals': 0, 'regime': 0, 'fundamentals': 0, 'macro': False, 'errors': []}

    # 1. Batch regime detection (fast — one call)
    try:
        results = svc.detect_batch(tickers=tickers)
        for ticker_key, r in results.items():
            # Also fetch strategy comment from research (cached)
            strategy_comment = ''
            try:
                research = svc.research(ticker_key)
                strategy_comment = research.strategy_comment
            except Exception:
                pass

            container.update_regime(ticker_key, {
                'regime': r.regime.value,
                'regime_name': r.regime.name,
                'confidence': r.confidence,
                'trend_direction': r.trend_direction,
                'strategy_comment': strategy_comment,
            })
            stats['regime'] += 1
    except Exception as e:
        logger.warning(f"Batch regime detection failed: {e}")
        stats['errors'].append(f"regime: {e}")

    # 2. Technicals per ticker
    for ticker in tickers:
        try:
            snap = svc.get_technicals(ticker)
            container.update_technicals(ticker, snap.model_dump(mode='json'))
            stats['technicals'] += 1
        except Exception as e:
            logger.warning(f"Technicals failed for {ticker}: {e}")
            stats['errors'].append(f"technicals({ticker}): {e}")

    # 3. Fundamentals per ticker (slower — yfinance calls, but cached)
    if not skip_fundamentals:
        from market_regime import fetch_fundamentals
        for ticker in tickers:
            try:
                fund = fetch_fundamentals(ticker)
                container.update_fundamentals(ticker, fund.model_dump(mode='json'))
                stats['fundamentals'] += 1
            except Exception as e:
                logger.warning(f"Fundamentals failed for {ticker}: {e}")
                stats['errors'].append(f"fundamentals({ticker}): {e}")

    # 4. Macro calendar (one call)
    try:
        from market_regime import get_macro_calendar
        cal = get_macro_calendar(lookahead_days=90)
        container.update_macro(cal.model_dump(mode='json'))
        stats['macro'] = True
    except Exception as e:
        logger.warning(f"Macro calendar failed: {e}")
        stats['errors'].append(f"macro: {e}")

    return stats


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
        # Never block-populate on normal page load — engine handles background refresh
        populate_stats = None
        if refresh:
            try:
                populate_stats = _populate_research_container(
                    container, tickers, skip_fundamentals=skip_fundamentals,
                )
                _save_container_to_db(container)
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
    # GET /research/{ticker} — single ticker full research
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

        # Populate just this ticker
        try:
            _populate_research_container(container, [symbol])
            _save_container_to_db(container)
        except Exception as e:
            logger.error(f"Research population failed for {symbol}: {e}")
            raise HTTPException(500, f"Research population failed: {e}")

        entry = container.get(symbol)
        if not entry:
            raise HTTPException(404, f"No research data for {symbol}")

        return entry.to_dict()

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

        stats = _populate_research_container(
            container, tickers, skip_fundamentals=skip_fund,
        )

        _save_container_to_db(container)

        return {
            'status': 'refreshed',
            'count': container.count,
            'stats': stats,
            'refreshed_at': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # GET /research/watchlist — just the watchlist config
    # ------------------------------------------------------------------

    @router.get("/research/watchlist")
    async def get_research_watchlist():
        """Return the watchlist configuration."""
        items = _load_watchlist()
        return {'watchlist': items, 'count': len(items)}

    return router
