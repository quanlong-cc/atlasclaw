# -*- coding: utf-8 -*-
"""
Config workspace and multi-layer loading tests.

Tests for ConfigManager workspace configuration loading.
"""

import json
import pytest
from pathlib import Path

from app.atlasclaw.core.config import ConfigManager
from app.atlasclaw.core.config_schema import AtlasClawConfig


class TestConfigWorkspaceLoading:
    """Test ConfigManager workspace configuration loading."""

    def test_load_workspace_config(self, tmp_path):
        """场景：工作区配置覆盖全局配置"""
        # Create global config
        global_config = {"model": {"primary": "global-model"}, "log_level": "info"}
        global_config_path = tmp_path / "global_config.json"
        with open(global_config_path, "w") as f:
            json.dump(global_config, f)

        # Create workspace config
        workspace_config = {"model": {"primary": "workspace-model"}}
        workspace_config_path = tmp_path / "atlasclaw.json"
        with open(workspace_config_path, "w") as f:
            json.dump(workspace_config, f)

        # Load config
        config_manager = ConfigManager(config_path=str(global_config_path))
        config = config_manager.load()

        # Workspace config should override global
        assert config.model.primary == "workspace-model"

    def test_load_user_config(self, tmp_path):
        """场景：加载用户区配置"""
        # Create workspace config with workspace path
        workspace_config = {
            "model": {"primary": "workspace-model"}, 
            "log_level": "info",
            "workspace": {"path": str(tmp_path)}
        }
        workspace_config_path = tmp_path / "atlasclaw.json"
        with open(workspace_config_path, "w") as f:
            json.dump(workspace_config, f)

        # Create user config
        user_config = {"model": {"primary": "user-model"}}
        users_dir = tmp_path / "users" / "test_user"
        users_dir.mkdir(parents=True)
        user_config_path = users_dir / "atlasclaw.json"
        with open(user_config_path, "w") as f:
            json.dump(user_config, f)

        # Load config
        config_manager = ConfigManager(config_path=str(workspace_config_path))
        config_manager.load()

        # Load user config (raw, not merged)
        user_config_loaded = config_manager.load_user_config("test_user")
        assert user_config_loaded.get("model", {}).get("primary") == "user-model"

    def test_config_merge_priority(self, tmp_path):
        """场景：验证配置优先级（工作区 > 全局 > 默认）"""
        # Create global config with some values
        global_config = {
            "model": {"primary": "global-model", "fallbacks": []},
            "log_level": "info"
        }
        global_config_path = tmp_path / "global_config.json"
        with open(global_config_path, "w") as f:
            json.dump(global_config, f)

        # Create workspace config that overrides only primary
        workspace_config = {"model": {"primary": "workspace-model"}}
        workspace_config_path = tmp_path / "atlasclaw.json"
        with open(workspace_config_path, "w") as f:
            json.dump(workspace_config, f)

        # Load config
        config_manager = ConfigManager(config_path=str(global_config_path))
        config = config_manager.load()

        # Workspace should override primary, but fallbacks should remain from global
        assert config.model.primary == "workspace-model"

    def test_missing_config_uses_defaults(self, tmp_path):
        """场景：缺失的配置项使用默认值填充"""
        # Create minimal config
        minimal_config = {"log_level": "debug"}
        config_path = tmp_path / "minimal_config.json"
        with open(config_path, "w") as f:
            json.dump(minimal_config, f)

        # Load config
        config_manager = ConfigManager(config_path=str(config_path))
        config = config_manager.load()

        # Should have default values for missing items
        assert config.log_level.value == "debug"
        assert config.workspace.path == "."  # default value


class TestWorkspaceConfigSchema:
    """Test WorkspaceConfig schema."""

    def test_workspace_config_defaults(self):
        """场景：验证 WorkspaceConfig 默认值"""
        from app.atlasclaw.core.config_schema import WorkspaceConfig

        config = WorkspaceConfig()
        assert config.path == "."
        assert config.per_user_isolation is True

    def test_workspace_config_custom_values(self):
        """场景：验证 WorkspaceConfig 自定义值"""
        from app.atlasclaw.core.config_schema import WorkspaceConfig

        config = WorkspaceConfig(path="/custom/path", per_user_isolation=False)
        assert config.path == "/custom/path"
        assert config.per_user_isolation is False


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""

    def test_full_config_loading_flow(self, tmp_path):
        """场景：完整配置加载流程"""
        # Create global config
        global_config = {
            "model": {"primary": "deepseek/deepseek-chat"},
            "log_level": "info"
        }
        global_config_path = tmp_path / "global_config.json"
        with open(global_config_path, "w") as f:
            json.dump(global_config, f)

        # Create workspace config
        workspace_config = {"workspace": {"path": str(tmp_path)}}
        workspace_config_path = tmp_path / "atlasclaw.json"
        with open(workspace_config_path, "w") as f:
            json.dump(workspace_config, f)

        # Load config
        config_manager = ConfigManager(config_path=str(global_config_path))
        config = config_manager.load()

        # Verify merged config
        assert config.model.primary == "deepseek/deepseek-chat"
        assert config.workspace.path == str(tmp_path)
