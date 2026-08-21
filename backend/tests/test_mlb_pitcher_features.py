"""MLB pitcher strikeout-prop features (sports/mlb/pitcher_features.py).
Hermetic: synthetic starts through the pure feature builder verify leakage-safe
rolling (prior starts only)."""
import numpy as np
import pandas as pd

from sports.mlb.pitcher_features import (ANCHOR_COL, add_pitcher_features,
                                         latest_pitcher_features)


def _starts(pid=1, ks=(5, 7, 6, 8, 4, 9, 6, 7)):
    n = len(ks)
    return pd.DataFrame({
        "pitcher_id": [pid] * n, "season": [2024] * n,
        "date": pd.date_range("2024-04-01", periods=n, freq="5D"),
        "K": list(ks), "IP": [6.0] * n, "BF": [24.0] * n, "opp": [""] * n,
        "is_home": [i % 2 for i in range(n)],
    })


def test_rolling_is_prior_only():
    f = add_pitcher_features(_starts()).sort_values("date").reset_index(drop=True)
    # K_L5 at start #6 = mean Ks of the 5 PRIOR starts (never the current one)
    assert abs(f.loc[6, "K_L5"] - np.mean([7, 6, 8, 4, 9])) < 1e-6
    assert pd.isna(f.loc[0, "K_L3"])          # first start: no history -> NaN
    assert int(f.loc[7, "_n_prior"]) == 7     # prior-start counter


def test_latest_features_keyed_by_id():
    latest = latest_pitcher_features(add_pitcher_features(_starts(pid=10)))
    assert 10 in latest
    rec = latest[10]
    assert "anchor" in rec and "feats" in rec and ANCHOR_COL == "K_L5"
    assert rec["anchor"] == np.mean([8, 4, 9, 6, 7])   # K_L5 entering the (unseen) next start
