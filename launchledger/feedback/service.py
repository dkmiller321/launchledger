"""Feedback and triage (PRD F1-F3)."""

from pathlib import Path
from typing import Any

from sqlalchemy import select

from launchledger.clock import now
from launchledger.db.models import Feedback, FeedbackEvent, Run
from launchledger.db.session import session_scope
from launchledger.evals.cases import write_draft

REASONS = {
    "wrong_data": "Wrong data",
    "missing_data": "Missing data",
    "unclear": "Unclear",
    "slow": "Slow",
    "other": "Other",
}
STATUSES = {
    "new": "New",
    "triaged": "Triaged",
    "fixed": "Fixed",
    "verified": "Verified",
    "wont_fix": "Won't fix",
}
CLOSED = {"verified", "wont_fix"}
DISPOSITIONS = {
    "data_issue": "Data issue",
    "prompt_issue": "Prompt issue",
    "guardrail_false_positive": "Guardrail false positive",
    "drift": "Drift",
    "feature_request": "Feature request",
}


class FeedbackError(ValueError):
    pass


def create_feedback(run_id: int, rating: str, reason: str | None, text: str) -> int:
    if rating not in ("up", "down"):
        raise FeedbackError("rating must be up or down")
    if rating == "down" and reason not in REASONS:
        raise FeedbackError("a thumbs-down needs a reason")
    with session_scope() as s:
        if s.get(Run, run_id) is None:
            raise FeedbackError(f"run {run_id} not found")
        row = Feedback(
            run_id=run_id,
            rating=rating,
            reason=reason if rating == "down" else None,
            text=text.strip(),
            status="new" if rating == "down" else "verified",
            created_at=now(),
            closed_at=None if rating == "down" else now(),
        )
        s.add(row)
        s.flush()
        return row.id


def update_feedback(feedback_id: int, status: str, disposition: str | None) -> None:
    if status not in STATUSES:
        raise FeedbackError(f"unknown status {status}")
    if disposition and disposition not in DISPOSITIONS:
        raise FeedbackError(f"unknown disposition {disposition}")
    with session_scope() as s:
        row = s.get(Feedback, feedback_id)
        if row is None:
            raise FeedbackError(f"feedback {feedback_id} not found")
        if disposition:
            row.disposition = disposition
        if status != row.status:
            s.add(
                FeedbackEvent(
                    feedback_id=row.id,
                    from_status=row.status,
                    to_status=status,
                    disposition=row.disposition,
                    at=now(),
                )
            )
            row.status = status
            row.closed_at = now() if status in CLOSED else None


def convert_to_case(feedback_id: int) -> tuple[str, Path]:
    """Write a draft golden case from the run behind this feedback (PRD F3)."""
    with session_scope() as s:
        fb = s.get(Feedback, feedback_id)
        if fb is None:
            raise FeedbackError(f"feedback {feedback_id} not found")
        run = s.get(Run, fb.run_id)
        if run is None or run.workflow is None:
            raise FeedbackError("the run behind this feedback has no workflow")
        answer = run.answer_json or {}
        facts = [f for c in answer.get("claims", []) for f in c.get("facts", [])]
        case_id = f"draft-{fb.id}"
        return case_id, write_draft(case_id, run.question, run.workflow, facts)


def list_feedback() -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.scalars(
            select(Feedback).where(Feedback.rating == "down").order_by(Feedback.id.desc())
        ).all()
        events = s.scalars(select(FeedbackEvent).order_by(FeedbackEvent.id)).all()
        runs = {r.id: r for r in s.scalars(select(Run).where(Run.id.in_([f.run_id for f in rows])))}
        by_item: dict[int, list[FeedbackEvent]] = {}
        for e in events:
            by_item.setdefault(e.feedback_id, []).append(e)
        out = []
        for f in rows:
            run = runs.get(f.run_id)
            out.append(
                {
                    "id": f.id,
                    "run_id": f.run_id,
                    "rating": f.rating,
                    "reason": f.reason,
                    "reason_label": REASONS.get(f.reason or "", ""),
                    "text": f.text,
                    "status": f.status,
                    "status_label": STATUSES[f.status],
                    "disposition": f.disposition,
                    "created_at": f.created_at.isoformat(),
                    "question": run.question if run else "",
                    "workflow": run.workflow if run else None,
                    "events": [
                        {
                            "from": e.from_status,
                            "to": e.to_status,
                            "at": e.at.isoformat(),
                            "disposition": e.disposition,
                        }
                        for e in by_item.get(f.id, [])
                    ],
                }
            )
        return out
