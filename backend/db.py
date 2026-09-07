from collections.abc import Generator

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.models import Base, Space

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


def init_db() -> None:
    """启用 pgvector、创建表结构，并初始化 student/company 空间。"""
    current_engine = init_engine()

    # 仅在 PostgreSQL 下启用 pgvector 扩展。
    if current_engine.dialect.name == "postgresql":
        with current_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=current_engine)
    _ensure_chunk_source_columns(current_engine)

    if SessionLocal is None:
        raise RuntimeError("Session factory is not initialized")

    with SessionLocal() as session:
        # 保持初始化幂等，重复启动时不重复插入空间数据。
        existing_spaces = set(session.scalars(select(Space.id)).all())
        for space_id, name in (("student", "student"), ("company", "company")):
            if space_id not in existing_spaces:
                session.add(Space(id=space_id, name=name))
        from backend.seed.demo_users import seed_demo_users
        from backend.seed.topic_owners import seed_topic_owners

        seed_demo_users(session)
        seed_topic_owners(session)
        session.commit()


def get_session() -> Generator[Session, None, None]:
    """为请求或服务调用提供数据库会话。"""
    if SessionLocal is None:
        raise RuntimeError("Database engine is not initialized")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
