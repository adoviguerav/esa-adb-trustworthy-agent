#!/usr/bin/env python3
"""M2 · [1] Continuous scores — raw per-window anomaly score from the M1 forest.

M1 caches a *binary* decision per point. The trustworthy layer needs the *continuous*
score behind that decision. This module reloads the exact same cached forest
(`data/cached/model.pkl`, never retrained) and runs `decision_function` over the test
windows, reproducing ESA's windowing (`subsequence_if/algorithm.py`) point-for-point.

Output: one continuous score per window, cached to `data/cached/scores_continuous.npy`.
Higher score = rarer. This score feeds conformal calibration [3].

Consistency guarantee (checked in `verify()`): binarising `score > clf.threshold_` and
padding with `window_size // 2` zeros must reproduce M1's cached binary `scores_test.csv`
exactly. If windowing drifts, that check fails loudly.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

MODEL_PKL = config.CACHE_DIR / "model.pkl"
SCORES_BINARY = config.CACHE_DIR / "scores_test.csv"  # M1 binary (predict + pad)
SCORES_CONTINUOUS = config.CACHE_DIR / "scores_continuous.npy"  # M2 output (per window)


# SHORT EXPLANATION: read the test file, keep only the 11 sensor columns we care about
# (channel_18..28), drop everything else. Returns a big table of raw numbers.
def load_test_channels() -> np.ndarray:
    """Load the test set restricted to the target channels, in CSV order (float32).

    Mirrors ESA's ``algorithm.py::load_data``: only ``target_channels`` are kept and
    their order follows the file, not ``TARGET_CHANNELS``. Since the CSV already lists
    channel_18..28 first and in order, the two coincide.
    """
    df = pd.read_csv(
        config.TEST_CSV,
        index_col="timestamp",
        usecols=["timestamp", *config.TARGET_CHANNELS],
        dtype={c: np.float32 for c in config.TARGET_CHANNELS},
    )
    # Preserve CSV column order (defensive; usecols already returns file order).
    ordered = [c for c in df.columns if c in set(config.TARGET_CHANNELS)]
    return df[ordered].to_numpy()


# SHORT EXPLANATION: slide a 17-step window down the table. Each window (17 time steps x
# 11 sensors = 187 numbers) becomes one row -- that is one "slice of time" the forest sees.
def window_data(data: np.ndarray, window_size: int) -> np.ndarray:
    """Window exactly as ESA's algorithm.py (sliding_window_view + reshape)."""
    windowed = sliding_window_view(data, window_shape=window_size, axis=0)
    return windowed.reshape(-1, window_size * data.shape[1])


# SHORT EXPLANATION: load the already-trained forest (never retrain it), show it every
# window, and ask "how rare is this?". One number per window -- higher means rarer.
def compute_scores() -> np.ndarray:
    """Load the M1 forest and return one continuous score per test window."""
    if not MODEL_PKL.exists():
        sys.exit(f"Missing cached model: {MODEL_PKL}. Run src/m1_detection/model.py first.")

    data = load_test_channels()
    windows = window_data(data, config.WINDOW_SIZE)

    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    print(f"Model loaded  <- {MODEL_PKL}  (threshold_={clf.threshold_:.6f})")

    scores = clf.decision_function(windows)
    return np.asarray(scores, dtype=np.float64)


# SHORT EXPLANATION: the "did it work?" check. Right count, no broken numbers, sane range,
# and the key one: chopping these raw scores at M1's threshold must give M1's exact
# yes/no back. If it does, our windowing is identical to ESA's -> the scores are trustworthy.
def verify(scores: np.ndarray) -> None:
    """Success-test for Phase 1 (raises AssertionError on any failure)."""
    n_points = sum(1 for _ in open(config.TEST_CSV)) - 1  # minus header
    expected_windows = n_points - (config.WINDOW_SIZE - 1)

    # (a) count == n windows
    assert len(scores) == expected_windows, (
        f"score count {len(scores)} != expected windows {expected_windows}"
    )
    # (b) no NaN / inf
    assert np.isfinite(scores).all(), "scores contain NaN/inf"
    # (c) sane range
    lo, hi = scores.min(), scores.max()
    assert -1.0 < lo < 0.0 < hi < 1.0, f"score range looks off: [{lo:.4f}, {hi:.4f}]"

    # (d) strong check: binarise + pad reproduces M1's cached binary exactly.
    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    binary = (scores > clf.threshold_).astype(np.int64)
    padded = np.pad(binary, config.WINDOW_SIZE // 2, constant_values=0)
    m1_binary = np.loadtxt(SCORES_BINARY, delimiter=",").astype(np.int64)
    assert len(padded) == len(m1_binary), (
        f"padded length {len(padded)} != M1 binary length {len(m1_binary)}"
    )
    mismatches = int(np.sum(padded != m1_binary))
    assert mismatches == 0, f"binary reproduction mismatch: {mismatches} points differ from M1"

    print("\n=== Phase 1 success-test ===")
    print(f"  (a) windows          : {len(scores)} == {expected_windows}  OK")
    print(f"  (b) finite           : no NaN/inf  OK")
    print(f"  (c) range            : [{lo:.4f}, {hi:.4f}]  OK")
    print(f"  (d) reproduces M1     : {mismatches} mismatches vs scores_test.csv  OK")
    print(f"      positives: {binary.sum()} windows above threshold ({binary.mean():.4%})")


# SHORT EXPLANATION: run the whole thing -- compute scores, save them to disk, then verify.
def main() -> None:
    scores = compute_scores()
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(SCORES_CONTINUOUS, scores)
    print(f"Continuous scores cached -> {SCORES_CONTINUOUS}  (n={len(scores)})")
    verify(scores)


if __name__ == "__main__":
    main()
