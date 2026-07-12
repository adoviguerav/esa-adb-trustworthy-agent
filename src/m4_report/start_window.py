"""[4 · start-flag] Offline builder: cache the FIRST flagged window's attribution per event.

The START alert may only describe what is visible the moment the event OPENS: its first
flagged window. M3 cached per-EVENT attribution (aggregated over ALL the event's windows) --
using that at start time would leak the event's future into the alert. This builder
re-derives the events EXACTLY like M3 (same flagged windows, same gap, same grouping code,
imported -- never re-implemented), takes each event's first window, attributes it with the
real model, and caches a tiny JSON. The demo then needs neither the model (48 MB) nor the
raw telemetry (GB): `alert.py` reads only this file.

Run once locally (needs model.pkl + test CSV). Output: data/cached/m4_start_windows.json.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

_SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SRC))  # src/ on path
sys.path.insert(0, str(_SRC / "m3_attribution"))  # M3 modules import each other by plain name
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels  # noqa: E402
from m2_uncertainty.split import load_timestamps  # noqa: E402
from aggregate import (  # noqa: E402  reuse M3's engine verbatim (D7 spirit)
    DEFAULT_GAP,
    EVENTS_JSON,
    build_marked_windows,
    group_events,
    marked_global_indices,
)
from attribute import (  # noqa: E402
    BASELINE_NPY,
    MODEL_PKL,
    SCORES_CONTINUOUS,
    attribute_many,
)

START_JSON = config.CACHE_DIR / "m4_start_windows.json"
CALIB_SCORES = config.CACHE_DIR / "calib_scores.npy"  # M2 calibration scores (the "normal" past)

# Intensity label = percentile of the window's raw M1 score vs the calibration distribution.
# Flagged windows sit above ~all of calibration by construction (p < alpha*), so most events
# will read "high" -- that is honest, not a bug: these ARE the rarest windows.
INTENSITY_BINS = ((0.95, "low"), (0.999, "moderate"))  # else "high"


def intensity_label(pct: float) -> str:
    """Bin a percentile-vs-calibration into a qualitative label (fixed, deterministic)."""
    for cut, name in INTENSITY_BINS:
        if pct <= cut:
            return name
    return "high"


# SHORT EXPLANATION: same ranking convention as M3's make_event -- positive contributions
# as % of the positive total -- but computed over ONE window instead of the whole event.
def channel_ranking(contrib: np.ndarray) -> list[list]:
    """[[channel_name, pct], ...] sorted desc; pct = share of positive contribution.
    Lists (not tuples) so the in-memory records survive a JSON round-trip unchanged."""
    pos = contrib.clip(min=0)
    total = pos.sum()
    return sorted(
        ([config.TARGET_CHANNELS[c], float(100 * pos[c] / total) if total > 0 else 0.0]
         for c in range(len(contrib))),
        key=lambda x: x[1], reverse=True,
    )


# SHORT EXPLANATION: regroup the flagged windows into events exactly like M3, keep only
# each event's FIRST window, attribute those 120 windows (one batch, 12 model calls),
# and assemble one small record per event.
def build() -> list[dict]:
    """Build the per-event first-window records and cache them to START_JSON."""
    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    baseline = np.load(BASELINE_NPY)
    data = load_test_channels()
    ts = load_timestamps()
    calib = np.load(CALIB_SCORES)

    marked_global, p_marked = marked_global_indices()
    pos_of = {int(g): i for i, g in enumerate(marked_global)}
    groups = group_events(marked_global, DEFAULT_GAP)
    first_idx = np.array([int(g.min()) for g in groups])

    win = build_marked_windows(data, first_idx, clf)  # channel-major guard vs M1 included
    contrib = attribute_many(win, clf, baseline)  # (n_events, 11)
    scores = np.load(SCORES_CONTINUOUS)[first_idx]

    records = []
    for eid, (fw, c, s) in enumerate(zip(first_idx, contrib, scores)):
        p = float(p_marked[pos_of[int(fw)]])
        pct = float((calib < s).mean())
        records.append({
            "event_id": eid,
            "window_idx": int(fw),
            "t": ts.iloc[int(fw)].isoformat(),
            "score": float(s),                       # raw M1 score of THIS window (degree)
            "p": p,                                  # M2 p-value of THIS window
            "confidence": 1.0 - p,                   # saturates (alpha* floor) -- reported as such
            "intensity_pct_vs_calib": pct,
            "intensity_label": intensity_label(pct),
            "channels": channel_ranking(c),          # from THIS window only (anti-leakage)
        })

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    START_JSON.write_text(json.dumps(records, indent=2))
    print(f"Start-window records cached -> {START_JSON}  (n={len(records)})")
    return records


# SHORT EXPLANATION: the builder's "did it work?". The one invariant that matters: the
# events derived here are THE SAME events M3 cached (same count, same first window, same
# start time) -- otherwise the flag would describe a different segmentation than the brief.
def verify(records: list[dict]) -> None:
    """Success-test for the F4 builder (raises AssertionError on mismatch)."""
    events = json.loads(EVENTS_JSON.read_text())
    assert len(records) == len(events), f"{len(records)} records != {len(events)} M3 events"
    for r, ev in zip(records, events):
        assert r["event_id"] == ev["event_id"], "event order mismatch"
        assert r["window_idx"] == ev["first_window"], (
            f"event {r['event_id']}: first window {r['window_idx']} != M3 {ev['first_window']}"
        )
        assert r["t"] == ev["start"], f"event {r['event_id']}: start time mismatch"
        assert r["channels"][0][1] > 0, f"event {r['event_id']}: no positive contribution"

    round_trip = json.loads(START_JSON.read_text())
    assert round_trip == records, "JSON round-trip changed the records"

    labels = sorted({r["intensity_label"] for r in records})
    print("\n=== M4 Phase 4 (builder) success-test ===")
    print(f"  (a) same events as M3 : {len(records)} events, first_window + start match  OK")
    print(f"  (b) round-trip JSON   : OK")
    print(f"  (c) intensity labels  : {labels}")
    sample = records[33]
    top = ", ".join(f"{ch}({pct:.1f}%)" for ch, pct in sample["channels"][:3])
    print(f"  sample event 33       : t={sample['t']}  score={sample['score']:.3f}  top: {top}")


def main() -> None:
    for path in (MODEL_PKL, BASELINE_NPY, EVENTS_JSON, CALIB_SCORES):
        if not path.exists():
            sys.exit(f"Missing prerequisite: {path}")
    verify(build())


if __name__ == "__main__":
    main()
