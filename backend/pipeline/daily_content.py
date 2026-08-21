#!/usr/bin/env python3
"""The daily content loop — the one command a schedule runs.

For a sport + date: predict the slate (team model), fetch free odds, select
best bets, LOCK the predictions immutably, render shareable cards, and grade the
previous day against actual outcomes. A human then reviews content_output/{date}/
and posts.

Dependency-injectable (games / team_predictor / odds_provider / dist_lookup) so
it's testable without network or heavy models.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import CONTENT_OUTPUT_DIR, KAGGLE_TEAM_GAMES_PARQUET
from content.render import render_slate
from picks.best_bet import select_best_bets
from sports.base import available_sports, get_sport
from track_record.aggregate import headline
from track_record.grade import append_ledger, grade_date
from track_record.lock import lock_predictions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_ledger() -> pd.DataFrame:
    from track_record.grade import RESULTS_LEDGER

    return pd.read_parquet(RESULTS_LEDGER) if RESULTS_LEDGER.exists() else pd.DataFrame()


def _nfl_outcomes_for_date(game_date: str) -> Dict[str, Dict[str, float]]:
    """Final NFL scores by game_key for a date, from nflverse schedules (which
    carry home_score/away_score). Unplayed games (NaN scores) are skipped."""
    from sports.base import get_sport
    from sports.nfl import data as nfl_data

    date = str(game_date)[:10]
    season = int(get_sport("nfl").season_from_date(date))
    try:
        s = nfl_data.load_schedules([season])
    except Exception as e:  # nflverse fetch is best-effort
        logger.info("NFL outcomes fetch failed for %s: %s", date, e)
        return {}
    s = s[s["game_date"].astype(str).str[:10] == date]
    out: Dict[str, Dict[str, float]] = {}
    for _, r in s.iterrows():
        hs, aw = r.get("home_score"), r.get("away_score")
        if pd.isna(hs) or pd.isna(aw):
            continue  # not played yet
        out[f"nfl:{date}:{r['away']}@{r['home']}"] = {"home_pts": float(hs), "away_pts": float(aw)}
    return out


def _mlb_outcomes_for_date(game_date: str) -> Dict[str, Dict[str, float]]:
    """Final MLB scores by game_key for a date, from the StatsAPI schedule (which
    carries home_score/away_score once status == Final)."""
    from sports.base import get_sport
    from sports.mlb import data as mlb_data

    date = str(game_date)[:10]
    season = int(get_sport("mlb").season_from_date(date))
    try:
        s = mlb_data.load_schedules([season])
    except Exception as e:  # StatsAPI fetch is best-effort
        logger.info("MLB outcomes fetch failed for %s: %s", date, e)
        return {}
    s = s[s["game_date"].astype(str).str[:10] == date]
    s = s[s["status"] == "Final"].dropna(subset=["home_score", "away_score"])
    out: Dict[str, Dict[str, float]] = {}
    for _, r in s.iterrows():
        out[f"mlb:{date}:{r['away']}@{r['home']}"] = {"home_pts": float(r["home_score"]),
                                                      "away_pts": float(r["away_score"])}
    return out


def _nhl_outcomes_for_date(game_date: str) -> Dict[str, Dict[str, float]]:
    """Final NHL scores by game_key for a date, from the NHL API schedule (goals,
    with gameState OFF/FINAL marking a completed game)."""
    from sports.base import get_sport
    from sports.nhl import data as nhl_data

    date = str(game_date)[:10]
    season = int(get_sport("nhl").season_from_date(date))  # NHL start-year == loader key
    try:
        s = nhl_data.load_schedules([season])
    except Exception as e:  # NHL API fetch is best-effort
        logger.info("NHL outcomes fetch failed for %s: %s", date, e)
        return {}
    s = s[s["game_date"].astype(str).str[:10] == date]
    s = s[s["status"].isin(["OFF", "FINAL"])].dropna(subset=["home_goals", "away_goals"])
    out: Dict[str, Dict[str, float]] = {}
    for _, r in s.iterrows():
        out[f"nhl:{date}:{r['away']}@{r['home']}"] = {"home_pts": float(r["home_goals"]),
                                                      "away_pts": float(r["away_goals"])}
    return out


def _soccer_outcomes_for_date(game_date: str) -> Dict[str, Dict[str, float]]:
    """Final EPL scores (goals) by game_key for a date, from the football-data.co.uk
    results cache. Only EPL has a free results feed wired; UCL/MLS locked slates won't
    grade until one is added. Team names fold to the same canonical identity as the
    Odds-API-sourced schedule via sports.soccer.teams.canonical_team, so the keys match
    the locked picks. Home/away picks graded on the score are correct even for draws
    (a draw loses a home/away moneyline); the pick pipeline emits no draw side."""
    from sports.base import get_sport
    from sports.soccer.team_features import build_epl_matches

    date = str(game_date)[:10]
    season = int(get_sport("soccer").season_from_date(date))  # European start-year
    try:
        m = build_epl_matches([season])
    except Exception as e:  # football-data fetch is best-effort
        logger.info("soccer outcomes fetch failed for %s: %s", date, e)
        return {}
    if m is None or m.empty or "date" not in m.columns:
        return {}
    m = m[m["date"].astype(str).str[:10] == date].dropna(subset=["fthg", "ftag"])
    out: Dict[str, Dict[str, float]] = {}
    for _, r in m.iterrows():
        out[f"soccer:{date}:{r['away']}@{r['home']}"] = {"home_pts": float(r["fthg"]),
                                                         "away_pts": float(r["ftag"])}
    return out


def outcomes_for_date(sport: str, game_date: str, parquet: Path = KAGGLE_TEAM_GAMES_PARQUET) -> Dict[str, Dict[str, float]]:
    """Final scores by game_key for a date (for grading). Dispatches by sport: NFL
    from nflverse schedules, MLB/NHL from their StatsAPI/NHL-API schedule loaders,
    soccer (EPL) from the football-data results cache, NBA from the team parquet."""
    if sport == "nfl":
        return _nfl_outcomes_for_date(game_date)
    if sport == "mlb":
        return _mlb_outcomes_for_date(game_date)
    if sport == "nhl":
        return _nhl_outcomes_for_date(game_date)
    if sport == "soccer":
        return _soccer_outcomes_for_date(game_date)
    if not Path(parquet).exists():
        return {}
    from sports.nba.teams import canonical_team

    df = pd.read_parquet(parquet, columns=["game_id", "game_date", "is_home_team", "team", "pts"])
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
    df = df[df["game_date"] == game_date]
    out: Dict[str, Dict[str, float]] = {}
    for gid, g in df.groupby("game_id"):
        home = g[g["is_home_team"] == 1]
        away = g[g["is_home_team"] == 0]
        if len(home) != 1 or len(away) != 1:
            continue
        h = canonical_team(home.iloc[0]["team"], strict=False)
        a = canonical_team(away.iloc[0]["team"], strict=False)
        key = f"nba:{game_date}:{a}@{h}"
        out[key] = {"home_pts": float(home.iloc[0]["pts"]), "away_pts": float(away.iloc[0]["pts"])}
    return out


def _default_prop_model(game_date: str, games: List[Dict[str, str]], season: str):
    """Player-prop projections from the clean v3 model (recent-form + minutes +
    availability), wrapped as NB predictive distributions for over/under. Replaces
    the deprecated global_lgbm path, which was degenerate (projection == L10)."""
    from models.distribution import PoissonNBHead
    from models.nba_player_predictor_v3 import default_nba_player_predictor_v3
    from picks.slate_props import SlatePropModel
    from sports.nba.roster import player_display_name, player_game_context

    v3 = default_nba_player_predictor_v3()

    def _predict(slug, opponent, is_home, date, seas):
        proj = v3.predict_player(player_display_name(slug)) or {}
        # REB is composed from OREB+DREB heads downstream; skip the summed convenience key.
        return {s: PoissonNBHead(mu=float(mu), dispersion=v3.dispersion(s))
                for s, mu in proj.items() if s != "REB"}

    return SlatePropModel(game_date, games, season, predict_distribution=_predict, context_fn=player_game_context)


def _build_prop_cards(prop_model, picks, star_players) -> List[Dict[str, Any]]:
    from sports.nba.roster import player_display_name

    slugs: List[str] = []
    for p in picks:
        if p.market_family == "player_prop" and p.subject not in slugs:
            slugs.append(p.subject)
    for s in (star_players or []):
        if s not in slugs:
            slugs.append(s)

    cards: List[Dict[str, Any]] = []
    for slug in slugs[:6]:
        proj = prop_model.projections(slug)
        if not proj:
            continue
        cards.append({"player_name": player_display_name(slug), "projections": proj,
                      "matchup": prop_model.matchup(slug)})
    return cards


def _sport_slate_props(sport: str, games, season: str) -> List[Dict[str, Any]]:
    """Marquee prop cards for sports that expose a slate enumerator, dispatched by
    sport. NFL: skill-position yardage. MLB: probable-starter strikeouts + regular
    hitters (hits/TB/HR). NHL: marquee skaters (points/shots). Each enumerator filters
    to the day's teams via the player's roster team. (NBA uses the injected prop_model
    / star_players path above.) Never raises — slate props are best-effort content."""
    try:
        if sport == "nfl":
            from models.nfl_player_predictor import default_nfl_player_predictor
            return default_nfl_player_predictor().slate_projections(games, season=season)
        if sport == "mlb":
            from models.mlb_batter_predictor import default_mlb_batter_predictor
            from models.mlb_pitcher_predictor import default_mlb_pitcher_predictor
            cards = default_mlb_pitcher_predictor().slate_projections(games, season=season)
            cards += default_mlb_batter_predictor().slate_projections(games, season=season)
            return cards
        if sport == "nhl":
            from models.nhl_skater_predictor import default_nhl_skater_predictor
            return default_nhl_skater_predictor().slate_projections(games, season=season)
        if sport == "soccer":
            # No free player-stats feed to model soccer props; the market is the ceiling.
            # Surface marquee matches' top market-implied anytime scorers (quota-capped).
            from sports.soccer.goalscorer_odds import fetch_anytime_goalscorer
            cards: List[Dict[str, Any]] = []
            for ev in fetch_anytime_goalscorer(max_events=3, top_k=2):
                matchup = f"{ev['home']} vs {ev['away']}"
                for player, prob in ev["scorers"]:
                    cards.append({"player_name": player, "sport": "soccer", "matchup": matchup,
                                  "projections": {"anytime_scorer_pct": round(prob * 100)}})
            return cards
    except Exception as e:  # slate props are best-effort content, never fatal
        logger.warning("slate props unavailable for %s %s: %s", sport, season, e)
    return []


def _attach_closing_moneyline(picks: List[Any], team_lines: List[Any]) -> int:
    """Settle each market-blind winner pick at the real captured closing moneyline.

    The picks stay MARKET-BLIND (the winner is chosen by the model alone, before this
    runs). Here we only look up the captured moneyline ``OddsLine`` matching a pick's
    (game_key, side) and set that pick's ``odds_american`` (+ display ``ev``) to the
    genuine closing price, so grading yields honest flat-stakes units. A pick with no
    captured moneyline keeps ``odds_american=None`` (ROI-ineligible) — we NEVER
    fabricate a price. Returns the number of picks priced (for logging/tests)."""
    from utils.odds_math import american_to_decimal, expected_value

    priced_lines = {
        (ln.game_key, ln.side): ln.odds_american
        for ln in (team_lines or [])
        if getattr(ln, "market_family", None) == "moneyline" and ln.odds_american is not None
    }
    if not priced_lines:
        return 0
    n = 0
    for p in picks:
        if p.market_family != "moneyline" or p.odds_american is not None:
            continue  # only settle the odds-free winner picks; never overwrite a price
        odds = priced_lines.get((p.game_key, p.side))
        if odds is None:
            continue
        p.odds_american = int(odds)
        p.ev = round(expected_value(p.model_prob, american_to_decimal(odds)), 4)
        n += 1
    return n


def run_day(
    sport: str,
    game_date: str,
    *,
    games: Optional[List[Dict[str, str]]] = None,
    team_predictor: Any = None,
    odds_provider: Any = None,
    dist_lookup: Optional[Callable[[str, str], Any]] = None,
    prop_model: Any = None,
    star_players: Optional[List[str]] = None,
    do_lock: bool = True,
    do_render: bool = True,
    out_root: Path = CONTENT_OUTPUT_DIR,
    model_version: str = "",
) -> Dict[str, Any]:
    sp = get_sport(sport)
    if games is None:
        games = sp.schedule(game_date)

    season = sp.season_from_date(game_date)

    # Team/score predictions route through the sport plugin, so every sport uses
    # its own model (nba -> team_predictor, nfl -> nfl_team_predictor, ...). An
    # explicitly injected team_predictor still wins (dependency injection for tests).
    game_preds = []
    for g in games:
        if team_predictor is not None:
            gp = team_predictor.predict_game(home=g["home"], away=g["away"], game_date=game_date)
        else:
            gp = sp.predict_game(home=g["home"], away=g["away"], game_date=game_date, season=season)
        if gp is not None:
            game_preds.append(gp)

    team_lines = odds_provider.fetch_game_markets(sport, game_date) if odds_provider else []
    prop_lines = odds_provider.fetch_player_props(sport, game_date) if odds_provider else []

    # The default prop model is NBA-specific (SlatePropModel + NBA roster); other
    # sports must inject their own prop_model/dist_lookup to get prop cards.
    if prop_model is None and dist_lookup is None and sport == "nba" and (prop_lines or star_players):
        prop_model = _default_prop_model(game_date, games, season)
    lookup = dist_lookup or (prop_model.dist_lookup() if prop_model else (lambda subj, stat: None))
    picks = select_best_bets(game_preds, team_lines, prop_lines, lookup)
    _attach_closing_moneyline(picks, team_lines)

    if do_lock and game_preds:
        try:
            lock_predictions(sport, game_date, game_preds, picks, model_version=model_version)
        except FileExistsError:
            logger.info("%s %s already locked — leaving the immutable snapshot intact", sport, game_date)

    prop_cards = _build_prop_cards(prop_model, picks, star_players) if prop_model else []
    if not prop_cards:
        prop_cards = _sport_slate_props(sport, games, season)

    record = headline(_load_ledger())
    cards: List[Path] = []
    if do_render and game_preds:
        cards = render_slate(game_date, game_preds, picks, record, out_root=out_root, prop_cards=prop_cards)

    summary = {"sport": sport, "game_date": game_date, "games": len(game_preds),
               "picks": len(picks), "prop_cards": len(prop_cards), "cards": len(cards), "record": record}
    logger.info("daily_content: %s", summary)
    return summary


def grade_previous_day(sport: str, game_date: str, parquet: Path = KAGGLE_TEAM_GAMES_PARQUET) -> int:
    """Grade an already-locked date against final scores; append to the ledger."""
    outcomes = outcomes_for_date(sport, game_date, parquet)
    if not outcomes:
        logger.info("no outcomes for %s %s yet", sport, game_date)
        return 0
    try:
        df = grade_date(sport, game_date, outcomes)
    except FileNotFoundError:
        logger.info("no lock to grade for %s %s", sport, game_date)
        return 0
    added = append_ledger(df)
    logger.info("graded %s %s: %d picks (+%d ledger rows)", sport, game_date, len(df), added)
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="nba", help='sport key, or "all" for every registered sport')
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--grade-date", default=None, help="also grade this prior date's locked slate")
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    sports = available_sports() if args.sport == "all" else [args.sport]
    # Inject a live game-market provider so the automated run GENERATES picks (spread/
    # total) -> locks them -> grades them next day, auto-populating the public track
    # record. Fails soft per sport (no key / off-season / down feed -> no picks). NBA/
    # NFL only for now; other sports lock predictions without team picks as before.
    from odds.providers.live_market import LiveMarketProvider
    odds_provider = LiveMarketProvider()
    for sport in sports:
        # Best-effort per sport: an out-of-season slate, a down data feed, or a
        # missing model must not abort the other sports' cards (the daily loop runs
        # all five together via `--sport all`).
        try:
            if args.grade_date:
                grade_previous_day(sport, args.grade_date)
            run_day(sport, args.date, odds_provider=odds_provider,
                    do_lock=not args.no_lock, do_render=not args.no_render)
        except Exception as e:
            logger.warning("daily_content: %s failed for %s: %s", sport, args.date, e)


if __name__ == "__main__":
    main()
