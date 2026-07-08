#!/usr/bin/env python3
"""M2 · shared metric helper — event-wise ESAScores on a chosen time sub-period.

M1's `evaluation.py` scores the WHOLE test. M2 needs to score arbitrary sub-periods
(validation third, test-final third) from a per-window binary prediction. This module
reuses ESA's ESAScores metric (untouched) and mirrors `evaluation.py`'s label building
exactly, so numbers stay comparable with M1.

Two pieces:
  - `windows_to_points`: map a per-window 0/1 prediction to per-point, using the SAME
    `np.pad(result, ws//2)` convention as ESA's `algorithm.py:132` (point = window center).
  - `ew_scores`: restrict labels + predictions to [lo, hi) and call ESAScores.
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

HALF = config.WINDOW_SIZE // 2  # 8: window center offset (== ESA's pad width)


# SHORT EXPLANATION: load the anomaly catalog with its Category column attached, exactly
# like M1's evaluation.py (same time-zone handling and test-range clipping), so the metric
# sees identical labels.
def load_labels() -> pd.DataFrame:
    """Labels with Category merged, tz-naive, clipped to the test time range."""
    labels = pd.read_csv(config.LABELS_CSV, parse_dates=["StartTime", "EndTime"])
    labels["StartTime"] = labels["StartTime"].apply(lambda t: t.tz_localize(None))
    labels["EndTime"] = labels["EndTime"].apply(lambda t: t.tz_localize(None))

    test_ts = pd.read_csv(config.TEST_CSV, usecols=["timestamp"], parse_dates=["timestamp"])
    tmin = test_ts["timestamp"].dt.tz_localize(None).min()
    tmax = test_ts["timestamp"].dt.tz_localize(None).max()
    labels = labels[(labels["StartTime"] >= tmin) & (labels["EndTime"] <= tmax)]

    types_path = str(config.LABELS_CSV).replace("labels.csv", "anomaly_types.csv")
    types = pd.read_csv(types_path)
    cols = list(types.columns[-4:])  # Category, Dimensionality, Locality, Length
    for c in cols:
        labels[c] = ""
    for _, row in types.iterrows():
        labels.loc[labels["ID"] == row["ID"], cols] = row[cols].values
    return labels


# SHORT EXPLANATION: turn a per-window 0/1 prediction into a per-point 0/1 array, placing
# each window's decision at its center point -- the same shift ESA's algorithm.py applies.
def windows_to_points(window_idx: np.ndarray, window_binary: np.ndarray, n_points: int) -> np.ndarray:
    """Scatter window predictions to their center points (idx + HALF)."""
    pred = np.zeros(n_points, dtype=np.uint8)
    pred[window_idx + HALF] = window_binary.astype(np.uint8)
    return pred


# SHORT EXPLANATION: score one time window [lo, hi). Restrict predictions and labels to
# that range and hand them to ESA's event-wise metric. Returns the full ESAScores dict.
def ew_scores(point_pred: np.ndarray, timestamps: pd.Series, labels: pd.DataFrame,
              lo, hi) -> dict:
    """Event-wise ESAScores over [lo, hi): F0.5 / precision / recall etc."""
    mask = (timestamps >= lo) & (timestamps < hi)
    tds = pd.DataFrame({"Timestamp": timestamps[mask].to_numpy(),
                        "Score": point_pred[mask].astype(np.uint8)})
    lab = labels[(labels["StartTime"] >= lo) & (labels["EndTime"] < hi)]
    y_true = lab[lab["Channel"].isin(config.TARGET_CHANNELS)].drop(columns=["Channel"])
    metric = ESAScores(betas=config.BETA, select_labels=config.SELECT_LABELS)
    return metric.score(y_true, tds)
