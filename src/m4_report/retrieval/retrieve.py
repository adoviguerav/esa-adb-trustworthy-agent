"""[4 · RAG] Deterministic retriever: match a live event's channel set against the corpus.

NO embeddings, NO vector DB. Similarity is a TVERSKY INDEX (Tversky 1977) over channel sets,
weighted by the event's per-channel attribution (top_channels). Tversky with alpha=1, beta=0.05:

    sim = shared / (shared + 1*event_only + beta*neighbor_only)

Rewards covering the event's attributed channels; the beta term lightly penalises a neighbor
that also touches many unrelated channels (a "lights up on everything" anomaly is not a good
match). The event side carries attribution weights; the neighbor-only side is counted flat
(beta each) because the corpus stores only WHICH channels each past anomaly touched, not how
much -- so no neighbor weights exist. beta is a fixed modelling choice, NOT a tuned knob.

Anti-leakage (R3): the corpus holds ground-truth annotations; a neighbor may only be used if it
ENDED strictly before the event started (neighbor.end < event.start). The corpus start is the
human ANNOTATION, event.start is the DETECTOR -- they differ, so a start<start guard would let
the event's own overlapping label leak in as a self-match. end<start closes it.
The RAG CHARACTERISES (what past cases this resembles); it does NOT detect ([1] already did).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
import config  # noqa: E402
from m4_report.retrieval.corpus import CORPUS_JSON, save_corpus  # noqa: E402

BETA = 0.05      # Tversky beta: mild penalty per unrelated neighbor channel (fixed, not tuned)
DEFAULT_K = 5    # how many neighbors to surface (display choice, not tuned)


def _parse(ts: str) -> pd.Timestamp:
    """Parse to tz-naive UTC (context times are naive, corpus times carry +00:00)."""
    return pd.to_datetime(ts, utc=True).tz_localize(None)


def load_corpus() -> list[dict]:
    """Load the RAG corpus (build once if absent); attach parsed times + channel sets."""
    if not CORPUS_JSON.exists():
        save_corpus()
    records = json.loads(CORPUS_JSON.read_text())
    for r in records:
        r["_start"], r["_end"] = _parse(r["start"]), _parse(r["end"])
        r["_channels"] = set(r["channels"])
    return records


def past_corpus(corpus: list[dict], event_start: pd.Timestamp) -> list[dict]:
    """Anti-leakage guard (R3): keep only neighbors that ENDED before the event started."""
    return [r for r in corpus if r["_end"] < event_start]


def query_weights(context: dict) -> dict:
    """Attribution weights from top_channels, normalised to sum 1 (leak-free query)."""
    total = sum(pct for _, pct in context["top_channels"]) or 1.0
    return {ch: pct / total for ch, pct in context["top_channels"]}


def tversky_similarity(query_w: dict, neigh: set, beta: float) -> float:
    """Weighted Tversky index (alpha=1, given beta): shared / (union, neighbor extras * beta)."""
    inter = set(query_w) & neigh
    union = set(query_w) | neigh
    num = sum(query_w[c] for c in inter)
    den = sum(query_w.get(c, beta) for c in union)  # event channels weighted; extras -> beta
    return num / den if den else 0.0


def retrieve(context: dict, corpus: list[dict], *, k: int = DEFAULT_K, beta: float = BETA) -> dict:
    """Top-K past neighbors + novelty + per-channel prior for one live event."""
    qw = query_weights(context)
    past = past_corpus(corpus, _parse(context["start"]))

    scored = sorted(
        ({"id": r["id"], "class": r["class"], "category": r["category"],
          "locality": r["locality"], "channels": r["channels"],
          "sim": tversky_similarity(qw, r["_channels"], beta)} for r in past),
        key=lambda x: (x["sim"], x["id"]), reverse=True,  # id as deterministic tie-break
    )
    max_sim = scored[0]["sim"] if scored else 0.0
    prior = {}
    for ch in qw:
        classes = pd.Series([r["class"] for r in past if ch in r["_channels"]])
        prior[ch] = {"past_count": int(classes.size),
                     "dominant_class": classes.mode().iat[0] if classes.size else None}

    return {
        "event_id": context["event_id"],
        "neighbors": scored[:k],
        "max_sim": max_sim,          # familiarity 0-1
        "novelty": 1.0 - max_sim,    # honest novelty: high => unlike anything past
        "channel_prior": prior,
        "params": {"k": k, "beta": beta},
    }


# SHORT EXPLANATION: F3 success-test -- R3 invariant over ALL 120 events + show event 33.
def main() -> None:
    corpus = load_corpus()
    contexts = json.loads((config.CACHE_DIR / "m3_event_contexts.json").read_text())
    by_id = {r["id"]: r for r in corpus}

    leaks = []
    for ctx in contexts:
        ev_start = _parse(ctx["start"])
        for nb in retrieve(ctx, corpus)["neighbors"]:
            if not (by_id[nb["id"]]["_end"] < ev_start):
                leaks.append((ctx["event_id"], nb["id"]))
    assert not leaks, f"R3 anti-leakage VIOLATED: {leaks[:10]}"

    ctx33 = next(c for c in contexts if c["event_id"] == 33)
    res = retrieve(ctx33, corpus)
    dom = set(ctx33["dominant_channels"])
    assert res["neighbors"] and dom & set(res["neighbors"][0]["channels"]), \
        "top neighbor of event 33 shares no dominant channel"
    print(f"=== M4 Fase 3 -- retriever OK · R3 invariant holds over {len(contexts)} events ===")
    print(f"event 33: max_sim={res['max_sim']:.3f} novelty={res['novelty']:.3f}")
    print(f"top-{res['params']['k']} neighbors (Tversky alpha=1 beta={res['params']['beta']}):")
    for nb in res["neighbors"]:
        print(f"  {nb['id']:>8} sim={nb['sim']:.3f} class={nb['class']} shared="
              f"{sorted(dom & set(nb['channels']))}")


if __name__ == "__main__":
    main()
