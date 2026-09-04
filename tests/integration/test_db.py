from types import SimpleNamespace

import pytest

from backend import db


def test_init_engine_creates_engine_and_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.engine = None
    db.SessionLocal = None

    fake_engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    created: dict[str, object] = {}

    def fake_create_engine(url: str, pool_pre_ping: bool) -> object:
        created["url"] = url
        created["pool_pre_ping"] = pool_pre_ping
        return fake_engine

    def fake_sessionmaker(*, bind: object, autoflush: bool, autocommit: bool) -> object:
        created["bind"] = bind
        created["autoflush"] = autoflush
        created["autocommit"] = autocommit
        return "session-factory"

    monkeypatch.setattr(db, "create_engine", fake_create_engine)
    monkeypatch.setattr(db, "sessionmaker", fake_sessionmaker)

    engine = db.init_engine()

    assert engine is fake_engine
    assert db.engine is fake_engine
    assert db.SessionLocal == "session-factory"
    assert created["pool_pre_ping"] is True
    assert created["bind"] is fake_engine


def test_get_session_yields_and_closes_session() -> None:
    class _FakeSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    session = _FakeSession()
    db.SessionLocal = lambda: session

    generator = db.get_session()
    yielded_session = next(generator)
    assert yielded_session is session

    with pytest.raises(StopIteration):
        next(generator)
    assert session.closed is True


def test_init_db_enables_pgvector_creates_tables_and_seeds_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed_sql: list[str] = []
    metadata_calls: list[object] = []
    added_space_ids: list[str] = []
    commit_calls = 0

    class _FakeConnection:
        def execute(self, stmt: object) -> None:
            executed_sql.append(str(stmt))

    class _FakeBeginContext:
        def __enter__(self) -> _FakeConnection:
            return _FakeConnection()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    fake_engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        begin=lambda: _FakeBeginContext(),
    )

    class _ScalarResult:
        @staticmethod
        def all() -> list[str]:
            return ["student"]

    class _FakeSession:
        def scalars(self, _query: object) -> _ScalarResult:
            return _ScalarResult()

        def add(self, item: object) -> None:
            added_space_ids.append(getattr(item, "id"))

        def commit(self) -> None:
            nonlocal commit_calls
            commit_calls += 1

    class _FakeSessionContext:
        def __enter__(self) -> _FakeSession:
            return _FakeSession()

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

    monkeypatch.setattr(db, "init_engine", lambda: fake_engine)
    monkeypatch.setattr(db.Base.metadata, "create_all", lambda *, bind: metadata_calls.append(bind))
    monkeypatch.setattr("backend.seed.demo_users.seed_demo_users", lambda _session: None)
    monkeypatch.setattr("backend.seed.topic_owners.seed_topic_owners", lambda _session: None)
    db.SessionLocal = lambda: _FakeSessionContext()

    db.init_db()

    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in executed_sql)
    assert metadata_calls == [fake_engine]
    assert added_space_ids == ["company"]
    assert commit_calls == 1
