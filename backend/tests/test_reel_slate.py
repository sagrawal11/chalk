"""Hermetic tests for the reel slate seam (content/reel_slate.py).

Pins the Python side of the render-reel.mjs data contract (reel/SLATE_CONTRACT.md):
``build_slate`` produces the right shape and rejects malformed games.
"""
import json

import pytest

from content.reel_slate import build_slate, write_slate


def _game(**over):
    g = {
        "homeName": "Lakers", "homeShort": "Lakers", "homeCity": "Los Angeles",
        "awayName": "Warriors", "awayShort": "Warriors", "awayCity": "Golden State",
        "homeScore": 112, "awayScore": 108, "confidence": 64,
        "winnerSide": "home", "reasoning": "home grades out ahead.",
    }
    g.update(over)
    return g


def test_build_slate_shape():
    slate = build_slate(
        date="SAT · FEB 8, 2026", win_pct=61.5, n_picks=43583,
        yesterday_correct=6, yesterday_total=8, games=[_game()],
    )
    assert slate["date"] == "SAT · FEB 8, 2026"
    assert slate["trackRecord"] == {"winPct": 61.5, "nPicks": 43583}
    assert slate["yesterday"] == {"correct": 6, "total": 8}
    assert len(slate["slate"]) == 1
    assert slate["slate"][0]["winnerSide"] == "home"


def test_build_slate_rejects_bad_winner_side():
    with pytest.raises(ValueError):
        build_slate(date="d", win_pct=1.0, n_picks=1, yesterday_correct=0,
                    yesterday_total=0, games=[_game(winnerSide="tie")])


def test_build_slate_rejects_missing_field():
    bad = _game()
    del bad["reasoning"]
    with pytest.raises(ValueError):
        build_slate(date="d", win_pct=1.0, n_picks=1, yesterday_correct=0,
                    yesterday_total=0, games=[bad])


def test_write_slate_roundtrip(tmp_path):
    slate = build_slate(date="d", win_pct=61.5, n_picks=10, yesterday_correct=1,
                        yesterday_total=2, games=[_game()])
    out = write_slate(slate, tmp_path / "slate.json")
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8")) == slate
