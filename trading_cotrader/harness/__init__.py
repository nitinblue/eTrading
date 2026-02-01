"""
Test Harness Package
====================

Modular test harness for Trading CoTrader.
Each step is a separate module that can be run independently.

Usage:
    from harness.runner import run_harness
    run_harness(use_mock=True)
"""

from harness.base import TestStep, StepResult
from harness.runner import run_harness

__all__ = ['TestStep', 'StepResult', 'run_harness']
