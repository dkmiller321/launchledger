"""Integration fixtures: a migrated test database and in-process clients (no server needed)."""

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DB = "postgresql+psycopg://launchledger:change-me@127.0.0.1:55432/launchledger_test"

TEST_ENV = {
    "LLM_MODE": "mock",
    "TEST_MODE": "1",
    "DRIFT_INJECTION": "1",
    "FROZEN_TODAY": "2026-10-01",
    "MOCK_LATENCY_MS": "0",
    "DRIFT_MONITOR_INTERVAL_S": "0",
}


def _test_db_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return DEFAULT_TEST_DB


def _ensure_database(url: str) -> None:
    plain = url.replace("+psycopg", "")
    base, _, name = plain.rpartition("/")
    with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')


def clear_caches() -> None:
    from launchledger.db.session import _factory, get_engine
    from launchledger.llm.mock import load_scripts
    from launchledger.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    _factory.cache_clear()
    load_scripts.cache_clear()


@pytest.fixture(scope="session")
def test_db(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    url = _test_db_url()
    _ensure_database(url)
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    saved = dict(os.environ)
    os.environ.update(
        {**TEST_ENV, "DATABASE_URL": url, "EVAL_DRAFTS_DIR": str(tmp_path_factory.mktemp("drafts"))}
    )
    clear_caches()
    yield url
    os.environ.clear()
    os.environ.update(saved)
    clear_caches()


def build_app() -> FastAPI:
    from launchledger.main import create_app

    return create_app()


@pytest.fixture(scope="session")
def app(test_db: str) -> FastAPI:
    from launchledger.systems.client import use_client_factory

    application = build_app()
    use_client_factory(lambda: TestClient(application, base_url="http://testserver"))
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def clean(app: FastAPI) -> None:
    """Fresh seed, baselines and app tables, like POST /api/test/reset."""
    from launchledger.ops import reset_all

    reset_all()
