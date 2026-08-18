"""Interactive one-time setup: sign in to Garmin, then configure Claude Desktop.

Login lives here rather than in a tool because Garmin's two-factor step needs a
real prompt. Once this has run, the server starts from the saved tokens alone.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any

from .session import token_path

SERVER_KEY = "garmin"

MACOS_CONFIG = (
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
)
WINDOWS_CONFIG = (
    Path(os.environ.get("APPDATA", Path.home())) / "Claude" / "claude_desktop_config.json"
)
LINUX_CONFIG = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return MACOS_CONFIG
    if system == "Windows":
        return WINDOWS_CONFIG
    return LINUX_CONFIG


def say(message: str = "") -> None:
    print(message, flush=True)


def rule() -> None:
    say("-" * 52)


def ask_mfa_code() -> str:
    say()
    say("Garmin has sent you a security code by email or text message.")
    while True:
        code = input("Enter the code: ").strip()
        if code:
            return code
        say("The code cannot be empty. Please try again.")


def sign_in() -> str:
    """Log in to Garmin and save the tokens. Returns the account holder's name."""
    from garminconnect import Garmin
    from garminconnect.exceptions import (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )

    say("Step 1 of 2: connect your Garmin account")
    say()
    say("Your password is used once to sign in and is never saved to disk.")
    say("Only Garmin's access tokens are stored, in your home folder.")
    say()

    email = input("Garmin email address: ").strip()
    if not email:
        raise SystemExit("No email address given. Nothing was changed.")
    password = getpass("Garmin password (typing stays hidden): ")
    if not password:
        raise SystemExit("No password given. Nothing was changed.")

    say()
    say("Signing in to Garmin Connect...")

    store = token_path()
    api = Garmin(email=email, password=password, prompt_mfa=ask_mfa_code)
    try:
        api.login(tokenstore=str(store))
    except GarminConnectAuthenticationError as exc:
        raise SystemExit(
            f"\nGarmin rejected that sign-in.\n\n{exc}\n\n"
            "Check the email and password at https://connect.garmin.com and run this again."
        ) from exc
    except GarminConnectTooManyRequestsError as exc:
        raise SystemExit(
            "\nGarmin is temporarily blocking sign-in attempts because there have "
            "been too many. Please wait about 15 minutes and run this again."
        ) from exc
    except GarminConnectConnectionError as exc:
        raise SystemExit(
            f"\nCould not reach Garmin Connect. Check your internet connection.\n\nDetails: {exc}"
        ) from exc

    return api.get_full_name() or email


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return content if isinstance(content, dict) else {}


def write_config(path: Path) -> tuple[Path | None, bool]:
    """Add this server to the Claude Desktop config, preserving everything else.

    Returns the backup path (if one was made) and whether an existing entry was
    replaced.
    """
    config = load_config(path)
    backup: Path | None = None
    if path.exists():
        backup = path.with_suffix(f".json.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)

    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    replaced = SERVER_KEY in servers

    # Calling the interpreter with -m avoids depending on the user's PATH,
    # which Claude Desktop does not inherit from the shell.
    servers[SERVER_KEY] = {
        "command": sys.executable,
        "args": ["-m", "garmin_mcp"],
    }
    config["mcpServers"] = servers

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return backup, replaced


def main() -> None:
    say()
    rule()
    say("  Garmin Connect for Claude -- setup")
    rule()
    say()

    name = sign_in()

    say()
    say(f"  Signed in as {name}")
    say(f"  Access tokens saved to {token_path()}")
    say()

    say("Step 2 of 2: tell Claude Desktop about it")
    say()
    target = config_path()
    try:
        backup, replaced = write_config(target)
    except OSError as exc:
        raise SystemExit(
            f"\nCould not write the Claude Desktop settings file at:\n  {target}\n\nDetails: {exc}"
        ) from exc

    say(f"  {'Updated' if replaced else 'Added'} the Garmin connection in {target}")
    if backup:
        say(f"  Your previous settings were backed up to {backup.name}")

    say()
    rule()
    say("  All done.")
    rule()
    say()
    say("Now quit Claude Desktop completely and open it again.")
    say("On a Mac, press Cmd+Q to quit -- closing the window is not enough.")
    say()
    say("Then try asking Claude:")
    say('  "How did I sleep last night?"')
    say('  "Show me my runs from the last two weeks."')
    say('  "What is my training readiness today?"')
    say()


if __name__ == "__main__":
    main()
