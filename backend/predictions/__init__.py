"""Sport-agnostic prediction schemas shared by the generic core (odds, picks,
track record, content). All NBA-specific logic lives behind the Sport plugin;
these containers only ever hold already-canonical codes and primitive fields so
they serialize cleanly for the immutable daily lock (see ``track_record``).
"""
from predictions.schema import (  # noqa: F401
    GamePrediction,
    PlayerPropPrediction,
    make_game_key,
)
