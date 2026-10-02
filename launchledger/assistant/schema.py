"""Structured final answer (PRD A4): prose, claims with field-level facts, caveats."""

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

FactValue = str | int | float | bool | None


class Fact(BaseModel):
    system: str
    record_type: str
    record_id: str
    field: str
    value: FactValue


class Claim(BaseModel):
    text: str
    facts: list[Fact] = Field(default_factory=list)


class FinalAnswer(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def parse_final(content: str | None) -> tuple[FinalAnswer | None, str]:
    """Parse model output into a FinalAnswer, or return the validation error text."""
    text = (content or "").strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON ({exc.msg})"
    try:
        return FinalAnswer.model_validate(data), ""
    except ValidationError as exc:
        return None, "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]
        )


def same_value(a: FactValue, b: Any) -> bool:
    """Value matching for graders and G2: numbers numerically, everything else as text."""
    if isinstance(a, bool) or isinstance(b, bool):
        return str(a).lower() == str(b).lower()
    if isinstance(a, int | float) or isinstance(b, int | float):
        try:
            return float(a) == float(b)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    return str(a) == str(b)
