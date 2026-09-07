"""搜索源：工具契约与注册表、站点响应解析、受限出网。"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from backend.config import settings
from backend.infra.open_resource.policy import (
    SEARCH_REQUEST_HOSTS,
    TAG_RE,
    normalize_host,
)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

_HREF_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)


class SearchTimeoutError(RuntimeError):
    """课外搜索超时。"""


class SearchUnavailableError(RuntimeError):
    """课外搜索不可用。"""


@dataclass(frozen=True)
class SearchTool:
    """可注册搜索工具：按 query 构 URL，再把响应解析为 hits。"""

    name: str
    build_url: Callable[[str], str]
    parse: Callable[[str], list[dict[str, str]]]


_registered_tools: list[SearchTool] = []


def register_search_tool(tool: SearchTool) -> None:
    """注册或覆盖同名搜索工具。"""
    kept = [item for item in _registered_tools if item.name != tool.name]
    _registered_tools[:] = [*kept, tool]


def clear_search_tools() -> None:
    _registered_tools.clear()


def list_search_tools() -> list[SearchTool]:
    return list(_registered_tools)


def unwrap_result_url(href: str) -> str | None:
    raw = html.unescape((href or "").strip())
    if not raw:
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = normalize_host(parsed.hostname)
    if host.endswith("duckduckgo.com") and "/l/" in (parsed.path or ""):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if not target:
            return None
        return unquote(target)
    return raw


def parse_arxiv_atom(xml_text: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return hits
    for entry in root.findall("atom:entry", ATOM_NS):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").split())
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").split())
        url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href") or ""
            if link.attrib.get("rel") == "alternate" or link.attrib.get("type") == "text/html":
                url = href
                break
        if not url:
            entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS) or ""
            url = entry_id.replace("http://", "https://", 1)
        if url:
            hits.append({"title": title or url, "url": url, "snippet": summary})
    return hits


def parse_duckduckgo_html(html_text: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for href, inner in _HREF_RE.findall(html_text or ""):
        url = unwrap_result_url(href)
        if not url:
            continue
        title = TAG_RE.sub("", inner)
        title = html.unescape(" ".join(title.split()))
        hits.append({"title": title or url, "url": url, "snippet": ""})
    return hits


def fetch_search_text(url: str) -> str:
    """仅允许向搜索端点发 GET；禁止跟随重定向、禁止客户端任意 URL。"""
    parsed = urlparse(url)
    host = normalize_host(parsed.hostname)
    if parsed.scheme != "https" or host not in SEARCH_REQUEST_HOSTS:
        raise SearchUnavailableError("搜索请求主机不在允许名单")
    if parsed.username or parsed.password:
        raise SearchUnavailableError("搜索请求主机不在允许名单")
    timeout = settings.learning_path_search_timeout_seconds
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(
                url,
                headers={"User-Agent": "FDE-learning-path/1.0"},
            )
    except httpx.TimeoutException as exc:
        raise SearchTimeoutError("课外搜索超时") from exc
    except httpx.HTTPError as exc:
        raise SearchUnavailableError("课外搜索不可用") from exc
    if response.status_code >= 400:
        raise SearchUnavailableError("课外搜索不可用")
    return response.text


def default_search_tools() -> list[SearchTool]:
    return [
        SearchTool(
            name="arxiv",
            build_url=lambda encoded: (
                "https://export.arxiv.org/api/query"
                f"?search_query=all:{encoded}&start=0&max_results=5"
            ),
            parse=parse_arxiv_atom,
        ),
        SearchTool(
            name="duckduckgo",
            build_url=lambda encoded: f"https://html.duckduckgo.com/html/?q={encoded}",
            parse=parse_duckduckgo_html,
        ),
    ]


def reset_default_search_tools() -> None:
    clear_search_tools()
    for tool in default_search_tools():
        register_search_tool(tool)
