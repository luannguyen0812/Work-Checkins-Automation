import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from datastore.sheets import _get_spreadsheet, get_all_interns

ss = _get_spreadsheet()

# All names from Team Members tab (source of truth)
tm_ws = ss.worksheet("Team Members")
tm_records = tm_ws.get_all_records()

# Everyone on Team Members (skip header/empty rows)
all_names = set()
for r in tm_records:
    name = str(r.get("Full Name", "") or r.get("Name", "") or "").strip()
    if name:
        all_names.add(name)

# Names that have registered via DM (have a telegram_user_id in ROSTER)
roster = get_all_interns()
registered_names = {i.full_name for i in roster if i.telegram_user_id}

missing = sorted(all_names - registered_names)

with open("/tmp/missing5.txt", "w") as f:
    f.write(f"Team Members total: {len(all_names)}\n")
    f.write(f"Registered in ROSTER: {len(registered_names)}\n")
    f.write(f"Missing ({len(missing)}):\n")
    for n in missing:
        f.write(f"  - {n}\n")
    # Also show all TM names for debug if count looks off
    if len(missing) == 0 or len(all_names) < 35:
        f.write(f"\nAll Team Members columns: {list(tm_records[0].keys()) if tm_records else 'EMPTY'}\n")
        f.write(f"Sample row: {tm_records[0] if tm_records else 'EMPTY'}\n")
