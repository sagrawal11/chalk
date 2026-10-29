"""NHL fan-out into the feature-experiment harness (M7). Hermetic (no NHL API).

Covers the NHL builder registry (team features only), full frame-column coverage, the
pre-registered roadmap queue, the seed, the shared walk-forward on a synthetic NHL
frame (two-year season labels), and frame assembly from a synthetic team-game frame.
The real data-dependent run is exercised against the cached/live NHL API in the M7 demo.
"""
import numpy as np
import pandas as pd

from experiments import roadmap
from experiments.champion import FEATURE_BUILDERS, ChampionConfig, resolve_feature_cols


def test_nhl_rung1_resolves_without_market_cols():
    cols = resolve_feature_cols("nhl", ["NHL-01", "NHL-02", "NHL-03", "NHL-04", "NHL-05"])
    assert cols == ["HOME_OFF", "AWAY_OFF", "HOME_DEF", "AWAY_DEF", "NET_DIFF",
                    "HOME_WINPCT", "AWAY_WINPCT", "HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"]
    assert not any("MARKET" in c for c in cols)  # no betting line in features


def test_nhl_form_and_rest_builders_resolve():
    assert resolve_feature_cols("nhl", ["NHL-06"]) == ["HOME_FORM", "AWAY_FORM"]
    assert resolve_feature_cols("nhl", ["NHL-07"]) == ["HOME_REST", "AWAY_REST", "REST_DIFF"]


def test_nhl_builders_cover_all_team_feature_cols():
    from sports.nhl.team_features import TEAM_FEATURE_COLS
    mapped = {c for cols in FEATURE_BUILDERS["nhl"].values() for c in cols}
    assert mapped == set(TEAM_FEATURE_COLS)
    assert not any("MARKET" in c for c in mapped)


def test_nhl_seed_resolves_to_box_score_champion():
    from experiments.eval_champion import _SEEDS
    c = ChampionConfig.new("nhl", **_SEEDS["nhl"])
    assert c.model_version == "nhl-v1" and c.rung == 1
    assert c.feature_cols[0] == "HOME_OFF"


def test_nhl_roadmap_queue_and_needs_builder_goalie():
    rm = roadmap.load_roadmap()
    exps = roadmap.experiments_for(rm, "nhl")
    assert {e["id"] for e in exps} >= {"NHL-06", "NHL-07", "NHL-20"}
    kr = roadmap.keep_rule_for(rm, "nhl", roadmap.get_experiment(rm, "nhl", "NHL-06"))
    assert kr["metric"] == "winner_logloss" and kr["min_delta"] == 0.0005
    # queue advances form then rest; the goalie rung is needs_builder (never auto-run)
    assert roadmap.next_unrun(rm, "nhl", set())["id"] == "NHL-06"
    assert roadmap.next_unrun(rm, "nhl", {"NHL-06"})["id"] == "NHL-07"
    assert roadmap.get_experiment(rm, "nhl", "NHL-20")["status"] == "needs_builder"


def test_walk_forward_backtest_nhl_two_year_labels():
    """The shared harness runs on an NHL frame with two-year season labels
    (2015 -> '2015-16') and a finite winner log-loss."""
    from backtest.team_backtest import summarize, walk_forward_backtest

    rng = np.random.RandomState(2)
    rows = []
    for season in range(2015, 2021):
        for g in range(220):
            strength = rng.normal(0.3, 1.2)          # small home edge
            margin = strength + rng.normal(0, 2.2)   # tight goal margins
            total = 6 + rng.normal(0, 2)
            rows.append({
                "season": season, "game_date": f"{season}-11-{(g % 27) + 1:02d}",
                "home": f"H{g%8}", "away": f"A{g%8}",
                "y_margin": margin, "y_total": total,
                "F_STRENGTH": strength, "F_NOISE": rng.normal(0, 1),
            })
    frame = pd.DataFrame(rows)
    bt = walk_forward_backtest(frame, sport="nhl", feature_cols=["F_STRENGTH", "F_NOISE"],
                               params={"random_state": 42, "n_jobs": 1, "verbose": -1})
    assert not bt.empty
    assert (bt["season"].str.match(r"^\d{4}-\d{2}$")).all()   # NHL two-year labels
    agg = summarize(bt)
    assert agg["winner_logloss"] is not None and agg["winner_logloss"] > 0


def _fake_team_games(seasons=(2020, 2021), n=40) -> pd.DataFrame:
    """A tiny synthetic one-row-per-team-game frame shaped like sports.nhl.data."""
    teams = ["AAA", "BBB", "CCC", "DDD"]
    rows, gid = [], 0
    for season in seasons:
        for i in range(n):
            h, a = teams[i % 4], teams[(i + 1) % 4]
            date = pd.Timestamp(f"{season}-10-05") + pd.Timedelta(days=i)
            base = {"game_id": gid, "season": season, "game_date": date}
            rows.append({**base, "team": h, "opponent": a, "is_home": 1,
                         "goals": 3.0, "opp_goals": 2.0})
            rows.append({**base, "team": a, "opponent": h, "is_home": 0,
                         "goals": 2.0, "opp_goals": 3.0})
            gid += 1
    df = pd.DataFrame(rows)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def test_honest_readout_finds_two_year_holdout_row(monkeypatch):
    """Regression: honest_readout must locate the untouched holdout row by the sport's
    own season label. Two-year sports (NHL/NBA) label 2020 as '2020-21', so a bare
    str(holdout) lookup returns empty and crashes. Fully hermetic (synthetic frame)."""
    import experiments.honest_readout as hr
    from experiments.champion import ChampionConfig

    rng = np.random.RandomState(3)
    rows = []
    for season in range(2015, 2021):
        for g in range(220):
            strength = rng.normal(0.3, 1.2)
            rows.append({"season": season, "game_date": f"{season}-11-{(g % 27) + 1:02d}",
                         "home": f"H{g%8}", "away": f"A{g%8}",
                         "y_margin": strength + rng.normal(0, 2.2), "y_total": 6 + rng.normal(0, 2),
                         "HOME_OFF": strength, "AWAY_OFF": rng.normal(0, 1)})
    frame = pd.DataFrame(rows)
    champ = ChampionConfig.new("nhl", "nhl-v1", 1, ["NHL-01"])  # -> HOME_OFF, AWAY_OFF
    monkeypatch.setattr(hr, "_build_frame", lambda sport, start, end, feature_cols=None: frame)
    monkeypatch.setattr(hr, "load_champion", lambda sport: champ)

    r = hr.honest_readout("nhl", start=2015, end=2020)
    # the untouched-test block is populated (the holdout row was found by its 2-year label)
    assert r["untouched_test"]["su_acc"] is not None
    assert r["untouched_test"]["n"] and r["untouched_test"]["n"] > 0


def test_nhl_frame_emits_harness_contract(monkeypatch):
    """build_team_game_frame emits y_margin/y_total/season/game_date + all feature
    columns from a synthetic team-game frame (no network)."""
    import sports.nhl.team_features as tf

    monkeypatch.setattr(tf, "load_team_games", lambda years: _fake_team_games())
    frame = tf.build_team_game_frame([2020, 2021])
    assert not frame.empty
    for col in ("y_margin", "y_total", "season", "game_date", "home", "away"):
        assert col in frame.columns
    assert set(tf.TEAM_FEATURE_COLS).issubset(frame.columns)
    # home team scored 3 vs 2 -> home margin +1 everywhere in the synthetic frame
    assert (frame["y_margin"] == 1.0).all()
