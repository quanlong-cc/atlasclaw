# -*- coding: utf-8 -*-
"""
FastAPI application entry point for AtlasClaw.

This module creates and configures the FastAPI application, including:
- Static file serving for the frontend
- API routes for session management and agent execution
- CORS middleware for development
- Health check endpoint

Usage:
    uvicorn app.atlasclaw.main:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.atlasclaw.api.routes import create_router, APIContext, install_request_validation_logging, set_api_context
from app.atlasclaw.api.webhook_dispatch import WebhookDispatchManager
from app.atlasclaw.session.manager import SessionManager
from app.atlasclaw.session.queue import SessionQueue
from app.atlasclaw.skills.registry import SkillRegistry
from app.atlasclaw.tools.registration import register_builtin_tools
from app.atlasclaw.tools.catalog import ToolProfile
from app.atlasclaw.agent.runner import AgentRunner
from app.atlasclaw.agent.prompt_builder import PromptBuilder, PromptBuilderConfig
from app.atlasclaw.core.config import get_config, get_config_path
from app.atlasclaw.core.provider_registry import ServiceProviderRegistry


_global_provider_registry: Optional[ServiceProviderRegistry] = None


# Global context components
_session_manager: Optional[SessionManager] = None
_session_queue: Optional[SessionQueue] = None
_skill_registry: Optional[SkillRegistry] = None
_agent_runner: Optional[AgentRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _session_manager, _session_queue, _skill_registry, _agent_runner, _global_provider_registry
    
    config = get_config()
    config_root = get_config_path().parent if get_config_path() is not None else Path.cwd()
    
    _session_manager = SessionManager(agents_dir=config.agents_dir)
    _session_queue = SessionQueue()
    _skill_registry = SkillRegistry()
    
    _global_provider_registry = ServiceProviderRegistry()
    if config.service_providers:
        _global_provider_registry.load_instances_from_config(config.service_providers)
    
    available_providers = {}
    provider_instances = _global_provider_registry.get_all_instance_configs()
    for provider_type in _global_provider_registry.list_providers():
        instances = _global_provider_registry.list_instances(provider_type)
        if instances:
            available_providers[provider_type] = instances
    
    # Register built-in tools (exec, read, write, web_search, etc.)
    registered_tools = register_builtin_tools(_skill_registry, profile=ToolProfile.FULL)
    print(f"[AtlasClaw] Registered {len(registered_tools)} built-in tools")
    
    # Load skills from built-in providers, workspace, and user directories
    # 1. Built-in provider skills (bundled with application)
    providers_dir = Path(__file__).parent / "providers"
    if providers_dir.exists():
        for provider_path in providers_dir.iterdir():
            if provider_path.is_dir():
                provider_skills = provider_path / "skills"
                if provider_skills.exists():
                    _skill_registry.load_from_directory(str(provider_skills), location="built-in")

    # 1b. Additional webhook skill roots (provider-qualified markdown skills)
    if config.webhook.enabled and config.webhook.skill_sources:
        for source in config.webhook.skill_sources:
            source_root = (config_root / source.root).resolve()
            if source_root.exists():
                _skill_registry.load_from_directory(
                    str(source_root),
                    location="external",
                    provider=source.provider,
                )
    
    # 2. Workspace skills (project-specific, highest priority)
    workspace_skills = Path.cwd() / "skills"
    if workspace_skills.exists():
        _skill_registry.load_from_directory(str(workspace_skills), location="workspace")
    
    # 3. User skills (personal overrides)
    user_skills = Path.home() / ".atlasclaw" / "skills"
    if user_skills.exists():
        _skill_registry.load_from_directory(str(user_skills), location="user")

    model_name = config.model.primary
    
    # Resolve model provider config from atlasclaw.json
    if "/" in model_name:
        provider, model = model_name.split("/", 1)
    else:
        provider, model = "openai", model_name
    
    provider_config = config.model.providers.get(provider, {})
    if not provider_config:
        raise RuntimeError(
            f"Provider '{provider}' not configured in atlasclaw.json. "
            f"Please add provider config under model.providers.{provider}"
        )
    
    import os
    base_url = provider_config.get("base_url", "")
    api_key = provider_config.get("api_key", "")
    api_type = provider_config.get("api_type", "openai")
    
    # Expand environment variables in config (e.g., "${ANTHROPIC_BASE_URL}")
    if base_url.startswith("${") and base_url.endswith("}"):
        env_var = base_url[2:-1]
        base_url = os.environ.get(env_var, "")
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")
    
    # Validate credentials
    if not base_url:
        raise RuntimeError(
            f"Missing base_url for provider '{provider}'. "
            f"Set environment variable or configure in atlasclaw.json"
        )
    if not api_key:
        raise RuntimeError(
            f"Missing api_key for provider '{provider}'. "
            f"Set environment variable or configure in atlasclaw.json"
        )
    
    # Set environment variables based on api_type
    if api_type == "anthropic":
        os.environ["ANTHROPIC_BASE_URL"] = base_url
        os.environ["ANTHROPIC_API_KEY"] = api_key
        pydantic_model = f"anthropic:{model}"
    else:
        # Default to OpenAI-compatible API
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["OPENAI_API_KEY"] = api_key
        pydantic_model = f"openai:{model}"
    
    # Create PydanticAI Agent
    from pydantic_ai import Agent
    from app.atlasclaw.core.deps import SkillDeps
    
    agent = Agent(
        pydantic_model,
        deps_type=SkillDeps,
        system_prompt="You are UniClaw, an enterprise AI assistant.",
    )
    
    # Register all skills as agent tools
    _skill_registry.register_to_agent(agent)
    
    # Create AgentRunner
    prompt_builder = PromptBuilder(PromptBuilderConfig())
    _agent_runner = AgentRunner(
        agent=agent,
        session_manager=_session_manager,
        prompt_builder=prompt_builder,
        session_queue=_session_queue,
    )

    webhook_manager = WebhookDispatchManager(config.webhook, _skill_registry)
    webhook_manager.validate_startup()
    
    print(f"[AtlasClaw] Agent created with model: {pydantic_model}")
    
    # Expose config on app.state so routes (e.g. SSO) can access it
    app.state.config = config
    # Coerce auth dict → AuthConfig object so SSO routes can call .provider / .oidc
    if config.auth is not None:
        from app.atlasclaw.auth.config import AuthConfig
        if isinstance(config.auth, dict):
            app.state.config.auth = AuthConfig(**config.auth)
        else:
            app.state.config.auth = config.auth
        # Treat disabled auth same as no auth
        if not app.state.config.auth.enabled:
            app.state.config.auth = None

    api_context = APIContext(
        session_manager=_session_manager,
        session_queue=_session_queue,
        skill_registry=_skill_registry,
        agent_runner=_agent_runner,
        service_provider_registry=_global_provider_registry,
        available_providers=available_providers,
        provider_instances=provider_instances,
        webhook_manager=webhook_manager,
    )
    set_api_context(api_context)
    
    print("[AtlasClaw] Application started successfully")
    print(f"[AtlasClaw] Session storage: {_session_manager.sessions_dir}")
    print(f"[AtlasClaw] Skills loaded: {len(_skill_registry.list_skills())} executable, {len(_skill_registry.list_md_skills())} markdown")
    
    yield
    
    # Cleanup on shutdown
    print("[AtlasClaw] Application shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AtlasClaw Enterprise Assistant",
        description="AI-powered enterprise assistant framework",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_request_validation_logging(app)
    
    # Mount static files for frontend
    frontend_dir = Path(__file__).parent.parent / "frontend"
    
    if frontend_dir.exists():
        # Mount static directories
        static_dir = frontend_dir / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        scripts_dir = frontend_dir / "scripts"
        if scripts_dir.exists():
            app.mount("/scripts", StaticFiles(directory=str(scripts_dir)), name="scripts")
        
        styles_dir = frontend_dir / "styles"
        if styles_dir.exists():
            app.mount("/styles", StaticFiles(directory=str(styles_dir)), name="styles")
        
        locales_dir = frontend_dir / "locales"
        if locales_dir.exists():
            app.mount("/locales", StaticFiles(directory=str(locales_dir)), name="locales")
        
        # Serve index.html for root path
        @app.get("/", include_in_schema=False)
        async def serve_index():
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {"error": "Frontend not found"}

        # Serve config.json
        @app.get("/config.json", include_in_schema=False)
        async def serve_config():
            config_path = frontend_dir / "config.json"
            if config_path.exists():
                return FileResponse(str(config_path))
            return {"apiBaseUrl": "http://127.0.0.1:8000"}
    
    # Include API routes
    api_router = create_router()
    app.include_router(api_router)

    # Include channel webhook routes
    app.include_router(channel_hooks_router)

    # Include channel management routes
    app.include_router(channels_router)

    # Include agent info routes
    app.include_router(agent_info_router)

    # Register AuthMiddleware — must be done at app creation time
    # (middleware cannot be added after startup)
    # Use config from lifespan (already loaded with correct working directory)
    try:
        from app.atlasclaw.auth.middleware import setup_auth_middleware
        from app.atlasclaw.core.config import ConfigManager
        from app.atlasclaw.auth.config import AuthConfig

        # Load config explicitly from the correct path
        config_path = Path(__file__).parent.parent.parent / "atlasclaw.json"
        if config_path.exists():
            _cfg_manager = ConfigManager(config_path=str(config_path))
            _cfg = _cfg_manager.config
        else:
            # Fallback to default config loading
            from app.atlasclaw.core.config import get_config
            _cfg = get_config()

        _auth = _cfg.auth if _cfg else None
        if isinstance(_auth, dict):
            _auth = AuthConfig(**_auth)
        # Respect the enabled flag — disabled auth runs in anonymous mode
        if _auth is not None and not _auth.enabled:
            _auth = None
        setup_auth_middleware(app, _auth)

        # Store config reference for routes to use
        app.state.config = _cfg
        if _auth is not None and isinstance(_auth, AuthConfig):
            app.state.config.auth = _auth
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).warning("AuthMiddleware setup skipped: %s", _e)

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.atlasclaw.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
