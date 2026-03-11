"""APIKeyProvider — static API key lookup from atlasclaw.json config."""

from __future__ import annotations

from typing import Any

from app.atlasclaw.auth.models import AuthResult, AuthenticationError
from app.atlasclaw.auth.providers.base import AuthProvider


class APIKeyProvider(AuthProvider):
    """
    Validates a static API key against the `auth.api_key.keys` config table.

    Config example in atlasclaw.json:
        "api_key": {
          "keys": {
            "sk-dev-key-001": {
              "user_id": "dev-user",
              "display_name": "Dev User",
              "roles": ["admin"]
            }
          }
        }
    """

    def __init__(self, keys: dict[str, dict[str, Any]]) -> None:
        # keys: {api_key_string -> {user_id, display_name, roles, ...}}
        self._keys = keys

    def provider_name(self) -> str:
        return "api_key"

    async def authenticate(self, credential: str) -> AuthResult:
        if not credential:
            raise AuthenticationError("API key is empty")

        entry = self._keys.get(credential)
        if entry is None:
            raise AuthenticationError("Invalid or unknown API key")

        return AuthResult(
            subject=entry.get("user_id", credential),
            display_name=entry.get("display_name", ""),
            roles=entry.get("roles", []),
            tenant_id=entry.get("tenant_id", "default"),
            raw_token=credential,
            extra=dict(entry),
        )
