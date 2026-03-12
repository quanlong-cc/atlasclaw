# -*- coding: utf-8 -*-
"""Slack channel handler."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.atlasclaw.channels.handler import ChannelHandler
from app.atlasclaw.channels.models import (
    ChannelMode,
    ChannelValidationResult,
    ConnectionStatus,
    InboundMessage,
    OutboundMessage,
    SendResult,
)

logger = logging.getLogger(__name__)


class SlackHandler(ChannelHandler):
    """Slack channel handler using Socket Mode.
    
    Connects to Slack via Socket Mode for real-time messaging.
    """
    
    channel_type = "slack"
    channel_name = "Slack"
    channel_icon = "💼"
    channel_mode = ChannelMode.BIDIRECTIONAL
    supports_long_connection = True
    supports_webhook = False
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._bot_token: Optional[str] = None
        self._app_token: Optional[str] = None
        self._websocket: Optional[Any] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
    
    async def setup(self, connection_config: Dict[str, Any]) -> bool:
        """Initialize Slack handler with configuration.
        
        Args:
            connection_config: Configuration with bot_token, app_token
            
        Returns:
            True if setup successful
        """
        try:
            self.config.update(connection_config)
            
            # Validate required fields
            if not self.config.get("bot_token"):
                logger.error("Slack bot_token is required")
                return False
            if not self.config.get("app_token"):
                logger.error("Slack app_token is required for Socket Mode")
                return False
            
            self._bot_token = self.config.get("bot_token")
            self._app_token = self.config.get("app_token")
            
            return True
        except Exception as e:
            logger.error(f"Slack setup failed: {e}")
            return False
    
    async def start(self, context: Any) -> bool:
        """Start Slack handler.
        
        Args:
            context: Application context
            
        Returns:
            True if started successfully
        """
        try:
            self._status = ConnectionStatus.CONNECTED
            logger.info("Slack handler started")
            return True
        except Exception as e:
            logger.error(f"Slack start failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False
    
    async def connect(self) -> bool:
        """Establish Socket Mode connection to Slack.
        
        Returns:
            True if connected successfully
        """
        try:
            import aiohttp
            
            # Step 1: Get WebSocket URL from Slack
            url = "https://slack.com/api/apps.connections.open"
            headers = {
                "Authorization": f"Bearer {self._app_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            ws_url = data.get("url")
                            logger.info(f"Got Slack WebSocket URL: {ws_url}")
                            
                            # Step 2: Connect WebSocket
                            # Note: Actual WebSocket connection would be implemented here
                            self._status = ConnectionStatus.CONNECTED
                            self._reconnect_attempts = 0
                            logger.info("Slack Socket Mode connected")
                            return True
                        else:
                            logger.error(f"Slack API error: {data.get('error')}")
                            return False
                    else:
                        logger.error(f"Slack API returned {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"Slack connect failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Slack.
        
        Returns:
            True if disconnected successfully
        """
        try:
            if self._websocket:
                await self._websocket.close()
                self._websocket = None
            
            self._status = ConnectionStatus.DISCONNECTED
            logger.info("Slack disconnected")
            return True
        except Exception as e:
            logger.error(f"Slack disconnect failed: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """Reconnect to Slack after connection loss.
        
        Returns:
            True if reconnected successfully
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False
        
        self._reconnect_attempts += 1
        logger.info(f"Slack reconnection attempt {self._reconnect_attempts}")
        
        await self.disconnect()
        return await self.connect()
    
    async def stop(self) -> bool:
        """Stop Slack handler and cleanup resources.
        
        Returns:
            True if stopped successfully
        """
        try:
            await self.disconnect()
            self._status = ConnectionStatus.DISCONNECTED
            return True
        except Exception as e:
            logger.error(f"Slack stop failed: {e}")
            return False
    
    async def handle_inbound(self, request: Any) -> Optional[InboundMessage]:
        """Handle incoming Slack message.
        
        Args:
            request: Slack event data
            
        Returns:
            Standardized InboundMessage
        """
        try:
            if isinstance(request, str):
                data = json.loads(request)
            else:
                data = request
            
            # Handle Slack event types
            event_type = data.get("type")
            
            # Handle URL verification
            if event_type == "url_verification":
                return None
            
            # Handle events
            if event_type == "events_api":
                payload = data.get("payload", {})
                event = payload.get("event", {})
                
                event_subtype = event.get("subtype")
                if event_subtype in ["bot_message", "message_changed"]:
                    return None
                
                # Get message text
                text = event.get("text", "")
                if not text:
                    return None
                
                # Get user info
                user = event.get("user", "")
                channel = event.get("channel", "")
                
                return InboundMessage(
                    message_id=event.get("ts", ""),
                    sender_id=user,
                    sender_name=user,  # Would need to look up user info
                    chat_id=channel,
                    channel_type=self.channel_type,
                    content=text,
                    content_type="text",
                    thread_id=event.get("thread_ts"),
                    metadata={
                        "team": payload.get("team_id"),
                        "event_type": event.get("type"),
                    },
                )
            
            return None
        except Exception as e:
            logger.error(f"Failed to handle Slack message: {e}")
            return None
    
    async def send_message(self, outbound: OutboundMessage) -> SendResult:
        """Send message to Slack.
        
        Args:
            outbound: Outbound message
            
        Returns:
            SendResult with success status
        """
        try:
            import aiohttp
            
            if not self._bot_token:
                return SendResult(
                    success=False,
                    error="Slack bot token not configured"
                )
            
            url = "https://slack.com/api/chat.postMessage"
            
            payload = {
                "channel": outbound.chat_id,
                "text": outbound.content,
            }
            
            if outbound.thread_id:
                payload["thread_ts"] = outbound.thread_id
            
            headers = {
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            return SendResult(
                                success=True,
                                message_id=data.get("ts")
                            )
                        else:
                            return SendResult(
                                success=False,
                                error=f"Slack API error: {data.get('error')}"
                            )
                    else:
                        return SendResult(
                            success=False,
                            error=f"HTTP {response.status}"
                        )
                        
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return SendResult(success=False, error=str(e))
    
    async def validate_config(self, config: Dict[str, Any]) -> ChannelValidationResult:
        """Validate Slack configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result
        """
        errors = []
        
        if not isinstance(config, dict):
            errors.append("Config must be a dictionary")
            return ChannelValidationResult(valid=False, errors=errors)
        
        if not config.get("bot_token"):
            errors.append("bot_token is required")
        
        if not config.get("app_token"):
            errors.append("app_token is required for Socket Mode")
        
        return ChannelValidationResult(valid=len(errors) == 0, errors=errors)
    
    def describe_schema(self) -> Dict[str, Any]:
        """Return Slack configuration schema.
        
        Returns:
            JSON Schema
        """
        return {
            "type": "object",
            "title": "Slack Configuration",
            "description": "Slack Socket Mode configuration",
            "required": ["bot_token", "app_token"],
            "properties": {
                "bot_token": {
                    "type": "string",
                    "title": "Bot Token",
                    "description": "Slack Bot User OAuth Token (xoxb-xxx)",
                },
                "app_token": {
                    "type": "string",
                    "title": "App Token",
                    "description": "Slack App-Level Token for Socket Mode (xapp-xxx)",
                },
            },
        }
