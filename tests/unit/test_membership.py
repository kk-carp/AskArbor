from backend.domain.membership import expected_spaces, get_allowed_spaces_for_user


def test_expected_spaces_for_student() -> None:
    assert expected_spaces(role="student", is_teaching=False) == ["student"]


def test_expected_spaces_for_employee() -> None:
    assert expected_spaces(role="employee", is_teaching=False) == ["company"]


def test_expected_spaces_for_teaching() -> None:
    assert expected_spaces(role="employee", is_teaching=True) == ["student", "company"]


def test_expected_spaces_unknown_role_without_teaching() -> None:
    assert expected_spaces(role="admin", is_teaching=False) == []


def test_get_allowed_spaces_for_user_reads_memberships(monkeypatch) -> None:
    class _ScalarResult:
        @staticmethod
        def all() -> list[str]:
            return ["company", "student"]

    class _Session:
        def scalars(self, _query: object) -> _ScalarResult:
            return _ScalarResult()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("backend.domain.membership.db.init_engine", lambda: None)
    monkeypatch.setattr("backend.domain.membership.db.SessionLocal", lambda: _Session())

    assert get_allowed_spaces_for_user("user-1") == ["student", "company"]


def test_get_allowed_spaces_for_user_returns_empty_without_membership(monkeypatch) -> None:
    class _ScalarResult:
        @staticmethod
        def all() -> list[str]:
            return []

    class _Session:
        def scalars(self, _query: object) -> _ScalarResult:
            return _ScalarResult()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("backend.domain.membership.db.init_engine", lambda: None)
    monkeypatch.setattr("backend.domain.membership.db.SessionLocal", lambda: _Session())

    assert get_allowed_spaces_for_user("user-1") == []
