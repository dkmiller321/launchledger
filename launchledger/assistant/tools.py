"""Agent tools: each is one HTTP GET to a system API (PRD A3)."""

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from launchledger.systems.client import systems_client

MAX_ITEMS_TO_MODEL = 50


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    system: str
    record_type: str
    path: str  # template with {arg} placeholders
    is_list: bool
    required: tuple[str, ...] = ()
    optional: tuple[tuple[str, str], ...] = ()  # (name, json type)

    @property
    def endpoint(self) -> str:
        return self.path

    def schema(self) -> dict[str, Any]:
        props: dict[str, Any] = {name: {"type": "string"} for name in self.required}
        for name, kind in self.optional:
            props[name] = {"type": kind}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": list(self.required),
                },
            },
        }


TOOLS: dict[str, ToolSpec] = {
    t.name: t
    for t in (
        ToolSpec(
            "get_serial",
            "Get one MES serial (unit) by serial number, e.g. SN-0042.",
            "mes",
            "serial",
            "/serials/{serial_number}",
            False,
            ("serial_number",),
        ),
        ToolSpec(
            "list_work_orders",
            "List MES work orders, filtered by serial, status, "
            "the PO they depend on, or the part number of their serial.",
            "mes",
            "work_order",
            "/work_orders",
            True,
            (),
            (
                ("serial_number", "string"),
                ("status", "string"),
                ("depends_on_po", "string"),
                ("part_number", "string"),
            ),
        ),
        ToolSpec(
            "list_inspections",
            "List MES inspections for a serial.",
            "mes",
            "inspection",
            "/inspections",
            True,
            ("serial_number",),
        ),
        ToolSpec(
            "list_ncrs",
            "List MES nonconformances (NCRs), filtered by serial, the part "
            "number of the serial, status (OPEN/CLOSED) or requirement.",
            "mes",
            "ncr",
            "/nonconformances",
            True,
            (),
            (
                ("serial_number", "string"),
                ("part_number", "string"),
                ("status", "string"),
                ("requirement_id", "string"),
            ),
        ),
        ToolSpec(
            "get_part",
            "Get one PLM part by part number, e.g. P-1077.",
            "plm",
            "part",
            "/parts/{part_number}",
            False,
            ("part_number",),
        ),
        ToolSpec(
            "get_bom",
            "List the BOM lines (children) of an assembly part.",
            "plm",
            "bom_line",
            "/parts/{part_number}/bom",
            True,
            ("part_number",),
        ),
        ToolSpec(
            "where_used",
            "List the BOM lines whose child is this part (where it is used).",
            "plm",
            "bom_line",
            "/parts/{part_number}/where_used",
            True,
            ("part_number",),
        ),
        ToolSpec(
            "get_po",
            "Get one ERP purchase order by id, e.g. PO-10233.",
            "erp",
            "purchase_order",
            "/purchase_orders/{po_id}",
            False,
            ("po_id",),
        ),
        ToolSpec(
            "list_pos",
            "List ERP purchase orders, filtered by supplier, part, status, "
            "or late_only=true for open POs that are late.",
            "erp",
            "purchase_order",
            "/purchase_orders",
            True,
            (),
            (
                ("supplier_id", "string"),
                ("part_number", "string"),
                ("status", "string"),
                ("late_only", "boolean"),
            ),
        ),
        ToolSpec(
            "get_supplier",
            "Get one ERP supplier by id, e.g. SUP-007.",
            "erp",
            "supplier",
            "/suppliers/{supplier_id}",
            False,
            ("supplier_id",),
        ),
        ToolSpec(
            "find_supplier",
            "Find ERP suppliers whose name contains the given text.",
            "erp",
            "supplier",
            "/suppliers",
            True,
            ("name",),
        ),
        ToolSpec(
            "get_requirement",
            "Get one requirement by id, e.g. REQ-118.",
            "req",
            "requirement",
            "/requirements/{req_id}",
            False,
            ("req_id",),
        ),
        ToolSpec(
            "list_requirement_parts",
            "List the PLM parts a requirement applies to.",
            "req",
            "part",
            "/requirements/{req_id}/parts",
            True,
            ("req_id",),
        ),
        ToolSpec(
            "list_requirements_for_part",
            "List the requirements that apply to a part.",
            "req",
            "requirement",
            "/requirements",
            True,
            ("part_number",),
        ),
        ToolSpec(
            "dw_supplier_on_time",
            "Data warehouse: a supplier's received POs, on-time count and rate, and open late POs.",
            "dw",
            "supplier_on_time",
            "/supplier_on_time/{supplier_id}",
            False,
            ("supplier_id",),
        ),
        ToolSpec(
            "dw_cycle_time",
            "Data warehouse: closed work-order count and average/last "
            "cycle time in days for a part's serials.",
            "dw",
            "wo_cycle_time",
            "/wo_cycle_time/{part_number}",
            False,
            ("part_number",),
        ),
    )
}


@dataclass
class ToolOutcome:
    name: str
    args: dict[str, Any]
    system: str
    endpoint: str
    path: str = ""
    status: str = "ok"  # ok | not_found | error
    http_status: int = 0
    body: Any = None
    detail: str = ""
    latency_ms: int = 0
    record_type: str = ""
    is_list: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        if self.status == "not_found":
            return True
        return self.is_list and isinstance(self.body, dict) and not self.body.get("items")

    def for_model(self) -> Any:
        """What the model sees: the body (lists truncated) or an error object."""
        if self.status == "not_found":
            return {"error": "not_found"}
        if self.status == "error":
            return {"error": self.detail}
        if self.is_list and isinstance(self.body, dict):
            items = self.body.get("items", [])
            if len(items) > MAX_ITEMS_TO_MODEL:
                return {**self.body, "items": items[:MAX_ITEMS_TO_MODEL], "truncated": True}
        return self.body


def execute(name: str, args: dict[str, Any], allowed: tuple[str, ...]) -> ToolOutcome:
    spec = TOOLS.get(name)
    if spec is None or name not in allowed:
        return ToolOutcome(
            name,
            args,
            spec.system if spec else "?",
            spec.endpoint if spec else "",
            status="error",
            detail=f"tool {name} is not allowed here",
        )
    outcome = ToolOutcome(
        name, args, spec.system, spec.endpoint, record_type=spec.record_type, is_list=spec.is_list
    )
    missing = [r for r in spec.required if not args.get(r)]
    if missing:
        outcome.status, outcome.detail = "error", f"missing argument {', '.join(missing)}"
        return outcome
    path = spec.path.format(
        **{k: str(args[k]) for k in spec.required if "{" + k + "}" in spec.path}
    )
    params = {k: v for k, v in args.items() if "{" + k + "}" not in spec.path and v is not None}
    params = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()}
    outcome.path = f"/systems/{spec.system}{path}"
    started = time.monotonic()
    try:
        resp = systems_client().get(outcome.path, params=params or None)
    except httpx.HTTPError as exc:
        outcome.status, outcome.detail = "error", f"{type(exc).__name__}: {exc}"
        return outcome
    finally:
        outcome.latency_ms = int((time.monotonic() - started) * 1000)
    outcome.http_status = resp.status_code
    if resp.status_code == 404:
        outcome.status = "not_found"
    elif resp.status_code != 200:
        outcome.status, outcome.detail = "error", f"HTTP {resp.status_code}"
    else:
        outcome.body = resp.json()
    return outcome
