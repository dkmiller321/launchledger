"""IT-10: dashboard numbers equal direct SQL counts after `ll demo seed-activity`; P1 drift."""

import pytest
from sqlalchemy import text

from launchledger.dashboard.demo import seed_activity
from launchledger.dashboard.metrics import compute, weekly_report
from launchledger.db.session import session_scope
from tests.test_evals import ll


def sql(query: str) -> int:
    with session_scope() as s:
        return int(s.execute(text(query)).scalar() or 0)


def test_it_10_dashboard_matches_sql(clean: None) -> None:
    seed_activity()
    m = compute()
    for decision in ("answered", "declined", "blocked"):
        assert m["decisions"][decision] == sql(
            f"SELECT count(*) FROM app.runs WHERE decision = '{decision}'"
        )
    assert m["decisions"] == {"answered": 14, "declined": 4, "blocked": 2}
    for status in ("new", "triaged", "fixed"):
        assert m["backlog"][status] == sql(
            f"SELECT count(*) FROM app.feedback WHERE rating = 'down' AND status = '{status}'"
        )
    assert m["backlog"] == {"new": 1, "triaged": 2, "fixed": 1}
    assert m["inflow_total"] == sql("SELECT count(*) FROM app.feedback WHERE rating = 'down'")
    assert m["outflow_total"] == sql(
        "SELECT count(*) FROM app.feedback WHERE status IN ('verified', 'wont_fix')"
    )
    assert [(w["week"], w["inflow"], w["outflow"]) for w in m["weeks"]] == [
        ("2026-W36", 2, 1),
        ("2026-W37", 3, 2),
        ("2026-W38", 4, 2),
        ("2026-W39", 3, 3),
    ]
    assert m["incidents_total"] == sql("SELECT count(*) FROM app.drift_incidents") == 2
    assert m["latest_eval"]["passed"] == 30
    report = weekly_report(m)
    assert "| 2026-W39 | 3 | 3 |" in report and "30/30" in report


@pytest.mark.parametrize("scenario", ["plm_null_revision", "erp_date_format"])
def test_p1_drift_mode_eval_has_no_wrong_answers(clean: None, scenario: str) -> None:
    out = ll("eval", "run", "--model", "mock", "--drift", scenario)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "| wrong 0" in out.stdout
