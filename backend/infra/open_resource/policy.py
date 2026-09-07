"""课外资料准入策略：请求主机名单、展示主机名单、屏蔽规则与结果归一化。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from backend.config import settings

SEARCH_REQUEST_HOSTS = frozenset({"export.arxiv.org"})

ALLOWED_RESULT_HOSTS = frozenset(
    {
        "arxiv.org",
        "export.arxiv.org",
        "github.com",
        "huggingface.co",
        "paperswithcode.com",
        "wikipedia.org",
        "zh.wikipedia.org",
        "en.wikipedia.org",
        "docs.python.org",
        "pytorch.org",
        "numpy.org",
        "scikit-learn.org",
        "cppreference.com",
        "developer.mozilla.org",
        "readthedocs.io",
    }
)

DEFAULT_BLOCK_HOSTS = frozenset(
    {
        "udemy.com",
        "coursera.org",
        "edx.org",
        "imooc.com",
        "study.163.com",
        "ke.qq.com",
        "time.geekbang.org",
    }
)

DEFAULT_BLOCK_KEYWORDS = (
    "训练营",
    "付费课",
    "vip 课",
    "vip课",
    "会员课",
    "就业班",
    "名额",
    "报名立减",
)

TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class ExternalResource:
    title: str
    url: str
    host: str
    kind: str
    snippet: str


def _split_csv(value: str) -> list[str]:
    return [part.strip().lower() for part in (value or "").split(",") if part.strip()]


def normalize_host(host: str | None) -> str:
    if not host:
        return ""
    return host.lower().removeprefix("www.").rstrip(".")


def _host_allowed(host: str) -> bool:
    if host in ALLOWED_RESULT_HOSTS:
        return True
    if host.endswith(".readthedocs.io"):
        return True
    return False


def _is_blocked(title: str, url: str, snippet: str, host: str) -> bool:
    extra_hosts = {normalize_host(item) for item in _split_csv(settings.learning_path_block_hosts)}
    if host in DEFAULT_BLOCK_HOSTS or host in extra_hosts:
        return True
    blob = f"{title} {url} {snippet}".lower()
    keywords = list(DEFAULT_BLOCK_KEYWORDS) + _split_csv(settings.learning_path_block_keywords)
    return any(keyword in blob for keyword in keywords)


def classify_kind(host: str) -> str:
    if host in {"arxiv.org", "export.arxiv.org"}:
        return "paper"
    if host in {"github.com", "huggingface.co"}:
        return "oss"
    return "docs"


def filter_search_hits(hits: list[dict[str, str]]) -> list[ExternalResource]:
    """只保留白名单主机；丢掉收费课/训练营/对标配置。不请求 hit 里的 URL。"""
    results: list[ExternalResource] = []
    seen: set[str] = set()
    for hit in hits:
        url = (hit.get("url") or "").strip()
        title = TAG_RE.sub("", hit.get("title") or "").strip() or url
        snippet = (hit.get("snippet") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.username or parsed.password:
            continue
        host = normalize_host(parsed.hostname)
        if not host or not _host_allowed(host):
            continue
        if _is_blocked(title, url, snippet, host):
            continue
        if url in seen:
            continue
        seen.add(url)
        results.append(
            ExternalResource(
                title=title[:200],
                url=url,
                host=host,
                kind=classify_kind(host),
                snippet=snippet[:300],
            )
        )
    return results
