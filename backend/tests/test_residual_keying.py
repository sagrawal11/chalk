"""Residual models are keyed on the canonical player slug (PLANNING.md 9.1), so
training keys and inference lookups can never diverge on name casing.
"""
import numpy as np
import pandas as pd

from model_training.train_hybrid import train_residuals
from utils.names import player_slug


class _ZeroGlobal:
    """Global model that predicts 0, so residual == y (easy to control)."""

    def predict(self, X):
        return np.zeros(len(X))


def _one_player(display_name, n=200, seed=0):
    rng = np.random.default_rng(seed)
    f1 = rng.normal(size=n)
    f2 = rng.normal(size=n)
    X = pd.DataFrame({"f1": f1, "f2": f2})
    # A clearly learnable residual so the model passes the OOS gate and is kept.
    y = pd.Series(4.0 * f1 + rng.normal(size=n) * 0.3)
    slugs = pd.Series([display_name] * n)
    dates = pd.Series(pd.date_range("2022-01-01", periods=n, freq="D"))
    return X, y, slugs, dates


def test_player_slug_normalizes_casing_and_punctuation():
    assert player_slug("LeBron James") == "lebron_james"
    assert player_slug("lebron_james") == "lebron_james"
    assert player_slug("De'Aaron Fox") == "deaaron_fox"
    assert player_slug("P.J. Tucker") == "pj_tucker"


def test_residual_dict_is_keyed_by_slug_not_display_name():
    X, y, names, dates = _one_player("LeBron James")
    # train_residuals slugifies the provided names internally in main(); here we
    # pass the slug series the trainer would build.
    slugs = names.map(player_slug)
    local, kept = train_residuals(X, y, _ZeroGlobal(), slugs, dates)

    assert kept == 1
    assert "lebron_james" in local
    # The display name must NOT be a key (that was the 9.1 bug).
    assert "LeBron James" not in local
    # A predictor looking up by slug (from any casing) resolves the model.
    assert player_slug("LeBron James") in local
    assert player_slug("lebron_james") in local
