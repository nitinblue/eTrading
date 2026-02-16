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
# Request body models
# ---------------------------------------------------------------------------

class ApprovalBody(BaseModel):
    notes: str = ""
    portfolio: str = ""


class RejectionBody(BaseModel):
    reason: str = ""


class ResumeBody(BaseModel):
    rationale: str


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
    # Dashboard HTML
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        html_path = Path(__file__).parent.parent / "ui" / "approval-dashboard.html"
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------

    @app.get("/api/pending")
    async def get_pending():
        """Get all pending recommendations from DB."""
        with session_scope() as session:
            repo = RecommendationRepository(session)
            pending = repo.get_pending()
            return [rec.to_dict() for rec in pending]

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

    return app
