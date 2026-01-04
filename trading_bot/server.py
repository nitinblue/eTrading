# trading_bot/server.py
"""
Server mode for the trading bot.
- FastAPI/Uvicorn server
- Background sheet refresh
- Endpoints for sheet triggers
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from threading import Thread
import time
import logging
from trading_bot.config import Config
from trading_bot.broker_mock import MockBroker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.portfolio import Portfolio
from trading_bot.positions import PositionsManager
from trading_bot.risk import RiskManager
from trading_bot.options_sheets_sync import OptionsSheetsSync

logger = logging.getLogger(__name__)

app = FastAPI(title="Trading Bot Server")

config = Config.load('config.yaml')

def get_execution_broker():
    """Broker for execution (paper/live/mock)."""
    mode = config.general.get('execution_mode', 'paper').lower()

    if mode == 'mock':
        broker = MockBroker()
        broker.connect()
        logger.info("Execution broker: Mock")
        return broker

    creds = config.broker.get(mode, {})
    if not creds:
        raise ValueError(f"No credentials for {mode}")

    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=(mode == 'paper')
    )
    broker.connect()
    logger.info(f"Execution broker: {mode.upper()}")
    return broker

execution_broker = get_execution_broker()
positions_manager = PositionsManager(execution_broker)
risk_manager = RiskManager(config.risk)
portfolio = Portfolio(positions_manager, risk_manager)
sheets = OptionsSheetsSync(config)

def background_refresh():
    while True:
        try:
            logger.info("Background refresh running")
            portfolio.update()
            capital = execution_broker.get_account_balance().get('equity', 100000.0)
            position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)
            sheets.update_monitoring_sheet(execution_broker, portfolio, position_risks)
        except Exception as e:
            logger.error(f"Background refresh failed: {e}")
        time.sleep(300)  # 5 minutes

@app.on_event("startup")
async def startup_event():
    thread = Thread(target=background_refresh, daemon=True)
    thread.start()
    logger.info("Background refresh started")

@app.get("/")
def root():
    return {"status": "Bot server running", "mode": config.general.execution_mode}

@app.post("/refresh")
def refresh_sheet():
    try:
        portfolio.update()
        capital = execution_broker.get_account_balance().get('equity', 100000.0)
        position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)
        sheets.update_monitoring_sheet(execution_broker, portfolio, position_risks)
        return JSONResponse({"status": "refresh_success"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/book_trades")
def book_trades():
    try:
        sheets.process_what_if_booking(execution_broker, portfolio)
        return JSONResponse({"status": "trades_booked"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("trading_bot.server:app", host="0.0.0.0", port=8000)