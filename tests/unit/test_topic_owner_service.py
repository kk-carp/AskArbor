import pytest

from app.models import TopicOwner
from app.seed.topic_owners import DEMO_TOPIC_OWNERS, seed_topic_owners
from app.services.topic_owner_service import (
    TopicOwnerError,
    UNCONFIGURED_OWNER,
    lookup_owner_for_employee,
    match_owner_for_question,
    upsert_topic_owner,
)


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[TopicOwner] | None = None, get_map=None):
        self.rows = list(rows or [])
        self.added: list[object] = []
        self._get_map = get_map or {}
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def scalars(self, _stmt):
        return _ScalarResult(self.rows)

    def get(self, model, key):
        return self._get_map.get((model, key))

    def add(self, obj) -> None:
        self.added.append(obj)
        if isinstance(obj, TopicOwner):
            self.rows.append(obj)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _obj) -> None:
        return None


def _sample_owners() -> list[TopicOwner]:
    return [
        TopicOwner(
            topic_key="leave",
            topic_name="请假休假",
            keywords="请假,休假,年假",
            owner_name="人力演示",
            contact="hr-demo@example.local",
        ),
        TopicOwner(
            topic_key="it",
            topic_name="IT支持",
            keywords="VPN,电脑",
            owner_name="IT演示",
            contact="it-demo@example.local",
        ),
    ]


def test_match_owner_returns_configured_contact() -> None:
    session = _FakeSession(_sample_owners())
    result = match_owner_for_question(session, "年假怎么请？")
    assert result.configured is True
    assert result.topic_key == "leave"
    assert result.name == "人力演示"
    assert result.contact == "hr-demo@example.local"


def test_match_owner_prefers_longest_keyword() -> None:
    owners = _sample_owners()
    owners.append(
        TopicOwner(
            topic_key="leave-sick",
            topic_name="病假",
            keywords="病假",
            owner_name="病假对接",
            contact="sick-demo@example.local",
        )
    )
    session = _FakeSession(owners)
    result = match_owner_for_question(session, "病假需要交什么材料")
    assert result.topic_key == "leave-sick"
    assert result.name == "病假对接"


def test_match_owner_returns_unconfigured_when_no_keyword() -> None:
    session = _FakeSession(_sample_owners())
    result = match_owner_for_question(session, "完全无关的问题xyz")
    assert result == UNCONFIGURED_OWNER
    assert result.configured is False
    assert result.name is None
    assert result.contact is None


def test_student_path_does_not_return_owner() -> None:
    session = _FakeSession(_sample_owners())
    result = lookup_owner_for_employee(
        session,
        user_role="student",
        question="年假怎么请？",
    )
    assert result is None


def test_employee_path_returns_unconfigured_object() -> None:
    session = _FakeSession(_sample_owners())
    result = lookup_owner_for_employee(
        session,
        user_role="employee",
        question="完全无关的问题xyz",
    )
    assert result is not None
    assert result.configured is False


def test_seed_topic_owners_skips_existing() -> None:
    existing = TopicOwner(
        topic_key="leave",
        topic_name="已有请假",
        keywords="请假",
        owner_name="已配置",
        contact="kept@example.local",
    )
    session = _FakeSession([existing])
    seed_topic_owners(session)
    added_keys = [item.topic_key for item in session.added if isinstance(item, TopicOwner)]
    assert "leave" not in added_keys
    assert len(added_keys) == len(DEMO_TOPIC_OWNERS) - 1
    assert existing.owner_name == "已配置"


def test_upsert_creates_and_updates(monkeypatch) -> None:
    store: dict[tuple, TopicOwner] = {}

    class _Session(_FakeSession):
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, model, key):
            return store.get((model, key))

        def add(self, obj) -> None:
            super().add(obj)
            store[(TopicOwner, obj.topic_key)] = obj

        def refresh(self, obj) -> None:
            return None

    monkeypatch.setattr(
        "app.services.topic_owner_service._ensure_session_factory",
        lambda: (lambda: _Session()),
    )

    created = upsert_topic_owner(
        topic_key="parking",
        topic_name="停车",
        keywords="停车,车位",
        name="行政演示",
        contact="parking-demo@example.local",
    )
    assert created.topic_key == "parking"
    assert created.name == "行政演示"

    updated = upsert_topic_owner(
        topic_key="parking",
        topic_name="停车管理",
        keywords="停车",
        name="行政演示2",
        contact="parking2-demo@example.local",
    )
    assert updated.topic_name == "停车管理"
    assert updated.name == "行政演示2"


def test_upsert_rejects_blank_name(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.topic_owner_service._ensure_session_factory",
        lambda: (lambda: _FakeSession()),
    )
    with pytest.raises(TopicOwnerError, match="不能为空"):
        upsert_topic_owner(
            topic_key="x",
            topic_name="x",
            keywords="",
            name="  ",
            contact="a@example.local",
        )
