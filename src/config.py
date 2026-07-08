"""Anchor constants for the M1 detector and the trustworthy layer [2][3][4].

Values mirror ``esa-adb/mission2_experiments.py`` so the whole pipeline stays
consistent. This module holds ONLY constants + path anchors — no logic.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
ESA = REPO / "esa-adb"  # ESA-ADB clone (detector + metric source; removed after cleanup)
ALGO = ESA / "TimeEval-algorithms" / "subsequence_if" / "algorithm.py"
PREP_DIR = REPO / "data" / "preprocessed_subset" / "multivariate" / "ESA-Mission2-semi-supervised"
TRAIN_CSV = PREP_DIR / "21_months.train.csv"
TEST_CSV = PREP_DIR / "21_months.test.csv"
LABELS_CSV = REPO / "data" / "ESA-Mission2" / "labels.csv"
CACHE_DIR = REPO / "data" / "cached"  # persisted model + scores (reused by tests / [2])

# --- Dataset: Mission2 lightweight subset ----------------------------------
# The 11 target channels of the M2 lightweight benchmark (channel_18 .. channel_28).
TARGET_CHANNELS: list[str] = [f"channel_{i}" for i in range(18, 29)]

# --- Detector [1] hyperparameters (subsequence_if, from mission2_experiments.py) ---
WINDOW_SIZE: int = 17
N_TREES: int = 200
RANDOM_STATE: int = 42

# --- Metric (ESAScores, event-wise) ----------------------------------------
BETA: float = 0.5  # F0.5 -> precision-weighted
SELECT_LABELS: dict[str, list[str]] = {"Category": ["Rare Event", "Anomaly"]}
BASELINE_F05: float = 0.949  # paper Table 2, M2 lightweight, Windowed iForest

# --- Uncertainty [2] -------------------------------------------------------
# Miscoverage level for conformal prediction (1 - alpha = target coverage).
CONFORMAL_ALPHA: float = 0.1

# Rolling (causal) recalibration [2b]: counter the temporal drift that breaks a
# single fixed calibration. For each block of BLOCK windows, calibrate against the
# ROLLING_N_CALIB most recent INDEPENDENT normal windows strictly in the past.
# Tuned so coverage on held-out normals lands near CONFORMAL_ALPHA (see rolling.py).
ROLLING_N_CALIB: int = 20000
ROLLING_BLOCK: int = 20000

# --- LLM layer [4] ---------------------------------------------------------
# Read from environment, never hardcode secrets. Provider = Anthropic (Claude).
LLM_API_KEY_ENV: str = "ANTHROPIC_API_KEY"
LLM_MODEL: str = os.getenv("ESA_LLM_MODEL", "claude-sonnet-5")


def require_llm_api_key() -> str:
    """Return the LLM API key or raise a clear error if it is not configured."""
    key = os.getenv(LLM_API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{LLM_API_KEY_ENV} not configured. Export it before running the LLM layer [4]."
        )
    return key
