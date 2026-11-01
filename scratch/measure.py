"""Reusable OOS referee for the accuracy loop (binary-margin sports).

Builds a sport's team-game frame ONCE, holds the most-recent full season UNTOUCHED
(the honest test set), and runs backtest.walk_forward_backtest on train+CV for each
named feature-col set so a baseline vs challenger is measured on identical data.

Soccer has its own 3-way path (backtest.soccer_backtest), measured separately.

Usage (from backend/):
    python ../scratch/measure.py nfl
    python ../scratch/measure.py mlb --sp-era
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Dict, List

warnings.filterwarnings("ignore")

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from backtest.team_backtest import summarize, walk_forward_backtest
from experiments.eval_champion import DETERMINISTIC_PARAMS, _pick_holdout


def build_frame(sport: str, start: int, end: int, *, fetch_sp_era: bool = False):
    if sport == "nfl":
        from sports.nfl.team_features import build_team_game_frame
        return build_team_game_frame(range(start, end + 1))
    if sport == "nhl":
        from sports.nhl.team_features import build_team_game_frame
        return build_team_game_frame(range(start, end + 1))
    if sport == "mlb":
        from sports.mlb.team_features import build_team_game_frame
        return build_team_game_frame(range(start, end + 1), fetch_sp_era=fetch_sp_era)
    raise ValueError(sport)


def measure(sport: str, frame, col_sets: Dict[str, List[str]]):
    frame = frame.copy()
    frame["season"] = frame["season"].astype(int)
    holdout = _pick_holdout(frame)
    traincv = frame[frame["season"] < holdout].copy()
    print(f"\n=== {sport.upper()} === frame={len(frame)} games, "
          f"seasons {frame['season'].min()}-{frame['season'].max()}, "
          f"untouched holdout={holdout}, train+CV games={len(traincv)}")
    out = {}
    for label, cols in col_sets.items():
        missing = [c for c in cols if c not in traincv.columns]
        if missing:
            print(f"  [{label}] SKIP missing cols: {missing}")
            continue
        bt = walk_forward_backtest(traincv, sport=sport, feature_cols=cols,
                                   params=DETERMINISTIC_PARAMS)
        m = summarize(bt)
        out[label] = m
        print(f"  [{label}] ({len(cols)} cols) su_acc={m.get('su_acc')} "
              f"winner_logloss={m.get('winner_logloss')} "
              f"margin_mae={m.get('margin_mae')} total_mae={m.get('total_mae')} "
              f"(n={m.get('games')}, seasons={m.get('seasons')})")
    # deltas vs the first set (treated as baseline)
    labels = list(out.keys())
    if len(labels) >= 2:
        base = out[labels[0]]
        print(f"  --- deltas vs [{labels[0]}] (negative margin/total/logloss = better) ---")
        for lab in labels[1:]:
            d = out[lab]
            def dl(k):
                a, b = d.get(k), base.get(k)
                return round(a - b, 4) if (a is not None and b is not None) else None
            print(f"  [{lab}] d_su_acc={dl('su_acc'):+} d_winner_logloss={dl('winner_logloss'):+} "
                  f"d_margin_mae={dl('margin_mae'):+} d_total_mae={dl('total_mae'):+}")
    return out


if __name__ == "__main__":
    sport = sys.argv[1] if len(sys.argv) > 1 else "nfl"
    sp_era = "--sp-era" in sys.argv

    if sport == "nfl":
        from sports.nfl.team_features import TEAM_FEATURE_COLS
        fr = build_frame("nfl", 2010, 2025)
        measure("nfl", fr, {
            "baseline(served)": TEAM_FEATURE_COLS,
            "+opp_adj_OFF": TEAM_FEATURE_COLS + ["HOME_OFF_ADJ", "AWAY_OFF_ADJ"],
            "+opp_adj_OFF+DEF": TEAM_FEATURE_COLS + ["HOME_OFF_ADJ", "AWAY_OFF_ADJ",
                                                     "HOME_DEF_ADJ", "AWAY_DEF_ADJ"],
        })
    elif sport == "nhl":
        from sports.nhl.team_features import TEAM_FEATURE_COLS
        fr = build_frame("nhl", 2015, 2025)
        measure("nhl", fr, {"baseline(served)": TEAM_FEATURE_COLS})
    elif sport == "mlb":
        from sports.mlb.team_features import TEAM_FEATURE_COLS
        base_no_era = [c for c in TEAM_FEATURE_COLS if "SP_ERA" not in c]
        fr = build_frame("mlb", 2015, 2025, fetch_sp_era=sp_era)
        measure("mlb", fr, {
            "baseline_no_SP_ERA": base_no_era,
            "+SP_ERA" + ("(real)" if sp_era else "(league-fill)"): TEAM_FEATURE_COLS,
        })
