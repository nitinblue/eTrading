"""
ML Learning Service — Wires MA's learning APIs into eTrading.

ML-E1: Drift detection — flags degrading strategies
ML-E2: Strategy bandits — Thompson Sampling for strategy selection
ML-E3: Threshold optimization — self-tunes gate cutoffs
ML-E4: POP calibration — corrects probability from actual win rates
ML-E5: IV rank threading — passes IV rank map to ranking

All state lives in eTrading (MLStateORM). MA computes, eTrading stores.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, MLStateORM

logger = logging.getLogger(__name__)


class MLLearningService:
    """Orchestrates all ML learning loops between eTrading and MA."""

    def __init__(self, ma=None):
        self.ma = ma

    # -----------------------------------------------------------------
    # Build TradeOutcome from closed trades
    # -----------------------------------------------------------------

    def _build_outcomes(self, days: int = 180) -> list:
        """Build MA TradeOutcome objects from closed trades in DB."""
        from market_analyzer import TradeOutcome, TradeExitReason, StrategyType

        outcomes = []
        with session_scope() as session:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            trades = session.query(TradeORM).filter(
                TradeORM.is_open == False,
                TradeORM.closed_at >= cutoff,
            ).all()

            for trade in trades:
                # Map strategy type
                strategy_str = trade.strategy.strategy_type if trade.strategy else 'iron_condor'
                try:
                    strategy_type = StrategyType(strategy_str)
                except ValueError:
                    strategy_type = StrategyType.IRON_CONDOR

                # Map exit reason
                exit_str = trade.exit_reason or 'manual'
                try:
                    exit_reason = TradeExitReason(exit_str)
                except ValueError:
                    exit_reason = TradeExitReason.MANUAL

                # Regime at entry/exit
                regime_entry = 1
                if trade.regime_at_entry:
                    try:
                        regime_entry = int(trade.regime_at_entry.replace('R', ''))
                    except (ValueError, AttributeError):
                        pass

                entry_price = float(trade.entry_price or 0)
                exit_price = float(trade.exit_price or 0)
                pnl = float(trade.total_pnl or 0)
                max_risk = float(trade.max_risk or abs(entry_price) or 1)
                pnl_pct = pnl / max_risk if max_risk else 0

                entry_date = (trade.opened_at or trade.created_at).date() if (trade.opened_at or trade.created_at) else date.today()
                exit_date = trade.closed_at.date() if trade.closed_at else date.today()
                holding_days = max(1, (exit_date - entry_date).days)

                # Score at entry from decision lineage
                score = 0.5
                lineage = trade.decision_lineage or {}
                if lineage.get('score'):
                    score = float(lineage['score'])

                try:
                    outcomes.append(TradeOutcome(
                        trade_id=trade.id,
                        ticker=trade.underlying_symbol,
                        strategy_type=strategy_type,
                        regime_at_entry=regime_entry,
                        regime_at_exit=regime_entry,  # approximate
                        entry_date=entry_date,
                        exit_date=exit_date,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        pnl_dollars=pnl,
                        pnl_pct=pnl_pct,
                        holding_days=holding_days,
                        exit_reason=exit_reason,
                        composite_score_at_entry=score,
                        structure_type=strategy_str,
                        order_side='credit' if entry_price > 0 else 'debit',
                        iv_rank_at_entry=None,  # TODO: store at entry
                    ))
                except Exception as e:
                    logger.debug(f"Skip trade {trade.id}: {e}")

        return outcomes

    # -----------------------------------------------------------------
    # ML-E1: Drift Detection
    # -----------------------------------------------------------------

    def run_drift_detection(self) -> list:
        """Detect strategy performance drift. Returns list of DriftAlert."""
        try:
            from market_analyzer import detect_drift
        except ImportError:
            return []

        outcomes = self._build_outcomes()
        if len(outcomes) < 10:
            logger.info(f"Drift: not enough outcomes ({len(outcomes)}, need 10+)")
            return []

        alerts = detect_drift(outcomes, window=20, min_trades=10)

        # Store in DB
        self._save_state('drift_alerts', {
            'alerts': [a.model_dump(mode='json') for a in alerts],
            'outcomes_analyzed': len(outcomes),
        }, len(outcomes))

        # Log
        warnings = [a for a in alerts if a.severity.value in ('warning', 'critical')]
        if warnings:
            for a in warnings:
                logger.warning(
                    f"Drift {a.severity.value}: {a.strategy_type.value} in R{a.regime_id} "
                    f"— win rate dropped {a.historical_win_rate:.0%} → {a.recent_win_rate:.0%}"
                )
        else:
            logger.info(f"Drift: no alerts from {len(outcomes)} outcomes")

        return alerts

    def get_drift_alerts(self) -> list:
        """Get stored drift alerts."""
        state = self._load_state('drift_alerts')
        if not state:
            return []
        return state.get('alerts', [])

    # -----------------------------------------------------------------
    # ML-E2: Strategy Bandits
    # -----------------------------------------------------------------

    def update_bandits(self) -> dict:
        """Rebuild bandits from all trade outcomes."""
        try:
            from market_analyzer import build_bandits
        except ImportError:
            return {}

        outcomes = self._build_outcomes()
        if not outcomes:
            return {}

        bandits = build_bandits(outcomes)

        # Serialize for storage
        serialized = {}
        for key, bandit in bandits.items():
            serialized[key] = bandit.model_dump(mode='json')

        self._save_state('bandits', serialized, len(outcomes))
        logger.info(f"Bandits: updated {len(bandits)} cells from {len(outcomes)} outcomes")

        return bandits

    def select_strategies_for_regime(self, regime_id: int, n: int = 3) -> List[Tuple[str, float]]:
        """Select top N strategies for a regime using Thompson Sampling."""
        try:
            from market_analyzer import select_strategies, StrategyBandit, StrategyType
        except ImportError:
            return []

        # Load bandits from DB
        state = self._load_state('bandits')
        if not state:
            return []

        # Reconstruct StrategyBandit objects
        bandits = {}
        for key, data in state.items():
            try:
                bandits[key] = StrategyBandit(**data)
            except Exception:
                continue

        if not bandits:
            return []

        # Available strategies
        available = list(StrategyType)

        selected = select_strategies(bandits, regime_id, available, n=n)
        return [(s.value if hasattr(s, 'value') else str(s), score) for s, score in selected]

    def update_single_bandit(self, strategy_type: str, regime_id: int, won: bool) -> None:
        """Update a single bandit after a trade closes."""
        try:
            from market_analyzer import update_bandit, StrategyBandit, StrategyType
        except ImportError:
            return

        state = self._load_state('bandits') or {}
        key = f"R{regime_id}_{strategy_type}"

        if key in state:
            try:
                bandit = StrategyBandit(**state[key])
            except Exception:
                bandit = StrategyBandit(
                    regime_id=regime_id,
                    strategy_type=StrategyType(strategy_type),
                )
        else:
            try:
                bandit = StrategyBandit(
                    regime_id=regime_id,
                    strategy_type=StrategyType(strategy_type),
                )
            except ValueError:
                return

        updated = update_bandit(bandit, won)
        state[key] = updated.model_dump(mode='json')
        self._save_state('bandits', state, 0)

        logger.info(f"Bandit updated: {key} {'WIN' if won else 'LOSS'} "
                    f"→ win_rate={updated.expected_win_rate:.0%} (n={updated.total_trades})")

    # -----------------------------------------------------------------
    # ML-E3: Threshold Optimization
    # -----------------------------------------------------------------

    def optimize_gate_thresholds(self) -> dict:
        """Run threshold optimization from trade outcomes."""
        try:
            from market_analyzer import optimize_thresholds, ThresholdConfig
        except ImportError:
            return {}

        outcomes = self._build_outcomes()
        if len(outcomes) < 15:
            logger.info(f"Threshold opt: not enough outcomes ({len(outcomes)}, need 15+)")
            return {}

        # Load current thresholds or use defaults
        current_state = self._load_state('thresholds')
        current = ThresholdConfig(**(current_state or {}))

        optimized = optimize_thresholds(outcomes, current)
        result = optimized.model_dump(mode='json')

        self._save_state('thresholds', result, len(outcomes))

        # Log changes
        changes = []
        for field in ThresholdConfig.model_fields:
            old_val = getattr(current, field)
            new_val = getattr(optimized, field)
            if old_val != new_val:
                changes.append(f"{field}: {old_val} → {new_val}")
        if changes:
            logger.info(f"Thresholds optimized from {len(outcomes)} outcomes: {', '.join(changes)}")
        else:
            logger.info(f"Thresholds unchanged from {len(outcomes)} outcomes")

        return result

    def get_thresholds(self) -> dict:
        """Get current optimized thresholds (or defaults)."""
        from market_analyzer import ThresholdConfig
        state = self._load_state('thresholds')
        if state:
            return state
        return ThresholdConfig().model_dump(mode='json')

    # -----------------------------------------------------------------
    # ML-E4: POP Calibration
    # -----------------------------------------------------------------

    def calibrate_pop(self) -> dict:
        """Calibrate POP regime factors from actual win rates."""
        try:
            from market_analyzer import calibrate_pop_factors
        except ImportError:
            return {}

        outcomes = self._build_outcomes()
        if len(outcomes) < 10:
            return {}

        factors = calibrate_pop_factors(outcomes)

        self._save_state('pop_factors', {
            'factors': {str(k): v for k, v in factors.items()},
            'outcomes_analyzed': len(outcomes),
        }, len(outcomes))

        logger.info(f"POP factors calibrated from {len(outcomes)} outcomes: {factors}")
        return factors

    def get_pop_factors(self) -> dict:
        """Get calibrated POP factors."""
        state = self._load_state('pop_factors')
        if state and 'factors' in state:
            return {int(k): v for k, v in state['factors'].items()}
        return {}

    # -----------------------------------------------------------------
    # ML-E5: IV Rank Map
    # -----------------------------------------------------------------

    def build_iv_rank_map(self, tickers: list) -> dict:
        """Build IV rank map from broker metrics for ranking."""
        if not self.ma or not self.ma.quotes:
            return {}

        iv_map = {}
        for ticker in tickers:
            try:
                metrics = self.ma.quotes.get_metrics(ticker)
                if metrics and metrics.iv_rank is not None:
                    iv_map[ticker] = metrics.iv_rank
            except Exception:
                pass

        return iv_map

    # -----------------------------------------------------------------
    # Full learning cycle
    # -----------------------------------------------------------------

    def run_full_learning_cycle(self) -> dict:
        """Run all ML learning steps. Call daily or after batch of closes."""
        results = {}

        # ML-E1: Drift
        drift_alerts = self.run_drift_detection()
        results['drift'] = {
            'alerts': len(drift_alerts),
            'warnings': sum(1 for a in drift_alerts if hasattr(a, 'severity') and a.severity.value == 'warning'),
            'critical': sum(1 for a in drift_alerts if hasattr(a, 'severity') and a.severity.value == 'critical'),
        }

        # ML-E2: Bandits
        bandits = self.update_bandits()
        results['bandits'] = {'cells': len(bandits)}

        # ML-E3: Thresholds
        thresholds = self.optimize_gate_thresholds()
        results['thresholds'] = {'optimized': bool(thresholds)}

        # ML-E4: POP calibration
        pop_factors = self.calibrate_pop()
        results['pop_factors'] = {'regimes': len(pop_factors)}

        logger.info(f"ML learning cycle complete: {results}")
        return results

    # -----------------------------------------------------------------
    # State persistence
    # -----------------------------------------------------------------

    def _save_state(self, state_type: str, state_data: dict, trades_analyzed: int) -> None:
        """Save ML state to DB."""
        with session_scope() as session:
            existing = session.query(MLStateORM).filter(
                MLStateORM.state_type == state_type
            ).first()

            if existing:
                existing.state_json = state_data
                existing.trades_analyzed = trades_analyzed
                existing.last_updated = datetime.utcnow()
            else:
                session.add(MLStateORM(
                    id=str(uuid.uuid4()),
                    state_type=state_type,
                    state_json=state_data,
                    trades_analyzed=trades_analyzed,
                ))
            session.commit()

    def _load_state(self, state_type: str) -> Optional[dict]:
        """Load ML state from DB."""
        with session_scope() as session:
            row = session.query(MLStateORM).filter(
                MLStateORM.state_type == state_type
            ).first()
            if row:
                return row.state_json
        return None
