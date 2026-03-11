"""Registry for channel adapter instances and factories."""

from __future__ import annotations

from typing import Any, Optional, Type

from .base import ChannelAdapter, ChannelConfig
from .websocket_adapter import WebSocketAdapter
from .sse_adapter import SSEAdapter
from .rest_adapter import RESTCallbackAdapter


class ChannelAdapterRegistry:
    """Manage channel adapter instances and factory lookups.

    Example:
        ```python
        registry = ChannelAdapterRegistry()
        registry.register("ws", WebSocketAdapter(config))
        adapter = registry.get("ws")
        ```
    """
    
    def __init__(self) -> None:
        """Initialize the registry with built-in adapter factories."""
        self._adapters: dict[str, ChannelAdapter] = {}
        self._factories: dict[str, Type[ChannelAdapter]] = {
            "websocket": WebSocketAdapter,
            "sse": SSEAdapter,
            "rest": RESTCallbackAdapter,
        }
    
    def register(self, channel_id: str, adapter: ChannelAdapter) -> None:
        """Register an adapter instance under a channel ID."""
        self._adapters[channel_id] = adapter
    
    def unregister(self, channel_id: str) -> bool:
        """Unregister an adapter by channel ID."""
        if channel_id in self._adapters:
            del self._adapters[channel_id]
            return True
        return False
    
    def get(self, channel_id: str) -> Optional[ChannelAdapter]:
        """Return the adapter registered for a channel ID."""
        return self._adapters.get(channel_id)
    
    def list_channels(self) -> list[str]:
        """Return all registered channel IDs."""
        return list(self._adapters.keys())
    
    def create(
        self,
        channel_type: str,
        config: ChannelConfig,
        **kwargs: Any,
    ) -> Optional[ChannelAdapter]:
        """Create an adapter instance using a registered factory."""
        factory = self._factories.get(channel_type)
        if not factory:
            return None
        
        return factory(config, **kwargs)
    
    def create_and_register(
        self,
        channel_id: str,
        channel_type: str,
        config: ChannelConfig,
        **kwargs: Any,
    ) -> Optional[ChannelAdapter]:
        """Create an adapter and register it under the provided channel ID."""
        adapter = self.create(channel_type, config, **kwargs)
        if adapter:
            self.register(channel_id, adapter)
        return adapter
    
    def register_factory(
        self,
        channel_type: str,
        factory: Type[ChannelAdapter],
    ) -> None:
        """

registeradapterfactory
        
        Args:
            channel_type:channeltype
            factory:adapter
        
"""
        self._factories[channel_type] = factory


def create_adapter(
    channel_type: str,
    config: ChannelConfig,
    **kwargs: Any,
) -> Optional[ChannelAdapter]:
    """

createadapter count
    
    Args:
        channel_type:channeltype
        config:Channel configuration
        **kwargs:parameter
        
    Returns:
        adapterinstanceor None
    
"""
    registry = ChannelAdapterRegistry()
    return registry.create(channel_type, config, **kwargs)
