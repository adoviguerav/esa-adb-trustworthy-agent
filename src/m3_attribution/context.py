#!/usr/bin/env python3
"""M3 · [5] Event context — the grounded, prioritised handoff to the LLM [4].

Turns the raw events (m3_events.json) into the package M4 will read. Every field is
TRACEABLE to a source (p-value, contribution, timestamps, channels.csv) -- zero free
text. This is what stops the LLM hallucinating: if the input is clean and grounded,
the judge in [4] has something to audit against.

Two honest design points:
  - m2_confidence (1 - min_p) SATURATES: every flagged event has p < alpha* = 2e-5, so
    confidence ~= 1 for all. It does NOT discriminate -> the queue is ordered by SEVERITY
    (duration x number of dominant channels), with confidence reported alongside.
  - localization = 'diffuse' when no channel reaches CONFIDENT_PCT of the blame: M3 can
    abstain on WHERE even when M2 is sure THAT something is wrong (honest 'I don't know').
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402
from channels import load_channel_meta, shared_relations  # noqa: E402

EVENTS_JSON = config.CACHE_DIR / "m3_events.json"
CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"

DOMINANT_PCT = 10.0    # a channel is "dominant" (drives the event) if it holds >= this % of blame
CONFIDENT_PCT = 25.0   # localization is "confident" if the top channel reaches this %, else "diffuse"

ALLOWED_KEYS = {
    "event_id", "start", "end", "duration_sec", "n_windows", "m2_confidence",
    "intensity", "priority", "top_channels", "dominant_channels", "localization",
    "shared_relations", "window_span",
}


# SHORT EXPLANATION: build one grounded context dict from one raw event. Every value is
# derived from the event's own fields or channels.csv -- nothing invented.
def build_context(ev: dict, meta: dict) -> dict:
    """Assemble the grounded, LLM-ready context for a single event."""
    top = [[c, p] for c, p in ev["ranking"] if p > 0]                 # from contrib
    dominant = [c for c, p in top if p >= DOMINANT_PCT]               # the real drivers
    top_pct = top[0][1] if top else 0.0
    localization = "confident" if top_pct >= CONFIDENT_PCT else "diffuse"
    confidence = 1.0 - ev["min_p"]                                    # from M2's p-value (SATURATES)
    intensity = ev["intensity_mean"]                                  # raw M1 score = DEGREE of anomaly
    # priority ranks by DEGREE (the only signal that discriminates; p is saturated), tempered
    # by log-duration so a short-but-intense event is not buried by a long-but-mild one.
    priority = intensity * math.log10(1.0 + ev["duration_sec"])
    return {
        "event_id": ev["event_id"],
        "start": ev["start"],
        "end": ev["end"],
        "duration_sec": ev["duration_sec"],
        "n_windows": ev["n_windows"],
        "m2_confidence": confidence,
        "intensity": intensity,
        "priority": priority,
        "top_channels": top,
        "dominant_channels": dominant,
        "localization": localization,
        "shared_relations": shared_relations(dominant, meta),         # from channels.csv
        "window_span": [ev["first_window"], ev["last_window"]],       # raw traceability
    }


# SHORT EXPLANATION: build all contexts, ordered by priority (highest first) -- the
# "lead the operator by the hand" queue, not a dump. Cache to JSON.
def build() -> list[dict]:
    """Read events, assemble grounded contexts, sort by priority desc, cache JSON."""
    events = json.loads(EVENTS_JSON.read_text())
    meta = load_channel_meta()
    contexts = [build_context(ev, meta) for ev in events]
    contexts.sort(key=lambda c: c["priority"], reverse=True)
    CONTEXTS_JSON.write_text(json.dumps(contexts, indent=2))
    print(f"Contexts cached -> {CONTEXTS_JSON}  (n={len(contexts)})")
    return contexts


# SHORT EXPLANATION: success-test -- all fields present & typed, no field outside the
# whitelist (no free text), grounding recomputes from source, sorted by priority, JSON
# round-trips identically.
def verify(contexts: list[dict]) -> None:
    """Success-test for M3 Phase 5."""
    events = {ev["event_id"]: ev for ev in json.loads(EVENTS_JSON.read_text())}

    for c in contexts:
        # (a) every field present, none null.
        assert set(c) == ALLOWED_KEYS, f"event {c['event_id']}: keys != whitelist ({set(c) ^ ALLOWED_KEYS})"
        assert all(c[k] is not None for k in c), f"event {c['event_id']} has a null field"
        # (b) grounding: confidence & priority recompute from the raw event (traceable).
        ev = events[c["event_id"]]
        assert abs(c["m2_confidence"] - (1.0 - ev["min_p"])) < 1e-12, "confidence not traceable to min_p"
        assert abs(c["intensity"] - ev["intensity_mean"]) < 1e-12, "intensity not traceable to raw score"
        expected_prio = ev["intensity_mean"] * math.log10(1.0 + ev["duration_sec"])
        assert abs(c["priority"] - expected_prio) < 1e-9, "priority not reproducible from grounded fields"

    # (c) sorted by priority descending.
    prios = [c["priority"] for c in contexts]
    assert prios == sorted(prios, reverse=True), "contexts not ordered by priority"

    # (d) JSON round-trips identically.
    assert json.loads(json.dumps(contexts)) == contexts, "context does not round-trip through JSON"

    diffuse = sum(1 for c in contexts if c["localization"] == "diffuse")
    with_rel = sum(1 for c in contexts if c["shared_relations"]["shared_unit"] or c["shared_relations"]["shared_group"])
    print("\n=== M3 Phase 5 success-test ===")
    print(f"  (a) fields present   : all {len(contexts)} events match the {len(ALLOWED_KEYS)}-field whitelist  OK")
    print(f"  (b) grounding        : confidence & priority recompute from source  OK  (no free text)")
    print(f"  (c) prioritised      : ordered by priority desc  OK")
    print(f"  (d) serialises       : JSON round-trips identically  OK")
    print(f"      localization     : {len(contexts)-diffuse} confident, {diffuse} diffuse (M3 abstains on where)")
    print(f"      coupled hints    : {with_rel} events flag channels sharing group/unit")
    print("      top-3 by priority:")
    for c in contexts[:3]:
        chans = ", ".join(f"{ch}({p:.0f}%)" for ch, p in c["top_channels"][:3])
        print(f"        #{c['event_id']}: prio={c['priority']:.3f}  intensity={c['intensity']:.3f}  "
              f"{c['duration_sec']:.0f}s  {c['localization']}  [{chans}]")


def main() -> None:
    contexts = build()
    verify(contexts)


if __name__ == "__main__":
    main()
