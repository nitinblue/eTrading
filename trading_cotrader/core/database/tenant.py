"""
Tenant Isolation — Multi-user data scoping.

Every user-owned query must be scoped by tenant_id.
This module provides:
  1. tenant_id column mixin for ORM models
  2. Scoped query helper
  3. Context manager for setting current tenant
  4. Middleware for FastAPI

Usage:
    # In API endpoint:
    @router.get("/trades")
    async def get_trades(user = Depends(get_current_user)):
        with session_scope() as session:
            trades = tenant_query(session, TradeORM, user.id).filter(...).all()

    # Or with context:
    with tenant_context(user_id):
        trades = session.query(TradeORM).filter(TradeORM.tenant_id == get_tenant_id()).all()
"""

import logging
from contextvars import ContextVar
from typing import Optional, TypeVar, Type

from sqlalchemy.orm import Session, Query

logger = logging.getLogger(__name__)

# Context variable for current tenant (thread-safe)
_current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)

T = TypeVar('T')


def set_tenant(tenant_id: Optional[str]) -> None:
    """Set the current tenant for this context (thread/async task)."""
    _current_tenant.set(tenant_id)


def get_tenant_id() -> Optional[str]:
    """Get the current tenant ID. None = no tenant (single-user mode)."""
    return _current_tenant.get()


def tenant_query(session: Session, model: Type[T], tenant_id: str = None) -> Query:
    """Create a query scoped to a tenant.

    Args:
        session: SQLAlchemy session
        model: ORM model class (must have tenant_id column)
        tenant_id: Explicit tenant ID. If None, uses context var.

    Returns:
        Query filtered by tenant_id. If no tenant set, returns unfiltered (single-user mode).
    """
    tid = tenant_id or get_tenant_id()
    q = session.query(model)
    if tid and hasattr(model, 'tenant_id'):
        q = q.filter(model.tenant_id == tid)
    return q


class tenant_context:
    """Context manager for setting tenant scope.

    Usage:
        with tenant_context(user_id):
            trades = tenant_query(session, TradeORM).filter(...).all()
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token = None

    def __enter__(self):
        self.token = _current_tenant.set(self.tenant_id)
        return self

    def __exit__(self, *args):
        _current_tenant.set(None)


def scoped_open_trades(session, model=None, tenant_id: str = None):
    """Convenience: query open trades scoped to tenant.

    Most common query pattern in the codebase.
    """
    if model is None:
        from trading_cotrader.core.database.schema import TradeORM
        model = TradeORM
    q = tenant_query(session, model, tenant_id)
    return q.filter(model.is_open == True)


def scoped_portfolios(session, portfolio_type: str = None, tenant_id: str = None):
    """Convenience: query portfolios scoped to tenant."""
    from trading_cotrader.core.database.schema import PortfolioORM
    q = tenant_query(session, PortfolioORM, tenant_id)
    if portfolio_type:
        q = q.filter(PortfolioORM.portfolio_type == portfolio_type)
    return q


def stamp_tenant(orm_obj, tenant_id: str = None) -> None:
    """Set tenant_id on an ORM object before saving.

    Call this in booking/creation flows to tag new records.
    """
    tid = tenant_id or get_tenant_id()
    if tid and hasattr(orm_obj, 'tenant_id') and not orm_obj.tenant_id:
        orm_obj.tenant_id = tid
