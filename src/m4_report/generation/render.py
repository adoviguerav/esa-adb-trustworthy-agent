"""Renderer: facts table + neighbors table + brief -> the operator-facing markdown.

The tables are built VERBATIM from the M3 context and the retrieval result -- the LLM
only contributes the prose paragraph. Fact values are rendered with ``json.dumps`` so
the success-test can assert byte-equality against the source context: the executable
proof of "the LLM does not emit facts".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path

# Fields shown in the facts table, in display order (same whitelist as the evidence).
FACTS_FIELDS = (
    "event_id", "start", "end", "duration_sec", "m2_confidence", "priority",
    "intensity", "localization", "dominant_channels", "top_channels",
)


# SHORT EXPLANATION: one (name, rendered-value) row per fact, straight from the context.
# json.dumps keeps the value exact and machine-comparable (no rounding, no reformat).
def facts_rows(context: dict) -> list[tuple[str, str]]:
    """Verbatim fact rows for one event."""
    return [(k, json.dumps(context[k])) for k in FACTS_FIELDS if k in context]


def _facts_table(context: dict) -> str:
    rows = "\n".join(f"| {k} | `{v}` |" for k, v in facts_rows(context))
    return "| fact | value (verbatim from M3) |\n|---|---|\n" + rows


def _neighbors_table(context: dict, retrieval: dict) -> str:
    event_ch = {ch for ch, _ in context["top_channels"]}
    head = "| past anomaly | similarity | shared channels |\n|---|---|---|"
    rows = "\n".join(
        f"| {nb['id']} | {nb['sim']:.3f} | {', '.join(sorted(event_ch & set(nb['channels']))) or '-'} |"
        for nb in retrieval["neighbors"]
    )
    return head + "\n" + rows


def render_alert(context: dict, retrieval: dict, brief_text: str) -> str:
    """The closing alert for one event: facts + retrieved history + audited prose."""
    return (
        f"## Anomaly event {context['event_id']} -- closing brief\n\n"
        f"### Facts (verbatim from the detection pipeline)\n\n"
        f"{_facts_table(context)}\n\n"
        f"note: m2_confidence saturates (~1 for every flagged event; alpha* floor) -- "
        f"it does not rank events. Use priority.\n\n"
        f"### Similar past anomalies (retrieved, all ended before this event)\n\n"
        f"{_neighbors_table(context, retrieval)}\n\n"
        f"combination novelty: {retrieval['novelty']:.3f} "
        f"(1 = channel set unlike anything in the archive)\n\n"
        f"### Brief (LLM-generated, audited)\n\n"
        f"{brief_text}\n"
    )


# SHORT EXPLANATION: F5 success-test (b) -- extract the facts table back OUT of the
# rendered markdown and compare byte-by-byte with rows built from a pristine reload of
# the context JSON. If the LLM (or the renderer) touched a single fact value, this fails.
def extract_facts_rows(markdown: str) -> list[tuple[str, str]]:
    """Parse the facts-table rows back out of a rendered alert."""
    rows = []
    for line in markdown.splitlines():
        if line.startswith("| ") and " | `" in line:
            name, value = line.strip("| ").split(" | ", 1)
            rows.append((name, value.strip().strip("`")))
    return rows


def main() -> None:
    import config  # noqa: E402  (src/ already on path)
    from m4_report.retrieval.retrieve import load_corpus, retrieve  # noqa: E402

    contexts = json.loads((config.CACHE_DIR / "m3_event_contexts.json").read_text())
    ctx = next(c for c in contexts if c["event_id"] == 33)
    retrieval = retrieve(ctx, load_corpus())

    doc = render_alert(ctx, retrieval, "PLACEHOLDER BRIEF (renderer test only).")

    pristine = next(c for c in json.loads((config.CACHE_DIR / "m3_event_contexts.json").read_text())
                    if c["event_id"] == 33)
    assert extract_facts_rows(doc) == facts_rows(pristine), "facts table != source context"
    assert "PLACEHOLDER BRIEF" in doc

    print("=== M4 Fase 5 -- render success-test ===")
    print("  (b) facts table byte-equal to M3 context values  OK")
    print(f"  document: {len(doc.encode())} bytes, {len(retrieval['neighbors'])} neighbors listed")


if __name__ == "__main__":
    main()
