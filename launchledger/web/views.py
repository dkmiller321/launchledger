"""Read models shared by HTML pages and the JSON inspection API (E2E_TESTS.md §1.8)."""

from typing import Any

from sqlalchemy import select

from launchledger.db.models import GuardrailResult, Run, RunStep
from launchledger.db.session import session_scope


def citation_href(fact: dict[str, Any]) -> str:
    return (
        f"/records/{str(fact.get('system', '')).lower()}/{fact.get('record_type')}/"
        f"{fact.get('record_id')}"
    )


def _step_json(step: RunStep) -> dict[str, Any]:
    p = step.payload_json
    out: dict[str, Any] = {
        "seq": step.seq,
        "kind": step.kind,
        "latency_ms": step.latency_ms,
        "tokens": step.tokens,
    }
    if step.kind == "llm":
        out.update(
            purpose=p.get("purpose"),
            repair=bool(p.get("repair")),
            model=p.get("model"),
            response=p.get("response"),
        )
    elif step.kind == "tool":
        out.update(
            tool=p.get("tool"),
            args=p.get("args"),
            system=p.get("system"),
            endpoint=p.get("endpoint"),
            path=p.get("path"),
            status=p.get("status"),
            http_status=p.get("http_status"),
            result=p.get("result"),
        )
    elif step.kind == "contract":
        out.update(
            system=p.get("system"),
            endpoint=p.get("endpoint"),
            contract=p.get("contract"),
            violations=p.get("violations"),
            gated_by=p.get("gated_by"),
        )
    elif step.kind == "guardrail":
        out.update(rule=p.get("rule"), passed=p.get("passed"), detail=p.get("detail"))
    return out


def run_view(run_id: int) -> dict[str, Any] | None:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            return None
        steps = s.scalars(
            select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq)
        ).all()
        guards = s.scalars(
            select(GuardrailResult)
            .where(GuardrailResult.run_id == run_id)
            .order_by(GuardrailResult.id)
        ).all()
        answer = run.answer_json or {}
        claims = [
            {
                "text": c.get("text", ""),
                "facts": [{**f, "href": citation_href(f)} for f in c.get("facts", [])],
            }
            for c in answer.get("claims", [])
        ]
        return {
            "id": run.id,
            "question": run.question,
            "workflow": run.workflow,
            "workflow_source": run.workflow_source,
            "model": run.model,
            "decision": run.decision,
            "decision_reason": run.decision_reason,
            "answer": answer.get("answer", ""),
            "claims": claims,
            "caveats": answer.get("caveats", []),
            "created_at": run.created_at.isoformat(),
            "steps": [_step_json(st) for st in steps],
            "guardrails": [
                {"rule": g.rule, "passed": g.passed, "detail": g.detail} for g in guards
            ],
        }


def list_runs(decision: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with session_scope() as s:
        stmt = select(Run).order_by(Run.id.desc()).limit(limit)
        if decision and decision != "all":
            stmt = stmt.where(Run.decision == decision)
        return [
            {
                "id": r.id,
                "question": r.question,
                "workflow": r.workflow,
                "decision": r.decision,
                "model": r.model,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in s.scalars(stmt)
        ]
