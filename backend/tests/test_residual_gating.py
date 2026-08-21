"""Residual models are gated on out-of-sample improvement (PLANNING.md 9.2):
a player whose residuals are learnable is kept; one whose residuals are pure
noise is dropped (falls back to global-only).
"""
import numpy as np
import pandas as pd

from model_training.train_hybrid import train_residuals


class _ZeroGlobal:
    def predict(self, X):
        return np.zeros(len(X))


def _combined():
    rng = np.random.default_rng(7)
    n = 220
    # Learnable player: residual is a strong linear function of a feature.
    lf1 = rng.normal(size=n)
    learn = pd.DataFrame({"f1": lf1, "f2": rng.normal(size=n)})
    learn_y = 5.0 * lf1 + rng.normal(size=n) * 0.2

    # Noise player: residual has no relationship to any feature.
    noise = pd.DataFrame({"f1": rng.normal(size=n), "f2": rng.normal(size=n)})
    noise_y = rng.normal(size=n)

    X = pd.concat([learn, noise], ignore_index=True)
    y = pd.concat([pd.Series(learn_y), pd.Series(noise_y)], ignore_index=True)
    slugs = pd.Series(["learnable_guy"] * n + ["noise_guy"] * n)
    dates = pd.Series(
        list(pd.date_range("2022-01-01", periods=n, freq="D"))
        + list(pd.date_range("2022-01-01", periods=n, freq="D"))
    )
    return X, y, slugs, dates


def test_only_improving_residual_models_are_kept():
    X, y, slugs, dates = _combined()
    local, kept = train_residuals(X, y, _ZeroGlobal(), slugs, dates)

    assert "learnable_guy" in local, "a genuinely learnable residual must be shipped"
    assert "noise_guy" not in local, "a noise residual must be gated out (fall back to global)"
    assert kept == 1
