"""The MCP server exposed to Claude Desktop."""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from . import __version__
from .tools import activities, health, workouts

INSTRUCTIONS = """\
Read and record Garmin Connect data for the person you are talking to.

Guidance:
- Dates are everyday phrases. Pass "today", "yesterday", "last 7 days",
  "this month" or "2026-08-18" straight through; do not convert them first.
- To discuss a specific activity, call list_activities or get_last_activity
  first to get its id, then get_activity_details.
- Tools return finished text. Relay the numbers as given and do not invent
  values for anything a tool left out -- a missing metric means the watch did
  not record it.
- If a tool replies that the account is not connected, tell the user to run
  the command it names in their Terminal. Do not try to log in yourself.
- Only log_weight, log_hydration, create_workout and schedule_workout change
  anything. Confirm with the user before calling those. Nothing can delete data.
"""


def build_server() -> MCPServer:
    server = MCPServer(
        name="garmin-connect",
        version=__version__,
        instructions=INSTRUCTIONS,
    )
    health.register(server)
    activities.register(server)
    workouts.register(server)
    return server


def main() -> None:
    # stdio transport owns stdout, so every log line must go to stderr or it
    # corrupts the JSON-RPC stream.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    build_server().run()


if __name__ == "__main__":
    main()
