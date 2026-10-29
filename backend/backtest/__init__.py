"""Honest historical backtesting: the reliability check.

Walk-forward: for each season S, train on seasons < S and predict S entirely
out-of-sample (no in-sample optimism), then grade the picks. Team markets are
gradeable now (final scores are in the parquet; ATS/O-U/ROI/CLV once free
historical odds are supplied). Player-prop historical odds don't exist for free,
so props rely on calibration + forward-collection instead.
"""
from backtest.team_backtest import walk_forward_backtest  # noqa: F401
