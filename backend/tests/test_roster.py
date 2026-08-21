"""Roster resolution, incl. accent-tolerant lookup (backend/sports/nba/roster.py).
Hermetic (tmp player_data with an accented dir name)."""
import pandas as pd

import sports.nba.roster as roster


def _make_player(base, dirname, team="DEN"):
    d = base / dirname
    d.mkdir(parents=True)
    pd.DataFrame({"GAME_DATE": ["2025-01-01", "2025-01-03"], "PLAYER_TEAM": [team, team]}).to_csv(
        d / f"{dirname}_data.csv", index=False
    )


def test_accented_dir_resolves_from_ascii_and_accented_input(tmp_path, monkeypatch):
    _make_player(tmp_path, "Nikola_Jokić")  # accented ć on disk
    monkeypatch.setattr(roster, "PLAYER_DATA_DIR", tmp_path)
    roster.clear_cache()
    try:
        assert roster.player_team("nikola_jokic") == "DEN"   # ASCII input resolves
        assert roster.player_team("nikola_joki") == "DEN"     # accent-stripped input resolves
        ctx = roster.player_game_context("nikola_jokic", [{"home": "DEN", "away": "LAL"}], "2025-01-15")
        assert ctx["opponent"] == "LAL" and ctx["is_home"] is True
    finally:
        roster.clear_cache()  # don't leak tmp mapping into other tests


def test_unknown_player_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(roster, "PLAYER_DATA_DIR", tmp_path)
    roster.clear_cache()
    try:
        assert roster.player_team("nobody_here") is None
    finally:
        roster.clear_cache()
