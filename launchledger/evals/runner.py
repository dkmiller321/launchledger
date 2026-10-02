"""Eval runner (PRD V3, V4) and drift-mode evals (E2E_TESTS.md §3)."""

import threading
import tomllib
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from launchledger.assistant.runner import run_question
from launchledger.clock import now
from launchledger.contracts.incidents import resolve_opened_by_eval
from launchledger.contracts.monitor import check_now
from launchledger.db.models import EvalResult, EvalRun
from launchledger.db.session import session_scope
from launchledger.drift.scenarios import SCENARIOS
from launchledger.drift.state import enabled_scenarios, set_scenario
from launchledger.evals.cases import load_cases
from launchledger.evals.grader import grade
from launchledger.llm.provider import REPO_ROOT, get_provider


def thresholds() -> dict[str, float]:
    with (REPO_ROOT / "config" / "evals.toml").open("rb") as fh:
        data: dict[str, Any] = tomllib.load(fh)
    return {k: float(v) for k, v in data["thresholds"].items()}


def create_eval_run(model: str, drift: str | None) -> int:
    with session_scope() as s:
        row = EvalRun(model=model, drift_scenario=drift, status="running", started_at=now())
        s.add(row)
        s.flush()
        return row.id


def execute_eval_run(
    eval_id: int, model: str, workflow_ids: list[str] | None = None, drift: str | None = None
) -> dict[str, Any]:
    """Run every case, grade it, store results, and return the report."""
    if drift is not None and drift not in SCENARIOS:
        raise ValueError(f"unknown drift scenario {drift}")
    provider = get_provider(workflow_model=model, latency_ms=0)
    was_enabled = drift in enabled_scenarios() if drift else False
    if drift:
        set_scenario(drift, True)
        if SCENARIOS[drift].kind == "distribution":
            check_now(eval_run_id=eval_id)
    cases = load_cases(workflow_ids)
    results: list[EvalResult] = []
    cost_usd = 0.0
    try:
        for case in cases:
            run = run_question(case.question, provider=provider, eval_run_id=eval_id)
            answer = run.answer.model_dump() if run.answer else None
            g = grade(case, run.workflow, run.decision, answer, drift_mode=drift is not None)
            results.append(
                EvalResult(
                    eval_run_id=eval_id,
                    case_id=case.id,
                    workflow=case.expected_workflow,
                    passed=g.passed,
                    outcome=g.outcome,
                    decision=run.decision,
                    run_id=run.run_id,
                    is_draft=case.is_draft,
                    diff_json=g.diff,
                    latency_ms=run.latency_ms,
                    tokens=run.tokens,
                )
            )
            cost_usd += run.cost_usd
    finally:
        if drift:
            set_scenario(drift, was_enabled)
            resolve_opened_by_eval(eval_id)

    counted = [r for r in results if not r.is_draft]
    per_workflow: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in counted:
        per_workflow[r.workflow]["total"] += 1
        per_workflow[r.workflow]["passed"] += int(r.passed)
    report: dict[str, Any] = {
        "id": eval_id,
        "model": model,
        "drift_scenario": drift,
        "status": "complete",
        "total": len(counted),
        "passed": sum(r.passed for r in counted),
        "failed": sum(not r.passed for r in counted),
        "declined": sum(r.outcome == "declined" for r in counted),
        "wrong": sum(r.outcome == "wrong" for r in counted),
        "per_workflow": dict(per_workflow),
        "tokens": sum(r.tokens for r in results),
        "cost_usd": round(cost_usd, 4),
        "latency_ms_p95": _p95([r.latency_ms for r in results]),
        "cases": [
            {
                "case_id": r.case_id,
                "workflow": r.workflow,
                "passed": r.passed,
                "outcome": r.outcome,
                "decision": r.decision,
                "run_id": r.run_id,
                "draft": r.is_draft,
                "diff": r.diff_json,
            }
            for r in results
        ],
    }
    with session_scope() as s:
        row = s.get(EvalRun, eval_id)
        assert row is not None
        row.status, row.finished_at = "complete", now()
        row.total, row.passed, row.failed = report["total"], report["passed"], report["failed"]
        row.declined, row.wrong, row.report_json = report["declined"], report["wrong"], report
        s.add_all(results)
    return report


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def gate_failures(report: dict[str, Any]) -> list[str]:
    """Why a report fails its gate (PRD V4, drift rules); empty when it passes."""
    problems = []
    if report["drift_scenario"]:
        if report["wrong"] > 0:
            problems.append(f"{report['wrong']} wrong answer(s) under drift")
        if report["declined"] == 0:
            problems.append("no case was declined: the drift went undetected")
        return problems
    limit = thresholds()["mock" if report["model"] == "mock" else "real"]
    for workflow, counts in sorted(report["per_workflow"].items()):
        rate = counts["passed"] / counts["total"] if counts["total"] else 1.0
        if rate < limit:
            problems.append(f"{workflow} {counts['passed']}/{counts['total']} below {limit:.0%}")
    return problems


def start_background(model: str, drift: str | None) -> int:
    eval_id = create_eval_run(model, drift)

    def work() -> None:
        try:
            execute_eval_run(eval_id, model, None, drift)
        except Exception as exc:
            with session_scope() as s:
                row = s.get(EvalRun, eval_id)
                if row is not None:
                    row.status = "failed"
                    row.report_json = {"error": str(exc)}
            raise

    threading.Thread(target=work, name=f"eval-{eval_id}", daemon=True).start()
    return eval_id


def eval_json(eval_id: int) -> dict[str, Any] | None:
    with session_scope() as s:
        row = s.get(EvalRun, eval_id)
        if row is None:
            return None
        if row.report_json and row.status == "complete":
            return dict(row.report_json)
        return {
            "id": row.id,
            "model": row.model,
            "drift_scenario": row.drift_scenario,
            "status": row.status,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "declined": 0,
            "wrong": 0,
            "per_workflow": {},
            "cases": [],
        }


def recent_eval_runs(limit: int = 20) -> list[EvalRun]:
    with session_scope() as s:
        return list(s.scalars(select(EvalRun).order_by(EvalRun.id.desc()).limit(limit)))
