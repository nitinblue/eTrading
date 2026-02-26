"""
Scenario Screener Base — Evaluates YAML-defined trigger conditions against market data.

Extends ScreenerBase with scenario-specific logic:
- Generic trigger evaluation from ScenarioTrigger fields vs TechnicalSnapshot
- Dynamic recommendation building from ScenarioStrategy templates
- Pluggable context dict for extra conditions (earnings, drawdown, etc.)
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)
from trading_cotrader.config.scenario_template_loader import (
    ScenarioTemplate, ScenarioStrategy
)
from trading_cotrader.services.screeners.screener_base import ScreenerBase

logger = logging.getLogger(__name__)


class ScenarioScreener(ScreenerBase):
    """Base class for scenario-triggered screeners."""

    scenario_name: str = ""

    def __init__(self, broker=None, technical_service=None,
                 template: Optional[ScenarioTemplate] = None):
        super().__init__(broker, technical_service)
        self.template = template
        if template:
            self.scenario_name = template.name
            self.name = template.display_name
            self.source = f"scenario_{template.scenario_type}"

    def evaluate_trigger(
        self, symbol: str, tech_snap, extra_context: Optional[dict] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if this scenario's trigger conditions are met for a symbol.

        Args:
            symbol: Underlying ticker.
            tech_snap: TechnicalSnapshot (may be None for mock).
            extra_context: Additional context (e.g. days_to_earnings).

        Returns:
            (triggered, reason, matched_conditions)
        """
        if self.template is None:
            return False, "no template loaded", {}

        trigger = self.template.trigger
        matched: Dict[str, Any] = {}
        ctx = extra_context or {}

        if tech_snap is None:
            return False, "no technical data", {}

        # pct_from_52w_high range [min, max]
        if trigger.pct_from_52w_high is not None:
            val = tech_snap.pct_from_52w_high
            if val is None:
                return False, "pct_from_52w_high unavailable", matched
            lo, hi = trigger.pct_from_52w_high
            if not (lo <= val <= hi):
                return False, f"pct_from_high={val:.1f}% outside [{lo}, {hi}]", matched
            matched['pct_from_high'] = val

        # pct_from_52w_high_max (single-sided)
        if trigger.pct_from_52w_high_max is not None:
            val = tech_snap.pct_from_52w_high
            if val is None:
                return False, "pct_from_52w_high unavailable", matched
            if val > trigger.pct_from_52w_high_max:
                return False, f"pct_from_high={val:.1f}% > max {trigger.pct_from_52w_high_max}", matched
            matched['pct_from_high'] = val

        # VIX range [min, max]
        vix_val = ctx.get('vix')
        if trigger.vix is not None:
            if vix_val is None:
                return False, "VIX unavailable", matched
            lo, hi = trigger.vix
            if not (lo <= float(vix_val) <= hi):
                return False, f"VIX={vix_val:.1f} outside [{lo}, {hi}]", matched
            matched['vix'] = float(vix_val)

        # VIX minimum
        if trigger.vix_min is not None:
            if vix_val is None:
                return False, "VIX unavailable", matched
            if float(vix_val) < trigger.vix_min:
                return False, f"VIX={vix_val:.1f} < min {trigger.vix_min}", matched
            matched['vix'] = float(vix_val)

        # RSI max
        if trigger.rsi_max is not None:
            val = tech_snap.rsi_14
            if val is None:
                return False, "RSI unavailable", matched
            if val > trigger.rsi_max:
                return False, f"RSI={val:.1f} > max {trigger.rsi_max}", matched
            matched['rsi'] = val

        # RSI range
        if trigger.rsi_range is not None:
            val = tech_snap.rsi_14
            if val is None:
                return False, "RSI unavailable", matched
            lo, hi = trigger.rsi_range
            if not (lo <= val <= hi):
                return False, f"RSI={val:.1f} outside [{lo}, {hi}]", matched
            matched['rsi'] = val

        # IV rank minimum
        if trigger.iv_rank_min is not None:
            val = tech_snap.iv_rank
            if val is None:
                return False, "IV rank unavailable", matched
            if val < trigger.iv_rank_min:
                return False, f"IV rank={val:.0f} < min {trigger.iv_rank_min}", matched
            matched['iv_rank'] = val

        # Directional regime
        if trigger.directional_regime is not None:
            val = tech_snap.directional_regime
            if val not in trigger.directional_regime:
                return False, f"regime={val} not in {trigger.directional_regime}", matched
            matched['directional_regime'] = val

        # Volatility regime
        if trigger.volatility_regime is not None:
            val = tech_snap.volatility_regime
            if val not in trigger.volatility_regime:
                return False, f"vol_regime={val} not in {trigger.volatility_regime}", matched
            matched['volatility_regime'] = val

        # Days to earnings
        if trigger.days_to_earnings is not None:
            val = ctx.get('days_to_earnings')
            if val is None:
                return False, "days_to_earnings unavailable", matched
            lo, hi = trigger.days_to_earnings
            if not (lo <= val <= hi):
                return False, f"days_to_earnings={val} outside [{lo}, {hi}]", matched
            matched['days_to_earnings'] = val

        # Bollinger width minimum
        if trigger.bollinger_width_min is not None:
            val = tech_snap.bollinger_width
            if val is None:
                return False, "bollinger_width unavailable", matched
            if val < trigger.bollinger_width_min:
                return False, f"bollinger_width={val:.4f} < min {trigger.bollinger_width_min}", matched
            matched['bollinger_width'] = val

        return True, "all trigger conditions met", matched

    def build_recommendation(
        self,
        symbol: str,
        strategy: ScenarioStrategy,
        tech_snap,
        matched: Dict[str, Any],
    ) -> Recommendation:
        """
        Build a Recommendation from a ScenarioStrategy + matched trigger context.
        """
        price = tech_snap.current_price if tech_snap else Decimal('100')
        dte = strategy.dte_target

        # Build market context
        market_ctx = MarketSnapshot(
            underlying_price=price,
            vix=Decimal(str(matched.get('vix', 0))) if matched.get('vix') else None,
            iv_rank=Decimal(str(matched.get('iv_rank', 0))) if matched.get('iv_rank') else None,
        )
        if tech_snap:
            market_ctx = self._enrich_market_context(market_ctx, tech_snap)

        # Build legs based on strategy type
        expiration = self._get_nearest_monthly_expiration(dte_target=dte)
        legs = self._build_legs(symbol, strategy, price, expiration)

        # Format rationale
        rationale = self._format_rationale(symbol, matched)

        # Determine suggested portfolio
        suggested = strategy.route_to_portfolios[0] if strategy.route_to_portfolios else None

        return Recommendation(
            source=self.source,
            screener_name=self.name,
            underlying=symbol,
            strategy_type=strategy.strategy_type,
            legs=legs,
            market_context=market_ctx,
            confidence=strategy.confidence,
            rationale=rationale,
            risk_category=strategy.risk_category,
            suggested_portfolio=suggested,
            scenario_template_name=self.template.name if self.template else None,
            scenario_type=self.template.scenario_type if self.template else None,
            trigger_conditions_met=matched,
        )

    def _build_legs(
        self,
        symbol: str,
        strategy: ScenarioStrategy,
        price: Decimal,
        expiration: str,
    ) -> List[RecommendedLeg]:
        """Build option legs from strategy parameters."""
        from trading_cotrader.services.screeners.vix_regime_screener import _round_strike

        legs = []
        st = strategy.strategy_type

        if st == 'vertical_spread':
            delta = strategy.short_delta or 0.30
            wing = strategy.wing_width_pct or 0.05
            opt_type = (strategy.option_type or 'put').upper()[0]
            if strategy.direction == 'sell' and opt_type == 'P':
                short_strike = _round_strike(price * (1 - Decimal(str(delta))))
                long_strike = _round_strike(short_strike - price * Decimal(str(wing)))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, opt_type, long_strike),
                        quantity=1, strike=long_strike, option_type='put', expiration=expiration,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, opt_type, short_strike),
                        quantity=-1, delta_target=Decimal(str(delta)), strike=short_strike, option_type='put', expiration=expiration,
                    ),
                ]
            else:
                # Call credit spread
                short_strike = _round_strike(price * (1 + Decimal(str(delta))))
                long_strike = _round_strike(short_strike + price * Decimal(str(wing)))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', short_strike),
                        quantity=-1, delta_target=Decimal(str(delta)), strike=short_strike, option_type='call', expiration=expiration,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', long_strike),
                        quantity=1, strike=long_strike, option_type='call', expiration=expiration,
                    ),
                ]

        elif st == 'strangle':
            delta = strategy.delta_target or 0.16
            offset = Decimal(str(delta))
            put_strike = _round_strike(price * (1 - offset))
            call_strike = _round_strike(price * (1 + offset))
            qty = -1 if strategy.direction == 'sell' else 1
            legs = [
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'P', put_strike),
                    quantity=qty, delta_target=Decimal(str(delta)), strike=put_strike, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', call_strike),
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
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'P', put_long),
                    quantity=1, strike=put_long, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'P', put_short),
                    quantity=-1, delta_target=Decimal(str(delta)), strike=put_short, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', call_short),
                    quantity=-1, delta_target=Decimal(str(delta)), strike=call_short, option_type='call', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', call_long),
                    quantity=1, strike=call_long, option_type='call', expiration=expiration,
                ),
            ]

        elif st == 'iron_butterfly':
            atm = _round_strike(price)
            wing = Decimal('10')
            legs = [
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'P', atm - wing),
                    quantity=1, strike=atm - wing, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'P', atm),
                    quantity=-1, strike=atm, option_type='put', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', atm),
                    quantity=-1, strike=atm, option_type='call', expiration=expiration,
                ),
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, 'C', atm + wing),
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
            qty = 1 if strategy.direction == 'buy' else -1
            legs = [
                RecommendedLeg(
                    streamer_symbol=self._build_option_streamer_symbol(symbol, expiration, opt_type, strike),
                    quantity=qty, delta_target=Decimal(str(delta)), strike=strike,
                    option_type='put' if opt_type == 'P' else 'call', expiration=expiration,
                ),
            ]

        elif st in ('calendar_spread', 'calendar_double_spread'):
            near_dte = strategy.near_dte_target or 7
            far_dte = strategy.far_dte_target or 30
            near_exp = self._get_nearest_monthly_expiration(dte_target=near_dte)
            far_exp = self._get_nearest_monthly_expiration(dte_target=far_dte)

            if st == 'calendar_spread':
                opt_type = (strategy.option_type or 'call').upper()[0]
                delta = strategy.delta_target or 0.40
                if opt_type == 'C':
                    strike = _round_strike(price * (1 + Decimal(str(delta)) * Decimal('0.1')))
                else:
                    strike = _round_strike(price * (1 - Decimal(str(delta)) * Decimal('0.1')))
                legs = [
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, near_exp, opt_type, strike),
                        quantity=-1, strike=strike, option_type='call' if opt_type == 'C' else 'put', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, far_exp, opt_type, strike),
                        quantity=1, strike=strike, option_type='call' if opt_type == 'C' else 'put', expiration=far_exp,
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
                        streamer_symbol=self._build_option_streamer_symbol(symbol, near_exp, 'P', put_strike),
                        quantity=-1, strike=put_strike, option_type='put', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, far_exp, 'P', put_strike),
                        quantity=1, strike=put_strike, option_type='put', expiration=far_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, near_exp, 'C', call_strike),
                        quantity=-1, strike=call_strike, option_type='call', expiration=near_exp,
                    ),
                    RecommendedLeg(
                        streamer_symbol=self._build_option_streamer_symbol(symbol, far_exp, 'C', call_strike),
                        quantity=1, strike=call_strike, option_type='call', expiration=far_exp,
                    ),
                ]

        return legs

    def _format_rationale(self, symbol: str, matched: Dict[str, Any]) -> str:
        """Format rationale from template + matched conditions."""
        if not self.template or not self.template.rationale_template:
            return f"Scenario {self.scenario_name} triggered for {symbol}"

        try:
            return self.template.rationale_template.format(
                underlying=symbol,
                **matched,
            )
        except (KeyError, ValueError):
            parts = [f"{k}={v}" for k, v in matched.items()]
            return f"Scenario {self.scenario_name} triggered for {symbol}: {', '.join(parts)}"

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        For each symbol: evaluate_trigger → if triggered, build_recommendation
        for each strategy in template.strategies.
        """
        if not self.template or not self.template.enabled:
            return []

        recommendations = []
        extra_context = self._build_extra_context(symbols)

        for symbol in symbols:
            tech_snap = self._get_technical_snapshot(symbol)
            sym_ctx = extra_context.get(symbol, extra_context.get('_global', {}))

            triggered, reason, matched = self.evaluate_trigger(symbol, tech_snap, sym_ctx)
            if not triggered:
                logger.debug(f"Scenario {self.scenario_name}: {symbol} — {reason}")
                continue

            logger.info(f"Scenario {self.scenario_name} TRIGGERED for {symbol}: {reason}")

            for strategy in self.template.strategies:
                try:
                    rec = self.build_recommendation(symbol, strategy, tech_snap, matched)
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(
                        f"Failed to build rec for {symbol}/{strategy.strategy_type}: {e}"
                    )

        return recommendations

    def _build_extra_context(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Build extra context for trigger evaluation. Override in subclasses.

        Returns:
            Dict of symbol → context dict. Use '_global' for cross-symbol context.
        """
        return {}
