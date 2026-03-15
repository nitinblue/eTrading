# Getting Started — For Priyanka
# CoTrader Setup & Daily Usage Guide
# Last Updated: March 14, 2026

## What Is This?

CoTrader is Nitin's systematic options trading system. It scans markets, finds trades, and manages them automatically. You don't need to make any trading decisions — the system does that. Your role is to start it, monitor it, and occasionally review what it's doing.

**Important:** Right now the system trades in "WhatIf" mode — it finds and tracks trades but does NOT place real orders with the broker. It's proving itself. When the track record is good enough, we promote trades to real.

---

## One-Time Setup (already done on Nitin's machine)

If you need to set up on a new machine:

1. **Install Python 3.12** from python.org
2. **Clone the repo** and create virtual environment:
   ```
   cd C:\Users\nitin\PythonProjects
   git clone <repo-url> eTrading
   cd eTrading
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e ../market_analyzer
   ```
3. **Create `.env` file** in the eTrading folder (ask Nitin for the values):
   ```
   TASTYTRADE_CLIENT_SECRET_PAPER=<ask Nitin>
   TASTYTRADE_REFRESH_TOKEN_PAPER=<ask Nitin>
   TASTYTRADE_CLIENT_SECRET_LIVE=<ask Nitin>
   TASTYTRADE_REFRESH_TOKEN_LIVE=<ask Nitin>
   ```
   **Never share this file or commit it to git.**

---

## Daily Usage

### Starting the System

Open a terminal (Git Bash or Command Prompt) and run:

```bash
cd C:\Users\nitin\PythonProjects\eTrading
.venv\Scripts\activate
python -m trading_cotrader.runners.run_workflow --paper --web
```

This starts:
- The trading engine (scans every 30 minutes automatically)
- The web dashboard at **http://localhost:8080**

**Leave this terminal running.** Don't close it while you want the system active.

### Opening the Dashboard

Open your browser and go to: **http://localhost:8080**

You'll see these pages (sidebar on the left):

| Icon | Page | What To Look At |
|------|------|----------------|
| 🏠 | **Overview** | System philosophy. Read once to understand how it works. |
| 🎯 | **Desks** | **Main page.** 3 trading desks, P&L, action buttons. |
| 📊 | **Research** | Market data. Regime, technicals per ticker. |
| 💻 | **Trading** | Blotter — all positions with Greeks. |
| ❓ | **Manual** | Complete user guide. |

### What To Do Each Day

**Morning (before 9:30 AM ET):**
1. Start the system (command above)
2. Open http://localhost:8080
3. Go to **Desks** page
4. Click **Scan** button — system will scan markets and find trades
5. Watch the proposals appear. Click **Deploy** to book them to WhatIf desks
6. That's it. System runs automatically after this.

**During the day:**
- The system automatically marks positions every 30 minutes
- It auto-closes trades that hit profit targets or stop losses
- You can check the Desks page anytime to see current P&L

**End of day:**
- Check the Desks page for final P&L
- No action needed — system handles everything
- Close the terminal when done (or leave it running overnight)

### CLI Commands (in the terminal)

While the system is running, you can type commands in the terminal:

| Command | What It Does |
|---------|-------------|
| `scan` | Scan markets for new opportunities |
| `propose` | Show what the system wants to trade |
| `deploy` | Book proposed trades to WhatIf |
| `mark` | Update prices on open trades |
| `exits` | Check if any trade should close |
| `report` | Daily P&L report |
| `health` | Check position health |
| `syscheck` | System health check |
| `perf` | Performance metrics |
| `help` | Show all commands |
| `quit` | Stop the system |

---

## Understanding the Dashboard

### Desks Page (🎯)

This is where you'll spend most of your time.

**Three desks:**
- **desk_0dte** ($10K) — Day trades. SPY, QQQ, IWM. Checked every 2 minutes.
- **desk_medium** ($15K) — 30-60 day trades. Top stocks. Checked every 30 minutes.
- **desk_leaps** ($20K) — Long-term trades. Blue chips.

**Action buttons:**
- **Scan** — Find new trade opportunities (green button)
- **Deploy** — Book the approved trades (purple button)
- **Mark** — Update prices and health status (blue button)

**Health badges on positions:**
- 🟢 **OK** — Position is fine. Hold.
- 🟡 **TST** — Price approaching our strike. System is watching.
- 🔴 **BRK** — Price past our strike. System may adjust or close.
- 🔴 **EXIT** — Profit target or stop loss hit. Auto-closing.

### What Do The Numbers Mean?

- **P&L** — Profit and Loss. Green = making money. Red = losing money.
- **POP** — Probability of Profit (e.g., 68% means 68% chance of winning).
- **EV** — Expected Value. Positive = good bet on average.
- **DTE** — Days To Expiration. How many days until the options expire.
- **Θ (theta)** — How much money we earn per day from time decay. Higher = better for income.

---

## Safety & Rules

1. **The system does NOT place real orders** — it only trades in WhatIf mode.
2. **Never change the `.env` file** unless Nitin tells you to.
3. **Never run with `--confirm`** — that would place real orders.
4. **If something looks wrong** — just close the terminal. The system stops.
5. **All trades are in paper mode** — no real money at risk.

### Emergency Stop
Just close the terminal window. Or type `quit` in the terminal. The system stops immediately.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found" error | Run: `.venv\Scripts\activate` first |
| "Environment variable not found" | Check `.env` file exists in eTrading folder |
| Dashboard not loading | Make sure you used `--web` flag. Check http://localhost:8080 |
| "No open trades" | Run `scan` first, then `deploy` |
| Prices showing $0 | Run `mark` to update prices |
| Browser shows old page | Hard refresh: Ctrl+Shift+R |

### If The System Crashes
```bash
cd C:\Users\nitin\PythonProjects\eTrading
.venv\Scripts\activate
python -m trading_cotrader.runners.run_workflow --paper --web
```
Just restart it. All data is saved in the database.

---

## Quick Reference Card

```
START:    python -m trading_cotrader.runners.run_workflow --paper --web
OPEN:     http://localhost:8080
SCAN:     Click "Scan" on Desks page (or type 'scan' in terminal)
DEPLOY:   Click "Deploy" on Desks page (or type 'deploy' in terminal)
MARK:     Click "Mark" on Desks page (or type 'mark' in terminal)
REPORT:   Type 'report' in terminal
STOP:     Type 'quit' or close the terminal
```

---

---

## Connecting Zerodha (India Market)

CoTrader supports trading on Indian markets through Zerodha's Kite Connect. This gives you access to NIFTY, BANKNIFTY, and stock F&O.

### One-Time Setup

1. **Get Kite Connect API credentials:**
   - Go to https://developers.kite.trade/
   - Sign up and create an app
   - You'll get an **API Key** and **API Secret**

2. **Add to your `.env` file:**
   ```
   ZERODHA_API_KEY=your_api_key
   ZERODHA_API_SECRET=your_api_secret
   ```

### Daily Login

Zerodha tokens expire every day at 6 AM IST. You need to re-login each morning before the market opens (9:15 AM IST).

**Step 1:** Start the server if not running:
```
python -m trading_cotrader.runners.run_workflow --paper --web
```

**Step 2:** In the terminal, type:
```
> zerodha-login
```

You'll see a URL like:
```
https://kite.zerodha.com/connect/login?v=3&api_key=xxxxx
```

**Step 3:** Open that URL in your browser. Log in with your Zerodha credentials.

**Step 4:** After login, Zerodha redirects you to a page. The URL will look like:
```
https://your-app.com/?request_token=abc123def456&action=login&status=success
```

**Step 5:** Copy the `request_token` value (the part after `request_token=` and before `&`). In the terminal, type:
```
> zerodha-login abc123def456
```

**Step 6:** You'll see:
```
Login successful!
Access token: xxxxxxxxxxxx...

Add to .env:
ZERODHA_ACCESS_TOKEN=xxxxxxxxxxxx
```

**Step 7:** Add the token to your `.env` file and restart the server.

### What You Get

Once connected, two India desks appear on the Desks page:

| Desk | Capital | What It Trades |
|------|---------|---------------|
| **desk_india_weekly** | ₹5,00,000 | NIFTY/BANKNIFTY weekly expiry. Iron condors, straddles, credit spreads. |
| **desk_india_monthly** | ₹10,00,000 | NIFTY/BANKNIFTY/stocks monthly expiry. Iron condors, verticals, calendars. |

The system will:
- Scan NIFTY and BANKNIFTY automatically
- Apply all 11 gates (same quality filter as US trades)
- Use INR currency (₹) for all India desk P&L
- Monitor during India market hours (9:15 AM - 3:30 PM IST)

### Important Notes

- **Token expires daily** — you must re-login each morning before market opens
- **Market hours are different** — India: 9:15 AM - 3:30 PM IST, US: 9:30 AM - 4:00 PM ET
- **Lot sizes vary** — NIFTY = 25, BANKNIFTY = 15 (not 100 like US options)
- **Cash-settled** — no assignment risk on index options (unlike US)
- **No LEAPs** — India F&O max expiry is ~3 months

### Both Markets at Once

You can run US (TastyTrade) and India (Zerodha) simultaneously. The Desks page groups them by market with flags:

```
🇺🇸 United States  USD
  desk_0dte ($10,000)  |  desk_medium ($15,000)  |  desk_leaps ($20,000)

🇮🇳 India  INR
  desk_india_weekly (₹5,00,000)  |  desk_india_monthly (₹10,00,000)
```

P&L is never mixed between currencies. Each market has its own capital total.

---

## For Nitin (Technical Notes)

- Broker credentials now in `.env` only — no YAML files
- Adapter reads env vars directly: `TASTYTRADE_CLIENT_SECRET_{PAPER|LIVE}`
- `.env` is in `.gitignore` (8 entries)
- `tastytrade_broker.yaml` deleted
- Trade execution blocked by default: `TRADE_EXECUTION_ENABLED` must be `true` + adapter `read_only=False`
- Paper mode: `--paper` flag uses paper account (5WY28619)
