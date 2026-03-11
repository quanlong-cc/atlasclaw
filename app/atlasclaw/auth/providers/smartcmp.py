"""SmartCMPProvider — validates CloudChef-Authenticate tokens via platform API."""

from __future__ import annotations

import httpx

from app.atlasclaw.auth.models import AuthResult, AuthenticationError
from app.atlasclaw.auth.providers.base import AuthProvider


class SmartCMPProvider(AuthProvider):
    """
    Calls the SmartCMP platform validate endpoint to verify the token.

    Requires `auth.smartcmp.validate_url` in atlasclaw.json.
    Verification results should be cached by AuthStrategy (TTL-based).
    """

    def __init__(self, validate_url: str, api_base_url: str = "") -> None:
        self._validate_url = validate_url
        self._api_base_url = api_base_url

    def provider_name(self) -> str:
        return "smartcmp"

    async def authenticate(self, credential: str) -> AuthResult:
        # Pre-validation: reject obviously empty or whitespace-only tokens
        if not credential or not credential.strip():
            raise AuthenticationError("SmartCMP token is empty or invalid format")

        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                resp = await client.get(
                    self._validate_url,
                    headers={"CloudChef-Authenticate": credential},
                )

            if resp.status_code != 200:
                raise AuthenticationError(
                    f"SmartCMP token validation failed: HTTP {resp.status_code}"
                )

            data = resp.json()

            # Prefer loginName, fall back to username / userId
            subject = (
                data.get("loginName")
                or data.get("username")
                or data.get("userId")
                or ""
            )
            if not subject:
                raise AuthenticationError(
                    "SmartCMP validation response missing user subject"
                )

            return AuthResult(
                subject=subject,
                display_name=(
                    data.get("displayName")
                    or data.get("fullName")
                    or subject
                ),
                email=data.get("email", ""),
                roles=data.get("roles", []),
                tenant_id=data.get("tenantId", "default"),
                raw_token=credential,
                extra=data,
            )

        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError(
                f"SmartCMP authentication error: {exc}"
            ) from exc
