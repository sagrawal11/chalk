"""Feature-experiment harness — hermetic tests (no NFL data / network).

Covers the roadmap loader, the pre-registered keep-rule decision logic, the ledger,
and version bumping. The full data-dependent run_experiment loop is exercised
end-to-end against real nflverse data in the M2 demo (documented), not in CI.
"""
import pytest

from experiments import ledger, roadmap
from experiments.champion import bump_version, resolve_feature_cols
from experiments.run_experiment import _decide


def test_bump_version():
    assert bump_version("nfl-v1") == "nfl-v2"
    assert bump_version("nfl-v9") == "nfl-v10"
    with pytest.raises(ValueError):
        bump_version("nfl")


def test_registry_has_rung2_3_builders():
    assert resolve_feature_cols("nfl", ["NFL-06"]) == ["HOME_FORM", "AWAY_FORM"]
    assert resolve_feature_cols("nfl", ["NFL-10"]) == ["HOME_OFF_ADJ", "AWAY_OFF_ADJ"]
    assert resolve_feature_cols("nfl", ["NFL-11"]) == ["HOME_DEF_ADJ", "AWAY_DEF_ADJ"]


def test_roadmap_loads_and_has_nfl_queue():
    rm = roadmap.load_roadmap()
    exps = roadmap.experiments_for(rm, "nfl")
    assert any(e["id"] == "NFL-06" for e in exps)
    # keep-rule inherits the pre-registered default
    kr = roadmap.keep_rule_for(rm, "nfl", roadmap.get_experiment(rm, "nfl", "NFL-06"))
    assert kr["metric"] == "winner_logloss" and kr["min_delta"] == 0.0005
    # next-unrun skips ids already in the ledger
    assert roadmap.next_unrun(rm, "nfl", set())["id"] == "NFL-06"
    assert roadmap.next_unrun(rm, "nfl", {"NFL-06"})["id"] == "NFL-10"


def test_needs_builder_is_not_queued():
    rm = roadmap.load_roadmap()
    nfl07 = roadmap.get_experiment(rm, "nfl", "NFL-07")
    assert nfl07["status"] == "needs_builder"
    # next_unrun only returns queued items, never needs_builder
    run = {e["id"] for e in roadmap.experiments_for(rm, "nfl") if e["status"] == "queued"}
    assert roadmap.next_unrun(rm, "nfl", run) is None


def test_keep_rule_decision():
    rule = {"metric": "winner_logloss", "improve": "lower", "min_delta": 0.0005,
            "guard_metric": "margin_mae", "guard_improve": "lower"}
    champ = {"winner_logloss": 0.6451, "margin_mae": 10.73}
    # clear improvement, guard ok -> keep
    d, delta, g = _decide(champ, {"winner_logloss": 0.6442, "margin_mae": 10.70}, rule)
    assert d == "keep" and delta == 0.0009 and g is True
    # improvement below min_delta -> drop
    d, _, _ = _decide(champ, {"winner_logloss": 0.6449, "margin_mae": 10.70}, rule)
    assert d == "drop"
    # improves primary but guard worsens -> drop
    d, _, g = _decide(champ, {"winner_logloss": 0.6440, "margin_mae": 10.80}, rule)
    assert d == "drop" and g is False
    # worse primary -> drop
    d, _, _ = _decide(champ, {"winner_logloss": 0.6462, "margin_mae": 10.70}, rule)
    assert d == "drop"


def test_ledger_append_and_counts(tmp_path):
    p = tmp_path / "ledger.jsonl"
    ledger.append_result({"id": "NFL-06", "sport": "nfl", "decision": "drop"}, path=p)
    ledger.append_result({"id": "NFL-10", "sport": "nfl", "decision": "keep"}, path=p)
    ledger.append_result({"id": "MLB-01", "sport": "mlb", "decision": "keep"}, path=p)
    assert ledger.run_ids("nfl", path=p) == {"NFL-06", "NFL-10"}
    assert ledger.counts("nfl", path=p) == {"run": 2, "kept": 1, "dropped": 1}
