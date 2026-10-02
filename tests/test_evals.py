"""IT-05, IT-06, IT-07: the eval CLI gate, golden facts vs the seed, drift-mode evals."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from launchledger.assistant.schema import same_value
from launchledger.evals.cases import load_cases
from launchledger.evals.grader import grade
from launchledger.systems.records import record_path
from tests.conftest import REPO_ROOT


def ll(*args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONWARNINGS": "ignore", **(extra_env or {})}
    return subprocess.run(
        ["uv", "run", "ll", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )


def test_grader() -> None:
    case = load_cases(["W5"])[0]
    facts = [dict(f) for f in case.expected_facts]
    answer = {"answer": "x", "claims": [{"text": "x", "facts": facts}]}
    assert grade(case, "po_status", "answered", answer).passed
    assert grade(case, "where_used", "answered", answer).outcome == "wrong"
    assert grade(case, "po_status", "declined", None, drift_mode=True).outcome == "declined"


def test_it_06_golden_facts_match_the_seed(clean: None, client: TestClient) -> None:
    cases = load_cases(include_drafts=False)
    assert len(cases) >= 30
    for case in cases:
        for f in case.expected_facts:
            got = client.get(record_path(f["record_type"], f["record_id"])).json()
            assert same_value(f["value"], got[f["field"]]), (case.id, f)


def test_it_05_cli_passes_then_fails_on_a_changed_golden_value(clean: None, tmp_path: Path) -> None:
    ok = ll("eval", "run", "--model", "mock", "--json-out", str(tmp_path / "r.json"))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "passed 60/60" in ok.stdout

    cases_dir = tmp_path / "cases"
    shutil.copytree(REPO_ROOT / "evals" / "cases", cases_dir)
    po = cases_dir / "po_status.yaml"
    data = yaml.safe_load(po.read_text(encoding="utf-8"))
    data[0]["expected_facts"][0]["value"] = "CLOSED"
    po.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    bad = ll(
        "eval",
        "run",
        "--model",
        "mock",
        "--workflow",
        "W5",
        extra_env={"EVAL_CASES_DIR": str(cases_dir)},
    )
    assert bad.returncode == 1, bad.stdout
    assert "GATE FAILED" in bad.stdout


@pytest.mark.parametrize(
    "scenario", ["erp_rename_promised_date", "mes_new_wo_status", "erp_cost_in_cents"]
)
def test_it_07_drift_mode_eval_has_no_wrong_answers(clean: None, scenario: str) -> None:
    out = ll("eval", "run", "--model", "mock", "--drift", scenario)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "| wrong 0" in out.stdout


def test_v8_compare_report(clean: None, tmp_path: Path) -> None:
    out = tmp_path / "compare.md"
    result = ll("eval", "compare", "mock", "mock", "--workflow", "W1", "--out", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    text = out.read_text(encoding="utf-8")
    assert "# Model comparison: mock vs mock" in text
    assert "| Passed | 5/5 | 5/5 |" in text
    assert "| serial_status | 5/5 | 5/5 |" in text
