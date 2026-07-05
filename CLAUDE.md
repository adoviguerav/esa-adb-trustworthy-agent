# Trustworthy Anomaly Agent sobre ESA-ADB

Agente que detecta anomalías en telemetría real de satélite (dataset oficial ESA-ADB), cuantifica su incertidumbre, explica qué canales la provocan y emite un informe grounded y auditable vía una capa LLM que no alucina. Proyecto público, amplificador de la candidatura ESA (Req. 20687).

## Función core

Sobre telemetría multivariante real: detectar → cuantificar incertidumbre calibrada → localizar canales responsables → informe legible y grounded (generador + juez LLM-as-judge). El diferenciador es la **capa trustworthy [2]+[3]+[4]**, no la detección.

## Arquitectura resumida

```
Telemetría ESA-ADB (Misión2 ligero, canales 18-28)
  → [1] Detector Windowed iForest (subsequence_if, pyod, CPU) → score/ventana  [interfaz fija D7]
  → [2] Incertidumbre (conformal/MAPIE o MC-dropout) → confianza calibrada + banda U
  → [3] Atribución por canal (feature contribution)  → canales responsables
  → [4] Capa LLM: Generador (grounded, refuse-when-unsure) + Juez (guardrail anti-alucinación)
  → [5] Demo/README reproducible
```

Todo tras [1] recibe la interfaz fija `scores + ventana + datos` (D7): el detector es intercambiable.

## Stack

- **Python** (CPU, corre en Mac M5 sin GPU/Docker para el MVP).
- **`subsequence_if`** — Windowed **Isolation Forest ESTÁNDAR** (Liu 2008, el que cita el paper), detector [1]. Implementado con **`pyod.models.iforest.IForest`** (window_size=17, n_trees=200, random_state=42). Confirmado en `esa-adb/TimeEval-algorithms/subsequence_if/` (manifest + `requirements.txt: pyod==1.1.2` + `algorithm.py: from pyod.models.iforest import IForest`). **NO es `eif`/Extended IF** — ese es el hermano `subsequence_eif`, que ESA NO usa en el grid de M2 ligero. Corrección histórica: la spec vieja decía "eif" por confundir `subsequence_if` (usado) con `subsequence_eif` (no usado); difieren en una letra.
- **MAPIE / conformal prediction** o MC-dropout propio — incertidumbre [2].
- **matplotlib / plotly** — visualización de atribución [3].
- **LLM vía API** con prompt de grounding estricto (o modelo local para argumento edge/offline) — capa [4].
- `requirements.txt`, seeds fijadas, reproducibilidad.

## Estructura de carpetas (destino, repo nuevo `esa-adb-trustworthy-agent`)

```
├── README.md            ← pieza central (entregable nº1)
├── requirements.txt
├── data/                ← instrucciones de descarga (NO el dataset)
│   └── cached_scores/   ← scores precalculados (D9) → demo sin GPU
├── src/
│   ├── config.py        ← constantes ancla (canales, hiperparámetros)
│   ├── interfaces.py    ← contrato D7 (DetectionResult, Pydantic)
│   ├── preprocessing.py ← [1a] ingesta + preproceso (crudo → CSV)
│   ├── model.py         ← [1b] detector Windowed iForest (subsequence_if, pyod)
│   ├── evals.py         ← adaptador a la métrica ESA
│   ├── metrics_esa/     ← métrica de ESA vendorizada (MIT, sin tocar)
│   ├── uncertainty.py   ← [2]  (pendiente)
│   ├── explain.py       ← [3]  (pendiente)
│   └── report.py        ← [4] capa LLM  (pendiente)
├── notebooks/demo.ipynb ← [5]
└── results/             ← figuras y métricas
```

## Convenciones de código

Reglas universales (inmutabilidad, archivos pequeños, error handling, validación con schema) → `~/.claude/rules/coding-style.md`. Testing (TDD, 80% cobertura) → `~/.claude/rules/testing.md`. Seguridad (secrets, validación) → `~/.claude/rules/security.md`. Git → `~/.claude/rules/git-workflow.md`.

Reglas del proyecto: `@.claude/rules/components.md`, `@.claude/rules/patterns.md`.

## Glosario del producto

- **Canal:** un sensor de telemetría (columna del dataset). M2 ligero = canales 18-28.
- **Anomalía contextual:** valor en rango pero raro en su contexto. **Colectiva:** combinación de canales imposible. Ambas justifican ML (el umbral fijo es mundo externo, D1).
- **Falso negativo:** no avisa de anomalía real → peor caso. **Falso positivo:** alarma falsa → fatiga de alarmas → se convierte en FN por vía humana. Buscar equilibrio, no minimizar FN a cualquier precio.
- **Incertidumbre:** distingue "seguro de que NO" de "no tengo ni idea". Prioriza, es honesta, da contexto.
- **F0.5 event-wise:** métrica principal (precision-weighted, 0-1). Referencia baseline M2 ligero: 0.949.
- **ESA-ADB:** dataset real anotado. **TimeEval:** el evaluador/árbitro (no usado en MVP; métricas en Python plano).

## Reglas inmutables

- **Datos de ESA, no sustituibles.** Nunca cambiar ESA-ADB por otro benchmark (NASA SMAP/MSL). El activo es "resuelvo el problema de ESA con datos de ESA".
- **Nunca Misión3.** El paper la descarta (anomalías triviales/escasas, gaps).
- **MVP = M2 ligero + Windowed iForest (`subsequence_if`, pyod) CPU.** No deep, no GPU, no Docker, no fork. Stack oficial deep es Fase 2 opcional.
- **Repo nuevo, no fork** del oficial (D10). Citar `kplabs-pl/ESA-ADB` + ESA/ESOC + Airbus + KP Labs.
- **El LLM afirma solo lo grounded.** Hipótesis van etiquetadas como hipótesis (D4). El juez bloquea lo no soportado (D5).
- **No overclaiming.** Edge-deployability se argumenta, no se certifica. Resultados trazables al dataset, cero datos inventados.
- **No diagnóstico de causa raíz** (D3): el sistema detecta y localiza; el "por qué" es juicio del operador.
- **Timebox duro: stop 24 jul.** Candidatura se envía 28 jul con o sin repo.

## Flujo principal

Telemetría → detección (score) → incertidumbre (confianza calibrada + U) → atribución (canales) → informe LLM (generador redacta desde ventana+canales+U; juez audita contra los datos y marca/bloquea lo no grounded) → salida al operador. El operador decide con contexto, no con flag ciego.

## Integraciones externas

- Dataset ESA-ADB en Zenodo: `zenodo.org/records/15237121` (completo) · `doi.org/10.5281/zenodo.12528696` (M1/M2).
- Código oficial: `github.com/kplabs-pl/ESA-ADB` (MIT).
- Paper: `arxiv.org/abs/2406.17826`.
- Kaggle (Fase 2): `kaggle.com/competitions/esa-adb-challenge`.
- LLM: API (proveedor a definir) con prompt de grounding estricto.

## Variables de entorno

- Clave del proveedor LLM (nombre a definir, p. ej. `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Nunca hardcodear; leer de entorno.

## Referencias

- `PRD.md` — features, acceptance criteria, personas, fases.
- `base.md` — design doc con el razonamiento largo y las 11 decisiones D1-D11.
- `.claude/rules/` — reglas del proyecto. `~/.claude/rules/` — reglas universales.
