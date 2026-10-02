# DEMO.md — the 2-minute demo

The story: an upstream team silently renames a field, and LaunchLedger refuses to answer instead of answering wrong, opens an incident, and the eval suite proves it.

**Setup (before you start recording):** `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build`, open `http://127.0.0.1:8000`, then reset once: `curl -X POST http://127.0.0.1:8000/api/test/reset`.

| Time | Do | Say |
|---|---|---|
| 0:00 | Ask page. Click the example **Where is SN-0042 and what's blocking it?** | "An engineer asks about a turbopump in build. The assistant reads three fake enterprise systems over their APIs." |
| 0:15 | Point at the **Answered** badge, the claims and the citation links. Click **WO-50102 · status**. | "Every claim cites the exact record and field. One click and you're looking at the source." |
| 0:30 | Back. Click **View trace**. | "Every run is traced: the router, each tool call, the contract check on every response, and five guardrails." |
| 0:45 | Ask **Which open work orders are at risk from late POs from Apex Castings?** → Answered. | "Here's a supply-chain question. It works." |
| 0:55 | Go to **Drift**, tick **erp_rename_promised_date**. | "Now ERP silently renames `promised_date`. Nothing errors upstream." |
| 1:05 | Ask the Apex Castings question again. | "Instead of guessing, it declines and says exactly why: ERP failed its contract on `promised_date`." |
| 1:15 | Back to **Drift**: ERP is red, one incident, one run affected. | "An incident opens automatically, so the platform team knows which upstream change to chase." |
| 1:25 | **Evals**, choose the same scenario, **Run mock suite**. | "And the regression suite proves it across all 60 golden cases: zero wrong answers, every affected question declined." |
| 1:45 | Untick the scenario, **Resolve** the incident, ask again → Answered. | "Fix upstream, resolve, and it answers again." |
| 1:55 | **Dashboard**. | "Leadership sees backlog flow, eval pass rate and drift incidents week over week." |

**If something looks off:** reset with `POST /api/test/reset` and start again. For the dashboard to show a month of history, run `docker compose exec app ll demo seed-activity` first (it replaces app data).
