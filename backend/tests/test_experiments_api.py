"""Progression feed /api/experiments — hermetic (isolated blueprint, committed data)."""
from flask import Flask

from web.experiments_api import bp


def _client():
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app.test_client()


def test_experiments_feed_serves_ledger_and_champion():
    r = _client().get("/api/experiments")
    assert r.status_code == 200
    data = r.get_json()
    assert {"experiments", "champions", "counts"} <= set(data)
    # the committed NFL champion + ledger from M2
    assert data["champions"].get("nfl", {}).get("model_version") == "nfl-v2"
    assert any(e["id"] == "NFL-10" and e["decision"] == "keep" for e in data["experiments"])
    assert data["counts"]["nfl"]["run"] >= 3
