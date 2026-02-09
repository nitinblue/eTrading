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
        result = data_service.sync_from_broker()

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
