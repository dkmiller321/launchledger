# VERIFICATION.md — what was run, and what was seen

Claude Code appends one section per stage: the stage number, every command run with its pass/fail counts (lint, types, unit/integration, E2E twice, evals, drift-mode evals), each scenario walked through the `playwright-headless` MCP server as `E2E-xx: pass | fail — note`, and anything surprising. Final acceptance adds a summary: totals, flaky specs (target 0), skipped tests and why, known issues, and the commands to run the app and the demo.

## Log

### Stages 0-6 · 2026-10-02

Stages 0-6 were implemented together after the parallel spec-writing in stage 0, then gated stage by stage. A harness bug was found and fixed mid-way (see "Harness fix" below); every number here is from runs after that fix.

| Check | Command | Result |
|---|---|---|
| Lint | `uv run ruff check . && uv run ruff format --check .` | clean |
| Types | `uv run mypy` | no issues, 46 files |
| Unit + integration (IT-01..IT-09, IT-11) | `uv run pytest tests` | 31 passed |
| Spec collection | `uv run pytest e2e --collect-only -q` | 35 collected |
| E2E stages 0-6, run 1 | `uv run pytest e2e -m "stage0 or ... or stage6"` | 27 passed |
| E2E stages 0-6, run 2 (no retries) | same | 27 passed, 0 flaky |
| Mock eval suite | `uv run ll eval run --model mock` | 30/30, exit 0 |
| Drift eval: erp_rename_promised_date | `ll eval run --model mock --drift ...` | 23 correct, 7 declined, 0 wrong, exit 0 |
| Drift eval: mes_new_wo_status | same | 15 correct, 15 declined, 0 wrong, exit 0 |
| Drift eval: erp_cost_in_cents | same | 23 correct, 7 declined, 0 wrong, exit 0 |
| Docker image builds and boots | `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build app` | migrate, seed, baseline, `/healthz` 200 |

**playwright-headless walkthrough** (`scripts/walkthrough/p0.js`, chained: ask, citation, back, trace, manual override, blocks, evals, drift, monitor):

- E2E-00: pass — healthz `{"status":"ok","db":true,"llm_mode":"mock"}`
- E2E-01: pass — record viewer SN-0042 IN_BUILD
- E2E-04: pass — Answered, 6 citations, chip serial_status; citation opens WO-50102 BLOCKED
- E2E-05: pass — 4 llm steps, 2 tool steps
- E2E-06: pass — `po_status (manual)`
- E2E-09: pass — `Declined: no workflow matches this question.`
- E2E-12: pass — `Blocked by guardrail: ids_exist (SN-9999 not found in MES).`
- E2E-13: pass — `facts_match_source (mes/serial/SN-0042.status is IN_BUILD, answer says SHIPPED)`
- E2E-14: pass — `citation_required`
- E2E-15: pass — `export_control`; page never shows 11.5
- E2E-16: pass — caveated answer for SN-0404
- E2E-17: pass — repaired output answered
- E2E-18: pass — mock suite 30/30 from the UI
- **E2E-21: pass** — Answered → toggle rename → `Declined: upstream data from ERP failed its contract (/purchase_orders: promised_date missing; unexpected field promise_date).` → ERP red, incident runs affected 1 → drift eval wrong 0, declined 7 → untoggle + resolve → Answered
- E2E-23: pass — silent Answered → check now → 1 distribution incident → `Declined: open drift incident on ERP unit_cost_usd (distribution).`
- Stage 6 (E2E-24..26) walked by pytest only so far; added to the final walkthrough.

**Harness fix.** The `live_server` fixture started uvicorn through `uv run`; on Windows, terminating `uv run` leaves the child uvicorn alive, so later sessions silently tested an old server on :8001 (found when the new feedback routes returned 404). The fixture now runs uvicorn with the venv interpreter, kills the process tree on teardown, and refuses to start if :8001 is taken. Stages 0-6 were all re-run after the fix (numbers above). Also: the dev server for walkthroughs and the pytest server share `launchledger_test`, so never run them at the same time (one walkthrough attempt failed because a pytest run reset the DB under it).

### Stages 7-8 · 2026-10-02

| Check | Command | Result |
|---|---|---|
| Fixtures | `uv run python scripts/build_fixtures.py` | 67 mock scripts, 60 golden cases |
| Lint / types | ruff, `uv run mypy` | clean, 49 files |
| Unit + integration (adds IT-10, P1 drift evals) | `uv run pytest tests` | 34 passed |
| Mock eval suite | `uv run ll eval run --model mock` | 60/60, 12 workflows at 5/5 |
| E2E all stages, run 1 | `uv run pytest e2e -m "not smoke"` | 31 passed |
| E2E all stages, run 2 | same | 31 passed, 0 flaky |

**Spec conflict found and resolved with the user (DECISIONS D15).** After stage 7, E2E-18/19/26 (`30/30`) and E2E-29 (`60/60`) could not both hold. The user chose "assert full pass, any size": the three specs now read N from the eval run and assert `N/N` / `(N-1)/N`.

**playwright-headless walkthrough** (`scripts/walkthrough/p1.js`, chained: ask, thumbs-down, triage x3, reload, convert, evals, P1 questions, dashboard):

- E2E-24: pass — submit disabled until a reason; item New with "Wrong data"
- E2E-25: pass — Triaged → Fixed → Verified, 3 events survive reload
- E2E-26: pass — draft case passes inside a 60/60 run
- E2E-27: pass — all six P1 workflows Answered with the right chip
- E2E-30: pass — decision mix 14/4/2, latest eval 30/30, 2 incidents; screenshot reviewed (bar colours and week labels tidied afterwards)

Dev-server note: `uvicorn --reload` launched through `uv run` stopped reloading after pytest-playwright cleared `test-results/` (which held its log). The walkthrough server now runs without reload from the venv interpreter, logging to `logs/`, and is restarted after code changes.
