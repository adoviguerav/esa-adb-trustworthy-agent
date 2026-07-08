#!/usr/bin/env python3
"""M2 · [3] Conformal p-value — turn a raw score into calibrated confidence.

One-class conformal anomaly detection (Vovk; Laxhammar & Falkman). For a query window
with score `s`, calibrated against `n` scores of held-out NORMAL windows:

    p = (#{calib >= s} + 1) / (n + 1)          confidence  C = 1 - p

Under exchangeability, p is (super)uniform on normal data, so P(p < alpha) <= alpha:
flagging when p < alpha controls the false-positive rate at alpha. This replaces M1's
blind contamination threshold with a threshold that *means* something and can be *measured*.

Calibration uses 1 window of every `window_size` (non-overlapping -> independent), so the
finite-sample guarantee holds despite the stride-1 overlap of neighbouring windows.

Outputs (cached): `calib_scores.npy` (the calibration set), `p_valid.npy`, `p_test.npy`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

SCORES_CONTINUOUS = config.CACHE_DIR / "scores_continuous.npy"
SPLIT_NPZ = config.CACHE_DIR / "split.npz"
CALIB_SCORES = config.CACHE_DIR / "calib_scores.npy"
P_VALID = config.CACHE_DIR / "p_valid.npy"
P_TEST = config.CACHE_DIR / "p_test.npy"


# SHORT EXPLANATION: the heart of M2. For a window's score, ask "of the known-normal
# windows, what fraction were this rare or rarer?". That fraction is the p-value: low p
# means almost no normal window was this weird -> suspicious. Done fast for millions at once.
def conformal_p(query: np.ndarray, calib: np.ndarray) -> np.ndarray:
    """Vectorised one-class conformal p-value of each query score against `calib`.

    p_i = (#{calib >= query_i} + 1) / (len(calib) + 1). Uses a sorted-search so the
    whole query array is scored in O((n+m) log n).
    """
    calib_sorted = np.sort(np.asarray(calib, dtype=np.float64))
    n = len(calib_sorted)
    ge = n - np.searchsorted(calib_sorted, query, side="left")  # #{calib >= query}
    return (ge + 1.0) / (n + 1.0)


# SHORT EXPLANATION: pick the calibration set -- normal windows from chunk 1, taking 1 of
# every 17. Neighbouring windows overlap 16/17 points (near-duplicates); skipping 17 makes
# them independent, so the guarantee is honest.
def select_calibration(scores: np.ndarray, normal: np.ndarray, thirds: np.ndarray) -> np.ndarray:
    """Independent, normal calibration windows from third 1 (1 of every window_size)."""
    step = config.WINDOW_SIZE
    cand = np.arange(0, len(scores), step)            # spaced >= window_size -> non-overlapping
    cand = cand[(thirds[cand] == 0) & normal[cand]]   # keep third-1 normal windows
    return scores[cand]


# SHORT EXPLANATION: build the calibration set, then compute p-values for chunk 2
# (validation) and chunk 3 (test-final), and save them.
def build() -> dict:
    """Compute calibration set + p-values for valid and test-final, cache them."""
    if not SCORES_CONTINUOUS.exists() or not SPLIT_NPZ.exists():
        sys.exit("Missing scores_continuous.npy / split.npz. Run scores.py and split.py first.")
    scores = np.load(SCORES_CONTINUOUS)
    split = np.load(SPLIT_NPZ)
    normal, thirds = split["window_normal"], split["window_third"]

    calib = select_calibration(scores, normal, thirds)
    p_valid = conformal_p(scores[thirds == 1], calib)
    p_test = conformal_p(scores[thirds == 2], calib)

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CALIB_SCORES, calib)
    np.save(P_VALID, p_valid)
    np.save(P_TEST, p_test)
    print(f"Calibration set -> {CALIB_SCORES}  (n={len(calib)})")
    print(f"p (valid)       -> {P_VALID}  (n={len(p_valid)})")
    print(f"p (test-final)  -> {P_TEST}  (n={len(p_test)})")
    return {"scores": scores, "normal": normal, "thirds": thirds, "calib": calib}


# SHORT EXPLANATION: given a target rate and sample size, how much wiggle room is normal?
# Returns the confidence interval, used to judge whether coverage is "close enough".
def _binom_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Normal-approximation binomial CI half-width around p at n samples."""
    half = z * np.sqrt(p * (1 - p) / n)
    return p - half, p + half


# SHORT EXPLANATION: the "did it work?" check. p stays in [0,1]; higher score gives lower
# p; a hand example matches exactly; and on same-era normals ~5% have p<0.05 as promised.
# This tests the MATH (same epoch); drift is Phase 5's job.
def verify(s: dict) -> None:
    """Success-test for Phase 3 (raises AssertionError on any failure)."""
    scores, normal, thirds = s["scores"], s["normal"], s["thirds"]

    # (a) p in [0,1] on a broad query.
    p_all = conformal_p(scores[thirds == 2], s["calib"])
    assert (p_all >= 0).all() and (p_all <= 1).all(), "p out of [0,1]"

    # (b) monotonicity: higher score -> lower (or equal) p.
    grid = np.linspace(scores.min(), scores.max(), 50)
    p_grid = conformal_p(grid, s["calib"])
    assert np.all(np.diff(p_grid) <= 1e-12), "p not monotone non-increasing in score"

    # (c) exact hand example.
    p_hand = conformal_p(np.array([0.35]), np.array([0.1, 0.2, 0.3, 0.4, 0.5]))[0]
    assert abs(p_hand - 3 / 6) < 1e-12, f"hand p={p_hand}, expected 0.5"

    # (d) coverage on INDEPENDENT normal windows held out of calibration (within third 1).
    #     Split the third-1 independent normals by INTERLEAVING (even / odd positions), not
    #     chronologically: both halves then share the same epoch and time-trend, so this
    #     isolates the conformal MATH. A chronological split conflates it with temporal
    #     drift -- which is real here even inside third 1 -- and that is Phase 5's job.
    step = config.WINDOW_SIZE
    cand = np.arange(0, len(scores), step)
    cand = cand[(thirds[cand] == 0) & normal[cand]]
    calib_a, check_b = scores[cand[::2]], scores[cand[1::2]]  # interleaved -> same epoch
    p_check = conformal_p(check_b, calib_a)
    alpha = 0.05
    rate = float(np.mean(p_check < alpha))
    lo, hi = _binom_ci(alpha, len(p_check))

    print("\n=== Phase 3 success-test ===")
    print(f"  (a) p in [0,1]       : [{p_all.min():.4f}, {p_all.max():.4f}]  OK")
    print(f"  (b) monotone         : p decreasing in score  OK")
    print(f"  (c) hand example     : p(0.35 | [.1...5]) = {p_hand:.4f} == 0.5  OK")
    print(f"  (d) coverage (indep) : P(p<{alpha}) = {rate:.4f}  "
          f"(target {alpha}, 95% CI [{lo:.4f}, {hi:.4f}], n={len(p_check)})")
    assert lo - 0.01 <= rate <= hi + 0.01, (
        f"empirical coverage {rate:.4f} outside CI [{lo:.4f}, {hi:.4f}] -> check drift/overlap"
    )
    print(f"      -> within CI: conformal math sound on same-epoch normals  OK")


# SHORT EXPLANATION: build the p-values, then verify them.
def main() -> None:
    s = build()
    verify(s)


if __name__ == "__main__":
    main()
