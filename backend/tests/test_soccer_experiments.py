"""Soccer 3-way fan-out into the harness (M7) — hermetic (no football-data fetch).

Covers the new machinery the binary sports don't have: the 3-way log-loss metric,
the Dixon-Coles correction, the param-based champion (model_params, not feature_cols),
the sport-level keep-rule, and the walk_forward_3way eval on synthetic matches. The
real EPL run is exercised against the cached data in the M7 demo.
"""
import math

import numpy as np
import pandas as pd

from backtest.soccer_backtest import (BASELINE_PARAMS, summarize_3way,
                                      three_way_logloss, walk_forward_3way)
from experiments import roadmap
from experiments.champion import (ChampionConfig, resolve_model_params, save_champion,
                                  load_champion)
from sports.soccer.team_features import add_team_features, three_way_from_lambdas


def test_three_way_logloss_endpoints():
    # perfect probability on the actual outcome -> 0; uniform -> ln(3).
    assert three_way_logloss(["H"], [1.0], [0.0], [0.0]) == 0.0
    uni = three_way_logloss(["H", "D", "A"], [1/3]*3, [1/3]*3, [1/3]*3)
    assert abs(uni - math.log(3)) < 1e-9


def test_dixon_coles_negative_rho_inflates_draws():
    base = three_way_from_lambdas(1.4, 1.1, dixon_coles_rho=0.0)
    dc = three_way_from_lambdas(1.4, 1.1, dixon_coles_rho=-0.13)
    for p in (base, dc):
        assert abs(p["p_home"] + p["p_draw"] + p["p_away"] - 1.0) < 1e-9
    assert dc["p_draw"] > base["p_draw"]           # negative rho pushes mass into draws


def test_resolve_model_params_folds_over_baseline():
    assert resolve_model_params("soccer", ["SOC-01"]) == BASELINE_PARAMS
    assert resolve_model_params("soccer", ["SOC-01", "SOC-02"])["dixon_coles"] is True
    assert resolve_model_params("soccer", ["SOC-01", "SOC-03"])["cross_season"] is True
    # market-blind: no param references a betting line
    assert not any("market" in k.lower() or "line" in k.lower()
                   for k in resolve_model_params("soccer", ["SOC-01"]))


def test_unknown_soccer_builder_raises():
    import pytest
    with pytest.raises(ValueError):
        resolve_model_params("soccer", ["SOC-99"])


def test_soccer_champion_is_param_based_and_roundtrips(tmp_path, monkeypatch):
    import experiments.champion as champ_mod
    c = ChampionConfig.new("soccer", "soccer-v1", 1, ["SOC-01"])
    assert c.feature_cols == []                    # param sport: no feature columns
    assert c.model_params["roll"] == 6 and c.model_params["cross_season"] is False
    monkeypatch.setattr(champ_mod, "CHAMPION_DIR", tmp_path)
    save_champion(ChampionConfig.new("soccer", "soccer-v2", 2, ["SOC-01", "SOC-03"]))
    loaded = load_champion("soccer")
    assert loaded.model_params["cross_season"] is True and loaded.feature_cols == []


def test_soccer_roadmap_sport_level_keep_rule_and_queue():
    rm = roadmap.load_roadmap()
    exp = roadmap.get_experiment(rm, "soccer", "SOC-02")
    kr = roadmap.keep_rule_for(rm, "soccer", exp)
    # the sport-level override wins over the global default (winner_logloss)
    assert kr["metric"] == "three_way_logloss" and kr["guard_metric"] == "three_way_acc"
    assert roadmap.next_unrun(rm, "soccer", set())["id"] == "SOC-02"
    assert roadmap.next_unrun(rm, "soccer", {"SOC-02"})["id"] == "SOC-03"
    # the binary sports are untouched by the sport-level rule
    nfl = roadmap.keep_rule_for(rm, "nfl", roadmap.get_experiment(rm, "nfl", "NFL-06"))
    assert nfl["metric"] == "winner_logloss"


def _synth_matches(seasons=(2021, 2022, 2023), teams=8) -> pd.DataFrame:
    """Synthetic EPL-like double round-robin; home teams score a touch more."""
    rng = np.random.RandomState(7)
    names = [f"T{i}" for i in range(teams)]
    rows = []
    for s in seasons:
        d = pd.Timestamp(f"{s}-08-10")
        for i in range(teams):
            for j in range(teams):
                if i == j:
                    continue
                rows.append({"season": str(s), "date": d, "home": names[i], "away": names[j],
                             "fthg": int(rng.poisson(1.5)), "ftag": int(rng.poisson(1.1))})
                d += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def test_walk_forward_3way_on_synthetic_matches():
    bt = walk_forward_3way(_synth_matches(), params={"min_prior": 1})
    assert not bt.empty
    for col in ("three_way_logloss", "three_way_acc", "total_mae", "draw_pred", "draw_act"):
        assert col in bt.columns
    assert (bt["three_way_logloss"] > 0).all()
    assert (bt["three_way_acc"].between(0.0, 1.0)).all()
    agg = summarize_3way(bt)
    assert agg["games"] > 0 and agg["three_way_logloss"] > 0


def test_cross_season_prior_is_leakage_safe_and_runs():
    m = _synth_matches()
    base = add_team_features(m, cross_season=False)
    blended = add_team_features(m, cross_season=True)
    # first season has no prior -> cross-season leaves it neutral where n_prior==0
    s1 = blended[(blended["season"] == "2021")]
    assert (s1.loc[s1["home_n_prior"] == 0, "home_attack"] == 1.0).all()
    # ratings still finite + present for both variants
    assert base["home_attack"].notna().all() and blended["home_attack"].notna().all()
