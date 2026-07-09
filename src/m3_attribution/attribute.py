#!/usr/bin/env python3
"""M3 · [2] Per-window attribution — which channels drive a window's rarity.

The engine of M3. Method = **perturbation / ablation**, model-agnostic (only uses
`decision_function`, so it survives a detector swap — D7):

    base       = rarity score of the window as-is
    for channel c:
        replace c's 17 values with its normal baseline, re-score -> new
        contrib[c] = base - new          (how much rarity c was carrying)

contrib[c] large & positive -> channel c was guilty; near zero -> innocent.

Channel-major layout (CRITICAL, risk #1): a flattened window is 187 numbers where
channel c occupies `[c*17:(c+1)*17]` (17 timesteps of channel c). This MUST match
ESA's `algorithm.py` reshape — so we reuse `window_data` from M2's `scores.py`
verbatim, never re-implement it. `verify()` guards it: an unperturbed window must
reproduce M1's cached continuous score exactly.

Cost: 1 + 11 = 12 `decision_function` calls total, each over ALL windows at once
(not one call per window). Fast even on the full test set.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels, window_data  # noqa: E402  SAME windowing as M1

MODEL_PKL = config.CACHE_DIR / "model.pkl"
BASELINE_NPY = config.CACHE_DIR / "m3_baseline.npy"
SCORES_CONTINUOUS = config.CACHE_DIR / "scores_continuous.npy"  # M1 truth (per window)
WS = config.WINDOW_SIZE  # 17
N_CH = len(config.TARGET_CHANNELS)  # 11


# SHORT EXPLANATION: put channel c's 17 slots to its normal value in a COPY of every
# window, re-score, and the drop in rarity is c's contribution. Done for all 11 channels
# with 12 scoring calls total (1 base + 11), each over the whole batch of windows.
def attribute_many(windows: np.ndarray, clf, baseline: np.ndarray) -> np.ndarray:
    """Per-channel contribution for a batch of flattened windows.

    windows: (m, 187) channel-major, exactly as produced by `window_data`.
    returns: (m, 11) contribution; contrib[i, c] = base_i - score_with_c_normalised.
    """
    base = clf.decision_function(windows)  # (m,)
    contrib = np.empty((len(windows), N_CH), dtype=np.float64)
    for c in range(N_CH):
        pert = windows.copy()
        pert[:, c * WS : (c + 1) * WS] = baseline[c]  # channel c -> its normal value
        new = clf.decision_function(pert)  # (m,)
        contrib[:, c] = base - new
    return contrib


# SHORT EXPLANATION: same thing for a single window -- convenience wrapper.
def attribute_window(window: np.ndarray, clf, baseline: np.ndarray) -> np.ndarray:
    """Per-channel contribution (11,) for one flattened window (187,)."""
    return attribute_many(window[None, :], clf, baseline)[0]


# SHORT EXPLANATION: build a synthetic flattened window that is "all normal" (every
# channel sits at its baseline). The starting point for controlled tests.
def _baseline_window(baseline: np.ndarray) -> np.ndarray:
    """An all-normal window (187,): each channel's 17 slots = its baseline value."""
    return np.repeat(baseline, WS).astype(np.float32)  # channel-major: [c*17:(c+1)*17]=baseline[c]


# SHORT EXPLANATION: the "did it work?" check. Five things: channel-major order matches
# M1 exactly (risk #1); a real rare window gets a culprit; normalising ALL channels kills
# the rarity (baseline not toxic); a single extreme channel dominates; and a collective
# case is measured (not pass/fail) to document the known 1-channel limit (risk #3).
def verify(clf, baseline: np.ndarray) -> None:
    """Success-test for M3 Phase 2 (raises AssertionError on hard checks)."""
    data = load_test_channels()
    windows = window_data(data, WS)  # (n, 187) -- SAME as M1
    m1_scores = np.load(SCORES_CONTINUOUS)

    # (e) CHANNEL-MAJOR GUARD (risk #1): unperturbed windows reproduce M1's scores.
    sample = np.array([0, len(windows) // 2, len(windows) - 1])
    ours = clf.decision_function(windows[sample])
    assert np.allclose(ours, m1_scores[sample], atol=1e-9), (
        "unperturbed score != M1 cached score -> windowing/order mismatch (risk #1)"
    )

    # (a) real rare window: the highest-scoring window must have >=1 positive contrib.
    rare_i = int(np.argmax(m1_scores))
    contrib = attribute_window(windows[rare_i], clf, baseline)
    assert (contrib > 0).sum() >= 1, "no channel lowers rarity on the rarest window"

    # (b) baseline not toxic: an all-normal window is less rare than a real anomaly.
    all_normal = _baseline_window(baseline)
    base_rare = clf.decision_function(windows[rare_i][None, :])[0]
    score_normal = clf.decision_function(all_normal[None, :])[0]
    assert score_normal < base_rare, "all-baseline window not less rare than a real anomaly (toxic baseline)"

    # (c) synthetic single-extreme: one channel pushed far out -> it dominates the ranking.
    k = 21 - 18  # channel_21 (wide dynamic range) as the planted culprit
    synth = _baseline_window(baseline).copy()
    synth[k * WS : (k + 1) * WS] = baseline[k] + 10.0  # clearly extreme vs its normal span
    contrib_synth = attribute_window(synth, clf, baseline)
    assert int(np.argmax(contrib_synth)) == k, (
        f"planted extreme channel {k+18} did not dominate (argmax={np.argmax(contrib_synth)+18})"
    )

    # (d) synthetic COLLECTIVE (measure, NOT pass/fail): start from a REAL normal window and
    #     break the JOINT relationship of a correlated pair (22 & 23 share physical_unit_9) by
    #     SWAPPING their trajectories. Each channel stays in a plausible range; only the
    #     combination is off -> a genuine collective anomaly (not two independent extremes).
    #     Documents how 1-channel perturbation splits coupled blame (known limit, risk #3).
    a, b = 22 - 18, 23 - 18
    normal_i = int(np.argmin(m1_scores))  # a most-normal real window as the clean base
    coll = windows[normal_i].copy()
    sa = coll[a * WS : (a + 1) * WS].copy()
    sb = coll[b * WS : (b + 1) * WS].copy()
    coll[a * WS : (a + 1) * WS], coll[b * WS : (b + 1) * WS] = sb, sa  # swap 22 <-> 23
    score_base_coll = clf.decision_function(windows[normal_i][None, :])[0]
    score_coll = clf.decision_function(coll[None, :])[0]
    contrib_coll = attribute_window(coll, clf, baseline)

    print("\n=== M3 Phase 2 success-test ===")
    print(f"  (e) channel-major   : unperturbed == M1 score on {len(sample)} windows  OK  (risk #1 guarded)")
    print(f"  (a) rare window     : {(contrib>0).sum()} channels lower rarity (window #{rare_i})  OK")
    print(f"  (b) baseline sane   : all-normal score {score_normal:.4f} < rare {base_rare:.4f}  OK")
    print(f"  (c) single-extreme  : channel_{k+18} dominates the ranking  OK")
    verdict = "rose (collective detected)" if score_coll > score_base_coll else "~unchanged (pair too similar)"
    print(f"  (d) collective (doc): swap channel_22<->23 trajectories in a normal window")
    print(f"        rarity {score_base_coll: .4f} -> {score_coll: .4f}  ({verdict})")
    for ch_i in (a, b):
        print(f"        channel_{ch_i+18}: contrib={contrib_coll[ch_i]: .5f}")
    print(f"      top real-anomaly channels (window #{rare_i}):")
    order = np.argsort(contrib)[::-1]
    total = contrib[contrib > 0].sum()
    for ch_i in order[:4]:
        pct = 100 * contrib[ch_i] / total if total > 0 else 0.0
        print(f"        channel_{ch_i+18}: contrib={contrib[ch_i]: .5f}  ({pct:4.1f}%)")


# SHORT EXPLANATION: load model + baseline, then run the success-test on real data.
def main() -> None:
    if not MODEL_PKL.exists():
        sys.exit(f"Missing cached model: {MODEL_PKL}. Run src/m1_detection/model.py first.")
    if not BASELINE_NPY.exists():
        sys.exit(f"Missing baseline: {BASELINE_NPY}. Run src/m3_attribution/baseline.py first.")
    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    baseline = np.load(BASELINE_NPY)
    print(f"Model + baseline loaded  (threshold_={clf.threshold_:.6f}, baseline shape={baseline.shape})")
    verify(clf, baseline)


if __name__ == "__main__":
    main()
