"""M3 · context + channel-relation tests.

Locks the LLM handoff: channel relations are grounded (coupled pair reports the shared
unit; unrelated pair reports nothing), and every event context is fully grounded (keys
in the whitelist, no nulls, confidence/priority/intensity traceable to source, JSON
round-trips). This is what protects "no hallucination" before the LLM sees anything.

Run: pytest tests/test_m3_context.py -v
Context tests skip if the M3 cache is missing (run aggregate.py + context.py first).
"""
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "m3_attribution"))
import config  # noqa: E402
from channels import load_channel_meta, shared_relations  # noqa: E402
import context as ctx  # noqa: E402

EVENTS = config.CACHE_DIR / "m3_events.json"
needs_events = pytest.mark.skipif(not EVENTS.exists(), reason="m3_events.json missing; run aggregate.py")


# --- channel relations: reads channels.csv (no pipeline cache) --------------

def test_shared_relations_coupled():
    """Channels 22 & 23 share physical_unit_9 and group_2 (grounded coupling hint)."""
    meta = load_channel_meta()
    rel = shared_relations(["channel_22", "channel_23"], meta)
    assert rel["shared_unit"].get("physical_unit_9") == ["channel_22", "channel_23"]
    assert "group_2" in rel["shared_group"]


def test_shared_relations_unrelated_empty():
    """Channels from different groups with no shared unit report no relation."""
    rel = shared_relations(["channel_18", "channel_25"], load_channel_meta())
    assert not rel["shared_group"] and not rel["shared_unit"]


def test_subsystem_excluded():
    """subsystem is shared by all 11 -> must not appear as a relation (no signal)."""
    rel = shared_relations(list(config.TARGET_CHANNELS), load_channel_meta())
    assert set(rel) == {"shared_group", "shared_unit"}  # no 'shared_subsystem'


# --- event context grounding: needs the cached events -----------------------

@needs_events
def test_context_whitelist_and_no_nulls():
    """Every context field is in the whitelist and non-null (no free text)."""
    events = json.loads(EVENTS.read_text())
    meta = load_channel_meta()
    for ev in events:
        c = ctx.build_context(ev, meta)
        assert set(c) == ctx.ALLOWED_KEYS
        assert all(c[k] is not None for k in c)


@needs_events
def test_context_fields_traceable():
    """confidence, intensity and priority recompute from the raw event (grounded)."""
    events = json.loads(EVENTS.read_text())
    meta = load_channel_meta()
    for ev in events:
        c = ctx.build_context(ev, meta)
        assert abs(c["m2_confidence"] - (1.0 - ev["min_p"])) < 1e-12
        assert abs(c["intensity"] - ev["intensity_mean"]) < 1e-12
        expected = ev["intensity_mean"] * math.log10(1.0 + ev["duration_sec"])
        assert abs(c["priority"] - expected) < 1e-9


@needs_events
def test_context_json_roundtrip_and_sorted():
    """The full context list serialises to JSON identically and is priority-sorted."""
    contexts = ctx.build()
    assert json.loads(json.dumps(contexts)) == contexts
    prios = [c["priority"] for c in contexts]
    assert prios == sorted(prios, reverse=True)
