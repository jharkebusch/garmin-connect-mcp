# Garmin Connect for Claude

Ask Claude about your Garmin data in plain English.

> *"How did I sleep last night?"*
> *"Show me my runs from the last two weeks."*
> *"Am I recovered enough to train hard today?"*
> *"How much did I run last month compared to the month before?"*

This connects your Garmin Connect account to the Claude Desktop app, so Claude
can read your workouts, sleep, heart rate and other health data and talk about
them with you.

**You do not need to know how to code to use this.** The installer asks you a
couple of questions and does the rest.

---

## What you need

- A Mac
- The [Claude Desktop app](https://claude.ai/download)
- A Garmin Connect account with a Garmin watch or device

---

## Install

Open the **Terminal** app on your Mac. (Press `Cmd + Space`, type `Terminal`,
press Enter.)

Copy this line, paste it into the Terminal window, and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/jharkebusch/garmin-connect-mcp/main/install.sh | bash
```

It will:

1. Set up a private, self-contained Python environment (your Mac's own Python
   is not touched)
2. Ask for your Garmin email and password, and the security code Garmin sends
   you
3. Configure Claude Desktop for you

When it finishes, **quit Claude Desktop completely** with `Cmd + Q` and open it
again. Closing the window is not enough.

Then just ask Claude about your Garmin data.

---

## What Claude can do

### Health and wellness

| Ask about | Tool |
| --- | --- |
| A day at a glance | `get_daily_summary` |
| Sleep, stages and sleep score | `get_sleep` |
| Daily step counts and totals | `get_steps` |
| Resting, low and high heart rate | `get_heart_rate` |
| Heart rate variability and recovery | `get_hrv` |
| Stress through the day | `get_stress` |
| Body Battery charge and drain | `get_body_battery` |
| Whether you are ready to train hard | `get_training_readiness` |
| VO2 max, fitness age, training status | `get_vo2max_and_fitness` |
| Body weight over time | `get_weight_history` |

### Workouts and activities

| Ask about | Tool |
| --- | --- |
| Activities in a period | `list_activities` |
| Activities on one day | `get_activities_on_day` |
| Everything about one activity | `get_activity_details` |
| Your most recent activity | `get_last_activity` |
| Kilometre or mile splits | `get_activity_splits` |
| Totals over a period | `get_date_range_summary` |
| Personal bests | `get_personal_records` |
| Your Garmin devices | `get_devices` |
| Saved workout plans | `list_workouts`, `get_workout` |
| Your training calendar | `get_scheduled_workouts` |

### Recording things (these change your Garmin account)

| Ask Claude to | Tool |
| --- | --- |
| Log a body weight | `log_weight` |
| Log water you drank | `log_hydration` |
| Build a workout plan | `create_workout` |
| Put a workout on your calendar | `schedule_workout` |

**Nothing can delete your data.** There is no tool that removes an activity, a
workout or a weigh-in, so a mistaken request cannot destroy your training
history.

---

## Dates in plain English

Every tool understands everyday phrases, so you can just talk normally:

`today` · `yesterday` · `last night` · `3 days ago` · `last 7 days` ·
`this week` · `last month` · `2026-08-18` · `2026-08-01 to 2026-08-18`

---

## Your privacy and security

- **Your password is never saved.** It is used once during setup to sign in,
  and then discarded.
- **Only Garmin's access tokens are stored**, in `~/.garminconnect`, as a file
  only your user account can read (`0600`, inside a `0700` folder).
- **Nothing is sent anywhere except Garmin.** There is no telemetry, no
  analytics and no third-party server. Your data goes from Garmin to your own
  Mac and nowhere else.
- **Everything runs locally** on your machine.
- Your Garmin data only reaches Anthropic if Claude includes it in a reply, the
  same as anything else you type into Claude.

---

## Updating

Run the same install command again. It updates in place and keeps you signed in.

## If you need to sign in again

Garmin sessions renew themselves and rarely expire. If Claude ever says your
login has expired, run this in Terminal:

```bash
garmin-mcp-setup
```

If your Terminal does not recognise that command, use the full path:

```bash
~/.garmin-mcp/bin/garmin-mcp-setup
```

## Uninstalling

```bash
rm -rf ~/.garmin-mcp ~/.garminconnect ~/.local/bin/garmin-mcp-setup
```

Then remove the `"garmin"` entry from the `mcpServers` section of
`~/Library/Application Support/Claude/claude_desktop_config.json`.

---

## Troubleshooting

**Claude does not see the Garmin tools.**
Quit Claude Desktop fully with `Cmd + Q` and reopen it. Closing the window
leaves it running in the background.

**"Your Garmin account is not connected yet."**
Run `garmin-mcp-setup` in Terminal.

**"Too many requests."**
Garmin rate-limits sign-in attempts. Wait about 15 minutes.

**A number is missing from a reply.**
Missing means your device did not record it. Some metrics (HRV, Body Battery,
training readiness) need a compatible Garmin watch worn overnight. The tools
leave a metric out rather than guessing a value.

---

## For developers

```bash
git clone https://github.com/jharkebusch/garmin-connect-mcp.git
cd garmin-connect-mcp
uv venv --python 3.12 && VIRTUAL_ENV=.venv uv pip install -e ".[dev]"
VIRTUAL_ENV=.venv uv run pytest
```

Layout:

- `src/garmin_mcp/server.py` — MCP server and tool registration
- `src/garmin_mcp/session.py` — authenticated Garmin client, thread offload
- `src/garmin_mcp/dates.py` — plain-English date parsing
- `src/garmin_mcp/format.py` — trims Garmin JSON into readable text
- `src/garmin_mcp/tools/` — the tools themselves
- `src/garmin_mcp/setup_cli.py` — interactive login and Claude configuration

Two design notes:

- `garminconnect` is synchronous, so every call is pushed to a worker thread.
  Otherwise one slow Garmin request stalls the whole server.
- Login cannot happen inside a tool call, because Garmin's two-factor step
  needs an interactive prompt. Setup writes a token file; the server only ever
  reads it.

---

## A caveat worth knowing

Garmin does not publish a public API. This uses the same interface the Garmin
mobile app uses, via the [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
library. It works well, but Garmin can change that interface at any time and
temporarily break third-party tools. If that happens, re-running the installer
picks up the fix once the underlying library ships one.

This project is not affiliated with, endorsed by, or connected to Garmin Ltd.
Use it with your own account and your own data.

## Licence

MIT — see [LICENSE](LICENSE).
