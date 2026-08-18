"""One shared, lazily-authenticated Garmin Connect client.

``garminconnect`` is entirely synchronous, so every call is pushed onto a
worker thread; otherwise a single slow Garmin request would stall the whole
MCP server. Login happens once, from the token file written by
``garmin-mcp-setup`` -- never from inside a tool call, because Garmin's
two-factor step needs an interactive prompt that MCP cannot provide.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
from garminconnect import Garmin
from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .dates import DateParseError

SETUP_COMMAND = "garmin-mcp-setup"

NOT_CONNECTED = (
    "Your Garmin account is not connected yet.\n\n"
    "To fix this, open the Terminal app on your Mac and run this command:\n"
    f"    {SETUP_COMMAND}\n\n"
    "It asks for your Garmin email, your password, and the security code Garmin "
    "sends you. Once it finishes, come back and ask me again."
)

SESSION_EXPIRED = (
    "Your Garmin login has expired and needs to be renewed.\n\n"
    "Open the Terminal app on your Mac and run this command:\n"
    f"    {SETUP_COMMAND}\n\n"
    "That signs you back in. Your data is untouched."
)

RATE_LIMITED = (
    "Garmin is temporarily refusing requests because too many were made in a "
    "short time. Please wait a few minutes and ask again."
)


class GarminError(RuntimeError):
    """A problem that should be explained to the user in plain language."""


def token_path() -> Path:
    """Where the Garmin OAuth tokens live."""
    override = os.environ.get("GARMINTOKENS")
    return Path(override).expanduser() if override else Path.home() / ".garminconnect"


def _login() -> Garmin:
    store = token_path()
    if not store.exists():
        raise GarminError(NOT_CONNECTED)
    api = Garmin()
    try:
        api.login(tokenstore=str(store))
    except GarminConnectAuthenticationError as exc:
        raise GarminError(SESSION_EXPIRED) from exc
    except GarminConnectTooManyRequestsError as exc:
        raise GarminError(RATE_LIMITED) from exc
    except FileNotFoundError as exc:
        raise GarminError(NOT_CONNECTED) from exc
    except GarminConnectConnectionError as exc:
        raise GarminError(
            "Could not reach Garmin Connect. Please check your internet "
            f"connection and try again.\n\nDetails: {exc}"
        ) from exc
    return api


class GarminSession:
    """Holds the authenticated client and serialises the first login."""

    def __init__(self) -> None:
        self._api: Garmin | None = None
        self._lock = anyio.Lock()

    async def api(self) -> Garmin:
        if self._api is not None:
            return self._api
        async with self._lock:
            # Another task may have logged in while we waited for the lock.
            if self._api is None:
                self._api = await anyio.to_thread.run_sync(_login)
        return self._api

    def reset(self) -> None:
        """Drop the cached client so the next call logs in again."""
        self._api = None

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        api = await self.api()
        func = getattr(api, method, None)
        if func is None:  # pragma: no cover - guards against library drift
            raise GarminError(f"This version of garminconnect has no '{method}' method.")
        try:
            return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))
        except GarminConnectAuthenticationError as exc:
            # Tokens were accepted at login but rejected now; force a re-login next time.
            self.reset()
            raise GarminError(SESSION_EXPIRED) from exc
        except GarminConnectTooManyRequestsError as exc:
            raise GarminError(RATE_LIMITED) from exc
        except GarminConnectConnectionError as exc:
            raise GarminError(f"Garmin Connect returned an error: {exc}") from exc
        except ValueError as exc:
            raise GarminError(f"That request was not valid: {exc}") from exc

    async def unit_system(self) -> str:
        """``metric`` or ``statute_us``, following the user's Garmin setting."""
        try:
            api = await self.api()
        except GarminError:
            return "metric"
        return api.get_unit_system() or "metric"


session = GarminSession()


async def call(method: str, *args: Any, **kwargs: Any) -> Any:
    return await session.call(method, *args, **kwargs)


async def metric() -> bool:
    from .format import is_metric

    return is_metric(await session.unit_system())


def friendly(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return expected failures as readable text instead of raising.

    A non-technical user is far better served by "run this command" than by a
    stack trace, and Claude relays a returned string verbatim.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except (GarminError, DateParseError) as exc:
            return str(exc)

    return wrapper
