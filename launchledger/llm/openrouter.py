"""OpenRouter chat completions with tool calling (OpenAI-compatible; no SDK)."""

import time
from typing import Any

import httpx

from launchledger.llm.provider import LlmError, LlmReply, Message, model_config

URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    def __init__(self, *, api_key: str, router_model: str, workflow_model: str) -> None:
        self.api_key = api_key
        self.router_model = router_model
        self.workflow_model = workflow_model
        cfg = model_config()
        self.defaults: dict[str, Any] = cfg.get("defaults", {})
        self.router_cfg: dict[str, Any] = cfg.get("router", {})
        self.client = httpx.Client(timeout=float(self.defaults.get("timeout_s", 60)))

    def chat(
        self, *, messages: list[Message], tools: list[dict[str, Any]], purpose: str
    ) -> LlmReply:
        is_router = purpose == "router"
        model = self.router_model if is_router else self.workflow_model
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.defaults.get("temperature", 0),
            "max_tokens": (self.router_cfg if is_router else self.defaults).get("max_tokens", 1500),
            "usage": {"include": True},
        }
        if tools:
            body["tools"] = tools
        if is_router:
            body["tool_choice"] = {"type": "function", "function": {"name": "select_workflow"}}
        headers = {"Authorization": f"Bearer {self.api_key}", "X-Title": "LaunchLedger"}

        started = time.monotonic()
        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                response = self.client.post(URL, json=body, headers=headers)
            except httpx.HTTPError as exc:
                if attempt == 1:
                    raise LlmError(f"OpenRouter unreachable: {exc}") from exc
                continue
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt == 0:
                time.sleep(1.0)
                continue
            break
        assert response is not None
        if response.status_code != 200:
            raise LlmError(f"OpenRouter HTTP {response.status_code}: {response.text[:200]}")
        data = response.json()
        try:
            message: Message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise LlmError(f"OpenRouter returned no choices: {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        return LlmReply(
            message={k: v for k, v in message.items() if k in ("role", "content", "tool_calls")},
            model=str(data.get("model", model)),
            tokens=int(usage.get("total_tokens") or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
            cost_usd=float(usage.get("cost") or 0.0),
            raw={"id": data.get("id")},
        )
