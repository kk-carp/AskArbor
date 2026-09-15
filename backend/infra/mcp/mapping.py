"""MCP 工具映射声明：仅保存工具名与注册协议，不绑定业务实现。"""

from __future__ import annotations

from typing import Iterable

from backend.infra.mcp.adapters import register_local_tool
from backend.infra.mcp.registry import ToolHandler, clear_registry, list_registered_tools

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "summarize_weak_points": "根据近期提问归纳知识薄弱点",
    "search_course": "课内检索候选",
    "search_external": "课外白名单搜索",
    "judge_relevance": "相关性判定与改写",
    "analyze_capability": "能力画像",
    "compose_report": "合成推荐文章结构",
    "web_search": "公开网页搜索（实践参考）",
    "search_arxiv": "arXiv Atom 搜索",
    "search_tavily": "Tavily 网页搜索",
}


def required_tool_names() -> tuple[str, ...]:
    """统一 MCP 路径要求的最小工具集合。"""
    return tuple(_TOOL_DESCRIPTIONS.keys())


def register_handlers(
    handlers: dict[str, ToolHandler],
    *,
    server: str = "local",
    replace: bool = True,
) -> None:
    """由上层组合根注入业务 handler；infra 不感知业务模块。"""
    if replace:
        clear_registry()
    missing = [name for name in required_tool_names() if name not in handlers]
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"MCP 工具映射缺失: {missing_text}")
    for name in required_tool_names():
        register_local_tool(
            name,
            handlers[name],
            description=_TOOL_DESCRIPTIONS.get(name, ""),
            server=server,
        )


def is_mapping_ready(expected: Iterable[str] | None = None) -> bool:
    names = {item.name for item in list_registered_tools()}
    target = set(expected or required_tool_names())
    return target.issubset(names)


def reset_mapping_for_tests() -> None:
    clear_registry()
