"""NFL sport plugin. Backed by the free nflverse data (nfl_data_py): schedules
with built-in spread/total lines, team game logs, and weekly player stats.

Proves the sport-agnostic core: NFL is a Sport plugin like NBA. Modeling
(team score model + player-prop models) reuses the generic pipeline once the
NFL feature engine is built; this scaffold provides identity + the data adapter.
"""
