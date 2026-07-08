#!/usr/bin/env python3
"""M2 · [4] Alpha — the cut on the p-value, in two flavours, chosen on validation.

The p-value orders windows by how normal they look; alpha is where we cut. Two alphas,
because they answer different questions:

  - BUDGET alpha (per-window guarantee story): a fixed alpha (0.05). "I tolerate 5% false
    alarms per window." Used for the confidence narrative + coverage check, NOT for F0.5.
  - OPTIMISED alpha* (per-event score story): searched on a fine, LOW grid (1e-4..0.05) to
    maximise event-wise EW_F_0.50 on the VALIDATION third. Marking 5% of windows would
    create thousands of false events (F0.5 ~ 0), so the good alpha is far lower.

Both fixed (`p_valid.npy`) and rolling (`p_valid_rolling.npy`) p-values are tuned; the
variant with the better VALIDATION F0.5 wins and goes to the test-final report [5]. alpha*
is never chosen by looking at the test third (no peeking).

Three-way band: two cuts (alpha_low, alpha_high) -> anomaly / abstain ("no sé") / normal.

Output (cached): `alpha_choice.npz` with the grids, F0.5 curves, alpha* per variant, winner.
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

SPLIT_NPZ = config.CACHE_DIR / "split.npz"
P_VALID = config.CACHE_DIR / "p_valid.npy"
P_VALID_ROLLING = config.CACHE_DIR / "p_valid_rolling.npy"
ALPHA_CHOICE = config.CACHE_DIR / "alpha_choice.npz"

BUDGET_ALPHA = 0.05                                  # per-window guarantee story
# Fine, LOW grid for F0.5. Lower bound near the conformal p-floor 1/(n_calib+1): below it
# no window can be flagged. F0.5 is precision-weighted, so the optimum sits very low; the
# grid must reach down to the floor or alpha* pins to the boundary and we leave F0.5 unused.
GRID = np.logspace(np.log10(2e-5), np.log10(0.05), 25)


# SHORT EXPLANATION: score the validation third once for a given alpha: flag a window as
# anomaly when p < alpha, map to points, and compute event-wise F0.5 (metric prints muted).
def f05_at_alpha(p_valid: np.ndarray, valid_idx: np.ndarray, alpha: float,
                 timestamps: pd.Series, labels: pd.DataFrame, n_points: int,
                 lo, hi) -> float:
    window_binary = (p_valid < alpha).astype(np.uint8)
    if window_binary.sum() == 0:
        return 0.0  # no window flagged (alpha below the conformal p-floor) -> no detections
    pts = metric.windows_to_points(valid_idx, window_binary, n_points)
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        r = metric.ew_scores(pts, timestamps, labels, lo, hi)
    return float(r.get("EW_F_0.50", 0.0))


# SHORT EXPLANATION: sweep the alpha grid for one p-value variant and return the F0.5 at
# each alpha plus the alpha* that maximises it (all on validation, never on test).
def optimise_alpha(p_valid: np.ndarray, valid_idx: np.ndarray, timestamps: pd.Series,
                   labels: pd.DataFrame, n_points: int, lo, hi) -> tuple[np.ndarray, float, float]:
    f05 = np.array([f05_at_alpha(p_valid, valid_idx, a, timestamps, labels, n_points, lo, hi)
                    for a in GRID])
    best = int(np.argmax(f05))
    return f05, float(GRID[best]), float(f05[best])


# SHORT EXPLANATION: tune alpha on the validation third for BOTH p-value variants (fixed
# and rolling), pick the one with the better validation F0.5 as the winner, and cache the
# whole choice (grids, curves, alpha*, winner) for the final report.
def build() -> dict:
    """Tune alpha on validation for both variants, pick the winner, cache the choice."""
    for f in (SPLIT_NPZ, P_VALID, P_VALID_ROLLING):
        if not f.exists():
            sys.exit(f"Missing {f}. Run scores.py, split.py, conformal.py, rolling.py first.")
    split = np.load(SPLIT_NPZ)
    thirds, normal, bounds = split["window_third"], split["window_normal"], split["point_bounds"]
    valid_idx = np.flatnonzero(thirds == 1)          # aligned with p_valid arrays
    p_fixed = np.load(P_VALID)
    p_roll = np.load(P_VALID_ROLLING)

    timestamps = pd.read_csv(config.TEST_CSV, usecols=["timestamp"],
                             parse_dates=["timestamp"])["timestamp"].dt.tz_localize(None)
    n_points = len(timestamps)
    labels = metric.load_labels()
    lo, hi = timestamps.iloc[bounds[1]], timestamps.iloc[bounds[2]]  # validation window

    print(f"Tuning alpha on validation (third 2): {len(valid_idx)} windows, "
          f"grid {GRID[0]:.1e}..{GRID[-1]:.1e} ({len(GRID)} pts)")
    f05_fixed, a_fixed, best_fixed = optimise_alpha(p_fixed, valid_idx, timestamps, labels, n_points, lo, hi)
    f05_roll, a_roll, best_roll = optimise_alpha(p_roll, valid_idx, timestamps, labels, n_points, lo, hi)

    winner = "fixed" if best_fixed >= best_roll else "rolling"
    np.savez(ALPHA_CHOICE, grid=GRID, f05_fixed=f05_fixed, f05_rolling=f05_roll,
             alpha_fixed=a_fixed, alpha_rolling=a_roll,
             best_fixed=best_fixed, best_rolling=best_roll, winner=winner,
             budget_alpha=BUDGET_ALPHA)
    print(f"alpha choice cached -> {ALPHA_CHOICE}")
    return {"thirds": thirds, "normal": normal, "bounds": bounds, "valid_idx": valid_idx,
            "p_fixed": p_fixed, "p_roll": p_roll, "timestamps": timestamps,
            "labels": labels, "n_points": n_points, "lo": lo, "hi": hi,
            "f05_fixed": f05_fixed, "a_fixed": a_fixed, "best_fixed": best_fixed,
            "f05_roll": f05_roll, "a_roll": a_roll, "best_roll": best_roll, "winner": winner}


# SHORT EXPLANATION: the "did it work?" check. Budget alpha gives ~alpha false-positive rate
# on validation normals; alpha* does no worse than the budget alpha on F0.5; and the 3-way
# band (anomaly / abstain / normal) produces non-empty, sensible counts.
def verify(s: dict) -> None:
    """Success-test for Phase 4."""
    thirds, normal, valid_idx = s["thirds"], s["normal"], s["valid_idx"]
    p_fixed, p_roll = s["p_fixed"], s["p_roll"]

    # (a) budget alpha -> FP rate on validation normals ~ BUDGET_ALPHA (aggregate).
    normal_valid = normal[valid_idx]
    fp_fixed = float(np.mean(p_fixed[normal_valid] < BUDGET_ALPHA))
    fp_roll = float(np.mean(p_roll[normal_valid] < BUDGET_ALPHA))

    # (b) alpha* does not hurt F0.5 vs the budget alpha (both on validation).
    f05_budget_fixed = f05_at_alpha(p_fixed, valid_idx, BUDGET_ALPHA, s["timestamps"],
                                    s["labels"], s["n_points"], s["lo"], s["hi"])

    # (c) 3-way band on validation (winner variant): non-empty categories.
    p_win = p_fixed if s["winner"] == "fixed" else p_roll
    a_low = s["a_fixed"] if s["winner"] == "fixed" else s["a_roll"]
    a_high = max(BUDGET_ALPHA, 10 * a_low)
    n = len(p_win)
    anom = int(np.sum(p_win < a_low))
    abst = int(np.sum((p_win >= a_low) & (p_win < a_high)))
    norm = int(np.sum(p_win >= a_high))

    print("\n=== Phase 4 success-test ===")
    print(f"  (a) budget alpha={BUDGET_ALPHA} FP rate on valid normals: "
          f"fixed={fp_fixed:.4f}  rolling={fp_roll:.4f}  (target ~{BUDGET_ALPHA})")
    print(f"  (b) F0.5 on validation:")
    print(f"        fixed   : alpha*={s['a_fixed']:.2e} -> F0.5={s['best_fixed']:.4f}  "
          f"(vs budget alpha F0.5={f05_budget_fixed:.4f})")
    print(f"        rolling : alpha*={s['a_roll']:.2e} -> F0.5={s['best_roll']:.4f}")
    print(f"      winner (better validation F0.5): {s['winner'].upper()}")
    print(f"  (c) 3-way band (winner, a_low={a_low:.2e}, a_high={a_high:.2e}):")
    print(f"        anomaly={anom} ({anom/n:.2%})  abstain={abst} ({abst/n:.2%})  "
          f"normal={norm} ({norm/n:.2%})")

    assert s["best_fixed"] >= f05_budget_fixed - 1e-9, "alpha* worse than budget alpha (fixed)"
    assert anom > 0 and abst > 0 and norm > 0, "a 3-way category is empty"
    print("  -> alpha* >= budget-alpha F0.5, and 3 categories non-empty  OK")


# SHORT EXPLANATION: tune alpha, then verify.
def main() -> None:
    s = build()
    verify(s)


if __name__ == "__main__":
    main()
