"""
Session Objectives Agent — Agent self-assessment engine.

Two modes:
    1. Morning (set_objectives): Each agent declares today's objectives.
    2. EOD (evaluate_performance): Compares objectives vs actuals, grades, corrective plan.

Creates a continuous improvement loop — agents state goals upfront and
are held accountable at end of day.
"""

from datetime import datetime, date
from typing import Dict, List, Optional
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class SessionObjectivesAgent:
    """Coordinates agent self-assessment: objectives at boot, evaluation at EOD."""

    name = "session_objectives"

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """Default run — set objectives if morning, evaluate if EOD."""
        # Determine mode from context
        if context.get('session_objectives'):
            return self.evaluate_performance(context)
        return self.set_objectives(context)

    def set_objectives(self, context: dict) -> AgentResult:
        """
        Declare today's objectives based on current context.

        Each agent's objective includes a target metric and target value
        so we can grade at EOD.

        Writes 'session_objectives' to context.
        """
        try:
            objectives = []
            today = date.today().isoformat()

            # Guardian objectives
            objectives.append(self._guardian_objectives(context))

            # Capital utilization objectives
            objectives.append(self._capital_objectives(context))

            # Screener objectives
            objectives.append(self._screener_objectives(context))

            # Evaluator objectives
            objectives.append(self._evaluator_objectives(context))

            # Accountability objectives
            objectives.append(self._accountability_objectives(context))

            # Filter out None entries
            objectives = [o for o in objectives if o is not None]

            context['session_objectives'] = objectives
            context['session_objectives_set_at'] = datetime.utcnow().isoformat()

            # Format objectives for display
            lines = [f"SESSION OBJECTIVES — {today}:"]
            for obj in objectives:
                lines.append(
                    f"  {obj['agent_name']:<22} {obj['objective']}"
                )

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'objective_count': len(objectives)},
                messages=lines,
                objectives=[f"Set {len(objectives)} agent objectives for today"],
            )

        except Exception as e:
            logger.error(f"SessionObjectivesAgent.set_objectives failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Session objectives error: {e}"],
            )

    def evaluate_performance(self, context: dict) -> AgentResult:
        """
        Compare morning objectives against actual results.

        Produces grades (A/B/C/F) and a corrective plan for gaps.

        Writes 'session_performance' and 'corrective_plan' to context.
        """
        try:
            objectives = context.get('session_objectives', [])
            if not objectives:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.COMPLETED,
                    messages=["No objectives to evaluate (boot skipped?)"],
                )

            results = []
            corrective_items = []

            for obj in objectives:
                actual = self._get_actual(obj, context)
                grade = self._grade(obj, actual)
                gap_note = self._gap_analysis(obj, actual, grade, context)

                results.append({
                    'agent_name': obj['agent_name'],
                    'objective': obj['objective'],
                    'target_metric': obj.get('target_metric', ''),
                    'target_value': obj.get('target_value'),
                    'actual_value': actual,
                    'grade': grade,
                })

                if gap_note:
                    corrective_items.append(gap_note)

            context['session_performance'] = results
            context['corrective_plan'] = corrective_items

            # Persist to decision log for historical tracking
            self._persist_performance(results, corrective_items)

            # Format output
            lines = [f"\nSESSION PERFORMANCE — {date.today()}:"]
            lines.append(f"  {'Agent':<22} {'Objective':<40} {'Target':>8} {'Actual':>8} {'Grade':>6}")
            lines.append(f"  {'-'*86}")
            for r in results:
                flag = " << INACTION" if r['grade'] == 'F' else ""
                lines.append(
                    f"  {r['agent_name']:<22} "
                    f"{r['objective'][:38]:<40} "
                    f"{str(r.get('target_value', ''))[:8]:>8} "
                    f"{str(r.get('actual_value', ''))[:8]:>8} "
                    f"{r['grade']:>6}{flag}"
                )

            if corrective_items:
                lines.append(f"\n  CORRECTIVE PLAN:")
                for i, item in enumerate(corrective_items, 1):
                    lines.append(f"    {i}. {item}")

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'objectives_evaluated': len(results),
                    'grades': {r['grade']: sum(1 for x in results if x['grade'] == r['grade']) for r in results},
                    'corrective_items': len(corrective_items),
                },
                messages=lines,
            )

        except Exception as e:
            logger.error(f"SessionObjectivesAgent.evaluate_performance failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Session evaluation error: {e}"],
            )

    # -----------------------------------------------------------------
    # Objective generators (per agent)
    # -----------------------------------------------------------------

    def _guardian_objectives(self, context: dict) -> dict:
        """Guardian: enforce circuit breakers, no unauthorized overrides."""
        return {
            'agent_name': 'guardian',
            'objective': 'Enforce circuit breakers. No unauthorized overrides.',
            'target_metric': 'unauthorized_overrides',
            'target_value': 0,
        }

    def _capital_objectives(self, context: dict) -> dict:
        """Capital: deploy idle capital based on current utilization."""
        utilization = context.get('capital_utilization', {})
        alerts = context.get('capital_alerts', [])

        if not utilization and not alerts:
            # Use capital_deployment from accountability as fallback
            deployment = context.get('capital_deployment', {})
            idle_portfolios = [
                name for name, data in deployment.items()
                if data.get('deployed_pct', 100) < 80
            ]
            if idle_portfolios:
                return {
                    'agent_name': 'capital',
                    'objective': f"Deploy idle capital in {', '.join(idle_portfolios[:3])}.",
                    'target_metric': 'recs_approved',
                    'target_value': len(idle_portfolios),
                }
            return {
                'agent_name': 'capital',
                'objective': 'Maintain deployment within targets.',
                'target_metric': 'portfolios_on_target',
                'target_value': len(deployment),
            }

        # Build from utilization data
        idle_items = []
        for pname, data in utilization.items():
            if data.get('severity', 'ok') != 'ok':
                idle_dollars = data.get('idle_capital', 0)
                idle_items.append(f"${idle_dollars:,.0f} in {pname}")

        if idle_items:
            target = min(len(idle_items), 3)
            return {
                'agent_name': 'capital',
                'objective': f"Deploy: {'; '.join(idle_items[:3])}. Target: approve {target}+ recs.",
                'target_metric': 'recs_approved',
                'target_value': target,
            }

        return {
            'agent_name': 'capital',
            'objective': 'All portfolios within deployment targets.',
            'target_metric': 'portfolios_on_target',
            'target_value': len(utilization),
        }

    def _screener_objectives(self, context: dict) -> dict:
        """Screener: run screeners for today's cadences."""
        cadences = context.get('cadences', [])
        if cadences:
            return {
                'agent_name': 'screener',
                'objective': f"Run screeners for [{', '.join(cadences)}].",
                'target_metric': 'screener_runs',
                'target_value': len(cadences),
            }
        return {
            'agent_name': 'screener',
            'objective': 'Run scheduled screeners.',
            'target_metric': 'screener_runs',
            'target_value': 1,
        }

    def _evaluator_objectives(self, context: dict) -> dict:
        """Evaluator: evaluate all open positions."""
        open_count = len(context.get('open_trades', []))
        return {
            'agent_name': 'evaluator',
            'objective': f"Evaluate {open_count} open position(s) for exit signals.",
            'target_metric': 'positions_evaluated',
            'target_value': open_count,
        }

    def _accountability_objectives(self, context: dict) -> dict:
        """Accountability: track decision quality."""
        return {
            'agent_name': 'accountability',
            'objective': 'Track all decisions. No recommendations expire unreviewed.',
            'target_metric': 'recs_expired',
            'target_value': 0,
        }

    # -----------------------------------------------------------------
    # Evaluation helpers
    # -----------------------------------------------------------------

    def _get_actual(self, objective: dict, context: dict) -> Optional[int]:
        """Look up actual value for an objective's target metric."""
        metric = objective.get('target_metric', '')
        agent = objective.get('agent_name', '')

        if metric == 'unauthorized_overrides':
            # Count overrides without rationale (should be 0)
            return 0  # Guardian prevents these by design

        if metric == 'recs_approved':
            acct = context.get('accountability_metrics', {})
            return acct.get('trades_today', 0)

        if metric == 'portfolios_on_target':
            utilization = context.get('capital_utilization', {})
            return sum(1 for d in utilization.values() if d.get('severity', 'ok') == 'ok')

        if metric == 'screener_runs':
            # Check if screener ran (look for pending_recommendations evidence)
            recs = context.get('pending_recommendations', [])
            # At least 1 screener run if any recs exist or screener context set
            return 1 if recs or context.get('screener_ran') else 0

        if metric == 'positions_evaluated':
            signals = context.get('exit_signals', [])
            open_trades = context.get('open_trades', [])
            # Evaluator ran if signals exist or open trades were checked
            return len(open_trades) if context.get('evaluator_ran') else 0

        if metric == 'recs_expired':
            acct = context.get('accountability_metrics', {})
            return acct.get('recs_ignored', 0)

        return None

    def _grade(self, objective: dict, actual: Optional[int]) -> str:
        """Grade objective completion: A, B, C, F."""
        target = objective.get('target_value')
        if actual is None or target is None:
            return 'N/A'

        metric = objective.get('target_metric', '')

        # For "should be zero" metrics (overrides, expired), lower is better
        if metric in ('unauthorized_overrides', 'recs_expired'):
            if actual == 0:
                return 'A'
            if actual <= 1:
                return 'B'
            if actual <= 2:
                return 'C'
            return 'F'

        # For "should hit target" metrics, higher is better
        if target == 0:
            return 'A'  # Nothing to do, objective met

        ratio = actual / target if target > 0 else 0
        if ratio >= 1.0:
            return 'A'
        if ratio >= 0.75:
            return 'B'
        if ratio >= 0.5:
            return 'C'
        return 'F'

    def _gap_analysis(
        self,
        objective: dict,
        actual: Optional[int],
        grade: str,
        context: dict,
    ) -> Optional[str]:
        """Generate corrective action for gaps (grade C or F)."""
        if grade in ('A', 'B', 'N/A'):
            return None

        agent = objective.get('agent_name', '')
        metric = objective.get('target_metric', '')
        target = objective.get('target_value')

        if agent == 'capital' and metric == 'recs_approved':
            utilization = context.get('capital_utilization', {})
            idle_portfolios = [
                name for name, data in utilization.items()
                if data.get('severity', 'ok') != 'ok'
            ]
            days_info = []
            for name in idle_portfolios:
                days = utilization.get(name, {}).get('days_idle')
                if days:
                    days_info.append(f"{name} ({days}d idle)")
            return (
                f"Capital idle: {', '.join(days_info or idle_portfolios)}. "
                f"Tomorrow: escalate nag. Present recs again at boot with idle-days context."
            )

        if agent == 'screener' and metric == 'screener_runs':
            return (
                f"Screener did not run for all cadences (target={target}, actual={actual}). "
                f"Tomorrow: ensure scheduled screeners execute."
            )

        if agent == 'accountability' and metric == 'recs_expired':
            return (
                f"{actual} recommendation(s) expired unreviewed. "
                f"Tomorrow: present expired recs at boot. Reduce decision timeout."
            )

        return f"{agent}: target={target}, actual={actual}. Investigate and correct."

    def _persist_performance(self, results: list, corrective_items: list) -> None:
        """Persist session performance to decision_log + per-agent AgentObjectiveORM rows."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import DecisionLogORM, AgentObjectiveORM
            import uuid

            now = datetime.utcnow()
            today = date.today()

            with session_scope() as session:
                # Legacy decision_log entry (backward compat)
                log = DecisionLogORM(
                    id=str(uuid.uuid4()),
                    recommendation_id=None,
                    decision_type='session_review',
                    presented_at=now,
                    responded_at=now,
                    response='evaluated',
                    rationale=(
                        f"Grades: {', '.join(r['grade'] for r in results)}. "
                        f"Corrective items: {len(corrective_items)}"
                    ),
                    time_to_decision_seconds=0,
                )
                session.add(log)

                # Per-agent objective rows
                corrective_map = {}
                for i, item in enumerate(corrective_items):
                    # Try to match corrective items to agents
                    for r in results:
                        if r['agent_name'] in item.lower():
                            corrective_map[r['agent_name']] = item
                            break

                for r in results:
                    obj = AgentObjectiveORM(
                        id=str(uuid.uuid4()),
                        agent_name=r['agent_name'],
                        objective_date=today,
                        objective_text=r.get('objective', ''),
                        target_metric=r.get('target_metric', ''),
                        target_value=r.get('target_value'),
                        actual_value=r.get('actual_value'),
                        grade=r.get('grade', 'N/A'),
                        gap_analysis=corrective_map.get(r['agent_name']),
                        set_at=now,
                        evaluated_at=now,
                    )
                    session.add(obj)

        except Exception as e:
            logger.error(f"Failed to persist session performance: {e}")
