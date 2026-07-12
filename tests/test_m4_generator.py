"""M4 · generator + precheck + render tests.

Locks the narrative lane: the evidence the LLM sees contains names and words but NO
precise measurements (ids, sims, novelty, intensity, priority, timestamps); the only
numbers are the human duration and the confidence %. The precheck catches every
fabrication type; the rendered facts table is byte-equal to the M3 context; the
canonical cached briefs replay offline (cache-first, zero API calls).

Run: pytest tests/test_m4_generator.py -v
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config  # noqa: E402
from m4_report import prompts  # noqa: E402
from m4_report.guardrails.precheck import _extract, precheck  # noqa: E402

CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"
LLM_CACHE = config.CACHE_DIR / "m4_llm_cache.json"
CORPUS_JSON = config.CACHE_DIR / "m4_anomaly_corpus.json"

needs_cache = pytest.mark.skipif(
    not (CONTEXTS_JSON.exists() and CORPUS_JSON.exists()), reason="M3/M4 cache missing"
)
needs_llm_cache = pytest.mark.skipif(not LLM_CACHE.exists(), reason="LLM cache missing")


@pytest.fixture(scope="module")
def ev33():
    from m4_report.retrieval.retrieve import load_corpus, retrieve

    contexts = json.loads(CONTEXTS_JSON.read_text())
    ctx = next(c for c in contexts if c["event_id"] == 33)
    retrieval = retrieve(ctx, load_corpus())
    return ctx, retrieval, prompts.evidence_block(ctx, retrieval)


# The narrative contract as an assert: the LLM's view has the qualitative machinery and
# NONE of the precise measurements (those live only in the deterministic tables).
@needs_cache
def test_evidence_narrative_contract(ev33):
    ctx, retrieval, evidence = ev33
    for expected in ("status", "coupling_note", "confidence_note", "combination_familiarity",
                     "dominant_channels", "localization", "duration"):
        assert expected in evidence, f"evidence lacks {expected}"
    assert "id_" not in evidence, "neighbor ids must not reach the LLM"
    assert str(retrieval["neighbors"][0]["sim"]) not in evidence
    assert f"{retrieval['novelty']:.6g}" not in evidence, "numeric novelty must not reach the LLM"
    assert str(ctx["intensity"]) not in evidence and str(ctx["priority"]) not in evidence
    assert ctx["start"] not in evidence and ctx["end"] not in evidence, "timestamps leak"


@needs_cache
def test_evidence_only_two_numbers(ev33):
    _, _, evidence = ev33
    _, numbers, timestamps = _extract(evidence)
    assert not timestamps, "no timestamps allowed in the LLM view"
    allowed = {30.0, 52.0, 48.0, 99.998, 1.0}  # duration parts + confidence % (+ "~1" note)
    assert numbers <= allowed, f"unexpected numbers reach the LLM: {sorted(numbers - allowed)}"


@needs_cache
def test_coupling_note(ev33):
    ctx, _, _ = ev33
    note = prompts._coupling_note(ctx["shared_relations"])
    assert note.startswith("hypothesis (unconfirmed):")
    assert "channel_23, channel_22, channel_21 share group_2" in note
    assert prompts._coupling_note({}) == (
        "no shared groups or physical units among the flagged channels"
    )


@needs_cache
def test_precheck_clean_and_dirty(ev33):
    _, _, evidence = ev33
    clean = ("The event is now closed. Dominant channels are channel_18, channel_23, "
             "channel_22 and channel_21. It lasted 30 h 52 min 48 s.")
    assert precheck(clean, evidence)["passed"]
    dirty = {
        "channel_99": clean + " channel_99 also fired.",
        "id_999": clean + " It matches id_999.",
        "7.77": clean + " Priority was 7.77.",
        "1999-01-01T00:00:00": clean + " It began at 1999-01-01T00:00:00.",
    }
    for token, text in dirty.items():
        result = precheck(text, evidence)
        assert not result["passed"] and token in result["offending"], token


@needs_cache
def test_precheck_unicode(ev33):
    _, _, evidence = ev33
    fancy = ("The event lasted 30 h 52 min 48 s on channel_18 – now closed, "
             "with confidence 99.998 %.")
    assert precheck(fancy, evidence)["passed"], "unicode cosmetics must not fail the check"


@needs_cache
def test_render_byte_equal(ev33):
    from m4_report.generation.render import extract_facts_rows, facts_rows, render_alert

    ctx, retrieval, _ = ev33
    doc = render_alert(ctx, retrieval, "PLACEHOLDER.")
    pristine = next(c for c in json.loads(CONTEXTS_JSON.read_text()) if c["event_id"] == 33)
    assert extract_facts_rows(doc) == facts_rows(pristine)


# Offline replay of the canonical briefs: cache-first means ZERO API calls here.
@needs_cache
@needs_llm_cache
def test_canonical_briefs_offline():
    from m4_report.generation.generator import generate_brief, load_contexts
    from m4_report.retrieval.retrieve import load_corpus, retrieve

    os.environ["ESA_LLM_USE_CACHE"] = "true"
    contexts = {c["event_id"]: c for c in load_contexts()}
    corpus = load_corpus()
    for eid in (33, 6):
        retrieval = retrieve(contexts[eid], corpus)
        brief = generate_brief(contexts[eid], retrieval)  # raises if precheck fails
        assert brief.strip()
        assert generate_brief(contexts[eid], retrieval) == brief, "cache round-trip differs"
