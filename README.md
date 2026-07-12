# Trustworthy Anomaly Agent on ESA-ADB

Anomaly detection on real satellite telemetry that an operator can actually act on: every alarm carries a calibrated confidence, a ranked list of the channels responsible, and a written brief whose every claim is audited against the data before it ships.

Built on **ESA-ADB**, the European Space Agency's official anomaly detection benchmark (real ESA mission telemetry, human-annotated). This project is independent and is not endorsed by ESA.

> **Start here: [`notebooks/demo.ipynb`](notebooks/demo.ipynb).**
> It is the whole system, end to end, with every output committed. Read it on GitHub to understand how it works and why it is built that way, without running a line of code. Clone it to reproduce every number below.

---

## The problem

A mission operator receives telemetry from hundreds of sensors and cannot watch them all. Fixed thresholds catch the trivial cases. The ones that matter are **contextual** (a value in range but strange for its context) and **collective** (each channel plausible on its own, the combination impossible), and those need machine learning.

But the operator is then handed a bare 0/1 flag from a model that cannot say how sure it is, cannot say where to look, and cannot say why. A flag you cannot interrogate is a flag you learn to ignore, and an ignored alert is a missed anomaly with extra steps.

## The differentiator

**The contribution is the trustworthy layer, not the detector.**

The detector is deliberately not novel: it reproduces ESA's own published baseline (F0.5 = 0.949) using ESA's own code, on a laptop. That number is the floor, not the achievement, and it doubles as a regression alarm: if a later change moves it, something broke.

What sits on top of it is the point:

- **Uncertainty** turns an arbitrary anomaly score into a calibrated, distribution-free confidence, so "I am sure" and "I have no idea" stop looking the same.
- **Attribution** names the channels that caused the detection, so triage starts at the right plot instead of all eleven.
- **A grounded LLM layer** writes the operator brief, with every figure lifted verbatim from the modules above and two guardrails in series that block anything the evidence does not support.

The detector is a replaceable part: modules 2 to 4 consume only its outputs, never its internals.

## Results

| Module | What it means | The number |
|---|---|---|
| [1] Detection | It reproduces ESA's published baseline for this benchmark subset, running on a MacBook: no Docker, no GPU, no cluster | Event-wise **F0.5 = 0.949**, the same figure ESA reports |
| [2] Uncertainty | It turns the raw score into a calibrated confidence and **derives** the threshold that separates anomaly from normal, instead of hand-picking one. At that threshold it never cried wolf | **Zero false alarms across 976,182 windows known to be normal**, at **99% precision** on the events it did flag |
| [3] Attribution | It tells you **exactly which channels carry the anomaly, and how much each one contributes** | The channel it names is one the ESA experts annotated **120 times out of 120**. Ranking by raw magnitude, the obvious approach, gets it right 74 |
| [4] Alert | It writes a report whose **every figure is deterministic**: the model contributes the prose and nothing else, and two guardrails audit it before it ships | Given 18 hand-written test briefs, it approved the 7 honest ones and **caught all 11 planted lies**. Over the 120 real events: **120 out of 120 clean** |

Every number is produced by a cell in the notebook and is traceable to the dataset. Nothing is invented.

## Architecture

```
Telemetry (ESA-ADB Mission2 lightweight, channels 18-28)
  → [1] Detection      Windowed Isolation Forest        → anomaly score per window
  → [2] Uncertainty    conformal p-values               → calibrated confidence
  → [3] Attribution    perturbation / ablation          → which channels caused it
  → [4] Alert layer    grounded brief + LLM judge       → auditable operator alert
  → [5] Streaming      no-lookahead state machine       → the whole mission, live
```

| Module | Code | In one line |
|---|---|---|
| [1] Detection | `src/m1_detection/` | ESA's `subsequence_if` run verbatim from the vendored copy: a 17-sample window over 11 channels, isolated by a standard Isolation Forest |
| [2] Uncertainty | `src/m2_uncertainty/` | Rank each score against certified-normal history to get a conformal p-value, so alpha becomes a false-alarm budget instead of a magic threshold |
| [3] Attribution | `src/m3_attribution/` | Ask the detector a counterfactual per channel (replace it with its normal baseline, re-score, measure the drop). No SHAP, no second model |
| [4] Alert layer | `src/m4_report/` | Deterministic flag when an event opens; at close, deterministic retrieval plus one generated paragraph, cleared by a lexical precheck AND an LLM judge |
| [5] Streaming | `src/m4_report/pipeline.py` | A state machine that never looks ahead. Batch and live differ only in the driver that feeds it |

**The notebook explains each of these properly, with the tradeoffs behind them.** This table is the map, not the territory.

---

## Quickstart

```bash
git clone <this-repo>
cd esa-adb-trustworthy-agent

python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Download the **ESA-Mission2** folder (3.8 GB) from Zenodo ([doi.org/10.5281/zenodo.12528696](https://doi.org/10.5281/zenodo.12528696)) and place it at `data/ESA-Mission2/`, so that `data/ESA-Mission2/labels.csv` exists. The dataset is not redistributed here.

```bash
jupyter notebook notebooks/demo.ipynb   # then run all cells, top to bottom
```

Everything runs on **CPU** (developed on a Mac laptop). No GPU, no Docker, no conda, and no clone of the ESA-ADB repository: the parts of it we need are vendored under `src/` (MIT, see [`NOTICE`](NOTICE)).

### What it costs, honestly

| Step | Cost on your machine | Cached afterwards? |
|---|---|---|
| Preprocessing (raw Zenodo channels to train/test CSVs) | about 29 minutes, once | Yes. Later runs detect the output and skip it |
| Detector training and scoring | about 11 minutes | Yes. Deterministic (seed 42): retraining reproduces the same bytes |
| Modules 2, 3 and 4 | seconds to a few minutes | Intermediate artifacts are reused |
| LLM layer | **free and offline** | The LLM cache ships with the repo |

**No API key is needed.** The committed LLM cache is not a cost saver (the model is free to run); it is a reproducibility device, because a language model is not bit-deterministic even at temperature zero, so the frozen response is the canonical reference. To regenerate briefs live instead, get a free key at [console.groq.com](https://console.groq.com), put `GROQ_API_KEY` in `.env`, and uncomment the bring-your-own-key cell in Section 4 of the notebook.

The cache rule in this repo: an artifact is committed only when recomputing it costs **money or an external dependency**, never when it merely costs time. That is why preprocessing and training run on your machine, and why exactly one artifact ships: the LLM cache.

## Repository layout

```
├── notebooks/demo.ipynb      the whole system, executable and explained (deliverable #1)
├── src/
│   ├── config.py             anchor constants (channels, hyperparameters, paths)
│   ├── m1_detection/         preprocessing, detector, ESA metric runner
│   │   └── vendor/           ESA's algorithm.py + prep utils, verbatim (MIT)
│   ├── metrics_esa/          ESA's event-wise ESAScores metric, vendored (MIT)
│   ├── m2_uncertainty/       split, conformal p-values, rolling recalibration, alpha tuning
│   ├── m3_attribution/       baseline, perturbation, event aggregation, evaluation, context
│   └── m4_report/            retrieval · generation · guardrails (precheck + judge) · pipeline
├── tests/                    regression suite, M1 to M4
├── docs/REPRODUCTION.md      how the ESA baseline was reproduced, and how the data was verified
├── data/                     download instructions (the dataset is NOT in the repo)
└── NOTICE                    attribution for the vendored ESA code and the dataset
```

---

## What this is not

Stated here because a trustworthiness project that overclaims about itself defeats its own purpose. Section 6 of the notebook covers this in full.

- **On-board deployment is argued, not certified.** Nothing here has been flown or benchmarked on flight hardware. Groq stands in as a **proxy** for a small on-prem model.
- **ESA-ADB is a ground benchmark.** Historical, already annotated. The streaming simulation is a faithful rehearsal, and a rehearsal is not a flight.
- **The system never diagnoses a root cause.** The channels are anonymized, so it cannot know what a sensor measures and does not pretend to. It detects, quantifies trust, and localizes. The "why" remains the operator's judgment.
- **The judge's golden set is an existence proof, not a statistical guarantee.** 18 hand-labelled cases prove the guardrail catches the violation types it was built for. It is not a claim about a hallucination rate in the wild.
- **This is not a state-of-the-art detector, on purpose.** It reproduces ESA's baseline.
- **Confidence is not P(anomaly).** It is calibrated control over false alarms, which is a smaller claim and a true one.

## Future work

Documented, deliberately not implemented (scope discipline, not oversight): a semantic channel catalogue grounded in a real mission catalogue; unsupervised clustering into anomaly families; a vector database for free-text knowledge (manuals, procedures), which is where embeddings would finally earn their place; action suggestion via telecommands, safety-gated and human in the loop (not done because the data does not support it: `telecommands.csv` has name and priority only, no temporal link); bounded self-refine when the judge blocks a brief; and a deep detector swap to exercise the detector-agnostic seam.

## Credits and licences

This project is built **on top of** ESA-ADB and does not modify it. All credit for the dataset and the benchmark goes to **ESA / ESOC**, **Airbus Defence and Space** and **KP Labs**. This repository is independent and carries **no ESA endorsement**.

- **Dataset:** ESA Anomaly Dataset (ESA-ADB), licence **CC BY 3.0 IGO**. Full record: [zenodo.org/records/15237121](https://zenodo.org/records/15237121). Mission1/Mission2: [doi.org/10.5281/zenodo.12528696](https://doi.org/10.5281/zenodo.12528696). Not redistributed here; download it yourself.
- **Official code:** [github.com/kplabs-pl/ESA-ADB](https://github.com/kplabs-pl/ESA-ADB) (MIT), itself built on [TimeEval](https://github.com/HPI-Information-Systems/TimeEval). The detector (`subsequence_if`), the preprocessing helpers and the `ESAScores` metric are vendored **verbatim** under `src/`. See [`NOTICE`](NOTICE) for the file-by-file attribution.
- **Paper:** [arXiv:2406.17826](https://arxiv.org/abs/2406.17826).
- **This repository's own code:** MIT (see [`LICENSE`](LICENSE)).

If you use this work, cite ESA-ADB and TimeEval:

```bibtex
@article{kotowski_european_2024,
  title   = {European {Space} {Agency} {Benchmark} for {Anomaly} {Detection} in {Satellite} {Telemetry}},
  author  = {Kotowski, Krzysztof and Haskamp, Christoph and Andrzejewski, Jacek and Ruszczak, Bogdan and Nalepa, Jakub and Lakey, Daniel and Collins, Peter and Kolmas, Aybike and Bartesaghi, Mauro and Martinez-Heras, Jose and De Canio, Gabriele},
  date    = {2024},
  publisher = {arXiv},
  doi     = {10.48550/arXiv.2406.17826}
}

@article{WenigEtAl2022TimeEval,
  title   = {TimeEval: {{A}} Benchmarking Toolkit for Time Series Anomaly Detection Algorithms},
  author  = {Wenig, Phillip and Schmidl, Sebastian and Papenbrock, Thorsten},
  date    = {2022},
  journaltitle = {Proceedings of the {{VLDB Endowment}} ({{PVLDB}})},
  volume  = {15},
  number  = {12},
  pages   = {3678--3681},
  doi     = {10.14778/3554821.3554873}
}
```
