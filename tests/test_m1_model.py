"""M1 · Model+Evaluation regression test.

Runs the event-wise metric on the cached detector scores and asserts the paper number
(EW_F_0.50 = 0.949) is reproduced. This is the success-test made repeatable: if the
detector or the metric wiring ever breaks, the number drifts and this fails.

Run: pytest tests/test_m1_model.py -v
Requires: data/cached/scores_test.csv (run src/m1_detection/model.py first).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402
from m1_detection import evaluation  # noqa: E402

CACHED_SCORES = config.CACHE_DIR / "scores_test.csv"

pytestmark = pytest.mark.skipif(
    not CACHED_SCORES.exists(),
    reason="cached scores missing; run src/m1_detection/model.py first",
)


def test_reproduces_paper_f05():
    """EW_F_0.50 within 0.001 of our reproduced 0.9487 (paper Table 2: 0.949)."""
    result = evaluation.evaluate()
    assert abs(result["EW_F_0.50"] - 0.9487) < 1e-3


def test_precision_and_recall():
    """EW precision/recall match the paper (0.951 / 0.940)."""
    result = evaluation.evaluate()
    assert abs(result["EW_precision"] - 0.951) < 2e-3
    assert abs(result["EW_recall"] - 0.940) < 2e-3
