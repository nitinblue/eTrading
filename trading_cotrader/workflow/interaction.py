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
    from trading_cotrader.workflow.engine import WorkflowEngine

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
            #   zerodha → zr, stallion → st
            #   *_whatif → append 'w' (ttw, firaw, fpw, zrw, stw)
            _PORTFOLIO_ALIASES[key] = key  # full name always works
    except Exception:
        pass

    # Hardcoded shortcuts (stable, won't break if YAML changes)
    shortcuts = {
        'tt': 'tastytrade', 'fira': 'fidelity_ira', 'fp': 'fidelity_personal',
        'zr': 'zerodha', 'st': 'stallion',
        'ttw': 'tastytrade_whatif', 'firaw': 'fidelity_ira_whatif',
        'fpw': 'fidelity_personal_whatif', 'zrw': 'zerodha_whatif', 'stw': 'stallion_whatif',
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
                "  Execution:\n"
                "    execute <trade_id>           — Preview WhatIf trade as live order (dry-run)\n"
                "    execute <trade_id> --confirm — Place the live order on broker\n"
                "    orders                       — Check live order status / fill updates\n"
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
            available_actions=['approve', 'reject', 'defer', 'status', 'list',
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
            daily_loss = ctx.get('daily_pnl_pct', 0)
            weekly_loss = ctx.get('weekly_pnl_pct', 0)
            lines.append(f"    Daily loss:     {daily_loss:.1f}% (limit 3%)")
            lines.append(f"    Weekly loss:    {weekly_loss:.1f}% (limit 5%)")
            vix = ctx.get('vix', 0)
            lines.append(f"    VIX level:      {vix} (halt >35)")

        # Trading constraints
        lines.append("\n  Trading Constraints")
        lines.append(f"  {'─' * 40}")
        trades_today = ctx.get('trades_today_count', 0)
        lines.append(f"    Trades today:   {trades_today} / 3 max")
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
