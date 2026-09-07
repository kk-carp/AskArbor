from urllib.parse import urlparse

import httpx
import pytest

from backend.infra.open_resource import policy as policy_mod
from backend.infra.open_resource import sources as sources_mod
from backend.infra.open_resource import (
    SearchTool,
    SearchTimeoutError,
    SearchUnavailableError,
    clear_search_tools,
    filter_search_hits,
    init_open_resource_search_tools,
    list_search_tools,
    parse_arxiv_atom,
    parse_duckduckgo_html,
    reset_default_search_tools,
    register_search_tool,
    search_open_resources,
    unwrap_result_url,
)


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <summary>Transformer architecture.</summary>
    <link href="https://arxiv.org/abs/1706.03762" rel="alternate" type="text/html"/>
  </entry>
</feed>
"""

DDG_HTML = """
<html><body>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F1706.03762">Paper</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.udemy.com%2Fcourse%2Fml">Udemy ML</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Fpytorch%2Fpytorch">PyTorch</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fevil.example%2Fx">Evil</a>
</body></html>
"""


@pytest.fixture(autouse=True)
def _init_default_tools() -> None:
    init_open_resource_search_tools()


def test_unwrap_ddg_redirect_extracts_target() -> None:
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Ffoo%2Fbar"
    assert unwrap_result_url(href) == "https://github.com/foo/bar"


def test_filter_keeps_allowlist_drops_udemy_bootcamp_and_unknown_host() -> None:
    hits = [
        {"title": "Attention", "url": "https://arxiv.org/abs/1706.03762", "snippet": "paper"},
        {"title": "Python 训练营报名", "url": "https://github.com/foo/camp", "snippet": ""},
        {"title": "Paid course", "url": "https://www.udemy.com/course/x", "snippet": ""},
        {"title": "Tutorial", "url": "https://docs.python.org/3/tutorial/", "snippet": ""},
        {"title": "Internal", "url": "http://evil.example/x", "snippet": ""},
    ]
    result = filter_search_hits(hits)
    urls = [item.url for item in result]
    assert "https://arxiv.org/abs/1706.03762" in urls
    assert "https://docs.python.org/3/tutorial/" in urls
    assert all("udemy" not in item.url for item in result)
    assert all("训练营" not in item.title for item in result)
    assert all("evil.example" not in item.url for item in result)
    assert all(item.host in {"arxiv.org", "docs.python.org"} for item in result)


def test_filter_applies_extra_block_hosts_and_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_mod.settings, "learning_path_block_hosts", "huggingface.co")
    monkeypatch.setattr(policy_mod.settings, "learning_path_block_keywords", "对标特训")
    hits = [
        {"title": "Docs", "url": "https://github.com/foo/bar", "snippet": "对标特训 大纲"},
        {"title": "Other", "url": "https://huggingface.co/models/x", "snippet": "readme"},
        {"title": "Ok", "url": "https://github.com/ok/ok", "snippet": "source code"},
    ]
    result = filter_search_hits(hits)
    assert [item.url for item in result] == ["https://github.com/ok/ok"]


def test_parse_arxiv_and_duckduckgo() -> None:
    papers = parse_arxiv_atom(ARXIV_XML)
    assert papers[0]["url"] == "https://arxiv.org/abs/1706.03762"
    web = parse_duckduckgo_html(DDG_HTML)
    urls = [item["url"] for item in web]
    assert "https://arxiv.org/abs/1706.03762" in urls
    assert "https://www.udemy.com/course/ml" in urls
    assert "https://github.com/pytorch/pytorch" in urls
    assert "https://evil.example/x" in urls


def test_search_open_resources_only_requests_allowlisted_hosts() -> None:
    requested: list[str] = []

    def _fetch(url: str) -> str:
        requested.append(url)
        host = (urlparse(url).hostname or "")
        assert host in {"export.arxiv.org", "html.duckduckgo.com"}
        if host == "export.arxiv.org":
            return ARXIV_XML
        return DDG_HTML

    results = search_open_resources(["attention is all you need"], fetch=_fetch)
    assert requested
    assert all(urlparse(url).hostname in {"export.arxiv.org", "html.duckduckgo.com"} for url in requested)
    assert all(not url.startswith("http://evil") for url in requested)
    urls = [item.url for item in results]
    assert "https://arxiv.org/abs/1706.03762" in urls
    assert "https://github.com/pytorch/pytorch" in urls
    assert all("udemy" not in item.url for item in results)
    assert all("evil.example" not in item.url for item in results)


def test_fetch_search_text_rejects_arbitrary_url() -> None:
    with pytest.raises(SearchUnavailableError):
        sources_mod.fetch_search_text("http://evil.example/x")


def test_search_keeps_arxiv_when_duckduckgo_fails() -> None:
    def _fetch(url: str) -> str:
        host = urlparse(url).hostname or ""
        if host == "export.arxiv.org":
            return ARXIV_XML
        raise httpx.HTTPError("ddg down")

    results = search_open_resources(["RAG概念"], fetch=_fetch)
    assert [item.url for item in results] == ["https://arxiv.org/abs/1706.03762"]


def test_search_timeout_maps_to_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_url: str) -> str:
        raise httpx.TimeoutException("timeout")

    with pytest.raises(SearchTimeoutError):
        search_open_resources(["dp"], fetch=_boom)


def test_search_http_error_maps_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_url: str) -> str:
        raise httpx.HTTPError("down")

    with pytest.raises(SearchUnavailableError):
        search_open_resources(["dp"], fetch=_boom)


def test_search_open_resources_supports_registered_tools() -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="custom",
            build_url=lambda encoded: f"https://export.arxiv.org/api/query?q={encoded}",
            parse=lambda _text: [
                {
                    "title": "NumPy Docs",
                    "url": "https://numpy.org/doc/stable/",
                    "snippet": "array basics",
                }
            ],
        )
    )

    def _fetch(url: str) -> str:
        assert "export.arxiv.org" in url
        return "ignored"

    results = search_open_resources(["numpy array"], fetch=_fetch)
    assert [item.url for item in results] == ["https://numpy.org/doc/stable/"]


def test_reset_default_search_tools_restores_arxiv_and_duckduckgo() -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="temp",
            build_url=lambda encoded: f"https://export.arxiv.org/api/query?q={encoded}",
            parse=lambda _text: [],
        )
    )
    reset_default_search_tools()
    names = {item.name for item in list_search_tools()}
    assert names == {"arxiv", "duckduckgo"}


def test_registry_mutates_in_place_so_module_references_stay_valid() -> None:
    registry = sources_mod._registered_tools
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="temp",
            build_url=lambda encoded: f"https://export.arxiv.org/api/query?q={encoded}",
            parse=lambda _text: [],
        )
    )
    assert [item.name for item in registry] == ["temp"]
    reset_default_search_tools()
    assert {item.name for item in registry} == {"arxiv", "duckduckgo"}
