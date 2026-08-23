"""Multi-sport carousel COVER generator (CONTENT_SPEC §3.4), Editorial Terminal.

The cover is the day's slate as compact rows ([sport] Away @ Home -> Winner Score · conf%);
the interior slides are the per-game score cards (content/game_cards.build_score_html).
IG gets this curated carousel; X/Reddit get the full per-sport depth (master plan §8).

Real data binds from the day's picks in the pipeline (M5); the CLI renders a
representative draft (mirroring the locked mockup) for design review.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from content.icons import BASEBALL, BASKETBALL, FOOTBALL, icon_for

TEMPLATES = Path(__file__).resolve().parent / "templates"

_ROW = ('<div class="crow"><div class="ic">{icon}</div>'
        '<div class="mt">{away}<span class="vs">@</span>{home}</div>'
        '<div class="res"><span class="ar">→</span><span class="win">{winner}</span>'
        '<span class="sc">{score}</span><span class="cf">· <b>{conf}</b>%</span></div></div>')


def build_carousel_cover_html(slate: Dict[str, Any], *, handle: str = "@playthechalk") -> str:
    rows = [
        _ROW.format(icon=icon_for(g["sport"]), away=g["away"], home=g["home"],
                    winner=g["winner"], score=g["score"], conf=g["conf"])
        for g in slate["games"]
    ]
    # masthead shows one icon per distinct sport on the slate, in first-seen order
    seen: List[str] = []
    for g in slate["games"]:
        if g["sport"] not in seen:
            seen.append(g["sport"])
    mast_icons = "".join(icon_for(s) for s in seen)
    tpl = (TEMPLATES / "carousel_cover.html").read_text(encoding="utf-8")
    for k, v in {"DATE": slate["date"], "ROWS": "\n".join(rows),
                 "MAST_ICONS": mast_icons, "HANDLE": handle}.items():
        tpl = tpl.replace(f"%%{k}%%", str(v))
    return tpl


_SAMPLE = {
    "date": "SUN, WEEK 1",
    "games": [
        {"sport": "nfl", "away": "Chiefs", "home": "Bills", "winner": "Bills", "score": "27–24", "conf": 58},
        {"sport": "nfl", "away": "Cowboys", "home": "Eagles", "winner": "Eagles", "score": "24–20", "conf": 55},
        {"sport": "nba", "away": "Knicks", "home": "Celtics", "winner": "Celtics", "score": "118–110", "conf": 62},
        {"sport": "nba", "away": "Lakers", "home": "Nuggets", "winner": "Nuggets", "score": "115–108", "conf": 60},
        {"sport": "mlb", "away": "Yankees", "home": "Red Sox", "winner": "Yankees", "score": "5–3", "conf": 54},
    ],
}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Render the carousel cover (HTML) — representative draft.")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_carousel_cover_html(_SAMPLE), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
