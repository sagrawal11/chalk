"""Feature-experiment harness (NEW, the centerpiece). Wired in M2.

See docs/ARCHITECTURE.md §5d and BUILD_PLAN M2. Lands here: roadmap.yaml,
run_experiment.py, honest_readout.py, and the experiments ledger. It orchestrates
the EXISTING walk-forward backtest (backtest/team_backtest.py); it does not
reinvent evaluation. The champion predicts from team features only; no betting
line is ever an input.
"""
