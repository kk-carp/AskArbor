import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase1_eval.py"


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("run_phase1_eval", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(module, **overrides):
    payload = {
        "id": "case-1",
        "category": "isolation",
        "role": "student",
        "expected_hit": False,
        "actual_hit": False,
        "hit_match": True,
        "refusal": True,
        "refusal_match": True,
        "source_accurate": True,
        "source_reason": "ok",
        "source_count": 0,
        "source_spaces": [],
        "answer_preview": "",
        "latency_ms": 1.0,
        "llm_called": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "isolation_ok": True,
    }
    payload.update(overrides)
    return module.CaseResult(**payload)


def test_check_isolation_student_and_employee() -> None:
    module = _load_eval_module()
    assert module.check_isolation("student", ["student"]) is True
    assert module.check_isolation("student", ["company"]) is False
    assert module.check_isolation("employee", ["company"]) is True
    assert module.check_isolation("employee", ["student"]) is False
    assert module.check_isolation("teaching", ["student", "company"]) is True


def test_evaluate_gate_passes_clean_results() -> None:
    module = _load_eval_module()
    verdict = module.evaluate_gate(
        [
            _result(module, id="iso-ok", isolation_ok=True, expected_hit=False, llm_called=False),
            _result(
                module,
                id="hit-ok",
                category="course",
                expected_hit=True,
                actual_hit=True,
                llm_called=True,
                isolation_ok=True,
            ),
        ]
    )
    assert verdict.passed is True
    assert verdict.failures == ()


def test_evaluate_gate_fails_on_isolation_and_miss_llm() -> None:
    module = _load_eval_module()
    verdict = module.evaluate_gate(
        [
            _result(module, id="iso-leak", isolation_ok=False, source_spaces=["company"]),
            _result(module, id="miss-llm", expected_hit=False, llm_called=True),
        ]
    )
    assert verdict.passed is False
    assert any("隔离未通过" in item and "iso-leak" in item for item in verdict.failures)
    assert any("期望未命中却调用了模型" in item and "miss-llm" in item for item in verdict.failures)


def test_evaluate_gate_warns_on_low_hit_but_still_passes() -> None:
    module = _load_eval_module()
    verdict = module.evaluate_gate(
        [
            _result(
                module,
                id="should-hit",
                category="course",
                expected_hit=True,
                actual_hit=False,
                llm_called=False,
            ),
        ]
    )
    assert verdict.passed is True
    assert verdict.warnings


def test_oracle_gate_exits_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_eval_module()
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_phase1_eval.py",
            "--mode",
            "oracle",
            "--gate",
            "--output-json",
            str(tmp_path / "gate.json"),
            "--output-md",
            str(tmp_path / "gate.md"),
        ],
    )
    assert module.main() == 0
    report = (tmp_path / "gate.json").read_text(encoding="utf-8")
    assert '"gate": true' in report
    assert "isolation-employee-deadline" in report


def test_oracle_without_gate_keeps_twelve_homework_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_eval_module()
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_phase1_eval.py",
            "--mode",
            "oracle",
            "--output-json",
            str(tmp_path / "hw.json"),
            "--output-md",
            str(tmp_path / "hw.md"),
        ],
    )
    assert module.main() == 0
    report = (tmp_path / "hw.json").read_text(encoding="utf-8")
    assert '"sample_count": 12' in report
    assert "isolation-employee-deadline" not in report
    assert '"gate": false' in report
