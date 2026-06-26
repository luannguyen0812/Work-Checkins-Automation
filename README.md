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
│   ├── setup.sh              # VPS provisioning script
│   ├── intern-checkin-bot.service    # systemd unit
│   └── intern-checkin-dashboard.service
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

---

## Bot Behaviour

### Check-in detection
The bot watches every group message (Privacy Mode must be OFF). Messages matching `CHECKIN_REGEX` (e.g. "Good morning, checking in!" / "GM checking in 🌅") are treated as check-ins.

### Auto-registration
When an unregistered intern sends any message, the bot fuzzy-matches their Telegram display name against the ROSTER's `full_name` column. On a confident match it writes their `telegram_user_id` back to the sheet — no manual step needed.

### Scheduled jobs (EDT / America/New_York)

| Time | Days | Job |
|---|---|---|
| 09:30 | Mon–Fri | Morning reminder in group |
| 11:30 | Mon–Fri | Second reminder |
| 17:45 | Mon–Fri | Pre-cutoff alert |
| 18:00 | Friday | Generate + DM weekly Excel report to admin |
| 02:00 | Sunday | Delete CHECKINS_* sheets older than `retention_weeks` |

### Late flag
An intern is marked `late=True` when their check-in timestamp (EDT) is after their shift's scheduled end time, as defined in ROSTER's `schedule_json` column.

---

## VPS Deployment

1. Copy `secrets/service-account.json` to the server manually (never via git)
2. Copy `.env` to the server and update all paths
3. Run `deploy/setup.sh` (installs deps, creates systemd units, enables services)
4. Two systemd services run independently:
   - `intern-checkin-bot.service` — the Telegram bot + scheduler
   - `intern-checkin-dashboard.service` — Gunicorn Flask app

> **Before deploy:** Set `SECRET_KEY` in `.env` to a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)

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
