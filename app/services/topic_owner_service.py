"""内部主题负责人：关键词匹配库中记录；无匹配则明确未配置，不编造。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.errors import ServiceUnavailableError
from app.models import TopicOwner
from app.schemas import OwnerInfo, TopicOwnerResponse


class TopicOwnerError(ValueError):
    """主题负责人配置错误（映射 400）。"""


UNCONFIGURED_OWNER = OwnerInfo(configured=False)


def _ensure_session_factory():
    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")
    return db.SessionLocal


def _split_keywords(keywords: str) -> list[str]:
    return [part.strip() for part in keywords.split(",") if part.strip()]


def _candidate_terms(owner: TopicOwner) -> list[str]:
    terms = [owner.topic_key, owner.topic_name, *_split_keywords(owner.keywords)]
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _to_response(owner: TopicOwner) -> TopicOwnerResponse:
    return TopicOwnerResponse(
        topic_key=owner.topic_key,
        topic_name=owner.topic_name,
        keywords=owner.keywords,
        name=owner.owner_name,
        contact=owner.contact,
    )


def _to_owner_info(owner: TopicOwner) -> OwnerInfo:
    return OwnerInfo(
        configured=True,
        topic_key=owner.topic_key,
        topic_name=owner.topic_name,
        name=owner.owner_name,
        contact=owner.contact,
    )


def match_owner_for_question(session: Session, question: str) -> OwnerInfo:
    """按问题文本匹配主题；取命中关键词最长的一条。无匹配则 configured=false。"""
    normalized = question.strip()
    if not normalized:
        return UNCONFIGURED_OWNER

    haystack = normalized.casefold()
    best: TopicOwner | None = None
    best_len = 0
    for owner in session.scalars(select(TopicOwner)).all():
        for term in _candidate_terms(owner):
            needle = term.casefold()
            if len(needle) < 2:
                continue
            if needle in haystack and len(needle) > best_len:
                best = owner
                best_len = len(needle)

    if best is None:
        return UNCONFIGURED_OWNER
    return _to_owner_info(best)


def lookup_owner_for_employee(
    session: Session,
    *,
    user_role: str | None,
    question: str,
) -> OwnerInfo | None:
    """仅内部员工（非学员）返回负责人；学员路径必须为 None，避免泄露。"""
    if user_role is None or user_role == "student":
        return None
    return match_owner_for_question(session, question)


def list_topic_owners() -> list[TopicOwnerResponse]:
    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        rows = session.scalars(select(TopicOwner).order_by(TopicOwner.topic_key)).all()
        return [_to_response(row) for row in rows]


def upsert_topic_owner(
    *,
    topic_key: str,
    topic_name: str,
    keywords: str,
    name: str,
    contact: str,
) -> TopicOwnerResponse:
    key = topic_key.strip()
    if not key:
        raise TopicOwnerError("主题 key 不能为空")
    title = topic_name.strip()
    owner_name = name.strip()
    owner_contact = contact.strip()
    if not title or not owner_name or not owner_contact:
        raise TopicOwnerError("主题名称、负责人姓名和联系方式不能为空")

    SessionLocal = _ensure_session_factory()
    with SessionLocal() as session:
        row = session.get(TopicOwner, key)
        if row is None:
            row = TopicOwner(
                topic_key=key,
                topic_name=title,
                keywords=keywords.strip(),
                owner_name=owner_name,
                contact=owner_contact,
            )
            session.add(row)
        else:
            row.topic_name = title
            row.keywords = keywords.strip()
            row.owner_name = owner_name
            row.contact = owner_contact
        session.commit()
        session.refresh(row)
        return _to_response(row)
