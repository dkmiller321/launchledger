"""IT-01, IT-02, IT-11 (E2E_TESTS.md §5)."""

import pytest
from starlette.testclient import TestClient

from tests.conftest import REPO_ROOT, build_app, clear_caches


def test_it_01_missing_database_url_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    from launchledger.settings import ConfigError, load_settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_settings(env_file=None)
    assert "DATABASE_URL" in str(exc.value)


def test_it_01_openrouter_mode_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from launchledger.settings import ConfigError, load_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1/x")
    monkeypatch.setenv("LLM_MODE", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_settings(env_file=None)
    assert "OPENROUTER_API_KEY" in str(exc.value)


@pytest.mark.parametrize(
    "flag,routes",
    [
        (
            "TEST_MODE",
            [
                ("post", "/api/test/reset"),
                ("get", "/api/test/seed-hash"),
                ("post", "/api/test/eval-overrides"),
            ],
        ),
        (
            "DRIFT_INJECTION",
            [
                ("post", "/api/admin/drift/erp_rename_promised_date/enable"),
                ("post", "/api/admin/drift/erp_rename_promised_date/set"),
                ("post", "/api/admin/drift/incidents/1/resolve"),
            ],
        ),
    ],
)
def test_it_02_gated_routes_404_when_flag_off(
    test_db: str, monkeypatch: pytest.MonkeyPatch, flag: str, routes: list[tuple[str, str]]
) -> None:
    monkeypatch.setenv(flag, "0")
    clear_caches()
    try:
        with TestClient(build_app()) as c:
            for method, path in routes:
                assert getattr(c, method)(path).status_code == 404, path
    finally:
        monkeypatch.setenv(flag, "1")
        clear_caches()


def test_it_02_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok", "db": True, "llm_mode": "mock"}


def test_it_11_ci_runs_every_gate() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for needle in (
        "postgres:16",
        "ruff check",
        "ruff format --check",
        "mypy",
        "pytest tests",
        "ll eval run --model mock",
        "--drift erp_rename_promised_date",
        "--drift mes_new_wo_status",
        "--drift erp_cost_in_cents",
        'pytest e2e -m "not smoke"',
    ):
        assert needle in ci, needle
