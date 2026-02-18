"""
Web Approval API — FastAPI app embedded in the workflow engine process.

Provides REST endpoints for the approval dashboard so multiple users
(across different networks) can approve/reject trade recommendations
from a browser.

Usage:
    # Created by run_workflow.py when --web flag is set:
    app = create_approval_app(engine)
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""

from pathlib import Path
from typing import TYPE_CHECKING
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from trading_cotrader.agents.messages import UserIntent
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.repositories.recommendation import RecommendationRepository

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trade financial helpers
# ---------------------------------------------------------------------------

def _compute_trade_financials(rec) -> dict:
    """
    Compute max_loss, max_profit, risk_display from recommendation legs.

    For defined-risk strategies: max_loss = spread width * qty * multiplier.
    For undefined-risk: max_loss shown as 'Undefined'.
    Max profit requires premium data (not available on recs), so shown as '--'.
    """
    legs = rec.legs or []
    risk_category = rec.risk_category or "defined"
    strikes = [float(l.strike) for l in legs if l.strike is not None]
    quantities = [abs(l.quantity) for l in legs if l.quantity]

    result = {
        'risk_display': risk_category.upper(),
        'max_loss': None,
        'max_loss_display': '--',
        'max_profit_display': '--',
        'spread_width': None,
    }

    if risk_category == "undefined":
        result['max_loss_display'] = 'Undefined'
        return result

    if len(strikes) < 2:
        return result

    # For defined-risk: compute spread width
    # Group legs by option_type to handle multi-spread structures (iron condors)
    puts = [l for l in legs if l.option_type == 'put' and l.strike is not None]
    calls = [l for l in legs if l.option_type == 'call' and l.strike is not None]

    put_strikes = sorted([float(l.strike) for l in puts])
    call_strikes = sorted([float(l.strike) for l in calls])

    put_width = (put_strikes[-1] - put_strikes[0]) if len(put_strikes) >= 2 else 0
    call_width = (call_strikes[-1] - call_strikes[0]) if len(call_strikes) >= 2 else 0

    # Max risk is the wider side (for iron condors both sides can't lose simultaneously)
    width = max(put_width, call_width) if (put_width and call_width) else (put_width or call_width)

    if width <= 0:
        return result

    qty = quantities[0] if quantities else 1
    multiplier = 100  # standard equity options
    max_loss = width * qty * multiplier

    result['spread_width'] = width
    result['max_loss'] = max_loss
    result['max_loss_display'] = f'${max_loss:,.0f}'

    return result


# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------

class ApprovalBody(BaseModel):
    notes: str = ""
    portfolio: str = ""


class RejectionBody(BaseModel):
    reason: str = ""


class ResumeBody(BaseModel):
    rationale: str


class ExecuteBody(BaseModel):
    confirm: bool = False


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_approval_app(engine: 'WorkflowEngine') -> FastAPI:
    """
    Create a FastAPI app wired to the given WorkflowEngine.

    All handlers call engine.handle_user_intent() — same code path as CLI.
    Thread-safe because handle_user_intent() does dict ops + session_scope()
    (creates new DB sessions per request).
    """
    app = FastAPI(title="CoTrader Approval Dashboard", docs_url="/docs")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # v2 API Router (React frontend)
    # ------------------------------------------------------------------
    from trading_cotrader.web.api_v2 import create_v2_router
    v2_router = create_v2_router(engine)
    app.include_router(v2_router, prefix="/api/v2")

    # ------------------------------------------------------------------
    # Admin API Router (config management)
    # ------------------------------------------------------------------
    from trading_cotrader.web.api_admin import create_admin_router
    admin_router = create_admin_router()
    app.include_router(admin_router, prefix="/api/admin")

    # ------------------------------------------------------------------
    # Reports API Router (pre-built report endpoints)
    # ------------------------------------------------------------------
    from trading_cotrader.web.api_reports import create_reports_router
    reports_router = create_reports_router()
    app.include_router(reports_router, prefix="/api/reports")

    # ------------------------------------------------------------------
    # Explorer API Router (structured query builder)
    # ------------------------------------------------------------------
    from trading_cotrader.web.api_explorer import create_explorer_router
    explorer_router = create_explorer_router()
    app.include_router(explorer_router, prefix="/api/explorer")

    # ------------------------------------------------------------------
    # Agents API Router (agent dashboard visibility)
    # ------------------------------------------------------------------
    from trading_cotrader.web.api_agents import create_agents_router
    agents_router = create_agents_router(engine)
    app.include_router(agents_router, prefix="/api/v2")

    # ------------------------------------------------------------------
    # Serve React frontend (production build)
    # ------------------------------------------------------------------
    from fastapi.staticfiles import StaticFiles
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static")

    # ------------------------------------------------------------------
    # Dashboard HTML — serve React app if built, else legacy HTML
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        # Try React build first
        react_index = Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html"
        if react_index.exists():
            return HTMLResponse(react_index.read_text(encoding="utf-8"))
        # Fallback to legacy approval dashboard
        html_path = Path(__file__).parent.parent / "ui" / "approval-dashboard.html"
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------

    @app.get("/api/pending")
    async def get_pending():
        """Get all pending recommendations from DB, enriched with trade financials."""
        with session_scope() as session:
            repo = RecommendationRepository(session)
            pending = repo.get_pending()
            results = []
            for rec in pending:
                d = rec.to_dict()
                # Compute max loss/profit from legs for display
                d.update(_compute_trade_financials(rec))
                results.append(d)
            return results

    @app.get("/api/status")
    async def get_status():
        """Get workflow engine status (same as CLI 'status' command)."""
        response = engine.interaction._status()
        return {"message": response.message, "data": response.data}

    @app.get("/api/history")
    async def get_history():
        """Recent accepted and rejected recommendations."""
        with session_scope() as session:
            repo = RecommendationRepository(session)
            accepted = repo.get_by_status("accepted")[:10]
            rejected = repo.get_by_status("rejected")[:10]
            return {
                "accepted": [r.to_dict() for r in accepted],
                "rejected": [r.to_dict() for r in rejected],
            }

    @app.get("/api/portfolios")
    async def get_portfolios():
        """Get list of portfolio names from config."""
        try:
            from trading_cotrader.config.risk_config_loader import get_risk_config
            config = get_risk_config()
            names = list(config.portfolios.portfolios.keys())
            return {"portfolios": names}
        except Exception as e:
            logger.warning(f"Could not load portfolio names: {e}")
            return {"portfolios": []}

    @app.get("/api/portfolios/detail")
    async def get_portfolios_detail():
        """Full portfolio data: capital, Greeks, P&L."""
        from trading_cotrader.core.database.schema import PortfolioORM
        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            return [
                {
                    "id": p.id, "name": p.name,
                    "broker": p.broker, "portfolio_type": p.portfolio_type,
                    "initial_capital": float(p.initial_capital or 0),
                    "total_equity": float(p.total_equity or 0),
                    "cash_balance": float(p.cash_balance or 0),
                    "buying_power": float(p.buying_power or 0),
                    "total_pnl": float(p.total_pnl or 0),
                    "daily_pnl": float(p.daily_pnl or 0),
                    "portfolio_delta": float(p.portfolio_delta or 0),
                    "portfolio_gamma": float(p.portfolio_gamma or 0),
                    "portfolio_theta": float(p.portfolio_theta or 0),
                    "portfolio_vega": float(p.portfolio_vega or 0),
                    "max_portfolio_delta": float(p.max_portfolio_delta or 500),
                    "max_portfolio_gamma": float(p.max_portfolio_gamma or 50),
                    "min_portfolio_theta": float(p.min_portfolio_theta or -500),
                    "max_portfolio_vega": float(p.max_portfolio_vega or 1000),
                    "var_1d_95": float(p.var_1d_95 or 0),
                    "var_1d_99": float(p.var_1d_99 or 0),
                }
                for p in portfolios
            ]

    @app.get("/api/positions")
    async def get_positions():
        """Open trades with Greeks."""
        from trading_cotrader.core.database.schema import TradeORM
        with session_scope() as session:
            trades = (
                session.query(TradeORM)
                .filter(TradeORM.is_open == True)
                .order_by(TradeORM.underlying_symbol)
                .all()
            )
            return [
                {
                    "id": t.id, "underlying": t.underlying_symbol,
                    "strategy_type": t.strategy.strategy_type if t.strategy else None,
                    "trade_status": t.trade_status,
                    "entry_price": float(t.entry_price) if t.entry_price else None,
                    "current_price": float(t.current_price) if t.current_price else None,
                    "total_pnl": float(t.total_pnl or 0),
                    "current_delta": float(t.current_delta or 0),
                    "current_gamma": float(t.current_gamma or 0),
                    "current_theta": float(t.current_theta or 0),
                    "current_vega": float(t.current_vega or 0),
                    "trade_source": t.trade_source,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                }
                for t in trades
            ]

    @app.get("/api/greeks")
    async def get_greeks():
        """Portfolio Greeks with limits."""
        from trading_cotrader.core.database.schema import PortfolioORM
        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type != 'deprecated')
                .order_by(PortfolioORM.name)
                .all()
            )
            return [
                {
                    "name": p.name,
                    "delta": float(p.portfolio_delta or 0),
                    "gamma": float(p.portfolio_gamma or 0),
                    "theta": float(p.portfolio_theta or 0),
                    "vega": float(p.portfolio_vega or 0),
                    "max_delta": float(p.max_portfolio_delta or 500),
                    "max_gamma": float(p.max_portfolio_gamma or 50),
                    "min_theta": float(p.min_portfolio_theta or -500),
                    "max_vega": float(p.max_portfolio_vega or 1000),
                    "delta_pct": abs(float(p.portfolio_delta or 0)) / float(p.max_portfolio_delta or 500) * 100
                        if float(p.max_portfolio_delta or 500) else 0,
                    "gamma_pct": abs(float(p.portfolio_gamma or 0)) / float(p.max_portfolio_gamma or 50) * 100
                        if float(p.max_portfolio_gamma or 50) else 0,
                    "theta_pct": abs(float(p.portfolio_theta or 0)) / abs(float(p.min_portfolio_theta or -500)) * 100
                        if float(p.min_portfolio_theta or -500) else 0,
                    "vega_pct": abs(float(p.portfolio_vega or 0)) / float(p.max_portfolio_vega or 1000) * 100
                        if float(p.max_portfolio_vega or 1000) else 0,
                }
                for p in portfolios
            ]

    @app.get("/api/capital")
    async def get_capital():
        """Capital utilization per portfolio."""
        from trading_cotrader.core.database.schema import PortfolioORM
        ctx_capital = engine.context.get('capital_utilization', {})
        ctx_portfolios = ctx_capital.get('portfolios', {})

        with session_scope() as session:
            portfolios = (
                session.query(PortfolioORM)
                .filter(PortfolioORM.portfolio_type.in_(['real', 'paper']))
                .order_by(PortfolioORM.name)
                .all()
            )
            result = []
            for p in portfolios:
                equity = float(p.total_equity or 0)
                cash = float(p.cash_balance or 0)
                deployed_pct = ((equity - cash) / equity * 100) if equity else 0
                row = {
                    "name": p.name,
                    "initial_capital": float(p.initial_capital or 0),
                    "total_equity": equity,
                    "cash_balance": cash,
                    "deployed_pct": round(deployed_pct, 1),
                    "idle_capital": cash,
                    "severity": "—",
                }
                pdata = ctx_portfolios.get(p.name, {})
                if pdata:
                    row["severity"] = pdata.get("severity", "—")
                    if pdata.get("opp_cost_daily") is not None:
                        row["opp_cost_daily"] = float(pdata["opp_cost_daily"])
                result.append(row)
            return result

    @app.get("/api/trades/today")
    async def get_trades_today():
        """Today's trades."""
        from trading_cotrader.core.database.schema import TradeORM
        from datetime import date as date_cls
        today_start = datetime.combine(date_cls.today(), datetime.min.time())

        with session_scope() as session:
            trades = (
                session.query(TradeORM)
                .filter(TradeORM.created_at >= today_start)
                .order_by(TradeORM.created_at.desc())
                .all()
            )
            return [
                {
                    "id": t.id, "underlying": t.underlying_symbol,
                    "strategy_type": t.strategy.strategy_type if t.strategy else None,
                    "trade_status": t.trade_status,
                    "trade_source": t.trade_source,
                    "entry_price": float(t.entry_price) if t.entry_price else None,
                    "total_pnl": float(t.total_pnl or 0),
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in trades
            ]

    @app.get("/api/risk")
    async def get_risk():
        """VaR, macro, circuit breakers."""
        ctx = engine.context
        risk = ctx.get('risk_snapshot', {})
        macro = ctx.get('macro_assessment', {})
        guardian = ctx.get('guardian_status', {})

        return {
            "var": {
                "var_95": risk.get('var_95'),
                "var_99": risk.get('var_99'),
                "expected_shortfall_95": risk.get('expected_shortfall_95'),
            },
            "macro": {
                "regime": macro.get('regime'),
                "vix": ctx.get('vix'),
                "confidence": macro.get('confidence'),
                "rationale": macro.get('rationale', '')[:120],
            },
            "circuit_breakers": guardian.get('circuit_breakers', {}),
            "trading_constraints": {
                "trades_today": ctx.get('trades_today_count', 0),
                "max_trades_per_day": 3,
                "halted": bool(ctx.get('halt_reason')),
                "halt_reason": ctx.get('halt_reason'),
            },
        }

    # ------------------------------------------------------------------
    # Action endpoints
    # ------------------------------------------------------------------

    @app.post("/api/approve/{rec_id}")
    async def approve(rec_id: str, body: ApprovalBody):
        """Approve a recommendation."""
        params = {}
        if body.portfolio:
            params["portfolio"] = body.portfolio
        intent = UserIntent(
            action="approve",
            target=rec_id,
            parameters=params,
            rationale=body.notes or "Approved via web dashboard",
        )
        response = engine.handle_user_intent(intent)
        return {"message": response.message, "data": response.data}

    @app.post("/api/reject/{rec_id}")
    async def reject(rec_id: str, body: RejectionBody):
        """Reject a recommendation."""
        intent = UserIntent(
            action="reject",
            target=rec_id,
            rationale=body.reason or "Rejected via web dashboard",
        )
        response = engine.handle_user_intent(intent)
        return {"message": response.message}

    @app.post("/api/defer/{rec_id}")
    async def defer(rec_id: str):
        """Defer a recommendation for later."""
        intent = UserIntent(action="defer", target=rec_id)
        response = engine.handle_user_intent(intent)
        return {"message": response.message}

    @app.post("/api/halt")
    async def halt():
        """Halt all trading."""
        intent = UserIntent(action="halt", rationale="Halted via web dashboard")
        response = engine.handle_user_intent(intent)
        return {"message": response.message}

    @app.post("/api/resume")
    async def resume(body: ResumeBody):
        """Resume trading (requires rationale)."""
        intent = UserIntent(action="resume", rationale=body.rationale)
        response = engine.handle_user_intent(intent)
        return {"message": response.message}

    # ------------------------------------------------------------------
    # Execution endpoints — WhatIf → Live Order
    # ------------------------------------------------------------------

    @app.post("/api/execute/{trade_id}")
    async def execute_trade(trade_id: str, body: ExecuteBody):
        """
        Execute a WhatIf trade as a live order.

        - confirm=false (default): dry-run preview with margin/fees
        - confirm=true: place the real order on the broker
        """
        params = {'confirm': body.confirm}
        intent = UserIntent(
            action="execute",
            target=trade_id,
            parameters=params,
        )
        response = engine.handle_user_intent(intent)
        return {
            "message": response.message,
            "data": response.data,
            "requires_action": response.requires_action,
        }

    @app.get("/api/orders")
    async def get_orders():
        """
        Get live/recent orders and auto-update fill status.

        Polls the broker for pending orders and auto-marks filled trades.
        """
        intent = UserIntent(action="orders")
        response = engine.handle_user_intent(intent)
        return {
            "message": response.message,
            "data": response.data,
        }

    return app
