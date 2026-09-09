"""薄弱点归纳：近期提问 → 知识性主题列表（供进阶资料推荐等学伴能力共用）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.errors import UpstreamServiceError
from backend.infra.generate import complete_chat

_URL_RE = re.compile(r"https?://\S+", re.I)
# 教务/事务性提问：不作为知识薄弱点（归纳与兜底都排除）
_TRANSACTIONAL_RE = re.compile(
    r"("
    r"截止|截止日期|截止时间|提交方式|怎么交|如何交|交作业|作业提交|提交作业|"
    r"上课时间|上课地点|考试时间|考试地点|教室|学分|成绩查询|请假|报名|"
    r"开课|结课|调课|补交|延期|班主任|教务|"
    r"deadline|due\s*date|how\s*to\s*submit|submit\s+(the\s+)?(homework|assignment|work)|"
    r"where\s+to\s+submit|when\s+is\s+(the\s+)?(homework|assignment)\s+due"
    r")",
    re.I,
)
_MAX_TOPICS = 3
_SCHEMA_RULE = (
    "只输出 JSON 字符串数组，最多 3 项，例如 [\"动态规划\"]。"
    "不要 Markdown、对象、URL 或说明文字。"
    "只含知识薄弱点；禁止事务性教务问题。"
)
_REPAIR_USER = (
    "上次输出不符合 schema：必须是 JSON 字符串数组，例如 [\"动态规划\"]。"
    "不要 Markdown、对象或其它文字。没有知识薄弱点时输出 []。"
)


@dataclass(frozen=True)
class TopicSchemaResult:
    topics: list[str]
    schema_ok: bool


def strip_urls(text: str) -> str:
    return _URL_RE.sub("", text or "").strip()


def is_transactional_question(text: str) -> bool:
    """作业截止、提交方式等事务/教务问题不算知识薄弱点。"""
    cleaned = strip_urls(text)
    if not cleaned:
        return False
    return _TRANSACTIONAL_RE.search(cleaned) is not None


def _sanitize_topic(item: object) -> str | None:
    if not isinstance(item, str):
        return None
    cleaned = strip_urls(item)
    if not cleaned or "://" in cleaned or is_transactional_question(cleaned):
        return None
    return cleaned


def _parse_json_array(text: str) -> list[object] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if match is None:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, list) else None


def parse_topic_schema(raw: str) -> TopicSchemaResult:
    """校验模型输出是否为 JSON 字符串数组；非法 JSON / 非数组视为 schema 失败。"""
    text = (raw or "").strip()
    if not text:
        return TopicSchemaResult(topics=[], schema_ok=False)
    data = _parse_json_array(text)
    if data is None:
        return TopicSchemaResult(topics=[], schema_ok=False)
    topics: list[str] = []
    for item in data:
        cleaned = _sanitize_topic(item)
        if cleaned:
            topics.append(cleaned)
        if len(topics) >= _MAX_TOPICS:
            break
    return TopicSchemaResult(topics=topics, schema_ok=True)


def parse_topic_list(raw: str) -> list[str]:
    return parse_topic_schema(raw).topics


def _complete_text(messages: list[dict[str, str]]) -> str | None:
    try:
        return complete_chat(messages).text
    except UpstreamServiceError:
        return None


def summarize_weak_points(questions: list[str]) -> list[str]:
    cleaned = [strip_urls(item) for item in questions]
    cleaned = [item for item in cleaned if item]
    knowledge_questions = [item for item in cleaned if not is_transactional_question(item)]
    if not knowledge_questions:
        return []
    fallback = knowledge_questions[:5]
    prompt = (
        "根据下列学员近期提问，归纳最多 3 个知识性薄弱点（概念、算法、代码、原理、公式等）。"
        "必须忽略事务性/教务类提问，例如：作业截止时间、提交方式、上课或考试时间地点、"
        "请假报名、联系班主任、成绩学分等；这些不能出现在结果中。"
        "若没有可归纳的知识性问题，输出空数组 []。"
        f"{_SCHEMA_RULE}\n\n"
        + "\n".join(f"- {item}" for item in cleaned[:20])
    )
    messages = [
        {"role": "system", "content": _SCHEMA_RULE},
        {"role": "user", "content": prompt},
    ]
    raw = _complete_text(messages)
    if raw is None:
        return fallback
    parsed = parse_topic_schema(raw)
    if not parsed.schema_ok:
        repair = [
            *messages,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": _REPAIR_USER},
        ]
        raw = _complete_text(repair)
        if raw is None:
            return fallback
        parsed = parse_topic_schema(raw)
        if not parsed.schema_ok:
            return fallback
    return parsed.topics or fallback
