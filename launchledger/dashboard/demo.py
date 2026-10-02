"""Deterministic demo activity for the dashboard (E2E_TESTS.md stage 8)."""

from datetime import UTC, datetime, timedelta

from launchledger.db.models import DriftIncident, EvalRun, Feedback, FeedbackEvent, Run
from launchledger.db.session import session_scope
from launchledger.ops import clear_app_tables

# Monday of ISO week 36, 2026 (weeks 36-39 run Aug 31 - Sep 27).
WEEK36 = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)

QUESTIONS = [
    ("Where is SN-0042 and what's blocking it?", "serial_status"),
    ("Which open work orders are at risk from late POs from Apex Castings?", "supplier_impact"),
    ("Which assemblies use part P-1077?", "where_used"),
    ("What open nonconformances are there against SN-0042?", "ncr_summary"),
    ("What's the status of PO-10233 and is it late?", "po_status"),
]

# (created week, closed week or None, final status, reason, disposition)
FEEDBACK = [
    (36, 36, "verified", "wrong_data", "data_issue"),
    (36, 37, "verified", "missing_data", "prompt_issue"),
    (37, 37, "verified", "unclear", "prompt_issue"),
    (37, 38, "verified", "wrong_data", "drift"),
    (37, 39, "verified", "wrong_data", "data_issue"),
    (38, 38, "verified", "slow", "feature_request"),
    (38, 39, "verified", "wrong_data", "guardrail_false_positive"),
    (38, 39, "wont_fix", "other", "feature_request"),
    (38, None, "fixed", "wrong_data", "data_issue"),
    (39, None, "triaged", "missing_data", "prompt_issue"),
    (39, None, "triaged", "unclear", None),
    (39, None, "new", "wrong_data", None),
]
DECISIONS = ["answered"] * 14 + ["declined"] * 4 + ["blocked"] * 2
STEPS = {
    "triaged": ["triaged"],
    "fixed": ["triaged", "fixed"],
    "verified": ["triaged", "fixed", "verified"],
    "wont_fix": ["triaged", "wont_fix"],
}


def at(week: int, day: int = 0, hour: int = 0) -> datetime:
    return WEEK36 + timedelta(weeks=week - 36, days=day, hours=hour)


def seed_activity() -> None:
    """Replace app data with a known month of activity: 20 runs, 12 feedback items, 3 eval
    runs and 2 resolved drift incidents."""
    clear_app_tables()
    with session_scope() as s:
        runs = []
        for i, decision in enumerate(DECISIONS):
            question, workflow = QUESTIONS[i % len(QUESTIONS)]
            reason = {
                "declined": "Declined: upstream data from ERP failed its contract "
                "(/purchase_orders: promised_date missing).",
                "blocked": "Blocked by guardrail: ids_exist (SN-9999 not found in MES).",
            }
            run = Run(
                question=question,
                workflow=workflow,
                workflow_source="router",
                model="mock/workflow",
                decision=decision,
                decision_reason=reason.get(decision, ""),
                answer_json=None,
                created_at=at(36 + i % 4, day=i % 5, hour=i % 7),
            )
            s.add(run)
            runs.append(run)
        s.flush()

        for i, (week, closed_week, status, reason_key, disposition) in enumerate(FEEDBACK):
            created = at(week, day=1 + i % 3)
            closed = at(closed_week, day=5) if closed_week else None
            fb = Feedback(
                run_id=runs[i].id,
                rating="down",
                reason=reason_key,
                text="Demo feedback",
                status=status,
                disposition=disposition,
                created_at=created,
                closed_at=closed,
            )
            s.add(fb)
            s.flush()
            previous = "new"
            for n, step in enumerate(STEPS.get(status, [])):
                stamp = (
                    closed
                    if step in ("verified", "wont_fix") and closed
                    else (created + timedelta(hours=4 * (n + 1)))
                )
                s.add(
                    FeedbackEvent(
                        feedback_id=fb.id,
                        from_status=previous,
                        to_status=step,
                        disposition=disposition,
                        at=stamp,
                    )
                )
                previous = step

        for week, passed in ((37, 28), (38, 29), (39, 30)):
            s.add(
                EvalRun(
                    model="mock",
                    drift_scenario=None,
                    status="complete",
                    started_at=at(week, day=2),
                    finished_at=at(week, day=2, hour=1),
                    total=30,
                    passed=passed,
                    failed=30 - passed,
                    declined=0,
                    wrong=0,
                    report_json={"passed": passed, "total": 30, "per_workflow": {}},
                )
            )

        for week, system, endpoint, field, kind in (
            (37, "erp", "/purchase_orders", "promised_date", "shape"),
            (39, "mes", "/work_orders", "status", "enum"),
        ):
            s.add(
                DriftIncident(
                    system=system,
                    endpoint=endpoint,
                    field=field,
                    kind=kind,
                    status="resolved",
                    detail="demo incident",
                    first_seen=at(week, day=1),
                    last_seen=at(week, day=1, hour=2),
                    resolved_at=at(week, day=2),
                    runs_affected=3,
                )
            )
