"""
AtlasClaw auth package.

Public API:
    UserInfo, AuthResult, ShadowUser, AuthenticationError  — data models
    AuthConfig, expand_env                                 — configuration
    AuthProvider                                           — provider interface
    ShadowUserStore                                        — persistence
    AuthStrategy, create_auth_strategy                     — orchestration
    AuthMiddleware, setup_auth_middleware                   — FastAPI integration
"""

from app.atlasclaw.auth.models import (
    UserInfo,
    AuthResult,
    ShadowUser,
    AuthenticationError,
    ANONYMOUS_USER,
)
from app.atlasclaw.auth.config import AuthConfig, expand_env
from app.atlasclaw.auth.providers.base import AuthProvider
from app.atlasclaw.auth.shadow_store import ShadowUserStore
from app.atlasclaw.auth.strategy import AuthStrategy, create_auth_strategy
from app.atlasclaw.auth.middleware import AuthMiddleware, setup_auth_middleware

__all__ = [
    "UserInfo",
    "AuthResult",
    "ShadowUser",
    "AuthenticationError",
    "ANONYMOUS_USER",
    "AuthConfig",
    "expand_env",
    "AuthProvider",
    "ShadowUserStore",
    "AuthStrategy",
    "create_auth_strategy",
    "AuthMiddleware",
    "setup_auth_middleware",
]
