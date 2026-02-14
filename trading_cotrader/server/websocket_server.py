"""
WebSocket Server for Real-Time Trading Grid

Provides:
- WebSocket endpoint for cell-level push updates
- REST endpoints for data and sync operations
- Event-driven architecture with container integration
- Real + What-If portfolio display

NO MOCK DATA - all data from TastyTrade broker and SQLite database.
"""

import json
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Set, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trading_cotrader.containers import ContainerManager, ContainerEvent
from trading_cotrader.services.data_service import DataService
from trading_cotrader.services.option_grid_service import OptionGridService

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def json_dumps(obj) -> str:
    """JSON serialize with Decimal support"""
    return json.dumps(obj, cls=DecimalEncoder)


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        message_str = json_dumps(message)
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(connection)

        for conn in disconnected:
            self.active_connections.discard(conn)

    async def send_cell_updates(self, event: ContainerEvent):
        """Send cell-level updates to all clients"""
        if not event.cell_updates:
            return

        message = {
            'type': 'cellUpdates',
            'eventType': event.event_type.value,
            'updates': [cu.to_dict() for cu in event.cell_updates],
            'timestamp': datetime.utcnow().isoformat(),
        }
        await self.broadcast(message)

    async def send_full_refresh(self, data: Dict[str, Any]):
        """Send full data refresh to all clients"""
        message = {
            'type': 'fullRefresh',
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }
        await self.broadcast(message)


# Global instances
connection_manager = ConnectionManager()
container_manager = ContainerManager()
data_service = DataService(container_manager)
option_grid_service = OptionGridService()


def on_container_event(event: ContainerEvent):
    """Handle container events - push to WebSocket clients"""
    asyncio.create_task(connection_manager.send_cell_updates(event))


# Register event listener
container_manager.add_event_listener(on_container_event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    logger.info("Starting Trading Grid WebSocket server...")

    # Try to load from database on startup
    try:
        result = data_service.refresh_from_database()
        if result.success:
            logger.info(f"Loaded {result.positions_count} positions from database")
            logger.info(f"Found {result.whatif_trades_count} what-if trades")
        else:
            logger.warning(f"No data in database: {result.error}")
            logger.info("Connect to broker using /api/sync to load data")
    except Exception as e:
        logger.error(f"Failed to load from database: {e}")

    yield

    logger.info("Shutting down Trading Grid server...")


# Create FastAPI app
app = FastAPI(
    title="Trading Grid API",
    description="Real-time trading grid with WebSocket updates - No mock data",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "Trading Grid API",
        "version": "2.0.0",
        "broker_connected": data_service.is_connected,
        "websocket": "/ws",
        "endpoints": {
            "data": "GET /api/data - Get current state",
            "sync": "POST /api/sync - Sync from TastyTrade broker",
            "refresh": "POST /api/refresh - Refresh from database",
            "portfolios": "GET /api/portfolios - Get real + what-if portfolios",
            "whatif": "POST /api/whatif - Create what-if trade",
            "events": "GET /api/events - Get trade events (event sourcing)",
            "ai_status": "GET /api/ai/status - AI/ML learning status",
            "ai_recommendations": "GET /api/ai/recommendations - AI suggestions",
        },
        "containers": {
            "initialized": container_manager.is_initialized,
            "positions": container_manager.positions.count,
            "underlyings": container_manager.risk_factors.underlyings,
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "broker_connected": data_service.is_connected,
        "timestamp": datetime.utcnow().isoformat(),
        "connections": len(connection_manager.active_connections),
    }


@app.post("/api/sync")
async def sync_from_broker():
    """
    Sync data from TastyTrade broker.

    This will:
    1. Connect to TastyTrade (if not connected)
    2. Fetch positions with Greeks from DXLink streaming
    3. Persist to SQLite database
    4. Refresh containers
    5. Push updates to all WebSocket clients
    """
    try:
        result = await data_service.sync_from_broker()

        if result.success:
            # Send full refresh to all clients
            state = container_manager.get_full_state()
            portfolios = data_service.get_portfolios_data()
            state['portfolios'] = portfolios
            await connection_manager.send_full_refresh(state)

            return {
                "status": "synced",
                "portfolio_id": result.portfolio_id,
                "positions": result.positions_count,
                "whatif_trades": result.whatif_trades_count,
                "timestamp": result.timestamp.isoformat(),
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def refresh_from_database():
    """
    Refresh containers from database.

    Does NOT connect to broker - just reloads from SQLite.
    Use this for quick refreshes when data is already synced.
    """
    try:
        result = data_service.refresh_from_database()

        if result.success:
            # Send full refresh to all clients
            state = container_manager.get_full_state()
            portfolios = data_service.get_portfolios_data()
            state['portfolios'] = portfolios
            await connection_manager.send_full_refresh(state)

            return {
                "status": "refreshed",
                "positions": result.positions_count,
                "whatif_trades": result.whatif_trades_count,
                "timestamp": result.timestamp.isoformat(),
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data")
async def get_data():
    """
    Get full current state for grid display.

    Returns:
    - Portfolio summary
    - Positions
    - Risk factors by underlying
    - Real + What-If portfolio views
    """
    try:
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios
        return JSONResponse(content=json.loads(json_dumps(state)))
    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolios")
async def get_portfolios():
    """
    Get both real portfolio and what-if portfolio.

    Real portfolio: Actual positions from broker
    What-If portfolio: Aggregated from what-if trades in database
    """
    try:
        portfolios = data_service.get_portfolios_data()
        return JSONResponse(content=json.loads(json_dumps(portfolios)))
    except Exception as e:
        logger.error(f"Error getting portfolios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WHAT-IF TRADE ENDPOINTS ====================

@app.post("/api/whatif")
async def create_whatif_trade(request: dict):
    """
    Create a what-if trade.

    Request body:
    {
        "underlying": "SPY",
        "strategy_type": "vertical",
        "legs": [
            {"option_type": "PUT", "strike": 580, "expiry": "2025-02-21", "quantity": -1},
            {"option_type": "PUT", "strike": 575, "expiry": "2025-02-21", "quantity": 1}
        ],
        "notes": "Bull put spread"
    }

    Response includes Greeks fetched from broker and mid price as entry.
    """
    try:
        underlying = request.get('underlying')
        strategy_type = request.get('strategy_type', 'custom')
        legs = request.get('legs', [])
        notes = request.get('notes', '')

        if not underlying or not legs:
            raise HTTPException(status_code=400, detail="Missing underlying or legs")

        result = data_service.create_whatif_trade(
            underlying=underlying,
            strategy_type=strategy_type,
            legs=legs,
            notes=notes,
        )

        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])

        # Broadcast update to all clients
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios
        await connection_manager.send_full_refresh(state)

        return JSONResponse(content=json.loads(json_dumps(result)))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating what-if trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/whatif/{trade_id}")
async def delete_whatif_trade(trade_id: str):
    """Remove a what-if trade"""
    try:
        result = data_service.remove_whatif_trade(trade_id)

        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])

        # Broadcast update to all clients
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios
        await connection_manager.send_full_refresh(state)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting what-if trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/whatif/{trade_id}/convert")
async def convert_whatif_to_real(trade_id: str):
    """Convert a what-if trade to real (ready for submission)"""
    try:
        result = data_service.convert_whatif_to_real(trade_id)

        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])

        # Broadcast update
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios
        await connection_manager.send_full_refresh(state)

        return JSONResponse(content=json.loads(json_dumps(result)))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting what-if trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whatif")
async def get_whatif_trades():
    """Get all what-if trades"""
    try:
        trades = data_service.get_whatif_trades()
        return JSONResponse(content=json.loads(json_dumps(trades)))
    except Exception as e:
        logger.error(f"Error getting what-if trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whatif/greeks")
async def get_whatif_greeks():
    """Get aggregated Greeks for all what-if trades"""
    try:
        greeks = data_service.get_whatif_greeks()
        return greeks
    except Exception as e:
        logger.error(f"Error getting what-if Greeks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OPTION CHAIN ENDPOINTS ====================

@app.get("/api/chain/{underlying}")
async def get_option_chain(underlying: str):
    """
    Get option chain for an underlying symbol.

    Returns expirations and strikes for the order builder.
    """
    try:
        chain = data_service.get_option_chain(underlying.upper())
        return JSONResponse(content=json.loads(json_dumps(chain)))
    except Exception as e:
        logger.error(f"Error getting option chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strikes/{underlying}/{expiry}")
async def get_atm_strikes(underlying: str, expiry: str):
    """
    Get ATM strikes for an underlying and expiry.

    Returns strikes within 10% of current price for order builder.
    """
    try:
        strikes = data_service.get_atm_strikes(underlying.upper(), expiry)
        return JSONResponse(content=json.loads(json_dumps(strikes)))
    except Exception as e:
        logger.error(f"Error getting ATM strikes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quote/{underlying}/{expiry}/{strike}/{option_type}")
async def get_option_quote(underlying: str, expiry: str, strike: float, option_type: str):
    """
    Get real-time quote and Greeks for a specific option.

    Used by Order Builder Step 3 to show bid/ask/mid and Greeks
    before user adds the leg.
    """
    try:
        quote = data_service.get_option_quote(
            underlying.upper(), expiry, strike, option_type.upper()
        )
        return JSONResponse(content=json.loads(json_dumps(quote)))
    except Exception as e:
        logger.error(f"Error getting option quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickers")
async def get_ticker_history():
    """
    Get list of tickers from positions and trades.

    Used by Order Builder Step 1 dropdown.
    """
    try:
        tickers = data_service.get_ticker_history()
        return JSONResponse(content=tickers)
    except Exception as e:
        logger.error(f"Error getting ticker history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EVENT ENDPOINTS ====================

@app.get("/api/events")
async def get_events(days: int = 30):
    """Get recent trade events (event sourcing)"""
    try:
        events = data_service.get_recent_events(days=days)
        return JSONResponse(content=json.loads(json_dumps(events)))
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI/ML ENDPOINTS ====================

@app.get("/api/ai/status")
async def get_ai_status():
    """Get AI/ML module status and learning progress"""
    try:
        status = data_service.get_ai_status()
        return JSONResponse(content=json.loads(json_dumps(status)))
    except Exception as e:
        logger.error(f"Error getting AI status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/recommendations")
async def get_ai_recommendations(underlying: str = None):
    """Get AI-generated trading recommendations"""
    try:
        recommendations = data_service.get_ai_recommendations(underlying)
        return JSONResponse(content=json.loads(json_dumps(recommendations)))
    except Exception as e:
        logger.error(f"Error getting AI recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/patterns")
async def get_ai_patterns():
    """Get recognized trading patterns"""
    try:
        status = data_service.get_ai_status()
        return JSONResponse(content=json.loads(json_dumps(status.get('patterns', []))))
    except Exception as e:
        logger.error(f"Error getting AI patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OPTION GRID ENDPOINTS ====================

@app.get("/api/grid/templates")
async def get_grid_templates():
    """Get available strategy templates"""
    try:
        templates = option_grid_service.get_strategy_templates()
        return JSONResponse(content=templates)
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/grid/{underlying}")
async def build_option_grid(underlying: str):
    """
    Build option grid for an underlying.

    Returns grid with strikes x expiries, each cell has bid/ask/mid/Greeks.
    """
    try:
        # Ensure broker is connected
        if not data_service.is_connected:
            data_service.connect_broker()

        # Set broker on grid service
        option_grid_service.set_broker(data_service.broker)

        # Build grid
        grid = option_grid_service.build_grid(underlying.upper())

        if not grid:
            raise HTTPException(status_code=404, detail=f"Could not build grid for {underlying}")

        # Populate Greeks
        option_grid_service.populate_greeks(grid)

        return JSONResponse(content=json.loads(json_dumps(grid.to_dict())))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building grid: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/grid/strategy")
async def apply_grid_strategy(request: dict):
    """
    Apply a strategy template to the current grid.

    Request: {"strategy": "iron_condor", "expiry_idx": 2}
    """
    try:
        strategy = request.get('strategy')
        expiry_idx = request.get('expiry_idx', 0)

        if not strategy:
            raise HTTPException(status_code=400, detail="Missing strategy")

        selected = option_grid_service.apply_strategy(strategy, expiry_idx)
        summary = option_grid_service.get_position_summary()

        return JSONResponse(content=json.loads(json_dumps({
            'selected_count': len(selected),
            'summary': summary,
            'grid': option_grid_service.current_grid.to_dict() if option_grid_service.current_grid else None
        })))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/grid/select")
async def select_grid_cell(request: dict):
    """
    Select/deselect a cell in the grid.

    Request: {"strike": 580, "expiry": "2025-03-21", "option_type": "P", "quantity": -1}
    """
    try:
        from decimal import Decimal
        from datetime import datetime

        strike = Decimal(str(request.get('strike')))
        expiry_str = request.get('expiry')
        expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        opt_type = request.get('option_type', 'P')
        quantity = request.get('quantity', 0)

        if not option_grid_service.current_grid:
            raise HTTPException(status_code=400, detail="No grid loaded")

        option_grid_service.current_grid.select_cell(strike, expiry, opt_type, quantity)
        summary = option_grid_service.get_position_summary()

        return JSONResponse(content=json.loads(json_dumps(summary)))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting cell: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/grid/clear")
async def clear_grid_selection():
    """Clear all selections in the grid"""
    try:
        if option_grid_service.current_grid:
            option_grid_service.current_grid.clear_selection()
        return {"status": "cleared"}
    except Exception as e:
        logger.error(f"Error clearing grid: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/grid/summary")
async def get_grid_summary():
    """Get summary of currently selected position"""
    try:
        summary = option_grid_service.get_position_summary()
        return JSONResponse(content=json.loads(json_dumps(summary)))
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/grid/submit")
async def submit_grid_as_whatif():
    """Submit current grid selection as a what-if trade"""
    try:
        if not option_grid_service.current_grid:
            raise HTTPException(status_code=400, detail="No grid loaded")

        selected = option_grid_service.current_grid.get_selected_cells()
        if not selected:
            raise HTTPException(status_code=400, detail="No cells selected")

        # Build legs for what-if trade
        underlying = option_grid_service.current_grid.underlying
        legs = []
        for cell in selected:
            legs.append({
                'option_type': 'CALL' if cell.option_type == 'C' else 'PUT',
                'strike': float(cell.strike),
                'expiry': cell.expiry.strftime('%Y-%m-%d'),
                'quantity': cell.quantity,
            })

        # Determine strategy type
        strategy_type = 'custom'
        if len(legs) == 2:
            strategy_type = 'vertical'
        elif len(legs) == 4:
            strategy_type = 'iron_condor'

        # Create what-if trade
        result = data_service.create_whatif_trade(
            underlying=underlying,
            strategy_type=strategy_type,
            legs=legs,
            notes='Created via Option Grid Builder'
        )

        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])

        # Clear grid selection
        option_grid_service.current_grid.clear_selection()

        # Broadcast update
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios
        await connection_manager.send_full_refresh(state)

        return JSONResponse(content=json.loads(json_dumps(result)))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting grid: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Protocol:
    - Client connects
    - Server sends 'connected' message
    - Server sends 'fullRefresh' with current state
    - Server pushes 'cellUpdates' on container changes
    - Client can send 'refresh' to trigger database reload
    - Client can send 'sync' to trigger broker sync
    """
    await connection_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_text(json_dumps({
            'type': 'connected',
            'broker_connected': data_service.is_connected,
            'timestamp': datetime.utcnow().isoformat(),
        }))

        # Send current state
        state = container_manager.get_full_state()
        portfolios = data_service.get_portfolios_data()
        state['portfolios'] = portfolios

        await websocket.send_text(json_dumps({
            'type': 'fullRefresh',
            'data': state,
            'timestamp': datetime.utcnow().isoformat(),
        }))

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get('type')

                if msg_type == 'refresh':
                    # Refresh from database
                    await refresh_from_database()

                elif msg_type == 'sync':
                    # Full sync from broker
                    await sync_from_broker()

                elif msg_type == 'ping':
                    await websocket.send_text(json_dumps({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat(),
                    }))

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from client: {data}")

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)


# For running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
