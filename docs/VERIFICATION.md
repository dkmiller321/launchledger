# VERIFICATION.md — what was run, and what was seen

Claude Code appends one section per stage: the stage number, every command run with its pass/fail counts (lint, types, unit/integration, E2E twice, evals, drift-mode evals), each scenario walked through the `playwright-headless` MCP server as `E2E-xx: pass | fail — note`, and anything surprising. Final acceptance adds a summary: totals, flaky specs (target 0), skipped tests and why, known issues, and the commands to run the app and the demo.

## Log
