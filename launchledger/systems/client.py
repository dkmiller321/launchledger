"""The HTTP client everything uses to reach /systems/*.

The server calls itself over real HTTP (SYSTEMS_BASE_URL). The CLI swaps in an in-process
client so `ll eval run` works without a running server.
"""

from collections.abc import Callable

import httpx

from launchledger.settings import get_settings

_override: Callable[[], httpx.Client] | None = None
_shared: httpx.Client | None = None


def use_client_factory(factory: Callable[[], httpx.Client]) -> None:
    global _override, _shared
    _override = factory
    _shared = None


def systems_client() -> httpx.Client:
    global _shared
    if _shared is None:
        if _override is not None:
            _shared = _override()
        else:
            _shared = httpx.Client(base_url=get_settings().systems_base_url, timeout=15)
    return _shared
