# Market Analyzer Requirements from eTrading (CoTrader)
# Date: 2026-03-09

## CONTEXT

eTrading (CoTrader) is the trading workflow / portfolio management / risk management layer.
MarketAnalyzer is the market intelligence / decision-making engine.

**Principle:** All trading decision-making lives in market_analyzer. eTrading only does:
- Portfolio-level checks (capital, utilization, max positions)
- Risk-level checks (max delta, circuit breakers)
- Trade-level checks (strategy allowed for portfolio, duplicate prevention)
- Execution (booking, persistence, P&L tracking)

---

## WHAT'S WORKING WELL

These are fully consumed by eTrading today:

| Service | eTrading Consumer | Status |
|---------|------------------|--------|
| `ma.regime.detect(ticker)` | Scout.populate() → ResearchContainer | OK |
| `ma.technicals.snapshot(ticker)` | Scout.populate() → ResearchContainer | OK |
| `ma.phase.detect(ticker)` | Scout.populate() → ResearchContainer | OK |
| `ma.opportunity.assess_*(ticker)` | Scout.populate() (4 of 11 assessments) | Partial |
| `ma.levels.analyze(ticker)` | Scout.populate() → ResearchContainer | OK |
| `ma.fundamentals.fetch(ticker)` | Scout.populate() → ResearchContainer | OK |
| `ma.macro.calendar()` | Scout.populate() → ResearchContainer | OK |
| `ma.screening.scan(tickers)` | Scout.run() → context['screening_candidates'] | OK |
| `ma.ranking.rank(tickers)` | Scout.run() → context['ranking'] | OK |
| `ma.black_swan.alert()` | Scout.run() → context['black_swan_level'] | OK |
| `ma.context.assess()` | Scout.run() → context['market_environment'] | OK |

---

## REQUIREMENTS: What eTrading Needs Next

### REQ-1: DXLink Streamer Symbols on TradeSpec [HIGH]

**Problem:** TradeSpec.streamer_symbols produces OCC format: `"SPY   260327P00580000"`
eTrading's TradeBookingService expects DXLink format: `".SPY260327P580"`

market_analyzer already has `leg_to_streamer_symbol_with_ticker(ticker, leg)` in
`broker/tastytrade/market_data.py` that produces the right format. But:
1. It's buried in the broker module, not on TradeSpec itself
2. TradeSpec doesn't expose DXLink-format symbols

**Ask:** Add a property to TradeSpec:
```python
@property
def dxlink_symbols(self) -> list[str]:
    """DXLink streamer symbols: ['.SPY260327P580', ...]."""
    return [
        f".{self.ticker}{leg.expiration.strftime('%y%m%d')}"
        f"{'C' if leg.option_type == 'call' else 'P'}"
        f"{int(leg.strike)}"
        for leg in self.legs
    ]
```

Also add a `signed_quantities` property that respects action (BTO=positive, STO=negative):
```python
@property
def signed_quantities(self) -> list[int]:
    """Quantities with sign: positive=buy, negative=sell."""
    return [
        leg.quantity if leg.action == LegAction.BTO else -leg.quantity
        for leg in self.legs
    ]
```

**Why:** This is the bridge between market_analyzer's trade proposals and eTrading's booking system.

---

### REQ-2: Position Sizing in TradeSpec [HIGH]

**Problem:** All TradeSpec legs come with `quantity=1` (default). market_analyzer knows the
strategy structure and risk, but doesn't size based on account capital.

**Ask:** Add a `size()` or `with_sizing()` method to TradeSpec:
```python
def with_sizing(self, account_capital: float, risk_pct: float = 0.02) -> 'TradeSpec':
    """Return a copy with leg quantities sized for the given capital and risk tolerance.

    For defined-risk (iron condor, vertical, etc.):
        max_risk = wing_width * 100
        contracts = floor(account_capital * risk_pct / max_risk)

    For undefined-risk: use margin estimate from strategy service.
    """
```

**Alternatively:** If this belongs on the strategy service:
```python
sized_spec = ma.strategy.size(trade_spec, capital=10000, risk_pct=0.02)
```

eTrading will pass: portfolio capital ($10K), risk_per_trade_pct (from risk_config.yaml).
market_analyzer returns: TradeSpec with quantities filled in.

---

### REQ-3: All 11 Opportunity Assessments in Ranking [MEDIUM]

**Current:** Scout.populate() only calls 4 assessments: zero_dte, leap, breakout, momentum.
The ranking service assesses all 11 strategy types.

**Ask:** Confirm ranking.rank() already calls ALL 11 assessments internally (iron_condor,
iron_butterfly, calendar, diagonal, ratio_spread, earnings, mean_reversion + the 4 above).
If so, no change needed — eTrading will consume them from the ranking results.

If not: ensure ranking.rank() assesses all relevant strategies per ticker, so the top_trades
list represents the full opportunity set.

---

### REQ-4: Exit Rule Monitoring Signal [MEDIUM]

**Problem:** TradeSpec carries exit rules (profit_target_pct, stop_loss_pct, exit_dte).
But after a trade is booked, eTrading needs to check: "given current price, should this
trade be closed?"

**Ask:** Add an exit check function:
```python
result = ma.exit.check(
    trade_spec=original_spec,
    entry_price=1.50,      # credit received
    current_price=0.75,    # current spread price
    current_dte=12,        # days remaining
)
# Returns: ExitSignal(should_exit=True, reason="profit_target", pnl_pct=0.50)
```

**Or simpler:** This is just math. eTrading can do it locally since it's trade-level
management, not market intelligence. The exit rules from TradeSpec are sufficient.

**Decision:** eTrading will handle exit monitoring locally — it's portfolio/trade management,
not market analysis. No change needed in market_analyzer.

---

### REQ-5: Watchlist-Aware Strategy Filtering [LOW]

**Current:** ranking.rank(tickers) ranks ALL 11 strategy types for every ticker.
Some strategies don't apply to all tickers (e.g., zero_dte only for SPX/SPY).

**Ask:** Ensure ranking already filters out irrelevant strategies per ticker. For example:
- ZERO_DTE: only SPX, SPY (high liquidity, 0DTE chains)
- EARNINGS: only tickers with upcoming earnings within 30 days
- LEAP: only tickers with 6+ month chains

If this filtering already happens in the assess_* methods (returning NO_GO), that's fine.

---

### REQ-6: Batch Ranking for Performance [LOW]

**Current:** ranking.rank() works well for the watchlist (~20 tickers).
As watchlist grows, might need performance optimization.

**Ask:** No immediate change. Just noting that if we scale to 100+ tickers,
we may need: `ma.ranking.rank_batch(tickers, strategies, max_results=20)` with
internal parallelism.

---

## SUMMARY

| Req | Priority | Description | Effort |
|-----|----------|-------------|--------|
| REQ-1 | HIGH | `dxlink_symbols` + `signed_quantities` on TradeSpec | Small |
| REQ-2 | HIGH | Position sizing method on TradeSpec or strategy service | Medium |
| REQ-3 | MEDIUM | Confirm all 11 assessments in ranking | Verify |
| REQ-4 | MEDIUM | Exit monitoring — DECIDED: eTrading handles locally | None |
| REQ-5 | LOW | Strategy filtering per ticker in ranking | Verify |
| REQ-6 | LOW | Batch ranking performance | Future |

**Critical path:** REQ-1 unblocks the Maverick → TradeBookingService bridge immediately.
REQ-2 unblocks capital-aware position sizing.
