#!/usr/bin/env python3
"""M3 · [3] Aggregate flagged windows into events (the window->event bridge).

M2 marks WINDOWS (p_test < alpha*). A real anomaly lights many contiguous windows
(16/17 overlap). This module groups contiguous marked windows into EVENTS, attributes
each event (sum of its windows' per-channel contributions), and dates it (start/end/
duration from timestamps). Output feeds Phase 5 (context for the LLM).

Everything downstream of here is event-wise (the operator, ESA's metric, the LLM).
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels  # noqa: E402
from m2_uncertainty.split import load_timestamps  # noqa: E402
from attribute import attribute_many  # noqa: E402  same-package engine

SPLIT_NPZ = config.CACHE_DIR / "split.npz"
P_TEST = config.CACHE_DIR / "p_test.npy"
ALPHA_CHOICE = config.CACHE_DIR / "alpha_choice.npz"
SCORES_CONTINUOUS = config.CACHE_DIR / "scores_continuous.npy"
MODEL_PKL = config.CACHE_DIR / "model.pkl"
BASELINE_NPY = config.CACHE_DIR / "m3_baseline.npy"
EVENTS_JSON = config.CACHE_DIR / "m3_events.json"

WS = config.WINDOW_SIZE  # 17
HALF = WS // 2  # 8
# Merge marked windows if index gap <= this (risk #5: configurable). Chosen with data:
# gap=100 (~30 min at ~18s/window) yields 120 predicted events == 120 labeled events in
# third 3 (1:1 alignment). Smaller gaps over-fragment the long real anomalies (median 34 min).
DEFAULT_GAP = 100


# SHORT EXPLANATION: which third-3 windows M2 flagged, expressed as GLOBAL window indices.
def marked_global_indices() -> tuple[np.ndarray, np.ndarray]:
    """Return (global window indices flagged in third 3, their p-values), time-ordered."""
    sp = np.load(SPLIT_NPZ)
    ac = np.load(ALPHA_CHOICE)
    alpha = float(ac[f"alpha_{str(ac['winner'])}"])  # winner='fixed' -> alpha_fixed = 2e-5
    p_test = np.load(P_TEST)  # (n_third3,), aligned to third-3 windows in order
    w3_idx = np.where(sp["window_third"] == 2)[0]  # global indices of third-3 windows
    assert len(w3_idx) == len(p_test), f"third-3 count {len(w3_idx)} != p_test {len(p_test)}"
    local = np.where(p_test < alpha)[0]
    return w3_idx[local], p_test[local]


# SHORT EXPLANATION: build ONLY the flagged windows (channel-major, 187), not all 3M.
# Guarded against M1: their unperturbed score must equal M1's cached score (risk #1).
def build_marked_windows(data: np.ndarray, marked_global: np.ndarray, clf) -> np.ndarray:
    """Flattened channel-major windows (m, 187) for the flagged global indices."""
    win = np.stack([data[i : i + WS] for i in marked_global])  # (m, 17, 11) time x channel
    win = win.transpose(0, 2, 1).reshape(len(marked_global), -1)  # (m, 187) channel-major
    m1 = np.load(SCORES_CONTINUOUS)[marked_global]
    assert np.allclose(clf.decision_function(win), m1, atol=1e-9), "channel-major mismatch (risk #1)"
    return win


# SHORT EXPLANATION: split a sorted list of marked window indices into events -- a new
# event starts whenever the gap to the previous marked window exceeds `gap`.
def group_events(marked_global: np.ndarray, gap: int) -> list[np.ndarray]:
    """List of arrays; each array holds the global window indices of one event."""
    if len(marked_global) == 0:
        return []
    order = np.argsort(marked_global)
    s = marked_global[order]
    cuts = np.where(np.diff(s) > gap)[0] + 1
    return np.split(s, cuts)


# SHORT EXPLANATION: assemble one event record: time span, duration, p-values (for M2
# confidence later), and per-channel contribution summed over the event's windows.
def make_event(event_id: int, win_idx: np.ndarray, contrib_rows: np.ndarray,
               p_rows: np.ndarray, score_rows: np.ndarray, ts: pd.Series) -> dict:
    """Grounded per-event summary (dict), ready to serialise."""
    first_pt, last_pt = int(win_idx.min()), int(win_idx.max()) + WS - 1
    start, end = ts.iloc[first_pt], ts.iloc[last_pt]
    contrib = contrib_rows.sum(axis=0)  # (11,) summed over the event's windows
    pos = contrib.clip(min=0)
    total = pos.sum()
    ranking = sorted(
        ((config.TARGET_CHANNELS[c], float(100 * pos[c] / total) if total > 0 else 0.0)
         for c in range(len(contrib))),
        key=lambda x: x[1], reverse=True,
    )
    return {
        "event_id": event_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_sec": float((end - start).total_seconds()),
        "n_windows": int(len(win_idx)),
        "first_window": first_pt,
        "last_window": int(win_idx.max()),
        "min_p": float(p_rows.min()),
        "mean_p": float(p_rows.mean()),
        # raw M1 score = DEGREE of anomaly. All marked windows share the same p-floor
        # (alpha* sits there, F0.5 -> precision), so p can't grade severity; the score can.
        "intensity_mean": float(score_rows.mean()),
        "intensity_peak": float(score_rows.max()),
        "contrib": {config.TARGET_CHANNELS[c]: float(contrib[c]) for c in range(len(contrib))},
        "ranking": ranking,
    }


# SHORT EXPLANATION: real labeled events with start AND end (load_events drops end),
# on our channels and the counted categories -- used to check predicted<->truth overlap.
def load_labeled_events() -> pd.DataFrame:
    """Labeled events: one row per ID with [StartTime, EndTime] on target channels."""
    lab = pd.read_csv(config.LABELS_CSV, parse_dates=["StartTime", "EndTime"])
    for col in ("StartTime", "EndTime"):
        lab[col] = lab[col].apply(lambda t: t.tz_localize(None))
    lab = lab[lab["Channel"].isin(config.TARGET_CHANNELS)]
    types_path = str(config.LABELS_CSV).replace("labels.csv", "anomaly_types.csv")
    types = pd.read_csv(types_path)[["ID", "Category"]]
    lab = lab.merge(types, on="ID", how="left")
    lab = lab[lab["Category"].isin(config.SELECT_LABELS["Category"])]
    return lab.groupby("ID", as_index=False).agg(StartTime=("StartTime", "min"),
                                                 EndTime=("EndTime", "max"))


# SHORT EXPLANATION: how many predicted events overlap at least one real labeled event
# (in time). This is the sample size available to validate attribution in Phase 6.
def count_overlaps(events: list[dict], labeled: pd.DataFrame) -> int:
    """Predicted events that intersect any labeled [StartTime, EndTime]."""
    S = labeled["StartTime"].to_numpy()
    E = labeled["EndTime"].to_numpy()
    n = 0
    for ev in events:
        ps, pe = np.datetime64(ev["start"]), np.datetime64(ev["end"])
        if np.any((ps <= E) & (pe >= S)):
            n += 1
    return n


# SHORT EXPLANATION: build all events, attribute them, cache to JSON.
def build(gap: int = DEFAULT_GAP) -> list[dict]:
    """Group -> attribute -> date every event; cache m3_events.json; return the list."""
    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    baseline = np.load(BASELINE_NPY)
    data = load_test_channels()
    ts = load_timestamps()

    marked_global, p_marked = marked_global_indices()
    win = build_marked_windows(data, marked_global, clf)
    contrib_all = attribute_many(win, clf, baseline)  # (m, 11), 12 scoring calls
    scores_all = np.load(SCORES_CONTINUOUS)[marked_global]  # raw M1 score per marked window

    # position of each marked global index within the flagged arrays, for per-event slicing
    pos_of = {int(g): i for i, g in enumerate(marked_global)}
    groups = group_events(marked_global, gap)

    events = []
    for eid, g in enumerate(groups):
        rows = np.array([pos_of[int(x)] for x in g])
        events.append(make_event(eid, g, contrib_all[rows], p_marked[rows], scores_all[rows], ts))

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_JSON.write_text(json.dumps(events, indent=2))
    print(f"Events cached -> {EVENTS_JSON}  (n={len(events)}, gap={gap})")
    return events


# SHORT EXPLANATION: success-test -- sane event count, non-empty ranking + positive
# duration each, and the early sample check (predicted<->labeled overlaps for Phase 6).
def verify(events: list[dict], gap: int) -> None:
    """Success-test for M3 Phase 3."""
    marked_global, _ = marked_global_indices()

    # (a) sane count: tens..low-thousands, not 1, not millions.
    n = len(events)
    assert 1 < n < 100000, f"event count {n} looks wrong"

    # (b) each event has a non-empty ranking and positive duration.
    for ev in events:
        assert len(ev["ranking"]) == len(config.TARGET_CHANNELS), "ranking wrong size"
        assert ev["duration_sec"] > 0, f"event {ev['event_id']} has non-positive duration"

    # (c) gap sensitivity: report event count at several gaps (risk #5).
    sens = {g: len(group_events(marked_global, g)) for g in (1, 3, 5, 10, 25)}

    # (d) EARLY SAMPLE CHECK (risk #4): predicted<->labeled overlaps available to Phase 6.
    labeled = load_labeled_events()
    overlaps = count_overlaps(events, labeled)

    print("\n=== M3 Phase 3 success-test ===")
    print(f"  (a) event count      : {n} (gap={gap})  OK")
    print(f"  (b) ranking+duration : all {n} events non-empty ranking, duration>0  OK")
    print(f"  (c) gap sensitivity  : {sens}")
    print(f"  (d) sample for F6    : {overlaps} predicted events overlap a labeled event")
    print(f"      marked windows   : {len(marked_global)}  ({len(marked_global)/1020793:.2%} of third 3)")
    if overlaps < 10:
        print("      WARNING: <10 overlaps -> hit@1 will be noisy; EXTEND to third 2 in Phase 6.")
    # a couple of example events, most-confident first (min_p ascending)
    top = sorted(events, key=lambda e: e["min_p"])[:3]
    print("      most-confident events (min_p asc):")
    for ev in top:
        chans = ", ".join(f"{c}({p:.0f}%)" for c, p in ev["ranking"][:3] if p > 0)
        print(f"        #{ev['event_id']}: {ev['n_windows']}w  {ev['duration_sec']:.0f}s  "
              f"min_p={ev['min_p']:.2e}  [{chans}]")


def main() -> None:
    gap = DEFAULT_GAP
    events = build(gap)
    verify(events, gap)


if __name__ == "__main__":
    main()
