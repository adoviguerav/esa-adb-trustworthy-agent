"""[4 · start-flag] START alert: deterministic template over the first window's cached facts.

NO LLM, NO RAG, NO model: when the event has just opened, reasoning would be premature and
the downlink budget is tiny -- a fixed template over grounded numbers is the honest tool.
This module reads ONLY `m4_start_windows.json` (built offline by `start_window.py`); it does
not even import M3's event contexts, so the aggregated event attribution (dominant_channels
= future information at start time) CANNOT leak into this alert by construction.

Pure functions: `start_flag(record) -> dict` and `render_flag(flag) -> str`. WHEN they fire
is the orchestrator's job (pipeline.py, F9) -- this module has no notion of time or streaming.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

START_JSON = config.CACHE_DIR / "m4_start_windows.json"

FLAG_PCT_MIN = 10.0   # a channel enters the flag only if it carries >=10% of the window's blame
FLAG_MAX_CH = 3       # downlink budget: at most 3 channels in the one-line alert
MAX_FLAG_BYTES = 160  # hard size budget (SMS-sized) -- asserted over every event


def load_start_windows() -> dict[int, dict]:
    """The cached first-window records, keyed by event_id (the only disk access here)."""
    records = json.loads(START_JSON.read_text())
    return {r["event_id"]: r for r in records}


# SHORT EXPLANATION: pure selection -- pick the flag's facts out of one cached record.
# Channels: those carrying >=10% of THIS window's attribution, capped at 3, never empty.
def start_flag(record: dict) -> dict:
    """Structured facts of the START alert for one event (no I/O, deterministic)."""
    strong = [ch for ch, pct in record["channels"] if pct >= FLAG_PCT_MIN]
    channels = (strong or [record["channels"][0][0]])[:FLAG_MAX_CH]
    return {
        "event_id": record["event_id"],
        "t": record["t"],
        "channels": channels,
        "score": record["score"],
        "intensity_label": record["intensity_label"],
        "p": record["p"],
        "confidence": record["confidence"],
    }


# SHORT EXPLANATION: the template. One fixed line, numbers straight from the flag dict.
# Confidence is never sold as discriminating: below the alpha* floor it reads "saturated".
def render_flag(flag: dict) -> str:
    """One-line START alert (fixed template, <= MAX_FLAG_BYTES)."""
    chs = ",".join(ch.removeprefix("channel_") for ch in flag["channels"])
    conf = ("conf>0.9999 (saturated)" if flag["p"] < 1e-4
            else f"conf={flag['confidence']:.4f}")
    return (f"ANOMALY START t={flag['t']} | ch {chs} | "
            f"intensity {flag['intensity_label']} (score {flag['score']:.3f}) | {conf}")


# SHORT EXPLANATION: F4 success-test. (a) flag windows == M3's first_window (right moment);
# (b) anti-leakage assert of the plan: flag channels come from the FIRST WINDOW's ranking,
# and they visibly DIFFER from the event-aggregated dominant_channels for some events
# (proof the flag is not just copying the event view); (c) every alert fits the byte
# budget; (d) two runs are byte-identical (deterministic).
def main() -> None:
    records = load_start_windows()
    events = json.loads((config.CACHE_DIR / "m3_events.json").read_text())
    contexts = {c["event_id"]: c for c in
                json.loads((config.CACHE_DIR / "m3_event_contexts.json").read_text())}

    # (a) right moment: one flag per event, anchored at M3's first window.
    assert len(records) == len(events)
    for ev in events:
        assert records[ev["event_id"]]["window_idx"] == ev["first_window"]

    # (b) anti-leakage: channels ⊆ first-window ranking; top-1 differs from the event's
    # aggregated view for at least one event (here it MUST diverge somewhere: if it never
    # did, the per-window cache would be indistinguishable from the leaky shortcut).
    diverge = 0
    for eid, rec in records.items():
        flag = start_flag(rec)
        allowed = {ch for ch, _ in rec["channels"]}
        assert set(flag["channels"]) <= allowed, f"event {eid}: channel outside first window"
        dom = contexts[eid]["dominant_channels"]
        if dom and flag["channels"][0] != dom[0]:
            diverge += 1
    assert diverge >= 1, "flag top-1 == event top-1 everywhere: first-window source not proven"

    # (c) byte budget + (d) determinism, over ALL events.
    sizes = []
    for rec in records.values():
        line1, line2 = render_flag(start_flag(rec)), render_flag(start_flag(rec))
        assert line1 == line2, "render not deterministic"
        sizes.append(len(line1.encode()))
    assert max(sizes) <= MAX_FLAG_BYTES, f"alert too big: {max(sizes)} bytes"

    print("=== M4 Phase 4 (alert) success-test ===")
    print(f"  (a) right moment   : {len(records)} flags anchored at M3 first_window  OK")
    print(f"  (b) anti-leakage   : channels from first window; top-1 differs from event view "
          f"in {diverge}/{len(records)} events  OK")
    print(f"  (c) size budget    : max {max(sizes)} bytes (limit {MAX_FLAG_BYTES})  OK")
    print(f"  (d) deterministic  : byte-identical on re-render  OK")
    print(f"\n  example (event 33): {render_flag(start_flag(records[33]))}")


if __name__ == "__main__":
    main()
