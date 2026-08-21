"""Walk-forward team backtest (backend/backtest/team_backtest.py). Hermetic:
synthetic frame with a learnable margin signal; asserts OOS winner accuracy beats
a coin flip and the odds-grading path works."""
import numpy as np
import pandas as pd
import pytest

from predictions.schema import make_game_key
from sports.nba.team_features import TEAM_FEATURE_COLS


def _frame(seasons=(2016, 2017, 2018, 2019, 2020), n=200):
    rng = np.random.default_rng(0)
    rows = []
    for s in seasons:
        for j in range(n):
            net = rng.normal(0, 5.0)
            row = {c: 0.0 for c in TEAM_FEATURE_COLS}
            row["NET_DIFF"] = net
            row["HOME_NET"] = net
            row["PACE_SUM"] = 198.0
            row.update({
                "season": s,
                "game_date": pd.Timestamp(f"{s}-11-01") + pd.Timedelta(days=j),
                "home": "LAL", "away": "BOS",
                "y_margin": 6.0 * net + rng.normal(0, 10.0),   # learnable winner signal
                "y_total": 220.0 + rng.normal(0, 15.0),
            })
            rows.append(row)
    return pd.DataFrame(rows)


def test_walk_forward_beats_coin_flip():
    pytest.importorskip("lightgbm")
    from backtest.team_backtest import summarize, walk_forward_backtest

    bt = walk_forward_backtest(_frame(), min_train_seasons=2, params={"n_estimators": 80})
    assert not bt.empty
    assert {"season", "su_acc", "margin_mae", "total_mae"} <= set(bt.columns)
    s = summarize(bt)
    assert s["su_acc"] > 0.6          # a real signal must beat 0.5 out-of-sample
    assert s["games"] > 0


def test_market_grading_path():
    pytest.importorskip("lightgbm")
    from backtest.team_backtest import summarize, walk_forward_backtest

    fr = _frame()
    odds = {}
    for _, r in fr.iterrows():
        gk = make_game_key("nba", str(r["game_date"])[:10], r["away"], r["home"])
        odds[gk] = {"spread_home": -3.5, "total": 220.0}

    bt = walk_forward_backtest(fr, min_train_seasons=2, odds=odds, params={"n_estimators": 80})
    assert "ats_pct" in bt.columns and bt["market_games"].sum() > 0
    s = summarize(bt)
    assert 0.0 <= s["ats_pct"] <= 1.0 and 0.0 <= s["ou_pct"] <= 1.0
