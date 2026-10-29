"""Render shareable, Instagram-sized cards (+ captions) from normalized
predictions / picks / track record. Pillow-based so it works with no browser.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from config.paths import CONTENT_OUTPUT_DIR
from content import brand_config as B

logger = logging.getLogger(__name__)


# --- font + draw helpers ---
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for p in (B.FONT_BOLD if bold else B.FONT_REGULAR):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _center(draw, cx, y, text, font, fill):
    draw.text((cx - _w(draw, text, font) / 2, y), text, font=font, fill=fill)


def _wrap(draw, text, font, max_w) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        t = (cur + " " + word).strip()
        if _w(draw, t, font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _bar(draw, W, y, frac, h=26):
    x0, x1 = W * 0.18, W * 0.82
    draw.rounded_rectangle([x0, y, x1, y + h], radius=h / 2, fill=B.PANEL)
    fw = (x1 - x0) * max(0.03, min(1.0, frac))
    draw.rounded_rectangle([x0, y, x0 + fw, y + h], radius=h / 2, fill=B.WIN)


def _pill(draw, cx, y, text, size, fg=None, bg=None):
    font = _font(size, True)
    tw = _w(draw, text, font)
    padx, h = 44, size + 34
    x0 = cx - (tw + 2 * padx) / 2
    draw.rounded_rectangle([x0, y, x0 + tw + 2 * padx, y + h], radius=h / 2, fill=bg or B.ACCENT)
    draw.text((cx - tw / 2, y + 15), text, font=font, fill=fg or B.BG)


def _base(size):
    img = Image.new("RGB", size, B.BG)
    return img, ImageDraw.Draw(img)


def _footer(draw, size, hashtags=None):
    W, H = size
    y = H - 250
    draw.line([(W * 0.1, y), (W * 0.9, y)], fill=B.PANEL, width=3)
    _center(draw, W / 2, y + 22, f"{B.BRAND}   {B.HANDLE}", _font(30, True), B.TEXT)
    yy = y + 74
    for ln in _wrap(draw, B.DISCLAIMER, _font(22), W * 0.82):
        _center(draw, W / 2, yy, ln, _font(22), B.MUTED)
        yy += 30
    _center(draw, W / 2, H - 44, hashtags or B.HASHTAGS, _font(22), B.MUTED)


def _confidence_label(conf: float) -> str:
    return "HIGH" if conf >= 0.5 else ("MEDIUM" if conf >= 0.2 else "LEAN")


# --- cards ---
def render_score_card(gp, out_dir: Path, size=B.FEED) -> Path:
    # 3-way sports (soccer) get a home/draw/away card instead of a winner bar.
    if getattr(gp, "p_draw", None) is not None:
        return render_score_card_3way(gp, out_dir, size)
    W, H = size
    img, draw = _base(size)
    _center(draw, W / 2, 64, B.BRAND, _font(46, True), B.ACCENT)
    _center(draw, W / 2, 128, "GAME PREDICTION", _font(30, True), B.MUTED)
    _center(draw, W / 2, 172, gp.game_date, _font(28), B.MUTED)

    _center(draw, W / 2, 300, f"{gp.away}   @   {gp.home}", _font(82, True), B.TEXT)
    _center(draw, W / 2, 452, f"{gp.pred_away_pts:.0f}  –  {gp.pred_home_pts:.0f}", _font(150, True), B.ACCENT)

    home_wins = gp.pred_home_pts >= gp.pred_away_pts
    winner = gp.home if home_wins else gp.away
    wp = gp.p_home_win if home_wins else (1 - gp.p_home_win)
    _center(draw, W / 2, 668, f"{winner} WIN  {wp * 100:.0f}%", _font(52, True), B.WIN)
    _bar(draw, W, 752, wp)
    _pill(draw, W / 2, 838, f"CONFIDENCE: {_confidence_label(gp.confidence)}", 34)
    _footer(draw, size, B.hashtags_for(gp.sport))

    out = Path(out_dir) / f"score_{gp.away}_at_{gp.home}.png"
    img.save(out)
    return out


def render_score_card_3way(gp, out_dir: Path, size=B.FEED) -> Path:
    """3-way (home / draw / away) match card for soccer: expected goals + the
    three outcome probabilities as bars, favored outcome highlighted."""
    W, H = size
    img, draw = _base(size)
    _center(draw, W / 2, 64, B.BRAND, _font(46, True), B.ACCENT)
    _center(draw, W / 2, 128, "MATCH PREDICTION", _font(30, True), B.MUTED)
    _center(draw, W / 2, 172, gp.game_date, _font(28), B.MUTED)

    # soccer convention: home team first (home is "at home")
    _center(draw, W / 2, 268, f"{gp.home}  vs  {gp.away}", _font(72, True), B.TEXT)
    _center(draw, W / 2, 400, f"{gp.pred_home_pts:.1f} – {gp.pred_away_pts:.1f}", _font(120, True), B.ACCENT)
    _center(draw, W / 2, 548, "EXPECTED GOALS", _font(28, True), B.MUTED)

    p_home = float(gp.p_home_win)
    p_draw = float(gp.p_draw or 0.0)
    p_away = float(gp.p_away_win if gp.p_away_win is not None else 1.0 - p_home)
    rows = [("HOME", gp.home, p_home), ("DRAW", "", p_draw), ("AWAY", gp.away, p_away)]
    top = max(p_home, p_draw, p_away)
    for i, (label, name, prob) in enumerate(rows):
        y = 620 + i * 150
        color = B.WIN if abs(prob - top) < 1e-9 else B.TEXT
        draw.text((W * 0.18, y), f"{label}  {name}".strip(), font=_font(38, True), fill=color)
        pct, pf = f"{prob * 100:.0f}%", _font(38, True)
        draw.text((W * 0.82 - _w(draw, pct, pf), y), pct, font=pf, fill=color)
        _bar(draw, W, y + 54, prob)

    # 3-way confidence: favorite's distance above a uniform 1/3 tossup, in [0,1]
    conf = max(0.0, (top - 1.0 / 3.0) / (2.0 / 3.0))
    _pill(draw, W / 2, 1010, f"CONFIDENCE: {_confidence_label(conf)}", 34)
    _footer(draw, size, B.hashtags_for(gp.sport))

    out = Path(out_dir) / f"score_{gp.away}_at_{gp.home}.png"
    img.save(out)
    return out


def _describe_pick(pick) -> str:
    mf = pick.market_family
    subj = pick.subject
    if mf == "spread":
        return f"{subj} {pick.line:+.1f}"
    if mf == "moneyline":
        return f"{subj} ML" + (f" ({pick.odds_american:+d})" if pick.odds_american else "")
    if mf in ("game_total", "team_total"):
        return f"{pick.side.upper()} {pick.line:g}"
    if mf == "player_prop":
        return f"{subj.replace('_', ' ').title()} {pick.side.upper()} {pick.line:g} {pick.stat}"
    return f"{subj} {pick.side}"


def render_best_bet_card(pick, out_dir: Path, size=B.FEED) -> Path:
    W, H = size
    img, draw = _base(size)
    _center(draw, W / 2, 64, B.BRAND, _font(46, True), B.ACCENT)
    _center(draw, W / 2, 150, "BEST BET OF THE DAY", _font(40, True), B.TEXT)

    _center(draw, W / 2, 340, _describe_pick(pick), _font(78, True), B.ACCENT)
    _center(draw, W / 2, 470, f"{pick.market_family.replace('_', ' ').title()}", _font(34), B.MUTED)

    _pill(draw, W / 2, 560, f"EDGE {pick.edge * 100:.1f}%", 40, fg=B.BG, bg=B.WIN)
    _center(draw, W / 2, 690, f"Model {pick.model_prob * 100:.0f}%   vs   Market {pick.fair_prob * 100:.0f}%", _font(38, True), B.TEXT)
    _center(draw, W / 2, 760, f"Confidence: {pick.confidence.upper()}", _font(32), B.MUTED)
    _footer(draw, size, B.hashtags_for(getattr(pick, "sport", "nba")))

    out = Path(out_dir) / f"bestbet_{pick.subject}_{pick.market_family}.png"
    img.save(out)
    return out


def render_record_card(record: Dict[str, Any], out_dir: Path, size=B.FEED, title="OUR TRACK RECORD") -> Path:
    W, H = size
    img, draw = _base(size)
    _center(draw, W / 2, 64, B.BRAND, _font(46, True), B.ACCENT)
    _center(draw, W / 2, 160, title, _font(40, True), B.TEXT)

    _center(draw, W / 2, 320, record.get("record", "0-0"), _font(150, True), B.ACCENT)
    units = float(record.get("units", 0.0) or 0.0)
    _center(draw, W / 2, 520, f"{units:+.1f} UNITS", _font(70, True), B.WIN if units >= 0 else B.LOSE)

    wp = record.get("win_pct")
    wp_txt = f"{wp * 100:.0f}%" if wp is not None else "-"
    streak = record.get("streak", 0)
    streak_txt = (f"W{streak}" if streak > 0 else f"L{-streak}") if streak else "-"
    _center(draw, W / 2, 660, f"Win rate {wp_txt}    Streak {streak_txt}    ({record.get('n_picks', 0)} picks)", _font(36, True), B.TEXT)
    _footer(draw, size)

    out = Path(out_dir) / "track_record.png"
    img.save(out)
    return out


# --- captions ---
def caption_for_score(gp) -> str:
    if getattr(gp, "p_draw", None) is not None:  # 3-way (soccer)
        p_home = float(gp.p_home_win)
        p_draw = float(gp.p_draw)
        p_away = float(gp.p_away_win if gp.p_away_win is not None else 1.0 - p_home)
        pick, pp = max([(gp.home, p_home), ("Draw", p_draw), (gp.away, p_away)], key=lambda t: t[1])
        pick_txt = "a draw" if pick == "Draw" else f"{pick} to win"
        return (f"{gp.home} vs {gp.away}, our model projects "
                f"{gp.pred_home_pts:.1f}-{gp.pred_away_pts:.1f}, {pick_txt} ({pp * 100:.0f}%). "
                f"Home {p_home * 100:.0f}% / Draw {p_draw * 100:.0f}% / Away {p_away * 100:.0f}%.\n\n"
                f"{B.DISCLAIMER}\n\n{B.hashtags_for(gp.sport)}")
    home_wins = gp.pred_home_pts >= gp.pred_away_pts
    winner = gp.home if home_wins else gp.away
    wp = gp.p_home_win if home_wins else (1 - gp.p_home_win)
    return (f"{gp.away} @ {gp.home}, our model projects "
            f"{gp.pred_away_pts:.0f}-{gp.pred_home_pts:.0f}, {winner} to win ({wp * 100:.0f}%).\n\n"
            f"{B.DISCLAIMER}\n\n{B.hashtags_for(gp.sport)}")


def caption_for_pick(pick) -> str:
    return (f"BEST BET: {_describe_pick(pick)}, {pick.edge * 100:.1f}% edge "
            f"(model {pick.model_prob * 100:.0f}% vs market {pick.fair_prob * 100:.0f}%).\n\n"
            f"{B.DISCLAIMER}\n\n{B.hashtags_for(getattr(pick, 'sport', 'nba'))}")


# Sport-aware prop display: which stats to show (in priority order), their card
# labels, and decimal places. The first up-to-3 present become the big "hero"
# numbers; the rest render as a secondary line. Keeps NBA's PTS/REB/AST look and
# gives NFL position-appropriate lines (QB pass+rush yds, WR rec yds+rec, ...).
_PROP_DISPLAY: Dict[str, Dict[str, Any]] = {
    "nba": {  # counting stats shown as integers (decimals default 0)
        "order": ["PTS", "REB", "AST", "FG3M", "STL", "BLK", "TOV"],
        "labels": {"FG3M": "3PM"},
        "decimals": {},
    },
    "nfl": {  # yards as integers, receptions to 1dp
        "order": ["passing_yards", "rushing_yards", "receiving_yards", "receptions"],
        "labels": {"passing_yards": "PASS YDS", "rushing_yards": "RUSH YDS",
                   "receiving_yards": "REC YDS", "receptions": "REC"},
        "decimals": {"receptions": 1},
    },
    "mlb": {  # batter hitting props + starter strikeouts (fractional projections)
        "order": ["hits", "totalBases", "homeRuns", "strikeouts"],
        "labels": {"hits": "HITS", "totalBases": "TOT BASES", "homeRuns": "HR",
                   "strikeouts": "K"},
        "decimals": {"hits": 1, "totalBases": 1, "homeRuns": 1, "strikeouts": 1},
    },
    "nhl": {  # skater points (goals+assists) + shots on goal
        "order": ["points", "shots"],
        "labels": {"points": "PTS", "shots": "SOG"},
        "decimals": {"points": 1, "shots": 1},
    },
    "soccer": {  # market-implied anytime-goalscorer probability (%), single hero number
        "order": ["anytime_scorer_pct"],
        "labels": {"anytime_scorer_pct": "SCORE %"},
        "decimals": {"anytime_scorer_pct": 0},
    },
}
_HERO_X = {1: (0.5,), 2: (0.34, 0.66), 3: (0.25, 0.5, 0.75)}


def _present_stats(projections: Dict[str, float], sport: str):
    cfg = _PROP_DISPLAY.get(sport, _PROP_DISPLAY["nba"])
    return [(cfg["labels"].get(s, s), float(projections[s]), cfg["decimals"].get(s, 0))
            for s in cfg["order"] if projections.get(s) is not None]


def render_props_card(player_name: str, projections: Dict[str, float], out_dir: Path,
                      matchup: str = "", size=B.FEED, sport: str = "nba") -> Path:
    W, H = size
    img, draw = _base(size)
    _center(draw, W / 2, 64, B.BRAND, _font(46, True), B.ACCENT)
    _center(draw, W / 2, 140, "PLAYER PROJECTION", _font(34, True), B.MUTED)
    _center(draw, W / 2, 258, player_name, _font(64, True), B.TEXT)
    if matchup:
        _center(draw, W / 2, 346, matchup, _font(34), B.MUTED)

    present = _present_stats(projections, sport)
    hero = present[:3]
    for (lbl, val, dec), xr in zip(hero, _HERO_X.get(len(hero), _HERO_X[3])):
        _center(draw, W * xr, 470, f"{val:.{dec}f}", _font(96, True), B.ACCENT)
        _center(draw, W * xr, 600, lbl, _font(36, True), B.MUTED)

    parts = [f"{lbl} {val:.{dec}f}" for lbl, val, dec in present[3:]]
    if parts:
        _center(draw, W / 2, 760, "    ·    ".join(parts), _font(34), B.TEXT)
    _footer(draw, size, B.hashtags_for(sport))

    out = Path(out_dir) / f"props_{player_name.replace(' ', '_')}.png"
    img.save(out)
    return out


def caption_for_props(player_name: str, projections: Dict[str, float], matchup: str = "", sport: str = "nba") -> str:
    hero = _present_stats(projections, sport)[:3]
    line = " / ".join(f"{val:.{dec}f} {lbl}" for lbl, val, dec in hero)
    mt = f" {matchup}" if matchup else ""
    return f"{player_name}{mt}, we project {line}.\n\n{B.DISCLAIMER}\n\n{B.hashtags_for(sport)}"


# --- orchestration ---
def render_slate(
    game_date: str,
    game_preds: List[Any],
    picks: Optional[List[Any]] = None,
    record: Optional[Dict[str, Any]] = None,
    out_root: Path = CONTENT_OUTPUT_DIR,
    max_games: int = 6,
    prop_cards: Optional[List[Dict[str, Any]]] = None,
) -> List[Path]:
    out_dir = Path(out_root) / game_date
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    for gp in game_preds[:max_games]:
        p = render_score_card(gp, out_dir)
        p.with_suffix(".txt").write_text(caption_for_score(gp))
        paths.append(p)

    if picks:
        p = render_best_bet_card(picks[0], out_dir)
        p.with_suffix(".txt").write_text(caption_for_pick(picks[0]))
        paths.append(p)

    if record:
        paths.append(render_record_card(record, out_dir))

    slate_sport = game_preds[0].sport if game_preds else "nba"
    for pc in (prop_cards or []):
        sp = pc.get("sport", slate_sport)
        p = render_props_card(pc["player_name"], pc["projections"], out_dir, pc.get("matchup", ""), sport=sp)
        p.with_suffix(".txt").write_text(caption_for_props(pc["player_name"], pc["projections"], pc.get("matchup", ""), sport=sp))
        paths.append(p)

    # Static control-room review page (embeds every card + caption for manual posting).
    from content.review import build_review_page
    build_review_page(out_dir, game_date, record)

    logger.info("rendered %d content cards -> %s", len(paths), out_dir)
    return paths
