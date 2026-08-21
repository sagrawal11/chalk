"""Prop trainers must not crash when their data-frame builder returns EMPTY (a
failed/partial live backfill on a fresh CI runner). Previously an empty frame hit
`frame[frame["_n_prior"] >= ...]` -> KeyError '_n_prior' and killed the step (seen
in the first bootstrap run for NHL skater). Now they log and skip."""
import importlib
import sys

import pandas as pd
import pytest


@pytest.mark.parametrize("modname,buildfn", [
    ("model_training.train_nhl_skater_model", "build_skater_frame"),
    ("model_training.train_mlb_batter_model", "build_batter_frame"),
    ("model_training.train_mlb_pitcher_model", "build_pitcher_frame"),
])
def test_prop_trainer_skips_empty_frame(tmp_path, monkeypatch, modname, buildfn):
    t = importlib.import_module(modname)
    monkeypatch.setattr(t, buildfn, lambda years: pd.DataFrame())   # empty backfill
    monkeypatch.setattr(sys, "argv", ["train", "--out", str(tmp_path / "out")])
    t.main()   # must return cleanly (no KeyError '_n_prior', no crash)
    assert not list((tmp_path / "out").glob("*.joblib"))   # nothing trained/written
