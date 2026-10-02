"""Test-only routes (E2E_TESTS.md §1.3). Mounted only when TEST_MODE=1; otherwise 404."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from launchledger.db.session import session_scope
from launchledger.evals.cases import set_override
from launchledger.ops import reset_all
from launchledger.systems.seed import seed_hash

test_router = APIRouter(prefix="/api/test")


@test_router.post("/reset")
async def reset() -> dict[str, Any]:
    await run_in_threadpool(reset_all)
    return {"ok": True}


@test_router.get("/seed-hash")
def get_seed_hash() -> dict[str, Any]:
    with session_scope() as s:
        return {"hash": seed_hash(s)}


@test_router.post("/eval-overrides")
async def eval_overrides(request: Request) -> JSONResponse:
    data = await request.json()
    set_override(str(data["case_id"]), list(data["expected_facts"]))
    return JSONResponse({"ok": True})
