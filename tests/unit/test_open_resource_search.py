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
    parse_tavily_results,
    reset_default_search_tools,
    register_search_tool,
    search_open_resources,
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

TAVILY_PAYLOAD = {
    "results": [
        {
            "title": "Paper",
            "url": "https://arxiv.org/abs/1706.03762",
            "content": "Transformer",
        },
        {
            "title": "Udemy ML",
            "url": "https://www.udemy.com/course/ml",
            "content": "paid",
        },
        {
            "title": "PyTorch",
            "url": "https://github.com/pytorch/pytorch",
            "content": "oss",
        },
        {
            "title": "Evil",
            "url": "https://evil.example/x",
            "content": "bad",
        },
    ]
}


@pytest.fixture(autouse=True)
def _init_default_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources_mod.settings, "tavily_api_key", "tvly-test")
    init_open_resource_search_tools()


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


def test_parse_arxiv_and_tavily() -> None:
    papers = parse_arxiv_atom(ARXIV_XML)
    assert papers[0]["url"] == "https://arxiv.org/abs/1706.03762"
    web = parse_tavily_results(TAVILY_PAYLOAD)
    urls = [item["url"] for item in web]
    assert "https://arxiv.org/abs/1706.03762" in urls
    assert "https://www.udemy.com/course/ml" in urls
    assert "https://github.com/pytorch/pytorch" in urls
    assert "https://evil.example/x" in urls


def test_search_open_resources_merges_arxiv_and_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sources_mod,
        "run_arxiv_search",
        lambda _q, **_k: parse_arxiv_atom(ARXIV_XML),
    )
    monkeypatch.setattr(
        sources_mod,
        "run_tavily_search",
        lambda _q, **_k: parse_tavily_results(TAVILY_PAYLOAD),
    )
    reset_default_search_tools()

    results = search_open_resources(["attention is all you need"])
    urls = [item.url for item in results]
    assert "https://arxiv.org/abs/1706.03762" in urls
    assert "https://github.com/pytorch/pytorch" in urls
    assert all("udemy" not in item.url for item in results)
    assert all("evil.example" not in item.url for item in results)


def test_fetch_search_text_rejects_arbitrary_url() -> None:
    with pytest.raises(SearchUnavailableError):
        sources_mod.fetch_search_text("http://evil.example/x")


def test_tavily_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources_mod.settings, "tavily_api_key", "")
    with pytest.raises(SearchUnavailableError):
        sources_mod.run_tavily_search("numpy")


def test_tavily_posts_only_to_api_host(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _post(body: dict, *, api_key: str, timeout: float) -> object:
        seen["api_key"] = api_key
        seen["timeout"] = timeout
        seen["include"] = body.get("include_domains")
        seen["exclude"] = body.get("exclude_domains")
        return TAVILY_PAYLOAD

    monkeypatch.setattr(sources_mod.settings, "tavily_api_key", "tvly-test")
    hits = sources_mod.run_tavily_search("pytorch", post=_post)
    assert seen["api_key"] == "tvly-test"
    assert "github.com" in (seen["include"] or [])
    assert "udemy.com" in (seen["exclude"] or [])
    assert any(item["url"].startswith("https://github.com/") for item in hits)


def test_search_keeps_arxiv_when_tavily_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sources_mod,
        "run_arxiv_search",
        lambda _q, **_k: parse_arxiv_atom(ARXIV_XML),
    )

    def _boom(_q: str, **_k):
        raise httpx.HTTPError("tavily down")

    monkeypatch.setattr(sources_mod, "run_tavily_search", _boom)
    reset_default_search_tools()

    results = search_open_resources(["RAG概念"])
    assert [item.url for item in results] == ["https://arxiv.org/abs/1706.03762"]


def test_search_timeout_maps_to_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="boom",
            run=lambda _q: (_ for _ in ()).throw(httpx.TimeoutException("timeout")),
        )
    )
    with pytest.raises(SearchTimeoutError):
        search_open_resources(["dp"])


def test_search_http_error_maps_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="boom",
            run=lambda _q: (_ for _ in ()).throw(httpx.HTTPError("down")),
        )
    )
    with pytest.raises(SearchUnavailableError):
        search_open_resources(["dp"])


def test_search_open_resources_supports_registered_tools() -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="custom",
            run=lambda _q: [
                {
                    "title": "NumPy Docs",
                    "url": "https://numpy.org/doc/stable/",
                    "snippet": "array basics",
                }
            ],
        )
    )
    results = search_open_resources(["numpy array"])
    assert [item.url for item in results] == ["https://numpy.org/doc/stable/"]


def test_reset_default_search_tools_restores_arxiv_and_tavily() -> None:
    clear_search_tools()
    register_search_tool(
        SearchTool(
            name="temp",
            run=lambda _q: [],
        )
    )
    reset_default_search_tools()
    names = {item.name for item in list_search_tools()}
    assert names == {"arxiv", "tavily"}


def test_registry_mutates_in_place_so_module_references_stay_valid() -> None:
    registry = sources_mod._registered_tools
    clear_search_tools()
    register_search_tool(SearchTool(name="temp", run=lambda _q: []))
    assert [item.name for item in registry] == ["temp"]
    reset_default_search_tools()
    assert {item.name for item in registry} == {"arxiv", "tavily"}
