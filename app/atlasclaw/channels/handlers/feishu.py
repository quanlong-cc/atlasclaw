# -*- coding: utf-8 -*-
"""Feishu (Lark) channel handler with WebSocket long connection."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

import aiohttp

from ..handler import ChannelHandler
from ..models import (
    ChannelMode,
    ChannelValidationResult,
    ConnectionStatus,
    InboundMessage,
    OutboundMessage,
    SendResult,
)

logger = logging.getLogger(__name__)


class FeishuHandler(ChannelHandler):
    """Feishu channel handler using WebSocket long connection to Event Center."""
    
    channel_type = "feishu"
    channel_name = "Feishu"
    channel_icon = "🐦"
    channel_mode = ChannelMode.BIDIRECTIONAL
    supports_long_connection = True
    supports_webhook = False
    
    # Feishu API endpoints
    FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
    AUTH_URL = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    WS_URL = "wss://ws.feishu.cn/ws"  # WebSocket endpoint for Event Center
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._ws_connection: Optional[Any] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._message_callback: Optional[Callable[[InboundMessage], None]] = None
        self._reconnect_interval = 5  # seconds
        self._max_reconnect_attempts = 10
        self._