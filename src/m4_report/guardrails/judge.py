"""[4 · guardrail 2] JUDGE -- semantic, LLM-as-judge (D5).

Audits a brief claim-by-claim against the SAME evidence block the generator saw, with a
forced refute stance (anti self-preference: generator and judge are the same model family
-- the prompt makes the judge an adversary, and the golden set (F8) measures that it does
not rubber-stamp). Catches what the lexical precheck cannot: hallucinations with no false
token ("resembles a thermal fault"), root-cause claims (D3), hypothesis-as-fact (D4),
certainty overclaims, unretrieved neighbors, dishonest novelty.

Verdict of the alert = precheck AND judge (wired in the pipeline, F9).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

try:  # Literal is 3.8+ in typing; keep explicit import local to one place
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
import config  # noqa: E402
from m4_report import llm, prompts  # noqa: E402

JUDGE_PROMPT = (Path(prompts.__file__).resolve().parent / "judge_prompt.md").read_text()


class Verdict(BaseModel):
    """The judge's structured verdict for one brief (the auditable unit of guardrail 2)."""

    verdict: Literal["PASS", "FLAG", "BLOCK"]
    reasons: List[str] = Field(
        default_factory=list,
        description="One entry per finding: quoted offending phrase + violated rule. Empty for PASS.",
    )


def judge(brief: str, evidence: str) -> Verdict:
    """Audit one brief against its evidence. Cache-first (same LLM seam as the generator)."""
    user = f"{evidence}\n\nBRIEF UNDER AUDIT:\n{brief}"
    return llm.structured(JUDGE_PROMPT, user, Verdict, model=config.JUDGE_MODEL)


# SHORT EXPLANATION: F7 success-test -- it evaluates the JUDGE, not the generator.
# (a) at least one real brief PASSes (a judge that blocks everything is useless); the
# other real verdicts are RECORDED as data, not asserted (a blocked real brief = the
# system working, and F9 shows it as "brief withheld"); (b) anti rubber-stamp: a
# hand-made root-cause claim must be BLOCKED (a judge that approves everything fails
# here); (c) citing a past anomaly that is not in the evidence must be BLOCKED
# (leakage path); (d) determinism via cache round-trip.
def main() -> None:
    from m4_report.generation.generator import generate_brief, load_contexts  # noqa: E402
    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

    contexts = load_contexts()
    corpus = load_corpus()
    by_id = {c["event_id"]: c for c in contexts}
    retrievals = {c["event_id"]: retrieve(c, corpus) for c in contexts}
    novel_id = max((e for e in retrievals if e != 33), key=lambda e: retrievals[e]["novelty"])

    # (a) the judge is not a universal blocker: >=1 real brief passes; the rest recorded.
    verdicts = {}
    for eid in (33, novel_id):
        evidence = prompts.evidence_block(by_id[eid], retrievals[eid])
        brief = generate_brief(by_id[eid], retrievals[eid])  # cache hit
        verdicts[eid] = judge(brief, evidence)
    assert any(v.verdict in ("PASS", "FLAG") for v in verdicts.values()), (
        f"judge blocked every real brief: { {e: v.verdict for e, v in verdicts.items()} }"
    )

    evidence33 = prompts.evidence_block(by_id[33], retrievals[33])
    brief33 = generate_brief(by_id[33], retrievals[33])

    # (b) anti rubber-stamp: explicit root cause -> BLOCK.
    dirty_cause = brief33 + (
        " The anomaly was caused by a thermal fault in the battery subsystem."
    )
    v_cause = judge(dirty_cause, evidence33)
    assert v_cause.verdict == "BLOCK", f"root-cause claim not blocked: {v_cause}"

    # (c) unretrieved neighbor: a real corpus id that is NOT in the retrieved top-K.
    retrieved_ids = {nb["id"] for nb in retrievals[33]["neighbors"]}
    outside = next(r["id"] for r in corpus if r["id"] not in retrieved_ids)
    dirty_neigh = brief33 + (
        f" This event closely matches the past anomaly {outside} from the archive."
    )
    v_neigh = judge(dirty_neigh, evidence33)
    assert v_neigh.verdict == "BLOCK", f"unretrieved neighbor {outside} not blocked: {v_neigh}"

    # (d) deterministic via the frozen cache (R1): the canonical verdict is the cached
    # one; with the cache toggle ON the same call returns the identical object. (A raw
    # API re-call may differ -- the LLM is not bit-deterministic; that is exploration
    # mode, not the reference.)
    import os
    os.environ["ESA_LLM_USE_CACHE"] = "true"
    assert judge(brief33, evidence33) == verdicts[33]

    print("=== M4 Fase 7 -- judge success-test ===")
    for eid in (33, novel_id):
        v = verdicts[eid]
        extra = f" reasons: {v.reasons}" if v.reasons else ""
        print(f"  (a) brief event {eid:>3}    : {v.verdict}{extra}")
    print(f"  (b) root-cause claim   : BLOCK  OK  ({v_cause.reasons[:1]})")
    print(f"  (c) unretrieved id     : BLOCK  OK  ({v_neigh.reasons[:1]})")
    print(f"  (d) cache round-trip   : identical verdict  OK")


if __name__ == "__main__":
    main()
