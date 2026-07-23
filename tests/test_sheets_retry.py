from requests.exceptions import ConnectionError

from datastore.sheets import _with_sheets_retry


def test_sheets_retry_recovers_from_transient_connection_error(monkeypatch):
    sleeps = []
    calls = {"count": 0}

    monkeypatch.setattr("datastore.sheets.time.sleep", lambda delay: sleeps.append(delay))

    def flaky_read():
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("temporary reset")
        return "ok"

    assert _with_sheets_retry(flaky_read) == "ok"
    assert calls["count"] == 2
    assert sleeps == [1.0]
