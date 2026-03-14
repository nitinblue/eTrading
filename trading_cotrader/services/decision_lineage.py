"""
Decision Lineage Service — Full explainability for every trade (G14).

Provides "explain this trade" capability:
  - At entry: gate-by-gate reasoning + market context + commentary (G25)
  - At exit: what triggered close + why
  - Data gaps: where analysis was weak (G26)
  - Performance feedback: outcomes → MA calibration (G24)

Called by:
  - API endpoint: GET /trades/{id}/explain
  - CLI: explain <trade_id>
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, TradeEventORM

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a single gate check."""
    name: str
    passed: bool
    value: Any = None
    threshold: Any = None
    detail: str = ''


@dataclass
class TradeExplanation:
    """Full decision tree for a trade."""
    trade_id: str
    ticker: str
    strategy_type: str
    status: str  # open, closed

    # Entry reasoning
    gates: List[GateResult] = field(default_factory=list)
    market_context: Dict[str, Any] = field(default_factory=dict)
    commentary: Dict[str, List[str]] = field(default_factory=dict)  # G25
    data_gaps: List[Dict[str, str]] = field(default_factory=list)   # G26

    # Entry analytics
    pop_at_entry: Optional[float] = None
    ev_at_entry: Optional[float] = None
    breakeven_low: Optional[float] = None
    breakeven_high: Optional[float] = None
    regime_at_entry: Optional[str] = None
    income_yield_roc: Optional[float] = None

    # Exit reasoning (if closed)
    exit_reason: Optional[str] = None
    exit_price: Optional[float] = None
    health_status_at_exit: Optional[str] = None
    adjustment_history: List[Dict] = field(default_factory=list)

    # Outcome
    total_pnl: Optional[float] = None
    days_held: Optional[int] = None

    # Raw lineage from DB
    raw_lineage: Optional[Dict] = None


class DecisionLineageService:
    """Build and query trade decision explanations."""

    def explain_trade(self, trade_id: str) -> Optional[TradeExplanation]:
        """Build full explanation for a trade from DB data."""
        with session_scope() as session:
            trade = session.query(TradeORM).get(trade_id)
            if not trade:
                return None

            strategy_type = trade.strategy.strategy_type if trade.strategy else 'unknown'

            explanation = TradeExplanation(
                trade_id=trade_id,
                ticker=trade.underlying_symbol,
                strategy_type=strategy_type,
                status='open' if trade.is_open else 'closed',
            )

            # Populate from decision_lineage JSON (stored at booking)
            lineage = trade.decision_lineage or {}
            explanation.raw_lineage = lineage

            # Gates
            for gate_data in lineage.get('gates', []):
                explanation.gates.append(GateResult(
                    name=gate_data.get('name', ''),
                    passed=gate_data.get('passed', True),
                    value=gate_data.get('value'),
                    threshold=gate_data.get('threshold'),
                    detail=gate_data.get('detail', ''),
                ))

            # Market context at entry
            explanation.market_context = lineage.get('market_context', {})

            # G25: Commentary from MA (debug=True)
            explanation.commentary = lineage.get('commentary', {})

            # G26: Data gaps
            explanation.data_gaps = lineage.get('data_gaps', [])

            # Entry analytics from TradeORM fields (G2)
            explanation.pop_at_entry = float(trade.pop_at_entry) if trade.pop_at_entry else None
            explanation.ev_at_entry = float(trade.ev_at_entry) if trade.ev_at_entry else None
            explanation.breakeven_low = float(trade.breakeven_low) if trade.breakeven_low else None
            explanation.breakeven_high = float(trade.breakeven_high) if trade.breakeven_high else None
            explanation.regime_at_entry = trade.regime_at_entry
            explanation.income_yield_roc = float(trade.income_yield_roc) if trade.income_yield_roc else None

            # Exit info
            if not trade.is_open:
                explanation.exit_reason = trade.exit_reason
                explanation.exit_price = float(trade.exit_price) if trade.exit_price else None
                explanation.total_pnl = float(trade.total_pnl) if trade.total_pnl else None
                if trade.opened_at and trade.closed_at:
                    explanation.days_held = (trade.closed_at - trade.opened_at).days

            # Health + adjustments
            explanation.health_status_at_exit = trade.health_status
            explanation.adjustment_history = trade.adjustment_history or []

            return explanation

    def build_lineage_at_entry(
        self,
        proposal: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build decision_lineage dict to store on TradeORM at booking time.

        Called by Maverick after gates pass, before booking.
        Captures gate results + market context + commentary (G25) + data gaps (G26).
        """
        lineage = {
            'timestamp': datetime.utcnow().isoformat(),
            'ticker': proposal.get('ticker', ''),
            'strategy_type': proposal.get('strategy_type', ''),
            'score': proposal.get('score', 0),
        }

        # Gate results
        gates = []
        gate_result = proposal.get('gate_result', 'PASS')

        # Reconstruct gate flow from proposal data
        gates.append({'name': 'verdict', 'passed': True, 'value': proposal.get('verdict'), 'threshold': 'not no_go'})
        gates.append({'name': 'score', 'passed': True, 'value': proposal.get('score'), 'threshold': f'>= 0.35'})
        gates.append({'name': 'trade_spec', 'passed': True, 'value': 'has legs', 'threshold': 'legs exist'})
        gates.append({'name': 'buying_power', 'passed': True, 'value': 'sufficient', 'threshold': 'BP available'})
        gates.append({'name': 'duplicate', 'passed': True, 'value': 'unique', 'threshold': 'no open position'})
        gates.append({'name': 'position_limit', 'passed': True, 'value': 'under limit', 'threshold': 'max positions'})

        ml_score = proposal.get('ml_score', 0)
        gates.append({'name': 'ml_score', 'passed': True, 'value': ml_score, 'threshold': '> -0.5'})

        pop = proposal.get('pop_at_entry')
        if pop is not None:
            gates.append({'name': 'pop', 'passed': True, 'value': f'{pop:.0%}', 'threshold': '>= 45%'})

        ev = proposal.get('ev_at_entry')
        if ev is not None:
            gates.append({'name': 'ev', 'passed': True, 'value': f'${ev:.2f}', 'threshold': '> $0'})

        if proposal.get('income_entry_confirmed') is not None:
            gates.append({'name': 'income_entry', 'passed': True,
                          'value': proposal.get('income_entry_score'), 'threshold': 'confirmed'})

        if proposal.get('execution_quality'):
            gates.append({'name': 'execution_quality', 'passed': True,
                          'value': proposal.get('execution_quality'), 'threshold': 'GO'})

        lineage['gates'] = gates

        # Market context snapshot
        research = context.get('research', {})
        ticker = proposal.get('ticker', '')
        ticker_data = research.get(ticker, {})
        lineage['market_context'] = {
            'regime': ticker_data.get('hmm_regime_label', 'unknown'),
            'regime_id': ticker_data.get('hmm_regime_id'),
            'rsi': ticker_data.get('rsi_14'),
            'atr_pct': ticker_data.get('atr_pct'),
            'phase': ticker_data.get('phase_name'),
            'black_swan': context.get('black_swan_level', 'NORMAL'),
            'trading_allowed': context.get('trading_allowed', True),
        }

        # G25: Commentary (if available from MA debug mode)
        commentary = context.get('commentary', {})
        if commentary:
            lineage['commentary'] = commentary

        # G26: Data gaps (if available)
        data_gaps = context.get('data_gaps', [])
        if data_gaps:
            lineage['data_gaps'] = data_gaps

        lineage['rationale'] = proposal.get('rationale', '')

        return lineage

    # -----------------------------------------------------------------
    # G24: Performance feedback — build TradeOutcome for MA
    # -----------------------------------------------------------------

    def build_trade_outcomes(self, days: int = 90) -> list:
        """Build TradeOutcome dicts from closed trades for MA's calibrate_weights().

        Returns list of dicts matching MA's TradeOutcome model.
        """
        outcomes = []

        with session_scope() as session:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            trades = session.query(TradeORM).filter(
                TradeORM.is_open == False,
                TradeORM.closed_at >= cutoff,
            ).all()

            for trade in trades:
                strategy_type = trade.strategy.strategy_type if trade.strategy else 'unknown'
                order_side = 'credit' if trade.entry_price and float(trade.entry_price) > 0 else 'debit'

                entry_regime = None
                if trade.regime_at_entry:
                    try:
                        entry_regime = int(trade.regime_at_entry.replace('R', ''))
                    except (ValueError, AttributeError):
                        pass

                pnl = float(trade.total_pnl or 0)
                entry = float(trade.entry_price or 0)
                max_risk = float(trade.max_risk or abs(entry) or 1)
                pnl_pct = pnl / max_risk if max_risk else 0

                days_held = 0
                if trade.opened_at and trade.closed_at:
                    days_held = (trade.closed_at - trade.opened_at).days

                outcomes.append({
                    'trade_id': trade.id,
                    'ticker': trade.underlying_symbol,
                    'structure_type': strategy_type,
                    'order_side': order_side,
                    'regime_at_entry': entry_regime,
                    'iv_rank_at_entry': None,  # not tracked yet
                    'dte_at_entry': None,       # not tracked yet
                    'entry_price': entry,
                    'exit_price': float(trade.exit_price or 0),
                    'contracts': 1,
                    'realized_pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'outcome': 'WIN' if pnl > 0 else 'LOSS',
                    'exit_reason': trade.exit_reason or 'unknown',
                    'days_held': days_held,
                })

        return outcomes
