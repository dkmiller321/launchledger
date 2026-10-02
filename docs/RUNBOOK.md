# RUNBOOK.md — operating LaunchLedger

What to do when something fires. Each section starts with what you see, then what to do.

## A drift incident is open

**You see:** `/drift` shows a system in red; answers that touch it end **Declined** with `Declined: upstream data from {SYSTEM} failed its contract (...)` or `Declined: open drift incident on {SYSTEM} {field} ({kind})`.

1. Open `/drift` and read the incident row: system, endpoint, field, kind, first seen, runs affected, and the detail text.
2. Find the change in the source:
   - **shape** (field missing, unexpected field, null where not allowed, date in a new format): a rename or format change in the upstream API. Check the upstream team's release notes for the endpoint shown.
   - **enum** (unexpected value such as `HOLD_QA`): a new status the contract does not know.
   - **distribution** (p50 moved by more than 2x): a unit or scale change under the same field name, e.g. dollars to cents.
3. Decide:
   - **The upstream change is a bug:** ask the owning team to roll back. Keep the incident open; the gate keeps answers safe meanwhile.
   - **The upstream change is intended:** update the contract in `launchledger/contracts/schemas.py` (and the tool or workflow guidance if a field was renamed), add or update golden cases that cover the new shape, and run the gates below.
4. Re-capture baselines if a distribution change is intended: `uv run ll drift baseline`.
5. Run `uv run ll drift check` (expect `0 problem(s) found`) and `uv run ll eval run --model mock` (expect 100%).
6. Resolve the incident on `/drift`. Resolving lifts the gate; do it only after step 5 passes.

## The eval gate fails in CI

**You see:** the `Mock eval suite` step prints `GATE FAILED: <workflow> n/5 below 100%`.

1. Read the failing case lines (`W5-01: wrong: missing fact ...`). Each line names the expected fact and what the run produced.
2. Open the run: `/evals/<id>` links each case to its trace at `/runs/<id>`.
3. A failing mock eval is never model noise. It means a tool, contract, guardrail, grader or seed change broke a workflow. Fix the code, or, if the expected value itself changed, regenerate fixtures with `uv run python scripts/build_fixtures.py` and confirm `tests/test_evals.py::test_it_06_golden_facts_match_the_seed` passes.

## A drift-mode eval reports wrong answers

**You see:** `GATE FAILED: n wrong answer(s) under drift`. This is the most serious failure: the assistant answered confidently from bad data.

1. List the `wrong` cases in the report and open their traces.
2. Check that every tool response in the trace has a `contract` step. A missing contract step means a tool bypassed the contract layer.
3. Check whether the drifted field is covered by the contract (`launchledger/contracts/schemas.py`). Tighten the contract or add a monitor sample, then rerun the drift-mode eval until `wrong 0`.

## Feedback is piling up

**You see:** the dashboard's open backlog grows week over week; inflow exceeds outflow.

1. Triage everything in `New` on `/feedback`: set a disposition (data issue, prompt issue, guardrail false positive, drift, feature request).
2. For every real bug, click **Convert to eval case**. The draft lands in `EVAL_DRAFTS_DIR` and runs with the next suite. Review it, move it into `evals/cases/<workflow>.yaml`, and add a matching mock script.
3. Close the loop: `Fixed` when the change merges, `Verified` when the new eval case passes.

## Upgrading a model

1. Set the candidate slug and run `uv run ll eval compare "$WORKFLOW_MODEL" <candidate>`.
2. Ship only if the candidate passes at least as many cases, with no new failures in any workflow and acceptable p95 latency and cost.
3. Update `WORKFLOW_MODEL` (or `ROUTER_MODEL`) in the environment; record the comparison report with the change.

## Weekly report

`uv run ll report weekly --out weekly.md` writes backlog flow, open backlog, decision mix and eval history for leadership.
