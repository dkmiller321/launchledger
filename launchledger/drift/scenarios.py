"""Injectable upstream drift scenarios (PRD D5, D7). Each rewrites one record type's JSON."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Record = dict[str, Any]


@dataclass(frozen=True)
class Scenario:
    name: str
    system: str
    record_type: str
    kind: str
    description: str
    priority: str
    transform: Callable[[Record], Record]


def _rename_promised_date(rec: Record) -> Record:
    out = {k: v for k, v in rec.items() if k != "promised_date"}
    if "promised_date" in rec:
        out["promise_date"] = rec["promised_date"]
    return out


def _new_wo_status(rec: Record) -> Record:
    number = int(str(rec.get("wo_id", "WO-0"))[3:])
    if rec.get("status") == "OPEN" and number % 2 == 1:
        return {**rec, "status": "HOLD_QA"}
    return rec


def _cost_in_cents(rec: Record) -> Record:
    cost = rec.get("unit_cost_usd")
    if isinstance(cost, int | float):
        return {**rec, "unit_cost_usd": round(cost * 100, 2)}
    return rec


def _null_revision(rec: Record) -> Record:
    number = int(str(rec.get("part_number", "P-1"))[2:])
    if number % 5 == 0:
        return {**rec, "revision": None}
    return rec


def _us_dates(rec: Record) -> Record:
    out = dict(rec)
    for key in ("due_date", "promised_date", "received_on"):
        value = out.get(key)
        if isinstance(value, str) and len(value) == 10 and value[4] == "-":
            out[key] = f"{value[5:7]}/{value[8:10]}/{value[0:4]}"
    return out


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario(
            "erp_rename_promised_date",
            "erp",
            "purchase_order",
            "shape",
            "ERP renames purchase_order.promised_date to promise_date",
            "P0",
            _rename_promised_date,
        ),
        Scenario(
            "mes_new_wo_status",
            "mes",
            "work_order",
            "enum",
            "MES adds work-order status HOLD_QA (odd-numbered OPEN work orders)",
            "P0",
            _new_wo_status,
        ),
        Scenario(
            "erp_cost_in_cents",
            "erp",
            "purchase_order",
            "distribution",
            "ERP reports unit_cost_usd in cents (x100), same field name",
            "P0",
            _cost_in_cents,
        ),
        Scenario(
            "plm_null_revision",
            "plm",
            "part",
            "shape",
            "PLM returns a null revision for parts whose number is divisible by 5",
            "P1",
            _null_revision,
        ),
        Scenario(
            "erp_date_format",
            "erp",
            "purchase_order",
            "shape",
            "ERP returns purchase-order dates as MM/DD/YYYY",
            "P1",
            _us_dates,
        ),
    )
}


def apply(enabled: list[str], record_type: str, record: Record) -> Record:
    """Apply every enabled scenario that targets this record type."""
    for name in enabled:
        scenario = SCENARIOS.get(name)
        if scenario is not None and scenario.record_type == record_type:
            record = scenario.transform(record)
    return record
