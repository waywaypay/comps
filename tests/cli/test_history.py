from pathlib import Path

import pytest

from comps.cli import history


@pytest.fixture()
def isolated_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(history, "HISTORY_DB", tmp_path / "history.db")
    monkeypatch.setenv("COMPS_SESSION", "test-session")
    yield


def test_save_and_last_roundtrip(isolated_history):
    history.save("vertical saas LBO", [{"deal_id": 1, "target": "Acme"}])
    last = history.last()
    assert last is not None
    q, results = last
    assert q == "vertical saas LBO"
    assert results[0]["deal_id"] == 1


def test_last_returns_most_recent(isolated_history):
    history.save("first", [{"deal_id": 1}])
    history.save("second", [{"deal_id": 2}])
    last = history.last()
    assert last is not None
    assert last[0] == "second"
