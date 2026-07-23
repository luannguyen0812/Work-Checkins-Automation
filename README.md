# Intern Check-In Bot & Dashboard

A production Telegram bot + Flask admin dashboard built to automate daily attendance tracking for a 43-person intern cohort. The bot monitors a Telegram group, parses check-in messages, scores attendance risk, and delivers weekly Excel reports — all backed by Google Sheets as a live database.

---

## What it does

| Feature | Detail |
|---|---|
| **Telegram bot** | Watches the intern group 24/7, captures check-in messages matching a regex, deduplicates, flags late arrivals |
| **Auto-registration** | First message from an unregistered intern fuzzy-matches their name to the ROSTER sheet and links their Telegram ID automatically |
| **Scheduled reminders** | Morning (9:30 AM), midday (11:30 AM), and pre-cutoff (5:45 PM) nudges in the group chat every weekday |
| **Risk scoring** | Weekly composite score from Weighted Attendance Rate, Recent Attendance Rate, Consecutive Absence Streak, and Late Check-In Rate |
| **Weekly report** | Friday 6 PM auto-generated 7-sheet Excel workbook with charts, heatmaps, streaks, and an optional Claude-generated executive narrative |
| **Admin dashboard** | Flask web app with login, dark UI, charts, heatmap, risk cards, audit log, and config sliders |
| **Google Sheets backend** | ROSTER, CONFIG, ESCALATIONS, and per-week CHECKINS tabs — no SQL database required |

---

## Architecture

```
Telegram Group
     │  (messages)
     ▼
bot/handlers.py  ──────────────────────────────────────────┐
     │  parse & validate check-in regex                    │
     │  auto-register unknown interns (fuzzy match)        │
     ▼                                                      │
datastore/sheets.py  ←──── Google Sheets API               │
  ROSTER tab        (gspread + service account)            │
  CHECKINS_YYYY_WW                                         │
  CONFIG                                                   │
  ESCALATIONS                                              │
     │                                                      │
     ├── bot/scheduler.py (APScheduler cron jobs)  ────────┘
     │     9:30  morning reminder
     │    11:30  second reminder
     │    17:45  pre-cutoff alert
     │    18:00 Fri  weekly report → Excel → Telegram DM
     │     2:00 Sun  data retention cleanup
     │
     └── admin/ (Flask + Gunicorn on port 5050)
           ├── Dashboard  — today's check-ins, donut chart
           ├── Interns    — roster with attendance bars, risk badges
           ├── Risk Report — RED/AMBER cards, full breakdown table
           ├── Weekly Data — Mon–Fri heatmap, 8-week trend chart
           ├── Audit Log  — event feed with badge types
           └── Settings   — live config sliders, user management
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot runtime | `python-telegram-bot >= 21.0` (async) |
| Scheduling | `APScheduler 3.x` BackgroundScheduler |
| Sheets API | `gspread >= 6.0` + `google-auth` service account |
| Web framework | `Flask >= 3.0` + `Flask-Login` |
| WSGI server | `Gunicorn` (2 workers, 127.0.0.1:5050) |
| Data models | `Pydantic v2` |
| Charts | `Chart.js 4.4.3` (CDN) |
| Styling | `Tailwind CSS` (CDN) + CSS variable theme |
| Reports | `openpyxl` / `xlsxwriter` + `pandas` |
| AI narrative | `anthropic` SDK (optional, falls back to plain text) |
| Auth | `werkzeug.security` scrypt password hashing |
| Language | Python 3.13 |

---

## Project Structure

```
intern_checkin_bot/
├── main.py                   # Entry point: starts bot + scheduler
├── wsgi.py                   # Gunicorn entry: loads .env, starts Flask
├── config.py                 # Cached config loader
├── requirements.txt
│
├── bot/
│   ├── handlers.py           # handle_message(): parse, dedup, write check-in
│   ├── scheduler.py          # 5 cron jobs + async bridge
│   ├── templates.py          # Telegram message text templates
│   └── validator.py          # CHECKIN_REGEX (isolated to avoid import cycles)
│
├── datastore/
│   ├── models.py             # Pydantic models: Intern, CheckIn, Config, ...
│   ├── sheets.py             # All Google Sheets read/write operations
│   └── queries.py            # compute_all_risk_scores() (bulk pre-fetch)
│
├── report/
│   ├── generator.py          # 7-sheet Excel workbook + Claude narrative
│   └── charts.py             # Chart helpers
│
├── admin/
│   ├── api.py                # Flask routes + demo data seeding
│   ├── auth.py               # Login, session management, user CRUD
│   └── templates/
│       ├── base.html         # Dark sidebar layout (indigo theme)
│       ├── login.html
│       ├── dashboard.html    # Today's donut + missing interns
│       ├── interns.html      # Roster table with filter dropdowns
│       ├── risk_report.html  # RED/AMBER cards + breakdown table
│       ├── weekly_data.html  # Heatmap + 8-week trend line chart
│       ├── audit_log.html    # Timestamped event feed
│       └── settings.html     # Config sliders, user management
│
├── utils/
│   ├── time_utils.py         # EDT timezone helpers, is_late(), iso_week()
│   └── privacy.py            # Telegram-safe name scrubbing
│
├── deploy/
│   ├── setup.sh              # VPS provisioning script (Path A — sudo)
│   ├── intern-checkin-bot.service    # systemd unit
│   ├── intern-checkin-dashboard.service
│   ├── intern-checkin-parseschedules.service
│   ├── intern-checkin-parseschedules.timer
│   └── vps/                  # Path B — no-sudo deployment (see VPS Deployment below)
│       ├── start_bot.sh / start_dashboard.sh
│       ├── watchdog_bot.sh / watchdog_dashboard.sh
│       └── rotate_logs.sh    # logrotate substitute, no root needed
│
├── docs/
│   ├── ADMIN_GUIDE.md        # Quick start + API endpoint reference
│   └── INTERN_ONBOARDING.md  # Intern-facing doc + onboarding message template
│
├── scripts/                  # One-off operational scripts (not part of main app)
│   ├── backfill_checkins.py  # Manual check-in backfill for bot outages
│   ├── send_apology_dms.py   # DM apologies for incorrect nudges
│   ├── parse_schedules.py    # Sync schedule text from Team Members → ROSTER
│   ├── find_unregistered.py  # Identify interns not yet linked to Telegram
│   ├── check_dm_reach.py     # Test which interns the bot can DM
│   ├── count_active.py       # Count active interns vs. unregistered
│   └── ...                   # Other debug utilities
│
├── tests/
│   ├── test_handlers.py       # Check-in message parsing / rejection paths
│   ├── test_scheduler.py      # Weekly attendance band classification
│   ├── test_sheets_retry.py   # Sheets API retry/backoff behavior
│   ├── test_report.py         # Excel report generation
│   ├── test_risk_model.py     # WAR/RAR/CAS/LCR scoring
│   └── test_validator.py      # CHECKIN_REGEX matching
├── secrets/                  # ← NOT committed (*.json in .gitignore)
│   └── service-account.json  # Google service account private key
└── .env                      # ← NOT committed
```

---

## Setup

### Prerequisites

- Python 3.13 (not 3.15 alpha — Rust cryptography incompatibility)
- A Google Cloud project with Sheets API enabled
- A Telegram bot token from [@BotFather](https://t.me/botfather)
- The bot added to your intern Telegram group **as admin**, with Privacy Mode **OFF**

### 1. Clone and create virtualenv

```bash
git clone https://github.com/YOUR_USERNAME/intern-checkin-bot.git
cd intern-checkin-bot
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Sheets service account

1. Go to Google Cloud Console → IAM & Admin → Service Accounts
2. Create a service account → add key → download JSON
3. Place the JSON at `secrets/service-account.json`
4. Share your Google Sheet with the service account email (Editor role)

> **Important:** Never commit `secrets/service-account.json`. It is covered by `*.json` in `.gitignore`.

### 3. Configure environment

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_GROUP_CHAT_ID` | The intern group chat ID (negative number) |
| `ADMIN_TELEGRAM_USER_ID` | Your personal Telegram user ID — receives weekly reports |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | From the Sheet URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Absolute path to `secrets/service-account.json` |
| `SECRET_KEY` | Random secret for Flask sessions — **change before deploy** |
| `ANTHROPIC_API_KEY` | Optional — enables AI narrative in weekly reports |
| `CLAUDE_SUMMARY_MODEL` | Default: `claude-haiku-4-5-20251001` |
| `REPORT_RECIPIENT_EMAIL` | Where to email reports (optional, Telegram DM is primary) |

### 4. Google Sheets structure

Your spreadsheet needs these tabs:

| Tab | Purpose |
|---|---|
| `ROSTER` | One row per intern: `intern_id`, `full_name`, `email`, `role`, `department`, `telegram_user_id`, `active`, `start_date`, `end_date`, ... |
| `CONFIG` | Key-value pairs: `morning_reminder_time`, `risk_red_threshold`, `retention_weeks`, etc. |
| `ESCALATIONS` | Auto-created by bot for risk escalations |
| `CHECKINS_YYYY_WW` | Auto-created per ISO week when first check-in arrives |

A `setup_sheets.py` script is included to initialize empty tabs.

### 5. Run locally

**Bot only:**
```bash
source .venv/bin/activate
python main.py
```

**Dashboard only (dev):**
```bash
source .venv/bin/activate
flask --app admin.api run --port 5050 --debug
```

**Dashboard (production-like with Gunicorn):**
```bash
source .venv/bin/activate
gunicorn --workers 2 --bind 127.0.0.1:5050 wsgi:app
```

The dashboard is at `http://localhost:5050`. Default admin credentials are set on first launch — see `admin/auth.py:ensure_default_admin()`.

---

## Dashboard Features

### Interns page
- Full roster table pulled live from Google Sheets
- Attendance progress bars and risk level badges (GREEN / AMBER / RED)
- Filter by department, risk level, or free-text search
- Seeded demo data when bot is not yet active

### Risk Report
- **RED** interns: 2-column cards with attendance %, max consecutive gap, risk score progress bar, "Schedule 1:1" CTA
- **AMBER** interns: 3-column compact cards
- Full breakdown table with all metrics

### Weekly Data (Heatmap)
- Mon–Fri grid: ✓ (checked in) / ✗ (absent) / — (future)
- Attendance rate column with color coding (≥75% green, ≥55% yellow, <55% red)
- 8-week attendance trend line chart

### Settings
- Live sliders for Red/Amber risk thresholds (reads real CONFIG values)
- Time pickers for all 4 reminder/cutoff times
- Report day and time selectors
- Retention period dropdown
- "Trigger Weekly Report Now" and "Purge Old Data" actions
- Dashboard user management (add / remove accounts)

---

## Risk Scoring Formula

```
raw = (WAR × 0.40) + (RAR × 0.30) + ((1 − CAS/5) × 0.20) + ((1 − LCR) × 0.10)
score = clamp(raw, 0, 1)
```

| Component | Weight | Description |
|---|---|---|
| WAR | 40% | Weighted Attendance Rate (4-week rolling) |
| RAR | 30% | Recent Attendance Rate (last 2 weeks) |
| CAS | 20% | Consecutive Absence Streak (normalized to 5) |
| LCR | 10% | Late Check-In Rate |

Bands: `score ≥ amber_threshold` → GREEN, `score ≥ red_threshold` → AMBER, else RED.

> **Note:** the weekly report and Telegram DM summary band on raw **WAR%** directly (`< 70%` RED, `70–85%` AMBER, `≥ 85%` GREEN) rather than the composite risk score — this keeps the weekly narrative reading as "attendance this week" while the dashboard's Risk Report keeps the full composite score for longer-term risk triage.

---

## Bot Behaviour

### Check-in detection
The bot watches every group message (Privacy Mode must be OFF). `CHECKIN_REGEX` in `bot/validator.py` matches a wide range of phrasing — "I'm online", "checking in", "clocking in", "logged on", "available from 9-5", "GM" variants, apostrophe styles from phone keyboards (`'`/`'`/`'`) — and intentionally excludes bare words like "here" or "present" that produced false positives in regular group chatter.

### Auto-registration
When an unregistered intern sends any message, the bot fuzzy-matches their Telegram display name against the ROSTER's `full_name` column. On a confident match it writes their `telegram_user_id` back to the sheet — no manual step needed. If a message parses as a valid check-in but the sender can't be matched to any active intern, it's logged to an `UNMATCHED_CHECKINS` sheet tab (reason, Telegram name/username, message text) instead of silently dropped, so misses are auditable.

### Duplicate protection
Check-ins are deduplicated two ways: by Telegram `message_id` (protects against delivery retries) and by intern + work date (protects against someone checking in twice in one day being counted twice).

### Scheduled jobs (EDT / America/New_York)

| Time | Days | Job |
|---|---|---|
| 09:30 (configurable) | Mon–Fri | Morning reminder in group |
| 11:30 (configurable) | Mon–Fri | Second reminder |
| 17:45 (configurable) | Mon–Fri | Pre-cutoff alert |
| Configurable day/time (default Monday 09:30) | Weekly | Generate + DM weekly Excel report to admin |
| 02:00 | Sunday | Delete CHECKINS_* sheets older than `retention_weeks` |

Reminder times and the weekly report day/time are read from CONFIG and can be changed from the Settings page — the scheduler reschedules its live APScheduler jobs immediately after a config save, with no bot restart needed (`bot/scheduler.py:reschedule_time_jobs()`).

If the bot process starts after the morning reminder window has already passed (e.g. after a crash/restart), it schedules a one-time catch-up reminder 30 minutes later instead of silently skipping the day — but only if the reminder wasn't already sent, verified against today's log file. Jobs also carry a wide misfire grace window (1 hour, coalesced) so a slow tick from system load or sleep/wake doesn't drop a job entirely.

Skips weekends and US federal holidays automatically, including the fixed-date holidays (Juneteenth, July 4th, Veterans Day, Christmas, New Year's) observed on the adjacent weekday when they fall on a weekend — both the actual date and the observed date are excluded from scheduling and from attendance-day counts.

### Late flag
An intern is marked `late=True` when their check-in timestamp (EDT) is after their shift's scheduled end time, as defined in ROSTER's `schedule_json` column.

---

## Reliability & Production Hardening

These were added after running the bot live against a 43-person cohort and observing real failure modes:

- **Sheets API retry with backoff** — every read/write to Google Sheets goes through `_with_sheets_retry()`, which retries transient errors (connection resets, timeouts, HTTP 429/5xx) up to 4 times with exponential backoff. A momentary network blip no longer drops a check-in.
- **In-memory caching** — the roster and CONFIG are cached for 5 minutes (`_interns_cache`, `_config_cache`) to cut down on Sheets API calls during busy check-in windows; both caches are explicitly invalidated on writes (new registration, config save, deactivation).
- **Attendance counts actual check-ins over stale schedules** — if an intern's stored `schedule_json` doesn't yet reflect a real change (new hire, shift swap), a genuine check-in on an "unscheduled" day still counts as presence rather than being silently excluded from their attendance rate.
- **Structured logging on every check-in decision** — accepted, rejected (wrong chat, unrecognised user, out-of-range date, duplicate, already checked in today), and validator misses are all logged with the Telegram user ID, username, and message text, making it possible to reconstruct exactly why any given message was or wasn't counted.
- **Backfill scripts for real incidents** — `scripts/backfill_checkins.py` and `scripts/backfill_2026_07_08.py` document two actual production incidents (bot lacked group admin rights on day one; a validator regex gap missed "online 11-2pm"-style multi-digit time ranges) and the exact manual correction applied, rather than silently patching the sheet by hand.
- **Schedule parsing via the Claude API, not a CLI subprocess** — both `datastore/sheets.py` (self-registration) and `scripts/parse_schedules.py` (nightly Team Members sync) originally shelled out to a local Claude Code CLI binary to parse freeform schedule text into structured JSON. That only worked on a machine with Claude Code installed and authenticated — it silently degraded to `"[]"`/`{}` on a server without it, and in one path (`parse_schedules.py`) would crash uncaught rather than degrade. Both now call the `anthropic` SDK directly with `ANTHROPIC_API_KEY`, matching the pattern already used for the weekly report narrative — portable to any server, and both paths degrade gracefully (skip parsing, log why) rather than crash if the key isn't set.

---

## VPS Deployment

Two deployment paths depending on what access you have on the target server.

### Path A — you have sudo

1. Copy `secrets/service-account.json` to the server manually (never via git)
2. Copy `.env` to the server and update all paths
3. Run `deploy/setup.sh` (installs deps, creates systemd units + timer, enables services, configures nginx)
4. Three systemd services run independently:
   - `intern-checkin-bot.service` — the Telegram bot + scheduler
   - `intern-checkin-dashboard.service` — Gunicorn Flask app
   - `intern-checkin-parseschedules.timer` — nightly schedule sync at 8 PM Eastern

> **Before deploy:** Set `SECRET_KEY` in `.env` to a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)

### Path B — restricted account, no sudo (e.g. a shared box you don't administer)

Scripts in `deploy/vps/` implement the same persistence guarantees without any root access — no `apt install`, no `/etc/systemd/system`, no nginx/certbot. Used in production against a shared VPS also running an unrelated mail server stack, where the deploy account was intentionally scoped to a single directory with no sudo.

1. `rsync`/`scp` the repo to the server directly — skip git entirely so no credentials need to live on a box you don't fully control:
   ```bash
   rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='logs/*' \
     --exclude='.git' --exclude='.env' --exclude='secrets/' --exclude='admin/users.json' \
     ./ user@server:/path/to/app/
   ```
2. Build the venv on the server (`python3.12 -m venv .venv` — check whatever Python 3.x is actually available; nothing here requires 3.13 specifically) and `pip install -r requirements.txt`
3. `scp` `.env`, `secrets/service-account.json`, and `admin/users.json` over separately, `chmod 600` all three
4. In the server's `.env`, set `FLASK_ENABLED=false` — `main.py` otherwise starts its own embedded dev Flask server on the same port the standalone `gunicorn` dashboard needs, and the two collide
5. Run the dashboard via `deploy/vps/start_dashboard.sh` (nohup + gunicorn, bound to `127.0.0.1` only — reach it via an SSH tunnel: `ssh -L 5051:127.0.0.1:5050 user@server`, then browse `localhost:5051`. No public port, no nginx, no TLS needed.)
6. Run the bot via `deploy/vps/start_bot.sh`
7. Install the crontab for auto-restart-on-crash and reboot persistence, with `CRON_TZ` pinned so scheduled times are correct regardless of the server's own system timezone:
   ```
   CRON_TZ=America/New_York
   @reboot /path/to/app/deploy/vps/start_dashboard.sh
   */5 * * * * /path/to/app/deploy/vps/watchdog_dashboard.sh
   @reboot /path/to/app/deploy/vps/start_bot.sh
   */5 * * * * /path/to/app/deploy/vps/watchdog_bot.sh
   0 20 * * * /path/to/app/.venv/bin/python3 /path/to/app/scripts/parse_schedules.py >> /path/to/app/logs/parseschedules.log 2>&1
   0 3 * * 0 /path/to/app/deploy/vps/rotate_logs.sh >> /path/to/app/logs/rotate.log 2>&1
   ```
8. **Cutting over from an already-running instance elsewhere** (e.g. a local machine): Telegram only allows one active poller per bot token. Stop the old instance first, confirm no process is left running, *then* start the new one — starting both even briefly produces `telegram.error.Conflict` and can duplicate or drop messages. The bot's own catch-up-reminder logic (see Bot Behaviour above) checks *today's log file on that machine* — a fresh server has no record that an old instance already sent today's reminder, so if cutting over after the morning reminder window has already fired elsewhere, manually seed today's dated log file with a matching `"Morning reminder sent"` JSON line first, or you'll get a duplicate reminder in the live group.

`deploy/vps/rotate_logs.sh` handles log rotation with no `logrotate` binary available: `gunicorn`'s access/error logs are rotated via `mv` + `SIGUSR1` (gunicorn reopens them cleanly); the raw `nohup` stdout/stderr redirects are rotated via copy-then-truncate-in-place, since renaming a file out from under a process holding an open write handle to it doesn't actually stop that process writing to the old (now unlinked-from-that-name) inode; and the app's own dated `bot_YYYY-MM-DD.log` files are never touched if still open (checked via `/proc/<pid>/fd`, not just filename/date), since `utils/logger.py` opens that file once at process startup and keeps writing to it even across midnight rather than rotating automatically.

---

## Security Notes

- `.env` is gitignored — never commit it
- `secrets/service-account.json` is covered by `*.json` in `.gitignore` — never commit it
- `admin/users.json` (password hashes) is gitignored
- Passwords are hashed with `werkzeug.security` scrypt (salted, not reversible)
- The dashboard should sit behind a reverse proxy (nginx) with HTTPS on a VPS
- `ADMIN_API_SECRET` bearer token gates the `/settings/config` and `/api/report/run` endpoints

---

## Key Design Decisions

**Google Sheets as database** — zero infrastructure to spin up, the intern team already lives in Sheets, and the data volume (43 interns × 5 days × 52 weeks) fits comfortably within Sheets limits.

**Service account auth** — unlike OAuth, service accounts never expire or need browser re-auth. The JSON key file is the only secret to protect.

**Demo data seeding** — pages show consistent seeded pseudo-random data when the bot hasn't run yet, using `hashlib.md5(f"{name}{offset}")` so the same intern always gets the same attendance % across page loads.

**Async bridge** — APScheduler runs in a background thread while the bot owns the asyncio event loop. The `_run_async(coro)` helper submits coroutines to the bot's loop captured via `post_init`, avoiding `asyncio.run()` from a non-main thread.

---

## Built With

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [gspread](https://github.com/burnash/gspread)
- [Flask](https://flask.palletsprojects.com/)
- [APScheduler](https://github.com/agronholm/apscheduler)
- [Pydantic v2](https://docs.pydantic.dev/)
- [Chart.js](https://www.chartjs.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [openpyxl](https://openpyxl.readthedocs.io/)

---

*Built by Luan Nguyen — attendance infrastructure for the IntraStack intern program.*
