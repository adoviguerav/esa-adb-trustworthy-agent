#!/usr/bin/env python3
"""M3 · [4] Channel metadata + shared relations (grounded hints for the LLM).

Names are anonymised (subsystem_1, physical_unit_9, group N) but the RELATIONS are
real: channels 21-24 share physical_unit_9 and group 2; 25-28 share group 1; 18-20
share group 5. When an event flags several channels that share a unit/group, that is
a grounded, RELATIVE hint of a coupled fault -- offered as hypothesis (D4), never as
absolute cause. M3 only provides the relation; the LLM [4] interprets it.

subsystem_1 is shared by ALL 11 target channels -> zero discriminating power -> excluded
from relations (a relation that everything satisfies carries no signal).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

CHANNELS_CSV = config.LABELS_CSV.parent / "channels.csv"  # data/ESA-Mission2/channels.csv


# SHORT EXPLANATION: load per-channel metadata for our 11 channels. physical_unit is
# None when the CSV leaves it blank (channels 18-20, 25-28 have no unit).
def load_channel_meta() -> dict[str, dict]:
    """Map channel -> {subsystem, physical_unit (None if blank), group} for 18-28."""
    df = pd.read_csv(CHANNELS_CSV)
    df = df[df["Channel"].isin(config.TARGET_CHANNELS)]
    meta = {}
    for _, r in df.iterrows():
        unit = r["Physical Unit"]
        meta[r["Channel"]] = {
            "subsystem": r["Subsystem"],
            "physical_unit": None if pd.isna(unit) else str(unit),
            "group": int(r["Group"]),
        }
    return meta


# SHORT EXPLANATION: among a set of flagged channels, which SUBSETS share a group or a
# physical unit. Only clusters of >=2 count (a relation needs at least two channels).
# subsystem is ignored (all target channels share it -> no signal).
def shared_relations(channels: list[str], meta: dict[str, dict] | None = None) -> dict:
    """Grounded relations among flagged channels: shared groups and shared physical units."""
    meta = meta or load_channel_meta()
    by_group: dict[str, list[str]] = {}
    by_unit: dict[str, list[str]] = {}
    for ch in channels:
        if ch not in meta:
            continue
        by_group.setdefault(f"group_{meta[ch]['group']}", []).append(ch)  # str key -> JSON-safe
        unit = meta[ch]["physical_unit"]
        if unit is not None:
            by_unit.setdefault(unit, []).append(ch)
    return {
        "shared_group": {g: chs for g, chs in by_group.items() if len(chs) >= 2},
        "shared_unit": {u: chs for u, chs in by_unit.items() if len(chs) >= 2},
    }


# SHORT EXPLANATION: the "did it work?" check -- 11 channels, the known clusters
# (21-24 share physical_unit_9; groups 5/2/1), and shared_relations behaves.
def verify() -> None:
    """Success-test for M3 Phase 4."""
    meta = load_channel_meta()

    # (a) all 11 target channels loaded.
    assert set(meta) == set(config.TARGET_CHANNELS), "missing/extra channels"

    # (b) known relations from the data: 21-24 share physical_unit_9; group clusters 5/2/1.
    unit9 = [c for c, m in meta.items() if m["physical_unit"] == "physical_unit_9"]
    assert set(unit9) == {f"channel_{i}" for i in range(21, 25)}, f"physical_unit_9 != 21-24: {unit9}"
    groups = {c: m["group"] for c, m in meta.items()}
    assert all(groups[f"channel_{i}"] == 5 for i in (18, 19, 20)), "18-20 not group 5"
    assert all(groups[f"channel_{i}"] == 2 for i in (21, 22, 23, 24)), "21-24 not group 2"
    assert all(groups[f"channel_{i}"] == 1 for i in (25, 26, 27, 28)), "25-28 not group 1"

    # (c) shared_relations behaves: coupled pair reports the relation; unrelated pair empty.
    rel_coupled = shared_relations(["channel_22", "channel_23"], meta)
    assert rel_coupled["shared_unit"].get("physical_unit_9") == ["channel_22", "channel_23"]
    assert "group_2" in rel_coupled["shared_group"]
    rel_none = shared_relations(["channel_18", "channel_25"], meta)  # group 5 vs 1, no unit
    assert not rel_none["shared_group"] and not rel_none["shared_unit"], "false relation reported"

    print("\n=== M3 Phase 4 success-test ===")
    print(f"  (a) channels loaded  : {len(meta)} (18-28)  OK")
    print(f"  (b) known relations  : physical_unit_9 = 21-24; groups 18-20->5, 21-24->2, 25-28->1  OK")
    print(f"  (c) shared_relations : coupled pair -> {rel_coupled['shared_unit']}  |  unrelated -> empty  OK")


def main() -> None:
    verify()


if __name__ == "__main__":
    main()
