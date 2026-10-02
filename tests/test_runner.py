"""IT-09: the model never sees an unchecked tool response; Declined beats Answered."""

import json
from typing import Any

import pytest

from launchledger.assistant import runner
from launchledger.contracts.check import ContractResult, Violation
from launchledger.llm.provider import LlmReply, Message


class RecordingProvider:
    """Calls get_serial once, then answers. Records every message list it was sent."""

    def __init__(self) -> None:
        self.seen: list[list[Message]] = []

    def chat(
        self, *, messages: list[Message], tools: list[dict[str, Any]], purpose: str
    ) -> LlmReply:
        self.seen.append([dict(m) for m in messages])
        if not any(m.get("role") == "assistant" for m in messages):
            call = {
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "get_serial",
                    "arguments": json.dumps({"serial_number": "SN-0042"}),
                },
            }
            return LlmReply({"role": "assistant", "content": None, "tool_calls": [call]}, "rec")
        final = {
            "answer": "SN-0042 is IN_BUILD.",
            "claims": [
                {
                    "text": "x",
                    "facts": [
                        {
                            "system": "MES",
                            "record_type": "serial",
                            "record_id": "SN-0042",
                            "field": "status",
                            "value": "IN_BUILD",
                        }
                    ],
                }
            ],
            "caveats": [],
        }
        return LlmReply({"role": "assistant", "content": json.dumps(final)}, "rec")


def test_it_09_failed_contract_never_reaches_the_model(
    clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*args: Any, **kwargs: Any) -> ContractResult:
        return ContractResult(
            "mes",
            "/serials/{serial_number}",
            [Violation("status", "enum", "status unexpected value X")],
        )

    monkeypatch.setattr(runner, "check_response", failing)
    provider = RecordingProvider()
    result = runner.run_question("anything", "serial_status", provider=provider)
    assert result.decision == "declined"
    assert "MES" in result.reason and "status" in result.reason
    assert len(provider.seen) == 1  # the model was never called with the tool result
    assert not any(m.get("role") == "tool" for msgs in provider.seen for m in msgs)


def test_checked_response_reaches_the_model_and_answers(clean: None) -> None:
    provider = RecordingProvider()
    result = runner.run_question("anything", "serial_status", provider=provider)
    assert result.decision == "answered"
    tool_messages = [m for m in provider.seen[-1] if m.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"])["status"] == "IN_BUILD"
