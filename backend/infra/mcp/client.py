"""MCP Client：统一 call_tool + off/shadow/merge 路由器。"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Callable, TypeVar

from backend.config import settings
from backend.infra.mcp.errors import (
    McpDisabledError,
    McpError,
    McpTimeoutError,
    McpUnavailableError,
)
from backend.infra.mcp import metrics
from backend.infra.mcp.registry import assert_tool_allowed, list_registered_tools

_log = logging.getLogger("backend.audit")
T = TypeVar("T")
_mapping_initializer: Callable[[], None] | None = None

_STRIP_KEYS = frozenset({"space_ids", "allowed_spaces", "space_id"})


def sanitize_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(arguments or {})
    for key in _STRIP_KEYS:
        payload.pop(key, None)
    return payload


def resolve_mode(tool: str) -> str:
    """全局 mcp_mode，可被 mcp_per_tool_override 覆盖。"""
    if not settings.mcp_enabled:
        return "off"
    overrides = _parse_overrides(settings.mcp_per_tool_override)
    if tool in overrides:
        return overrides[tool]
    return settings.mcp_mode


def _parse_overrides(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    text = (raw or "").strip()
    if not text:
        return result
    for part in text.split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, mode = item.split("=", 1)
        name = name.strip()
        mode = mode.strip().lower()
        if name and mode in {"off", "shadow", "merge"}:
            result[name] = mode
    return result


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """调用已登记 MCP 工具（当前以 local adapter 为主）。"""
    if not settings.mcp_enabled:
        raise McpDisabledError("MCP 未启用")
    spec = assert_tool_allowed(name)
    payload = sanitize_arguments(arguments)
    timeout = max(0.1, float(settings.mcp_timeout_seconds))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(spec.handler, payload)
            return future.result(timeout=timeout)
    except FuturesTimeout as exc:
        raise McpTimeoutError(f"MCP 工具超时: {name}") from exc
    except McpError:
        raise
    except Exception as exc:
        raise McpUnavailableError(f"MCP 工具调用失败: {name}") from exc


def set_mapping_initializer(initializer: Callable[[], None] | None) -> None:
    """注册 MCP 映射初始化器（由应用层注入）。"""
    global _mapping_initializer
    _mapping_initializer = initializer


def invoke_with_mode(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    legacy: Callable[[], T],
    result_fingerprint: Callable[[T], str] | None = None,
) -> T:
    """按 off/shadow/merge 执行：shadow 返回 legacy；merge 走 MCP。"""
    mode = resolve_mode(name)
    if mode == "off":
        return legacy()

    if mode == "shadow":
        legacy_result = legacy()
        started = time.perf_counter()
        try:
            mcp_result = call_tool(name, arguments)
            elapsed_ms = (time.perf_counter() - started) * 1000
            metrics.record_call(name, mode="shadow", elapsed_ms=elapsed_ms, error=False)
            if result_fingerprint is not None:
                left = result_fingerprint(legacy_result)
                right = result_fingerprint(mcp_result)  # type: ignore[arg-type]
                if left != right:
                    metrics.record_shadow_mismatch(name, f"legacy={left!r} mcp={right!r}")
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            metrics.record_call(name, mode="shadow", elapsed_ms=elapsed_ms, error=True)
            _log.info("mcp_shadow_error tool=%s err=%s", name, type(exc).__name__)
        return legacy_result

    # merge
    started = time.perf_counter()
    try:
        result = call_tool(name, arguments)
        metrics.record_call(
            name,
            mode="merge",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=False,
        )
        return result  # type: ignore[return-value]
    except McpError as exc:
        metrics.record_call(
            name,
            mode="merge",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=True,
        )
        _log.warning("mcp_merge_fallback tool=%s type=%s", name, exc.error_type)
        return legacy()


def fingerprint_tool_result(result: Any) -> str:
    """用于 shadow 对比的粗指纹。"""
    ok = getattr(result, "ok", None)
    error_type = getattr(result, "error_type", None)
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        keys = sorted(data.keys())
        return f"ok={ok}|err={error_type}|keys={keys}|n={len(data)}"
    if isinstance(result, str):
        return f"str:{len(result)}"
    if isinstance(result, list):
        return f"list:{len(result)}"
    return f"type={type(result).__name__}"


def ensure_mapping_bootstrapped() -> None:
    """确保映射已装载：不做业务导入，由上层注入 initializer。"""
    if list_registered_tools():
        return
    if _mapping_initializer is None:
        raise McpUnavailableError("MCP 映射初始化器未配置")
    _mapping_initializer()
    if not list_registered_tools():
        raise McpUnavailableError("MCP 映射初始化后仍为空")
