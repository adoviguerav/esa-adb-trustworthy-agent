# Reproduction of ESA-ADB Mission2-lightweight — Windowed iForest

**Result: `EW_F_0.50 = 0.9487` vs paper target `0.949`.** Reproduced with ESA's own
code, **no Docker, no conda**, on Mac CPU.

| Metric (event-wise) | Paper (Table 2) | Ours |
|---|---|---|
| EW_F_0.50 | 0.949 | 0.94866 |
| EW_precision | 0.951 | 0.95085 |
| EW_recall | 0.940 | 0.94000 |

## What runs (all ESA code, ours is thin glue only)

All ESA files are vendored verbatim under `src/` (MIT, see `NOTICE`) — since M5 fase 0
the pipeline runs **without the esa-adb clone**, verified end-to-end (preprocessing
diff = 0 against the golden output; retrained model byte-identical; same 0.9487).

```
Zenodo raw ESA-Mission2  (data/ESA-Mission2/)
  → [preprocessing]  src/m1_detection/preprocessing.py
                     (ESA's Mission2_semiunsupervised_prep_from_raw.py, channel subset;
                      vendored deps in src/m1_detection/vendor/{timeeval_min,prep_utils})
  → 21_months.train.csv / 21_months.test.csv   (channels 18-28 + 4 telecommands)
  → [detector]  src/m1_detection/vendor/algorithm.py  (verbatim subsequence_if, via subprocess)
                = PyOD IForest (standard Isolation Forest, Liu 2008), window=17, n_trees=200, seed=42
  → data/cached/scores_test.csv (binary 0/1 per point: clf.predict() + np.pad)
  → [metric]  src/metrics_esa (vendored timeeval.metrics.ESAScores)
              betas=0.5, select_labels={"Category": ["Rare Event", "Anomaly"]}
  → EW_F_0.50 = 0.9487
```

**Only change vs ESA:** no Docker orchestration (we call `algorithm.py` + `ESAScores`
directly). The detector is `subsequence_if` = **standard IF (pyod)**, NOT `eif`/Extended —
see the note in CLAUDE.md. Runner: `src/m1_detection/model.py`. Env: `docs/ENV_DEVIATIONS.md`.

## Preprocessing verification (independent of the detector / the 0.949)

Checked BEFORE any detector output, against three external ground truths:

| # | Check | Ground truth | Result |
|---|---|---|---|
| 1 | Grid length ×4 splits (148801 / 729601 / 1464001 / 3067201) | ESA shipped `datasets.csv` | ✅ exact |
| 2 | Max anomaly length ×4 splits (540 / 8049 / 8049 / 93029) | ESA shipped `datasets.csv` | ✅ exact |
| 3 | 18s spacing between samples | resample invariant | ✅ |
| 4 | Train ≤ 2001-10-01 < test (1-sample overlap = ESA floor/ceil design) | ESA split logic | ✅ |
| 5 | is_anomaly ∈ {0,1,2} | label domain | ✅ |
| 6 | Value vs raw pickle (channel_18, zero-order-hold) | Zenodo raw data | ✅ |

Check 1 also closes the channel-subset risk: the grid length matches ESA's 104-dim
reference exactly, proving that dropping the other channels did not change the time grid.

## How to run

```bash
# 0. From the repo root, venv active (see requirements.txt). No esa-adb clone needed.

# 1. Preprocess raw Zenodo data -> train/test CSVs (~30 min, one-time)
python src/m1_detection/preprocessing.py data/ESA-Mission2

# 2. Detector: train + score (~11 min, deterministic seed=42)
PYTHONPATH=src python src/m1_detection/model.py

# 3. Metric
PYTHONPATH=src python src/m1_detection/evaluation.py   # -> EW_F_0.50 = 0.9487
```

The demo notebook (`notebooks/demo.ipynb`) runs these same steps as cells.
