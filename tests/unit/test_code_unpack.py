from io import BytesIO
from zipfile import ZipFile

from backend.infra.code_unpack import infer_language, safe_relative_path, unpack_course_zip


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_unpack_keeps_source_and_notes_with_path_and_language() -> None:
    raw = _zip_bytes(
        {
            "labs/sort.py": b"def bubble_sort(values):\n    return values\n",
            "notes/complexity.md": "# 冒泡排序\n时间复杂度 O(n^2)\n".encode("utf-8"),
        }
    )

    members, skipped = unpack_course_zip(raw)

    paths = {item.path: item for item in members}
    assert set(paths) == {"labs/sort.py", "notes/complexity.md"}
    assert paths["labs/sort.py"].language == "python"
    assert paths["notes/complexity.md"].language == "markdown"
    assert skipped == []


def test_unpack_skips_git_binaries_and_path_traversal() -> None:
    raw = _zip_bytes(
        {
            "labs/sort.py": b"x = 1\n",
            ".git/config": b"[core]\n",
            "labs/__pycache__/sort.cpython-311.pyc": b"\x00\x01",
            "labs/logo.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
            "../escape.py": b"secret = 1\n",
            "nested/../../outside.py": b"x = 2\n",
        }
    )

    members, skipped = unpack_course_zip(raw)

    assert [item.path for item in members] == ["labs/sort.py"]
    reasons = {item.path: item.reason for item in skipped}
    assert ".git/config" in reasons or any("忽略目录" in reason for reason in reasons.values())
    assert any("logo.png" in path for path in reasons)
    assert any("非法路径" in item.reason for item in skipped)


def test_unpack_skips_oversized_member() -> None:
    raw = _zip_bytes({"labs/huge.py": b"x" * 64})
    members, skipped = unpack_course_zip(raw, max_member_bytes=16)
    assert members == []
    assert skipped[0].path == "labs/huge.py"
    assert skipped[0].reason == "单文件过大"


def test_unpack_rejects_non_zip() -> None:
    try:
        unpack_course_zip(b"not a zip")
    except ValueError as exc:
        assert "zip" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_safe_relative_path_and_language_helpers() -> None:
    assert safe_relative_path("labs\\sort.py") == "labs/sort.py"
    assert safe_relative_path("../x.py") is None
    assert safe_relative_path("/abs/x.py") is None
    assert infer_language("CMakeLists.txt") == "cmake"
    assert infer_language("src/demo.CPP") == "cpp"
