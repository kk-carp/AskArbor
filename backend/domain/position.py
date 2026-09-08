"""岗位标识与入职类问句：仅用于检索 query 轻量增强。"""

from __future__ import annotations

# 第一期已知岗位；未知 key 不拼接，避免噪声。
POSITION_LABELS: dict[str, str] = {
    "algo_engineer": "算法工程师",
}

ONBOARDING_MARKERS: tuple[str, ...] = (
    "入职",
    "新人",
    "报到",
    "onboarding",
    "入职指南",
    "入职资料",
    "先看什么",
    "要看哪些资料",
    "要看什么资料",
)


def position_label(position_key: str | None) -> str | None:
    key = (position_key or "").strip()
    if not key:
        return None
    return POSITION_LABELS.get(key)


def is_onboarding_question(question: str) -> bool:
    text = (question or "").strip().lower()
    if not text:
        return False
    for marker in ONBOARDING_MARKERS:
        if marker.lower() in text:
            return True
    return False


def boost_retrieval_query(question: str, position_key: str | None) -> str:
    """入职类问句且有岗位中文名时拼接；否则原样返回。"""
    base = (question or "").strip()
    if not base or not is_onboarding_question(base):
        return base
    label = position_label(position_key)
    if not label:
        return base
    if label in base:
        return base
    return f"{base} {label}"
