"""The one interface every LLM call goes through (PRD A6)."""

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]

Message = dict[str, Any]


class LlmError(Exception):
    """The model could not be reached or returned something unusable."""


@dataclass
class LlmReply:
    message: Message
    model: str
    tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class LlmProvider(Protocol):
    def chat(
        self, *, messages: list[Message], tools: list[dict[str, Any]], purpose: str
    ) -> LlmReply: ...


@lru_cache(maxsize=1)
def model_config() -> dict[str, Any]:
    with (REPO_ROOT / "config" / "models.toml").open("rb") as fh:
        return tomllib.load(fh)


def get_provider(workflow_model: str | None = None, latency_ms: int | None = None) -> LlmProvider:
    """The provider for LLM_MODE, optionally pinned to another workflow model (evals)."""
    from launchledger.settings import get_settings

    settings = get_settings()
    if workflow_model == "mock" or (workflow_model is None and settings.llm_mode == "mock"):
        from launchledger.llm.mock import MockProvider

        return MockProvider(settings.mock_latency_ms if latency_ms is None else latency_ms)
    from launchledger.llm.openrouter import OpenRouterProvider

    if not settings.openrouter_api_key:
        raise LlmError("OPENROUTER_API_KEY is not set")
    return OpenRouterProvider(
        api_key=settings.openrouter_api_key,
        router_model=settings.router_model or (workflow_model or settings.workflow_model),
        workflow_model=workflow_model or settings.workflow_model,
    )
