"""MCP 工具组合根：在应用层注入业务 handler。"""

from __future__ import annotations

from typing import Any

from backend.config import settings
from backend.infra.mcp.mapping import is_mapping_ready, register_handlers


def _strip_space_args(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in (arguments or {}).items()
        if k not in {"space_ids", "allowed_spaces", "space_id"}
    }


def bootstrap_mcp_tools(*, force: bool = False) -> None:
    """把已存在工具绑定到 MCP registry。"""
    if (not force) and is_mapping_ready():
        return
    handlers = _build_handlers()
    register_handlers(handlers, replace=True)


def _build_handlers() -> dict[str, Any]:
    from backend.infra.generate import _run_general_assist_web_search_impl
    from backend.infra.open_resource import sources as sources_mod
    from backend.services import advanced_resources_tools as tools
    from backend.services.conversation_service import list_recent_user_questions

    def summarize(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        return tools.tool_summarize_weak_points(
            user_id=str(args.get("user_id") or ""),
            limit=args.get("limit"),
        )

    def search_course(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        return tools.tool_search_course(query=str(args.get("query") or ""))

    def search_external(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        queries = args.get("queries")
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = []
        return tools.tool_search_external(queries=queries)

    def judge(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        candidates = args.get("candidates")
        if not isinstance(candidates, list):
            candidates = []
        return tools.tool_judge_relevance(
            topic=str(args.get("topic") or ""),
            channel=str(args.get("channel") or ""),
            candidates=[item for item in candidates if isinstance(item, dict)],
            query=str(args.get("query") or ""),
        )

    def analyze(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        questions = args.get("questions")
        if not isinstance(questions, list):
            questions = list_recent_user_questions(
                user_id=str(args.get("user_id") or ""),
                limit=settings.learning_path_recent_questions,
            )
        weak_points = args.get("weak_points")
        if not isinstance(weak_points, list):
            weak_points = []
        return tools.tool_analyze_capability(
            questions=questions,
            weak_points=weak_points,
        )

    def compose(arguments: dict[str, Any]):
        args = _strip_space_args(arguments)
        capability = args.get("capability")
        if not isinstance(capability, dict):
            capability = {}
        weak_points = args.get("weak_points")
        if not isinstance(weak_points, list):
            weak_points = []
        materials = args.get("materials")
        if not isinstance(materials, list):
            materials = []
        return tools.tool_compose_report(
            capability=capability,
            weak_points=[str(x) for x in weak_points],
            materials=[item for item in materials if isinstance(item, dict)],
        )

    def web_search(arguments: dict[str, Any]) -> str:
        args = _strip_space_args(arguments)
        query = str(args.get("query") or args.get("q") or "").strip()
        return _run_general_assist_web_search_impl(query)

    def arxiv(arguments: dict[str, Any]) -> list[dict[str, str]]:
        args = _strip_space_args(arguments)
        query = str(args.get("query") or "").strip()
        if not query:
            return []
        return sources_mod.run_arxiv_search(query)

    def tavily(arguments: dict[str, Any]) -> list[dict[str, str]]:
        args = _strip_space_args(arguments)
        query = str(args.get("query") or "").strip()
        if not query:
            return []
        return sources_mod.run_tavily_search(query)

    return {
        "summarize_weak_points": summarize,
        "search_course": search_course,
        "search_external": search_external,
        "judge_relevance": judge,
        "analyze_capability": analyze,
        "compose_report": compose,
        "web_search": web_search,
        "search_arxiv": arxiv,
        "search_tavily": tavily,
    }
