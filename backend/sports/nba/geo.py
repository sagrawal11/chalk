"""Arena geography for travel / altitude / timezone features.

Each canonical team maps to (lat, lon, tz_offset_hours, altitude_ft) for its home
arena's city. Used to derive leakage-safe schedule features: a game's venue and
altitude are known before tip, and travel is measured from the player's PREVIOUS
game's venue: all prior-or-known information.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

from sports.nba.teams import canonical_team

# code -> (lat, lon, tz_offset_hours, altitude_ft)
TEAM_GEO: Dict[str, Tuple[float, float, int, int]] = {
    "ATL": (33.76, -84.40, -5, 1050), "BKN": (40.68, -73.97, -5, 33),
    "BOS": (42.37, -71.06, -5, 141), "CHA": (35.23, -80.84, -5, 751),
    "CHI": (41.88, -87.67, -6, 594), "CLE": (41.50, -81.69, -5, 653),
    "DAL": (32.79, -96.81, -6, 430), "DEN": (39.75, -105.01, -7, 5280),
    "DET": (42.34, -83.05, -5, 600), "GSW": (37.77, -122.39, -8, 52),
    "HOU": (29.75, -95.36, -6, 43), "IND": (39.76, -86.16, -5, 715),
    "LAC": (34.04, -118.27, -8, 233), "LAL": (34.04, -118.27, -8, 233),
    "MEM": (35.14, -90.05, -6, 337), "MIA": (25.78, -80.19, -5, 6),
    "MIL": (43.04, -87.92, -6, 617), "MIN": (44.98, -93.28, -6, 830),
    "NOP": (29.95, -90.08, -6, 3), "NYK": (40.75, -73.99, -5, 33),
    "OKC": (35.46, -97.52, -6, 1201), "ORL": (28.54, -81.38, -5, 82),
    "PHI": (39.90, -75.17, -5, 39), "PHX": (33.45, -112.07, -7, 1086),
    "POR": (45.53, -122.67, -8, 50), "SAC": (38.58, -121.50, -8, 30),
    "SAS": (29.43, -98.44, -6, 650), "TOR": (43.64, -79.38, -5, 249),
    "UTA": (40.77, -111.90, -7, 4226), "WAS": (38.90, -77.02, -5, 25),
}
# Fallback: US centroid, Central time, moderate elevation.
_DEFAULT = (39.8, -98.6, -6, 900)

ALTITUDE_THRESHOLD_FT = 3000  # Denver / Salt Lake City are the meaningful ones


def team_geo(code: str) -> Tuple[float, float, int, int]:
    return TEAM_GEO.get(canonical_team(code, strict=False), _DEFAULT)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
