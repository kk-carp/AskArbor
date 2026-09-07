"""课程代码 zip 解包：忽略无关文件，拒绝路径穿越。"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import zipfile

MAX_ZIP_MEMBERS = 200
MAX_ZIP_TOTAL_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 512 * 1024

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".idea",
        ".vscode",
        ".mypy_cache",
        ".pytest_cache",
    }
)
SKIP_FILE_NAMES = frozenset({".ds_store", "thumbs.db"})
SKIP_EXTENSIONS = frozenset(
    {
        "pyc",
        "pyo",
        "so",
        "dll",
        "exe",
        "bin",
        "o",
        "a",
        "lib",
        "obj",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "ico",
        "bmp",
        "svg",
        "mp4",
        "mp3",
        "wav",
        "zip",
        "tar",
        "gz",
        "rar",
        "7z",
        "ttf",
        "otf",
        "woff",
        "woff2",
        "class",
        "jar",
    }
)
MEMBER_EXTENSIONS = frozenset(
    {
        "py",
        "pyi",
        "c",
        "h",
        "cc",
        "cpp",
        "cxx",
        "hpp",
        "hh",
        "md",
        "txt",
        "rst",
        "json",
        "yaml",
        "yml",
        "toml",
        "cmake",
        "pdf",
        "docx",
        "ipynb",
        "csv",
        "sh",
    }
)
LANGUAGE_BY_EXT = {
    "py": "python",
    "pyi": "python",
    "c": "c",
    "h": "c",
    "cc": "cpp",
    "cpp": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "hh": "cpp",
    "md": "markdown",
    "txt": "text",
    "rst": "rst",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "cmake": "cmake",
    "pdf": "pdf",
    "docx": "docx",
    "ipynb": "jupyter",
    "csv": "csv",
    "sh": "shell",
}
SPECIAL_FILENAMES = {
    "cmakelists.txt": "cmake",
}


@dataclass(frozen=True)
class ZipSkipped:
    path: str
    reason: str


@dataclass(frozen=True)
class ZipMember:
    path: str
    content: bytes
    language: str | None


def infer_language(relative_path: str) -> str | None:
    name = PurePosixPath(relative_path).name.lower()
    if name in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[name]
    extension = PurePosixPath(relative_path).suffix.lower().lstrip(".")
    return LANGUAGE_BY_EXT.get(extension)


def _extension(relative_path: str) -> str:
    return PurePosixPath(relative_path).suffix.lower().lstrip(".")


def safe_relative_path(raw_name: str) -> str | None:
    """返回包内相对 POSIX 路径；目录、绝对路径或含 `..` 时返回 None。"""
    normalized = raw_name.replace("\\", "/").strip()
    if not normalized or normalized.endswith("/"):
        return None
    if normalized.startswith("/") or (len(normalized) >= 2 and normalized[1] == ":"):
        return None
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    if any(len(part) > 200 for part in parts):
        return None
    relative = "/".join(parts)
    if len(relative) > 512:
        return None
    return relative


def _skip_reason(relative_path: str) -> str | None:
    parts = relative_path.split("/")
    if any(part in SKIP_DIR_NAMES for part in parts[:-1]):
        return "忽略目录"
    name = parts[-1]
    if name.lower() in SKIP_FILE_NAMES:
        return "忽略文件"
    if name.startswith("._"):
        return "忽略文件"
    extension = _extension(relative_path)
    if extension in SKIP_EXTENSIONS:
        return "忽略二进制或压缩文件"
    if name.lower() in SPECIAL_FILENAMES:
        return None
    if extension not in MEMBER_EXTENSIONS:
        return "不支持的文件类型"
    return None


def unpack_course_zip(
    raw: bytes,
    *,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
) -> tuple[list[ZipMember], list[ZipSkipped]]:
    """解出可入库成员；路径穿越与忽略名单进入 skipped，不写入切片。"""
    buffer = BytesIO(raw)
    if not zipfile.is_zipfile(buffer):
        raise ValueError("不是有效的 zip 文件")
    buffer.seek(0)

    members: list[ZipMember] = []
    skipped: list[ZipSkipped] = []
    total_bytes = 0

    with zipfile.ZipFile(buffer) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise ValueError("课程代码包内文件过多")

        for info in infos:
            display_name = info.filename.replace("\\", "/")
            if info.is_dir() or display_name.endswith("/"):
                continue

            relative = safe_relative_path(info.filename)
            if relative is None:
                skipped.append(ZipSkipped(path=display_name, reason="非法路径"))
                continue

            ignore_reason = _skip_reason(relative)
            if ignore_reason is not None:
                skipped.append(ZipSkipped(path=relative, reason=ignore_reason))
                continue

            if info.file_size > max_member_bytes:
                skipped.append(ZipSkipped(path=relative, reason="单文件过大"))
                continue

            total_bytes += info.file_size
            if total_bytes > MAX_ZIP_TOTAL_BYTES:
                raise ValueError("课程代码包解压后体积过大")

            content = archive.read(info)
            if b"\x00" in content:
                skipped.append(ZipSkipped(path=relative, reason="忽略二进制文件"))
                continue

            members.append(
                ZipMember(
                    path=relative,
                    content=content,
                    language=infer_language(relative),
                )
            )

    return members, skipped
