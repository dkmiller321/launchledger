"""Drift incidents: open, update, resolve, list."""

from typing import Any

from sqlalchemy import select

from launchledger.clock import now
from launchledger.contracts.check import OpenIncident
from launchledger.db.models import DriftIncident
from launchledger.db.session import session_scope


def open_incidents() -> list[OpenIncident]:
    with session_scope() as s:
        rows = s.scalars(
            select(DriftIncident).where(DriftIncident.status == "open").order_by(DriftIncident.id)
        ).all()
        return [OpenIncident(r.id, r.system, r.field, r.kind) for r in rows]


def record_incident(
    system: str,
    endpoint: str,
    field: str,
    kind: str,
    detail: str,
    *,
    from_run: bool,
    eval_run_id: int | None = None,
) -> int:
    """Open a new incident, or update the open one for the same system, field and kind."""
    with session_scope() as s:
        row = s.scalars(
            select(DriftIncident).where(
                DriftIncident.status == "open",
                DriftIncident.system == system,
                DriftIncident.field == field,
                DriftIncident.kind == kind,
            )
        ).first()
        stamp = now()
        if row is None:
            row = DriftIncident(
                system=system,
                endpoint=endpoint,
                field=field,
                kind=kind,
                status="open",
                detail=detail,
                first_seen=stamp,
                last_seen=stamp,
                runs_affected=1 if from_run else 0,
                opened_by_eval=eval_run_id,
            )
            s.add(row)
        else:
            row.last_seen = stamp
            if from_run:
                row.runs_affected += 1
        s.flush()
        return row.id


def bump_runs_affected(incident_id: int) -> None:
    with session_scope() as s:
        row = s.get(DriftIncident, incident_id)
        if row is not None:
            row.runs_affected += 1
            row.last_seen = now()


def resolve(incident_id: int) -> bool:
    with session_scope() as s:
        row = s.get(DriftIncident, incident_id)
        if row is None or row.status != "open":
            return False
        row.status = "resolved"
        row.resolved_at = now()
        return True


def resolve_opened_by_eval(eval_run_id: int) -> None:
    with session_scope() as s:
        for row in s.scalars(
            select(DriftIncident).where(
                DriftIncident.status == "open", DriftIncident.opened_by_eval == eval_run_id
            )
        ):
            row.status = "resolved"
            row.resolved_at = now()


def incidents_json() -> list[dict[str, Any]]:
    with session_scope() as s:
        rows = s.scalars(select(DriftIncident).order_by(DriftIncident.id.desc())).all()
        return [
            {
                "id": r.id,
                "system": r.system,
                "endpoint": r.endpoint,
                "field": r.field,
                "kind": r.kind,
                "status": r.status,
                "detail": r.detail,
                "first_seen": r.first_seen.isoformat(),
                "runs_affected": r.runs_affected,
            }
            for r in rows
        ]
