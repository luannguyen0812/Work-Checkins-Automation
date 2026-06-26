import sys; sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from datastore.sheets import get_config
cfg = get_config()
with open("/tmp/cfg_out.txt", "w") as f:
    f.write(f"group_chat_id: {cfg.group_chat_id}\n")
    f.write(f"morning_reminder_time: {cfg.morning_reminder_time}\n")
    f.write(f"checkin_cutoff_time: {cfg.checkin_cutoff_time}\n")
