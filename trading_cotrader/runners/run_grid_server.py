"""
Grid Server Runner — DEPRECATED

The old grid server has been replaced by the web approval dashboard
embedded in the workflow engine.

Usage:
    python -m trading_cotrader.runners.run_workflow --web --port 8080
"""

import sys


def main():
    print()
    print("DEPRECATED: run_grid_server has been replaced.")
    print()
    print("Use the web approval dashboard instead:")
    print("  python -m trading_cotrader.runners.run_workflow --web --port 8080")
    print()
    print("This starts the workflow engine with an embedded web dashboard")
    print("accessible at http://localhost:8080")
    sys.exit(1)


if __name__ == "__main__":
    main()
