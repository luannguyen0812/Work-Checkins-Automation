import re

CHECKIN_REGEX = re.compile(
    r"\b("
    r"online"                            # "online", "online from 9am", "going online"
    r"|i'?m\s+online"                   # "I'm online", "im online"
    r"|i'?ll\s+be\s+online"            # "I'll be online from..."
    r"|i\s+will\s+be\s+online"         # "I will be online"
    r"|i\s+am\s+online"                # "I am online"
    r"|(?:just\s+)?came\s+online"      # "came online", "just came online"
    r"|checking\s+in"                   # "checking in"
    r"|check\s*[‑\-]?\s*in"           # "check-in", "checkin"
    r"|present"                         # "present"
    r"|here"                            # "here"
    r"|good\s+morning"                  # "good morning"
    r"|gm"                              # "gm"
    r")\b",
    re.IGNORECASE,
)


def is_checkin(text: str) -> bool:
    return bool(CHECKIN_REGEX.search(text))
