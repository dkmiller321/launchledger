"""Golden cases (PRD V1) from evals/cases/*.yaml, plus drafts and test-only overrides."""

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from launchledger.assistant.workflows import WORKFLOWS
from launchledger.llm.provider import REPO_ROOT
from launchledger.settings import get_settings

_overrides: dict[str, list[dict[str, Any]]] = {}


@dataclass
class Case:
    id: str
    question: str
    expected_workflow: str
    expected_decision: str
    expected_facts: list[dict[str, Any]]
    forbidden_values: list[str] = field(default_factory=list)
    is_draft: bool = False

    @property
    def workflow_id(self) -> str:
        return WORKFLOWS[self.expected_workflow].id


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _load_file(path: Path, is_draft: bool) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [
        Case(
            id=str(c["id"]),
            question=str(c["question"]),
            expected_workflow=str(c["expected_workflow"]),
            expected_decision=str(c.get("expected_decision", "answered")),
            expected_facts=list(c.get("expected_facts") or []),
            forbidden_values=[str(v) for v in c.get("forbidden_values") or []],
            is_draft=is_draft,
        )
        for c in raw
    ]


def load_cases(workflow_ids: list[str] | None = None, include_drafts: bool = True) -> list[Case]:
    settings = get_settings()
    cases: list[Case] = []
    for path in sorted(_resolve(settings.eval_cases_dir).glob("*.yaml")):
        cases.extend(_load_file(path, False))
    drafts_dir = _resolve(settings.eval_drafts_dir)
    if include_drafts and drafts_dir.exists():
        for path in sorted(drafts_dir.glob("*.yaml")):
            cases.extend(_load_file(path, True))
    for case in cases:
        if case.id in _overrides:
            case.expected_facts = _overrides[case.id]
    if workflow_ids:
        wanted = {w.upper() for w in workflow_ids}
        cases = [c for c in cases if c.workflow_id in wanted or c.expected_workflow in wanted]
    return sorted(cases, key=lambda c: (c.is_draft, _sort_key(c.id)))


def _sort_key(case_id: str) -> tuple[int, str]:
    head = case_id.split("-")[0]
    return (int(head[1:]) if head[1:].isdigit() else 99, case_id)


def set_override(case_id: str, expected_facts: list[dict[str, Any]]) -> None:
    _overrides[case_id] = expected_facts


def clear_overrides() -> None:
    _overrides.clear()


def clear_drafts() -> None:
    drafts_dir = _resolve(get_settings().eval_drafts_dir)
    if drafts_dir.exists():
        shutil.rmtree(drafts_dir)


def write_draft(case_id: str, question: str, workflow: str, facts: list[dict[str, Any]]) -> Path:
    drafts_dir = _resolve(get_settings().eval_drafts_dir)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    path = drafts_dir / f"{case_id}.yaml"
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": case_id,
                    "question": question,
                    "expected_workflow": workflow,
                    "expected_decision": "answered",
                    "expected_facts": facts,
                    "forbidden_values": [],
                }
            ],
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path
