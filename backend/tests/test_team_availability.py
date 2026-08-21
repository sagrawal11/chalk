"""Teammate-availability reconstruction (data_collection/collect_team_availability.py).
Hermetic: builds a tiny synthetic multi-player log set in tmp."""
import json

import pandas as pd
import pytest

from data_collection.collect_team_availability import build_team_availability


def _mk(base, dirname, team, rows):  # rows: list of (date, min, pts)
    d = base / dirname
    d.mkdir(parents=True)
    pd.DataFrame(
        [{"GAME_DATE": dt, "PLAYER_TEAM": team, "MIN": m, "PTS": p} for dt, m, p in rows]
    ).to_csv(d / f"{dirname}_data.csv", index=False)


def test_star_absence_is_detected(tmp_path):
    dates = ["2025-01-01", "2025-01-03", "2025-01-05", "2025-01-07"]
    # STAR plays the first three games (~31 min) then is OUT on 2025-01-07.
    _mk(tmp_path, "Star_Player", "AAA", [(dates[0], 30, 28), (dates[1], 32, 30), (dates[2], 31, 26)])
    _mk(tmp_path, "Role_One", "AAA", [(d, 22, 12) for d in dates])
    _mk(tmp_path, "Role_Two", "AAA", [(d, 18, 9) for d in dates])
    _mk(tmp_path, "Bench_Guy", "AAA", [(d, 5, 2) for d in dates])  # below rotation threshold

    by = build_team_availability(tmp_path, tmp_path / "ta.parquet").set_index("game_date")

    d4 = pd.Timestamp("2025-01-07")
    assert by.loc[d4, "TM_OUT_MIN"] == pytest.approx(31.0, abs=0.5)   # star's ~31 baseline min
    assert by.loc[d4, "TM_OUT_COUNT"] == 1
    assert by.loc[d4, "TM_TOP_OUT"] == 1                              # the star was the top rotation player
    assert by.loc[pd.Timestamp("2025-01-01"), "TM_OUT_MIN"] == 0      # no prior window -> nothing out

    rot = json.loads(by.loc[d4, "TM_ROT_JSON"])
    assert "star_player" in rot and "role_one" in rot
    assert "bench_guy" not in rot                                     # 5 min < rotation threshold


def test_full_rotation_present_means_no_out(tmp_path):
    dates = ["2025-02-01", "2025-02-03", "2025-02-05"]
    _mk(tmp_path, "A_One", "BBB", [(d, 30, 20) for d in dates])
    _mk(tmp_path, "A_Two", "BBB", [(d, 25, 15) for d in dates])
    by = build_team_availability(tmp_path, tmp_path / "ta.parquet").set_index("game_date")
    # everyone always plays -> nobody out on any date
    assert (by["TM_OUT_MIN"] == 0).all() and (by["TM_OUT_COUNT"] == 0).all()
