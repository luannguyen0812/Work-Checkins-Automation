import pytest
from bot.validator import CHECKIN_REGEX


@pytest.mark.parametrize("text", [
    "I'm online",
    "online",
    "checking in",
    "check-in",
    "check in",
    "good morning",
    "Hey team, I'm online today!",
    "available from 9-5",
    "I'm available today",
    "logging on now",
    "logged in",
    "clocking in",
    "working from 10-4",
])
def test_checkin_regex_matches(text):
    assert CHECKIN_REGEX.search(text), f"Expected match for: {text!r}"


@pytest.mark.parametrize("text", [
    "Hello everyone",
    "What's up?",
    "See you all later",
    # Bare words dropped intentionally — too prone to false positives in
    # normal group chatter (e.g. "I'm present at the meeting", "gm" used
    # sarcastically, "here" in unrelated sentences).
    "present",
    "here",
    "gm",
])
def test_checkin_regex_no_match(text):
    assert not CHECKIN_REGEX.search(text), f"Expected no match for: {text!r}"
