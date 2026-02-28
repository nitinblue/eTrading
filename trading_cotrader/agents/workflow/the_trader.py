"""
TheTrader — Morning Trading Workflow Script

Takes MarketAnalyzer's daily plan, applies multi-layer risk checks,
and books surviving trades into the WhatIf portfolio.

Usage:
    python -m trading_cotrader.agents.workflow.the_trader
"""
import sys
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from market_analyzer import MarketAnalyzer, DataService
from market_analyzer.models.opportunity import LegAction

import trading_cotrader.core.models.domain as dm
from trading_cotrader.config.risk_config_loader import (
    RiskConfigLoader,
    PortfolioConfig,
    PortfolioRiskLimits,
)
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, PortfolioORM, StrategyORM
from trading_cotrader.services.trade_booking_service import (
    TradeBookingService,
    LegInput,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORTFOLIO_NAME = "tastytrade_whatif"

# Strategies with unlimited loss potential
UNDEFINED_RISK_STRATEGIES = {
    "ratio_spread",
    "big_lizard",
    "jade_lizard",
}
# These are undefined only when SOLD (short)
UNDEFINED_WHEN_SHORT = {"straddle", "strangle"}
# Single options are undefined when short
SINGLE_STRATEGY = "single"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_legs(spec) -> str:
    """Format legs from TradeSpec into readable string."""
    if not spec or not spec.legs:
        return "n/a"
    parts = []
    for leg in spec.legs[:4]:
        action = leg.action.value if hasattr(leg.action, "value") else str(leg.action)
        otype = leg.option_type.upper() if leg.option_type else "?"
        strike = f"${leg.strike:.0f}" if leg.strike else "?"
        parts.append(f"{action} {strike} {otype}")
    return " | ".join(parts)


def _parse_risk_per_spread(spec) -> Optional[float]:
    """Try to extract numeric risk-per-spread from TradeSpec."""
    if spec and spec.max_risk_per_spread:
        try:
            return float(str(spec.max_risk_per_spread).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            pass
    # Fallback: wing_width_points * 100
    if spec and spec.wing_width_points:
        try:
            return float(spec.wing_width_points) * 100
        except (ValueError, TypeError):
            pass
    return None


def _get_current_positions(portfolio_name: str) -> list:
    """Query DB for open trades in the given portfolio. Returns list of dicts."""
    positions = []
    with session_scope() as session:
        portfolio = session.query(PortfolioORM).filter(
            PortfolioORM.name == portfolio_name
        ).first()
        if not portfolio:
            return positions
        trades = (
            session.query(TradeORM)
            .filter(
                TradeORM.portfolio_id == portfolio.id,
                TradeORM.is_open.is_(True),
            )
            .all()
        )
        for t in trades:
            strat_type = ""
            if t.strategy_id:
                strat = session.query(StrategyORM).filter(
                    StrategyORM.id == t.strategy_id
                ).first()
                if strat:
                    strat_type = strat.strategy_type
            positions.append({
                "underlying": t.underlying_symbol,
                "strategy_type": strat_type,
                "delta": float(t.entry_delta or 0),
            })
    return positions


# ---------------------------------------------------------------------------
# Step 3: Risk Gate — check functions
# ---------------------------------------------------------------------------
def check_structure(trade_spec, strategy_type: str) -> Tuple[bool, str]:
    """3a: Validate trade structure — legs, wing width, strike validity."""
    if not trade_spec or not trade_spec.legs:
        return False, "No legs on trade spec"

    legs = trade_spec.legs
    leg_count = len(legs)

    # Check all legs have valid strikes and expirations
    for i, leg in enumerate(legs):
        if not leg.strike or leg.strike <= 0:
            return False, f"Leg {i+1} has invalid strike: {leg.strike}"
        if not leg.expiration:
            return False, f"Leg {i+1} has no expiration"

    # Wing width check for spreads (IC, butterfly, vertical)
    if strategy_type in ("iron_condor", "iron_butterfly") and leg_count == 4:
        strikes = sorted([leg.strike for leg in legs])
        # For IC: check both wings have width > 0
        call_wing = strikes[3] - strikes[2]
        put_wing = strikes[1] - strikes[0]
        if call_wing <= 0 or put_wing <= 0:
            return False, f"Zero wing width: put_wing={put_wing}, call_wing={call_wing}"

    if strategy_type == "vertical_spread" and leg_count == 2:
        width = abs(legs[0].strike - legs[1].strike)
        if width <= 0:
            return False, f"Zero spread width: {width}"

    # Leg count sanity
    expected = {
        "iron_condor": 4, "iron_butterfly": 4,
        "vertical_spread": 2, "calendar": 2, "diagonal": 2,
    }
    if strategy_type in expected and leg_count != expected[strategy_type]:
        return False, f"Expected {expected[strategy_type]} legs for {strategy_type}, got {leg_count}"

    return True, "OK"


def check_defined_risk(strategy_type: str, legs, risk_limits: PortfolioRiskLimits) -> Tuple[bool, str]:
    """3b: Block unlimited-loss strategies if allow_undefined_risk=false."""
    if risk_limits.allow_undefined_risk:
        return True, "Undefined risk allowed by config"

    st = strategy_type.lower()

    if st in UNDEFINED_RISK_STRATEGIES:
        return False, f"{strategy_type} has UNLIMITED loss potential"

    if st in UNDEFINED_WHEN_SHORT:
        # Undefined only when sold — check if any leg is STO
        has_short = any(
            (leg.action == LegAction.SELL_TO_OPEN
             if hasattr(leg.action, 'value') and leg.action == LegAction.SELL_TO_OPEN
             else str(leg.action).upper() in ("STO", "SELL_TO_OPEN"))
            for leg in (legs or [])
        )
        if has_short:
            return False, f"Short {strategy_type} has UNLIMITED loss potential"

    if st == SINGLE_STRATEGY:
        # Single short option = undefined risk
        has_short = any(
            (leg.action == LegAction.SELL_TO_OPEN
             if hasattr(leg.action, 'value') and leg.action == LegAction.SELL_TO_OPEN
             else str(leg.action).upper() in ("STO", "SELL_TO_OPEN"))
            for leg in (legs or [])
        )
        if has_short:
            return False, "Naked short option has UNLIMITED loss potential"

    return True, "Defined risk"


def check_position_risk(
    trade_spec, capital: float, risk_limits: PortfolioRiskLimits
) -> Tuple[bool, str]:
    """3c: Per-trade risk check — risk per contract vs account limits."""
    risk_per_contract = _parse_risk_per_spread(trade_spec)
    if risk_per_contract is None:
        return False, "Cannot determine risk per contract"
    if risk_per_contract <= 0:
        return False, f"Risk per contract is ${risk_per_contract:.0f} (must be > 0)"

    max_trade_risk = capital * (risk_limits.max_single_trade_risk_pct / 100)
    if risk_per_contract > max_trade_risk:
        return False, (
            f"Risk/contract ${risk_per_contract:.0f} > max single trade risk "
            f"${max_trade_risk:.0f} ({risk_limits.max_single_trade_risk_pct}% of ${capital:,.0f})"
        )

    return True, f"Risk/contract ${risk_per_contract:.0f} within limits"


def check_portfolio_risk(
    ticker: str,
    strategy_type: str,
    risk_limits: PortfolioRiskLimits,
    current_positions: list,
    trade_delta: float = 0,
) -> Tuple[bool, str]:
    """3d: Portfolio-level risk — position counts, delta, concentration."""
    total_positions = len(current_positions)
    if total_positions >= risk_limits.max_positions:
        return False, f"At max positions: {total_positions}/{risk_limits.max_positions}"

    # Positions in this underlying
    underlying_count = sum(1 for p in current_positions if p["underlying"] == ticker)
    if underlying_count >= risk_limits.max_positions_per_underlying:
        return False, (
            f"{ticker}: {underlying_count} positions already "
            f"(max {risk_limits.max_positions_per_underlying})"
        )

    # Positions of same strategy type
    strat_count = sum(
        1 for p in current_positions if p["strategy_type"] == strategy_type
    )
    if strat_count >= risk_limits.max_per_strategy_type:
        return False, (
            f"{strategy_type}: {strat_count} positions already "
            f"(max {risk_limits.max_per_strategy_type})"
        )

    # Portfolio delta
    total_delta = sum(p["delta"] for p in current_positions) + trade_delta
    if abs(total_delta) > risk_limits.max_portfolio_delta:
        return False, (
            f"Portfolio delta would be {total_delta:.0f} "
            f"(max {risk_limits.max_portfolio_delta})"
        )

    # Concentration: positions in this underlying / total (rough proxy)
    if total_positions > 0:
        concentration_pct = ((underlying_count + 1) / (total_positions + 1)) * 100
        if concentration_pct > risk_limits.max_concentration_pct:
            return False, (
                f"{ticker} concentration {concentration_pct:.0f}% "
                f"> max {risk_limits.max_concentration_pct}%"
            )

    return True, "Portfolio risk OK"


def size_position(
    trade_spec, capital: float, size_factor: float, risk_limits: PortfolioRiskLimits
) -> Tuple[int, str]:
    """3e: Calculate number of contracts based on risk_per_trade_pct from config."""
    risk_per_contract = _parse_risk_per_spread(trade_spec)
    if not risk_per_contract or risk_per_contract <= 0:
        return 0, "Cannot determine risk per contract"

    risk_pct = risk_limits.risk_per_trade_pct / 100
    max_risk = capital * risk_pct * size_factor
    contracts = int(max_risk / risk_per_contract)
    if contracts <= 0:
        return 0, (
            f"Too expensive: risk/contract ${risk_per_contract:.0f} > "
            f"adjusted budget ${max_risk:.0f} ({risk_limits.risk_per_trade_pct}% x {size_factor:.0%})"
        )

    return contracts, f"{contracts} contracts (${risk_per_contract:.0f}/ea, budget ${max_risk:.0f} @ {risk_limits.risk_per_trade_pct}%)"


# ---------------------------------------------------------------------------
# Step 4: TradeSpec → LegInput[]
# ---------------------------------------------------------------------------
def tradespec_to_legs(ticker: str, trade_spec, quantity: int) -> List[LegInput]:
    """Convert TradeSpec legs to LegInput[] for TradeBookingService."""
    leg_inputs = []
    for leg in trade_spec.legs:
        # Build DXLink symbol: .{TICKER}{YYMMDD}{P/C}{strike}
        exp = leg.expiration
        yy = f"{exp.year % 100:02d}"
        mm = f"{exp.month:02d}"
        dd = f"{exp.day:02d}"
        pc = "C" if leg.option_type.lower() == "call" else "P"
        strike_str = str(int(leg.strike)) if leg.strike == int(leg.strike) else str(leg.strike)
        symbol = f".{ticker}{yy}{mm}{dd}{pc}{strike_str}"

        # Quantity sign: BTO → positive, STO → negative
        leg_qty = leg.quantity if hasattr(leg, "quantity") else 1
        is_sell = (
            leg.action == LegAction.SELL_TO_OPEN
            if hasattr(leg.action, "value") and hasattr(LegAction, "SELL_TO_OPEN")
            else str(leg.action).upper() in ("STO", "SELL_TO_OPEN")
        )
        signed_qty = -abs(leg_qty * quantity) if is_sell else abs(leg_qty * quantity)

        leg_inputs.append(LegInput(streamer_symbol=symbol, quantity=signed_qty))

    return leg_inputs


# ---------------------------------------------------------------------------
# Step 5: Book trade
# ---------------------------------------------------------------------------
def book_trade(
    ticker: str,
    strategy_type: str,
    legs: List[LegInput],
    rationale: str,
    score: float,
    verdict: str,
    booking_svc: TradeBookingService,
) -> Optional[str]:
    """Book a trade to tastytrade_whatif. Returns trade_id or None."""
    result = booking_svc.book_whatif_trade(
        underlying=ticker,
        strategy_type=strategy_type,
        legs=legs,
        portfolio_name=PORTFOLIO_NAME,
        trade_source=dm.TradeSource.TRADER_SCRIPT,
        rationale=rationale,
        notes=f"Score: {score:.2f}, Verdict: {verdict}",
    )
    if result.success:
        print(f"  BOOKED: trade_id={result.trade_id} entry=${result.entry_price:.2f}")
        if result.total_greeks:
            g = result.total_greeks
            print(f"          delta={g.get('delta', 0):.2f} theta={g.get('theta', 0):.2f} "
                  f"vega={g.get('vega', 0):.2f}")
        return result.trade_id
    else:
        print(f"  BOOKING FAILED: {result.error}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Morning trading workflow. Returns 0=booked, 1=no trades, 2=all rejected."""
    ma = MarketAnalyzer(data_service=DataService())

    # Load risk config
    loader = RiskConfigLoader()
    config = loader.load()
    portfolio_cfg = config.portfolios.get_by_name(PORTFOLIO_NAME)
    if not portfolio_cfg:
        print(f"ERROR: Portfolio '{PORTFOLIO_NAME}' not found in risk_config.yaml")
        return 2
    risk_limits = portfolio_cfg.risk_limits
    capital = portfolio_cfg.initial_capital

    # =======================================================================
    # STEP 1: MORNING CHECK
    # =======================================================================
    print("=" * 70)
    print("STEP 1: MORNING CHECK — Daily Plan")
    print("=" * 70)

    plan = ma.plan.generate()
    print(f"Date:        {plan.plan_for_date}")
    print(f"Day Verdict: {plan.day_verdict.value.upper()}")
    for r in plan.day_verdict_reasons:
        print(f"  -> {r}")
    print(f"Risk Budget: max {plan.risk_budget.max_new_positions} positions, "
          f"${plan.risk_budget.max_daily_risk_dollars} daily risk, "
          f"sizing {plan.risk_budget.position_size_factor:.0%}")
    print(f"Total trades found: {plan.total_trades}")

    if plan.expiry_events:
        print("\nEXPIRY TODAY:")
        for e in plan.expiry_events:
            tickers = ", ".join(e.tickers[:5])
            print(f"  {e.label} - {tickers}")

    if plan.day_verdict.value in ("no_trade", "avoid"):
        print("\nVERDICT: NO TRADING TODAY. System says stand down.")
        print(f"Summary: {plan.summary}")
        return 1

    # =======================================================================
    # STEP 2: SHOW TRADE IDEAS
    # =======================================================================
    print()
    print("=" * 70)
    print("STEP 2: TRADE IDEAS (GO/CAUTION only)")
    print("=" * 70)

    candidates = []
    for horizon, trades in plan.trades_by_horizon.items():
        if not trades:
            continue
        print(f"\n--- {horizon.upper()} ({len(trades)} trades) ---")
        for t in trades:
            if t.verdict.lower() not in ("go", "caution"):
                continue
            spec = t.trade_spec
            legs_str = _format_legs(spec)
            max_loss = spec.max_loss_desc if spec and spec.max_loss_desc else "?"
            max_profit = spec.max_profit_desc if spec and spec.max_profit_desc else "?"
            risk_per = f"risk/spread={spec.max_risk_per_spread}" if spec and spec.max_risk_per_spread else ""
            print(f"  #{t.rank} {t.ticker:6s} {t.strategy_type:20s} "
                  f"{t.verdict.upper():7s} score={t.composite_score:.2f}")
            print(f"         legs: {legs_str}")
            print(f"         P&L:  profit={max_profit}  loss={max_loss} {risk_per}")
            candidates.append(t)

    if not candidates:
        print("\nNo GO/CAUTION trades. Sit on hands today.")
        print(f"Summary: {plan.summary}")
        return 1

    # =======================================================================
    # STEP 3: RISK GATE
    # =======================================================================
    print()
    print("=" * 70)
    print("STEP 3: RISK GATE — Multi-Layer Checks")
    print("=" * 70)

    current_positions = _get_current_positions(PORTFOLIO_NAME)
    print(f"Current open positions: {len(current_positions)}")

    passing_trades = []
    for t in candidates:
        spec = t.trade_spec
        ticker = t.ticker
        strategy = t.strategy_type
        print(f"\n--- {ticker} {strategy} (score={t.composite_score:.2f}) ---")

        # 3a: Structure check
        ok, msg = check_structure(spec, strategy)
        print(f"  [{'PASS' if ok else 'REJECT'}] Structure: {msg}")
        if not ok:
            continue

        # 3b: Defined risk check
        ok, msg = check_defined_risk(strategy, spec.legs if spec else [], risk_limits)
        print(f"  [{'PASS' if ok else 'REJECT'}] Defined Risk: {msg}")
        if not ok:
            continue

        # 3c: Position-level risk
        ok, msg = check_position_risk(spec, capital, risk_limits)
        print(f"  [{'PASS' if ok else 'REJECT'}] Position Risk: {msg}")
        if not ok:
            continue

        # 3d: Portfolio-level risk
        ok, msg = check_portfolio_risk(ticker, strategy, risk_limits, current_positions)
        print(f"  [{'PASS' if ok else 'REJECT'}] Portfolio Risk: {msg}")
        if not ok:
            continue

        # 3e: Position sizing
        contracts, msg = size_position(spec, capital, plan.risk_budget.position_size_factor, risk_limits)
        print(f"  [{'PASS' if contracts > 0 else 'REJECT'}] Sizing: {msg}")
        if contracts <= 0:
            continue

        passing_trades.append((t, contracts))

    if not passing_trades:
        print("\nAll trades rejected by risk gate.")
        return 2

    # =======================================================================
    # STEP 4 + 5: CONVERT & BOOK
    # =======================================================================
    print()
    print("=" * 70)
    print("STEP 4-5: CONVERT LEGS & BOOK TO WHATIF")
    print("=" * 70)

    booking_svc = TradeBookingService()
    booked = 0

    for t, contracts in passing_trades:
        spec = t.trade_spec
        ticker = t.ticker
        strategy = t.strategy_type
        print(f"\n--- Booking: {ticker} {strategy} x{contracts} ---")

        leg_inputs = tradespec_to_legs(ticker, spec, contracts)
        for li in leg_inputs:
            print(f"  Leg: {li.streamer_symbol} qty={li.quantity}")

        trade_id = book_trade(
            ticker=ticker,
            strategy_type=strategy,
            legs=leg_inputs,
            rationale=t.rationale,
            score=t.composite_score,
            verdict=t.verdict,
            booking_svc=booking_svc,
        )
        if trade_id:
            booked += 1

    # =======================================================================
    # STEP 6: SUMMARY
    # =======================================================================
    print()
    print("=" * 70)
    print("STEP 6: SUMMARY")
    print("=" * 70)
    print(f"  Candidates:  {len(candidates)}")
    print(f"  Passed gate: {len(passing_trades)}")
    print(f"  Booked:      {booked}")
    print(f"  Rejected:    {len(candidates) - len(passing_trades)}")
    print(f"  Capital:     ${capital:,.0f}")
    print(f"  Risk/trade:  {risk_limits.risk_per_trade_pct}%")
    print(f"\n  {plan.summary}")

    return 0 if booked > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
