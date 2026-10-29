"""Reel slate seam — the Python↔Remotion wiring for the daily predictions reel.

`reel/render-reel.mjs` renders a 1080×1920 MP4 from a *slate JSON* (see
`reel/SLATE_CONTRACT.md`, whose single source of truth is the validator inside
render-reel.mjs). This module is the Python side of that seam:

  * ``build_slate(...)``  — assemble a day's data into the contract shape.
  * ``write_slate(...)``  — serialize it to JSON.
  * ``render_reel(path)`` — invoke render-reel.mjs on a written slate.

M0 lands the *seam* (contract + writer + invoker). Assembling ``games`` from real
market-blind predictions + the graded track record is wired into
``pipeline/daily_content`` in M3 (docs/ARCHITECTURE.md §5g, BUILD_PLAN M3).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

REEL_DIR = Path(__file__).resolve().parents[2] / "reel"
RENDER_SCRIPT = REEL_DIR / "render-reel.mjs"

# The per-game keys render-reel.mjs requires (kept in sync with SLATE_CONTRACT.md).
_GAME_STR_KEYS = ("homeName", "homeShort", "homeCity",
                  "awayName", "awayShort", "awayCity", "reasoning")
_GAME_NUM_KEYS = ("homeScore", "awayScore", "confidence")


def build_slate(
    *,
    date: str,
    win_pct: float,
    n_picks: int,
    yesterday_correct: int,
    yesterday_total: int,
    games: Sequence[Mapping[str, Any]],
) -> dict:
    """Assemble a slate dict in the render-reel.mjs contract shape.

    Each ``games`` item must carry the keys in ``_GAME_STR_KEYS`` +
    ``_GAME_NUM_KEYS`` plus ``winnerSide`` in {"home", "away"}. Raises
    ``ValueError`` on a malformed game so a bad slate fails here, loudly, rather
    than silently downstream in the renderer.
    """
    slate_games: list[dict] = []
    for i, g in enumerate(games):
        for k in _GAME_STR_KEYS:
            if not isinstance(g.get(k), str) or not g[k]:
                raise ValueError(f"games[{i}].{k} must be a non-empty string")
        for k in _GAME_NUM_KEYS:
            if not isinstance(g.get(k), (int, float)) or isinstance(g.get(k), bool):
                raise ValueError(f"games[{i}].{k} must be a number")
        if g.get("winnerSide") not in ("home", "away"):
            raise ValueError(f'games[{i}].winnerSide must be "home" or "away"')
        slate_games.append({
            **{k: g[k] for k in _GAME_STR_KEYS},
            **{k: g[k] for k in _GAME_NUM_KEYS},
            "winnerSide": g["winnerSide"],
        })
    if not slate_games:
        raise ValueError("slate must contain at least one game")
    return {
        "date": date,
        "trackRecord": {"winPct": float(win_pct), "nPicks": int(n_picks)},
        "yesterday": {"correct": int(yesterday_correct), "total": int(yesterday_total)},
        "slate": slate_games,
    }


def write_slate(slate: Mapping[str, Any], out_path: str | Path) -> Path:
    """Write a slate dict to JSON (UTF-8, pretty). Returns the path written."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(slate, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def render_reel(
    slate_path: str | Path,
    out_path: str | Path | None = None,
    *,
    check_only: bool = False,
) -> subprocess.CompletedProcess:
    """Invoke render-reel.mjs on a slate JSON.

    ``check_only=True`` validates the contract without rendering (the CI / seam
    smoke-test). A full render requires the reel deps installed (``npm ci`` in
    ``reel/``). Raises ``CalledProcessError`` on non-zero exit.
    """
    if not RENDER_SCRIPT.exists():
        raise FileNotFoundError(f"render script missing: {RENDER_SCRIPT}")
    cmd = ["node", str(RENDER_SCRIPT)]
    if check_only:
        cmd.append("--check")
    cmd.append(str(slate_path))
    if out_path is not None:
        cmd.append(str(out_path))
    return subprocess.run(cmd, cwd=str(REEL_DIR), check=True)
