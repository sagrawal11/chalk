"""Pinned triptych generator (CONTENT_SPEC §3.5): one 3240x1350 continuous
panorama, sliced into 3x 1080x1350 tiles (post right->middle->left). No sport icon.

Numbers come from the public track record (seeded market-blind walk-forward). The
CLI renders a representative draft; the pipeline refreshes the numbers over time.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / "templates"


def build_triptych_html(*, overall_pct: str = "61.5", games: str = "43,600",
                        nba_pct: str = "66.0", nfl_pct: str = "62.2") -> str:
    tpl = (TEMPLATES / "triptych.html").read_text(encoding="utf-8")
    for k, v in {"OVERALL_PCT": overall_pct, "GAMES": games,
                 "NBA_PCT": nba_pct, "NFL_PCT": nfl_pct}.items():
        tpl = tpl.replace(f"%%{k}%%", str(v))
    return tpl


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Render the pinned triptych panorama (HTML).")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_triptych_html(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
