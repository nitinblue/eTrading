# Trading Plan Templates

Pre-filled trade specifications organized by cadence. Populate the night before, execute next day.
Each file is a complete, ready-to-book trade with entry conditions, P&L drivers, and manual Greeks.

## Book a template

```bash
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/<filename>.json --no-broker
```

## 0DTE Templates (same-day expiry)

| File | Strategy | Underlying | Portfolio |
|------|----------|------------|-----------|
| `0dte_iron_butterfly_spy.json` | Iron Butterfly | SPY | high_risk |

**When:** 9:45-11:00 AM ET, after morning volatility settles. Close by 2:30 PM.
**Avoid:** FOMC, CPI/PPI, quad witching, ex-dividend days.

## Weekly Income Templates (5-14 DTE)

| File | Strategy | Underlying | Portfolio | Entry Day | Source |
|------|----------|------------|-----------|-----------|--------|
| `weekly_call_calendar_spx_7_9.json` | Call Calendar 7/9 DTE | SPX | medium_risk | Wednesday 3 PM | OptionsKit: 82% WR, 64% CAGR |
| `weekly_call_calendar_spx_9_12.json` | Call Calendar 9/12 DTE | SPX | medium_risk | Wednesday 2 PM | OptionsKit: 80% WR, 51% CAGR |
| `weekly_put_diagonal_qqq.json` | Put Diagonal 7/10 DTE | QQQ | medium_risk | Friday 1:30 PM | OptionsKit: 88% WR, 20% CAGR |
| `weekly_double_calendar_spy.json` | Double Calendar | SPY | medium_risk | Wednesday 2-3 PM | Neutral weekly income |

**Futures expiry awareness:** Skip quarterly expiry weeks (Mar/Jun/Sep/Dec 3rd Friday). Align short leg to nearest weekly expiry. Roll front leg day BEFORE expiry.

## Monthly Income Templates (30-60 DTE)

| File | Strategy | Legs | Underlying | Portfolio |
|------|----------|------|------------|-----------|
| `monthly_iron_condor_spy.json` | Iron Condor | 4 | SPY | high_risk |
| `monthly_iron_butterfly_spy.json` | Iron Butterfly | 4 | SPY | high_risk |
| `monthly_vertical_spread_spy.json` | Vertical Spread | 2 | SPY | medium_risk |
| `monthly_calendar_spread_spy.json` | Calendar Spread | 2 | SPY | medium_risk |
| `monthly_diagonal_pmcc_spy.json` | Diagonal / PMCC | 2 | SPY | medium_risk |
| `monthly_straddle_spy.json` | Short Straddle | 2 | SPY | high_risk |
| `monthly_strangle_spy.json` | Short Strangle | 2 | SPY | high_risk |
| `monthly_butterfly_spy.json` | Long Butterfly | 3 | SPY | high_risk |
| `monthly_condor_spy.json` | Long Condor | 4 | SPY | high_risk |
| `monthly_ratio_spread_spy.json` | Ratio Spread (1x2) | 2 | SPY | model_portfolio |
| `monthly_jade_lizard_spy.json` | Jade Lizard | 3 | SPY | model_portfolio |
| `monthly_big_lizard_spy.json` | Big Lizard | 3 | SPY | model_portfolio |
| `monthly_single_spy.json` | Single (CSP/naked) | 1 | SPY | high_risk |
| `monthly_covered_call_spy.json` | Covered Call | 2 | SPY | core_holdings |
| `monthly_protective_put_spy.json` | Protective Put | 2 | SPY | core_holdings |
| `monthly_collar_spy.json` | Collar | 3 | SPY | core_holdings |

## LEAPS Templates (6-12 months, set-and-forget)

| File | Strategy | Legs | Underlying | Portfolio | Source |
|------|----------|------|------------|-----------|--------|
| `leaps_short_put_nvda.json` | Short Put LEAPS | 1 | NVDA | core_holdings | Ravish: 30-50 delta, min 20% ROI |
| `leaps_covered_call_nvda.json` | LEAPS Covered Call | 2 | NVDA | core_holdings | Ravish: 30% target, 40% on margin |
| `leaps_collar_nvda.json` | Zero-Cost Collar | 3 | NVDA | core_holdings | Ravish: premium-neutral, set & forget |
| `leaps_hybrid_collar_nvda.json` | Hybrid Collar (4-leg) | 4 | NVDA | core_holdings | Ravish: deep OTM put funds wider range |
| `leaps_risk_reversal_nvda.json` | Super Risk Reversal | 3 | NVDA | core_holdings | Ravish: put funds bull call spread |

**Philosophy:** 80% of capital allocation. Like real estate investing — look for good deals. High win rate, minimal management, 20-40% CAGR. Individual top stocks only (not indices).
**When:** Opportunistic — when quality stock is near support + oversold (RSI <30). Not a weekly trade.
**Leverage:** Without leverage = very low risk. With leverage, max 2x. Reduce delta for margin trades.
**Wheel:** If short put assigned → transition to LEAPS covered call → wheel system.

## Custom

| File | Strategy | Underlying | Portfolio |
|------|----------|------------|-----------|
| `custom_combo_spy.json` | Custom multi-leg | SPY | model_portfolio |

## Template Structure

Each JSON file contains:
- `_usage`: CLI command to book this trade
- `underlying`, `strategy_type`, `portfolio_name`: Trade routing
- `entry_conditions`: When to enter (IV rank, market outlook, DTE, delta targets, timing)
- `pnl_drivers`: What drives profit/loss (max profit/loss, primary/secondary drivers, Greeks profile, backtest metrics)
- `legs[]`: Option/stock legs with `streamer_symbol` and `quantity`
- `manual_greeks.legs[]`: Pre-computed Greeks for `--no-broker` mode

## Symbol Format

- `.SPY260417P580` = SPY, expiry 2026-04-17, Put, strike $580
- `.SPX260225C6000` = SPX, expiry 2026-02-25, Call, strike $6000
- `SPY` = equity (100 shares per contract)
- Positive quantity = buy, negative = sell

## Workflow

1. **Night before:** Pick template by cadence. Update strikes/expiry to current market. Fill in rationale.
2. **Morning:** Review entry conditions. Check IV rank, VIX, RSI, regime.
3. **Entry time:** Execute at the specified time (varies by strategy).
4. **Management:** Follow exit rules in `pnl_drivers` section.
