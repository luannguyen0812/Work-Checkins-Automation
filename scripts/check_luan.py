from dotenv import load_dotenv; load_dotenv()
import sys
sys.path.insert(0, ".")
from datastore.sheets import get_all_interns
results = []
for i in get_all_interns():
    if 'luan' in i.full_name.lower() or 'luan' in i.intern_id.lower():
        results.append(f"{i.intern_id} | {i.full_name} | tg:{i.telegram_user_id} | active:{i.active}")
if not results:
    results.append("NOT IN ROSTER")
with open("/tmp/luan_check.txt","w") as f:
    f.write("\n".join(results)+"\n")
