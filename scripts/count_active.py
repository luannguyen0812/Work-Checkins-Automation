import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from datastore.sheets import get_all_interns
from datetime import date

today = date.today()
active = [i for i in get_all_interns() if i.active and i.start_date <= today <= i.end_date]
no_tg = [i for i in active if not i.telegram_user_id]

registered_ids = {
    8318978943, 8609029340, 8745107983, 7843504658, 8777080368, 8705383449,
    8172413710, 8829770880, 8469070180, 8428330686, 7055732834, 8548981681,
    8615535893, 8062370989, 8227139899, 8526222987, 1613425467, 8664063540,
    7086173655, 6809785672, 8612145329, 6711113792, 5921041978, 5984190804,
    5257222160, 8207368337, 8616117059, 7123186160, 8244300201, 8313507706,
    654921537, 7017391677, 8643085468, 8768290106,
}

unregistered = [i for i in active if i.telegram_user_id and i.telegram_user_id not in registered_ids]
no_id = [i for i in active if not i.telegram_user_id]

with open("/tmp/count_active.txt", "w") as f:
    f.write(f"Total active interns today: {len(active)}\n")
    f.write(f"No Telegram ID in roster: {len(no_id)}\n")
    for i in no_id:
        f.write(f"  - {i.full_name}\n")
    f.write(f"Have ID but never DM'd: {len(unregistered)}\n")
    for i in unregistered:
        f.write(f"  - {i.full_name} (tg: {i.telegram_user_id})\n")
