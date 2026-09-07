"""课外搜索编排：薄弱点关键词 × 已注册工具，失败归类为超时或不可用。"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx

from backend.infra.open_resource.policy import ExternalResource, filter_search_hits
from backend.infra.open_resource.sources import (
    SearchTimeoutError,
    SearchTool,
    SearchUnavailableError,
    fetch_search_text,
    list_search_tools,
)

_logger = logging.getLogger(__name__)


def _query_variants(query: str) -> list[str]:
    text = (query or "").strip()
    if not text:
        return []
    variants = [text]
    latin = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9+\-]{1,}", text))
    if latin and latin.casefold() not in {text.casefold()}:
        variants.append(latin)
    return variants


def search_open_resources(queries: list[str], *, fetch=None) -> list[ExternalResource]:
    """按薄弱点关键词检索已注册搜索工具，过滤后再返回。"""
    fetch_fn = fetch or fetch_search_text
    raw_hits: list[dict[str, str]] = []
    timed_out = False
    unavailable = False

    def _try_fetch(tool: SearchTool, encoded_query: str) -> None:
        nonlocal timed_out, unavailable
        try:
            raw_hits.extend(tool.parse(fetch_fn(tool.build_url(encoded_query))))
        except SearchTimeoutError:
            timed_out = True
        except SearchUnavailableError:
            unavailable = True
        except httpx.TimeoutException:
            timed_out = True
        except httpx.HTTPError:
            unavailable = True

    try:
        seen_q: set[str] = set()
        for query in queries[:3]:
            for variant in _query_variants(query):
                if variant in seen_q:
                    continue
                seen_q.add(variant)
                encoded = quote(variant)
                for tool in list_search_tools():
                    _try_fetch(tool, encoded)
    except Exception as exc:
        _logger.warning("open resource search failed: %s", exc)
        raise SearchUnavailableError("课外搜索不可用") from exc

    results = filter_search_hits(raw_hits)[:8]
    if results:
        return results
    if timed_out:
        raise SearchTimeoutError("课外搜索超时")
    if unavailable:
        raise SearchUnavailableError("课外搜索不可用")
    return []
