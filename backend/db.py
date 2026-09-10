"""SQLAlchemy 引擎与会话；启动时建表并确保 student / company 空间存在。"""

from collections.abc import Generator
import logging

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.models import Base, Space

_log = logging.getLogger("uvicorn.error")

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def init_engine() -> Engine:
    """根据配置创建 SQLAlchemy 引擎与会话工厂。"""
    global engine, SessionLocal

    if engine is None:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    return engine


def _ensure_chunk_source_columns(current_engine: Engine) -> None:
    """已有库补齐 path/language；create_all 不会给旧表加列。"""
    if current_engine.dialect.name != "postgresql":
        return
    with current_engine.begin() as connection:
        connection.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS path VARCHAR(512)"))
        connection.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS language VARCHAR(32)"))


def _ensure_user_position_key(current_engine: Engine) -> None:
    """已有库补齐 users.position_key。"""
    if current_engine.dialect.name != "postgresql":
        return
    with current_engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS position_key VARCHAR(64)"))


def _ensure_chunk_content_tsv(current_engine: Engine) -> None:
    """词法检索列 + GIN；对 content_tsv 为空的行按 jieba 分词回填。"""
    if current_engine.dialect.name != "postgresql":
        return
    with current_engine.begin() as connection:
        connection.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_chunks_content_tsv ON chunks USING GIN (content_tsv)")
        )

    from backend.infra.lexical import to_search_text

    if SessionLocal is None:
        return
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT id, content FROM chunks WHERE content_tsv IS NULL")
        ).mappings().all()
        total = len(rows)
        if total:
            _log.info("backfill content_tsv for %s chunks", total)
        for index, row in enumerate(rows, start=1):
            search_text = to_search_text(row["content"] or "")
            if not search_text:
                continue
            session.execute(
                text(
                    """
                    UPDATE chunks
                    SET content_tsv = to_tsvector('simple', :search_text)
                    WHERE id = :id
                    """
                ),
                {"search_text": search_text, "id": row["id"]},
            )
            if index == 1 or index == total or index % 50 == 0:
                _log.info("content_tsv backfill %s/%s", index, total)
        session.commit()
        if total:
            _log.info("content_tsv backfill finished")


def init_db() -> None:
    """启用 pgvector、创建表结构，并初始化 student/company 空间。"""
    current_engine = init_engine()

    # 仅在 PostgreSQL 下启用 pgvector 扩展。
    if current_engine.dialect.name == "postgresql":
        with current_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=current_engine)
    _ensure_chunk_source_columns(current_engine)
    _ensure_user_position_key(current_engine)
    _ensure_chunk_content_tsv(current_engine)


    if SessionLocal is None:
        raise RuntimeError("Session factory is not initialized")

    with SessionLocal() as session:
        # 保持初始化幂等，重复启动时不重复插入空间数据。
        existing_spaces = set(session.scalars(select(Space.id)).all())
        for space_id, name in (("student", "student"), ("company", "company")):
            if space_id not in existing_spaces:
                session.add(Space(id=space_id, name=name))
        from backend.seed.topic_owners import seed_topic_owners

        # 正式环境不写入上课用的演示账号；本机/上课仍幂等写入。
        if settings.app_env == "local":
            from backend.seed.demo_users import seed_demo_users

            seed_demo_users(session)
        seed_topic_owners(session)
        session.commit()

    purge_expired_on_startup()


def purge_expired_on_startup() -> None:
    """启动时按配置清理一次过期会话/已回复工单；失败只记日志，不阻断启动。"""
    if SessionLocal is None:
        return
    if settings.data_retention_days <= 0:
        return
    try:
        from datetime import datetime, timezone

        from backend.services.retention_service import purge_expired

        with SessionLocal() as session:
            result = purge_expired(
                session,
                now=datetime.now(timezone.utc),
                retention_days=settings.data_retention_days,
            )
            session.commit()
        if result.conversations or result.tickets:
            _log.info(
                "purged expired data conversations=%s tickets=%s retention_days=%s",
                result.conversations,
                result.tickets,
                settings.data_retention_days,
            )
    except Exception:
        _log.exception("expired data purge failed")


def get_session() -> Generator[Session, None, None]:
    """为请求或服务调用提供数据库会话。"""
    if SessionLocal is None:
        raise RuntimeError("Database engine is not initialized")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
