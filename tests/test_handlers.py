import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from bot.handlers import handle_message


def test_non_checkin_message_does_not_read_sheets(monkeypatch):
    from datastore import sheets

    def fail_get_config():
        raise AssertionError("non-check-in chatter should not touch Sheets")

    monkeypatch.setattr(sheets, "get_config", fail_get_config)

    update = SimpleNamespace(
        message=SimpleNamespace(
            text="See you all later",
            chat_id=-123,
            from_user=SimpleNamespace(id=456),
        )
    )

    asyncio.run(handle_message(update, SimpleNamespace()))


def test_unknown_checkin_user_is_written_to_unmatched(monkeypatch):
    from datastore import sheets

    captured = {}

    monkeypatch.setattr(
        sheets,
        "get_config",
        lambda: SimpleNamespace(group_chat_id=-123),
    )
    monkeypatch.setattr(sheets, "get_intern_by_telegram_id", lambda user_id: None)
    monkeypatch.setattr(
        sheets,
        "write_unmatched_checkin",
        lambda **kwargs: captured.update(kwargs),
    )

    update = SimpleNamespace(
        message=SimpleNamespace(
            text="I'm online 10-1pm",
            chat_id=-123,
            message_id=789,
            date=datetime(2026, 7, 6, 13, 57, tzinfo=timezone.utc),
            from_user=SimpleNamespace(
                id=456,
                username="unknown_user",
                first_name="Unknown",
                last_name="Intern",
            ),
        )
    )

    asyncio.run(handle_message(update, SimpleNamespace()))

    assert captured["reason"] == "unrecognised_telegram_user"
    assert captured["telegram_user_id"] == 456
    assert captured["telegram_username"] == "unknown_user"
    assert captured["telegram_name"] == "Unknown Intern"
    assert captured["message_id"] == 789
    assert captured["message_text"] == "I'm online 10-1pm"
