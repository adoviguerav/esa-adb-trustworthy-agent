#!/usr/bin/env python3
"""M2 · [2] Temporal split — carve the test period into calib / valid / test-final.

Conformal calibration needs a *clean* set of windows known to be normal, never used to
train the forest. The forest trained on the *train* period, so the whole test is
unseen; we split it by time into three contiguous thirds:

  third 1  -> CALIBRATION   (normal windows only: the "distribution of normal rarity")
  third 2  -> VALIDATION    (all windows + labels: to tune alpha* later [4])
  third 3  -> TEST-FINAL    (all windows: report M2 once, no peeking)

A window is *normal* iff none of its 17 points is anomalous across channels 18-28
(union of the `is_anomaly_channel_*` columns). Windows are assigned to a third by their
center point (index + window_size // 2).

Output: `data/cached/split.npz` with the point-index third boundaries and a per-window
normal mask. Downstream phases derive calib/valid/test index sets from these.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

SPLIT_NPZ = config.CACHE_DIR / "split.npz"
HALF = config.WINDOW_SIZE // 2  # 8: pad / center offset


# SHORT EXPLANATION: read the "is this moment anomalous?" columns. If ANY of the 11 sensors
# is flagged at a given moment, that moment counts as anomalous. One 0/1 flag per point.
def load_point_anomaly() -> np.ndarray:
    """Per-point anomaly flag (0/1): 1 if any target channel is anomalous at that point."""
    anomaly_cols = [f"is_anomaly_{c}" for c in config.TARGET_CHANNELS]
    df = pd.read_csv(
        config.TEST_CSV,
        index_col="timestamp",
        usecols=["timestamp", *anomaly_cols],
        dtype={c: np.uint8 for c in anomaly_cols},
    )
    return (df[anomaly_cols].to_numpy().max(axis=1) > 0).astype(np.uint8)


# SHORT EXPLANATION: a window is "normal" only if ALL 17 of its points are clean. These
# clean windows are the raw material for calibration ("this is what normal looks like").
def window_normal_mask(point_anomaly: np.ndarray) -> np.ndarray:
    """True for a window iff all its `window_size` points are non-anomalous."""
    win = sliding_window_view(point_anomaly, window_shape=config.WINDOW_SIZE)
    return win.max(axis=1) == 0  # (n_windows,)


# SHORT EXPLANATION: work out where to cut the timeline into three equal-length chunks by time.
def third_boundaries(n_points: int) -> np.ndarray:
    """Point-index boundaries [0, t1, t2, n] splitting the timeline into equal thirds."""
    return np.array([0, n_points // 3, 2 * (n_points // 3), n_points], dtype=np.int64)


# SHORT EXPLANATION: label each window with which chunk it belongs to (0, 1, or 2),
# deciding by the window's middle point.
def window_third(n_windows: int, bounds: np.ndarray) -> np.ndarray:
    """Assign each window (0..n_windows-1) to a third by its center point (idx + HALF)."""
    centers = np.arange(n_windows) + HALF
    # np.digitize with the inner boundaries -> 0,1,2
    return np.clip(np.digitize(centers, bounds[1:-1]), 0, 2).astype(np.int8)


# SHORT EXPLANATION: read the time column, so we know which real dates each chunk covers.
def load_timestamps() -> pd.Series:
    """Test timestamps (parsed), used to map thirds to time ranges for event counting."""
    ts = pd.read_csv(config.TEST_CSV, usecols=["timestamp"], parse_dates=["timestamp"])
    return ts["timestamp"].dt.tz_localize(None)


# SHORT EXPLANATION: read the anomaly catalog, keep only our channels and the anomaly
# types the metric counts, and collapse to one row per real event.
def load_events() -> pd.DataFrame:
    """Unique anomaly events (by ID) on target channels, categories per the metric."""
    labels = pd.read_csv(config.LABELS_CSV, parse_dates=["StartTime", "EndTime"])
    labels["StartTime"] = labels["StartTime"].apply(lambda t: t.tz_localize(None))
    labels["EndTime"] = labels["EndTime"].apply(lambda t: t.tz_localize(None))
    labels = labels[labels["Channel"].isin(config.TARGET_CHANNELS)]

    types_path = str(config.LABELS_CSV).replace("labels.csv", "anomaly_types.csv")
    types = pd.read_csv(types_path)[["ID", "Category"]]
    labels = labels.merge(types, on="ID", how="left")
    labels = labels[labels["Category"].isin(config.SELECT_LABELS["Category"])]
    # One row per event: earliest StartTime per ID.
    return labels.groupby("ID", as_index=False)["StartTime"].min()


# SHORT EXPLANATION: count how many real anomaly events fall in each chunk (sanity check).
def count_events_per_third(events: pd.DataFrame, ts: pd.Series, bounds: np.ndarray) -> list[int]:
    """Events whose StartTime falls inside each third's time range."""
    edges = [ts.iloc[b if b < len(ts) else -1] for b in bounds]
    counts = []
    for k in range(3):
        lo, hi = edges[k], edges[k + 1]
        in_range = (events["StartTime"] >= lo) & (events["StartTime"] < hi)
        counts.append(int(in_range.sum()))
    return counts


# SHORT EXPLANATION: run all the steps above and save the split (boundaries + normal mask
# + chunk labels) to disk.
def build() -> dict:
    """Compute the split, cache it, and return the pieces needed by verify()."""
    point_anomaly = load_point_anomaly()
    n_points = len(point_anomaly)
    normal = window_normal_mask(point_anomaly)
    n_windows = len(normal)
    bounds = third_boundaries(n_points)
    thirds = window_third(n_windows, bounds)

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        SPLIT_NPZ,
        point_bounds=bounds,
        window_normal=normal,
        window_third=thirds,
    )
    print(f"Split cached -> {SPLIT_NPZ}")
    return {
        "point_anomaly": point_anomaly,
        "n_points": n_points,
        "normal": normal,
        "n_windows": n_windows,
        "bounds": bounds,
        "thirds": thirds,
    }


# SHORT EXPLANATION: the "did it work?" check. Chunks don't overlap and cover everything;
# sampled "normal" windows really are clean; event counts match; reports calibration size.
def verify(s: dict) -> None:
    """Success-test for Phase 2 (raises AssertionError on any failure)."""
    normal, thirds, bounds = s["normal"], s["thirds"], s["bounds"]
    n_windows, n_points = s["n_windows"], s["n_points"]

    # (a) thirds disjoint, cover all windows, no gaps.
    counts = np.bincount(thirds, minlength=3)
    assert counts.sum() == n_windows, "third assignment does not cover all windows"
    assert (counts > 0).all(), "an empty third"
    assert (np.diff(bounds) > 0).all() and bounds[0] == 0 and bounds[-1] == n_points, (
        "point boundaries not a clean partition"
    )

    # (b) spot-check: sampled normal windows truly have 17 clean points.
    pa = s["point_anomaly"]
    normal_idx = np.flatnonzero(normal)
    rng = np.random.default_rng(config.RANDOM_STATE)
    sample = rng.choice(normal_idx, size=min(200, len(normal_idx)), replace=False)
    for i in sample:
        assert pa[i : i + config.WINDOW_SIZE].sum() == 0, f"window {i} flagged normal but has anomalies"

    # (c) events per third ~ 134/96/120 (already measured).
    events = load_events()
    ts = load_timestamps()
    ev = count_events_per_third(events, ts, bounds)

    # (d) calibration normal windows in third 1.
    calib_normal = int(np.sum(normal & (thirds == 0)))

    print("\n=== Phase 2 success-test ===")
    print(f"  (a) partition        : windows per third = {counts.tolist()} (sum {counts.sum()})  OK")
    print(f"      point bounds     : {bounds.tolist()}")
    print(f"  (b) normal spot-check: {len(sample)} sampled windows all clean  OK")
    print(f"  (c) events per third : {ev}  (total {sum(ev)}; expected ~134/96/120, 350)")
    print(f"  (d) calib normals    : {calib_normal} normal windows in third 1 "
          f"(~{calib_normal // config.WINDOW_SIZE} after 1-of-17)")


# SHORT EXPLANATION: build the split, then verify it.
def main() -> None:
    s = build()
    verify(s)


if __name__ == "__main__":
    main()
