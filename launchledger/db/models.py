"""SQLAlchemy models.

System schemas hold fake source data; `app` holds what LaunchLedger produces.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


SYSTEM_SCHEMAS = ("plm", "mes", "erp", "req", "dw")
ALL_SCHEMAS = (*SYSTEM_SCHEMAS, "app")


# --- PLM -------------------------------------------------------------------------------------


class Part(Base):
    __tablename__ = "parts"
    __table_args__ = {"schema": "plm"}
    part_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    revision: Mapped[str] = mapped_column(String(4))
    mass_kg: Mapped[float] = mapped_column(Float)
    unit_cost_usd: Mapped[float] = mapped_column(Float)
    export_controlled: Mapped[bool] = mapped_column(Boolean)
    controlled_notes: Mapped[str | None] = mapped_column(Text)


class BomLine(Base):
    __tablename__ = "bom_lines"
    __table_args__ = {"schema": "plm"}
    bom_line_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    parent_pn: Mapped[str] = mapped_column(String(16), index=True)
    child_pn: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[int] = mapped_column(Integer)


# --- MES -------------------------------------------------------------------------------------


class Serial(Base):
    __tablename__ = "serials"
    __table_args__ = {"schema": "mes"}
    serial_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    part_number: Mapped[str] = mapped_column(String(16), index=True)
    revision: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(16))
    location: Mapped[str] = mapped_column(String(80))


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = {"schema": "mes"}
    wo_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16))
    blocked_reason: Mapped[str | None] = mapped_column(String(160))
    depends_on_po: Mapped[str | None] = mapped_column(String(16), index=True)
    description: Mapped[str] = mapped_column(String(160))
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)


class Inspection(Base):
    __tablename__ = "inspections"
    __table_args__ = {"schema": "mes"}
    inspection_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(16), index=True)
    result: Mapped[str] = mapped_column(String(8))
    inspected_at: Mapped[date] = mapped_column(Date)


class Nonconformance(Base):
    __tablename__ = "nonconformances"
    __table_args__ = {"schema": "mes"}
    ncr_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(16), index=True)
    severity: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12))
    requirement_id: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(String(160))


# --- ERP -------------------------------------------------------------------------------------


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {"schema": "erp"}
    supplier_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = {"schema": "erp"}
    po_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(String(16), index=True)
    part_number: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    promised_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12))
    unit_cost_usd: Mapped[float] = mapped_column(Float)
    received_on: Mapped[date | None] = mapped_column(Date)


# --- REQ and DW (P1) -------------------------------------------------------------------------


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = {"schema": "req"}
    req_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    text: Mapped[str] = mapped_column(String(240))
    verification_method: Mapped[str] = mapped_column(String(24))


class RequirementPartLink(Base):
    __tablename__ = "part_links"
    __table_args__ = {"schema": "req"}
    req_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    part_number: Mapped[str] = mapped_column(String(16), primary_key=True)


class SupplierOnTime(Base):
    __tablename__ = "supplier_on_time"
    __table_args__ = {"schema": "dw"}
    supplier_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    pos_received: Mapped[int] = mapped_column(Integer)
    pos_on_time: Mapped[int] = mapped_column(Integer)
    on_time_rate: Mapped[float] = mapped_column(Float)
    open_late_pos: Mapped[int] = mapped_column(Integer)


class WoCycleTime(Base):
    __tablename__ = "wo_cycle_time"
    __table_args__ = {"schema": "dw"}
    part_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    closed_wos: Mapped[int] = mapped_column(Integer)
    avg_cycle_days: Mapped[float] = mapped_column(Float)
    last_cycle_days: Mapped[float] = mapped_column(Float)


# --- app -------------------------------------------------------------------------------------


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    workflow: Mapped[str | None] = mapped_column(String(40))
    workflow_source: Mapped[str] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(120))
    decision: Mapped[str] = mapped_column(String(10), index=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    answer_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunStep(Base):
    __tablename__ = "run_steps"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("app.runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(12))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int | None] = mapped_column(Integer)


class GuardrailResult(Base):
    __tablename__ = "guardrail_results"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("app.runs.id", ondelete="CASCADE"), index=True)
    rule: Mapped[str] = mapped_column(String(40))
    passed: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str] = mapped_column(Text, default="")


class ContractBaseline(Base):
    __tablename__ = "contract_baselines"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system: Mapped[str] = mapped_column(String(8))
    endpoint: Mapped[str] = mapped_column(String(80))
    field: Mapped[str] = mapped_column(String(40))
    p50: Mapped[float] = mapped_column(Float)
    min: Mapped[float] = mapped_column(Float)
    max: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DriftIncident(Base):
    __tablename__ = "drift_incidents"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system: Mapped[str] = mapped_column(String(8))
    endpoint: Mapped[str] = mapped_column(String(80))
    field: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(10), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runs_affected: Mapped[int] = mapped_column(Integer, default=0)
    opened_by_eval: Mapped[int | None] = mapped_column(Integer)


class DriftScenarioState(Base):
    __tablename__ = "drift_scenarios"
    __table_args__ = {"schema": "app"}
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(120))
    drift_scenario: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    declined: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_run_id: Mapped[int] = mapped_column(
        ForeignKey("app.eval_runs.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(60))
    workflow: Mapped[str] = mapped_column(String(40))
    passed: Mapped[bool] = mapped_column(Boolean)
    outcome: Mapped[str] = mapped_column(String(10))
    decision: Mapped[str] = mapped_column(String(10))
    run_id: Mapped[int | None] = mapped_column(Integer)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    diff_json: Mapped[list[Any]] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("app.runs.id", ondelete="CASCADE"))
    rating: Mapped[str] = mapped_column(String(4))
    reason: Mapped[str | None] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10))
    disposition: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = {"schema": "app"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("app.feedback.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(10))
    to_status: Mapped[str] = mapped_column(String(10))
    disposition: Mapped[str | None] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
