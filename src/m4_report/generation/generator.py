"""Generator [4a]: one grounded event context -> a validated Report.

Consumes ONLY the grounded context (from M3's m3_event_contexts.json) -- never the raw
telemetry. After generation it enforces the grounding guard: every channel the model
cited must exist in the context, else the report is rejected (fail loud, do not ship it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # m4_report/ on path
import config  # noqa: E402
import llm  # noqa: E402
import prompts  # noqa: E402
from schema import Report  # noqa: E402

CONTEXTS_JSON = config.CACHE_DIR / "m3_event_contexts.json"


def generate_report(context: dict) -> Report:
    """Generate a grounded Report for one event; guard that all cited channels are real."""
    user = prompts.evidence_block(context)
    report = llm.structured(prompts.GENERATOR_SYSTEM, user, Report, model=config.LLM_MODEL)
    report.event_id = context["event_id"]  # set by us, not trusted from the model

    allowed = {c for c, _ in context["top_channels"]}
    cited = set(report.responsible_channels) | {ch for h in report.hypotheses for ch in h.channels}
    stray = cited - allowed
    if stray:
        raise ValueError(f"generator cited channels not in context {context['event_id']}: {sorted(stray)}")
    return report


def load_contexts() -> list[dict]:
    """Load the priority-sorted grounded contexts produced by M3."""
    return json.loads(CONTEXTS_JSON.read_text())


# SHORT EXPLANATION: Fase 1 success-test -- generate the top-priority event and show it.
def main() -> None:
    context = load_contexts()[0]  # highest priority
    report = generate_report(context)
    print(f"=== M4 Fase 1 -- report for event {report.event_id} ({context['localization']}) ===")
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
