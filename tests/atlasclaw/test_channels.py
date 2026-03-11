# -*- coding: utf-8 -*-
"""
渠道适配器模块单元测试

测试 BaseChannelAdapter、WebSocketAdapter、SSEAdapter、RESTCallbackAdapter、
ChannelAdapterRegistry 等组件。
"""

import asyncio
import json

import pytest

from app.atlasclaw.channels.base import (
    BaseChannelAdapter,
    ChannelConfig,
    ChannelMessage,
    DeliveryStatus,
    MessageChunk,
    MessageType,
    SendResult,
    TypingIndicator,
)
from app.atlasclaw.channels.registry import ChannelAdapterRegistry
from app.atlasclaw.channels.sse_adapter import SSEAdapter
from app.atlasclaw.channels.websocket_adapter import WebSocketAdapter


# ── 测试辅助 ────────────────────────────────────────────────────


class _FakeWebSocket:
    """假 WebSocket 连接"""

    def __init__(self, *, is_closed: bool = False):
        self.sent: list[dict] = []
        self._closed = is_closed

    @property
    def closed(self) -> bool:
        return self._closed

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class _ConcreteAdapter(BaseChannelAdapter):
    """BaseChannelAdapter 的具体实现用于测试"""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.sent_messages: list[tuple[str, str]] = []

    async def send_message(self, chat_id, content, **kwargs):
        self.sent_messages.append((chat_id, content))
        return SendResult(success=True, message_id="msg-1", status=DeliveryStatus.SENT)


# ── Data Models ─────────────────────────────────────────────────


class TestChannelConfig:
    """ChannelConfig 测试类"""

    def test_create_config(self):
        """测试创建配置"""
        config = ChannelConfig(
            channel_id="test", channel_type="websocket",
        )
        assert config.channel_id == "test"
        assert config.text_chunk_limit == 4096
        assert config.supports_markdown

    def test_config_with_custom_values(self):
        """测试自定义配置"""
        config = ChannelConfig(
            channel_id="telegram",
            channel_type="telegram",
            text_chunk_limit=4096,
            supports_reactions=True,
            rate_limit_per_second=30.0,
        )
        assert config.supports_reactions
        assert config.rate_limit_per_second == 30.0


class TestSendResult:
    """SendResult 测试类"""

    def test_success_result(self):
        """测试成功结果"""
        r = SendResult(success=True, message_id="m1", status=DeliveryStatus.SENT)
        assert r.success
        assert r.message_id == "m1"

    def test_failure_result(self):
        """测试失败结果"""
        r = SendResult(success=False, error="timeout", status=DeliveryStatus.FAILED)
        assert not r.success
        assert r.error == "timeout"


class TestChannelMessage:
    """ChannelMessage 测试类"""

    def test_create_text_message(self):
        """测试创建文本消息"""
        msg = ChannelMessage(
            message_id="m1",
            channel_id="ws",
            chat_id="c1",
            content="Hello",
        )
        assert msg.message_type == MessageType.TEXT
        assert msg.content == "Hello"

    def test_message_with_reply(self):
        """测试带回复的消息"""
        msg = ChannelMessage(
            message_id="m1", channel_id="ws", chat_id="c1",
            content="Reply", reply_to_id="m0",
        )
        assert msg.reply_to_id == "m0"


# ── BaseChannelAdapter ──────────────────────────────────────────


class TestBaseChannelAdapter:
    """BaseChannelAdapter 测试类"""

    def test_properties(self):
        """测试属性"""
        config = ChannelConfig(channel_id="test", channel_type="ws")
        adapter = _ConcreteAdapter(config)
        assert adapter.channel_id == "test"
        assert adapter.config is config

    def test_split_content_short(self):
        """短文本不分割"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", text_chunk_limit=100,
        )
        adapter = _ConcreteAdapter(config)
        chunks = adapter.split_content("Short text")
        assert len(chunks) == 1
        assert chunks[0] == "Short text"

    def test_split_content_long(self):
        """长文本分割"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", text_chunk_limit=50,
        )
        adapter = _ConcreteAdapter(config)
        text = "Word " * 30  # ~150 chars
        chunks = adapter.split_content(text)
        assert len(chunks) >= 2
        assert all(len(c) <= 50 for c in chunks)

    def test_format_content_passthrough(self):
        """默认内容直通"""
        config = ChannelConfig(channel_id="test", channel_type="ws")
        adapter = _ConcreteAdapter(config)
        assert adapter.format_content("**bold**") == "**bold**"

    def test_markdown_to_html(self):
        """测试 Markdown 转 HTML"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", markdown_to_html=True,
        )
        adapter = _ConcreteAdapter(config)
        result = adapter.format_content("**bold**")
        assert "<b>bold</b>" in result

    def test_html_to_markdown(self):
        """测试 HTML 转 Markdown"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", html_to_markdown=True,
        )
        adapter = _ConcreteAdapter(config)
        result = adapter.format_content("<b>bold</b>")
        assert "**bold**" in result

    @pytest.mark.asyncio
    async def test_send_typing_indicator(self):
        """测试发送输入指示器"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", supports_typing=True,
        )
        adapter = _ConcreteAdapter(config)
        assert await adapter.send_typing_indicator("chat-1")

    @pytest.mark.asyncio
    async def test_send_typing_unsupported(self):
        """测试不支持输入指示器"""
        config = ChannelConfig(
            channel_id="test", channel_type="ws", supports_typing=False,
        )
        adapter = _ConcreteAdapter(config)
        assert not await adapter.send_typing_indicator("chat-1")

    @pytest.mark.asyncio
    async def test_send_chunk_buffer(self):
        """测试分块缓冲"""
        config = ChannelConfig(channel_id="test", channel_type="ws")
        adapter = _ConcreteAdapter(config)

        # 非最终块只缓冲
        r1 = await adapter.send_chunk("c1", MessageChunk(content="a", chunk_index=0))
        assert r1.success
        assert r1.status == DeliveryStatus.PENDING

        # 最终块触发发送
        r2 = await adapter.send_chunk(
            "c1", MessageChunk(content="b", chunk_index=1, is_final=True),
        )
        assert r2.success
        assert r2.status == DeliveryStatus.SENT
        assert len(adapter.sent_messages) == 1
        assert adapter.sent_messages[0][1] == "ab"

    @pytest.mark.asyncio
    async def test_edit_message_unsupported(self):
        """测试默认不支持编辑"""
        config = ChannelConfig(channel_id="test", channel_type="ws")
        adapter = _ConcreteAdapter(config)
        r = await adapter.edit_message("c1", "m1", "new")
        assert not r.success

    @pytest.mark.asyncio
    async def test_delete_message_unsupported(self):
        """测试默认不支持删除"""
        config = ChannelConfig(channel_id="test", channel_type="ws")
        adapter = _ConcreteAdapter(config)
        assert not await adapter.delete_message("c1", "m1")


# ── WebSocketAdapter ────────────────────────────────────────────


class TestWebSocketAdapter:
    """WebSocketAdapter 测试类"""

    def _make_adapter(self) -> tuple[WebSocketAdapter, _FakeWebSocket]:
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        ws = _FakeWebSocket()
        adapter = WebSocketAdapter(config, connection=ws)
        return adapter, ws

    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试发送消息"""
        adapter, ws = self._make_adapter()
        result = await adapter.send_message("chat-1", "Hello!")
        assert result.success
        assert result.message_id is not None
        assert len(ws.sent) == 1
        assert ws.sent[0]["payload"]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self):
        """测试无连接发送"""
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        adapter = WebSocketAdapter(config)
        result = await adapter.send_message("chat-1", "Hello!")
        assert not result.success

    @pytest.mark.asyncio
    async def test_send_message_closed(self):
        """测试连接已关闭"""
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        ws = _FakeWebSocket(is_closed=True)
        adapter = WebSocketAdapter(config, connection=ws)
        result = await adapter.send_message("chat-1", "Hello!")
        assert not result.success

    @pytest.mark.asyncio
    async def test_send_typing(self):
        """测试发送输入指示器"""
        adapter, ws = self._make_adapter()
        result = await adapter.send_typing_indicator("chat-1")
        assert result
        assert ws.sent[-1]["event"] == "typing"

    @pytest.mark.asyncio
    async def test_send_chunk(self):
        """测试发送分块"""
        adapter, ws = self._make_adapter()
        chunk = MessageChunk(content="Partial", chunk_index=0, is_final=False)
        result = await adapter.send_chunk("chat-1", chunk)
        assert result.success
        assert ws.sent[-1]["event"] == "stream"
        assert ws.sent[-1]["payload"]["content"] == "Partial"

    @pytest.mark.asyncio
    async def test_edit_message(self):
        """测试编辑消息"""
        adapter, ws = self._make_adapter()
        result = await adapter.edit_message("chat-1", "msg-1", "Updated")
        assert result.success
        assert ws.sent[-1]["event"] == "message_edit"

    @pytest.mark.asyncio
    async def test_delete_message(self):
        """测试删除消息"""
        adapter, ws = self._make_adapter()
        result = await adapter.delete_message("chat-1", "msg-1")
        assert result
        assert ws.sent[-1]["event"] == "message_delete"

    def test_add_remove_connection(self):
        """测试添加/移除连接"""
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        adapter = WebSocketAdapter(config)
        ws = _FakeWebSocket()
        adapter.add_connection("chat-1", ws)
        assert adapter.get_connection("chat-1") is ws
        adapter.remove_connection("chat-1")
        assert adapter.get_connection("chat-1") is None

    @pytest.mark.asyncio
    async def test_seq_increments(self):
        """测试序列号递增"""
        adapter, ws = self._make_adapter()
        adapter.add_connection("c1", ws)
        await adapter.send_message("c1", "msg1")
        await adapter.send_message("c1", "msg2")
        assert ws.sent[-1]["seq"] > ws.sent[0]["seq"]


# ── SSEAdapter ──────────────────────────────────────────────────


class TestSSEAdapter:
    """SSEAdapter 测试类"""

    def _make_adapter(self) -> tuple[SSEAdapter, list[tuple[str, dict]]]:
        config = ChannelConfig(channel_id="sse", channel_type="sse")
        adapter = SSEAdapter(config)
        received: list[tuple[str, dict]] = []

        def sender(event_type: str, data: dict):
            received.append((event_type, data))

        adapter.register_sender("chat-1", sender)
        return adapter, received

    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试发送消息"""
        adapter, received = self._make_adapter()
        result = await adapter.send_message("chat-1", "Hello!")
        assert result.success
        assert len(received) == 1
        assert received[0][0] == "message"
        assert received[0][1]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_message_no_sender(self):
        """测试无发送函数"""
        config = ChannelConfig(channel_id="sse", channel_type="sse")
        adapter = SSEAdapter(config)
        result = await adapter.send_message("chat-1", "Hello!")
        assert not result.success

    @pytest.mark.asyncio
    async def test_send_typing(self):
        """测试发送输入指示器"""
        adapter, received = self._make_adapter()
        result = await adapter.send_typing_indicator("chat-1")
        assert result
        assert received[-1][0] == "typing"

    @pytest.mark.asyncio
    async def test_send_chunk(self):
        """测试发送分块"""
        adapter, received = self._make_adapter()
        chunk = MessageChunk(content="Delta", chunk_index=0, is_final=False)
        result = await adapter.send_chunk("chat-1", chunk)
        assert result.success
        assert received[-1][0] == "assistant"  # 非 final 用 assistant 事件

    @pytest.mark.asyncio
    async def test_send_chunk_final(self):
        """测试最终分块"""
        adapter, received = self._make_adapter()
        chunk = MessageChunk(content="End", chunk_index=1, is_final=True)
        result = await adapter.send_chunk("chat-1", chunk)
        assert result.success
        assert received[-1][0] == "message"  # final 用 message 事件

    @pytest.mark.asyncio
    async def test_async_sender(self):
        """测试异步发送函数"""
        config = ChannelConfig(channel_id="sse", channel_type="sse")
        adapter = SSEAdapter(config)
        received = []

        async def async_sender(event_type: str, data: dict):
            received.append((event_type, data))

        adapter.register_sender("chat-1", async_sender)
        result = await adapter.send_message("chat-1", "Async test")
        assert result.success
        assert len(received) == 1

    def test_unregister_sender(self):
        """测试注销发送函数"""
        adapter, _ = self._make_adapter()
        adapter.unregister_sender("chat-1")
        assert adapter._senders.get("chat-1") is None

    def test_format_sse_event(self):
        """测试格式化 SSE 事件"""
        sse = SSEAdapter.format_sse_event("message", {"text": "hello"}, event_id=42)
        assert "id: 42" in sse
        assert "event: message" in sse
        assert "data: " in sse
        assert "hello" in sse

    def test_format_sse_event_no_id(self):
        """测试无 ID 格式化"""
        sse = SSEAdapter.format_sse_event("ping", {})
        assert "id:" not in sse
        assert "event: ping" in sse


# ── ChannelAdapterRegistry ──────────────────────────────────────


class TestChannelAdapterRegistry:
    """ChannelAdapterRegistry 测试类"""

    def test_register_and_get(self):
        """测试注册和获取"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        adapter = WebSocketAdapter(config)
        registry.register("ws", adapter)
        assert registry.get("ws") is adapter

    def test_unregister(self):
        """测试注销"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        registry.register("ws", WebSocketAdapter(config))
        assert registry.unregister("ws")
        assert registry.get("ws") is None

    def test_unregister_nonexistent(self):
        """测试注销不存在的适配器"""
        registry = ChannelAdapterRegistry()
        assert not registry.unregister("ghost")

    def test_list_channels(self):
        """测试列出渠道"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="a", channel_type="ws")
        registry.register("a", WebSocketAdapter(config))
        registry.register("b", SSEAdapter(ChannelConfig(channel_id="b", channel_type="sse")))
        channels = registry.list_channels()
        assert set(channels) == {"a", "b"}

    def test_create_websocket(self):
        """测试工厂创建 WebSocket"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        adapter = registry.create("websocket", config)
        assert isinstance(adapter, WebSocketAdapter)

    def test_create_sse(self):
        """测试工厂创建 SSE"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="sse", channel_type="sse")
        adapter = registry.create("sse", config)
        assert isinstance(adapter, SSEAdapter)

    def test_create_unknown(self):
        """测试创建未知类型"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="x", channel_type="x")
        assert registry.create("unknown_type", config) is None

    def test_create_and_register(self):
        """测试创建并注册"""
        registry = ChannelAdapterRegistry()
        config = ChannelConfig(channel_id="ws", channel_type="websocket")
        adapter = registry.create_and_register("ws-1", "websocket", config)
        assert adapter is not None
        assert registry.get("ws-1") is adapter

    def test_register_factory(self):
        """测试注册工厂"""
        registry = ChannelAdapterRegistry()
        registry.register_factory("custom", WebSocketAdapter)
        config = ChannelConfig(channel_id="c", channel_type="custom")
        adapter = registry.create("custom", config)
        assert isinstance(adapter, WebSocketAdapter)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
