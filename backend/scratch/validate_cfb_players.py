#!/usr/bin/env python3
"""Validate the CFBD player loader on one season before the full pull.

Checks: frame shape, FBS-game coverage vs the games cache, canonicalization
(every player's team is one of the game's two teams), and stat realism.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sports.cfb.data import PLAYER_STAT_COLS, load_games, load_player_games

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2024

games = load_games([YEAR])
pg = load_player_games([YEAR])

print(f"=== CFB player games {YEAR} ===")
print(f"rows={len(pg)}  players={pg['player_id'].nunique()}  "
      f"player-game-ids={pg['game_id'].nunique()}  fbs-games={games['game_id'].nunique()}")
print(f"cols={list(pg.columns)}")

# Coverage: fraction of FBS games that have any player stats.
cov = pg['game_id'].nunique() / max(1, games['game_id'].nunique())
print(f"game coverage: {cov:.3f}")

# is_home correctness: a player's team must be the game's home or away.
gm = games.set_index('game_id')[['home', 'away']]
bad = 0
for gid, grp in pg.groupby('game_id'):
    hw = gm.loc[gid]
    teams = set(grp['team'])
    stray = teams - {hw['home'], hw['away']}
    bad += len(stray)
print(f"stray teams (team not home/away, canonicalization misses): {bad}")
print(f"is_home mean={pg['is_home'].mean():.3f} (want ~0.5)")

print("\n=== stat realism (max single-game) ===")
for c in PLAYER_STAT_COLS:
    print(f"  {c:<16} max={pg[c].max():>7.1f}  mean>0={pg[pg[c] > 0][c].mean():>6.2f}  nonzero={int((pg[c] > 0).sum())}")

print("\n=== top 5 single-game passing_yards ===")
print(pg.nlargest(5, 'passing_yards')[['player_name', 'team', 'opponent', 'passing_yards', 'attempts', 'completions']].to_string(index=False))
