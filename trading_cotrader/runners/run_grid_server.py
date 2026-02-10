"""
Grid Server Runner

Starts the WebSocket server for the Trading Grid UI.
All data comes from TastyTrade broker and SQLite database - NO MOCK DATA.

Usage:
    python -m trading_cotrader.runners.run_grid_server

Then open trading_cotrader/ui/trading-grid.html in a browser.

On first run:
    Click "Sync Broker" button in UI to connect to TastyTrade and load positions.
    After that, data persists in SQLite and loads automatically on restart.
"""

import sys
import argparse
import logging
from pathlib import Path
import asyncio # Ensure this is imported at the top

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Run Trading Grid Server')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    parser.add_argument('--auto-sync', action='store_true',
                        help='Automatically sync from broker on startup')
    args = parser.parse_args()

    # Import after logging setup
    from trading_cotrader.server.websocket_server import app, data_service, container_manager
    from trading_cotrader.config.settings import setup_logging

    setup_logging()

    # Auto-sync from broker if requested
    if args.auto_sync:
        logger.info("Auto-sync enabled - connecting to TastyTrade broker...")
        # result = data_service.sync_from_broker()
        result = asyncio.run(data_service.sync_from_broker())
        if result.success:
            logger.info(f"Synced {result.positions_count} positions from broker")
        else:
            logger.error(f"Auto-sync failed: {result.error}")
            logger.info("Server will start anyway - use UI to sync manually")

    # Run server
    import uvicorn

    ui_path = Path(__file__).parent.parent / 'ui' / 'trading-grid.html'

    print()
    print("=" * 60)
    print("TRADING GRID SERVER")
    print("=" * 60)
    print()
    print(f"Server starting on: http://localhost:{args.port}")
    print()
    print("Open UI in browser:")
    print(f"  file://{ui_path.absolute()}")
    print()
    print("API Endpoints:")
    print(f"  GET  http://localhost:{args.port}/           - Health check")
    print(f"  GET  http://localhost:{args.port}/api/data   - Get current data")
    print(f"  POST http://localhost:{args.port}/api/sync   - Sync from TastyTrade")
    print(f"  POST http://localhost:{args.port}/api/refresh - Refresh from database")
    print(f"  WS   ws://localhost:{args.port}/ws           - WebSocket updates")
    print()
    print("First time setup:")
    print("  1. Open UI in browser")
    print("  2. Click 'Sync Broker' to connect to TastyTrade")
    print("  3. Positions will be loaded and persisted to SQLite")
    print()
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
