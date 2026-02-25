"""
Market Analyzer Terminal API — interactive analysis terminal on the web.

Translates MarketAnalyzer CLI commands into structured block responses
that the frontend renders as a Claude Code-style terminal.

Single endpoint: POST /terminal/execute  {"command": "analyze SPY"}
"""

from typing import TYPE_CHECKING
import logging
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from market_analyzer import MarketAnalyzer, DataService

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

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


def _handle_rank(args: list[str], ma: MarketAnalyzer) -> list[dict]:
    tickers = [a.upper() for a in args] if args else None
    if not tickers:
        from market_analyzer.config import get_settings
        tickers = get_settings().display.default_tickers

    result = ma.ranking.rank(tickers)
    blocks: list[dict] = [_header(f"Trade Ranking ({result.as_of_date})")]

    if result.black_swan_gate:
        blocks.append(_status("TRADING HALTED \u2014 Black Swan CRITICAL", "red"))

    if result.top_trades:
        rows = [
            [str(e.rank), e.ticker, e.strategy_type, e.verdict, f"{e.composite_score:.2f}",
             e.direction, e.rationale[:50]]
            for e in result.top_trades[:10]
        ]
        blocks.append(_table(["#", "Ticker", "Strategy", "Verdict", "Score", "Direction", "Rationale"], rows))

    blocks.append(_text(result.summary, "dim"))
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

    # Bollinger & Stochastic
    blocks.append(_kv([
        _kv_item("Bollinger BW", f"{t.bollinger.bandwidth:.4f}"),
        _kv_item("Bollinger %B", f"{t.bollinger.percent_b:.2f}"),
        _kv_item("Stochastic K", f"{t.stochastic.k:.0f}"),
        _kv_item("Stochastic D", f"{t.stochastic.d:.0f}"),
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
                ["rank", "rank [SPY GLD ...]", "Rank trades across tickers"],
                ["regime", "regime [SPY GLD ...]", "Detect regime for tickers"],
                ["technicals", "technicals SPY", "Technical snapshot"],
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
        "rank": _handle_rank,
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
            blocks = handler(args, _get_ma())
            return TerminalResponse(blocks=blocks, command=body.command, success=True)
        except Exception as e:
            logger.error(f"Terminal command '{body.command}' failed: {e}", exc_info=True)
            return TerminalResponse(
                blocks=[_error(f"Error: {e}")],
                command=body.command,
                success=False,
            )

    return router
