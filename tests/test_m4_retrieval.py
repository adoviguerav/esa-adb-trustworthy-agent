"""M4 · retrieval tests.

Locks the RAG layer: corpus integrity (644 records), the R3 anti-leakage invariant over
ALL 120 events (the critical M4 test), Tversky determinism (sorted float sums -- a real
bug once), a frozen reference similarity for event 33, reproducible tie-breaks, and the
deterministic qualitative helpers (familiarity, human duration).

Run: pytest tests/test_m4_retrieval.py -v
Cached-data tests skip if the M3/M4 cache is missing (run the phase scripts first).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config  # noqa: E402
from m4_report.prompts import familiarity, human_duration  # noqa: E402
from m4_report.retrieval.corpus import CORPUS_JSON  # noqa: E402
from m4_report.retrieval.retrieve import (  # noqa: E402
    load_corpus,
    retrieve,
    tversky_similarity,
)

CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"

needs_corpus = pytest.mark.skipif(not CORPUS_JSON.exists(), reason="corpus cache missing")
needs_contexts = pytest.mark.skipif(not CONTEXTS_JSON.exists(), reason="M3 contexts missing")


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(scope="module")
def contexts():
    return json.loads(CONTEXTS_JSON.read_text())


@needs_corpus
def test_corpus_shape(corpus):
    assert len(corpus) == 644
    required = {"id", "class", "category", "locality", "channels", "start", "end", "duration_sec"}
    for r in corpus:
        assert required <= set(r), f"{r['id']} missing fields {required - set(r)}"


@needs_corpus
def test_corpus_integrity(corpus):
    assert len({r["id"] for r in corpus}) == 644, "ids not unique"
    for r in corpus:
        assert r["_end"] >= r["_start"], f"{r['id']}: end < start"
    covered = set().union(*(r["_channels"] for r in corpus))
    assert set(config.TARGET_CHANNELS) <= covered, "some target channel never anomalous"


@needs_corpus
def test_corpus_round_trip():
    records = json.loads(CORPUS_JSON.read_text())
    assert json.loads(json.dumps(records)) == records


# The critical M4 invariant (R3): the corpus holds ground truth; a neighbor may only be
# used if it ENDED strictly before the event started. Checked for EVERY retrieved
# neighbor of EVERY event.
@needs_corpus
@needs_contexts
def test_r3_no_leakage(corpus, contexts):
    import pandas as pd

    by_id = {r["id"]: r for r in corpus}
    leaks = []
    for ctx in contexts:
        ev_start = pd.to_datetime(ctx["start"], utc=True).tz_localize(None)
        for nb in retrieve(ctx, corpus)["neighbors"]:
            if not (by_id[nb["id"]]["_end"] < ev_start):
                leaks.append((ctx["event_id"], nb["id"]))
    assert not leaks, f"R3 anti-leakage VIOLATED: {leaks[:10]}"


# Regression for a real bug: float sums over unordered sets differed in the last ulp
# across processes and broke LLM cache keys. Sums must iterate sorted -> identical.
@needs_corpus
@needs_contexts
def test_tversky_deterministic(corpus, contexts):
    for ctx in contexts[:10]:
        a = retrieve(ctx, corpus)
        b = retrieve(ctx, corpus)
        assert a["neighbors"] == b["neighbors"]
        assert a["novelty"] == b["novelty"]
    # hand-checked value: query {a:0.6, b:0.4}, neighbor {a, c} -> 0.6/(0.6+0.4+0.05)
    sim = tversky_similarity({"a": 0.6, "b": 0.4}, {"a", "c"}, beta=0.05)
    assert abs(sim - 0.6 / 1.05) < 1e-12


# Frozen reference: if a future change moves the retrieval, this test says so loudly.
@needs_corpus
@needs_contexts
def test_reference_sim_event33(corpus, contexts):
    ctx = next(c for c in contexts if c["event_id"] == 33)
    r = retrieve(ctx, corpus)
    top = r["neighbors"][0]
    assert top["id"] == "id_638"
    assert abs(top["sim"] - 0.8977905587388094) < 1e-12
    assert abs(r["novelty"] - 0.10220944126119058) < 1e-12
    dom = set(ctx["dominant_channels"])
    assert dom & set(top["channels"]), "top neighbor shares no dominant channel"


@needs_corpus
@needs_contexts
def test_tie_break_by_id(corpus, contexts):
    ctx = contexts[0]
    scored = retrieve(ctx, corpus, k=len(corpus))["neighbors"]
    for x, y in zip(scored, scored[1:]):
        if x["sim"] == y["sim"]:
            assert x["id"] > y["id"], "equal sims must order desc by id (deterministic)"


def test_familiarity_and_duration():
    assert familiarity(0.0) == "familiar"
    assert familiarity(0.149) == "familiar"
    assert familiarity(0.15) == "somewhat familiar"
    assert familiarity(0.349) == "somewhat familiar"
    assert familiarity(0.35) == "novel"
    assert human_duration(111168.0) == "30 h 52 min 48 s"
    assert human_duration(1098.0) == "18 min 18 s"
    assert human_duration(0) == "0 s"
    assert human_duration(3600) == "1 h"
