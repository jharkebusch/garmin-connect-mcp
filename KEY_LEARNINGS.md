# Key Learnings — Garmin Connect MCP

Project-specific bugs, corrections, and confirmed patterns.

---

## Format

### [YYYY-MM-DD] Category: Short title
**Wrong:** What was done incorrectly.
**Correct:** What the right approach is.
**Why:** Reason given or inferred.

Categories: `bug` | `pattern` | `preference` | `security`

---

## Entries

### [2026-08-18] pattern: garth is dead — garminconnect >= 0.3.10 replaced it
**Wrong:** Assuming Garmin auth still runs through `garth`, the library nearly every
Garmin tool depended on.
**Correct:** `garth` was deprecated after Garmin added TLS fingerprinting and Cloudflare
protection, which broke its mobile auth flow (429s). `garminconnect` 0.3.10 dropped it
entirely for `curl_cffi` (TLS impersonation) + `ua-generator`, and requires Python >= 3.12.
Pin `garminconnect>=0.3.10`.
**Why:** Anything built on the pre-0.3.10 stack cannot log in at all.

### [2026-08-18] pattern: `FastMCP` is `MCPServer` in mcp 2.0
**Wrong:** `from mcp.server.fastmcp import FastMCP`.
**Correct:** `from mcp.server.mcpserver import MCPServer`. The `.tool()` decorator and
`.run()` behave the same; `Tool.inputSchema` is now `Tool.input_schema`.
**Why:** mcp 2.0.0 renamed the ergonomic server API.

### [2026-08-18] pattern: MFA cannot happen inside an MCP tool call
**Wrong:** Exposing a `login` tool that prompts for the 2FA code.
**Correct:** `resume_login()` needs the *same* client object that began the login, and a
tool call has no way to prompt mid-flight. Login belongs in a separate interactive CLI
(`garmin-mcp-setup`) that writes a token store; the server only ever loads tokens.
Passing `prompt_mfa=` to `Garmin()` also makes `login()` persist tokens automatically,
whereas `return_on_mfa=True` returns early and never dumps them.
**Why:** Any in-tool login design is unimplementable, not merely awkward.

### [2026-08-18] pattern: `curl | bash` installers must read prompts from /dev/tty
**Wrong:** Calling an interactive setup command at the end of a piped installer.
**Correct:** With `curl ... | bash`, stdin *is* the script, so prompts get EOF or eat the
rest of the script. Redirect explicitly: `garmin-mcp-setup < /dev/tty`, with a printed
fallback command when `/dev/tty` is unreadable.
**Why:** Silent, confusing failure for exactly the non-technical users the installer targets.

### [2026-08-18] pattern: shape Garmin JSON before it reaches the model
**Wrong:** Returning raw endpoint payloads from tools.
**Correct:** Garmin returns huge nested blobs with per-second sample arrays. Every tool
renders a compact `label: value` report, drops missing fields rather than printing them as
zero, and falls back to pruned JSON only when no known field matched.
**Why:** Raw payloads blow the context window, read badly, and a printed `0` for a metric
the watch never recorded is worse than an omission — it invites false conclusions.

### [2026-08-18] bug: don't instantiate a pydantic workout model to read its defaults
**Wrong:** `model().sportType` to get a sport's default type dict.
**Correct:** `model.model_fields["sportType"].default_factory()`. `BaseWorkout` has required
fields (`workoutName`, `estimatedDurationInSecs`, `workoutSegments`), so a bare `model()`
raises `ValidationError`.
**Why:** Broke every `create_workout` call; caught only because tests exercised the builder.

### [2026-08-18] pattern: positional-only params in test helpers
**Wrong:** `async def run_tool(server, name, **arguments)`.
**Correct:** `async def run_tool(server, tool_name, /, **arguments)`. Otherwise a tool whose
own argument is called `name` collides with the helper's parameter.
**Why:** `TypeError: got multiple values for argument 'name'` across every `create_workout` test.

### [2026-08-18] pattern: garminconnect is synchronous
**Wrong:** Calling library methods directly from async tool bodies.
**Correct:** Push every call through `anyio.to_thread.run_sync`.
**Why:** One slow Garmin request otherwise stalls the whole MCP event loop.

### [2026-08-18] security: token storage is already handled by the library
**Wrong:** Re-implementing permissions on the token file.
**Correct:** `client.dump()` already writes `0600` inside a `0700` directory, atomically,
with `O_NOFOLLOW`. Don't duplicate it. Never store the password — it is used once at setup.
**Why:** Duplicated hardening drifts out of sync with the upstream fix (GHSA-wjhr-76vg-2hvc).
