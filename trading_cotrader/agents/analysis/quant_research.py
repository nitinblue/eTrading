"""
Quant Research Agent — Evaluates research templates, auto-books into research portfolios.

Uses config/research_templates.yaml for all hypothesis definitions:
  - Entry conditions evaluated via ConditionEvaluator (generic, config-driven)
  - Leg construction for options via _build_legs() (reuses ScenarioScreener patterns)
  - Equity templates produce single equity leg recommendations
  - Parameter variants tagged with variant_id for A/B comparison

Every MONITORING cycle:
  1. Load enabled research templates from YAML
  2. Build global context (VIX, earnings calendar)
  3. For each template → for each symbol in universe → evaluate entry conditions
  4. If triggered → build Recommendation → auto-book into target_portfolio
  5. Track results in context for reporting
"""

import copy
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import calendar

from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.services.research.condition_evaluator import (
    ConditionEvaluator, Condition,
)
from trading_cotrader.services.research.template_loader import (
    ResearchTemplate, StrategyVariant, ParameterVariant,
    get_enabled_templates,
)

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


class QuantResearchAgent:
    """
    Evaluates research templates, auto-books triggered hypotheses into research portfolios.

    Behavior is fully driven by config/research_templates.yaml:
    - Which templates to evaluate (enabled flag)
    - Universe, entry/exit conditions, strategies, variants per template
    - Target research portfolio per template

    The agent does NOT make autonomous decisions. It evaluates conditions
    faithfully and tracks outcomes for ML training.
    """

    name = "quant_research"

    def __init__(self, config=None):
        self.config = config
        self._evaluator = ConditionEvaluator()

    def safety_check(self, context: dict) -> tuple[bool, str]:
        """Research pipeline is always safe — no real capital involved."""
        return True, ""

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
            import yaml
            from pathlib import Path
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

        # VIX — try mock/yfinance
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

        ta = self._get_technical_service()

        with session_scope() as session:
            svc = RecommendationService(session, broker=None)

            for symbol in symbols:
                # Get technical snapshot
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
                        f"{symbol} — conditions not met"
                    )
                    continue

                logger.info(
                    f"Research {template.name}/{variant.variant_id} "
                    f"TRIGGERED for {symbol}"
                )

                # Build recommendations for each strategy
                for strategy in strategies:
                    try:
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
                            notes=f"Auto-accepted by QuantResearchAgent ({template.name}/{variant.variant_id})",
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
            market_ctx.iv_rank = Decimal(str(snap.iv_rank)) if snap.iv_rank else None
            market_ctx.rsi = Decimal(str(snap.rsi_14)) if snap.rsi_14 else None
            market_ctx.ema_20 = snap.ema_20
            market_ctx.ema_50 = snap.ema_50
            market_ctx.sma_200 = snap.sma_200
            market_ctx.atr_percent = snap.atr_percent
            market_ctx.directional_regime = snap.directional_regime
            market_ctx.volatility_regime = snap.volatility_regime
            market_ctx.pct_from_52w_high = snap.pct_from_52w_high

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
        """Get or create TechnicalAnalysisService (cached)."""
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
