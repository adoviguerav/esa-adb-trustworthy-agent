"""M3 · attribution tests.

Locks the attribution engine and event aggregation: pure grouping logic (no cache),
the channel-major guard (risk #1), single-extreme dominance, collective blame splitting,
baseline sanity (risk #2), and the strong validity check (perturbation beats random).

Run: pytest tests/test_m3_attribution.py -v
Cached-data tests skip if the M1/M2/M3 cache is missing (run the phase scripts first).
"""
import pickle
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "m3_attribution"))
import config  # noqa: E402
import attribute  # noqa: E402
from aggregate import group_events  # noqa: E402

MODEL = config.CACHE_DIR / "model.pkl"
BASELINE = config.CACHE_DIR / "m3_baseline.npy"
SCORES = config.CACHE_DIR / "scores_continuous.npy"
EVENTS = config.CACHE_DIR / "m3_events.json"
WS = config.WINDOW_SIZE
N_CH = len(config.TARGET_CHANNELS)

cache_ok = MODEL.exists() and BASELINE.exists() and SCORES.exists()
needs_cache = pytest.mark.skipif(not cache_ok, reason="M1/M3 cache missing; run the phase scripts")


@pytest.fixture(scope="module")
def clf():
    with open(MODEL, "rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="module")
def baseline():
    return np.load(BASELINE)


# --- pure logic: no cache needed -------------------------------------------

def test_group_events_splits_on_gap():
    """A gap larger than tolerance splits an event; within tolerance it merges."""
    marked = np.array([1, 2, 3, 20, 21])
    two = group_events(marked, gap=5)     # 20-3 = 17 > 5 -> split
    one = group_events(marked, gap=20)    # 17 <= 20 -> single event
    assert [list(g) for g in two] == [[1, 2, 3], [20, 21]]
    assert [list(g) for g in one] == [[1, 2, 3, 20, 21]]


def test_group_events_empty():
    """No marked windows -> no events."""
    assert group_events(np.array([], dtype=int), gap=5) == []


# --- attribution engine: needs the model + baseline ------------------------

@needs_cache
def test_channel_major_matches_m1(clf):
    """Unperturbed windows reproduce M1's cached scores exactly (risk #1 guard)."""
    from m2_uncertainty.scores import load_test_channels, window_data
    data = load_test_channels()
    windows = window_data(data, WS)
    m1 = np.load(SCORES)
    sample = np.array([0, len(windows) // 2, len(windows) - 1])
    assert np.allclose(clf.decision_function(windows[sample]), m1[sample], atol=1e-9)


@needs_cache
def test_single_extreme_dominates(clf, baseline):
    """A synthetic window with one extreme channel -> that channel tops the ranking."""
    k = 21 - 18
    synth = attribute._baseline_window(baseline).copy()
    synth[k * WS:(k + 1) * WS] = baseline[k] + 10.0
    contrib = attribute.attribute_window(synth, clf, baseline)
    assert int(np.argmax(contrib)) == k


@needs_cache
def test_collective_both_blamed(clf, baseline):
    """Two channels perturbed together -> both receive positive contribution (risk #3)."""
    a, b = 21 - 18, 22 - 18
    coll = attribute._baseline_window(baseline).copy()
    coll[a * WS:(a + 1) * WS] = baseline[a] + 2.0
    coll[b * WS:(b + 1) * WS] = baseline[b] + 2.0
    contrib = attribute.attribute_window(coll, clf, baseline)
    assert contrib[a] > 0 and contrib[b] > 0


@needs_cache
def test_baseline_not_toxic(clf, baseline):
    """An all-normal window is less rare than a planted single-channel anomaly (risk #2)."""
    normal = attribute._baseline_window(baseline)
    anom = normal.copy()
    anom[0:WS] = baseline[0] + 10.0
    assert clf.decision_function(normal[None, :])[0] < clf.decision_function(anom[None, :])[0]


# --- events + validity: needs the full M3 cache ----------------------------

@pytest.mark.skipif(not EVENTS.exists(), reason="m3_events.json missing; run aggregate.py")
def test_events_cached_sane():
    """Every cached event has a full-size ranking and a positive duration."""
    events = json.loads(EVENTS.read_text())
    assert len(events) > 1
    for ev in events:
        assert len(ev["ranking"]) == N_CH
        assert ev["duration_sec"] > 0


@pytest.mark.skipif(not (cache_ok and EVENTS.exists() and config.TEST_CSV.exists()),
                    reason="full M3 cache / test CSV missing")
def test_perturbation_beats_random():
    """The strong success-test: perturbation hit@1 must beat the random expectation."""
    from evaluate import build
    res = build()
    assert res["perturbation"][0] > res["random"][0]
