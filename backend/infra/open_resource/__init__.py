"""课外开源/免费资料搜索：只请求白名单搜索主机，结果再过展示白名单。"""

from backend.infra.open_resource.bootstrap import init_open_resource_search_tools
from backend.infra.open_resource.policy import (
    ExternalResource,
    classify_kind,
    filter_search_hits,
    normalize_host,
)
from backend.infra.open_resource.search import search_open_resources
from backend.infra.open_resource.sources import (
    SearchTimeoutError,
    SearchTool,
    SearchUnavailableError,
    clear_search_tools,
    fetch_search_text,
    list_search_tools,
    parse_arxiv_atom,
    parse_duckduckgo_html,
    register_search_tool,
    reset_default_search_tools,
    unwrap_result_url,
)

__all__ = [
    "ExternalResource",
    "SearchTimeoutError",
    "SearchTool",
    "SearchUnavailableError",
    "classify_kind",
    "clear_search_tools",
    "fetch_search_text",
    "filter_search_hits",
    "init_open_resource_search_tools",
    "list_search_tools",
    "normalize_host",
    "parse_arxiv_atom",
    "parse_duckduckgo_html",
    "register_search_tool",
    "reset_default_search_tools",
    "search_open_resources",
    "unwrap_result_url",
]
