import re

# Matches straight apostrophe, curly right single quotation mark (U+2019), and
# curly left single quotation mark (U+2018) so "I'm"/"I'll" typed on phones work.
_APO = r"['‘’]"

CHECKIN_REGEX = re.compile(
    r"\b("
    r"i" + _APO + r"?m\s+online"       # "I'm online", "im online"
    r"|i" + _APO + r"?ll\s+be\s+online"  # "I'll be online from..."
    r"|i\s+will\s+be\s+online"         # "I will be online"
    r"|i\s+am\s+online"                # "I am online"
    r"|online"                                       # "online", "online 11-2pm", "online from 9"
    r"|(?:just\s+)?came\s+online"      # "came online", "just came online"
    r"|going\s+online"                  # "going online"
    r"|logging\s+(?:in|on)"            # "logging in", "logging on"
    r"|logged\s+(?:in|on)"             # "logged in", "logged on"
    r"|clock(?:ing)?\s+in"             # "clock in", "clocking in"
    r"|checking\s+in"                   # "checking in"
    r"|check\s*[‑\-]?\s*in"           # "check-in", "checkin"
    r"|available\s+(?:from|until|till|today|now)"  # "available from 9-5"
    r"|working\s+(?:from|until|till|today|now)"    # "working from 9-5"
    r"|good\s+morning"                  # "good morning"
    r")\b",
    re.IGNORECASE,
)


def is_checkin(text: str) -> bool:
    return bool(CHECKIN_REGEX.search(text))
