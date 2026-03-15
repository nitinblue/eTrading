#!/bin/bash
# CoTrader Setup Script — Run on a new machine
# Usage: bash scripts/setup_new_machine.sh

echo "============================================"
echo "CoTrader Setup"
echo "============================================"
echo

# 1. Check Python
echo "Checking Python..."
python --version 2>&1 || { echo "ERROR: Python not found. Install Python 3.12 from python.org"; exit 1; }
echo

# 2. Create venv
echo "Creating virtual environment..."
python -m venv .venv
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
echo

# 3. Install dependencies
echo "Installing Python packages..."
pip install -r requirements.txt
echo

# 4. Install market_analyzer
echo "Installing market_analyzer..."
pip install --no-deps -e ../market_analyzer
echo

# 5. Check .env
if [ ! -f .env ]; then
    echo "============================================"
    echo "IMPORTANT: .env file not found!"
    echo "============================================"
    echo
    echo "Copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    echo "  Then edit .env with your TastyTrade tokens"
    echo
    echo "Ask Nitin for the token values."
    echo "============================================"
    cp .env.example .env
    echo "Created .env from template. EDIT IT before running."
else
    echo ".env exists ✓"
fi
echo

# 6. Initialize database
echo "Initializing database..."
python -c "
from trading_cotrader.config.settings import get_settings
get_settings()
from trading_cotrader.core.database.session import init_database
init_database()
print('Database initialized ✓')
"
echo

# 7. Create trading desks
echo "Creating trading desks..."
python -c "
from trading_cotrader.config.settings import get_settings
get_settings()
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import PortfolioORM
from decimal import Decimal
import uuid

desks = [
    ('desk_0dte', '0DTE Trading Desk', 10000),
    ('desk_medium', 'Medium-Term Desk', 15000),
    ('desk_leaps', 'LEAPs Desk', 20000),
    ('desk_india_weekly', 'India Weekly', 500000),
    ('desk_india_monthly', 'India Monthly', 1000000),
]
with session_scope() as session:
    for name, display, capital in desks:
        if not session.query(PortfolioORM).filter(PortfolioORM.name == name).first():
            session.add(PortfolioORM(
                id=str(uuid.uuid4()), name=name, portfolio_type='what_if',
                initial_capital=Decimal(str(capital)), cash_balance=Decimal(str(capital)),
                buying_power=Decimal(str(capital)), total_equity=Decimal(str(capital)),
                description=display,
            ))
            print(f'  Created: {name}')
        else:
            print(f'  Exists: {name}')
    session.commit()
print('Desks ready ✓')
"
echo

# 8. Build frontend
echo "Building frontend..."
cd frontend && npm install 2>/dev/null || pnpm install
npm run build 2>/dev/null || pnpm build
cd ..
echo "Frontend built ✓"
echo

echo "============================================"
echo "Setup complete!"
echo "============================================"
echo
echo "To start:"
echo "  source .venv/Scripts/activate"
echo "  python -m trading_cotrader.runners.run_workflow --paper --web"
echo
echo "Then open: http://localhost:8080"
echo "============================================"
