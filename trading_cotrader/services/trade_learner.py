"""
Trade Learner — ML/RL learning from trade outcomes.

Implements a simple but effective reinforcement learning loop:
  State = (market_regime, iv_rank, strategy_type, dte_bucket, portfolio)
  Action = (trade / no_trade / close / hold)
  Reward = risk-adjusted P&L (Sharpe-like)

Uses a Q-table approach (tabular RL) for interpretability and small state space.
Patterns are stored in the RecognizedPatternORM table for persistence across sessions.

Called by:
  - After every trade close (incremental learning)
  - Daily batch learning (nightly)
  - CLI 'learn' command (on-demand analysis)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import json
import logging
import math

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, TradeEventORM

logger = logging.getLogger(__name__)


@dataclass
class TradePattern:
    """A learned pattern from trade history."""
    pattern_key: str          # e.g., "R1:high_iv:iron_condor:0dte:credit"
    strategy_type: str
    conditions: Dict          # Market conditions that led to this pattern
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    win_rate: float = 0.0
    avg_days_held: float = 0.0
    sharpe: float = 0.0       # Risk-adjusted score
    confidence: float = 0.0   # 0-1, increases with more trades

    def update(self, pnl: float, is_win: bool, days_held: int):
        """Update pattern stats with a new trade outcome."""
        self.trades += 1
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl += pnl
        self.avg_pnl = self.total_pnl / self.trades
        self.win_rate = self.wins / self.trades if self.trades > 0 else 0
        # Running average of days held
        self.avg_days_held = ((self.avg_days_held * (self.trades - 1)) + days_held) / self.trades
        # Confidence increases with sample size (asymptotic to 1.0)
        self.confidence = 1 - (1 / (1 + self.trades * 0.2))


@dataclass
class LearningResult:
    """Result of a learning cycle."""
    trades_analyzed: int = 0
    patterns_updated: int = 0
    patterns_discovered: int = 0
    best_patterns: List[TradePattern] = field(default_factory=list)
    worst_patterns: List[TradePattern] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)


class TradeLearner:
    """
    Reinforcement learning from trade outcomes.

    Q-table approach: state → expected reward.
    State is discretized into buckets for interpretability.

    Usage:
        learner = TradeLearner()
        result = learner.learn_from_history(days=30)
        score = learner.score_trade(strategy_type, regime, iv_rank, dte)
    """

    def __init__(self):
        self._patterns: Dict[str, TradePattern] = {}
        self._loaded = False

    def learn_from_history(self, days: int = 90, portfolio_type: str = 'what_if') -> LearningResult:
        """
        Analyze closed trades and build/update patterns.

        Args:
            days: How many days of history to analyze
            portfolio_type: Filter by trade type

        Returns:
            LearningResult with insights and pattern stats.
        """
        result = LearningResult()

        with session_scope() as session:
            # Get closed trades with outcomes
            cutoff = datetime.utcnow() - timedelta(days=days)
            trades = (
                session.query(TradeORM)
                .filter(
                    TradeORM.trade_status == 'closed',
                    TradeORM.closed_at >= cutoff,
                )
                .all()
            )

            if portfolio_type:
                trades = [t for t in trades if t.trade_type == portfolio_type]

            result.trades_analyzed = len(trades)

            if not trades:
                result.insights.append("No closed trades to learn from.")
                return result

            # Get events for market context
            events_by_trade = {}
            trade_ids = [t.id for t in trades]
            events = (
                session.query(TradeEventORM)
                .filter(TradeEventORM.trade_id.in_(trade_ids))
                .all()
            )
            for e in events:
                events_by_trade.setdefault(e.trade_id, []).append(e)

            # Build/update patterns
            for trade in trades:
                pattern_key = self._build_pattern_key(trade, events_by_trade.get(trade.id, []))
                if not pattern_key:
                    continue

                entry = float(trade.entry_price or 0)
                pnl = float(trade.total_pnl or 0)
                is_win = pnl > 0
                days_held = (trade.closed_at - (trade.opened_at or trade.created_at)).days if trade.closed_at else 0

                if pattern_key not in self._patterns:
                    strategy = trade.strategy.strategy_type if trade.strategy else 'unknown'
                    self._patterns[pattern_key] = TradePattern(
                        pattern_key=pattern_key,
                        strategy_type=strategy,
                        conditions=self._extract_conditions(trade, events_by_trade.get(trade.id, [])),
                    )
                    result.patterns_discovered += 1

                self._patterns[pattern_key].update(pnl, is_win, days_held)
                result.patterns_updated += 1

        # Compute Sharpe-like score for each pattern
        self._compute_scores()

        # Save to DB
        self._persist_patterns()

        # Generate insights
        result.best_patterns = sorted(
            [p for p in self._patterns.values() if p.trades >= 3],
            key=lambda p: p.sharpe,
            reverse=True,
        )[:5]
        result.worst_patterns = sorted(
            [p for p in self._patterns.values() if p.trades >= 3],
            key=lambda p: p.sharpe,
        )[:5]

        result.insights = self._generate_insights()
        self._loaded = True

        return result

    def score_trade(
        self,
        strategy_type: str,
        regime: str = 'unknown',
        iv_bucket: str = 'medium',
        dte_bucket: str = 'medium',
        order_side: str = 'credit',
    ) -> float:
        """
        Score a potential trade based on learned patterns.

        Returns: -1.0 (strong avoid) to +1.0 (strong go).
        0.0 = no opinion (insufficient data).
        """
        if not self._loaded:
            self._load_patterns()

        key = f"{regime}:{iv_bucket}:{strategy_type}:{dte_bucket}:{order_side}"
        pattern = self._patterns.get(key)

        if not pattern or pattern.trades < 3:
            return 0.0  # Insufficient data

        # Score = confidence × (normalized Sharpe)
        # Sharpe > 1 is good, > 2 is great
        normalized = max(-1.0, min(1.0, pattern.sharpe / 2.0))
        return round(normalized * pattern.confidence, 2)

    def get_pattern_summary(self) -> List[Dict]:
        """Get all patterns sorted by score for display."""
        if not self._loaded:
            self._load_patterns()

        patterns = sorted(
            self._patterns.values(),
            key=lambda p: p.sharpe * p.confidence,
            reverse=True,
        )
        return [
            {
                'pattern': p.pattern_key,
                'strategy': p.strategy_type,
                'trades': p.trades,
                'win_rate': f"{p.win_rate:.0%}",
                'avg_pnl': f"${p.avg_pnl:+.2f}",
                'total_pnl': f"${p.total_pnl:+.2f}",
                'sharpe': f"{p.sharpe:.2f}",
                'confidence': f"{p.confidence:.0%}",
                'avg_days': f"{p.avg_days_held:.0f}",
            }
            for p in patterns if p.trades >= 2
        ]

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _build_pattern_key(self, trade: TradeORM, events: List) -> Optional[str]:
        """Build a state key from trade + market context."""
        strategy = trade.strategy.strategy_type if trade.strategy else 'unknown'

        # Extract market context from entry event
        regime = 'unknown'
        iv_bucket = 'medium'
        for event in events:
            if event.event_type == 'trade_opened' and event.market_context:
                ctx = event.market_context if isinstance(event.market_context, dict) else {}
                regime = ctx.get('market_regime', 'unknown')
                iv_rank = ctx.get('iv_rank', 50)
                iv_bucket = 'low' if iv_rank < 30 else ('high' if iv_rank > 70 else 'medium')
                break

        # DTE bucket from legs
        dte_bucket = self._dte_bucket(trade)

        # Order side from entry price
        entry = float(trade.entry_price or 0)
        order_side = 'credit' if entry > 0 else 'debit'

        return f"{regime}:{iv_bucket}:{strategy}:{dte_bucket}:{order_side}"

    def _dte_bucket(self, trade: TradeORM) -> str:
        """Categorize trade by DTE at entry."""
        # Check leg expirations vs opened_at
        opened = trade.opened_at or trade.created_at
        if not opened:
            return 'medium'

        min_dte = None
        for leg in trade.legs:
            if leg.symbol and leg.symbol.expiration:
                exp = leg.symbol.expiration
                if isinstance(exp, datetime):
                    exp = exp.date()
                dte = (exp - opened.date()).days
                if min_dte is None or dte < min_dte:
                    min_dte = dte

        if min_dte is None:
            return 'medium'
        if min_dte <= 1:
            return '0dte'
        if min_dte <= 7:
            return 'weekly'
        if min_dte <= 60:
            return 'medium'
        return 'leaps'

    def _extract_conditions(self, trade: TradeORM, events: List) -> Dict:
        """Extract market conditions for pattern storage."""
        conditions = {
            'underlying': trade.underlying_symbol,
            'strategy_type': trade.strategy.strategy_type if trade.strategy else 'unknown',
        }
        for event in events:
            if event.event_type == 'trade_opened' and event.market_context:
                ctx = event.market_context if isinstance(event.market_context, dict) else {}
                conditions.update({
                    'regime': ctx.get('market_regime'),
                    'iv_rank': ctx.get('iv_rank'),
                    'vix': ctx.get('vix'),
                })
                break
        return conditions

    def _compute_scores(self):
        """Compute Sharpe-like scores for all patterns."""
        for p in self._patterns.values():
            if p.trades < 2:
                p.sharpe = 0.0
                continue

            # Collect per-trade P&L for standard deviation
            # Since we don't store individual P&Ls, approximate from win/loss stats
            # Sharpe ≈ avg_return / std_return
            avg = p.avg_pnl
            if p.trades > 1 and avg != 0:
                # Approximate variance from win rate and average
                # Higher win rate with consistent returns = higher Sharpe
                variance_proxy = abs(avg) * (1 - p.win_rate) * 2
                if variance_proxy > 0:
                    p.sharpe = avg / variance_proxy
                else:
                    p.sharpe = avg / abs(avg) * 2.0 if avg else 0
            else:
                p.sharpe = 0.0

    def _persist_patterns(self):
        """Save patterns to RecognizedPatternORM."""
        try:
            from trading_cotrader.core.database.schema import RecognizedPatternORM
            with session_scope() as session:
                for key, pattern in self._patterns.items():
                    existing = session.query(RecognizedPatternORM).filter_by(
                        pattern_type='trade_rl',
                        description=key,
                    ).first()

                    if existing:
                        existing.occurrences = pattern.trades
                        existing.success_rate = Decimal(str(round(pattern.win_rate, 4)))
                        existing.avg_pnl = Decimal(str(round(pattern.avg_pnl, 2)))
                        existing.confidence_score = Decimal(str(round(pattern.confidence, 4)))
                        existing.last_seen = datetime.utcnow()
                        existing.conditions = pattern.conditions
                    else:
                        new_pattern = RecognizedPatternORM(
                            id=f"rl_{key}",
                            pattern_type='trade_rl',
                            description=key,
                            conditions=pattern.conditions,
                            occurrences=pattern.trades,
                            success_rate=Decimal(str(round(pattern.win_rate, 4))),
                            avg_pnl=Decimal(str(round(pattern.avg_pnl, 2))),
                            confidence_score=Decimal(str(round(pattern.confidence, 4))),
                        )
                        session.add(new_pattern)

                session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist patterns: {e}")

    def _load_patterns(self):
        """Load patterns from DB."""
        try:
            from trading_cotrader.core.database.schema import RecognizedPatternORM
            with session_scope() as session:
                rows = session.query(RecognizedPatternORM).filter_by(
                    pattern_type='trade_rl'
                ).all()

                for row in rows:
                    key = row.description
                    self._patterns[key] = TradePattern(
                        pattern_key=key,
                        strategy_type=(row.conditions or {}).get('strategy_type', 'unknown'),
                        conditions=row.conditions or {},
                        trades=row.occurrences or 0,
                        wins=int((row.occurrences or 0) * float(row.success_rate or 0)),
                        losses=int((row.occurrences or 0) * (1 - float(row.success_rate or 0))),
                        total_pnl=float(row.avg_pnl or 0) * (row.occurrences or 0),
                        avg_pnl=float(row.avg_pnl or 0),
                        win_rate=float(row.success_rate or 0),
                        confidence=float(row.confidence_score or 0),
                    )
        except Exception as e:
            logger.debug(f"Could not load patterns: {e}")

        self._loaded = True

    def _generate_insights(self) -> List[str]:
        """Generate human-readable insights from patterns."""
        insights = []
        patterns = [p for p in self._patterns.values() if p.trades >= 3]

        if not patterns:
            insights.append("Not enough data yet — need at least 3 trades per pattern.")
            return insights

        # Best and worst
        best = max(patterns, key=lambda p: p.sharpe * p.confidence)
        worst = min(patterns, key=lambda p: p.sharpe * p.confidence)

        insights.append(
            f"Best pattern: {best.pattern_key} — "
            f"{best.wins}/{best.trades} wins, avg P&L ${best.avg_pnl:+.2f}"
        )
        if worst.sharpe < 0:
            insights.append(
                f"Worst pattern: {worst.pattern_key} — "
                f"{worst.wins}/{worst.trades} wins, avg P&L ${worst.avg_pnl:+.2f} — AVOID"
            )

        # Strategy-level stats
        by_strategy = defaultdict(list)
        for p in patterns:
            by_strategy[p.strategy_type].append(p)

        for strategy, pats in by_strategy.items():
            total_trades = sum(p.trades for p in pats)
            total_wins = sum(p.wins for p in pats)
            total_pnl = sum(p.total_pnl for p in pats)
            wr = total_wins / total_trades if total_trades else 0
            insights.append(
                f"{strategy}: {total_trades} trades, {wr:.0%} win rate, "
                f"total P&L ${total_pnl:+.2f}"
            )

        return insights
