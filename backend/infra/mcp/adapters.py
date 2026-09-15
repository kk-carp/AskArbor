"""本地函数适配为 MCP 工具 handler（过渡期；不启独立进程）。"""

from __future__ import annotations

from typing import Any, Callable

from backend.infra.mcp.registry import McpToolSpec, register_tool

LocalFn = Callable[..., Any]


def register_local_tool(
    name: str,
    handler: Callable[[dict[str, Any]], Any],
    *,
    description: str = "",
    server: str = "local",
) -> None:
    """把已有实现登记为 local MCP 工具。"""
    register_tool(
        McpToolSpec(
            name=name,
            server=server,
            handler=handler,
            description=description,
        )
    )
