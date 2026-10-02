# DECISIONS.md — choices made during the build

Claude Code appends one numbered entry per decision the docs left open: date, decision, why, and alternatives considered. This includes assumptions from the planning phase, installed package versions that differ from expectations, pinned records added for golden cases (with their IDs), the definitions chosen for P1 workflows such as shortage and cycle time, and any proposed spec change (marked **Proposed spec change**, with the scenario ID, never applied silently).

## Log

### D1 · 2026-10-02 · Repo-local git identity
`git config user.name` was unset. Set repo-locally to "Donald Miller" (from the user's Claude Docs profile) so stage commits work. Global git config untouched.

### D2 · 2026-10-02 · Database host is 127.0.0.1, not localhost
On this Windows machine `localhost` tries IPv6 first and each Postgres connection took ~10 s (Docker publishes on 127.0.0.1 only). All URLs in `.env.example`, `.env`, `e2e/conftest.py` use `127.0.0.1`.

### D3 · 2026-10-02 · Sync SQLAlchemy + psycopg instead of async (deviation from CLAUDE.md conventions)
psycopg's async mode cannot run on Windows' default Proactor event loop, which uvicorn uses. DB code is sync; FastAPI runs sync endpoints in its threadpool, and tool calls use a sync httpx client from those threads, so the app calling itself over HTTP cannot deadlock (each self-call is served by another pool thread). The few endpoints that read a request body are `async` and hand the work to `run_in_threadpool`. CLAUDE.md's "async end to end" line is updated to match. Alternative considered: `asyncpg` (not pre-approved).

### D4 · 2026-10-02 · Drift injection is applied in the system response layer
Instead of a body-rewriting ASGI middleware, every system endpoint serialises its records through `drift.scenarios.apply(...)` before returning. Same effect (the HTTP response is drifted for every consumer: tools, record viewer, monitor, G2 re-fetch), far simpler and testable as pure functions.

### D5 · 2026-10-02 · Drift UI routes
Scenario toggles post to `/api/admin/drift/{scenario}/set` (form field `enabled`), gated with the other admin routes. Incident resolve and "check now" are not demo-only, so they also live at `/api/drift/incidents/{id}/resolve` and `/api/drift/check` (ungated); the PRD's `/api/admin/drift/incidents/{id}/resolve` exists too.

### D6 · 2026-10-02 · Contract range for unit_cost_usd is deliberately loose (0.01–50,000,000)
So that `erp_cost_in_cents` (x100) passes the inline contract and is caught only by the distribution monitor, as E2E-23 requires ("silent" first). With a tight range the inline check would fire first and the monitor path would never be exercised.

### D7 · 2026-10-02 · Extra pinned records for golden cases -02..-05
Added below the reserved random ranges: `SN-0120` (P-2001, PLANNED, Bay 1 - Kitting), `WO-50410` (SN-0120, OPEN, depends on PO-10410), `NCR-0320` (SN-0057, MINOR, OPEN, REQ-118, "Flange surface pitting"), `PO-10300` (SUP-012, P-3300, due=promised 2026-10-15, OPEN), `PO-10410` (SUP-019, P-3300, due=promised 2026-09-20, OPEN, so late by due date). Random fill shrinks to keep the totals in §1.4.

### D8 · 2026-10-02 · One generator for mock scripts and golden cases
`scripts/build_fixtures.py` writes both `fixtures/llm-mock.json` and `evals/cases/*.yaml`, so a golden case's expected facts are exactly what its mock script cites. Scripts are matched longest trigger first so a short trigger (`open nonconformances`) never shadows a specific question. Mock evals therefore test the pipeline (tools, contracts, guardrails, grader); model quality is measured by real-model runs.

### D9 · 2026-10-02 · Decline reasons the contract does not define
LLM unreachable: `Declined: the model could not be reached ({detail}).` Tool refused before sending (not allowed / missing argument): `Declined: tool {name} failed ({detail}).` More than 8 tool calls: `Declined: the assistant needed more than 8 tool calls.`

### D10 · 2026-10-02 · G3 includes REQ-\d{3} from the start
Harmless before stage 7 (REQ records exist in the seed) and avoids a behaviour change mid-build.

### D11 · 2026-10-02 · The CLI runs the systems in-process
`ll` uses Starlette's `TestClient` against the app unless `--systems-url` is given, so `ll eval run` needs no running server (CI, Docker entrypoint). It ignores `SYSTEMS_BASE_URL` from `.env` by default.

### D12 · 2026-10-02 · Spec-writer resolutions (E2E specs written in parallel in stage 0)
Contract steps expose `contract: "pass"|"fail"` and `endpoint`; `/runs/{id}` renders the answer card too; the eval detail block carries `data-eval-id`; dashboard keys `latest` and `total`; `feedback-submit` disabled until a reason is chosen; `ll eval run --json-out`; CLI prints tokens and cost.

### D13 · 2026-10-02 · Installed versions
Python 3.12.11, uv 0.7.14, FastAPI/Starlette current minors, uvicorn 0.54, SQLAlchemy 2.x, psycopg 3, htmx 2.0.4 (vendored). Starlette warns that using `httpx` with its TestClient is deprecated in favour of `httpx2`; harmless, left as is.
