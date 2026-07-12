"""[4 · F9] Two-moment pipeline over a streaming replay of the mission timeline.

The core is a STATE MACHINE that consumes one observation at a time and never looks
ahead: at window N it only knows windows <= N. Opening an event fires the START flag
(moment 1, deterministic template); closing it (a quiet gap) fires the audited BRIEF
(moment 2, retrieval + LLM + precheck AND judge). Batch vs live streaming differ ONLY in
the driver that feeds the machine: here a `for` over the cached flagged-window indices
(the replayed M2 output); on board, a `while` over a live feed -- `replay()` cannot tell.

Declared boundary (Scenario & Assumptions): the demo streams the CACHED outputs of
M1/M2, and on close it looks up the M3-aggregated context instead of aggregating
incrementally (that would need the 48 MB model). Same WHEN-logic, replayed WHAT-payload.

BLOCK behaviour (trustworthy): a blocked brief NEVER ships -- the alert goes down with
the deterministic tables plus "brief withheld" and the judge's reasons. Blocked prose is
not even stored in m4_alerts.json.

Outputs: data/cached/m4_alerts.json (all events) + docs/m4_alert_example.md (event 33)
+ aggregate PASS/FLAG/BLOCK stats (the generator's real-world scorecard) + downlink metric.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

_SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_SRC / "m3_attribution"))  # M3 modules import each other by plain name
import config  # noqa: E402
from aggregate import DEFAULT_GAP, marked_global_indices  # noqa: E402
from m4_report import prompts  # noqa: E402
from m4_report.alert import load_start_windows, render_flag, start_flag  # noqa: E402
from m4_report.generation.generator import generate_brief, load_contexts  # noqa: E402
from m4_report.generation.render import render_alert  # noqa: E402
from m4_report.guardrails.judge import judge  # noqa: E402
from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

ALERTS_JSON = config.CACHE_DIR / "m4_alerts.json"
EXAMPLE_MD = config.REPO / "docs" / "m4_alert_example.md"
BYTES_PER_SAMPLE = 4 * len(config.TARGET_CHANNELS)  # float32 x 11 channels per row
WS = config.WINDOW_SIZE

WITHHELD = "**Brief withheld by the guardrail** (precheck AND judge must approve)."


# SHORT EXPLANATION: the streaming state machine. Consumes flagged-window indices one at
# a time, in order; an index farther than `gap` from the last one closes the open event
# and opens the next. No lookahead: every decision uses only already-seen indices.
def replay(flagged_stream, on_open, on_close, gap: int = DEFAULT_GAP) -> None:
    """Drive the two moments over any ordered stream of flagged window indices."""
    first = last = None
    for idx in flagged_stream:
        assert last is None or idx > last, "stream not in time order"
        if first is None:
            first, last = idx, idx
            on_open(idx)
        elif idx - last > gap:
            on_close(first, last)
            first, last = idx, idx
            on_open(idx)
        else:
            last = idx
    if first is not None:
        on_close(first, last)  # end of stream flushes the open event


def flagged_stream():
    """The replayed M2 output: flagged global window indices, time-ordered."""
    marked, _ = marked_global_indices()
    return (int(i) for i in np.sort(marked))


# SHORT EXPLANATION: LLM calls go through a small retry harness -- the free tier rate
# limits; a cached call returns instantly (no sleep), an API call is paced and retried.
def _call(fn, *args, pause: float = 2.5, retries: int = 6):
    for attempt in range(retries):
        t0 = time.monotonic()
        try:
            result = fn(*args)
            if time.monotonic() - t0 > 0.1:  # real API call -> pace the next one
                time.sleep(pause)
            return result
        except Exception as e:  # noqa: BLE001 -- retry only rate-limit shaped errors
            msg = str(e).lower()
            if attempt < retries - 1 and ("429" in msg or "rate" in msg or "limit" in msg):
                time.sleep(45)
                continue
            raise


def close_event(context: dict, corpus: list[dict]) -> dict:
    """Moment 2 for one closed event: retrieval -> brief -> precheck AND judge -> alert."""
    retrieval = retrieve(context, corpus)
    evidence = prompts.evidence_block(context, retrieval)

    try:
        brief = _call(generate_brief, context, retrieval)  # precheck runs inside
    except ValueError as e:  # precheck violation -> withheld, the replay must not die
        reasons = [f"precheck: {e}"]
        doc = render_alert(context, retrieval, f"{WITHHELD}\nReasons: {reasons[0]}")
        return {"verdict": "BLOCK", "blocked_by": "precheck", "reasons": reasons,
                "brief": None, "alert_md": doc}

    verdict = _call(judge, brief, evidence)
    if verdict.verdict == "BLOCK":
        reasons = verdict.reasons
        doc = render_alert(context, retrieval,
                           WITHHELD + "\nJudge reasons: " + " | ".join(reasons))
        return {"verdict": "BLOCK", "blocked_by": "judge", "reasons": reasons,
                "brief": None, "alert_md": doc}

    note = "" if verdict.verdict == "PASS" else "\n\n(FLAG: " + " | ".join(verdict.reasons) + ")"
    doc = render_alert(context, retrieval, brief + note)
    return {"verdict": verdict.verdict, "blocked_by": None, "reasons": verdict.reasons,
            "brief": brief, "alert_md": doc}


def run() -> dict:
    """Full replay over the mission timeline; returns {event_id: alert record}."""
    start_records = load_start_windows()
    contexts = {c["event_id"]: c for c in load_contexts()}
    corpus = load_corpus()
    alerts: dict[int, dict] = {}
    state = {"eid": -1}

    def on_open(first_idx: int) -> None:
        state["eid"] += 1
        eid = state["eid"]
        rec = start_records[eid]
        # alignment guard: the machine discovered the SAME opening M3/M4 cached offline
        assert rec["window_idx"] == first_idx, f"event {eid}: open at {first_idx} != {rec['window_idx']}"
        flag = start_flag(rec)
        alerts[eid] = {"event_id": eid, "flag": flag, "flag_text": render_flag(flag)}

    def on_close(first_idx: int, last_idx: int) -> None:
        eid = state["eid"]
        ctx = contexts[eid]
        result = close_event(ctx, corpus)
        raw_bytes = (last_idx + WS - first_idx) * BYTES_PER_SAMPLE  # raw telemetry span
        alert_bytes = len(alerts[eid]["flag_text"].encode()) + len(result["alert_md"].encode())
        alerts[eid].update(result)
        alerts[eid].update({"raw_bytes": raw_bytes, "alert_bytes": alert_bytes})
        print(f"  event {eid:>3}: {result['verdict']:<5} "
              f"(downlink {raw_bytes:>9,} -> {alert_bytes:,} bytes)", flush=True)

    replay(flagged_stream(), on_open, on_close)

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    serialisable = {str(k): {kk: vv for kk, vv in v.items() if kk != "alert_md"}
                    for k, v in alerts.items()}
    ALERTS_JSON.write_text(json.dumps(serialisable, indent=2))
    EXAMPLE_MD.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_MD.write_text(
        f"# Example two-moment alert (event 33)\n\n"
        f"## Moment 1 -- START flag (deterministic, ~bytes, no LLM)\n\n"
        f"```\n{alerts[33]['flag_text']}\n```\n\n"
        f"## Moment 2 -- closing alert (audited)\n\n{alerts[33]['alert_md']}\n"
    )
    return alerts


# SHORT EXPLANATION: F9 success-test. (a) machine/offline alignment held for all events
# (asserted during the run); (b) every event produced flag + verdict; (c) BLOCK path
# renders "withheld" without the prose -- exercised on a known-dirty brief if no real
# BLOCK occurred (we do not depend on luck); (d) downlink ratio reported; (e) round-trip.
def main() -> None:
    alerts = run()

    n = len(alerts)
    counts = {v: sum(1 for a in alerts.values() if a["verdict"] == v)
              for v in ("PASS", "FLAG", "BLOCK")}
    assert all("flag_text" in a and "verdict" in a for a in alerts.values())

    blocked = [a for a in alerts.values() if a["verdict"] == "BLOCK"]
    if blocked:
        sample = blocked[0]
        assert sample["brief"] is None and "withheld" in sample["alert_md"]
    else:  # forced BLOCK path check on a known-dirty brief (golden D2)
        contexts = {c["event_id"]: c for c in load_contexts()}
        corpus = load_corpus()
        retrieval = retrieve(contexts[33], corpus)
        dirty = ("The event on channel_18 closed. The pattern is consistent with a "
                 "thermal regulation fault affecting the battery subsystem.")
        v = _call(judge, dirty, prompts.evidence_block(contexts[33], retrieval))
        assert v.verdict == "BLOCK"
        doc = render_alert(contexts[33], retrieval, WITHHELD)
        assert "withheld" in doc and "thermal" not in doc

    round_trip = json.loads(ALERTS_JSON.read_text())
    assert len(round_trip) == n

    raw = sum(a["raw_bytes"] for a in alerts.values())
    sent = sum(a["alert_bytes"] for a in alerts.values())
    print("\n=== M4 Fase 9 -- pipeline success-test ===")
    print(f"  (a) stream/offline alignment : {n} events opened at the exact cached window  OK")
    print(f"  (b) two moments everywhere   : {n} flags + {n} audited alerts  OK")
    print(f"  (c) BLOCK path               : {'real (' + str(counts['BLOCK']) + ' events)' if blocked else 'forced synthetic'} -- prose withheld  OK")
    print(f"  (d) downlink                 : {raw:,} raw bytes -> {sent:,} alert bytes "
          f"({raw / max(sent, 1):,.0f}x reduction)")
    print(f"  (e) round-trip               : {ALERTS_JSON.name} OK · example: {EXAMPLE_MD}")
    print(f"\n  generator scorecard on {n} events: "
          f"{counts['PASS']} PASS · {counts['FLAG']} FLAG · {counts['BLOCK']} BLOCK")


if __name__ == "__main__":
    main()
