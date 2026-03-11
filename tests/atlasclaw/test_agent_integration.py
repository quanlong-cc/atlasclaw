# -*- coding: utf-8 -*-
"""
PydanticAI Agent 集成测试

测试真实 PydanticAI Agent 的类型解析和工具注册。
这些测试验证 RunContext[SkillDeps] 类型注解在运行时能正确解析。
"""

import os
import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from app.atlasclaw.core.deps import SkillDeps


# 标记为 LLM 测试，需要 API key
pytestmark = pytest.mark.llm


class TestAgentTypeResolution:
    """测试 PydanticAI Agent 类型解析"""

    def test_import_runcontext_at_runtime(self):
        """验证 RunContext 可以在运行时导入"""
        from pydantic_ai import RunContext
        assert RunContext is not None

    def test_import_skilldeps_at_runtime(self):
        """验证 SkillDeps 可以在运行时导入"""
        from app.atlasclaw.core.deps import SkillDeps
        assert SkillDeps is not None

    def test_create_agent_with_deps_type(self, kimi_env_vars):
        """验证可以创建带 deps_type 的 Agent"""
        from pydantic_ai import Agent
        from app.atlasclaw.core.deps import SkillDeps
        
        # 设置环境变量
        os.environ["ANTHROPIC_BASE_URL"] = kimi_env_vars["base_url"]
        os.environ["ANTHROPIC_API_KEY"] = kimi_env_vars["api_key"]
        
        agent = Agent(
            "anthropic:kimi-k2.5",
            deps_type=SkillDeps,
            system_prompt="You are a test assistant.",
        )
        
        assert agent is not None
        assert agent._deps_type == SkillDeps

    def test_register_tool_with_runcontext_annotation(self, kimi_env_vars, skill_registry):
        """验证带 RunContext 注解的 handler 可以注册到真实 Agent"""
        from pydantic_ai import Agent
        from app.atlasclaw.core.deps import SkillDeps
        from app.atlasclaw.skills.registry import SkillMetadata
        
        # 设置环境变量
        os.environ["ANTHROPIC_BASE_URL"] = kimi_env_vars["base_url"]
        os.environ["ANTHROPIC_API_KEY"] = kimi_env_vars["api_key"]
        
        # 创建 Agent
        agent = Agent(
            "anthropic:kimi-k2.5",
            deps_type=SkillDeps,
            system_prompt="You are a test assistant.",
        )
        
        # 定义带正确类型注解的 handler
        async def test_handler(ctx: "RunContext[SkillDeps]", query: str) -> dict:
            """测试工具函数"""
            return {"result": f"Processed: {query}"}
        
        # 注册到 SkillRegistry
        skill_registry.register(
            SkillMetadata(name="test_tool", description="Test tool"),
            test_handler,
        )
        
        # 注册到 Agent - 这是关键测试点
        # 如果类型注解有问题，这里会抛出 NameError 或 UserError
        skill_registry.register_to_agent(agent)
        
        # 验证工具已注册
        assert "test_tool" in skill_registry.list_skills()

    def test_builtin_tools_registration(self, kimi_env_vars):
        """验证内置工具可以注册到真实 Agent"""
        from pydantic_ai import Agent
        from app.atlasclaw.core.deps import SkillDeps
        from app.atlasclaw.skills.registry import SkillRegistry
        from app.atlasclaw.tools.registration import register_builtin_tools
        from app.atlasclaw.tools.catalog import ToolProfile
        
        # 设置环境变量
        os.environ["ANTHROPIC_BASE_URL"] = kimi_env_vars["base_url"]
        os.environ["ANTHROPIC_API_KEY"] = kimi_env_vars["api_key"]
        
        # 创建 Agent
        agent = Agent(
            "anthropic:kimi-k2.5",
            deps_type=SkillDeps,
            system_prompt="You are a test assistant.",
        )
        
        # 创建 SkillRegistry 并注册内置工具
        registry = SkillRegistry()
        registered = register_builtin_tools(registry, profile=ToolProfile.FULL)
        
        assert len(registered) > 0, "应该注册至少一个内置工具"
        
        # 注册到 Agent - 验证所有内置工具的类型注解都正确
        registry.register_to_agent(agent)
        
        # 验证工具数量
        skills = registry.list_skills()
        assert len(skills) >= len(registered)


class TestProviderSkillsTypeResolution:
    """测试 Provider Skills 的类型解析"""

    def test_jira_skill_handler_annotation(self, kimi_env_vars):
        """验证 JIRA skill handler 的类型注解正确"""
        from pydantic_ai import Agent
        from app.atlasclaw.core.deps import SkillDeps
        from app.atlasclaw.skills.registry import SkillRegistry, SkillMetadata
        
        # 设置环境变量
        os.environ["ANTHROPIC_BASE_URL"] = kimi_env_vars["base_url"]
        os.environ["ANTHROPIC_API_KEY"] = kimi_env_vars["api_key"]
        
        # 创建 Agent
        agent = Agent(
            "anthropic:kimi-k2.5",
            deps_type=SkillDeps,
            system_prompt="You are a test assistant.",
        )
        
        # 加载 JIRA provider skills
        registry = SkillRegistry()
        providers_dir = os.path.join(os.path.dirname(__file__), "..", "app", "atlasclaw", "providers")
        
        if os.path.exists(providers_dir):
            for provider_name in os.listdir(providers_dir):
                provider_path = os.path.join(providers_dir, provider_name)
                if os.path.isdir(provider_path):
                    skills_dir = os.path.join(provider_path, "skills")
                    if os.path.exists(skills_dir):
                        registry.load_from_directory(skills_dir, location="built-in")
        
        # 注册到 Agent - 验证 provider skills 的类型注解
        registry.register_to_agent(agent)


class TestProviderInstanceToolsTypeResolution:
    """测试 Provider Instance 工具的类型解析"""

    def test_list_provider_instances_tool_annotation(self, kimi_env_vars):
        """验证 list_provider_instances_tool 的类型注解正确"""
        from pydantic_ai import Agent
        from app.atlasclaw.core.deps import SkillDeps
        from app.atlasclaw.skills.registry import SkillRegistry, SkillMetadata
        
        # 设置环境变量
        os.environ["ANTHROPIC_BASE_URL"] = kimi_env_vars["base_url"]
        os.environ["ANTHROPIC_API_KEY"] = kimi_env_vars["api_key"]
        
        # 创建 Agent
        agent = Agent(
            "anthropic:kimi-k2.5",
            deps_type=SkillDeps,
            system_prompt="You are a test assistant.",
        )
        
        # 导入并注册 provider instance tools
        from app.atlasclaw.tools.providers.instance_tools import (
            list_provider_instances_tool,
            select_provider_instance_tool,
        )
        
        registry = SkillRegistry()
        registry.register(
            SkillMetadata(name="list_provider_instances", description="List provider instances"),
            list_provider_instances_tool,
        )
        registry.register(
            SkillMetadata(name="select_provider_instance", description="Select provider instance"),
            select_provider_instance_tool,
        )
        
        # 注册到 Agent - 验证类型注解
        registry.register_to_agent(agent)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "llm"])
