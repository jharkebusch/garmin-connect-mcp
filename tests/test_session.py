from pathlib import Path

import pytest
from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from garmin_mcp import session as session_module
from garmin_mcp.dates import DateParseError
from garmin_mcp.session import (
    NOT_CONNECTED,
    RATE_LIMITED,
    SESSION_EXPIRED,
    GarminError,
    GarminSession,
    friendly,
    token_path,
)


class TestTokenPath:
    def test_defaults_to_the_home_folder(self, monkeypatch):
        monkeypatch.delenv("GARMINTOKENS", raising=False)
        assert token_path() == Path.home() / ".garminconnect"

    def test_environment_variable_wins(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "tokens"))
        assert token_path() == tmp_path / "tokens"


class TestLogin:
    def test_missing_token_folder_tells_the_user_to_run_setup(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GARMINTOKENS", str(tmp_path / "absent"))
        with pytest.raises(GarminError) as excinfo:
            session_module._login()
        assert str(excinfo.value) == NOT_CONNECTED
        assert "garmin-mcp-setup" in str(excinfo.value)

    def test_rejected_tokens_ask_for_a_fresh_sign_in(self, monkeypatch, tmp_path):
        store = tmp_path / "tokens"
        store.mkdir()
        monkeypatch.setenv("GARMINTOKENS", str(store))

        class Boom:
            def login(self, tokenstore=None):
                raise GarminConnectAuthenticationError("nope")

        monkeypatch.setattr(session_module, "Garmin", lambda *a, **k: Boom())
        with pytest.raises(GarminError) as excinfo:
            session_module._login()
        assert str(excinfo.value) == SESSION_EXPIRED


class TestSessionCall:
    async def test_rate_limiting_is_explained_in_plain_language(self, monkeypatch):
        class Api:
            def get_thing(self):
                raise GarminConnectTooManyRequestsError("429")

        current = GarminSession()
        current._api = Api()
        with pytest.raises(GarminError) as excinfo:
            await current.call("get_thing")
        assert str(excinfo.value) == RATE_LIMITED

    async def test_expired_tokens_clear_the_cached_client(self, monkeypatch):
        class Api:
            def get_thing(self):
                raise GarminConnectAuthenticationError("expired")

        current = GarminSession()
        current._api = Api()
        with pytest.raises(GarminError):
            await current.call("get_thing")
        # Without this, every later call keeps reusing the dead client.
        assert current._api is None

    async def test_unknown_method_is_reported_not_crashed(self):
        current = GarminSession()
        current._api = object()
        with pytest.raises(GarminError, match="no 'get_missing' method"):
            await current.call("get_missing")

    async def test_successful_call_passes_arguments_through(self):
        class Api:
            def get_thing(self, day, limit=1):
                return {"day": day, "limit": limit}

        current = GarminSession()
        current._api = Api()
        assert await current.call("get_thing", "2026-08-18", limit=5) == {
            "day": "2026-08-18",
            "limit": 5,
        }

    async def test_unit_system_falls_back_to_metric_when_not_connected(self, monkeypatch):
        current = GarminSession()

        async def boom():
            raise GarminError("nope")

        monkeypatch.setattr(current, "api", boom)
        assert await current.unit_system() == "metric"


class TestFriendly:
    async def test_returns_garmin_errors_as_readable_text(self):
        @friendly
        async def tool():
            raise GarminError("Please run setup.")

        assert await tool() == "Please run setup."

    async def test_returns_date_errors_as_readable_text(self):
        @friendly
        async def tool():
            raise DateParseError("Bad date.")

        assert await tool() == "Bad date."

    async def test_lets_unexpected_errors_through(self):
        @friendly
        async def tool():
            raise ZeroDivisionError("bug")

        with pytest.raises(ZeroDivisionError):
            await tool()

    async def test_preserves_the_signature_so_mcp_can_build_a_schema(self):
        import inspect

        @friendly
        async def tool(day: str = "today", count: int = 1) -> str:
            return "ok"

        signature = inspect.signature(tool)
        assert list(signature.parameters) == ["day", "count"]
        assert signature.parameters["count"].annotation is int
