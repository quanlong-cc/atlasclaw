"""Service provider registry for provider templates, instances, and skill wrappers."""

from __future__ import annotations

import functools
import importlib.util
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from app.atlasclaw.core.deps import SkillDeps
    from app.atlasclaw.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")

_SENSITIVE_KEYS = frozenset(
    {
        "token",
        "password",
        "secret",
        "api_key",
        "apikey",
        "access_token",
        "private_key",
        "credential",
    }
)


def _resolve_env(value: str) -> str:
    """Resolve ${VAR} or ${VAR:default} placeholders."""

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        return os.environ.get(var_name, default if default is not None else "")

    return _ENV_PATTERN.sub(_replacer, value)


def _resolve_env_recursive(obj: Any) -> Any:
    """Resolve environment placeholders in nested structures."""
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(item) for item in obj]
    return obj


def _is_sensitive(key: str) -> bool:
    return key.lower() in _SENSITIVE_KEYS


def _redact_config(config: dict[str, Any]) -> dict[str, Any]:
    return {k: ("***" if _is_sensitive(k) else v) for k, v in config.items()}


@dataclass
class ProviderTemplate:
    name: str
    path: Path
    md_path: Path
    skills_dir: Path


class ServiceProviderRegistry:
    """Registry of provider templates and provider instances from configuration."""

    def __init__(self) -> None:
        self._templates: dict[str, ProviderTemplate] = {}
        self._instances: dict[str, dict[str, dict[str, Any]]] = {}

    def load_from_directory(self, providers_dir: Path) -> int:
        """Load provider templates from a providers directory."""
        providers_dir = Path(providers_dir).expanduser()
        if not providers_dir.is_dir():
            logger.debug("providers directory does not exist: %s", providers_dir)
            return 0

        count = 0
        for sub in sorted(providers_dir.iterdir()):
            if not sub.is_dir() or sub.name.startswith(("_", ".")):
                continue

            md_path = self._find_provider_md(sub)
            if md_path is None:
                logger.warning(
                    "Skipping provider directory %s: missing PROVIDER.md or %s.md",
                    sub.name,
                    sub.name,
                )
                continue

            template = ProviderTemplate(
                name=sub.name,
                path=sub,
                md_path=md_path,
                skills_dir=sub / "skills",
            )
            self._templates[sub.name] = template
            count += 1
            logger.info("Discovered provider: %s (%s)", sub.name, md_path.name)

        return count

    def load_instances_from_config(self, config: dict[str, dict[str, Any]]) -> None:
        """Load provider instance configuration from atlasclaw config."""
        for provider_type, instances in config.items():
            if not isinstance(instances, dict):
                logger.warning(
                    "Provider %s config format invalid: expected dict, got %s",
                    provider_type,
                    type(instances).__name__,
                )
                continue

            resolved_instances: dict[str, dict[str, Any]] = {}
            for instance_name, params in instances.items():
                if not isinstance(params, dict):
                    logger.warning(
                        "Provider %s.%s config format invalid: expected dict, got %s",
                        provider_type,
                        instance_name,
                        type(params).__name__,
                    )
                    continue
                resolved_instances[instance_name] = _resolve_env_recursive(params)

            self._instances[provider_type] = resolved_instances
            logger.info(
                "Loaded provider instances: %s -> %s",
                provider_type,
                list(resolved_instances.keys()),
            )

    def list_providers(self) -> list[str]:
        all_types = set(self._templates.keys()) | set(self._instances.keys())
        return sorted(all_types)

    def list_instances(self, provider_type: str) -> list[str]:
        return sorted(self._instances.get(provider_type, {}).keys())

    def get_instance_config(
        self,
        provider_type: str,
        instance_name: str,
    ) -> Optional[dict[str, Any]]:
        instances = self._instances.get(provider_type)
        if instances is None:
            return None
        config = instances.get(instance_name)
        return dict(config) if isinstance(config, dict) else None

    def get_instance_config_redacted(
        self,
        provider_type: str,
        instance_name: str,
    ) -> Optional[dict[str, Any]]:
        config = self.get_instance_config(provider_type, instance_name)
        if config is None:
            return None
        return _redact_config(config)

    def get_all_instance_configs(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return all resolved provider instance configs."""
        return {
            provider_type: {
                instance_name: dict(instance_cfg)
                for instance_name, instance_cfg in instances.items()
            }
            for provider_type, instances in self._instances.items()
        }

    def get_available_providers_summary(self) -> dict[str, list[str]]:
        return {
            provider_type: self.list_instances(provider_type)
            for provider_type in self.list_providers()
        }

    def get_template(self, provider_type: str) -> Optional[ProviderTemplate]:
        return self._templates.get(provider_type)

    def register_skills_to(self, skill_registry: "SkillRegistry") -> int:
        """Load and register provider skills with provider-aware wrappers."""
        from app.atlasclaw.skills.registry import SkillMetadata

        total = 0
        for provider_type, template in self._templates.items():
            if not template.skills_dir.is_dir():
                continue

            for py_file in sorted(template.skills_dir.glob("*.py")):
                if py_file.name.startswith("_") or py_file.stem == "shared":
                    continue

                try:
                    module = self._load_module(py_file)
                except Exception as exc:
                    logger.warning("Failed loading provider skill %s: %s", py_file, exc)
                    continue

                skill_metadata_raw = getattr(module, "SKILL_METADATA", None)
                handler = getattr(module, "handler", None)
                if skill_metadata_raw is None or handler is None:
                    continue

                original_name = (
                    skill_metadata_raw.name if hasattr(skill_metadata_raw, "name") else py_file.stem
                )
                description = (
                    skill_metadata_raw.description
                    if hasattr(skill_metadata_raw, "description")
                    else ""
                )
                prefixed_name = f"{provider_type}__{original_name}"

                metadata = SkillMetadata(
                    name=prefixed_name,
                    description=description,
                    category=f"provider:{provider_type}",
                    provider_type=provider_type,
                    instance_required=True,
                    location="built-in",
                )

                wrapped = self._make_handler_wrapper(handler=handler, provider_type=provider_type)
                skill_registry.register(metadata, wrapped)
                total += 1

        logger.info("Registered %d provider skills", total)
        return total

    def _make_handler_wrapper(self, handler: Callable, provider_type: str) -> Callable:
        registry = self

        @functools.wraps(handler)
        async def wrapper(ctx: "RunContext[SkillDeps]", **kwargs: Any) -> Any:
            extra = (
                ctx.deps.extra
                if hasattr(ctx, "deps") and isinstance(getattr(ctx.deps, "extra", None), dict)
                else {}
            )

            # Always expose all provider instances to skills via deps.extra.
            extra.setdefault("provider_instances", registry.get_all_instance_configs())

            selected_type = str(extra.get("provider_type", ""))
            selected_name = str(extra.get("provider_instance_name", ""))
            selected_cfg = extra.get("provider_instance")

            # If already selected and valid for this provider, run directly.
            if (
                selected_type == provider_type
                and selected_name
                and isinstance(selected_cfg, dict)
            ):
                return await handler(ctx, **kwargs)

            instances = registry.list_instances(provider_type)
            if len(instances) == 0:
                return {
                    "is_error": True,
                    "content": [
                        {"type": "text", "text": f"Provider '{provider_type}' has no configured instances."}
                    ],
                }

            # Keep an explicitly chosen instance name if present.
            if selected_type == provider_type and selected_name in instances:
                cfg = registry.get_instance_config(provider_type, selected_name) or {}
                extra["provider_type"] = provider_type
                extra["provider_instance_name"] = selected_name
                extra["provider_instance"] = cfg
                return await handler(ctx, **kwargs)

            # Auto-select if exactly one instance exists.
            if len(instances) == 1:
                instance_name = instances[0]
                cfg = registry.get_instance_config(provider_type, instance_name) or {}
                extra["provider_type"] = provider_type
                extra["provider_instance_name"] = instance_name
                extra["provider_instance"] = cfg
                return await handler(ctx, **kwargs)

            # Multiple instances and no selection.
            return {
                "is_error": True,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Provider '{provider_type}' has {len(instances)} instances: "
                            f"{', '.join(instances)}. Call list_provider_instances('{provider_type}') "
                            "then select_provider_instance before invoking provider skills."
                        ),
                    }
                ],
            }

        return wrapper

    @staticmethod
    def _find_provider_md(directory: Path) -> Optional[Path]:
        provider_md = directory / "PROVIDER.md"
        if provider_md.is_file():
            return provider_md

        named_md = directory / f"{directory.name}.md"
        if named_md.is_file():
            return named_md

        return None

    @staticmethod
    def _load_module(file_path: Path) -> Any:
        spec = importlib.util.spec_from_file_location(f"provider_skill_{file_path.stem}", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module: {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module