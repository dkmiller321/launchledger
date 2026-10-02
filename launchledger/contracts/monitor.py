"""Batch drift monitor (PRD D3): sample list endpoints, check contracts and value distributions."""

import logging
import statistics
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select

from launchledger.clock import now
from launchledger.contracts.check import validate_records
from launchledger.contracts.incidents import record_incident
from launchledger.db.models import ContractBaseline
from launchledger.db.session import session_scope
from launchledger.systems.client import systems_client

log = logging.getLogger(__name__)

SAMPLE_SIZE = 200
P50_TOLERANCE = 2.0  # p50 must stay within [base / 2, base * 2]


@dataclass(frozen=True)
class Sample:
    system: str
    endpoint: str
    record_type: str
    numeric_fields: tuple[str, ...] = ()


SAMPLES: tuple[Sample, ...] = (
    Sample("plm", "/parts", "part", ("mass_kg", "unit_cost_usd")),
    Sample("plm", "/bom_lines", "bom_line", ("qty",)),
    Sample("mes", "/serials", "serial"),
    Sample("mes", "/work_orders", "work_order"),
    Sample("mes", "/inspections", "inspection"),
    Sample("mes", "/nonconformances", "ncr"),
    Sample("erp", "/suppliers", "supplier"),
    Sample("erp", "/purchase_orders", "purchase_order", ("qty", "unit_cost_usd")),
    Sample("req", "/requirements", "requirement"),
    Sample("dw", "/supplier_on_time", "supplier_on_time", ("on_time_rate",)),
    Sample("dw", "/wo_cycle_time", "wo_cycle_time", ("avg_cycle_days",)),
)


def _fetch(sample: Sample) -> list[dict[str, Any]]:
    resp = systems_client().get(
        f"/systems/{sample.system}{sample.endpoint}", params={"limit": SAMPLE_SIZE}
    )
    resp.raise_for_status()
    items: list[dict[str, Any]] = resp.json()["items"]
    return items


def _numbers(items: list[dict[str, Any]], fld: str) -> list[float]:
    return [float(i[fld]) for i in items if isinstance(i.get(fld), int | float)]


def capture_baselines() -> None:
    """Record p50/min/max of every numeric field from a clean sample."""
    rows = []
    stamp = now()
    for sample in SAMPLES:
        if not sample.numeric_fields:
            continue
        items = _fetch(sample)
        for fld in sample.numeric_fields:
            values = _numbers(items, fld)
            if values:
                rows.append(
                    ContractBaseline(
                        system=sample.system,
                        endpoint=sample.endpoint,
                        field=fld,
                        p50=statistics.median(values),
                        min=min(values),
                        max=max(values),
                        captured_at=stamp,
                    )
                )
    with session_scope() as s:
        s.execute(delete(ContractBaseline))
        s.add_all(rows)


def has_baselines() -> bool:
    with session_scope() as s:
        return s.scalars(select(ContractBaseline).limit(1)).first() is not None


def distribution_shift(base_p50: float, values: list[float]) -> str | None:
    """Pure: a description of the shift if the sample's median left the tolerance band."""
    if not values or base_p50 <= 0:
        return None
    p50 = statistics.median(values)
    ratio = p50 / base_p50
    if 1 / P50_TOLERANCE <= ratio <= P50_TOLERANCE:
        return None
    return f"p50 moved from {base_p50:g} to {p50:g} (x{ratio:.2f})"


def check_now(eval_run_id: int | None = None) -> int:
    """Run one monitor pass. Returns how many problems were found (incidents opened/updated)."""
    with session_scope() as s:
        baselines = {
            (b.system, b.endpoint, b.field): b.p50 for b in s.scalars(select(ContractBaseline))
        }
    found = 0
    for sample in SAMPLES:
        try:
            items = _fetch(sample)
        except Exception as exc:  # one bad endpoint must not stop the pass
            log.warning(
                "drift monitor could not sample %s%s: %s", sample.system, sample.endpoint, exc
            )
            continue
        violations = validate_records(sample.record_type, items)
        if violations:
            first = violations[0]
            record_incident(
                sample.system,
                sample.endpoint,
                first.field,
                first.kind,
                "; ".join(v.problem for v in violations),
                from_run=False,
                eval_run_id=eval_run_id,
            )
            found += 1
            continue
        for fld in sample.numeric_fields:
            base = baselines.get((sample.system, sample.endpoint, fld))
            if base is None:
                continue
            shift = distribution_shift(base, _numbers(items, fld))
            if shift:
                record_incident(
                    sample.system,
                    sample.endpoint,
                    fld,
                    "distribution",
                    shift,
                    from_run=False,
                    eval_run_id=eval_run_id,
                )
                found += 1
    return found
