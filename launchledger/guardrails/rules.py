"""Guardrails G1-G5 (PRD G1-G6): pure functions over the answer and what the run fetched.

Record lookups are injected (`fetch`), so every rule is unit-testable without HTTP.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from launchledger.assistant.schema import FinalAnswer, same_value

Fetch = Callable[[str, str], dict[str, Any] | None]  # (record_type, id) -> record or None

ID_PATTERN = re.compile(r"\b(SN-\d{4}|P-\d{4}|PO-\d{5}|WO-\d{5}|NCR-\d{4}|REQ-\d{3})\b")
ID_TYPES = {
    "SN": ("serial", "MES"),
    "P": ("part", "PLM"),
    "PO": ("purchase_order", "ERP"),
    "WO": ("work_order", "MES"),
    "NCR": ("ncr", "MES"),
    "REQ": ("requirement", "REQ"),
}
RECORD_SYSTEMS = {
    "part": "PLM",
    "bom_line": "PLM",
    "serial": "MES",
    "work_order": "MES",
    "inspection": "MES",
    "ncr": "MES",
    "supplier": "ERP",
    "purchase_order": "ERP",
    "requirement": "REQ",
    "supplier_on_time": "DW",
    "wo_cycle_time": "DW",
}
ALLOWED_CONTROLLED_FIELDS = {"part_number", "name", "export_controlled"}
NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class GuardContext:
    answer: FinalAnswer
    fetch: Fetch
    tool_empty_or_failed: bool = False
    fetched_records: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


@dataclass(frozen=True)
class GuardResult:
    rule: str
    passed: bool
    detail: str = ""


def citation_required(ctx: GuardContext) -> GuardResult:
    bad = [i + 1 for i, c in enumerate(ctx.answer.claims) if not c.facts]
    if bad:
        return GuardResult(
            "citation_required", False, f"claim {', '.join(map(str, bad))} has no cited facts"
        )
    return GuardResult("citation_required", True)


def facts_match_source(ctx: GuardContext) -> GuardResult:
    for claim in ctx.answer.claims:
        for f in claim.facts:
            label = f"{f.system.lower()}/{f.record_type}/{f.record_id}.{f.field}"
            expected_system = RECORD_SYSTEMS.get(f.record_type)
            if expected_system is None or expected_system != f.system.upper():
                return GuardResult(
                    "facts_match_source", False, f"{label} cites an unknown record type or system"
                )
            record = ctx.fetch(f.record_type, f.record_id)
            if record is None:
                return GuardResult("facts_match_source", False, f"{label}: record not found")
            if f.field not in record:
                return GuardResult("facts_match_source", False, f"{label}: no such field")
            if not same_value(f.value, record[f.field]):
                return GuardResult(
                    "facts_match_source",
                    False,
                    f"{label} is {record[f.field]}, answer says {f.value}",
                )
    return GuardResult("facts_match_source", True)


def ids_exist(ctx: GuardContext) -> GuardResult:
    caveat_text = " ".join(ctx.answer.caveats)
    missing = []
    for found in dict.fromkeys(ID_PATTERN.findall(ctx.answer.answer)):
        if found in caveat_text:
            continue
        record_type, system = ID_TYPES[found.split("-")[0]]
        if ctx.fetch(record_type, found) is None:
            missing.append(f"{found} not found in {system}")
    if missing:
        return GuardResult("ids_exist", False, "; ".join(missing))
    return GuardResult("ids_exist", True)


def export_control(ctx: GuardContext) -> GuardResult:
    controlled: dict[str, dict[str, Any]] = {}
    for record_type, rec in ctx.fetched_records:
        if record_type == "part" and rec.get("export_controlled") is True:
            controlled[str(rec.get("part_number"))] = rec
    for claim in ctx.answer.claims:
        for f in claim.facts:
            if f.record_type != "part" or f.field in ALLOWED_CONTROLLED_FIELDS:
                continue
            part = controlled.get(f.record_id) or ctx.fetch("part", f.record_id)
            if part and part.get("export_controlled") is True:
                return GuardResult(
                    "export_control",
                    False,
                    f"answer cites {f.field} of export-controlled {f.record_id}",
                )
    prose = ctx.answer.answer
    for pn, rec in controlled.items():
        notes = str(rec.get("controlled_notes") or "")
        if not notes:
            continue
        leaked = notes in prose or any(n in NUMBER.findall(prose) for n in NUMBER.findall(notes))
        if leaked:
            return GuardResult("export_control", False, f"answer reveals controlled data of {pn}")
    return GuardResult("export_control", True)


def uncertainty_stated(ctx: GuardContext) -> GuardResult:
    if ctx.tool_empty_or_failed and not ctx.answer.caveats:
        return GuardResult(
            "uncertainty_stated", False, "a tool returned no data but the answer states no caveat"
        )
    return GuardResult("uncertainty_stated", True)


RULES: tuple[Callable[[GuardContext], GuardResult], ...] = (
    citation_required,
    facts_match_source,
    ids_exist,
    export_control,
    uncertainty_stated,
)


def run_all(ctx: GuardContext) -> list[GuardResult]:
    return [rule(ctx) for rule in RULES]


def blocked_reason(results: list[GuardResult]) -> str:
    failed = [r for r in results if not r.passed]
    if not failed:
        return ""
    if len(failed) == 1:
        return f"Blocked by guardrail: {failed[0].rule} ({failed[0].detail})."
    names = ", ".join(r.rule for r in failed)
    details = "; ".join(r.detail for r in failed)
    return f"Blocked by guardrails: {names} ({details})."
