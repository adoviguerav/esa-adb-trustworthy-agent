#!/usr/bin/env python3
"""M3 · [1] Per-channel baseline — the "normal value" of each channel (18-28).

Attribution (Phase 2) works by *perturbation*: to ask "does channel c cause this
anomaly?", we replace channel c with its normal value and see how much the rarity
drops. This module builds that normal value — one number per channel.

Definition: the **median of each channel over the NORMAL points of third 1**.
  - median      -> robust: an anomalous spike does not move it.
  - third 1     -> M2's calibration past. Using third 3 (where we validate) would
                   leak the future into the explanation. Forbidden.
  - normal only -> a point counts iff no target channel is anomalous there
                   (same per-point flag M2 uses); anomalous points would poison it.

Output: `data/cached/m3_baseline.npy`, shape (11,), float32 (raw channel units).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels  # noqa: E402  raw channel VALUES
from m2_uncertainty.split import (  # noqa: E402  normal mask + third cuts
    load_point_anomaly,
    third_boundaries,
)

BASELINE_NPY = config.CACHE_DIR / "m3_baseline.npy"


# SHORT EXPLANATION: which points belong to third 1 AND are normal. The median is
# taken only over these -- the clean past, no leak from the validation future.
def third1_normal_mask() -> np.ndarray:
    """Boolean mask (n_points,): True for points in third 1 with no anomaly flagged."""
    point_anomaly = load_point_anomaly()  # (n_points,) 0/1
    n_points = len(point_anomaly)
    bounds = third_boundaries(n_points)  # [0, t1, t2, n]
    t1 = bounds[1]
    in_third1 = np.arange(n_points) < t1
    is_normal = point_anomaly == 0
    return in_third1 & is_normal


# SHORT EXPLANATION: the "normal value" of every channel = median over the clean
# third-1 points. One number per channel (18..28), in the channel's raw units.
def compute_baseline() -> np.ndarray:
    """Return the per-channel median over third-1 normal points, shape (11,) float32."""
    data = load_test_channels()  # (n_points, 11) raw values, CSV channel order
    mask = third1_normal_mask()
    if mask.sum() == 0:
        raise RuntimeError("no normal points in third 1 -- cannot build baseline")
    baseline = np.median(data[mask], axis=0)  # (11,)
    return baseline.astype(np.float32)


# SHORT EXPLANATION: the "did it work?" check. 11 finite values, built only from the
# clean third-1 past (no leak), and each value inside that channel's own normal range.
def verify(baseline: np.ndarray) -> None:
    """Success-test for M3 Phase 1 (raises AssertionError on any failure)."""
    data = load_test_channels()
    mask = third1_normal_mask()
    n_used = int(mask.sum())

    # (a) shape + finite: exactly 11 usable numbers.
    assert baseline.shape == (len(config.TARGET_CHANNELS),), (
        f"baseline shape {baseline.shape} != ({len(config.TARGET_CHANNELS)},)"
    )
    assert np.isfinite(baseline).all(), "baseline contains NaN/inf"

    # (b) no leak: every point used sits in third 1 and is normal.
    point_anomaly = load_point_anomaly()
    bounds = third_boundaries(len(point_anomaly))
    used_idx = np.where(mask)[0]
    assert used_idx.max() < bounds[1], "baseline used a point outside third 1 (leak)"
    assert point_anomaly[used_idx].max() == 0, "baseline used an anomalous point (poison)"

    # (c) sane range: each baseline value lies within its channel's third-1 normal span.
    lo = data[mask].min(axis=0)
    hi = data[mask].max(axis=0)
    assert np.all(baseline >= lo) and np.all(baseline <= hi), (
        "a baseline value falls outside its channel's observed normal range"
    )

    print("\n=== M3 Phase 1 success-test ===")
    print(f"  (a) shape/finite : {baseline.shape}, no NaN/inf  OK")
    print(f"  (b) no leak      : {n_used} points, all in third 1 and normal  OK")
    print(f"  (c) sane range   : every channel within its normal span  OK")
    for ch, val, l, h in zip(config.TARGET_CHANNELS, baseline, lo, hi):
        print(f"      {ch:>11}: baseline={val: .4f}  span=[{l: .4f}, {h: .4f}]")


# SHORT EXPLANATION: run it -- build the baseline, cache it to disk, then verify.
def main() -> None:
    baseline = compute_baseline()
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(BASELINE_NPY, baseline)
    print(f"Baseline cached -> {BASELINE_NPY}  (shape={baseline.shape})")
    verify(baseline)


if __name__ == "__main__":
    main()
