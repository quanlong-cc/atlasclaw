# AtlasClaw-Core Code Structure

## Directory Tree

```
AtlasClaw-Core/
├── app/
│   ├── frontend/                    # Web UI (DeepChat-based)
│   │   ├── index.html              # Main entry point
│   │   ├── scripts/                # JavaScript modules
│   │   │   ├── api-client.js       # API client
│   │   │   ├── session-manager.js  # Session management
│   │   │   ├── message-handler.js  # Message handling
│   │   │   └── ui-components.js    # UI components
│   │   ├── styles/                 # CSS styles
│   │   ├── locales/                # i18n translations
│   │   └── static/                 # Static assets
│   │
│   └── atlasclaw/                    # Core backend
│       ├── __init__.py
│       ├── main.py                 # FastAPI application entry
│       │
│       ├── agent/                  # Agent Engine
│       │   ├── __init__.py
│       │   ├── runner.py           # Agent execution engine
│       │   ├── routing.py          # Multi-agent routing
│       │   ├── prompt_builder.py   # System prompt builder
│       │   ├── stream.py           # Streaming events & chunking
│       │   └── compaction.py       # Context compaction
│       │
│       ├── api/                    # API Layer
│       │   ├── __init__.py
│       │   ├── routes.py           # REST API routes
│       │   ├── gateway.py          # WebSocket gateway
│       │   ├── sse.py              # SSE manager
│       │   ├── websocket.py        # WebSocket handler
│       │   └── request_orchestrator.py
│       │
│       ├── auth/                   # Authentication System
│       │   ├── __init__.py
│       │   ├── middleware.py       # Auth middleware
│       │   ├── strategy.py         # Auth strategy
│       │   ├── models.py           # User models
│       │   ├── config.py           # Auth configuration
│       │   ├── shadow_store.py     # Shadow user store
│       │   └── providers/          # Auth providers
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── none.py
│       │       ├── api_key.py
│       │       ├── oidc.py
│       │       └── smartcmp.py
│       │
│       ├── channels/               # Channel Adapters
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── rest_adapter.py
│       │   ├── sse_adapter.py
│       │   └── websocket_adapter.py
│       │
│       ├── core/                   # Core Infrastructure
│       │   ├── __init__.py
│       │   ├── config.py           # Configuration manager
│       │   ├── config_schema.py    # Pydantic config schemas
│       │   ├── deps.py             # Skill dependency injection
│       │   ├── execution_context.py
│       │   ├── provider_registry.py
│       │   └── tenant.py
│       │
│       ├── hooks/                  # Hook System
│       │   └── system.py
│       │
│       ├── media/                  # Media Processing
│       │   ├── link_extractor.py
│       │   ├── tts.py
│       │   └── understanding.py
│       │
│       ├── memory/                 # Memory System
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   └── search.py
│       │
│       ├── messages/               # Message Processing
│       │   ├── command.py
│       │   └── handler.py
│       │
│       ├── models/                 # Model Management
│       │   ├── __init__.py
│       │   ├── providers.py
│       │   ├── retry.py
│       │   └── failover.py
│       │
│       ├── providers/              # Built-in Providers
│       │   └── jira/               # Jira Provider Example
│       │       ├── skills/
│       │       │   └── jira-issue/
│       │       │       ├── SKILL.md
│       │       │       └── scripts/
│       │       └── scripts/
│       │
│       ├── session/                # Session Management
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   ├── context.py
│       │   └── queue.py
│       │
│       ├── skills/                 # Skills System
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   └── frontmatter.py
│       │
│       ├── tools/                  # Built-in Tools
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── catalog.py
│       │   ├── registration.py
│       │   ├── filesystem/         # File system tools
│       │   ├── memory/             # Memory tools
│       │   ├── providers/          # Provider tools
│       │   ├── runtime/            # Runtime tools
│       │   ├── sessions/           # Session tools
│       │   ├── ui/                 # UI tools
│       │   └── web/                # Web tools
│       │
│       └── workflow/               # Workflow Engine
│           ├── __init__.py
│           ├── engine.py
│           └── orchestrator.py
│
├── tests/                          # Test Suite
│   ├── conftest.py                 # pytest configuration
│   ├── atlasclaw.test.json           # Test configuration
│   ├── atlasclaw/                    # Python tests
│   │   ├── test_core.py
│   │   ├── test_agent.py
│   │   ├── test_agent_integration.py
│   │   ├── test_e2e_api.py
│   │   ├── auth/
│   │   ├── memory/
│   │   ├── session/
│   │   └── providers/
│   └── frontend/                   # Frontend tests
│
├── docs/                           # Documentation
│   ├── PROJECT_OVERVIEW.md
│   ├── CODING_STANDARDS.md
│   ├── CODE_STRUCTURE.md
│   └── images/architecture/
│
├── openspec/                       # OpenSpec Specifications
│   ├── AGENTS.md
│   ├── project.md
│   ├── changes/
│   └── completed/
│
├── atlasclaw.json                    # Main configuration
└── requirements.txt                # Python dependencies
```

## Module Dependencies

### Core Dependencies

```
main.py
├── agent/runner.py
│   ├── core/deps.py
│   ├── session/manager.py
│   └── skills/registry.py
├── api/routes.py
│   ├── agent/runner.py
│   ├── auth/middleware.py
│   └── session/manager.py
├── auth/middleware.py
│   └── auth/strategy.py
├── core/config.py
│   └── core/config_schema.py
└── skills/registry.py
    └── tools/registration.py
```

### Data Flow

```
User Request
    ↓
API Layer (routes.py)
    ↓
Auth Middleware
    ↓
Agent Runner
    ↓
Skill Execution
    ↓
Provider API
    ↓
Response Stream (SSE)
```

## Key Files

### Entry Points

| File | Purpose |
|------|---------|
| `app/atlasclaw/main.py` | FastAPI application entry |
| `app/frontend/index.html` | Web UI entry |

### Configuration

| File | Purpose |
|------|---------|
| `atlasclaw.json` | Main configuration file |
| `tests/atlasclaw.test.json` | Test configuration |
| `app/atlasclaw/core/config_schema.py` | Configuration schemas |

### Core Logic

| File | Purpose |
|------|---------|
| `app/atlasclaw/agent/runner.py` | Agent execution engine |
| `app/atlasclaw/skills/registry.py` | Skills registration |
| `app/atlasclaw/session/manager.py` | Session management |
| `app/atlasclaw/memory/manager.py` | Memory management |

### API

| File | Purpose |
|------|---------|
| `app/atlasclaw/api/routes.py` | REST API routes |
| `app/atlasclaw/api/sse.py` | SSE streaming |
| `app/atlasclaw/api/websocket.py` | WebSocket handler |

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Modules | `snake_case.py` | `runner.py` |
| Classes | `PascalCase` | `AgentRunner` |
| Functions | `snake_case` | `run_agent` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY` |
| Tests | `test_*.py` | `test_runner.py` |
| Test Classes | `Test*` | `TestAgentRunner` |
| Test Methods | `test_*` | `test_run` |

## Import Patterns

### Standard Pattern

```python
# Standard library
import asyncio
from pathlib import Path
from typing import Any

# Third-party
import httpx
from pydantic import BaseModel

# Local application
from app.atlasclaw.core.config import get_config
from app.atlasclaw.session.manager import SessionManager
```

### Relative Imports

```python
# Within a package
from .base import BaseTool
from ..core.config import get_config
```

## Extension Points

### Adding a New Provider

1. Create directory: `app/atlasclaw/providers/<name>/`
2. Add `PROVIDER.md` documentation
3. Create skills in `skills/<skill-name>/`
4. Register in configuration

### Adding a New Skill

1. Create directory: `skills/<skill-name>/`
2. Add `SKILL.md` with metadata
3. Add `scripts/handler.py` with `SKILL_METADATA` and `handler`
4. Skill auto-discovered on startup

### Adding a New Tool

1. Add tool definition in `tools/catalog.py`
2. Implement tool in appropriate subdirectory
3. Register in `tools/registration.py`

## Data Storage

### Session Storage

```
~/.atlasclaw/agents/<agent_id>/sessions/<user_id>/
├── sessions.json
├── <session_id>.jsonl
└── archive/
```

### Memory Storage

```
~/.atlasclaw/agents/<agent_id>/memory/
├── vector/
└── fulltext/
```

### Configuration Storage

```
~/.atlasclaw/
├── config.json
└── workspace/
```
