"""Pytest configuration for backend tests.

Ensures the ``backend/`` directory is importable so tests can ``import
feature_engine`` and ``import model_training.train_*`` exactly the way the
training scripts do at runtime.
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture(autouse=True)
def _market_anchored_by_default(monkeypatch):
    """The existing suite was written against the MARKET-ANCHORED behavior, which
    ``MARKET_BLIND=0`` reproduces exactly. Pin it off by default so those tests stay
    meaningful regardless of the product default (which is market-blind). Market-blind
    tests opt back in with ``monkeypatch.setenv("MARKET_BLIND", "1")``."""
    monkeypatch.setenv("MARKET_BLIND", "0")
