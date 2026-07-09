#!/usr/bin/env python3
"""M3 · [6] Validate attribution against per-channel ground truth (strong success-test).

For every predicted event that overlaps the truth, the real culprits are the channels
whose `is_anomaly_channel_c` flag is set anywhere in the event's span. We rank channels
three ways and score each against that truth:

  - perturbation (ours)  : channels by summed contribution.
  - magnitude (baseline) : channels by max |value - baseline| over the span.
  - random (baseline)    : analytic expectation = |truth| / 11.

Metrics: hit@1 (top-1 among the true culprits) and precision@3. Criterion fixed BEFORE
looking (anti-peeking): perturbation must beat RANDOM (hard); perturbation vs magnitude
is reported honestly whichever way it falls. Events with no true channel in span are not
evaluable -> counted aside, excluded from the score (risk #6).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels  # noqa: E402

EVENTS_JSON = config.CACHE_DIR / "m3_events.json"
BASELINE_NPY = config.CACHE_DIR / "m3_baseline.npy"
WS = config.WINDOW_SIZE
K = 3  # precision@K
INVOLVEMENT_THR = 0.5  # a channel is a "true culprit" if anomalous for >= this fraction of the span


# SHORT EXPLANATION: load the 11 per-channel truth columns as an (n_points, 11) boolean
# array (value > 0 = anomalous; tercio-3 uses value 2 = "Rare Event", an anomaly per ESA).
def load_channel_truth() -> np.ndarray:
    """Per-point per-channel anomaly flag (bool), shape (n_points, 11)."""
    cols = [f"is_anomaly_channel_{c.split('_')[1]}" for c in config.TARGET_CHANNELS]
    df = pd.read_csv(config.TEST_CSV, usecols=cols)
    return df[cols].to_numpy() > 0


# SHORT EXPLANATION: the true culprits of an event = channels anomalous for at least
# INVOLVEMENT_THR of the span. "Any point" over-counts on long events (transient
# propagation floods every channel); requiring sustained involvement keeps the real ones.
def true_channels(ev: dict, truth: np.ndarray) -> set[int]:
    """Indices (0..10) of channels anomalous for >= INVOLVEMENT_THR of the event span."""
    lo, hi = ev["first_window"], ev["last_window"] + WS - 1
    involvement = truth[lo : hi + 1].mean(axis=0)  # (11,) fraction of span each channel is anomalous
    return set(np.where(involvement >= INVOLVEMENT_THR)[0])


# SHORT EXPLANATION: our attribution ranking -> channel indices, best first.
def rank_perturbation(ev: dict) -> list[int]:
    """Channel indices ordered by summed contribution (from the event ranking)."""
    name_to_idx = {c: i for i, c in enumerate(config.TARGET_CHANNELS)}
    return [name_to_idx[ch] for ch, _ in ev["ranking"]]


# SHORT EXPLANATION: magnitude baseline -> channels by biggest deviation from baseline
# over the event span. Ignores the detector entirely (the naive alternative).
def rank_magnitude(ev: dict, data: np.ndarray, baseline: np.ndarray) -> list[int]:
    """Channel indices ordered by max |value - baseline| over the event span."""
    lo, hi = ev["first_window"], ev["last_window"] + WS - 1
    dev = np.abs(data[lo : hi + 1] - baseline).max(axis=0)  # (11,)
    return list(np.argsort(dev)[::-1])


# SHORT EXPLANATION: hit@1 (is the #1 pick a real culprit) and precision@K for a ranking.
def score_ranking(ranking: list[int], truth: set[int]) -> tuple[float, float]:
    """Return (hit@1, precision@K) of a channel ranking against the true set."""
    hit1 = 1.0 if ranking[0] in truth else 0.0
    topk = ranking[:K]
    preck = len(set(topk) & truth) / K
    return hit1, preck


# SHORT EXPLANATION: run the comparison across all evaluable events and report.
def build() -> dict:
    """Score perturbation vs magnitude vs random over evaluable events."""
    events = json.loads(EVENTS_JSON.read_text())
    truth = load_channel_truth()
    data = load_test_channels()
    baseline = np.load(BASELINE_NPY)

    rows = {"pert": [], "mag": [], "rand": []}
    n_eval, n_skip = 0, 0
    for ev in events:
        tset = true_channels(ev, truth)
        if not tset:  # no per-channel truth in span -> not evaluable (risk #6)
            n_skip += 1
            continue
        n_eval += 1
        rows["pert"].append(score_ranking(rank_perturbation(ev), tset))
        rows["mag"].append(score_ranking(rank_magnitude(ev, data, baseline), tset))
        frac = len(tset) / len(config.TARGET_CHANNELS)
        rows["rand"].append((frac, frac))  # E[hit@1] = E[precision@K] = |truth|/11

    def mean(key):
        a = np.array(rows[key])
        return float(a[:, 0].mean()), float(a[:, 1].mean())

    return {
        "n_evaluable": n_eval, "n_skipped": n_skip,
        "perturbation": mean("pert"), "magnitude": mean("mag"), "random": mean("rand"),
    }


# SHORT EXPLANATION: success-test -- perturbation MUST beat random (hard); perturbation
# vs magnitude is reported honestly whichever way it lands.
def verify(res: dict) -> None:
    """Success-test for M3 Phase 6."""
    p1, pk = res["perturbation"]
    m1, mk = res["magnitude"]
    r1, rk = res["random"]

    # HARD: attribution must beat chance, else it is meaningless.
    assert p1 > r1, f"perturbation hit@1 {p1:.3f} does not beat random {r1:.3f} -> broken"

    beats_mag = p1 > m1
    verdict = "perturbation WINS" if beats_mag else "magnitude ties/wins -> reported honestly"

    print("\n=== M3 Phase 6 success-test (attribution validity) ===")
    print(f"  evaluable events : {res['n_evaluable']}  (skipped, no channel truth: {res['n_skipped']})")
    print(f"  {'method':<13} {'hit@1':>8} {'prec@3':>8}")
    print(f"  {'perturbation':<13} {p1:>8.3f} {pk:>8.3f}")
    print(f"  {'magnitude':<13} {m1:>8.3f} {mk:>8.3f}")
    print(f"  {'random (E)':<13} {r1:>8.3f} {rk:>8.3f}")
    print(f"  HARD  perturbation > random : {p1:.3f} > {r1:.3f}  OK")
    print(f"  vs magnitude : {verdict}")


def main() -> None:
    res = build()
    verify(res)


if __name__ == "__main__":
    main()
