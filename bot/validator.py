import re

CHECKIN_REGEX = re.compile(
    r"\b(online|i'?m\s+online|checking\s+in|check\s*[‑\-]?\s*in|present|here|good\s+morning|gm)\b",
    re.IGNORECASE,
)


def is_checkin(text: str) -> bool:
    return bool(CHECKIN_REGEX.search(text))
