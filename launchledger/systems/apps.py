"""The five fake enterprise systems, each its own FastAPI sub-app (PRD S1-S8).

Every response passes through the drift injector, which rewrites records only for scenarios
switched on with DRIFT_INJECTION=1 (PRD D5).
"""

from datetime import date
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from launchledger.clock import today
from launchledger.db import models as m
from launchledger.db.session import session_scope
from launchledger.drift import scenarios
from launchledger.drift.state import enabled_scenarios
from launchledger.systems.records import RECORD_TYPES, RecordType

MAX_LIMIT = 200


def not_found() -> JSONResponse:
    return JSONResponse({"error": "not_found"}, status_code=404)


def _out(rt: RecordType, row: Any, enabled: list[str]) -> dict[str, Any]:
    return scenarios.apply(enabled, rt.name, rt.serialize(row))


def get_one(record_type: str, record_id: str) -> JSONResponse:
    rt = RECORD_TYPES[record_type]
    with session_scope() as s:
        row = s.get(rt.model, record_id)
        if row is None:
            return not_found()
        return JSONResponse(_out(rt, row, enabled_scenarios()))


def list_page(record_type: str, stmt: Select[Any], limit: int, offset: int) -> JSONResponse:
    rt = RECORD_TYPES[record_type]
    limit = max(1, min(limit, MAX_LIMIT))
    with session_scope() as s:
        total = s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        pk = getattr(rt.model, rt.pk)
        rows = s.scalars(stmt.order_by(pk).limit(limit).offset(offset)).all()
        enabled = enabled_scenarios()
        items = [_out(rt, r, enabled) for r in rows]
    return JSONResponse({"items": items, "total": total, "limit": limit, "offset": offset})


def is_late(status: str, due: date, promised: date, on: date) -> bool:
    """PRD: an OPEN PO is late if its promise slipped past due, or it is past due."""
    return status == "OPEN" and (promised > due or due < on)


# --- PLM -------------------------------------------------------------------------------------

plm = FastAPI(title="PLM")


@plm.get("/parts")
def plm_parts(
    export_controlled: bool | None = None, limit: int = 50, offset: int = 0
) -> JSONResponse:
    stmt = select(m.Part)
    if export_controlled is not None:
        stmt = stmt.where(m.Part.export_controlled == export_controlled)
    return list_page("part", stmt, limit, offset)


@plm.get("/parts/{part_number}")
def plm_part(part_number: str) -> JSONResponse:
    return get_one("part", part_number)


def _part_exists(part_number: str) -> bool:
    with session_scope() as s:
        return s.get(m.Part, part_number) is not None


@plm.get("/parts/{part_number}/bom")
def plm_bom(part_number: str, limit: int = 50, offset: int = 0) -> JSONResponse:
    if not _part_exists(part_number):
        return not_found()
    return list_page(
        "bom_line", select(m.BomLine).where(m.BomLine.parent_pn == part_number), limit, offset
    )


@plm.get("/parts/{part_number}/where_used")
def plm_where_used(part_number: str, limit: int = 50, offset: int = 0) -> JSONResponse:
    if not _part_exists(part_number):
        return not_found()
    return list_page(
        "bom_line", select(m.BomLine).where(m.BomLine.child_pn == part_number), limit, offset
    )


@plm.get("/bom_lines")
def plm_bom_lines(limit: int = 50, offset: int = 0) -> JSONResponse:
    return list_page("bom_line", select(m.BomLine), limit, offset)


@plm.get("/bom_lines/{bom_line_id}")
def plm_bom_line(bom_line_id: str) -> JSONResponse:
    return get_one("bom_line", bom_line_id)


# --- MES -------------------------------------------------------------------------------------

mes = FastAPI(title="MES")


@mes.get("/serials")
def mes_serials(
    part_number: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0
) -> JSONResponse:
    stmt = select(m.Serial)
    if part_number:
        stmt = stmt.where(m.Serial.part_number == part_number)
    if status:
        stmt = stmt.where(m.Serial.status == status)
    return list_page("serial", stmt, limit, offset)


@mes.get("/serials/{serial_number}")
def mes_serial(serial_number: str) -> JSONResponse:
    return get_one("serial", serial_number)


@mes.get("/work_orders")
def mes_work_orders(
    serial_number: str | None = None,
    status: str | None = None,
    depends_on_po: str | None = None,
    part_number: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    stmt = select(m.WorkOrder)
    if serial_number:
        stmt = stmt.where(m.WorkOrder.serial_number == serial_number)
    if status:
        stmt = stmt.where(m.WorkOrder.status == status)
    if depends_on_po:
        stmt = stmt.where(m.WorkOrder.depends_on_po == depends_on_po)
    if part_number:
        serials = select(m.Serial.serial_number).where(m.Serial.part_number == part_number)
        stmt = stmt.where(m.WorkOrder.serial_number.in_(serials))
    return list_page("work_order", stmt, limit, offset)


@mes.get("/work_orders/{wo_id}")
def mes_work_order(wo_id: str) -> JSONResponse:
    return get_one("work_order", wo_id)


@mes.get("/inspections")
def mes_inspections(
    serial_number: str | None = None, limit: int = 50, offset: int = 0
) -> JSONResponse:
    stmt = select(m.Inspection)
    if serial_number:
        stmt = stmt.where(m.Inspection.serial_number == serial_number)
    return list_page("inspection", stmt, limit, offset)


@mes.get("/inspections/{inspection_id}")
def mes_inspection(inspection_id: str) -> JSONResponse:
    return get_one("inspection", inspection_id)


@mes.get("/nonconformances")
def mes_ncrs(
    serial_number: str | None = None,
    part_number: str | None = None,
    status: str | None = None,
    requirement_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    stmt = select(m.Nonconformance)
    if serial_number:
        stmt = stmt.where(m.Nonconformance.serial_number == serial_number)
    if part_number:
        serials = select(m.Serial.serial_number).where(m.Serial.part_number == part_number)
        stmt = stmt.where(m.Nonconformance.serial_number.in_(serials))
    if status:
        stmt = stmt.where(m.Nonconformance.status == status)
    if requirement_id:
        stmt = stmt.where(m.Nonconformance.requirement_id == requirement_id)
    return list_page("ncr", stmt, limit, offset)


@mes.get("/nonconformances/{ncr_id}")
def mes_ncr(ncr_id: str) -> JSONResponse:
    return get_one("ncr", ncr_id)


# --- ERP -------------------------------------------------------------------------------------

erp = FastAPI(title="ERP")


@erp.get("/suppliers")
def erp_suppliers(name: str | None = None, limit: int = 50, offset: int = 0) -> JSONResponse:
    stmt = select(m.Supplier)
    if name:
        stmt = stmt.where(m.Supplier.name.ilike(f"%{name}%"))
    return list_page("supplier", stmt, limit, offset)


@erp.get("/suppliers/{supplier_id}")
def erp_supplier(supplier_id: str) -> JSONResponse:
    return get_one("supplier", supplier_id)


@erp.get("/purchase_orders")
def erp_pos(
    supplier_id: str | None = None,
    part_number: str | None = None,
    status: str | None = None,
    late_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    stmt = select(m.PurchaseOrder)
    if supplier_id:
        stmt = stmt.where(m.PurchaseOrder.supplier_id == supplier_id)
    if part_number:
        stmt = stmt.where(m.PurchaseOrder.part_number == part_number)
    if status:
        stmt = stmt.where(m.PurchaseOrder.status == status)
    if late_only:
        po = m.PurchaseOrder
        stmt = stmt.where(
            po.status == "OPEN", or_(po.promised_date > po.due_date, po.due_date < today())
        )
    return list_page("purchase_order", stmt, limit, offset)


@erp.get("/purchase_orders/{po_id}")
def erp_po(po_id: str) -> JSONResponse:
    return get_one("purchase_order", po_id)


# --- REQ (P1) --------------------------------------------------------------------------------

req = FastAPI(title="REQ")


@req.get("/requirements")
def req_requirements(
    part_number: str | None = None, limit: int = 50, offset: int = 0
) -> JSONResponse:
    stmt = select(m.Requirement)
    if part_number:
        linked = select(m.RequirementPartLink.req_id).where(
            m.RequirementPartLink.part_number == part_number
        )
        stmt = stmt.where(m.Requirement.req_id.in_(linked))
    return list_page("requirement", stmt, limit, offset)


@req.get("/requirements/{req_id}")
def req_requirement(req_id: str) -> JSONResponse:
    return get_one("requirement", req_id)


@req.get("/requirements/{req_id}/parts")
def req_requirement_parts(req_id: str, limit: int = 50, offset: int = 0) -> JSONResponse:
    with session_scope() as s:
        if s.get(m.Requirement, req_id) is None:
            return not_found()
    linked = select(m.RequirementPartLink.part_number).where(m.RequirementPartLink.req_id == req_id)
    return list_page("part", select(m.Part).where(m.Part.part_number.in_(linked)), limit, offset)


# --- DW (P1) ---------------------------------------------------------------------------------

dw = FastAPI(title="DW")


@dw.get("/supplier_on_time")
def dw_supplier_on_time(limit: int = 50, offset: int = 0) -> JSONResponse:
    return list_page("supplier_on_time", select(m.SupplierOnTime), limit, offset)


@dw.get("/supplier_on_time/{supplier_id}")
def dw_supplier_on_time_one(supplier_id: str) -> JSONResponse:
    return get_one("supplier_on_time", supplier_id)


@dw.get("/wo_cycle_time")
def dw_cycle_times(limit: int = 50, offset: int = 0) -> JSONResponse:
    return list_page("wo_cycle_time", select(m.WoCycleTime), limit, offset)


@dw.get("/wo_cycle_time/{part_number}")
def dw_cycle_time_one(part_number: str) -> JSONResponse:
    return get_one("wo_cycle_time", part_number)


SYSTEM_APPS: dict[str, FastAPI] = {"plm": plm, "mes": mes, "erp": erp, "req": req, "dw": dw}

_ = (Query, Session)
