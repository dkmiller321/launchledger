"""Response contracts per record type (PRD D1): exact shape, enums, ranges, nullability."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartContract(_Contract):
    part_number: str
    name: str
    revision: str
    mass_kg: float = Field(ge=0.001, le=100_000)
    # Deliberately loose: a x100 unit change stays in range and is only caught by the
    # distribution monitor (PRD D3). That silent case is what the monitor exists for.
    unit_cost_usd: float = Field(ge=0.01, le=50_000_000)
    export_controlled: bool
    controlled_notes: str | None


class BomLineContract(_Contract):
    bom_line_id: str
    parent_pn: str
    child_pn: str
    qty: int = Field(ge=1, le=10_000)


class SerialContract(_Contract):
    serial_number: str
    part_number: str
    revision: str
    status: Literal["PLANNED", "IN_BUILD", "COMPLETE", "SCRAPPED"]
    location: str


class WorkOrderContract(_Contract):
    wo_id: str
    serial_number: str
    status: Literal["OPEN", "IN_PROGRESS", "BLOCKED", "CLOSED"]
    blocked_reason: str | None
    depends_on_po: str | None
    description: str
    opened_on: date
    closed_on: date | None


class InspectionContract(_Contract):
    inspection_id: str
    serial_number: str
    result: Literal["PASS", "FAIL"]
    inspected_at: date


class NcrContract(_Contract):
    ncr_id: str
    serial_number: str
    severity: Literal["MINOR", "MAJOR", "CRITICAL"]
    status: Literal["OPEN", "CLOSED"]
    requirement_id: str
    description: str


class SupplierContract(_Contract):
    supplier_id: str
    name: str


class PurchaseOrderContract(_Contract):
    po_id: str
    supplier_id: str
    part_number: str
    qty: int = Field(ge=1, le=100_000)
    due_date: date
    promised_date: date
    status: Literal["OPEN", "RECEIVED", "CANCELLED"]
    unit_cost_usd: float = Field(ge=0.01, le=50_000_000)
    received_on: date | None


class RequirementContract(_Contract):
    req_id: str
    text: str
    verification_method: Literal["Inspection", "Test", "Analysis", "Demonstration"]


class SupplierOnTimeContract(_Contract):
    supplier_id: str
    name: str
    pos_received: int = Field(ge=0)
    pos_on_time: int = Field(ge=0)
    on_time_rate: float = Field(ge=0, le=1)
    open_late_pos: int = Field(ge=0)


class WoCycleTimeContract(_Contract):
    part_number: str
    closed_wos: int = Field(ge=0)
    avg_cycle_days: float = Field(ge=0, le=3650)
    last_cycle_days: float = Field(ge=0, le=3650)


CONTRACTS: dict[str, type[_Contract]] = {
    "part": PartContract,
    "bom_line": BomLineContract,
    "serial": SerialContract,
    "work_order": WorkOrderContract,
    "inspection": InspectionContract,
    "ncr": NcrContract,
    "supplier": SupplierContract,
    "purchase_order": PurchaseOrderContract,
    "requirement": RequirementContract,
    "supplier_on_time": SupplierOnTimeContract,
    "wo_cycle_time": WoCycleTimeContract,
}
