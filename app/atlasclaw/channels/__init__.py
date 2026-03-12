# -*- coding: utf-8 -*-
"""Channel management for AtlasClaw."""

from __future__ import annotations

from .handler import ChannelHandler
from .manager import ChannelManager
from .models import (
    ChannelConnection,
    ChannelMode,
    ChannelValidationResult,
    ConnectionStatus,
    InboundMessage,
    OutboundMessage,
    SendResult,
)
from .registry import ChannelRegistry
from .store import ChannelStore

__all__ = [
    "ChannelHandler",
    "ChannelManager",
    "ChannelRegistry",
    "ChannelStore",
    "ChannelConnection",
    "ChannelMode",
    "ChannelValidationResult",
    "ConnectionStatus",
    "InboundMessage",
    "OutboundMessage",
    "SendResult",
]
