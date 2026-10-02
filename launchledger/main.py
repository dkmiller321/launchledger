"""FastAPI app: UI, assistant API, the fake systems under /systems/*, and the drift monitor."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from launchledger.settings import get_settings
from launchledger.systems.apps import SYSTEM_APPS
from launchledger.web.routes import admin_router, router

log = logging.getLogger(__name__)


async def _monitor_loop(interval_s: int) -> None:
    from launchledger.contracts.monitor import check_now

    while True:
        await asyncio.sleep(interval_s)
        try:
            await run_in_threadpool(check_now)
        except Exception:  # a crashed tick logs and the loop continues (PRD §5)
            log.exception("drift monitor tick failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    interval = get_settings().drift_monitor_interval_s
    task = asyncio.create_task(_monitor_loop(interval)) if interval > 0 else None
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LaunchLedger", lifespan=lifespan)
    for name, sub in SYSTEM_APPS.items():
        app.mount(f"/systems/{name}", sub)
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
        name="static",
    )
    app.include_router(router)
    if settings.drift_injection:
        app.include_router(admin_router)
    if settings.test_mode:
        from launchledger.web.test_routes import test_router

        app.include_router(test_router)
    return app


app = create_app()
