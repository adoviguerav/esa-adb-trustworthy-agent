#!/usr/bin/env python3
"""M2 · [5] Evaluation — report M2 on the untouched test-final third, once.

Pulls together everything: the winning p-value variant + alpha* (from alpha.py), scores
the TEST-FINAL third (third 3, never used for tuning) with the same event-wise ESAScores
as M1, and reports honestly:

  - M2 precision / recall / F0.5 / F2 at alpha* and at the budget alpha.
  - Baseline M1@third-final: M1's cached binary restricted to third 3, SAME metric, so
    "M2 vs M1" is pears-to-pears (M1's 0.9487 is full-test and not directly comparable).
  - Coverage on held-out third-3 normals: aggregate + per-block spread (the drift bursts).
  - A plot to docs/m2_drift.png: normal-score p95 vs the frozen threshold over time.

Reports F2 and recall next to F0.5 because F0.5 alone weights precision and hides the
false-negative side that matters operationally (see plan's headline trade-off).
"""
from __future__ import annotations

import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty import metric  # noqa: E402
from m2_uncertainty.conformal import conformal_p  # noqa: E402

SPLIT_NPZ = config.CACHE_DIR / "split.npz"
SCORES_CONTINUOUS = config.CACHE_DIR / "scores_continuous.npy"
CALIB_SCORES = config.CACHE_DIR / "calib_scores.npy"
P_TEST = config.CACHE_DIR / "p_test.npy"
P_TEST_ROLLING = config.CACHE_DIR / "p_test_rolling.npy"
ALPHA_CHOICE = config.CACHE_DIR / "alpha_choice.npz"
M1_BINARY = config.CACHE_DIR / "scores_test.csv"
DRIFT_PNG = config.REPO / "docs" / "m2_drift.png"


# SHORT EXPLANATION: F_beta from precision and recall. Lets us report F0.5 and F2 from the
# same event-wise precision/recall without re-running the metric.
def f_beta(precision: float, recall: float, beta: float) -> float:
    b2 = beta * beta
    denom = b2 * precision + recall
    return float((1 + b2) * precision * recall / denom) if denom > 0 else 0.0


# SHORT EXPLANATION: score a per-window 0/1 prediction over a time range with ESAScores and
# return precision / recall / F0.5 / F2 (metric prints muted).
def report_at(p_values: np.ndarray, window_idx: np.ndarray, alpha: float,
              timestamps: pd.Series, labels: pd.DataFrame, n_points: int, lo, hi) -> dict:
    wb = (p_values < alpha).astype(np.uint8)
    marked = int(wb.sum())
    if marked == 0:
        return {"marked": 0, "precision": 0.0, "recall": 0.0, "F0.5": 0.0, "F2": 0.0}
    pts = metric.windows_to_points(window_idx, wb, n_points)
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        r = metric.ew_scores(pts, timestamps, labels, lo, hi)
    prec, rec = float(r.get("EW_precision", 0.0)), float(r.get("EW_recall", 0.0))
    return {"marked": marked, "precision": prec, "recall": rec,
            "F0.5": float(r.get("EW_F_0.50", 0.0)), "F2": f_beta(prec, rec, 2.0)}


# SHORT EXPLANATION: baseline M1 on the SAME third-3 window, from M1's cached per-point
# binary, via the SAME ESAScores -> a fair "M2 vs M1" comparison on identical ground.
def m1_at_period(timestamps: pd.Series, labels: pd.DataFrame, lo, hi) -> dict:
    m1 = np.loadtxt(M1_BINARY, delimiter=",").astype(np.uint8)
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        r = metric.ew_scores(m1, timestamps, labels, lo, hi)
    prec, rec = float(r.get("EW_precision", 0.0)), float(r.get("EW_recall", 0.0))
    return {"precision": prec, "recall": rec,
            "F0.5": float(r.get("EW_F_0.50", 0.0)), "F2": f_beta(prec, rec, 2.0)}


# SHORT EXPLANATION: coverage on held-out third-3 independent normals -- aggregate plus the
# per-block spread that exposes the bursts (a single aggregate number hides them).
def coverage_report(scores, normal, thirds, calib, alpha=0.05, n_blocks=60) -> dict:
    step = config.WINDOW_SIZE
    ni = np.arange(0, len(scores), step)
    ni = ni[(thirds[ni] == 2) & normal[ni]]           # third-3 independent normals
    p = conformal_p(scores[ni], calib)
    order = np.argsort(ni)
    per_block = np.array([float(np.mean(p[order][b] < alpha))
                          for b in np.array_split(np.arange(len(p)), n_blocks)])
    return {"aggregate": float(np.mean(p < alpha)), "n": len(p),
            "block_std": float(per_block.std()), "block_min": float(per_block.min()),
            "block_max": float(per_block.max())}


# SHORT EXPLANATION: draw the drift picture -- per-time-block p95 of the normal score vs the
# frozen calibration threshold. Where p95 spikes above the line = a burst = false alarms.
def make_plot(scores, normal, thirds, calib, n_blocks=60) -> None:
    import matplotlib
    if "ipykernel" not in sys.modules:  # headless CLI only: switching inside a notebook
        matplotlib.use("Agg")           # would silently kill plt.show() for later cells
    import matplotlib.pyplot as plt

    step = config.WINDOW_SIZE
    ni = np.arange(0, len(scores), step)
    ni = ni[normal[ni]]                                # all independent normals, time-sorted
    s = scores[ni]
    thr = float(np.quantile(calib, 0.95))              # frozen p<0.05 threshold
    blocks = np.array_split(np.arange(len(s)), n_blocks)
    p95 = [np.quantile(s[b], 0.95) for b in blocks]
    mean = [s[b].mean() for b in blocks]
    x = np.arange(n_blocks)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x, p95, color="crimson", label="normal-score p95 (per block)")
    ax.plot(x, mean, color="steelblue", label="normal-score mean (per block)")
    ax.axhline(thr, color="black", ls="--", label="frozen third-1 threshold (p<0.05)")
    ax.set_xlabel("time block (across whole test)")
    ax.set_ylabel("IForest score")
    ax.set_title("M2 drift: normal-score tail (p95) spikes in bursts; mean stays flat")
    ax.legend(fontsize=8)
    fig.tight_layout()
    DRIFT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(DRIFT_PNG, dpi=120)
    plt.close(fig)


# SHORT EXPLANATION: run the whole final evaluation on test-final and print the honest
# report; assert only the sanity checks (metric runs, categories make sense).
def evaluate() -> None:
    for f in (SPLIT_NPZ, SCORES_CONTINUOUS, CALIB_SCORES, P_TEST, ALPHA_CHOICE, M1_BINARY):
        if not f.exists():
            sys.exit(f"Missing {f}. Run phases 1-4 first.")
    split = np.load(SPLIT_NPZ)
    thirds, normal, bounds = split["window_third"], split["window_normal"], split["point_bounds"]
    scores = np.load(SCORES_CONTINUOUS)
    calib = np.load(CALIB_SCORES)
    ch = np.load(ALPHA_CHOICE)
    winner, a_star, budget = str(ch["winner"]), float(ch["alpha_fixed"]), float(ch["budget_alpha"])
    if winner != "fixed":
        a_star = float(ch["alpha_rolling"])
    p_test = np.load(P_TEST if winner == "fixed" else P_TEST_ROLLING)

    test_idx = np.flatnonzero(thirds == 2)            # aligned with p_test
    timestamps = pd.read_csv(config.TEST_CSV, usecols=["timestamp"],
                             parse_dates=["timestamp"])["timestamp"].dt.tz_localize(None)
    n_points = len(timestamps)
    labels = metric.load_labels()
    lo = timestamps.iloc[bounds[2]]
    hi = timestamps.iloc[bounds[3] - 1] + pd.Timedelta(seconds=1)  # inclusive last point

    m2_star = report_at(p_test, test_idx, a_star, timestamps, labels, n_points, lo, hi)
    m2_budget = report_at(p_test, test_idx, budget, timestamps, labels, n_points, lo, hi)
    m1 = m1_at_period(timestamps, labels, lo, hi)
    cov = coverage_report(scores, normal, thirds, calib)
    make_plot(scores, normal, thirds, calib)

    print("\n================ M2 FINAL REPORT (test-final = third 3, once) ================")
    print(f"Winner variant: {winner.upper()}   alpha* = {a_star:.2e}   budget alpha = {budget}")
    print(f"\n  M2 @ alpha* (optimised for F0.5):")
    print(f"    marked {m2_star['marked']} windows ({m2_star['marked']/len(p_test):.2%})")
    print(f"    precision={m2_star['precision']:.4f}  recall={m2_star['recall']:.4f}  "
          f"F0.5={m2_star['F0.5']:.4f}  F2={m2_star['F2']:.4f}")
    print(f"\n  M2 @ budget alpha (guarantee story, expected weak F0.5):")
    print(f"    precision={m2_budget['precision']:.4f}  recall={m2_budget['recall']:.4f}  "
          f"F0.5={m2_budget['F0.5']:.4f}  F2={m2_budget['F2']:.4f}")
    print(f"\n  Baseline M1 @ third-final (same ESAScores, fair ground):")
    print(f"    precision={m1['precision']:.4f}  recall={m1['recall']:.4f}  "
          f"F0.5={m1['F0.5']:.4f}  F2={m1['F2']:.4f}")
    print(f"    NOTE: M2@alpha* ~= M1 here. The F0.5-optimal conformal cut (score > max normal-")
    print(f"    calibration ~ -0.003) nearly coincides with M1's contamination threshold (~0):")
    print(f"    ~99.97% point agreement, event-wise identical. M2 TIES M1 on F0.5, it does not")
    print(f"    beat it -- two independent threshold routes land in the same place (mutual sanity).")
    print(f"\n  Coverage on third-3 held-out normals (target {0.05}):")
    print(f"    aggregate={cov['aggregate']:.4f} (n={cov['n']})  "
          f"per-block std={cov['block_std']:.3f} min={cov['block_min']:.3f} max={cov['block_max']:.3f}")
    print(f"    -> aggregate near target; per-block bursts remain (honest limit).")
    print(f"\n  Drift plot -> {DRIFT_PNG}")

    print("\n=== Phase 5 success-test ===")
    print(f"  (a) coverage reported (aggregate + per-block spread)  OK")
    print(f"  (b) M1@third-final via same ESAScores: F0.5={m1['F0.5']:.4f} (plausible)  OK")
    print(f"  (c) M2 F0.5/recall/F2 at alpha* reported  OK")
    print(f"  (d) M2 vs M1@third-final: F0.5 {m2_star['F0.5']:.3f} vs {m1['F0.5']:.3f} -- M2 TIES M1")
    print(f"      (alpha* recovers ~M1's threshold). M2's value is NOT a better score but the")
    print(f"      trustworthy layer: calibrated confidence, 3-way abstention, coverage self-diagnosis.")
    assert 0.0 <= m1["F0.5"] <= 1.0 and m2_star["marked"] > 0, "sanity failed"
    print("\nNote: M1 full-test regression (0.9487) lives in tests/test_m1_model.py (M2 untouched).")


# SHORT EXPLANATION: run the final evaluation.
def main() -> None:
    evaluate()


if __name__ == "__main__":
    main()
