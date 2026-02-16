"""
Portfolio Evaluation Service — Continuously evaluates open trades and
generates exit/roll/adjust recommendations.

Wires the existing RulesEngine to real trade data and generates
Recommendation objects (same as entry recommendations) with
recommendation_type = EXIT / ROLL / ADJUST.

Pipeline:
    Open Trades → RulesEngine (profit target, stop loss, DTE, delta) →
    PositionAction → Liquidity Check → Recommendation (EXIT/ROLL/ADJUST)

Usage:
    from trading_cotrader.services.portfolio_evaluation_service import PortfolioEvaluationService
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        svc = PortfolioEvaluationService(session, broker=broker)
        recs = svc.evaluate_portfolio('high_risk')
        for rec in recs:
            print(f"{rec.underlying}: {rec.recommendation_type.value} — {rec.rationale}")
"""

from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal
import logging

from sqlalchemy.orm import Session

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendationType, RecommendedLeg, MarketSnapshot
)
from trading_cotrader.core.models.domain import TradeSource
from trading_cotrader.repositories.recommendation import RecommendationRepository
from trading_cotrader.repositories.trade import TradeRepository
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.services.position_mgmt.rules_engine import (
    RulesEngine, ActionType, PositionAction, RulePriority,
    ProfitTargetRule, StopLossRule, DTEExitRule, DeltaBreachRule,
)
from trading_cotrader.services.liquidity_service import LiquidityService

logger = logging.getLogger(__name__)


class PortfolioEvaluationService:
    """
    Evaluates open trades against exit rules and generates
    exit/roll/adjust recommendations.
    """

    def __init__(self, session: Session, broker=None):
        self.session = session
        self.broker = broker
        self.trade_repo = TradeRepository(session)
        self.portfolio_repo = PortfolioRepository(session)
        self.rec_repo = RecommendationRepository(session)
        self.liquidity_svc = LiquidityService(broker=broker)

    def evaluate_portfolio(
        self,
        portfolio_name: str,
        dry_run: bool = False,
    ) -> List[Recommendation]:
        """
        Evaluate all open trades in a portfolio and generate recommendations.

        Args:
            portfolio_name: Portfolio config name (e.g. 'high_risk').
            dry_run: If True, return recs without saving to DB.

        Returns:
            List of exit/roll/adjust Recommendations.
        """
        # Get portfolio from DB
        portfolio = self.portfolio_repo.get_by_account(
            broker='cotrader', account_id=portfolio_name
        )
        if not portfolio:
            logger.warning(f"Portfolio '{portfolio_name}' not found")
            return []

        # Get open trades
        open_trades = self.trade_repo.get_by_portfolio(
            portfolio.id, open_only=True
        )
        if not open_trades:
            logger.info(f"No open trades in portfolio '{portfolio_name}'")
            return []

        logger.info(
            f"Evaluating {len(open_trades)} open trades in '{portfolio_name}'"
        )

        # Build rules engine from config
        engine = self._build_rules_engine(portfolio_name)
        if not engine.rules:
            logger.warning("No exit rules configured — using defaults")
            engine = self._default_rules_engine()

        # Evaluate each trade
        recommendations = []
        for trade in open_trades:
            recs = self._evaluate_trade(trade, engine, portfolio_name)
            recommendations.extend(recs)

        # Save to DB unless dry_run
        if not dry_run and recommendations:
            saved = []
            for rec in recommendations:
                created = self.rec_repo.create_from_domain(rec)
                if created:
                    saved.append(created)
            logger.info(f"Saved {len(saved)} exit recommendations to DB")
            return saved

        return recommendations

    def evaluate_all_portfolios(
        self,
        dry_run: bool = False,
    ) -> Dict[str, List[Recommendation]]:
        """
        Evaluate all managed portfolios.

        Returns:
            Dict of portfolio_name -> List[Recommendation].
        """
        try:
            from trading_cotrader.services.portfolio_manager import PortfolioManager
            pm = PortfolioManager(self.session)
            portfolios = pm.get_all_managed_portfolios()
        except Exception as e:
            logger.error(f"Failed to get managed portfolios: {e}")
            return {}

        results = {}
        for portfolio in portfolios:
            # Extract config name from account_id
            config_name = portfolio.account_id
            recs = self.evaluate_portfolio(config_name, dry_run=dry_run)
            if recs:
                results[config_name] = recs

        return results

    def _evaluate_trade(
        self,
        trade,
        engine: RulesEngine,
        portfolio_name: str,
    ) -> List[Recommendation]:
        """Evaluate a single trade against rules and generate recommendations."""
        # Build a position-like object from the trade for the rules engine
        mock_position = _TradeAsPosition(trade)

        # Evaluate
        action = engine.evaluate_position(
            position=mock_position,
            trade=trade,
            market_data={},
        )

        if not action.should_act():
            return []

        # Check liquidity for adjustment/roll
        liquidity_ok = True
        liquidity_reason = ""
        if trade.legs:
            for leg in trade.legs:
                if hasattr(leg, 'symbol') and leg.symbol and leg.symbol.is_option:
                    # Build streamer symbol from leg
                    streamer_sym = self._leg_to_streamer_symbol(leg)
                    if streamer_sym:
                        snap = self.liquidity_svc.check_liquidity(streamer_sym)
                        if not self.liquidity_svc.meets_adjustment_threshold(snap):
                            liquidity_ok = False
                            liquidity_reason = self.liquidity_svc.get_liquidity_reason(
                                snap, self.liquidity_svc.config.adjustment
                            )
                            break

        # Determine recommendation type based on action + liquidity
        rec_type, rec_action = self._determine_rec_type(action, liquidity_ok)

        # Build rationale
        rule_names = [r.rule_name for r in action.triggered_rules]
        rationale = f"{action.primary_reason}"
        if not liquidity_ok:
            rationale += f" [illiquid: {liquidity_reason} → recommending CLOSE instead of {action.action.value}]"

        # Build recommendation
        rec = Recommendation(
            recommendation_type=rec_type,
            source=TradeSource.MANUAL.value,
            screener_name="portfolio_evaluation",
            underlying=trade.underlying_symbol or "",
            strategy_type=getattr(trade, 'strategy_type', '') or '',
            legs=self._trade_legs_to_rec_legs(trade),
            market_context=MarketSnapshot(timestamp=datetime.utcnow()),
            confidence=self._action_to_confidence(action),
            rationale=rationale,
            risk_category=getattr(trade, 'risk_category', 'defined') or 'defined',
            suggested_portfolio=portfolio_name,
            trade_id_to_close=trade.id,
            exit_action=rec_action,
            exit_urgency=action.urgency,
            triggered_rules=rule_names,
        )

        return [rec]

    def _determine_rec_type(
        self, action: PositionAction, liquidity_ok: bool
    ) -> tuple:
        """
        Determine recommendation type from RulesEngine action + liquidity.

        If illiquid, downgrade ROLL/ADJUST → CLOSE.
        """
        if action.action == ActionType.CLOSE:
            return RecommendationType.EXIT, ActionType.CLOSE.value
        elif action.action == ActionType.ROLL:
            if liquidity_ok:
                return RecommendationType.ROLL, ActionType.ROLL.value
            else:
                return RecommendationType.EXIT, ActionType.CLOSE.value
        elif action.action == ActionType.ADJUST:
            if liquidity_ok:
                return RecommendationType.ADJUST, ActionType.ADJUST.value
            else:
                return RecommendationType.EXIT, ActionType.CLOSE.value
        elif action.action == ActionType.HEDGE:
            return RecommendationType.ADJUST, ActionType.HEDGE.value
        else:
            return RecommendationType.EXIT, ActionType.CLOSE.value

    def _action_to_confidence(self, action: PositionAction) -> int:
        """Map action priority to confidence 1-10."""
        if action.priority == RulePriority.CRITICAL:
            return 10
        elif action.priority == RulePriority.HIGH:
            return 8
        elif action.priority == RulePriority.MEDIUM:
            return 6
        else:
            return 4

    def _build_rules_engine(self, portfolio_name: str) -> RulesEngine:
        """Build rules engine from portfolio's exit_rule_profile."""
        try:
            from trading_cotrader.config.risk_config_loader import get_risk_config
            config = get_risk_config()

            portfolio_config = config.portfolios.get_by_name(portfolio_name)
            if not portfolio_config:
                return RulesEngine.from_config(config)

            profile_name = portfolio_config.exit_rule_profile
            profile = config.exit_rule_profiles.get(profile_name)
            if not profile:
                return RulesEngine.from_config(config)

            # Build rules from profile
            rules = [
                ProfitTargetRule(
                    target_percent=profile.profit_target_pct,
                    name=f"{profile_name}_profit_target",
                    priority=1,
                ),
                StopLossRule(
                    max_loss_percent=profile.stop_loss_multiplier * 100,
                    name=f"{profile_name}_stop_loss",
                    priority=1,
                ),
                DTEExitRule(
                    dte_threshold=profile.roll_dte,
                    name=f"{profile_name}_roll_dte",
                    priority=2,
                ),
                DTEExitRule(
                    dte_threshold=profile.close_dte,
                    name=f"{profile_name}_close_dte",
                    priority=1,
                ),
            ]
            return RulesEngine(rules)

        except Exception as e:
            logger.warning(f"Failed to build rules engine from config: {e}")
            return self._default_rules_engine()

    def _default_rules_engine(self) -> RulesEngine:
        """Default rules engine with sensible defaults."""
        return RulesEngine([
            ProfitTargetRule(target_percent=50, name="default_profit_50pct", priority=1),
            StopLossRule(max_loss_percent=200, name="default_stop_200pct", priority=1),
            DTEExitRule(dte_threshold=21, name="default_dte_21", priority=2),
        ])

    def _trade_legs_to_rec_legs(self, trade) -> List[RecommendedLeg]:
        """Convert trade legs to RecommendedLeg objects."""
        rec_legs = []
        if not hasattr(trade, 'legs') or not trade.legs:
            return rec_legs

        for leg in trade.legs:
            streamer = self._leg_to_streamer_symbol(leg) or ""
            rec_legs.append(RecommendedLeg(
                streamer_symbol=streamer,
                quantity=getattr(leg, 'quantity', 0),
                strike=getattr(getattr(leg, 'symbol', None), 'strike', None),
                option_type=(
                    getattr(getattr(leg, 'symbol', None), 'option_type', None)
                    and getattr(getattr(leg, 'symbol', None), 'option_type').value
                ) or None,
                expiration=(
                    str(getattr(getattr(leg, 'symbol', None), 'expiration', None))
                    if getattr(getattr(leg, 'symbol', None), 'expiration', None)
                    else None
                ),
            ))
        return rec_legs

    def _leg_to_streamer_symbol(self, leg) -> Optional[str]:
        """Build streamer symbol from a leg's symbol object."""
        symbol = getattr(leg, 'symbol', None)
        if not symbol:
            return None

        if not getattr(symbol, 'is_option', False):
            return getattr(symbol, 'ticker', None)

        ticker = getattr(symbol, 'ticker', '')
        exp = getattr(symbol, 'expiration', None)
        opt_type = getattr(symbol, 'option_type', None)
        strike = getattr(symbol, 'strike', None)

        if not all([ticker, exp, opt_type, strike]):
            return None

        exp_str = exp.strftime('%y%m%d') if hasattr(exp, 'strftime') else str(exp)
        opt_char = 'C' if 'call' in str(opt_type).lower() else 'P'
        strike_int = int(strike)
        return f".{ticker}{exp_str}{opt_char}{strike_int}"


class _TradeAsPosition:
    """
    Adapter that makes a Trade look like a Position for the RulesEngine.

    The RulesEngine was designed for Position objects; this wrapper
    provides the interface the rules expect.
    """

    def __init__(self, trade):
        self._trade = trade
        self.id = trade.id
        self.symbol = self._first_leg_symbol()
        self.quantity = self._total_quantity()
        self.total_cost = getattr(trade, 'entry_price', Decimal('0'))

    def unrealized_pnl(self) -> Decimal:
        """Estimate unrealized P&L from entry vs current price."""
        entry = getattr(self._trade, 'entry_price', None) or Decimal('0')
        current = getattr(self._trade, 'current_price', None) or entry
        return current - entry

    @property
    def greeks(self):
        """Return current Greeks."""
        return getattr(self._trade, 'current_greeks', None)

    def _first_leg_symbol(self):
        """Get the first leg's symbol for DTE/delta checks."""
        legs = getattr(self._trade, 'legs', None)
        if legs:
            for leg in legs:
                sym = getattr(leg, 'symbol', None)
                if sym:
                    return sym
        # Fallback: create a minimal symbol-like object
        return type('Symbol', (), {
            'ticker': getattr(self._trade, 'underlying_symbol', 'UNKNOWN'),
            'expiration': None,
        })()

    def _total_quantity(self) -> int:
        """Sum of all leg quantities."""
        legs = getattr(self._trade, 'legs', None)
        if legs:
            return sum(getattr(l, 'quantity', 0) for l in legs)
        return 0
