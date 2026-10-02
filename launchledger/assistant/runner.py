"""One question = one run (PRD A1-A5). Router -> workflow agent -> contracts -> guardrails.

Rules (PRD §6): the model never sees an unchecked tool response, and Declined beats Answered.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from launchledger.assistant.schema import FinalAnswer, parse_final
from launchledger.assistant.tools import TOOLS, ToolOutcome, execute
from launchledger.assistant.workflows import (
    MAX_TOOL_CALLS,
    ROUTER_PROMPT,
    WORKFLOWS,
    router_tool,
    system_prompt,
)
from launchledger.clock import now, today
from launchledger.contracts.check import ContractResult, check_response
from launchledger.contracts.incidents import bump_runs_affected, open_incidents, record_incident
from launchledger.db.models import GuardrailResult, Run, RunStep
from launchledger.db.session import session_scope
from launchledger.guardrails.rules import GuardContext, blocked_reason, run_all
from launchledger.llm.provider import LlmError, LlmProvider, LlmReply, Message, get_provider
from launchledger.systems.client import systems_client
from launchledger.systems.records import record_path

REPAIR_PROMPT = (
    "Your last reply was not valid: {error}. Reply again with ONLY the JSON object "
    "described in the instructions."
)


@dataclass
class RunTrace:
    steps: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0

    def add(
        self, kind: str, payload: dict[str, Any], latency_ms: int = 0, tokens: int | None = None
    ) -> None:
        self.steps.append(
            {"kind": kind, "payload": payload, "latency_ms": latency_ms, "tokens": tokens}
        )
        self.latency_ms += latency_ms
        self.tokens += tokens or 0

    def llm(self, reply: LlmReply, purpose: str, repair: bool = False) -> None:
        self.cost_usd += reply.cost_usd
        self.add(
            "llm",
            {"purpose": purpose, "model": reply.model, "repair": repair, "response": reply.message},
            reply.latency_ms,
            reply.tokens,
        )


@dataclass
class RunResult:
    run_id: int
    decision: str
    reason: str
    workflow: str | None
    answer: FinalAnswer | None
    tokens: int
    latency_ms: int
    cost_usd: float


@dataclass
class _Outcome:
    decision: str = "declined"
    reason: str = ""
    answer: FinalAnswer | None = None
    raw_answer: FinalAnswer | None = None
    guardrails: list[Any] = field(default_factory=list)


@lru_cache(maxsize=1)
def _router_tools() -> list[dict[str, Any]]:
    return [router_tool()]


def _fetch_record(record_type: str, record_id: str) -> dict[str, Any] | None:
    try:
        path = record_path(record_type, record_id)
    except KeyError:
        return None
    resp = systems_client().get(path)
    if resp.status_code != 200:
        return None
    data: dict[str, Any] = resp.json()
    return data


def _route(provider: LlmProvider, question: str, trace: RunTrace) -> str:
    messages: list[Message] = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": question},
    ]
    reply = provider.chat(messages=messages, tools=_router_tools(), purpose="router")
    trace.llm(reply, "router")
    for call in reply.message.get("tool_calls") or []:
        try:
            choice = json.loads(call["function"]["arguments"]).get("workflow", "")
        except (KeyError, json.JSONDecodeError, AttributeError):
            continue
        if choice in WORKFLOWS:
            return str(choice)
    return "unsupported"


def _check(outcome: ToolOutcome, eval_run_id: int | None) -> ContractResult | None:
    """Contract check + incident gate. None when there is nothing to check (404 / error)."""
    if outcome.status != "ok":
        return None
    result = check_response(
        outcome.system,
        outcome.endpoint,
        outcome.record_type,
        outcome.body,
        outcome.is_list,
        open_incidents(),
    )
    if result.violations:
        first = result.violations[0]
        record_incident(
            outcome.system,
            outcome.endpoint,
            first.field,
            first.kind,
            "; ".join(v.problem for v in result.violations),
            from_run=True,
            eval_run_id=eval_run_id,
        )
    elif result.gated_by is not None:
        bump_runs_affected(result.gated_by.id)
    return result


def _agent(
    provider: LlmProvider,
    workflow_name: str,
    question: str,
    trace: RunTrace,
    eval_run_id: int | None,
) -> _Outcome:
    workflow = WORKFLOWS[workflow_name]
    tools = [TOOLS[t].schema() for t in workflow.tools]
    messages: list[Message] = [
        {"role": "system", "content": system_prompt(workflow, today().isoformat())},
        {"role": "user", "content": question},
    ]
    calls = 0
    repaired = False
    repairing = False
    empty_or_failed = False
    fetched: list[tuple[str, dict[str, Any]]] = []
    while True:
        try:
            reply = provider.chat(messages=messages, tools=tools, purpose="workflow")
        except LlmError as exc:
            return _Outcome("declined", f"Declined: the model could not be reached ({exc}).")
        trace.llm(reply, "workflow", repair=repairing)
        repairing = False
        message = reply.message
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            messages.append(
                {"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls}
            )
            for call in tool_calls:
                calls += 1
                if calls > MAX_TOOL_CALLS:
                    return _Outcome(
                        "declined",
                        f"Declined: the assistant needed more than {MAX_TOOL_CALLS} tool calls.",
                    )
                name = call.get("function", {}).get("name", "")
                try:
                    args = json.loads(call.get("function", {}).get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                outcome = execute(name, args if isinstance(args, dict) else {}, workflow.tools)
                trace.add(
                    "tool",
                    {
                        "tool": name,
                        "args": args,
                        "system": outcome.system,
                        "endpoint": outcome.endpoint,
                        "path": outcome.path,
                        "status": outcome.status,
                        "http_status": outcome.http_status,
                        "detail": outcome.detail,
                        "result": outcome.for_model(),
                    },
                    outcome.latency_ms,
                )
                if outcome.status == "error":
                    if outcome.path:  # the request was sent: transport error or 5xx
                        reason = (
                            f"Declined: {outcome.system.upper()} could not be reached "
                            f"({outcome.detail})."
                        )
                    else:  # refused before sending: tool not allowed or bad arguments
                        reason = f"Declined: tool {name} failed ({outcome.detail})."
                    return _Outcome("declined", reason)
                contract = _check(outcome, eval_run_id)
                if contract is not None:
                    trace.add("contract", contract.to_json())
                    if not contract.passed:
                        return _Outcome("declined", contract.decision_reason())
                if outcome.empty:
                    empty_or_failed = True
                if outcome.status == "ok":
                    items = outcome.body.get("items", []) if outcome.is_list else [outcome.body]
                    fetched.extend((outcome.record_type, r) for r in items if isinstance(r, dict))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(outcome.for_model()),
                    }
                )
            continue

        final, error = parse_final(message.get("content"))
        if final is None:
            if repaired:
                return _Outcome(
                    "declined", "Declined: model output failed validation after 1 repair attempt."
                )
            repaired = repairing = True
            messages.append({"role": "assistant", "content": message.get("content") or ""})
            messages.append({"role": "user", "content": REPAIR_PROMPT.format(error=error)})
            continue

        ctx = GuardContext(
            answer=final,
            fetch=_fetch_record,
            tool_empty_or_failed=empty_or_failed,
            fetched_records=fetched,
        )
        results = run_all(ctx)
        for r in results:
            trace.add("guardrail", {"rule": r.rule, "passed": r.passed, "detail": r.detail})
        reason = blocked_reason(results)
        if reason:
            return _Outcome("blocked", reason, None, final, results)
        return _Outcome("answered", "", final, final, results)


def run_question(
    question: str,
    workflow: str | None = None,
    *,
    provider: LlmProvider | None = None,
    eval_run_id: int | None = None,
) -> RunResult:
    provider = provider or get_provider()
    trace = RunTrace()
    source = "manual" if workflow else "router"
    chosen: str | None = workflow
    try:
        if chosen is None:
            chosen = _route(provider, question, trace)
        if chosen not in WORKFLOWS:
            outcome = _Outcome("declined", "Declined: no workflow matches this question.")
        else:
            outcome = _agent(provider, chosen, question, trace, eval_run_id)
    except LlmError as exc:
        outcome = _Outcome("declined", f"Declined: the model could not be reached ({exc}).")

    workflow_model = next(
        (
            s["payload"]["model"]
            for s in trace.steps
            if s["kind"] == "llm" and s["payload"]["purpose"] == "workflow"
        ),
        None,
    )
    router_model = next(
        (s["payload"]["model"] for s in trace.steps if s["kind"] == "llm"), "manual"
    )
    recorded = outcome.raw_answer
    with session_scope() as s:
        run = Run(
            question=question,
            workflow=chosen if chosen in WORKFLOWS else None,
            workflow_source=source,
            model=workflow_model or router_model,
            decision=outcome.decision,
            decision_reason=outcome.reason,
            answer_json=recorded.model_dump() if recorded else None,
            created_at=now(),
        )
        s.add(run)
        s.flush()
        for seq, step in enumerate(trace.steps, start=1):
            s.add(
                RunStep(
                    run_id=run.id,
                    seq=seq,
                    kind=step["kind"],
                    payload_json=step["payload"],
                    latency_ms=step["latency_ms"],
                    tokens=step["tokens"],
                )
            )
        for r in outcome.guardrails:
            s.add(GuardrailResult(run_id=run.id, rule=r.rule, passed=r.passed, detail=r.detail))
        run_id = run.id
    return RunResult(
        run_id,
        outcome.decision,
        outcome.reason,
        chosen if chosen in WORKFLOWS else None,
        outcome.answer,
        trace.tokens,
        trace.latency_ms,
        trace.cost_usd,
    )
