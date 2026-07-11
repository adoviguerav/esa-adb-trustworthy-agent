"""[4 · RAG] Build the anomaly corpus: the case base the retriever searches.

OFFLINE, once. labels.csv (per-channel, N rows per anomaly) is aggregated per ID and
joined with anomaly_types.csv (one row per ID) into 644 structured records. This corpus
is the RAG ground truth -- the retriever later matches a live event's channel set against
it. `Length` in anomaly_types is CATEGORICAL (Subsequence/Point), NOT a duration: the real
duration is derived from labels (end - start), never from Length.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ on path
import config  # noqa: E402

LABELS_CSV = config.LABELS_CSV
TYPES_CSV = config.LABELS_CSV.parent / "anomaly_types.csv"
CORPUS_JSON = config.CACHE_DIR / "m4_anomaly_corpus.json"


def build_corpus() -> list[dict]:
    """labels join anomaly_types on ID -> one record per anomaly (channels aggregated)."""
    labels = pd.read_csv(LABELS_CSV, parse_dates=["StartTime", "EndTime"])
    types = pd.read_csv(TYPES_CSV).set_index("ID")

    orphans = set(labels["ID"]) ^ set(types.index)
    if orphans:
        raise ValueError(f"labels/anomaly_types ID mismatch (orphans): {sorted(orphans)[:10]}")

    grouped = labels.groupby("ID")
    span = grouped.agg(start=("StartTime", "min"), end=("EndTime", "max"))
    channels = grouped["Channel"].apply(lambda s: sorted(set(s)))

    records = []
    for anomaly_id in sorted(types.index, key=lambda x: int(x.split("_")[1])):
        start, end = span.loc[anomaly_id, "start"], span.loc[anomaly_id, "end"]
        row = types.loc[anomaly_id]
        records.append({
            "id": anomaly_id,
            "class": row["Class"],
            "category": row["Category"],
            "locality": row["Locality"],
            "channels": channels.loc[anomaly_id],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_sec": (end - start).total_seconds(),
        })
    return records


def save_corpus() -> list[dict]:
    """Build and persist the corpus cache (D9)."""
    records = build_corpus()
    CORPUS_JSON.write_text(json.dumps(records, indent=2))
    return records


# SHORT EXPLANATION: Fase 2 success-test -- build, then assert the invariants.
def main() -> None:
    records = save_corpus()
    assert len(records) == 644, f"expected 644 records, got {len(records)}"
    assert all(r["duration_sec"] >= 0 for r in records), "found end < start"
    covered = {c for r in records for c in r["channels"]}
    missing = set(config.TARGET_CHANNELS) - covered
    assert not missing, f"M2 target channels missing from corpus: {sorted(missing)}"
    assert json.loads(CORPUS_JSON.read_text()) == records, "round-trip JSON mismatch"

    years = sorted({r["start"][:4] for r in records})
    print(f"=== M4 Fase 2 -- corpus built: {len(records)} anomalies ===")
    print(f"channels 18-28 all covered · years {years[0]}-{years[-1]} · 0 orphans")
    print(f"example: {json.dumps(records[0], indent=2)}")


if __name__ == "__main__":
    main()
