"""搜索源：工具契约与注册表、arXiv / Tavily 适配器、受限出网。"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote, urlparse

import httpx

from backend.config import settings
from backend.infra.open_resource.policy import (
    ALLOWED_RESULT_HOSTS,
    DEFAULT_BLOCK_HOSTS,
    SEARCH_REQUEST_HOSTS,
    normalize_host,
)

_logger = logging.getLogger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class SearchTimeoutError(RuntimeError):
    """课外搜索超时。"""


class SearchUnavailableError(RuntimeError):
    """课外搜索不可用。"""


@dataclass(frozen=True)
class SearchTool:
    """可注册搜索工具：输入明文 query，返回 title/url/snippet hits。"""

    name: str
    run: Callable[[str], list[dict[str, str]]]


_registered_tools: list[SearchTool] = []


def register_search_tool(tool: SearchTool) -> None:
    """注册或覆盖同名搜索工具。"""
    kept = [item for item in _registered_tools if item.name != tool.name]
    _registered_tools[:] = [*kept, tool]


def clear_search_tools() -> None:
    _registered_tools.clear()


def list_search_tools() -> list[SearchTool]:
    return list(_registered_tools)


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


def parse_tavily_results(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []
    hits: list[dict[str, str]] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return hits
    for item in results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = str(item.get("title") or "").strip() or url
        snippet = str(item.get("content") or "").strip()
        hits.append({"title": title, "url": url, "snippet": snippet})
    return hits


def fetch_search_text(url: str) -> str:
    """仅允许向已登记搜索端点发 GET；禁止跟随重定向、禁止客户端任意 URL。"""
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
                headers={"User-Agent": "FDE-open-resource/1.0"},
            )
    except httpx.TimeoutException as exc:
        raise SearchTimeoutError("课外搜索超时") from exc
    except httpx.HTTPError as exc:
        raise SearchUnavailableError("课外搜索不可用") from exc
    if response.status_code >= 400:
        raise SearchUnavailableError("课外搜索不可用")
    return response.text


def run_arxiv_search(query: str, *, fetch=None) -> list[dict[str, str]]:
    text = (query or "").strip()
    if not text:
        return []
    encoded = quote(text)
    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query=all:{encoded}&start=0&max_results=5"
    )
    fetch_fn = fetch or fetch_search_text
    return parse_arxiv_atom(fetch_fn(url))


def run_tavily_search(query: str, *, post=None) -> list[dict[str, str]]:
    """调用 Tavily Search；不抓取任意用户 URL，结果仍须过展示白名单。"""
    text = (query or "").strip()
    if not text:
        return []
    api_key = (settings.tavily_api_key or "").strip()
    if not api_key:
        raise SearchUnavailableError("课外搜索不可用")

    extra_block = [
        part.strip().lower()
        for part in (settings.learning_path_block_hosts or "").split(",")
        if part.strip()
    ]
    exclude_domains = sorted({normalize_host(item) for item in DEFAULT_BLOCK_HOSTS | set(extra_block) if item})
    include_domains = sorted(ALLOWED_RESULT_HOSTS)
    body = {
        "query": text,
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_domains": include_domains,
        "exclude_domains": exclude_domains,
    }
    timeout = settings.learning_path_search_timeout_seconds
    post_fn = post or _post_tavily_json
    try:
        payload = post_fn(body, api_key=api_key, timeout=timeout)
    except SearchTimeoutError:
        raise
    except SearchUnavailableError:
        raise
    except httpx.TimeoutException as exc:
        raise SearchTimeoutError("课外搜索超时") from exc
    except httpx.HTTPError as exc:
        raise SearchUnavailableError("课外搜索不可用") from exc
    return parse_tavily_results(payload)


def _post_tavily_json(body: dict, *, api_key: str, timeout: float) -> object:
    parsed = urlparse(TAVILY_SEARCH_URL)
    host = normalize_host(parsed.hostname)
    if parsed.scheme != "https" or host != "api.tavily.com":
        raise SearchUnavailableError("搜索请求主机不在允许名单")
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.post(
                TAVILY_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "FDE-open-resource/1.0",
                },
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise SearchTimeoutError("课外搜索超时") from exc
    except httpx.HTTPError as exc:
        raise SearchUnavailableError("课外搜索不可用") from exc
    if response.status_code >= 400:
        _logger.warning("tavily search failed status=%s", response.status_code)
        raise SearchUnavailableError("课外搜索不可用")
    try:
        return response.json()
    except ValueError as exc:
        raise SearchUnavailableError("课外搜索不可用") from exc


def default_search_tools() -> list[SearchTool]:
    return [
        SearchTool(name="arxiv", run=run_arxiv_search),
        SearchTool(name="tavily", run=run_tavily_search),
    ]


def reset_default_search_tools() -> None:
    clear_search_tools()
    for tool in default_search_tools():
        register_search_tool(tool)
