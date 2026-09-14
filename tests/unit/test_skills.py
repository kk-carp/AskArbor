"""本仓 Skill 包加载与内置断言。"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.domain.skills import (
    ADVANCED_RESOURCE_TOOLS,
    SkillLoadError,
    assert_builtin_skills,
    clear_skill_cache,
    load_skill,
    list_skills,
    parse_skill_markdown,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_skill_cache()
    yield
    clear_skill_cache()


def test_load_builtin_skills_from_repo() -> None:
    course = load_skill("course-qa")
    assert course.tools == frozenset()
    assert "知识库" in course.body or "问答" in course.body

    advanced = load_skill("advanced-resources")
    assert advanced.tools == ADVANCED_RESOURCE_TOOLS

    assist = load_skill("general-assist-search")
    assert assist.tools == frozenset({"web_search"})


def test_list_skills_includes_builtins() -> None:
    names = {s.name for s in list_skills()}
    assert {"course-qa", "advanced-resources", "general-assist-search"} <= names


def test_assert_builtin_skills_ok() -> None:
    assert_builtin_skills()


def test_unknown_tool_rejected() -> None:
    text = """---
name: bad-skill
description: invents a tool
tools:
  - web_search
  - shell
system_extra: ""
---

body
"""
    with pytest.raises(SkillLoadError, match="未登记工具"):
        parse_skill_markdown(text, directory_name="bad-skill")


def test_name_must_match_directory() -> None:
    text = """---
name: other-name
description: mismatch
tools: []
---

body
"""
    with pytest.raises(SkillLoadError, match="不一致"):
        parse_skill_markdown(text, directory_name="course-qa")


def test_missing_skill_file(tmp_path: Path) -> None:
    with pytest.raises(SkillLoadError, match="找不到"):
        load_skill("no-such-skill", root=tmp_path)


def test_assert_fails_when_advanced_tools_shrunk(tmp_path: Path) -> None:
    (tmp_path / "course-qa").mkdir()
    (tmp_path / "course-qa" / "SKILL.md").write_text(
        "---\nname: course-qa\ndescription: qa\ntools: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "advanced-resources").mkdir()
    (tmp_path / "advanced-resources" / "SKILL.md").write_text(
        "---\nname: advanced-resources\ndescription: adv\ntools:\n"
        "  - search_course\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "general-assist-search").mkdir()
    (tmp_path / "general-assist-search" / "SKILL.md").write_text(
        "---\nname: general-assist-search\ndescription: assist\ntools:\n"
        "  - web_search\n---\n\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(SkillLoadError, match="六工具"):
        assert_builtin_skills(root=tmp_path)


def test_run_tool_not_in_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.domain import skills as skills_mod
    from backend.services import advanced_resources_tools as tools

    fake = skills_mod.SkillSpec(
        name="advanced-resources",
        description="subset",
        tools=frozenset({"search_course"}),
        system_extra="",
        body="",
    )
    monkeypatch.setattr(skills_mod, "load_skill", lambda name, **_kw: fake)

    names = {item["name"] for item in tools.list_tool_specs()}
    assert names == {"search_course"}

    blocked = tools.run_tool("summarize_weak_points", {}, user_id="u1")
    assert blocked.ok is False
    assert blocked.error_type == "tool_not_in_skill"
