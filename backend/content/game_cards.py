"""Score + results card generators (CONTENT_SPEC §3.1/§3.3), Editorial Terminal.

build_score_html(pred): a GamePrediction-shaped dict -> the daily score card.
build_results_html(day): graded results -> the results card.

Real data binds from predictions/track_record in the daily pipeline (M5); the CLI
here renders representative drafts (mirroring the locked mockups) for design review.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

TEMPLATES = Path(__file__).resolve().parent / "templates"
_DOT = ' <span class="rd">●</span>'


def _fill(tpl: str, tokens: Dict[str, Any]) -> str:
    for k, v in tokens.items():
        tpl = tpl.replace(f"%%{k}%%", str(v))
    return tpl


def build_score_html(p: Dict[str, Any], *, handle: str = "@playthechalk") -> str:
    """Fill the score card from a GamePrediction-shaped dict. The winner's numeral
    renders red, the loser's grey — regardless of home/away."""
    home_win = p["winner_side"] == "home"
    winner = p["home_name"] if home_win else p["away_name"]
    conf = round(float(p["confidence"]) * 100)
    tpl = (TEMPLATES / "score.html").read_text(encoding="utf-8")
    return _fill(tpl, {
        "LEAGUE": p["league"], "WHEN": p["when"],
        "AWAY_NAME": p["away_name"], "HOME_NAME": p["home_name"],
        "AWAY_CITY": p["away_city"], "HOME_CITY": p["home_city"],
        "AWAY_SUB": "AWAY" + ("" if home_win else " · PREDICTED WINNER" + _DOT),
        "HOME_SUB": "HOME" + (" · PREDICTED WINNER" + _DOT if home_win else ""),
        "AWAY_SCORE": p["away_score"], "HOME_SCORE": p["home_score"],
        "AWAY_SCLASS": "lose" if home_win else "win",
        "HOME_SCLASS": "win" if home_win else "lose",
        "WINNER": winner, "CONF": f"{conf}%", "CONF_PCT": conf, "HANDLE": handle,
    })


_ROW = ('<div class="grow"><div class="badge {cls}">{mark}</div>'
        '<div class="g"><div class="team">{team}</div>'
        '<div class="det">CALLED {called} · FINAL {final}</div></div>'
        '<div class="verdict {cls}">{verdict}</div></div>')


def build_results_html(day: Dict[str, Any], *, handle: str = "@playthechalk") -> str:
    rows = [
        _ROW.format(cls="hit" if g["hit"] else "miss",
                    mark="✓" if g["hit"] else "✗",
                    team=g["team"], called=g["called"], final=g["final"],
                    verdict="HIT" if g["hit"] else "MISS")
        for g in day["games"]
    ]
    tw, tl = day["today"]
    sw, sl = day["season"]
    tpl = (TEMPLATES / "results.html").read_text(encoding="utf-8")
    return _fill(tpl, {
        "DAY": day["day"], "ROWS": "\n".join(rows),
        "TODAY_W": tw, "TODAY_L": tl, "SEASON_W": sw, "SEASON_L": sl, "HANDLE": handle,
    })


# --- representative drafts (mirror the locked mockups); real data binds in the pipeline ---
_SAMPLE_SCORE = {
    "league": "NFL", "when": "WEEK 1 · SUN 1:00 PM ET",
    "away_name": "Kansas City Chiefs", "home_name": "Buffalo Bills",
    "away_city": "Kansas City", "home_city": "Buffalo",
    "away_score": 24, "home_score": 27, "winner_side": "home", "confidence": 0.58,
}
_SAMPLE_RESULTS = {
    "day": "SUNDAY, WEEK 1", "today": (4, 2), "season": (4, 2),
    "games": [
        {"team": "Buffalo", "called": "BUF", "final": "28–21", "hit": True},
        {"team": "Philadelphia", "called": "PHI", "final": "24–17", "hit": True},
        {"team": "Baltimore", "called": "BAL", "final": "<b>CINCINNATI</b> 20–19", "hit": False},
        {"team": "San Francisco", "called": "SF", "final": "31–20", "hit": True},
        {"team": "Detroit", "called": "DET", "final": "<b>GREEN BAY</b> 27–24", "hit": False},
        {"team": "Kansas City", "called": "KC", "final": "23–20", "hit": True},
    ],
}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Render a score/results card (HTML) — representative draft.")
    ap.add_argument("--kind", required=True, choices=["score", "results"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    html = build_score_html(_SAMPLE_SCORE) if a.kind == "score" else build_results_html(_SAMPLE_RESULTS)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
