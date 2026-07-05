#!/usr/bin/env python3
"""M1 · Evaluation — event-wise ESAScores on the detector output.

Reads the cached point scores (data/cached/scores_test.csv from model.py), rebuilds
the labels + scored-timestamps exactly as ESA's timeeval/core/experiments.py::evaluate
does (lines 339-355 and 124/154-155), and calls ESA's ESAScores metric.

Metric code is ESA's, untouched. This file only wires inputs -> ESAScores.
Target (paper Table 2): EW_F_0.50 = 0.949.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/ on path
import config  # noqa: E402

sys.path.insert(0, str(config.ESA))  # ESAScores lives in ESA's timeeval package
from timeeval.metrics import ESAScores  # noqa: E402
from sklearn.preprocessing import MinMaxScaler  # noqa: E402

SCORES_TEST = config.CACHE_DIR / "scores_test.csv"


def scale_scores(y_scores: np.ndarray) -> np.ndarray:
    """Copied from core/experiments.py::Experiment.scale_scores (MinMax per column)."""
    y_scores = np.asarray(y_scores, dtype=np.float32)
    if y_scores.ndim == 1:
        y_scores = np.expand_dims(y_scores, -1)
    for i in range(y_scores.shape[-1]):
        mask = np.isinf(y_scores[..., i]) | np.isneginf(y_scores[..., i]) | np.isnan(y_scores[..., i])
        scores = y_scores[..., i][~mask]
        if len(scores) > 0:
            y_scores[..., i][~mask] = MinMaxScaler().fit_transform(scores.reshape(-1, 1)).ravel()
    return y_scores


def build_labels_and_scores(scores_path: Path):
    """Copied from core/experiments.py::Experiment.__init__ (lines 339-355)."""
    labels_df = pd.read_csv(config.LABELS_CSV, parse_dates=["StartTime", "EndTime"])
    labels_df["StartTime"] = labels_df["StartTime"].apply(lambda t: t.tz_localize(None))
    labels_df["EndTime"] = labels_df["EndTime"].apply(lambda t: t.tz_localize(None))

    test_data_scores = pd.read_csv(config.TEST_CSV, usecols=["timestamp"], parse_dates=[0])
    test_data_scores.rename(columns={"timestamp": "Timestamp"}, inplace=True)
    test_data_scores["Score"] = np.uint8(0)

    labels_df = labels_df[labels_df["StartTime"] >= test_data_scores["Timestamp"].min()]
    labels_df = labels_df[labels_df["EndTime"] <= test_data_scores["Timestamp"].max()]

    anomaly_types_path = str(config.LABELS_CSV).replace("labels.csv", "anomaly_types.csv")
    anomaly_types_df = pd.read_csv(anomaly_types_path)
    columns_to_copy = anomaly_types_df.columns[-4:]
    for col in columns_to_copy:
        labels_df[col] = ""
    for _, row in anomaly_types_df.iterrows():
        labels_df.loc[labels_df["ID"] == row["ID"], columns_to_copy] = row[columns_to_copy].values

    y_scores = np.loadtxt(scores_path, delimiter=",")
    y_scores = scale_scores(y_scores)
    test_data_scores["Score"] = y_scores.max(axis=1).astype(np.uint8)
    return labels_df, test_data_scores


def evaluate() -> dict:
    """Compute event-wise ESAScores from the cached detector output. Returns the dict."""
    if not SCORES_TEST.exists():
        sys.exit(f"Missing cached scores: {SCORES_TEST}. Run model.py first.")
    labels_df, test_data_scores = build_labels_and_scores(SCORES_TEST)
    y_true = labels_df[labels_df["Channel"].isin(config.TARGET_CHANNELS)].drop(columns=["Channel"])
    metric = ESAScores(betas=config.BETA, select_labels=config.SELECT_LABELS)
    return metric.score(y_true, test_data_scores)


def main() -> None:
    result = evaluate()
    print("\n=== RESULT (ESAScores, event-wise) ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"\nEW_F_0.50 = {result.get('EW_F_0.50')}   (paper target: {config.BASELINE_F05})")


if __name__ == "__main__":
    main()
