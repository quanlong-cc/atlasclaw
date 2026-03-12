# AtlasClaw Extensions 架构设计

基于当前 AtlasClaw 实现和 Channel Integrations 设计，提供可扩展的 Auth 和 Channel 机制。

## 设计原则

1. **内置 + 可扫描**：核心 Auth 和 Channel 类型内置，同时自动扫描 providers 目录下的扩展
2. **分离关注点**：Auth、Channel、Skills 各自独立，不强制统一接口
3. **用户隔离**：Channel 连接按用户隔离存储，Auth 按配置实例化
4. **协议优先**：使用 Python Protocol 和 ABC 定义契约，而非强制继承
5. **长连接优先**：所有 Channel 优先使用长连接（WebSocket/Socket Mode），Webhook 作为备选

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AtlasClaw 扩展架构                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   AuthProvider  │  │  ChannelHandler │  │        Skills               │  │
│  │   (认证提供者)   │  │   (通道处理器)   │  │      (技能注册表)            │  │
│  │                 │  │                 │  │                             │  │
│  │ • OIDC          │  │ • Feishu        │  │ • Executable                │  │
│  │ • OAuth2        │  │ • Slack         │  │ • Markdown                  │  │
│  │ • API Key       │  │ • WhatsApp      │  │ • Hybrid                    │  │
│  │ • SAML          │  │ • WebSocket     │  │                             │  │
│  │ • (Provider扫描) │  │ • SSE           │  │                             │  │
│  │                 │  │ • REST          │  │                             │  │
│  │                 │  │ • (Provider扫描) │  │                             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│           │                    │                        │                   │
│           ▼                    ▼                        ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Registry (注册表)                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │AuthRegistry  │  │ChannelRegistry│  │    SkillRegistry         │  │   │
│  │  │              │  │              │  │                          │  │   │
│  │  │register()    │  │register()    │  │   register()             │  │   │
│  │  │get()         │  │get()         │  │   execute()              │  │   │
│  │  │list()        │  │list()        │  │   load_from_directory()  │  │   │
│  │  │scan_providers│  │scan_providers│  │                          │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 1. 统一的 Provider 目录扫描机制

Auth、Channel、Skills 都采用相同的目录扫描方式从 providers 加载扩展。

### 1.1 目录结构

```
app/atlasclaw/providers/
└── <provider_name>/
    ├── __init__.py
    ├── config.json              # Provider 配置
    ├── auth/                    # Auth 扩展 (可选)
    │   └── <auth_type>.py       # AuthProvider 实现
    ├── channels/                # Channel 扩展 (可选)
    │   └── <channel_type>.py    # ChannelHandler 实现
    └── skills/                  # Skills 扩展 (可选)
        └── <skill_name>/
            ├── SKILL.md
            └── scripts/
```

### 1.2 扫描加载流程

```python
# 统一的扫描机制
class ProviderScanner:
    """扫描 providers 目录下的 auth、channel、skills 扩展"""
    
    @staticmethod
    def scan_providers(providers_dir: Path):
        """扫描所有 provider 目录"""
        for provider_path in providers_dir.iterdir():
            if not provider_path.is_dir():
                continue
            
            provider_name = provider_path.name
            
            # 1. 扫描 Auth 扩展
            auth_dir = provider_path / "auth"
            if auth_dir.exists():
                ProviderScanner._scan_auth_extensions(auth_dir, provider_name)
            
            # 2. 扫描 Channel 扩展
            channels_dir = provider_path / "channels"
            if channels_dir.exists():
                ProviderScanner._scan_channel_extensions(channels_dir, provider_name)
            
            # 3. 扫描 Skills 扩展 (已存在)
            skills_dir = provider_path / "skills"
            if skills_dir.exists():
                SkillRegistry.load_from_directory(skills_dir, location="built-in")
    
    @staticmethod
    def _scan_auth_extensions(auth_dir: Path, provider_name: str):
        """扫描 Auth 扩展"""
        for auth_file in auth_dir.glob("*.py"):
            if auth_file.name.startswith("_"):
                continue
            # 动态导入并注册
            module = import_module_from_path(auth_file)
            if hasattr(module, "AuthProvider"):
                auth_class = module.AuthProvider
                auth_id = getattr(auth_class, "auth_id", auth_file.stem)
                AuthRegistry.register(auth_id, auth_class)
    
    @staticmethod
    def _scan_channel_extensions(channels_dir: Path, provider_name: str):
        """扫描 Channel 扩展"""
        for channel_file in channels_dir.glob("*.py"):
            if channel_file.name.startswith("_"):
                continue
            module = import_module_from_path(channel_file)
            if hasattr(module, "ChannelHandler"):
                handler_class = module.ChannelHandler
                channel_type = getattr(handler_class, "channel_type", channel_file.stem)
                ChannelRegistry.register(channel_type, handler_class)
```

### 1.3 Provider 扩展示例

```python
# app/atlasclaw/providers/ldap/auth/ldap.py
from app.atlasclaw.auth.providers.base import AuthProvider

class LDAPAuth(AuthProvider):
    """LDAP 认证提供者"""
    
    auth_id = "ldap"  # 标识符
    auth_name = "LDAP"
    
    async def authenticate(self, credential: str) -> AuthResult:
        # LDAP 认证逻辑
        pass
    
    def provider_name(self) -> str:
        return "ldap"
```

```python
# app/atlasclaw/providers/feishu/channels/feishu.py
from app.atlasclaw.channels.handler import ChannelHandler

class FeishuHandler(ChannelHandler):
    """钉钉通道处理器"""
    
    channel_type = "feishu"
    channel_name = "Feishu"
    
    async def start(self, connection, context):
        # 启动飞书连接
        pass
    
    async def send_message(self, connection, outbound):
        # 发送飞书消息
        pass
    
    # ... 其他方法
```

## 2. Auth 扩展设计

### 2.1 当前实现回顾

当前 `app/atlasclaw/auth/providers/base.py`：

```python
class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, credential: str) -> AuthResult: ...
    
    @abstractmethod
    def provider_name(self) -> str: ...
```

### 2.2 扩展设计

保持当前简单设计，添加注册机制和 Provider 扫描：

```python
# app/atlasclaw/auth/registry.py
from typing import Type, Dict, Optional, List
from pathlib import Path

class AuthRegistry:
    """Auth 提供者注册表"""
    
    _providers: Dict[str, Type[AuthProvider]] = {}
    
    @classmethod
    def register(cls, provider_id: str, provider_class: Type[AuthProvider]):
        """注册 Auth 提供者"""
        cls._providers[provider_id] = provider_class
        
    @classmethod
    def get(cls, provider_id: str) -> Optional[Type[AuthProvider]]:
        """获取 Auth 提供者类"""
        return cls._providers.get(provider_id)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有已注册的提供者"""
        return list(cls._providers.keys())
    
    @classmethod
    def scan_providers(cls, providers_dir: Path):
        """扫描 providers 目录下的 auth 扩展"""
        for provider_path in providers_dir.iterdir():
            if not provider_path.is_dir():
                continue
            
            auth_dir = provider_path / "auth"
            if not auth_dir.exists():
                continue
            
            for auth_file in auth_dir.glob("*.py"):
                if auth_file.name.startswith("_"):
                    continue
                # 动态导入
                module = import_module_from_path(auth_file)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, AuthProvider) and 
                        attr is not AuthProvider and
                        hasattr(attr, "auth_id")):
                        cls.register(attr.auth_id, attr)
```

### 2.3 内置 Auth 类型

| 类型 | ID | 说明 | 位置 |
|------|-----|------|------|
| OIDC | `oidc` | OpenID Connect | 内置 |
| OAuth2 | `oauth2` | OAuth 2.0 | 内置 |
| API Key | `api_key` | 简单 API Key | 内置 |
| SAML | `saml` | SAML 2.0 | 内置 |
| None | `none` | 无认证（开发用）| 内置 |
| LDAP | `ldap` | LDAP 认证 | Provider 扩展 |
| AD | `ad` | Active Directory | Provider 扩展 |

### 2.4 Auth 配置（全局）

Auth 配置是**全局**的，对整个 workspace 生效，存储在 workspace 根目录的 `atlasclaw.json` 中：

```json
// <workspace>/atlasclaw.json
{
  "auth": {
    "provider": "oidc",
    "config": {
      "issuer_url": "https://auth.example.com",
      "client_id": "atlasclaw",
      "client_secret": "${OIDC_CLIENT_SECRET}"
    }
  }
}
```

**注意**：Auth 配置是 workspace 级别的，所有用户共享同一个认证配置。这与 Channel 配置不同，Channel 是按用户隔离的。

## 3. Channel 扩展设计

### 3.1 统一的 ChannelRegistry

使用**单一的 ChannelRegistry** 管理所有 Channel（内置和扩展）：

```python
# app/atlasclaw/channels/registry.py
from typing import Type, Dict, Optional, List, Any
from pathlib import Path
from enum import Enum

class ChannelMode(Enum):
    """Channel 工作模式"""
    INBOUND = "inbound"      # 仅接收（如 Webhook）
    OUTBOUND = "outbound"    # 仅发送（如 SMTP）
    BIDIRECTIONAL = "bidirectional"  # 双向（如 WebSocket）

class ChannelRegistry:
    """
    统一的 Channel 注册表
    
    管理所有类型的 Channel：
    - 内置 Channel：WebSocket、SSE、REST（由 AtlasClaw 主动监听）
    - 扩展 Channel：Feishu、Slack、WhatsApp（由 Driver 管理连接）
    """
    
    _handlers: Dict[str, Type[ChannelHandler]] = {}
    _instances: Dict[str, ChannelHandler] = {}  # channel_id -> handler instance
    _connections: Dict[str, ChannelConnection] = {}  # connection_id -> connection
    
    @classmethod
    def register(cls, channel_type: str, handler_class: Type[ChannelHandler]):
        """
        注册 Channel Handler
        
        Args:
            channel_type: Channel 类型标识，如 'feishu', 'slack', 'websocket'
            handler_class: ChannelHandler 子类
        """
        cls._handlers[channel_type] = handler_class
        
    @classmethod
    def get(cls, channel_type: str) -> Optional[Type[ChannelHandler]]:
        """获取 Handler 类"""
        return cls._handlers.get(channel_type)
    
    @classmethod
    def list_channels(cls) -> List[str]:
        """列出所有已注册的 Channel 类型"""
        return list(cls._handlers.keys())
    
    @classmethod
    def create_instance(
        cls,
        channel_id: str,
        channel_type: str,
        config: Dict[str, Any]
    ) -> Optional[ChannelHandler]:
        """
        创建 Channel Handler 实例
        
        对于内置 Channel（WebSocket/SSE/REST），创建实例并注册
        对于扩展 Channel，通常由 Connection 管理
        """
        handler_class = cls._handlers.get(channel_type)
        if not handler_class:
            return None
        
        instance = handler_class(config)
        cls._instances[channel_id] = instance
        return instance
    
    @classmethod
    def get_instance(cls, channel_id: str) -> Optional[ChannelHandler]:
        """获取已创建的 Handler 实例"""
        return cls._instances.get(channel_id)
    
    @classmethod
    def scan_providers(cls, providers_dir: Path):
        """扫描 providers 目录下的 channels 扩展"""
        for provider_path in providers_dir.iterdir():
            if not provider_path.is_dir():
                continue
            
            channels_dir = provider_path / "channels"
            if not channels_dir.exists():
                continue
            
            for channel_file in channels_dir.glob("*.py"):
                if channel_file.name.startswith("_"):
                    continue
                # 动态导入
                module = import_module_from_path(channel_file)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ChannelHandler) and 
                        attr is not ChannelHandler and
                        hasattr(attr, "channel_type")):
                        cls.register(attr.channel_type, attr)
```

### 3.2 ChannelHandler 接口

统一的 ChannelHandler 接口，适用于内置和扩展 Channel：

```python
# app/atlasclaw/channels/handler.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum

class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class ChannelHandler(ABC):
    """
    Channel 处理器基类
    
    统一处理所有 Channel 类型：
    - 内置 Channel（WebSocket/SSE/REST）：AtlasClaw 主动监听连接
    - 扩展 Channel（Feishu/Slack）：连接到外部平台
    """
    
    channel_type: str = ""      # 类型标识，如 'feishu', 'websocket'
    channel_name: str = ""      # 显示名称
    channel_icon: str = ""      # 图标
    channel_mode: ChannelMode = ChannelMode.BIDIRECTIONAL  # 工作模式
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._status = ConnectionStatus.DISCONNECTED
        self._connection_id: Optional[str] = None
    
    # ========== 配置管理 ==========
    
    def validate_config(self, config: Dict[str, Any]) -> ChannelValidationResult:
        """
        验证配置（可选）
        
        对于需要用户配置的 Channel（如 Feishu），验证配置有效性
        对于内置 Channel，通常无需验证
        """
        return ChannelValidationResult(valid=True)
    
    def describe_schema(self) -> Optional[Dict[str, Any]]:
        """
        返回配置表单 schema（可选）
        
        用于前端渲染配置界面
        """
        return None
    
    # ========== 生命周期管理 ==========
    
    @abstractmethod
    async def setup(self, connection_config: Dict[str, Any]) -> bool:
        """
        初始化配置
        
        - 验证凭据（Token、Key 等）
        - 初始化 API 客户端
        - 获取平台信息
        """
        pass
    
    @abstractmethod
    async def start(self, context: Any) -> bool:
        """
        启动 Channel
        
        内置 Channel：启动服务器监听（WebSocket/SSE/HTTP）
        扩展 Channel：建立到平台的连接（Webhook/WebSocket/轮询）
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """停止 Channel，清理资源"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        return self._status == ConnectionStatus.CONNECTED
    
    def get_status(self) -> ConnectionStatus:
        """获取当前状态"""
        return self._status
    
    # ========== 消息接收（平台 -> AtlasClaw）==========
    
    @abstractmethod
    async def handle_inbound(
        self, 
        request: Any
    ) -> Optional[InboundMessage]:
        """
        处理入站消息
        
        内置 Channel：处理客户端连接请求
        扩展 Channel：处理平台 Webhook/消息推送
        
        Args:
            request: 请求对象（FastAPI Request 或连接对象）
            
        Returns:
            InboundMessage if valid message
        """
        pass
    
    # ========== 消息发送（AtlasClaw -> 平台）==========
    
    @abstractmethod
    async def send_message(
        self,
        outbound: OutboundMessage
    ) -> SendResult:
        """
        发送消息
        
        内置 Channel：通过 WebSocket/SSE 发送给客户端
        扩展 Channel：调用平台 API 发送
        """
        pass
    
    async def send_typing_indicator(
        self,
        chat_id: str,
        duration: float = 5.0
    ) -> bool:
        """发送输入指示器"""
        return False
    
    # ========== 能力查询 ==========
    
    def supports_typing(self) -> bool:
        return False
    
    def supports_media(self) -> bool:
        return False
    
    def supports_thread(self) -> bool:
        return False
```

### 3.3 内置 Channel 实现

```python
# app/atlasclaw/channels/handlers/websocket.py
class WebSocketHandler(ChannelHandler):
    """WebSocket Channel - 内置"""
    
    channel_type = "websocket"
    channel_name = "WebSocket"
    channel_mode = ChannelMode.BIDIRECTIONAL
    
    async def setup(self, config: Dict[str, Any]) -> bool:
        # WebSocket 无需特殊配置
        return True
    
    async def start(self, context: Any) -> bool:
        # 启动 WebSocket 服务器，等待客户端连接
        # 在 FastAPI 中注册 WebSocket 路由
        self._status = ConnectionStatus.CONNECTED
        return True
    
    async def handle_inbound(
        self, 
        websocket: WebSocket
    ) -> Optional[InboundMessage]:
        # 处理客户端 WebSocket 连接
        # 接收消息并转换为 InboundMessage
        data = await websocket.receive_json()
        return InboundMessage(
            message_id=data["id"],
            sender_id=data["user_id"],
            chat_id=data["session_id"],
            content=data["message"],
            channel_type=self.channel_type,
        )
    
    async def send_message(
        self,
        outbound: OutboundMessage
    ) -> SendResult:
        # 通过 WebSocket 发送给客户端
        # ...
        pass
```

### 3.4 扩展 Channel 实现

```python
# app/atlasclaw/providers/feishu/channels/feishu.py
class FeishuHandler(ChannelHandler):
    """飞书 Channel - 扩展"""
    
    channel_type = "feishu"
    channel_name = "Feishu"
    channel_icon = "feishu"
    channel_mode = ChannelMode.BIDIRECTIONAL
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._api: Optional[FeishuAPI] = None
    
    async def setup(self, connection_config: Dict[str, Any]) -> bool:
        """验证飞书配置"""
        app_id = connection_config.get("app_id")
        app_secret = connection_config.get("app_secret")
        
        # 验证 Token 有效性
        self._api = FeishuAPI(app_id, app_secret)
        return await self._api.validate_credentials()
    
    async def start(self, context: Any) -> bool:
        """
        启动飞书 Channel
        
        Webhook 模式：无需主动启动，等待平台推送
        WebSocket 模式：建立长连接
        """
        # 如果是 WebSocket 模式，建立连接
        if self.config.get("mode") == "websocket":
            await self._api.connect_websocket()
        
        self._status = ConnectionStatus.CONNECTED
        return True
    
    async def handle_inbound(
        self, 
        request: Request
    ) -> Optional[InboundMessage]:
        """处理飞书 Webhook"""
        # 1. 验证签名
        signature = request.headers.get("X-Signature")
        body = await request.body()
        if not self._verify_signature(body, signature):
            return None
        
        # 2. 解析消息
        data = await request.json()
        
        # 3. 转换为统一格式
        return InboundMessage(
            message_id=data["message"]["message_id"],
            sender_id=data["sender"]["sender_id"]["open_id"],
            sender_name=data["sender"]["nickname"],
            chat_id=data["chat_id"],
            content=data["message"]["content"]["text"],
            channel_type=self.channel_type,
        )
    
    async def send_message(
        self,
        outbound: OutboundMessage
    ) -> SendResult:
        """发送飞书消息"""
        # 转换格式并调用飞书 API
        result = await self._api.send_message(
            chat_id=outbound.chat_id,
            content=self._format_content(outbound)
        )
        return SendResult(
            success=result.success,
            message_id=result.message_id,
        )
```

### 3.5 内置 Channel 类型

| 类型 | ID | 传输方式 | 位置 | 说明 |
|------|-----|---------|------|------|
| WebSocket | `websocket` | WebSocket | 内置 | 浏览器/客户端连接 |
| SSE | `sse` | SSE | 内置 | 服务器推送 |
| REST | `rest` | HTTP | 内置 | 回调接口 |
| Feishu | `feishu` | Webhook/WebSocket | Provider 扩展 | 飞书机器人 |
| Slack | `slack` | Webhook/Socket | Provider 扩展 | Slack 集成 |
| WhatsApp | `whatsapp` | WebSocket | Provider 扩展 | WhatsApp Business |
| DingTalk | `dingtalk` | Webhook | Provider 扩展 | 钉钉机器人 |

### 3.6 用户 Channel 配置存储

Channel 配置按用户隔离，存储在 workspace 的用户目录下：

```
<workspace>/
└── users/
    └── <user_id>/
        └── channels/
            ├── feishu.json       # 用户飞书连接配置
            └── slack.json        # 用户 Slack 连接配置
```

```json
// feishu.json
{
  "version": 1,
  "channel_type": "feishu",
  "updated_at": "2026-03-11T12:00:00Z",
  "connections": [
    {
      "id": "feishu_conn_001",
      "name": "工作机器人",
      "enabled": true,
      "is_default": true,
      "config": {
        "app_id": "cli_xxx",
        "app_secret": "enc:xxxx",
        "verification_token": "enc:xxxx"
      },
      "runtime_state": {
        "status": "connected",
        "last_seen_at": "2026-03-11T12:00:00Z"
      }
    }
  ]
}
```

**注意**：Channel 配置与 Auth 配置不同，Channel 是按用户隔离的，每个用户可以有自己的 Channel 连接配置。

## 4. Skills（已实现）

`SkillRegistry` 已完全实现，支持：

- 可执行技能注册和执行
- Markdown 技能加载（SKILL.md）
- 从 providers 目录自动扫描
- 优先级管理（workspace > user > built-in）

```python
# 已实现的扫描方式（main.py 中）
providers_dir = Path(__file__).parent / "providers"
if providers_dir.exists():
    for provider_path in providers_dir.iterdir():
        if provider_path.is_dir():
            provider_skills = provider_path / "skills"
            if provider_skills.exists():
                _skill_registry.load_from_directory(str(provider_skills), location="built-in")
```

## 5. 启动时的统一扫描

```python
# main.py 启动流程
def load_extensions():
    """加载所有扩展"""
    providers_dir = Path(__file__).parent / "providers"
    
    # 1. 扫描 Auth 扩展
    AuthRegistry.scan_providers(providers_dir)
    
    # 2. 扫描 Channel 扩展（统一注册到 ChannelRegistry）
    ChannelRegistry.scan_providers(providers_dir)
    
    # 3. 注册内置 Channel
    ChannelRegistry.register("websocket", WebSocketHandler)
    ChannelRegistry.register("sse", SSEHandler)
    ChannelRegistry.register("rest", RESTHandler)
    
    # 4. 扫描 Skills 扩展（已存在）
    for provider_path in providers_dir.iterdir():
        if provider_path.is_dir():
            provider_skills = provider_path / "skills"
            if provider_skills.exists():
                _skill_registry.load_from_directory(str(provider_skills), location="built-in")
```

## 6. 与现有组件的关系

### 6.1 配置存储对比

| 特性 | Service Providers | Channel Integrations | Auth Providers |
|------|-------------------|---------------------|----------------|
| 用途 | 企业系统能力 | 消息通道 | 身份认证 |
| **配置位置** | `<workspace>/atlasclaw.json` | `<workspace>/users/<user_id>/channels/` | `<workspace>/atlasclaw.json` |
| **作用范围** | Workspace 全局 | 用户隔离 | Workspace 全局 |
| 生命周期 | 应用级单例 | 用户级多实例 | 请求级 |
| 扩展位置 | `providers/<name>/` | `providers/<name>/channels/` | `providers/<name>/auth/` |
| 加载方式 | 配置实例化 | Handler 注册 + 扫描 | Provider 注册 + 扫描 |

### 6.2 Channel 工作流程

#### 6.2.1 当前 Channel 架构（已存在）

当前 AtlasClaw 已经实现了基础的 Channel 系统：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         当前 Channel 架构                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐ │
│  │  WebSocket       │     │  SSE             │     │  REST           │ │
│  │  Handler         │     │  Handler         │     │  Handler        │ │
│  │                  │     │                  │     │                 │ │
│  │ • 浏览器连接      │     │ • 服务器推送      │     │ • HTTP 回调     │ │
│  │ • 实时双向通信    │     │ • 单向流         │     │ • Webhook 接收  │ │
│  └────────┬─────────┘     └────────┬─────────┘     └────────┬────────┘ │
│           │                        │                        │          │
│           └────────────────────────┼────────────────────────┘          │
│                                    │                                   │
│                                    ▼                                   │
│                         ┌─────────────────────┐                        │
│                         │ ChannelRegistry     │                        │
│                         │                     │                        │
│                         │ • register()        │                        │
│                         │ • get()             │                        │
│                         │ • create_instance() │                        │
│                         └──────────┬──────────┘                        │
│                                    │                                   │
│                                    ▼                                   │
│                         ┌─────────────────────┐                        │
│                         │ Session Manager     │                        │
│                         │                     │                        │
│                         │ • 会话创建/恢复      │                        │
│                         │ • 消息路由           │                        │
│                         └──────────┬──────────┘                        │
│                                    │                                   │
│                                    ▼                                   │
│                         ┌─────────────────────┐                        │
│                         │ Agent Runner        │                        │
│                         │ + Skills            │                        │
│                         └─────────────────────┘                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**当前 Channel 注册位置：**
- `app/atlasclaw/channels/registry.py` - `ChannelRegistry`（统一注册表）
- 内置 Handler：WebSocket、SSE、REST
- 在 `main.py` 中注册到 Registry

**当前工作流程：**
1. 客户端通过 WebSocket/SSE/REST 连接到 AtlasClaw
2. `ChannelHandler` 接收消息，转换为 `InboundMessage`
3. `SessionManager` 根据 `session_key` 路由到对应会话
4. `AgentRunner` 处理消息，调用 Skills
5. 响应通过同一个 `ChannelHandler` 返回给客户端

#### 6.2.2 详细消息交互流程

**外部 Channel 完整交互流程（以 Feishu 为例）：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     消息接收流程（平台 -> AtlasClaw）                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 用户发送消息                                                             │
│     ┌─────────┐                                                             │
│     │  用户   │───在 Feishu 群聊中 @机器人发送消息                            │
│     └────┬────┘                                                             │
│          │                                                                  │
│  2. 平台推送消息                                                             │
│          ▼                                                                  │
│     ┌─────────────┐                                                         │
│     │  Feishu     │───检测到消息，推送到配置的 Webhook URL                    │
│     │  服务器     │    POST /api/channel-hooks/feishu/conn_001               │
│     └──────┬──────┘                                                         │
│            │                                                                │
│  3. AtlasClaw 接收消息                                                       │
│            ▼                                                                │
│     ┌─────────────────┐                                                     │
│     │  FastAPI        │───接收 HTTP 请求                                     │
│     │  Webhook Route  │    /api/channel-hooks/{type}/{connection_id}        │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  4. Handler 处理消息                                                         │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  FeishuHandler  │───handle_inbound() 被调用                            │
│     │                 │                                                     │
│     │  4.1 验证签名    │───验证 X-Signature 防止伪造                          │
│     │  4.2 解析消息    │───解析 JSON payload                                  │
│     │  4.3 格式转换    │───转换为 InboundMessage                              │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  5. 消息路由到 Agent                                                         │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  ChannelManager │───路由消息到对应 Session                              │
│     │                 │                                                     │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  6. 创建/获取会话                                                            │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  Session        │───根据 (channel_type, chat_id, user_id) 获取 Session │
│     │  Manager        │    如果不存在则创建新会话                              │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  7. Agent 处理消息                                                           │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  Request        │───构建请求上下文                                      │
│     │  Orchestrator   │    (message, session, user_context)                  │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  8. 执行 Skills                                                              │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  Agent Runner   │───调用 LLM，执行 Skills                              │
│     │  + Skills       │    生成回复内容                                       │
│     └────────┬────────┘                                                     │
│              │                                                              │
└──────────────┼──────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     消息发送流程（AtlasClaw -> 平台）                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  9. 准备发送回复                                                             │
│     ┌─────────────────┐                                                     │
│     │  OutboundMessage│───包含回复内容、chat_id、格式信息等                   │
│     │  (reply)        │                                                     │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  10. Handler 发送消息                                                        │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  FeishuHandler  │───send_message() 被调用                              │
│     │                 │                                                     │
│     │  10.1 格式转换   │───将 Markdown 转为 Feishu 富文本                     │
│     │  10.2 调用 API   │───POST /open-apis/message/v4/send/                  │
│     │  10.3 处理响应   │───获取 message_id，记录发送状态                       │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  11. 返回结果                                                                │
│              ▼                                                              │
│     ┌─────────────────┐                                                     │
│     │  SendResult     │───success=True, message_id=xxx                       │
│     │                 │───更新消息状态为 SENT                                │
│     └────────┬────────┘                                                     │
│              │                                                              │
│  12. 用户在平台看到回复                                                       │
│              ▼                                                              │
│     ┌─────────┐                                                             │
│     │  用户   │───在 Feishu 中看到机器人的回复                                 │
│     └─────────┘                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**关键交互点说明：**

| 阶段 | 组件 | 职责 |
|------|------|------|
| **接收** | FeishuHandler.handle_inbound() | 验证签名、解析消息、格式转换 |
| **路由** | ChannelManager | 将消息路由到正确的 Session |
| **处理** | RequestOrchestrator + AgentRunner | 业务逻辑处理、Skills 执行 |
| **发送** | FeishuHandler.send_message() | 格式转换、调用平台 API |

**消息格式转换示例：**

```python
# Feishu 消息格式 -> InboundMessage
{
    "message_id": "om_123456",
    "sender": {"sender_id": {"open_id": "ou_xxx"}, "nickname": "张三"},
    "chat_id": "oc_xxx",
    "message_type": "text",
    "content": {"text": "@机器人 你好"},
    "create_time": "1234567890"
}
↓ 转换
InboundMessage(
    message_id="om_123456",
    sender_id="ou_xxx",
    sender_name="张三",
    chat_id="oc_xxx",
    content="@机器人 你好",
    channel_type="feishu",
    connection_id="feishu_conn_001",
)

# OutboundMessage -> Feishu 消息格式
OutboundMessage(
    content="你好！有什么可以帮助你的？",
    chat_id="oc_xxx",
    format="markdown"
)
↓ 转换
{
    "chat_id": "oc_xxx",
    "msg_type": "interactive",
    "card": {
        "elements": [{"tag": "div", "text": {"content": "你好！有什么可以帮助你的？"}}]
    }
}
```

#### 6.2.3 关键区别

| 特性 | 内置 Channel | 扩展 Channel |
|------|-------------|-------------|
| **连接发起方** | AtlasClaw（等待客户端连接）| 外部系统（主动连接）|
| **配置位置** | `atlasclaw.json` | `<workspace>/users/<user_id>/channels/` |
| **管理方式** | `ChannelRegistry` 统一管理 | `ChannelRegistry` 统一管理 |
| **生命周期** | 连接即创建 | 显式配置后启动/停止 |
| **用户隔离** | 会话级 | 配置级（每个用户独立配置）|

## 7. API 设计

### 7.1 Channel 配置 API

```
GET    /api/channels                    # 列出支持的通道类型
GET    /api/channels/{type}/schema      # 获取配置表单 schema
GET    /api/channels/{type}/connections # 列出用户的连接
POST   /api/channels/{type}/connections # 创建连接
GET    /api/channels/{type}/connections/{id}
PATCH  /api/channels/{type}/connections/{id}
DELETE /api/channels/{type}/connections/{id}
POST   /api/channels/{type}/connections/{id}/verify
POST   /api/channels/{type}/connections/{id}/enable
POST   /api/channels/{type}/connections/{id}/disable
```

### 7.2 Channel Webhook API

```
POST /api/channel-hooks/{channel_type}/{connection_id}
```

独立于现有的 `webhook_dispatch.py`（用于 Skills）。

## 8. 实现建议

### 8.1 目录结构

#### 代码目录

```
app/atlasclaw/
├── auth/
│   ├── providers/
│   │   ├── base.py          # AuthProvider ABC
│   │   ├── oidc.py          # 内置 OIDC
│   │   ├── oauth2.py        # 内置 OAuth2
│   │   └── api_key.py       # 内置 API Key
│   └── registry.py          # AuthRegistry + 扫描
│
├── channels/
│   ├── handler.py           # ChannelHandler ABC（统一接口）
│   ├── registry.py          # ChannelRegistry（统一注册表）
│   ├── manager.py           # ChannelManager（连接管理）
│   └── handlers/            # 内置 Handler 实现
│       ├── __init__.py
│       ├── websocket.py     # WebSocket Handler
│       ├── sse.py           # SSE Handler
│       └── rest.py          # REST Handler
│
├── providers/               # Provider 扩展目录
│   ├── jira/                # Jira Provider
│   │   ├── __init__.py
│   │   ├── skills/          # Jira Skills
│   │   └── ...
│   ├── feishu/              # Feishu Provider (扩展)
│   │   ├── __init__.py
│   │   ├── channels/
│   │   │   └── feishu.py    # Feishu Handler
│   │   └── skills/
│   ├── slack/               # Slack Provider (扩展)
│   │   ├── channels/
│   │   │   └── slack.py
│   │   └── skills/
│   └── ldap/                # LDAP Provider (扩展)
│       └── auth/
│           └── ldap.py      # LDAP AuthProvider
│
└── skills/
    └── registry.py          # SkillRegistry (已存在)
```

#### Workspace 目录结构

```
<workspace>/
├── atlasclaw.json           # 全局配置（Auth、Service Providers）
├── .atlasclaw/              # 系统目录
│   ├── agents/              # Agent 定义
│   ├── providers/           # Provider 配置
│   └── channels/            # Channel 配置（代码）
│
└── users/                   # 用户目录
    └── <user_id>/           # 用户隔离数据
        ├── atlasclaw.json   # 用户配置
        ├── sessions/        # 会话数据
        ├── memory/          # 长期记忆
        └── channels/        # Channel 配置（用户隔离）
            ├── feishu.json
            └── slack.json
```

**配置存储规则：**
- **Auth**: `<workspace>/atlasclaw.json` - 全局，所有用户共享
- **Channel**: `<workspace>/users/<user_id>/channels/*.json` - 用户隔离
- **Service Providers**: `<workspace>/atlasclaw.json` - 全局

### 8.2 实现优先级

1. **Phase 1**: Auth Registry + Provider 扫描机制
2. **Phase 2**: ChannelRegistry（统一注册表）+ ChannelHandler 接口
3. **Phase 3**: 内置 Channel 迁移到 ChannelHandler
4. **Phase 4**: Channel Manager + Store + REST API
5. **Phase 5**: Feishu Handler（作为 Provider 扩展）
6. **Phase 6**: Slack/WhatsApp Handlers

## 9. 与 OpenClaw 的对比

| 特性 | OpenClaw | AtlasClaw (本设计) |
|------|----------|-------------------|
| 插件架构 | 统一 Plugin 系统 | 分离的 Registry + Provider 扫描 |
| Channel | `ChannelPlugin` 继承 | `ChannelHandler` 统一接口 |
| Registry | 多个（AdapterRegistry + PluginRegistry）| **单一 ChannelRegistry** |
| Auth | `AuthAdapter` 继承 | `AuthProvider` + Provider 扫描 |
| Skills | SDK 注册 | 目录扫描 (已实现) |
| 发现机制 | 目录扫描 + SDK | 统一的 Provider 目录扫描 |
| 用户隔离 | 无 | Channel 配置用户隔离 |
| 配置存储 | 全局 | Auth/Provider 全局, Channel 用户目录 |

## 10. 优势

1. **单一 Registry**：使用一个 ChannelRegistry 管理所有 Channel，简化架构
2. **统一接口**：内置和扩展 Channel 使用相同的 ChannelHandler 接口
3. **简单**：无统一 Plugin 抽象，各组件保持独立接口
4. **灵活**：Auth 简单函数式，Channel 统一接口，Skills 保持现有实现
5. **可扩展**：Provider 目录下即可扩展 auth/channels/skills
6. **向后兼容**：Skills 已实现的扫描机制保持不变

---

*本设计基于当前 AtlasClaw 实现，废弃了统一 Plugin 架构，采用统一的 Provider 目录扫描机制和单一的 ChannelRegistry。*
