# Trustworthy Anomaly Agent sobre ESA-ADB

> Detección de anomalías en telemetría real de satélite con **incertidumbre calibrada**, **explicabilidad por canal** e **informe grounded** que no alucina.

*(Proyecto en construcción. El repo público destino es `esa-adb-trustworthy-agent`.)*

## Descripción

Un operador de misión recibe telemetría de cientos de sensores y no tiene ojos para vigilarlos todos. La detección por umbral fijo captura lo trivial; las anomalías **contextuales** (raras en su contexto) y **colectivas** (combinación imposible de canales) requieren ML. Pero el benchmark oficial de ESA (ESA-ADB) demuestra que los detectores estándar aún no sirven para deployment real, y que ningún algoritmo gana siempre (*No Free Lunch*): un operador no puede confiar en un flag ciego.

Este proyecto ataca ese hueco. Sobre el dataset oficial **ESA-ADB**, construye una **capa de confianza** encima de una detección sólida: cuantifica la incertidumbre de cada alarma, señala qué canales la provocan, y emite un informe legible que distingue "seguro" de "no sé" — con un guardrail LLM-as-judge que bloquea cualquier afirmación no soportada por los datos.

Pensado para ingenieros de operaciones de misión, y diseñado como bloque edge-deployable (argumentado) para recortar downlink.

## Stack

- **Python** (CPU — corre en un portátil sin GPU para el MVP).
- **PyOD** — Window iForest (detector).
- **MAPIE / conformal prediction** (o MC-dropout) — incertidumbre calibrada.
- **matplotlib / plotly** — visualización de atribución por canal.
- **LLM vía API** con prompt de grounding estricto — generador + juez.

## Quick start

*(Pendiente de implementación. Estructura prevista:)*

```bash
git clone <repo>
cd esa-adb-trustworthy-agent
pip install -r requirements.txt

# Nivel Demo — corre la capa trustworthy desde scores cacheados, SIN GPU:
jupyter notebook notebooks/demo.ipynb
```

Para reproducir la detección completa, seguir las instrucciones de descarga del dataset en `data/` (ESA-ADB Misión2 subconjunto ligero desde Zenodo).

## Estructura de carpetas

```
├── data/cached_scores/   scores precalculados → demo sin GPU
├── src/                  detect · uncertainty · explain · report
├── notebooks/demo.ipynb  recorrido reproducible
└── results/              figuras y métricas
```

## Reproducibilidad — 3 niveles

| Nivel | Qué corre | Hardware |
|---|---|---|
| **Demo** | Capa trustworthy [2]+[3]+[4] desde scores cacheados | Cualquier portátil, sin GPU |
| **Ligero** | Detector CPU + capas sobre Misión2 ligero | Mac/PC normal |
| **Oficial** *(opcional)* | Stack Docker + detector deep oficial | Linux + GPU NVIDIA |

El diferencial es siempre reproducible sin hardware pesado.

## Documentación interna

- [`PRD.md`](PRD.md) — problema, features, acceptance criteria, fases.
- [`CLAUDE.md`](CLAUDE.md) — guía de arquitectura y reglas para el desarrollo asistido.
- [`base.md`](base.md) — design doc con el razonamiento y las 11 decisiones de diseño.

## Créditos y licencia

Construido **sobre** el benchmark ESA-ADB, no lo modifica. Créditos a **ESA/ESOC**, **Airbus Defence and Space** y **KP Labs** (`github.com/kplabs-pl/ESA-ADB`, MIT). La reproducción usa el detector `subsequence_if` y la métrica `ESAScores` del framework **TimeEval** (incluido en el repo ESA-ADB, MIT), y **PyOD** para el Isolation Forest estándar (Liu et al., 2008).

Si usas este trabajo, cita ESA-ADB y TimeEval:

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

*Licencia del dataset Zenodo pendiente de verificar antes de publicación. Licencia del repo a definir.*
*En la fase de empaquetado, el código de ESA/TimeEval que se copie a `src/` llevará su cabecera de licencia MIT + un fichero `NOTICE` con esta atribución.*
