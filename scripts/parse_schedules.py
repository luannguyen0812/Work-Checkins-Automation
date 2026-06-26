#!/usr/bin/env python3
"""
Schedule sync: parse freeform schedule text from Team Members col E,
convert all times to America/New_York, and write schedule_json + schedule_raw to ROSTER.

Only re-parses rows where Team Members col E has changed since last run.
Safe to run repeatedly — idempotent when nothing changed.

Run from the bot directory:
    .venv/bin/python3 parse_schedules.py

Scheduled nightly via cron.
"""

import json
import os
import subprocess
import sys

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)
os.environ.setdefault(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    os.path.join(BOT_DIR, "secrets/service-account.json"),
)
os.environ.setdefault(
    "GOOGLE_SHEETS_SPREADSHEET_ID",
    "1rEKBrDAUcd3EDUjNYJi_knJmdfl-4PxPdOkcqcVBfXM",
)

from datastore.sheets import _get_spreadsheet  # noqa: E402

CLAUDE_BIN = "/usr/local/bin/claude"

PARSE_PROMPT = (
    "You are a schedule parser. Convert each intern's freeform schedule text into structured JSON.\n\n"
    "Rules:\n"
    "- Output ONLY valid JSON, no explanation.\n"
    "- Output a JSON object where each key is the intern's full name and the value is an array of schedule segments.\n"
    '- Each segment: {{"days": [...], "start": "HH:MM", "end": "HH:MM"}}\n'
    '- days: array of full day names: "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"\n'
    "- start/end: 24-hour HH:MM format, converted to America/New_York (Eastern Time, currently EDT = UTC-4)\n"
    "- Timezone conversions: CST = UTC-5 → EDT add 1h | CDT = UTC-5 → EDT add 1h | PDT = UTC-7 → EDT add 3h | PST = UTC-8 → EDT add 4h | EDT/EST/ET = no change\n"
    "- Day abbreviations: M=Mon, T=Tue, W=Wed, Th/Thu=Thu, F=Fri, Sa/Sat=Sat, Su/Sun=Sun\n"
    "- SS = Sat+Sun, FSS = Fri+Sat+Sun, MTW = Mon+Tue+Wed, MTWTF = Mon-Fri, etc.\n"
    "- If blank or unparseable, return [] for that intern.\n"
    '- Obvious typos: "9AM-6AM" going backwards implies PM end time.\n'
    '- Split shifts on same days (e.g. "8-9AM 8:30-10:30PM") use two segments with the same days.\n'
    "- If no days are specified, assume Mon-Fri.\n\n"
    "Interns to parse:\n"
    "{entries}\n\n"
    "Output ONLY the JSON object."
)


def parse_with_claude(entries: list[tuple[str, str]]) -> dict:
    """Batch-parse entries via Claude. Returns {name: schedule_list}."""
    formatted = "\n".join(f'- {name}: "{sched}"' for name, sched in entries)
    prompt = PARSE_PROMPT.format(entries=formatted)
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("Claude error:", result.stderr[:500])
        sys.exit(1)
    raw = result.stdout.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        print("JSON parse error:", e)
        print("Raw output:", raw[:1000])
        sys.exit(1)


def _ensure_col(ws, name: str) -> int:
    """Add column `name` to sheet if missing, expanding grid. Returns 1-based index."""
    headers = ws.row_values(1)
    if name in headers:
        return headers.index(name) + 1
    col_idx = len(headers) + 1
    if ws.col_count < col_idx:
        ws.resize(rows=ws.row_count, cols=col_idx)
    ws.update_cell(1, col_idx, name)
    print(f"  Added column '{name}' at col {col_idx}")
    return col_idx


def _normalize(s: str) -> str:
    return s.strip().lower()


def main():
    ss = _get_spreadsheet()

    # Build name → raw schedule map from Team Members
    tm_ws = ss.worksheet("Team Members")
    tm_records = tm_ws.get_all_records()
    tm_schedule: dict[str, str] = {}
    for r in tm_records:
        name = (
            r.get("Full Name") or r.get("full_name") or
            f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip()
        )
        raw = str(r.get("Preferred Shift | Interns Hours") or "").strip()
        if name:
            tm_schedule[name] = raw

    # Read ROSTER and ensure both columns exist
    roster_ws = ss.worksheet("ROSTER")
    json_col = _ensure_col(roster_ws, "schedule_json")
    raw_col = _ensure_col(roster_ws, "schedule_raw")

    roster_records = roster_ws.get_all_records()

    # Find rows that need re-parsing
    to_parse: list[tuple[int, str, str]] = []  # (row_idx, full_name, new_raw)
    for row_idx, r in enumerate(roster_records, start=2):
        full_name = str(r.get("full_name", "")).strip()
        if not full_name:
            continue

        # Match against Team Members (exact then case-insensitive)
        new_raw = tm_schedule.get(full_name)
        if new_raw is None:
            for tm_name, tm_raw in tm_schedule.items():
                if _normalize(tm_name) == _normalize(full_name):
                    new_raw = tm_raw
                    break
        if new_raw is None:
            continue  # intern not in Team Members tab — skip

        stored_raw = str(r.get("schedule_raw", "")).strip()
        stored_json = str(r.get("schedule_json", "")).strip()
        raw_changed = _normalize(new_raw) != _normalize(stored_raw)
        # Also re-parse if raw is present but json failed (empty or literal "[]" with non-blank raw)
        json_missing = new_raw and (not stored_json or stored_json == "[]")
        if raw_changed or json_missing:
            to_parse.append((row_idx, full_name, new_raw))

    if not to_parse:
        print("No schedule changes detected. Nothing to do.")
        return

    print(f"{len(to_parse)} row(s) changed — re-parsing via Claude...")
    parsed = parse_with_claude([(name, raw) for _, name, raw in to_parse])

    updated = 0
    for row_idx, full_name, new_raw in to_parse:
        schedule = parsed.get(full_name)
        if schedule is None:
            for p_name, p_sched in parsed.items():
                if _normalize(p_name) == _normalize(full_name):
                    schedule = p_sched
                    break

        if schedule is not None:
            roster_ws.update_cell(row_idx, json_col, json.dumps(schedule))
            roster_ws.update_cell(row_idx, raw_col, new_raw)
            segs = len(schedule)
            print(f"  ✓ {full_name}: {segs} segment(s)  [{new_raw[:60]}]")
            updated += 1
        else:
            print(f"  ? {full_name}: Claude returned no result — skipping")

    print(f"\nDone. Updated {updated}/{len(to_parse)} row(s).")


if __name__ == "__main__":
    main()
