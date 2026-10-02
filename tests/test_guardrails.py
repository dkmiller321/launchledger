"""IT-04: every guardrail passes good input and fails bad input (pure, no HTTP)."""

from typing import Any

from launchledger.assistant.schema import FinalAnswer
from launchledger.guardrails.rules import (
    GuardContext,
    blocked_reason,
    citation_required,
    export_control,
    facts_match_source,
    ids_exist,
    run_all,
    uncertainty_stated,
)

RECORDS: dict[tuple[str, str], dict[str, Any]] = {
    ("serial", "SN-0042"): {"serial_number": "SN-0042", "status": "IN_BUILD"},
    ("part", "P-1077"): {
        "part_number": "P-1077",
        "name": "Turbopump inducer housing",
        "revision": "C",
        "unit_cost_usd": 18450.0,
        "export_controlled": True,
        "controlled_notes": "Inducer blade angle 11.5 deg; CMM tolerance 0.02 mm",
    },
    ("purchase_order", "PO-10233"): {"po_id": "PO-10233", "qty": 4, "status": "OPEN"},
}


def fetch(record_type: str, record_id: str) -> dict[str, Any] | None:
    return RECORDS.get((record_type, record_id))


def ctx(data: dict[str, Any], **kw: Any) -> GuardContext:
    return GuardContext(answer=FinalAnswer.model_validate(data), fetch=fetch, **kw)


def fact(rtype: str, rid: str, field: str, value: Any, system: str = "MES") -> dict[str, Any]:
    return {
        "system": system,
        "record_type": rtype,
        "record_id": rid,
        "field": field,
        "value": value,
    }


GOOD = {
    "answer": "SN-0042 is IN_BUILD.",
    "claims": [{"text": "x", "facts": [fact("serial", "SN-0042", "status", "IN_BUILD")]}],
}


def test_good_answer_passes_everything() -> None:
    results = run_all(ctx(GOOD))
    assert all(r.passed for r in results)
    assert blocked_reason(results) == ""


def test_citation_required() -> None:
    assert not citation_required(ctx({"answer": "a", "claims": [{"text": "x"}]})).passed


def test_facts_match_source() -> None:
    bad = {
        "answer": "a",
        "claims": [{"text": "x", "facts": [fact("serial", "SN-0042", "status", "SHIPPED")]}],
    }
    result = facts_match_source(ctx(bad))
    assert not result.passed and "IN_BUILD" in result.detail and "SHIPPED" in result.detail
    numeric = {
        "answer": "a",
        "claims": [{"text": "x", "facts": [fact("purchase_order", "PO-10233", "qty", 4.0, "ERP")]}],
    }
    assert facts_match_source(ctx(numeric)).passed
    wrong_system = {
        "answer": "a",
        "claims": [
            {"text": "x", "facts": [fact("serial", "SN-0042", "status", "IN_BUILD", "ERP")]}
        ],
    }
    assert not facts_match_source(ctx(wrong_system)).passed
    missing = {
        "answer": "a",
        "claims": [{"text": "x", "facts": [fact("serial", "SN-0001", "status", "IN_BUILD")]}],
    }
    assert not facts_match_source(ctx(missing)).passed


def test_ids_exist_and_caveat_exemption() -> None:
    ghost = ids_exist(ctx({"answer": "SN-0042 and SN-9999."}))
    assert not ghost.passed and "SN-9999 not found in MES" in ghost.detail
    stated = {"answer": "I couldn't find SN-0404.", "caveats": ["SN-0404 was not found."]}
    assert ids_exist(ctx(stated)).passed
    assert ids_exist(ctx({"answer": "SUP-0071 is not an ID we check."})).passed


def test_export_control() -> None:
    part = RECORDS[("part", "P-1077")]
    leak = ctx({"answer": "Blade angle 11.5 deg."}, fetched_records=[("part", part)])
    assert not export_control(leak).passed
    cited = ctx(
        {
            "answer": "a",
            "claims": [
                {
                    "text": "x",
                    "facts": [
                        fact("part", "P-1077", "controlled_notes", part["controlled_notes"], "PLM")
                    ],
                }
            ],
        }
    )
    assert not export_control(cited).passed
    cost = ctx(
        {
            "answer": "a",
            "claims": [
                {"text": "x", "facts": [fact("part", "P-1077", "unit_cost_usd", 18450.0, "PLM")]}
            ],
        }
    )
    assert not export_control(cost).passed
    allowed = ctx(
        {
            "answer": "P-1077 is export-controlled; revision C.",
            "claims": [
                {
                    "text": "x",
                    "facts": [
                        fact("part", "P-1077", "export_controlled", True, "PLM"),
                        fact("part", "P-1077", "name", part["name"], "PLM"),
                    ],
                }
            ],
        },
        fetched_records=[("part", part)],
    )
    assert export_control(allowed).passed


def test_uncertainty_stated() -> None:
    assert not uncertainty_stated(ctx({"answer": "a"}, tool_empty_or_failed=True)).passed
    assert uncertainty_stated(
        ctx({"answer": "a", "caveats": ["none found"]}, tool_empty_or_failed=True)
    ).passed


def test_blocked_reason_templates() -> None:
    results = run_all(ctx({"answer": "SN-0404 is in Bay 1."}, tool_empty_or_failed=True))
    reason = blocked_reason(results)
    assert reason.startswith("Blocked by guardrails: ids_exist, uncertainty_stated (")
    single = blocked_reason(run_all(ctx({"answer": "a", "claims": [{"text": "x"}]})))
    assert single.startswith("Blocked by guardrail: citation_required (")
