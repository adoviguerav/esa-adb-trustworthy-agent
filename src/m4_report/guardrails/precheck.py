"""[4 · guardrail 1] PRECHECK -- lexical, deterministic, NO LLM.

Every citable item in the brief (channel_N / id_N / group_N tokens, numbers, timestamps)
must literally exist in the EVIDENCE string the generator saw. Both sides are parsed with
the SAME extractor, so the check cannot drift from the model's view. Matching is EXACT:
the evidence shows floats already rounded to 6 significant figures, so the model has no
excuse to reformat a number.

What this catches: a fabricated token (channel_99), a fabricated neighbor (id_999), an
invented or altered number, a wrong timestamp. What it CANNOT see: a semantic
hallucination with no false token ("resembles a thermal fault") -- that is the judge's
job (guardrail 2, F7). Verdict of the alert = precheck AND judge.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path

# Citable entities: channels, past-anomaly ids, shared groups / physical units.
_TOKEN_RE = re.compile(r"\b(?:channel|id|group|physical_unit)_\d+\b", re.IGNORECASE)
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


# SHORT EXPLANATION: the model decorates numbers/dates with unicode (non-breaking hyphen
# U+2011, thin/narrow spaces U+2009/U+202F inside "111 168" or before a unit). Digit-group
# separators vanish ONLY between digits; elsewhere unicode spaces become plain spaces --
# an earlier global strip glued "channel_18 31.4" into "channel_1831.4" and broke everything.
def _normalise(text: str) -> str:
    text = text.replace("\u2011", "-").replace("\u2013", "-")  # non-breaking hyphen, en-dash
    text = re.sub("(\d)[\u2009\u202f,](?=\d{3}\b)", r"\1", text)  # 111 168 / 111,168 -> 111168
    text = re.sub("[\u2009\u202f\u00a0]", " ", text)  # remaining unicode spaces -> plain
    text = re.sub(r"(\d{4}-\d{2}-\d{2})\s+T", r"\1T", text)         # "2002-12-09 T16:.." -> joined
    return text


# SHORT EXPLANATION: one extractor for BOTH sides. Order matters: timestamps out first
# (so their digits are not shredded into numbers), then tokens (so channel_18 does not
# leak an 18), then what remains is scanned for bare numbers.
def _extract(text: str) -> tuple[set, set, set]:
    """(tokens, numbers, timestamps) cited/present in a text."""
    text = _normalise(text)
    timestamps = set(_TS_RE.findall(text))
    text = _TS_RE.sub(" ", text)
    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    text = _TOKEN_RE.sub(" ", text)
    numbers = {float(n) for n in _NUM_RE.findall(text)}
    return tokens, numbers, timestamps


def precheck(brief: str, evidence: str) -> dict:
    """Lexical audit of a brief against the evidence it was generated from."""
    ev_tok, ev_num, ev_ts = _extract(evidence)
    br_tok, br_num, br_ts = _extract(brief)
    offending = (
        sorted(br_tok - ev_tok)
        + sorted(f"{n:g}" for n in br_num - ev_num)
        + sorted(br_ts - ev_ts)
    )
    return {"passed": not offending, "offending": offending}


# SHORT EXPLANATION: F6 success-test. The two canonical cached briefs must PASS; four
# hand-dirtied variants (fake channel / fake neighbor / invented number / wrong
# timestamp) must each FAIL naming exactly the injected item.
def main() -> None:
    from m4_report import prompts  # noqa: E402  (src/ on path)
    from m4_report.generation.generator import generate_brief, load_contexts  # noqa: E402
    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

    contexts = load_contexts()
    corpus = load_corpus()
    by_id = {c["event_id"]: c for c in contexts}
    retrievals = {c["event_id"]: retrieve(c, corpus) for c in contexts}
    novel_id = max((e for e in retrievals if e != 33), key=lambda e: retrievals[e]["novelty"])

    # (a) canonical briefs pass.
    evidences, briefs = {}, {}
    for eid in (33, novel_id):
        evidences[eid] = prompts.evidence_block(by_id[eid], retrievals[eid])
        briefs[eid] = generate_brief(by_id[eid], retrievals[eid])  # cache hit, offline
        result = precheck(briefs[eid], evidences[eid])
        assert result["passed"], f"canonical brief {eid} failed precheck: {result['offending']}"

    # (b) each injected fabrication is caught and named.
    dirty = {
        "channel_99": briefs[33] + " channel_99 also fired.",
        "id_999": briefs[33] + " This matches the past anomaly id_999.",
        "7.77": briefs[33] + " The priority was 7.77.",
        "1999-01-01T00:00:00": briefs[33] + " It started at 1999-01-01T00:00:00.",
    }
    for expected, text in dirty.items():
        result = precheck(text, evidences[33])
        assert not result["passed"] and expected in result["offending"], (
            f"injected '{expected}' not caught: {result['offending']}"
        )

    # (c) deterministic.
    assert precheck(briefs[33], evidences[33]) == precheck(briefs[33], evidences[33])

    print("=== M4 Fase 6 -- precheck success-test ===")
    print(f"  (a) canonical briefs PASS : events 33, {novel_id}  OK")
    print(f"  (b) fabrications caught   : {len(dirty)}/4 (token, id, number, timestamp)  OK")
    print(f"  (c) deterministic         : OK")


if __name__ == "__main__":
    main()
