"""train_hybrid._load_or_build_features memory hygiene: the concatenated training
matrix is downcast to float32 on load. In float64 the real matrix is ~3.9 GB and
concat + split's copy briefly hold ~8 GB, OOM-killing the 7 GB CI runner; float32
halves it. Hermetic: a tiny synthetic feature parquet through the real loader."""
import pandas as pd

from model_training.train_hybrid import _load_or_build_features


class _NoBuild:
    """Engine stub: a valid parquet (has ARCH_PROB_0) must be LOADED, never rebuilt."""
    def build_training_features(self, *a, **k):  # pragma: no cover - must not run
        raise AssertionError("should load the feature parquet, not rebuild it")


def test_load_downcasts_float64_to_float32(tmp_path):
    d = tmp_path / "player_data" / "lebron_james"
    d.mkdir(parents=True)
    df = pd.DataFrame({
        "PLAYER_NAME": ["LeBron James"] * 3,
        "SEASON": ["2024"] * 3,
        "GAME_DATE": pd.date_range("2024-01-01", periods=3),
        "ARCH_PROB_0": [0.1, 0.2, 0.3],   # presence marks a valid feature parquet
        "PTS": [25.0, 30.0, 28.0],
        "MIN_L10": [34.0, 33.0, 35.0],
    })
    assert (df.dtypes == "float64").sum() == 3          # starts as float64
    df.to_parquet(d / "lebron_james_features.parquet")

    full = _load_or_build_features(_NoBuild(), tmp_path / "player_data", None)

    assert len(full) == 3
    assert (full.dtypes == "float64").sum() == 0        # all float64 downcast...
    assert (full.dtypes == "float32").sum() == 3        # ...to float32 (ARCH_PROB_0, PTS, MIN_L10)
    assert full["GAME_DATE"].dtype.kind == "M"          # datetime/object columns untouched
