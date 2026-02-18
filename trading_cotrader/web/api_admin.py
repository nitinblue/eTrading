"""
Admin API Router — CRUD endpoints for YAML configuration files.

Config persistence: YAML remains source of truth. Admin API reads YAML → returns JSON
→ user edits in UI → PUT sends changes → backend validates → writes back to YAML
→ reloads singleton.

Mounted in approval_api.py at /api/admin prefix.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import copy
import logging

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML file paths
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path(__file__).parent.parent / "config"
_RISK_YAML = _CONFIG_DIR / "risk_config.yaml"
_WORKFLOW_YAML = _CONFIG_DIR / "workflow_rules.yaml"
_BROKERS_YAML = _CONFIG_DIR / "brokers.yaml"


# ---------------------------------------------------------------------------
# YAML read/write helpers
# ---------------------------------------------------------------------------

def _read_yaml(path: Path) -> dict:
    """Read a YAML file and return as dict."""
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Config file not found: {path.name}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict) -> None:
    """Write dict back to YAML file, preserving readability."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )
    logger.info(f"Config written: {path.name}")


def _read_risk_yaml() -> dict:
    return _read_yaml(_RISK_YAML)


def _write_risk_yaml(data: dict) -> None:
    _write_yaml(_RISK_YAML, data)


def _read_workflow_yaml() -> dict:
    return _read_yaml(_WORKFLOW_YAML)


def _write_workflow_yaml(data: dict) -> None:
    _write_yaml(_WORKFLOW_YAML, data)


def _reload_all_configs() -> dict:
    """Reload all config singletons from YAML files."""
    results = {}
    try:
        from trading_cotrader.config.risk_config_loader import reload_risk_config
        reload_risk_config()
        results["risk_config"] = "reloaded"
    except Exception as e:
        results["risk_config"] = f"error: {e}"

    try:
        from trading_cotrader.config.workflow_config_loader import load_workflow_config
        load_workflow_config()
        results["workflow_config"] = "reloaded"
    except Exception as e:
        results["workflow_config"] = f"error: {e}"

    try:
        from trading_cotrader.config.broker_config_loader import get_broker_registry
        get_broker_registry()
        results["broker_config"] = "reloaded"
    except Exception as e:
        results["broker_config"] = f"error: {e}"

    logger.info(f"Config reload results: {results}")
    return results


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------

class PortfolioUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    initial_capital: Optional[float] = None
    target_annual_return_pct: Optional[float] = None
    exit_rule_profile: Optional[str] = None
    allowed_strategies: Optional[List[str]] = None
    active_strategies: Optional[List[str]] = None
    risk_limits: Optional[Dict[str, Any]] = None
    preferred_underlyings: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class RiskUpdate(BaseModel):
    portfolio_risk: Optional[Dict[str, Any]] = None
    concentration: Optional[Dict[str, Any]] = None
    exit_rule_profiles: Optional[Dict[str, Any]] = None
    liquidity_thresholds: Optional[Dict[str, Any]] = None
    margin: Optional[Dict[str, Any]] = None


class StrategyRuleUpdate(BaseModel):
    min_iv_rank: Optional[int] = None
    preferred_iv_rank: Optional[int] = None
    market_outlook: Optional[List[str]] = None
    dte_range: Optional[List[int]] = None
    entry_filters: Optional[Dict[str, Any]] = None
    requires: Optional[str] = None
    profit_target_pct: Optional[float] = None
    stop_loss_multiplier: Optional[float] = None
    time_stop: Optional[str] = None
    avoid_events: Optional[List[str]] = None


class WorkflowUpdate(BaseModel):
    workflow: Optional[Dict[str, Any]] = None
    circuit_breakers: Optional[Dict[str, Any]] = None
    trading_constraints: Optional[Dict[str, Any]] = None
    trading_schedule: Optional[Dict[str, Any]] = None
    execution_defaults: Optional[Dict[str, Any]] = None


class CapitalPlanUpdate(BaseModel):
    idle_alert_pct: Optional[Dict[str, float]] = None
    escalation: Optional[Dict[str, Any]] = None
    target_annual_return_pct: Optional[Dict[str, float]] = None
    staggered_deployment: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_admin_router() -> APIRouter:
    """Create the admin API router with all config CRUD endpoints."""
    router = APIRouter()

    # ==================================================================
    # PORTFOLIOS
    # ==================================================================

    @router.get("/portfolios")
    async def get_portfolios():
        """Get all portfolio configs from YAML."""
        data = _read_risk_yaml()
        portfolios = data.get("portfolios", {})
        return {"portfolios": portfolios}

    @router.get("/portfolios/{name}")
    async def get_portfolio(name: str):
        """Get a single portfolio config."""
        data = _read_risk_yaml()
        portfolios = data.get("portfolios", {})
        if name not in portfolios:
            raise HTTPException(status_code=404, detail=f"Portfolio '{name}' not found")
        return {"name": name, **portfolios[name]}

    @router.put("/portfolios/{name}")
    async def update_portfolio(name: str, body: PortfolioUpdate):
        """Update a portfolio's config in YAML."""
        data = _read_risk_yaml()
        portfolios = data.get("portfolios", {})
        if name not in portfolios:
            raise HTTPException(status_code=404, detail=f"Portfolio '{name}' not found")

        portfolio = portfolios[name]
        updates = body.model_dump(exclude_none=True)

        # Validate active_strategies is subset of allowed_strategies
        new_allowed = updates.get("allowed_strategies", portfolio.get("allowed_strategies", []))
        new_active = updates.get("active_strategies", portfolio.get("active_strategies", []))
        if new_active:
            invalid = set(new_active) - set(new_allowed)
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Active strategies not in allowed: {sorted(invalid)}"
                )

        # Validate exit_rule_profile
        if "exit_rule_profile" in updates:
            valid_profiles = list(data.get("exit_rule_profiles", {}).keys())
            if updates["exit_rule_profile"] not in valid_profiles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid exit_rule_profile. Valid: {valid_profiles}"
                )

        # Merge updates
        for key, value in updates.items():
            if key == "risk_limits" and isinstance(value, dict):
                if "risk_limits" not in portfolio:
                    portfolio["risk_limits"] = {}
                portfolio["risk_limits"].update(value)
            else:
                portfolio[key] = value

        _write_risk_yaml(data)
        _reload_all_configs()
        return {"status": "updated", "name": name, "portfolio": portfolio}

    # ==================================================================
    # RISK SETTINGS
    # ==================================================================

    @router.get("/risk")
    async def get_risk_settings():
        """Get full risk config (VaR, Greeks, concentration, margin, drawdown, exit profiles, liquidity)."""
        data = _read_risk_yaml()
        return {
            "portfolio_risk": data.get("portfolio_risk", {}),
            "concentration": data.get("concentration", {}),
            "exit_rule_profiles": data.get("exit_rule_profiles", {}),
            "exit_rules": data.get("exit_rules", {}),
            "liquidity_thresholds": data.get("liquidity_thresholds", {}),
            "margin": data.get("margin", {}),
            "iv_settings": data.get("iv_settings", {}),
        }

    @router.put("/risk")
    async def update_risk_settings(body: RiskUpdate):
        """Update risk config sections."""
        data = _read_risk_yaml()
        updates = body.model_dump(exclude_none=True)

        for section, values in updates.items():
            if section in data and isinstance(values, dict):
                _deep_merge(data[section], values)
            else:
                data[section] = values

        _write_risk_yaml(data)
        _reload_all_configs()
        return {"status": "updated", "sections": list(updates.keys())}

    # ==================================================================
    # STRATEGY RULES
    # ==================================================================

    @router.get("/strategies")
    async def get_strategy_rules():
        """Get all strategy rules with entry filters."""
        data = _read_risk_yaml()
        return {"strategy_rules": data.get("strategy_rules", {})}

    @router.put("/strategies/{name}")
    async def update_strategy_rule(name: str, body: StrategyRuleUpdate):
        """Update a single strategy rule."""
        data = _read_risk_yaml()
        rules = data.get("strategy_rules", {})
        if name not in rules:
            raise HTTPException(status_code=404, detail=f"Strategy rule '{name}' not found")

        updates = body.model_dump(exclude_none=True)
        for key, value in updates.items():
            if key == "entry_filters" and isinstance(value, dict):
                if "entry_filters" not in rules[name]:
                    rules[name]["entry_filters"] = {}
                rules[name]["entry_filters"].update(value)
            else:
                rules[name][key] = value

        _write_risk_yaml(data)
        _reload_all_configs()
        return {"status": "updated", "strategy": name, "rule": rules[name]}

    # ==================================================================
    # WORKFLOW RULES
    # ==================================================================

    @router.get("/workflow")
    async def get_workflow_rules():
        """Get circuit breakers, trading constraints, schedule, execution defaults."""
        data = _read_workflow_yaml()
        return {
            "workflow": data.get("workflow", {}),
            "circuit_breakers": data.get("circuit_breakers", {}),
            "trading_constraints": data.get("trading_constraints", {}),
            "trading_schedule": data.get("trading_schedule", {}),
            "decision_timeouts": data.get("decision_timeouts", {}),
            "execution_defaults": data.get("execution_defaults", {}),
            "notifications": data.get("notifications", {}),
            "qa": data.get("qa", {}),
        }

    @router.put("/workflow")
    async def update_workflow_rules(body: WorkflowUpdate):
        """Update workflow rules sections."""
        data = _read_workflow_yaml()
        updates = body.model_dump(exclude_none=True)

        for section, values in updates.items():
            if section in data and isinstance(values, dict):
                _deep_merge(data[section], values)
            else:
                data[section] = values

        _write_workflow_yaml(data)
        _reload_all_configs()
        return {"status": "updated", "sections": list(updates.keys())}

    # ==================================================================
    # CAPITAL DEPLOYMENT
    # ==================================================================

    @router.get("/capital-plan")
    async def get_capital_plan():
        """Get idle alerts, escalation, target returns, staggered ramp."""
        data = _read_workflow_yaml()
        cd = data.get("capital_deployment", {})
        return {
            "idle_alert_pct": cd.get("idle_alert_pct", {}),
            "escalation": cd.get("escalation", {}),
            "target_annual_return_pct": cd.get("target_annual_return_pct", {}),
            "staggered_deployment": cd.get("staggered_deployment", {}),
        }

    @router.put("/capital-plan")
    async def update_capital_plan(body: CapitalPlanUpdate):
        """Update capital deployment plan."""
        data = _read_workflow_yaml()
        cd = data.get("capital_deployment", {})
        updates = body.model_dump(exclude_none=True)

        for key, value in updates.items():
            if key in cd and isinstance(value, dict):
                _deep_merge(cd[key], value)
            else:
                cd[key] = value

        data["capital_deployment"] = cd
        _write_workflow_yaml(data)
        _reload_all_configs()
        return {"status": "updated", "sections": list(updates.keys())}

    # ==================================================================
    # CONFIG MANAGEMENT
    # ==================================================================

    @router.post("/reload")
    async def reload_configs():
        """Force reload all configs from YAML files."""
        results = _reload_all_configs()
        return {"status": "reloaded", "results": results}

    return router


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, updates: dict) -> None:
    """Deep merge updates into base dict in-place."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
