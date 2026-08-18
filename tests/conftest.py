"""Shared fixtures.

Garmin Connect is an external service, so it is faked here; everything else
(the MCP call path, formatting, date parsing) runs for real.
"""

from typing import Any

import pytest

from garmin_mcp import session as session_module
from garmin_mcp.server import build_server


class FakeSession:
    """Stands in for GarminSession, returning canned Garmin payloads."""

    def __init__(self, responses: dict[str, Any] | None = None, unit: str = "metric") -> None:
        self.responses = responses or {}
        self.unit = unit
        self.calls: list[tuple[str, tuple, dict]] = []

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((method, args, kwargs))
        if method not in self.responses:
            raise AssertionError(f"Unexpected Garmin call: {method}")
        value = self.responses[method]
        if isinstance(value, Exception):
            raise value
        return value

    async def unit_system(self) -> str:
        return self.unit

    async def api(self) -> Any:  # pragma: no cover - not used by the tools
        raise NotImplementedError


@pytest.fixture
def server():
    return build_server()


@pytest.fixture
def fake_garmin(monkeypatch):
    """Install a FakeSession and return a function to load responses into it."""

    holder: dict[str, FakeSession] = {}

    def install(responses: dict[str, Any] | None = None, unit: str = "metric") -> FakeSession:
        fake = FakeSession(responses, unit)
        monkeypatch.setattr(session_module, "session", fake)
        holder["fake"] = fake
        return fake

    install()
    return install


async def run_tool(server, tool_name: str, /, **arguments) -> str:
    """Call a tool the way a client would and return its text.

    Positional-only so a tool argument called ``name`` cannot collide with it.
    """
    result = await server.call_tool(tool_name, arguments)
    blocks = getattr(result, "content", None) or []
    return "\n".join(getattr(block, "text", "") for block in blocks)
