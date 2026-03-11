"""Channel adapter interfaces and built-in adapter exports."""

from app.atlasclaw.channels.base import (
    ChannelAdapter,
    ChannelMessage,
    ChannelConfig,
    MessageChunk,
    TypingIndicator,
)
from app.atlasclaw.channels.registry import (
    ChannelAdapterRegistry,
    create_adapter,
)
from app.atlasclaw.channels.websocket_adapter import WebSocketAdapter
from app.atlasclaw.channels.sse_adapter import SSEAdapter
from app.atlasclaw.channels.rest_adapter import RESTCallbackAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "ChannelConfig",
    "MessageChunk",
    "TypingIndicator",
    "ChannelAdapterRegistry",
    "create_adapter",
    "WebSocketAdapter",
    "SSEAdapter",
    "RESTCallbackAdapter",
]
