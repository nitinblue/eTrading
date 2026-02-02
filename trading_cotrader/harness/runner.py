"""
Test Harness Runner
===================

Orchestrates all test steps with rich tabular output.

Usage:
    python -m harness.runner              # Full test with broker
    python -m harness.runner --skip-sync  # Use existing DB data
    python -m harness.runner --mock       # Mock data (no broker)
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_cotrader.harness.base import (
    TestStep, StepResult, header, subheader, success, error, warning,
    rich_table, Colors, colored
)

# Import all steps
from trading_cotrader.harness.steps.step01_imports import ImportStep
from trading_cotrader.harness.steps.step02_broker import BrokerConnectionStep
from trading_cotrader.harness.steps.step03_portfolio import PortfolioSyncStep
from trading_cotrader.harness.steps.step04_market_data import MarketDataContainerStep
from trading_cotrader.harness.steps.step05_risk_aggregation import RiskAggregationStep
from trading_cotrader.harness.steps.step06_hedging import HedgeCalculatorStep
from trading_cotrader.harness.steps.step07_risk_limits import RiskLimitsStep
from trading_cotrader.harness.steps.step08_trades import TradeHistoryStep
from trading_cotrader.harness.steps.step09_events import EventsStep
from trading_cotrader.harness.steps.step10_ml_status import MLStatusStep


def run_harness(skip_sync: bool = False, use_mock: bool = False):
    """
    Run the complete test harness.
    
    Args:
        skip_sync: Skip broker sync, use existing DB data
        use_mock: Use mock data (no broker connection)
    """
    print(header("TRADING COTRADER TEST HARNESS"))
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'MOCK' if use_mock else 'SKIP-SYNC' if skip_sync else 'FULL'}")
    print()
    
    # Shared context between steps
    context: Dict[str, Any] = {
        'skip_sync': skip_sync,
        'use_mock': use_mock,
    }
    
    # Define steps in order
    steps: List[TestStep] = [
        ImportStep(context),
        BrokerConnectionStep(context),
        PortfolioSyncStep(context),
        MarketDataContainerStep(context),
        RiskAggregationStep(context),
        HedgeCalculatorStep(context),
        RiskLimitsStep(context),
        TradeHistoryStep(context),
        EventsStep(context),
        MLStatusStep(context),
        ]
    
    # Run all steps
    results: List[StepResult] = []
    
    for i, step in enumerate(steps, 1):
        print(subheader(f"[{i}/{len(steps)}] {step.name}"))
        print(f"  {step.description}")
        print()
        
        result = step.run()
        results.append(result)
        
        # Print tables
        for table in result.tables:
            print(table)
            print()
        
        # Print messages
        for msg in result.messages:
            print(f"  {msg}")
        
        # Print status
        if result.passed:
            print(success(f"{step.name} PASSED ({result.duration_ms:.0f}ms)"))
        else:
            print(error(f"{step.name} FAILED: {result.error}"))
            if result.exception:
                import traceback
                traceback.print_exception(type(result.exception), result.exception, 
                                         result.exception.__traceback__)
        
        print()
    
    # Final summary
    print(header("TEST SUMMARY"))
    
    summary_data = []
    total_time = 0
    passed = 0
    failed = 0
    
    for result in results:
        total_time += result.duration_ms
        status = "✓" if result.passed else "✗"
        status_color = "🟢" if result.passed else "🔴"
        
        if result.passed:
            passed += 1
        else:
            failed += 1
        
        summary_data.append([
            result.step_name,
            f"{result.duration_ms:.0f}ms",
            len(result.tables),
            status_color,
            result.error[:30] if result.error else ""
        ])
    
    print(rich_table(
        summary_data,
        headers=["Step", "Time", "Tables", "Status", "Error"],
        title="📋 Step Results"
    ))
    
    print()
    print(f"  Total Steps: {len(results)}")
    print(f"  {success(f'Passed: {passed}')}")
    if failed:
        print(f"  {error(f'Failed: {failed}')}")
    print(f"  Total Time: {total_time:.0f}ms")
    
    if failed == 0:
        print()
        print(success("ALL TESTS PASSED! ✨"))
    else:
        print()
        print(error(f"{failed} step(s) failed - check errors above"))
    
    return failed == 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Trading CoTrader Test Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m harness.runner              # Full test with broker
  python -m harness.runner --skip-sync  # Use existing DB data
  python -m harness.runner --mock       # Mock data (no broker)
        """
    )
    
    parser.add_argument(
        '--skip-sync', 
        action='store_true',
        help='Skip broker sync, use existing database data'
    )
    
    parser.add_argument(
        '--mock',
        action='store_true', 
        help='Use mock data (no broker connection needed)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    try:
        from config.settings import setup_logging
        setup_logging()
    except ImportError:
        pass  # Continue without logging setup
    
    success = run_harness(
        skip_sync=args.skip_sync,
        use_mock=args.mock
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
