"""MCP 工具登记：仅允许已登记 server + tool；默认 local adapter。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.config import settings
from backend.infra.mcp.errors import McpNotAllowedError

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class McpToolSpec:
    """已登记工具：name 与 Agent/Skill 工具名对齐。"""

    name: str
    server: str
    handler: ToolHandler
    description: str = ""


_TOOLS: dict[str, McpToolSpec] = {}


def clear_registry() -> None:
    _TOOLS.clear()


def register_tool(spec: McpToolSpec) -> None:
    _TOOLS[spec.name] = spec


def list_registered_tools() -> list[McpToolSpec]:
    return list(_TOOLS.values())


def get_tool(name: str) -> McpToolSpec | None:
    return _TOOLS.get(name)


def allowed_servers() -> set[str]:
    raw = (settings.mcp_allow_servers or "local").strip()
    if not raw:
        return {"local"}
    return {part.strip() for part in raw.split(",") if part.strip()}


def assert_tool_allowed(name: str) -> McpToolSpec:
    spec = _TOOLS.get(name)
    if spec is None:
        raise McpNotAllowedError(f"未登记的 MCP 工具: {name}")
    if spec.server not in allowed_servers():
        raise McpNotAllowedError(
            f"MCP server 未允许: {spec.server}（工具 {name}）"
        )
    return spec
