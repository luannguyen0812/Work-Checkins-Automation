# Admin Guide

See `INTERN_CHECKIN_AUTOMATION_CONTEXT.md` sections 14–18 for full reference.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in all values
python setup_sheets.py
python main.py
```

## Admin API (localhost:5050)
All requests require `Authorization: Bearer <ADMIN_API_SECRET>`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness check |
| `/status` | GET | Today's check-in summary |
| `/config` | POST | Update a CONFIG key |
| `/report/run` | POST | Trigger report on demand |
| `/interns` | GET | List active interns |
| `/interns/{id}/opt-out` | POST | Deactivate an intern |
