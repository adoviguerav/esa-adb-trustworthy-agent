"""Structured I/O for the LLM layer [4].

The Report is the AUDITABLE UNIT: the judge [4b] audits these fields against the event
context, not free prose. Keeping the output a validated Pydantic object (not a markdown
blob) is what lets the guardrails check grounding claim-by-claim.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    """A labelled hypothesis (D4) -- tentative, never asserted as fact, never a root cause (D3)."""

    text: str = Field(..., description="The hypothesis, phrased as explicitly tentative.")
    channels: list[str] = Field(
        default_factory=list,
        description="Channels this hypothesis refers to; each MUST appear in the context.",
    )


class Report(BaseModel):
    """Grounded operator report for one anomaly event.

    Every channel cited (in ``responsible_channels`` or any hypothesis) must come from the
    event context. ``severity`` is derived from intensity, NOT from confidence (which is
    saturated and non-discriminative). When ``localization`` is 'diffuse' the report
    abstains on WHERE: ``abstained`` is True and ``responsible_channels`` is empty.
    """

    event_id: int = Field(default=-1, description="Set by the pipeline from the context, not the model.")
    summary: str = Field(..., description="What happened and when, grounded in the context only.")
    responsible_channels: list[str] = Field(
        default_factory=list, description="Culprit channels, taken from the context's dominant_channels."
    )
    severity: str = Field(..., description="Qualitative severity from intensity (NOT confidence).")
    localization: str = Field(..., description="'confident' or 'diffuse', echoed from the context.")
    abstained: bool = Field(..., description="True when diffuse: the report abstains on WHERE.")
    hypotheses: list[Hypothesis] = Field(default_factory=list)
