"""
WebSocket Server for Real-Time Cell Updates

Provides:
- WebSocket endpoint for cell-level push updates
- REST endpoint for initial data load
- Event-driven architecture with container integration
- Refresh endpoint to reload from data source
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
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

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

        # Clean up disconnected
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

# Data provider (can be swapped)
_data_provider = None


def set_data_provider(provider):
    """Set the data provider for loading snapshots"""
    global _data_provider
    _data_provider = provider


def on_container_event(event: ContainerEvent):
    """Handle container events - push to WebSocket clients"""
    asyncio.create_task(connection_manager.send_cell_updates(event))


# Register event listener
container_manager.add_event_listener(on_container_event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    logger.info("Starting WebSocket server...")

    # Initial load if data provider is set
    if _data_provider:
        try:
            snapshot = _data_provider.get_snapshot()
            container_manager.load_from_snapshot(snapshot)
            logger.info("Initial data loaded from provider")
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")

    yield

    logger.info("Shutting down WebSocket server...")


# Create FastAPI app
app = FastAPI(
    title="Trading Grid API",
    description="Real-time trading grid with WebSocket cell updates",
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
        "websocket": "/ws",
        "endpoints": {
            "data": "/api/data",
            "refresh": "/api/refresh",
            "health": "/health",
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
        "timestamp": datetime.utcnow().isoformat(),
        "connections": len(connection_manager.active_connections),
    }


@app.get("/api/data")
async def get_data():
    """
    Get full current state for initial grid load.
    Returns all data needed to populate grids.
    """
    try:
        state = container_manager.get_full_state()
        return JSONResponse(content=json.loads(json_dumps(state)))
    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def refresh_data():
    """
    Trigger data refresh from source.
    Broadcasts cell updates to all connected clients.
    """
    try:
        if _data_provider:
            snapshot = _data_provider.get_snapshot()
            event = container_manager.load_from_snapshot(snapshot)
        else:
            # Try loading from mock data
            event = container_manager.refresh()

        # Also send full refresh to all clients
        state = container_manager.get_full_state()
        await connection_manager.send_full_refresh(state)

        return {
            "status": "refreshed",
            "positions": container_manager.positions.count,
            "cell_updates": len(event.cell_updates),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Protocol:
    - Client connects
    - Server sends 'connected' message
    - Server pushes 'cellUpdates' on changes
    - Server pushes 'fullRefresh' on manual refresh
    - Client can send 'refresh' to trigger reload
    """
    await connection_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_text(json_dumps({
            'type': 'connected',
            'timestamp': datetime.utcnow().isoformat(),
        }))

        # Send current state
        state = container_manager.get_full_state()
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
                    # Client requested refresh
                    await refresh_data()

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
