"""Free, source-agnostic odds ingestion.

The whole pipeline speaks one normalized ``OddsLine`` vocabulary; concrete free
sources (PrizePicks/Underdog/DraftKings live, sportsbookreview/Kaggle historical
CSV, manual drop) sit behind the ``OddsProvider`` interface so nothing is
vendor-locked. Odds are used for market CONTEXT and ATS/O-U grading, not
staking (this is a content product).
"""
from odds.schema import MARKET_FAMILIES, OddsLine  # noqa: F401
from odds.provider import OddsProvider  # noqa: F401
