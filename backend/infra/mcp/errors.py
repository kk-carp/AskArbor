"""MCP 错误分类：失败停留在工具层，不得抬成知识库未命中。"""

from __future__ import annotations


class McpError(RuntimeError):
    """MCP 调用失败基类。"""

    error_type: str = "mcp_unavailable"

    def __init__(self, message: str, *, error_type: str | None = None) -> None:
        super().__init__(message)
        if error_type:
            self.error_type = error_type


class McpDisabledError(McpError):
    error_type = "mcp_disabled"


class McpTimeoutError(McpError):
    error_type = "mcp_timeout"


class McpUnavailableError(McpError):
    error_type = "mcp_unavailable"


class McpNotAllowedError(McpError):
    error_type = "mcp_not_allowed"


class McpBadPayloadError(McpError):
    error_type = "mcp_bad_payload"
