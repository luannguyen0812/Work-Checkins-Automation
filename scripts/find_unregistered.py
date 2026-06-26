import sys, json
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from datastore.sheets import get_all_interns
from datetime import date

registered_ids = {
    8318978943, 8609029340, 8745107983, 7843504658, 8777080368, 8705383449,
    8172413710, 8829770880, 8469070180, 8428330686, 7055732834, 8548981681,
    8615535893, 8062370989, 8227139899, 8526222987, 1613425467, 8664063540,
    7086173655, 6809785672, 8612145329, 6711113792, 5921041978, 5984190804,
    5257222160, 8207368337, 8616117059, 7123186160, 8244300201, 8313507706,
    654921537, 7017391677, 8643085468, 8768290106,
}

today = date.today()
missing = []
for i in get_all_interns():
    if not i.active:
        continue
    if not (i.start_date <= today <= i.end_date):
        continue
    if i.telegram_user_id not in registered_ids:
        missing.append(f"{i.full_name} (intern_id: {i.intern_id})")

with open("/tmp/unregistered.txt", "w") as f:
    f.write(f"Missing ({len(missing)}):\n")
    for n in missing:
        f.write(f"  - {n}\n")
