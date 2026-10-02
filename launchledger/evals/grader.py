"""Deterministic grader (PRD V2). No LLM judge."""

from dataclasses import dataclass, field
from typing import Any

from launchledger.assistant.schema import same_value
from launchledger.evals.cases import Case


@dataclass
class Grade:
    passed: bool
    outcome: str  # correct | declined | wrong
    diff: list[str] = field(default_factory=list)


def _key(f: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(f.get("system", "")).upper(),
        str(f.get("record_type", "")),
        str(f.get("record_id", "")),
        str(f.get("field", "")),
    )


def _label(f: dict[str, Any]) -> str:
    sys_, rtype, rid, fld = _key(f)
    return f"{sys_} {rtype} {rid} {fld} = {f.get('value')}"


def grade(
    case: Case,
    workflow: str | None,
    decision: str,
    answer: dict[str, Any] | None,
    drift_mode: bool = False,
) -> Grade:
    diff: list[str] = []
    if workflow != case.expected_workflow:
        diff.append(f"workflow: expected {case.expected_workflow}, got {workflow}")
    if decision != case.expected_decision:
        diff.append(f"decision: expected {case.expected_decision}, got {decision}")
    facts = [f for c in (answer or {}).get("claims", []) for f in c.get("facts", [])]
    for exp in case.expected_facts:
        matches = [f for f in facts if _key(f) == _key(exp)]
        if not any(same_value(exp.get("value"), f.get("value")) for f in matches):
            got = ", ".join(str(f.get("value")) for f in matches) or "not cited"
            diff.append(f"missing fact {_label(exp)} (got {got})")
    text = " ".join([str((answer or {}).get("answer", "")), *[str(f.get("value")) for f in facts]])
    for bad in case.forbidden_values:
        if bad in text:
            diff.append(f"forbidden value present: {bad}")
    correct = not diff
    if correct:
        return Grade(True, "correct", diff)
    if drift_mode and decision == "declined":
        return Grade(False, "declined", diff)
    return Grade(False, "wrong", diff)
