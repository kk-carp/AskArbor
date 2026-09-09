"""薄弱点归纳：近期提问 → 知识性主题列表（供进阶资料推荐等学伴能力共用）。"""

from __future__ import annotations

import json
import re

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


def strip_urls(text: str) -> str:
    return _URL_RE.sub("", text or "").strip()


def is_transactional_question(text: str) -> bool:
    """作业截止、提交方式等事务/教务问题不算知识薄弱点。"""
    cleaned = strip_urls(text)
    if not cleaned:
        return False
    return _TRANSACTIONAL_RE.search(cleaned) is not None


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
                if cleaned and "://" not in cleaned and not is_transactional_question(cleaned):
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
        if cleaned and "://" not in cleaned and not is_transactional_question(cleaned):
            topics.append(cleaned)
        if len(topics) >= 5:
            break
    return topics


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
        "只输出 JSON 字符串数组，例如 [\"动态规划\"]。"
        "不要输出 URL、广告或外链。\n\n"
        + "\n".join(f"- {item}" for item in cleaned[:20])
    )
    try:
        raw = complete_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "只输出 JSON 字符串数组。"
                        "只含知识薄弱点；禁止事务性教务问题；禁止链接。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
    except UpstreamServiceError:
        return fallback
    topics = parse_topic_list(raw)
    return topics or fallback
