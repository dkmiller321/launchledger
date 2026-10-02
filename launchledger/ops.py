"""Whole-system operations shared by the CLI and the test routes."""

from sqlalchemy import delete

from launchledger.db import models as m
from launchledger.db.session import session_scope
from launchledger.systems.seed import is_seeded, seed

APP_TABLES_IN_DELETE_ORDER: tuple[type[m.Base], ...] = (
    m.FeedbackEvent,
    m.Feedback,
    m.EvalResult,
    m.EvalRun,
    m.GuardrailResult,
    m.RunStep,
    m.Run,
    m.DriftIncident,
    m.ContractBaseline,
    m.DriftScenarioState,
)


def clear_app_tables() -> None:
    with session_scope() as s:
        for model in APP_TABLES_IN_DELETE_ORDER:
            s.execute(delete(model))


def seed_systems(if_empty: bool = False) -> bool:
    """Seed the system schemas. Returns False when skipped because data already exists."""
    with session_scope() as s:
        if if_empty and is_seeded(s):
            return False
        seed(s)
    return True


def reset_all() -> None:
    """Test reset (E2E_TESTS.md §1.3): app tables, drift state, seed, baselines, overrides."""
    from launchledger.contracts.monitor import capture_baselines
    from launchledger.evals.cases import clear_drafts, clear_overrides

    clear_app_tables()
    seed_systems()
    capture_baselines()
    clear_overrides()
    clear_drafts()
