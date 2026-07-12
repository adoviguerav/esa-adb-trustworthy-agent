"""Prompt templates (first-class, versioned as .md) + the grounded EVIDENCE renderer.

The grounding contract lives in the .md files so it can be reviewed/versioned like code.
``evidence_block`` renders ONLY whitelisted data: FACTS (this event, from M3) + HISTORY
(retrieved past anomalies). Nothing else reaches the LLM -- that is what keeps generation
grounded. The anonymised class/category labels of neighbors are deliberately STRIPPED
from the generator's view: the brief speaks membership/count ("these channels appear in
N past anomalies"), never unvalidated resemblance ("looks like class_22").
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent
GENERATOR_PROMPT = (_DIR / "generator_prompt.md").read_text()

# Whitelist of context fields the generator may see (no raw telemetry, no free text).
# m2_confidence + priority ARE shown (the ESA duty asks for uncertainty quantification);
# the prompt forces the saturation caveat when confidence is mentioned.
_EVIDENCE_FIELDS = (
    "event_id", "start", "end", "duration_sec", "m2_confidence", "priority",
    "intensity", "localization", "top_channels", "dominant_channels", "shared_relations",
)


# SHORT EXPLANATION: the neighbor view for the LLM keeps only what membership language
# needs (which past anomaly, which channels, how similar). class/category/locality stay
# in the machine output -- an anonymised label invites resemblance claims and tells a
# human operator nothing.
def _history_view(retrieval: dict) -> dict:
    """The retrieval evidence the generator may cite."""
    return {
        "neighbors": [
            {"id": nb["id"], "channels": nb["channels"], "sim": nb["sim"]}
            for nb in retrieval["neighbors"]
        ],
        "novelty": retrieval["novelty"],
        "channel_past_count": {
            ch: prior["past_count"] for ch, prior in retrieval["channel_prior"].items()
        },
    }


# SHORT EXPLANATION: self-explanatory key names in the model's view -- the generator
# proved it misreads bare keys (called an attribution % "units of intensity"). Only what
# the LLM sees is renamed; the context itself keeps its M3 names.
_FIELD_RENAMES = {
    "m2_confidence": "m2_confidence_saturated",
    "top_channels": "top_channels_pct_of_attribution",
}


def evidence_block(context: dict, retrieval: dict) -> str:
    """Render FACTS (M3) + HISTORY (retrieval) -- the only material the model may use."""
    facts = {_FIELD_RENAMES.get(k, k): context[k] for k in _EVIDENCE_FIELDS if k in context}
    return (
        "EVIDENCE (use ONLY these facts):\n"
        "FACTS (this event):\n" + json.dumps(facts, indent=2) + "\n"
        "HISTORY (past anomalies, all ended before this event started):\n"
        + json.dumps(_history_view(retrieval), indent=2)
    )
