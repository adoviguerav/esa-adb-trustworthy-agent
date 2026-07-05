"""Anchor constants for the trustworthy layer [2][3][4].

Values mirror the detector reproduction in ``repro/run_subsequence_if.py`` and
``esa-adb/mission2_experiments.py`` so the whole pipeline stays consistent. This
module holds ONLY constants — no logic, no I/O.
"""
from __future__ import annotations

import os

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
