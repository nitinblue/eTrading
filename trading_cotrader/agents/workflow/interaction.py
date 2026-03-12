"""
Interaction Manager — Routes user intents to workflow engine actions.

Handles: approve, reject, defer, status, list, halt, resume, override,
         portfolios, positions, greeks, capital, pending, trades, risk,
         book, templates.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
import logging

import trading_cotrader.core.models.domain as dm
from trading_cotrader.agents.messages import UserIntent, SystemResponse

if TYPE_CHECKING:
    from trading_cotrader.agents.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


def _fmt_dec(val, places: int = 2, prefix: str = '') -> str:
    """Format a Decimal/float/None to fixed-width string."""
    if val is None:
        return '—'
    try:
        v = float(val)
        if prefix == '$':
            return f"${v:,.{places}f}"
        elif prefix == '+':
            return f"{v:+,.{places}f}"
        return f"{v:,.{places}f}"
    except (TypeError, ValueError):
        return str(val)




# Portfolio short aliases: short_name → config_key
# Loaded once from YAML config; fallback to hardcoded if config unavailable.
_PORTFOLIO_ALIASES: dict[str, str] = {}


def _load_portfolio_aliases() -> dict[str, str]:
    """Build short alias → config key mapping from portfolio config."""
    if _PORTFOLIO_ALIASES:
        return _PORTFOLIO_ALIASES

    try:
        from trading_cotrader.config.risk_config_loader import get_risk_config
        rc = get_risk_config()
        for key, pc in rc.portfolios.portfolios.items():
            # Auto-generate short aliases:
            #   tastytrade → tt, fidelity_ira → fira, fidelity_personal → fp
            #   zerodha → zr
            #   *_whatif → append 'w' (ttw, firaw, fpw, zrw)
            _PORTFOLIO_ALIASES[key] = key  # full name always works
    except Exception:
        pass

    # Hardcoded shortcuts (stable, won't break if YAML changes)
    shortcuts = {
        'tt': 'tastytrade', 'fira': 'fidelity_ira', 'fp': 'fidelity_personal',
        'zr': 'zerodha',
        # Trading desks
        '0dte': 'desk_0dte', 'zero': 'desk_0dte',
        'med': 'desk_medium', 'medium': 'desk_medium', '45dte': 'desk_medium',
        'leaps': 'desk_leaps', 'leap': 'desk_leaps',
    }
    _PORTFOLIO_ALIASES.update(shortcuts)
    return _PORTFOLIO_ALIASES


def resolve_portfolio_name(input_name: str) -> str:
    """Resolve a short alias, config key, or number to a portfolio config key."""
    aliases = _load_portfolio_aliases()

    # Direct match (full name or alias)
    if input_name in aliases:
        return aliases[input_name]

    # Case-insensitive
    lower = input_name.lower()
    for alias, config_key in aliases.items():
        if alias.lower() == lower:
            return config_key

    # Not found — return as-is (let downstream report the error)
    return input_name


class InteractionManager:
    """Routes user commands to the appropriate workflow engine actions."""

    def __init__(self, engine: 'WorkflowEngine'):
        self.engine = engine

    def handle(self, intent: UserIntent) -> SystemResponse:
        """
        Route a UserIntent to the correct handler.

        Returns SystemResponse with results and available actions.
        """
        handlers = {
            'approve': self._approve,
            'reject': self._reject,
            'defer': self._defer,
            'status': self._status,
            'list': self._list_pending,
            'halt': self._halt,
            'resume': self._resume,
            'override': self._override,
            'help': self._help,
            # Report commands
            'portfolios': self._portfolios,
            'positions': self._positions,
            'greeks': self._greeks,
            'capital': self._capital,
            'pending': self._pending,
            'trades': self._trades,
            'risk': self._risk,
            # Execution commands
            'execute': self._execute,
            'orders': self._orders,
            # Trade booking
            'book': self._book,
            'templates': self._templates,
            # Trading workflow: plan → scan → propose → deploy → mark → exits
            'plan': self._plan,
            'strategies': self._strategies,
            'scan': self._scan,
            'propose': self._propose,
            'deploy': self._deploy,
            'mark': self._mark,
            'exits': self._exits,
            'golive': self._execute,  # Alias: go live = execute on broker
            # New: close, performance, learn, setup-desks
            'close': self._close,
            'perf': self._performance,
            'performance': self._performance,
            'learn': self._learn,
            'setup-desks': self._setup_desks,
        }

        handler = handlers.get(intent.action)
        if not handler:
            return SystemResponse(
                message=f"Unknown action: {intent.action}. "
                        f"Available: {', '.join(handlers.keys())}",
                available_actions=list(handlers.keys()),
            )

        try:
            return handler(intent)
        except Exception as e:
            logger.error(f"Error handling intent '{intent.action}': {e}")
            return SystemResponse(
                message=f"Error: {e}",
                requires_action=False,
            )

    def _approve(self, intent: UserIntent) -> SystemResponse:
        """Approve a recommendation."""
        if not intent.target:
            return SystemResponse(
                message="Usage: approve <recommendation_id> [--portfolio <name>]",
                requires_action=True,
            )

        # Add to approved actions — resolve portfolio alias to config key
        raw_portfolio = intent.parameters.get('portfolio')
        resolved_portfolio = resolve_portfolio_name(raw_portfolio) if raw_portfolio else None
        action = {
            'recommendation_id': intent.target,
            'portfolio': resolved_portfolio,
            'notes': intent.rationale or 'Approved via workflow',
        }
        approved = self.engine.context.get('approved_actions', [])
        approved.append(action)
        self.engine.context['approved_actions'] = approved

        return SystemResponse(
            message=f"Approved recommendation {intent.target[:8]}... "
                    f"({len(approved)} action(s) queued)",
            data={'approved_count': len(approved)},
        )

    def _reject(self, intent: UserIntent) -> SystemResponse:
        """Reject a recommendation."""
        if not intent.target:
            return SystemResponse(message="Usage: reject <recommendation_id>")

        return SystemResponse(
            message=f"Rejected recommendation {intent.target[:8]}...",
        )

    def _defer(self, intent: UserIntent) -> SystemResponse:
        """Defer a decision for later."""
        if not intent.target:
            return SystemResponse(message="Usage: defer <recommendation_id>")

        return SystemResponse(
            message=f"Deferred recommendation {intent.target[:8]}... "
                    f"(will be reminded in {self.engine.config.decision_timeouts.reminder_minutes} min)",
        )

    def _status(self, intent: UserIntent = None) -> SystemResponse:
        """Show current workflow status."""
        ctx = self.engine.context
        state = self.engine.state if hasattr(self.engine, 'state') else 'unknown'

        lines = [
            f"State: {state}",
            f"Cycle: {ctx.get('cycle_count', 0)}",
            f"Trading day: {ctx.get('is_trading_day', '?')}",
            f"Cadences: {ctx.get('cadences', [])}",
            f"VIX: {ctx.get('vix', '?')}",
            f"Open trades: {len(ctx.get('open_trades', []))}",
            f"Pending entry recs: {len(ctx.get('pending_recommendations', []))}",
            f"Exit signals: {len(ctx.get('exit_signals', []))}",
            f"Trades today: {ctx.get('trades_today_count', 0)}",
        ]

        risk = ctx.get('risk_snapshot', {})
        if risk:
            lines.append(f"VaR 95%: ${risk.get('var_95', 0):,.0f}")

        macro = ctx.get('macro_assessment', {})
        if macro:
            lines.append(f"Macro: {macro.get('regime', '?')} — {macro.get('rationale', '')[:60]}")

        return SystemResponse(
            message="\n".join(lines),
            data={
                'state': str(state),
                'vix': ctx.get('vix'),
                'open_trades': len(ctx.get('open_trades', [])),
            },
            available_actions=['approve', 'reject', 'defer', 'list', 'halt', 'resume'],
        )

    def _list_pending(self, intent: UserIntent = None) -> SystemResponse:
        """List all pending recommendations."""
        ctx = self.engine.context
        recs = ctx.get('pending_recommendations', [])
        exits = ctx.get('exit_signals', [])

        if not recs and not exits:
            return SystemResponse(message="No pending decisions.")

        lines = []
        if recs:
            lines.append("ENTRY RECOMMENDATIONS:")
            for r in recs:
                lines.append(
                    f"  [{r.get('id', '?')[:8]}] {r.get('underlying', '?')} "
                    f"{r.get('strategy_type', '?')} conf={r.get('confidence', '?')}"
                )

        if exits:
            lines.append("EXIT SIGNALS:")
            for s in exits:
                lines.append(
                    f"  [{s.get('id', '?')[:8]}] {s.get('underlying', '?')} "
                    f"{s.get('type', '?')} urgency={s.get('exit_urgency', '?')}"
                )

        return SystemResponse(
            message="\n".join(lines),
            pending_decisions=[*recs, *exits],
            requires_action=True,
            available_actions=['approve', 'reject', 'defer'],
        )

    def _halt(self, intent: UserIntent) -> SystemResponse:
        """Manually halt trading."""
        reason = intent.rationale or "Manual halt via user command"
        self.engine.context['halt_reason'] = reason
        try:
            self.engine.halt()
        except Exception:
            pass  # may already be halted
        return SystemResponse(message=f"Trading HALTED: {reason}")

    def _resume(self, intent: UserIntent) -> SystemResponse:
        """Resume from halted state."""
        if not intent.rationale:
            return SystemResponse(
                message="Resume requires rationale. Usage: resume --rationale 'why it's safe to resume'",
                requires_action=True,
            )
        try:
            self.engine.context['halt_override_rationale'] = intent.rationale
            self.engine.resume()
            return SystemResponse(message=f"Resumed trading. Rationale: {intent.rationale}")
        except Exception as e:
            return SystemResponse(message=f"Cannot resume: {e}")

    def _override(self, intent: UserIntent) -> SystemResponse:
        """Override a circuit breaker (requires rationale)."""
        if not intent.rationale:
            return SystemResponse(
                message="Override requires written rationale. "
                        "Usage: override --target <breaker> --rationale 'why'",
                requires_action=True,
            )

        breaker = intent.target or "unknown"
        granted = self.engine.guardian.request_override(breaker, intent.rationale)
        if granted:
            return SystemResponse(message=f"Override granted for '{breaker}'")
        return SystemResponse(message=f"Override DENIED for '{breaker}' — no rationale")

    def _help(self, intent: UserIntent = None) -> SystemResponse:
        """Show available commands."""
        return SystemResponse(
            message=(
                "Available commands:\n"
                "\n"
                "  Trading Workflow:\n"
                "    plan                          — Daily plan: desk-aware trade ideas (fast, single call)\n"
                "    strategies <ticker>             — 9-strategy assessment for a ticker (detailed)\n"
                "    scan                          — Full scan: Scout populate + screen + Maverick gates\n"
                "    propose                       — Show Maverick's trade proposals (from last scan)\n"
                "    deploy                        — Book all proposed trades to WhatIf portfolio\n"
                "    deploy --portfolio <alias>    — Book to specific portfolio\n"
                "    mark                          — Mark-to-market: update prices/Greeks on all open trades\n"
                "    exits                         — Check exit rules: profit targets, stop losses, DTE\n"
                "    close <id>                    — Close a specific trade\n"
                "    close auto                    — Auto-close all URGENT + profit target exit signals\n"
                "\n"
                "  Actions:\n"
                "    approve <id>       — Approve a recommendation\n"
                "    reject <id>        — Reject a recommendation\n"
                "    defer <id>         — Defer a decision\n"
                "    halt               — Halt all trading\n"
                "    resume             — Resume trading (requires rationale)\n"
                "    override <breaker> — Override circuit breaker (requires rationale)\n"
                "\n"
                "  Trade Booking:\n"
                "    templates                     — List available trade templates\n"
                "    book <#>                      — Book template by index\n"
                "    book <#> --portfolio <alias>  — Book to portfolio (tt/fira/fp/zr/st + w for whatif)\n"
                "    book <filename.json>          — Book by filename\n"
                "\n"
                "  Execution (Go Live):\n"
                "    golive <trade_id>            — Preview WhatIf trade as live order (dry-run)\n"
                "    golive <trade_id> --confirm  — Place the live order on broker\n"
                "    execute <trade_id>           — Same as golive\n"
                "    orders                       — Check live order status / fill updates\n"
                "\n"
                "  Analytics:\n"
                "    perf [desk]                   — Performance dashboard (all desks or one)\n"
                "    learn [days]                  — ML/RL learning analysis (default 90 days)\n"
                "    setup-desks                   — Delete old WhatIf + create 3 trading desks\n"
                "\n"
                "  Reports:\n"
                "    status             — Workflow state summary\n"
                "    list               — Pending recommendations (brief)\n"
                "    portfolios         — All portfolios: capital, Greeks, P&L\n"
                "    positions          — Open trades with Greeks and P&L\n"
                "    greeks             — Portfolio Greeks vs limits\n"
                "    capital            — Capital utilization per portfolio\n"
                "    pending            — Pending recs + exit signals (detailed)\n"
                "    trades             — Today's executed trades\n"
                "    risk               — VaR, macro, circuit breakers\n"
                "\n"
                "  help               — Show this help\n"
                "  quit               — Stop the workflow engine"
            ),
            available_actions=['plan', 'strategies', 'scan', 'propose', 'deploy', 'mark', 'exits',
                             'close', 'perf', 'performance', 'learn', 'setup-desks',
                             'approve', 'reject', 'defer', 'status', 'list',
                             'halt', 'resume', 'override', 'help', 'quit',
                             'portfolios', 'positions', 'greeks', 'capital',
                             'pending', 'trades', 'risk', 'execute', 'orders',
                             'book', 'templates'],
        )

    # ==================================================================
    # Trade booking handlers
    # ==================================================================

    _TEMPLATE_DIR = Path(__file__).resolve().parents[2] / 'config' / 'templates'

    def _templates(self, intent: UserIntent = None) -> SystemResponse:
        """List available trade templates."""
        templates = sorted(self._TEMPLATE_DIR.glob('*.json'))
        if not templates:
            return SystemResponse(message="No templates found.")

        lines = ["TRADE TEMPLATES", "\u2550" * 70]
        lines.append(f"{'#':<4} {'File':<45} {'Underlying':<8} {'Strategy'}")
        lines.append("\u2500" * 70)

        import json
        for i, t in enumerate(templates):
            try:
                data = json.loads(t.read_text())
                underlying = data.get('underlying', '?')
                strategy = data.get('strategy_type', '?')
            except Exception:
                underlying = '?'
                strategy = '?'
            lines.append(f"{i:<4} {t.stem:<45} {underlying:<8} {strategy}")

        lines.append("\u2500" * 70)
        lines.append(f"Book:  book <#> --portfolio <alias>")
        lines.append(f"       Aliases: tt fira fp zr st | ttw firaw fpw zrw stw")

        return SystemResponse(
            message="\n".join(lines),
            data={'template_count': len(templates)},
        )

    def _book(self, intent: UserIntent) -> SystemResponse:
        """
        Book a WhatIf trade from a template file.

        Usage:
            book <#>                          — book template by index (see 'templates')
            book <#> --portfolio <name>       — book to specific portfolio
            book <filename.json>              — book by filename
            book <path/to/file.json>          — book by full path
        """
        if not intent.target:
            return SystemResponse(
                message="Usage: book <#>  or  book <filename.json> [--portfolio <name>]\n"
                        "       Type 'templates' to see available templates.",
            )

        # Resolve the template file
        target = intent.target
        filepath = self._resolve_template(target)
        if filepath is None:
            return SystemResponse(
                message=f"Template not found: {target}\n"
                        f"Type 'templates' to see available templates.",
            )

        # Load and validate
        import json
        try:
            trade_data = json.loads(filepath.read_text())
        except Exception as e:
            return SystemResponse(message=f"Failed to load {filepath.name}: {e}")

        # Multi-strategy file support
        if 'strategies' in trade_data:
            return SystemResponse(
                message=f"{filepath.name} is a multi-strategy file with "
                        f"{len(trade_data['strategies'])} strategies. "
                        f"Use the CLI for multi-strategy booking:\n"
                        f"  python -m trading_cotrader.cli.book_trade --file {filepath} --list",
            )

        # Validate required fields
        for field in ('underlying', 'strategy_type', 'legs'):
            if field not in trade_data:
                return SystemResponse(message=f"Template missing required field: {field}")

        if not trade_data.get('legs'):
            return SystemResponse(message="Template has no legs.")

        # Override portfolio if specified (resolve short aliases)
        portfolio_override = intent.parameters.get('portfolio')
        if portfolio_override:
            trade_data['portfolio_name'] = resolve_portfolio_name(portfolio_override)
        elif trade_data.get('portfolio_name'):
            trade_data['portfolio_name'] = resolve_portfolio_name(trade_data['portfolio_name'])

        portfolio_name = trade_data.get('portfolio_name', '—')
        underlying = trade_data['underlying']
        strategy = trade_data['strategy_type']
        num_legs = len(trade_data['legs'])

        # Book using manual Greeks path (same as --no-broker)
        from trading_cotrader.cli.book_trade import book_with_manual_greeks

        result = book_with_manual_greeks(trade_data)

        if not result.success:
            return SystemResponse(
                message=f"Booking FAILED: {result.error}",
                data={'error': result.error},
            )

        # Format leg summary
        leg_lines = []
        if result.legs:
            for leg in result.legs:
                side = 'SELL' if leg.quantity < 0 else 'BUY '
                greeks = leg.position_greeks
                leg_lines.append(
                    f"    {side} {abs(leg.quantity)}x {leg.streamer_symbol:<28} "
                    f"@ ${leg.mid_price:.2f}  "
                    f"d={greeks['delta']:+.1f} th={greeks['theta']:+.1f}"
                )

        total = result.total_greeks or {}

        lines = [
            "",
            "  TRADE BOOKED",
            "  " + "\u2550" * 55,
            f"  Trade ID:    {result.trade_id[:12]}...",
            f"  Template:    {filepath.stem}",
            f"  Underlying:  {underlying}",
            f"  Strategy:    {strategy}",
            f"  Portfolio:   {portfolio_name}",
            f"  Entry:       ${float(result.entry_price):,.2f}",
            "",
            "  Legs:",
            *leg_lines,
            "",
            f"  Net Greeks:  delta={total.get('delta', 0):+.2f}  "
            f"theta={total.get('theta', 0):+.2f}  "
            f"gamma={total.get('gamma', 0):+.4f}  "
            f"vega={total.get('vega', 0):+.2f}",
            "",
            "  " + "\u2500" * 55,
            f"  View with: positions",
        ]

        return SystemResponse(
            message="\n".join(lines),
            data={
                'trade_id': result.trade_id,
                'underlying': underlying,
                'strategy': strategy,
                'portfolio': portfolio_name,
                'entry_price': float(result.entry_price),
            },
        )

    def _resolve_template(self, target: str) -> Path | None:
        """Resolve a template target to a file path.

        Accepts:
          - Index number (from 'templates' listing)
          - Filename with or without .json
          - Absolute or relative file path
        """
        # Try as integer index
        try:
            idx = int(target)
            templates = sorted(self._TEMPLATE_DIR.glob('*.json'))
            if 0 <= idx < len(templates):
                return templates[idx]
            return None
        except ValueError:
            pass

        # Try as direct path
        p = Path(target)
        if p.is_file():
            return p

        # Try as filename in templates dir
        candidate = self._TEMPLATE_DIR / target
        if candidate.is_file():
            return candidate

        # Try with .json extension
        if not target.endswith('.json'):
            candidate = self._TEMPLATE_DIR / (target + '.json')
            if candidate.is_file():
                return candidate

        return None

    # ==================================================================
    # Report handlers
    # ==================================================================

    def _portfolios(self, intent: UserIntent = None) -> SystemResponse:
        """All portfolios: short alias, broker, capital, equity, cash, deployed %, Greeks."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import PortfolioORM

        # Build reverse map: display_name → short alias
        aliases = _load_portfolio_aliases()
        # Invert: config_key → shortest alias
        key_to_alias: dict[str, str] = {}
        for alias, config_key in aliases.items():
            if alias == config_key:
                continue  # skip full names, we want the short ones
            if config_key not in key_to_alias or len(alias) < len(key_to_alias[config_key]):
                key_to_alias[config_key] = alias

        # Build display_name / account_number → short alias by loading config
        name_to_alias: dict[str, str] = {}
        try:
            from trading_cotrader.config.risk_config_loader import get_risk_config
            rc = get_risk_config()
            for key, pc in rc.portfolios.portfolios.items():
                short = key_to_alias.get(key, key)
                name_to_alias[pc.display_name] = short
                name_to_alias[key] = short
                if pc.account_number:
                    name_to_alias[pc.account_number] = short
        except Exception:
            pass

        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            if not portfolios:
                return SystemResponse(message="No portfolios found.")

            hdr = (
                f"{'ID':<6} {'Name':<22} {'Broker':<12} {'Type':<8} "
                f"{'Equity':>12} {'Cash':>12} {'Dply%':>6} "
                f"{'Delta':>8} {'Theta':>8} {'P&L':>10}"
            )
            sep = "\u2500" * len(hdr)

            lines = ["PORTFOLIOS", "\u2550" * len(hdr), hdr, sep]
            tot_equity = tot_cash = tot_pnl = Decimal(0)
            tot_delta = tot_theta = Decimal(0)

            for p in portfolios:
                equity = p.total_equity or Decimal(0)
                cash = p.cash_balance or Decimal(0)
                deployed_pct = (
                    float((equity - cash) / equity * 100) if equity else 0.0
                )
                delta = p.portfolio_delta or Decimal(0)
                theta = p.portfolio_theta or Decimal(0)
                pnl = p.total_pnl or Decimal(0)
                broker = (p.broker or '—')[:11]
                ptype = (p.portfolio_type or '—')[:7]
                short = (name_to_alias.get(p.name)
                         or name_to_alias.get(p.account_id)
                         or '—')

                lines.append(
                    f"{short:<6} {p.name[:21]:<22} {broker:<12} "
                    f"{ptype:<8} "
                    f"{_fmt_dec(equity, 0, '$'):>12} {_fmt_dec(cash, 0, '$'):>12} "
                    f"{deployed_pct:>5.0f}% "
                    f"{_fmt_dec(delta, 1, '+'):>8} {_fmt_dec(theta, 1, '+'):>8} "
                    f"{_fmt_dec(pnl, 0, '$'):>10}"
                )
                tot_equity += equity
                tot_cash += cash
                tot_pnl += pnl
                tot_delta += delta
                tot_theta += theta

            lines.append(sep)
            lines.append(
                f"{'':6} {'TOTAL':<22} {'':<12} {'':<8} "
                f"{_fmt_dec(tot_equity, 0, '$'):>12} {_fmt_dec(tot_cash, 0, '$'):>12} "
                f"{'':>6} "
                f"{_fmt_dec(tot_delta, 1, '+'):>8} {_fmt_dec(tot_theta, 1, '+'):>8} "
                f"{_fmt_dec(tot_pnl, 0, '$'):>10}"
            )
            lines.append("")
            lines.append("Use ID in commands:  book 22 --portfolio ttw")

        return SystemResponse(
            message="\n".join(lines),
            data={'portfolio_count': len(portfolios)},
        )

    def _positions(self, intent: UserIntent = None) -> SystemResponse:
        """Open + WhatIf trades grouped by portfolio."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import TradeORM, PortfolioORM

        # Build name → alias lookup
        aliases = _load_portfolio_aliases()
        key_to_alias: dict[str, str] = {}
        for alias, config_key in aliases.items():
            if alias == config_key:
                continue
            if config_key not in key_to_alias or len(alias) < len(key_to_alias[config_key]):
                key_to_alias[config_key] = alias
        name_to_alias: dict[str, str] = {}
        try:
            from trading_cotrader.config.risk_config_loader import get_risk_config
            rc = get_risk_config()
            for key, pc in rc.portfolios.portfolios.items():
                short = key_to_alias.get(key, key)
                name_to_alias[pc.display_name] = short
                if pc.account_number:
                    name_to_alias[pc.account_number] = short
        except Exception:
            pass

        with session_scope() as session:
            trades = (
                session.query(TradeORM)
                .filter(TradeORM.trade_status.in_([
                    'executed', 'partial', 'intent', 'pending',
                ]))
                .order_by(TradeORM.underlying_symbol)
                .all()
            )
            if not trades:
                return SystemResponse(message="No positions. Book one with: book <#> --portfolio <alias>")

            # Group by portfolio
            by_portfolio: dict[str, list] = {}
            for t in trades:
                pname = '—'
                if t.portfolio:
                    pname = t.portfolio.name or '—'
                by_portfolio.setdefault(pname, []).append(t)

            hdr = (
                f"  {'ID':<10} {'Underlying':<10} {'Strategy':<18} {'Status':<8} "
                f"{'Entry':>10} {'P&L':>10} "
                f"{'Delta':>7} {'Theta':>7}"
            )
            sep = "\u2500" * (len(hdr) + 2)

            lines = ["POSITIONS BY PORTFOLIO"]
            total_count = 0
            whatif_count = 0

            for pname in sorted(by_portfolio.keys()):
                ptrades = by_portfolio[pname]
                short = name_to_alias.get(pname, '—')
                p_delta = Decimal(0)
                p_theta = Decimal(0)

                lines.append("")
                lines.append(f"\u2550\u2550 {pname} [{short}]  ({len(ptrades)} trades) \u2550" * 1)
                lines.append(hdr)
                lines.append(sep)

                for t in ptrades:
                    strategy_name = '—'
                    if t.strategy_id and t.strategy:
                        strategy_name = t.strategy.strategy_type or '—'

                    entry = t.entry_price
                    pnl = t.total_pnl or Decimal(0)
                    delta = t.current_delta or Decimal(0)
                    theta = t.current_theta or Decimal(0)
                    p_delta += delta
                    p_theta += theta

                    status = t.trade_status or '—'
                    if status == 'intent' and t.trade_type == 'what_if':
                        status = 'WHATIF'
                        whatif_count += 1
                    elif status == 'executed':
                        status = 'OPEN'
                    elif status == 'pending':
                        status = 'PENDING'

                    lines.append(
                        f"  {t.id[:8]:<10} {t.underlying_symbol[:9]:<10} "
                        f"{strategy_name[:17]:<18} {status:<8} "
                        f"{_fmt_dec(entry, 2, '$'):>10} "
                        f"{_fmt_dec(pnl, 0, '$'):>10} "
                        f"{_fmt_dec(delta, 1, '+'):>7} {_fmt_dec(theta, 1, '+'):>7}"
                    )
                    total_count += 1

                lines.append(
                    f"  {'':10} {'':10} {'':18} {'':8} "
                    f"{'':>10} {'':>10} "
                    f"{_fmt_dec(p_delta, 1, '+'):>7} {_fmt_dec(p_theta, 1, '+'):>7}"
                )

            lines.append("")
            lines.append(f"Total: {total_count}  (WHATIF: {whatif_count})")
            if whatif_count:
                lines.append("")
                lines.append("Execute a WhatIf:  execute <id>           (preview)")
                lines.append("                   execute <id> --confirm (place order)")

        return SystemResponse(
            message="\n".join(lines),
            data={'total_count': total_count, 'whatif_count': whatif_count},
        )

    def _greeks(self, intent: UserIntent = None) -> SystemResponse:
        """Portfolio-level Greeks with limits and headroom."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import PortfolioORM

        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            if not portfolios:
                return SystemResponse(message="No portfolios found.")

            lines = ["PORTFOLIO GREEKS", "\u2550" * 80]

            for p in portfolios:
                delta = float(p.portfolio_delta or 0)
                gamma = float(p.portfolio_gamma or 0)
                theta = float(p.portfolio_theta or 0)
                vega = float(p.portfolio_vega or 0)

                max_d = float(p.max_portfolio_delta or 500)
                max_g = float(p.max_portfolio_gamma or 50)
                min_t = float(p.min_portfolio_theta or -500)
                max_v = float(p.max_portfolio_vega or 1000)

                d_pct = abs(delta) / max_d * 100 if max_d else 0
                g_pct = abs(gamma) / max_g * 100 if max_g else 0
                t_pct = abs(theta) / abs(min_t) * 100 if min_t else 0
                v_pct = abs(vega) / max_v * 100 if max_v else 0

                def bar(pct: float) -> str:
                    filled = int(pct / 10)
                    filled = min(filled, 10)
                    return "\u2588" * filled + "\u2591" * (10 - filled)

                lines.append(f"\n  {p.name}")
                lines.append(f"  {'─' * 70}")
                lines.append(
                    f"    Delta: {delta:>+8.1f} / {max_d:>6.0f}  "
                    f"[{bar(d_pct)}] {d_pct:>4.0f}%"
                )
                lines.append(
                    f"    Gamma: {gamma:>+8.3f} / {max_g:>6.1f}  "
                    f"[{bar(g_pct)}] {g_pct:>4.0f}%"
                )
                lines.append(
                    f"    Theta: {theta:>+8.1f} / {min_t:>6.0f}  "
                    f"[{bar(t_pct)}] {t_pct:>4.0f}%"
                )
                lines.append(
                    f"    Vega:  {vega:>+8.1f} / {max_v:>6.0f}  "
                    f"[{bar(v_pct)}] {v_pct:>4.0f}%"
                )

        return SystemResponse(
            message="\n".join(lines),
            data={'portfolio_count': len(portfolios)},
        )

    def _capital(self, intent: UserIntent = None) -> SystemResponse:
        """Capital utilization: deployed vs idle, gap %, severity."""
        # Try context first (populated by CapitalUtilizationAgent)
        ctx_capital = self.engine.context.get('capital_utilization', {})

        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import PortfolioORM

        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type.in_(['real', 'paper']))
                .order_by(PortfolioORM.name)
                .all()
            )
            if not portfolios and not ctx_capital:
                return SystemResponse(message="No capital data available.")

            hdr = (
                f"{'Portfolio':<22} {'Initial':>12} {'Equity':>12} "
                f"{'Cash':>12} {'Deployed%':>9} {'Idle$':>12} {'Severity':<10}"
            )
            sep = "\u2500" * len(hdr)
            lines = ["CAPITAL UTILIZATION", "\u2550" * len(hdr), hdr, sep]

            # Use context data if available (richer: has severity, opp cost)
            ctx_portfolios = ctx_capital.get('portfolios', {})

            for p in portfolios:
                initial = p.initial_capital or Decimal(0)
                equity = p.total_equity or Decimal(0)
                cash = p.cash_balance or Decimal(0)
                deployed = equity - cash if equity else Decimal(0)
                deployed_pct = float(deployed / equity * 100) if equity else 0.0
                idle = float(cash)
                severity = '—'

                # Overlay richer data from context if available
                pdata = ctx_portfolios.get(p.name, {})
                if pdata:
                    severity = pdata.get('severity', '—')
                    if pdata.get('gap_pct') is not None:
                        deployed_pct = 100 - float(pdata['gap_pct'])
                    if pdata.get('idle_capital') is not None:
                        idle = float(pdata['idle_capital'])

                lines.append(
                    f"{p.name[:21]:<22} {_fmt_dec(initial, 0, '$'):>12} "
                    f"{_fmt_dec(equity, 0, '$'):>12} "
                    f"{_fmt_dec(cash, 0, '$'):>12} "
                    f"{deployed_pct:>8.1f}% "
                    f"{_fmt_dec(Decimal(str(idle)), 0, '$'):>12} "
                    f"{severity:<10}"
                )

            lines.append(sep)

            # Summary from context
            summary = ctx_capital.get('summary', {})
            if summary:
                lines.append(
                    f"  Opportunity cost/day: {_fmt_dec(summary.get('total_opp_cost_daily'), 2, '$')}"
                )

        return SystemResponse(message="\n".join(lines))

    def _pending(self, intent: UserIntent = None) -> SystemResponse:
        """Show pending decisions from workflow context."""
        ctx = self.engine.context
        recs = ctx.get('pending_recommendations', [])
        exits = ctx.get('exit_signals', [])

        if not recs and not exits:
            return SystemResponse(message="No pending decisions.")

        lines = []
        if recs:
            lines.append(f"PENDING RECOMMENDATIONS: {len(recs)}")
            for r in recs:
                lines.append(
                    f"  [{r.get('id', '?')[:8]}] {r.get('underlying', '?')} "
                    f"{r.get('strategy_type', '?')} conf={r.get('confidence', '?')}"
                )
        if exits:
            lines.append(f"EXIT SIGNALS: {len(exits)}")
            for s in exits:
                lines.append(
                    f"  [{s.get('id', '?')[:8]}] {s.get('underlying', '?')} "
                    f"{s.get('type', '?')} urgency={s.get('exit_urgency', '?')}"
                )

        return SystemResponse(
            message="\n".join(lines),
            pending_decisions=[*recs, *exits],
            requires_action=True,
            data={'pending_count': len(recs) + len(exits)},
        )

    def _trades(self, intent: UserIntent = None) -> SystemResponse:
        """Today's trades: what was executed, source, P&L."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import TradeORM

        today_start = datetime.combine(date.today(), datetime.min.time())

        with session_scope() as session:
            trades = (
                session.query(TradeORM)
                .filter(TradeORM.created_at >= today_start)
                .order_by(TradeORM.created_at.desc())
                .all()
            )
            if not trades:
                return SystemResponse(message="No trades today.")

            hdr = (
                f"{'ID':<10} {'Underlying':<10} {'Strategy':<18} "
                f"{'Status':<10} {'Entry':>8} {'P&L':>10} "
                f"{'Source':<14} {'Time':<8}"
            )
            sep = "\u2500" * len(hdr)
            lines = ["TODAY'S TRADES", "\u2550" * len(hdr), hdr, sep]

            for t in trades:
                strategy_name = '—'
                if t.strategy:
                    strategy_name = t.strategy.strategy_type or '—'

                time_str = t.created_at.strftime('%H:%M') if t.created_at else '—'
                source = (t.trade_source or 'manual')[:13]
                status = (t.trade_status or '—')[:9]

                lines.append(
                    f"{t.id[:9]:<10} {t.underlying_symbol[:9]:<10} "
                    f"{strategy_name[:17]:<18} "
                    f"{status:<10} "
                    f"{_fmt_dec(t.entry_price, 2, '$'):>8} "
                    f"{_fmt_dec(t.total_pnl, 0, '$'):>10} "
                    f"{source:<14} {time_str:<8}"
                )

            lines.append(sep)
            lines.append(f"Total today: {len(trades)}")

        return SystemResponse(
            message="\n".join(lines),
            data={'trade_count': len(trades)},
        )

    def _risk(self, intent: UserIntent = None) -> SystemResponse:
        """Risk dashboard: VaR, macro, circuit breakers, constraints."""
        ctx = self.engine.context
        lines = ["RISK DASHBOARD", "\u2550" * 70]

        # VaR
        risk = ctx.get('risk_snapshot', {})
        lines.append("\n  Value at Risk")
        lines.append(f"  {'─' * 40}")
        lines.append(f"    VaR 95% (1-day): {_fmt_dec(risk.get('var_95'), 0, '$')}")
        lines.append(f"    VaR 99% (1-day): {_fmt_dec(risk.get('var_99'), 0, '$')}")
        if risk.get('expected_shortfall_95'):
            lines.append(
                f"    ES 95%:          {_fmt_dec(risk.get('expected_shortfall_95'), 0, '$')}"
            )

        # Macro
        macro = ctx.get('macro_assessment', {})
        lines.append("\n  Macro Environment")
        lines.append(f"  {'─' * 40}")
        lines.append(f"    Regime:     {macro.get('regime', '—')}")
        lines.append(f"    VIX:        {ctx.get('vix', '—')}")
        lines.append(f"    Confidence: {macro.get('confidence', '—')}")
        rationale = macro.get('rationale', '')
        if rationale:
            lines.append(f"    Rationale:  {rationale[:60]}")

        # Circuit breakers
        guardian = ctx.get('guardian_status', {})
        breakers = guardian.get('circuit_breakers', {})
        lines.append("\n  Circuit Breakers")
        lines.append(f"  {'─' * 40}")
        if breakers:
            for name, status in breakers.items():
                indicator = "TRIPPED" if status else "OK"
                symbol = "!!" if status else "  "
                lines.append(f"    {symbol} {name:<25} {indicator}")
        else:
            cb = self.engine.config.circuit_breakers
            daily_loss = ctx.get('daily_pnl_pct', 0)
            weekly_loss = ctx.get('weekly_pnl_pct', 0)
            lines.append(f"    Daily loss:     {daily_loss:.1f}% (limit {cb.daily_loss_pct}%)")
            lines.append(f"    Weekly loss:    {weekly_loss:.1f}% (limit {cb.weekly_loss_pct}%)")
            vix = ctx.get('vix', 0)
            lines.append(f"    VIX level:      {vix} (halt >{cb.vix_halt_threshold:.0f})")

        # Trading constraints
        tc = self.engine.config.constraints
        lines.append("\n  Trading Constraints")
        lines.append(f"  {'─' * 40}")
        trades_today = ctx.get('trades_today_count', 0)
        lines.append(f"    Trades today:   {trades_today} / {tc.max_trades_per_day} max")
        halted = ctx.get('halt_reason')
        if halted:
            lines.append(f"    STATUS:         HALTED — {halted}")
        else:
            lines.append(f"    STATUS:         Active")

        return SystemResponse(
            message="\n".join(lines),
            data={
                'var_95': risk.get('var_95'),
                'macro_regime': macro.get('regime'),
                'trades_today': trades_today,
                'halted': bool(halted),
            },
        )

    # ==================================================================
    # Execution handlers — WhatIf → Live Order
    # ==================================================================

    def _execute(self, intent: UserIntent) -> SystemResponse:
        """
        Execute a WhatIf trade as a live order on the broker.

        Flow:
          1. `execute <trade_id>` → dry-run preview with full risk detail
          2. `execute <trade_id> --confirm` → place the real order
        """
        if not intent.target:
            return SystemResponse(
                message="Usage: execute <trade_id>     (dry-run preview)\n"
                        "       execute <trade_id> --confirm  (place real order)",
            )

        trade_id = intent.target
        is_confirm = intent.parameters.get('confirm', False)

        # ---- Load the trade from DB ----
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import (
            TradeORM, LegORM, SymbolORM, PortfolioORM,
        )

        with session_scope() as session:
            # Support partial ID matching (like git short hashes)
            trade = session.query(TradeORM).filter_by(id=trade_id).first()
            if not trade:
                matches = (
                    session.query(TradeORM)
                    .filter(TradeORM.id.like(f"{trade_id}%"))
                    .all()
                )
                if len(matches) == 1:
                    trade = matches[0]
                    trade_id = trade.id  # expand to full ID
                elif len(matches) > 1:
                    ids = ", ".join(m.id[:8] for m in matches[:5])
                    return SystemResponse(
                        message=f"Ambiguous ID '{trade_id}' matches {len(matches)} trades: {ids}\n"
                                f"Use more characters to disambiguate.",
                    )
            if not trade:
                return SystemResponse(message=f"Trade not found: {trade_id}")

            # Validate: must be a WhatIf/paper trade that is open or intent
            if trade.trade_type not in ('what_if', 'paper'):
                return SystemResponse(
                    message=f"Trade {trade_id[:8]} is type '{trade.trade_type}' — "
                            f"only what_if/paper trades can be executed live.",
                )
            if trade.trade_status in ('closed', 'cancelled', 'expired'):
                return SystemResponse(
                    message=f"Trade {trade_id[:8]} is {trade.trade_status} — cannot execute.",
                )
            if not trade.legs:
                return SystemResponse(
                    message=f"Trade {trade_id[:8]} has no legs — nothing to execute.",
                )

            # ---- Resolve target broker ----
            # Find the real portfolio that matches this trade's portfolio's broker
            portfolio = trade.portfolio
            if not portfolio:
                return SystemResponse(message=f"Trade {trade_id[:8]} has no portfolio assigned.")

            # Load config to find the real portfolio & broker
            from trading_cotrader.config.risk_config_loader import get_risk_config
            risk_config = get_risk_config()

            # Try to find matching config: portfolio name or broker+account_id
            portfolio_config = None
            for name, pc in risk_config.portfolios.portfolios.items():
                if pc.broker_firm == (portfolio.broker or '') and \
                   pc.account_number == (portfolio.account_id or ''):
                    portfolio_config = pc
                    break
                # Also match by portfolio name
                if name == portfolio.name:
                    portfolio_config = pc
                    break

            # If this is a whatif portfolio, find its real parent
            target_config = portfolio_config
            if portfolio_config and portfolio_config.is_whatif and portfolio_config.mirrors_real:
                real_config = risk_config.portfolios.get_by_name(portfolio_config.mirrors_real)
                if real_config:
                    target_config = real_config

            if not target_config:
                return SystemResponse(
                    message=f"Cannot resolve target broker for portfolio '{portfolio.name}'.",
                )

            # Check execution config
            exec_cfg = self.engine.config.execution
            if target_config.broker_firm not in exec_cfg.allowed_brokers:
                return SystemResponse(
                    message=f"Broker '{target_config.broker_firm}' is not in allowed_brokers "
                            f"for live execution. Allowed: {exec_cfg.allowed_brokers}",
                )

            # Get the adapter
            broker_router = self.engine.broker_router
            adapter = broker_router.adapters.get(target_config.broker_firm)
            if not adapter:
                return SystemResponse(
                    message=f"No adapter loaded for '{target_config.broker_firm}'. "
                            f"Start the workflow with broker credentials to execute live orders.",
                )

            # Check adapter has place_order
            if not hasattr(adapter, 'place_order'):
                return SystemResponse(
                    message=f"Adapter for '{target_config.broker_firm}' does not support order placement.",
                )

            # ---- Build order legs ----
            order_legs = []
            streamer_symbols = []  # for quote fetching
            leg_details = []  # for display

            for leg_orm in trade.legs:
                sym = leg_orm.symbol
                if not sym:
                    return SystemResponse(
                        message=f"Leg {leg_orm.id[:8]} has no symbol — cannot execute.",
                    )

                # Determine OCC symbol
                if sym.asset_type == 'option':
                    occ_symbol = adapter._domain_symbol_to_occ(
                        dm.Symbol(
                            ticker=sym.ticker,
                            asset_type=dm.AssetType.OPTION,
                            option_type=(dm.OptionType.CALL if sym.option_type == 'call'
                                        else dm.OptionType.PUT),
                            strike=Decimal(str(sym.strike)) if sym.strike else Decimal(0),
                            expiration=sym.expiration,
                            multiplier=sym.multiplier or 100,
                        )
                    )
                    instrument_type = 'EQUITY_OPTION'
                    # Build streamer symbol for quote
                    streamer_sym = adapter._occ_to_streamer_symbol(occ_symbol)
                    if streamer_sym:
                        streamer_symbols.append(streamer_sym)
                else:
                    occ_symbol = sym.ticker
                    instrument_type = 'EQUITY'
                    streamer_symbols.append(sym.ticker)

                # Map leg side to order action
                side = (leg_orm.side or '').lower()
                qty = leg_orm.quantity or 0

                if side in ('sell', 'sell_to_open'):
                    action = 'SELL_TO_OPEN'
                elif side in ('buy', 'buy_to_open'):
                    action = 'BUY_TO_OPEN'
                elif side == 'sell_to_close':
                    action = 'SELL_TO_CLOSE'
                elif side == 'buy_to_close':
                    action = 'BUY_TO_CLOSE'
                else:
                    # Infer from quantity sign
                    if qty < 0:
                        action = 'SELL_TO_OPEN'
                    else:
                        action = 'BUY_TO_OPEN'

                order_legs.append({
                    'occ_symbol': occ_symbol,
                    'action': action,
                    'quantity': abs(qty),
                    'instrument_type': instrument_type,
                })

                # For display
                strike_str = f"{sym.strike}" if sym.strike else ''
                opt_str = f" {sym.option_type.upper()[0] if sym.option_type else ''}{strike_str}" if sym.asset_type == 'option' else ''
                exp_str = f" {sym.expiration.strftime('%y%m%d')}" if sym.expiration else ''
                leg_details.append({
                    'action': action.replace('_', ' '),
                    'quantity': abs(qty),
                    'symbol': f"{sym.ticker}{exp_str}{opt_str}",
                    'occ': occ_symbol,
                    'entry_price': float(leg_orm.entry_price) if leg_orm.entry_price else 0,
                })

            # ---- Fetch current quotes for mid-price ----
            mid_price = None
            quote_details = {}
            try:
                if streamer_symbols:
                    quotes = adapter.get_quotes(streamer_symbols)
                    for i, leg in enumerate(leg_details):
                        sym_key = streamer_symbols[i] if i < len(streamer_symbols) else None
                        if sym_key and sym_key in quotes:
                            q = quotes[sym_key]
                            leg['bid'] = q.get('bid', 0)
                            leg['ask'] = q.get('ask', 0)
                            leg['mid'] = (q.get('bid', 0) + q.get('ask', 0)) / 2
                            quote_details[sym_key] = q

                    # Calculate net mid price across all legs
                    # Credit legs (SELL) add to price, debit legs (BUY) subtract
                    net_mid = Decimal(0)
                    for i, ol in enumerate(order_legs):
                        sym_key = streamer_symbols[i] if i < len(streamer_symbols) else None
                        if sym_key and sym_key in quotes:
                            q = quotes[sym_key]
                            leg_mid = Decimal(str((q.get('bid', 0) + q.get('ask', 0)) / 2))
                            if 'SELL' in ol['action']:
                                net_mid += leg_mid * ol['quantity']
                            else:
                                net_mid -= leg_mid * ol['quantity']

                    # Apply price offset from config
                    net_mid += Decimal(str(exec_cfg.price_offset))
                    mid_price = net_mid
            except Exception as e:
                logger.warning(f"Could not fetch quotes for mid-price: {e}")

            # Fall back to entry price if no quotes
            if mid_price is None:
                mid_price = Decimal(str(trade.entry_price or 0))

            # ---- Determine credit/debit ----
            # TastyTrade convention: positive = credit, negative = debit
            price_type = "CREDIT" if mid_price > 0 else "DEBIT"

            # ---- If confirming, check stored preflight ----
            if is_confirm:
                pending = self.engine.context.get('pending_execution', {})
                if pending.get('trade_id') != trade_id:
                    return SystemResponse(
                        message=f"No pending preview for trade {trade_id[:8]}. "
                                f"Run 'execute {trade_id[:8]}' first to preview.",
                    )

                # Use stored price from preflight
                stored_price = Decimal(str(pending.get('price', mid_price)))

                try:
                    result = adapter.place_order(
                        legs=order_legs,
                        price=stored_price,
                        order_type=exec_cfg.order_type,
                        time_in_force=exec_cfg.time_in_force,
                        dry_run=False,
                    )
                except Exception as e:
                    return SystemResponse(
                        message=f"Order FAILED: {e}",
                        data={'error': str(e)},
                    )

                if result.get('errors'):
                    return SystemResponse(
                        message=f"Order REJECTED by broker:\n"
                                + "\n".join(f"  - {err}" for err in result['errors']),
                        data=result,
                    )

                # Update trade in DB: set broker_trade_id and status
                trade.broker_trade_id = str(result.get('order_id', ''))
                trade.trade_status = 'pending'
                trade.submitted_at = datetime.utcnow()
                session.commit()

                # Clear pending execution
                self.engine.context.pop('pending_execution', None)

                order_id = result.get('order_id', '?')
                lines = [
                    "",
                    f"  Order PLACED on {target_config.broker_firm.title()}!",
                    f"  \u2550" * 50,
                    f"  Order ID:    {order_id}",
                    f"  Status:      {result.get('status', '?')}",
                    f"  Price:       ${abs(float(stored_price)):.2f} {price_type}",
                    f"  Fees:        ${result.get('fees', 0):.2f}",
                    "",
                    f"  Trade {trade_id[:8]} status → PENDING",
                    f"  Use 'orders' to check fill status.",
                ]
                if result.get('warnings'):
                    lines.append("  Warnings:")
                    for w in result['warnings']:
                        lines.append(f"    - {w}")

                return SystemResponse(
                    message="\n".join(lines),
                    data={
                        'order_id': order_id,
                        'trade_id': trade_id,
                        'status': result.get('status'),
                    },
                )

            # ---- Dry-run preview ----
            try:
                preflight = adapter.place_order(
                    legs=order_legs,
                    price=mid_price,
                    order_type=exec_cfg.order_type,
                    time_in_force=exec_cfg.time_in_force,
                    dry_run=True,
                )
            except Exception as e:
                return SystemResponse(
                    message=f"Dry-run FAILED: {e}",
                    data={'error': str(e)},
                )

            if preflight.get('errors'):
                return SystemResponse(
                    message=f"Order would be REJECTED:\n"
                            + "\n".join(f"  - {err}" for err in preflight['errors']),
                    data=preflight,
                )

            # Store for confirm step
            self.engine.context['pending_execution'] = {
                'trade_id': trade_id,
                'price': float(mid_price),
                'order_legs': order_legs,
                'preflight': preflight,
                'target_broker': target_config.broker_firm,
                'target_account': target_config.account_number,
            }

            # ---- Format preview ----
            bp = preflight.get('buying_power_effect', {})
            strategy_name = '—'
            if trade.strategy:
                strategy_name = trade.strategy.strategy_type or '—'

            lines = [
                "",
                "  ORDER PREVIEW (DRY-RUN)",
                "  " + "\u2550" * 50,
                f"  Underlying:   {trade.underlying_symbol}",
                f"  Strategy:     {strategy_name}",
                f"  Target:       {target_config.broker_firm.title()} ({target_config.account_number})",
                "",
                "  Legs:",
            ]

            for ld in leg_details:
                bid_ask = ""
                if 'bid' in ld and 'ask' in ld:
                    bid_ask = f"  (bid={ld['bid']:.2f} / ask={ld['ask']:.2f})"
                price_str = f"@ ${ld.get('mid', ld['entry_price']):.2f}" if 'mid' in ld else ""
                lines.append(
                    f"    {ld['action']:<16} {ld['quantity']}x {ld['symbol']:<25} {price_str}{bid_ask}"
                )

            lines.extend([
                "",
                f"  Net Price:    ${abs(float(mid_price)):.2f} {price_type} (LIMIT)",
                "",
                "  Margin / Buying Power:",
                f"    Current BP:     ${bp.get('current_buying_power', 0):>12,.2f}",
                f"    BP Change:      ${bp.get('change_in_buying_power', 0):>12,.2f}",
                f"    BP After:       ${bp.get('new_buying_power', 0):>12,.2f}",
                f"    Margin Req:     ${bp.get('isolated_order_margin_requirement', 0):>12,.2f}",
                "",
                f"  Fees:         ${preflight.get('fees', 0):.2f}",
            ])

            # Greeks from trade
            delta = float(trade.current_delta or 0)
            theta = float(trade.current_theta or 0)
            gamma = float(trade.current_gamma or 0)
            vega = float(trade.current_vega or 0)
            if any([delta, theta, gamma, vega]):
                lines.extend([
                    "",
                    "  Trade Greeks:",
                    f"    Delta: {delta:+.2f}  Theta: {theta:+.2f}  "
                    f"Gamma: {gamma:+.3f}  Vega: {vega:+.2f}",
                ])

            if preflight.get('warnings'):
                lines.append("")
                lines.append("  Warnings:")
                for w in preflight['warnings']:
                    lines.append(f"    - {w}")

            lines.extend([
                "",
                "  " + "\u2500" * 50,
                f"  To place this order: execute {trade_id[:8]} --confirm",
                f"  To cancel: any other command clears the preview.",
            ])

        return SystemResponse(
            message="\n".join(lines),
            requires_action=True,
            data={
                'trade_id': trade_id,
                'price': float(mid_price),
                'price_type': price_type,
                'fees': preflight.get('fees', 0),
                'buying_power_effect': bp,
                'preview': True,
            },
            available_actions=[f'execute {trade_id[:8]} --confirm'],
        )

    def _orders(self, intent: UserIntent = None) -> SystemResponse:
        """
        Show live/recent orders and auto-update fill status.

        Queries trades with trade_status='pending' and broker_trade_id set,
        polls the broker for fill status, and auto-marks filled trades.
        """
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import TradeORM

        # Get adapter for checking orders
        adapter = None
        for broker_name in (self.engine.config.execution.allowed_brokers or []):
            adapter = self.engine.broker_router.adapters.get(broker_name)
            if adapter and hasattr(adapter, 'get_order'):
                break

        with session_scope() as session:
            # Find all pending trades with broker order IDs
            pending_trades = (
                session.query(TradeORM)
                .filter(
                    TradeORM.trade_status == 'pending',
                    TradeORM.broker_trade_id.isnot(None),
                    TradeORM.broker_trade_id != '',
                )
                .order_by(TradeORM.submitted_at.desc())
                .all()
            )

            lines = ["LIVE ORDERS", "\u2550" * 80]
            updated_count = 0

            if pending_trades and adapter:
                hdr = (
                    f"{'OrderID':<12} {'Underlying':<10} {'Status':<12} "
                    f"{'Price':>10} {'Filled':>8} {'Age':<10}"
                )
                lines.extend([hdr, "\u2500" * 80])

                for t in pending_trades:
                    order_info = {}
                    try:
                        order_info = adapter.get_order(t.broker_trade_id)
                    except Exception as e:
                        logger.warning(f"Could not fetch order {t.broker_trade_id}: {e}")
                        order_info = {
                            'status': 'UNKNOWN',
                            'order_id': t.broker_trade_id,
                        }

                    status = order_info.get('status', 'UNKNOWN')

                    # Auto-update filled orders
                    if status == 'Filled':
                        t.trade_status = 'executed'
                        t.executed_at = datetime.utcnow()
                        # Try to get fill price
                        fill_price = order_info.get('price')
                        if fill_price is not None:
                            t.current_price = Decimal(str(fill_price))
                        updated_count += 1

                    elif status in ('Cancelled', 'Rejected', 'Expired', 'Removed'):
                        t.trade_status = 'cancelled'
                        t.notes = (t.notes or '') + f" Broker status: {status}"
                        t.is_open = False
                        updated_count += 1

                    # Age calculation
                    age_str = '—'
                    if t.submitted_at:
                        age_secs = (datetime.utcnow() - t.submitted_at).total_seconds()
                        if age_secs < 60:
                            age_str = f"{int(age_secs)}s"
                        elif age_secs < 3600:
                            age_str = f"{int(age_secs / 60)}m"
                        else:
                            age_str = f"{int(age_secs / 3600)}h {int((age_secs % 3600) / 60)}m"

                    # Price
                    price_str = _fmt_dec(order_info.get('price'), 2, '$')

                    # Filled qty
                    filled = order_info.get('filled_quantity', 0)
                    total_qty = sum(
                        abs(leg.quantity or 0) for leg in t.legs
                    ) if t.legs else 0
                    fill_str = f"{filled}/{total_qty}"

                    lines.append(
                        f"{str(t.broker_trade_id)[:11]:<12} "
                        f"{t.underlying_symbol[:9]:<10} "
                        f"{status[:11]:<12} "
                        f"{price_str:>10} "
                        f"{fill_str:>8} "
                        f"{age_str:<10}"
                    )

                session.commit()

            elif pending_trades and not adapter:
                lines.append("No broker adapter available — cannot poll order status.")
                lines.append(f"  {len(pending_trades)} pending trade(s) with broker order IDs.")
            else:
                lines.append("No pending orders.")

            # Also show recently filled (last hour)
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            recent = (
                session.query(TradeORM)
                .filter(
                    TradeORM.trade_status.in_(['executed', 'cancelled']),
                    TradeORM.broker_trade_id.isnot(None),
                    TradeORM.broker_trade_id != '',
                    TradeORM.executed_at >= one_hour_ago,
                )
                .order_by(TradeORM.executed_at.desc())
                .limit(10)
                .all()
            )

            if recent:
                lines.extend(["", "RECENT (last hour)", "\u2500" * 80])
                for t in recent:
                    time_str = t.executed_at.strftime('%H:%M') if t.executed_at else '—'
                    lines.append(
                        f"  {str(t.broker_trade_id)[:11]:<12} "
                        f"{t.underlying_symbol[:9]:<10} "
                        f"{t.trade_status:<12} "
                        f"{_fmt_dec(t.current_price, 2, '$'):>10} "
                        f"{time_str}"
                    )

            if updated_count:
                lines.extend(["", f"Updated {updated_count} order(s)."])

        return SystemResponse(
            message="\n".join(lines),
            data={
                'pending_count': len(pending_trades),
                'updated_count': updated_count,
            },
        )

    # ==================================================================
    # Trading workflow: scan → propose → deploy
    # ==================================================================

    def _plan(self, intent: UserIntent = None) -> SystemResponse:
        """Generate desk-aware daily trading plan via MarketAnalyzer."""
        from trading_cotrader.services.daily_plan_service import generate_desk_plan

        engine = self.engine
        lines = ["DAILY TRADING PLAN", "\u2550" * 80]

        # Get MarketAnalyzer from Scout (it has broker-injected providers)
        try:
            ma = engine.scout._get_market_analyzer()
        except Exception as e:
            return SystemResponse(message=f"Cannot init MarketAnalyzer: {e}")

        lines.append("Generating plan (single call across all desks)...")
        try:
            result = generate_desk_plan(ma)
        except Exception as e:
            return SystemResponse(message=f"Plan generation failed: {e}")

        # Day verdict
        verdict = result.get('day_verdict', '?').upper()
        reasons = result.get('day_verdict_reasons', [])
        elapsed = result.get('elapsed_s', '?')
        lines.append(f"  Verdict: {verdict}  ({elapsed}s)")
        for r in reasons:
            lines.append(f"    {r}")

        # Risk budget
        rb = result.get('risk_budget', {})
        lines.append(
            f"  Risk budget: max {rb.get('max_new_positions', '?')} positions, "
            f"${rb.get('max_daily_risk_dollars', '?')} daily risk, "
            f"size factor {rb.get('position_size_factor', '?')}"
        )

        # Expiry events
        for ev in result.get('expiry_events', []):
            lines.append(f"  EXPIRY: {ev.get('label', '?')} ({', '.join(ev.get('tickers', []))})")

        # Per-desk breakdown
        desk_plans = result.get('desk_plans', [])
        for dp in desk_plans:
            desk_name = dp.get('display_name', dp.get('desk_key', '?'))
            count = dp.get('trade_count', 0)
            capital = dp.get('capital', 0)
            lines.extend(["", f"  {desk_name} (${capital:,}): {count} trades"])

            for t in dp.get('trades', []):
                ticker = t.get('ticker', '?')
                strat = t.get('strategy_type', '?')
                verdict_t = t.get('verdict', '?')
                score = t.get('composite_score', 0)
                direction = t.get('direction', '?')
                v_mark = '\u2713' if verdict_t == 'go' else ('~' if verdict_t == 'caution' else '\u2717')

                lines.append(
                    f"    {t.get('rank', '?'):>2}. {ticker:<8} {strat:<18} "
                    f"{v_mark} {verdict_t:<7} {score:>5.2f}  {direction}"
                )

                # Show trade spec legs if available
                spec = t.get('trade_spec')
                if spec and spec.get('leg_codes'):
                    legs_str = ' | '.join(spec['leg_codes'][:4])
                    lines.append(f"        {legs_str}")

                rationale = t.get('rationale', '')
                if rationale:
                    lines.append(f"        {rationale[:80]}")

        total = result.get('total_trades', 0)
        summary = result.get('summary', '')
        lines.extend([
            "",
            f"  {summary}",
            "",
            "  Next: 'scan' for full pipeline (Scout + Maverick gates) → 'propose' → 'deploy'",
        ])

        return SystemResponse(
            message="\n".join(lines),
            data={
                'total_trades': total,
                'desks': len(desk_plans),
                'verdict': result.get('day_verdict', '?'),
            },
        )

    def _strategies(self, intent: UserIntent = None) -> SystemResponse:
        """Run 9 strategy assessments for a single ticker."""
        if not intent or not intent.target:
            return SystemResponse(
                message="Usage: strategies <ticker>\n  Example: strategies AAPL",
                requires_action=True,
            )

        ticker = intent.target.upper()
        engine = self.engine

        # Get MarketAnalyzer
        try:
            ma = engine.scout._get_market_analyzer()
        except Exception as e:
            return SystemResponse(message=f"Cannot init MarketAnalyzer: {e}")

        strategies = [
            ('Iron Condor', ma.opportunity.assess_iron_condor),
            ('Iron Butterfly', ma.opportunity.assess_iron_butterfly),
            ('Calendar', ma.opportunity.assess_calendar),
            ('Diagonal', ma.opportunity.assess_diagonal),
            ('0DTE', ma.opportunity.assess_zero_dte),
            ('Breakout', ma.opportunity.assess_breakout),
            ('Momentum', ma.opportunity.assess_momentum),
            ('Mean Reversion', ma.opportunity.assess_mean_reversion),
            ('LEAP', ma.opportunity.assess_leap),
        ]

        lines = [f"STRATEGY ASSESSMENT: {ticker}", "\u2550" * 80]
        go_count = 0
        caution_count = 0

        for label, assess_fn in strategies:
            try:
                result = assess_fn(ticker)
                verdict = getattr(result, 'verdict', None) or '?'
                verdict_lower = verdict.lower() if isinstance(verdict, str) else '?'
                conf = getattr(result, 'confidence', None)
                direction = getattr(result, 'direction', None) or getattr(result, 'trend_direction', None) or ''
                summary = getattr(result, 'summary', None) or ''

                conf_str = f" {int(conf * 100)}%" if conf is not None else ''
                dir_str = f" {direction}" if direction else ''

                if verdict_lower == 'go':
                    v_mark = '\u2713 GO'
                    go_count += 1
                elif verdict_lower == 'caution':
                    v_mark = '~ CAUTION'
                    caution_count += 1
                else:
                    v_mark = '\u2717 NO GO'

                lines.append(f"  {label:<18} {v_mark}{conf_str}{dir_str}")
                if summary:
                    lines.append(f"    {summary[:100]}")

                # Show trade spec legs if available
                spec = getattr(result, 'trade_spec', None)
                if spec:
                    leg_codes = getattr(spec, 'leg_codes', None) or (spec.get('leg_codes') if isinstance(spec, dict) else None)
                    if leg_codes:
                        lines.append(f"    Legs: {' | '.join(leg_codes[:4])}")
            except Exception as e:
                lines.append(f"  {label:<18} ERROR: {e}")

        score = go_count * 2 + caution_count
        lines.extend([
            "",
            f"  Score: {score} ({go_count} GO, {caution_count} CAUTION)",
        ])

        return SystemResponse(
            message="\n".join(lines),
            data={
                'ticker': ticker,
                'go_count': go_count,
                'caution_count': caution_count,
                'score': score,
            },
        )

    def _scan(self, intent: UserIntent = None) -> SystemResponse:
        """Run Scout's screening + ranking pipeline on the watchlist."""
        engine = self.engine

        lines = ["MARKET SCAN", "\u2550" * 80]

        # Run Scout.populate (fetch data) + Scout.run (screen + rank)
        try:
            lines.append("Running Scout.populate() — fetching market data...")
            result = engine.scout.populate(engine.context)
            lines.append(f"  {result.messages[0] if result.messages else result.status.value}")
        except Exception as e:
            lines.append(f"  Scout.populate failed: {e}")

        try:
            lines.append("Running Scout.run() — screening + ranking...")
            result = engine.scout.run(engine.context)
            for msg in result.messages:
                lines.append(f"  {msg}")
        except Exception as e:
            lines.append(f"  Scout.run failed: {e}")

        # Run Maverick to generate proposals from rankings
        try:
            lines.append("Running Maverick.run() — generating proposals...")
            result = engine.maverick.run(engine.context)
            for msg in result.messages:
                lines.append(f"  {msg}")
        except Exception as e:
            lines.append(f"  Maverick.run failed: {e}")

        # Show ranking summary
        ranking = engine.context.get('ranking', [])
        if ranking:
            lines.extend(["", "TOP RANKED IDEAS", "\u2500" * 80])
            lines.append(
                f"  {'#':<3} {'Ticker':<8} {'Strategy':<20} {'Verdict':<9} "
                f"{'Score':>6} {'Direction':<10}"
            )
            lines.append("  " + "\u2500" * 70)
            for i, r in enumerate(ranking[:15]):
                verdict = r.get('verdict', '?')
                v_mark = '\u2713' if verdict == 'go' else ('~' if verdict == 'caution' else '\u2717')
                lines.append(
                    f"  {i:<3} {r.get('ticker', '?'):<8} "
                    f"{r.get('strategy_name', '?'):<20} "
                    f"{v_mark} {verdict:<7} "
                    f"{r.get('composite_score', 0):>5.2f}  "
                    f"{r.get('direction', '?'):<10}"
                )

        # Show proposals
        proposals = engine.context.get('trade_proposals', [])
        proposed = [p for p in proposals if p.get('status') == 'proposed']
        rejected = [p for p in proposals if p.get('status') == 'rejected']

        if proposed:
            lines.extend(["", "TRADE PROPOSALS (ready to deploy)", "\u2500" * 80])
            for i, p in enumerate(proposed):
                spec = p.get('trade_spec', {})
                legs = spec.get('legs', [])
                lines.append(
                    f"  [{i}] {p['ticker']} {p['strategy_name']} — "
                    f"score={p['score']:.2f} {p['direction']}"
                )
                lines.append(f"      {p.get('rationale', '')[:80]}")
                for leg in legs:
                    action = leg.get('action', '?')
                    qty = leg.get('quantity', 1)
                    ot = 'C' if leg.get('option_type') == 'call' else 'P'
                    strike = leg.get('strike', 0)
                    exp = leg.get('expiration', '?')
                    lines.append(f"        {action} {qty}x {p['ticker']} {ot}{strike:.0f} {exp}")
                exit_rules = p.get('exit_rules', {})
                if exit_rules.get('exit_summary'):
                    lines.append(f"      Exit: {exit_rules['exit_summary']}")
            lines.extend(["", "  → Type 'deploy' to book these to WhatIf portfolio"])
        else:
            lines.extend(["", f"  No actionable proposals ({len(rejected)} rejected by gates)"])

        mkt_env = engine.context.get('market_environment', '?')
        bs_level = engine.context.get('black_swan_level', '?')
        lines.extend(["", f"  Environment: {mkt_env} | Black Swan: {bs_level}"])

        return SystemResponse(
            message="\n".join(lines),
            data={
                'ranking_count': len(ranking),
                'proposed': len(proposed),
                'rejected': len(rejected),
            },
        )

    def _propose(self, intent: UserIntent = None) -> SystemResponse:
        """Show current trade proposals (from last scan)."""
        proposals = self.engine.context.get('trade_proposals', [])
        if not proposals:
            return SystemResponse(
                message="No proposals. Run 'scan' first to generate trade proposals.",
            )

        lines = ["TRADE PROPOSALS", "\u2550" * 80]

        proposed = [p for p in proposals if p.get('status') == 'proposed']
        rejected = [p for p in proposals if p.get('status') == 'rejected']

        if proposed:
            lines.append("PROPOSED (will book on 'deploy'):")
            lines.append(
                f"  {'#':<3} {'Ticker':<8} {'Strategy':<18} "
                f"{'Score':>6} {'Dir':<10} Rationale"
            )
            lines.append("  " + "\u2500" * 75)
            for i, p in enumerate(proposed):
                spec = p.get('trade_spec', {})
                lines.append(
                    f"  {i:<3} {p['ticker']:<8} {p['strategy_name']:<18} "
                    f"{p['score']:>5.2f}  {p['direction']:<10} "
                    f"{p.get('rationale', '')[:40]}"
                )
                # Show legs
                for leg in spec.get('legs', []):
                    action = leg.get('action', '?')
                    ot = 'C' if leg.get('option_type') == 'call' else 'P'
                    strike = leg.get('strike', 0)
                    exp = leg.get('expiration', '?')
                    label = leg.get('strike_label', '')
                    lines.append(
                        f"        {action} {leg.get('quantity', 1)}x "
                        f"{p['ticker']} {ot}{strike:.0f} {exp}  ({label})"
                    )
                # Exit rules
                exit_rules = p.get('exit_rules', {})
                if exit_rules.get('exit_summary'):
                    lines.append(f"      Exit: {exit_rules['exit_summary']}")
                # Risk notes
                for note in p.get('risk_notes', [])[:2]:
                    lines.append(f"      \u26a0 {note}")
                lines.append("")

        if rejected:
            lines.append(f"REJECTED ({len(rejected)}):")
            for p in rejected[:5]:
                lines.append(
                    f"  \u2717 {p.get('ticker', '?')} {p.get('strategy_name', '?')} "
                    f"— {p.get('gate_result', '?')}"
                )
            if len(rejected) > 5:
                lines.append(f"  ... and {len(rejected) - 5} more")

        if proposed:
            lines.extend([
                "",
                f"  {len(proposed)} trade(s) ready. Type 'deploy' to book to WhatIf.",
                "  Type 'deploy --portfolio tt' to book to a specific portfolio.",
            ])

        return SystemResponse(
            message="\n".join(lines),
            data={'proposed': len(proposed), 'rejected': len(rejected)},
        )

    def _deploy(self, intent: UserIntent) -> SystemResponse:
        """Book all proposed trades to WhatIf portfolio."""
        proposals = self.engine.context.get('trade_proposals', [])
        proposed = [p for p in proposals if p.get('status') == 'proposed']

        if not proposed:
            return SystemResponse(
                message="No proposals to deploy. Run 'scan' first.",
            )

        # Resolve portfolio
        raw_portfolio = intent.parameters.get('portfolio') if intent else None
        portfolio_name = resolve_portfolio_name(raw_portfolio) if raw_portfolio else None

        lines = ["DEPLOYING TRADES", "\u2550" * 80]
        target = portfolio_name or self.engine.maverick.DEFAULT_WHATIF_PORTFOLIO
        lines.append(f"  Target portfolio: {target}")
        lines.append(f"  Trades to book: {len(proposed)}")
        lines.append("")

        # Book via Maverick
        results = self.engine.maverick.book_proposals(
            self.engine.context,
            portfolio_name=portfolio_name,
        )

        success_count = 0
        fail_count = 0
        for r in results:
            if r.get('success'):
                success_count += 1
                greeks = r.get('greeks', {})
                lines.append(
                    f"  \u2713 {r['ticker']} {r['strategy']} — "
                    f"entry=${r.get('entry_price', 0):.2f}  "
                    f"\u0394={greeks.get('delta', 0):.2f}  "
                    f"\u0398={greeks.get('theta', 0):.2f}  "
                    f"score={r.get('score', 0):.2f}"
                )
                lines.append(f"    trade_id: {r.get('trade_id', '?')[:12]}...")
            else:
                fail_count += 1
                lines.append(
                    f"  \u2717 {r.get('ticker', '?')} {r.get('strategy', '?')} — "
                    f"{r.get('error', 'unknown error')}"
                )

        lines.extend([
            "",
            f"  Done: {success_count} booked, {fail_count} failed",
        ])

        if success_count > 0:
            lines.append("  Type 'trades' to see booked trades. Type 'positions' for portfolio.")

        # Clear proposals after deployment
        self.engine.context['trade_proposals'] = []

        return SystemResponse(
            message="\n".join(lines),
            data={'booked': success_count, 'failed': fail_count},
        )

    def _mark(self, intent: UserIntent = None) -> SystemResponse:
        """Run mark-to-market on all open trades."""
        engine = self.engine
        lines = ["MARK-TO-MARKET", "\u2550" * 80]

        try:
            result = engine.maverick.mark_to_market()

            if not result.results:
                lines.append("  No open trades to mark.")
                if result.trades_skipped:
                    lines.append(f"  ({result.trades_skipped} trades skipped — no valid symbols)")
                return SystemResponse(message="\n".join(lines))

            lines.append(
                f"  {'Underlying':<10} {'Strategy':<18} {'Entry':>10} "
                f"{'Current':>10} {'P&L':>10} {'P&L%':>7} {'Legs'}"
            )
            lines.append("  " + "\u2500" * 75)

            for r in result.results:
                pnl_sign = '+' if r.pnl >= 0 else ''
                lines.append(
                    f"  {r.underlying:<10} {r.strategy_type:<18} "
                    f"${r.entry_price:>9.2f} ${r.current_price:>9.2f} "
                    f"{pnl_sign}${r.pnl:>8.2f} {r.pnl_pct:>+6.1f}% "
                    f"{r.legs_marked}/{r.legs_total}"
                )

            lines.extend([
                "",
                f"  Total P&L: ${result.total_pnl:+,.2f}",
                f"  Trades marked: {result.trades_marked} | "
                f"Failed: {result.trades_failed} | "
                f"Skipped: {result.trades_skipped}",
            ])

            if result.errors:
                lines.append("")
                for err in result.errors[:3]:
                    lines.append(f"  \u2717 {err}")

        except Exception as e:
            lines.append(f"  Error: {e}")

        return SystemResponse(
            message="\n".join(lines),
            data={'trades_marked': result.trades_marked if 'result' in dir() else 0},
        )

    def _exits(self, intent: UserIntent = None) -> SystemResponse:
        """Check exit conditions on all open trades."""
        lines = ["EXIT MONITOR", "\u2550" * 80]

        try:
            from trading_cotrader.services.exit_monitor import ExitMonitorService
            monitor = ExitMonitorService()
            result = monitor.check_all_exits()

            if not result.signals:
                lines.append(f"  All {result.trades_checked} open trades within limits.")
                lines.append(f"  ({result.trades_ok} trades OK)")
                return SystemResponse(message="\n".join(lines))

            # Group by severity
            urgent = [s for s in result.signals if s.severity == 'URGENT']
            warnings = [s for s in result.signals if s.severity == 'WARNING']
            info = [s for s in result.signals if s.severity == 'INFO']

            if urgent:
                lines.extend(["", "  URGENT — Action Required:"])
                lines.append("  " + "\u2500" * 70)
                for s in urgent:
                    dte_str = f" ({s.dte} DTE)" if s.dte is not None else ""
                    lines.append(
                        f"  \u26a0 {s.underlying:<8} {s.strategy_type:<16} "
                        f"P&L ${s.current_pnl:+.2f} ({s.current_pnl_pct:+.0f}%){dte_str}"
                    )
                    lines.append(f"    {s.message}")
                    lines.append(f"    Action: {s.action}")
                    lines.append("")

            if warnings:
                lines.extend(["  WARNINGS:"])
                for s in warnings:
                    dte_str = f" ({s.dte} DTE)" if s.dte is not None else ""
                    lines.append(
                        f"  ~ {s.underlying:<8} {s.strategy_type:<16} "
                        f"P&L ${s.current_pnl:+.2f}{dte_str} — {s.signal_type}"
                    )

            if info:
                lines.extend(["", "  PROFIT TARGETS HIT:"])
                for s in info:
                    lines.append(
                        f"  \u2713 {s.underlying:<8} {s.strategy_type:<16} "
                        f"P&L ${s.current_pnl:+.2f} ({s.current_pnl_pct:+.0f}%) — TAKE PROFIT"
                    )

            lines.extend([
                "",
                f"  Summary: {result.trades_checked} checked, "
                f"{result.urgent_count} urgent, {result.warning_count} warnings, "
                f"{len(info)} profit targets hit",
            ])

            # Store in context for other commands
            self.engine.context['exit_signals'] = result.signals

        except Exception as e:
            lines.append(f"  Error: {e}")

        return SystemResponse(message="\n".join(lines))

    # ==================================================================
    # Close trade handler
    # ==================================================================

    def _close(self, intent: UserIntent) -> SystemResponse:
        """Close a trade by ID, or auto-close all exit signals."""
        from trading_cotrader.services.trade_lifecycle import TradeLifecycleService

        lifecycle = TradeLifecycleService(
            container_manager=self.engine.container_manager,
        )

        target = (intent.target or '').strip()

        # 'close auto' — auto-close all URGENT + PROFIT_TARGET signals
        if target == 'auto':
            exit_signals = self.engine.context.get('exit_signals', [])
            if not exit_signals:
                return SystemResponse(message="No exit signals to auto-close. Run 'exits' first.")

            results = lifecycle.auto_close_from_signals(exit_signals)
            if not results:
                return SystemResponse(message="No trades qualified for auto-close.")

            lines = ["AUTO-CLOSE RESULTS", "═" * 60]
            for r in results:
                if r['success']:
                    lines.append(
                        f"  ✓ {r['underlying']:<8} {r['strategy_type']:<16} "
                        f"P&L ${float(r['pnl']):+.2f}  reason={r['reason']}"
                    )
                else:
                    lines.append(f"  ✗ {r.get('error', 'unknown error')}")

            closed_count = sum(1 for r in results if r['success'])
            lines.append(f"\n  {closed_count}/{len(results)} trades closed.")

            # Clear exit signals after auto-close
            self.engine.context['exit_signals'] = []
            return SystemResponse(message="\n".join(lines))

        # 'close <trade_id>' — close specific trade
        if not target:
            return SystemResponse(
                message="Usage: close <trade_id>  or  close auto\n"
                        "  close <trade_id> [--reason <reason>]  — Close specific trade\n"
                        "  close auto                            — Auto-close all exit signals"
            )

        reason = 'manual'
        params = intent.params or {}
        if isinstance(params, dict) and 'reason' in params:
            reason = params['reason']

        result = lifecycle.close_trade(trade_id=target, reason=reason)

        if result['success']:
            return SystemResponse(
                message=(
                    f"Trade closed: {result['underlying']} {result['strategy_type']}\n"
                    f"  Entry:  ${float(result['entry_price']):,.2f}\n"
                    f"  Exit:   ${float(result['exit_price']):,.2f}\n"
                    f"  P&L:    ${float(result['pnl']):+,.2f} ({result['pnl_pct']:+.1f}%)\n"
                    f"  Reason: {result['reason']}"
                )
            )
        else:
            return SystemResponse(message=f"Close failed: {result.get('error', 'unknown')}")

    # ==================================================================
    # Performance dashboard handler
    # ==================================================================

    def _performance(self, intent: UserIntent = None) -> SystemResponse:
        """Show per-desk performance dashboard."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import PortfolioORM, TradeORM
        from trading_cotrader.services.performance_metrics_service import PerformanceMetricsService

        lines = ["PERFORMANCE DASHBOARD", "═" * 80]

        desk_names = ['desk_0dte', 'desk_medium', 'desk_leaps']
        target = (intent.target or '').strip() if intent else ''
        if target:
            resolved = resolve_portfolio_name(target)
            desk_names = [resolved]

        with session_scope() as session:
            svc = PerformanceMetricsService(session)

            for desk_name in desk_names:
                portfolio = session.query(PortfolioORM).filter_by(name=desk_name).first()
                if not portfolio:
                    lines.append(f"\n  {desk_name}: NOT FOUND — run 'setup-desks' to create")
                    continue

                metrics = svc.calculate_portfolio_metrics(
                    portfolio_id=portfolio.id,
                    label=desk_name,
                    initial_capital=portfolio.initial_capital or Decimal('0'),
                )
                breakdown = svc.calculate_strategy_breakdown(
                    portfolio_id=portfolio.id,
                    label=desk_name,
                )

                # Header
                cap = float(portfolio.initial_capital or 0)
                equity = float(portfolio.total_equity or cap)
                lines.extend([
                    "",
                    f"  ┌─ {desk_name.upper()} {'─' * (60 - len(desk_name))}",
                    f"  │  Capital: ${cap:,.0f}  →  Equity: ${equity:,.0f}  "
                    f"(Return: {metrics.return_pct:+.1f}%)",
                ])

                # Overall stats
                if metrics.total_trades > 0:
                    lines.extend([
                        f"  │  Trades: {metrics.total_trades}  "
                        f"(W:{metrics.winning_trades} L:{metrics.losing_trades} B:{metrics.breakeven_trades})",
                        f"  │  Win Rate: {metrics.win_rate:.1f}%  "
                        f"Profit Factor: {metrics.profit_factor:.2f}  "
                        f"Expectancy: ${float(metrics.expectancy):+,.2f}",
                        f"  │  Total P&L: ${float(metrics.total_pnl):+,.2f}  "
                        f"Avg Win: ${float(metrics.avg_win):,.2f}  "
                        f"Avg Loss: ${float(metrics.avg_loss):,.2f}",
                        f"  │  Sharpe: {metrics.sharpe_ratio:.2f}  "
                        f"Max Drawdown: {metrics.max_drawdown_pct:.1f}%",
                    ])
                else:
                    lines.append(f"  │  No closed trades yet.")

                # Strategy breakdown
                if breakdown.strategies:
                    lines.append(f"  │")
                    lines.append(f"  │  By Strategy:")
                    for strat, sm in breakdown.strategies.items():
                        lines.append(
                            f"  │    {strat:<20} "
                            f"{sm.total_trades:>3} trades  "
                            f"{sm.win_rate:5.1f}% WR  "
                            f"${float(sm.total_pnl):>+9,.2f}  "
                            f"PF={sm.profit_factor:.2f}"
                        )

                # Open trades count
                open_count = (
                    session.query(TradeORM)
                    .filter_by(portfolio_id=portfolio.id, is_open=True)
                    .count()
                )
                lines.append(f"  │  Open Positions: {open_count}")
                lines.append(f"  └{'─' * 65}")

        return SystemResponse(message="\n".join(lines))

    # ==================================================================
    # ML learning handler
    # ==================================================================

    def _learn(self, intent: UserIntent = None) -> SystemResponse:
        """Run ML/RL learning analysis on closed trades."""
        from trading_cotrader.services.trade_learner import TradeLearner

        lines = ["ML/RL LEARNING ANALYSIS", "═" * 80]

        days = 90
        if intent and intent.target:
            try:
                days = int(intent.target)
            except ValueError:
                pass

        learner = TradeLearner()
        result = learner.learn_from_history(days=days)

        lines.append(f"  Analyzed {result.trades_analyzed} closed trades (last {days} days)")
        lines.append(f"  Patterns: {result.patterns_updated} updated, {result.patterns_discovered} new")

        # Insights
        if result.insights:
            lines.extend(["", "  INSIGHTS:"])
            for insight in result.insights:
                lines.append(f"    • {insight}")

        # Best patterns
        if result.best_patterns:
            lines.extend(["", "  TOP PATTERNS (by risk-adjusted return):"])
            for p in result.best_patterns:
                lines.append(
                    f"    ↑ {p.pattern_key:<40} "
                    f"{p.trades:>3} trades  "
                    f"{p.win_rate:5.0%} WR  "
                    f"${p.avg_pnl:>+8.2f} avg  "
                    f"Sharpe={p.sharpe:.2f}"
                )

        # Worst patterns
        if result.worst_patterns:
            worst_negative = [p for p in result.worst_patterns if p.sharpe < 0]
            if worst_negative:
                lines.extend(["", "  AVOID PATTERNS (negative Sharpe):"])
                for p in worst_negative:
                    lines.append(
                        f"    ↓ {p.pattern_key:<40} "
                        f"{p.trades:>3} trades  "
                        f"{p.win_rate:5.0%} WR  "
                        f"${p.avg_pnl:>+8.2f} avg  "
                        f"Sharpe={p.sharpe:.2f}"
                    )

        # All patterns summary
        summary = learner.get_pattern_summary()
        if summary:
            lines.extend(["", f"  ALL PATTERNS ({len(summary)} with ≥2 trades):"])
            for row in summary[:15]:
                lines.append(
                    f"    {row['pattern']:<40} "
                    f"{row['trades']:>3} trades  "
                    f"{row['win_rate']:>5}  "
                    f"{row['avg_pnl']:>10}  "
                    f"S={row['sharpe']}"
                )

        return SystemResponse(message="\n".join(lines))

    # ==================================================================
    # Setup desks handler
    # ==================================================================

    def _setup_desks(self, intent: UserIntent = None) -> SystemResponse:
        """Delete old WhatIf portfolios and create 3 trading desks."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import PortfolioORM
        from trading_cotrader.config.risk_config_loader import get_risk_config
        import uuid

        lines = ["SETUP TRADING DESKS", "═" * 60]

        with session_scope() as session:
            # 1. Delete existing WhatIf portfolios
            old_whatif = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()

            deleted = 0
            for p in old_whatif:
                lines.append(f"  Deleting: {p.name} (id={p.id[:8]}...)")
                session.delete(p)
                deleted += 1

            if deleted:
                session.flush()
                lines.append(f"  Deleted {deleted} old WhatIf portfolio(s).")
            else:
                lines.append("  No existing WhatIf portfolios to delete.")

            # 2. Create the 3 trading desks from risk_config
            rc = get_risk_config()
            desk_configs = {
                'desk_0dte': {'capital': Decimal('10000'), 'desc': '0DTE Day Trading Desk'},
                'desk_medium': {'capital': Decimal('10000'), 'desc': '~45 DTE Medium-Term Desk'},
                'desk_leaps': {'capital': Decimal('20000'), 'desc': 'LEAPs 1-2 Year Desk'},
            }

            created = 0
            for desk_name, desk_info in desk_configs.items():
                # Get risk limits from config if available
                risk_limits = {}
                cfg = rc.portfolios.get_by_name(desk_name)
                if cfg:
                    risk_limits = cfg.risk_limits or {}

                portfolio = PortfolioORM(
                    id=str(uuid.uuid4()),
                    name=desk_name,
                    portfolio_type='what_if',
                    initial_capital=desk_info['capital'],
                    cash_balance=desk_info['capital'],
                    buying_power=desk_info['capital'],
                    total_equity=desk_info['capital'],
                    description=desk_info['desc'],
                    max_portfolio_delta=Decimal(str(risk_limits.get('max_delta', 100))),
                    max_position_size_pct=Decimal(str(risk_limits.get('max_position_size_pct', 10))),
                )
                session.add(portfolio)
                created += 1
                lines.append(
                    f"  Created: {desk_name}  "
                    f"capital=${float(desk_info['capital']):,.0f}  "
                    f"type=what_if"
                )

            session.commit()

            lines.extend([
                "",
                f"  Summary: {deleted} deleted, {created} created.",
                "",
                "  Trading desks ready:",
                "    desk_0dte   — $10K  0DTE day trades (SPY, QQQ, IWM)",
                "    desk_medium — $10K  ~45 DTE medium-term (top 10 underlyings)",
                "    desk_leaps  — $20K  LEAPs 1-2 year (blue chips)",
                "",
                "  Next: 'scan' → 'propose' → 'deploy' → 'mark' → 'exits' → 'close auto'",
            ])

        # Refresh containers after desk setup
        try:
            self.engine._refresh_containers()
        except Exception:
            pass

        return SystemResponse(message="\n".join(lines))
