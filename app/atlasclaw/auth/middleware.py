"""
AuthMiddleware — FastAPI/Starlette middleware for request authentication.

Extracts credential from CloudChef-Authenticate header / Authorization Bearer /
Cookie and injects a UserInfo into request.state.user_info.

Setup example:
    from app.atlasclaw.auth.middleware import setup_auth_middleware
    setup_auth_middleware(app, auth_config)
"""

from __future__ import annotations

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.atlasclaw.auth.models import UserInfo, ANONYMOUS_USER, AuthenticationError
from app.atlasclaw.auth.strategy import AuthStrategy

logger = logging.getLogger(__name__)

# Paths that bypass authentication entirely
_SKIP_PATHS = frozenset({"/health", "/ping", "/favicon.ico", "/docs", "/openapi.json"})

# SSO paths — must not be intercepted by auth checks
_SSO_PATHS = frozenset({"/api/auth/login", "/api/auth/callback", "/api/auth/logout", "/api/auth/me"})

# Static asset path prefixes — always pass through (no auth, no redirect)
_STATIC_PREFIXES = ("/static/", "/styles/", "/scripts/", "/locales/", "/config.json", "/index.html")


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that resolves user identity for every request.

    Modes:
    - ``anonymous_fallback=True``: no auth configured → always inject
      ``user_id="anonymous"`` and skip all credential checks.
    - ``strategy.provider.provider_name() == "none"``: NoneProvider → resolve
      with empty credential (returns the configured ``default_user_id``).
    - Any real provider: extract credential, call strategy.resolve_user(),
      return 401 on AuthenticationError.
    """

    def __init__(
        self,
        app,
        strategy: AuthStrategy,
        anonymous_fallback: bool = False,
        oidc_redirect_uri: str = "",
    ) -> None:
        super().__init__(app)
        self._strategy = strategy
        self._anonymous_fallback = anonymous_fallback
        # Non-empty means standalone deployment: middleware can redirect to SSO
        self._oidc_redirect_uri = oidc_redirect_uri

    async def dispatch(self, request: Request, call_next):
        # Skip non-API / health paths
        if request.url.path in _SKIP_PATHS:
            request.state.user_info = ANONYMOUS_USER
            return await call_next(request)

        # Static assets — always pass through without auth
        if request.url.path.startswith(_STATIC_PREFIXES):
            request.state.user_info = ANONYMOUS_USER
            return await call_next(request)

        # SSO flow paths — always pass through without auth
        if request.url.path in _SSO_PATHS:
            request.state.user_info = ANONYMOUS_USER
            return await call_next(request)

        # Anonymous mode: no auth configured in atlasclaw.json
        if self._anonymous_fallback:
            request.state.user_info = ANONYMOUS_USER
            return await call_next(request)

        provider_name = self._strategy.provider.provider_name()

        # NoneProvider: always succeeds without a credential
        if provider_name == "none":
            try:
                request.state.user_info = await self._strategy.resolve_user("")
            except Exception:
                request.state.user_info = ANONYMOUS_USER
            return await call_next(request)

        # Real provider: extract and validate credential
        credential = self._extract_credential(request)
        if not credential:
            # If a redirect_uri is configured (standalone deployment),
            # redirect browser navigations to SSO login.
            # Root path "/" always redirects to SSO regardless of Accept header.
            if self._oidc_redirect_uri and (
                request.url.path == "/" or self._is_browser_request(request)
            ):
                logger.debug(
                    "No credential → redirecting to SSO login: %s",
                    request.url.path,
                )
                return RedirectResponse(url="/api/auth/login", status_code=302)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        try:
            request.state.user_info = await self._strategy.resolve_user(credential)
            return await call_next(request)
        except AuthenticationError as exc:
            logger.debug("Auth failed for %s: %s", request.url.path, exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

    @staticmethod
    def _is_browser_request(request: Request) -> bool:
        """
        Heuristic: a request is considered a browser navigation when
        the ``Accept`` header includes ``text/html`` AND there is no
        ``X-Requested-With: XMLHttpRequest`` header (which SPA/iframe
        XHR calls usually set).
        """
        accept = request.headers.get("accept", "")
        xhr = request.headers.get("x-requested-with", "")
        return "text/html" in accept and xhr.lower() != "xmlhttprequest"

    @staticmethod
    def _extract_credential(request: Request) -> str:
        """
        Precedence:
          1. CloudChef-Authenticate header
          2. Authorization: Bearer <token>
          3. CloudChef-Authenticate cookie
        """
        # 1. Header
        token = request.headers.get("CloudChef-Authenticate", "").strip()
        if token:
            return token

        # 2. Authorization Bearer
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()

        # 3. Cookie
        token = request.cookies.get("CloudChef-Authenticate", "").strip()
        if token:
            return token

        return ""


def setup_auth_middleware(
    app,
    auth_config: Optional[object],
    shadow_store: Optional[object] = None,
) -> None:
    """
    Attach AuthMiddleware to a FastAPI application.

    Args:
        app: FastAPI application instance.
        auth_config: AuthConfig loaded from atlasclaw.json, or None for anonymous.
        shadow_store: Optional ShadowUserStore override (for testing).
    """
    from app.atlasclaw.auth.strategy import create_auth_strategy
    from app.atlasclaw.auth.config import AuthConfig

    if auth_config is None:
        # No auth section in atlasclaw.json → anonymous fallback
        from app.atlasclaw.auth.providers.none import NoneProvider
        from app.atlasclaw.auth.shadow_store import ShadowUserStore

        _store = shadow_store or ShadowUserStore()
        _provider = NoneProvider(default_user_id="anonymous")
        strategy = AuthStrategy(
            provider=_provider, shadow_store=_store, cache_ttl_seconds=0
        )
        app.add_middleware(AuthMiddleware, strategy=strategy, anonymous_fallback=True)
        logger.info("AuthMiddleware: anonymous fallback mode (no auth config)")
        return

    # Coerce raw dict from atlasclaw.json into AuthConfig if needed
    if isinstance(auth_config, dict):
        auth_config = AuthConfig(**auth_config)

    strategy = create_auth_strategy(auth_config, shadow_store)
    if strategy is None:
        logger.warning("AuthMiddleware: create_auth_strategy returned None, using anonymous")
        app.add_middleware(
            AuthMiddleware,
            strategy=AuthStrategy(
                provider=__import__(
                    "app.atlasclaw.auth.providers.none", fromlist=["NoneProvider"]
                ).NoneProvider(),
                shadow_store=__import__(
                    "app.atlasclaw.auth.shadow_store", fromlist=["ShadowUserStore"]
                ).ShadowUserStore(),
            ),
            anonymous_fallback=True,
        )
        return

    # Pass redirect_uri so middleware can auto-detect standalone vs embedded mode
    oidc_redirect_uri = ""
    if auth_config.provider.lower() == "oidc":
        oidc_redirect_uri = auth_config.oidc.expanded().redirect_uri

    app.add_middleware(
        AuthMiddleware,
        strategy=strategy,
        anonymous_fallback=False,
        oidc_redirect_uri=oidc_redirect_uri,
    )
    logger.info(
        "AuthMiddleware: registered with provider=%r, standalone_sso=%s",
        auth_config.provider,
        bool(oidc_redirect_uri),
    )
