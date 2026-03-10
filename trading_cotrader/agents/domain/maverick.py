"""
Maverick Agent (Trader) — Domain orchestrator for trading workflow.

Consumes Scout's screening + ranking results to produce trade proposals.
Cross-references with Steward's portfolio state and Sentinel's risk checks
to filter, size, and book WhatIf trades.

Decision-making (which strategy, which strikes, which expiry) lives in
market_analyzer. Maverick enforces portfolio-level and risk-level gates:
  - Is the strategy allowed for this portfolio?
  - Do we have room for more positions (max_positions)?
  - Do we already have an open trade on this underlying?
  - Is the black swan gate clear?
  - Is trading allowed (market context)?
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar, Dict, List, Optional

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


def _trade_spec_to_leg_inputs(
    ticker: str,
    trade_spec: Dict[str, Any],
    position_size: int = 1,
) -> List[Dict[str, Any]]:
    """Convert a serialized TradeSpec dict to LegInput-compatible dicts.

    TradeSpec legs have: action (BTO/STO), quantity, option_type, strike, expiration.
    TradeBookingService expects: streamer_symbol (.SPY260327P580), quantity (signed).

    Args:
        ticker: Underlying symbol
        trade_spec: Serialized TradeSpec dict
        position_size: Number of spreads/contracts (from position sizing)
    """
    legs = trade_spec.get('legs', [])
    result = []
    for leg in legs:
        strike = leg.get('strike', 0)
        exp_str = leg.get('expiration', '')  # ISO date string from model_dump
        option_type = leg.get('option_type', 'put')
        action = leg.get('action', 'BTO')
        leg_qty = leg.get('quantity', 1)  # Per-spread quantity (usually 1, 2 for ratios)

        # Parse expiration
        if isinstance(exp_str, str):
            try:
                exp_date = date.fromisoformat(exp_str)
            except ValueError:
                logger.warning(f"Invalid expiration: {exp_str}")
                continue
        elif isinstance(exp_str, date):
            exp_date = exp_str
        else:
            continue

        # Build DXLink streamer symbol: .TICKER YYMMDD P/C STRIKE
        opt_char = 'C' if option_type == 'call' else 'P'
        date_part = exp_date.strftime('%y%m%d')
        strike_int = int(strike)
        streamer_symbol = f".{ticker}{date_part}{opt_char}{strike_int}"

        # Scale quantity by position size, preserve leg ratio
        total_qty = leg_qty * position_size
        # Signed quantity: BTO = positive (buy), STO = negative (sell)
        signed_qty = total_qty if action == 'BTO' else -total_qty

        result.append({
            'streamer_symbol': streamer_symbol,
            'quantity': signed_qty,
        })
    return result


class MaverickAgent(BaseAgent):
    """Trading orchestrator: consumes Scout rankings, enforces portfolio gates, proposes trades."""

    # Class-level metadata
    name: ClassVar[str] = "maverick"
    display_name: ClassVar[str] = "Maverick (Trader)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "Trading orchestration — ranking → gates → trade proposals"
    intro: ClassVar[str] = (
        "I bring it all together. I consume Scout's ranked trade ideas, apply "
        "portfolio-level and risk-level gates, and produce trade proposals ready "
        "for booking into WhatIf portfolios."
    )
    responsibilities: ClassVar[List[str]] = [
        "Consume Scout rankings",
        "Portfolio-level gate checks",
        "Risk-level gate checks",
        "Trade proposal generation",
        "Duplicate prevention",
        "WhatIf trade booking",
        "Decision tracking",
    ]
    datasources: ClassVar[List[str]] = [
        "context['ranking'] (from Scout)",
        "context['screening_candidates'] (from Scout)",
        "context['black_swan_level'] (from Scout)",
        "context['trading_allowed'] (from Scout/Context)",
        "PortfolioBundle (via ContainerManager)",
        "ResearchContainer (via ContainerManager)",
    ]
    boundaries: ClassVar[List[str]] = [
        "LIMIT orders only (no market orders)",
        "Defined-risk strategies only for WhatIf",
        "Cannot override risk limits",
        "All decisions delegated to market_analyzer",
    ]
    runs_during: ClassVar[List[str]] = ["booting", "monitoring"]

    # Configurable thresholds
    MIN_SCORE_THRESHOLD = 0.35          # Minimum composite_score to consider
    MAX_PROPOSALS_PER_CYCLE = 3         # Don't propose more than N trades per cycle
    COOLDOWN_HOURS = 8                  # Don't re-propose same underlying+strategy within N hours
    MAX_RISK_PER_TRADE_PCT = Decimal('0.02')   # 2% of portfolio per trade
    DEFAULT_CAPITAL = Decimal('10000')          # Fallback if portfolio has no equity

    # Trading desks by DTE range
    DESK_0DTE = "desk_0dte"
    DESK_MEDIUM = "desk_medium"
    DESK_LEAPS = "desk_leaps"
    DEFAULT_WHATIF_PORTFOLIO = DESK_MEDIUM  # Fallback

    def __init__(self, container_manager=None, config=None, broker=None):
        super().__init__(container=None, config=config)
        self._container_manager = container_manager
        self._broker = broker

    def run(self, context: dict) -> AgentResult:
        """
        Main trading logic. Three phases:

        Phase 1: Position analysis (existing positions)
          Cross-reference Steward's positions with Scout's research.

        Phase 2: New trade proposals (from Scout's ranking)
          Filter ranked candidates through portfolio/risk gates.
          Produce trade proposals ready for WhatIf booking.

        Phase 3: Exit monitoring (open trades)
          Check open trades against exit rules (profit target, stop loss, DTE).
        """
        if not self._container_manager:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                messages=["Maverick: no container_manager — skipped"],
            )

        messages: List[str] = []

        # ── Phase 1: Analyze existing positions ──
        position_signals = self._analyze_positions()
        context['trading_signals'] = position_signals
        if position_signals:
            messages.append(f"Position signals: {len(position_signals)} underlyings")

        # ── Phase 2: Generate new trade proposals ──
        proposals = self._generate_proposals(context)
        context['trade_proposals'] = proposals
        messages.append(f"Trade proposals: {len(proposals)} (from ranking)")

        # Log proposals for visibility
        for p in proposals:
            status = p.get('status', 'proposed')
            ticker = p.get('ticker', '?')
            strategy = p.get('strategy_name', '?')
            score = p.get('score', 0)
            gate = p.get('gate_result', '')
            if status == 'proposed':
                messages.append(f"  → {ticker} {strategy} (score={score:.2f})")
            else:
                messages.append(f"  ✗ {ticker} {strategy} — {gate}")

        # ── Phase 3: Exit monitoring ──
        exit_signals = self._check_exits()
        context['exit_signals'] = exit_signals
        if exit_signals:
            urgent = [s for s in exit_signals if s.severity == 'URGENT']
            warnings = [s for s in exit_signals if s.severity == 'WARNING']
            if urgent:
                messages.append(f"EXIT ALERTS: {len(urgent)} URGENT, {len(warnings)} warnings")
                for s in urgent:
                    messages.append(f"  ⚠ {s.message}")
            elif warnings:
                messages.append(f"Exit warnings: {len(warnings)}")

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data={
                'position_signals': len(position_signals),
                'proposals': len([p for p in proposals if p['status'] == 'proposed']),
                'rejected': len([p for p in proposals if p['status'] == 'rejected']),
                'exit_signals': len(exit_signals),
            },
            messages=messages,
        )

    # -----------------------------------------------------------------
    # Phase 1: Existing position analysis
    # -----------------------------------------------------------------

    def _analyze_positions(self) -> List[Dict[str, Any]]:
        """Cross-reference positions with research for management signals."""
        research = self._container_manager.research
        signals = []

        for bundle in self._container_manager.get_all_bundles():
            for underlying in bundle.positions.underlyings:
                positions = bundle.positions.get_by_underlying(underlying)
                net_delta = sum(float(p.delta) for p in positions)

                signal = {
                    'underlying': underlying,
                    'portfolio': bundle.config_name,
                    'net_delta': round(net_delta, 2),
                    'position_count': len(positions),
                }

                entry = research.get(underlying)
                if entry:
                    signal.update({
                        'regime': entry.hmm_regime_label,
                        'phase': entry.phase_name,
                        'rsi': entry.rsi_14,
                        'levels_direction': entry.levels_direction,
                    })

                signals.append(signal)

        return signals

    # -----------------------------------------------------------------
    # Phase 2: New trade proposals from ranking
    # -----------------------------------------------------------------

    def _generate_proposals(self, context: dict) -> List[Dict[str, Any]]:
        """Filter ranked candidates through gates and produce proposals."""
        ranking = context.get('ranking', [])
        if not ranking:
            return []

        # Gate 0: Global gates
        if context.get('black_swan_level', 'NORMAL') == 'CRITICAL':
            return [{'status': 'rejected', 'gate_result': 'BLACK_SWAN_CRITICAL',
                     'ticker': 'ALL', 'strategy_name': 'ALL', 'score': 0}]

        if not context.get('trading_allowed', True):
            return [{'status': 'rejected', 'gate_result': 'TRADING_HALTED',
                     'ticker': 'ALL', 'strategy_name': 'ALL', 'score': 0}]

        # Get existing open trades for duplicate check
        open_underlyings = self._get_open_whatif_underlyings()

        proposals = []
        proposed_count = 0

        for entry in ranking:
            if proposed_count >= self.MAX_PROPOSALS_PER_CYCLE:
                break

            ticker = entry.get('ticker', '')
            strategy_name = entry.get('strategy_name', '')
            strategy_type = entry.get('strategy_type', '')
            verdict = entry.get('verdict', 'no_go')
            score = entry.get('composite_score', 0)
            trade_spec = entry.get('trade_spec')
            rationale = entry.get('rationale', '')
            direction = entry.get('direction', '')
            risk_notes = entry.get('risk_notes', [])

            proposal = {
                'ticker': ticker,
                'strategy_name': strategy_name,
                'strategy_type': strategy_type,
                'verdict': verdict,
                'score': score,
                'direction': direction,
                'rationale': rationale,
                'risk_notes': risk_notes,
                'trade_spec': trade_spec,
            }

            # Gate 1: Verdict
            if verdict == 'no_go':
                proposal['status'] = 'rejected'
                proposal['gate_result'] = 'NO_GO verdict'
                proposals.append(proposal)
                continue

            # Gate 2: Score threshold
            if score < self.MIN_SCORE_THRESHOLD:
                proposal['status'] = 'rejected'
                proposal['gate_result'] = f'Score {score:.2f} < {self.MIN_SCORE_THRESHOLD}'
                proposals.append(proposal)
                continue

            # Gate 3: Trade spec exists (has actual legs to book)
            if not trade_spec or not trade_spec.get('legs'):
                proposal['status'] = 'rejected'
                proposal['gate_result'] = 'No trade_spec / no legs'
                proposals.append(proposal)
                continue

            # Gate 4: Duplicate prevention — already have open trade on this underlying
            underlying_key = f"{ticker}:{strategy_type}"
            if underlying_key in open_underlyings:
                proposal['status'] = 'rejected'
                proposal['gate_result'] = f'Duplicate — open {strategy_type} on {ticker}'
                proposals.append(proposal)
                continue

            # Gate 5: Position count limit
            max_positions = self._get_max_positions()
            current_positions = len(open_underlyings)
            if current_positions + proposed_count >= max_positions:
                proposal['status'] = 'rejected'
                proposal['gate_result'] = f'Max positions ({max_positions}) reached'
                proposals.append(proposal)
                continue

            # Gate 6: ML score — strong avoid signal from learned patterns
            ml_score = self._ml_score(strategy_type, trade_spec)
            proposal['ml_score'] = ml_score
            if ml_score <= -0.5:
                proposal['status'] = 'rejected'
                proposal['gate_result'] = f'ML AVOID (score={ml_score:.2f})'
                proposals.append(proposal)
                continue

            # All gates passed — mark as proposed
            proposal['status'] = 'proposed'
            proposal['gate_result'] = 'PASS'

            # Position sizing: scale quantity based on capital allocation
            quantity = self._compute_position_size(trade_spec)
            proposal['quantity'] = quantity

            # Build leg inputs for booking (with sized quantities)
            leg_inputs = _trade_spec_to_leg_inputs(ticker, trade_spec, quantity)
            proposal['leg_inputs'] = leg_inputs

            # Route to correct desk based on DTE
            desk = self._route_to_desk(trade_spec)
            proposal['desk'] = desk

            # Build exit rules from trade_spec
            proposal['exit_rules'] = {
                'profit_target_pct': trade_spec.get('profit_target_pct'),
                'stop_loss_pct': trade_spec.get('stop_loss_pct'),
                'exit_dte': trade_spec.get('exit_dte'),
                'exit_summary': trade_spec.get('exit_summary', ''),
                'order_side': trade_spec.get('order_side', 'credit'),
            }

            proposals.append(proposal)
            proposed_count += 1
            open_underlyings.add(underlying_key)  # prevent intra-cycle duplicates

        return proposals

    def _compute_position_size(self, trade_spec: Dict[str, Any]) -> int:
        """
        Compute number of contracts based on portfolio capital and max risk.

        Logic:
          1. Get available capital from WhatIf portfolio
          2. Max risk per trade = capital × MAX_RISK_PER_TRADE_PCT (default 2%)
          3. Max risk per spread from trade_spec (wing_width × 100 - estimated credit)
          4. Contracts = floor(max_risk_budget / max_risk_per_spread)
          5. Minimum 1, maximum 10
        """
        # Get portfolio capital
        capital = self.DEFAULT_CAPITAL
        try:
            for bundle in self._container_manager.get_all_bundles():
                if bundle.config_name == self.DEFAULT_WHATIF_PORTFOLIO:
                    equity = bundle.portfolio.total_equity or Decimal('0')
                    if equity > 0:
                        capital = equity
                    break
        except Exception:
            pass

        # Risk budget per trade
        risk_budget = capital * self.MAX_RISK_PER_TRADE_PCT

        # Max risk per spread (from trade_spec)
        wing_width = trade_spec.get('wing_width_points')
        if wing_width and wing_width > 0:
            # Defined risk: max_loss = wing_width × 100 (per spread)
            max_risk_per_spread = Decimal(str(wing_width)) * 100
        else:
            # Single leg or undefined risk — use estimated price × 100
            legs = trade_spec.get('legs', [])
            total_premium = sum(abs(float(l.get('strike', 0))) * 0.01 for l in legs)
            max_risk_per_spread = Decimal(str(max(total_premium * 100, 500)))

        if max_risk_per_spread <= 0:
            return 1

        contracts = int(risk_budget / max_risk_per_spread)
        return max(1, min(contracts, 10))

    def _get_open_whatif_underlyings(self) -> set:
        """Get set of 'ticker:strategy_type' keys for open WhatIf trades."""
        open_keys = set()
        try:
            for bundle in self._container_manager.get_all_bundles():
                whatif_trades = bundle.trades.get_what_if_trades()
                for t in whatif_trades:
                    key = f"{t.underlying}:{t.strategy_type}"
                    open_keys.add(key)
        except Exception as e:
            logger.debug(f"Could not check open trades: {e}")
        return open_keys

    def _route_to_desk(self, trade_spec: Dict[str, Any]) -> str:
        """Route a trade to the correct desk based on DTE."""
        target_dte = trade_spec.get('target_dte', 45)
        structure = trade_spec.get('structure_type', '').lower()

        # 0DTE: same-day expiration
        if target_dte <= 1 or '0dte' in structure:
            return self.DESK_0DTE

        # LEAPs: 180+ DTE
        if target_dte >= 180 or 'leap' in structure or 'pmcc' in structure:
            return self.DESK_LEAPS

        # Medium-term: 7-179 DTE (majority of trades)
        return self.DESK_MEDIUM

    def _get_max_positions(self) -> int:
        """Get max_positions from risk config for the WhatIf portfolio."""
        try:
            from trading_cotrader.config.risk_config_loader import get_risk_config
            rc = get_risk_config()
            whatif_cfg = rc.portfolios.get_by_name(self.DEFAULT_WHATIF_PORTFOLIO)
            if whatif_cfg:
                return whatif_cfg.risk_limits.get('max_positions', 10)
            # Check parent if WhatIf inherits
            mirrors = getattr(whatif_cfg, 'mirrors_real', None)
            if mirrors:
                parent_cfg = rc.portfolios.get_by_name(mirrors)
                if parent_cfg:
                    return parent_cfg.risk_limits.get('max_positions', 10)
        except Exception:
            pass
        return 10  # safe default

    # -----------------------------------------------------------------
    # ML scoring gate
    # -----------------------------------------------------------------

    def _ml_score(self, strategy_type: str, trade_spec: Dict[str, Any]) -> float:
        """Score a potential trade using ML/RL learned patterns. Returns -1 to +1."""
        try:
            from trading_cotrader.services.trade_learner import TradeLearner
            learner = TradeLearner()

            # Extract state dimensions from trade_spec
            target_dte = trade_spec.get('target_dte', 45)
            if target_dte <= 1:
                dte_bucket = '0dte'
            elif target_dte <= 7:
                dte_bucket = 'weekly'
            elif target_dte <= 60:
                dte_bucket = 'medium'
            else:
                dte_bucket = 'leaps'

            order_side = trade_spec.get('order_side', 'credit')
            regime = trade_spec.get('regime', 'unknown')
            iv_bucket = trade_spec.get('iv_bucket', 'medium')

            return learner.score_trade(
                strategy_type=strategy_type,
                regime=regime,
                iv_bucket=iv_bucket,
                dte_bucket=dte_bucket,
                order_side=order_side,
            )
        except Exception:
            return 0.0  # No opinion on error

    # -----------------------------------------------------------------
    # Trade booking (called externally after approval)
    # -----------------------------------------------------------------

    def book_proposals(self, context: dict, portfolio_name: str = None) -> List[Dict[str, Any]]:
        """
        Book all approved proposals into a WhatIf portfolio.

        Called by the workflow engine or CLI after user reviews proposals.
        Returns list of booking results.
        """
        from trading_cotrader.services.trade_booking_service import (
            TradeBookingService, LegInput,
        )
        import trading_cotrader.core.models.domain as dm

        proposals = context.get('trade_proposals', [])
        approved = [p for p in proposals if p.get('status') == 'proposed']

        if not approved:
            return [{'success': False, 'error': 'No approved proposals to book'}]

        # Create booking service (broker optional — works with zeros if no broker)
        service = TradeBookingService(
            broker=self._broker,
            container_manager=self._container_manager,
        )

        results = []
        for proposal in approved:
            ticker = proposal['ticker']
            strategy_type = proposal.get('strategy_type', proposal.get('strategy_name', ''))
            leg_inputs = proposal.get('leg_inputs', [])
            rationale = proposal.get('rationale', '')
            score = proposal.get('score', 0)
            trade_spec = proposal.get('trade_spec', {})
            exit_rules = proposal.get('exit_rules', {})

            # Route to correct desk (override with explicit portfolio if provided)
            target_portfolio = portfolio_name or proposal.get('desk', self.DEFAULT_WHATIF_PORTFOLIO)

            if not leg_inputs:
                results.append({
                    'success': False,
                    'ticker': ticker,
                    'strategy': strategy_type,
                    'error': 'No leg inputs',
                })
                continue

            # Build LegInput objects
            legs = [
                LegInput(
                    streamer_symbol=l['streamer_symbol'],
                    quantity=l['quantity'],
                )
                for l in leg_inputs
            ]

            # Build notes with exit rules
            notes_parts = [rationale]
            if exit_rules.get('exit_summary'):
                notes_parts.append(f"Exit: {exit_rules['exit_summary']}")
            if trade_spec.get('spec_rationale'):
                notes_parts.append(f"Spec: {trade_spec['spec_rationale']}")
            notes = ' | '.join(p for p in notes_parts if p)

            # Book the trade
            booking_result = service.book_whatif_trade(
                underlying=ticker,
                strategy_type=strategy_type,
                legs=legs,
                notes=notes,
                rationale=rationale,
                confidence=int(score * 10),
                portfolio_name=target_portfolio,
                trade_source=dm.TradeSource.AI_RECOMMENDATION,
            )

            result_dict = {
                'success': booking_result.success,
                'ticker': ticker,
                'strategy': strategy_type,
                'score': score,
            }
            if booking_result.success:
                result_dict['trade_id'] = booking_result.trade_id
                result_dict['entry_price'] = float(booking_result.entry_price)
                result_dict['greeks'] = booking_result.total_greeks
                logger.info(
                    f"Booked WhatIf: {ticker} {strategy_type} "
                    f"entry=${booking_result.entry_price:.2f} "
                    f"score={score:.2f}"
                )
            else:
                result_dict['error'] = booking_result.error
                logger.warning(f"Failed to book {ticker} {strategy_type}: {booking_result.error}")

            # Store exit rules on the trade in DB
            if booking_result.success and exit_rules:
                self._store_exit_rules(booking_result.trade_id, exit_rules, trade_spec)

            results.append(result_dict)

        return results

    def _store_exit_rules(
        self,
        trade_id: str,
        exit_rules: Dict[str, Any],
        trade_spec: Dict[str, Any],
    ) -> None:
        """Store exit rules on the TradeORM for exit monitoring."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import TradeORM

        try:
            with session_scope() as session:
                trade_orm = session.query(TradeORM).get(trade_id)
                if not trade_orm:
                    return

                entry = abs(float(trade_orm.entry_price or 0))
                order_side = exit_rules.get('order_side', trade_spec.get('order_side', 'credit'))

                # Profit target as dollar amount
                tp_pct = exit_rules.get('profit_target_pct')
                if tp_pct and entry:
                    if order_side == 'credit':
                        trade_orm.profit_target = Decimal(str(round(entry * tp_pct, 2)))
                    else:
                        trade_orm.profit_target = Decimal(str(round(entry * tp_pct, 2)))

                # Stop loss as dollar amount
                sl_pct = exit_rules.get('stop_loss_pct')
                if sl_pct and entry:
                    if order_side == 'credit':
                        trade_orm.stop_loss = Decimal(str(round(entry * sl_pct, 2)))
                    else:
                        trade_orm.stop_loss = Decimal(str(round(entry * sl_pct, 2)))

                # Max risk from trade_spec
                wing_width = trade_spec.get('wing_width_points')
                if wing_width:
                    trade_orm.max_risk = Decimal(str(round(wing_width * 100 - entry, 2)))

                session.commit()
        except Exception as e:
            logger.debug(f"Could not store exit rules for {trade_id}: {e}")

    # -----------------------------------------------------------------
    # Phase 3: Exit monitoring
    # -----------------------------------------------------------------

    def _check_exits(self) -> List:
        """Check open trades for exit conditions. Returns list of ExitSignal."""
        try:
            from trading_cotrader.services.exit_monitor import ExitMonitorService
            monitor = ExitMonitorService()
            result = monitor.check_all_exits()
            return result.signals
        except Exception as e:
            logger.debug(f"Exit monitor error: {e}")
            return []

    # -----------------------------------------------------------------
    # Mark-to-market (called by engine or CLI)
    # -----------------------------------------------------------------

    def mark_to_market(self):
        """Run mark-to-market on all open trades. Returns MarkToMarketResult."""
        from trading_cotrader.services.mark_to_market import MarkToMarketService
        service = MarkToMarketService(
            broker=self._broker,
            container_manager=self._container_manager,
        )
        return service.mark_all_open_trades()
