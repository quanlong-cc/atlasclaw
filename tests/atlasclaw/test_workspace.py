# -*- coding: utf-8 -*-
"""
Workspace initialization and management tests.

Tests for WorkspaceInitializer and UserWorkspaceInitializer.
"""

import json
import pytest
from pathlib import Path

from app.atlasclaw.core.workspace import WorkspaceInitializer, UserWorkspaceInitializer


class TestWorkspaceInitializer:
    """Test WorkspaceInitializer functionality."""

    def test_initialize_creates_directory_structure(self, tmp_path):
        """场景：首次创建工作区目录结构"""
        initializer = WorkspaceInitializer(str(tmp_path))
        result = initializer.initialize()
        
        assert result is True
        assert (tmp_path / ".atlasclaw").exists()
        assert (tmp_path / ".atlasclaw" / "agents").exists()
        assert (tmp_path / ".atlasclaw" / "providers").exists()
        assert (tmp_path / ".atlasclaw" / "skills").exists()
        assert (tmp_path / ".atlasclaw" / "channels").exists()
        assert (tmp_path / "users").exists()

    def test_initialize_creates_default_main_agent(self, tmp_path):
        """场景：首次创建默认 main Agent"""
        initializer = WorkspaceInitializer(str(tmp_path))
        initializer.initialize()
        
        main_agent_dir = tmp_path / ".atlasclaw" / "agents" / "main"
        assert main_agent_dir.exists()
        assert (main_agent_dir / "SOUL.md").exists()
        assert (main_agent_dir / "IDENTITY.md").exists()
        assert (main_agent_dir / "USER.md").exists()
        assert (main_agent_dir / "MEMORY.md").exists()

    def test_initialize_idempotent(self, tmp_path):
        """场景：目录已存在时跳过创建"""
        initializer = WorkspaceInitializer(str(tmp_path))
        
        # First initialization
        result1 = initializer.initialize()
        assert result1 is True
        
        # Second initialization should also succeed
        result2 = initializer.initialize()
        assert result2 is True
        
        # Directory should still exist
        assert (tmp_path / ".atlasclaw").exists()

    def test_is_initialized_returns_false_for_new_workspace(self, tmp_path):
        """场景：检查未初始化工作区"""
        initializer = WorkspaceInitializer(str(tmp_path))
        assert initializer.is_initialized() is False

    def test_is_initialized_returns_true_for_initialized_workspace(self, tmp_path):
        """场景：检查已初始化工作区"""
        initializer = WorkspaceInitializer(str(tmp_path))
        initializer.initialize()
        assert initializer.is_initialized() is True

    def test_default_main_agent_content(self, tmp_path):
        """场景：验证默认 main Agent 文件内容"""
        initializer = WorkspaceInitializer(str(tmp_path))
        initializer.initialize()
        
        soul_md = tmp_path / ".atlasclaw" / "agents" / "main" / "SOUL.md"
        content = soul_md.read_text(encoding="utf-8")
        
        assert "agent_id: \"main\"" in content
        assert "系统提示词" in content
        assert "能力范围" in content


class TestUserWorkspaceInitializer:
    """Test UserWorkspaceInitializer functionality."""

    def test_initialize_creates_user_directory_structure(self, tmp_path):
        """场景：首次创建用户目录结构（user_id="gang.wu"）"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "gang.wu")
        result = initializer.initialize()
        
        assert result is True
        user_dir = tmp_path / "users" / "gang.wu"
        assert user_dir.exists()
        assert (user_dir / "channels").exists()
        assert (user_dir / "sessions").exists()
        assert (user_dir / "memory").exists()

    def test_initialize_creates_default_user_config(self, tmp_path):
        """场景：创建默认用户级 atlasclaw.json"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "test_user")
        initializer.initialize()
        
        config_path = tmp_path / "users" / "test_user" / "atlasclaw.json"
        assert config_path.exists()
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        assert "providers" in config
        assert "skills" in config

    def test_initialize_idempotent(self, tmp_path):
        """场景：用户目录已存在时跳过创建"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "test_user")
        
        # First initialization
        result1 = initializer.initialize()
        assert result1 is True
        
        # Second initialization should also succeed
        result2 = initializer.initialize()
        assert result2 is True

    def test_is_initialized_returns_false_for_new_user(self, tmp_path):
        """场景：检查未初始化用户"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "new_user")
        assert initializer.is_initialized() is False

    def test_is_initialized_returns_true_for_initialized_user(self, tmp_path):
        """场景：检查已初始化用户"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "test_user")
        initializer.initialize()
        assert initializer.is_initialized() is True

    def test_get_sessions_dir(self, tmp_path):
        """场景：获取用户 sessions 目录"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "test_user")
        initializer.initialize()
        
        sessions_dir = initializer.get_sessions_dir()
        assert sessions_dir == tmp_path / "users" / "test_user" / "sessions"
        assert sessions_dir.exists()

    def test_get_memory_dir(self, tmp_path):
        """场景：获取用户 memory 目录"""
        initializer = UserWorkspaceInitializer(str(tmp_path), "test_user")
        initializer.initialize()
        
        memory_dir = initializer.get_memory_dir()
        assert memory_dir == tmp_path / "users" / "test_user" / "memory"
        assert memory_dir.exists()


class TestWorkspaceIntegration:
    """Integration tests for workspace functionality."""

    def test_full_workspace_initialization_flow(self, tmp_path):
        """场景：服务首次启动，自动创建工作区目录和默认 main Agent"""
        # Initialize workspace
        workspace_init = WorkspaceInitializer(str(tmp_path))
        workspace_init.initialize()
        
        # Initialize default user
        user_init = UserWorkspaceInitializer(str(tmp_path), "default")
        user_init.initialize()
        
        # Verify complete structure
        assert (tmp_path / ".atlasclaw" / "agents" / "main" / "SOUL.md").exists()
        assert (tmp_path / "users" / "default" / "sessions").exists()

    def test_workspace_persists_across_restarts(self, tmp_path):
        """场景：服务重启，保留已有工作区配置"""
        # First initialization
        workspace_init = WorkspaceInitializer(str(tmp_path))
        workspace_init.initialize()
        
        # Modify a file
        soul_md = tmp_path / ".atlasclaw" / "agents" / "main" / "SOUL.md"
        original_content = soul_md.read_text(encoding="utf-8")
        soul_md.write_text(original_content + "\n# Modified", encoding="utf-8")
        
        # Second initialization should not overwrite
        workspace_init.initialize()
        
        modified_content = soul_md.read_text(encoding="utf-8")
        assert "# Modified" in modified_content
