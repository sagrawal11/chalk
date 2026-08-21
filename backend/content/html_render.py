"""Render CHALK content in the locked "Editorial Terminal" design from real data.

The card is an HTML template (``templates/card_editorial.html``) filled with a
game's prediction, then rasterized to a 1080x1350 PNG. HTML/CSS is the medium so
the design matches the design-shotgun mockups exactly (real fonts, precise type).

Rasterization is intentionally pluggable so CI can choose its toolchain:
  * ``CHALK_RASTERIZER`` env = a command template with {html} and {png} and {w}/{h}
    (e.g. a headless-chrome or gstack-browse invocation), OR
  * Playwright (``pip install playwright``) if importable, OR
  * fall back to writing the .html only (caller screenshots it) — never crash.

This module does NOT replace the Pillow renderer yet; it's the production path for
the new design, wired in once the look is signed off.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TEMPLATES = Path(__file__).resolve().parent / "templates"
CARD_W, CARD_H = 1080, 1350

# Minimal team-color chips (bg, fg). Extend per sport; unknowns get the ink chip.
TEAM_COLORS: Dict[str, tuple] = {
    "LAL": ("#552583", "#FDB927"), "BOS": ("#007A33", "#FFFFFF"),
    "GSW": ("#1D428A", "#FFC72C"), "MIA": ("#98002E", "#F9A01B"),
    "NYK": ("#006BB6", "#F58426"), "DEN": ("#0E2240", "#FEC524"),
}
_INK_CHIP = ("#16130F", "#FFFFFF")


def _chip_style(abbr: str) -> str:
    bg, fg = TEAM_COLORS.get(abbr.upper(), _INK_CHIP)
    return f"background:{bg};color:{fg}"


def render_card_html(game: Dict[str, Any]) -> str:
    """Fill the Editorial-Terminal card template. ``game`` keys:
    sport, slate, home_name, away_name, home_abbr, away_abbr, home_score,
    away_score, winner_side ('home'|'away'), confidence (0-1), reasoning,
    track_line, handle."""
    tpl = (TEMPLATES / "card_editorial.html").read_text(encoding="utf-8")
    home_win = game.get("winner_side", "home") == "home"
    winner_name = game["home_name"] if home_win else game["away_name"]
    conf = max(0.0, min(1.0, float(game.get("confidence", 0.5))))
    tokens = {
        "SLATE": game.get("slate", ""),
        "HOME_ROW": "line win" if home_win else "line",
        "AWAY_ROW": "line" if home_win else "line win",
        "HOME_NAME": game["home_name"], "AWAY_NAME": game["away_name"],
        "HOME_ABBR": game["home_abbr"], "AWAY_ABBR": game["away_abbr"],
        "HOME_SCORE": str(game["home_score"]), "AWAY_SCORE": str(game["away_score"]),
        "HOME_CHIP": _chip_style(game["home_abbr"]), "AWAY_CHIP": _chip_style(game["away_abbr"]),
        "WINNER": winner_name,
        "SCORELINE": f"{max(game['home_score'], game['away_score'])}–{min(game['home_score'], game['away_score'])}",
        "CONF": f"{round(conf * 100)}%", "CONF_WIDTH": f"{round(conf * 100)}%",
        "REASON": game.get("reasoning", ""),
        "TRACK": game.get("track_line", ""),
        "HANDLE": game.get("handle", "@playthechalk"),
    }
    for k, v in tokens.items():
        tpl = tpl.replace(f"%%{k}%%", v)
    return tpl


def rasterize(html_path: Path, png_path: Path, w: int = CARD_W, h: int = CARD_H) -> bool:
    """Best-effort HTML->PNG. Returns True on success. Order: $CHALK_RASTERIZER,
    then Playwright, else leave the HTML (False)."""
    cmd_tpl = os.environ.get("CHALK_RASTERIZER")
    if cmd_tpl:
        cmd = cmd_tpl.format(html=str(html_path), png=str(png_path), w=w, h=h)
        try:
            subprocess.run(cmd, shell=True, check=True)
            return png_path.exists()
        except Exception as e:  # pragma: no cover - env-specific
            logger.warning("CHALK_RASTERIZER failed: %s", e)
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto(html_path.as_uri())
            pg.wait_for_timeout(600)
            pg.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": w, "height": h})
            b.close()
        return png_path.exists()
    except Exception as e:  # pragma: no cover - optional dep
        logger.info("Playwright rasterizer unavailable (%s); wrote HTML only", e)
    return False


def render_card_png(game: Dict[str, Any], out_png: Path) -> Optional[Path]:
    """Render a game card to PNG. Always writes the .html alongside; returns the
    PNG path if rasterization succeeded, else None (HTML is still available)."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(render_card_html(game), encoding="utf-8")
    ok = rasterize(html_path, out_png)
    return out_png if ok else None


def game_from_prediction(gp: Any, home_name: str, away_name: str,
                         reasoning: str, track_line: str, slate: str = "") -> Dict[str, Any]:
    """Adapt a predictions.schema.GamePrediction into the card ``game`` dict. The
    confidence shown is the model's win probability for the favored side."""
    p_home = float(gp.p_home_win)
    home_win = p_home >= 0.5
    return {
        "sport": gp.sport, "slate": slate,
        "home_name": home_name, "away_name": away_name,
        "home_abbr": gp.home, "away_abbr": gp.away,
        "home_score": int(round(gp.pred_home_pts)), "away_score": int(round(gp.pred_away_pts)),
        "winner_side": "home" if home_win else "away",
        "confidence": p_home if home_win else 1.0 - p_home,
        "reasoning": reasoning, "track_line": track_line,
        "handle": "@playthechalk",
    }
