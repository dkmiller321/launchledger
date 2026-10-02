# LaunchLedger

An AI assistant over a fictional rocket manufacturer's enterprise systems (PLM, MES, ERP, requirements, data warehouse), wrapped in the sustaining-engineering layer that keeps it trustworthy.

**The core promise:** when upstream data changes silently, the assistant declines instead of answering confidently wrong, opens a drift incident naming the system and field, and the eval suite proves it.

- **Grounded answers.** Tool-calling workflows read the systems only over their REST APIs. Every claim cites the record and field it came from.
- **Contracts on every response.** Each tool response is validated against its system's contract before the model sees it. An open drift incident gates any response carrying that field.
- **Guardrails.** Five machine-checkable rules run on every answer: citations required, facts re-checked against the source, IDs must exist, export-controlled data never leaks, uncertainty must be stated.
- **Regression evals in CI.** 60 golden cases, graded deterministically, plus drift-mode evals that must produce zero wrong answers.
- **Drift monitor.** Batch checks of schema and value distributions catch silent unit changes.
- **Feedback triage and a leadership dashboard.** Thumbs-down reports flow through New → Triaged → Fixed → Verified and can become eval cases.

## Run it

```bash
cp .env.example .env
docker compose up -d --build        # app on http://127.0.0.1:8000, mock model, no API key needed
```

Demo mode with drift injection and test routes: `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build`. The 2-minute walkthrough is in [docs/DEMO.md](docs/DEMO.md).

Real models: set `LLM_MODE=openrouter`, `OPENROUTER_API_KEY`, `WORKFLOW_MODEL` and `ROUTER_MODEL` in `.env`.

## Develop

```bash
uv sync
docker compose up -d postgres
uv run alembic upgrade head && uv run ll seed && uv run ll drift baseline
uv run uvicorn launchledger.main:app --reload
```

| Check | Command |
|---|---|
| Lint, types | `uv run ruff check . && uv run mypy` |
| Unit + integration | `uv run pytest tests` |
| E2E (Playwright) | `uv run playwright install chromium && uv run pytest e2e -m "not smoke"` |
| Eval gate | `uv run ll eval run --model mock` |
| Drift gate | `uv run ll eval run --model mock --drift erp_rename_promised_date` |
| Model comparison | `uv run ll eval compare <slugA> <slugB>` |
| Weekly report | `uv run ll report weekly` |

Docs: [PRD](docs/PRD.md) · [acceptance contract](docs/E2E_TESTS.md) · [runbook](docs/RUNBOOK.md) · [decisions](docs/DECISIONS.md) · [verification log](docs/VERIFICATION.md).

All data is synthetic. Halcyon Aerospace is fictional.
