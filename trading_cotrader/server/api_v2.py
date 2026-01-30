"""
Trading CoTrader API - Institutional Trading Backend

Single endpoint returns complete MarketSnapshot:
- Market context (indices, rates, vol, commodities, FX)
- Positions with live bid/ask/greeks
- Risk aggregation by underlying
- Limit breaches
- Hedge recommendations
- Scenario matrices
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from decimal import Decimal
from datetime import datetime
import json
import asyncio
import logging
from trading_cotrader.config.settings import setup_logging, get_settings
from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
# from adapters.tastytrade_adapter import TastytradeAdapter

# Local imports
from contracts import (
    MarketSnapshot, RiskLimit, create_default_limits
)
from data_provider import MockDataProvider, RefreshBasedProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trading CoTrader API",
    description="Institutional Trading Risk Monitor",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# JSON Encoder for Decimal
# ============================================================================

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def serialize_snapshot(snapshot: MarketSnapshot) -> dict:
    """Convert MarketSnapshot to JSON-serializable dict"""
    return json.loads(json.dumps(snapshot, cls=DecimalEncoder, default=lambda o: o.__dict__))


# ============================================================================
# Global State
# ============================================================================

# Use mock provider by default. Set use_live=True to use TastyTrade.
USE_LIVE_DATA = True

if USE_LIVE_DATA:
    # Import your TastyTrade adapter
    adapter = TastytradeAdapter(is_paper=False)
    adapter.authenticate()
    
    
    
    settings = get_settings()
    
    print(f"  Mode: {'PAPER' if settings.is_paper_trading else 'LIVE'}")
    
    try:
        broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if broker.authenticate(): logger.info("connected to broker")
            
        data_provider = RefreshBasedProvider(adapter)        
        pass
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
else:
    data_provider = MockDataProvider()

# WebSocket connections
connected_clients: List[WebSocket] = []


# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Trading CoTrader API",
        "version": "2.0.0",
        "mode": "live" if USE_LIVE_DATA else "mock",
        "endpoints": {
            "snapshot": "GET /snapshot - Complete market snapshot",
            "refresh": "POST /refresh - Force data refresh",
            "limits": "GET/POST /limits - Risk limits",
            "health": "GET /health - Service health"
        }
    }


@app.get("/snapshot")
async def get_snapshot():
    """
    Get complete market snapshot
    
    This is THE endpoint. One call, everything you need.
    """
    try:
        snapshot = await data_provider.get_snapshot()
        return JSONResponse(content=serialize_snapshot(snapshot))
    except Exception as e:
        logger.error(f"Error getting snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/refresh")
async def force_refresh():
    """Force a data refresh"""
    try:
        await data_provider.refresh()
        snapshot = await data_provider.get_snapshot()
        
        # Broadcast to WebSocket clients
        await broadcast_update({
            "type": "snapshot_updated",
            "data": serialize_snapshot(snapshot)
        })
        
        return {"status": "refreshed", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error refreshing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/limits")
async def get_limits():
    """Get current risk limits"""
    return [
        {
            "metric": l.metric,
            "underlying": l.underlying,
            "min_value": float(l.min_value) if l.min_value else None,
            "max_value": float(l.max_value) if l.max_value else None
        }
        for l in data_provider.limits
    ]


class LimitUpdate(BaseModel):
    metric: str
    underlying: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@app.post("/limits")
async def update_limits(limits: List[LimitUpdate]):
    """Update risk limits"""
    new_limits = [
        RiskLimit(
            metric=l.metric,
            underlying=l.underlying,
            min_value=Decimal(str(l.min_value)) if l.min_value is not None else None,
            max_value=Decimal(str(l.max_value)) if l.max_value is not None else None
        )
        for l in limits
    ]
    data_provider.limits = new_limits
    return {"status": "updated", "count": len(new_limits)}


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "mode": "live" if USE_LIVE_DATA else "mock",
        "refresh_count": data_provider.refresh_count,
        "websocket_clients": len(connected_clients),
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# WebSocket (for future streaming)
# ============================================================================

async def broadcast_update(message: dict):
    """Broadcast update to all WebSocket clients"""
    for client in connected_clients:
        try:
            await client.send_json(message)
        except:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    
    Currently push-on-refresh. Will be continuous streaming later.
    """
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    
    try:
        # Send initial snapshot
        snapshot = await data_provider.get_snapshot()
        await websocket.send_json({
            "type": "initial_snapshot",
            "data": serialize_snapshot(snapshot)
        })
        
        # Listen for client messages
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "refresh":
                await data_provider.refresh()
                snapshot = await data_provider.get_snapshot()
                await websocket.send_json({
                    "type": "snapshot_updated",
                    "data": serialize_snapshot(snapshot)
                })
            
            elif data.get("action") == "subscribe":
                # Future: subscribe to specific symbols
                await websocket.send_json({
                    "type": "subscribed",
                    "symbols": data.get("symbols", [])
                })
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


# ============================================================================
# Startup / Shutdown
# ============================================================================

@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("Trading CoTrader API Starting...")
    logger.info(f"Mode: {'LIVE' if USE_LIVE_DATA else 'MOCK'}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    logger.info("Trading CoTrader API Shutting down...")


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
