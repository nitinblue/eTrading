"""
Test Harness Base Classes and Utilities
=======================================

Provides base class for test steps and shared utilities.
"""

import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from tabulate import tabulate

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def colored(text: str, color: str) -> str:
    """Add color to text for terminal output."""
    return f"{color}{text}{Colors.END}"


def header(text: str, width: int = 80) -> str:
    """Create a formatted header."""
    return colored(f"\n{'='*width}\n{text.center(width)}\n{'='*width}", Colors.BOLD)


def subheader(text: str, width: int = 60) -> str:
    """Create a formatted subheader."""
    return colored(f"\n{'-'*width}\n{text}\n{'-'*width}", Colors.CYAN)


def success(text: str) -> str:
    return colored(f"✓ {text}", Colors.GREEN)


def warning(text: str) -> str:
    return colored(f"⚠ {text}", Colors.YELLOW)


def error(text: str) -> str:
    return colored(f"✗ {text}", Colors.RED)


def format_currency(value: Optional[Decimal]) -> str:
    """Format decimal as currency."""
    if value is None:
        return "-"
    return f"${float(value):,.2f}"


def format_percent(value: Optional[float]) -> str:
    """Format as percentage."""
    if value is None:
        return "-"
    return f"{value:.1f}%"


def format_greek(value: Optional[Decimal], precision: int = 2) -> str:
    """Format greek value with sign."""
    if value is None:
        return "-"
    v = float(value)
    if precision == 2:
        return f"{v:+.2f}"
    elif precision == 4:
        return f"{v:+.4f}"
    return f"{v:+.{precision}f}"


def format_quantity(value: int) -> str:
    """Format quantity with sign."""
    return f"{value:+d}" if value != 0 else "0"


def rich_table(data: List[List[Any]], headers: List[str], title: str = None, 
               tablefmt: str = "rounded_grid") -> str:
    """Create a rich formatted table with optional title."""
    table = tabulate(data, headers=headers, tablefmt=tablefmt, 
                     numalign="right", stralign="left")
    if title:
        title_line = colored(f"\n{title}", Colors.BOLD)
        return f"{title_line}\n{table}"
    return table


@dataclass
class StepResult:
    """Result of a test step execution."""
    step_name: str
    passed: bool
    duration_ms: float
    tables: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    error: Optional[str] = None
    exception: Optional[Exception] = None
    
    def add_table(self, table: str):
        self.tables.append(table)
    
    def add_message(self, msg: str):
        self.messages.append(msg)


class TestStep(ABC):
    """
    Base class for test harness steps.
    
    Each step should:
    1. Have a clear name and description
    2. Execute its test logic
    3. Return rich tabular output for UI design insights
    """
    
    name: str = "Unnamed Step"
    description: str = ""
    
    def __init__(self, context: Dict[str, Any]):
        """
        Initialize with shared context.
        
        Context is a dict shared between steps for passing data
        (e.g., portfolio, positions, registry, etc.)
        """
        self.context = context
    
    @abstractmethod
    def execute(self) -> StepResult:
        """
        Execute the test step.
        
        Returns:
            StepResult with tables and status
        """
        pass
    
    def run(self) -> StepResult:
        """Run the step with error handling and timing."""
        start = datetime.now()
        
        try:
            result = self.execute()
            result.duration_ms = (datetime.now() - start).total_seconds() * 1000
            return result
            
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            return StepResult(
                step_name=self.name,
                passed=False,
                duration_ms=duration,
                error=str(e),
                exception=e,
                messages=[f"Exception: {type(e).__name__}: {e}"]
            )
    
    def _success_result(self, tables: List[str] = None, messages: List[str] = None) -> StepResult:
        """Helper to create a successful result."""
        return StepResult(
            step_name=self.name,
            passed=True,
            duration_ms=0,
            tables=tables or [],
            messages=messages or []
        )
    
    def _fail_result(self, error: str, tables: List[str] = None) -> StepResult:
        """Helper to create a failed result."""
        return StepResult(
            step_name=self.name,
            passed=False,
            duration_ms=0,
            error=error,
            tables=tables or []
        )
