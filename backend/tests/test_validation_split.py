"""Honest validation methodology (backend/model_training/validation.py).

Guards PLANNING.md 8.1/8.2: the final season is a true holdout — never a CV
fold — and CV never scores on the holdout season.
"""
import numpy as np
import pandas as pd
import pytest


def _synthetic():
    rng = np.random.default_rng(0)
    seasons = ["2019-20", "2020-21", "2021-22", "2022-23"]
    rows = []
    for si, s in enumerate(seasons):
        for j in range(80):
            x = rng.normal()
            rows.append(
                {
                    "season": s,
                    "x": x,
                    "y": 3.0 * x + rng.normal() * 0.3 + si,
                    "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=si * 400 + j),
                }
            )
    df = pd.DataFrame(rows)
    return df[["x"]], df["y"], df["season"], df["date"]


def test_holdout_is_last_season_and_untouched_by_cv():
    pytest.importorskip("lightgbm")
    from model_training.validation import walk_forward_train

    X, y, seasons, dates = _synthetic()
    model, m = walk_forward_train(X, y, seasons, dates=dates, params={"n_estimators": 60})

    assert m["holdout_season"] == "2022-23"
    cv_seasons = {c["season"] for c in m["cv_metrics"]}
    assert "2022-23" not in cv_seasons, "holdout season must never be a CV fold"
    assert cv_seasons.issubset({"2020-21", "2021-22"})
    assert m["cv_mae"] is not None
    assert m["holdout_mae"] >= 0.0
    assert m["best_iteration"] >= 1
    assert len(model.predict(X.iloc[:5])) == 5


def test_stub_season_never_becomes_holdout():
    """A partial/stub current season (few rows) must not be auto-picked as the
    scoring holdout — that yields a meaningless ~200-row holdout_mae. The guard
    drops it so the holdout is the last FULL season instead."""
    pytest.importorskip("lightgbm")
    from model_training.validation import walk_forward_train

    X, y, seasons, dates = _synthetic()            # 4 full seasons of 80 rows each
    # Append a stub "current" season with only a handful of games.
    rng = np.random.default_rng(2)
    stub = pd.DataFrame({
        "x": rng.normal(size=6),
        "y": rng.normal(size=6),
        "season": ["2023-24"] * 6,
        "date": pd.date_range("2024-10-25", periods=6, freq="D"),
    })
    X = pd.concat([X, stub[["x"]]], ignore_index=True)
    y = pd.concat([y, stub["y"]], ignore_index=True)
    seasons = pd.concat([seasons, stub["season"]], ignore_index=True)
    dates = pd.concat([dates, stub["date"]], ignore_index=True)

    _, m = walk_forward_train(X, y, seasons, dates=dates, params={"n_estimators": 60})
    assert m["holdout_season"] == "2022-23", "stub season must be excluded from holdout"
    assert "2023-24" not in {c["season"] for c in m["cv_metrics"]}


def test_degenerate_few_seasons_still_returns_holdout():
    pytest.importorskip("lightgbm")
    from model_training.validation import walk_forward_train

    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame(
        {
            "x": rng.normal(size=n),
            "season": ["2023-24"] * n,
            "date": pd.date_range("2023-11-01", periods=n, freq="D"),
        }
    )
    df["y"] = 2.0 * df["x"] + rng.normal(size=n) * 0.2
    model, m = walk_forward_train(
        df[["x"]], df["y"], df["season"], dates=df["date"], params={"n_estimators": 40}
    )
    assert m["cv_mae"] is None            # not enough seasons for CV
    assert m["holdout_mae"] >= 0.0        # but still a temporal holdout estimate
    assert m["n_holdout"] > 0
