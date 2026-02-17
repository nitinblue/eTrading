# CoTrader Test Playbook
> A guided walkthrough of all features. Run these tests in order.
> Each test explains what you're doing, what to expect, and how to verify success.
>
> **Prerequisites**: Python installed, terminal open in the project folder (`C:\Users\nitin\PythonProjects\eTrading`)

---

## Setup (One-time)

### Test 1: Database Setup
**What**: Creates all database tables from scratch.
```bash
python -m trading_cotrader.scripts.setup_database
```
**Expect**: No errors. You should see table creation messages.

### Test 2: Initialize Portfolios
**What**: Creates 10 portfolios (5 real brokers + 5 WhatIf mirrors).
```bash
python -m trading_cotrader.cli.init_portfolios --dry-run
```
**Expect**: Dry-run output showing 10 portfolios that would be created. No actual changes.

```bash
python -m trading_cotrader.cli.init_portfolios
```
**Expect**: 10 portfolios created. You should see names like "Tastytrade", "Fidelity IRA", "Zerodha", "Stallion Asset", and their WhatIf mirrors.

### Test 3: Load Stallion Holdings
**What**: Loads 29 equity holdings from Stallion managed fund (read-only).
```bash
python -m trading_cotrader.cli.load_stallion --dry-run
```
**Expect**: Preview of 29 equity positions. No actual changes.

```bash
python -m trading_cotrader.cli.load_stallion
```
**Expect**: 29 positions created.

---

## Automated Tests

### Test 4: Unit Tests
**What**: Runs all 157 automated tests (pricing, Greeks, trade booking, portfolio management, risk, etc.)
```bash
python -m pytest trading_cotrader/tests/ -v
```
**Expect**: All tests pass (green). Some deprecation warnings are OK to ignore.
**Key thing to check**: The last line should say `157 passed`.

### Test 5: Integration Harness
**What**: Runs 17-step integration test covering the full pipeline.
```bash
python -m trading_cotrader.harness.runner --skip-sync
```
**Expect**: 14-15 steps pass, 1-2 skip (those need a live broker connection). Look for the summary at the end.

---

## Screeners & Recommendations

### Test 6: VIX Screener
**What**: Runs the VIX regime screener on SPY and QQQ to find trade opportunities.
```bash
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY,QQQ --no-broker
```
**Expect**: Recommendations generated based on current VIX level. You'll see strategy suggestions with confidence scores.

### Test 7: LEAPS Screener
**What**: Screens for long-term options (LEAPS) opportunities.
```bash
python -m trading_cotrader.cli.run_screener --screener leaps --symbols AAPL,MSFT --no-broker
```
**Expect**: LEAPS-specific recommendations (these are pickier — may produce zero results, which is fine).

### Test 8: All Screeners
**What**: Runs VIX + IV rank + LEAPS screeners together.
```bash
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker
```
**Expect**: Combined output from all screeners. More results than a single screener.

### Test 9: Macro Short-Circuit
**What**: Tests that screeners are blocked when macro conditions are bad.
```bash
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook uncertain --expected-vol extreme --no-broker
```
**Expect**: Should say something like "risk_off" or "macro blocked" — no recommendations generated. This is correct! The system refuses to screen when conditions are dangerous.

### Test 10: List Recommendations
**What**: Lists all pending recommendations waiting for your decision.
```bash
python -m trading_cotrader.cli.accept_recommendation --list --no-broker
```
**Expect**: A list of pending recommendations from the screener runs above. Each has an ID, underlying, strategy, and confidence score.

---

## Trade Booking

### Test 11: Book a WhatIf Trade
**What**: Books a simulated trade from a template file.
```bash
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/trade_template.json --no-broker
```
**Expect**: Trade booked successfully with a trade ID. This is a WhatIf trade — no real money involved.

---

## Portfolio Evaluation

### Test 12: Evaluate Open Positions
**What**: Checks open trades for exit/roll/adjustment signals.
```bash
python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker --dry-run
```
**Expect**: Lists any open trades and whether they should be closed, rolled, or adjusted. If no open trades, it'll say so. Dry-run means no changes are made.

---

## Workflow Engine (The Main Event)

### Test 13: Single Cycle Test
**What**: Runs one complete cycle of the workflow engine: boot → macro check → screening → recommendations → monitoring → reporting.
```bash
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock
```
**Expect**: You'll see the state machine progress through each state:
1. `=== WORKFLOW BOOT ===`
2. Calendar check
3. Market data (mock)
4. Portfolio state
5. Safety check (Guardian)
6. Macro assessment
7. Screening
8. Recommendations (if any)
9. Monitoring
10. Reporting
11. Back to IDLE

This should complete in ~10-30 seconds.

### Test 14: Web Dashboard
**What**: Starts the workflow engine with the web approval dashboard.
```bash
python -m trading_cotrader.runners.run_workflow --web --port 8080 --no-broker --mock
```
**Expect**:
1. Workflow engine starts and runs through its boot cycle
2. Web server starts on port 8080
3. Open your browser to **http://localhost:8080**

**What you'll see in the browser:**
- Dark-themed dashboard
- **Header**: "COTRADER approval dashboard" with a green/red connection dot
- **Status bar**: Shows current workflow state, cycle count, VIX, open trades
- **Pending Recommendations table**: Shows trade recommendations with columns:
  - Type (ENTRY/EXIT/ROLL/ADJUST)
  - Underlying (SPY, QQQ, etc.)
  - Strategy
  - **Portfolio** (which account it targets)
  - **Risk** (DEFINED or UNDEFINED)
  - **Max Loss** (calculated from spread width)
  - Confidence score (color-coded bar)
  - Rationale
  - Age
  - Action buttons: Approve / Reject / Defer

**Things to try in the dashboard:**
1. Click **Approve** on a recommendation — a modal appears with portfolio dropdown and notes field
2. Click **Reject** — a modal appears asking for a reason
3. Click **Defer** — moves the recommendation to later
4. Click **Refresh** to manually refresh data (auto-refreshes every 15 seconds)
5. Look at the **Recent Decisions** section at the bottom — shows your approvals/rejections

**To stop**: Press `Ctrl+C` in the terminal.

### Test 15: Interactive CLI Mode
**What**: Starts continuous workflow with interactive commands.
```bash
python -m trading_cotrader.runners.run_workflow --paper --no-broker --mock
```
**Expect**: Engine starts and enters monitoring state. You can type commands:

| Command | What it does |
|---------|-------------|
| `status` | Shows current state, cycle count, VIX, open trades |
| `list` | Lists pending entry recommendations + exit signals |
| `approve <id>` | Approves a recommendation (use first 8 chars of ID) |
| `reject <id>` | Rejects a recommendation |
| `defer <id>` | Defers for later |
| `halt` | Emergency halt — stops all trading |
| `resume --rationale "testing"` | Resumes after halt (requires a reason) |
| `help` | Shows all available commands |

**To stop**: Press `Ctrl+C`.

---

## Multi-Broker Features

### Test 16: Fidelity CSV Import
**What**: Imports positions from a Fidelity CSV export file.
**Note**: You need an actual Fidelity CSV file for this. If you don't have one, skip this test.
```bash
python -m trading_cotrader.cli.sync_fidelity --file Portfolio_Positions.csv
```
**Expect**: Positions loaded from CSV into the Fidelity portfolio.

---

## Verification Checklist

After running the tests, verify:

- [ ] Test 4: `157 passed` (unit tests)
- [ ] Test 5: 14+ steps pass (harness)
- [ ] Test 6-8: Screeners produce recommendations
- [ ] Test 9: Macro short-circuit blocks screening (expected!)
- [ ] Test 10: Recommendations listed
- [ ] Test 11: Trade booked successfully
- [ ] Test 13: Single cycle completes without errors
- [ ] Test 14: Web dashboard loads at http://localhost:8080
- [ ] Test 14: Dashboard shows Portfolio, Risk, Max Loss columns
- [ ] Test 14: Approve/Reject/Defer buttons work
- [ ] Test 15: CLI commands (status, list, help) work

---

## Troubleshooting

**"Module not found" errors**: Make sure you're in the project root directory (`C:\Users\nitin\PythonProjects\eTrading`).

**Database errors**: Run `python -m trading_cotrader.scripts.setup_database` to recreate tables.

**Port 8080 already in use**: Use a different port: `--port 8081`

**"No recommendations"**: This is normal! The screeners only recommend when market conditions match. Try running with different symbols or use `--mock` flag.

**Tests fail with import errors**: Make sure all dependencies are installed: `pip install -r requirements.txt`
