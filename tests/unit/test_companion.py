import pytest

from backend.domain.companion import (
    CompanionForbiddenError,
    companion_spaces,
    require_companion_spaces,
)


def test_companion_spaces_keeps_only_student() -> None:
    assert companion_spaces(["student", "company"]) == ["student"]
    assert companion_spaces(["student"]) == ["student"]


def test_companion_spaces_empty_without_student() -> None:
    assert companion_spaces(["company"]) == []
    assert companion_spaces([]) == []


def test_require_companion_spaces_raises_for_employee() -> None:
    with pytest.raises(CompanionForbiddenError, match="学伴"):
        require_companion_spaces(["company"])
