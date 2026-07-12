"""Prompt templates (first-class, versioned as .md) + the grounded EVIDENCE renderer.

The grounding contract lives in the .md files so it can be reviewed/versioned like code.
``evidence_block`` renders the ONLY material the LLM may use, and it is deliberately
NARRATIVE-SHAPED: names (channels, groups, units), qualitative words, a human-readable
duration and a confidence percentage. Precise measurements (attribution %, intensity,
priority, novelty, neighbor ids/sims, timestamps) NEVER reach the LLM -- they live in the
deterministic tables of the rendered alert, where nothing can hallucinate them. The model
narrates; the tables carry the figures. Qualitative words the brief may use (familiarity,
saturation) are computed HERE, deterministically -- the model repeats them, it does not
choose them.
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent

# PROMPT VERSIONING: a shipped prompt version is NEVER edited -- a change means a new
# _vN file and bumping the pointer here. Old versions stay reviewable side-by-side and
# the LLM cache (keyed by prompt content) tells versions apart by construction.
# v1 -> v2: added the QUOTE-don't-paraphrase rule (4 real paraphrase-drift BLOCKs in the
# 120-event run: "moderate match", "anomalous window has ended", "coordinated
# deviation", "reflects its rarity"). v2 re-passed those 4 events: 4/4 PASS.
GENERATOR_PROMPT = (_DIR / "generator_prompt_v2.md").read_text()

# Familiarity thresholds over novelty (fixed modelling choices, like beta/K in retrieval).
_FAMILIARITY_BINS = ((0.15, "familiar"), (0.35, "somewhat familiar"))  # else "novel"

# The saturation caveat is itself a FACT the brief must be able to assert (the judge
# audits only against evidence -- a mandated-but-unstated caveat would always be blocked).
_CONFIDENCE_NOTE = (
    "confidence is saturated (near its ceiling) across ALL flagged events; it does not "
    "rank or discriminate between events -- use the priority value in the facts table"
)


def human_duration(seconds: float) -> str:
    """111168.0 -> '30 h 52 min 48 s' (deterministic; the only duration the LLM sees)."""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    parts = ([f"{h} h"] if h else []) + ([f"{m} min"] if m else []) + ([f"{sec} s"] if sec or not (h or m) else [])
    return " ".join(parts)


def familiarity(novelty: float) -> str:
    """Deterministic qualitative label for the archive relationship (the LLM repeats it)."""
    for cut, label in _FAMILIARITY_BINS:
        if novelty < cut:
            return label
    return "novel"


# SHORT EXPLANATION: the coupling hypothesis is pre-rendered by CODE from
# shared_relations -- the generator kept mis-assigning which channels share which group
# (a real judge catch, twice). The model may only repeat this sentence; it never
# reassembles the relation itself.
def _coupling_note(shared_relations: dict) -> str:
    parts = []
    for rel_kind, groups in shared_relations.items():
        kind = rel_kind.removeprefix("shared_")  # group / unit
        for name, channels in groups.items():
            parts.append(f"{', '.join(channels)} share {name} ({kind})")
    if not parts:
        return "no shared groups or physical units among the flagged channels"
    return ("hypothesis (unconfirmed): " + "; ".join(parts)
            + " -- a coupled behaviour is possible")


def evidence_block(context: dict, retrieval: dict) -> str:
    """The narrative-shaped evidence -- names and words, no precise measurements."""
    view = {
        "event": {
            "status": "closed -- the detector stopped flagging windows (says nothing "
                      "about the underlying issue being resolved)",
            "localization": context["localization"],
            "dominant_channels": context["dominant_channels"],
            "all_flagged_channels": [ch for ch, _ in context["top_channels"]],
            "coupling_note": _coupling_note(context["shared_relations"]),
            "duration": human_duration(context["duration_sec"]),
            "confidence": f"{100 * context['m2_confidence']:.3f} %",
            "confidence_note": _CONFIDENCE_NOTE,
        },
        "archive": {
            "combination_familiarity": familiarity(retrieval["novelty"]),
            "familiarity_note": (
                "derived deterministically from how much this event's CHANNEL COMBINATION "
                "matches past anomalies; it says nothing about magnitude or severity. "
                "Exact similarities and past-anomaly ids are in the similar-anomalies table"
            ),
        },
    }
    return "EVIDENCE (use ONLY these facts):\n" + json.dumps(view, indent=2)
