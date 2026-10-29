"""Honest historical backtesting: the reliability check.

Walk-forward: for each season S, train on seasons < S and predict S entirely
out-of-sample (no in-sample optimism), then grade the picks against the real
result (winner + final score). Player props are graded predicted-vs-actual, and
lean on calibration + forward-collection.
"""
from backtest.team_backtest import walk_forward_backtest  # noqa: F401
