"""
CoTrader Terminal API — unified interactive terminal on the web.

Two command sets in one terminal:
  1. Market Analysis (19 commands) — powered by MarketAnalyzer
  2. Trading (9 commands) — positions, portfolios, booking, execution

Single endpoint: POST /terminal/execute  {"command": "analyze SPY"}
"""

from typing import TYPE_CHECKING
import asyncio
import logging
from datetime import date, datetime
from decimal import Decimal

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
# Trade resolution helpers
# ---------------------------------------------------------------------------

def _resolve_trade(trade_id_prefix: str, session) -> 'TradeORM | None':
    """Resolve a trade by partial ID (git-style prefix match)."""
    from trading_cotrader.core.database.schema import TradeORM

    trade = session.query(TradeORM).filter(TradeORM.id == trade_id_prefix).first()
    if trade:
        return trade

    trades = (
        session.query(TradeORM)
        .filter(TradeORM.id.like(f"{trade_id_prefix}%"))
        .all()
    )
    if len(trades) == 1:
        return trades[0]
    return None  # Not found or ambiguous


def _trade_to_tradespec(trade: 'TradeORM'):
    """Convert DB TradeORM + legs to MarketAnalyzer TradeSpec for adjustment analysis."""
    from market_analyzer.models.opportunity import TradeSpec, LegSpec, LegAction

    legs = []
    for leg in trade.legs:
        sym = leg.symbol
        if not sym or sym.asset_type != 'option':
            continue

        side_lower = (leg.side or '').lower()
        action = LegAction.STO if 'sell' in side_lower else LegAction.BTO

        exp_date = sym.expiration.date() if sym.expiration else date.today()
        dte = (exp_date - date.today()).days

        legs.append(LegSpec(
            role=f"{'short' if action == LegAction.STO else 'long'}_{sym.option_type or 'call'}",
            action=action,
            quantity=abs(leg.quantity),
            option_type=sym.option_type or 'call',
            strike=float(sym.strike or 0),
            strike_label=f"${float(sym.strike or 0):.0f} {sym.option_type or '?'}",
            expiration=exp_date,
            days_to_expiry=max(dte, 0),
            atm_iv_at_expiry=float(leg.entry_iv or 0.20),
        ))

    underlying_price = float(
        trade.current_underlying_price or trade.entry_underlying_price or 0
    )

    strategy_type = None
    if trade.strategy:
        strategy_type = trade.strategy.strategy_type

    target_exp = legs[0].expiration if legs else date.today()
    target_dte = legs[0].days_to_expiry if legs else 0

    return TradeSpec(
        ticker=trade.underlying_symbol,
        legs=legs,
        underlying_price=underlying_price,
        target_dte=target_dte,
        target_expiration=target_exp,
        structure_type=strategy_type,
        order_side="credit" if trade.entry_price and float(trade.entry_price) > 0 else "debit",
        spec_rationale="Loaded from DB for adjustment analysis",
    )


# ---------------------------------------------------------------------------
# Market Analysis command handlers — each returns list[dict] blocks
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


def _handle_plan(args: list[str], ma: MarketAnalyzer, *, plan_store: dict | None = None) -> list[dict]:
    """Generate daily trading plan. Optionally stores the plan object in plan_store."""
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

    # Store plan for book command
    if plan_store is not None:
        plan_store['plan'] = plan

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
    blocks.append(_text("Use 'book <#>' to book a trade by rank number.", "dim"))
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
        _header("CoTrader Terminal \u2014 Available Commands"),
        _section("Market Analysis"),
        _table(
            ["Command", "Usage", "Description"],
            [
                ["context", "context", "Market environment assessment"],
                ["analyze", "analyze SPY [QQQ ...]", "Full instrument analysis"],
                ["screen", "screen [SPY GLD ...]", "Screen tickers for setups"],
                ["entry", "entry SPY breakout", "Confirm entry signal"],
                ["strategy", "strategy SPY", "Strategy recommendation + sizing"],
                ["exit_plan", "exit_plan SPY 580", "Exit plan for a position"],
                ["plan", "plan [SPY ...] [--date YYYY-MM-DD]", "Daily trading plan"],
                ["rank", "rank [SPY GLD ...]", "Rank trades across tickers"],
                ["regime", "regime [SPY GLD ...]", "Detect regime for tickers"],
                ["technicals", "technicals SPY", "Technical snapshot"],
                ["vol", "vol SPY", "Volatility surface & term structure"],
                ["setup", "setup SPY [type]", "Price-based setup assessment"],
                ["opportunity", "opportunity SPY [play]", "Option play assessment"],
                ["levels", "levels SPY", "Support/resistance levels"],
                ["macro", "macro", "Macro economic calendar"],
                ["stress", "stress", "Black swan / tail-risk alert"],
            ],
        ),
        _section("Trading"),
        _table(
            ["Command", "Usage", "Description"],
            [
                ["positions", "positions [portfolio]", "Open trades with Greeks"],
                ["portfolios", "portfolios", "All portfolios: capital + Greeks"],
                ["greeks", "greeks", "Portfolio Greeks vs limits"],
                ["capital", "capital", "Capital utilization"],
                ["trades", "trades", "Today's executed trades"],
                ["book", "book <#> [--portfolio ttw]", "Book WhatIf from plan/template"],
                ["execute", "execute <id> [--confirm]", "Execute WhatIf trade"],
                ["orders", "orders", "Pending broker orders"],
                ["morning", "morning", "Run morning trading workflow"],
            ],
        ),
        _section("Trade Management"),
        _table(
            ["Command", "Usage", "Description"],
            [
                ["adjust", "adjust <id>", "Adjustment recommendations for open trade"],
                ["close", "close <id> [--confirm]", "Close a position"],
                ["chain", "chain <ticker> [exp]", "Option chain with broker Greeks"],
                ["iv", "iv <ticker>", "IV rank, percentile, HV, beta"],
                ["pnl", "pnl <id>", "Detailed P&L with Greek attribution"],
                ["status", "status", "Broker connection & system state"],
            ],
        ),
        _text("Workflow: plan SPY \u2192 book 1 \u2192 execute <id> --confirm", "dim"),
        _text("Monitor: positions \u2192 pnl <id> \u2192 adjust <id> \u2192 close <id>", "dim"),
        _text("help, clear", "dim"),
    ]


def _handle_clear(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    return [{"type": "clear"}]


# ---------------------------------------------------------------------------
# Trading command handlers — each returns list[dict] blocks
# ---------------------------------------------------------------------------

def _handle_t_positions(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Open trades grouped by portfolio."""
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.core.database.schema import TradeORM

    portfolio_filter = args[0].lower() if args else None

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
            return [_text("No positions. Book one with: plan SPY \u2192 book <#>")]

        # Group by portfolio
        by_portfolio: dict[str, list] = {}
        for t in trades:
            pname = t.portfolio.name if t.portfolio else '\u2014'
            if portfolio_filter and portfolio_filter not in pname.lower():
                continue
            by_portfolio.setdefault(pname, []).append(t)

        if not by_portfolio:
            return [_text(f"No positions matching '{portfolio_filter}'.")]

        blocks: list[dict] = [_header("Positions by Portfolio")]

        total_count = 0
        whatif_count = 0

        for pname in sorted(by_portfolio.keys()):
            ptrades = by_portfolio[pname]
            blocks.append(_section(f"{pname} ({len(ptrades)} trades)"))

            rows = []
            for t in ptrades:
                strategy_name = '\u2014'
                if t.strategy_id and t.strategy:
                    strategy_name = t.strategy.strategy_type or '\u2014'

                status = t.trade_status or '\u2014'
                if status == 'intent' and t.trade_type == 'what_if':
                    status = 'WHATIF'
                    whatif_count += 1
                elif status == 'executed':
                    status = 'OPEN'
                elif status == 'pending':
                    status = 'PENDING'

                rows.append([
                    t.id[:8],
                    t.underlying_symbol,
                    strategy_name[:18],
                    status,
                    _safe(t.entry_price, ".2f", "\u2014"),
                    _safe(t.total_pnl, ".0f", "\u2014"),
                    _safe(t.current_delta, "+.1f", "0"),
                    _safe(t.current_theta, "+.1f", "0"),
                ])
                total_count += 1

            blocks.append(_table(
                ["ID", "Underlying", "Strategy", "Status", "Entry", "P&L", "Delta", "Theta"],
                rows,
            ))

        blocks.append(_text(f"Total: {total_count}  (WhatIf: {whatif_count})", "dim"))
        if whatif_count:
            blocks.append(_text("Execute WhatIf: execute <id> [--confirm]", "dim"))

        return blocks


def _handle_t_portfolios(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """All portfolios: capital, Greeks, P&L."""
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
            return [_text("No portfolios found.")]

        rows = []
        for p in portfolios:
            equity = float(p.total_equity or 0)
            cash = float(p.cash_balance or 0)
            deployed_pct = ((equity - cash) / equity * 100) if equity else 0

            rows.append([
                p.name[:22],
                (p.broker or '\u2014')[:12],
                (p.portfolio_type or '\u2014')[:8],
                f"${equity:,.0f}",
                f"${cash:,.0f}",
                f"{deployed_pct:.0f}%",
                _safe(p.portfolio_delta, "+.1f", "0"),
                _safe(p.portfolio_theta, "+.1f", "0"),
                _safe(p.total_pnl, "+.0f", "0"),
            ])

        return [
            _header("Portfolios"),
            _table(
                ["Name", "Broker", "Type", "Equity", "Cash", "Deployed", "Delta", "Theta", "P&L"],
                rows,
            ),
        ]


def _handle_t_greeks(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Portfolio Greeks vs limits with visual utilization."""
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
            return [_text("No portfolios found.")]

        blocks: list[dict] = [_header("Portfolio Greeks vs Limits")]

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

            def _greek_color(pct: float) -> str:
                if pct > 80:
                    return "red"
                if pct > 50:
                    return "yellow"
                return "green"

            blocks.append(_section(p.name))
            blocks.append(_kv([
                _kv_item("Delta", f"{delta:+.1f} / {max_d:.0f} ({d_pct:.0f}%)", _greek_color(d_pct)),
                _kv_item("Gamma", f"{gamma:+.3f} / {max_g:.1f} ({g_pct:.0f}%)", _greek_color(g_pct)),
                _kv_item("Theta", f"{theta:+.1f} / {min_t:.0f} ({t_pct:.0f}%)", _greek_color(t_pct)),
                _kv_item("Vega", f"{vega:+.1f} / {max_v:.0f} ({v_pct:.0f}%)", _greek_color(v_pct)),
            ]))

        return blocks


def _handle_t_capital(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Capital utilization per portfolio."""
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.core.database.schema import PortfolioORM

    with session_scope() as session:
        portfolios = (
            session.query(PortfolioORM)
            .filter(PortfolioORM.portfolio_type.in_(['real', 'paper']))
            .order_by(PortfolioORM.name)
            .all()
        )
        if not portfolios:
            return [_text("No portfolios found.")]

        rows = []
        for p in portfolios:
            initial = float(p.initial_capital or 0)
            equity = float(p.total_equity or 0)
            cash = float(p.cash_balance or 0)
            deployed_pct = ((equity - cash) / equity * 100) if equity else 0
            idle = cash

            rows.append([
                p.name[:22],
                f"${initial:,.0f}",
                f"${equity:,.0f}",
                f"${cash:,.0f}",
                f"{deployed_pct:.0f}%",
                f"${idle:,.0f}",
            ])

        return [
            _header("Capital Utilization"),
            _table(
                ["Portfolio", "Initial", "Equity", "Cash", "Deployed", "Idle"],
                rows,
            ),
        ]


def _handle_t_trades(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Today's executed trades."""
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
            return [_text("No trades today.")]

        rows = []
        for t in trades:
            strategy_name = '\u2014'
            if t.strategy:
                strategy_name = t.strategy.strategy_type or '\u2014'

            time_str = t.created_at.strftime('%H:%M') if t.created_at else '\u2014'

            rows.append([
                t.id[:8],
                t.underlying_symbol,
                strategy_name[:18],
                t.trade_status or '\u2014',
                t.trade_source or 'manual',
                _safe(t.entry_price, ".2f", "\u2014"),
                _safe(t.total_pnl, ".0f", "\u2014"),
                time_str,
            ])

        return [
            _header(f"Today's Trades ({len(trades)})"),
            _table(
                ["ID", "Underlying", "Strategy", "Status", "Source", "Entry", "P&L", "Time"],
                rows,
            ),
        ]


def _handle_t_book(args: list[str], engine: 'WorkflowEngine', ma: MarketAnalyzer) -> list[dict]:
    """Book a WhatIf trade from plan output or template."""
    if not args:
        return [_error("Usage: book <#> [--portfolio <alias>]\n  # = trade rank from 'plan', or template index from 'templates'")]

    target = args[0]

    # Parse --portfolio flag
    portfolio_name = None
    for i, a in enumerate(args[1:], 1):
        if a == '--portfolio' and i + 1 < len(args):
            portfolio_name = args[i + 1]
            break

    # Try to interpret as plan trade index
    try:
        trade_idx = int(target)
    except ValueError:
        trade_idx = None

    last_plan = engine.context.get('last_plan')

    # If integer and we have a stored plan, try plan-based booking
    if trade_idx is not None and last_plan is not None:
        all_trades = last_plan.all_trades
        # Match by rank number
        trade = None
        for t in all_trades:
            if t.rank == trade_idx:
                trade = t
                break

        if trade is not None:
            return _book_from_plan(trade, engine, portfolio_name)

    # Fall back to template-based booking via InteractionManager
    from trading_cotrader.agents.messages import UserIntent

    params: dict = {}
    if portfolio_name:
        params['portfolio'] = portfolio_name

    intent = UserIntent(action='book', target=target, parameters=params)
    response = engine.interaction._book(intent)
    return [_text(response.message)]


def _book_from_plan(trade, engine: 'WorkflowEngine', portfolio_name: str | None) -> list[dict]:
    """Book a specific trade from the daily plan through the risk gate."""
    from trading_cotrader.agents.workflow.the_trader import (
        check_structure, check_defined_risk, check_position_risk,
        check_portfolio_risk, size_position, tradespec_to_legs,
        _get_current_positions, PORTFOLIO_NAME,
    )
    from trading_cotrader.config.risk_config_loader import RiskConfigLoader
    from trading_cotrader.services.trade_booking_service import TradeBookingService
    from trading_cotrader.agents.workflow.interaction import resolve_portfolio_name
    import trading_cotrader.core.models.domain as dm

    target_portfolio = resolve_portfolio_name(portfolio_name) if portfolio_name else PORTFOLIO_NAME

    # Load risk config
    loader = RiskConfigLoader()
    config = loader.load()
    portfolio_cfg = config.portfolios.get_by_name(target_portfolio)
    if not portfolio_cfg:
        return [_error(f"Portfolio '{target_portfolio}' not found in risk_config.yaml")]

    risk_limits = portfolio_cfg.risk_limits
    capital = portfolio_cfg.initial_capital

    spec = trade.trade_spec
    ticker = trade.ticker
    strategy = trade.strategy_type

    blocks: list[dict] = [_header(f"Booking: #{trade.rank} {ticker} {strategy}")]
    blocks.append(_kv([
        _kv_item("Score", f"{trade.composite_score:.2f}"),
        _kv_item("Verdict", str(trade.verdict).upper()),
        _kv_item("Portfolio", target_portfolio),
    ]))

    # Risk gate checks
    checks = [
        ("Structure", check_structure(spec, strategy)),
        ("Defined Risk", check_defined_risk(strategy, spec.legs if spec else [], risk_limits)),
        ("Position Risk", check_position_risk(spec, capital, risk_limits)),
    ]

    current_positions = _get_current_positions(target_portfolio)
    checks.append(("Portfolio Risk", check_portfolio_risk(
        ticker, strategy, risk_limits, current_positions,
    )))

    # Show risk gate results
    blocks.append(_section("Risk Gate"))
    gate_items = []
    all_pass = True
    for name, (ok, msg) in checks:
        color = "green" if ok else "red"
        gate_items.append(_kv_item(name, f"{'PASS' if ok else 'REJECT'}: {msg}", color))
        if not ok:
            all_pass = False
    blocks.append(_kv(gate_items))

    if not all_pass:
        blocks.append(_status("REJECTED \u2014 trade did not pass risk gate", "red"))
        return blocks

    # Position sizing
    contracts, size_msg = size_position(spec, capital, 1.0, risk_limits)
    blocks.append(_kv([_kv_item("Sizing", size_msg, "green" if contracts > 0 else "red")]))

    if contracts <= 0:
        blocks.append(_status("REJECTED \u2014 position too expensive", "red"))
        return blocks

    # Convert legs and book
    leg_inputs = tradespec_to_legs(ticker, spec, contracts)

    svc = TradeBookingService()
    result = svc.book_whatif_trade(
        underlying=ticker,
        strategy_type=strategy,
        legs=leg_inputs,
        portfolio_name=target_portfolio,
        trade_source=dm.TradeSource.TRADER_SCRIPT,
        rationale=trade.rationale,
        notes=f"Score: {trade.composite_score:.2f}, Verdict: {trade.verdict}",
    )

    if not result.success:
        blocks.append(_status(f"BOOKING FAILED: {result.error}", "red"))
        return blocks

    blocks.append(_status("BOOKED", "green"))
    kv_items = [
        _kv_item("Trade ID", result.trade_id[:12]),
        _kv_item("Entry", f"${float(result.entry_price):.2f}"),
    ]
    if result.total_greeks:
        g = result.total_greeks
        kv_items.append(_kv_item("Greeks",
            f"delta={g.get('delta', 0):+.2f} theta={g.get('theta', 0):+.2f} "
            f"vega={g.get('vega', 0):+.2f}"))
    blocks.append(_kv(kv_items))
    blocks.append(_text("View with: positions | Execute with: execute <id>", "dim"))

    return blocks


def _handle_t_execute(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Preview or place a WhatIf trade as a live order."""
    if not args:
        return [_error("Usage: execute <trade_id> [--confirm]")]

    from trading_cotrader.agents.messages import UserIntent

    trade_id = args[0]
    params: dict = {}
    if '--confirm' in args:
        params['confirm'] = True

    intent = UserIntent(action='execute', target=trade_id, parameters=params)
    response = engine.interaction._execute(intent)
    return [_text(response.message)]


def _handle_t_orders(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Pending/recent broker orders."""
    from trading_cotrader.agents.messages import UserIntent

    intent = UserIntent(action='orders')
    response = engine.interaction._orders(intent)
    return [_text(response.message)]


def _handle_t_morning(args: list[str], engine: 'WorkflowEngine', ma: MarketAnalyzer) -> list[dict]:
    """Run the morning trading workflow: plan -> risk gate -> book."""
    from trading_cotrader.agents.workflow.the_trader import (
        check_structure, check_defined_risk, check_position_risk,
        check_portfolio_risk, size_position, tradespec_to_legs,
        _get_current_positions, PORTFOLIO_NAME,
    )
    from trading_cotrader.config.risk_config_loader import RiskConfigLoader
    from trading_cotrader.services.trade_booking_service import TradeBookingService
    import trading_cotrader.core.models.domain as dm

    blocks: list[dict] = [_header("Morning Trading Workflow")]

    # Load risk config
    loader = RiskConfigLoader()
    config = loader.load()
    portfolio_cfg = config.portfolios.get_by_name(PORTFOLIO_NAME)
    if not portfolio_cfg:
        return [_error(f"Portfolio '{PORTFOLIO_NAME}' not found")]

    risk_limits = portfolio_cfg.risk_limits
    capital = portfolio_cfg.initial_capital

    # Step 1: Generate plan
    blocks.append(_section("Step 1: Daily Plan"))
    plan = ma.plan.generate()
    engine.context['last_plan'] = plan

    verdict_str = plan.day_verdict.value.upper().replace("_", " ")
    blocks.append(_kv([
        _kv_item("Date", str(plan.plan_for_date)),
        _kv_item("Verdict", verdict_str,
                 "green" if "TRADE" in verdict_str else "red"),
        _kv_item("Trades Found", str(plan.total_trades)),
        _kv_item("Risk Budget", f"{plan.risk_budget.position_size_factor:.0%} sizing"),
    ]))

    if plan.day_verdict.value in ("no_trade", "avoid"):
        blocks.append(_status("NO TRADING TODAY", "red"))
        blocks.append(_text(plan.summary, "dim"))
        return blocks

    # Step 2: Filter GO/CAUTION candidates
    candidates = [t for t in plan.all_trades
                  if str(t.verdict).lower() in ("go", "caution")]
    blocks.append(_section(f"Step 2: Candidates ({len(candidates)} GO/CAUTION)"))

    if not candidates:
        blocks.append(_text("No GO/CAUTION trades. Sit on hands today.", "dim"))
        return blocks

    for t in candidates:
        v = str(t.verdict).upper()
        blocks.append(_text(
            f"  #{t.rank} {t.ticker} {t.strategy_type} {v} score={t.composite_score:.2f}"
        ))

    # Step 3: Risk gate
    blocks.append(_section("Step 3: Risk Gate"))
    current_positions = _get_current_positions(PORTFOLIO_NAME)
    blocks.append(_text(f"Current positions: {len(current_positions)}", "dim"))

    passing_trades = []
    for t in candidates:
        spec = t.trade_spec
        ticker = t.ticker
        strategy = t.strategy_type

        checks = [
            check_structure(spec, strategy),
            check_defined_risk(strategy, spec.legs if spec else [], risk_limits),
            check_position_risk(spec, capital, risk_limits),
            check_portfolio_risk(ticker, strategy, risk_limits, current_positions),
        ]

        all_pass = all(ok for ok, _ in checks)
        if not all_pass:
            failed = [msg for ok, msg in checks if not ok]
            blocks.append(_kv([_kv_item(f"{ticker} {strategy}", f"REJECT: {failed[0]}", "red")]))
            continue

        contracts, size_msg = size_position(
            spec, capital, plan.risk_budget.position_size_factor, risk_limits,
        )
        if contracts <= 0:
            blocks.append(_kv([_kv_item(f"{ticker} {strategy}", f"REJECT: {size_msg}", "red")]))
            continue

        blocks.append(_kv([_kv_item(f"{ticker} {strategy}", f"PASS \u2014 {contracts} contracts", "green")]))
        passing_trades.append((t, contracts))

    if not passing_trades:
        blocks.append(_status("All trades rejected by risk gate", "red"))
        return blocks

    # Step 4-5: Book
    blocks.append(_section(f"Step 4-5: Booking ({len(passing_trades)} trades)"))
    svc = TradeBookingService()
    booked = 0

    for t, contracts in passing_trades:
        spec = t.trade_spec
        ticker = t.ticker
        strategy = t.strategy_type

        leg_inputs = tradespec_to_legs(ticker, spec, contracts)
        result = svc.book_whatif_trade(
            underlying=ticker,
            strategy_type=strategy,
            legs=leg_inputs,
            portfolio_name=PORTFOLIO_NAME,
            trade_source=dm.TradeSource.TRADER_SCRIPT,
            rationale=t.rationale,
            notes=f"Score: {t.composite_score:.2f}, Verdict: {t.verdict}",
        )

        if result.success:
            booked += 1
            blocks.append(_kv([_kv_item(f"{ticker} {strategy}",
                f"BOOKED \u2014 {result.trade_id[:8]} @ ${float(result.entry_price):.2f}", "green")]))
        else:
            blocks.append(_kv([_kv_item(f"{ticker} {strategy}", f"FAILED: {result.error}", "red")]))

    # Summary
    blocks.append(_section("Summary"))
    blocks.append(_kv([
        _kv_item("Candidates", str(len(candidates))),
        _kv_item("Passed Gate", str(len(passing_trades))),
        _kv_item("Booked", str(booked), "green" if booked > 0 else "red"),
        _kv_item("Rejected", str(len(candidates) - len(passing_trades))),
    ]))
    blocks.append(_text(plan.summary, "dim"))
    blocks.append(_text("View with: positions | Execute with: execute <id>", "dim"))

    return blocks


# ---------------------------------------------------------------------------
# Trade Management command handlers
# ---------------------------------------------------------------------------

def _handle_t_adjust(args: list[str], engine: 'WorkflowEngine', ma: MarketAnalyzer) -> list[dict]:
    """Adjustment recommendations for an open trade."""
    if not args:
        return [_error("Usage: adjust <trade_id>")]

    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        trade = _resolve_trade(args[0], session)
        if not trade:
            return [_error(f"Trade '{args[0]}' not found (or ambiguous prefix).")]

        if not trade.is_open:
            return [_error(f"Trade {trade.id[:8]} is closed.")]

        ticker = trade.underlying_symbol

        try:
            trade_spec = _trade_to_tradespec(trade)
        except Exception as e:
            return [_error(f"Cannot convert trade to spec: {e}")]

        if not trade_spec.legs:
            return [_error(f"Trade {trade.id[:8]} has no option legs to analyze.")]

        regime = ma.regime.detect(ticker)
        technicals = ma.technicals.snapshot(ticker)
        analysis = ma.adjustment.analyze(trade_spec, regime, technicals)

        strategy_name = trade.strategy.strategy_type if trade.strategy else 'unknown'
        status_colors = {
            'SAFE': 'green', 'TESTED': 'yellow', 'BREACHED': 'red', 'MAX_LOSS': 'red',
        }
        status_str = analysis.position_status.value if hasattr(analysis.position_status, 'value') else str(analysis.position_status)

        blocks: list[dict] = [
            _header(f"Adjustment Analysis \u2014 {ticker} {strategy_name}"),
            _status(status_str.upper(), status_colors.get(status_str.upper(), 'yellow')),
        ]

        kv_items = [
            _kv_item("Current Price", f"${analysis.current_price:.2f}"),
            _kv_item("Entry Price", _safe(trade.entry_price, ".2f", "N/A")),
            _kv_item("P&L Est",
                     f"${analysis.pnl_estimate:.0f}" if analysis.pnl_estimate is not None else "N/A",
                     "green" if (analysis.pnl_estimate or 0) > 0
                     else "red" if (analysis.pnl_estimate or 0) < 0 else None),
            _kv_item("DTE", str(analysis.remaining_dte)),
            _kv_item("Regime", f"R{analysis.regime_id}"),
        ]
        if analysis.distance_to_short_put_pct is not None:
            kv_items.append(_kv_item("Dist Short Put", f"{analysis.distance_to_short_put_pct:+.1f}%"))
        if analysis.distance_to_short_call_pct is not None:
            kv_items.append(_kv_item("Dist Short Call", f"{analysis.distance_to_short_call_pct:+.1f}%"))
        blocks.append(_kv(kv_items))

        if analysis.adjustments:
            blocks.append(_section("Recommended Adjustments"))
            rows = []
            for adj in analysis.adjustments:
                adj_type = adj.adjustment_type.value if hasattr(adj.adjustment_type, 'value') else str(adj.adjustment_type)
                cost_str = f"${adj.estimated_cost:.0f}" if adj.estimated_cost is not None else "N/A"
                rows.append([
                    adj_type.replace('_', ' ').title(),
                    adj.description[:50],
                    cost_str,
                    f"{adj.risk_change:+.0f}",
                    adj.urgency,
                ])
            blocks.append(_table(["Type", "Description", "Cost", "Risk \u0394", "Urgency"], rows))
        else:
            blocks.append(_text("No adjustments needed.", "dim"))

        blocks.append(_text(analysis.recommendation, "dim"))
        return blocks


def _handle_t_close(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Close a position — preview or confirm."""
    if not args:
        return [_error("Usage: close <trade_id> [--confirm]")]

    from trading_cotrader.core.database.session import session_scope

    trade_id = args[0]
    confirm = '--confirm' in args

    with session_scope() as session:
        trade = _resolve_trade(trade_id, session)
        if not trade:
            return [_error(f"Trade '{trade_id}' not found (or ambiguous prefix).")]

        if not trade.is_open:
            return [_error(f"Trade {trade.id[:8]} is already closed.")]

        strategy_name = trade.strategy.strategy_type if trade.strategy else 'unknown'

        if not confirm:
            # Preview
            blocks: list[dict] = [
                _header(f"Close Preview \u2014 {trade.underlying_symbol} {strategy_name}"),
                _kv([
                    _kv_item("Trade ID", trade.id[:12]),
                    _kv_item("Status", trade.trade_status or 'open'),
                    _kv_item("Type", trade.trade_type or 'real'),
                    _kv_item("Entry Price", _safe(trade.entry_price, ".2f", "N/A")),
                    _kv_item("Current P&L", _safe(trade.total_pnl, ".0f", "N/A"),
                             "green" if trade.total_pnl and float(trade.total_pnl) > 0
                             else "red" if trade.total_pnl and float(trade.total_pnl) < 0 else None),
                ]),
            ]

            if trade.legs:
                rows = []
                for leg in trade.legs:
                    sym = leg.symbol
                    desc = sym.ticker if sym else "?"
                    if sym and sym.option_type:
                        desc = f"{sym.ticker} {sym.option_type.upper()} ${float(sym.strike or 0):.0f}"
                        if sym.expiration:
                            desc += f" {sym.expiration.strftime('%m/%d')}"
                    rows.append([
                        leg.side or '?',
                        str(leg.quantity),
                        desc,
                        _safe(leg.entry_price, ".2f", "N/A"),
                        _safe(leg.current_price, ".2f", "N/A"),
                    ])
                blocks.append(_table(["Side", "Qty", "Description", "Entry", "Current"], rows))

            if trade.trade_type == 'what_if' or trade.trade_status == 'intent':
                blocks.append(_text("WhatIf trade \u2014 will be marked closed in DB.", "dim"))
            elif trade.broker_trade_id:
                blocks.append(_text("Live trade \u2014 will be marked closed in DB. Place closing order via broker manually.", "dim"))
            else:
                blocks.append(_text("No broker ID \u2014 will be marked closed in DB.", "dim"))

            blocks.append(_text("Run: close <id> --confirm  to execute.", "dim"))
            return blocks

        # Confirm — close in DB
        trade.trade_status = 'closed'
        trade.is_open = False
        trade.closed_at = datetime.utcnow()
        trade.exit_reason = 'manual_close'
        session.commit()

        blocks = [
            _header(f"Closed \u2014 {trade.underlying_symbol} {strategy_name}"),
            _status("CLOSED", "green"),
            _kv([
                _kv_item("Trade ID", trade.id[:12]),
                _kv_item("P&L", _safe(trade.total_pnl, ".0f", "N/A")),
                _kv_item("Exit Reason", "manual_close"),
            ]),
        ]
        if trade.broker_trade_id:
            blocks.append(_text(
                f"Note: Broker trade {trade.broker_trade_id} \u2014 place closing order via broker manually.",
                "dim",
            ))
        return blocks


def _handle_t_chain(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """Option chain with broker Greeks."""
    if not args:
        return [_error("Usage: chain <ticker> [expiration YYYY-MM-DD]")]

    ticker = args[0].upper()
    exp = None
    if len(args) > 1:
        try:
            exp = date.fromisoformat(args[1])
        except ValueError:
            return [_error(f"Invalid expiration date: {args[1]}. Use YYYY-MM-DD format.")]

    try:
        snapshot = ma.quotes.get_chain(ticker, expiration=exp)
    except Exception as e:
        return [_error(f"Failed to get chain for {ticker}: {e}")]

    if not snapshot.quotes:
        return [_text(f"No option chain data for {ticker}.")]

    blocks: list[dict] = [
        _header(f"{ticker} \u2014 Option Chain ({snapshot.source})"),
        _kv([_kv_item("Underlying", f"${snapshot.underlying_price:.2f}")]),
    ]

    from collections import defaultdict
    by_exp: dict[date, dict[str, list]] = defaultdict(lambda: {"call": [], "put": []})
    for q in snapshot.quotes:
        by_exp[q.expiration][q.option_type].append(q)

    for exp_date in sorted(by_exp.keys()):
        blocks.append(_section(f"Exp: {exp_date}"))

        for otype in ("call", "put"):
            quotes = sorted(by_exp[exp_date][otype], key=lambda q: q.strike)
            if not quotes:
                continue

            blocks.append(_text(f"  {otype.upper()}S", "dim"))
            rows = []
            for q in quotes:
                rows.append([
                    f"${q.strike:.0f}",
                    f"{q.bid:.2f}",
                    f"{q.ask:.2f}",
                    f"{q.mid:.2f}",
                    f"{q.implied_volatility:.1%}" if q.implied_volatility else "N/A",
                    f"{q.delta:+.3f}" if q.delta is not None else "N/A",
                    f"{q.gamma:.4f}" if q.gamma is not None else "N/A",
                    f"{q.theta:.3f}" if q.theta is not None else "N/A",
                    f"{q.vega:.3f}" if q.vega is not None else "N/A",
                    str(q.open_interest),
                ])
            blocks.append(_table(
                ["Strike", "Bid", "Ask", "Mid", "IV", "Delta", "Gamma", "Theta", "Vega", "OI"],
                rows,
            ))

    return blocks


def _handle_t_iv(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    """IV rank, percentile, HV, beta for a ticker."""
    if not args:
        return [_error("Usage: iv <ticker>")]

    ticker = args[0].upper()
    metrics = ma.quotes.get_metrics(ticker)

    if metrics is None:
        return [_text(f"No IV metrics available for {ticker}. Broker may not be connected.")]

    def _iv_color(val: float | None) -> str | None:
        if val is None:
            return None
        return "green" if val > 50 else "red" if val < 20 else None

    kv_items = [
        _kv_item("IV Rank",
                 f"{metrics.iv_rank:.0f}" if metrics.iv_rank is not None else "N/A",
                 _iv_color(metrics.iv_rank)),
        _kv_item("IV Percentile",
                 f"{metrics.iv_percentile:.0f}" if metrics.iv_percentile is not None else "N/A",
                 _iv_color(metrics.iv_percentile)),
        _kv_item("IV 30d", f"{metrics.iv_30_day:.1%}" if metrics.iv_30_day is not None else "N/A"),
        _kv_item("HV 30d", f"{metrics.hv_30_day:.1%}" if metrics.hv_30_day is not None else "N/A"),
        _kv_item("HV 60d", f"{metrics.hv_60_day:.1%}" if metrics.hv_60_day is not None else "N/A"),
        _kv_item("Beta", f"{metrics.beta:.2f}" if metrics.beta is not None else "N/A"),
        _kv_item("Corr SPY", f"{metrics.corr_spy:.2f}" if metrics.corr_spy is not None else "N/A"),
        _kv_item("Earnings", str(metrics.earnings_date) if metrics.earnings_date else "N/A"),
    ]

    blocks: list[dict] = [
        _header(f"{ticker} \u2014 IV Metrics ({ma.quotes.source})"),
        _kv(kv_items),
    ]

    if metrics.iv_30_day is not None and metrics.hv_30_day is not None:
        spread = metrics.iv_30_day - metrics.hv_30_day
        label = "overpriced" if spread > 0 else "underpriced"
        blocks.append(_text(f"IV-HV spread: {spread:+.1%} ({label})", "dim"))

    return blocks


def _handle_t_pnl(args: list[str], engine: 'WorkflowEngine') -> list[dict]:
    """Detailed P&L breakdown with Greek attribution."""
    if not args:
        return [_error("Usage: pnl <trade_id>")]

    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        trade = _resolve_trade(args[0], session)
        if not trade:
            return [_error(f"Trade '{args[0]}' not found (or ambiguous prefix).")]

        strategy_name = trade.strategy.strategy_type if trade.strategy else 'unknown'
        status = 'OPEN' if trade.is_open else 'CLOSED'

        opened = trade.opened_at or trade.created_at
        duration_days = (datetime.utcnow() - opened).days if opened else 0

        total_pnl = float(trade.total_pnl or 0)
        pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else None

        blocks: list[dict] = [
            _header(f"P&L \u2014 {trade.underlying_symbol} {strategy_name}"),
            _status(status, "green" if trade.is_open else "gray"),
            _kv([
                _kv_item("Trade ID", trade.id[:12]),
                _kv_item("Duration", f"{duration_days} days"),
                _kv_item("Total P&L", f"${total_pnl:+,.0f}", pnl_color),
            ]),
        ]

        # Entry vs Current
        blocks.append(_section("Entry vs Current"))
        blocks.append(_kv([
            _kv_item("Entry Price", _safe(trade.entry_price, ".2f", "N/A")),
            _kv_item("Current Price", _safe(trade.current_price, ".2f", "N/A")),
            _kv_item("Underlying Entry", _safe(trade.entry_underlying_price, ".2f", "N/A")),
            _kv_item("Underlying Now", _safe(trade.current_underlying_price, ".2f", "N/A")),
        ]))

        # P&L Attribution
        delta_pnl = float(trade.delta_pnl or 0)
        gamma_pnl = float(trade.gamma_pnl or 0)
        theta_pnl = float(trade.theta_pnl or 0)
        vega_pnl = float(trade.vega_pnl or 0)
        unexplained = float(trade.unexplained_pnl or 0)

        def _pct(part: float) -> str:
            return f"{part / total_pnl * 100:.0f}%" if total_pnl else "\u2014"

        blocks.append(_section("P&L Attribution"))
        blocks.append(_table(
            ["Component", "P&L", "% of Total"],
            [
                ["Delta", f"${delta_pnl:+,.0f}", _pct(delta_pnl)],
                ["Gamma", f"${gamma_pnl:+,.0f}", _pct(gamma_pnl)],
                ["Theta", f"${theta_pnl:+,.0f}", _pct(theta_pnl)],
                ["Vega", f"${vega_pnl:+,.0f}", _pct(vega_pnl)],
                ["Unexplained", f"${unexplained:+,.0f}", _pct(unexplained)],
                ["TOTAL", f"${total_pnl:+,.0f}", "100%"],
            ],
        ))

        # Per-leg breakdown
        if trade.legs:
            blocks.append(_section("Leg Breakdown"))
            rows = []
            for leg in trade.legs:
                sym = leg.symbol
                desc = sym.ticker if sym else "?"
                if sym and sym.option_type:
                    desc = f"{sym.option_type.upper()[0]} ${float(sym.strike or 0):.0f}"
                    if sym.expiration:
                        desc += f" {sym.expiration.strftime('%m/%d')}"

                leg_pnl = 0.0
                if leg.entry_price is not None and leg.current_price is not None:
                    mult = sym.multiplier or 100 if sym else 100
                    leg_pnl = (float(leg.current_price) - float(leg.entry_price)) * leg.quantity * mult

                rows.append([
                    f"{leg.side} {leg.quantity}x",
                    desc,
                    f"d={_safe(leg.entry_delta, '+.3f', '\u2014')} \u03b8={_safe(leg.entry_theta, '+.3f', '\u2014')}",
                    f"d={_safe(leg.delta, '+.3f', '\u2014')} \u03b8={_safe(leg.theta, '+.3f', '\u2014')}",
                    f"${leg_pnl:+,.0f}",
                ])
            blocks.append(_table(
                ["Leg", "Description", "Entry Greeks", "Current Greeks", "P&L"],
                rows,
            ))

        return blocks


def _handle_t_status(args: list[str], engine: 'WorkflowEngine', ma: MarketAnalyzer) -> list[dict]:
    """Broker connection, quote source, engine state."""
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.core.database.schema import PortfolioORM, TradeORM

    blocks: list[dict] = [_header("System Status")]

    # Broker & Data
    has_broker = ma.quotes.has_broker
    quote_source = ma.quotes.source
    blocks.append(_section("Broker & Data"))
    blocks.append(_kv([
        _kv_item("Broker Connected", "Yes" if has_broker else "No",
                 "green" if has_broker else "red"),
        _kv_item("Quote Source", quote_source),
        _kv_item("Adjustment Source", ma.adjustment.quote_source),
    ]))

    # Workflow Engine
    engine_state = str(engine.state) if hasattr(engine, 'state') else 'unknown'
    cycle_count = engine.context.get('cycle_count', 0)

    blocks.append(_section("Workflow Engine"))
    blocks.append(_kv([
        _kv_item("State", engine_state.upper()),
        _kv_item("Cycle Count", str(cycle_count)),
        _kv_item("Trading Day", "Yes" if engine.context.get('is_trading_day') else "No",
                 "green" if engine.context.get('is_trading_day') else "red"),
        _kv_item("Engine Started", str(engine.context.get('engine_start_time', 'N/A'))),
    ]))

    # Portfolio & position counts
    with session_scope() as session:
        portfolio_count = session.query(PortfolioORM).filter(
            PortfolioORM.portfolio_type != 'deprecated'
        ).count()
        open_trade_count = session.query(TradeORM).filter(
            TradeORM.is_open == True,  # noqa: E712
        ).count()

    blocks.append(_section("Portfolio"))
    blocks.append(_kv([
        _kv_item("Portfolios", str(portfolio_count)),
        _kv_item("Open Trades", str(open_trade_count)),
    ]))

    return blocks


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_terminal_router(engine: 'WorkflowEngine') -> APIRouter:
    """Create the terminal API router with MA + trading commands."""
    router = APIRouter()

    # Reuse the engine's existing broker session for MA live quotes.
    # Creating a separate connect_tastytrade() session fails because
    # Account.get() + asyncio.new_event_loop() conflicts with uvicorn's loop.
    # Instead, wrap the adapter's raw tastytrade Session objects in MA providers.
    _broker_market_data = None
    _broker_metrics = None
    if engine.broker is not None and getattr(engine.broker, 'session', None) is not None:
        try:
            from market_analyzer.broker.tastytrade.market_data import TastyTradeMarketData
            from market_analyzer.broker.tastytrade.metrics import TastyTradeMetrics

            class _AdapterSessionShim:
                """Minimal shim so MA providers can use the engine adapter's sessions."""
                def __init__(self, adapter):
                    self._adapter = adapter

                @property
                def sdk_session(self):
                    return self._adapter.session

                @property
                def data_session(self):
                    return self._adapter.data_session

            shim = _AdapterSessionShim(engine.broker)
            _broker_market_data = TastyTradeMarketData(shim)
            _broker_metrics = TastyTradeMetrics(shim)
            logger.info("Terminal MA: reusing engine broker session for live quotes")
        except Exception as e:
            logger.warning(f"Terminal MA: broker session shim failed: {e}")

    _ma_instance: list[MarketAnalyzer | None] = [None]  # mutable container for nonlocal

    def _get_ma() -> MarketAnalyzer:
        if _ma_instance[0] is None:
            _ma_instance[0] = MarketAnalyzer(
                data_service=DataService(),
                market_data=_broker_market_data,
                market_metrics=_broker_metrics,
            )
        return _ma_instance[0]

    # Plan handler with context storage
    def _plan_with_store(args: list[str], ma: MarketAnalyzer) -> list[dict]:
        plan_store: dict = {}
        blocks = _handle_plan(args, ma, plan_store=plan_store)
        if 'plan' in plan_store:
            engine.context['last_plan'] = plan_store['plan']
        return blocks

    handlers: dict = {
        # Market Analysis commands
        "context": _handle_context,
        "analyze": _handle_analyze,
        "screen": _handle_screen,
        "entry": _handle_entry,
        "strategy": _handle_strategy,
        "exit_plan": _handle_exit_plan,
        "plan": _plan_with_store,
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
        # Trading commands (closures capturing engine)
        "positions": lambda args, ma: _handle_t_positions(args, engine),
        "portfolios": lambda args, ma: _handle_t_portfolios(args, engine),
        "greeks": lambda args, ma: _handle_t_greeks(args, engine),
        "capital": lambda args, ma: _handle_t_capital(args, engine),
        "trades": lambda args, ma: _handle_t_trades(args, engine),
        "book": lambda args, ma: _handle_t_book(args, engine, ma),
        "execute": lambda args, ma: _handle_t_execute(args, engine),
        "orders": lambda args, ma: _handle_t_orders(args, engine),
        "morning": lambda args, ma: _handle_t_morning(args, engine, ma),
        # Trade Management commands
        "adjust": lambda args, ma: _handle_t_adjust(args, engine, ma),
        "close": lambda args, ma: _handle_t_close(args, engine),
        "chain": _handle_t_chain,
        "iv": _handle_t_iv,
        "pnl": lambda args, ma: _handle_t_pnl(args, engine),
        "status": lambda args, ma: _handle_t_status(args, engine, ma),
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
