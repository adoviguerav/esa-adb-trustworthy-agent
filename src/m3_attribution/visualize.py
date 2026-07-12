#!/usr/bin/env python3
"""M3 · [7] Visualise one event: channel x time contribution heatmap + ranking bar.

Makes the attribution legible. Recomputes PER-WINDOW contribution over the event span
(m3_events.json only stored the sum), draws a channel x time heatmap (which channels are
hot, and when), and a horizontal ranking bar with the ESA ground-truth channels marked
so figure and truth can be compared at a glance.

Output: docs/m3_attribution_example.png
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import matplotlib
if "ipykernel" not in sys.modules:  # headless CLI only: switching inside a notebook
    matplotlib.use("Agg")           # would silently kill plt.show() for later cells
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from m2_uncertainty.scores import load_test_channels  # noqa: E402
from m3_attribution.attribute import attribute_many  # noqa: E402
from m3_attribution.evaluate import load_channel_truth, true_channels  # noqa: E402

EVENTS_JSON = config.CACHE_DIR / "m3_events.json"
BASELINE_NPY = config.CACHE_DIR / "m3_baseline.npy"
MODEL_PKL = config.CACHE_DIR / "model.pkl"
OUT_PNG = config.REPO / "docs" / "m3_attribution_example.png"
WS = config.WINDOW_SIZE
CH_LABELS = [c.split("_")[1] for c in config.TARGET_CHANNELS]  # "18".."28"


# SHORT EXPLANATION: pick a representative event -- confident, short enough to read, and
# ideally showing a coupled pair (channels sharing a physical unit) for the story.
def choose_event(events: list[dict]) -> dict:
    """Prefer a short, coupled event; fall back to the shortest one."""
    coupled = [e for e in events
               if len({"channel_21", "channel_22", "channel_23", "channel_24"}
                      .intersection(c for c, p in e["ranking"][:3] if p >= 10)) >= 2]
    pool = coupled or events
    return min(pool, key=lambda e: e["last_window"] - e["first_window"])


# SHORT EXPLANATION: per-window contribution (n_win, 11) over the event's contiguous
# window range -- the temporal profile behind the event's summed ranking.
def event_contrib_matrix(ev: dict, data: np.ndarray, clf, baseline: np.ndarray) -> np.ndarray:
    """Attribute every window in [first_window .. last_window]; returns (n_win, 11)."""
    lo, hi = ev["first_window"], ev["last_window"]
    idx = np.arange(lo, hi + 1)
    win = np.stack([data[i : i + WS] for i in idx]).transpose(0, 2, 1).reshape(len(idx), -1)
    return attribute_many(win, clf, baseline)  # (n_win, 11)


# SHORT EXPLANATION: draw the two-panel figure and save it.
def render(ev: dict, contrib: np.ndarray, truth_set: set[int]) -> None:
    """Heatmap (channel x window) + ranking bar with truth channels marked."""
    fig, (axh, axb) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [3, 1]})

    # Panel 1: channel x time heatmap of contribution.
    im = axh.imshow(contrib.T, aspect="auto", cmap="magma", origin="lower")
    axh.set_yticks(range(len(CH_LABELS)))
    axh.set_yticklabels([f"ch {c}" for c in CH_LABELS])
    axh.set_xlabel("window (time ->)")
    axh.set_title(f"Event #{ev['event_id']} - per-channel contribution over time "
                  f"({ev['duration_sec']:.0f}s, {ev['n_windows']} flagged windows)")
    fig.colorbar(im, ax=axh, label="contribution (rarity drop)")

    # Panel 2: summed ranking; true culprits (ESA) in colour, others greyed.
    ranking = ev["ranking"]
    names = [c.split("_")[1] for c, _ in ranking]
    pcts = [p for _, p in ranking]
    idx_of = {c: i for i, c in enumerate(config.TARGET_CHANNELS)}
    colours = ["#d62728" if idx_of[c] in truth_set else "#bbbbbb" for c, _ in ranking]
    y = range(len(names))
    axb.barh(list(y), pcts, color=colours)
    axb.set_yticks(list(y))
    axb.set_yticklabels([f"ch {n}" for n in names])
    axb.invert_yaxis()
    axb.set_xlabel("attribution %")
    axb.set_title("ranking (red = true culprit, ESA)")

    fig.tight_layout()
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=120)
    plt.close(fig)


# SHORT EXPLANATION: choose an event, compute its contribution matrix, render the figure.
def build() -> dict:
    """Pick a representative event and render its attribution figure."""
    events = json.loads(EVENTS_JSON.read_text())
    with open(MODEL_PKL, "rb") as f:
        clf = pickle.load(f)
    baseline = np.load(BASELINE_NPY)
    data = load_test_channels()
    truth = load_channel_truth()

    ev = choose_event(events)
    contrib = event_contrib_matrix(ev, data, clf, baseline)
    tset = true_channels(ev, truth)
    render(ev, contrib, tset)
    return {"event": ev, "contrib": contrib, "truth": tset}


# SHORT EXPLANATION: success-test -- the PNG exists and is non-trivial, and the hottest
# channel in the heatmap matches the #1 of the summed ranking (figure agrees with data).
def verify(res: dict) -> None:
    """Success-test for M3 Phase 7."""
    ev, contrib = res["event"], res["contrib"]
    assert OUT_PNG.exists() and OUT_PNG.stat().st_size > 10_000, "figure not written / too small"
    hottest = int(np.argmax(contrib.clip(min=0).sum(axis=0)))  # channel with most total contribution
    top_name = ev["ranking"][0][0]
    assert config.TARGET_CHANNELS[hottest] == top_name, (
        f"heatmap hottest ({config.TARGET_CHANNELS[hottest]}) != ranking #1 ({top_name})"
    )
    print("\n=== M3 Phase 7 success-test ===")
    print(f"  figure written   : {OUT_PNG}  ({OUT_PNG.stat().st_size//1000} KB)  OK")
    print(f"  event shown      : #{ev['event_id']} ({ev['duration_sec']:.0f}s)")
    print(f"  hottest == #1    : channel_{CH_LABELS[hottest]} matches ranking top  OK")
    print(f"  true culprits    : {sorted(config.TARGET_CHANNELS[i].split('_')[1] for i in res['truth'])}")


def main() -> None:
    res = build()
    verify(res)


if __name__ == "__main__":
    main()
