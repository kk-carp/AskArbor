from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.models import Conversation, Ticket, TicketStatus
from backend.services.retention_service import purge_expired


class _FakeResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


class _FakeSession:
    def __init__(self, conversations: list[object], tickets: list[object]) -> None:
        self._conversations = conversations
        self._tickets = tickets
        self.deleted: list[object] = []
        self._calls = 0

    def scalars(self, _query: object) -> _FakeResult:
        self._calls += 1
        if self._calls == 1:
            return _FakeResult(self._conversations)
        return _FakeResult(self._tickets)

    def delete(self, item: object) -> None:
        self.deleted.append(item)


def test_purge_expired_skips_when_days_not_positive() -> None:
    session = _FakeSession(conversations=[object()], tickets=[object()])
    result = purge_expired(session, retention_days=0)
    assert result.conversations == 0
    assert result.tickets == 0
    assert session.deleted == []


def test_purge_expired_deletes_old_conversations_and_replied_tickets() -> None:
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    old_conversation = SimpleNamespace(id="c-old", updated_at=now - timedelta(days=100))
    old_ticket = SimpleNamespace(
        id="t-old",
        status=TicketStatus.replied.value,
        updated_at=now - timedelta(days=100),
    )
    session = _FakeSession(conversations=[old_conversation], tickets=[old_ticket])

    result = purge_expired(session, now=now, retention_days=90)

    assert result.conversations == 1
    assert result.tickets == 1
    assert session.deleted == [old_conversation, old_ticket]
    assert Conversation.__tablename__ == "conversations"
    assert Ticket.__tablename__ == "tickets"
