"""Soccer Poisson team-model features (sports/soccer/team_features.py).
Hermetic: synthetic EPL-shaped matches through the pure builders verify (a)
leakage-safe prior-only attack/defense ratings, and (b) that the 3-way Poisson
probabilities are a valid distribution (sum to 1). No network."""
import numpy as np
import pandas as pd

from sports.soccer.team_features import (add_team_features, latest_team_ratings,
                                         predict_3way, three_way_from_lambdas)


def _matches():
    """A tiny synthetic season: 'Strong' scores a lot at home & concedes little;
    'Weak' is the opposite. Round-robin-ish so every team has home & away games."""
    rows = [
        # date, home, away, fthg, ftag
        ("2024-08-01", "Strong", "Weak", 3, 0),
        ("2024-08-08", "Mid", "Weak", 2, 1),
        ("2024-08-15", "Weak", "Mid", 0, 2),
        ("2024-08-22", "Strong", "Mid", 2, 1),
        ("2024-08-29", "Mid", "Strong", 1, 2),
        ("2024-09-05", "Weak", "Strong", 0, 3),
        ("2024-09-12", "Strong", "Weak", 4, 1),
        ("2024-09-19", "Weak", "Mid", 1, 1),
        ("2024-09-26", "Mid", "Strong", 0, 2),
        ("2024-10-03", "Strong", "Mid", 3, 0),
    ]
    return pd.DataFrame(
        [{"season": "2024", "date": d, "home": h, "away": a, "fthg": hg, "ftag": ag}
         for d, h, a, hg, ag in rows]
    )


def test_ratings_are_prior_only():
    """A team's home attack rating on a given match uses only its PRIOR home games."""
    f = add_team_features(_matches())
    # First-ever home game for each team -> no prior history -> neutral rating 1.0.
    first_strong_home = f[f["home"] == "Strong"].sort_values("date").iloc[0]
    assert first_strong_home["home_n_prior"] == 0
    assert abs(first_strong_home["home_attack"] - 1.0) < 1e-9

    # Strong's 2nd home game (2024-08-22): rating built from its 1 prior home game
    # (scored 3). league_avg is total goals / (2 * n_matches).
    la = f["league_avg"].iloc[0]
    second_strong_home = f[(f["home"] == "Strong") & (f["date"] == pd.Timestamp("2024-08-22"))].iloc[0]
    assert second_strong_home["home_n_prior"] == 1
    assert abs(second_strong_home["home_attack"] - (3.0 / la)) < 1e-6
    # And its own goals in THIS match (2) never leaked into that rating.
    assert second_strong_home["home_attack"] != (np.mean([3, 2]) / la)


def test_no_future_leak_monotone_count():
    """Prior-game counts increase 0,1,2,... — never counting the current game."""
    f = add_team_features(_matches())
    strong_home = f[f["home"] == "Strong"].sort_values("date")
    assert list(strong_home["home_n_prior"]) == [0, 1, 2, 3]


def test_three_way_probs_sum_to_one():
    for lam_h, lam_a in [(1.5, 1.1), (2.3, 0.4), (0.6, 0.6), (3.0, 2.0)]:
        p = three_way_from_lambdas(lam_h, lam_a)
        assert abs(p["p_home"] + p["p_draw"] + p["p_away"] - 1.0) < 1e-9
        assert all(0.0 <= p[k] <= 1.0 for k in ("p_home", "p_draw", "p_away"))
    # Higher home lambda -> higher home-win prob (sanity of the scoreline sum).
    assert three_way_from_lambdas(2.5, 0.5)["p_home"] > three_way_from_lambdas(1.0, 1.0)["p_home"]


def test_predict_3way_uses_ratings_and_favors_strong():
    ratings = latest_team_ratings(_matches())
    assert "Strong" in ratings and "Weak" in ratings
    out = predict_3way("Strong", "Weak", ratings,
                       league_avg=ratings["Strong"]["league_avg"], min_prior=1)
    assert out is not None
    assert abs(out["p_home"] + out["p_draw"] + out["p_away"] - 1.0) < 1e-9
    assert out["p_home"] > out["p_away"]            # strong home side favored
    assert out["total"] > 0 and out["lambda_home"] > out["lambda_away"]


def test_predict_3way_none_when_no_data():
    ratings = latest_team_ratings(_matches())
    # Unknown club -> no ratings -> None so the caller can fall back to base rates.
    assert predict_3way("Strong", "Nonexistent United", ratings, min_prior=1) is None
    # Usage gate: require more prior games than the tiny synthetic season provides.
    assert predict_3way("Strong", "Weak", ratings, min_prior=99) is None


def test_latest_ratings_use_recent_actual_games():
    """latest_team_ratings must use a team's most recent ACTUAL games (not a
    stale shift), so Strong's home attack reflects its real home scoring."""
    ratings = latest_team_ratings(_matches())
    la = ratings["Strong"]["league_avg"]
    # Strong home goals: 3, 2, 4, 3 -> mean 3.0 (window >= 4).
    assert abs(ratings["Strong"]["home_attack"] - (3.0 / la)) < 1e-6
    assert ratings["Strong"]["home_n_prior"] == 4
