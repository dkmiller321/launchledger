"""Leadership metrics (PRD B1, B2): one source for the dashboard and the weekly report."""

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select

from launchledger.db.models import DriftIncident, EvalRun, Feedback, Run
from launchledger.db.session import session_scope

OPEN_STATUSES = ("new", "triaged", "fixed")
CLOSED_STATUSES = ("verified", "wont_fix")


def iso_week(stamp: datetime) -> str:
    year, week, _ = stamp.isocalendar()
    return f"{year}-W{week:02d}"


def compute(weeks: int = 6) -> dict[str, Any]:
    with session_scope() as s:
        feedback = s.scalars(select(Feedback).where(Feedback.rating == "down")).all()
        runs = s.scalars(select(Run)).all()
        evals = s.scalars(
            select(EvalRun)
            .where(EvalRun.status == "complete", EvalRun.drift_scenario.is_(None))
            .order_by(EvalRun.id)
        ).all()
        incidents = s.scalars(select(DriftIncident)).all()

        inflow = Counter(iso_week(f.created_at) for f in feedback)
        outflow = Counter(
            iso_week(f.closed_at)
            for f in feedback
            if f.status in CLOSED_STATUSES and f.closed_at is not None
        )
        week_keys = sorted(set(inflow) | set(outflow))[-weeks:]
        backlog = Counter(f.status for f in feedback if f.status in OPEN_STATUSES)
        decisions = Counter(r.decision for r in runs)
        incident_weeks = Counter(iso_week(i.first_seen) for i in incidents)
        eval_rows = [
            {
                "id": e.id,
                "model": e.model,
                "passed": e.passed,
                "total": e.total,
                "when": e.started_at.strftime("%Y-%m-%d"),
                "per_workflow": (e.report_json or {}).get("per_workflow", {}),
            }
            for e in evals
        ]
    return {
        "weeks": [
            {"week": w, "inflow": inflow.get(w, 0), "outflow": outflow.get(w, 0)} for w in week_keys
        ],
        "inflow_total": sum(inflow.values()),
        "outflow_total": sum(outflow.values()),
        "backlog": {status: backlog.get(status, 0) for status in OPEN_STATUSES},
        "backlog_total": sum(backlog.values()),
        "decisions": {d: decisions.get(d, 0) for d in ("answered", "declined", "blocked")},
        "runs_total": len(runs),
        "evals": eval_rows,
        "latest_eval": eval_rows[-1] if eval_rows else None,
        "incidents_total": len(incidents),
        "incidents_open": sum(1 for i in incidents if i.status == "open"),
        "incident_weeks": sorted(incident_weeks.items()),
    }


def weekly_report(m: dict[str, Any]) -> str:
    """Markdown for leadership (PRD B2)."""
    lines = ["# LaunchLedger weekly report", ""]
    latest = m["latest_eval"]
    lines.append(
        f"Eval pass rate (latest mock suite): "
        f"{f'{latest["passed"]}/{latest["total"]}' if latest else 'no runs yet'}. "
        f"Open feedback backlog: {m['backlog_total']}. "
        f"Drift incidents: {m['incidents_total']} ({m['incidents_open']} open)."
    )
    lines += ["", "## Feedback inflow vs outflow", "", "| Week | In | Out |", "| --- | --- | --- |"]
    lines += [f"| {w['week']} | {w['inflow']} | {w['outflow']} |" for w in m["weeks"]]
    lines += ["", "## Open backlog", "", "| Status | Items |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in m["backlog"].items()]
    lines += ["", "## Answers by decision", "", "| Decision | Runs |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in m["decisions"].items()]
    lines += ["", "## Eval runs", "", "| Run | Date | Passed |", "| --- | --- | --- |"]
    lines += [f"| {e['id']} | {e['when']} | {e['passed']}/{e['total']} |" for e in m["evals"]]
    return "\n".join(lines) + "\n"
