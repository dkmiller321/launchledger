# KIT_FEEDBACK.md — self-improvement log

A running log of problems hit while building from this kit (`CLAUDE.md`, `KICKOFF.md`, `docs/PRD.md`, `docs/E2E_TESTS.md`, `.env.example`). Each entry records what happened, what it cost, and a concrete change for the next kit. Add entries as they happen, under a dated heading per stage. Also record what worked well and should be kept.

Kit: `idea-to-build-kit` v1.1.0 · Project: LaunchLedger

Tags: **[env]** machine/setup · **[contract]** E2E_TESTS.md · **[prd]** PRD gaps · **[process]** CLAUDE.md/KICKOFF workflow · **[stack]** library/version surprises · **[agent]** your own mistakes

Entry format:

```
N. **[tag] One-line summary.** What happened.
   - *Cost:* time, failed runs, questions to the user.
   - *Kit change:* the specific edit that would have prevented it.
```

## Log

### 2026-10-02 · Kickoff and stages 0-5

1. **[env] `localhost` costs 10 s per Postgres connection on Windows.** It tries IPv6 (::1) first, and Docker publishes on 127.0.0.1 only. The first `alembic upgrade` looked hung.
   - *Cost:* ~10 minutes diagnosing a "hang", one timed-out command.
   - *Kit change:* use `127.0.0.1` in every URL in `.env.example`, the e2e conftest default and CLAUDE.md.

2. **[stack] psycopg async does not run on Windows' default event loop**, but CLAUDE.md mandated "async end to end" with psycopg 3. Built with sync SQLAlchemy in FastAPI's threadpool instead (DECISIONS D3).
   - *Cost:* a design decision before the first line of DB code; a CLAUDE.md edit.
   - *Kit change:* for Python kits on Windows, say "sync SQLAlchemy + threadpool" (or pre-approve `asyncpg`) and drop the async rule.

3. **[agent] A half-finished first `alembic upgrade` left an empty `public.alembic_version`, and autogenerate then wrote `op.drop_table('alembic_version')` into the initial migration.** Every later upgrade failed with "relation alembic_version does not exist".
   - *Cost:* ~15 minutes of SQL tracing.
   - *Kit change:* tell the builder to give the Alembic `env.py` an `include_name` filter (own schemas only, skip `alembic_version`) before the first autogenerate.

4. **[contract] The golden-case contract needed pinned records the kit did not list.** Cases -02..-05 needed a second supplier with POs, a late-by-due-date PO, another serial and NCR (DECISIONS D7).
   - *Cost:* small; decided and documented without asking.
   - *Kit change:* pin 2-3 extra records per workflow in E2E_TESTS §1.4, or say explicitly that adding pinned records is expected.

5. **[contract] `erp_cost_in_cents` and the contract ranges interact.** If the inline range for `unit_cost_usd` is realistic, the x100 change trips the inline check first and E2E-23's "silent, then caught by the monitor" path never happens.
   - *Cost:* caught in design; range set deliberately loose (DECISIONS D6).
   - *Kit change:* state the intended range in PRD D1/D5 so builders don't tighten it.

6. **[process] Worked well, keep:** writing all 35 specs in a parallel fork during stage 0 from the testid contract meant stages 0-5 passed 24/24 E2E on the first full run; the exact decision-reason templates removed all ambiguity; the single generator for mock scripts + golden cases kept facts in sync.
   - *Kit change:* keep the parallel spec-writing guidance and the reason-template table.

7. **[env] Unicode separators in CLI output print as mojibake in the Windows console (cp1252).**
   - *Cost:* one rerun.
   - *Kit change:* tell builders to keep CLI output ASCII.

8. **[contract] The e2e `live_server` fixture leaked servers on Windows.** It launched `uv run uvicorn`; terminating it left the real uvicorn alive on :8001, and later sessions passed `/healthz` against the stale process and tested old code.
   - *Cost:* stages 2-5 results had to be re-run; ~10 minutes to find the orphan.
   - *Kit change:* in E2E_TESTS §1.2, say "launch uvicorn with the venv's python, kill the process tree on teardown, and fail if the port is already in use".

9. **[process] The walkthrough dev server and the pytest server share one test database.** Running both at once let a pytest reset wipe data mid-walkthrough.
   - *Cost:* one failed walkthrough and a rerun.
   - *Kit change:* give walkthroughs their own database (e.g. `launchledger_walk`) or state "never run them concurrently".

## Sending this log to KitForge (final acceptance step 7)

Send exactly one report. Each log entry becomes one `corrections` item (`text` = the entry with its tag, cost and kit change; `quote` = the user's own words if the user corrected you, else omit it). Use the final test totals.

```bash
curl -s -X POST http://127.0.0.1:4317/api/runs/report -H "content-type: application/json" -d @- <<'JSON'
{
  "kit": "idea-to-build-kit",
  "version": "1.1.0",
  "project_path": "<absolute path of this repo>",
  "outcome": "<success | partial | failed>",
  "corrections": [
    { "text": "<[tag] entry text, cost and kit change>" }
  ],
  "tests": { "passed": 0, "failed": 0 }
}
JSON
```

- `outcome`: `success` if every P0 scenario passes and final acceptance completed; `partial` if done with spec changes, skips or known issues; `failed` if abandoned.
- If the command fails (KitForge is not running), say so in one line and stop. Do not retry.
