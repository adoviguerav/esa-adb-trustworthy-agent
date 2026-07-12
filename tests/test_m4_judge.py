"""M4 · judge + golden + alerts tests.

Locks the measurement chain: the Verdict schema, the judge's certification against the
human-labelled golden set (precision 1.0 / recall 1.0, FROZEN as reference numbers), the
golden set's own shape, and the production alerts artefact -- including the trustworthy
invariant that blocked prose can never ship inside m4_alerts.json.

Run: pytest tests/test_m4_judge.py -v
LLM-dependent tests replay the frozen cache (zero API calls); they skip if it is missing.
"""
import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config  # noqa: E402
from m4_report.guardrails.judge import Verdict  # noqa: E402

GOLDEN_JSON = ROOT / "src" / "m4_report" / "evals" / "golden.json"
ALERTS_JSON = config.CACHE_DIR / "m4_alerts.json"
LLM_CACHE = config.CACHE_DIR / "m4_llm_cache.json"

needs_llm_cache = pytest.mark.skipif(not LLM_CACHE.exists(), reason="LLM cache missing")
needs_alerts = pytest.mark.skipif(not ALERTS_JSON.exists(), reason="m4_alerts.json missing")


def test_verdict_schema():
    v = Verdict(verdict="PASS", reasons=[])
    assert v.verdict == "PASS" and v.reasons == []
    assert Verdict(verdict="BLOCK", reasons=["root cause: ..."]).reasons
    with pytest.raises(ValidationError):
        Verdict(verdict="MAYBE", reasons=[])


# The judge's certificate as a regression test: the golden eval replayed from the frozen
# cache must keep precision 1.0 AND recall 1.0. If any future change (prompt, evidence,
# model) moves either number, this fails loudly. Fix direction: harden the judge, never
# soften the golden.
@needs_llm_cache
def test_golden_from_cache():
    from m4_report.evals.run_eval import run

    os.environ["ESA_LLM_USE_CACHE"] = "true"
    report = run()
    assert report["recall"] == 1.0, [r for r in report["results"] if not r["ok"]]
    assert report["precision"] == 1.0, [r for r in report["results"] if not r["ok"]]
    assert report["n_clean"] == 7 and report["n_dirty"] == 11


def test_golden_labels_balanced():
    cases = json.loads(GOLDEN_JSON.read_text())["cases"]
    clean = [c for c in cases if c["expected"] == "PASS"]
    dirty = [c for c in cases if c["expected"] == "BLOCK"]
    assert len(clean) == 5 and len(dirty) == 11  # + 2 dynamic canonical PASS cases
    assert len({c["id"] for c in cases}) == len(cases), "case ids not unique"
    for c in cases:
        assert c["tests"].strip(), f"{c['id']}: undocumented case"
        assert c["evidence_ref"] in ("event_33", "event_6", "event_33_diffuse")


@needs_alerts
def test_alerts_scorecard():
    alerts = json.loads(ALERTS_JSON.read_text())
    assert len(alerts) == 120
    for eid, a in alerts.items():
        assert a["flag_text"] and a["verdict"] in ("PASS", "FLAG", "BLOCK"), eid
        assert len(a["flag_text"].encode()) <= 160, f"event {eid}: flag over budget"
    counts = {v: sum(1 for a in alerts.values() if a["verdict"] == v)
              for v in ("PASS", "FLAG", "BLOCK")}
    # frozen v2 scorecard -- a future prompt/model change that degrades it must be seen
    assert counts == {"PASS": 120, "FLAG": 0, "BLOCK": 0}, counts


# Trustworthy invariant, armed forever: if a future run produces BLOCKs again, the
# withheld prose must NOT travel inside the artefact (tables + reasons only).
@needs_alerts
def test_blocked_prose_never_shipped():
    alerts = json.loads(ALERTS_JSON.read_text())
    for eid, a in alerts.items():
        if a["verdict"] == "BLOCK":
            assert a["brief"] is None, f"event {eid}: blocked prose shipped in alerts json"
