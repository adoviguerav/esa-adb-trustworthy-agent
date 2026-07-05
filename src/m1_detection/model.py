#!/usr/bin/env python3
"""M1 · Model — Windowed iForest detector (subsequence_if).

Runs ESA's own detector (`TimeEval-algorithms/subsequence_if/algorithm.py`, PyOD
IForest) via its JSON CLI: train on 21_months.train.csv, execute on 21_months.test.csv.
Persists the trained model + the point scores to data/cached/ so evaluation and the
trustworthy layer [2] reuse them without retraining.

Detector code is ESA's, untouched. This file only wires the CLI and caches outputs.
Config in src/config.py mirrors esa-adb/mission2_experiments.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

MODEL_PKL = config.CACHE_DIR / "model.pkl"
SCORES_TEST = config.CACHE_DIR / "scores_test.csv"  # binary point scores (predict + pad)


def run_algorithm(execution_type: str, extra: dict) -> None:
    """Invoke ESA's algorithm.py via its JSON CLI (train or execute)."""
    cfg = {
        "executionType": execution_type,
        "customParameters": {
            "window_size": config.WINDOW_SIZE,
            "n_trees": config.N_TREES,
            "random_state": config.RANDOM_STATE,
            "target_channels": config.TARGET_CHANNELS,
        },
    }
    cfg.update(extra)
    print(f"\n=== algorithm.py [{execution_type}] ===")
    subprocess.run([sys.executable, str(config.ALGO), json.dumps(cfg)], check=True)


def main() -> None:
    for p in (config.ALGO, config.TRAIN_CSV, config.TEST_CSV):
        if not p.exists():
            sys.exit(f"Missing required input: {p}")
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    run_algorithm("train", {"dataInput": str(config.TRAIN_CSV), "modelOutput": str(MODEL_PKL)})
    run_algorithm("execute", {
        "dataInput": str(config.TEST_CSV),
        "modelInput": str(MODEL_PKL),
        "dataOutput": str(SCORES_TEST),
    })
    print(f"\nModel cached  -> {MODEL_PKL}")
    print(f"Scores cached -> {SCORES_TEST}")


if __name__ == "__main__":
    main()
