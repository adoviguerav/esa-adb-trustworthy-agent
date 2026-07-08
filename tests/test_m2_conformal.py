"""M2 · conformal p-value tests.

Locks the conformal math: deterministic hand example, monotonicity, and same-epoch
coverage (~uniform p on normals). The coverage test uses INTERLEAVED calibration so it
checks the math, not the temporal drift (drift is a measured finding, not a unit test).

Run: pytest tests/test_m2_conformal.py -v
Cached-data tests skip if the M2 cache is missing (run the phase scripts first).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402
from m2_uncertainty.conformal import conformal_p  # noqa: E402

SCORES = config.CACHE_DIR / "scores_continuous.npy"
SPLIT = config.CACHE_DIR / "split.npz"


def test_hand_example_exact():
    """p(0.35 | [0.1,0.2,0.3,0.4,0.5]) = (#>=0.35 + 1)/(5+1) = (2+1)/6 = 0.5."""
    p = conformal_p(np.array([0.35]), np.array([0.1, 0.2, 0.3, 0.4, 0.5]))[0]
    assert abs(p - 0.5) < 1e-12


def test_bounds_and_extremes():
    """p in (0,1]; a score above all calib gets the floor 1/(n+1); below all gets ~1."""
    calib = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    p = conformal_p(np.array([0.6, 0.0, 0.25]), calib)
    assert (p > 0).all() and (p <= 1).all()
    assert abs(p[0] - 1 / (len(calib) + 1)) < 1e-12       # above all -> floor
    assert abs(p[1] - 1.0) < 1e-12                        # below all -> 1


def test_monotone_decreasing():
    """Higher score -> lower (or equal) p."""
    calib = np.linspace(-0.2, 0.3, 500)
    grid = np.linspace(-0.3, 0.4, 200)
    p = conformal_p(grid, calib)
    assert np.all(np.diff(p) <= 1e-12)


@pytest.mark.skipif(not (SCORES.exists() and SPLIT.exists()),
                    reason="M2 cache missing; run scores.py + split.py first")
def test_same_epoch_coverage():
    """Interleaved same-epoch normals: P(p<0.05) ~ 0.05 (the conformal guarantee holds)."""
    scores = np.load(SCORES)
    split = np.load(SPLIT)
    normal, thirds = split["window_normal"], split["window_third"]
    step = config.WINDOW_SIZE
    cand = np.arange(0, len(scores), step)
    cand = cand[(thirds[cand] == 0) & normal[cand]]       # third-1 independent normals
    calib_a, check_b = scores[cand[::2]], scores[cand[1::2]]  # interleaved -> same epoch
    rate = float(np.mean(conformal_p(check_b, calib_a) < 0.05))
    assert 0.03 <= rate <= 0.08, f"same-epoch coverage {rate:.4f} outside [0.03, 0.08]"
