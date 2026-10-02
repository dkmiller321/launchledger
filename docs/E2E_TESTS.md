# E2E_TESTS.md — Acceptance contract

Every scenario below becomes a pytest-playwright test in `e2e/` **before** the feature is built (stage 0). A stage is done when its scenarios, and every earlier stage's scenarios, pass. After that you walk them again through the `playwright-headless` MCP server.

**The most important test in the suite is E2E-21** (drift → Declined, never wrong). It proves the product's core promise. If time runs short, everything else gives way to it.

## 1. Test harness

### 1.1 Running

| Command | What it does |
|---|---|
| `uv run pytest e2e -m "not smoke"` | All E2E scenarios except `@smoke`. The `live_server` fixture starts the app (see 1.2) unless `BASE_URL` is set. |
| `uv run pytest e2e -m stage3` | One stage's scenarios. |
| `uv run pytest e2e -m "stage0 or stage1 or stage2"` | Cumulative run through stage 2 (what each stage gate uses). |
| `BASE_URL=http://127.0.0.1:8000 uv run pytest e2e -m "not smoke"` | Against an already-running app, such as the Docker Compose stack with the test override. |
| `RUN_SMOKE=1 uv run pytest e2e -m smoke` | Real-model smoke suite. Needs `OPENROUTER_API_KEY`, `ROUTER_MODEL`, `WORKFLOW_MODEL`, and a server started with `LLM_MODE=openrouter`. |
| `uv run pytest e2e --collect-only -q` | Proves every spec imports and is collected (stage 0 check). |
| `uv run pytest tests` | Unit + integration (section 5). |

Conventions:

- One file per stage: `e2e/test_stage0.py` … `e2e/test_stage8.py`, plus `e2e/test_smoke.py`.
- Test function names start with the scenario ID: `test_e2e_21_drift_rename_declines`. Each carries `@pytest.mark.stageN` (and `@pytest.mark.smoke` for smoke). Register markers in `pyproject.toml` with `--strict-markers`.
- Chromium only, headless, **no parallelism** (the tests share one database), `--tracing retain-on-failure`, `--output test-results/`.
- Default Playwright timeout 10 s; `expect` timeout 10 s; eval runs may wait up to 90 s.
- In stage 0 only, run the not-yet-implemented specs with `--timeout`-style fast failure: set `PW_TIMEOUT_MS=2000` so the baseline run takes seconds, not minutes.
- **Run the cumulative suite twice in a row with no retries before every stage commit.** Any flake is a bug.

### 1.2 Server under test

The session-scoped `live_server` fixture (in `e2e/conftest.py`):

1. Uses `TEST_DATABASE_URL` (a separate `launchledger_test` database; never the dev database).
2. Runs `alembic upgrade head` against it.
3. Starts `uvicorn launchledger.main:app --host 127.0.0.1 --port 8001` as a subprocess with:
   `LLM_MODE=mock`, `TEST_MODE=1`, `DRIFT_INJECTION=1`, `FROZEN_TODAY=2026-10-01`, `MOCK_LATENCY_MS=150`, `DRIFT_MONITOR_INTERVAL_S=0` (scheduler off; checks only on demand), `SYSTEMS_BASE_URL=http://127.0.0.1:8001`, `EVAL_DRAFTS_DIR=<tmp dir>`.
4. Waits for `GET /healthz` → 200, yields the base URL, and kills the process at session end.

If `BASE_URL` is set, it skips all of that and uses the given URL.

### 1.3 Database reset

When `TEST_MODE=1`, the app exposes `POST /api/test/reset`. It:

- truncates every `app.*` table,
- disables every drift scenario,
- clears eval overrides (1.6) and empties `EVAL_DRAFTS_DIR`,
- re-seeds the system schemas (`ll seed` logic, seed 42),
- re-captures contract baselines (`ll drift baseline` logic),

and returns `{"ok": true}`. **The route returns 404 when `TEST_MODE` is not `1`.** An autouse fixture calls it before every test.

Other test-only routes (same 404 rule):

| Route | Effect |
|---|---|
| `GET /api/test/seed-hash` | `{"hash": "<sha256 over all system-schema rows ordered by PK>"}` |
| `POST /api/test/eval-overrides` | Body `{"case_id": "...", "expected_facts": [...]}` replaces that case's expected facts until the next reset. |
| `POST /api/test/seed-activity` | Same as `ll demo seed-activity` (section 2, stage 8). |

### 1.4 Seed: pinned demo records

`ll seed` inserts these records **exactly**, then fills the rest randomly (RNG seed 42) up to the totals below. Random records use the reserved ID ranges and **never reference pinned records** (no random PO to SUP-007, no random BOM line touching a pinned part, no random WO depending on a pinned PO).

Totals after seeding: parts 120, bom_lines 200, serials 300, work_orders 400, inspections 250, nonconformances 80, suppliers 25, purchase_orders 600.

Reserved random ID ranges: parts `P-4000`–`P-4999`, bom lines `BL-1000`+, serials `SN-1000`+, work orders `WO-60000`+, inspections `INS-8000`+, NCRs `NCR-1000`+, suppliers `SUP-100`+, POs `PO-20000`+. IDs below those ranges are for pinned records only; add more pinned records there as golden cases need them (section 3).

**PLM parts**

| part_number | name | revision | mass_kg | unit_cost_usd | export_controlled | controlled_notes |
|---|---|---|---|---|---|---|
| P-1077 | Turbopump inducer housing | C | 14.2 | 18450.00 | true | `Inducer blade angle 11.5 deg; CMM tolerance 0.02 mm` |
| P-2001 | LOX turbopump assembly | B | 96.5 | 412000.00 | true | `Shaft seal stack-up per HX-77` |
| P-2110 | Fuel turbopump assembly | B | 88.0 | 398000.00 | true | `Impeller balance grade G1.0` |
| P-1500 | Stage 2 tank dome | A | 212.5 | 96000.00 | false | null |
| P-3300 | Engine controller harness | D | 6.8 | 22300.00 | false | null |

**PLM BOM lines**: `BL-0001` P-2001 → P-1077 qty 1 · `BL-0002` P-2110 → P-1077 qty 1 · `BL-0003` P-2001 → P-3300 qty 1.

**MES serials**

| serial_number | part_number | revision | status | location |
|---|---|---|---|---|
| SN-0042 | P-2001 | B | IN_BUILD | Bay 3 - Engine Integration |
| SN-0057 | P-2110 | B | IN_BUILD | Bay 3 - Engine Integration |
| SN-0101 | P-1500 | A | COMPLETE | Stores - Building 2 |

**MES work orders**

| wo_id | serial_number | status | blocked_reason | depends_on_po | description |
|---|---|---|---|---|---|
| WO-50101 | SN-0042 | CLOSED | null | null | Machine housing interfaces |
| WO-50102 | SN-0042 | BLOCKED | Awaiting inducer housing castings | PO-10233 | Install inducer housing |
| WO-50103 | SN-0042 | OPEN | null | null | Final assembly and leak check |
| WO-50217 | SN-0057 | OPEN | null | PO-10233 | Install inducer housing |
| WO-50300 | SN-0101 | CLOSED | null | null | Dome weld and X-ray |

**MES inspections**: `INS-7001` SN-0042 PASS 2026-09-10 · `INS-7002` SN-0101 PASS 2026-08-21.

**MES nonconformances**

| ncr_id | serial_number | severity | status | requirement_id | description |
|---|---|---|---|---|---|
| NCR-0311 | SN-0042 | MAJOR | OPEN | REQ-118 | Porosity in casting flange |
| NCR-0298 | SN-0042 | MINOR | CLOSED | REQ-104 | Scratch on mounting face |

**ERP suppliers**: `SUP-007` Apex Castings · `SUP-012` Orbital Fasteners · `SUP-019` Cryo Valve Works.

**ERP purchase orders** (SUP-007 has exactly these three)

| po_id | supplier_id | part_number | qty | due_date | promised_date | status | unit_cost_usd |
|---|---|---|---|---|---|---|---|
| PO-10233 | SUP-007 | P-1077 | 4 | 2026-09-15 | 2026-10-20 | OPEN | 18450.00 |
| PO-10240 | SUP-007 | P-1077 | 2 | 2026-11-01 | 2026-11-01 | OPEN | 18450.00 |
| PO-10198 | SUP-007 | P-1077 | 2 | 2026-07-01 | 2026-07-01 | RECEIVED | 18100.00 |

"Late" = `status == OPEN` and (`promised_date > due_date` or `due_date < today`), with today from the injected clock (2026-10-01 in tests). PO-10233 is late; PO-10240 is not.

**P1 pinned records (stage 7):** `REQ-118` "Casting porosity limited to ASTM E505 level 2", verification `Inspection`, linked to P-1077 · `REQ-104` "Mounting face finish 63 Ra max", verification `Inspection`, linked to P-2001.

### 1.5 System API routes and record types

| Tool | HTTP | Record type in facts / viewer |
|---|---|---|
| `get_serial(serial_number)` | `GET /systems/mes/serials/{sn}` | `serial` |
| `list_work_orders(serial_number?, status?, depends_on_po?)` | `GET /systems/mes/work_orders` | `work_order` |
| `list_inspections(serial_number)` | `GET /systems/mes/inspections` | `inspection` |
| `list_ncrs(serial_number?, part_number?, status?)` | `GET /systems/mes/nonconformances` | `ncr` |
| `get_part(part_number)` | `GET /systems/plm/parts/{pn}` | `part` |
| `get_bom(part_number)` | `GET /systems/plm/parts/{pn}/bom` | `bom_line` |
| `where_used(part_number)` | `GET /systems/plm/parts/{pn}/where_used` | `bom_line` |
| `get_po(po_id)` | `GET /systems/erp/purchase_orders/{id}` | `purchase_order` |
| `list_pos(supplier_id?, part_number?, status?, late_only?)` | `GET /systems/erp/purchase_orders` | `purchase_order` |
| `get_supplier(supplier_id)` | `GET /systems/erp/suppliers/{id}` | `supplier` |
| `find_supplier(name)` | `GET /systems/erp/suppliers?name=` | `supplier` |

List endpoints return `{"items": [...], "total": n, "limit": l, "offset": o}`, `limit` default 50, max 200. A missing ID returns 404 `{"error": "not_found"}`. Fact `system` values are uppercase (`PLM`, `MES`, `ERP`, `REQ`, `DW`); URL segments are lowercase. Record viewer URL: `/records/{system}/{type}/{id}`, e.g. `/records/mes/work_order/WO-50102`.

Allowed tools per workflow (anything else returns a tool error):

| Workflow | Allowed tools |
|---|---|
| `serial_status` | get_serial, list_work_orders, get_part |
| `supplier_impact` | find_supplier, get_supplier, list_pos, list_work_orders |
| `where_used` | where_used, get_bom, get_part |
| `ncr_summary` | list_ncrs, get_serial, get_part |
| `po_status` | get_po, get_supplier, list_work_orders |
| `build_readiness` | get_serial, list_work_orders, list_inspections, list_ncrs |

### 1.6 The mock model

When `LLM_MODE=mock`, `launchledger/llm/mock.py` provides `MockProvider`, which implements the same `LlmProvider.chat(messages, tools, purpose)` interface as `OpenRouterProvider` and returns OpenAI-shaped assistant messages (with `tool_calls` or `content`). **Only the LLM is faked:** the scripted tool calls execute through the real tool layer, real HTTP to the real system APIs, the real contract checks and the real guardrails. Scripts live in `fixtures/llm-mock.json`. Each call sleeps `MOCK_LATENCY_MS` first (150 in E2E so the "running" state is observable; 0 in evals and CI).

In mock mode, runs record the model as `mock/router` and `mock/workflow`. The eval runner always uses `MOCK_LATENCY_MS=0`.

**Router calls** (`purpose="router"`): every script's trigger is also a router entry for the workflow shown in brackets in the table below. Lower-case the question and pick the first `router` entry whose trigger it contains; respond with a `select_workflow` tool call naming that workflow. No match → `select_workflow{"workflow": "unsupported"}`. When the user picked a workflow manually, the router is not called.

**Workflow calls** (`purpose="workflow"`): pick the first `workflows` script whose trigger the lower-cased question contains (independent of which workflow runs it). The step index is the number of assistant messages already in the conversation. A step is either `{"tool_calls": [...]}`, `{"final": {...}}` (sent as JSON `content`) or `{"raw": "..."}` (sent as plain `content`, used to test invalid output). No matching script → `{"raw": "Mock: no script for this prompt."}`. Running past the last step → the same raw text.

**Value matching (graders and G2):** compare JSON values after normalising numbers (`1 == 1.0`, `18450 == 18450.00`) and dates (ISO `YYYY-MM-DD` strings). Everything else is an exact string match.

Scripts (router workflow in brackets; final answers shown as `answer` plus facts written `SYSTEM type ID field = value`):

| Script | Trigger (contains) | Steps and exact output |
|---|---|---|
| M1 serial status [serial_status] | `where is sn-0042` | 1 `get_serial{serial_number:"SN-0042"}` · 2 `list_work_orders{serial_number:"SN-0042"}` · 3 final. answer: `SN-0042 is IN_BUILD at Bay 3 - Engine Integration. It is blocked by WO-50102 (Awaiting inducer housing castings), which depends on PO-10233. WO-50103 is still OPEN.` Claims: (a) `SN-0042 is in build at Bay 3.` facts MES serial SN-0042 status = IN_BUILD; MES serial SN-0042 location = Bay 3 - Engine Integration. (b) `WO-50102 is blocked waiting for castings on PO-10233.` facts MES work_order WO-50102 status = BLOCKED; blocked_reason = Awaiting inducer housing castings; depends_on_po = PO-10233. (c) `WO-50103 is open.` fact MES work_order WO-50103 status = OPEN. caveats `[]` |
| M2 supplier impact [supplier_impact] | `late pos from apex castings` | 1 `find_supplier{name:"Apex Castings"}` · 2 `list_pos{supplier_id:"SUP-007", status:"OPEN"}` · 3 `list_work_orders{depends_on_po:"PO-10233"}` · 4 final. answer: `Apex Castings has one late open PO: PO-10233, due 2026-09-15 but now promised 2026-10-20. Two work orders depend on it: WO-50102 (BLOCKED) and WO-50217 (OPEN). PO-10240 is on time.` Claims: (a) `PO-10233 from Apex Castings is late.` facts ERP supplier SUP-007 name = Apex Castings; ERP purchase_order PO-10233 status = OPEN; due_date = 2026-09-15; promised_date = 2026-10-20. (b) `WO-50102 and WO-50217 depend on PO-10233.` facts MES work_order WO-50102 depends_on_po = PO-10233; MES work_order WO-50217 depends_on_po = PO-10233. (c) `PO-10240 is on time.` facts ERP purchase_order PO-10240 due_date = 2026-11-01; promised_date = 2026-11-01. |
| M3 where used [where_used] | `which assemblies use part p-1077` | 1 `where_used{part_number:"P-1077"}` · 2 final. answer: `P-1077 is used in two assemblies: P-2001 and P-2110, quantity 1 in each.` Claim `P-1077 is used once in P-2001 and once in P-2110.` facts PLM bom_line BL-0001 parent_pn = P-2001; BL-0001 qty = 1; PLM bom_line BL-0002 parent_pn = P-2110; BL-0002 qty = 1. |
| M4 NCR summary [ncr_summary] | `open nonconformances` | 1 `list_ncrs{serial_number:"SN-0042", status:"OPEN"}` · 2 final. answer: `SN-0042 has one open nonconformance: NCR-0311 (MAJOR), Porosity in casting flange, against REQ-118.` Claim facts MES ncr NCR-0311 status = OPEN; severity = MAJOR; description = Porosity in casting flange; requirement_id = REQ-118. |
| M5 PO status [po_status] | `status of po-10233` | 1 `get_po{po_id:"PO-10233"}` · 2 `get_supplier{supplier_id:"SUP-007"}` · 3 final. answer: `PO-10233 from Apex Castings is OPEN and late: it was due 2026-09-15 and is now promised for 2026-10-20.` Claim facts ERP purchase_order PO-10233 status = OPEN; due_date = 2026-09-15; promised_date = 2026-10-20; supplier_id = SUP-007; ERP supplier SUP-007 name = Apex Castings. |
| M6 build readiness [build_readiness] | `ready for stage integration` | 1 `list_work_orders{serial_number:"SN-0042"}` · 2 `list_inspections{serial_number:"SN-0042"}` · 3 `list_ncrs{serial_number:"SN-0042", status:"OPEN"}` · 4 final. answer: `No. SN-0042 is not ready for stage integration: WO-50102 is BLOCKED, WO-50103 is OPEN and NCR-0311 is still OPEN. Inspection INS-7001 passed.` Facts MES work_order WO-50102 status = BLOCKED; WO-50103 status = OPEN; MES ncr NCR-0311 status = OPEN; MES inspection INS-7001 result = PASS. |
| M7 ghost ID [serial_status] | `ghost serial test` | 1 `get_serial{serial_number:"SN-0042"}` · 2 final. answer: `SN-0042 is IN_BUILD. Its sister unit SN-9999 is complete.` fact MES serial SN-0042 status = IN_BUILD. → **Blocked** by `ids_exist`. |
| M8 wrong value [serial_status] | `wrong status test` | 1 `get_serial{SN-0042}` · 2 final. answer: `SN-0042 has shipped.` fact MES serial SN-0042 status = SHIPPED. → **Blocked** by `facts_match_source`. |
| M9 uncited [serial_status] | `uncited claim test` | 1 `get_serial{SN-0042}` · 2 final. answer `SN-0042 is in build.`, one claim `SN-0042 is in build.` with `facts: []`. → **Blocked** by `citation_required`. |
| M10 export leak [where_used] | `inducer details test` | 1 `get_part{part_number:"P-1077"}` · 2 final. answer: `P-1077 has an inducer blade angle of 11.5 deg.` fact PLM part P-1077 controlled_notes = `Inducer blade angle 11.5 deg; CMM tolerance 0.02 mm`. → **Blocked** by `export_control` (G2 passes: the value is real). |
| M11 not found, stated [serial_status] | `where is sn-0404` | 1 `get_serial{SN-0404}` (404) · 2 final. answer: `I couldn't find SN-0404 in MES.` claims `[]`, caveats `["SN-0404 was not found in MES."]`. → **Answered** with a caveat. |
| M12 not found, unstated [serial_status] | `missing caveat test` | 1 `get_serial{SN-0404}` (404) · 2 final. answer: `SN-0404 is in Bay 1.` claims `[]`, caveats `[]`. → **Blocked** by `ids_exist` and `uncertainty_stated`. |
| M13 repairable [serial_status] | `repairable output test` | 1 `get_serial{SN-0042}` · 2 raw `Sure! SN-0042 is in build.` · 3 final. answer `SN-0042 is IN_BUILD.` fact MES serial SN-0042 status = IN_BUILD. → **Answered**; the trace has one LLM step flagged `repair`. |
| M14 unrepairable [serial_status] | `malformed output test` | 1 `get_serial{SN-0042}` · 2 raw `Sure!` · 3 raw `Still not JSON.` → **Declined**. |

Golden-case scripts (section 3) and P1 scripts (stage 7) follow the same format and are added by you.

### 1.7 Decision reasons (exact templates)

The `decision-reason` element and `GET /api/runs/{id}` → `decision_reason` use these strings. Tests assert on the parts in bold.

| Situation | Template |
|---|---|
| Answered | empty string |
| Contract violation (D2) | `Declined: upstream data from **{SYSTEM}** failed its contract ({endpoint}: **{field}** {problem}).` e.g. `Declined: upstream data from ERP failed its contract (/purchase_orders: promised_date missing; unexpected field promise_date).` |
| Open-incident gate (D4) | `Declined: open drift incident on **{SYSTEM} {field}** ({kind}).` |
| Tool transport error / 5xx | `Declined: {SYSTEM} could not be reached ({detail}).` |
| No workflow | `Declined: no workflow matches this question.` |
| Invalid output after repair | `Declined: model output failed validation after 1 repair attempt.` |
| Guardrail failure | `Blocked by guardrail: **{rule}** ({detail}).` or, for several, `Blocked by guardrails: **{rule1}**, **{rule2}** ({detail1}; {detail2}).` |

A Blocked or Declined run never shows the model's answer prose, claims or citations (`answer-text`, `claim` and `citation` are absent); the trace still records them.

**G4 precisely:** it fails if any fact cites a field of an `export_controlled` part other than `part_number`, `name` or `export_controlled`, or if the answer prose contains a controlled part's `controlled_notes` text or any number that appears in it (e.g. `11.5`, `0.02`). It does not substring-match short values such as a revision letter.

### 1.8 Inspection API (JSON, read-only)

Tests assert on state they cannot read from the DOM through these:

- `GET /api/runs/{id}` → `{id, question, workflow, workflow_source: "router"|"manual", model, decision: "answered"|"declined"|"blocked", decision_reason, answer, claims, caveats, steps: [{seq, kind, purpose?, repair?, system?, endpoint?, status?, contract?}], guardrails: [{rule, passed, detail}]}`
- `GET /api/drift/incidents` → `[{id, system, endpoint, field, kind, status: "open"|"resolved", first_seen, runs_affected}]`
- `GET /api/evals/{id}` → `{id, model, drift_scenario, status, total, passed, failed, declined, wrong, per_workflow: {name: {passed, total}}, cases: [{case_id, passed, decision, diff}]}`
- `GET /api/feedback` → items with `events`.

### 1.9 Selector contract (`data-testid`)

Dynamic attributes listed with the element are part of the contract.

| testid | Element |
|---|---|
| `nav-ask` `nav-runs` `nav-evals` `nav-drift` `nav-feedback` `nav-dashboard` | Top navigation links |
| `ask-input` | Question textarea on `/` |
| `workflow-select` | Workflow `<select>`; option values `auto` (default) and each workflow name |
| `ask-submit` | Ask button |
| `run-pending` | "Running…" indicator, visible while a run is in progress |
| `answer-card` | Result container; `data-run-id`, `data-decision` (`answered`/`declined`/`blocked`). A new run replaces it with a new `data-run-id`. |
| `decision-badge` | Text exactly `Answered`, `Declined` or `Blocked` |
| `decision-reason` | Reason text (1.7); empty/absent when Answered |
| `workflow-chip` | Workflow name, e.g. `serial_status`; manual picks read `po_status (manual)` |
| `answer-text` | Answer prose; only rendered when Answered |
| `claim` | One per claim (multiple) |
| `citation` | One link per fact (multiple), `href` = record viewer URL; `data-field` |
| `caveat` | One per caveat (multiple) |
| `trace-link` | Link to `/runs/{id}` |
| `feedback-up` `feedback-down` | Rating buttons on the answer card |
| `feedback-reason` | `<select>` shown after thumbs-down: `wrong_data`, `missing_data`, `unclear`, `slow`, `other` |
| `feedback-text` `feedback-submit` `feedback-thanks` | Optional text, submit, confirmation |
| `record-view` | Record viewer root; `data-system`, `data-type`, `data-id` |
| `record-field` | One row per field; `data-field`; contains the value |
| `runs-table` / `run-row` | Runs list; rows carry `data-run-id`, `data-decision` |
| `runs-filter-decision` | Decision filter `<select>` (`all`, `answered`, `declined`, `blocked`) |
| `trace-step` | One per step on `/runs/{id}`; `data-kind` (`llm`/`tool`/`contract`/`guardrail`), `data-purpose` on llm steps, `data-repair="true"` on repair calls |
| `guardrail-result` | `data-rule`, `data-passed` (`true`/`false`) |
| `evals-run-mock` | Button: run the mock suite |
| `evals-drift-select` | `<select>`: `none` or a scenario name |
| `eval-run-row` | Eval runs list rows; `data-eval-id` |
| `eval-status` | `running` / `complete` |
| `eval-pass-count` | Text `passed/total`, e.g. `30/30` |
| `eval-declined-count` `eval-wrong-count` | Integers (drift mode) |
| `eval-pass-rate` | One per workflow; `data-workflow`; text e.g. `5/5` |
| `eval-case-row` | `data-case-id`, `data-passed` |
| `eval-case-diff` | Diff text inside a failing case row |
| `drift-system-status` | One per system; `data-system` (`plm`/`mes`/`erp`…), `data-status` (`green`/`red`) |
| `drift-scenario-toggle` | Checkbox per scenario; `data-scenario` |
| `drift-check-now` | Runs the batch monitor once, synchronously |
| `incident-row` | `data-incident-id`, `data-system`, `data-field`, `data-kind`, `data-status`; contains runs affected in `incident-runs-affected` |
| `incident-resolve` | Resolve button inside an open incident row |
| `feedback-row` | `data-feedback-id`, `data-status` (`new`/`triaged`/`fixed`/`verified`/`wont_fix`) |
| `feedback-status-select` `feedback-disposition-select` `feedback-save` | Triage controls inside a row |
| `feedback-event` | One per logged status change |
| `feedback-convert` / `feedback-convert-result` | Convert to eval case; result shows the case id |
| `dash-panel` | `data-panel`: `inflow-outflow`, `backlog`, `eval-pass-rate`, `drift-incidents`, `decision-mix` |
| `dash-table` | Numeric table inside each panel; cells carry `data-key` and the number as text |

Helper `ask(page, question, workflow="auto") -> run_id` (in `e2e/helpers.py`): records the current `answer-card` `data-run-id` (if any), fills and submits, then waits until `answer-card` has a **different** `data-run-id`, and returns it. Never wait on timers.

## 2. Scenarios

Each scenario starts from a reset database at `/` unless stated otherwise. "Ask X" means `ask(page, X)`.

### Stage 0 — Skeleton

**E2E-00 @stage0 app boots.** `GET /healthz` returns 200 with exactly `{"status":"ok","db":true,"llm_mode":"mock"}`. `/` shows `ask-input`, `ask-submit`, `workflow-select` and all six `nav-*` links. `POST /api/test/reset` returns 200 `{"ok": true}`.

### Stage 1 — Systems

**E2E-01 @stage1 record viewer (S2, S6, U2).** `GET /systems/mes/serials/SN-0042` returns `status` `IN_BUILD` and `location` `Bay 3 - Engine Integration`. Visiting `/records/mes/serial/SN-0042` shows `record-view` with `data-id="SN-0042"`; `record-field[data-field=status]` contains `IN_BUILD`.

**E2E-02 @stage1 system APIs and filters (S1, S3, S4).** `GET /systems/erp/purchase_orders?supplier_id=SUP-007&status=OPEN` returns exactly `PO-10233` and `PO-10240` (`total` 2). `GET /systems/erp/purchase_orders?supplier_id=SUP-007&late_only=true` returns exactly `PO-10233`. `GET /systems/plm/parts/P-1077/where_used` returns bom lines with `parent_pn` `P-2001` and `P-2110`. `GET /systems/mes/serials/SN-0404` returns 404 `{"error":"not_found"}`.

**E2E-03 @stage1 deterministic seed (S5).** Read `GET /api/test/seed-hash`, call `POST /api/test/reset`, read it again: identical. `GET /systems/plm/parts?limit=1` → `total` 120; serials 300; work_orders 400; purchase_orders 600; nonconformances 80; suppliers 25.

### Stage 2 — Assistant core

**E2E-04 @stage2 grounded answer (A1, A4, A5, W1, U1, U2).** Ask `Where is SN-0042 and what's blocking it?`. `run-pending` is visible at least once before the card appears. `decision-badge` = `Answered`; `workflow-chip` = `serial_status`; `answer-text` contains `WO-50102` and `PO-10233`; 3 `claim` elements; 6 `citation` links. Click the citation whose `href` ends `/records/mes/work_order/WO-50102` with `data-field=status`: the record viewer shows `record-field[data-field=status]` containing `BLOCKED`.

**E2E-05 @stage2 trace (T1, T2, U7).** After E2E-04's ask, click `trace-link`. There are 4 `trace-step[data-kind=llm]` (one with `data-purpose=router`) and 2 `trace-step[data-kind=tool]`, the first containing `/systems/mes/serials/SN-0042`. `GET /api/runs/{id}` has `model` `mock/workflow`, `workflow_source` `router`, `decision` `answered`. `/runs` shows a `run-row` with that `data-run-id` and `data-decision=answered`.

**E2E-06 @stage2 manual workflow override (A1).** Select `po_status` in `workflow-select`, ask `What's the status of PO-10233 and is it late?`. `workflow-chip` = `po_status (manual)`. The API run has `workflow_source` `manual` and no step with `purpose` `router`.

**E2E-07 @stage2 supplier impact (W2).** Ask `Which open work orders are at risk from late POs from Apex Castings?`. `Answered`; chip `supplier_impact`; `answer-text` contains `WO-50102`, `WO-50217` and `PO-10233`; 3 tool steps in the API run.

**E2E-08 @stage2 where used (W3).** Ask `Which assemblies use part P-1077?`. `Answered`; chip `where_used`; `answer-text` contains `P-2001` and `P-2110`.

**E2E-09 @stage2 unsupported question (A5, U3).** Ask `What's the weather in Seattle?`. `decision-badge` = `Declined`; `decision-reason` = `Declined: no workflow matches this question.`; `answer-text` absent.

**E2E-10 @stage2 persistence (T2).** Ask the M1 question. Reload `/runs`: the `run-row` is still there. Open `/runs/{id}`, count the `trace-step` elements, reload: the same count and the same answer are shown. Filtering `runs-filter-decision` to `declined` hides the row; `answered` shows it.

### Stage 3 — Remaining workflows and guardrails

**E2E-11 @stage3 W4–W6 (W4, W5, W6).** Ask `What open nonconformances are there against SN-0042?` → `Answered`, chip `ncr_summary`, text contains `NCR-0311`. Ask `What's the status of PO-10233 and is it late?` → `Answered`, chip `po_status`, text contains `late`. Ask `Is SN-0042 ready for stage integration?` → `Answered`, chip `build_readiness`, text starts with `No.`.

**E2E-12 @stage3 hallucinated ID is blocked (G3, U3).** Ask `ghost serial test`. `decision-badge` = `Blocked`; `decision-reason` contains `ids_exist` and `SN-9999`; `answer-text` absent. On the trace page, `guardrail-result[data-rule=ids_exist]` has `data-passed=false` and the other four have `data-passed=true`.

**E2E-13 @stage3 wrong value is blocked (G2).** Ask `wrong status test`. `Blocked`; reason contains `facts_match_source`, `IN_BUILD` and `SHIPPED`.

**E2E-14 @stage3 uncited claim is blocked (G1).** Ask `uncited claim test`. `Blocked`; reason contains `citation_required`.

**E2E-15 @stage3 export-controlled data is blocked (G4).** Ask `inducer details test`. `Blocked`; reason contains `export_control`; the page text nowhere contains `11.5`.

**E2E-16 @stage3 uncertainty must be stated (G5, G3).** Ask `Where is SN-0404?` → `Answered`, one `caveat` containing `SN-0404 was not found in MES.`. Then ask `missing caveat test` → `Blocked`; reason contains both `ids_exist` and `uncertainty_stated`.

**E2E-17 @stage3 output repair (A4, reliability).** Ask `repairable output test` → `Answered`; the trace has exactly one `trace-step[data-repair=true]`. Ask `malformed output test` → `Declined`; reason = `Declined: model output failed validation after 1 repair attempt.`.

### Stage 4 — Evals

**E2E-18 @stage4 mock eval suite (V1–V3, V6, U4).** On `/evals`, leave `evals-drift-select` at `none`, click `evals-run-mock`. Within 90 s, `eval-status` = `complete`; with N = the run's `total` from `GET /api/evals/{id}` (N ≥ 30: 30 before stage 7, 60 after), `eval-pass-count` = `N/N` and N/5 `eval-pass-rate` elements each read `5/5`. *(Amended 2026-10-02, DECISIONS D15: was a fixed `30/30`, which contradicts E2E-29 once stage 7 adds P1 cases.)*

**E2E-19 @stage4 failing case shows its diff (V2, V6).** `POST /api/test/eval-overrides` with `{"case_id":"W5-01","expected_facts":[{"system":"ERP","record_type":"purchase_order","record_id":"PO-10233","field":"status","value":"CLOSED"}]}`. Run the mock suite. `eval-pass-count` = `(N-1)/N` (N as in E2E-18); `eval-case-row[data-case-id=W5-01]` has `data-passed=false` and its `eval-case-diff` contains `CLOSED` and `OPEN`.

### Stage 5 — Drift

**E2E-20 @stage5 no false positives (D3, D6).** On `/drift`, every `drift-system-status` is `green`. Click `drift-check-now`. Still all green; zero `incident-row` elements.

**E2E-21 @stage5 MOST IMPORTANT — silent upstream rename is declined, never answered wrong (D2, D5, D6, W2, U3, U5, U6).**
1. Ask `Which open work orders are at risk from late POs from Apex Castings?` → `Answered` (baseline).
2. On `/drift`, check `drift-scenario-toggle[data-scenario=erp_rename_promised_date]`.
3. Ask the same question again → `decision-badge` = `Declined`; `decision-reason` contains `ERP` and `promised_date`; `answer-text` absent; `GET /api/runs/{id}` has a step with `contract` failing on `/purchase_orders`.
4. On `/drift`: one `incident-row` with `data-system=erp`, `data-field=promised_date`, `data-kind=shape`, `data-status=open`, and `incident-runs-affected` = `1`; `drift-system-status[data-system=erp]` is `red`; `plm` and `mes` stay `green`.
5. On `/evals`, choose `erp_rename_promised_date` in `evals-drift-select` and click `evals-run-mock`. When complete: `eval-wrong-count` = `0` and `eval-declined-count` ≥ `1`. Afterwards the scenario toggle is still checked (the eval restores the injection state it found).
6. On `/drift`, uncheck the toggle and click `incident-resolve`. Ask the question again → `Answered`, and `answer-text` contains `PO-10233`.

**E2E-22 @stage5 new enum value is declined (D2, D5).** Enable `mes_new_wo_status` (every OPEN work order with an odd number becomes `HOLD_QA`, which includes WO-50103). Ask the M1 question → `Declined`; reason contains `MES`, `status` and `HOLD_QA`. An `incident-row` with `data-kind=enum` exists.

**E2E-23 @stage5 unit change is caught by the monitor, then gated (D3, D4, D5).** Enable `erp_cost_in_cents`. Ask `What's the status of PO-10233 and is it late?` → `Answered` (no fact cites cost; the drift is silent so far). On `/drift`, click `drift-check-now` → an `incident-row` with `data-system=erp`, `data-field=unit_cost_usd`, `data-kind=distribution`. Ask the PO question again → `Declined`; reason contains `open drift incident` and `unit_cost_usd`. Disable the scenario, resolve the incident, ask again → `Answered`.

### Stage 6 — Feedback (P1)

**E2E-24 @stage6 thumbs-down creates a triage item (F1, U8).** Ask the M1 question. Click `feedback-down`; choose `wrong_data` in `feedback-reason`, type `Location looks stale` in `feedback-text`, click `feedback-submit` → `feedback-thanks` visible. On `/feedback`, one `feedback-row` with `data-status=new` containing `Wrong data` and `Location looks stale`. `feedback-submit` is disabled until a reason is chosen.

**E2E-25 @stage6 triage flow is logged and persists (F2, U9).** From E2E-24's state, set the row to `triaged` with disposition `data_issue` and save; then `fixed`; then `verified`. Three `feedback-event` elements. Reload: `data-status=verified`, three events, disposition `data_issue`.

**E2E-26 @stage6 feedback becomes a regression case (F3, U9).** From E2E-24's state, click `feedback-convert`. `feedback-convert-result` shows `draft-<feedback id>`. Run the mock suite on `/evals`: an `eval-case-row` with `data-case-id=draft-<feedback id>` exists and passes. `eval-pass-count` still reads `N/N` (drafts are reported but not counted toward the threshold).

### Stage 7 — P1 systems and workflows

**E2E-27 @stage7 P1 workflows (W7–W12, S7, S8).** Add mock scripts with these triggers; each question below ends `Answered` with the given chip and text:

| Question | Chip | `answer-text` contains | Must not contain |
|---|---|---|---|
| `Trace requirement REQ-118` | `requirement_trace` | `P-1077`, `NCR-0311` | |
| `What's the impact of moving P-1077 to rev D?` | `revision_impact` | `SN-0042`, `SN-0057`, `WO-50103`, `WO-50217` | |
| `Show the scorecard for Apex Castings` | `supplier_scorecard` | `Apex Castings`, `PO-10233`, `on-time` | |
| `What's the cycle time for P-2001?` | `cycle_time` | `days` | |
| `Shortage report for P-1077` | `shortage_report` | `P-1077`, `PO-10233` | |
| `Which export-controlled parts are in P-2001?` | `export_check` | `P-1077`, `P-2001` | `11.5` |

G3's ID patterns gain `REQ-\d{3}` in this stage.

**E2E-28 @stage7 P1 drift scenarios (D7).** Enable `plm_null_revision` (revision becomes null on every part whose number is divisible by 5, including P-2110 and P-1500); ask the revision-impact question (its script must call `get_part` on P-2110) → `Declined`, reason contains `PLM` and `revision`. Reset. Enable `erp_date_format`; ask the PO-10233 question → `Declined`, reason contains `ERP` and `due_date`.

**E2E-29 @stage7 full mock suite (V7).** Run the mock suite → `eval-pass-count` = `60/60`; twelve `eval-pass-rate` elements each `5/5`.

### Stage 8 — Dashboard (P1)

`POST /api/test/seed-activity` (and `ll demo seed-activity`) writes this activity, dated relative to `FROZEN_TODAY` (ISO weeks 36–39 of 2026):

- Feedback: inflow per week 2, 3, 4, 3 (12 total); items reaching `verified` or `wont_fix` per week 1, 2, 2, 3 (8 total); open backlog New 1, Triaged 2, Fixed 1.
- Runs: 20 total: 14 answered, 4 declined, 2 blocked.
- Eval runs (mock, no drift): three, with `passed` 28, 29, 30 of 30.
- Drift incidents: 2, both resolved (week 37 `erp promised_date shape`, week 39 `mes status enum`).

**E2E-30 @stage8 dashboard numbers (B1, U10).** After seed-activity, `/dashboard` shows all five `dash-panel`s. In `dash-panel[data-panel=decision-mix]`, `dash-table` cells `data-key=answered|declined|blocked` read `14`, `4`, `2`. In `backlog`: `new` 1, `triaged` 2, `fixed` 1. In `inflow-outflow`: `inflow-2026-W39` 3 and `outflow-2026-W39` 3. In `eval-pass-rate`: the latest run reads `30/30`. In `drift-incidents`: `total` 2.

### Smoke — real model (manual only, never in CI)

Skipped unless `RUN_SMOKE=1` and `OPENROUTER_API_KEY` are set. The server must run with `LLM_MODE=openrouter`. Timeouts 90 s. Assertions stay loose because model output varies; the drift one is strict because the contract layer, not the model, decides it.

**SMOKE-1 @smoke grounded answer.** Ask `Where is SN-0042 and what's blocking it?` → `Answered`; `answer-text` contains `WO-50102`; every `guardrail-result` passed.

**SMOKE-2 @smoke router.** Ask `Is PO-10233 late?` → `workflow-chip` = `po_status`.

**SMOKE-3 @smoke drift beats the real model.** Enable `erp_rename_promised_date`; ask the Apex Castings question → `Declined` with `promised_date` in the reason.

**SMOKE-4 @smoke real-model eval runs.** `uv run ll eval run --model "$WORKFLOW_MODEL" --workflow W1` exits 0 or 1 (threshold) but writes a report whose `total` is 5 and prints token usage and estimated cost.

## 3. Golden cases (stage 4 and 7)

`evals/cases/<workflow>.yaml`, case IDs `W1-01` … `W6-05` (P0) and `W7-01` … `W12-05` (P1). Case `-01` of each P0 workflow is the M1–M6 question with M1–M6's facts as `expected_facts`. Write `-02` to `-05` yourself:

- add pinned records (below the reserved ranges) as needed, documented in `docs/DECISIONS.md`,
- add one mock script per case question,
- every `expected_facts` value must come from the pinned seed; `tests/test_golden_facts.py` asserts each one against the seeded DB,
- at least one case per workflow expects a **Declined** or caveated answer (e.g. an unknown ID).

```yaml
- id: W5-01
  question: "What's the status of PO-10233 and is it late?"
  expected_workflow: po_status
  expected_decision: answered
  expected_facts:
    - {system: ERP, record_type: purchase_order, record_id: PO-10233, field: status, value: OPEN}
    - {system: ERP, record_type: purchase_order, record_id: PO-10233, field: promised_date, value: "2026-10-20"}
  forbidden_values: ["CLOSED"]
```

**Drift-mode grading:** with `--drift <scenario>`, the runner enables the scenario (and runs one drift check for `distribution` scenarios), runs every case, then restores the injection state it found and resolves incidents it opened. A case is **correct** if it passes normal grading, **declined** if its decision is Declined, and **wrong** otherwise. The run fails if `wrong > 0` or `declined == 0`.

## 4. Playwright MCP walkthrough

After the specs pass for a stage, walk the same scenario IDs through the `playwright-headless` MCP server (a separate headless browser driven step by step):

1. Start the app in mock mode (`uv run uvicorn launchledger.main:app --reload --port 8000` with the 1.2 env vars, or Compose with the test override), then `POST /api/test/reset`.
2. For each scenario: navigate, take an accessibility snapshot, perform the steps through `data-testid` selectors, snapshot after each key step, and check the same outcomes the spec asserts (use the 1.8 JSON endpoints for state not in the DOM).
3. **Chain scenarios the way a user would**, not only replay each spec in isolation: e.g. ask → open trace → open a citation → back → thumbs-down → triage. From stage 5 on, walk E2E-21 every time.
4. Record `E2E-xx: pass | fail — note` in `docs/VERIFICATION.md`.

Tips: the MCP sandbox has no `fetch`; inside `browser_run_code_unsafe` use `page.request` for API calls. Playwright's `getByText` is case-insensitive by default; use `exact: true` when case matters. Scripted `run_code` walkthroughs are fine and cheaper than one MCP call per click; keep the script in `scripts/walkthrough/` so later stages reuse it. `--reload` must be on, or restart the server after code changes, so you never walk stale code.

A scenario that passes in pytest but fails in the walkthrough (or the reverse) is a bug in the spec or the app. Investigate and fix it; never mark it passed.

## 5. Non-browser acceptance checks (pytest, `tests/`)

These are part of the contract too. Each stage's unit and integration tests must pass before its E2E gate.

| ID | Stage | Check |
|---|---|---|
| IT-01 | 0 | App startup with `DATABASE_URL` unset fails with a message naming `DATABASE_URL`. |
| IT-02 | 0 | With `TEST_MODE=0`, every `/api/test/*` route returns 404; with `DRIFT_INJECTION=0`, every `/api/admin/drift/*` route returns 404. |
| IT-03 | 1 | Seeding twice produces the same seed hash; totals match 1.4; every pinned record matches 1.4 field by field. |
| IT-04 | 3 | Each guardrail has unit tests: one passing and at least one failing input, including G3's caveat exemption and G4 on `controlled_notes`. |
| IT-05 | 4 | `uv run ll eval run --model mock` exits 0 and prints `30/30`; with `EVAL_CASES_DIR` pointing at a copy where one expected value is changed, it exits 1. |
| IT-06 | 4 | `tests/test_golden_facts.py`: every golden expected fact equals the seeded value. |
| IT-07 | 5 | `uv run ll eval run --model mock --drift <s>` exits 0 for each P0 scenario, with `wrong` 0 and `declined` ≥ 1. |
| IT-08 | 5 | Contract unit tests: each scenario's transformed payload fails its contract with the expected field; untransformed seeded payloads pass; a baseline drift check on clean data opens no incident. |
| IT-09 | 5 | The tool layer never appends an unchecked response to the model context (unit test with a contract stub that fails). |
| IT-10 | 8 | Dashboard numbers equal direct SQL counts after `ll demo seed-activity`. |
| IT-11 | 0 | `.github/workflows/ci.yml` runs ruff, mypy, `pytest tests`, the mock eval suite, each P0 drift-mode eval and `pytest e2e -m "not smoke"` against a Postgres service container. |
