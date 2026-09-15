"""MCP shadow / 调用指标（进程内累计，重启清零）。"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

_log = logging.getLogger("backend.audit")
_lock = threading.Lock()


@dataclass
class _Counters:
    calls: int = 0
    shadow_calls: int = 0
    merge_calls: int = 0
    errors: int = 0
    shadow_mismatches: int = 0
    elapsed_ms_total: float = 0.0
    by_tool: dict[str, int] = field(default_factory=dict)


_counters = _Counters()


def reset_metrics() -> None:
    global _counters
    with _lock:
        _counters = _Counters()


def snapshot() -> dict[str, object]:
    with _lock:
        return {
            "calls": _counters.calls,
            "shadow_calls": _counters.shadow_calls,
            "merge_calls": _counters.merge_calls,
            "errors": _counters.errors,
            "shadow_mismatches": _counters.shadow_mismatches,
            "elapsed_ms_total": round(_counters.elapsed_ms_total, 2),
            "by_tool": dict(_counters.by_tool),
        }


def record_call(
    tool: str,
    *,
    mode: str,
    elapsed_ms: float,
    error: bool = False,
) -> None:
    with _lock:
        _counters.calls += 1
        _counters.by_tool[tool] = _counters.by_tool.get(tool, 0) + 1
        _counters.elapsed_ms_total += max(0.0, elapsed_ms)
        if mode == "shadow":
            _counters.shadow_calls += 1
        elif mode == "merge":
            _counters.merge_calls += 1
        if error:
            _counters.errors += 1


def record_shadow_mismatch(tool: str, detail: str) -> None:
    with _lock:
        _counters.shadow_mismatches += 1
    _log.info(
        "mcp_shadow_mismatch tool=%s detail=%s",
        tool,
        (detail or "")[:200],
    )
