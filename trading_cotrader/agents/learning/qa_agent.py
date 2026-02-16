"""
QA Agent — Daily test health assessment and gap identification.

Runs in REPORTING state to:
1. Run pytest with coverage and capture results
2. Analyze per-file coverage percentages
3. Identify untested files and low-coverage modules
4. Catalog boundary/edge cases from existing tests
5. Suggest new test cases for uncovered code paths
6. Persist QA report to decision_log table

Usage:
    qa = QAAgent(config)
    result = qa.run(context)
"""

import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class QAAgent:
    """Daily QA assessment agent."""

    name = "qa_agent"

    def __init__(self, config=None):
        self.config = config
        self._min_coverage_pct = 70.0
        if config:
            qa_config = getattr(config, 'qa', None)
            if qa_config and hasattr(qa_config, 'min_coverage_pct'):
                self._min_coverage_pct = qa_config.min_coverage_pct

    def run(self, context: dict) -> AgentResult:
        """Run daily QA assessment."""
        messages = []
        data = {}

        try:
            # 1. Run tests and capture results
            test_results = self._run_tests()
            data['test_results'] = test_results
            messages.append(
                f"Tests: {test_results['passed']}/{test_results['total']} passed "
                f"({test_results['failed']} failed, {test_results['errors']} errors)"
            )

            # 2. Run coverage analysis
            coverage = self._run_coverage()
            data['coverage'] = coverage
            if coverage.get('total_pct') is not None:
                messages.append(f"Coverage: {coverage['total_pct']:.1f}%")
            else:
                messages.append("Coverage: not available (pytest-cov not installed?)")

            # 3. Identify low-coverage files
            low_coverage = self._find_low_coverage(coverage)
            data['low_coverage_files'] = low_coverage
            if low_coverage:
                messages.append(f"Low coverage ({len(low_coverage)} files below {self._min_coverage_pct}%)")

            # 4. Suggest test cases
            suggestions = self._suggest_test_cases(low_coverage)
            data['suggestions'] = suggestions
            if suggestions:
                messages.append(f"Suggested {len(suggestions)} new test cases")

            # 5. Build report
            report = self._build_report(test_results, coverage, low_coverage, suggestions)
            data['qa_report'] = report
            context['qa_report'] = report

            # 6. Persist to decision_log
            self._persist_report(report)

            status = AgentStatus.COMPLETED
            if test_results['failed'] > 0:
                status = AgentStatus.ERROR
                messages.append("FAILING TESTS DETECTED")

        except Exception as e:
            logger.error(f"QA agent error: {e}")
            messages.append(f"QA assessment failed: {e}")
            status = AgentStatus.ERROR

        return AgentResult(
            agent_name=self.name,
            status=status,
            data=data,
            messages=messages,
            metrics={
                'tests_passed': data.get('test_results', {}).get('passed', 0),
                'tests_failed': data.get('test_results', {}).get('failed', 0),
                'coverage_pct': data.get('coverage', {}).get('total_pct', 0),
            },
        )

    def safety_check(self, context: dict) -> tuple:
        """QA agent is always safe to run."""
        return True, ""

    def _run_tests(self) -> Dict[str, Any]:
        """Run pytest and capture results."""
        try:
            result = subprocess.run(
                ['python', '-m', 'pytest', 'trading_cotrader/tests/', '-v', '--tb=short', '-q'],
                capture_output=True, text=True, timeout=120,
                cwd=str(Path(__file__).parent.parent.parent.parent),
            )

            output = result.stdout + result.stderr
            passed = failed = errors = 0

            for line in output.splitlines():
                if 'passed' in line and ('failed' in line or 'error' in line or line.strip().startswith('=')):
                    # Parse summary line like "116 passed, 2 failed"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'passed' in part and i > 0:
                            try:
                                passed = int(parts[i - 1])
                            except ValueError:
                                pass
                        if 'failed' in part and i > 0:
                            try:
                                failed = int(parts[i - 1])
                            except ValueError:
                                pass
                        if 'error' in part and i > 0:
                            try:
                                errors = int(parts[i - 1])
                            except ValueError:
                                pass
                elif 'passed' in line and line.strip().startswith('='):
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if 'passed' in part and i > 0:
                            try:
                                passed = int(parts[i - 1])
                            except ValueError:
                                pass

            return {
                'total': passed + failed + errors,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'return_code': result.returncode,
                'duration_hint': 'see output',
            }

        except subprocess.TimeoutExpired:
            return {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'return_code': -1, 'timeout': True}
        except Exception as e:
            logger.warning(f"Failed to run tests: {e}")
            return {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0, 'return_code': -1, 'error': str(e)}

    def _run_coverage(self) -> Dict[str, Any]:
        """Run pytest with coverage and parse results."""
        try:
            result = subprocess.run(
                [
                    'python', '-m', 'pytest', 'trading_cotrader/tests/',
                    '--cov=trading_cotrader', '--cov-report=json', '-q',
                ],
                capture_output=True, text=True, timeout=180,
                cwd=str(Path(__file__).parent.parent.parent.parent),
            )

            # Read coverage JSON
            cov_json_path = Path(__file__).parent.parent.parent.parent / 'coverage.json'
            if cov_json_path.exists():
                with open(cov_json_path, 'r') as f:
                    cov_data = json.load(f)

                total_pct = cov_data.get('totals', {}).get('percent_covered', 0)
                files = {}
                for fpath, fdata in cov_data.get('files', {}).items():
                    files[fpath] = {
                        'covered_lines': fdata.get('summary', {}).get('covered_lines', 0),
                        'num_statements': fdata.get('summary', {}).get('num_statements', 0),
                        'percent_covered': fdata.get('summary', {}).get('percent_covered', 0),
                        'missing_lines': fdata.get('summary', {}).get('missing_lines', 0),
                    }

                return {
                    'total_pct': total_pct,
                    'files': files,
                }

            return {'total_pct': None, 'files': {}, 'note': 'coverage.json not generated'}

        except subprocess.TimeoutExpired:
            return {'total_pct': None, 'files': {}, 'note': 'coverage timed out'}
        except Exception as e:
            logger.warning(f"Coverage analysis failed: {e}")
            return {'total_pct': None, 'files': {}, 'note': str(e)}

    def _find_low_coverage(self, coverage: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find files with coverage below threshold."""
        low = []
        for fpath, fdata in coverage.get('files', {}).items():
            pct = fdata.get('percent_covered', 100)
            if pct < self._min_coverage_pct:
                low.append({
                    'file': fpath,
                    'percent_covered': pct,
                    'missing_lines': fdata.get('missing_lines', 0),
                    'num_statements': fdata.get('num_statements', 0),
                })
        return sorted(low, key=lambda x: x['percent_covered'])

    def _suggest_test_cases(self, low_coverage_files: List[Dict]) -> List[Dict[str, str]]:
        """Suggest test cases for low-coverage files."""
        suggestions = []
        for entry in low_coverage_files[:10]:
            fpath = entry['file']
            module = Path(fpath).stem

            # Suggest based on module type
            if 'service' in module:
                suggestions.append({
                    'file': fpath,
                    'suggestion': f"Add unit tests for {module}: mock dependencies, test public methods",
                    'priority': 'high' if entry['percent_covered'] < 30 else 'medium',
                })
            elif 'agent' in module:
                suggestions.append({
                    'file': fpath,
                    'suggestion': f"Add tests for {module}.run(): test context updates, edge cases",
                    'priority': 'medium',
                })
            elif 'repository' in module or 'repo' in module:
                suggestions.append({
                    'file': fpath,
                    'suggestion': f"Add DB round-trip tests for {module}: CRUD + edge cases",
                    'priority': 'medium',
                })
            else:
                suggestions.append({
                    'file': fpath,
                    'suggestion': f"Review {module} for untested code paths",
                    'priority': 'low',
                })

        return suggestions

    def _build_report(
        self,
        test_results: Dict,
        coverage: Dict,
        low_coverage: List[Dict],
        suggestions: List[Dict],
    ) -> str:
        """Build structured QA report."""
        lines = [
            "=== QA ASSESSMENT REPORT ===",
            f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
            "",
            "--- TEST RESULTS ---",
            f"Total: {test_results['total']}  |  Passed: {test_results['passed']}  |  "
            f"Failed: {test_results['failed']}  |  Errors: {test_results['errors']}",
        ]

        if coverage.get('total_pct') is not None:
            lines.extend([
                "",
                "--- COVERAGE ---",
                f"Total: {coverage['total_pct']:.1f}%",
            ])

        if low_coverage:
            lines.extend([
                "",
                f"--- LOW COVERAGE FILES (below {self._min_coverage_pct}%) ---",
            ])
            for entry in low_coverage[:15]:
                lines.append(
                    f"  {entry['file']}: {entry['percent_covered']:.1f}% "
                    f"({entry['missing_lines']} lines uncovered)"
                )

        if suggestions:
            lines.extend([
                "",
                "--- SUGGESTED TEST CASES ---",
            ])
            for s in suggestions:
                lines.append(f"  [{s['priority'].upper()}] {s['suggestion']}")

        lines.append("")
        lines.append("=== END QA REPORT ===")
        return "\n".join(lines)

    def _persist_report(self, report: str) -> None:
        """Persist QA report to decision_log table."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import DecisionLogORM
            import uuid

            with session_scope() as session:
                entry = DecisionLogORM(
                    id=str(uuid.uuid4()),
                    decision_type='qa_report',
                    agent_name=self.name,
                    summary='Daily QA Assessment',
                    details_json={'report': report},
                    created_at=datetime.utcnow(),
                )
                session.add(entry)

        except Exception as e:
            logger.debug(f"Could not persist QA report: {e}")
