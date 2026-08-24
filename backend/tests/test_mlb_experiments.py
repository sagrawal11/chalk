"""MLB fan-out into the feature-experiment harness (M7) — hermetic (no StatsAPI).

Covers the MLB builder registry (market-blind), full frame-column coverage, the
pre-registered roadmap queue, the seed, the shared walk-forward on a synthetic MLB
frame (single-year labels), and the SP_ERA cost gate — building the box-score frame
with ``fetch_sp_era=False`` must never trigger the per-pitcher game-log backfill.
The real data-dependent run is exercised against live StatsAPI in the M7 demo.
"""
import numpy as np
import pandas as pd

from experiments import roadmap
from experiments.champion import FEATURE_BUILDERS, ChampionConfig, resolve_feature_cols


def test_mlb_rung1_resolves_and_is_market_blind():
    cols = resolve_feature_cols("mlb", ["MLB-01", "MLB-02", "MLB-03", "MLB-04", "MLB-05"])
    assert cols == ["HOME_OFF", "AWAY_OFF", "HOME_DEF", "AWAY_DEF", "NET_DIFF",
                    "HOME_WINPCT", "AWAY_WINPCT", "HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"]
    assert not any("MARKET" in c for c in cols)  # champion is market-blind


def test_mlb_sp_and_form_builders_resolve():
    assert resolve_feature_cols("mlb", ["MLB-06"]) == ["HOME_FORM", "AWAY_FORM"]
    assert resolve_feature_cols("mlb", ["MLB-20"]) == ["HOME_SP_RA", "AWAY_SP_RA", "SP_RA_DIFF"]
    assert resolve_feature_cols("mlb", ["MLB-21"]) == ["HOME_SP_ERA", "AWAY_SP_ERA", "SP_ERA_DIFF"]


def test_mlb_builders_cover_all_team_feature_cols():
    """Every column the MLB frame emits is reachable from exactly the builders, and
    no builder points at a column the frame doesn't produce (typo guard)."""
    from sports.mlb.team_features import TEAM_FEATURE_COLS
    mapped = {c for cols in FEATURE_BUILDERS["mlb"].values() for c in cols}
    assert mapped == set(TEAM_FEATURE_COLS)
    assert not any("MARKET" in c for c in mapped)


def test_mlb_seed_resolves_to_box_score_champion():
    from experiments.eval_champion import _SEEDS
    c = ChampionConfig.new("mlb", **_SEEDS["mlb"])
    assert c.model_version == "mlb-v1" and c.rung == 1
    assert c.feature_cols[0] == "HOME_OFF"
    assert not any("SP_" in col for col in c.feature_cols)  # day-1 champ has no pitcher signal


def test_mlb_roadmap_queue_and_keep_rule():
    rm = roadmap.load_roadmap()
    exps = roadmap.experiments_for(rm, "mlb")
    assert {e["id"] for e in exps} >= {"MLB-06", "MLB-20", "MLB-21", "MLB-07"}
    kr = roadmap.keep_rule_for(rm, "mlb", roadmap.get_experiment(rm, "mlb", "MLB-06"))
    assert kr["metric"] == "winner_logloss" and kr["min_delta"] == 0.0005
    # queue advances by the ledger's run-ids, form first then the starting pitcher
    assert roadmap.next_unrun(rm, "mlb", set())["id"] == "MLB-06"
    assert roadmap.next_unrun(rm, "mlb", {"MLB-06"})["id"] == "MLB-20"


def test_walk_forward_backtest_mlb_single_year_labels():
    """The shared harness runs on an MLB frame: single-year season labels + a finite
    winner log-loss (MLB is low-signal, so SU stays modest — that's honest)."""
    from backtest.team_backtest import summarize, walk_forward_backtest

    rng = np.random.RandomState(1)
    rows = []
    for season in range(2015, 2021):
        for g in range(200):
            strength = rng.normal(0.3, 1.5)          # small home edge (MLB-ish)
            margin = strength + rng.normal(0, 3.0)   # tight run margins
            total = 9 + rng.normal(0, 3)
            rows.append({
                "season": season, "game_date": f"{season}-06-{(g % 27) + 1:02d}",
                "home": f"H{g%6}", "away": f"A{g%6}",
                "y_margin": margin, "y_total": total,
                "F_STRENGTH": strength, "F_NOISE": rng.normal(0, 1),
            })
    frame = pd.DataFrame(rows)
    bt = walk_forward_backtest(frame, sport="mlb", feature_cols=["F_STRENGTH", "F_NOISE"],
                               params={"random_state": 42, "n_jobs": 1, "verbose": -1})
    assert not bt.empty
    assert (bt["season"].str.match(r"^\d{4}$")).all()   # MLB single-year labels
    agg = summarize(bt)
    assert agg["winner_logloss"] is not None and agg["winner_logloss"] > 0
    assert 0.0 <= agg["su_acc"] <= 1.0


def _fake_team_games(seasons=(2020, 2021), n=40) -> pd.DataFrame:
    """A tiny synthetic one-row-per-team-game frame shaped like sports.mlb.data."""
    teams = ["AAA", "BBB", "CCC", "DDD"]
    rows, gid = [], 0
    for season in seasons:
        for i in range(n):
            h, a = teams[i % 4], teams[(i + 1) % 4]
            date = pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=i)
            base = {"game_id": gid, "season": season, "game_date": date}
            rows.append({**base, "team": h, "opponent": a, "is_home": 1,
                         "runs": 5.0, "opp_runs": 3.0, "sp": 100 + i, "opp_sp": 200 + i})
            rows.append({**base, "team": a, "opponent": h, "is_home": 0,
                         "runs": 3.0, "opp_runs": 5.0, "sp": 200 + i, "opp_sp": 100 + i})
            gid += 1
    df = pd.DataFrame(rows)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def test_fetch_sp_era_false_skips_the_pitcher_backfill(monkeypatch):
    """The box-score ladder builds the frame WITHOUT the network-heavy per-pitcher
    ERA fetch; SP_ERA falls back to the league-average constant fill."""
    import sports.mlb.pitcher_data as pitcher_data
    import sports.mlb.team_features as tf

    monkeypatch.setattr(tf, "load_team_games", lambda years: _fake_team_games())

    def _must_not_fetch(years):
        raise AssertionError("build_pitcher_starts must not run when fetch_sp_era=False")

    monkeypatch.setattr(pitcher_data, "build_pitcher_starts", _must_not_fetch)

    frame = tf.build_team_game_frame([2020, 2021], fetch_sp_era=False)
    assert not frame.empty
    assert set(tf.TEAM_FEATURE_COLS).issubset(frame.columns)
    # SP_ERA never fetched -> league-average constant for every game
    assert (frame["HOME_SP_ERA"] == tf._LEAGUE_ERA).all()
    assert (frame["AWAY_SP_ERA"] == tf._LEAGUE_ERA).all()
