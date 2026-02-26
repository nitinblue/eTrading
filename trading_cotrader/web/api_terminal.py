"""
Market Analyzer Terminal API — interactive analysis terminal on the web.

Translates MarketAnalyzer CLI commands into structured block responses
that the frontend renders as a Claude Code-style terminal.

Single endpoint: POST /terminal/execute  {"command": "analyze SPY"}
"""

from typing import TYPE_CHECKING
import asyncio
import logging
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from market_analyzer import MarketAnalyzer, DataService

if TYPE_CHECKING:
    from trading_cotrader.agents.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TerminalRequest(BaseModel):
    command: str


class TerminalResponse(BaseModel):
    blocks: list[dict]
    command: str
    success: bool


# ---------------------------------------------------------------------------
# Block builder helpers
# ---------------------------------------------------------------------------

def _header(text: str) -> dict:
    return {"type": "header", "text": text}


def _kv(items: list[dict]) -> dict:
    return {"type": "keyvalue", "items": items}


def _kv_item(key: str, value: str, color: str | None = None) -> dict:
    d: dict = {"key": key, "value": value}
    if color:
        d["color"] = color
    return d


def _table(headers: list[str], rows: list[list[str]]) -> dict:
    return {"type": "table", "headers": headers, "rows": rows}


def _text(text: str, style: str = "") -> dict:
    d: dict = {"type": "text", "text": text}
    if style:
        d["style"] = style
    return d


def _error(text: str) -> dict:
    return {"type": "error", "text": text}


def _section(title: str) -> dict:
    return {"type": "section", "title": title}


def _status(label: str, color: str) -> dict:
    return {"type": "status", "label": label, "color": color}


def _list(items: list[str], style: str = "") -> dict:
    d: dict = {"type": "list", "items": items}
    if style:
        d["style"] = style
    return d


def _safe(val, fmt: str = ".2f", fallback: str = "N/A") -> str:
    """Safely format a numeric value."""
    if val is None:
        return fallback
    try:
        return f"{val:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


# ---------------------------------------------------------------------------
# Command handlers — each returns list[dict] blocks
# ---------------------------------------------------------------------------

def _handle_context(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    ctx = ma.context.assess()
    blocks: list[dict] = [
        _header(f"Market Context \u2014 {ctx.market} ({ctx.as_of_date})"),
        _kv([
            _kv_item("Environment", ctx.environment_label, "cyan"),
            _kv_item("Trading", "ALLOWED" if ctx.trading_allowed else "HALTED",
                     "green" if ctx.trading_allowed else "red"),
            _kv_item("Size Factor", f"{ctx.position_size_factor:.0%}"),
            _kv_item("Black Swan", f"{ctx.black_swan.alert_level} (score: {ctx.black_swan.composite_score:.2f})",
                     "green" if ctx.black_swan.alert_level == "normal" else "yellow"),
        ]),
    ]

    # Macro events next 7 days
    events_7 = ctx.macro.events_next_7_days
    if events_7:
        blocks.append(_section("Macro Events (Next 7 Days)"))
        rows = [[str(e.date), e.name, e.impact] for e in events_7]
        blocks.append(_table(["Date", "Event", "Impact"], rows))

    # Intermarket
    if ctx.intermarket.entries:
        blocks.append(_section("Intermarket Dashboard"))
        rows = [
            [entry.ticker, f"R{entry.regime}", f"{entry.confidence:.0%}", entry.trend_direction or ""]
            for entry in ctx.intermarket.entries
        ]
        blocks.append(_table(["Ticker", "Regime", "Confidence", "Direction"], rows))

    blocks.append(_text(ctx.summary, "dim"))
    return blocks


def _handle_analyze(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if not args:
        return [_error("Usage: analyze TICKER [TICKER ...]")]

    blocks: list[dict] = []
    for ticker in [a.upper() for a in args]:
        a = ma.instrument.analyze(ticker, include_opportunities=True)
        blocks.append(_header(f"{ticker} \u2014 Instrument Analysis ({a.as_of_date})"))
        blocks.append(_kv([
            _kv_item("Regime", f"R{a.regime_id} ({a.regime.confidence:.0%})", "cyan"),
            _kv_item("Phase", f"{a.phase.phase_name} ({a.phase.confidence:.0%})"),
            _kv_item("Trend Bias", str(a.trend_bias)),
            _kv_item("Volatility", str(a.volatility_label)),
            _kv_item("Price", f"${a.technicals.current_price:.2f}"),
            _kv_item("RSI", f"{a.technicals.rsi.value:.1f}"),
            _kv_item("ATR%", f"{a.technicals.atr_pct:.2f}%"),
        ]))

        # Levels
        if a.levels:
            blocks.append(_section("Levels"))
            level_items = []
            if a.levels.stop_loss:
                level_items.append(
                    _kv_item("Stop", f"${a.levels.stop_loss.price:.2f} ({a.levels.stop_loss.distance_pct:+.1f}%)", "red")
                )
            if a.levels.best_target:
                level_items.append(
                    _kv_item("Target", f"${a.levels.best_target.price:.2f} (R:R {a.levels.best_target.risk_reward_ratio:.1f})", "green")
                )
            if level_items:
                blocks.append(_kv(level_items))

        # Actionable setups
        if a.actionable_setups:
            blocks.append(_list(a.actionable_setups, "conditions"))

        blocks.append(_text(a.summary, "dim"))
    return blocks


def _handle_screen(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    tickers = [a.upper() for a in args] if args else None
    if not tickers:
        from market_analyzer.config import get_settings
        tickers = get_settings().display.default_tickers

    result = ma.screening.scan(tickers)
    blocks: list[dict] = [_header(f"Screening Results ({result.as_of_date})")]

    if not result.candidates:
        blocks.append(_text("No candidates found."))
    else:
        rows = [
            [c.ticker, c.screen, f"{c.score:.2f}", f"R{c.regime_id}",
             f"{c.rsi:.0f}", f"{c.atr_pct:.2f}", c.reason[:60]]
            for c in result.candidates
        ]
        blocks.append(_table(["Ticker", "Screen", "Score", "Regime", "RSI", "ATR%", "Reason"], rows))

    blocks.append(_text(result.summary, "dim"))
    return blocks


def _handle_entry(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if len(args) < 2:
        return [_error("Usage: entry TICKER TRIGGER_TYPE\n  Triggers: breakout, pullback, momentum, mean_reversion, orb")]

    ticker = args[0].upper()
    trigger_map = {
        "breakout": "breakout_confirmed",
        "pullback": "pullback_to_support",
        "momentum": "momentum_continuation",
        "mean_reversion": "mean_reversion_extreme",
        "orb": "orb_breakout",
    }
    trigger_name = trigger_map.get(args[1].lower(), args[1].lower())

    from market_analyzer.models.entry import EntryTriggerType
    trigger = EntryTriggerType(trigger_name)
    result = ma.entry.confirm(ticker, trigger)

    blocks: list[dict] = [
        _header(f"{ticker} \u2014 Entry Confirmation ({result.trigger_type.value})"),
        _status("CONFIRMED" if result.confirmed else "NOT CONFIRMED",
                "green" if result.confirmed else "red"),
        _kv([
            _kv_item("Confidence", f"{result.confidence:.0%}"),
            _kv_item("Conditions", f"{result.conditions_met}/{result.conditions_total}"),
        ]),
    ]

    price_items = []
    if result.suggested_entry_price:
        price_items.append(_kv_item("Entry Price", f"${result.suggested_entry_price:.2f}"))
    if result.suggested_stop_price:
        price_items.append(_kv_item("Stop Price", f"${result.suggested_stop_price:.2f}", "red"))
    if result.risk_per_share:
        price_items.append(_kv_item("Risk/Share", f"${result.risk_per_share:.2f}"))
    if price_items:
        blocks.append(_kv(price_items))

    # Conditions as list
    cond_items = []
    for c in result.conditions:
        prefix = "+" if c.met else "-"
        cond_items.append(f"{prefix} {c.name}: {c.description}")
    if cond_items:
        blocks.append(_list(cond_items, "conditions"))

    return blocks


def _handle_strategy(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if not args:
        return [_error("Usage: strategy TICKER")]

    ticker = args[0].upper()
    ohlcv = ma.data.get_ohlcv(ticker) if ma.data else None
    regime = ma.regime.detect(ticker, ohlcv)
    technicals = ma.technicals.snapshot(ticker, ohlcv)
    result = ma.strategy.select(ticker, regime=regime, technicals=technicals)

    p = result.primary_structure
    blocks: list[dict] = [
        _header(f"{ticker} \u2014 Strategy Recommendation"),
        _kv([
            _kv_item("Structure", p.structure_type.value),
            _kv_item("Direction", str(p.direction)),
            _kv_item("Max Loss", str(p.max_loss)),
            _kv_item("Theta", str(p.theta_exposure)),
            _kv_item("Vega", str(p.vega_exposure)),
            _kv_item("DTE Range", f"{result.suggested_dte_range[0]}-{result.suggested_dte_range[1]}"),
            _kv_item("Delta Range", f"{result.suggested_delta_range[0]:.0%}-{result.suggested_delta_range[1]:.0%}"),
        ]),
    ]

    if result.wing_width_suggestion:
        blocks[-1]["items"].append(_kv_item("Wing Width", str(result.wing_width_suggestion)))

    # Position sizing
    size = ma.strategy.size(result, current_price=technicals.current_price)
    blocks.append(_section("Position Sizing"))
    blocks.append(_kv([
        _kv_item("Account", f"${size.account_size:,.0f}"),
        _kv_item("Max Risk", f"${size.max_risk_dollars:,.0f} ({size.max_risk_pct:.0f}%)"),
        _kv_item("Contracts", f"{size.suggested_contracts} (max {size.max_contracts})"),
    ]))
    if size.margin_estimate:
        blocks[-1]["items"].append(_kv_item("Margin Est", f"${size.margin_estimate:,.0f}"))

    blocks.append(_text(result.regime_rationale, "dim"))

    if result.alternative_structures:
        blocks.append(_section("Alternatives"))
        alt_items = [f"- {alt.structure_type.value} ({alt.direction}): {alt.rationale}"
                     for alt in result.alternative_structures]
        blocks.append(_list(alt_items))

    return blocks


def _handle_exit_plan(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if len(args) < 2:
        return [_error("Usage: exit_plan TICKER ENTRY_PRICE")]

    ticker = args[0].upper()
    try:
        entry_price = float(args[1])
    except ValueError:
        return [_error("Entry price must be a number.")]

    ohlcv = ma.data.get_ohlcv(ticker) if ma.data else None
    regime = ma.regime.detect(ticker, ohlcv)
    technicals = ma.technicals.snapshot(ticker, ohlcv)
    levels = ma.levels.analyze(ticker, ohlcv=ohlcv)
    strategy = ma.strategy.select(ticker, regime=regime, technicals=technicals)

    plan = ma.exit.plan(
        ticker, strategy, entry_price=entry_price,
        regime=regime, technicals=technicals, levels=levels,
    )

    blocks: list[dict] = [
        _header(f"{ticker} \u2014 Exit Plan ({plan.strategy_type} @ ${entry_price:.2f})"),
    ]

    # Profit targets
    if plan.profit_targets:
        blocks.append(_section("Profit Targets"))
        for t in plan.profit_targets:
            blocks.append(_kv([
                _kv_item(f"${t.price:.2f}", f"{t.pct_from_entry:+.1f}%", "green"),
                _kv_item("Action", f"{t.action}: {t.description}"),
            ]))

    # Stop loss
    if plan.stop_loss:
        blocks.append(_section("Stop Loss"))
        blocks.append(_kv([
            _kv_item("Price", f"${plan.stop_loss.price:.2f} ({plan.stop_loss.pct_from_entry:+.1f}%)", "red"),
            _kv_item("Description", plan.stop_loss.description),
        ]))

    # Trailing stop
    if plan.trailing_stop:
        blocks.append(_section("Trailing Stop"))
        blocks.append(_kv([
            _kv_item("Price", f"${plan.trailing_stop.price:.2f}"),
            _kv_item("Description", plan.trailing_stop.description),
        ]))

    # Ratios & thresholds
    ratio_items = []
    if plan.risk_reward_ratio:
        ratio_items.append(_kv_item("R:R Ratio", f"{plan.risk_reward_ratio:.1f}", "cyan"))
    if plan.dte_exit_threshold:
        ratio_items.append(_kv_item("Time Exit", f"Close at {plan.dte_exit_threshold} DTE"))
    if plan.theta_decay_exit_pct:
        ratio_items.append(_kv_item("Theta Exit", f"Close at {plan.theta_decay_exit_pct:.0f}% max profit"))
    if ratio_items:
        blocks.append(_kv(ratio_items))

    # Adjustments
    if plan.adjustments:
        blocks.append(_section("Adjustments"))
        adj_items = [f"[{adj.urgency}] {adj.condition} \u2192 {adj.action}" for adj in plan.adjustments]
        blocks.append(_list(adj_items))

    blocks.append(_text(f"Regime Change: {plan.regime_change_action}", "dim"))
    return blocks


def _handle_plan(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """Generate daily trading plan."""
    from market_analyzer.models.trading_plan import PlanHorizon

    tickers: list[str] = []
    plan_date = None
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            try:
                plan_date = date.fromisoformat(args[i + 1])
            except ValueError:
                return [_error(f"Invalid date: {args[i + 1]}")]
            i += 2
        else:
            tickers.append(args[i].upper())
            i += 1

    plan = ma.plan.generate(tickers=tickers or None, plan_date=plan_date)
    blocks: list[dict] = []

    day_str = plan.plan_for_date.strftime("%a %b %d, %Y")
    blocks.append(_header(f"Daily Trading Plan - {day_str}"))

    # Day verdict
    verdict_colors = {"trade": "green", "trade_light": "yellow", "avoid": "red", "no_trade": "red"}
    vc = verdict_colors.get(plan.day_verdict, "")
    blocks.append(_kv_item("Day Verdict", plan.day_verdict.value.upper().replace("_", " "), vc))

    if plan.day_verdict_reasons:
        for r in plan.day_verdict_reasons:
            blocks.append(_text(f"  {r}", "dim"))

    # Risk budget
    b = plan.risk_budget
    blocks.append(_section("Risk Budget"))
    blocks.append(_kv_item("Max New Positions", str(b.max_new_positions)))
    blocks.append(_kv_item("Daily Risk Budget", f"${b.max_daily_risk_dollars:,.0f}"))
    blocks.append(_kv_item("Position Sizing", f"{b.position_size_factor:.0%}"))

    # Expiry events
    if plan.expiry_events:
        blocks.append(_section("Expiry Events"))
        for e in plan.expiry_events:
            blocks.append(_text(f"  {e.label} ({e.date})"))

    if plan.upcoming_expiries:
        future = [e for e in plan.upcoming_expiries if e.date > plan.plan_for_date]
        if future:
            nxt = future[0]
            blocks.append(_kv_item("Next Expiry", f"{nxt.label} ({nxt.date})"))

    # Trades by horizon
    if not plan.all_trades:
        blocks.append(_text("No actionable trades.", "dim"))
    else:
        from market_analyzer.models.opportunity import get_structure_profile, RiskProfile

        horizon_labels = {
            PlanHorizon.ZERO_DTE: "0DTE",
            PlanHorizon.WEEKLY: "Weekly",
            PlanHorizon.MONTHLY: "Monthly",
            PlanHorizon.LEAP: "LEAP",
        }
        for h in PlanHorizon:
            trades = plan.trades_by_horizon.get(h, [])
            if not trades:
                continue
            blocks.append(_section(f"{horizon_labels[h]} ({len(trades)} trades)"))

            for t in trades:
                verdict_str = t.verdict.value.upper() if hasattr(t.verdict, 'value') else str(t.verdict).upper()

                # Profile tag
                tag = ""
                legs = ""
                if t.trade_spec is not None:
                    legs = " | ".join(t.trade_spec.leg_codes)
                    if t.trade_spec.structure_type:
                        p = get_structure_profile(
                            t.trade_spec.structure_type,
                            t.trade_spec.order_side,
                            t.direction,
                        )
                        risk_str = ("UNDEFINED" if p.risk_profile == RiskProfile.UNDEFINED
                                    else p.risk_profile.value)
                        tag = f"{p.payoff_graph} {p.bias} / {risk_str}"

                blocks.append(_text(
                    f"#{t.rank} {t.ticker}  {t.strategy_type}  {verdict_str}  {t.composite_score:.2f}"
                ))
                if tag:
                    blocks.append(_text(f"  {tag}", "dim"))
                if legs:
                    blocks.append(_text(f"  {legs}"))

                # Max profit/loss + exit
                detail_items = []
                if t.trade_spec:
                    mp = t.trade_spec.max_profit_desc or ""
                    ml = t.trade_spec.max_loss_desc or ""
                    if mp or ml:
                        detail_items.append(f"Max P: {mp} | Max L: {ml}")
                    if t.trade_spec.exit_summary:
                        detail_items.append(f"Exit: {t.trade_spec.exit_summary}")
                if t.max_entry_price is not None:
                    detail_items.append(f"Chase limit: ${t.max_entry_price:.2f}")
                if t.expiry_note:
                    detail_items.append(f"NOTE: {t.expiry_note}")
                if detail_items:
                    blocks.append(_text(f"  {' | '.join(detail_items)}", "dim"))

    blocks.append(_text(plan.summary, "dim"))
    return blocks


def _handle_rank(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    tickers = [a.upper() for a in args] if args else None
    if not tickers:
        from market_analyzer.config import get_settings
        tickers = get_settings().display.default_tickers

    result = ma.ranking.rank(tickers)
    blocks: list[dict] = [_header(f"Trade Ranking ({result.as_of_date})")]

    if result.black_swan_gate:
        blocks.append(_status("TRADING HALTED - Black Swan CRITICAL", "red"))

    if result.top_trades:
        from market_analyzer.models.opportunity import get_structure_profile, RiskProfile

        rows = []
        for e in result.top_trades[:10]:
            legs_str = ""
            exit_str = ""
            graph = ""
            risk = ""
            if e.trade_spec is not None:
                legs_str = " | ".join(e.trade_spec.leg_codes[:2])
                if len(e.trade_spec.leg_codes) > 2:
                    legs_str += " ..."
                exit_str = e.trade_spec.exit_summary or ""
                if e.trade_spec.structure_type:
                    p = get_structure_profile(
                        e.trade_spec.structure_type,
                        e.trade_spec.order_side,
                        e.direction,
                    )
                    graph = p.payoff_graph or ""
                    risk = (p.risk_profile.value.upper()
                            if p.risk_profile == RiskProfile.UNDEFINED
                            else p.risk_profile.value)

            rows.append([
                str(e.rank), e.ticker, str(e.strategy_type),
                graph or "-", e.direction, risk or "-",
                str(e.verdict), f"{e.composite_score:.2f}",
                legs_str or "-", exit_str or "-",
            ])

        blocks.append(_table(
            ["#", "Ticker", "Strategy", "Payoff", "Bias", "Risk",
             "Verdict", "Score", "Legs", "Exit"],
            rows,
        ))

    blocks.append(_text(result.summary, "dim"))
    return blocks


def _handle_vol(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """Volatility surface for a single ticker."""
    if not args:
        return [_error("Usage: vol TICKER")]

    ticker = args[0].upper()
    surf = ma.vol_surface.surface(ticker)

    blocks: list[dict] = [
        _header(f"{ticker} - Volatility Surface ({surf.as_of_date})"),
        _kv([
            _kv_item("Underlying", f"${surf.underlying_price:.2f}"),
            _kv_item("Front IV", f"{surf.front_iv:.1%}"),
            _kv_item("Back IV", f"{surf.back_iv:.1%}"),
            _kv_item("Term Slope", f"{surf.term_slope:+.1%} ({'contango' if surf.is_contango else 'backwardation'})"),
            _kv_item("Calendar Edge", f"{surf.calendar_edge_score:.2f}"),
            _kv_item("Data Quality", surf.data_quality),
        ]),
    ]

    if surf.term_structure:
        rows = [
            [str(pt.expiration), str(pt.days_to_expiry), f"{pt.atm_iv:.1%}", f"${pt.atm_strike:.0f}"]
            for pt in surf.term_structure
        ]
        blocks.append(_section("Term Structure"))
        blocks.append(_table(["Expiry", "DTE", "ATM IV", "Strike"], rows))

    if surf.skew_by_expiry:
        sk = surf.skew_by_expiry[0]
        blocks.append(_section("Skew (front expiry)"))
        blocks.append(_kv([
            _kv_item("ATM IV", f"{sk.atm_iv:.1%}"),
            _kv_item("OTM Put IV", f"{sk.otm_put_iv:.1%} (skew: +{sk.put_skew:.1%})"),
            _kv_item("OTM Call IV", f"{sk.otm_call_iv:.1%} (skew: +{sk.call_skew:.1%})"),
            _kv_item("Skew Ratio", f"{sk.skew_ratio:.1f}"),
        ]))

    if surf.best_calendar_expiries:
        f, b = surf.best_calendar_expiries
        blocks.append(_kv_item("Best Calendar", f"sell {f} / buy {b} (diff: {surf.iv_differential_pct:+.1f}%)"))

    blocks.append(_text(surf.summary, "dim"))
    return blocks


def _handle_setup(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """Assess price-based setups (breakout, momentum, mean_reversion, orb)."""
    if not args:
        return [_error("Usage: setup TICKER [type]\n  Types: breakout, momentum, mr, orb, all (default)")]

    ticker = args[0].upper()
    setup_type = args[1].lower() if len(args) > 1 else "all"

    type_map = {
        "breakout": ["breakout"],
        "momentum": ["momentum"],
        "mr": ["mean_reversion"],
        "mean_reversion": ["mean_reversion"],
        "orb": ["orb"],
        "all": ["breakout", "momentum", "mean_reversion", "orb"],
    }
    setups = type_map.get(setup_type)
    if setups is None:
        return [_error(f"Unknown setup: '{setup_type}'. Use: breakout, momentum, mr, orb, all")]

    blocks: list[dict] = [_header(f"{ticker} - Setup Assessment")]

    for s in setups:
        try:
            if s == "breakout":
                result = ma.opportunity.assess_breakout(ticker)
            elif s == "momentum":
                result = ma.opportunity.assess_momentum(ticker)
            elif s == "mean_reversion":
                result = ma.opportunity.assess_mean_reversion(ticker)
            elif s == "orb":
                from market_analyzer.opportunity.setups.orb import assess_orb as _orb_assess
                regime = ma.regime.detect(ticker)
                technicals = ma.technicals.snapshot(ticker)
                result = _orb_assess(ticker, regime, technicals, orb=None)
            else:
                continue

            v = result.verdict if isinstance(result.verdict, str) else result.verdict.value
            verdict_colors = {"go": "green", "caution": "yellow", "no_go": "red"}
            name = s.replace("_", " ").title()
            conf = result.confidence if hasattr(result, "confidence") else 0

            blocks.append(_section(f"{name}: {v.upper()} ({conf:.0%})"))

            if hasattr(result, "hard_stops") and result.hard_stops:
                for hs in result.hard_stops[:2]:
                    blocks.append(_text(f"STOP: {hs.description}", "red"))

            items = []
            if hasattr(result, "direction") and result.direction != "neutral":
                items.append(_kv_item("Direction", result.direction.title()))
            if hasattr(result, "strategy") and isinstance(result.strategy, str):
                items.append(_kv_item("Strategy", result.strategy.replace("_", " ").title()))

            # ORB-specific
            if hasattr(result, "orb_status") and result.orb_status != "none":
                items.append(_kv_item("ORB Status", result.orb_status))
                items.append(_kv_item("Range", f"{result.range_pct:.2f}%"))
                if result.range_vs_daily_atr_pct is not None:
                    items.append(_kv_item("Range/ATR", f"{result.range_vs_daily_atr_pct:.0f}%"))

            if items:
                blocks.append(_kv(items))

            if hasattr(result, "signals") and result.signals:
                sig_items = [
                    f"[{'+ ' if sig.favorable else '- '}] {sig.description}"
                    for sig in result.signals[:5]
                ]
                blocks.append(_list(sig_items))

            # Trade spec
            if hasattr(result, "trade_spec") and result.trade_spec is not None:
                ts = result.trade_spec
                blocks.append(_text(f"Legs: {' | '.join(ts.leg_codes)}"))
                if ts.exit_summary:
                    blocks.append(_text(f"Exit: {ts.exit_summary}", "dim"))

            blocks.append(_text(result.summary, "dim"))

        except Exception as exc:
            blocks.append(_text(f"{s.replace('_', ' ').title()}: {exc}", "red"))

    return blocks


def _handle_opportunity(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """Assess option play opportunities."""
    if not args:
        return [_error("Usage: opportunity TICKER [play]\n  Plays: ic, ifly, calendar, diagonal, ratio, zero_dte, leap, earnings, all")]

    ticker = args[0].upper()
    play = args[1].lower() if len(args) > 1 else "all"

    play_map = {
        "ic": ["iron_condor"], "iron_condor": ["iron_condor"],
        "ifly": ["iron_butterfly"], "iron_butterfly": ["iron_butterfly"],
        "calendar": ["calendar"], "cal": ["calendar"],
        "diagonal": ["diagonal"], "diag": ["diagonal"],
        "ratio": ["ratio_spread"], "ratio_spread": ["ratio_spread"],
        "zero_dte": ["zero_dte"], "0dte": ["zero_dte"],
        "leap": ["leap"], "earnings": ["earnings"],
        "all": ["iron_condor", "iron_butterfly", "calendar", "diagonal", "ratio_spread", "earnings"],
    }
    plays = play_map.get(play)
    if plays is None:
        return [_error(f"Unknown play: '{play}'. Use: ic, ifly, calendar, diagonal, ratio, zero_dte, leap, earnings, all")]

    blocks: list[dict] = [_header(f"{ticker} - Option Play Assessment")]

    for p in plays:
        try:
            method = getattr(ma.opportunity, f"assess_{p}")
            result = method(ticker)

            v_color = {"go": "green", "caution": "yellow", "no_go": "red"}.get(result.verdict.value, "")
            name = p.replace("_", " ").title()

            blocks.append(_section(f"{name}: {result.verdict.value.upper()} ({result.confidence:.0%})"))

            if result.hard_stops:
                for hs in result.hard_stops[:2]:
                    blocks.append(_text(f"STOP: {hs.description}", "red"))

            if hasattr(result, "strategy") and result.verdict.value != "no_go":
                items = [
                    _kv_item("Strategy", result.strategy.name),
                    _kv_item("Structure", result.strategy.structure[:80]),
                ]
                if result.strategy.risk_notes:
                    items.append(_kv_item("Risk", result.strategy.risk_notes[0]))
                blocks.append(_kv(items))

            # Iron condor wings
            if hasattr(result, "wing_width_suggestion") and result.verdict.value != "no_go":
                blocks.append(_kv_item("Wings", result.wing_width_suggestion))

            # Trade spec
            if hasattr(result, "trade_spec") and result.trade_spec is not None:
                ts = result.trade_spec
                spec_items = []
                if ts.target_expiration:
                    spec_items.append(_kv_item("Expiry", f"{ts.target_expiration} ({ts.target_dte}d)"))
                if ts.front_expiration and ts.back_expiration:
                    spec_items.append(_kv_item("Front", f"{ts.front_expiration} ({ts.front_dte}d, IV {ts.iv_at_front:.1%})"))
                    spec_items.append(_kv_item("Back", f"{ts.back_expiration} ({ts.back_dte}d, IV {ts.iv_at_back:.1%})"))
                if ts.wing_width_points:
                    spec_items.append(_kv_item("Wing Width", f"${ts.wing_width_points:.0f}"))
                if spec_items:
                    blocks.append(_kv(spec_items))

                blocks.append(_text(f"Legs: {' | '.join(ts.leg_codes)}"))
                if ts.max_profit_desc or ts.max_loss_desc:
                    blocks.append(_text(f"Max P: {ts.max_profit_desc or 'N/A'} | Max L: {ts.max_loss_desc or 'N/A'}"))
                if ts.exit_summary:
                    blocks.append(_text(f"Exit: {ts.exit_summary}", "dim"))

            # Ratio spread margin
            if hasattr(result, "margin_warning") and result.margin_warning:
                blocks.append(_text(f"MARGIN: {result.margin_warning}", "yellow"))

        except Exception as exc:
            blocks.append(_text(f"{p.replace('_', ' ').title()}: {exc}", "red"))

    return blocks


def _handle_regime(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    tickers = [a.upper() for a in args] if args else None
    if not tickers:
        from market_analyzer.config import get_settings
        tickers = get_settings().display.default_tickers

    results = ma.regime.detect_batch(tickers=tickers)
    blocks: list[dict] = [_header("Regime Detection")]
    rows = [
        [t, f"R{r.regime}", f"{r.confidence:.0%}", r.trend_direction or "", str(r.as_of_date)]
        for t, r in results.items()
    ]
    blocks.append(_table(["Ticker", "Regime", "Confidence", "Direction", "Date"], rows))
    return blocks


def _handle_technicals(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if not args:
        return [_error("Usage: technicals TICKER")]

    ticker = args[0].upper()
    t = ma.technicals.snapshot(ticker)

    rsi_note = "(OB)" if t.rsi.is_overbought else "(OS)" if t.rsi.is_oversold else ""
    macd_arrow = "\u2191" if t.macd.is_bullish_crossover else "\u2193" if t.macd.is_bearish_crossover else ""

    blocks: list[dict] = [
        _header(f"{ticker} \u2014 Technical Snapshot ({t.as_of_date})"),
        _kv([
            _kv_item("Price", f"${t.current_price:.2f}"),
            _kv_item("RSI", f"{t.rsi.value:.1f} {rsi_note}",
                     "red" if t.rsi.is_overbought else "green" if t.rsi.is_oversold else None),
            _kv_item("ATR", f"${t.atr:.2f} ({t.atr_pct:.2f}%)"),
            _kv_item("MACD", f"{t.macd.histogram:+.4f} {macd_arrow}"),
        ]),
    ]

    # Moving averages
    ma_data = t.moving_averages
    blocks.append(_section("Moving Averages"))
    blocks.append(_kv([
        _kv_item("SMA 20", f"${ma_data.sma_20:.2f} ({ma_data.price_vs_sma_20_pct:+.1f}%)"),
        _kv_item("SMA 50", f"${ma_data.sma_50:.2f} ({ma_data.price_vs_sma_50_pct:+.1f}%)"),
        _kv_item("SMA 200", f"${ma_data.sma_200:.2f} ({ma_data.price_vs_sma_200_pct:+.1f}%)"),
    ]))

    # Bollinger, Stochastic & Phase
    blocks.append(_kv([
        _kv_item("Bollinger BW", f"{t.bollinger.bandwidth:.4f}"),
        _kv_item("Bollinger %B", f"{t.bollinger.percent_b:.2f}"),
        _kv_item("Stochastic K", f"{t.stochastic.k:.0f}"),
        _kv_item("Stochastic D", f"{t.stochastic.d:.0f}"),
        _kv_item("Phase", f"{t.phase.phase.value} ({t.phase.confidence:.0%})"),
    ]))

    # Signals
    if t.signals:
        blocks.append(_section("Signals"))
        sig_items = [f"[{s.direction}] {s.name}: {s.description}" for s in t.signals[:5]]
        blocks.append(_list(sig_items))

    return blocks


def _handle_levels(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    if not args:
        return [_error("Usage: levels TICKER")]

    ticker = args[0].upper()
    result = ma.levels.analyze(ticker)
    return [
        _header(f"{ticker} \u2014 Levels Analysis ({result.as_of_date})"),
        _text(result.summary),
    ]


def _handle_macro(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    cal = ma.macro.calendar()
    blocks: list[dict] = [_header("Macro Calendar")]

    kv_items = []
    if cal.next_event:
        kv_items.append(_kv_item("Next Event", f"{cal.next_event.name} ({cal.next_event.date}) \u2014 {cal.days_to_next}d"))
    if cal.next_fomc:
        kv_items.append(_kv_item("Next FOMC", f"{cal.next_fomc.date} \u2014 {cal.days_to_next_fomc}d", "yellow"))
    if kv_items:
        blocks.append(_kv(kv_items))

    if cal.events_next_30_days:
        blocks.append(_section("Next 30 Days"))
        rows = [[str(e.date), e.name, e.impact] for e in cal.events_next_30_days]
        blocks.append(_table(["Date", "Event", "Impact"], rows))

    return blocks


def _handle_stress(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    alert = ma.black_swan.alert()
    level_color = {
        "normal": "green",
        "elevated": "yellow",
        "high": "yellow",
        "critical": "red",
    }
    color = level_color.get(alert.alert_level, "yellow")

    blocks: list[dict] = [
        _header(f"Tail-Risk Alert ({alert.as_of_date})"),
        _status(alert.alert_level.upper(), color),
        _kv([
            _kv_item("Score", f"{alert.composite_score:.2f}"),
            _kv_item("Action", alert.action),
        ]),
    ]

    if alert.indicators:
        blocks.append(_section("Indicators"))
        rows = [
            [ind.name, ind.status, f"{ind.score:.2f}",
             f"{ind.value:.2f}" if ind.value is not None else "N/A"]
            for ind in alert.indicators
        ]
        blocks.append(_table(["Name", "Status", "Score", "Value"], rows))

    if alert.triggered_breakers > 0:
        blocks.append(_status(f"{alert.triggered_breakers} circuit breaker(s) triggered!", "red"))

    blocks.append(_text(alert.summary, "dim"))
    return blocks


def _handle_help(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    return [
        _header("Market Analyzer \u2014 Available Commands"),
        _table(
            ["Command", "Usage", "Description"],
            [
                ["context", "context", "Market environment assessment"],
                ["analyze", "analyze SPY [QQQ ...]", "Full instrument analysis"],
                ["screen", "screen [SPY GLD ...]", "Screen tickers for setups"],
                ["entry", "entry SPY breakout", "Confirm entry signal"],
                ["strategy", "strategy SPY", "Strategy recommendation + sizing"],
                ["exit_plan", "exit_plan SPY 580", "Exit plan for a position"],
                ["plan", "plan [SPY GLD ...] [--date YYYY-MM-DD]", "Daily trading plan"],
                ["rank", "rank [SPY GLD ...]", "Rank trades across tickers"],
                ["regime", "regime [SPY GLD ...]", "Detect regime for tickers"],
                ["technicals", "technicals SPY", "Technical snapshot"],
                ["vol", "vol SPY", "Volatility surface & term structure"],
                ["setup", "setup SPY [breakout|momentum|mr|orb|all]", "Price-based setup assessment"],
                ["opportunity", "opportunity SPY [ic|ifly|calendar|diagonal|ratio|leap|all]", "Option play assessment"],
                ["levels", "levels SPY", "Support/resistance levels"],
                ["macro", "macro", "Macro economic calendar"],
                ["stress", "stress", "Black swan / tail-risk alert"],
                ["help", "help", "Show this help"],
                ["clear", "clear", "Clear terminal history"],
            ],
        ),
        _text("Arguments in [brackets] are optional. Without tickers, commands use defaults.", "dim"),
    ]


def _handle_clear(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    return [{"type": "clear"}]


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_terminal_router(engine: 'WorkflowEngine') -> APIRouter:
    """Create the terminal API router."""
    router = APIRouter()
    _ma_instance: list[MarketAnalyzer | None] = [None]  # mutable container for nonlocal

    def _get_ma() -> MarketAnalyzer:
        if _ma_instance[0] is None:
            _ma_instance[0] = MarketAnalyzer(data_service=DataService())
        return _ma_instance[0]

    handlers = {
        "context": _handle_context,
        "analyze": _handle_analyze,
        "screen": _handle_screen,
        "entry": _handle_entry,
        "strategy": _handle_strategy,
        "exit_plan": _handle_exit_plan,
        "plan": _handle_plan,
        "rank": _handle_rank,
        "vol": _handle_vol,
        "setup": _handle_setup,
        "opportunity": _handle_opportunity,
        "regime": _handle_regime,
        "technicals": _handle_technicals,
        "levels": _handle_levels,
        "macro": _handle_macro,
        "stress": _handle_stress,
        "help": _handle_help,
        "clear": _handle_clear,
    }

    @router.post("/terminal/execute")
    async def execute_command(body: TerminalRequest) -> TerminalResponse:
        parts = body.command.strip().split()
        if not parts:
            return TerminalResponse(
                blocks=[_error("Empty command")],
                command="",
                success=False,
            )

        cmd = parts[0].lower()
        args = parts[1:]

        handler = handlers.get(cmd)
        if not handler:
            return TerminalResponse(
                blocks=[_error(f"Unknown command: '{cmd}'. Type 'help' for available commands.")],
                command=body.command,
                success=False,
            )

        try:
            # Run in thread pool — MarketAnalyzer calls are synchronous and can
            # take 10-30s.  Without to_thread() this blocks the entire event loop,
            # starving every other request (portfolios, dashboard, etc.).
            blocks = await asyncio.to_thread(handler, args, _get_ma())
            return TerminalResponse(blocks=blocks, command=body.command, success=True)
        except Exception as e:
            logger.error(f"Terminal command '{body.command}' failed: {e}", exc_info=True)
            return TerminalResponse(
                blocks=[_error(f"Error: {e}")],
                command=body.command,
                success=False,
            )

    return router
