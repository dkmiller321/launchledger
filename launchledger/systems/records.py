"""Record types exposed by the fake systems: fields, primary key and URL plural."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from launchledger.db import models as m


@dataclass(frozen=True)
class RecordType:
    name: str
    system: str
    model: type[m.Base]
    plural: str
    pk: str
    fields: tuple[str, ...]

    def serialize(self, row: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in self.fields:
            value = getattr(row, f)
            out[f] = value.isoformat() if isinstance(value, date) else value
        return out


RECORD_TYPES: dict[str, RecordType] = {
    rt.name: rt
    for rt in (
        RecordType(
            "part",
            "plm",
            m.Part,
            "parts",
            "part_number",
            (
                "part_number",
                "name",
                "revision",
                "mass_kg",
                "unit_cost_usd",
                "export_controlled",
                "controlled_notes",
            ),
        ),
        RecordType(
            "bom_line",
            "plm",
            m.BomLine,
            "bom_lines",
            "bom_line_id",
            ("bom_line_id", "parent_pn", "child_pn", "qty"),
        ),
        RecordType(
            "serial",
            "mes",
            m.Serial,
            "serials",
            "serial_number",
            ("serial_number", "part_number", "revision", "status", "location"),
        ),
        RecordType(
            "work_order",
            "mes",
            m.WorkOrder,
            "work_orders",
            "wo_id",
            (
                "wo_id",
                "serial_number",
                "status",
                "blocked_reason",
                "depends_on_po",
                "description",
                "opened_on",
                "closed_on",
            ),
        ),
        RecordType(
            "inspection",
            "mes",
            m.Inspection,
            "inspections",
            "inspection_id",
            ("inspection_id", "serial_number", "result", "inspected_at"),
        ),
        RecordType(
            "ncr",
            "mes",
            m.Nonconformance,
            "nonconformances",
            "ncr_id",
            ("ncr_id", "serial_number", "severity", "status", "requirement_id", "description"),
        ),
        RecordType(
            "supplier", "erp", m.Supplier, "suppliers", "supplier_id", ("supplier_id", "name")
        ),
        RecordType(
            "purchase_order",
            "erp",
            m.PurchaseOrder,
            "purchase_orders",
            "po_id",
            (
                "po_id",
                "supplier_id",
                "part_number",
                "qty",
                "due_date",
                "promised_date",
                "status",
                "unit_cost_usd",
                "received_on",
            ),
        ),
        RecordType(
            "requirement",
            "req",
            m.Requirement,
            "requirements",
            "req_id",
            ("req_id", "text", "verification_method"),
        ),
        RecordType(
            "supplier_on_time",
            "dw",
            m.SupplierOnTime,
            "supplier_on_time",
            "supplier_id",
            ("supplier_id", "name", "pos_received", "pos_on_time", "on_time_rate", "open_late_pos"),
        ),
        RecordType(
            "wo_cycle_time",
            "dw",
            m.WoCycleTime,
            "wo_cycle_time",
            "part_number",
            ("part_number", "closed_wos", "avg_cycle_days", "last_cycle_days"),
        ),
    )
}


def record_path(record_type: str, record_id: str) -> str:
    rt = RECORD_TYPES[record_type]
    return f"/systems/{rt.system}/{rt.plural}/{record_id}"
