# -*- coding: utf-8 -*-
"""WhatsApp channel handler."""

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


class WhatsAppHandler(ChannelHandler):
    """WhatsApp channel handler using WhatsApp Business API.
    
    Connects to WhatsApp Business API for messaging.
    Supports both Webhook and WebSocket modes depending on configuration.
    """
    
    channel_type = "whatsapp"
    channel_name = "WhatsApp"
    channel_icon = "💬"
    channel_mode = ChannelMode.BIDIRECTIONAL
    supports_long_connection = True
    supports_webhook = True
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._phone_number_id: Optional[str] = None
        self._business_account_id: Optional[str] = None
        self._websocket: Optional[Any] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
    
    async def setup(self, connection_config: Dict[str, Any]) -> bool:
        """Initialize WhatsApp handler with configuration.
        
        Args:
            connection_config: Configuration with access_token, phone_number_id
            
        Returns:
            True if setup successful
        """
        try:
            self.config.update(connection_config)
            
            # Validate required fields
            if not self.config.get("access_token"):
                logger.error("WhatsApp access_token is required")
                return False
            if not self.config.get("phone_number_id"):
                logger.error("WhatsApp phone_number_id is required")
                return False
            
            self._access_token = self.config.get("access_token")
            self._phone_number_id = self.config.get("phone_number_id")
            self._business_account_id = self.config.get("business_account_id")
            
            return True
        except Exception as e:
            logger.error(f"WhatsApp setup failed: {e}")
            return False
    
    async def start(self, context: Any) -> bool:
        """Start WhatsApp handler.
        
        Args:
            context: Application context
            
        Returns:
            True if started successfully
        """
        try:
            self._status = ConnectionStatus.CONNECTED
            logger.info("WhatsApp handler started")
            return True
        except Exception as e:
            logger.error(f"WhatsApp start failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False
    
    async def connect(self) -> bool:
        """Establish connection to WhatsApp Business API.
        
        For WhatsApp Cloud API, this validates the connection.
        For WhatsApp Business API on-premise, this establishes WebSocket.
        
        Returns:
            True if connected successfully
        """
        try:
            import aiohttp
            
            # Validate access token by making a test request
            url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        self._status = ConnectionStatus.CONNECTED
                        self._reconnect_attempts = 0
                        logger.info("WhatsApp API connected")
                        return True
                    else:
                        logger.error(f"WhatsApp API validation failed: {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"WhatsApp connect failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from WhatsApp.
        
        Returns:
            True if disconnected successfully
        """
        try:
            self._access_token = None
            self._status = ConnectionStatus.DISCONNECTED
            logger.info("WhatsApp disconnected")
            return True
        except Exception as e:
            logger.error(f"WhatsApp disconnect failed: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """Reconnect to WhatsApp after connection loss.
        
        Returns:
            True if reconnected successfully
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False
        
        self._reconnect_attempts += 1
        logger.info(f"WhatsApp reconnection attempt {self._reconnect_attempts}")
        
        await self.disconnect()
        return await self.connect()
    
    async def stop(self) -> bool:
        """Stop WhatsApp handler and cleanup resources.
        
        Returns:
            True if stopped successfully
        """
        try:
            await self.disconnect()
            self._status = ConnectionStatus.DISCONNECTED
            return True
        except Exception as e:
            logger.error(f"WhatsApp stop failed: {e}")
            return False
    
    async def handle_inbound(self, request: Any) -> Optional[InboundMessage]:
        """Handle incoming WhatsApp message.
        
        Args:
            request: WhatsApp webhook data
            
        Returns:
            Standardized InboundMessage
        """
        try:
            if isinstance(request, str):
                data = json.loads(request)
            else:
                data = request
            
            # Parse WhatsApp webhook format
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            
            if "messages" not in value:
                return None
            
            messages = value.get("messages", [])
            if not messages:
                return None
            
            message = messages[0]
            contacts = value.get("contacts", [{}])[0]
            
            # Extract message content
            msg_type = message.get("type", "text")
            if msg_type == "text":
                content = message.get("text", {}).get("body", "")
            else:
                content = f"[{msg_type}]"
            
            return InboundMessage(
                message_id=message.get("id", ""),
                sender_id=message.get("from", ""),
                sender_name=contacts.get("profile", {}).get("name", "Anonymous"),
                chat_id=message.get("from", ""),
                channel_type=self.channel_type,
                content=content,
                content_type="text",
                metadata={
                    "timestamp": message.get("timestamp"),
                    "type": msg_type,
                },
            )
        except Exception as e:
            logger.error(f"Failed to handle WhatsApp message: {e}")
            return None
    
    async def send_message(self, outbound: OutboundMessage) -> SendResult:
        """Send message to WhatsApp.
        
        Args:
            outbound: Outbound message
            
        Returns:
            SendResult with success status
        """
        try:
            import aiohttp
            
            if not self._access_token or not self._phone_number_id:
                return SendResult(
                    success=False,
                    error="WhatsApp not properly configured"
                )
            
            url = f"https://graph.facebook.com/v18.0/{self._phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": outbound.chat_id,
                "type": "text",
                "text": {"body": outbound.content},
            }
            
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("messages"):
                            return SendResult(
                                success=True,
                                message_id=data["messages"][0].get("id")
                            )
                        else:
                            return SendResult(
                                success=False,
                                error="No message ID returned"
                            )
                    else:
                        error_text = await response.text()
                        return SendResult(
                            success=False,
                            error=f"HTTP {response.status}: {error_text}"
                        )
                        
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return SendResult(success=False, error=str(e))
    
    async def validate_config(self, config: Dict[str, Any]) -> ChannelValidationResult:
        """Validate WhatsApp configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result
        """
        errors = []
        
        if not isinstance(config, dict):
            errors.append("Config must be a dictionary")
            return ChannelValidationResult(valid=False, errors=errors)
        
        if not config.get("access_token"):
            errors.append("access_token is required")
        
        if not config.get("phone_number_id"):
            errors.append("phone_number_id is required")
        
        return ChannelValidationResult(valid=len(errors) == 0, errors=errors)
    
    def describe_schema(self) -> Dict[str, Any]:
        """Return WhatsApp configuration schema.
        
        Returns:
            JSON Schema
        """
        return {
            "type": "object",
            "title": "WhatsApp Configuration",
            "description": "WhatsApp Business API configuration",
            "required": ["access_token", "phone_number_id"],
            "properties": {
                "access_token": {
                    "type": "string",
                    "title": "Access Token",
                    "description": "WhatsApp Business API access token",
                },
                "phone_number_id": {
                    "type": "string",
                    "title": "Phone Number ID",
                    "description": "WhatsApp phone number ID",
                },
                "business_account_id": {
                    "type": "string",
                    "title": "Business Account ID",
                    "description": "WhatsApp Business Account ID (optional)",
                },
                "webhook_verify_token": {
                    "type": "string",
                    "title": "Webhook Verify Token",
                    "description": "Token for webhook verification (optional)",
                },
            },
        }
