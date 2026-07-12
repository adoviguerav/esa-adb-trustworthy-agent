"""[4 · F8] Judge golden eval -- who watches the watchman.

The generator is evaluated by the judge; the judge is evaluated HERE, against
human-labelled ground truth: clean briefs it must approve (precision) and dirty briefs
with one known injected violation each that it must block (recall). The chain of trust
ends in a human: this file is small on purpose -- anyone can read the 18 cases and check
the labels themselves.

Scoring: a clean case counts as approved on PASS or FLAG (FLAG does not withhold the
brief); a dirty case counts as caught ONLY on BLOCK. Target: recall = 1.0 on dirty. If
recall < 1.0 the fix is to HARDEN the judge prompt -- never to soften the golden set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
from m4_report import prompts  # noqa: E402
from m4_report.guardrails.judge import judge  # noqa: E402

GOLDEN_JSON = Path(__file__).resolve().parent / "golden.json"


# SHORT EXPLANATION: the three evidence variants cases refer to. event_33 / event_6 are
# the real evidences; event_33_diffuse is synthetic (localization forced to "diffuse",
# no dominant channels) -- the mission data has no diffuse event, but the judge must
# still be examined on the abstention rule.
def build_evidences() -> dict:
    from m4_report.generation.generator import load_contexts  # noqa: E402
    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

    contexts = load_contexts()
    corpus = load_corpus()
    by_id = {c["event_id"]: c for c in contexts}
    r33 = retrieve(by_id[33], corpus)
    r6 = retrieve(by_id[6], corpus)
    diffuse_ctx = {**by_id[33], "localization": "diffuse", "dominant_channels": []}
    return {
        "event_33": prompts.evidence_block(by_id[33], r33),
        "event_6": prompts.evidence_block(by_id[6], r6),
        "event_33_diffuse": prompts.evidence_block(diffuse_ctx, r33),
        "_refs": (by_id, r33, r6),
    }


def load_cases(evidences: dict) -> list[dict]:
    """The 16 hand-written cases + the 2 canonical cached briefs (dynamic, PASS)."""
    from m4_report.generation.generator import generate_brief  # noqa: E402

    cases = json.loads(GOLDEN_JSON.read_text())["cases"]
    by_id, r33, r6 = evidences["_refs"]
    cases.append({"id": "C1", "expected": "PASS", "evidence_ref": "event_33",
                  "tests": "canonical cached brief of event 33",
                  "brief": generate_brief(by_id[33], r33)})
    cases.append({"id": "C5", "expected": "PASS", "evidence_ref": "event_6",
                  "tests": "canonical cached brief of event 6",
                  "brief": generate_brief(by_id[6], r6)})
    return cases


def run() -> dict:
    """Judge every golden case; return per-case results + precision/recall."""
    evidences = build_evidences()
    cases = load_cases(evidences)

    results = []
    for case in cases:
        verdict = judge(case["brief"], evidences[case["evidence_ref"]])
        if case["expected"] == "PASS":
            ok = verdict.verdict in ("PASS", "FLAG")  # FLAG does not withhold the brief
        else:
            ok = verdict.verdict == "BLOCK"
        results.append({**case, "got": verdict.verdict, "ok": ok,
                        "reasons": verdict.reasons})

    clean = [r for r in results if r["expected"] == "PASS"]
    dirty = [r for r in results if r["expected"] == "BLOCK"]
    return {
        "results": results,
        "precision": sum(r["ok"] for r in clean) / len(clean),
        "recall": sum(r["ok"] for r in dirty) / len(dirty),
        "n_clean": len(clean),
        "n_dirty": len(dirty),
    }


# SHORT EXPLANATION: F8 success-test. recall == 1.0 is the hard bar (a missed dirty case
# means the guardrail has a hole); precision is reported and must stay high (an
# over-blocking judge starves the operator of prose). Framed in the README as an
# existence proof over ~18 cases, NOT a statistical guarantee (no meta-overclaim).
def main() -> None:
    report = run()
    print("=== M4 Fase 8 -- judge golden eval ===")
    print(f"  {'case':<5} {'expected':<9} {'got':<6} ok  tests")
    for r in sorted(report["results"], key=lambda x: x["id"]):
        mark = "OK " if r["ok"] else "FAIL"
        print(f"  {r['id']:<5} {r['expected']:<9} {r['got']:<6} {mark} {r['tests']}")
        if not r["ok"]:
            print(f"        reasons: {r['reasons']}")
    print(f"\n  precision (clean approved): {report['precision']:.2f}  "
          f"({int(report['precision'] * report['n_clean'])}/{report['n_clean']})")
    print(f"  recall    (dirty blocked) : {report['recall']:.2f}  "
          f"({int(report['recall'] * report['n_dirty'])}/{report['n_dirty']})")

    assert report["recall"] == 1.0, "recall < 1.0: harden the judge prompt, never soften the golden"
    assert report["precision"] >= 0.8, "judge over-blocking: starves the operator of prose"
    print("\n  success-test: recall = 1.0, precision >= 0.8  OK")


if __name__ == "__main__":
    main()
