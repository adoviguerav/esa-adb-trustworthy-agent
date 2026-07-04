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

Construido **sobre** el benchmark ESA-ADB, no lo modifica. Créditos a **ESA/ESOC**, **Airbus Defence and Space** y **KP Labs** (`github.com/kplabs-pl/ESA-ADB`, MIT). Paper: [arxiv.org/abs/2406.17826](https://arxiv.org/abs/2406.17826).

*Licencia del dataset Zenodo pendiente de verificar antes de publicación. Licencia del repo a definir.*
