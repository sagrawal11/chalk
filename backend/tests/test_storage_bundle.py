"""utils.storage._gather_upload_tasks — the pure (no-network) manifest builder for
the full R2 training bundle. Verifies it ships player game logs (minus the bloated
per-player feature CSVs), the ENTIRE artifacts tree EXCEPT local ``*backup*`` dirs
(so every per-sport model dir travels to CI), and the per-sport data caches."""
from pathlib import Path

from utils.storage import _gather_upload_tasks


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_gather_upload_tasks_manifest(tmp_path):
    pdir = tmp_path / "player_data"
    adir = tmp_path / "artifacts"
    mlb, nhl, soc = tmp_path / "mlb", tmp_path / "nhl", tmp_path / "soccer"

    _touch(pdir / "lebron_james" / "lebron_james_data.csv")
    _touch(pdir / "lebron_james" / "lebron_james_features.csv")   # bloat -> skipped
    _touch(adir / "global" / "global_lgbm_PTS.joblib")
    _touch(adir / "mlb_team" / "team_margin.joblib")              # new per-sport dir travels
    _touch(adir / "nhl_skater" / "skater_points.joblib")
    _touch(adir / "feature_columns.json")
    _touch(adir / "global_backup_pre_x" / "old.joblib")           # backup -> skipped
    _touch(adir / "nfl_team_backup_pre_market" / "old.joblib")    # backup -> skipped
    _touch(mlb / "schedule_2015.parquet")
    _touch(nhl / "skater_games_2023.parquet")
    _touch(soc / "epl_matches_2021.parquet")

    tasks = _gather_upload_tasks(
        pdir, adir, [(mlb, "data/mlb/"), (nhl, "data/nhl/"), (soc, "data/soccer/")]
    )
    keys = {k for _, k in tasks}

    # player logs in, bloated feature CSVs out
    assert "data/player_data/lebron_james/lebron_james_data.csv" in keys
    assert not any(k.endswith("_features.csv") for k in keys)
    # global + every per-sport model dir + feature_columns.json
    assert "artifacts/global/global_lgbm_PTS.joblib" in keys
    assert "artifacts/mlb_team/team_margin.joblib" in keys
    assert "artifacts/nhl_skater/skater_points.joblib" in keys
    assert "artifacts/feature_columns.json" in keys
    # local backup dirs never travel
    assert not any("backup" in k for k in keys)
    # per-sport historical data caches ship to CI
    assert "data/mlb/schedule_2015.parquet" in keys
    assert "data/nhl/skater_games_2023.parquet" in keys
    assert "data/soccer/epl_matches_2021.parquet" in keys


def test_gather_upload_tasks_missing_dirs_ok(tmp_path):
    # A fresh checkout before any build: nothing on disk -> empty manifest, no error.
    tasks = _gather_upload_tasks(
        tmp_path / "nope_p", tmp_path / "nope_a", [(tmp_path / "nope_m", "data/mlb/")]
    )
    assert tasks == []
