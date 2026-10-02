"""Which drift scenarios are injected right now (stored in app.drift_scenarios)."""

from sqlalchemy import select

from launchledger.db.models import DriftScenarioState
from launchledger.db.session import session_scope
from launchledger.drift.scenarios import SCENARIOS
from launchledger.settings import get_settings


def enabled_scenarios() -> list[str]:
    if not get_settings().drift_injection:
        return []
    with session_scope() as s:
        rows = s.scalars(select(DriftScenarioState).where(DriftScenarioState.enabled)).all()
        return sorted(r.name for r in rows if r.name in SCENARIOS)


def set_scenario(name: str, enabled: bool) -> None:
    if name not in SCENARIOS:
        raise KeyError(name)
    with session_scope() as s:
        row = s.get(DriftScenarioState, name)
        if row is None:
            s.add(DriftScenarioState(name=name, enabled=enabled))
        else:
            row.enabled = enabled
