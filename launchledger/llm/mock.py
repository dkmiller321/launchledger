"""Scripted mock model (E2E_TESTS.md §1.6). Only the LLM is faked; tools still run for real."""

import json
import time
from functools import lru_cache
from typing import Any

from launchledger.llm.provider import REPO_ROOT, LlmReply, Message

NO_SCRIPT = "Mock: no script for this prompt."


@lru_cache(maxsize=1)
def load_scripts() -> dict[str, Any]:
    with (REPO_ROOT / "fixtures" / "llm-mock.json").open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _question(messages: list[Message]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            return str(msg.get("content", "")).lower()
    return ""


def route(question: str) -> str:
    q = question.lower()
    for entry in load_scripts()["router"]:
        if entry["trigger"] in q:
            return str(entry["workflow"])
    return "unsupported"


def script_step(question: str, step: int) -> dict[str, Any]:
    q = question.lower()
    for script in load_scripts()["workflows"]:
        if script["trigger"] in q:
            steps: list[dict[str, Any]] = script["steps"]
            return steps[step] if step < len(steps) else {"raw": NO_SCRIPT}
    return {"raw": NO_SCRIPT}


class MockProvider:
    def __init__(self, latency_ms: int = 0) -> None:
        self.latency_ms = latency_ms

    def chat(
        self, *, messages: list[Message], tools: list[dict[str, Any]], purpose: str
    ) -> LlmReply:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000)
        question = _question(messages)
        if purpose == "router":
            call = {
                "id": "call_router",
                "type": "function",
                "function": {
                    "name": "select_workflow",
                    "arguments": json.dumps({"workflow": route(question)}),
                },
            }
            message: Message = {"role": "assistant", "content": None, "tool_calls": [call]}
            return LlmReply(message=message, model="mock/router", latency_ms=self.latency_ms)

        index = sum(1 for m in messages if m.get("role") == "assistant")
        step = script_step(question, index)
        if "tool_calls" in step:
            calls = [
                {
                    "id": f"call_{index}_{j}",
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c.get("arguments", {})),
                    },
                }
                for j, c in enumerate(step["tool_calls"])
            ]
            message = {"role": "assistant", "content": None, "tool_calls": calls}
        elif "final" in step:
            message = {"role": "assistant", "content": json.dumps(step["final"])}
        else:
            message = {"role": "assistant", "content": str(step.get("raw", NO_SCRIPT))}
        return LlmReply(message=message, model="mock/workflow", latency_ms=self.latency_ms)
