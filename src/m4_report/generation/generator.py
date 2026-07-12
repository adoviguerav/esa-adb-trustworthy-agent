"""Generator [4a]: grounded evidence (M3 facts + retrieval) -> the Brief (prose only).

Consumes ONLY the grounded context (m3_event_contexts.json) and the retrieval result --
never raw telemetry. After generation it enforces the mechanical grounding guard: every
`channel_N` / `id_N` token the model wrote must exist in the EVIDENCE, else the brief is
rejected loudly (never shipped). Semantic auditing (root cause, overclaim, hypothesis-as-
fact) is NOT done here -- that is the judge's job (guardrails, F7/F8).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
import config  # noqa: E402
from m4_report import llm, prompts  # noqa: E402

CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"

_TOKEN_RE = re.compile(r"\b(channel_\d+|id_\d+)\b")


# SHORT EXPLANATION: the mechanical guard. Collect every channel_N / id_N the model
# wrote and check each against the evidence (event channels + neighbor channels + ids).
def stray_tokens(text: str, context: dict, retrieval: dict) -> set[str]:
    """Tokens cited in ``text`` that do NOT exist in the evidence (empty set = grounded)."""
    allowed = {ch for ch, _ in context["top_channels"]}
    for nb in retrieval["neighbors"]:
        allowed.add(nb["id"])
        allowed.update(nb["channels"])
    return set(_TOKEN_RE.findall(text)) - allowed


def generate_brief(context: dict, retrieval: dict) -> str:
    """One grounded Brief for one closed event; raises if the guard finds a stray token."""
    user = prompts.evidence_block(context, retrieval)
    text = llm.text(prompts.GENERATOR_PROMPT, user)
    if not text.strip():
        raise ValueError(f"empty brief for event {context['event_id']}")
    stray = stray_tokens(text, context, retrieval)
    if stray:
        raise ValueError(
            f"brief for event {context['event_id']} cites tokens outside evidence: {sorted(stray)}"
        )
    return text


def load_contexts() -> list[dict]:
    """The priority-sorted grounded contexts produced by M3."""
    return json.loads(CONTEXTS_JSON.read_text())


# SHORT EXPLANATION: F5 success-test on two REAL reference events: the top-priority one
# (event 33) and the most NOVEL one (highest novelty -> exercises the honest-novelty
# language). Checks are mechanical only: guard clean + cache round-trip byte-equal.
def main() -> None:
    import os

    from m4_report.retrieval.retrieve import load_corpus, retrieve  # local: avoids cycle

    contexts = load_contexts()
    corpus = load_corpus()
    by_id = {c["event_id"]: c for c in contexts}

    retrievals = {c["event_id"]: retrieve(c, corpus) for c in contexts}
    novel_id = max((eid for eid in retrievals if eid != 33),
                   key=lambda eid: retrievals[eid]["novelty"])
    picks = [33, novel_id]

    briefs = {}
    for eid in picks:
        briefs[eid] = generate_brief(by_id[eid], retrievals[eid])
        assert not stray_tokens(briefs[eid], by_id[eid], retrievals[eid])  # guard, re-checked

    # cache round-trip: with the cache toggle ON, the same call must return the exact
    # same text (the committed cache is the canonical reference, D9).
    os.environ["ESA_LLM_USE_CACHE"] = "true"
    for eid in picks:
        again = generate_brief(by_id[eid], retrievals[eid])
        assert again == briefs[eid], f"cache round-trip differs for event {eid}"

    print("=== M4 Fase 5 -- generator success-test ===")
    print(f"  (a) guard          : 0 stray tokens in {len(picks)} briefs  OK")
    print(f"  (b) cache round-trip: byte-equal on re-call  OK")
    for eid in picks:
        role = "top-priority" if eid == 33 else f"most-novel (novelty={retrievals[eid]['novelty']:.3f})"
        print(f"\n--- event {eid} ({role}) ---\n{briefs[eid]}")


if __name__ == "__main__":
    main()
