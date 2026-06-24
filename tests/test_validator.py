import pytest
from bot.validator import CHECKIN_REGEX


@pytest.mark.parametrize("text", [
    "I'm online",
    "online",
    "checking in",
    "check-in",
    "check in",
    "present",
    "here",
    "good morning",
    "gm",
    "Hey team, I'm online today!",
])
def test_checkin_regex_matches(text):
    assert CHECKIN_REGEX.search(text), f"Expected match for: {text!r}"


@pytest.mark.parametrize("text", [
    "Hello everyone",
    "What's up?",
    "See you all later",
])
def test_checkin_regex_no_match(text):
    assert not CHECKIN_REGEX.search(text), f"Expected no match for: {text!r}"
