"""集中管理课外搜索工具注册。"""

from __future__ import annotations

import logging

from backend.config import settings
from backend.infra.open_resource.sources import (
    SearchTool,
    list_search_tools,
    register_search_tool,
    reset_default_search_tools,
    run_arxiv_search,
    run_tavily_search,
)

_logger = logging.getLogger(__name__)


def init_open_resource_search_tools() -> None:
    """应用启动时初始化默认搜索工具注册表；可选经 MCP 统一调用。"""
    reset_default_search_tools()
    if settings.mcp_enabled:
        _wrap_search_tools_with_mcp()
    names = ",".join(tool.name for tool in list_search_tools())
    _logger.info("open-resource tools initialized: %s", names)


def _wrap_search_tools_with_mcp() -> None:
    from backend.infra.mcp import ensure_mapping_bootstrapped, invoke_with_mode

    ensure_mapping_bootstrapped()

    def _arxiv(query: str) -> list[dict[str, str]]:
        return invoke_with_mode(
            "search_arxiv",
            {"query": query},
            legacy=lambda: run_arxiv_search(query),
            result_fingerprint=lambda hits: f"list:{len(hits) if isinstance(hits, list) else -1}",
        )

    def _tavily(query: str) -> list[dict[str, str]]:
        return invoke_with_mode(
            "search_tavily",
            {"query": query},
            legacy=lambda: run_tavily_search(query),
            result_fingerprint=lambda hits: f"list:{len(hits) if isinstance(hits, list) else -1}",
        )

    register_search_tool(SearchTool(name="arxiv", run=_arxiv))
    register_search_tool(SearchTool(name="tavily", run=_tavily))
