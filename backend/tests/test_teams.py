"""Canonical team identity + season bridge (backend/sports/nba/teams.py).

Hermetic: does not read the parquet (data-dependent tests already fail when
data files are absent). ``PARQUET_TEAM_CODES`` is the verified set of distinct
'team' codes in kaggle_team_games.parquet.
"""
import pytest

from sports.nba.teams import (
    CANONICAL_TEAMS,
    ESPN_TO_NBA_MAP,
    canonical_team,
    season_int_to_str,
    season_str_to_int,
)

# Distinct 'team' codes present in kaggle_team_games.parquet (verified).
PARQUET_TEAM_CODES = [
    "ATL", "BKN", "BOS", "BRK", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
    "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NJN",
    "NOH", "NOK", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC",
    "SAS", "SEA", "TOR", "UTA", "WAS",
]


def test_exactly_thirty_canonical_teams():
    assert len(CANONICAL_TEAMS) == 30


def test_every_parquet_code_resolves_to_canonical():
    for code in PARQUET_TEAM_CODES:
        canon = canonical_team(code)
        assert canon in CANONICAL_TEAMS, f"{code} -> {canon} is not canonical"


def test_every_espn_code_resolves_to_canonical():
    for espn, expected in ESPN_TO_NBA_MAP.items():
        assert canonical_team(espn) == expected
        assert expected in CANONICAL_TEAMS


def test_relocations_fold_correctly():
    assert canonical_team("NJN") == "BKN"
    assert canonical_team("BRK") == "BKN"
    assert canonical_team("SEA") == "OKC"
    assert canonical_team("NOH") == "NOP"
    assert canonical_team("NOK") == "NOP"


def test_case_and_whitespace_insensitive():
    assert canonical_team(" bkn ") == "BKN"
    assert canonical_team("gsw") == "GSW"


def test_idempotent():
    for code in PARQUET_TEAM_CODES:
        c = canonical_team(code)
        assert canonical_team(c) == c


def test_unknown_raises_in_strict_mode():
    with pytest.raises(ValueError):
        canonical_team("ZZZ")


def test_unknown_passthrough_when_not_strict():
    assert canonical_team("ZZZ", strict=False) == "ZZZ"


def test_season_int_to_str():
    assert season_int_to_str(2024) == "2024-25"
    assert season_int_to_str(2006) == "2006-07"
    assert season_int_to_str(1999) == "1999-00"


def test_season_str_to_int():
    assert season_str_to_int("2024-25") == 2024
    assert season_str_to_int("2006-07") == 2006
    assert season_str_to_int("2024-2025") == 2024


def test_season_roundtrip_identity():
    for y in range(1996, 2031):
        assert season_str_to_int(season_int_to_str(y)) == y
    for s in ("2019-20", "2024-25", "1999-00"):
        assert season_int_to_str(season_str_to_int(s)) == s
