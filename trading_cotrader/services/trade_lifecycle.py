"""
Trade Lifecycle Service — Close trades, record outcomes, feed ML.

Handles:
  1. Close a trade (update DB, record exit price, compute final P&L)
  2. Record outcome for ML learning (win/loss, what went right/wrong)
  3. Auto-close trades based on exit signals
  4. Update portfolio cash balance after closing

Called by:
  - CLI 'close' command
  - Engine monitoring cycle (auto-close on exit signals)
  - Maverick when exit conditions met
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import logging

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM
from trading_cotrader.repositories.trade import TradeRepository
from trading_cotrader.repositories.event import EventRepository
import trading_cotrader.core.models.events as ev

logger = logging.getLogger(__name__)


class TradeLifecycleService:
    """
    Close trades and record outcomes for ML learning.

    Usage:
        service = TradeLifecycleService()
        result = service.close_trade(trade_id, reason='profit_target')
        results = service.auto_close_from_signals(exit_signals)
    """

    def __init__(self, container_manager=None):
        self.container_manager = container_manager

    def close_trade(
        self,
        trade_id: str,
        reason: str = 'manual',
        exit_price: Optional[Decimal] = None,
    ) -> Dict:
        """
        Close a trade and record the outcome.

        Args:
            trade_id: Trade ID to close
            reason: Why closing (profit_target, stop_loss, dte_exit, expired, manual)
            exit_price: Override exit price (defaults to current_price from DB)

        Returns:
            Dict with success, trade_id, pnl, pnl_pct, reason
        """
        with session_scope() as session:
            trade_repo = TradeRepository(session)
            event_repo = EventRepository(session)

            trade_orm = session.query(TradeORM).get(trade_id)
            if not trade_orm:
                return {'success': False, 'error': f'Trade {trade_id} not found'}

            if not trade_orm.is_open:
                return {'success': False, 'error': f'Trade {trade_id} already closed'}

            # Compute final P&L
            entry = Decimal(str(trade_orm.entry_price or 0))
            current = Decimal(str(trade_orm.current_price or entry))
            final_exit = exit_price if exit_price is not None else current
            pnl = final_exit - entry
            pnl_pct = float(pnl / abs(entry) * 100) if entry else 0

            # Close the trade
            trade_orm.is_open = False
            trade_orm.trade_status = 'closed'
            trade_orm.closed_at = datetime.utcnow()
            trade_orm.exit_price = final_exit
            trade_orm.exit_reason = reason
            trade_orm.total_pnl = pnl
            trade_orm.last_updated = datetime.utcnow()

            # Record outcome event for ML
            outcome = ev.TradeOutcomeData(
                outcome=ev.TradeOutcome.WIN if pnl > 0 else (
                    ev.TradeOutcome.LOSS if pnl < 0 else ev.TradeOutcome.BREAKEVEN
                ),
                final_pnl=pnl,
                pnl_percent=Decimal(str(round(pnl_pct, 2))),
                days_held=self._days_held(trade_orm),
                close_reason=reason,
            )

            strategy_type = trade_orm.strategy.strategy_type if trade_orm.strategy else 'unknown'
            close_event = ev.TradeEvent(
                event_type=ev.EventType.TRADE_CLOSED,
                trade_id=trade_id,
                timestamp=datetime.utcnow(),
                strategy_type=strategy_type,
                underlying_symbol=trade_orm.underlying_symbol,
                entry_delta=trade_orm.entry_delta or 0,
                entry_gamma=trade_orm.entry_gamma or 0,
                entry_theta=trade_orm.entry_theta or 0,
                entry_vega=trade_orm.entry_vega or 0,
                net_credit_debit=entry,
                outcome=outcome,
                tags=['closed', reason, trade_orm.trade_type or 'what_if'],
            )
            event_repo.create_from_domain(close_event)

            session.commit()

            underlying = trade_orm.underlying_symbol
            logger.info(
                f"Closed {underlying} {strategy_type}: "
                f"P&L=${pnl:+.2f} ({pnl_pct:+.1f}%) reason={reason}"
            )

            # W15: Auto-update Thompson Sampling bandit on close
            try:
                regime_at_entry = 1
                if trade_orm.regime_at_entry:
                    try:
                        regime_at_entry = int(trade_orm.regime_at_entry.replace('R', ''))
                    except (ValueError, AttributeError):
                        pass
                from trading_cotrader.services.ml_learning_service import MLLearningService
                ml = MLLearningService()
                ml.update_single_bandit(strategy_type, regime_at_entry, won=(pnl > 0))
            except Exception as e:
                logger.debug(f"Bandit update skipped: {e}")

            return {
                'success': True,
                'trade_id': trade_id,
                'underlying': underlying,
                'strategy_type': strategy_type,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'reason': reason,
                'entry_price': entry,
                'exit_price': final_exit,
            }

    def auto_close_from_signals(self, exit_signals: List) -> List[Dict]:
        """
        Auto-close trades based on exit monitor signals.

        Only closes on:
          - URGENT signals (stop loss, expired)
          - PROFIT_TARGET signals with INFO severity

        Returns list of close results.
        """
        results = []
        for signal in exit_signals:
            # Auto-close on urgent (stop loss, expired) and profit targets
            if signal.severity == 'URGENT' or signal.signal_type == 'PROFIT_TARGET':
                result = self.close_trade(
                    trade_id=signal.trade_id,
                    reason=signal.signal_type.lower(),
                )
                results.append(result)
                if result['success']:
                    logger.info(
                        f"Auto-closed {signal.underlying} — "
                        f"{signal.signal_type}: P&L=${result['pnl']:+.2f}"
                    )

        # Refresh containers after closing
        if results and self.container_manager:
            try:
                with session_scope() as session:
                    self.container_manager.load_from_repositories(session)
            except Exception as e:
                logger.warning(f"Container refresh after close failed: {e}")

        return results

    def _days_held(self, trade_orm: TradeORM) -> int:
        """Calculate days held for a trade."""
        opened = trade_orm.opened_at or trade_orm.created_at
        if not opened:
            return 0
        return max(0, (datetime.utcnow() - opened).days)
