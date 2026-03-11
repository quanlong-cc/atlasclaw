"""

Configuration manager

implementmulti configurationparse(run > environment variable > > default value)andconfiguration.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional, Any
from pydantic import ValidationError
from dotenv import load_dotenv

from app.atlasclaw.core.config_schema import AtlasClawConfig


class ConfigManager:
    """

Configuration manager
    
    configuration(from to):
    1. runtime override(through set())
    2. environment variable(ATLASCLAW_* prefix)
    3. profile(atlasclaw.json / atlasclaw.yaml)
    4. default value(config_schema.py in)
    
    Example usage:
        ```python
        config_manager = ConfigManager()
        config_manager.load()
        
        # getconfiguration
        timeout = config_manager.config.agent_defaults.timeout_seconds
        
        # runtime override
        config_manager.set("agent_defaults.timeout_seconds", 300)
        
        #
        config_manager.reload()
        ```
    
"""
    
    DEFAULT_CONFIG_PATHS = [
        "atlasclaw.json",
        "atlasclaw.yaml",
        "~/.atlasclaw/config.json",
    ]
    
    ENV_PREFIX = "ATLASCLAW_"
    
    def __init__(self, config_path: Optional[str] = None):
        """

initializeConfiguration manager
        
        Args:
            config_path:configurationfile path(optional)
        
"""
        self._config_path = config_path or os.environ.get("ATLASCLAW_CONFIG")
        self._config: AtlasClawConfig = AtlasClawConfig()
        self._runtime_overrides: dict[str, Any] = {}
        self._loaded = False
        self._resolved_config_path: Optional[Path] = None
    
    @property
    def config(self) -> AtlasClawConfig:
        """get configuration"""
        if not self._loaded:
            self.load()
        return self._config

    @property
    def resolved_config_path(self) -> Optional[Path]:
        """Return the absolute path of the config file that was loaded, if any."""
        if not self._loaded:
            self.load()
        return self._resolved_config_path
    
    def load(self) -> AtlasClawConfig:
        """
        加载配置
        
        优先级: 默认值 <- 全局配置 <- 工作区配置 <- 用户区配置 <- 环境变量 <- 运行时覆盖
        
        Returns:
            配置对象
        """
        # 1. 从默认值开始
        config_dict: dict[str, Any] = {}
        
        # 2. 加载全局配置
        global_config = self._load_from_file()
        if global_config:
            config_dict = self._deep_merge(config_dict, global_config)
        
        # 3. 加载工作区配置（最高优先级文件配置）
        workspace_config = self._load_workspace_config()
        if workspace_config:
            config_dict = self._deep_merge(config_dict, workspace_config)
        
        # 4. 从环境变量加载
        env_config = self._load_from_env()
        if env_config:
            config_dict = self._deep_merge(config_dict, env_config)
        
        # 5. 应用运行时覆盖
        if self._runtime_overrides:
            config_dict = self._deep_merge(config_dict, self._runtime_overrides)
        
        # 6. 创建配置对象
        try:
            self._config = AtlasClawConfig(**config_dict)
        except ValidationError as e:
            # 配置验证失败，使用默认值
            print(f"[ConfigManager] 配置验证失败，使用默认值: {e}")
            self._config = AtlasClawConfig()
        
        self._loaded = True
        return self._config
    
    def _load_workspace_config(self) -> Optional[dict]:
        """加载工作区配置"""
        # 首先尝试从已加载的配置中获取工作区路径
        workspace_path = "."
        if self._config_path:
            workspace_path = str(Path(self._config_path).parent)
        
        # 尝试加载工作区 atlasclaw.json
        workspace_config_path = Path(workspace_path) / "atlasclaw.json"
        if workspace_config_path.exists():
            try:
                with open(workspace_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ConfigManager] 读取工作区配置失败 {workspace_config_path}: {e}")
        
        return None
    
    def load_user_config(self, user_id: str) -> dict:
        """加载用户区配置"""
        workspace_path = Path(self.config.workspace.path)
        user_config_path = workspace_path / "users" / user_id / "atlasclaw.json"
        
        if user_config_path.exists():
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ConfigManager] 读取用户配置失败 {user_config_path}: {e}")
        
        return {}
    
    def reload(self) -> AtlasClawConfig:
        """configuration"""
        self._loaded = False
        return self.load()
    
    def set(self, key: str, value: Any) -> None:
        """

run configuration
        
        Args:
            key:configuration(, such as "agent_defaults.timeout_seconds")
            value:configuration
        
"""
        self._set_nested(self._runtime_overrides, key.split("."), value)
        # apply
        self._loaded = False
    
    def get(self, key: str, default: Any = None) -> Any:
        """

get configuration
        
        Args:
            key:configuration()
            default:default value
            
        Returns:
            configuration ordefault value
        
"""
        try:
            obj = self.config
            for part in key.split("."):
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                elif isinstance(obj, dict) and part in obj:
                    obj = obj[part]
                else:
                    return default
            return obj
        except Exception:
            return default
    
    def _load_from_file(self) -> Optional[dict]:
        """from configuration"""
        paths = [self._config_path] if self._config_path else self.DEFAULT_CONFIG_PATHS
        
        for path_str in paths:
            if not path_str:
                continue
            path = Path(path_str).expanduser()
            if path.exists():
                try:
                    self._resolved_config_path = path.resolve()
                    self._load_sidecar_dotenv(self._resolved_config_path)
                    with open(path, "r", encoding="utf-8") as f:
                        if path.suffix == ".json":
                            return json.load(f)
                        elif path.suffix in (".yaml", ".yml"):
                            # YAML support(optional)
                            try:
                                import yaml
                                return yaml.safe_load(f)
                            except ImportError:
                                print(f"[ConfigManager] YAML 支持需要安装 PyYAML")
                                continue
                except Exception as e:
                    print(f"[ConfigManager] 读取配置文件失败 {path}: {e}")
                    continue
        return None

    @staticmethod
    def _load_sidecar_dotenv(config_path: Path) -> None:
        """Load `.env` next to the resolved config file without overriding existing env vars."""
        dotenv_path = config_path.parent / ".env"
        if dotenv_path.is_file():
            load_dotenv(dotenv_path=dotenv_path, override=False)
    
    def _load_from_env(self) -> dict:
        """

fromenvironment variable configuration
        
        environment variableformat:ATLASCLAW_<PATH>__<KEY>
        such as:ATLASCLAW_AGENT_DEFAULTS__TIMEOUT_SECONDS=300
        
"""
        config: dict[str, Any] = {}
        
        for key, value in os.environ.items():
            if not key.startswith(self.ENV_PREFIX):
                continue
            
            # prefix configuration
            config_key = key[len(self.ENV_PREFIX):].lower()
            parts = config_key.split("__")
            
            # parse type
            parsed_value = self._parse_env_value(value)
            
            # to configurationdictionary
            self._set_nested(config, parts, parsed_value)
        
        return config
    
    def _parse_env_value(self, value: str) -> Any:
        """parseenvironment variable type"""
        # parse JSON(support type)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        
        # 
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        
        # count
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # characters
        return value
    
    def _set_nested(self, d: dict, keys: list[str], value: Any) -> None:
        """at dictionaryin"""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """dictionary"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


# Configuration managerinstance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """get Configuration managerinstance"""
    global _config_manager
    if _config_manager is None:
        config_path = os.environ.get("ATLASCLAW_CONFIG")
        _config_manager = ConfigManager(config_path=config_path)
    return _config_manager


def get_config() -> AtlasClawConfig:
    """get configuration"""
    return get_config_manager().config


def get_config_path() -> Optional[Path]:
    """Return the resolved config file path for the active config manager."""
    return get_config_manager().resolved_config_path
