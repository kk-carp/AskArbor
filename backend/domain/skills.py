"""本仓 Skill 包加载与校验（CE §3.2）；不是公司 SkillHub。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.config import settings

# 与 advanced_resources TOOL_SPECS + generate.web_search 对齐；Skill 只能缩小此集合
ADVANCED_RESOURCE_TOOLS = frozenset(
    {
        "summarize_weak_points",
        "search_course",
        "search_external",
        "judge_relevance",
        "analyze_capability",
        "compose_report",
    }
)
WEB_SEARCH_TOOL = "web_search"
GLOBAL_TOOL_NAMES = ADVANCED_RESOURCE_TOOLS | {WEB_SEARCH_TOOL}

BUILTIN_SKILL_NAMES = (
    "course-qa",
    "advanced-resources",
    "general-assist-search",
)


class SkillLoadError(ValueError):
    """SKILL.md 缺失、格式错误或声明了未知工具。"""


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    tools: frozenset[str]
    system_extra: str
    body: str


def skills_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    configured = Path(settings.skills_dir)
    if configured.is_absolute():
        return configured
    return Path.cwd() / configured


def _split_frontmatter(text: str) -> tuple[str, str]:
    raw = text.lstrip("\ufeff")
    if not raw.startswith("---"):
        raise SkillLoadError("SKILL.md 必须以 YAML frontmatter（---）开头")
    rest = raw[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        raise SkillLoadError("SKILL.md 缺少结束 frontmatter 分隔符 ---")
    meta = rest[:end]
    body = rest[end + len("\n---") :]
    if body.startswith("\r\n"):
        body = body[2:]
    elif body.startswith("\n"):
        body = body[1:]
    return meta, body.strip()


def _parse_frontmatter(meta: str) -> dict[str, object]:
    """无第三方 YAML：支持 name/description/system_extra 标量与 tools 列表。"""
    data: dict[str, object] = {}
    tools: list[str] | None = None
    in_tools = False
    for raw_line in meta.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if in_tools:
            if line.startswith(" ") or line.startswith("\t"):
                item = stripped
                if item.startswith("- "):
                    item = item[2:].strip()
                elif item.startswith("-"):
                    item = item[1:].strip()
                else:
                    raise SkillLoadError(f"tools 列表项格式无效: {raw_line!r}")
                if not item:
                    raise SkillLoadError("tools 列表项不能为空")
                assert tools is not None
                tools.append(item.strip("\"'"))
                continue
            in_tools = False
        if ":" not in stripped:
            raise SkillLoadError(f"frontmatter 行无效: {raw_line!r}")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "tools":
            tools = []
            data["tools"] = tools
            if value in {"", "[]"}:
                in_tools = value == ""
                continue
            raise SkillLoadError("tools 请使用多行列表（每行 - name）或 tools: []")
        if key in {"name", "description", "system_extra"}:
            data[key] = value.strip("\"'")
            continue
        raise SkillLoadError(f"不支持的 frontmatter 字段: {key}")
    if "tools" not in data:
        raise SkillLoadError("frontmatter 缺少 tools")
    return data


def _validate_tools(tools: object) -> frozenset[str]:
    if not isinstance(tools, list):
        raise SkillLoadError("tools 必须是列表")
    names: list[str] = []
    for item in tools:
        if not isinstance(item, str) or not item.strip():
            raise SkillLoadError("tools 项必须是非空字符串")
        names.append(item.strip())
    unique = frozenset(names)
    if len(unique) != len(names):
        raise SkillLoadError("tools 含重复项")
    unknown = sorted(unique - GLOBAL_TOOL_NAMES)
    if unknown:
        raise SkillLoadError(f"Skill 声明了未登记工具: {', '.join(unknown)}")
    return unique


def parse_skill_markdown(text: str, *, directory_name: str) -> SkillSpec:
    meta, body = _split_frontmatter(text)
    data = _parse_frontmatter(meta)
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip()
    if not name:
        raise SkillLoadError("frontmatter 缺少 name")
    if not description:
        raise SkillLoadError("frontmatter 缺少 description")
    if name != directory_name:
        raise SkillLoadError(f"name={name!r} 与目录名 {directory_name!r} 不一致")
    tools = _validate_tools(data["tools"])
    system_extra = str(data.get("system_extra") or "").strip()
    return SkillSpec(
        name=name,
        description=description,
        tools=tools,
        system_extra=system_extra,
        body=body,
    )


@lru_cache(maxsize=32)
def _load_skill_cached(name: str, root_resolved: str) -> SkillSpec:
    path = Path(root_resolved) / name / "SKILL.md"
    if not path.is_file():
        raise SkillLoadError(f"找不到 Skill 文件: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_skill_markdown(text, directory_name=name)


def clear_skill_cache() -> None:
    _load_skill_cached.cache_clear()


def load_skill(name: str, *, root: str | Path | None = None) -> SkillSpec:
    normalized = (name or "").strip()
    if not normalized:
        raise SkillLoadError("Skill 名称不能为空")
    base = skills_root(root).resolve()
    return _load_skill_cached(normalized, str(base))


def list_skills(*, root: str | Path | None = None) -> list[SkillSpec]:
    base = skills_root(root)
    if not base.is_dir():
        return []
    specs: list[SkillSpec] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        specs.append(load_skill(child.name, root=base))
    return specs


def assert_builtin_skills(*, root: str | Path | None = None) -> None:
    """启动时校验三个内置包；失败则阻止带着错误清单上课。"""
    clear_skill_cache()
    base = skills_root(root)
    course = load_skill("course-qa", root=base)
    if course.tools:
        raise SkillLoadError("course-qa 的 tools 必须为空")
    advanced = load_skill("advanced-resources", root=base)
    if advanced.tools != ADVANCED_RESOURCE_TOOLS:
        raise SkillLoadError(
            "advanced-resources 的 tools 必须正好是进阶资料六工具全集"
        )
    assist = load_skill("general-assist-search", root=base)
    if assist.tools != frozenset({WEB_SEARCH_TOOL}):
        raise SkillLoadError("general-assist-search 的 tools 必须仅为 web_search")
