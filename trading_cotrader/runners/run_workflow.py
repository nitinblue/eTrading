import sys
import os
# Prevent stale .pyc from causing AttributeError on editable-installed packages
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

"""
Workflow Engine Runner — CLI entry point for the continuous trading workflow.

Usage:
    python -m trading_cotrader.runners.run_workflow --once --no-broker --mock
    python -m trading_cotrader.runners.run_workflow --paper --no-broker
    python -m trading_cotrader.runners.run_workflow --paper --no-broker --web --port 8080

Commands (interactive mode):
    status    — Show current workflow state
    list      — List pending recommendations
    approve <id> [--portfolio <name>]  — Approve a recommendation
    reject <id>  — Reject a recommendation
    defer <id>   — Defer a decision
    halt         — Halt all trading
    resume       — Resume trading (requires rationale)
    help         — Show all commands
    quit         — Stop the workflow engine
"""

import sys
import argparse
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def parse_cli_intent(raw: str):
    """Parse a user input string into a UserIntent."""
    from trading_cotrader.agents.messages import UserIntent

    parts = raw.strip().split()
    if not parts:
        return UserIntent(action='help')

    action = parts[0].lower()
    target = None
    rationale = ''
    parameters = {}

    # Parse remaining args
    i = 1
    while i < len(parts):
        if parts[i] == '--portfolio' and i + 1 < len(parts):
            parameters['portfolio'] = parts[i + 1]
            i += 2
        elif parts[i] == '--rationale' and i + 1 < len(parts):
            rationale = ' '.join(parts[i + 1:])
            break
        elif parts[i] == '--notes' and i + 1 < len(parts):
            rationale = ' '.join(parts[i + 1:])
            break
        elif parts[i] == '--confirm':
            parameters['confirm'] = True
            i += 1
        elif target is None and not parts[i].startswith('--'):
            target = parts[i]
            i += 1
        else:
            i += 1

    return UserIntent(
        action=action,
        target=target,
        parameters=parameters,
        rationale=rationale,
    )


def _build_frontend():
    """Build frontend if source is newer than dist."""
    import subprocess
    from pathlib import Path

    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    dist_dir = frontend_dir / "dist"
    src_dir = frontend_dir / "src"

    if not (frontend_dir / "package.json").exists():
        return  # No frontend

    # Check if build needed: dist missing or src newer
    needs_build = not dist_dir.exists()
    if not needs_build and dist_dir.exists():
        dist_mtime = max(f.stat().st_mtime for f in dist_dir.rglob("*") if f.is_file()) if any(dist_dir.rglob("*")) else 0
        src_mtime = max(f.stat().st_mtime for f in src_dir.rglob("*") if f.is_file()) if src_dir.exists() else 0
        needs_build = src_mtime > dist_mtime

    if needs_build:
        print("Building frontend...")
        try:
            result = subprocess.run(
                ["pnpm", "build"],
                cwd=str(frontend_dir),
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                print("Frontend built successfully.")
            else:
                print(f"Frontend build failed: {result.stderr[:200]}")
        except FileNotFoundError:
            # pnpm not found, try npm
            try:
                subprocess.run(
                    ["npm", "run", "build"],
                    cwd=str(frontend_dir),
                    capture_output=True, text=True, timeout=60,
                )
                print("Frontend built successfully (npm).")
            except Exception:
                print("Frontend build skipped (pnpm/npm not found).")
        except Exception as e:
            print(f"Frontend build skipped: {e}")


def _start_web_server(engine, port: int):
    """Build frontend if needed, then start the web dashboard in a daemon thread."""
    _build_frontend()

    from trading_cotrader.web.approval_api import create_approval_app
    import uvicorn

    app = create_approval_app(engine)

    thread = threading.Thread(
        target=uvicorn.run,
        kwargs={
            "app": app,
            "host": "0.0.0.0",
            "port": port,
            "log_level": "warning",
        },
        daemon=True,
    )
    thread.start()

    print(f"Web dashboard: http://localhost:{port}")
    print(f"  Remote access: expose port {port} via ngrok, Tailscale, or Cloudflare Tunnel")
    print()


def main():
    parser = argparse.ArgumentParser(description='Run Trading Workflow Engine')
    parser.add_argument('--paper', action='store_true', default=True,
                        help='Paper trading mode (default)')
    parser.add_argument('--mock', action='store_true',
                        help='Use mock market data')
    parser.add_argument('--no-broker', action='store_true',
                        help='Run without broker connection')
    parser.add_argument('--once', action='store_true',
                        help='Run one cycle then exit (for testing)')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to workflow_rules.yaml')
    parser.add_argument('--web', action='store_true',
                        help='Start web approval dashboard')
    parser.add_argument('--port', type=int, default=8080,
                        help='Web dashboard port (default: 8080)')
    args = parser.parse_args()

    # Setup
    from trading_cotrader.config.settings import setup_logging
    setup_logging()

    # Broker setup — connect all available brokers
    brokers = {}
    primary_broker = None
    if not args.no_broker:
        # TastyTrade (US)
        try:
            from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
            tt = TastytradeAdapter(is_paper=args.paper)
            if tt.authenticate():
                brokers['tastytrade'] = tt
                primary_broker = tt
                logger.info(f"TastyTrade: connected (account={tt.account_id})")
        except Exception as e:
            logger.debug(f"TastyTrade: {e}")

        # Zerodha (India)
        try:
            from trading_cotrader.adapters.zerodha_adapter import ZerodhaAdapter
            zd = ZerodhaAdapter()
            if zd.authenticate():
                brokers['zerodha'] = zd
                if not primary_broker:
                    primary_broker = zd
                logger.info(f"Zerodha: connected (market=INDIA)")
        except Exception as e:
            logger.debug(f"Zerodha: {e}")

        if not brokers:
            logger.warning("No brokers connected. Running without broker.")

    # Initialize engine with all connected brokers
    from trading_cotrader.agents.workflow.engine import WorkflowEngine
    engine = WorkflowEngine(
        broker=primary_broker,
        adapters=brokers,  # Pass all brokers
        use_mock=args.mock or args.no_broker,
        paper_mode=args.paper,
        config_path=args.config,
    )

    mode = "PAPER" if args.paper else "LIVE"
    data = "MOCK" if (args.mock or args.no_broker) else "LIVE"

    print()
    print("=" * 60)
    print(f"TRADING WORKFLOW ENGINE — {mode} mode, {data} data")
    print("=" * 60)
    print()

    # Start web dashboard if requested
    if args.web:
        _start_web_server(engine, args.port)

    if args.once:
        print("Running single cycle...")
        engine.run_once()
        if args.web:
            print(f"\nSingle cycle complete. Dashboard still running at http://localhost:{args.port}")
            print("Press Ctrl+C to exit.")
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
        else:
            print("\nSingle cycle complete.")
        return

    # Start scheduler for continuous mode
    from trading_cotrader.agents.workflow.scheduler import WorkflowScheduler
    scheduler = WorkflowScheduler(engine, engine.config)
    scheduler.start()

    # Run initial boot
    print("Running initial boot cycle...")
    try:
        engine.run_once()
    except Exception as e:
        logger.error(f"Initial boot failed: {e}")

    # Interactive CLI loop
    print()
    print("Workflow engine running. Type 'help' for commands, 'quit' to stop.")
    if args.web:
        print(f"Web dashboard active at http://localhost:{args.port}")
    print()

    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() == 'quit':
                break

            intent = parse_cli_intent(user_input)
            response = engine.handle_user_intent(intent)
            print(response.message)
            print()

    except KeyboardInterrupt:
        print("\nShutting down...")

    scheduler.stop()
    print("Workflow engine stopped.")


if __name__ == "__main__":
    main()
