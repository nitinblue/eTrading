"""
Scout Agent (Quant) — Domain agent that owns the ResearchContainer.

Responsibilities:
  1. populate(): Fill ResearchContainer from market_analyzer library (regime, technicals,
     fundamentals, macro). Replaces _populate_research_container() from api_research.py.
  2. run(): Evaluate research templates against container data, auto-book triggered
     hypotheses into research portfolios.

Uses config/research_templates.yaml for all hypothesis definitions:
  - Entry conditions evaluated via ConditionEvaluator (generic, config-driven)
  - Leg construction for options via _build_legs() (reuses ScenarioScreener patterns)
  - Equity templates produce single equity leg recommendations
  - Parameter variants tagged with variant_id for A/B comparison

Every MONITORING cycle:
  1. populate() — refresh container from market_analyzer library
  2. run() — evaluate templates, auto-book triggered ones
"""

import copy
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TYPE_CHECKING
import calendar

import yaml

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.services.research.condition_evaluator import (
    ConditionEvaluator, Condition,
)
from trading_cotrader.services.research.template_loader import (
    ResearchTemplate, StrategyVariant, ParameterVariant,
    get_enabled_templates,
)

if TYPE_CHECKING:
    from trading_cotrader.containers.research_container import ResearchContainer, ResearchEntry

logger = logging.getLogger(__name__)


def _round_strike(price: Decimal, step: int = 5) -> Decimal:
    """Round price to nearest strike increment."""
    return Decimal(str(int(round(float(price) / step) * step)))


def _build_option_streamer_symbol(
    ticker: str, expiration_str: str, option_type: str, strike: Decimal,
) -> str:
    """Build DXLink streamer symbol for an option."""
    strike_str = str(int(strike))
    return f".{ticker}{expiration_str}{option_type}{strike_str}"


def _get_nearest_monthly_expiration(dte_target: int = 45) -> str:
    """Get nearest monthly options expiration as YYMMDD string."""
    target_date = datetime.utcnow() + timedelta(days=dte_target)
    year = target_date.year
    month = target_date.month
    cal = calendar.Calendar()

    fridays = [
        d for d in cal.itermonthdates(year, month)
        if d.weekday() == 4 and d.month == month
    ]
    if len(fridays) >= 3:
        third_friday = fridays[2]
    else:
        third_friday = fridays[-1]

    if third_friday < target_date.date():
        month += 1
        if month > 12:
            month = 1
            year += 1
        fridays = [
            d for d in cal.itermonthdates(year, month)
            if d.weekday() == 4 and d.month == month
        ]
        third_friday = fridays[2] if len(fridays) >= 3 else fridays[-1]

    return third_friday.strftime('%y%m%d')


# ---------------------------------------------------------------------------
# ResearchEntry -> ConditionEvaluator adapter
# ---------------------------------------------------------------------------

class _ResearchEntryAdapter:
    """
    Adapts ResearchEntry to the snapshot interface expected by ConditionEvaluator.

    ConditionEvaluator's _SNAPSHOT_FIELDS maps indicator names to snapshot attributes.
    ResearchEntry uses slightly different names. This adapter bridges the gap.
    """

    def __init__(self, entry: 'ResearchEntry'):
        self.symbol = entry.symbol
        self.current_price = Decimal(str(entry.current_price)) if entry.current_price else Decimal('0')
        # ConditionEvaluator maps 'sma_20' -> 'bollinger_middle'
        self.bollinger_middle = entry.sma_20
        self.sma_50 = entry.sma_50
        self.sma_200 = entry.sma_200
        self.ema_20 = entry.ema_21                  # closest available (21 vs 20)
        self.ema_50 = entry.sma_50                  # fallback
        self.rsi_14 = entry.rsi_14
        self.atr_percent = entry.atr_pct
        self.atr_14 = entry.atr
        self.iv_rank = None                         # broker-only, not in ResearchEntry
        self.iv_percentile = None
        self.pct_from_52w_high = entry.pct_from_52w_high
        self.bollinger_upper = entry.bollinger_upper
        self.bollinger_lower = entry.bollinger_lower
        self.bollinger_width = entry.bollinger_bandwidth
        self.vwap = entry.vwma_20                   # closest available
        self.high_52w = None
        self.low_52w = None
        self.nearest_support = entry.support
        self.nearest_resistance = entry.resistance
        self.volume = None
        self.avg_volume_20 = None
        self.directional_regime = None
        self.volatility_regime = None


# ---------------------------------------------------------------------------
# ScoutAgent
# ---------------------------------------------------------------------------

class ScoutAgent(BaseAgent):
    """
    Domain agent that owns the ResearchContainer.

    populate(): Fills container from market_analyzer library (regime, technicals,
                fundamentals, macro). Replaces the old _populate_research_container()
                utility function that lived in api_research.py.

    run(): Evaluates research templates against container data (or falls back to
           TechnicalAnalysisService when container is None), auto-books triggered
           hypotheses into research portfolios.

    Behavior is fully driven by config/research_templates.yaml:
    - Which templates to evaluate (enabled flag)
    - Universe, entry/exit conditions, strategies, variants per template
    - Target research portfolio per template
    """

    # Class-level metadata
    name: ClassVar[str] = "scout"
    display_name: ClassVar[str] = "Scout (Quant)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "Research pipeline executor"
    intro: ClassVar[str] = (
        "I run scenario-based research. 7 templates, parameter variants, "
        "auto-booking into research portfolios. I own the ResearchContainer "
        "and populate it from market data sources."
    )
    responsibilities: ClassVar[List[str]] = [
        "Watchlist data population",
        "Scenario screening",
        "Auto-booking",
        "Parameter variants",
        "Research trade tracking",
    ]
    datasources: ClassVar[List[str]] = [
        "market_analyzer library",
        "research_templates.yaml",
        "ConditionEvaluator",
        "ResearchContainer",
    ]
    boundaries: ClassVar[List[str]] = [
        "Books into research portfolios only (not live)",
        "Cannot modify templates",
        "Auto-accept only for research",
    ]
    runs_during: ClassVar[List[str]] = ["monitoring"]

    def __init__(self, container: 'ResearchContainer' = None, config=None):
        super().__init__(container=container, config=config)
        self._evaluator = ConditionEvaluator()

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

    def _get_market_analyzer(self):
        """Lazy-init MarketAnalyzer facade singleton."""
        if not hasattr(self, '_market_analyzer'):
            from market_analyzer import MarketAnalyzer
            from market_analyzer.data import DataService
            self._market_analyzer = MarketAnalyzer(data_service=DataService())
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
    # run() -- Evaluate research templates
    # -----------------------------------------------------------------

    def run(self, context: dict) -> AgentResult:
        """
        Evaluate all enabled research templates, auto-book triggered ones.

        Reads templates from config/research_templates.yaml.
        Writes 'research_trades_booked' to context.
        """
        # Check if research is enabled in workflow_rules.yaml
        if not self._is_research_enabled():
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'enabled': False},
                messages=["Research pipeline disabled in config"],
            )

        # Load enabled templates
        templates = get_enabled_templates()
        if not templates:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'template_count': 0},
                messages=["No enabled research templates found"],
            )

        # Build global context (VIX, earnings)
        global_ctx = self._build_global_context()

        total_recs = 0
        total_booked = 0
        total_failed = 0
        messages = []
        booked_trades = []

        for template_name, template in templates.items():
            # Resolve universe
            symbols = self._resolve_universe(template)
            if not symbols:
                messages.append(f"{template_name}: no symbols")
                continue

            # Get variants (default to just 'base')
            variants = template.variants or [ParameterVariant(variant_id='base')]

            for variant in variants:
                try:
                    recs, booked, failed = self._evaluate_template_variant(
                        template=template,
                        symbols=symbols,
                        variant=variant,
                        global_ctx=global_ctx,
                    )
                    total_recs += recs
                    total_booked += booked
                    total_failed += failed

                    if booked > 0:
                        booked_trades.append({
                            'template': template_name,
                            'variant': variant.variant_id,
                            'portfolio': template.target_portfolio,
                            'count': booked,
                        })

                except Exception as e:
                    logger.error(f"Research template {template_name}/{variant.variant_id} failed: {e}")
                    messages.append(f"{template_name}/{variant.variant_id}: ERROR {e}")
                    total_failed += 1

            messages.append(f"{template_name}: {len(variants)} variant(s)")

        # Update context
        context['research_trades_booked'] = booked_trades

        summary = f"Research: {total_recs} recs, {total_booked} booked, {total_failed} failed"
        messages.insert(0, summary)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data={
                'recommendations_generated': total_recs,
                'trades_booked': total_booked,
                'trades_failed': total_failed,
                'templates_evaluated': len(templates),
            },
            messages=messages,
            metrics={
                'recs_generated': total_recs,
                'trades_booked': total_booked,
            },
            objectives=[
                f"Evaluated {len(templates)} research templates",
                f"Generated {total_recs} research recommendations",
                f"Auto-booked {total_booked} trades into research portfolios",
            ],
        )

    def _is_research_enabled(self) -> bool:
        """Check if research is enabled in workflow_rules.yaml."""
        try:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'workflow_rules.yaml'
            with open(config_path) as f:
                raw = yaml.safe_load(f)
            research = raw.get('research', {})
            return research.get('enabled', False)
        except Exception as e:
            logger.warning(f"Failed to check research enabled: {e}")
            return False

    def _build_global_context(self) -> Dict[str, Any]:
        """Build global context dict with VIX and earnings data."""
        ctx: Dict[str, Any] = {}

        # VIX -- try from container first, then fallback to TechnicalAnalysisService
        if self.container is not None:
            vix_entry = self.container.get('^VIX')
            if vix_entry and vix_entry.current_price:
                ctx['vix'] = float(vix_entry.current_price)
                return ctx

        try:
            ta = self._get_technical_service()
            if ta:
                vix_snap = ta.get_snapshot('^VIX')
                if vix_snap and vix_snap.current_price:
                    ctx['vix'] = float(vix_snap.current_price)
        except Exception as e:
            logger.debug(f"VIX fetch failed: {e}")

        return ctx

    def _resolve_universe(self, template: ResearchTemplate) -> List[str]:
        """Resolve the symbol universe for a template."""
        if template.universe:
            return list(template.universe)

        if template.universe_from == 'earnings_calendar':
            return self._get_earnings_symbols()

        return []

    def _get_snapshot_from_container(self, symbol: str):
        """Get a ConditionEvaluator-compatible snapshot from the container."""
        if self.container is None:
            return None
        entry = self.container.get(symbol)
        if entry is None or entry.timestamp is None:
            return None
        return _ResearchEntryAdapter(entry)

    def _make_snapshot_adapter(self, entry):
        """Create a ConditionEvaluator-compatible adapter from a ResearchEntry.

        Used by api_trading_sheet.py to evaluate templates against container data
        instead of calling TechnicalAnalysisService directly.
        """
        return _ResearchEntryAdapter(entry)

    def _evaluate_template_variant(
        self,
        template: ResearchTemplate,
        symbols: List[str],
        variant: ParameterVariant,
        global_ctx: Dict[str, Any],
    ) -> Tuple[int, int, int]:
        """
        Evaluate a template with a specific variant against all symbols.

        Returns (recommendations_count, booked_count, failed_count).
        """
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.services.recommendation_service import RecommendationService

        # Apply variant overrides to strategies
        strategies = self._apply_variant_overrides(template, variant)

        recs_count = 0
        booked_count = 0
        failed_count = 0

        with session_scope() as session:
            svc = RecommendationService(session, broker=None)

            for symbol in symbols:
                # Get technical snapshot -- prefer container, fallback to service
                snap = self._get_snapshot_from_container(symbol)
                if snap is None:
                    ta = self._get_technical_service()
                    snap = ta.get_snapshot(symbol) if ta else None

                # Build per-symbol context (earnings days, etc.)
                sym_ctx = dict(global_ctx)
                if template.universe_from == 'earnings_calendar':
                    days = self._get_days_to_earnings(symbol)
                    if days is not None:
                        sym_ctx['days_to_earnings'] = days

                # Evaluate entry conditions (AND logic)
                triggered, details = self._evaluator.evaluate_all(
                    template.entry_conditions, snap, sym_ctx,
                )

                if not triggered:
                    logger.debug(
                        f"Research {template.name}/{variant.variant_id}: "
                        f"{symbol} -- conditions not met"
                    )
                    continue

                logger.info(
                    f"Research {template.name}/{variant.variant_id} "
                    f"TRIGGERED for {symbol}"
                )

                # Build recommendations for each strategy
                for strategy in strategies:
                    try:
                        # Dedup: skip if already booked today for this template/variant/symbol/strategy
                        if self._has_research_duplicate(
                            session, template.name, variant.variant_id,
                            symbol, strategy.strategy_type,
                        ):
                            logger.debug(
                                f"DEDUP: Skipping {symbol}/{strategy.strategy_type} "
                                f"for {template.name}/{variant.variant_id} -- already booked today"
                            )
                            continue

                        rec = self._build_recommendation(
                            template=template,
                            strategy=strategy,
                            symbol=symbol,
                            snap=snap,
                            matched_conditions=details,
                            variant_id=variant.variant_id,
                        )
                        recs_count += 1

                        # Persist recommendation
                        rec_repo = svc.rec_repo
                        created = rec_repo.create_from_domain(rec)
                        if not created:
                            failed_count += 1
                            continue

                        # Auto-accept into target portfolio
                        result = svc.accept_recommendation(
                            rec_id=rec.id,
                            notes=f"Auto-accepted by ScoutAgent ({template.name}/{variant.variant_id})",
                            portfolio_name=template.target_portfolio,
                        )

                        if result.get('success'):
                            booked_count += 1
                            logger.debug(
                                f"Booked research trade {result['trade_id'][:8]}... "
                                f"({symbol} {strategy.strategy_type} -> {template.target_portfolio})"
                            )
                        else:
                            failed_count += 1
                            logger.warning(
                                f"Failed to book research trade: {result.get('error')} "
                                f"({symbol} {strategy.strategy_type})"
                            )

                    except Exception as e:
                        logger.warning(
                            f"Failed to build rec for {symbol}/{strategy.strategy_type}: {e}"
                        )
                        failed_count += 1

        return recs_count, booked_count, failed_count

    def _has_research_duplicate(
        self, session, template_name: str, variant_id: str,
        symbol: str, strategy_type: str,
    ) -> bool:
        """Check if same template/variant/symbol/strategy already booked today."""
        try:
            from trading_cotrader.core.database.schema import RecommendationORM
            from sqlalchemy import func

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            count = (
                session.query(func.count(RecommendationORM.id))
                .filter(
                    RecommendationORM.underlying == symbol,
                    RecommendationORM.strategy_type == strategy_type,
                    RecommendationORM.scenario_template_name == template_name,
                    RecommendationORM.created_at >= today_start,
                )
                .scalar() or 0
            )
            return count > 0
        except Exception as e:
            logger.warning(f"Research dedup check failed: {e}")
            return False

    def _apply_variant_overrides(
        self, template: ResearchTemplate, variant: ParameterVariant,
    ) -> List[StrategyVariant]:
        """Apply variant parameter overrides to template strategies."""
        if not variant.overrides or not template.trade_strategy.strategies:
            return list(template.trade_strategy.strategies)

        # Deep-copy to avoid mutating the originals
        strategies = copy.deepcopy(template.trade_strategy.strategies)
        for strategy in strategies:
            for key, value in variant.overrides.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)

        return strategies

    def _build_recommendation(
        self,
        template: ResearchTemplate,
        strategy: StrategyVariant,
        symbol: str,
        snap: Any,
        matched_conditions: Dict[str, Any],
        variant_id: str,
    ) -> 'Recommendation':
        """Build a Recommendation from a template strategy + matched conditions."""
        from trading_cotrader.core.models.recommendation import (
            Recommendation, RecommendedLeg, MarketSnapshot,
        )

        price = snap.current_price if snap else Decimal('100')

        # Build market context
        market_ctx = MarketSnapshot(underlying_price=price)
        if snap:
            market_ctx.iv_rank = Decimal(str(snap.iv_rank)) if getattr(snap, 'iv_rank', None) else None
            market_ctx.rsi = Decimal(str(snap.rsi_14)) if getattr(snap, 'rsi_14', None) else None
            market_ctx.ema_20 = getattr(snap, 'ema_20', None)
            market_ctx.ema_50 = getattr(snap, 'ema_50', None)
            market_ctx.sma_200 = getattr(snap, 'sma_200', None)
            market_ctx.atr_percent = getattr(snap, 'atr_percent', None)
            market_ctx.directional_regime = getattr(snap, 'directional_regime', None)
            market_ctx.volatility_regime = getattr(snap, 'volatility_regime', None)
            market_ctx.pct_from_52w_high = getattr(snap, 'pct_from_52w_high', None)

        # Build legs based on instrument type
        if template.trade_strategy.instrument == 'equity':
            legs = self._build_equity_legs(symbol, template)
            strategy_type_str = f"equity_{template.trade_strategy.position_type or 'long'}"
        else:
            legs = self._build_option_legs(symbol, strategy, price)
            strategy_type_str = strategy.strategy_type

        # Build rationale
        condition_summary = ", ".join(
            f"{k}={v.get('actual')}" for k, v in matched_conditions.items()
            if isinstance(v, dict) and v.get('passed')
        )
        rationale = (
            f"{template.display_name} triggered for {symbol}. "
            f"Conditions: {condition_summary}"
        )

        # Tag with variant and template info
        trigger_info = {
            'variant_id': variant_id,
            'template_name': template.name,
            'template_author': template.author,
        }
        # Add matched condition actuals
        for k, v in matched_conditions.items():
            if isinstance(v, dict):
                trigger_info[f'cond_{k}'] = v.get('actual')

        return Recommendation(
            source='research_template',
            screener_name=template.display_name,
            underlying=symbol,
            strategy_type=strategy_type_str,
            legs=legs,
            market_context=market_ctx,
            confidence=strategy.confidence if hasattr(strategy, 'confidence') else 5,
            rationale=rationale,
            risk_category=strategy.risk_category if hasattr(strategy, 'risk_category') else 'defined',
            suggested_portfolio=template.target_portfolio,
            scenario_template_name=template.name,
            scenario_type=template.cadence,
            trigger_conditions_met=trigger_info,
        )

    def _build_equity_legs(
        self, symbol: str, template: ResearchTemplate,
    ) -> List:
        """Build a single equity leg for equity-type templates."""
        from trading_cotrader.core.models.recommendation import RecommendedLeg

        qty = 1 if (template.trade_strategy.position_type or 'long') == 'long' else -1
        return [
            RecommendedLeg(
                streamer_symbol=symbol,
                quantity=qty,
            ),
        ]

    def _build_option_legs(
        self,
        symbol: str,
        strategy: StrategyVariant,
        price: Decimal,
    ) -> List:
        """Build option legs from strategy parameters (reuses ScenarioScreener patterns)."""
        from trading_cotrader.core.models.recommendation import RecommendedLeg

        st = strategy.strategy_type
        dte = strategy.dte_target or 45
        expiration = _get_nearest_monthly_expiration(dte_target=dte)
        legs = []

        if st == 'vertical_spread':
            delta = strategy.short_delta or 0.30
            wing = strategy.wing_width_pct or 0.05
            opt_type = (strategy.option_type or 'put').upper()[0]
            if (strategy.direction or 'sell') == 'sell' and opt_type == 'P':
                short_strike = _round_strike(price * (1 - Decimal(str(delta))))
                long_strike = _round_strike(short_strike - price * Decimal(str(wing)))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, expiration, opt_type, long_strike),
                        quantity=1, strike=long_strike, option_type='put', expiration=expiration,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, expiration, opt_type, short_strike),
                        quantity=-1, delta_target=Decimal(str(delta)), strike=short_strike, option_type='put', expiration=expiration,
                    ),
                ]
            else:
                short_strike = _round_strike(price * (1 + Decimal(str(delta))))
                long_strike = _round_strike(short_strike + price * Decimal(str(wing)))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', short_strike),
                        quantity=-1, delta_target=Decimal(str(delta)), strike=short_strike, option_type='call', expiration=expiration,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', long_strike),
                        quantity=1, strike=long_strike, option_type='call', expiration=expiration,
                    ),
                ]

        elif st == 'strangle':
            delta = strategy.delta_target or 0.16
            offset = Decimal(str(delta))
            put_strike = _round_strike(price * (1 - offset))
            call_strike = _round_strike(price * (1 + offset))
            qty = -1 if (strategy.direction or 'sell') == 'sell' else 1
            legs = [
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'P', put_strike),
                    quantity=qty, delta_target=Decimal(str(delta)), strike=put_strike, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', call_strike),
                    quantity=qty, delta_target=Decimal(str(delta)), strike=call_strike, option_type='call', expiration=expiration,
                ),
            ]

        elif st == 'iron_condor':
            delta = strategy.short_delta or 0.20
            wing = strategy.wing_width_pct or 0.08
            offset = Decimal(str(delta))
            wing_d = price * Decimal(str(wing))
            put_short = _round_strike(price * (1 - offset))
            put_long = _round_strike(put_short - wing_d)
            call_short = _round_strike(price * (1 + offset))
            call_long = _round_strike(call_short + wing_d)
            legs = [
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'P', put_long),
                    quantity=1, strike=put_long, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'P', put_short),
                    quantity=-1, delta_target=Decimal(str(delta)), strike=put_short, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', call_short),
                    quantity=-1, delta_target=Decimal(str(delta)), strike=call_short, option_type='call', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', call_long),
                    quantity=1, strike=call_long, option_type='call', expiration=expiration,
                ),
            ]

        elif st == 'iron_butterfly':
            atm = _round_strike(price)
            wing = Decimal('10')
            legs = [
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'P', atm - wing),
                    quantity=1, strike=atm - wing, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'P', atm),
                    quantity=-1, strike=atm, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', atm),
                    quantity=-1, strike=atm, option_type='call', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, 'C', atm + wing),
                    quantity=1, strike=atm + wing, option_type='call', expiration=expiration,
                ),
            ]

        elif st == 'single':
            opt_type = (strategy.option_type or 'put').upper()[0]
            delta = strategy.delta_target or 0.20
            if opt_type == 'P':
                strike = _round_strike(price * (1 - Decimal(str(delta))))
            else:
                strike = _round_strike(price * (1 + Decimal(str(delta))))
            qty = 1 if (strategy.direction or 'buy') == 'buy' else -1
            legs = [
                RecommendedLeg(
                    streamer_symbol=_build_option_streamer_symbol(symbol, expiration, opt_type, strike),
                    quantity=qty, delta_target=Decimal(str(delta)), strike=strike,
                    option_type='put' if opt_type == 'P' else 'call', expiration=expiration,
                ),
            ]

        elif st in ('calendar_spread', 'double_calendar', 'calendar_double_spread'):
            near_dte = strategy.near_dte_target or 7
            far_dte = strategy.far_dte_target or 30
            near_exp = _get_nearest_monthly_expiration(dte_target=near_dte)
            far_exp = _get_nearest_monthly_expiration(dte_target=far_dte)

            if st == 'calendar_spread':
                opt_type = (strategy.option_type or 'call').upper()[0]
                delta = strategy.delta_target or 0.40
                if opt_type == 'C':
                    strike = _round_strike(price * (1 + Decimal(str(delta)) * Decimal('0.1')))
                else:
                    strike = _round_strike(price * (1 - Decimal(str(delta)) * Decimal('0.1')))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, near_exp, opt_type, strike),
                        quantity=-1, strike=strike,
                        option_type='call' if opt_type == 'C' else 'put', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, far_exp, opt_type, strike),
                        quantity=1, strike=strike,
                        option_type='call' if opt_type == 'C' else 'put', expiration=far_exp,
                    ),
                ]
            else:
                # Double calendar
                put_delta = strategy.put_delta or 0.35
                call_delta = strategy.call_delta or 0.35
                put_strike = _round_strike(price * (1 - Decimal(str(put_delta)) * Decimal('0.1')))
                call_strike = _round_strike(price * (1 + Decimal(str(call_delta)) * Decimal('0.1')))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, near_exp, 'P', put_strike),
                        quantity=-1, strike=put_strike, option_type='put', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, far_exp, 'P', put_strike),
                        quantity=1, strike=put_strike, option_type='put', expiration=far_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, near_exp, 'C', call_strike),
                        quantity=-1, strike=call_strike, option_type='call', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=_build_option_streamer_symbol(symbol, far_exp, 'C', call_strike),
                        quantity=1, strike=call_strike, option_type='call', expiration=far_exp,
                    ),
                ]

        return legs

    def _get_technical_service(self):
        """Get or create TechnicalAnalysisService (cached). Fallback for when container is None."""
        if not hasattr(self, '_technical_service'):
            try:
                from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
                self._technical_service = TechnicalAnalysisService(use_mock=True)
            except Exception as e:
                logger.warning(f"TechnicalAnalysisService unavailable: {e}")
                self._technical_service = None
        return self._technical_service

    def _get_earnings_symbols(self) -> List[str]:
        """Get symbols with upcoming earnings from EarningsCalendarService."""
        try:
            from trading_cotrader.services.earnings_calendar_service import EarningsCalendarService
            svc = EarningsCalendarService()

            candidates = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
                'AMD', 'JPM', 'V', 'MA', 'DIS', 'NFLX', 'CRM', 'ADBE',
                'INTC', 'PYPL', 'SQ', 'UBER', 'ABNB',
            ]

            symbols_with_earnings = []
            for symbol in candidates:
                days = svc.days_to_earnings(symbol)
                if days is not None and 1 <= days <= 14:
                    symbols_with_earnings.append(symbol)

            logger.info(f"Earnings calendar: {len(symbols_with_earnings)} symbols with upcoming earnings")
            return symbols_with_earnings

        except Exception as e:
            logger.warning(f"Failed to get earnings symbols: {e}")
            return []

    def _get_days_to_earnings(self, symbol: str) -> Optional[int]:
        """Get days to earnings for a specific symbol."""
        try:
            from trading_cotrader.services.earnings_calendar_service import EarningsCalendarService
            if not hasattr(self, '_earnings_svc'):
                self._earnings_svc = EarningsCalendarService()
            return self._earnings_svc.days_to_earnings(symbol)
        except Exception:
            return None
