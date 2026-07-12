"""Generator [4a]: grounded evidence (M3 facts + retrieval) -> the Brief (narrative prose).

Consumes ONLY the narrative-shaped evidence (names, qualitative words, human duration,
confidence %) -- precise measurements never reach the model, so it cannot hallucinate or
embellish them; they live in the deterministic tables of the rendered alert. After
generation the brief must pass the lexical precheck against its own evidence (single
guard source -- the same check the pipeline applies). Semantic auditing is the judge's
job (guardrails, F7/F8).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
import config  # noqa: E402
from m4_report import llm, prompts  # noqa: E402
from m4_report.guardrails.precheck import precheck  # noqa: E402

CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"


def generate_brief(context: dict, retrieval: dict) -> str:
    """One grounded Brief for one closed event; raises if the precheck finds a violation."""
    evidence = prompts.evidence_block(context, retrieval)
    text = llm.text(prompts.GENERATOR_PROMPT, evidence)
    if not text.strip():
        raise ValueError(f"empty brief for event {context['event_id']}")
    result = precheck(text, evidence)
    if not result["passed"]:
        raise ValueError(
            f"brief for event {context['event_id']} failed precheck: {result['offending']}"
        )
    return text


def load_contexts() -> list[dict]:
    """The priority-sorted grounded contexts produced by M3."""
    return json.loads(CONTEXTS_JSON.read_text())


# SHORT EXPLANATION: F5 success-test on two REAL reference events: the top-priority one
# (event 33) and the most NOVEL one (exercises the familiarity language). Mechanical
# checks only: precheck clean + cache round-trip byte-equal.
def main() -> None:
    import os

    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

    contexts = load_contexts()
    corpus = load_corpus()
    by_id = {c["event_id"]: c for c in contexts}

    retrievals = {c["event_id"]: retrieve(c, corpus) for c in contexts}
    novel_id = max((eid for eid in retrievals if eid != 33),
                   key=lambda eid: retrievals[eid]["novelty"])
    picks = [33, novel_id]

    briefs = {eid: generate_brief(by_id[eid], retrievals[eid]) for eid in picks}

    # cache round-trip: with the cache toggle ON, the same call must return the exact
    # same text (the committed cache is the canonical reference, D9).
    os.environ["ESA_LLM_USE_CACHE"] = "true"
    for eid in picks:
        assert generate_brief(by_id[eid], retrievals[eid]) == briefs[eid], (
            f"cache round-trip differs for event {eid}"
        )

    print("=== M4 Fase 5 -- generator success-test ===")
    print(f"  (a) precheck clean  : {len(picks)} briefs, 0 violations  OK")
    print(f"  (b) cache round-trip: byte-equal on re-call  OK")
    for eid in picks:
        role = "top-priority" if eid == 33 else f"most-novel (novelty={retrievals[eid]['novelty']:.3f})"
        print(f"\n--- event {eid} ({role}) ---\n{briefs[eid]}")


if __name__ == "__main__":
    main()
