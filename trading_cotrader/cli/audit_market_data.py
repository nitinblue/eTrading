"""
CLI: Audit codebase for hardcoded market data / local math violations
=====================================================================

Enforces the ZERO LOCAL MATH policy:
  - Greeks and prices ALWAYS come from the broker (DXLink streaming)
  - No Black-Scholes, POP/EV, VaR calculations
  - No hardcoded prices, correlations, volatilities, rates
  - No fallback values that mask missing real data

Usage:
    python -m trading_cotrader.cli.audit_market_data
    python -m trading_cotrader.cli.audit_market_data --fix    # show suggested fixes
    python -m trading_cotrader.cli.audit_market_data --strict # also flag warnings

Scans: trading_cotrader/ (excluding tests/, playground/, config/*.yaml)
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Directories to skip
SKIP_DIRS = {'tests', 'playground', '__pycache__', 'frontend', 'node_modules', '.venv'}
# Harness is test infrastructure — mock data is expected there
SKIP_DIRS.add('harness')
# Files to skip
SKIP_FILES = {'audit_market_data.py'}  # don't flag ourselves


@dataclass
class Violation:
    file: str
    line: int
    code: str
    rule: str
    severity: str  # ERROR, WARNING
    message: str
    suggestion: str = ""


# ── Detection Rules ──


def check_black_scholes(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag Black-Scholes / option pricing math."""
    violations = []
    patterns = [
        (r'\bnorm\.cdf\b', "scipy.stats.norm.cdf — Black-Scholes math"),
        (r'\bnorm\.pdf\b', "scipy.stats.norm.pdf — Black-Scholes math"),
        (r'\bblack.scholes\b', "Black-Scholes pricing function", True),
        (r'\bbs_price\b', "Black-Scholes price calculation"),
        (r'\b[dD]1\s*=.*log\b', "d1 calculation (Black-Scholes)"),
        (r'\b[dD]2\s*=.*[dD]1\b', "d2 calculation (Black-Scholes)"),
        (r'\bmath\.erfc?\b', "Error function — option pricing math"),
        (r'\bnp\.exp\s*\(\s*-\s*r', "Discounting formula (option pricing)"),
    ]
    for pattern, msg, *_ in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            violations.append(Violation(
                file=filepath, line=lineno, code=line.strip(),
                rule="NO_LOCAL_MATH", severity="ERROR",
                message=msg,
                suggestion="Use broker DXLink for option prices and Greeks.",
            ))
    return violations


def check_hardcoded_greeks(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag hardcoded Greek values (fallback defaults)."""
    violations = []
    # Pattern: delta = 0.5, theta = -0.05, gamma = 0.01, vega = 0.15, iv = 0.20
    patterns = [
        (r'(?:delta|gamma|theta|vega)\s*=\s*(?:Decimal\()?[\'"]?-?0\.\d+',
         "Hardcoded Greek value"),
        (r'(?:implied_vol|iv|volatility)\s*=\s*(?:Decimal\()?[\'"]?0\.\d+',
         "Hardcoded implied volatility"),
    ]
    for pattern, msg in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            # Skip legitimate patterns: function signatures with defaults, test assertions
            if 'def ' in line or 'assert' in line or '#' in line.split('=')[0]:
                continue
            # Skip: delta = pos.delta (reading from object, not hardcoding)
            stripped = line.strip()
            if '=' in stripped:
                rhs = stripped.split('=', 1)[1].strip()
                # If RHS starts with a variable access (not a literal), skip
                if re.match(r'^[a-zA-Z_]', rhs) and not re.match(r'^(?:Decimal|float)', rhs):
                    continue
            violations.append(Violation(
                file=filepath, line=lineno, code=line.strip(),
                rule="NO_HARDCODED_GREEKS", severity="ERROR",
                message=msg,
                suggestion="Fetch from broker DXLink or raise error if unavailable.",
            ))
    return violations


def check_hardcoded_correlation(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag hardcoded correlation values or matrices."""
    violations = []
    stripped = line.strip()

    # Pattern 1: correlation dict with literal values like ('AAPL', 'MSFT'): 0.8
    if re.search(r"\('\w+',\s*'\w+'\)\s*:\s*-?0\.\d+", stripped):
        violations.append(Violation(
            file=filepath, line=lineno, code=stripped,
            rule="NO_HARDCODED_CORRELATIONS", severity="ERROR",
            message="Hardcoded correlation pair value",
            suggestion="Compute from actual return data or raise error if data unavailable.",
        ))
        return violations

    # Pattern 2: correlation variable = literal
    if re.search(r'(?:corr|correlation)\s*[=\[{].*0\.\d', line, re.IGNORECASE):
        if 'def ' in line or 'import' in line:
            return []
        # Skip: initialization like `total_weighted_corr = 0.0`
        if re.match(r'^[\w_]+\s*=\s*0\.0\s*$', stripped):
            return []
        violations.append(Violation(
            file=filepath, line=lineno, code=stripped,
            rule="NO_HARDCODED_CORRELATIONS", severity="ERROR",
            message="Hardcoded correlation value",
            suggestion="Compute from actual return data or raise error if data unavailable.",
        ))
    return violations


def check_hardcoded_rates(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag hardcoded interest rates, dividend yields."""
    violations = []
    # Match: risk_free_rate = 0.05, risk_free_rate: float = 0.05, etc.
    # 0.0 is safe (means "no assumption") — only flag non-zero literal rates
    patterns = [
        (r'risk.free.rate\b.*\b0\.[1-9]\d*', "Hardcoded risk-free rate"),
        (r'risk.free.rate\b.*\b0\.0[1-9]\d*', "Hardcoded risk-free rate"),
        (r'dividend.yield\b.*=\s*(?:Decimal\()?[\'"]?0\.0[1-9]\d*', "Hardcoded dividend yield"),
    ]
    for pattern, msg in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            if 'def ' in line:
                violations.append(Violation(
                    file=filepath, line=lineno, code=line.strip(),
                    rule="NO_HARDCODED_RATES", severity="WARNING",
                    message=f"{msg} (function default)",
                    suggestion="Read from risk_config.yaml or fetch from treasury API.",
                ))
            else:
                violations.append(Violation(
                    file=filepath, line=lineno, code=line.strip(),
                    rule="NO_HARDCODED_RATES", severity="ERROR",
                    message=msg,
                    suggestion="Read from risk_config.yaml or fetch from treasury API.",
                ))
    return violations


def check_hardcoded_volatility(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag hardcoded volatility assumptions."""
    violations = []
    # Pattern: volatilities = {sym: 0.25 for sym in ...}
    if re.search(r'volatilit\w*\s*[=:]\s*\{.*0\.\d+', line, re.IGNORECASE):
        violations.append(Violation(
            file=filepath, line=lineno, code=line.strip(),
            rule="NO_HARDCODED_VOLATILITY", severity="ERROR",
            message="Hardcoded volatility assumption",
            suggestion="Compute from actual return data or get IV from broker.",
        ))
    # Pattern: vol = 0.25
    if re.search(r'\bvol(?:atility)?\s*=\s*0\.\d+', line, re.IGNORECASE):
        if 'def ' not in line:
            violations.append(Violation(
                file=filepath, line=lineno, code=line.strip(),
                rule="NO_HARDCODED_VOLATILITY", severity="ERROR",
                message="Hardcoded volatility value",
                suggestion="Compute from actual return data or get IV from broker.",
            ))
    return violations


def check_fallback_defaults(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag fallback/default values that mask missing market data."""
    violations = []
    # Pattern: return 0.5 (in correlation context — generic fallback)
    if re.search(r'return\s+0\.5\s*$', line.strip()):
        violations.append(Violation(
            file=filepath, line=lineno, code=line.strip(),
            rule="NO_FALLBACK_DEFAULTS", severity="WARNING",
            message="Fallback return value — may mask missing data",
            suggestion="Raise DataUnavailableError instead of returning a guess.",
        ))
    return violations


def check_local_var_calculation(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag local VaR, POP, EV calculations."""
    violations = []
    patterns = [
        (r'\bvar\s*=.*percentile\b', "Local VaR calculation"),
        (r'\bpop\s*=.*norm\.cdf\b', "Local POP (probability of profit) calculation"),
    ]
    for pattern, msg in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            violations.append(Violation(
                file=filepath, line=lineno, code=line.strip(),
                rule="NO_LOCAL_MATH", severity="ERROR",
                message=msg,
                suggestion="These calculations belong in market_analyzer, not eTrading.",
            ))
    # expected_value — only flag actual calculations, not DB columns or getattr
    if re.search(r'\bexpected.value\s*=', line, re.IGNORECASE):
        stripped = line.strip()
        # Skip: Column definitions, getattr, None assignments
        if any(kw in stripped for kw in ['Column(', 'getattr(', '= None', '=None']):
            return violations
        violations.append(Violation(
            file=filepath, line=lineno, code=stripped,
            rule="NO_LOCAL_MATH", severity="ERROR",
            message="Local expected value calculation",
            suggestion="These calculations belong in market_analyzer, not eTrading.",
        ))
    return violations


# ── Scanner ──


def check_hardcoded_risk_limits(line: str, lineno: int, filepath: str) -> List[Violation]:
    """Flag hardcoded risk limit percentages that should be in config."""
    violations = []
    stripped = line.strip()
    # Pattern: portfolio_value * Decimal('0.03') — embedded risk limit
    if re.search(r'portfolio.value\s*\*\s*Decimal\([\'"]0\.\d+', stripped):
        violations.append(Violation(
            file=filepath, line=lineno, code=stripped,
            rule="NO_HARDCODED_RISK_LIMITS", severity="WARNING",
            message="Hardcoded risk limit percentage — should be in risk_config.yaml",
            suggestion="Move to risk_config.yaml and load via get_risk_config().",
        ))
    return violations


ALL_CHECKS = [
    check_black_scholes,
    check_hardcoded_greeks,
    check_hardcoded_correlation,
    check_hardcoded_rates,
    check_hardcoded_volatility,
    check_fallback_defaults,
    check_local_var_calculation,
    check_hardcoded_risk_limits,
]


def scan_file(filepath: Path) -> List[Violation]:
    """Scan a single Python file for violations."""
    violations = []
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return violations

    lines = content.splitlines()
    in_docstring = False

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track docstrings (triple-quoted strings)
        triple_count = stripped.count('"""') + stripped.count("'''")
        if triple_count == 1:
            in_docstring = not in_docstring
            continue
        if triple_count >= 2:
            # Opening and closing on same line — skip this line
            continue
        if in_docstring:
            continue

        # Skip comments and empty lines
        if not stripped or stripped.startswith('#'):
            continue

        for check in ALL_CHECKS:
            violations.extend(check(line, lineno, str(filepath)))

    return violations


def scan_codebase(root: Path, strict: bool = False) -> List[Violation]:
    """Scan the entire codebase for market data violations."""
    violations = []

    for pyfile in sorted(root.rglob('*.py')):
        # Skip excluded directories
        rel_parts = pyfile.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if pyfile.name in SKIP_FILES:
            continue

        file_violations = scan_file(pyfile)

        if not strict:
            file_violations = [v for v in file_violations if v.severity == 'ERROR']

        violations.extend(file_violations)

    return violations


def format_report(violations: List[Violation], show_fix: bool = False) -> str:
    """Format violations into a readable report."""
    if not violations:
        return (
            "\n"
            "  ZERO LOCAL MATH AUDIT — CLEAN\n"
            "  No violations found. All market data comes from broker.\n"
        )

    lines = [
        "",
        "  ZERO LOCAL MATH AUDIT — VIOLATIONS FOUND",
        "  " + "=" * 68,
        "",
    ]

    # Group by file
    by_file: dict[str, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    errors = sum(1 for v in violations if v.severity == 'ERROR')
    warnings = sum(1 for v in violations if v.severity == 'WARNING')

    for filepath, file_violations in sorted(by_file.items()):
        # Shorten path for display
        short = filepath.replace('\\', '/')
        if 'trading_cotrader/' in short:
            short = short.split('trading_cotrader/', 1)[1]
        lines.append(f"  {short}")
        lines.append("  " + "-" * 60)

        for v in sorted(file_violations, key=lambda x: x.line):
            sev = "ERR" if v.severity == "ERROR" else "WRN"
            lines.append(f"    L{v.line:<5} [{sev}] {v.rule}")
            lines.append(f"           {v.code[:80]}")
            lines.append(f"           {v.message}")
            if show_fix and v.suggestion:
                lines.append(f"           FIX: {v.suggestion}")
            lines.append("")

    lines.extend([
        "  " + "=" * 68,
        f"  Total: {len(violations)} violation(s) — {errors} error(s), {warnings} warning(s)",
        "",
        "  Policy: Greeks, prices, correlations, volatility MUST come from broker.",
        "  If data unavailable, raise an error — never return a guess.",
    ])

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit codebase for hardcoded market data")
    parser.add_argument('--fix', action='store_true', help='Show fix suggestions')
    parser.add_argument('--strict', action='store_true', help='Include warnings')
    parser.add_argument('--path', type=str, default=None,
                        help='Path to scan (default: trading_cotrader/)')
    args = parser.parse_args()

    root = Path(args.path) if args.path else Path(__file__).resolve().parents[1]

    print()
    print("  Scanning for zero-local-math violations...")
    print(f"  Root: {root}")
    print()

    violations = scan_codebase(root, strict=args.strict)
    report = format_report(violations, show_fix=args.fix)
    print(report)

    # Exit code: 1 if errors found
    errors = sum(1 for v in violations if v.severity == 'ERROR')
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
