"""
AuthStrategy — orchestrates Provider → ShadowUserStore → UserInfo.
Includes a simple in-memory TTL cache keyed by credential.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.atlasclaw.auth.config import AuthConfig
from app.atlasclaw.auth.models import UserInfo, ANONYMOUS_USER
from app.atlasclaw.auth.providers.base import AuthProvider
from app.atlasclaw.auth.shadow_store import ShadowUserStore

logger = logging.getLogger(__name__)


class AuthStrategy:
    """
    Coordinates the full authentication flow:

      1. AuthProvider.authenticate(credential)  →  AuthResult
      2. ShadowUserStore.get_or_create(provider, result)  →  ShadowUser
      3. ShadowUser.to_user_info(raw_token)  →  UserInfo

    Results are cached in memory for ``cache_ttl_seconds`` to avoid repeated
    remote calls for the same token.
    """

    def __init__(
        self,
        provider: AuthProvider,
        shadow_store: ShadowUserStore,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._provider = provider
        self._shadow_store = shadow_store
        self._cache_ttl = cache_ttl_seconds
        # token -> (UserInfo, expiry_monotonic_ts)
        self._cache: dict[str, tuple[UserInfo, float]] = {}

    @property
    def provider(self) -> AuthProvider:
        return self._provider

    async def resolve_user(self, credential: str) -> UserInfo:
        """
        Validate *credential* and return the corresponding UserInfo.

        Raises:
            AuthenticationError: propagated from the underlying provider.
        """
        # --- TTL cache hit -------------------------------------------
        if credential and credential in self._cache:
            user_info, expiry = self._cache[credential]
            if time.monotonic() < expiry:
                return user_info
            del self._cache[credential]

        # --- authenticate with provider ------------------------------
        result = await self._provider.authenticate(credential)

        # --- map to shadow user -------------------------------------
        shadow = await self._shadow_store.get_or_create(
            provider=self._provider.provider_name(),
            result=result,
        )

        user_info = shadow.to_user_info(raw_token=result.raw_token)

        # --- populate cache -----------------------------------------
        if self._cache_ttl > 0 and credential:
            self._cache[credential] = (
                user_info,
                time.monotonic() + self._cache_ttl,
            )

        return user_info


def create_auth_strategy(
    config: Optional[AuthConfig],
    shadow_store: Optional[ShadowUserStore] = None,
) -> Optional[AuthStrategy]:
    """
    Factory that builds an AuthStrategy from ``config``.

    Returns:
        - ``None`` when ``config`` is None (anonymous fallback mode).
        - An ``AuthStrategy`` wrapping the configured provider otherwise.
    """
    if config is None:
        return None

    from app.atlasclaw.auth.providers import create_provider

    try:
        config.validate_provider_config()
    except ValueError as exc:
        logger.error("Auth config validation failed: %s", exc)
        raise

    store = shadow_store or ShadowUserStore()
    provider = create_provider(config)
    return AuthStrategy(
        provider=provider,
        shadow_store=store,
        cache_ttl_seconds=config.cache_ttl_seconds,
    )
