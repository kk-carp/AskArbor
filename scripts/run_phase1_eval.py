from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"
ROLE_TO_USERNAME = {
    "student": "student_demo",
    "employee": "employee_demo",
    "teaching": "teaching_demo",
}
TRANSIENT_HTTP_ERRORS = (
    httpx.ReadError,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.WriteError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.PoolTimeout,
)


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    role: str
    question: str
    expected_hit: bool
    expected_spaces: list[str]
    expected_title_keywords: list[str]


@dataclass(frozen=True)
class CaseResult:
    id: str
    category: str
    role: str
    expected_hit: bool
    actual_hit: bool
    hit_match: bool
    refusal: bool
    refusal_match: bool
    source_accurate: bool
    source_reason: str
    source_count: int
    source_spaces: list[str]
    answer_preview: str
    latency_ms: float | None
    llm_called: bool
    prompt_tokens: int
    completion_tokens: int
    isolation_ok: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run phase-1 evaluation and export baseline / closed-loop metrics."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--case-file",
        default="docs/samples/eval/phase1_minimal_eval_set.jsonl",
        help="课上默认 12 条；闭环请用 docs/samples/eval/phase1_extended_eval_set.jsonl",
    )
    parser.add_argument(
        "--student-doc",
        default="docs/samples/t13/student_course_sample.md",
    )
    parser.add_argument(
        "--company-doc",
        default="docs/samples/t13/company_policy_sample.md",
    )
    parser.add_argument(
        "--output-json",
        default="docs/phase1_eval_baseline.json",
    )
    parser.add_argument(
        "--output-md",
        default="docs/phase1_eval_baseline.md",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=180.0,
        help="Per-request timeout. /ask with rerank + DeepSeek can exceed 30s.",
    )
    parser.add_argument("--health-timeout-sec", type=int, default=120)
    parser.add_argument(
        "--mode",
        choices=["live", "oracle"],
        default="live",
        help="live: call API; oracle: generate synthetic baseline from expected labels.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip uploading sample documents before evaluation.",
    )
    parser.add_argument(
        "--demo-password",
        default=os.environ.get("DEMO_PASSWORD", "demo1234"),
        help="Password for seeded demo accounts.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="发版门禁：隔离未通过或未命中却调模型则非 0 退出。",
    )
    parser.add_argument(
        "--gate-extra-file",
        default="docs/samples/eval/gate_extra_isolation.jsonl",
        help="仅 --gate 时追加的越权样本；不计入课上 12 条作业集。",
    )
    parser.add_argument(
        "--prompt-price-per-1m",
        type=float,
        default=float(os.environ.get("EVAL_PROMPT_PRICE_PER_1M", "1.0")),
        help="Prompt token 单价（元 / 百万 token），用于估算单次成本。",
    )
    parser.add_argument(
        "--completion-price-per-1m",
        type=float,
        default=float(os.environ.get("EVAL_COMPLETION_PRICE_PER_1M", "2.0")),
        help="Completion token 单价（元 / 百万 token），用于估算单次成本。",
    )
    parser.add_argument(
        "--baseline-json",
        default="",
        help="可选：上一版评测 JSON，用于写入优化对比页。",
    )
    parser.add_argument(
        "--write-comparison",
        default="",
        help="可选：输出一页优化对比 Markdown 路径。",
    )
    return parser.parse_args()


def is_loopback_api(api_base: str) -> bool:
    host = (urlparse(api_base).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def make_http_client(timeout_sec: float, api_base: str) -> httpx.Client:
    """本机地址不读 HTTP_PROXY；关闭 keep-alive，避免 uvicorn --reload 重启后复用已死连接。"""
    return httpx.Client(
        timeout=timeout_sec,
        trust_env=not is_loopback_api(api_base),
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
        headers={"Connection": "close"},
    )


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    retries: int = 4,
    recover_health: tuple[str, int] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """重试连接被掐（WinError 10054）：常见于 --reload 在请求中途重启。"""
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return client.request(method, url, **kwargs)
        except TRANSIENT_HTTP_ERRORS as exc:
            last_exc = exc
            if attempt + 1 >= retries:
                break
            print(
                f"{type(exc).__name__} on {method} {url}; "
                f"retry {attempt + 1}/{retries - 1} after waiting for /health",
                flush=True,
            )
            time.sleep(1.0 * (attempt + 1))
            if recover_health is not None:
                api_base, health_timeout = recover_health
                try:
                    wait_for_health_ready(client, api_base, health_timeout)
                except RuntimeError:
                    pass
    assert last_exc is not None
    raise last_exc


def load_cases(case_file: Path) -> list[EvalCase]:
    if not case_file.exists():
        raise FileNotFoundError(f"Case file not found: {case_file}")
    cases: list[EvalCase] = []
    with case_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            cases.append(
                EvalCase(
                    id=payload["id"],
                    category=payload["category"],
                    role=payload["role"],
                    question=payload["question"],
                    expected_hit=bool(payload["expected_hit"]),
                    expected_spaces=list(payload.get("expected_spaces", [])),
                    expected_title_keywords=list(payload.get("expected_title_keywords", [])),
                )
            )
    if not cases:
        raise ValueError("No evaluation cases were loaded.")
    return cases


def merge_cases(base: list[EvalCase], extra: list[EvalCase]) -> list[EvalCase]:
    """按 id 去重，保留作业集原有条目。"""
    merged = list(base)
    seen = {case.id for case in merged}
    for case in extra:
        if case.id not in seen:
            merged.append(case)
            seen.add(case.id)
    return merged


def wait_for_health_ready(
    client: httpx.Client, api_base: str, timeout_sec: int
) -> dict[str, Any]:
    last_payload: dict[str, Any] | None = None
    deadline = datetime.now(timezone.utc).timestamp() + timeout_sec
    while datetime.now(timezone.utc).timestamp() <= deadline:
        try:
            response = client.get(f"{api_base}/health")
            response.raise_for_status()
            payload = response.json()
            last_payload = payload
            if (
                payload.get("api") is True
                and payload.get("database") is True
                and payload.get("embedding_loaded") is True
            ):
                return payload
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Health check not ready within {timeout_sec}s; last={last_payload}")


def upload_sample_doc(
    client: httpx.Client,
    api_base: str,
    path: Path,
    space: str,
    health_timeout_sec: int,
) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Sample document not found: {path}")
    last_exc: BaseException | None = None
    for attempt in range(4):
        try:
            with path.open("rb") as content:
                response = client.post(
                    f"{api_base}/documents",
                    data={"space": space},
                    files={"file": (path.name, content, "text/markdown")},
                )
            if response.status_code == 409:
                detail = response.json().get("detail")
                if isinstance(detail, dict) and detail.get("code") == "duplicate_document":
                    return
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "ready":
                raise RuntimeError(f"Uploaded document not ready: {path.name}, payload={payload}")
            if int(payload.get("chunk_count", 0)) <= 0:
                raise RuntimeError(f"Uploaded document has no chunks: {path.name}, payload={payload}")
            return
        except TRANSIENT_HTTP_ERRORS as exc:
            last_exc = exc
            if attempt + 1 >= 4:
                break
            print(
                f"{type(exc).__name__} uploading {path.name}; "
                f"retry {attempt + 1}/3 after waiting for /health",
                flush=True,
            )
            time.sleep(1.0 * (attempt + 1))
            try:
                wait_for_health_ready(client, api_base, health_timeout_sec)
            except RuntimeError:
                pass
    assert last_exc is not None
    raise last_exc


def login_as_teaching_for_upload(
    client: httpx.Client,
    api_base: str,
    password: str,
    health_timeout_sec: int,
) -> None:
    """入库需教学岗权限；评测上传前先登录 teaching_demo。"""
    response = request_with_retry(
        client,
        "POST",
        f"{api_base}/login",
        recover_health=(api_base, health_timeout_sec),
        json={"username": "teaching_demo", "password": password},
    )
    response.raise_for_status()


def check_isolation(role: str, source_spaces: list[str]) -> bool:
    """学员来源不得出现 company；员工来源不得出现 student。"""
    if role == "student":
        return "company" not in source_spaces
    if role == "employee":
        return "student" not in source_spaces
    return True


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def is_refusal(payload: dict[str, Any]) -> bool:
    return (
        payload.get("hit") is False
        and payload.get("answer") == MISS_ANSWER
        and len(payload.get("sources", [])) == 0
    )


def evaluate_source_accuracy(case: EvalCase, payload: dict[str, Any]) -> tuple[bool, str]:
    sources = payload.get("sources", [])
    if case.expected_hit:
        if payload.get("hit") is not True:
            return False, "expected hit but actual miss"
        if not sources:
            return False, "expected non-empty sources"
        source_spaces = [str(item.get("space_id", "")) for item in sources]
        invalid_spaces = [space for space in source_spaces if space not in case.expected_spaces]
        if invalid_spaces:
            return False, f"unexpected source spaces: {invalid_spaces}"

        keywords = [keyword.lower() for keyword in case.expected_title_keywords]
        if keywords:
            source_titles = [str(item.get("title", "")).lower() for item in sources]
            if not any(any(keyword in title for keyword in keywords) for title in source_titles):
                return False, "expected title keyword not found in sources"
        return True, "ok"

    if sources:
        return False, "expected empty sources for miss case"
    return True, "ok"


def login_demo_user(
    client: httpx.Client,
    api_base: str,
    role: str,
    password: str,
    health_timeout_sec: int,
) -> None:
    username = ROLE_TO_USERNAME.get(role)
    if not username:
        raise ValueError(f"No demo account mapped for role: {role}")
    response = request_with_retry(
        client,
        "POST",
        f"{api_base}/login",
        recover_health=(api_base, health_timeout_sec),
        json={"username": username, "password": password},
    )
    response.raise_for_status()


def run_case(
    client: httpx.Client,
    api_base: str,
    case: EvalCase,
    demo_password: str,
    health_timeout_sec: int,
    *,
    logged_in_role: str | None = None,
) -> tuple[CaseResult, str]:
    """返回 (结果, 当前已登录角色)。同角色复用 Cookie，避免评测触发登录限流。"""
    last_exc: BaseException | None = None
    response: httpx.Response | None = None
    latency_ms = 0.0
    current_role = logged_in_role
    for attempt in range(4):
        if current_role != case.role:
            login_demo_user(client, api_base, case.role, demo_password, health_timeout_sec)
            current_role = case.role
        payload = {"question": case.question}
        started = time.perf_counter()
        try:
            response = client.post(f"{api_base}/ask", json=payload)
        except TRANSIENT_HTTP_ERRORS as exc:
            last_exc = exc
            current_role = None
            if attempt + 1 >= 4:
                break
            print(
                f"{type(exc).__name__} on POST {api_base}/ask ({case.id}); "
                f"retry {attempt + 1}/3 after waiting for /health",
                flush=True,
            )
            time.sleep(1.0 * (attempt + 1))
            try:
                wait_for_health_ready(client, api_base, health_timeout_sec)
            except RuntimeError:
                pass
            continue
        latency_ms = (time.perf_counter() - started) * 1000
        break
    if response is None:
        assert last_exc is not None
        raise last_exc
    response.raise_for_status()
    body = response.json()

    refusal = is_refusal(body)
    source_accurate, source_reason = evaluate_source_accuracy(case, body)
    actual_hit = bool(body.get("hit"))
    expected_refusal = not case.expected_hit
    source_spaces = [str(item.get("space_id", "")) for item in body.get("sources", [])]
    answer = str(body.get("answer", "")).strip().replace("\n", " ")
    answer_preview = answer[:120]
    llm_called = bool(body.get("llm_called"))
    prompt_tokens = int(body.get("prompt_tokens") or 0)
    completion_tokens = int(body.get("completion_tokens") or 0)

    assert current_role is not None
    return (
        CaseResult(
            id=case.id,
            category=case.category,
            role=case.role,
            expected_hit=case.expected_hit,
            actual_hit=actual_hit,
            hit_match=(actual_hit == case.expected_hit),
            refusal=refusal,
            refusal_match=(refusal == expected_refusal),
            source_accurate=source_accurate,
            source_reason=source_reason,
            source_count=len(body.get("sources", [])),
            source_spaces=source_spaces,
            answer_preview=answer_preview,
            latency_ms=latency_ms,
            llm_called=llm_called,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            isolation_ok=check_isolation(case.role, source_spaces),
        ),
        current_role,
    )


def run_oracle_case(case: EvalCase) -> CaseResult:
    source_spaces = list(case.expected_spaces) if case.expected_hit else []
    answer_preview = "oracle-hit" if case.expected_hit else MISS_ANSWER
    llm_called = bool(case.expected_hit)
    return CaseResult(
        id=case.id,
        category=case.category,
        role=case.role,
        expected_hit=case.expected_hit,
        actual_hit=case.expected_hit,
        hit_match=True,
        refusal=not case.expected_hit,
        refusal_match=True,
        source_accurate=True,
        source_reason="ok",
        source_count=(1 if case.expected_hit else 0),
        source_spaces=source_spaces,
        answer_preview=answer_preview,
        latency_ms=0.0,
        llm_called=llm_called,
        prompt_tokens=(100 if llm_called else 0),
        completion_tokens=(50 if llm_called else 0),
        isolation_ok=check_isolation(case.role, source_spaces),
    )


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def estimate_cost_cny(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    prompt_price_per_1m: float,
    completion_price_per_1m: float,
) -> float:
    return (
        prompt_tokens * prompt_price_per_1m + completion_tokens * completion_price_per_1m
    ) / 1_000_000.0


def summarize_results(
    results: list[CaseResult],
    *,
    prompt_price_per_1m: float,
    completion_price_per_1m: float,
) -> dict[str, Any]:
    categories = sorted({result.category for result in results})
    summary: dict[str, Any] = {
        "overall": summarize_group(
            "overall",
            results,
            prompt_price_per_1m=prompt_price_per_1m,
            completion_price_per_1m=completion_price_per_1m,
        ),
        "by_category": {},
        "pricing": {
            "currency": "CNY",
            "prompt_price_per_1m": prompt_price_per_1m,
            "completion_price_per_1m": completion_price_per_1m,
        },
    }
    for category in categories:
        group = [item for item in results if item.category == category]
        summary["by_category"][category] = summarize_group(
            category,
            group,
            prompt_price_per_1m=prompt_price_per_1m,
            completion_price_per_1m=completion_price_per_1m,
        )
    return summary


def summarize_group(
    name: str,
    group: list[CaseResult],
    *,
    prompt_price_per_1m: float,
    completion_price_per_1m: float,
) -> dict[str, Any]:
    total = len(group)
    hit_count = sum(1 for item in group if item.actual_hit)
    refusal_count = sum(1 for item in group if item.refusal)
    source_accurate_count = sum(1 for item in group if item.source_accurate)
    hit_match_count = sum(1 for item in group if item.hit_match)
    refusal_match_count = sum(1 for item in group if item.refusal_match)
    isolation_ok_count = sum(1 for item in group if item.isolation_ok)

    hit_cases = [item for item in group if item.actual_hit]
    miss_cases = [item for item in group if not item.actual_hit]
    expected_hits = [item for item in group if item.expected_hit]
    expected_misses = [item for item in group if not item.expected_hit]
    source_accurate_on_hit = sum(1 for item in hit_cases if item.source_accurate)
    # Recall@k：期望命中样本中，返回来源含期望空间/标题关键词的比例（k=接口返回条数）
    recall_hits = sum(1 for item in expected_hits if item.source_accurate)
    correct_refusals = sum(
        1
        for item in expected_misses
        if item.refusal and (not item.llm_called) and item.isolation_ok
    )

    latencies = [item.latency_ms for item in group if item.latency_ms is not None]
    hit_latencies = [item.latency_ms for item in hit_cases if item.latency_ms is not None]
    miss_latencies = [item.latency_ms for item in miss_cases if item.latency_ms is not None]

    total_prompt = sum(item.prompt_tokens for item in group)
    total_completion = sum(item.completion_tokens for item in group)
    hit_prompt = sum(item.prompt_tokens for item in hit_cases)
    hit_completion = sum(item.completion_tokens for item in hit_cases)
    refusal_prompt = sum(item.prompt_tokens for item in miss_cases)
    refusal_completion = sum(item.completion_tokens for item in miss_cases)
    total_cost = estimate_cost_cny(
        total_prompt,
        total_completion,
        prompt_price_per_1m=prompt_price_per_1m,
        completion_price_per_1m=completion_price_per_1m,
    )
    avg_hit_prompt = (hit_prompt / len(hit_cases)) if hit_cases else 0.0
    avg_hit_completion = (hit_completion / len(hit_cases)) if hit_cases else 0.0
    counterfactual_prompt = total_prompt + int(round(avg_hit_prompt * len(expected_misses)))
    counterfactual_completion = total_completion + int(
        round(avg_hit_completion * len(expected_misses))
    )
    counterfactual_cost = estimate_cost_cny(
        counterfactual_prompt,
        counterfactual_completion,
        prompt_price_per_1m=prompt_price_per_1m,
        completion_price_per_1m=completion_price_per_1m,
    )

    return {
        "name": name,
        "total": total,
        "hit_count": hit_count,
        "refusal_count": refusal_count,
        "source_accurate_count": source_accurate_count,
        "hit_match_count": hit_match_count,
        "refusal_match_count": refusal_match_count,
        "isolation_ok_count": isolation_ok_count,
        "expected_hit_count": len(expected_hits),
        "expected_miss_count": len(expected_misses),
        "recall_hit_count": recall_hits,
        "correct_refusal_count": correct_refusals,
        "hit_rate": ratio(hit_count, total),
        "refusal_rate": ratio(refusal_count, total),
        "source_accuracy_rate": ratio(source_accurate_count, total),
        "hit_match_rate": ratio(hit_match_count, total),
        "refusal_match_rate": ratio(refusal_match_count, total),
        "source_accuracy_rate_on_hit": ratio(source_accurate_on_hit, len(hit_cases)),
        "isolation_ok_rate": ratio(isolation_ok_count, total),
        "recall_at_k": ratio(recall_hits, len(expected_hits)),
        "correct_refusal_rate": ratio(correct_refusals, len(expected_misses)),
        "avg_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "hit_avg_latency_ms": mean(hit_latencies),
        "refusal_avg_latency_ms": mean(miss_latencies),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "hit_prompt_tokens": hit_prompt,
        "hit_completion_tokens": hit_completion,
        "refusal_prompt_tokens": refusal_prompt,
        "refusal_completion_tokens": refusal_completion,
        "llm_called_count": sum(1 for item in group if item.llm_called),
        "total_cost_cny": total_cost,
        "avg_cost_cny_per_query": (total_cost / total) if total else 0.0,
        "counterfactual_all_llm_cost_cny": counterfactual_cost,
        "cost_saved_by_refusal_cny": max(0.0, counterfactual_cost - total_cost),
    }


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"


def _fmt_cny(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.6f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2%}"


def build_markdown(
    mode: str,
    api_base: str,
    case_file: str,
    summary: dict[str, Any],
    results: list[CaseResult],
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    overall = summary["overall"]
    pricing = summary.get("pricing", {})
    title = "Phase 1 评测基线" if overall["total"] > 12 else "Phase 1 最小评测基线"

    lines = [
        f"# {title}",
        "",
        f"- 运行模式：`{mode}`",
        f"- 生成时间：{generated_at}",
        f"- API：`{api_base}`",
        f"- 评测集：`{case_file}`",
        f"- 样本数：{overall['total']}",
        (
            f"- 计价假设：prompt ¥{pricing.get('prompt_price_per_1m', '-')}/M · "
            f"completion ¥{pricing.get('completion_price_per_1m', '-')}/M"
        ),
        "",
        "## 基线指标（Overall）",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 命中率 (hit/total) | {overall['hit_count']}/{overall['total']} = {overall['hit_rate']:.2%} |",
        f"| 拒答率 (refusal/total) | {overall['refusal_count']}/{overall['total']} = {overall['refusal_rate']:.2%} |",
        (
            f"| Recall@k (期望命中且来源准确) | {overall['recall_hit_count']}/"
            f"{overall['expected_hit_count']} = {overall['recall_at_k']:.2%} |"
        ),
        (
            f"| 正确拒答率 (期望未命中且固定拒答、未调模型) | {overall['correct_refusal_count']}/"
            f"{overall['expected_miss_count']} = {overall['correct_refusal_rate']:.2%} |"
        ),
        f"| 来源准确率 (source-accurate/total) | {overall['source_accurate_count']}/{overall['total']} = {overall['source_accuracy_rate']:.2%} |",
        f"| 隔离通过率 (isolation_ok/total) | {overall['isolation_ok_count']}/{overall['total']} = {overall['isolation_ok_rate']:.2%} |",
        f"| 平均延迟 ms | {_fmt_ms(overall['avg_latency_ms'])} |",
        f"| P95 延迟 ms | {_fmt_ms(overall['p95_latency_ms'])} |",
        f"| 命中路径平均延迟 ms | {_fmt_ms(overall['hit_avg_latency_ms'])} |",
        f"| 拒答路径平均延迟 ms | {_fmt_ms(overall['refusal_avg_latency_ms'])} |",
        f"| 命中 prompt+completion token | {overall['hit_prompt_tokens']}+{overall['hit_completion_tokens']} |",
        f"| 拒答 prompt+completion token | {overall['refusal_prompt_tokens']}+{overall['refusal_completion_tokens']} |",
        f"| 调用 LLM 次数 | {overall['llm_called_count']}/{overall['total']} |",
        f"| 估算总成本 CNY | {_fmt_cny(overall['total_cost_cny'])} |",
        f"| 估算单次成本 CNY | {_fmt_cny(overall['avg_cost_cny_per_query'])} |",
        f"| 拒答相对「全量调模型」节省 CNY | {_fmt_cny(overall['cost_saved_by_refusal_cny'])} |",
        "",
        "## 分类别指标",
        "",
        "| 类别 | 样本数 | 命中率 | 拒答率 | Recall@k | 正确拒答率 | 隔离通过率 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for category, cat_summary in summary["by_category"].items():
        lines.append(
            f"| {category} | {cat_summary['total']} | {cat_summary['hit_rate']:.2%} | "
            f"{cat_summary['refusal_rate']:.2%} | {cat_summary['recall_at_k']:.2%} | "
            f"{cat_summary['correct_refusal_rate']:.2%} | {cat_summary['isolation_ok_rate']:.2%} |"
        )

    if mode == "oracle":
        lines.extend(
            [
                "",
                "> 说明：本次为 `oracle` 合成基线（按评测集期望标签生成），用于先固化指标口径。",
                "> 命中样本的 token 为占位值（prompt=100, completion=50），拒答为 0；延迟为 0。",
                "> 真实系统基线请在 API/数据库/向量模型可用后用 `--mode live` 重跑。",
            ]
        )

    lines.extend(
        [
            "",
            "## 样本明细",
            "",
            "| id | category | role | hit | refusal | isolation_ok | llm_called | prompt | completion | latency_ms | source_spaces |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in results:
        source_spaces = ",".join(item.source_spaces) if item.source_spaces else "-"
        latency = _fmt_ms(item.latency_ms)
        lines.append(
            f"| {item.id} | {item.category} | {item.role} | {item.actual_hit} | "
            f"{item.refusal} | {item.isolation_ok} | {item.llm_called} | "
            f"{item.prompt_tokens} | {item.completion_tokens} | {latency} | {source_spaces} |"
        )

    return "\n".join(lines) + "\n"


def _metric_row(label: str, before: str, after: str, note: str = "") -> str:
    suffix = f" | {note}" if note else " |"
    return f"| {label} | {before} | {after}{suffix}"


def enrich_report_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """旧基线 JSON 可能缺 Recall/成本字段：若有 results 则按现口径重算 overall。"""
    results_raw = report.get("results")
    if not isinstance(results_raw, list) or not results_raw:
        return report
    try:
        results = [CaseResult(**item) for item in results_raw]
    except TypeError:
        return report
    pricing = (report.get("metrics") or {}).get("pricing") or {}
    prompt_price = float(pricing.get("prompt_price_per_1m", 1.0))
    completion_price = float(pricing.get("completion_price_per_1m", 2.0))
    report = dict(report)
    report["metrics"] = summarize_results(
        results,
        prompt_price_per_1m=prompt_price,
        completion_price_per_1m=completion_price,
    )
    return report


def build_comparison_markdown(
    *,
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
    case_file: str,
) -> str:
    """一页优化对比：相对课上小样本基线 + 拒答成本收益。"""
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    cur = current["metrics"]["overall"]
    pricing = current["metrics"].get("pricing", {})
    base_overall = (baseline or {}).get("metrics", {}).get("overall") if baseline else None
    base_count = (baseline or {}).get("sample_count")
    base_mode = (baseline or {}).get("mode", "-")

    def _b(key: str, fmt: str = "pct") -> str:
        if not base_overall or key not in base_overall or base_overall[key] is None:
            return "-"
        value = base_overall[key]
        if fmt == "pct":
            return _fmt_pct(float(value))
        if fmt == "ms":
            return _fmt_ms(float(value))
        if fmt == "cny":
            return _fmt_cny(float(value))
        return str(value)

    lines = [
        "# 评测闭环：一页优化对比",
        "",
        f"- 生成时间：{generated_at}",
        f"- 当前评测集：`{case_file}`（{current.get('sample_count')} 条，`{current.get('mode')}`）",
        (
            f"- 对照基线：{'`'+str((baseline or {}).get('case_file','-'))+'`' if baseline else '无'} "
            f"（{base_count or '-'} 条，`{base_mode}`）"
        ),
        (
            f"- 计价：prompt ¥{pricing.get('prompt_price_per_1m', 1.0)}/M · "
            f"completion ¥{pricing.get('completion_price_per_1m', 2.0)}/M（可用环境变量覆盖）"
        ),
        "",
        "## 结论",
        "",
        (
            f"在 {cur['total']} 条样本上，Recall@k={cur['recall_at_k']:.2%}，"
            f"正确拒答率={cur['correct_refusal_rate']:.2%}，隔离通过率={cur['isolation_ok_rate']:.2%}；"
            f"平均延迟 {_fmt_ms(cur['avg_latency_ms'])} ms（P95 {_fmt_ms(cur['p95_latency_ms'])}），"
            f"估算单次成本 ¥{_fmt_cny(cur['avg_cost_cny_per_query'])}。"
            f"相对「期望拒答也调模型」的反事实，本轮拒答节省约 ¥{_fmt_cny(cur['cost_saved_by_refusal_cny'])}。"
        ),
        "",
        "## 指标对照",
        "",
        "| 指标 | 对照基线 | 当前闭环 | 说明 |",
        "| --- | --- | --- | --- |",
        _metric_row("样本数", str(base_count or "-"), str(cur["total"]), "课上 12 → 闭环 50+"),
        _metric_row("Recall@k", _b("recall_at_k"), _fmt_pct(cur["recall_at_k"]), "期望命中且来源准确"),
        _metric_row(
            "正确拒答率",
            _b("correct_refusal_rate"),
            _fmt_pct(cur["correct_refusal_rate"]),
            "含 no_answer / isolation 负样本",
        ),
        _metric_row("拒答率", _b("refusal_rate"), _fmt_pct(cur["refusal_rate"]), "实际固定拒答占比"),
        _metric_row("隔离通过率", _b("isolation_ok_rate"), _fmt_pct(cur["isolation_ok_rate"]), "须 100%"),
        _metric_row("平均延迟 ms", _b("avg_latency_ms", "ms"), _fmt_ms(cur["avg_latency_ms"]), ""),
        _metric_row("P95 延迟 ms", _b("p95_latency_ms", "ms"), _fmt_ms(cur["p95_latency_ms"]), ""),
        _metric_row(
            "单次成本 CNY",
            _b("avg_cost_cny_per_query", "cny"),
            _fmt_cny(cur["avg_cost_cny_per_query"]),
            "按 token × 单价",
        ),
        "",
        "## 拒答对成本的贡献",
        "",
        "| 项 | 数值 |",
        "| --- | --- |",
        f"| 实际估算总成本 | ¥{_fmt_cny(cur['total_cost_cny'])} |",
        f"| 反事实（期望拒答也按命中均摊调模型） | ¥{_fmt_cny(cur['counterfactual_all_llm_cost_cny'])} |",
        f"| 拒答节省 | ¥{_fmt_cny(cur['cost_saved_by_refusal_cny'])} |",
        f"| 调用 LLM 次数 | {cur['llm_called_count']}/{cur['total']} |",
        "",
        "## 仍薄弱的地方",
        "",
        "1. 语料仍是两份 T13 样例文档，Recall 高不代表复杂语料下的检索质量。",
        "2. 单价为评测假设，需按实际 DeepSeek 账单校准。",
        "3. 未单独跑「关 hybrid / 关 rerank」对照；工程上可改环境变量后重跑本脚本对比。",
        "4. 本页由脚本生成；若 live 时关闭了 rerank，Recall/正确拒答率可能低于默认双开配置。",
        "",
        "## 复现命令",
        "",
        "```powershell",
        "python .\\scripts\\run_phase1_eval.py --mode live `",
        "  --case-file docs\\samples\\eval\\phase1_extended_eval_set.jsonl `",
        "  --output-json docs\\phase1_eval_extended.json `",
        "  --output-md docs\\phase1_eval_extended.md `",
        "  --baseline-json docs\\phase1_eval_baseline.json `",
        "  --write-comparison docs\\16-评测闭环对比.md",
        "```",
        "",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def evaluate_gate(results: list[CaseResult]) -> GateVerdict:
    """隔离必须 100%；期望未命中不得调模型。命中率偏低只警告。"""
    failures: list[str] = []
    warnings: list[str] = []

    isolation_failed = [item.id for item in results if not item.isolation_ok]
    if isolation_failed:
        failures.append("隔离未通过: " + ", ".join(isolation_failed))

    leaked_llm = [item.id for item in results if (not item.expected_hit) and item.llm_called]
    if leaked_llm:
        failures.append("期望未命中却调用了模型: " + ", ".join(leaked_llm))

    expected_hits = [item for item in results if item.expected_hit]
    if expected_hits:
        hit_on_expected = ratio(sum(1 for item in expected_hits if item.actual_hit), len(expected_hits))
        if hit_on_expected < 0.5:
            warnings.append(
                f"期望命中样本的实际命中率 {hit_on_expected:.0%} 偏低，不挡发版"
            )

    return GateVerdict(passed=not failures, failures=tuple(failures), warnings=tuple(warnings))


def main() -> int:
    args = parse_args()

    api_base = args.api_base.rstrip("/")
    case_file = Path(args.case_file)
    student_doc = Path(args.student_doc)
    company_doc = Path(args.company_doc)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    cases = load_cases(case_file)
    extra_file = Path(args.gate_extra_file)
    if args.gate:
        cases = merge_cases(cases, load_cases(extra_file))
    # 同角色连跑，减少登录切换与限流压力
    role_order = {"student": 0, "employee": 1, "teaching": 2}
    cases = sorted(cases, key=lambda item: (role_order.get(item.role, 9), item.id))

    if args.mode == "live":
        with make_http_client(args.timeout_sec, api_base) as client:
            wait_for_health_ready(client, api_base=api_base, timeout_sec=args.health_timeout_sec)
            if not args.skip_upload:
                login_as_teaching_for_upload(
                    client, api_base, args.demo_password, args.health_timeout_sec
                )
                upload_sample_doc(
                    client, api_base, student_doc, "student", args.health_timeout_sec
                )
                upload_sample_doc(
                    client, api_base, company_doc, "company", args.health_timeout_sec
                )
                wait_for_health_ready(
                    client, api_base=api_base, timeout_sec=args.health_timeout_sec
                )
            results: list[CaseResult] = []
            logged_in_role: str | None = None
            for case in cases:
                result, logged_in_role = run_case(
                    client,
                    api_base,
                    case,
                    demo_password=args.demo_password,
                    health_timeout_sec=args.health_timeout_sec,
                    logged_in_role=logged_in_role,
                )
                results.append(result)
                print(
                    f"[{len(results)}/{len(cases)}] {case.id} hit={result.actual_hit} "
                    f"refusal={result.refusal} {result.latency_ms:.0f}ms",
                    flush=True,
                )
    else:
        results = [run_oracle_case(case) for case in cases]

    summary = summarize_results(
        results,
        prompt_price_per_1m=args.prompt_price_per_1m,
        completion_price_per_1m=args.completion_price_per_1m,
    )
    report = {
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "case_file": str(case_file),
        "sample_count": len(results),
        "gate": bool(args.gate),
        "metrics": summary,
        "results": [asdict(item) for item in results],
    }
    markdown = build_markdown(args.mode, api_base, str(case_file), summary, results)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")

    if args.write_comparison:
        baseline_payload: dict[str, Any] | None = None
        if args.baseline_json:
            baseline_path = Path(args.baseline_json)
            if baseline_path.exists():
                baseline_payload = enrich_report_metrics(
                    json.loads(baseline_path.read_text(encoding="utf-8"))
                )
        comparison_path = Path(args.write_comparison)
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_path.write_text(
            build_comparison_markdown(
                current=report,
                baseline=baseline_payload,
                case_file=str(case_file),
            ),
            encoding="utf-8",
        )
        print(f"comparison={comparison_path}")

    overall = summary["overall"]
    print("Phase1 eval done.")
    print(f"hit_rate={overall['hit_rate']:.2%}")
    print(f"refusal_rate={overall['refusal_rate']:.2%}")
    print(f"recall_at_k={overall['recall_at_k']:.2%}")
    print(f"correct_refusal_rate={overall['correct_refusal_rate']:.2%}")
    print(f"source_accuracy_rate={overall['source_accuracy_rate']:.2%}")
    print(f"isolation_ok_rate={overall['isolation_ok_rate']:.2%}")
    print(f"avg_latency_ms={overall['avg_latency_ms']}")
    print(f"p95_latency_ms={overall['p95_latency_ms']}")
    print(f"avg_cost_cny_per_query={overall['avg_cost_cny_per_query']:.6f}")
    print(
        "tokens hit="
        f"{overall['hit_prompt_tokens']}+{overall['hit_completion_tokens']} "
        f"refusal={overall['refusal_prompt_tokens']}+{overall['refusal_completion_tokens']}"
    )
    print(f"json={output_json}")
    print(f"markdown={output_md}")

    if args.gate:
        verdict = evaluate_gate(results)
        for warning in verdict.warnings:
            print(f"gate warning: {warning}", flush=True)
        if not verdict.passed:
            for failure in verdict.failures:
                print(f"gate failed: {failure}", flush=True)
            return 2
        print("gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
