# -*- coding: utf-8 -*-
"""Channel configuration store for user-specific channel connections."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ChannelConnection

logger = logging.getLogger(__name__)


class ChannelStore:
    """Store for user channel connection configurations.
    
    Stores channel configurations per-user in:
    <workspace>/users/<user_id>/channels/<channel_type>.json
    """
    
    def __init__(self, workspace_path: Path):
        """Initialize channel store.
        
        Args:
            workspace_path: Path to workspace directory
        """
        self.workspace_path = Path(workspace_path)
        self.channels_dir = self.workspace_path / "users"
    
    def _get_user_channels_dir(self, user_id: str) -> Path:
        """Get user's channels directory.
        
        Args:
            user_id: User identifier
            
        Returns:
            Path to user's channels directory
        """
        return self.channels_dir / user_id / "channels"
    
    def _get_config_path(self, user_id: str, channel_type: str) -> Path:
        """Get configuration file path.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            
        Returns:
            Path to configuration file
        """
        return self._get_user_channels_dir(user_id) / f"{channel_type}.json"
    
    def _ensure_dir(self, path: Path) -> None:
        """Ensure directory exists.
        
        Args:
            path: Directory path
        """
        path.mkdir(parents=True, exist_ok=True)
    
    def get_connections(
        self,
        user_id: str,
        channel_type: str
    ) -> List[ChannelConnection]:
        """Get all connections for a user and channel type.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            
        Returns:
            List of channel connections
        """
        config_path = self._get_config_path(user_id, channel_type)
        
        if not config_path.exists():
            return []
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            connections_data = data.get("connections", [])
            connections = []
            
            for conn_data in connections_data:
                connection = ChannelConnection(
                    id=conn_data.get("id", ""),
                    name=conn_data.get("name", ""),
                    channel_type=channel_type,
                    config=conn_data.get("config", {}),
                    enabled=conn_data.get("enabled", True),
                    is_default=conn_data.get("is_default", False),
                )
                connections.append(connection)
            
            return connections
            
        except Exception as e:
            logger.error(f"Failed to load connections for {user_id}/{channel_type}: {e}")
            return []
    
    def get_connection(
        self,
        user_id: str,
        channel_type: str,
        connection_id: str
    ) -> Optional[ChannelConnection]:
        """Get a specific connection.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            connection_id: Connection identifier
            
        Returns:
            Channel connection or None if not found
        """
        connections = self.get_connections(user_id, channel_type)
        
        for conn in connections:
            if conn.id == connection_id:
                return conn
        
        return None
    
    def save_connection(
        self,
        user_id: str,
        channel_type: str,
        connection: ChannelConnection
    ) -> bool:
        """Save a connection.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            connection: Connection to save
            
        Returns:
            True if saved successfully
        """
        try:
            config_path = self._get_config_path(user_id, channel_type)
            self._ensure_dir(config_path.parent)
            
            # Load existing connections
            connections = self.get_connections(user_id, channel_type)
            
            # Update or add connection
            found = False
            for i, conn in enumerate(connections):
                if conn.id == connection.id:
                    connections[i] = connection
                    found = True
                    break
            
            if not found:
                connections.append(connection)
            
            # Save to file
            data = {
                "channel_type": channel_type,
                "connections": [
                    {
                        "id": conn.id,
                        "name": conn.name,
                        "config": conn.config,
                        "enabled": conn.enabled,
                        "is_default": conn.is_default,
                    }
                    for conn in connections
                ]
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save connection: {e}")
            return False
    
    def delete_connection(
        self,
        user_id: str,
        channel_type: str,
        connection_id: str
    ) -> bool:
        """Delete a connection.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            connection_id: Connection identifier
            
        Returns:
            True if deleted successfully
        """
        try:
            config_path = self._get_config_path(user_id, channel_type)
            
            if not config_path.exists():
                return False
            
            # Load existing connections
            connections = self.get_connections(user_id, channel_type)
            
            # Remove connection
            connections = [c for c in connections if c.id != connection_id]
            
            # Save to file
            data = {
                "channel_type": channel_type,
                "connections": [
                    {
                        "id": conn.id,
                        "name": conn.name,
                        "config": conn.config,
                        "enabled": conn.enabled,
                        "is_default": conn.is_default,
                    }
                    for conn in connections
                ]
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete connection: {e}")
            return False
    
    def update_connection_status(
        self,
        user_id: str,
        channel_type: str,
        connection_id: str,
        enabled: bool
    ) -> bool:
        """Update connection enabled status.
        
        Args:
            user_id: User identifier
            channel_type: Channel type
            connection_id: Connection identifier
            enabled: New enabled status
            
        Returns:
            True if updated successfully
        """
        connection = self.get_connection(user_id, channel_type, connection_id)
        
        if not connection:
            return False
        
        connection.enabled = enabled
        return self.save_connection(user_id, channel_type, connection)
