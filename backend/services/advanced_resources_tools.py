"""进阶资料推荐白名单工具：薄弱点、课内/课外检索、相关性判定。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.config import settings
from backend.errors import ServiceUnavailableError, UpstreamServiceError
from backend.infra.embed import encode_query, is_loaded
from backend.infra.generate import complete_chat
from backend.infra.open_resource import (
    SearchTimeoutError,
    SearchUnavailableError,
    search_open_resources,
)
from backend.infra.retrieve import run_retrieval
from backend.services.conversation_service import list_recent_user_questions
from backend.services.weak_points import summarize_weak_points

_audit = logging.getLogger("backend.audit")
_URL_RE = re.compile(r"https?://", re.I)


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    data: dict[str, Any]
    error_type: str | None = None
    message: str | None = None


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "summarize_weak_points",
        "description": "根据近期提问归纳知识薄弱点",
        "params": ["limit"],
    },
    {
        "name": "search_course",
        "description": "在 student 课程空间检索课内资料候选",
        "params": ["query"],
    },
    {
        "name": "search_external",
        "description": "按关键词搜索开源/免费课外阅读（白名单主机）",
        "params": ["queries"],
    },
    {
        "name": "judge_relevance",
        "description": "对照薄弱点判定候选去留，必要时建议改写搜索词",
        "params": ["topic", "channel", "candidates", "query"],
    },
    {
        "name": "analyze_capability",
        "description": "根据近期提问与薄弱点生成能力画像",
        "params": ["questions", "weak_points"],
    },
    {
        "name": "compose_report",
        "description": "将能力分析与已筛选资料合成为推荐文章结构",
        "params": ["capability", "weak_points", "materials"],
    },
]

WHITELIST = frozenset(item["name"] for item in TOOL_SPECS)


def list_tool_specs() -> list[dict[str, Any]]:
    return list(TOOL_SPECS)


def tool_summarize_weak_points(*, user_id: str, limit: int | None = None) -> ToolResult:
    cap = settings.learning_path_recent_questions if limit is None else max(1, min(int(limit), 50))
    questions = list_recent_user_questions(user_id=user_id, limit=cap)
    if not questions:
        return ToolResult(
            tool="summarize_weak_points",
            ok=True,
            data={"weak_points": []},
            message="提问记录不足",
        )
    weak_points = summarize_weak_points(questions)[: settings.advanced_resources_max_topics]
    return ToolResult(
        tool="summarize_weak_points",
        ok=True,
        data={"weak_points": weak_points},
    )


def tool_search_course(*, query: str) -> ToolResult:
    text = (query or "").strip()
    if not text:
        return ToolResult(
            tool="search_course",
            ok=False,
            data={},
            error_type="invalid_args",
            message="query 不能为空",
        )
    if not is_loaded():
        raise ServiceUnavailableError("向量模型未加载")
    query_vector = encode_query(text)
    retrieved = run_retrieval(
        query_text=text,
        query_vector=query_vector,
        allowed_spaces=["student"],
    )
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in retrieved:
        if item.space_id != "student":
            continue
        doc_id = str(item.document_id)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        snippet = (item.content or "").strip().replace("\n", " ")
        if len(snippet) > 240:
            snippet = snippet[:240] + "…"
        candidates.append(
            {
                "id": doc_id,
                "document_id": doc_id,
                "title": item.title,
                "space_id": "student",
                "path": item.path,
                "snippet": snippet,
                "score": float(item.score),
            }
        )
    return ToolResult(
        tool="search_course",
        ok=True,
        data={"query": text, "candidates": candidates, "candidate_count": len(candidates)},
    )


def tool_search_external(*, queries: list[str]) -> ToolResult:
    cleaned = [str(item).strip() for item in queries if str(item).strip()]
    if not cleaned:
        return ToolResult(
            tool="search_external",
            ok=False,
            data={},
            error_type="invalid_args",
            message="queries 不能为空",
        )
    try:
        hits = search_open_resources(cleaned)
    except SearchTimeoutError:
        return ToolResult(
            tool="search_external",
            ok=False,
            data={"queries": cleaned, "candidates": []},
            error_type="search_timeout",
            message="课外搜索超时",
        )
    except SearchUnavailableError:
        return ToolResult(
            tool="search_external",
            ok=False,
            data={"queries": cleaned, "candidates": []},
            error_type="search_unavailable",
            message="课外搜索暂不可用",
        )
    candidates = [
        {
            "id": item.url,
            "title": item.title,
            "url": item.url,
            "host": item.host,
            "kind": item.kind,
            "snippet": item.snippet or "",
            "score": 0.0,
        }
        for item in hits
    ]
    return ToolResult(
        tool="search_external",
        ok=True,
        data={"queries": cleaned, "candidates": candidates, "candidate_count": len(candidates)},
    )


def _parse_judge_payload(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match is None:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _sanitize_refined_query(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or _URL_RE.search(text):
        return None
    if len(text) > 80:
        text = text[:80].strip()
    return text or None


def _fallback_keep(candidates: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    ordered = sorted(
        candidates,
        key=lambda item: float(item.get("score") or 0.0),
        reverse=True,
    )
    return ordered[: max(0, k)]


def tool_judge_relevance(
    *,
    topic: str,
    channel: str,
    candidates: list[dict[str, Any]],
    query: str,
) -> ToolResult:
    topic_text = (topic or "").strip()
    channel_text = (channel or "").strip()
    if channel_text not in {"course", "external"}:
        return ToolResult(
            tool="judge_relevance",
            ok=False,
            data={},
            error_type="invalid_args",
            message="channel 必须是 course 或 external",
        )
    if not topic_text:
        return ToolResult(
            tool="judge_relevance",
            ok=False,
            data={},
            error_type="invalid_args",
            message="topic 不能为空",
        )

    by_id = {str(item.get("id")): item for item in candidates if item.get("id")}
    if not by_id:
        return ToolResult(
            tool="judge_relevance",
            ok=True,
            data={
                "keep_ids": [],
                "drop_ids": [],
                "keep": [],
                "need_refine": True,
                "refined_query": topic_text[:80],
                "reason": "无候选",
                "fallback": False,
            },
        )

    compact = []
    for item in candidates:
        cid = str(item.get("id") or "")
        if not cid:
            continue
        compact.append(
            {
                "id": cid,
                "title": item.get("title") or "",
                "path": item.get("path"),
                "snippet": (item.get("snippet") or "")[:180],
                "score": item.get("score"),
                "host": item.get("host"),
                "kind": item.get("kind"),
            }
        )

    prompt = (
        f"薄弱点/主题：{topic_text}\n"
        f"渠道：{channel_text}\n"
        f"当前搜索词：{(query or topic_text).strip()}\n"
        "候选资料（只能使用下列 id）：\n"
        f"{json.dumps(compact, ensure_ascii=False)}\n\n"
        "判断哪些与主题直接相关。只输出一个 JSON 对象，字段："
        "keep_ids（字符串数组）、drop_ids（字符串数组）、"
        "need_refine（布尔）、refined_query（字符串或 null）、reason（一句话）。"
        "keep_ids/drop_ids 中的 id 必须来自候选。"
        "若全部不相关，keep_ids 为空且 need_refine=true，并给出更具体的 refined_query（不要 URL）。"
        "若已有相关条目，need_refine=false。"
    )

    fallback = False
    try:
        raw = complete_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是资料相关性审核器。只输出 JSON 对象。"
                        "禁止编造候选中不存在的 id 或 URL。"
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        ).text
        payload = _parse_judge_payload(raw)
    except UpstreamServiceError:
        payload = None

    if payload is None:
        fallback = True
        keep_list = _fallback_keep(list(by_id.values()), settings.advanced_resources_judge_fallback_k)
        keep_ids = [str(item["id"]) for item in keep_list]
        _audit.info(
            "feature=advanced_resources tool=judge_relevance fallback=1 topic=%s channel=%s",
            topic_text,
            channel_text,
        )
        return ToolResult(
            tool="judge_relevance",
            ok=True,
            data={
                "keep_ids": keep_ids,
                "drop_ids": [cid for cid in by_id if cid not in keep_ids],
                "keep": keep_list,
                "need_refine": len(keep_list) == 0,
                "refined_query": topic_text[:80] if not keep_list else None,
                "reason": "判定失败，已降级保留高分候选",
                "fallback": True,
            },
        )

    allowed = set(by_id)
    keep_ids = [
        str(item)
        for item in (payload.get("keep_ids") or [])
        if str(item) in allowed
    ]
    # 去重保序
    seen_keep: set[str] = set()
    ordered_keep: list[str] = []
    for cid in keep_ids:
        if cid not in seen_keep:
            seen_keep.add(cid)
            ordered_keep.append(cid)
    keep_ids = ordered_keep

    drop_ids = [
        str(item)
        for item in (payload.get("drop_ids") or [])
        if str(item) in allowed and str(item) not in keep_ids
    ]
    for cid in allowed:
        if cid not in keep_ids and cid not in drop_ids:
            drop_ids.append(cid)

    need_refine = bool(payload.get("need_refine")) and len(keep_ids) == 0
    refined = _sanitize_refined_query(payload.get("refined_query")) if need_refine else None
    if need_refine and not refined:
        need_refine = False

    reason = payload.get("reason")
    if not isinstance(reason, str):
        reason = ""
    reason = reason.strip()[:200]

    keep_list = [by_id[cid] for cid in keep_ids]
    return ToolResult(
        tool="judge_relevance",
        ok=True,
        data={
            "keep_ids": keep_ids,
            "drop_ids": drop_ids,
            "keep": keep_list,
            "need_refine": need_refine,
            "refined_query": refined,
            "reason": reason,
            "fallback": fallback,
        },
    )


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match is None:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def tool_analyze_capability(
    *,
    questions: list[str],
    weak_points: list[str],
) -> ToolResult:
    qs = [str(item).strip() for item in questions if str(item).strip()][:20]
    topics = [str(item).strip() for item in weak_points if str(item).strip()][:5]
    fallback = {
        "strengths": ["愿意主动提问并寻求资料"],
        "gaps": topics or ["近期提问较少，画像尚不完整"],
        "level_summary": (
            "根据近期提问，你正在围绕以下主题补强："
            + ("、".join(topics) if topics else "课程基础知识")
            + "。建议先抓住一条主线精读再扩展。"
        ),
    }
    if not qs and not topics:
        return ToolResult(
            tool="analyze_capability",
            ok=True,
            data=fallback,
            message="提问记录不足，使用默认能力描述",
        )

    prompt = (
        "根据学员近期提问与薄弱点，写一段简短能力分析。"
        "只输出 JSON 对象，字段：strengths（字符串数组，最多3）、"
        "gaps（字符串数组，最多5）、level_summary（一段中文，120字内）。"
        "禁止输出 URL 或外链。\n\n"
        f"薄弱点：{json.dumps(topics, ensure_ascii=False)}\n"
        f"近期提问：\n" + "\n".join(f"- {item}" for item in qs)
    )
    try:
        raw = complete_chat(
            [
                {
                    "role": "system",
                    "content": "你是学伴诊断助手。只输出 JSON；禁止链接。",
                },
                {"role": "user", "content": prompt},
            ]
        ).text
        payload = _parse_json_object(raw)
    except UpstreamServiceError:
        payload = None

    if payload is None:
        return ToolResult(tool="analyze_capability", ok=True, data=fallback, message="能力分析降级")

    strengths = [str(x).strip() for x in (payload.get("strengths") or []) if str(x).strip()][:3]
    gaps = [str(x).strip() for x in (payload.get("gaps") or []) if str(x).strip()][:5]
    summary = payload.get("level_summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = fallback["level_summary"]
    else:
        summary = summary.strip()[:300]
        if _URL_RE.search(summary):
            summary = fallback["level_summary"]

    return ToolResult(
        tool="analyze_capability",
        ok=True,
        data={
            "strengths": strengths or fallback["strengths"],
            "gaps": gaps or fallback["gaps"],
            "level_summary": summary,
        },
    )


def build_material_catalog(
    course_items: list[dict[str, Any]],
    external_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """供 compose_report 使用的资料目录；id 不可被模型发明。"""
    catalog: list[dict[str, Any]] = []
    for item in course_items:
        doc_id = str(item.get("document_id") or item.get("id") or "")
        if not doc_id:
            continue
        catalog.append(
            {
                "id": doc_id,
                "channel": "course",
                "title": str(item.get("title") or ""),
                "path": item.get("path"),
                "snippet": str(item.get("snippet") or "")[:180],
            }
        )
    for item in external_items:
        url = str(item.get("url") or item.get("id") or "")
        if not url.startswith("http"):
            continue
        catalog.append(
            {
                "id": url,
                "channel": "external",
                "title": str(item.get("title") or url),
                "host": item.get("host"),
                "kind": item.get("kind"),
                "snippet": str(item.get("snippet") or "")[:180],
            }
        )
    return catalog


def hydrate_report(
    raw_report: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """校验 compose 输出并把 ref_id 回填为可展示资料。"""
    by_id = {str(item["id"]): item for item in catalog}
    title = raw_report.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "你的进阶学习建议"
    else:
        title = title.strip()[:80]

    capability = raw_report.get("capability_analysis")
    if not isinstance(capability, str) or not capability.strip():
        capability = ""
    else:
        capability = capability.strip()[:800]

    weak_details = []
    for item in raw_report.get("weak_points_detail") or []:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        why = str(item.get("why") or "").strip()
        if topic:
            weak_details.append({"topic": topic[:80], "why": why[:200]})

    materials_out = []
    for item in raw_report.get("materials") or []:
        if not isinstance(item, dict):
            continue
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_id not in by_id:
            continue
        src = by_id[ref_id]
        reason = str(item.get("reason") or "").strip()[:300]
        how = str(item.get("how_to_use") or "").strip()[:200]
        materials_out.append(
            {
                "ref_id": ref_id,
                "channel": src.get("channel"),
                "title": src.get("title"),
                "path": src.get("path"),
                "url": src.get("id") if src.get("channel") == "external" else None,
                "host": src.get("host"),
                "kind": src.get("kind"),
                "reason": reason or "与当前薄弱点相关",
                "how_to_use": how or "先通读标题对应章节，再对照自己的提问试着复述要点。",
            }
        )

    next_steps = []
    for item in raw_report.get("next_steps") or []:
        text = str(item).strip()
        if text and not _URL_RE.search(text):
            next_steps.append(text[:120])
        if len(next_steps) >= 5:
            break
    if not next_steps:
        next_steps = ["先精读一篇最相关的课内资料", "用自己的话总结三个要点", "带着疑问再回到问答页追问"]

    return {
        "title": title,
        "capability_analysis": capability,
        "weak_points_detail": weak_details,
        "materials": materials_out,
        "next_steps": next_steps,
    }


def tool_compose_report(
    *,
    capability: dict[str, Any],
    weak_points: list[str],
    materials: list[dict[str, Any]],
) -> ToolResult:
    catalog = materials
    allowed_ids = [str(item.get("id")) for item in catalog if item.get("id")]
    fallback_materials = [
        {
            "ref_id": cid,
            "reason": "与识别到的薄弱点相关，建议优先阅读",
            "how_to_use": "先浏览标题与摘要，再精读与提问最接近的段落。",
        }
        for cid in allowed_ids[:6]
    ]
    fallback_report = hydrate_report(
        {
            "title": "你的进阶学习建议",
            "capability_analysis": str((capability or {}).get("level_summary") or ""),
            "weak_points_detail": [{"topic": t, "why": "近期提问中反复出现或尚未掌握"} for t in weak_points[:5]],
            "materials": fallback_materials,
            "next_steps": [
                "按推荐顺序阅读课内资料",
                "对照薄弱点做一道小练习或复述",
                "回到问答页针对仍不懂的点继续提问",
            ],
        },
        catalog,
    )

    if not catalog:
        return ToolResult(
            tool="compose_report",
            ok=True,
            data={"report": fallback_report, "fallback": True},
            message="暂无已筛选资料，仅生成能力与下一步建议",
        )

    prompt = (
        "你是学伴编辑。根据能力分析与「允许引用的资料目录」写一篇进阶推荐文章结构。"
        "只输出 JSON，字段："
        "title，capability_analysis（一段），"
        "weak_points_detail（[{topic,why}]），"
        "materials（[{ref_id,reason,how_to_use}]，ref_id 必须来自目录 id），"
        "next_steps（字符串数组，最多5条）。"
        "禁止编造目录以外的 ref_id 或任何 URL。\n\n"
        f"能力分析：{json.dumps(capability, ensure_ascii=False)}\n"
        f"薄弱点：{json.dumps(weak_points, ensure_ascii=False)}\n"
        f"资料目录：{json.dumps(catalog, ensure_ascii=False)}"
    )
    try:
        raw = complete_chat(
            [
                {
                    "role": "system",
                    "content": "只输出 JSON。materials.ref_id 必须来自资料目录。禁止虚构链接。",
                },
                {"role": "user", "content": prompt},
            ]
        ).text
        payload = _parse_json_object(raw)
    except UpstreamServiceError:
        payload = None

    if payload is None:
        return ToolResult(
            tool="compose_report",
            ok=True,
            data={"report": fallback_report, "fallback": True},
            message="成文降级",
        )

    report = hydrate_report(payload, catalog)
    if not report["capability_analysis"]:
        report["capability_analysis"] = fallback_report["capability_analysis"]
    if not report["weak_points_detail"]:
        report["weak_points_detail"] = fallback_report["weak_points_detail"]
    if not report["materials"]:
        report["materials"] = fallback_report["materials"]

    return ToolResult(
        tool="compose_report",
        ok=True,
        data={"report": report, "fallback": False},
    )


def run_tool(name: str, args: dict[str, Any] | None, *, user_id: str) -> ToolResult:
    """执行白名单工具；未知名称由调用方先校验。"""
    payload = args or {}
    # 忽略客户端试图传入的空间参数
    payload = {k: v for k, v in payload.items() if k not in {"space_ids", "allowed_spaces", "space_id"}}

    if name == "summarize_weak_points":
        return tool_summarize_weak_points(user_id=user_id, limit=payload.get("limit"))
    if name == "search_course":
        return tool_search_course(query=str(payload.get("query") or ""))
    if name == "search_external":
        queries = payload.get("queries")
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = []
        return tool_search_external(queries=queries)
    if name == "judge_relevance":
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            candidates = []
        return tool_judge_relevance(
            topic=str(payload.get("topic") or ""),
            channel=str(payload.get("channel") or ""),
            candidates=[item for item in candidates if isinstance(item, dict)],
            query=str(payload.get("query") or ""),
        )
    if name == "analyze_capability":
        questions = payload.get("questions")
        if not isinstance(questions, list):
            questions = list_recent_user_questions(
                user_id=user_id,
                limit=settings.learning_path_recent_questions,
            )
        weak_points = payload.get("weak_points")
        if not isinstance(weak_points, list):
            weak_points = []
        return tool_analyze_capability(questions=questions, weak_points=weak_points)
    if name == "compose_report":
        capability = payload.get("capability")
        if not isinstance(capability, dict):
            capability = {}
        weak_points = payload.get("weak_points")
        if not isinstance(weak_points, list):
            weak_points = []
        materials = payload.get("materials")
        if not isinstance(materials, list):
            materials = []
        return tool_compose_report(
            capability=capability,
            weak_points=[str(x) for x in weak_points],
            materials=[item for item in materials if isinstance(item, dict)],
        )
    return ToolResult(
        tool=name,
        ok=False,
        data={},
        error_type="unknown_tool",
        message=f"未知工具: {name}",
    )


def course_item_from_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = item.get("document_id") or item.get("id")
    if not doc_id:
        return None
    try:
        UUID(str(doc_id))
    except ValueError:
        return None
    return {
        "document_id": str(doc_id),
        "title": str(item.get("title") or ""),
        "space_id": "student",
        "path": item.get("path"),
    }


def external_item_from_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    url = item.get("url") or item.get("id")
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    return {
        "title": str(item.get("title") or url),
        "url": url,
        "host": str(item.get("host") or ""),
        "kind": str(item.get("kind") or "doc"),
        "snippet": str(item.get("snippet") or ""),
    }
