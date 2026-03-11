# -*- coding: utf-8 -*-
"""
AuthProvider 单元测试

涵盖 SmartCMPProvider、OIDCProvider、APIKeyProvider、NoneProvider。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.atlasclaw.auth.models import AuthResult, AuthenticationError
from app.atlasclaw.auth.providers.none import NoneProvider
from app.atlasclaw.auth.providers.smartcmp import SmartCMPProvider
from app.atlasclaw.auth.providers.api_key import APIKeyProvider
from app.atlasclaw.auth.config import SmartCMPAuthConfig, APIKeyAuthConfig


# ───────────────────────────────────────────────────────────
# NoneProvider
# ───────────────────────────────────────────────────────────

class TestNoneProvider:
    def test_provider_name(self):
        provider = NoneProvider()
        assert provider.provider_name() == "none"

    @pytest.mark.asyncio
    async def test_returns_default_user(self):
        provider = NoneProvider(default_user_id="admin")
        result = await provider.authenticate("")
        assert result.subject == "admin"
        assert result.display_name == "Default User"

    @pytest.mark.asyncio
    async def test_ignores_credential(self):
        provider = NoneProvider(default_user_id="dev")
        result = await provider.authenticate("any-token")
        assert result.subject == "dev"


# ───────────────────────────────────────────────────────────
# SmartCMPProvider
# ───────────────────────────────────────────────────────────

class TestSmartCMPProvider:
    def _make_provider(self, validate_url="https://api.example.com/validate"):
        return SmartCMPProvider(validate_url=validate_url)

    def test_provider_name(self):
        assert self._make_provider().provider_name() == "smartcmp"

    @pytest.mark.asyncio
    async def test_empty_token_raises(self):
        provider = self._make_provider()
        with pytest.raises(AuthenticationError, match="empty"):
            await provider.authenticate("")

    @pytest.mark.asyncio
    async def test_whitespace_token_raises(self):
        provider = self._make_provider()
        with pytest.raises(AuthenticationError, match="empty"):
            await provider.authenticate("   ")

    @pytest.mark.asyncio
    async def test_valid_token_returns_auth_result(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "loginName": "alice",
            "displayName": "Alice User",
            "tenantId": "t-001",
            "email": "alice@corp.com",
            "roles": ["admin"],
        }

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            result = await provider.authenticate("valid-token")

        assert result.subject == "alice"
        assert result.display_name == "Alice User"
        assert result.tenant_id == "t-001"

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(AuthenticationError):
                await provider.authenticate("bad-token")


# ───────────────────────────────────────────────────────────
# APIKeyProvider
# ───────────────────────────────────────────────────────────

class TestAPIKeyProvider:
    def _make_provider(self):
        keys = {
            "key-abc": {"user_id": "u-abc", "display_name": "API User"},
            "key-xyz": {"user_id": "u-xyz"},
        }
        return APIKeyProvider(keys=keys)

    def test_provider_name(self):
        assert self._make_provider().provider_name() == "api_key"

    @pytest.mark.asyncio
    async def test_known_key_returns_result(self):
        provider = self._make_provider()
        result = await provider.authenticate("key-abc")
        assert result.subject == "u-abc"
        assert result.display_name == "API User"

    @pytest.mark.asyncio
    async def test_unknown_key_raises(self):
        provider = self._make_provider()
        with pytest.raises(AuthenticationError):
            await provider.authenticate("unknown-key")

    @pytest.mark.asyncio
    async def test_empty_key_raises(self):
        provider = self._make_provider()
        with pytest.raises(AuthenticationError):
            await provider.authenticate("")
