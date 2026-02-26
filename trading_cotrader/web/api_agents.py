"""
Agent API Router — Dashboard visibility for all 15 agents.

Mounted in approval_api.py at /api/v2 alongside existing v2 routes.

Endpoints:
    GET /agents               — All 15 agents with status, latest run, grade
    GET /agents/summary       — Dashboard stats (error count, avg duration, grades)
    GET /agents/runs/latest   — Latest run per agent
    GET /agents/context       — Current engine context (truncated)
    GET /agents/timeline      — Recent cycle timeline
    GET /agents/ml-status     — ML pipeline readiness
    GET /agents/{name}        — Single agent detail
    GET /agents/{name}/runs   — Paginated run history
    GET /agents/{name}/objectives — Historical objectives + grades
"""

from datetime import datetime, date, timedelta
from typing import TYPE_CHECKING, Any, Optional
import json
import logging

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import func, desc

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import AgentRunORM, AgentObjectiveORM

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent registry — built dynamically from BaseAgent.get_metadata()
# ---------------------------------------------------------------------------

def _build_registry(engine) -> dict:
    """Build agent registry from class metadata on BaseAgent subclasses."""
    from trading_cotrader.agents.base import BaseAgent

    registry = {}
    for attr_name in ['sentinel', 'scout', 'steward', 'maverick', 'atlas']:
        agent = getattr(engine, attr_name, None)
        if agent and isinstance(agent, BaseAgent):
            meta = agent.get_metadata()
            registry[meta['name']] = meta
    return registry


# Fallback static registry for when engine hasn't initialized yet
AGENT_REGISTRY: dict[str, dict] = {
    'sentinel': {
        'display_name': 'Sentinel (Risk)',
        'category': 'domain',
        'role': 'Risk manager, circuit breakers & execution gatekeeper',
        'intro': 'I am the risk manager. Circuit breakers, VaR, concentration, fitness checks, kill switch -- nothing gets through without my approval.',
        'description': 'Combined risk manager: circuit breakers + portfolio risk metrics.',
        'responsibilities': ['Circuit breakers (daily/weekly loss)', 'VIX halt threshold', 'Emergency halt', 'Parametric VaR', 'Concentration', 'Portfolio fitness', 'Trade execution gate'],
        'datasources': ['workflow_rules.yaml', 'VIX feed', 'Daily P&L', 'PortfolioORM', 'PositionORM', 'Broker adapters'],
        'boundaries': ['Cannot override human halt decisions', 'LIMIT orders only', 'Reports risk metrics, gates trades'],
        'runs_during': ['booting', 'screening', 'monitoring', 'execution'],
    },
    'scout': {
        'display_name': 'Scout (Quant)',
        'category': 'domain',
        'role': 'Research pipeline — market analysis, screening, ranking',
        'intro': 'I own the ResearchContainer and populate it from MarketAnalyzer. I screen the watchlist for setups and rank candidates for Maverick.',
        'description': 'Owns ResearchContainer. Populates from market_analyzer library, screens for setups, ranks candidates.',
        'responsibilities': ['Watchlist data population', 'Market screening (breakout, momentum, mean-reversion, income)', 'Candidate ranking', 'Black swan monitoring', 'Market context assessment'],
        'datasources': ['market_analyzer library', 'ResearchContainer'],
        'boundaries': ['Read-only — does not book trades', 'Produces signals for Maverick to act on'],
        'runs_during': ['monitoring'],
    },
    'steward': {
        'display_name': 'Steward (Portfolio)',
        'category': 'domain',
        'role': 'Portfolio state, positions, P&L, capital utilization',
        'intro': 'I manage portfolio state. Positions, P&L tracking, capital utilization, position monitoring.',
        'description': 'Portfolio manager: state, positions, P&L, capital utilization.',
        'responsibilities': ['Portfolio state', 'Position monitoring', 'P&L tracking', 'Capital utilization', 'Broker sync coordination'],
        'datasources': ['PortfolioORM', 'PositionORM', 'TradeORM', 'Broker adapters', 'PortfolioBundle'],
        'boundaries': ['Read-only portfolio state', 'Does not place trades', 'Does not evaluate risk'],
        'runs_during': ['booting', 'monitoring'],
    },
    'maverick': {
        'display_name': 'Maverick (Trader)',
        'category': 'domain',
        'role': 'Trading orchestration & Scout/Steward cross-reference',
        'intro': 'I bring it all together. I cross-reference portfolio positions with market intelligence to surface trading signals.',
        'description': 'Domain orchestrator: cross-references Scout (research) + Steward (portfolio) for trading decisions.',
        'responsibilities': ['Trading orchestration', 'Scout/Steward cross-reference', 'Trading signals', 'Blotter data coordination', 'Order execution', 'Notifications', 'Session objectives', 'Decision tracking'],
        'datasources': ['PortfolioBundle (via ContainerManager)', 'ResearchContainer (via ContainerManager)', 'DecisionLogORM', 'Broker adapters'],
        'boundaries': ['LIMIT orders only', 'Requires explicit approval', 'Cannot override risk limits'],
        'runs_during': ['booting', 'monitoring', 'execution', 'reporting'],
    },
    'atlas': {
        'display_name': 'Atlas (Infra)',
        'category': 'domain',
        'role': 'Infrastructure, ops & QA',
        'intro': 'I handle the plumbing. Reports, test health, performance tracking.',
        'description': 'Consolidated infrastructure: reporting, QA, system health.',
        'responsibilities': ['Daily reports', 'Performance reports', 'Test suite health', 'Coverage analysis', 'System health monitoring'],
        'datasources': ['PortfolioORM', 'TradeORM', 'PerformanceMetricsService', 'pytest runner'],
        'boundaries': ['Cannot make trading decisions', 'Infrastructure and reporting only'],
        'runs_during': ['reporting'],
    },
}


def _safe_json(val: Any) -> Any:
    """Convert non-serializable values to string."""
    if val is None:
        return None
    try:
        json.dumps(val)
        return val
    except (TypeError, ValueError):
        return str(val)


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_agents_router(engine: 'WorkflowEngine') -> APIRouter:
    router = APIRouter(tags=["agents"])

    # ------------------------------------------------------------------
    # GET /agents — All 15 agents with latest run + grade
    # ------------------------------------------------------------------
    @router.get("/agents")
    async def list_agents():
        # Try dynamic registry from agent classes, fall back to static
        registry = _build_registry(engine) or AGENT_REGISTRY
        agents = []
        with session_scope() as session:
            for name, meta in registry.items():
                # Latest run
                latest_run = (
                    session.query(AgentRunORM)
                    .filter(AgentRunORM.agent_name == name)
                    .order_by(desc(AgentRunORM.started_at))
                    .first()
                )
                # Run count
                run_count = (
                    session.query(func.count(AgentRunORM.id))
                    .filter(AgentRunORM.agent_name == name)
                    .scalar()
                ) or 0
                # Today's grade
                today_obj = (
                    session.query(AgentObjectiveORM)
                    .filter(
                        AgentObjectiveORM.agent_name == name,
                        AgentObjectiveORM.objective_date == date.today(),
                    )
                    .first()
                )

                agents.append({
                    'name': name,
                    'display_name': meta['display_name'],
                    'category': meta['category'],
                    'role': meta['role'],
                    'intro': meta.get('intro', ''),
                    'description': meta['description'],
                    'responsibilities': meta['responsibilities'],
                    'datasources': meta.get('datasources', []),
                    'boundaries': meta.get('boundaries', []),
                    'runs_during': meta['runs_during'],
                    'capabilities_implemented': meta.get('capabilities_implemented', []),
                    'capabilities_planned': meta.get('capabilities_planned', []),
                    'status': latest_run.status if latest_run else 'idle',
                    'last_run_at': _iso(latest_run.started_at) if latest_run else None,
                    'last_duration_ms': latest_run.duration_ms if latest_run else None,
                    'last_error': latest_run.error_message if latest_run and latest_run.status == 'error' else None,
                    'run_count': run_count,
                    'today_grade': today_obj.grade if today_obj else None,
                    'today_objective': today_obj.objective_text if today_obj else None,
                })
        return agents

    # ------------------------------------------------------------------
    # GET /agents/summary — Dashboard stats
    # ------------------------------------------------------------------
    @router.get("/agents/summary")
    async def agents_summary():
        with session_scope() as session:
            today_start = datetime.combine(date.today(), datetime.min.time())

            total_runs = (
                session.query(func.count(AgentRunORM.id))
                .filter(AgentRunORM.started_at >= today_start)
                .scalar()
            ) or 0

            error_count = (
                session.query(func.count(AgentRunORM.id))
                .filter(
                    AgentRunORM.started_at >= today_start,
                    AgentRunORM.status == 'error',
                )
                .scalar()
            ) or 0

            avg_duration = (
                session.query(func.avg(AgentRunORM.duration_ms))
                .filter(AgentRunORM.started_at >= today_start)
                .scalar()
            ) or 0

            # Grade distribution
            grades = (
                session.query(AgentObjectiveORM.grade, func.count(AgentObjectiveORM.id))
                .filter(AgentObjectiveORM.objective_date == date.today())
                .group_by(AgentObjectiveORM.grade)
                .all()
            )
            grade_dist = {g: c for g, c in grades}

            return {
                'total_agents': len(_build_registry(engine) or AGENT_REGISTRY),
                'today_runs': total_runs,
                'today_errors': error_count,
                'avg_duration_ms': round(avg_duration, 1),
                'grade_distribution': grade_dist,
                'cycle_count': engine.context.get('cycle_count', 0),
                'current_state': engine.state,
            }

    # ------------------------------------------------------------------
    # GET /agents/runs/latest — Latest run per agent
    # ------------------------------------------------------------------
    @router.get("/agents/runs/latest")
    async def latest_runs():
        results = []
        with session_scope() as session:
            for name in (_build_registry(engine) or AGENT_REGISTRY):
                run = (
                    session.query(AgentRunORM)
                    .filter(AgentRunORM.agent_name == name)
                    .order_by(desc(AgentRunORM.started_at))
                    .first()
                )
                if run:
                    results.append({
                        'agent_name': run.agent_name,
                        'status': run.status,
                        'started_at': _iso(run.started_at),
                        'duration_ms': run.duration_ms,
                        'workflow_state': run.workflow_state,
                        'cycle_id': run.cycle_id,
                        'messages': run.messages or [],
                        'error_message': run.error_message,
                    })
        return results

    # ------------------------------------------------------------------
    # GET /agents/context — Current engine context (truncated)
    # ------------------------------------------------------------------
    @router.get("/agents/context")
    async def agent_context():
        ctx = {}
        for k, v in engine.context.items():
            s = _safe_json(v)
            # Truncate large values
            if isinstance(s, (list, dict)):
                try:
                    serialized = json.dumps(s)
                    if len(serialized) > 2000:
                        ctx[k] = f"<{type(v).__name__}, {len(serialized)} chars>"
                    else:
                        ctx[k] = s
                except (TypeError, ValueError):
                    ctx[k] = str(v)[:200]
            else:
                ctx[k] = s
        return ctx

    # ------------------------------------------------------------------
    # GET /agents/timeline — Recent cycles timeline
    # ------------------------------------------------------------------
    @router.get("/agents/timeline")
    async def agent_timeline(cycles: int = Query(3, ge=1, le=20)):
        with session_scope() as session:
            # Get max cycle_id
            max_cycle = (
                session.query(func.max(AgentRunORM.cycle_id))
                .scalar()
            ) or 0

            min_cycle = max(1, max_cycle - cycles + 1)

            runs = (
                session.query(AgentRunORM)
                .filter(AgentRunORM.cycle_id >= min_cycle)
                .order_by(AgentRunORM.cycle_id, AgentRunORM.started_at)
                .all()
            )

            timeline = {}
            for run in runs:
                cid = run.cycle_id or 0
                if cid not in timeline:
                    timeline[cid] = []
                timeline[cid].append({
                    'agent_name': run.agent_name,
                    'status': run.status,
                    'workflow_state': run.workflow_state,
                    'started_at': _iso(run.started_at),
                    'duration_ms': run.duration_ms,
                    'error_message': run.error_message,
                })

            return {'cycles': timeline}

    # ------------------------------------------------------------------
    # GET /agents/ml-status — ML pipeline readiness
    # ------------------------------------------------------------------
    @router.get("/agents/ml-status")
    async def ml_status():
        # Try to get from engine context first
        cached = engine.context.get('ml_status')
        if cached:
            return cached

        # Fall back to direct query
        try:
            from trading_cotrader.core.database.schema import (
                DailyPerformanceORM, TradeEventORM, TradeORM,
            )
            with session_scope() as session:
                snapshots = session.query(func.count(DailyPerformanceORM.id)).scalar() or 0
                events = session.query(func.count(TradeEventORM.event_id)).scalar() or 0
                events_with_outcomes = (
                    session.query(func.count(TradeEventORM.event_id))
                    .filter(TradeEventORM.outcome.isnot(None))
                    .scalar()
                ) or 0
                closed_trades = (
                    session.query(func.count(TradeORM.id))
                    .filter(TradeORM.trade_status == 'closed')
                    .scalar()
                ) or 0

                supervised_ready = closed_trades >= 100
                rl_ready = closed_trades >= 500

                return {
                    'snapshots': snapshots,
                    'events': events,
                    'events_with_outcomes': events_with_outcomes,
                    'closed_trades': closed_trades,
                    'supervised_learning_ready': supervised_ready,
                    'supervised_trades_needed': max(0, 100 - closed_trades),
                    'rl_ready': rl_ready,
                    'rl_trades_needed': max(0, 500 - closed_trades),
                    'features_defined': 55,
                    'feature_groups': {
                        'market': 21,
                        'position': 19,
                        'portfolio': 15,
                    },
                }
        except Exception as e:
            logger.warning(f"ML status query failed: {e}")
            return {
                'snapshots': 0, 'events': 0, 'events_with_outcomes': 0,
                'closed_trades': 0,
                'supervised_learning_ready': False, 'supervised_trades_needed': 100,
                'rl_ready': False, 'rl_trades_needed': 500,
                'features_defined': 55,
                'feature_groups': {'market': 21, 'position': 19, 'portfolio': 15},
            }

    # ------------------------------------------------------------------
    # GET /agents/{name} — Single agent detail
    # ------------------------------------------------------------------
    @router.get("/agents/{name}")
    async def agent_detail(name: str):
        registry = _build_registry(engine) or AGENT_REGISTRY
        if name not in registry:
            raise HTTPException(404, f"Agent '{name}' not found")

        meta = registry[name]

        with session_scope() as session:
            # Recent runs (last 20)
            recent_runs = (
                session.query(AgentRunORM)
                .filter(AgentRunORM.agent_name == name)
                .order_by(desc(AgentRunORM.started_at))
                .limit(20)
                .all()
            )

            # Recent objectives (last 30 days)
            cutoff = date.today() - timedelta(days=30)
            objectives = (
                session.query(AgentObjectiveORM)
                .filter(
                    AgentObjectiveORM.agent_name == name,
                    AgentObjectiveORM.objective_date >= cutoff,
                )
                .order_by(desc(AgentObjectiveORM.objective_date))
                .all()
            )

            # Run count and avg duration
            run_count = (
                session.query(func.count(AgentRunORM.id))
                .filter(AgentRunORM.agent_name == name)
                .scalar()
            ) or 0
            avg_duration = (
                session.query(func.avg(AgentRunORM.duration_ms))
                .filter(AgentRunORM.agent_name == name)
                .scalar()
            ) or 0
            error_count = (
                session.query(func.count(AgentRunORM.id))
                .filter(
                    AgentRunORM.agent_name == name,
                    AgentRunORM.status == 'error',
                )
                .scalar()
            ) or 0

            return {
                **meta,
                'name': name,
                'stats': {
                    'total_runs': run_count,
                    'avg_duration_ms': round(avg_duration, 1),
                    'error_count': error_count,
                },
                'recent_runs': [
                    {
                        'id': r.id,
                        'cycle_id': r.cycle_id,
                        'workflow_state': r.workflow_state,
                        'status': r.status,
                        'started_at': _iso(r.started_at),
                        'finished_at': _iso(r.finished_at),
                        'duration_ms': r.duration_ms,
                        'messages': r.messages or [],
                        'data': r.data_json or {},
                        'metrics': r.metrics_json or {},
                        'error_message': r.error_message,
                    }
                    for r in recent_runs
                ],
                'objectives': [
                    {
                        'id': o.id,
                        'date': o.objective_date.isoformat(),
                        'objective': o.objective_text,
                        'target_metric': o.target_metric,
                        'target_value': o.target_value,
                        'actual_value': o.actual_value,
                        'grade': o.grade,
                        'gap_analysis': o.gap_analysis,
                    }
                    for o in objectives
                ],
            }

    # ------------------------------------------------------------------
    # GET /agents/{name}/runs — Paginated run history
    # ------------------------------------------------------------------
    @router.get("/agents/{name}/runs")
    async def agent_runs(
        name: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        registry = _build_registry(engine) or AGENT_REGISTRY
        if name not in registry:
            raise HTTPException(404, f"Agent '{name}' not found")

        with session_scope() as session:
            total = (
                session.query(func.count(AgentRunORM.id))
                .filter(AgentRunORM.agent_name == name)
                .scalar()
            ) or 0

            runs = (
                session.query(AgentRunORM)
                .filter(AgentRunORM.agent_name == name)
                .order_by(desc(AgentRunORM.started_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

            return {
                'total': total,
                'offset': offset,
                'limit': limit,
                'runs': [
                    {
                        'id': r.id,
                        'cycle_id': r.cycle_id,
                        'workflow_state': r.workflow_state,
                        'status': r.status,
                        'started_at': _iso(r.started_at),
                        'finished_at': _iso(r.finished_at),
                        'duration_ms': r.duration_ms,
                        'messages': r.messages or [],
                        'data': r.data_json or {},
                        'metrics': r.metrics_json or {},
                        'objectives': r.objectives or [],
                        'requires_human': r.requires_human,
                        'human_prompt': r.human_prompt,
                        'error_message': r.error_message,
                    }
                    for r in runs
                ],
            }

    # ------------------------------------------------------------------
    # GET /agents/{name}/objectives — Historical objectives + grades
    # ------------------------------------------------------------------
    @router.get("/agents/{name}/objectives")
    async def agent_objectives(
        name: str,
        days: int = Query(30, ge=1, le=365),
    ):
        registry = _build_registry(engine) or AGENT_REGISTRY
        if name not in registry:
            raise HTTPException(404, f"Agent '{name}' not found")

        cutoff = date.today() - timedelta(days=days)

        with session_scope() as session:
            objectives = (
                session.query(AgentObjectiveORM)
                .filter(
                    AgentObjectiveORM.agent_name == name,
                    AgentObjectiveORM.objective_date >= cutoff,
                )
                .order_by(desc(AgentObjectiveORM.objective_date))
                .all()
            )

            return {
                'agent_name': name,
                'days': days,
                'objectives': [
                    {
                        'id': o.id,
                        'date': o.objective_date.isoformat(),
                        'objective': o.objective_text,
                        'target_metric': o.target_metric,
                        'target_value': o.target_value,
                        'actual_value': o.actual_value,
                        'grade': o.grade,
                        'gap_analysis': o.gap_analysis,
                        'set_at': _iso(o.set_at),
                        'evaluated_at': _iso(o.evaluated_at),
                    }
                    for o in objectives
                ],
            }

    return router
