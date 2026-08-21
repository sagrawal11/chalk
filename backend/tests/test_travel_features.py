"""Travel / altitude / fatigue features (feature_engine._add_travel_features).
Hermetic: constructs a synthetic player frame, no disk/model dependencies."""
import numpy as np
import pandas as pd
import pytest

import feature_engine as fe
from feature_engine import FeatureEngine


def _frame():
    # LAL player: home vs BOS, @ DEN (altitude), @ UTA (altitude, dense stretch), home vs GSW.
    return pd.DataFrame({
        "GAME_DATE": pd.to_datetime(["2025-01-01", "2025-01-03", "2025-01-04", "2025-01-10"]),
        "IS_HOME": [1, 0, 0, 1],
        "PLAYER_TEAM": ["LAL", "LAL", "LAL", "LAL"],
        "OPPONENT_TEAM": ["BOS", "DEN", "UTA", "GSW"],
    })


def _out():
    eng = FeatureEngine.__new__(FeatureEngine)   # hermetic (method uses no instance state)
    return eng._add_travel_features(_frame()).set_index("GAME_DATE")


def test_altitude_and_venue():
    o = _out()
    assert o.loc["2025-01-01", "TRV_ALT_FEET"] == pytest.approx(233)      # home = LAL
    assert o.loc["2025-01-03", "TRV_ALT_FEET"] == pytest.approx(5280)     # @ DEN
    assert o.loc["2025-01-03", "TRV_IS_ALTITUDE"] == 1
    assert o.loc["2025-01-04", "TRV_IS_ALTITUDE"] == 1                    # @ UTA
    assert o.loc["2025-01-01", "TRV_IS_ALTITUDE"] == 0


def test_travel_and_timezone_prior_only():
    o = _out()
    assert o.loc["2025-01-01", "TRV_MILES"] == 0.0        # first game: no prior venue
    assert o.loc["2025-01-03", "TRV_MILES"] > 500         # LAL -> DEN
    assert o.loc["2025-01-03", "TRV_TZ_SHIFT"] == pytest.approx(1.0)  # PT(-8) -> MT(-7)


def test_road_trip_and_fatigue():
    o = _out()
    assert o.loc["2025-01-01", "TRV_ROAD_TRIP_LEN"] == 0
    assert o.loc["2025-01-03", "TRV_ROAD_TRIP_LEN"] == 1
    assert o.loc["2025-01-04", "TRV_ROAD_TRIP_LEN"] == 2   # consecutive away
    assert o.loc["2025-01-10", "TRV_ROAD_TRIP_LEN"] == 0   # back home
    assert o.loc["2025-01-04", "TRV_3IN4"] == 1            # games on 1st,3rd,4th
    assert o.loc["2025-01-01", "TRV_3IN4"] == 0


def test_whitelist_keeps_travel_features():
    # TRV_ prefix must survive _clean_output_columns.
    eng = FeatureEngine.__new__(FeatureEngine)
    df = eng._add_travel_features(_frame())
    for c in ["PTS", "PLAYER_NAME"]:
        df[c] = 0
    kept = eng._clean_output_columns(df).columns
    assert "TRV_ALT_FEET" in kept and "TRV_MILES" in kept and "TRV_3IN4" in kept
