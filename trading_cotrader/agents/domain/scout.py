"""
Scout Agent (Quant) — Domain agent that owns the ResearchContainer.

Responsibilities:
  1. populate(): Fill ResearchContainer from market_analyzer library (regime, technicals,
     fundamentals, macro, levels, opportunities).
  2. run(): Use market_analyzer screening + ranking to find actionable setups.

Every MONITORING cycle:
  1. populate() — refresh container from market_analyzer library
  2. run() — screen watchlist, rank candidates, log results
"""

import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, TYPE_CHECKING

import yaml

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

if TYPE_CHECKING:
    from trading_cotrader.containers.research_container import ResearchContainer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ScoutAgent
# ---------------------------------------------------------------------------

class ScoutAgent(BaseAgent):
    """
    Domain agent that owns the ResearchContainer.

    populate(): Fills container from market_analyzer library (regime, technicals,
                fundamentals, macro, levels, opportunities).

    run(): Uses market_analyzer screening + ranking to find actionable setups
           across the watchlist. Results are logged and stored in context for
           downstream agents (Maverick).
    """

    # Class-level metadata
    name: ClassVar[str] = "scout"
    display_name: ClassVar[str] = "Scout (Quant)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "Research pipeline — market analysis, screening, ranking"
    intro: ClassVar[str] = (
        "I own the ResearchContainer and populate it from MarketAnalyzer. "
        "I screen the watchlist for setups and rank candidates for Maverick."
    )
    responsibilities: ClassVar[List[str]] = [
        "Watchlist data population",
        "Market screening (breakout, momentum, mean-reversion, income)",
        "Candidate ranking",
        "Black swan monitoring",
        "Market context assessment",
    ]
    datasources: ClassVar[List[str]] = [
        "market_analyzer library",
        "ResearchContainer",
    ]
    boundaries: ClassVar[List[str]] = [
        "Read-only — does not book trades",
        "Produces signals for Maverick to act on",
    ]
    runs_during: ClassVar[List[str]] = ["monitoring"]

    def __init__(self, container: 'ResearchContainer' = None, config=None,
                 market_data=None, market_metrics=None, watchlist_provider=None):
        super().__init__(container=container, config=config)
        self._injected_market_data = market_data
        self._injected_market_metrics = market_metrics
        self._watchlist_provider = watchlist_provider

    def safety_check(self, context: dict) -> tuple[bool, str]:
        """Research pipeline is always safe -- no real capital involved."""
        return True, ""

    # -----------------------------------------------------------------
    # populate() -- Fill ResearchContainer from market_analyzer library
    # -----------------------------------------------------------------

    def populate(self, context: dict) -> AgentResult:
        """
        Fill ResearchContainer from market_analyzer library.

        Steps:
          1. Load watchlist if not loaded
          2. Batch regime detection
          3. Per-ticker technicals
          4. Per-ticker fundamentals (unless skip_fundamentals=True)
          5. Macro calendar
          6. Persist to DB

        Returns AgentResult with populate stats.
        """
        if self.container is None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=["No container -- cannot populate"],
            )

        # Ensure watchlist is loaded
        if not self.container.watchlist_config:
            self._load_watchlist()

        tickers = self.container.symbols
        if not tickers:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'tickers': 0},
                messages=["No tickers in watchlist -- nothing to populate"],
            )

        skip_fundamentals = context.get('skip_fundamentals', False)
        stats = self._populate_from_library(tickers, skip_fundamentals=skip_fundamentals)

        # Persist to DB
        self._save_to_db()

        msg = (
            f"Research populated: {stats.get('regime', 0)} regime, "
            f"{stats.get('technicals', 0)} technicals, "
            f"{stats.get('phase', 0)} phase, "
            f"{stats.get('opportunities', 0)} opportunities, "
            f"{stats.get('levels', 0)} levels, "
            f"{stats.get('fundamentals', 0)} fundamentals"
        )
        errors = stats.get('errors', [])
        messages = [msg]
        if errors:
            messages.append(f"{len(errors)} errors: {'; '.join(str(e) for e in errors[:3])}")

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data=stats,
            messages=messages,
        )

    def _populate_from_library(self, tickers: List[str], skip_fundamentals: bool = False) -> dict:
        """
        Populate ResearchContainer from market_analyzer library for given tickers.

        Returns summary dict with counts of what was populated.
        """
        ma = self._get_market_analyzer()
        container = self.container
        stats = {
            'technicals': 0, 'regime': 0, 'fundamentals': 0,
            'phase': 0, 'opportunities': 0, 'levels': 0,
            'macro': False, 'errors': [],
        }

        # 1. Batch regime detection (fast -- one call)
        try:
            results = ma.regime.detect_batch(tickers=tickers)
            for ticker_key, r in results.items():
                strategy_comment = ''
                try:
                    research = ma.regime.research(ticker_key)
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

        # 2. Technicals per ticker (includes smart money + MACD line/signal)
        for ticker in tickers:
            try:
                snap = ma.technicals.snapshot(ticker)
                container.update_technicals(ticker, snap.model_dump(mode='json'))
                stats['technicals'] += 1
            except Exception as e:
                logger.warning(f"Technicals failed for {ticker}: {e}")
                stats['errors'].append(f"technicals({ticker}): {e}")

        # 3. Phase per ticker (enhanced Wyckoff from PhaseService)
        for ticker in tickers:
            try:
                phase_result = ma.phase.detect(ticker)
                container.update_phase(ticker, phase_result.model_dump(mode='json'))
                stats['phase'] += 1
            except Exception as e:
                logger.warning(f"Phase detection failed for {ticker}: {e}")
                stats['errors'].append(f"phase({ticker}): {e}")

        # 4. Opportunities per ticker (4 horizons)
        for ticker in tickers:
            opps = {}
            try:
                opps['zero_dte'] = ma.opportunity.assess_zero_dte(ticker).model_dump(mode='json')
            except Exception as e:
                logger.debug(f"0DTE opportunity failed for {ticker}: {e}")
            try:
                opps['leap'] = ma.opportunity.assess_leap(ticker).model_dump(mode='json')
            except Exception as e:
                logger.debug(f"LEAP opportunity failed for {ticker}: {e}")
            try:
                opps['breakout'] = ma.opportunity.assess_breakout(ticker).model_dump(mode='json')
            except Exception as e:
                logger.debug(f"Breakout opportunity failed for {ticker}: {e}")
            try:
                opps['momentum'] = ma.opportunity.assess_momentum(ticker).model_dump(mode='json')
            except Exception as e:
                logger.debug(f"Momentum opportunity failed for {ticker}: {e}")

            if opps:
                container.update_opportunities(ticker, opps)
                stats['opportunities'] += 1

        # 5. Levels analysis per ticker
        for ticker in tickers:
            try:
                levels_result = ma.levels.analyze(ticker)
                container.update_levels(ticker, levels_result.model_dump(mode='json'))
                stats['levels'] += 1
            except Exception as e:
                logger.debug(f"Levels analysis failed for {ticker}: {e}")
                stats['errors'].append(f"levels({ticker}): {e}")

        # 6. Fundamentals per ticker (slower -- yfinance calls, but cached)
        if not skip_fundamentals:
            for ticker in tickers:
                try:
                    fund = ma.fundamentals.get(ticker)
                    container.update_fundamentals(ticker, fund.model_dump(mode='json'))
                    stats['fundamentals'] += 1
                except Exception as e:
                    logger.warning(f"Fundamentals failed for {ticker}: {e}")
                    stats['errors'].append(f"fundamentals({ticker}): {e}")

        # 7. Macro calendar (one call)
        try:
            cal_data = ma.macro.calendar(lookahead_days=90)
            container.update_macro(cal_data.model_dump(mode='json'))
            stats['macro'] = True
        except Exception as e:
            logger.warning(f"Macro calendar failed: {e}")
            stats['errors'].append(f"macro: {e}")

        return stats

    def _resolve_tickers(self) -> List[str]:
        """Resolve ticker universe: broker watchlist → registry presets → YAML fallback.

        Priority:
          1. TastyTrade broker watchlists (MA-Income, MA-Sectors)
          2. MarketRegistry presets (UV1: 85+ curated instruments)
          3. YAML config (market_watchlist.yaml)
        """
        # G10: Try broker watchlists
        if self._watchlist_provider:
            try:
                tickers = self._watchlist_provider.get_watchlist('MA-Income')
                if tickers:
                    try:
                        sectors = self._watchlist_provider.get_watchlist('MA-Sectors')
                        if sectors:
                            combined = list(dict.fromkeys(tickers + sectors))
                            logger.info(f"Watchlist: {len(combined)} tickers from MA-Income + MA-Sectors")
                            return combined
                    except Exception:
                        pass
                    logger.info(f"Watchlist: {len(tickers)} tickers from MA-Income")
                    return tickers
            except Exception as e:
                logger.debug(f"Watchlist provider failed: {e}")

        # UV1: Try MarketRegistry presets (broker-independent)
        try:
            from market_analyzer import MarketRegistry
            registry = MarketRegistry()
            # Use 'income' preset — the core trading universe
            tickers = registry.get_universe(preset='income')
            if tickers:
                logger.info(f"Watchlist: {len(tickers)} tickers from registry (income preset)")
                return tickers
            # Fallback: all US instruments
            tickers = registry.get_universe(market='US')
            if tickers:
                logger.info(f"Watchlist: {len(tickers)} tickers from registry (US market)")
                return tickers[:25]  # Cap at 25 for scan speed
        except Exception as e:
            logger.debug(f"Registry universe failed: {e}")

        # Fallback: YAML config
        yaml_tickers = self.container.symbols if self.container else []
        if yaml_tickers:
            logger.info(f"Watchlist: {len(yaml_tickers)} tickers from YAML config")
        return yaml_tickers

    def _get_market_analyzer(self):
        """Lazy-init MarketAnalyzer facade singleton.

        Uses broker-provided market_data/metrics if available (single connection,
        SaaS-ready).  Falls back to standalone mode (no live broker quotes).
        """
        if not hasattr(self, '_market_analyzer'):
            from market_analyzer import MarketAnalyzer
            from market_analyzer.data import DataService
            self._market_analyzer = MarketAnalyzer(
                data_service=DataService(),
                market_data=self._injected_market_data,
                market_metrics=self._injected_market_metrics,
            )
        return self._market_analyzer

    def _load_watchlist(self) -> None:
        """Load market_watchlist.yaml into container."""
        config_path = Path(__file__).parent.parent.parent / 'config' / 'market_watchlist.yaml'
        if not config_path.exists():
            return
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        items = cfg.get('watchlist', [])
        self.container.load_watchlist_config(items)

    def _save_to_db(self) -> None:
        """Persist container state to DB (fire-and-forget)."""
        if self.container is None:
            logger.warning("_save_to_db: no container -- skipping")
            return
        try:
            from trading_cotrader.core.database.session import session_scope
            with session_scope() as session:
                self.container.save_to_db(session)
        except Exception as e:
            logger.warning(f"Failed to persist research to DB: {e}")

    # -----------------------------------------------------------------
    # run() -- Screen watchlist + rank candidates via market_analyzer
    # -----------------------------------------------------------------

    def run(self, context: dict) -> AgentResult:
        """
        Screen the watchlist for actionable setups using market_analyzer.

        Uses ma.screening.scan() to find candidates and ma.ranking.rank()
        to prioritize them. Results stored in context for Maverick.
        """
        if self.container is None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=["No container -- cannot run screening"],
            )

        # G10: Pull tickers from TastyTrade watchlist if available, YAML fallback
        tickers = self._resolve_tickers()
        if not tickers:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'tickers': 0},
                messages=["No tickers in watchlist"],
            )

        ma = self._get_market_analyzer()
        messages: List[str] = []
        candidates: List[Dict[str, Any]] = []
        ranking: List[Dict[str, Any]] = []

        # G11: Two-phase scan — screen first (fast), then rank candidates only
        # Phase 1: Screen watchlist (with auto-select filtering)
        try:
            scan_result = ma.screening.scan(tickers, min_score=0.4, top_n=20)
            for c in scan_result.candidates:
                candidates.append(c.model_dump(mode='json'))
            messages.append(f"Phase 1 screen: {len(candidates)} candidates from {scan_result.tickers_scanned} tickers")
        except TypeError:
            # Fallback if scan() doesn't accept min_score/top_n yet
            try:
                scan_result = ma.screening.scan(tickers)
                for c in scan_result.candidates:
                    candidates.append(c.model_dump(mode='json'))
                messages.append(f"Phase 1 screen: {len(candidates)} candidates")
            except Exception as e:
                logger.warning(f"Screening failed: {e}")
                messages.append(f"Screening error: {e}")
        except Exception as e:
            logger.warning(f"Screening failed: {e}")
            messages.append(f"Screening error: {e}")

        # Phase 2: Rank only screened candidates (not full watchlist)
        ranked_tickers = list({c.get('ticker', '') for c in candidates if c.get('ticker')})
        if not ranked_tickers:
            ranked_tickers = tickers[:10]  # fallback: rank top watchlist

        # ML-E5: Build IV rank map from broker metrics
        iv_rank_map = {}
        try:
            if ma.quotes:
                for t in ranked_tickers:
                    metrics = ma.quotes.get_metrics(t)
                    if metrics and metrics.iv_rank is not None:
                        iv_rank_map[t] = metrics.iv_rank
                if iv_rank_map:
                    messages.append(f"IV rank: {len(iv_rank_map)} tickers")
        except Exception as e:
            logger.debug(f"IV rank map failed: {e}")

        # ML-E2/E6: Get bandit-selected strategies for current regime
        rank_kwargs: Dict[str, Any] = {'skip_intraday': True, 'debug': True}
        if iv_rank_map:
            rank_kwargs['iv_rank_map'] = iv_rank_map
        try:
            from trading_cotrader.services.ml_learning_service import MLLearningService
            ml_svc = MLLearningService()
            # Get current regime for strategy selection
            regime_id = 1
            try:
                regime = ma.regime.detect(ranked_tickers[0] if ranked_tickers else 'SPY')
                regime_id = regime.regime if hasattr(regime, 'regime') else 1
            except Exception:
                pass
            bandit_strategies = ml_svc.select_strategies_for_regime(regime_id, n=5)
            if bandit_strategies:
                # Pass as strategy filter hint (not all ranking services support this)
                rank_kwargs['strategies'] = [s for s, _ in bandit_strategies]
                messages.append(f"Bandits: R{regime_id} → {', '.join(s for s, _ in bandit_strategies[:3])}")
        except Exception as e:
            logger.debug(f"Bandit strategy selection skipped: {e}")

        try:
            rank_result = ma.ranking.rank(ranked_tickers, **rank_kwargs)
            for r in rank_result.top_trades:
                ranking.append(r.model_dump(mode='json'))
            messages.append(f"Phase 2 rank: {len(ranking)} ranked from {len(ranked_tickers)} candidates")
        except TypeError:
            # Fallback if rank() doesn't accept all kwargs
            try:
                rank_result = ma.ranking.rank(ranked_tickers, skip_intraday=True)
                for r in rank_result.top_trades:
                    ranking.append(r.model_dump(mode='json'))
                messages.append(f"Phase 2 rank: {len(ranking)} ranked (basic)")
            except Exception as e:
                logger.warning(f"Ranking failed: {e}")
                messages.append(f"Ranking error: {e}")
        except Exception as e:
            logger.warning(f"Ranking failed: {e}")
            messages.append(f"Ranking error: {e}")

        # 3. Black swan check
        black_swan_level = 'NORMAL'
        try:
            bs = ma.black_swan.alert()
            black_swan_level = bs.alert_level
            if bs.alert_level != 'NORMAL':
                messages.append(f"Black Swan: {bs.alert_level} (score={bs.composite_score:.0%})")
        except Exception as e:
            logger.debug(f"Black swan check failed: {e}")

        # 4. Market context (with debug=True for commentary)
        try:
            ctx = ma.context.assess(debug=True)
            messages.append(f"Context: {ctx.environment_label}, trading={'ON' if ctx.trading_allowed else 'HALTED'}")
            context['market_environment'] = ctx.environment_label
            context['trading_allowed'] = ctx.trading_allowed
            context['position_size_factor'] = ctx.position_size_factor
            # Store commentary for decision lineage (G25)
            if hasattr(ctx, 'commentary') and ctx.commentary:
                context.setdefault('commentary', {})['context'] = ctx.commentary
        except TypeError:
            try:
                ctx = ma.context.assess()
                context['market_environment'] = ctx.environment_label
                context['trading_allowed'] = ctx.trading_allowed
                context['position_size_factor'] = ctx.position_size_factor
            except Exception as e:
                logger.debug(f"Context check failed: {e}")
        except Exception as e:
            logger.debug(f"Context check failed: {e}")

        # 4b. Macro dashboard (MC1-MC5)
        try:
            from market_analyzer import compute_macro_dashboard
            macro = compute_macro_dashboard()
            context['macro_dashboard'] = macro.model_dump(mode='json') if hasattr(macro, 'model_dump') else {}
            if hasattr(macro, 'overall_risk_level'):
                messages.append(f"Macro: {macro.overall_risk_level} risk")
        except Exception as e:
            logger.debug(f"Macro dashboard skipped: {e}")

        # 4c. Cross-market US-India correlation (CM1)
        try:
            from market_analyzer import analyze_cross_market
            from market_analyzer.data import DataService
            ds = DataService()
            spy_data = ds.get_ohlcv('SPY', period='3mo')
            nifty_data = ds.get_ohlcv('^NSEI', period='3mo')
            if spy_data is not None and not spy_data.empty and nifty_data is not None and not nifty_data.empty:
                # Get regimes for both
                spy_regime = 1
                nifty_regime = 1
                try:
                    spy_r = ma.regime.detect('SPY')
                    spy_regime = spy_r.regime if hasattr(spy_r, 'regime') else 1
                    nifty_r = ma.regime.detect('NIFTY')
                    nifty_regime = nifty_r.regime if hasattr(nifty_r, 'regime') else 1
                except Exception:
                    pass
                cm = analyze_cross_market(
                    source_ticker='SPY', target_ticker='NIFTY',
                    source_ohlcv=spy_data, target_ohlcv=nifty_data,
                    source_regime_id=spy_regime, target_regime_id=nifty_regime,
                )
                context['cross_market'] = cm.model_dump(mode='json') if hasattr(cm, 'model_dump') else {}
                sync = cm.sync_status.value if hasattr(cm.sync_status, 'value') else str(cm.sync_status)
                messages.append(f"Cross-market: US-India {sync}, corr={cm.correlation_20d:.2f}, gap={cm.predicted_india_gap_pct:+.2f}%")
        except Exception as e:
            logger.debug(f"Cross-market analysis skipped: {e}")

        # 5. Regime staleness check (SQ2)
        try:
            for t in ranked_tickers[:3]:
                regime = ma.regime.detect(t, debug=True)
                if hasattr(regime, 'model_age_days') and regime.model_age_days and regime.model_age_days > 60:
                    logger.info(f"Regime model stale for {t}: {regime.model_age_days} days old. Consider retrain.")
                    messages.append(f"Regime stale: {t} ({regime.model_age_days}d old)")
        except Exception:
            pass

        # Store results in context for Maverick
        context['screening_candidates'] = candidates
        context['ranking'] = ranking
        context['black_swan_level'] = black_swan_level
        context['iv_rank_map'] = iv_rank_map

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data={
                'candidates': len(candidates),
                'ranked': len(ranking),
                'black_swan': black_swan_level,
            },
            messages=messages,
            metrics={
                'candidates_found': len(candidates),
                'ranked_count': len(ranking),
            },
            objectives=[
                f"Screened {len(tickers)} tickers, found {len(candidates)} candidates",
                f"Ranked {len(ranking)} candidates for Maverick",
            ],
        )
