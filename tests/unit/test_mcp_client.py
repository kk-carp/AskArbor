"""MCP 统一工具调用：模式、登记、清洗与故障隔离。"""

from __future__ import annotations

import pytest

from backend.infra.mcp import (
    call_tool,
    ensure_mapping_bootstrapped,
    fingerprint_tool_result,
    invoke_with_mode,
    list_registered_tools,
    reset_metrics,
    resolve_mode,
    sanitize_arguments,
    set_mapping_initializer,
    snapshot,
)
from backend.infra.mcp.errors import McpDisabledError, McpNotAllowedError, McpTimeoutError
from backend.infra.mcp.mapping import reset_mapping_for_tests
from backend.infra.mcp.registry import clear_registry, register_tool, McpToolSpec
from backend.services.mcp_tooling import bootstrap_mcp_tools
from backend.services.advanced_resources_tools import ToolResult, run_tool


@pytest.fixture(autouse=True)
def _reset_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_mapping_for_tests()
    clear_registry()
    reset_metrics()
    set_mapping_initializer(bootstrap_mcp_tools)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", False)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_mode", "off")
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_per_tool_override", "")
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_timeout_seconds", 15.0)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_allow_servers", "local")
    yield
    reset_mapping_for_tests()
    reset_metrics()
    set_mapping_initializer(None)


def test_sanitize_arguments_strips_space_keys() -> None:
    cleaned = sanitize_arguments(
        {"query": "RAG", "space_ids": ["company"], "allowed_spaces": ["x"], "space_id": "y"}
    )
    assert cleaned == {"query": "RAG"}


def test_resolve_mode_off_when_disabled() -> None:
    assert resolve_mode("search_external") == "off"


def test_resolve_mode_per_tool_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_mode", "shadow")
    monkeypatch.setattr(
        "backend.infra.mcp.client.settings.mcp_per_tool_override",
        "search_external=merge,web_search=off",
    )
    assert resolve_mode("search_external") == "merge"
    assert resolve_mode("web_search") == "off"
    assert resolve_mode("search_course") == "shadow"


def test_call_tool_disabled_raises() -> None:
    with pytest.raises(McpDisabledError):
        call_tool("search_external", {"queries": ["x"]})


def test_call_tool_unregistered_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    with pytest.raises(McpNotAllowedError):
        call_tool("no_such_tool", {})


def test_invoke_off_uses_legacy_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"legacy": 0, "mcp": 0}

    def legacy() -> str:
        calls["legacy"] += 1
        return "legacy"

    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", False)
    assert invoke_with_mode("demo", {}, legacy=legacy) == "legacy"
    assert calls["legacy"] == 1


def test_invoke_shadow_returns_legacy_and_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_mode", "shadow")

    def handler(arguments: dict) -> str:
        return f"mcp:{arguments.get('q')}"

    register_tool(McpToolSpec(name="demo", server="local", handler=handler))
    result = invoke_with_mode(
        "demo",
        {"q": "1"},
        legacy=lambda: "legacy",
        result_fingerprint=lambda x: str(x),
    )
    assert result == "legacy"
    snap = snapshot()
    assert snap["shadow_calls"] == 1
    assert snap["shadow_mismatches"] == 1


def test_invoke_merge_uses_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_mode", "merge")

    def handler(arguments: dict) -> str:
        return f"mcp:{arguments.get('q')}"

    register_tool(McpToolSpec(name="demo", server="local", handler=handler))
    assert invoke_with_mode("demo", {"q": "RAG"}, legacy=lambda: "legacy") == "mcp:RAG"
    assert snapshot()["merge_calls"] == 1


def test_invoke_merge_falls_back_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_mode", "merge")
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_timeout_seconds", 0.05)

    def slow(_arguments: dict) -> str:
        import time

        time.sleep(0.2)
        return "slow"

    register_tool(McpToolSpec(name="slow_tool", server="local", handler=slow))
    assert invoke_with_mode("slow_tool", {}, legacy=lambda: "legacy") == "legacy"
    assert snapshot()["errors"] >= 1


def test_mapping_registers_expected_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", True)
    ensure_mapping_bootstrapped()
    names = {item.name for item in list_registered_tools()}
    assert {
        "summarize_weak_points",
        "search_course",
        "search_external",
        "judge_relevance",
        "analyze_capability",
        "compose_report",
        "web_search",
        "search_arxiv",
        "search_tavily",
    } <= names


def test_run_tool_off_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.domain.skills.load_skill",
        lambda _name: type("S", (), {"name": "advanced-resources", "tools": {"search_course"}})(),
    )
    monkeypatch.setattr(
        "backend.services.advanced_resources_tools.tool_search_course",
        lambda **_k: ToolResult(tool="search_course", ok=True, data={"candidates": []}),
    )
    monkeypatch.setattr("backend.infra.mcp.client.settings.mcp_enabled", False)
    result = run_tool("search_course", {"query": "图", "space_ids": ["company"]}, user_id="u1")
    assert result.ok is True
    assert result.tool == "search_course"


def test_fingerprint_tool_result() -> None:
    result = ToolResult(tool="x", ok=True, data={"a": 1, "b": 2})
    assert "ok=True" in fingerprint_tool_result(result)
    assert "keys=['a', 'b']" in fingerprint_tool_result(result)
