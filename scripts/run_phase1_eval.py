from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"
ROLE_TO_USERNAME = {
    "student": "student_demo",
    "employee": "employee_demo",
    "teaching": "teaching_demo",
}


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run phase-1 minimal evaluation and export baseline metrics."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--case-file",
        default="docs/samples/eval/phase1_minimal_eval_set.jsonl",
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
    parser.add_argument("--timeout-sec", type=float, default=30.0)
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
    return parser.parse_args()


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
    raise RuntimeError(f"Health check not ready within {timeout_sec}s; last={last_payload}")


def upload_sample_doc(client: httpx.Client, api_base: str, path: Path, space: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Sample document not found: {path}")
    with path.open("rb") as content:
        files = {"file": (path.name, content, "text/markdown")}
        data = {"space": space}
        response = client.post(f"{api_base}/documents", data=data, files=files)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ready":
        raise RuntimeError(f"Uploaded document not ready: {path.name}, payload={payload}")
    if int(payload.get("chunk_count", 0)) <= 0:
        raise RuntimeError(f"Uploaded document has no chunks: {path.name}, payload={payload}")


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


def login_demo_user(client: httpx.Client, api_base: str, role: str, password: str) -> None:
    username = ROLE_TO_USERNAME.get(role)
    if not username:
        raise ValueError(f"No demo account mapped for role: {role}")
    response = client.post(
        f"{api_base}/login",
        json={"username": username, "password": password},
    )
    response.raise_for_status()


def run_case(
    client: httpx.Client,
    api_base: str,
    case: EvalCase,
    demo_password: str,
) -> CaseResult:
    login_demo_user(client, api_base, case.role, demo_password)
    payload = {"question": case.question}
    response = client.post(f"{api_base}/ask", json=payload)
    response.raise_for_status()
    body = response.json()

    refusal = is_refusal(body)
    source_accurate, source_reason = evaluate_source_accuracy(case, body)
    actual_hit = bool(body.get("hit"))
    expected_refusal = not case.expected_hit
    source_spaces = [str(item.get("space_id", "")) for item in body.get("sources", [])]
    answer = str(body.get("answer", "")).strip().replace("\n", " ")
    answer_preview = answer[:120]

    return CaseResult(
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
    )


def run_oracle_case(case: EvalCase) -> CaseResult:
    source_spaces = list(case.expected_spaces) if case.expected_hit else []
    answer_preview = "oracle-hit" if case.expected_hit else MISS_ANSWER
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
    )


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def summarize_results(results: list[CaseResult]) -> dict[str, Any]:
    categories = sorted({result.category for result in results})
    summary: dict[str, Any] = {
        "overall": summarize_group("overall", results),
        "by_category": {},
    }
    for category in categories:
        group = [item for item in results if item.category == category]
        summary["by_category"][category] = summarize_group(category, group)
    return summary


def summarize_group(name: str, group: list[CaseResult]) -> dict[str, Any]:
    total = len(group)
    hit_count = sum(1 for item in group if item.actual_hit)
    refusal_count = sum(1 for item in group if item.refusal)
    source_accurate_count = sum(1 for item in group if item.source_accurate)
    hit_match_count = sum(1 for item in group if item.hit_match)
    refusal_match_count = sum(1 for item in group if item.refusal_match)

    hit_cases = [item for item in group if item.actual_hit]
    source_accurate_on_hit = sum(1 for item in hit_cases if item.source_accurate)

    return {
        "name": name,
        "total": total,
        "hit_count": hit_count,
        "refusal_count": refusal_count,
        "source_accurate_count": source_accurate_count,
        "hit_match_count": hit_match_count,
        "refusal_match_count": refusal_match_count,
        "hit_rate": ratio(hit_count, total),
        "refusal_rate": ratio(refusal_count, total),
        "source_accuracy_rate": ratio(source_accurate_count, total),
        "hit_match_rate": ratio(hit_match_count, total),
        "refusal_match_rate": ratio(refusal_match_count, total),
        "source_accuracy_rate_on_hit": ratio(source_accurate_on_hit, len(hit_cases)),
    }


def build_markdown(
    mode: str,
    api_base: str,
    case_file: str,
    summary: dict[str, Any],
    results: list[CaseResult],
) -> str:
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    overall = summary["overall"]

    lines = [
        "# Phase 1 最小评测基线",
        "",
        f"- 运行模式：`{mode}`",
        f"- 生成时间：{generated_at}",
        f"- API：`{api_base}`",
        f"- 评测集：`{case_file}`",
        f"- 样本数：{overall['total']}",
        "",
        "## 基线指标（Overall）",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 命中率 (hit/total) | {overall['hit_count']}/{overall['total']} = {overall['hit_rate']:.2%} |",
        f"| 拒答率 (refusal/total) | {overall['refusal_count']}/{overall['total']} = {overall['refusal_rate']:.2%} |",
        f"| 来源准确率 (source-accurate/total) | {overall['source_accurate_count']}/{overall['total']} = {overall['source_accuracy_rate']:.2%} |",
        "",
        "## 分类别指标",
        "",
        "| 类别 | 样本数 | 命中率 | 拒答率 | 来源准确率 |",
        "| --- | --- | --- | --- | --- |",
    ]
    if mode == "oracle":
        lines.extend(
            [
                "",
                "> 说明：本次为 `oracle` 合成基线（按评测集期望标签生成），用于先固化指标口径。",
                "> 真实系统基线请在 API/数据库/向量模型可用后用 `--mode live` 重跑。",
            ]
        )

    for category, cat_summary in summary["by_category"].items():
        lines.append(
            f"| {category} | {cat_summary['total']} | {cat_summary['hit_rate']:.2%} | "
            f"{cat_summary['refusal_rate']:.2%} | {cat_summary['source_accuracy_rate']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## 样本明细",
            "",
            "| id | category | role | expected_hit | actual_hit | refusal | source_accurate | source_spaces |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in results:
        source_spaces = ",".join(item.source_spaces) if item.source_spaces else "-"
        lines.append(
            f"| {item.id} | {item.category} | {item.role} | {item.expected_hit} | {item.actual_hit} | "
            f"{item.refusal} | {item.source_accurate} | {source_spaces} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()

    api_base = args.api_base.rstrip("/")
    case_file = Path(args.case_file)
    student_doc = Path(args.student_doc)
    company_doc = Path(args.company_doc)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    cases = load_cases(case_file)

    if args.mode == "live":
        with httpx.Client(timeout=args.timeout_sec) as client:
            wait_for_health_ready(client, api_base=api_base, timeout_sec=args.health_timeout_sec)
        if not args.skip_upload:
            upload_sample_doc(client, api_base, student_doc, "student")
            upload_sample_doc(client, api_base, company_doc, "company")
        results = [
            run_case(client, api_base, case, demo_password=args.demo_password) for case in cases
        ]
    else:
        results = [run_oracle_case(case) for case in cases]

    summary = summarize_results(results)
    report = {
        "mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "case_file": str(case_file),
        "sample_count": len(results),
        "metrics": summary,
        "results": [asdict(item) for item in results],
    }
    markdown = build_markdown(args.mode, api_base, str(case_file), summary, results)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(markdown, encoding="utf-8")

    overall = summary["overall"]
    print("Phase1 eval done.")
    print(f"hit_rate={overall['hit_rate']:.2%}")
    print(f"refusal_rate={overall['refusal_rate']:.2%}")
    print(f"source_accuracy_rate={overall['source_accuracy_rate']:.2%}")
    print(f"json={output_json}")
    print(f"markdown={output_md}")


if __name__ == "__main__":
    main()
