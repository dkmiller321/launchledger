"""Inline contract check (PRD D2) and open-incident gate (PRD D4). Pure functions."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from launchledger.contracts.schemas import CONTRACTS


@dataclass(frozen=True)
class Violation:
    field: str
    kind: str  # shape | enum | range | type
    problem: str


@dataclass(frozen=True)
class OpenIncident:
    id: int
    system: str
    field: str
    kind: str


@dataclass
class ContractResult:
    system: str
    endpoint: str
    violations: list[Violation] = field(default_factory=list)
    gated_by: OpenIncident | None = None

    @property
    def passed(self) -> bool:
        return not self.violations and self.gated_by is None

    @property
    def primary(self) -> Violation | None:
        return self.violations[0] if self.violations else None

    def decision_reason(self) -> str:
        """Exact templates from E2E_TESTS.md §1.7."""
        if self.violations:
            problems = "; ".join(v.problem for v in self.violations)
            return (
                f"Declined: upstream data from {self.system.upper()} failed its contract "
                f"({self.endpoint}: {problems})."
            )
        assert self.gated_by is not None
        g = self.gated_by
        return f"Declined: open drift incident on {g.system.upper()} {g.field} ({g.kind})."

    def to_json(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "endpoint": self.endpoint,
            "contract": "pass" if self.passed else "fail",
            "violations": [v.__dict__ for v in self.violations],
            "gated_by": self.gated_by.__dict__ if self.gated_by else None,
        }


def _violation(err: Any) -> Violation:
    loc = [str(p) for p in err.get("loc", ())]
    name = loc[0] if loc else "?"
    etype = err.get("type", "")
    value = err.get("input")
    if etype == "missing":
        return Violation(name, "shape", f"{name} missing")
    if etype == "extra_forbidden":
        return Violation(name, "shape", f"unexpected field {name}")
    if etype in ("literal_error", "enum"):
        return Violation(name, "enum", f"{name} unexpected value {value}")
    if etype in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        return Violation(name, "range", f"{name} out of range ({value})")
    if value is None:
        return Violation(name, "shape", f"{name} is null")
    if etype.startswith("date"):
        return Violation(name, "shape", f"{name} invalid date '{value}'")
    return Violation(name, "type", f"{name} {err.get('msg', 'invalid')}")


def validate_records(record_type: str, records: list[dict[str, Any]]) -> list[Violation]:
    """Every distinct violation across the records, in field order of the first record seen."""
    contract = CONTRACTS[record_type]
    seen: dict[str, Violation] = {}
    for rec in records:
        try:
            contract.model_validate(rec)
        except ValidationError as exc:
            for err in exc.errors():
                v = _violation(err)
                seen.setdefault(v.problem, v)
    # Missing fields first, so a rename names the field that disappeared.
    return sorted(seen.values(), key=lambda v: v.problem.startswith("unexpected"))


def records_of(body: Any, is_list: bool) -> list[dict[str, Any]]:
    if is_list:
        items = body.get("items", []) if isinstance(body, dict) else []
        return [i for i in items if isinstance(i, dict)]
    return [body] if isinstance(body, dict) else []


def check_response(
    system: str,
    endpoint: str,
    record_type: str,
    body: Any,
    is_list: bool,
    open_incidents: list[OpenIncident],
) -> ContractResult:
    result = ContractResult(system=system, endpoint=endpoint)
    records = records_of(body, is_list)
    result.violations = validate_records(record_type, records)
    if result.violations:
        return result
    for incident in open_incidents:
        if incident.system == system and any(incident.field in r for r in records):
            result.gated_by = incident
            break
    return result
