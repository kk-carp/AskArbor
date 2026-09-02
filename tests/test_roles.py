import pytest

from app.roles import get_allowed_spaces


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("student", ["student"]),
        ("employee", ["company"]),
        ("teaching", ["student", "company"]),
    ],
)
def test_get_allowed_spaces_returns_expected_mapping(role: str, expected: list[str]) -> None:
    assert get_allowed_spaces(role) == expected


@pytest.mark.parametrize("invalid_role", ["admin", "", "   "])
def test_get_allowed_spaces_raises_for_invalid_role(invalid_role: str) -> None:
    with pytest.raises(ValueError, match="Invalid role:"):
        get_allowed_spaces(invalid_role)


def test_get_allowed_spaces_returns_new_list_instance() -> None:
    first = get_allowed_spaces("student")
    second = get_allowed_spaces("student")
    assert first == second == ["student"]
    assert first is not second
