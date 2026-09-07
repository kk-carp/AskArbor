"""学习路径：近期提问 → 薄弱点 → 课内召回 + 课外搜索。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from backend.config import settings
from backend.domain.companion import require_companion_spaces
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.infra.embed import encode_query, is_loaded
from backend.infra.generate import complete_chat
from backend.infra.open_resource import (
    ExternalResource,
    SearchTimeoutError,
    SearchUnavailableError,
    search_open_resources,
)
from backend.infra.retrieve import search_chunks
from backend.schemas import CourseRecommendation, ExternalRecommendation
from backend.services.conversation_service import list_recent_user_questions

_audit_logger = logging.getLogger("backend.audit")
_URL_RE = re.compile(r"https?://\S+", re.I)


@dataclass(frozen=True)
class LearningPathResult:
    weak_points: list[str]
    course: list[CourseRecommendation]
    external: list[ExternalRecommendation]
    error_type: str | None = None
    message: str | None = None
    from_cache: bool = False


# 进程内按用户缓存；无 Redis。进页读缓存，显式 refresh 才重建。
_path_cache: dict[str, LearningPathResult] = {}


def clear_learning_path_cache() -> None:
    """测试或热重载时清空缓存。"""
    _path_cache.clear()


def get_learning_path(
    *,
    user_id: str,
    allowed_spaces: list[str],
    refresh: bool = False,
) -> LearningPathResult:
    """默认返回该用户缓存；refresh=True 或无缓存时重新生成并写入。"""
    require_companion_spaces(allowed_spaces)
    if not refresh:
        cached = _path_cache.get(user_id)
        if cached is not None:
            return LearningPathResult(
                weak_points=cached.weak_points,
                course=list(cached.course),
                external=list(cached.external),
                error_type=cached.error_type,
                message=cached.message,
                from_cache=True,
            )
    result = build_learning_path(user_id=user_id, allowed_spaces=allowed_spaces)
    _path_cache[user_id] = result
    return LearningPathResult(
        weak_points=result.weak_points,
        course=list(result.course),
        external=list(result.external),
        error_type=result.error_type,
        message=result.message,
        from_cache=False,
    )


def strip_urls(text: str) -> str:
    return _URL_RE.sub("", text or "").strip()


def parse_topic_list(raw: str) -> list[str]:
    text = (raw or "").strip()
    data: object
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if match is None:
            topics: list[str] = []
            for line in text.splitlines():
                cleaned = strip_urls(line.lstrip("-* ").strip())
                if cleaned and "://" not in cleaned:
                    topics.append(cleaned)
                if len(topics) >= 5:
                    break
            return topics
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    topics = []
    for item in data:
        if not isinstance(item, str):
            continue
        cleaned = strip_urls(item)
        if cleaned and "://" not in cleaned:
            topics.append(cleaned)
        if len(topics) >= 5:
            break
    return topics


def _summarize_weak_points(questions: list[str]) -> list[str]:
    cleaned = [strip_urls(item) for item in questions]
    cleaned = [item for item in cleaned if item]
    fallback = cleaned[:5]
    prompt = (
        "根据下列学员近期提问，归纳最多 3 个薄弱知识点。"
        "只输出 JSON 字符串数组，例如 [\"动态规划\"]。"
        "不要输出 URL、广告或外链。\n\n"
        + "\n".join(f"- {item}" for item in cleaned[:20])
    )
    try:
        raw = complete_chat(
            [
                {"role": "system", "content": "只输出 JSON 数组。禁止输出链接。"},
                {"role": "user", "content": prompt},
            ]
        )
    except UpstreamServiceError:
        return fallback
    topics = parse_topic_list(raw)
    return topics or fallback


def _retrieve_course(weak_points: list[str]) -> list[CourseRecommendation]:
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")
    query = " ".join(weak_points).strip()[:500]
    if not query:
        return []
    query_vector = encode_query(query)
    retrieved = search_chunks(
        query_vector=query_vector,
        allowed_spaces=["student"],
        top_k=settings.retrieve_top_k,
    )
    course: list[CourseRecommendation] = []
    seen: set[str] = set()
    for item in retrieved:
        if item.score < settings.retrieve_min_score:
            continue
        if item.space_id != "student":
            continue
        key = str(item.document_id)
        if key in seen:
            continue
        seen.add(key)
        course.append(
            CourseRecommendation(
                document_id=item.document_id,
                title=item.title,
                space_id="student",
                path=item.path,
            )
        )
        if len(course) >= 8:
            break
    return course


def build_learning_path(*, user_id: str, allowed_spaces: list[str]) -> LearningPathResult:
    spaces = require_companion_spaces(allowed_spaces)
    _ = spaces
    questions = list_recent_user_questions(
        user_id=user_id,
        limit=settings.learning_path_recent_questions,
    )
    if not questions:
        _audit_logger.info(
            "learning-path user_id=%s error=%s docs=%s",
            user_id,
            "empty_history",
            "",
        )
        return LearningPathResult(
            weak_points=[],
            course=[],
            external=[],
            message="提问记录不足，暂无法识别薄弱点",
        )

    weak_points = _summarize_weak_points(questions)
    course = _retrieve_course(weak_points)

    error_type: str | None = None
    external_items: list[ExternalResource] = []
    try:
        external_items = search_open_resources(weak_points)
    except SearchTimeoutError:
        error_type = "search_timeout"
    except SearchUnavailableError:
        error_type = "search_unavailable"

    external = [
        ExternalRecommendation(
            title=item.title,
            url=item.url,
            host=item.host,
            kind=item.kind,
            snippet=item.snippet,
        )
        for item in external_items
    ]

    message: str | None = None
    if error_type == "search_timeout":
        message = "课外搜索超时，课内推荐仍可用" if course else "课外搜索超时，课程空间暂无可推荐资料"
    elif error_type == "search_unavailable":
        message = "课外搜索暂不可用，课内推荐仍可用" if course else "课外搜索暂不可用，课程空间暂无可推荐资料"
    elif not course and not external:
        message = "没有可推荐资料"
    elif not course:
        message = "课程空间暂无可推荐资料"

    _audit_logger.info(
        "learning-path user_id=%s error=%s docs=%s paths=%s",
        user_id,
        error_type or "ok",
        ",".join(str(item.document_id) for item in course),
        ",".join(item.path or "" for item in course),
    )
    return LearningPathResult(
        weak_points=weak_points,
        course=course,
        external=external,
        error_type=error_type,
        message=message,
    )
