"""Shared E2E fixtures: the server under test, DB reset, API client, timeouts (E2E_TESTS.md §1)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import psycopg
import pytest
from playwright.sync_api import expect

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DB = "postgresql+psycopg://launchledger:change-me@127.0.0.1:55432/launchledger_test"
TEST_PORT = 8001


def _dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _test_db_url() -> str:
    return (
        os.environ.get("TEST_DATABASE_URL") or _dotenv().get("TEST_DATABASE_URL") or DEFAULT_TEST_DB
    )


def _ensure_database(url: str) -> None:
    plain = url.replace("+psycopg", "")
    base, _, db_name = plain.rpartition("/")
    db_name = db_name.split("?")[0]
    with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _stop(proc: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def live_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    base_url = os.environ.get("BASE_URL")
    if base_url:
        yield base_url.rstrip("/")
        return

    db_url = _test_db_url()
    _ensure_database(db_url)

    env = {**os.environ, "DATABASE_URL": db_url}
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env, check=True)

    drafts_dir = tmp_path_factory.mktemp("eval-drafts")
    env.update(
        {
            "LLM_MODE": "mock",
            "TEST_MODE": "1",
            "DRIFT_INJECTION": "1",
            "FROZEN_TODAY": "2026-10-01",
            "MOCK_LATENCY_MS": "150",
            "DRIFT_MONITOR_INTERVAL_S": "0",
            "SYSTEMS_BASE_URL": f"http://127.0.0.1:{TEST_PORT}",
            "EVAL_DRAFTS_DIR": str(drafts_dir),
        }
    )
    log_dir = REPO_ROOT / "test-results"
    log_dir.mkdir(exist_ok=True)
    log = (log_dir / "server.log").open("w", encoding="utf-8")
    if _port_in_use(TEST_PORT):
        raise RuntimeError(
            f"port {TEST_PORT} is already in use; a stale server would be tested. Stop it first."
        )
    # Run uvicorn with this venv's interpreter directly (not `uv run`), so terminating the
    # process actually stops the server; on Windows `uv run` leaves the child orphaned.
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "launchledger.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(TEST_PORT),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{TEST_PORT}"
    try:
        deadline = time.monotonic() + 60
        while True:
            if proc.poll() is not None:
                raise RuntimeError("server exited early; see test-results/server.log")
            try:
                if httpx.get(f"{url}/healthz", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("server did not become healthy within 60 s")
            time.sleep(0.5)
        yield url
    finally:
        _stop(proc)
        log.close()


@pytest.fixture
def api(live_server: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=live_server, timeout=30) as client:
        yield client


@pytest.fixture(scope="session")
def base_url(live_server: str) -> str:
    """pytest-playwright reads this so page.goto("/...") resolves against the server."""
    return live_server


@pytest.fixture(autouse=True)
def _reset_db(request: pytest.FixtureRequest, live_server: str) -> None:
    if request.node.get_closest_marker("smoke"):
        return
    response = httpx.post(f"{live_server}/api/test/reset", timeout=60)
    response.raise_for_status()


@pytest.fixture(autouse=True)
def _timeouts(request: pytest.FixtureRequest) -> None:
    timeout_ms = int(os.environ.get("PW_TIMEOUT_MS", "10000"))
    expect.set_options(timeout=timeout_ms)
    if "page" in request.fixturenames:
        request.getfixturevalue("page").set_default_timeout(timeout_ms)
