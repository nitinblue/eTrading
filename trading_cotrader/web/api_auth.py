"""
Auth API — Registration, login, token refresh.

Endpoints:
    POST /api/auth/register — Create account
    POST /api/auth/login — Get tokens
    POST /api/auth/refresh — Refresh access token
    GET  /api/auth/me — Current user info
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from trading_cotrader.core.security.auth import (
    register_user, authenticate_user, get_user_from_token,
    create_access_token, decode_token,
)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency: validate JWT and return user."""
    if not credentials:
        # No auth header — allow anonymous for now (single-user mode)
        return None

    user = get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def create_auth_router() -> APIRouter:
    router = APIRouter(tags=["auth"])

    @router.post("/register")
    async def register(req: RegisterRequest):
        """Create a new account."""
        result = register_user(req.email, req.password, req.name)
        if not result:
            raise HTTPException(400, "Email already registered")
        return {"message": "Account created", "user": result}

    @router.post("/login")
    async def login(req: LoginRequest):
        """Authenticate and get tokens."""
        result = authenticate_user(req.email, req.password)
        if not result:
            raise HTTPException(401, "Invalid email or password")
        return TokenResponse(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            user={'id': result['id'], 'email': result['email'], 'name': result['name']},
        )

    @router.post("/refresh")
    async def refresh(req: RefreshRequest):
        """Refresh an access token."""
        payload = decode_token(req.refresh_token)
        if not payload or payload.get('type') != 'refresh':
            raise HTTPException(401, "Invalid refresh token")

        user_id = payload.get('sub')
        # Create new access token
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import UserORM
        with session_scope() as session:
            user = session.query(UserORM).get(user_id)
            if not user or not user.is_active:
                raise HTTPException(401, "User not found or inactive")
            access_token = create_access_token(user.id, user.email)
            return {"access_token": access_token, "token_type": "bearer"}

    @router.get("/me")
    async def me(user=Depends(get_current_user)):
        """Get current user info."""
        if not user:
            return {"authenticated": False, "message": "No auth token provided (single-user mode)"}
        return {"authenticated": True, "user": user}

    return router
