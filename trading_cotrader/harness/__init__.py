"""
Test Harness Package
====================

Modular test harness for Trading CoTrader.
Each step is a separate module that can be run independently.

Usage:
    from harness.runner import run_harness
    run_harness(use_mock=True)
"""

from trading_cotrader.harness.base import TestStep, StepResult
from trading_cotrader.harness.runner import run_harness

__all__ = ['TestStep', 'StepResult', 'run_harness']
