"""HTML pages and JSON API. HTMX requests get partials; other clients get JSON."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from launchledger.assistant.runner import run_question
from launchledger.assistant.workflows import WORKFLOWS
from launchledger.contracts.incidents import incidents_json, resolve
from launchledger.contracts.monitor import check_now
from launchledger.db.session import db_ok
from launchledger.drift.scenarios import SCENARIOS
from launchledger.drift.state import enabled_scenarios, set_scenario
from launchledger.evals.runner import eval_json, recent_eval_runs, start_background
from launchledger.feedback.service import (
    DISPOSITIONS,
    STATUSES,
    FeedbackError,
    convert_to_case,
    create_feedback,
    list_feedback,
    update_feedback,
)
from launchledger.settings import get_settings
from launchledger.systems.client import systems_client
from launchledger.systems.records import RECORD_TYPES, record_path
from launchledger.web.views import list_runs, run_view

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter()

EXAMPLES = [
    "Where is SN-0042 and what's blocking it?",
    "Which open work orders are at risk from late POs from Apex Castings?",
    "Which assemblies use part P-1077?",
    "What's the status of PO-10233 and is it late?",
    "Is SN-0042 ready for stage integration?",
]


def _htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def page(request: Request, name: str, active: str, **ctx: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"active": active, **ctx})


async def _payload(request: Request) -> dict[str, Any]:
    if request.headers.get("content-type", "").startswith("application/json"):
        data: dict[str, Any] = await request.json()
        return data
    return dict(await request.form())


@router.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "db": db_ok(), "llm_mode": get_settings().llm_mode}


# --- Ask ---------------------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def ask_page(request: Request) -> HTMLResponse:
    return page(request, "ask.html", "ask", workflows=list(WORKFLOWS.values()), examples=EXAMPLES)


@router.post("/api/ask", response_model=None)
async def api_ask(request: Request) -> Response:
    data = await _payload(request)
    question = str(data.get("question", "")).strip()
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=422)
    workflow = str(data.get("workflow") or "auto")
    chosen = None if workflow == "auto" else workflow
    if chosen is not None and chosen not in WORKFLOWS:
        return JSONResponse({"error": f"unknown workflow {chosen}"}, status_code=422)
    result = await run_in_threadpool(run_question, question, chosen)
    if _htmx(request):
        return templates.TemplateResponse(
            request, "_answer_card.html", {"run": run_view(result.run_id)}
        )
    return JSONResponse(
        {"run_id": result.run_id, "decision": result.decision, "decision_reason": result.reason}
    )


# --- Runs and records --------------------------------------------------------------------------


@router.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request, decision: str = "all") -> HTMLResponse:
    return page(request, "runs.html", "runs", runs=list_runs(decision), decision=decision)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_page(request: Request, run_id: int) -> HTMLResponse:
    run = run_view(run_id)
    if run is None:
        return page(request, "not_found.html", "runs", what=f"Run {run_id}")
    return page(request, "run_detail.html", "runs", run=run)


@router.get("/api/runs/{run_id}")
def api_run(run_id: int) -> JSONResponse:
    run = run_view(run_id)
    if run is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(run)


@router.get("/records/{system}/{record_type}/{record_id}", response_class=HTMLResponse)
def record_page(request: Request, system: str, record_type: str, record_id: str) -> HTMLResponse:
    rt = RECORD_TYPES.get(record_type)
    if rt is None or rt.system != system:
        return page(request, "not_found.html", "", what=f"Record type {system}/{record_type}")
    resp = systems_client().get(record_path(record_type, record_id))
    if resp.status_code != 200:
        return page(request, "not_found.html", "", what=f"{system.upper()} {record_id}")
    return page(
        request,
        "record.html",
        "",
        system=system,
        record_type=record_type,
        record_id=record_id,
        record=resp.json(),
    )


# --- Evals -------------------------------------------------------------------------------------


def _eval_view(eval_id: int) -> dict[str, Any] | None:
    report = eval_json(eval_id)
    if report is None:
        return None
    workflows = sorted(
        report.get("per_workflow", {}).items(), key=lambda kv: int(WORKFLOWS[kv[0]].id[1:])
    )
    return {**report, "workflows": workflows}


@router.get("/evals", response_class=HTMLResponse)
def evals_page(request: Request) -> HTMLResponse:
    return page(
        request, "evals.html", "evals", runs=recent_eval_runs(), scenarios=list(SCENARIOS.values())
    )


@router.post("/api/evals/run", response_model=None)
async def api_eval_run(request: Request) -> Response:
    data = await _payload(request)
    model = str(data.get("model") or "mock")
    drift = str(data.get("drift") or "none")
    drift_name = None if drift == "none" else drift
    if drift_name is not None and drift_name not in SCENARIOS:
        return JSONResponse({"error": f"unknown drift scenario {drift}"}, status_code=422)
    eval_id = await run_in_threadpool(start_background, model, drift_name)
    if _htmx(request):
        return templates.TemplateResponse(request, "_eval_detail.html", {"e": _eval_view(eval_id)})
    return JSONResponse({"id": eval_id, "status": "running"})


@router.get("/evals/{eval_id}", response_class=HTMLResponse)
def eval_page(request: Request, eval_id: int) -> HTMLResponse:
    view = _eval_view(eval_id)
    if view is None:
        return page(request, "not_found.html", "evals", what=f"Eval run {eval_id}")
    return page(request, "eval_page.html", "evals", e=view)


@router.get("/evals/{eval_id}/partial", response_class=HTMLResponse)
def eval_partial(request: Request, eval_id: int) -> HTMLResponse:
    return templates.TemplateResponse(request, "_eval_detail.html", {"e": _eval_view(eval_id)})


@router.get("/api/evals/{eval_id}")
def api_eval(eval_id: int) -> JSONResponse:
    report = eval_json(eval_id)
    if report is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(report)


# --- Drift -------------------------------------------------------------------------------------

SYSTEM_NAMES = ("plm", "mes", "erp", "req", "dw")


def _drift_context() -> dict[str, Any]:
    incidents = incidents_json()
    red = {i["system"] for i in incidents if i["status"] == "open"}
    return {
        "systems": [(name, "red" if name in red else "green") for name in SYSTEM_NAMES],
        "scenarios": list(SCENARIOS.values()),
        "enabled": set(enabled_scenarios()),
        "injection": get_settings().drift_injection,
        "incidents": incidents,
    }


def drift_panel(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "_drift_panel.html", _drift_context())


@router.get("/drift", response_class=HTMLResponse)
def drift_page(request: Request) -> HTMLResponse:
    return page(request, "drift.html", "drift", **_drift_context())


@router.get("/api/drift/incidents")
def api_incidents() -> JSONResponse:
    return JSONResponse(incidents_json())


@router.post("/api/drift/check", response_model=None)
async def api_drift_check(request: Request) -> Response:
    found = await run_in_threadpool(check_now)
    if _htmx(request):
        return drift_panel(request)
    return JSONResponse({"problems": found})


@router.post("/api/drift/incidents/{incident_id}/resolve", response_model=None)
def api_resolve(request: Request, incident_id: int) -> Response:
    ok = resolve(incident_id)
    if _htmx(request):
        return drift_panel(request)
    return JSONResponse({"resolved": ok}, status_code=200 if ok else 404)


# --- Admin: drift injection (only with DRIFT_INJECTION=1) ---------------------------------------

admin_router = APIRouter(prefix="/api/admin/drift")


@admin_router.post("/{scenario}/set", response_model=None)
async def admin_set(request: Request, scenario: str) -> Response:
    if scenario not in SCENARIOS:
        return JSONResponse({"error": "unknown scenario"}, status_code=404)
    data = await _payload(request)
    set_scenario(scenario, bool(data.get("enabled")))
    return drift_panel(request) if _htmx(request) else JSONResponse({"ok": True})


@admin_router.post("/{scenario}/enable")
def admin_enable(scenario: str) -> JSONResponse:
    if scenario not in SCENARIOS:
        return JSONResponse({"error": "unknown scenario"}, status_code=404)
    set_scenario(scenario, True)
    return JSONResponse({"scenario": scenario, "enabled": True})


@admin_router.post("/{scenario}/disable")
def admin_disable(scenario: str) -> JSONResponse:
    if scenario not in SCENARIOS:
        return JSONResponse({"error": "unknown scenario"}, status_code=404)
    set_scenario(scenario, False)
    return JSONResponse({"scenario": scenario, "enabled": False})


@admin_router.post("/incidents/{incident_id}/resolve")
def admin_resolve(incident_id: int) -> JSONResponse:
    ok = resolve(incident_id)
    return JSONResponse({"resolved": ok}, status_code=200 if ok else 404)


# --- Feedback (P1) -----------------------------------------------------------------------------


def _feedback_list(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_feedback_list.html",
        {"items": list_feedback(), "statuses": STATUSES, "dispositions": DISPOSITIONS},
    )


@router.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request) -> HTMLResponse:
    return page(
        request,
        "feedback.html",
        "feedback",
        items=list_feedback(),
        statuses=STATUSES,
        dispositions=DISPOSITIONS,
    )


@router.get("/api/feedback")
def api_feedback_list() -> JSONResponse:
    return JSONResponse(list_feedback())


@router.post("/api/feedback", response_model=None)
async def api_feedback(request: Request) -> Response:
    data = await _payload(request)
    try:
        feedback_id = create_feedback(
            int(data.get("run_id", 0)),
            str(data.get("rating", "")),
            str(data.get("reason") or "") or None,
            str(data.get("text") or ""),
        )
    except (FeedbackError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    if _htmx(request):
        return HTMLResponse(
            f'<p data-testid="feedback-thanks" class="muted">Thanks. Logged as feedback '
            f"#{feedback_id}.</p>"
        )
    return JSONResponse({"id": feedback_id})


@router.post("/api/feedback/{feedback_id}", response_model=None)
async def api_feedback_update(request: Request, feedback_id: int) -> Response:
    data = await _payload(request)
    try:
        update_feedback(
            feedback_id, str(data.get("status", "")), str(data.get("disposition") or "") or None
        )
    except FeedbackError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    return _feedback_list(request) if _htmx(request) else JSONResponse({"ok": True})


@router.post("/api/feedback/{feedback_id}/convert", response_model=None)
def api_feedback_convert(request: Request, feedback_id: int) -> Response:
    try:
        case_id, path = convert_to_case(feedback_id)
    except FeedbackError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    if _htmx(request):
        return HTMLResponse(
            f'<span data-testid="feedback-convert-result">Wrote eval case {case_id} '
            f"({path.name})</span>"
        )
    return JSONResponse({"case_id": case_id, "path": str(path)})
