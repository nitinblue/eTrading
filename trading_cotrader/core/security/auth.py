"""
Auth Service — JWT token creation/validation, password hashing.

SaaS authentication layer:
  - Email + password registration/login
  - JWT access + refresh tokens
  - OAuth stub (Google, GitHub — future)
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import UserORM

logger = logging.getLogger(__name__)

# Config — move to settings in production
SECRET_KEY = "cotrader-secret-key-change-in-production"  # TODO: from env var
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def register_user(email: str, password: str, name: str = None) -> Optional[dict]:
    """Register a new user. Returns user dict or None if email exists."""
    with session_scope() as session:
        existing = session.query(UserORM).filter(UserORM.email == email).first()
        if existing:
            return None

        user = UserORM(
            id=str(uuid.uuid4()),
            email=email,
            name=name or email.split('@')[0],
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(user)
        session.commit()

        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
        }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user. Returns user dict with tokens or None."""
    with session_scope() as session:
        user = session.query(UserORM).filter(
            UserORM.email == email,
            UserORM.is_active == True,
        ).first()

        if not user or not verify_password(password, user.password_hash):
            return None

        user.last_login = datetime.utcnow()
        session.commit()

        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'access_token': create_access_token(user.id, user.email),
            'refresh_token': create_refresh_token(user.id),
            'token_type': 'bearer',
        }


def get_user_from_token(token: str) -> Optional[dict]:
    """Get user from JWT token. Returns user dict or None."""
    payload = decode_token(token)
    if not payload or payload.get('type') != 'access':
        return None

    user_id = payload.get('sub')
    with session_scope() as session:
        user = session.query(UserORM).filter(
            UserORM.id == user_id,
            UserORM.is_active == True,
        ).first()

        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'subscription_tier': user.subscription_tier,
        }
