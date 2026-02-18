# Trading CoTrader — Setup Guide

Quick-start guide to get the system running on a fresh machine.

---

## Prerequisites

### 1. Python (3.11+)
```bash
# Check version
python --version
# Should be 3.11 or higher
```

### 2. Node.js (20+) and pnpm
```bash
# Check versions
node --version    # Should be 20+
npm --version     # Comes with Node.js

# Install pnpm (package manager for frontend)
npm install -g pnpm
pnpm --version
```

### 3. Git
```bash
git --version
```

---

## Step-by-Step Setup

### Step 1: Clone the repo
```bash
git clone <repo-url> eTrading
cd eTrading
```

### Step 2: Python virtual environment + dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Windows (Git Bash):
source .venv/Scripts/activate
# On Mac/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Step 3: Environment variables
Create a `.env` file in the project root:
```bash
# Required for TastyTrade broker (optional if running --no-broker)
TASTYTRADE_USERNAME=your_username
TASTYTRADE_PASSWORD=your_password

# Paper trading mode (ALWAYS set this to true unless going live)
IS_PAPER_TRADING=true
```

### Step 4: Initialize the database
```bash
python -m trading_cotrader.scripts.setup_database
```

### Step 5: Initialize portfolios
```bash
python -m trading_cotrader.cli.init_portfolios
```

### Step 6: Frontend setup
```bash
cd frontend

# Install frontend dependencies
pnpm install

# Go back to project root
cd ..
```

---

## Running the System

### Option A: Backend only (no broker, mock data)
```bash
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock
```

### Option B: Backend + Web Dashboard (recommended for daily use)
```bash
# Terminal 1: Start backend with web server
python -m trading_cotrader.runners.run_workflow --web --port 8080 --no-broker --mock

# Terminal 2: Start frontend dev server
cd frontend
pnpm dev
# Frontend available at http://localhost:5173
# Backend API at http://localhost:8080
```

### Option C: Production build (single server)
```bash
# Build the frontend
cd frontend
pnpm build
cd ..

# Start backend — it serves the built frontend at http://localhost:8080
python -m trading_cotrader.runners.run_workflow --web --port 8080 --no-broker --mock
```

---

## Running Tests

```bash
# Python tests (should all pass)
pytest trading_cotrader/tests/ -v

# Integration harness (14/16 pass without broker)
python -m trading_cotrader.harness.runner --skip-sync

# Frontend type check
cd frontend
pnpm build
```

---

## Python Dependencies (requirements.txt)

Key packages:
| Package | Purpose |
|---------|---------|
| `sqlalchemy` | Database ORM |
| `fastapi` | Web API server |
| `uvicorn` | ASGI server for FastAPI |
| `pydantic` | Data validation |
| `transitions` | Workflow state machine |
| `apscheduler` | Task scheduling |
| `yfinance` | Market data (free) |
| `scipy` | VaR calculations |
| `numpy` | Numerical computing |
| `pandas` | Data analysis |
| `exchange_calendars` | NYSE holiday calendar |
| `python-dotenv` | .env file loading |
| `requests` | HTTP client |
| `tastytrade` | TastyTrade broker SDK (optional) |

### Frontend Dependencies (frontend/package.json)

| Package | Purpose |
|---------|---------|
| `react`, `react-dom` | UI framework |
| `react-router-dom` | Client-side routing |
| `@tanstack/react-query` | Server state management + polling |
| `ag-grid-react`, `ag-grid-community` | Financial data grids |
| `recharts` | Charts (P&L, risk) |
| `zustand` | Client state (WebSocket, UI) |
| `axios` | HTTP client |
| `lucide-react` | Icons |
| `clsx` | CSS class helpers |
| `tailwindcss` | CSS framework |
| `typescript` | Type safety |
| `vite` | Build tool + dev server |
| `@vitejs/plugin-react` | React Vite plugin |

---

## Troubleshooting

### "Module not found" errors
Make sure you're running from the project root, and the virtual environment is activated:
```bash
cd /path/to/eTrading
source .venv/Scripts/activate   # Windows Git Bash
python -m trading_cotrader.scripts.setup_database
```

### "pnpm: command not found"
```bash
npm install -g pnpm
```

### Frontend proxy errors (CORS, 502)
Make sure the backend is running on port 8080 before starting the frontend:
```bash
# Terminal 1 first:
python -m trading_cotrader.runners.run_workflow --web --port 8080 --no-broker --mock

# Terminal 2 after backend is up:
cd frontend && pnpm dev
```

### Database errors
Re-run setup:
```bash
python -m trading_cotrader.scripts.setup_database
python -m trading_cotrader.cli.init_portfolios
```
