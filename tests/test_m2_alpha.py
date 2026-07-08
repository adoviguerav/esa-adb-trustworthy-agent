"""M2 · alpha-selection tests.

Locks the two-alpha story from the cached choice (`alpha_choice.npz`):
  - the optimised alpha* does no worse than the budget alpha on validation F0.5;
  - alpha* is very low (F0.5 is precision-weighted -> pushes to the p-floor);
  - the budget alpha (0.05) floods false events -> weak F0.5 (the two alphas ARE different);
  - the winner variant has the best validation F0.5 (selection is honest).

NOTE on the guarantee: budget-alpha coverage ~= alpha only holds SAME-EPOCH (see
test_m2_conformal). Across the chronological split it is inflated by drift/bursts
(measured, not a bug), so we do NOT assert "FP ~ alpha" on validation here.

Run: pytest tests/test_m2_alpha.py -v
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402

ALPHA_CHOICE = config.CACHE_DIR / "alpha_choice.npz"

pytestmark = pytest.mark.skipif(
    not ALPHA_CHOICE.exists(),
    reason="alpha_choice.npz missing; run src/m2_uncertainty/alpha.py first",
)


def _load():
    return np.load(ALPHA_CHOICE)


def test_optimized_not_worse_than_budget():
    """alpha* F0.5 >= F0.5 at the grid's top (0.05 == budget alpha), both on validation."""
    d = _load()
    assert d["best_fixed"] >= d["f05_fixed"][-1] - 1e-9
    assert d["best_rolling"] >= d["f05_rolling"][-1] - 1e-9


def test_alpha_star_is_low():
    """Precision-weighted F0.5 pushes alpha* very low (near the conformal p-floor)."""
    d = _load()
    assert float(d["alpha_fixed"]) <= 1e-3


def test_budget_alpha_floods():
    """Budget alpha (0.05) marks ~5% of windows -> thousands of false events -> weak F0.5.

    This is the whole reason there are TWO alphas: the guarantee alpha is useless for F0.5.
    """
    d = _load()
    assert d["f05_fixed"][-1] < 0.1  # grid[-1] == 0.05 == budget alpha


def test_winner_has_best_validation_f05():
    """The cached winner is the variant with the higher validation F0.5."""
    d = _load()
    winner = str(d["winner"])
    assert winner in ("fixed", "rolling")
    if winner == "fixed":
        assert d["best_fixed"] >= d["best_rolling"]
    else:
        assert d["best_rolling"] >= d["best_fixed"]
