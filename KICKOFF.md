# KICKOFF.md — paste the prompt below into Claude Code

Before you start: this folder should contain `CLAUDE.md`, `KICKOFF.md`, `KIT_FEEDBACK.md`, `.env.example` and `docs/`. Run `cp .env.example .env` (mock mode needs no key). Start Docker Desktop. Start Claude Code in this folder and run `/mcp` to confirm the `playwright-headless` server is connected.

---

```
You are building LaunchLedger from a folder that holds only its build kit.

Read, in order: docs/PRD.md, docs/E2E_TESTS.md, CLAUDE.md. Follow CLAUDE.md's rules
for the whole build.

Phase 0: Preflight (fix what you can, ask only if blocked)
- Check: `docker ps` works; this folder is a git repo (if not, `git init` and make
  the kit files the first commit); `git config user.name` is set; `.env` exists
  (else copy .env.example); `uv --version` works and `uv python install 3.12`
  succeeds; ports 8000, 8001 and 55432 are free.
- Save these checks as scripts/preflight.sh so they can be re-run.

Phase 1: Plan (then continue without waiting)
- Summarise the build in under 20 lines: stages, the mock-model design, how the
  contract layer sits between tools and the model, and how you will verify each
  stage with pytest-playwright and the `playwright-headless` MCP server.
- List contradictions or gaps in the docs. If any block you, stop and ask.
  Otherwise record your assumptions in docs/DECISIONS.md and continue.

Phase 2: Tests first (stage 0)
- Scaffold stage 0: uv project, FastAPI app with /healthz, settings with fail-fast
  validation, Postgres in docker-compose.yml (+ docker-compose.test.yml), Alembic,
  base layout with the six nav links, /api/test/reset, MockProvider loading
  fixtures/llm-mock.json with scripts M1–M14, the e2e/ harness (live_server
  fixture, ask() helper, markers), and .github/workflows/ci.yml.
- Write EVERY scenario in docs/E2E_TESTS.md as a test in e2e/, tagged by stage,
  plus the smoke tests, using the testid contract exactly. Write the §5 checks
  that belong to stage 0.
- `uv run pytest e2e --collect-only -q` must list them all. Then run the stage-0
  gate; E2E-00, IT-01, IT-02 and IT-11 must pass. Run the rest once with
  PW_TIMEOUT_MS=2000 just to confirm they fail fast and cleanly.
- Build and boot the Docker image now (`docker compose up -d --build`, then
  /healthz) so missing dependencies surface in stage 0, not at the end.
- Confirm the `playwright-headless` MCP server works: navigate to the running app
  and take a snapshot. Record results in docs/VERIFICATION.md. Commit.

Phase 3: Build stages 1–9
- For each stage follow the Workflow in CLAUDE.md: implement, lint/types/unit,
  that stage's and all earlier stages' E2E tests green twice, evals where
  applicable, a `playwright-headless` walkthrough (chained, E2E-21 every time
  from stage 5), VERIFICATION.md, KIT_FEEDBACK.md, commit.
- Stage 5 is the core promise. Do not start stage 6 until E2E-21 passes in both
  pytest and the MCP walkthrough.
- Never weaken an assertion to make it pass. Propose spec changes instead.

Phase 4: Final acceptance
- Run the Final acceptance steps in CLAUDE.md against the Docker Compose stack,
  including the KitForge report.
- Finish with a short report: pass/fail totals, anything skipped and why, known
  issues, and the exact commands I need to run the app and the 2-minute demo.
```

---

## Useful follow-up prompts

- **Resume after a break:** `Read CLAUDE.md, docs/VERIFICATION.md and docs/DECISIONS.md, find the last completed stage, and continue from the next one.`
- **Re-verify the core promise:** `Reset the DB and walk E2E-21 and E2E-23 through the playwright-headless MCP server; report each step and screenshot the /drift page.`
- **Real model:** `Set LLM_MODE=openrouter, start the server, run RUN_SMOKE=1 uv run pytest e2e -m smoke, then uv run ll eval run --model "$WORKFLOW_MODEL" and report pass rate per workflow, latency and cost.`
- **Compare models (stage 9):** `Run uv run ll eval compare "$WORKFLOW_MODEL" "$COMPARE_MODEL" and summarise the report in three bullets.`
- **Demo prep:** `Reset, run ll demo seed-activity, then walk docs/DEMO.md end to end through playwright-headless and fix anything that doesn't match the script.`
