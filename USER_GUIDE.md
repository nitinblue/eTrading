# Trading CoTrader — User Guide

*For Aarti (and anyone running this system)*

---

## What This System Does

This is an automated trading assistant. It:

1. **Scans the market** every 30 minutes for trading opportunities
2. **Proposes trades** (iron condors, spreads, LEAPs) with full risk sizing
3. **Books them into paper trading desks** so you can watch performance
4. **Monitors open trades** for profit targets and stop losses
5. **Auto-closes trades** when targets hit or risk limits breach
6. **Learns from outcomes** to get better over time

You have **3 funded paper trading desks** (no real money at risk):

| Desk | Capital | What it trades | Profit Target | Stop Loss |
|------|---------|---------------|---------------|-----------|
| **0DTE** | $10,000 | Same-day SPY/QQQ/IWM | 90% of credit | None (risk is capped by wings) |
| **Medium** | $10,000 | ~45 DTE on top 10 stocks | 50% of credit | 2x credit received |
| **LEAPs** | $20,000 | 6-24 month options on blue chips | 100% gain | 50% loss |

---

## Starting the System

### Daily Start (with broker connection for live quotes)
```
python -m trading_cotrader.runners.run_workflow --paper --web
```

### Without broker (for testing — uses cached/mock data)
```
python -m trading_cotrader.runners.run_workflow --paper --no-broker --web
```

When it starts, you'll see:
```
============================================================
TRADING WORKFLOW ENGINE — PAPER mode, LIVE data
============================================================

Running initial boot cycle...
Workflow engine running. Type 'help' for commands, 'quit' to stop.
Web dashboard active at http://localhost:8080

>
```

The `>` prompt is where you type commands.

---

## Daily Workflow — What You Actually Do

### Morning (system does this automatically on boot)

The system automatically:
- Syncs positions from TastyTrade
- Scans the market watchlist
- Generates trade proposals
- Books approved trades to the right desk
- Marks existing trades to current prices

**You don't need to do anything.** Just start it and let it run.

### During the Day

Every 30 minutes the system runs a cycle: scan → propose → book → mark → check exits → auto-close.

**Check on it whenever you want:**

```
> perf                    ← See how all 3 desks are doing
> positions               ← See all open trades
> exits                   ← Check which trades need attention
```

### If You Want to Close Something Early

```
> close auto              ← Close everything that hit profit/stop targets
> close abc123            ← Close a specific trade (use the trade ID from 'positions')
```

### End of Day

```
> perf                    ← Review the day's performance
> learn                   ← Run ML analysis to update patterns
> quit                    ← Stop the engine
```

---

## Command Reference

### The Core Trading Flow

| Command | What it does |
|---------|-------------|
| `scan` | Force a market scan right now (normally runs automatically) |
| `propose` | See what trades Maverick wants to make |
| `deploy` | Manually book proposals (normally auto-booked) |
| `mark` | Update all trade prices to current market |
| `exits` | Check which trades hit profit/stop/DTE rules |
| `close auto` | Close all trades that triggered exit rules |
| `close <trade_id>` | Close one specific trade |

### Checking Performance

| Command | What it does |
|---------|-------------|
| `perf` | Performance dashboard for all 3 desks |
| `perf 0dte` | Just the 0DTE desk |
| `perf medium` | Just the medium-term desk |
| `perf leaps` | Just the LEAPs desk |
| `learn` | ML/RL analysis — best/worst patterns, insights |
| `learn 30` | Analyze only last 30 days |

### Viewing Positions and Portfolios

| Command | What it does |
|---------|-------------|
| `positions` | All open trades with Greeks and P&L |
| `portfolios` | All portfolios: capital, Greeks, P&L totals |
| `greeks` | Portfolio Greeks vs their risk limits |
| `capital` | How much capital is deployed vs idle |
| `trades` | Today's executed trades |
| `risk` | Risk dashboard: VaR, macro, circuit breakers |
| `status` | Engine state: cycle count, trading day, VIX |

### Going Live (Sending a Paper Trade to Real Broker)

When you see a paper trade performing well and want to place it for real:

```
> golive abc123            ← Preview: shows you legs, margin impact, fees
> golive abc123 --confirm  ← PLACES THE REAL ORDER on TastyTrade
```

**Important:** `golive` without `--confirm` is always safe — it's just a preview. Only `--confirm` sends the order.

```
> orders                   ← Check if your live orders filled
```

### Emergency Controls

| Command | What it does |
|---------|-------------|
| `halt` | Stop all trading immediately |
| `resume` | Resume trading (type a reason) |

---

## How the System Thinks

### Scout (the analyst)
Scans the market watchlist, detects regimes (trending/mean-reverting, high/low volatility), finds opportunities. Uses MarketAnalyzer — no opinions, just data.

### Maverick (the trader)
Takes Scout's ranked ideas and decides:
- Is this strategy allowed for this desk?
- Do we have room for more positions?
- Do we already have a trade on this ticker?
- Is the black swan gate clear?
- Is the ML score positive? (learned from past trades)
- How many contracts? (2% of capital per trade max)

Then routes to the right desk by DTE: 0-1 days → 0DTE desk, 7-179 → Medium, 180+ → LEAPs.

### Sentinel (the risk manager)
Enforces circuit breakers: daily loss limit, weekly loss limit, VIX halt threshold, max drawdown per desk.

### Steward (the accountant)
Tracks capital: what's deployed, what's idle, Greeks vs limits.

---

## Exit Rules — How Trades Get Closed

### 0DTE Desk
- **Profit target:** Close when 90% of the credit received is captured
- **Stop loss:** None — these are defined-risk (iron condors, verticals). Max loss = wing width
- **DTE:** Holds to expiration (same day)

### Medium-Term Desk
- **Profit target:** Close when 50% of credit captured
- **Stop loss:** Close if loss reaches 2x the credit received
- **DTE exit:** Close if less than 21 days to expiration

### LEAPs Desk
- **Profit target:** Close at 100% gain
- **Stop loss:** Close at 50% loss
- **DTE exit:** Close if less than 90 days to expiration

All exit rules are checked every 30-minute cycle. **URGENT** exits (stop loss, expired) auto-close immediately. Profit targets auto-close too.

---

## Understanding the Performance Dashboard

```
> perf
```

```
  ┌─ DESK_0DTE ──────────────────────────────────────
  │  Capital: $10,000  →  Equity: $10,850  (Return: +8.5%)
  │  Trades: 12  (W:8 L:3 B:1)
  │  Win Rate: 66.7%  Profit Factor: 2.15  Expectancy: +$70.83
  │  Sharpe: 1.85  Max Drawdown: 12.3%
  │  Open Positions: 2
  └───────────────────────────────────────────────────
```

**What the numbers mean:**

| Metric | Good | Bad | What it means |
|--------|------|-----|---------------|
| **Win Rate** | >55% | <45% | % of trades that made money |
| **Profit Factor** | >1.5 | <1.0 | Dollars won / dollars lost. Below 1.0 = losing money |
| **Expectancy** | Positive | Negative | Average P&L per trade. Must be positive to make money. |
| **Sharpe** | >1.0 | <0 | Risk-adjusted return. Higher = more consistent |
| **Max Drawdown** | <15% | >25% | Worst peak-to-trough loss. How bad can it get? |

---

## The "Go Live" Decision

After watching paper trades for 5 days:

1. Run `perf` — are all 3 desks profitable? Is Sharpe > 1?
2. Run `learn` — are the top patterns making money consistently?
3. Pick the best-performing desk
4. When you see a new trade booked, check it: `positions`
5. If it looks good: `golive <trade_id>` to preview
6. If the preview looks right: `golive <trade_id> --confirm`

**Start small.** One trade at a time. The system will always paper-trade in parallel so you can compare.

---

## Troubleshooting

### "No proposals to deploy"
The market didn't have good enough opportunities. This is fine. The system has strict gates — it only trades when conditions align. Check back next cycle (30 min).

### "Trade not found"
Trade IDs are long UUIDs. You only need the first 6-8 characters: `close abc123` works.

### "Broker not connected"
Start with `--paper --web` (not `--no-broker`). The system needs the TastyTrade connection for live quotes.

### "MarketAnalyzer unavailable"
Run: `pip install --force-reinstall --no-deps -e ../market_analyzer`

### System seems stuck
Type `status` to see current state. If it says HALTED, type `resume` with a reason.

---

## Quick Reference Card

```
DAILY ROUTINE
─────────────────────────────────────────
Start:     python -m trading_cotrader.runners.run_workflow --paper --web
Check:     perf | positions | exits
Close:     close auto
Review:    perf | learn
Stop:      quit

GOING LIVE
─────────────────────────────────────────
Preview:   golive <id>
Execute:   golive <id> --confirm
Check:     orders

DESK SHORTCUTS
─────────────────────────────────────────
0dte       → desk_0dte    ($10K, same-day)
med        → desk_medium  ($10K, ~45 DTE)
leaps      → desk_leaps   ($20K, 6-24 months)

ALL COMMANDS
─────────────────────────────────────────
scan        propose     deploy      mark
exits       close       perf        learn
positions   portfolios  greeks      capital
trades      risk        status      golive
orders      halt        resume      help
```
