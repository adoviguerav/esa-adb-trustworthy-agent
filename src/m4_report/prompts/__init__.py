"""Prompt templates (first-class, versioned as .md) + the grounded evidence renderer.

The grounding contract lives in the .md files so it can be reviewed/versioned like code.
``evidence_block`` renders ONLY the whitelisted context fields the model may use -- nothing
else reaches the LLM, which is what keeps generation grounded.
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent
GENERATOR_SYSTEM = (_DIR / "generator_system.md").read_text()

# Whitelist of context fields the generator is allowed to see (no raw telemetry, no free text).
_EVIDENCE_FIELDS = (
    "event_id", "start", "end", "duration_sec", "intensity", "localization",
    "top_channels", "dominant_channels", "shared_relations",
)


def evidence_block(context: dict) -> str:
    """Render the grounded context as the EVIDENCE block the model may use -- and only that."""
    evidence = {k: context[k] for k in _EVIDENCE_FIELDS if k in context}
    return "EVIDENCE (use only these facts):\n" + json.dumps(evidence, indent=2)
