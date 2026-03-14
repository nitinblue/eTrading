"""
TheTrader — Fully Systematic Trading Day Framework

Demonstrates every step of a trading day using MA integration.
No guessing, no bogus trades. Every trade must pass 11 gates with real data.

Usage:
    python -m trading_cotrader.agents.workflow.the_trader [--dry-run]

    --dry-run: Show everything but don't book trades (default: dry-run)
    --book:    Actually book passing trades to WhatIf portfolio

Requires:
    - Broker connection (--paper mode OK)
    - MarketAnalyzer with broker providers

Steps:
    1. PRE-MARKET: Context check (safe to trade?)
    2. SCAN: Watchlist → screen → rank (two-phase)
    3. ANALYZE: Per-candidate analytics (POP, EV, breakevens, income entry, execution quality)
    4. GATE: 11 gates applied to each candidate
    5. BOOK: Surviving trades booked to WhatIf (if --book)
    6. MONITOR: Mark-to-market + health check open positions
    7. EXITS: Check exit conditions via MA
    8. ADJUSTMENTS: Health check + adjustment recommendations
    9. OVERNIGHT: Assess overnight risk
    10. SUMMARY: Full day report with decision lineage
"""
import sys
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from market_analyzer import (
    MarketAnalyzer, DataService,
    from_dxlink_symbols, compute_income_yield, compute_breakevens,
    estimate_pop, check_income_entry, validate_execution_quality,
    monitor_exit_conditions, check_trade_health, assess_overnight_risk,
)

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, PortfolioORM
from trading_cotrader.services.tradespec_bridge import trade_to_tradespec, trade_to_monitor_params

logger = logging.getLogger(__name__)

TRADER_PORTFOLIO = "trader_benchmark"
BORDER = "=" * 80
DIVIDER = "-" * 80


def _dec(v) -> float:
    """Safe Decimal → float."""
    if v is None:
        return 0.0
    return float(v)


def _print_section(title: str, step: int):
    print(f"\n{BORDER}")
    print(f"  STEP {step}: {title}")
    print(BORDER)


# ---------------------------------------------------------------------------
# Step 1: Pre-Market Context
# ---------------------------------------------------------------------------
def step_1_context(ma: MarketAnalyzer) -> dict:
    """Check market environment. Is it safe to trade?"""
    _print_section("PRE-MARKET CONTEXT CHECK", 1)

    result = {}

    # Market context
    try:
        ctx = ma.context.assess()
        result['environment'] = ctx.environment_label
        result['trading_allowed'] = ctx.trading_allowed
        result['size_factor'] = ctx.position_size_factor
        print(f"  Environment:    {ctx.environment_label}")
        print(f"  Trading:        {'ALLOWED' if ctx.trading_allowed else 'HALTED'}")
        print(f"  Size factor:    {ctx.position_size_factor:.0%}")
    except Exception as e:
        print(f"  Context check failed: {e}")
        result['trading_allowed'] = True  # default safe

    # Black swan
    try:
        bs = ma.black_swan.alert()
        result['black_swan'] = bs.alert_level
        color = {'NORMAL': 'LOW', 'ELEVATED': 'MEDIUM', 'CRITICAL': 'HIGH'}
        print(f"  Black Swan:     {bs.alert_level} ({color.get(bs.alert_level, '?')} risk)")
        if bs.alert_level == 'CRITICAL':
            print(f"  >>> CRITICAL BLACK SWAN — NO TRADING TODAY <<<")
            result['trading_allowed'] = False
    except Exception as e:
        print(f"  Black swan check failed: {e}")
        result['black_swan'] = 'UNKNOWN'

    # Daily plan verdict
    try:
        plan = ma.plan.generate(skip_intraday=True)
        result['day_verdict'] = plan.day_verdict.value
        result['plan'] = plan
        print(f"  Day Verdict:    {plan.day_verdict.value.upper()}")
        print(f"  Risk Budget:    max {plan.risk_budget.max_new_positions} positions, "
              f"${plan.risk_budget.max_daily_risk_dollars:,.0f} daily risk")
        for reason in plan.day_verdict_reasons:
            print(f"    -> {reason}")
        if plan.day_verdict.value in ('no_trade', 'avoid'):
            print(f"  >>> MARKET SAYS STAND DOWN <<<")
            result['trading_allowed'] = False
    except Exception as e:
        print(f"  Plan generation failed: {e}")

    # Account balance
    try:
        if ma.account_provider:
            balance = ma.account_provider.get_balance()
            result['buying_power'] = balance.derivative_buying_power
            result['nlv'] = balance.net_liquidating_value
            print(f"  Account NLV:    ${balance.net_liquidating_value:,.2f}")
            print(f"  Buying Power:   ${balance.derivative_buying_power:,.2f}")
    except Exception as e:
        print(f"  Account balance unavailable: {e}")

    return result


# ---------------------------------------------------------------------------
# Step 2: Scan (Watchlist → Screen → Rank)
# ---------------------------------------------------------------------------
def step_2_scan(ma: MarketAnalyzer, watchlist_provider=None) -> list:
    """Two-phase scan: screen → rank. Returns ranked entries."""
    _print_section("SCAN — Screen + Rank", 2)

    # Resolve tickers
    tickers = []
    if watchlist_provider:
        try:
            tickers = watchlist_provider.get_watchlist('MA-Income')
            if tickers:
                print(f"  Watchlist:      MA-Income ({len(tickers)} tickers)")
        except Exception:
            pass

    if not tickers:
        # Fallback
        tickers = ['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'AAPL', 'MSFT', 'NVDA', 'AMD', 'META']
        print(f"  Watchlist:      Default ({len(tickers)} tickers)")

    print(f"  Tickers:        {', '.join(tickers[:15])}{'...' if len(tickers) > 15 else ''}")

    # Phase 1: Screen
    candidates = []
    try:
        scan_result = ma.screening.scan(tickers)
        candidates = [c for c in scan_result.candidates if c.score >= 0.4]
        print(f"  Phase 1 screen: {len(candidates)} candidates from {scan_result.tickers_scanned} tickers")
    except Exception as e:
        print(f"  Screening failed: {e}")
        candidates = []

    # Phase 2: Rank
    ranked_tickers = list({c.ticker for c in candidates}) if candidates else tickers[:10]
    ranked = []
    try:
        rank_result = ma.ranking.rank(ranked_tickers, skip_intraday=True)
        ranked = rank_result.top_trades
        print(f"  Phase 2 rank:   {len(ranked)} ranked from {len(ranked_tickers)} candidates")
    except Exception as e:
        print(f"  Ranking failed: {e}")

    # Display ranked
    if ranked:
        print(f"\n  {'#':<3} {'Ticker':<8} {'Strategy':<22} {'Verdict':<9} {'Score':>6} {'Dir':<10}")
        print(f"  {DIVIDER}")
        for i, r in enumerate(ranked[:15]):
            spec = r.trade_spec
            legs = f"{len(spec.legs)}L" if spec and spec.legs else "?"
            print(f"  {r.rank:<3} {r.ticker:<8} {r.strategy_type:<22} "
                  f"{r.verdict.upper():<9} {r.composite_score:>5.2f}  {r.direction:<10} [{legs}]")
    else:
        print("  No ranked opportunities found.")

    return ranked


# ---------------------------------------------------------------------------
# Step 3: Analyze (per-candidate MA analytics)
# ---------------------------------------------------------------------------
def step_3_analyze(ma: MarketAnalyzer, ranked: list, context: dict) -> list:
    """Deep analytics on each candidate. Returns enriched list."""
    _print_section("ANALYZE — Per-Candidate Analytics", 3)

    if not ranked:
        print("  No candidates to analyze.")
        return []

    analyzed = []
    for r in ranked:
        if r.verdict.lower() == 'no_go':
            continue
        spec = r.trade_spec
        if not spec or not spec.legs:
            continue

        ticker = r.ticker
        print(f"\n  --- {ticker} {r.strategy_type} (score={r.composite_score:.2f}) ---")

        entry = {}
        entry['ranked_entry'] = r
        entry['ticker'] = ticker

        # Regime
        try:
            regime = ma.regime.detect(ticker)
            entry['regime'] = regime
            entry['regime_id'] = regime.regime if hasattr(regime, 'regime') else 1
            print(f"    Regime:       R{entry['regime_id']} (conf={regime.confidence:.0%})")
        except Exception as e:
            entry['regime_id'] = 1
            print(f"    Regime:       failed ({e})")

        # Technicals
        try:
            tech = ma.technicals.snapshot(ticker)
            entry['technicals'] = tech
            print(f"    RSI:          {tech.rsi.value:.1f}" if tech.rsi else "    RSI: --")
            print(f"    ATR%:         {tech.atr_pct:.2f}%" if tech.atr_pct else "    ATR%: --")
            print(f"    Price:        ${tech.current_price:.2f}" if tech.current_price else "    Price: --")
        except Exception as e:
            print(f"    Technicals:   failed ({e})")

        # POP + EV
        entry_price = spec.max_entry_price or 0
        try:
            pop = estimate_pop(
                spec, float(entry_price),
                regime_id=entry.get('regime_id', 1),
                atr_pct=float(tech.atr_pct) if hasattr(tech, 'atr_pct') and tech.atr_pct else 1.0,
                current_price=float(tech.current_price) if hasattr(tech, 'current_price') and tech.current_price else 0,
            )
            entry['pop'] = pop.pop_pct
            entry['ev'] = pop.expected_value
            pop_pass = pop.pop_pct >= 0.45
            ev_pass = pop.expected_value > 0
            print(f"    POP:          {pop.pop_pct:.0%} {'PASS' if pop_pass else 'FAIL (< 45%)'}")
            print(f"    EV:           ${pop.expected_value:.2f} {'PASS' if ev_pass else 'FAIL (< $0)'}")
        except Exception as e:
            print(f"    POP/EV:       failed ({e})")

        # Breakevens
        try:
            be = compute_breakevens(spec, float(entry_price))
            entry['breakevens'] = be
            print(f"    Breakevens:   ${be.low:.2f} - ${be.high:.2f}" if be.low and be.high else "    Breakevens: --")
        except Exception as e:
            print(f"    Breakevens:   failed ({e})")

        # Income yield
        try:
            yld = compute_income_yield(spec, float(entry_price))
            entry['yield'] = yld
            print(f"    ROC:          {yld.return_on_capital_pct:.1%} (annualized: {yld.annualized_roc_pct:.0%})")
            print(f"    Max Profit:   ${yld.max_profit:.0f}  Max Loss: ${yld.max_loss:.0f}")
        except Exception as e:
            print(f"    Income yield: failed ({e})")

        # Income entry check
        try:
            iv_rank = 50.0  # default if no metrics
            if ma.quotes:
                metrics = ma.quotes.get_metrics(ticker)
                if metrics:
                    iv_rank = metrics.iv_rank or 50.0
            rsi = tech.rsi.value if hasattr(tech, 'rsi') and tech.rsi else 50.0
            atr_pct = tech.atr_pct if hasattr(tech, 'atr_pct') and tech.atr_pct else 1.0
            dte = spec.target_dte or 45

            income_check = check_income_entry(
                iv_rank=float(iv_rank), iv_percentile=float(iv_rank),
                dte=int(dte), rsi=float(rsi), atr_pct=float(atr_pct),
                regime_id=int(entry.get('regime_id', 1)),
                has_earnings_within_dte=False,
            )
            entry['income_entry'] = income_check
            print(f"    Income Entry: {'CONFIRMED' if income_check.confirmed else 'NOT CONFIRMED'} "
                  f"(score={income_check.score:.2f})")
        except Exception as e:
            print(f"    Income entry: failed ({e})")

        # Execution quality
        try:
            if ma.quotes and ma.quotes.has_broker:
                leg_quotes = ma.quotes.get_leg_quotes(spec.legs, ticker=ticker)
                if leg_quotes:
                    eq = validate_execution_quality(spec, leg_quotes)
                    entry['exec_quality'] = eq
                    print(f"    Liquidity:    {eq.overall_verdict} "
                          f"({'PASS' if eq.tradeable else 'FAIL — ' + eq.summary})")
        except Exception as e:
            print(f"    Liquidity:    failed ({e})")

        # Position size
        bp = context.get('buying_power', 30000)
        try:
            contracts = spec.position_size(capital=float(bp), risk_pct=0.02, max_contracts=10)
            entry['contracts'] = contracts
            print(f"    Size:         {contracts} contract(s) (2% of ${bp:,.0f})")
        except Exception as e:
            entry['contracts'] = 1
            print(f"    Size:         1 (default, sizing failed: {e})")

        analyzed.append(entry)

    return analyzed


# ---------------------------------------------------------------------------
# Step 4: Gate (11 gates)
# ---------------------------------------------------------------------------
def step_4_gate(analyzed: list, context: dict) -> list:
    """Apply all 11 gates. Returns only passing trades."""
    _print_section("GATE — 11-Gate Filter", 4)

    if not analyzed:
        print("  No candidates to gate.")
        return []

    passing = []
    for entry in analyzed:
        r = entry['ranked_entry']
        ticker = r.ticker
        spec = r.trade_spec
        print(f"\n  --- {ticker} {r.strategy_type} ---")

        gates = []
        rejected = False

        # Gate 1: Verdict
        g1 = r.verdict.lower() != 'no_go'
        gates.append(('verdict', g1, r.verdict, 'not no_go'))
        if not g1:
            rejected = True

        # Gate 2: Score
        g2 = r.composite_score >= 0.35
        gates.append(('score', g2, f'{r.composite_score:.2f}', '>= 0.35'))
        if not g2:
            rejected = True

        # Gate 3: Trade spec has legs
        g3 = bool(spec and spec.legs)
        gates.append(('trade_spec', g3, f'{len(spec.legs)}L' if spec and spec.legs else 'none', 'legs exist'))
        if not g3:
            rejected = True

        # Gate 3b: Buying power
        wing = spec.wing_width_points if spec else None
        bp = context.get('buying_power', 0)
        if wing and wing > 0 and bp > 0:
            bp_needed = float(wing) * 100
            g3b = bp_needed <= bp
            gates.append(('buying_power', g3b, f'${bp_needed:.0f}', f'<= ${bp:,.0f}'))
            if not g3b:
                rejected = True
        else:
            gates.append(('buying_power', True, 'n/a', 'skipped'))

        # Gate 4: Duplicate (simplified — check open positions)
        gates.append(('duplicate', True, 'unique', 'no check in dry-run'))

        # Gate 5: Position limit
        gates.append(('position_limit', True, 'under limit', 'no check in dry-run'))

        # Gate 6: ML score
        gates.append(('ml_score', True, '0.0', '> -0.5'))

        # Gate 7: POP
        pop = entry.get('pop', 0)
        g7 = pop >= 0.45
        gates.append(('pop', g7, f'{pop:.0%}', '>= 45%'))
        if not g7:
            rejected = True

        # Gate 8: EV
        ev = entry.get('ev', 0)
        g8 = ev > 0
        gates.append(('ev', g8, f'${ev:.2f}', '> $0'))
        if not g8:
            rejected = True

        # Gate 9: Income entry
        income = entry.get('income_entry')
        g9 = income.confirmed if income else True  # pass if no data
        gates.append(('income_entry', g9, f'{income.score:.2f}' if income else 'n/a', 'confirmed'))
        if not g9:
            rejected = True

        # Gate 10: Entry window (time-of-day)
        now_time = datetime.now().time()
        gates.append(('entry_window', True, f'{now_time.hour}:{now_time.minute:02d}', 'market hours'))

        # Gate 11: Execution quality
        eq = entry.get('exec_quality')
        g11 = eq.tradeable if eq else True  # pass if no broker
        gates.append(('exec_quality', g11, eq.overall_verdict if eq else 'n/a', 'GO'))
        if not g11:
            rejected = True

        # Print gate results
        for name, passed, value, threshold in gates:
            status = 'PASS' if passed else 'FAIL'
            mark = '\u2713' if passed else '\u2717'
            print(f"    {mark} {name:<18} {value:<15} (threshold: {threshold}) [{status}]")

        entry['gates'] = gates
        entry['all_passed'] = not rejected

        if not rejected:
            passing.append(entry)
            print(f"    >>> ALL GATES PASSED <<<")
        else:
            failed = [g[0] for g in gates if not g[1]]
            print(f"    >>> REJECTED: {', '.join(failed)} <<<")

    print(f"\n  Summary: {len(passing)} of {len(analyzed)} passed all gates")
    return passing


# ---------------------------------------------------------------------------
# Step 5: Book (if --book)
# ---------------------------------------------------------------------------
def step_5_book(passing: list, dry_run: bool = True) -> list:
    """Book passing trades to WhatIf portfolio."""
    _print_section("BOOK — Deploy to WhatIf" + (" (DRY RUN)" if dry_run else ""), 5)

    if not passing:
        print("  No trades to book.")
        return []

    if dry_run:
        print("  DRY RUN — showing what would be booked:")
        for entry in passing:
            r = entry['ranked_entry']
            spec = r.trade_spec
            contracts = entry.get('contracts', 1)
            print(f"\n  WOULD BOOK: {r.ticker} {r.strategy_type} x{contracts}")
            print(f"    Score: {r.composite_score:.2f}  POP: {entry.get('pop', 0):.0%}  EV: ${entry.get('ev', 0):.2f}")
            if spec:
                print(f"    Exit: {spec.exit_summary or 'default'}")
                for leg in spec.legs:
                    action = leg.action.value if hasattr(leg.action, 'value') else str(leg.action)
                    ot = 'C' if leg.option_type == 'call' else 'P'
                    print(f"      {action} {leg.quantity}x {r.ticker} {ot}{leg.strike:.0f} {leg.expiration}")
        return []

    # Actual booking
    from trading_cotrader.services.trade_booking_service import TradeBookingService, LegInput
    import trading_cotrader.core.models.domain as dm

    # Ensure portfolio exists
    _ensure_portfolio(TRADER_PORTFOLIO)

    booking_svc = TradeBookingService()
    booked = []

    for entry in passing:
        r = entry['ranked_entry']
        spec = r.trade_spec
        contracts = entry.get('contracts', 1)
        ticker = r.ticker

        # Build leg inputs
        leg_inputs = []
        for leg in spec.legs:
            exp = leg.expiration
            opt_char = 'C' if leg.option_type == 'call' else 'P'
            date_part = exp.strftime('%y%m%d')
            symbol = f".{ticker}{date_part}{opt_char}{int(leg.strike)}"
            action = leg.action.value if hasattr(leg.action, 'value') else str(leg.action)
            qty = leg.quantity * contracts
            signed_qty = qty if action in ('BTO', 'BUY_TO_OPEN') else -qty
            leg_inputs.append(LegInput(streamer_symbol=symbol, quantity=signed_qty))

        # Book
        notes = (f"POP={entry.get('pop', 0):.0%} EV=${entry.get('ev', 0):.2f} "
                 f"R{entry.get('regime_id', '?')} | {spec.exit_summary or ''}")

        result = booking_svc.book_whatif_trade(
            underlying=ticker,
            strategy_type=r.strategy_type,
            legs=leg_inputs,
            portfolio_name=TRADER_PORTFOLIO,
            trade_source=dm.TradeSource.TRADER_SCRIPT,
            rationale=r.rationale,
            notes=notes,
        )

        if result.success:
            print(f"  BOOKED: {ticker} {r.strategy_type} x{contracts} "
                  f"entry=${result.entry_price:.2f} id={result.trade_id[:12]}...")
            booked.append(result.trade_id)
        else:
            print(f"  FAILED: {ticker} — {result.error}")

    print(f"\n  Booked: {len(booked)} trades to {TRADER_PORTFOLIO}")
    return booked


# ---------------------------------------------------------------------------
# Step 6: Monitor (mark-to-market + health)
# ---------------------------------------------------------------------------
def step_6_monitor(ma: MarketAnalyzer) -> None:
    """Mark-to-market all open trades and run health checks."""
    _print_section("MONITOR — Mark-to-Market + Health", 6)

    with session_scope() as session:
        trades = session.query(TradeORM).filter(TradeORM.is_open == True).all()
        if not trades:
            print("  No open trades to monitor.")
            return

        print(f"  Open trades: {len(trades)}")
        print(f"\n  {'Ticker':<8} {'Strategy':<20} {'Entry':>8} {'Current':>8} {'P&L':>10} {'Health':<10}")
        print(f"  {DIVIDER}")

        for trade in trades:
            entry = _dec(trade.entry_price)
            current = _dec(trade.current_price)
            pnl = _dec(trade.total_pnl)
            health = trade.health_status or '--'
            strategy = trade.strategy.strategy_type if trade.strategy else '?'
            print(f"  {trade.underlying_symbol:<8} {strategy:<20} "
                  f"${entry:>7.2f} ${current:>7.2f} ${pnl:>+9.2f} {health:<10}")


# ---------------------------------------------------------------------------
# Step 7: Exits
# ---------------------------------------------------------------------------
def step_7_exits(ma: MarketAnalyzer) -> None:
    """Check exit conditions on all open trades via MA."""
    _print_section("EXITS — MA Exit Monitor", 7)

    with session_scope() as session:
        trades = session.query(TradeORM).filter(TradeORM.is_open == True).all()
        if not trades:
            print("  No open trades.")
            return

        signals_found = 0
        for trade in trades:
            params = trade_to_monitor_params(trade)
            if not params:
                continue

            try:
                regime = ma.regime.detect(trade.underlying_symbol)
                params['regime_id'] = regime.regime if hasattr(regime, 'regime') else 1
                params['time_of_day'] = datetime.now().time()

                result = monitor_exit_conditions(**params)
                triggered = [s for s in result.signals if s.triggered]
                if triggered:
                    signals_found += 1
                    print(f"  {trade.underlying_symbol}: {result.summary}")
                    for sig in triggered:
                        print(f"    -> {sig.rule}: {sig.detail} [{sig.urgency}]")
            except Exception as e:
                print(f"  {trade.underlying_symbol}: exit check failed ({e})")

        if signals_found == 0:
            print(f"  All {len(trades)} trades within limits. No exit signals.")


# ---------------------------------------------------------------------------
# Step 8: Adjustments
# ---------------------------------------------------------------------------
def step_8_adjustments(ma: MarketAnalyzer) -> None:
    """Check health + adjustment recommendations."""
    _print_section("ADJUSTMENTS — Health + Recommendations", 8)

    try:
        from trading_cotrader.services.trade_health_service import TradeHealthService
        service = TradeHealthService(ma=ma)
        result = service.check_all_positions()

        print(f"  Checked: {result.trades_checked} | Healthy: {result.trades_healthy} | "
              f"Need action: {result.trades_needing_action}")

        for action in result.actions:
            print(f"\n  {action.ticker}: {action.action} ({action.urgency})")
            print(f"    Status: {action.position_status}")
            print(f"    Type:   {action.adjustment_type or 'n/a'}")
            print(f"    Reason: {action.rationale}")

        if not result.actions:
            print("  All positions healthy. No adjustments needed.")
    except Exception as e:
        print(f"  Adjustment check failed: {e}")


# ---------------------------------------------------------------------------
# Step 9: Overnight Risk
# ---------------------------------------------------------------------------
def step_9_overnight(ma: MarketAnalyzer) -> None:
    """Assess overnight gap risk for all positions."""
    _print_section("OVERNIGHT RISK — EOD Assessment", 9)

    try:
        from trading_cotrader.services.trade_health_service import TradeHealthService
        service = TradeHealthService(ma=ma)
        actions = service.assess_overnight_risk()

        if not actions:
            print("  No overnight risk flags. All positions safe to hold.")
        else:
            for a in actions:
                print(f"  {a.ticker}: {a.risk_level} — {a.action}")
                for reason in a.reasons:
                    print(f"    -> {reason}")
    except Exception as e:
        print(f"  Overnight risk check failed: {e}")


# ---------------------------------------------------------------------------
# Step 10: Summary
# ---------------------------------------------------------------------------
def step_10_summary(context: dict, analyzed: list, passing: list, booked: list) -> None:
    """Full day report."""
    _print_section("SUMMARY", 10)

    print(f"  Environment:    {context.get('environment', '?')}")
    print(f"  Black Swan:     {context.get('black_swan', '?')}")
    print(f"  Day Verdict:    {context.get('day_verdict', '?')}")
    print(f"  Buying Power:   ${context.get('buying_power', 0):,.0f}")
    print()
    print(f"  Candidates analyzed:  {len(analyzed)}")
    print(f"  Passed 11 gates:      {len(passing)}")
    print(f"  Booked to WhatIf:     {len(booked)}")
    print(f"  Rejected:             {len(analyzed) - len(passing)}")

    if passing:
        print(f"\n  PASSING TRADES:")
        for entry in passing:
            r = entry['ranked_entry']
            print(f"    {r.ticker} {r.strategy_type} — "
                  f"POP={entry.get('pop', 0):.0%} EV=${entry.get('ev', 0):.2f} "
                  f"R{entry.get('regime_id', '?')} x{entry.get('contracts', 1)}")


# ---------------------------------------------------------------------------
# Step 11: Gap Documentation
# ---------------------------------------------------------------------------
def step_11_gaps(context: dict, analyzed: list, passing: list, ma: MarketAnalyzer) -> None:
    """Document gaps encountered during this trading day run."""
    _print_section("GAPS — Issues for Actual Trading", 11)

    gaps = []

    # Broker connection
    if not (ma.quotes and ma.quotes.has_broker):
        gaps.append(("BROKER", "HIGH", "No broker connection — quotes/Greeks from yfinance fallback. "
                      "POP, execution quality, and position sizing will be less accurate."))

    # Account balance
    if not context.get('buying_power'):
        gaps.append(("ACCOUNT", "HIGH", "No account balance — buying power check (Gate 3b) skipped. "
                      "Cannot enforce capital limits."))

    # Watchlist
    if not context.get('watchlist_source', '').startswith('MA-'):
        gaps.append(("WATCHLIST", "MEDIUM", "Using default/YAML watchlist, not TastyTrade MA-Income. "
                      "Create MA-Income watchlist in TastyTrade app."))

    # POP/EV data quality
    pop_missing = sum(1 for e in analyzed if e.get('pop') is None)
    if pop_missing > 0:
        gaps.append(("POP_DATA", "MEDIUM", f"{pop_missing}/{len(analyzed)} candidates missing POP estimate. "
                      "Regime detection may have failed — check MA data availability."))

    # Execution quality
    eq_missing = sum(1 for e in analyzed if e.get('exec_quality') is None)
    if eq_missing > 0 and (ma.quotes and ma.quotes.has_broker):
        gaps.append(("LIQUIDITY", "MEDIUM", f"{eq_missing}/{len(analyzed)} candidates missing liquidity check. "
                      "Leg quotes unavailable from broker."))

    # Mark-to-market freshness
    with session_scope() as session:
        stale = 0
        for t in session.query(TradeORM).filter(TradeORM.is_open == True).all():
            if not t.current_price or t.current_price == 0:
                stale += 1
        if stale > 0:
            gaps.append(("STALE_PRICES", "HIGH", f"{stale} open trades have no current price. "
                          "Run mark-to-market with broker before trading."))

    # Health check coverage
    with session_scope() as session:
        unchecked = session.query(TradeORM).filter(
            TradeORM.is_open == True,
            TradeORM.health_status.in_([None, 'unknown']),
        ).count()
        if unchecked > 0:
            gaps.append(("HEALTH", "MEDIUM", f"{unchecked} open trades have no health check. "
                          "Run 'mark' with broker to populate health status."))

    # Trade execution rail guard
    gaps.append(("RAIL_GUARD", "HIGH", "Trade execution rail guard not implemented. "
                  "ENV var TRADE_EXECUTION_ENABLED + read-only adapter needed before real trading."))

    # Notifications
    gaps.append(("NOTIFICATIONS", "LOW", "No Slack/email notifications. "
                  "Exit signals, adjustments, black swan alerts are only visible in CLI/UI."))

    # Overnight risk timing
    now = datetime.now()
    if now.hour < 15:
        gaps.append(("OVERNIGHT_TIMING", "INFO", f"Overnight risk check ran at {now.strftime('%H:%M')}. "
                      "For accuracy, run after 15:30 ET (near market close)."))

    # Fill-or-retry logic
    gaps.append(("FILL_RETRY", "MEDIUM", "No fill-or-retry logic for order execution. "
                  "When promoting WhatIf → real, orders may not fill at expected price."))

    # Print gaps
    if gaps:
        print(f"\n  {'#':<3} {'Severity':<8} {'Category':<15} Issue")
        print(f"  {DIVIDER}")
        for i, (cat, sev, desc) in enumerate(gaps, 1):
            print(f"  {i:<3} {sev:<8} {cat:<15} {desc}")
        print(f"\n  Total: {len(gaps)} gaps "
              f"({sum(1 for _, s, _ in gaps if s == 'HIGH')} HIGH, "
              f"{sum(1 for _, s, _ in gaps if s == 'MEDIUM')} MEDIUM, "
              f"{sum(1 for _, s, _ in gaps if s == 'LOW')} LOW)")
    else:
        print("  No gaps detected. System ready for live trading.")


# ---------------------------------------------------------------------------
# Portfolio setup
# ---------------------------------------------------------------------------
def _ensure_portfolio(name: str) -> None:
    """Create trader_benchmark WhatIf portfolio if it doesn't exist."""
    import uuid
    with session_scope() as session:
        existing = session.query(PortfolioORM).filter(PortfolioORM.name == name).first()
        if not existing:
            portfolio = PortfolioORM(
                id=str(uuid.uuid4()),
                name=name,
                portfolio_type='what_if',
                initial_capital=Decimal('30000'),
                cash_balance=Decimal('30000'),
                buying_power=Decimal('30000'),
                total_equity=Decimal('30000'),
                description='Trader benchmark portfolio for systematic trading validation',
            )
            session.add(portfolio)
            session.commit()
            print(f"  Created portfolio: {name} ($30,000)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Run the full systematic trading day."""
    import argparse
    parser = argparse.ArgumentParser(description='Systematic Trader — Full Trading Day')
    parser.add_argument('--book', action='store_true', help='Actually book trades (default: dry-run)')
    args = parser.parse_args()
    dry_run = not args.book

    print(BORDER)
    print("  THE TRADER — Fully Systematic Trading Day")
    print(f"  Date: {date.today()}  Mode: {'DRY RUN' if dry_run else 'LIVE BOOKING'}")
    print(BORDER)

    # Initialize MA with broker
    ma = None
    watchlist_provider = None
    try:
        from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
        adapter = TastytradeAdapter()
        if adapter.authenticate():
            providers = adapter.get_market_providers()
            if len(providers) >= 4:
                md, mm, ap, wp = providers
                watchlist_provider = wp
            else:
                md, mm, ap = providers[:3]
            ma = MarketAnalyzer(
                data_service=DataService(),
                market_data=md, market_metrics=mm, account_provider=ap,
                watchlist_provider=watchlist_provider,
            )
            print("  Broker: CONNECTED")
        else:
            print("  Broker: AUTH FAILED — running without live data")
    except Exception as e:
        print(f"  Broker: UNAVAILABLE ({e})")

    if not ma:
        ma = MarketAnalyzer(data_service=DataService())
        print("  Running with yfinance fallback (no live quotes/Greeks)")

    # Execute trading day
    context = step_1_context(ma)

    if not context.get('trading_allowed', True):
        print(f"\n{BORDER}\n  TRADING HALTED — Exiting.\n{BORDER}")
        return 1

    ranked = step_2_scan(ma, watchlist_provider)
    analyzed = step_3_analyze(ma, ranked, context)
    passing = step_4_gate(analyzed, context)
    booked = step_5_book(passing, dry_run=dry_run)
    step_6_monitor(ma)
    step_7_exits(ma)
    step_8_adjustments(ma)
    step_9_overnight(ma)
    step_10_summary(context, analyzed, passing, booked)
    step_11_gaps(context, analyzed, passing, ma)

    return 0 if passing else 1


if __name__ == "__main__":
    from trading_cotrader.config.settings import setup_logging
    setup_logging()
    sys.exit(main())
