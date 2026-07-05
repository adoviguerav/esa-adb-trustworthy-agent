# Environment deviations from ESA-ADB `environment.yml`

We reproduce ESA-ADB **without conda and without Docker** (local `.venv`, Python 3.9.20).
Their `esa-adb/environment.yml` pins the conda env. We install the same packages via `pip`.

**No source code of `esa-adb/` has been modified.** Only Python packages installed in `.venv`.

## Matched exactly (critical)

| Package | env.yml | installed | Why it matters |
|---|---|---|---|
| numpy | 1.21.* | 1.21.6 | `eif` C-extension ABI breaks on numpy 2.x |
| pandas | 1.5.* | 1.5.3 | preprocessing dataframe ops |
| portion | 2.4.1 | 2.4.1 | interval math in metrics |
| durations | 0.3.* | 0.3.3 | imported by timeeval docker adapter |
| numpyencoder | 0.3.* | 0.3.2 | JSON serialization |
| prts | 1.0.0.3 | 1.0.0.3 | timeeval `other_metrics` (range-based P/R) |
| dask[distributed] | 2021.5.* | 2021.5.1 | imported by `timeeval/__init__` (TimeEval class) |
| click | 8.0.2 | 8.0.2 | pinned by ESA for dask compat |
| eif | (repo detector) | 2.0.2 | the detector itself |

## Deviations (do NOT affect preprocessed telemetry data)

| Package | env.yml | installed | Justification |
|---|---|---|---|
| statsmodels | 0.12.* | 0.14.1 | Only used by `DatasetAnalyzer` (adfuller/kpss) to write stationarity **metadata** to `datasets.csv`. Does NOT alter the `.npy`/labels used for detection+scoring. Downgrading risks scipy/numpy dependency conflicts. |
| docker (SDK) | 4.4.* | 7.1.0 | Only needs to *import* so `import timeeval` succeeds. Docker orchestration (`mission2_experiments.py`) is NOT used — we run the algorithm locally. |
| tqdm | 4.54.* | 4.68.3 | Progress bar only. Cosmetic. |

## Detector dependency: pyod + numpy bump

The **real** `subsequence_if` detector is **PyOD `IForest` 1.1.2** (standard Isolation
Forest, sklearn under the hood) — confirmed by `TimeEval-algorithms/subsequence_if/`
(`manifest.json`, `requirements.txt: pyod==1.1.2`, `algorithm.py: from pyod.models.iforest import IForest`).
It is NOT Extended IF (`eif`). Earlier debugging that used `eif` was reproducing the wrong detector.

| Package | source | installed | Note |
|---|---|---|---|
| pyod | subsequence_if/requirements.txt (==1.1.2) | 1.1.2 | the detector |
| numpy | env.yml 1.21.* | **bumped to 1.23.5 for the runner** | pyod→numba needs numpy>=1.22 |

**numpy pin conflict, resolved:** `eif` needs numpy 1.21.6 (ABI); pyod's `numba` needs
numpy>=1.22. Since the real reproduction uses **pyod, not eif**, we bump numpy to 1.23.5
for `repro/run_subsequence_if.py`. numpy's legacy `RandomState` (Mersenne Twister) is
version-stable, so `random_state=42` gives identical IForest results — no fidelity loss.
`eif` is no longer importable, which is fine: nothing in the reproduction uses it.

## Not installed (Docker orchestration path, unused)

We do NOT build any Docker containers. The README's Docker steps are only for running
the full experiment grid via `mission?_experiments.py`. We bypass that with a minimal
local runner that calls the same Python functions directly.
