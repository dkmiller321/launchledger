# CLAUDE.md — LaunchLedger

Read these first, in order:

1. `docs/PRD.md`: what we are building and why. It is the source of truth for scope.
2. `docs/E2E_TESTS.md`: the acceptance contract. A feature exists when its scenarios pass.
3. This file: how to work.

If this file and the PRD disagree, the PRD wins. If the PRD and E2E_TESTS.md disagree, stop and ask.

## Stack (fixed)

| Layer | Choice |
|---|---|
| Runtime | Python 3.12 via `uv` (`uv python install 3.12`); `pyproject.toml` + `uv.lock` committed |
| Web | FastAPI, Uvicorn, Jinja2 templates, htmx 2.x **vendored** at `launchledger/web/static/htmx.min.js`, one hand-written `app.css`. No CDN, no JS build. |
| Data | Postgres 16, SQLAlchemy 2 (async, `psycopg` 3 driver), Alembic migrations |
| Validation / config | pydantic v2, pydantic-settings |
| HTTP | httpx (async) for system APIs and OpenRouter (OpenAI-compatible chat completions; no SDK) |
| CLI | Typer, console script `ll` |
| Data files | PyYAML (golden cases), `tomllib` (stdlib) for `config/*.toml` |
| Tests | pytest, pytest-asyncio, pytest-playwright (Chromium) |
| Lint / types | ruff (lint + format), mypy (`strict = true` for `launchledger/`) |
| Runtime | Docker Compose: `app` + `postgres` |
| CI | GitHub Actions, Postgres 16 service container |

Pre-approved packages (major versions pinned; take the newest minor): `fastapi`, `uvicorn[standard]`, `jinja2>=3`, `sqlalchemy>=2,<3`, `alembic>=1`, `psycopg[binary]>=3`, `pydantic>=2,<3`, `pydantic-settings>=2,<3`, `httpx`, `typer`, `pyyaml`, `python-multipart`; dev: `pytest>=8`, `pytest-asyncio`, `pytest-playwright`, `ruff`, `mypy`, `types-PyYAML`. **Ask before adding any other runtime dependency.** If an installed version's API differs from what you expect, read its installed source or docs rather than guessing, and note the version in `docs/DECISIONS.md`.

## Hard rules

- **Tests first.** Write every E2E scenario in `docs/E2E_TESTS.md` as a pytest-playwright test in stage 0, before the features exist. Specs may fail; they may never be weakened later to pass. If a scenario is wrong, say so and propose the change in `docs/DECISIONS.md`. Never silently edit an assertion, a testid, an expected string or a mock script's output.
- **Nothing is done until it has run.** For every claim that something works, state the command you ran and what you observed.
- **Mock LLM for tests.** With `LLM_MODE=mock`, the app uses the scripted `MockProvider` (E2E_TESTS.md §1.6). No test except `@smoke` may call OpenRouter. CI never has an API key.
- **Only the LLM is faked.** Mock tool calls go through the real tool layer, real HTTP to the system APIs, real contracts and real guardrails. Never shortcut a test by reading the DB inside the assistant.
- **The assistant never reads Postgres.** Tools call `/systems/...` over HTTP only (PRD A3).
- **The model never sees an unchecked tool response** (PRD §6 rules). Contract check and incident gate sit between the HTTP call and the model context.
- **Declined beats Answered.** Any contract violation, tool error or open gated incident in a run forces Declined, whatever the model wrote.
- **Selectors are a contract.** Use the `data-testid` values and attributes in E2E_TESTS.md §1.9 exactly.
- **Decision reasons are a contract.** Use the templates in E2E_TESTS.md §1.7 exactly.
- **Golden values come from the seed.** Never hand-type an expected value without the IT-06 check covering it.
- **Licences:** recreate functionality only; copy no code from promptfoo, Langfuse (never open its `ee/`), Great Expectations or Guardrails AI.
- **Non-goals stay out:** auth, multi-tenancy, RAG/embeddings, multi-turn memory, LLM-judge grading, SPA frameworks, cloud deploys.
- **No TODOs or stubs** in committed code. Implement it, or record it as out of scope in `docs/DECISIONS.md`.
- **Secrets stay server-side.** `OPENROUTER_API_KEY` is never logged, rendered, or stored in a trace.
- **Test and admin routes are gated.** `/api/test/*` → 404 unless `TEST_MODE=1`; `/api/admin/drift/*` → 404 unless `DRIFT_INJECTION=1`.

## Conventions

- Layout:
  ```
  launchledger/
    main.py            # FastAPI app factory, lifespan (drift monitor task), mounts /systems/*
    settings.py        # the ONLY place env is read (pydantic-settings), fail fast with the var name
    clock.py           # injected clock; FROZEN_TODAY support
    db/                # engine, models per schema (plm, mes, erp, req, dw, app), alembic/
    systems/           # one sub-app per system: plm.py, mes.py, erp.py (+ req.py, dw.py), seed.py
    contracts/         # pydantic response contracts + value expectations per endpoint, baseline, monitor
    drift/             # injector middleware + scenario registry
    llm/               # provider.py (interface), openrouter.py, mock.py
    assistant/         # router.py, workflows.py (prompts + allowed tools), tools.py, runner.py, schema.py (claims/facts)
    guardrails/        # registry.py + one module per rule, pure functions
    evals/             # loader, grader (pure), runner, report
    feedback/  dashboard/
    web/               # routes, templates/, static/
    cli.py             # Typer app `ll`
  config/models.toml  config/evals.toml
  evals/cases/*.yaml   fixtures/llm-mock.json
  tests/ (unit + integration)   e2e/ (pytest-playwright)   scripts/
  ```
- Core logic is pure and unit-tested in isolation: guardrails, grader, contract checks, drift transforms, late-PO rule, distribution comparison. Routes and CLI only wire them up.
- Async end to end on the request path. **Never call the system APIs with a sync client from inside a request**: the app calls itself over HTTP, and a sync call deadlocks a single worker. The CLI uses `httpx.ASGITransport` against the app unless `SYSTEMS_BASE_URL` is set.
- Errors: let exceptions propagate to one handler at the edge. The run loop is the exception: it catches tool/LLM failures and turns them into a Declined decision with the error in the trace. No retry decorators or circuit breakers beyond PRD §5 (one LLM retry on 5xx/429).
- Logging: stdlib `logging`, module-level loggers.
- In Docker the app binds `0.0.0.0:8000` inside the container and Compose publishes `127.0.0.1:8000:8000`. Postgres publishes on host port `55432`.
- Commit after each stage: `stage N: <summary>`. A stage's commit may contain shared UI code that a later stage verifies; say so in the commit body.

## Workflow

Work through PRD → Milestones (stages 0–9) in order, **without waiting for confirmation between stages** unless you are blocked.

For each stage:

1. Implement the stage.
2. `uv run ruff check . && uv run ruff format --check . && uv run mypy launchledger && uv run pytest tests` (unit + integration for this and earlier stages; E2E_TESTS.md §5).
3. `uv run pytest e2e -m "stage0 or … or stageN"`: this stage's scenarios **and every earlier stage's** must pass. Run it **twice in a row**; any flake is a bug to fix now.
4. From stage 4: `uv run ll eval run --model mock` passes. From stage 5: each P0 drift-mode eval passes.
5. **Walk the stage with the `playwright-headless` MCP server** (E2E_TESTS.md §4): reset, drive each of this stage's scenarios via testids, snapshot, check the same outcomes, and chain them the way a user would. From stage 5 on, also walk E2E-21 every time.
6. Append to `docs/VERIFICATION.md`: stage, commands with pass/fail counts, each walked scenario `E2E-xx: pass | fail — note`, anything surprising.
7. Append to `KIT_FEEDBACK.md` anything the kit got wrong or left out (format in that file). Do this as it happens, not at the end.
8. Commit.

Stop and ask when:

- a change would alter the PRD's scope, a test assertion, a testid, a decision-reason template or a mock script's output,
- a dependency outside the approved list seems necessary,
- the same failure survives three genuine fix attempts,
- a PRD rule and a scenario can't both be satisfied.

Otherwise decide, record the decision in `docs/DECISIONS.md` (date, decision, why, alternatives), and keep going.

## Final acceptance

1. `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build` (the test override sets `TEST_MODE=1`, `DRIFT_INJECTION=1`, `LLM_MODE=mock`, `FROZEN_TODAY=2026-10-01`, `MOCK_LATENCY_MS=150`, `SYSTEMS_BASE_URL=http://127.0.0.1:8000`); wait for `GET http://127.0.0.1:8000/healthz` → 200.
2. `BASE_URL=http://127.0.0.1:8000 uv run pytest e2e -m "not smoke"`: all pass. Run it three times; record any flaky spec (target 0).
3. Inside the container: `docker compose exec app ll eval run --model mock` and each drift-mode eval pass.
4. Walk every P0 scenario (stages 0–5) through `playwright-headless` against the container, E2E-21 last.
5. If `OPENROUTER_API_KEY`, `ROUTER_MODEL` and `WORKFLOW_MODEL` are set: start a dev server with `LLM_MODE=openrouter` and run `RUN_SMOKE=1 uv run pytest e2e -m smoke`. Report real-model eval numbers if you ran them.
6. Write the final summary in `docs/VERIFICATION.md`: totals, skipped tests and why, known issues, and the exact commands to run LaunchLedger for real (without the test override) and to run the 2-minute demo in `docs/DEMO.md`.
7. **Report to KitForge.** Send `KIT_FEEDBACK.md` as one report (the command is in that file). If KitForge isn't running, say so in one line and stop; don't retry.
