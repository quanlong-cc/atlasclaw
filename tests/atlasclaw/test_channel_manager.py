# -*- coding: utf-8 -*-
"""Tests for ChannelManager."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.atlasclaw.channels import ChannelConnection, ChannelRegistry
from app.atlasclaw.channels.handlers import WebSocketHandler
from app.atlasclaw.channels.manager import ChannelManager


class TestChannelManager:
    """Test ChannelManager functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ChannelManager(self.temp_dir)
        
        # Clear registry
        ChannelRegistry._handlers.clear()
        ChannelRegistry._instances.clear()
        ChannelRegistry._connections.clear()
        
        # Register test handler
        ChannelRegistry.register("websocket", WebSocketHandler)

    @pytest.mark.asyncio
    async def test_initialize_connection(self):
        """Test initializing a connection."""
        # Save connection config first
        conn = ChannelConnection(
            id="conn-123",
            name="Test Connection",
            channel_type="websocket",
            config={"path": "/ws"},
            enabled=True,
        )
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        # Initialize connection
        # Note: WebSocketHandler supports long connection but base connect() returns False
        # In production, Feishu/Slack handlers would override connect() to return True
        result = await self.manager.initialize_connection("user-123", "websocket", "conn-123")
        
        # Base WebSocketHandler.connect() returns False, so initialization fails
        # This is expected - real implementations would override connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_connection_not_found(self):
        """Test initializing a non-existent connection."""
        result = await self.manager.initialize_connection("user-123", "websocket", "nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_connection(self):
        """Test stopping a connection."""
        # Setup connection first
        conn = ChannelConnection(
            id="conn-123",
            name="Test",
            channel_type="websocket",
            config={},
            enabled=True,
        )
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        # Note: initialize_connection fails because base connect() returns False
        # So we manually add a handler to test stop_connection
        from app.atlasclaw.channels.handlers import WebSocketHandler
        handler = WebSocketHandler({})
        instance_key = "user-123:websocket:conn-123"
        self.manager._active_connections[instance_key] = handler
        
        # Stop connection
        result = await self.manager.stop_connection("user-123", "websocket", "conn-123")
        
        assert result is True
        
        # Check that instance was removed
        assert instance_key not in self.manager._active_connections

    @pytest.mark.asyncio
    async def test_stop_connection_not_active(self):
        """Test stopping a connection that is not active."""
        result = await self.manager.stop_connection("user-123", "websocket", "nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_route_inbound_message(self):
        """Test routing inbound message."""
        # Setup connection - manually add handler since initialize_connection fails
        conn = ChannelConnection(
            id="conn-123",
            name="Test",
            channel_type="websocket",
            config={},
            enabled=True,
        )
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        # Manually create and register handler
        from app.atlasclaw.channels.handlers import WebSocketHandler
        handler = WebSocketHandler({})
        instance_key = "user-123:websocket:conn-123"
        ChannelRegistry.create_instance(instance_key, "websocket", {})
        self.manager._active_connections[instance_key] = handler
        
        # Route message
        request = {
            "message_id": "msg-123",
            "sender_id": "user-456",
            "sender_name": "Test User",
            "chat_id": "chat-789",
            "content": "Hello",
        }
        
        inbound = await self.manager.route_inbound_message("websocket", "conn-123", request)
        
        assert inbound is not None
        assert inbound.message_id == "msg-123"
        assert inbound.content == "Hello"

    @pytest.mark.asyncio
    async def test_route_inbound_message_no_handler(self):
        """Test routing when handler not found."""
        inbound = await self.manager.route_inbound_message("websocket", "nonexistent", {})
        
        assert inbound is None

    def test_get_user_connections(self):
        """Test getting user connections."""
        # Save connections
        conn1 = ChannelConnection(id="conn-1", name="Conn 1", channel_type="websocket")
        conn2 = ChannelConnection(id="conn-2", name="Conn 2", channel_type="websocket")
        
        self.manager.store.save_connection("user-123", "websocket", conn1)
        self.manager.store.save_connection("user-123", "websocket", conn2)
        
        # Get connections
        connections = self.manager.get_user_connections("user-123")
        
        assert len(connections) == 2

    def test_get_user_connections_with_filter(self):
        """Test getting user connections with channel type filter."""
        conn = ChannelConnection(id="conn-1", name="Conn 1", channel_type="websocket")
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        connections = self.manager.get_user_connections("user-123", "websocket")
        
        assert len(connections) == 1
        assert connections[0]["channel_type"] == "websocket"

    @pytest.mark.asyncio
    async def test_enable_connection(self):
        """Test enabling a connection."""
        conn = ChannelConnection(
            id="conn-123",
            name="Test",
            channel_type="websocket",
            config={},
            enabled=False,
        )
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        # Note: enable_connection calls initialize_connection which fails
        # because base connect() returns False
        result = await self.manager.enable_connection("user-123", "websocket", "conn-123")
        
        # Result is False because initialization fails
        assert result is False
        
        # But connection status should still be enabled
        retrieved = self.manager.store.get_connection("user-123", "websocket", "conn-123")
        assert retrieved.enabled is True

    @pytest.mark.asyncio
    async def test_disable_connection(self):
        """Test disabling a connection."""
        # Setup and manually add handler
        conn = ChannelConnection(
            id="conn-123",
            name="Test",
            channel_type="websocket",
            config={},
            enabled=True,
        )
        self.manager.store.save_connection("user-123", "websocket", conn)
        
        # Manually add handler since initialize_connection fails
        from app.atlasclaw.channels.handlers import WebSocketHandler
        handler = WebSocketHandler({})
        instance_key = "user-123:websocket:conn-123"
        self.manager._active_connections[instance_key] = handler
        
        # Disable
        result = await self.manager.disable_connection("user-123", "websocket", "conn-123")
        
        assert result is True
        
        # Check connection is disabled
        retrieved = self.manager.store.get_connection("user-123", "websocket", "conn-123")
        assert retrieved.enabled is False
