"""
Trade Health Service — Orchestrates health checks + adjustment decisions.

G9:  Adjustment pipeline (TESTED/BREACHED → MA recommends action)
G22: Overnight risk assessment (call before market close)
G23: Deterministic adjustment decisions via recommend_action()

For each open trade:
  1. Build TradeSpec via bridge (G1)
  2. Get regime + technicals from MA
  3. Call MA's recommend_action() for deterministic decision (G23)
  4. Return HealthAction: HOLD / CLOSE / ADJUST / ROLL

Called by:
  - Engine monitoring cycle (step 8b, after auto-close)
  - Engine EOD cycle (overnight risk check)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM
from trading_cotrader.services.tradespec_bridge import trade_to_tradespec

logger = logging.getLogger(__name__)


@dataclass
class HealthAction:
    """What the system should do with a position."""
    trade_id: str
    ticker: str
    action: str          # HOLD, CLOSE, ADJUST, ROLL
    urgency: str         # immediate, soon, monitor
    position_status: str  # safe, tested, breached, max_loss
    rationale: str
    # For ADJUST/ROLL: details of the recommended adjustment
    adjustment_type: Optional[str] = None  # DO_NOTHING, CLOSE_FULL, ROLL_OUT, ROLL_AWAY, etc.
    new_legs: Optional[list] = None
    close_legs: Optional[list] = None


@dataclass
class HealthCheckResult:
    """Result of checking all positions."""
    actions: List[HealthAction] = field(default_factory=list)
    trades_checked: int = 0
    trades_healthy: int = 0
    trades_needing_action: int = 0

    @property
    def has_immediate(self) -> bool:
        return any(a.urgency == 'immediate' for a in self.actions)


@dataclass
class OvernightAction:
    """Overnight risk assessment result for a position."""
    trade_id: str
    ticker: str
    risk_level: str     # LOW, MEDIUM, HIGH, CLOSE_BEFORE_CLOSE
    action: str         # HOLD, CLOSE
    reasons: List[str]
    summary: str


class TradeHealthService:
    """Orchestrates health checks + adjustment recommendations for all positions."""

    def __init__(self, ma, broker=None):
        """
        Args:
            ma: MarketAnalyzer instance (required for regime + technicals).
            broker: Optional broker for position data.
        """
        self.ma = ma
        self.broker = broker

    def check_all_positions(self, trade_type: str = None) -> HealthCheckResult:
        """Run health check + adjustment recommendation for all open trades.

        For each trade:
          1. Convert to TradeSpec (G1)
          2. Get regime + technicals from MA
          3. Call recommend_action() for deterministic decision (G23)
          4. Map to HealthAction
        """
        result = HealthCheckResult()

        try:
            from market_analyzer.service.adjustment import AdjustmentService
        except ImportError:
            logger.warning("AdjustmentService not available — skipping health checks")
            return result

        adj_service = AdjustmentService(
            quote_service=getattr(self.ma, 'quotes', None),
        )

        with session_scope() as session:
            query = session.query(TradeORM).filter(TradeORM.is_open == True)
            if trade_type:
                query = query.filter(TradeORM.trade_type == trade_type)
            trades = query.all()

            result.trades_checked = len(trades)

            for trade in trades:
                action = self._check_single(trade, adj_service)
                if action:
                    if action.action == 'HOLD':
                        result.trades_healthy += 1
                    else:
                        result.actions.append(action)
                        result.trades_needing_action += 1

                        # Update health status in DB
                        trade.health_status = action.position_status
                        trade.health_checked_at = datetime.utcnow()

                        # Append to adjustment history
                        if action.action in ('ADJUST', 'ROLL', 'CLOSE'):
                            history = trade.adjustment_history or []
                            history.append({
                                'timestamp': datetime.utcnow().isoformat(),
                                'action': action.action,
                                'type': action.adjustment_type,
                                'status': action.position_status,
                                'rationale': action.rationale,
                            })
                            trade.adjustment_history = history

            session.commit()

        if result.trades_needing_action:
            logger.info(
                f"Health check: {result.trades_needing_action} positions need action "
                f"out of {result.trades_checked} checked"
            )

        return result

    def _check_single(self, trade: TradeORM, adj_service) -> Optional[HealthAction]:
        """Check a single trade and return recommended action."""
        spec = trade_to_tradespec(trade)
        if not spec:
            return None

        # Get regime + technicals from MA
        try:
            regime = self.ma.regime.detect(trade.underlying_symbol)
            technicals = self.ma.technicals.snapshot(trade.underlying_symbol)
        except Exception as e:
            logger.debug(f"Skipping health check for {trade.underlying_symbol}: {e}")
            return None

        # G23: Deterministic adjustment decision
        try:
            decision = adj_service.recommend_action(
                trade_spec=spec,
                regime=regime,
                technicals=technicals,
            )
        except Exception as e:
            logger.debug(f"recommend_action failed for {trade.id}: {e}")
            return None

        # Map AdjustmentType enum to action string
        action_str = decision.action.value if hasattr(decision.action, 'value') else str(decision.action)

        if action_str == 'DO_NOTHING':
            return HealthAction(
                trade_id=trade.id,
                ticker=trade.underlying_symbol,
                action='HOLD',
                urgency='monitor',
                position_status=decision.position_status.value if hasattr(decision.position_status, 'value') else str(decision.position_status),
                rationale=decision.rationale,
            )

        if action_str == 'CLOSE_FULL':
            return HealthAction(
                trade_id=trade.id,
                ticker=trade.underlying_symbol,
                action='CLOSE',
                urgency=decision.urgency,
                position_status=decision.position_status.value if hasattr(decision.position_status, 'value') else str(decision.position_status),
                rationale=decision.rationale,
                adjustment_type='CLOSE_FULL',
            )

        # ROLL_OUT, ROLL_AWAY, NARROW_UNTESTED, ADD_WING, CONVERT
        new_legs = None
        close_legs = None
        if decision.detail:
            new_legs = getattr(decision.detail, 'new_legs', None)
            close_legs = getattr(decision.detail, 'close_legs', None)
            # Serialize LegSpec objects if present
            if new_legs and hasattr(new_legs[0], 'model_dump'):
                new_legs = [l.model_dump(mode='json') for l in new_legs]
            if close_legs and hasattr(close_legs[0], 'model_dump'):
                close_legs = [l.model_dump(mode='json') for l in close_legs]

        return HealthAction(
            trade_id=trade.id,
            ticker=trade.underlying_symbol,
            action='ADJUST',
            urgency=decision.urgency,
            position_status=decision.position_status.value if hasattr(decision.position_status, 'value') else str(decision.position_status),
            rationale=decision.rationale,
            adjustment_type=action_str.upper(),
            new_legs=new_legs,
            close_legs=close_legs,
        )

    # -----------------------------------------------------------------
    # G22: Overnight risk assessment
    # -----------------------------------------------------------------

    def assess_overnight_risk(self, trade_type: str = None) -> List[OvernightAction]:
        """Check all open positions for overnight gap risk.

        Call this at ~15:30 ET. Returns list of positions with
        HIGH or CLOSE_BEFORE_CLOSE risk level.
        """
        try:
            from market_analyzer import assess_overnight_risk
        except ImportError:
            return []

        actions = []

        with session_scope() as session:
            query = session.query(TradeORM).filter(TradeORM.is_open == True)
            if trade_type:
                query = query.filter(TradeORM.trade_type == trade_type)
            trades = query.all()

            for trade in trades:
                dte = self._compute_dte(trade)
                if dte is None:
                    continue

                # Get position status from health_status field
                position_status = trade.health_status or 'unknown'
                if position_status == 'unknown':
                    position_status = 'safe'

                # Get regime
                regime_id = 1
                try:
                    regime = self.ma.regime.detect(trade.underlying_symbol)
                    regime_id = regime.regime if hasattr(regime, 'regime') else 1
                except Exception:
                    pass

                strategy_type = trade.strategy.strategy_type if trade.strategy else 'unknown'
                order_side = 'credit'
                if trade.entry_price and float(trade.entry_price) < 0:
                    order_side = 'debit'

                # Check for earnings/macro tomorrow
                has_earnings = False
                has_macro = False
                try:
                    research = getattr(self, '_research', {})
                    ticker_data = research.get(trade.underlying_symbol, {})
                    dte_earnings = ticker_data.get('days_to_earnings')
                    if dte_earnings is not None and dte_earnings <= 1:
                        has_earnings = True
                except Exception:
                    pass

                try:
                    risk = assess_overnight_risk(
                        trade_id=trade.id,
                        ticker=trade.underlying_symbol,
                        structure_type=strategy_type,
                        order_side=order_side,
                        dte_remaining=dte,
                        regime_id=int(regime_id),
                        position_status=position_status,
                        has_earnings_tomorrow=has_earnings,
                        has_macro_event_tomorrow=has_macro,
                    )

                    risk_level = risk.risk_level.value if hasattr(risk.risk_level, 'value') else str(risk.risk_level)

                    if risk_level in ('HIGH', 'CLOSE_BEFORE_CLOSE'):
                        action = 'CLOSE' if risk_level == 'CLOSE_BEFORE_CLOSE' else 'HOLD'
                        actions.append(OvernightAction(
                            trade_id=trade.id,
                            ticker=trade.underlying_symbol,
                            risk_level=risk_level,
                            action=action,
                            reasons=risk.reasons,
                            summary=risk.summary,
                        ))
                except Exception as e:
                    logger.debug(f"Overnight risk failed for {trade.id}: {e}")

        if actions:
            logger.info(
                f"Overnight risk: {len(actions)} positions flagged "
                f"({sum(1 for a in actions if a.action == 'CLOSE')} need closing)"
            )

        return actions

    def _compute_dte(self, trade: TradeORM) -> Optional[int]:
        """Compute days to earliest leg expiration."""
        today = date.today()
        dtes = []
        for leg in trade.legs:
            if leg.symbol and leg.symbol.expiration:
                exp = leg.symbol.expiration
                if isinstance(exp, datetime):
                    exp = exp.date()
                dtes.append((exp - today).days)
        return min(dtes) if dtes else None
