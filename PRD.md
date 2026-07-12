# PRD — Trustworthy Anomaly Agent sobre ESA-ADB

**Autor:** Adolfo Viguera Varea
**Repo destino:** `esa-adb-trustworthy-agent` (nuevo, no fork — ver D10)
**Objetivo del artefacto:** proyecto público que prueba, con datos reales de ESA, que una IA de entorno crítico (grounded, auditable, con incertidumbre) resuelve el problema del AI & Data Science Section de ESTEC. Amplificador de la candidatura al Junior Professional in AI and Data Science (Req. 20687).

> Documento fuente: `base.md` (design doc refinado, 11 decisiones de diseño D1-D11). Este PRD lo formaliza; `base.md` conserva el razonamiento largo.

---

## 1. Problema y contexto

Un operador de misión recibe telemetría de cientos de sensores (canales) cada pocos segundos — un Excel gigante de años de filas. No tiene ojos para vigilar todos los canales ni para conocer el comportamiento normal de cada uno. Es un **cuello de botella humano**: el dato está, la capacidad de triar no.

La detección por umbral fijo (límite por canal) existe en operaciones reales desde hace décadas y captura anomalías puntuales triviales. No captura las dos clases que importan:
- **Contextual:** valor en rango pero raro en su contexto (batería a 20° es normal, salvo tras entrar en sombra, donde debería enfriarse).
- **Colectiva:** ningún canal solo está mal, pero la combinación es imposible.

Estas requieren aprender el patrón normal multivariante en el tiempo — territorio ML/DL. Pero el paper ESA-ADB demuestra que los detectores estándar aún **no sirven para deployment real** (en el set completo todos fracasan, F0.5 ≈ 0.07). El hueco abierto: un operador no puede confiar en un flag ciego cuando ni los expertos saben qué detector fía sin probar (No Free Lunch, D11).

**Por qué ahora:** ESA publicó ESA-ADB (dataset + benchmark) y declara el problema de trustworthiness abierto. Encaja exacto con el puesto de ESTEC.

## 2. Solución propuesta

Un agente que, sobre el dataset oficial ESA-ADB, detecta anomalías en telemetría real, **cuantifica su incertidumbre** (confianza calibrada, no score crudo), **explica qué canales la provocan**, y emite un **informe grounded y legible** vía una capa LLM que no alucina (generador + juez LLM-as-judge). El núcleo diferenciador no es la detección — es la **capa trustworthy [2]+[3]+[4]** encima de una detección sólida. Diseñado como bloque edge-deployable (argumentado, no certificado) para recortar downlink.

## 3. Personas, roles y permisos

| Rol | Descripción | Puede | No puede |
|---|---|---|---|
| Ingeniero de operaciones de misión (usuario) | Recibe cientos de eventos de telemetría, necesita triar rápido | Ver etiqueta 0/1 + confianza calibrada + canales responsables + informe legible; priorizar por confianza | Esperar diagnóstico de causa raíz (eso es su juicio, no del sistema — D3) |
| Recruiter técnico ESA (evaluador) | Lee el README en 3 min para juzgar el proyecto | Reproducir la demo sin GPU (scores cacheados, D9); leer resultados vs baseline | — |
| Autor/mantenedor | Construye y publica el repo | Todo | Overclaiming: fingir despliegue a bordo o inventar datos |

## 4. User stories

- Como **operador**, quiero que cada alarma venga con una confianza calibrada, para priorizar cuáles miro primero y no sufrir fatiga de alarmas.
- Como **operador**, quiero saber qué canales dispararon la detección, para orientar mi investigación sin abrir los cientos de canales.
- Como **operador**, quiero un informe en lenguaje natural que distinga "seguro" de "no sé", para decidir con contexto y no con un flag ciego.
- Como **operador**, quiero que el informe nunca afirme una causa que los datos no soportan, para poder confiar en él en un entorno crítico.
- Como **recruiter técnico**, quiero clonar el repo y correr una demo en mi portátil sin GPU, para verificar que el proyecto es real en 3 minutos.

## 5. Acceptance criteria

> **Estado a 2026-07-12:** los 5 componentes están cerrados. Lo único pendiente es el
> horneado del notebook (Run All con outputs committeados) y el **clean-room test** (clonar
> en otra máquina y hacer de visitante). Tres criterios se **desviaron conscientemente**
> durante la implementación: están marcados con ⚠️ y explicados abajo, no son deuda oculta.

**Detección [1]**
- [x] Carga Misión2 subconjunto ligero (canales 18-28) desde datos oficiales de Zenodo.
- [x] Windowed iForest (`subsequence_if`, Isolation Forest estándar vía `pyod`, CPU) corre en Mac sin GPU/Docker y produce score por ventana.
- [x] Métrica F0.5 event-wise reportada y comparable al baseline publicado por ESA: **0.9487** (referencia 0.949).
- [x] ⚠️ **Detector intercambiable — reformulado.** No hay una clase `DetectionResult` ni un adapter: eran stubs que nunca se implementaron y se **borraron** (código muerto). La intercambiabilidad se consigue **por construcción**: [2], [3] y [4] consumen SOLO las salidas del detector (score continuo por ventana, los datos ventaneados, y `decision_function` para la atribución), nunca sus internals. Cambiar de detector = regenerar artefactos, no reescribir la capa trustworthy. Una interfaz nominal habría sido ceremonia sin garantía.

**Incertidumbre [2]**
- [x] Score crudo convertido en confianza calibrada: **conformal p-values** propios (no MAPIE, no MC-dropout: el detector no es probabilístico ni tiene dropout).
- [x] Métrica de calibración reportada: cobertura medida **0.0486** frente al objetivo 0.05, más **0 falsas alarmas en 976.182 ventanas normales** en el punto de operación α* = 2e-5. Tercio final intacto: F0.5 **0.9809**.
- [x] ⚠️ **Salida = 0/1 + confianza — sin "banda U".** Se emite etiqueta + **p-value conformal** (y su confianza 1-p), que es una garantía *distribution-free* sobre la tasa de falsas alarmas. No se emite una banda de incertidumbre: un detector one-class no da P(anomalía) sin una tasa base, así que una "banda" habría sido un número inventado. La confianza **satura** (~1 en todo evento marcado, por el suelo de α*) y **se reporta como saturada**, nunca como certeza discriminante: para priorizar se usa `priority`.

**Explicabilidad [3]**
- [x] Atribución por canal (perturbación/ablación) por cada detección. Validada: **hit@1 = 1.0** frente a 0.617 (magnitud) y 0.475 (aleatorio) sobre 120 eventos.
- [x] Salida visual (heatmap canal × tiempo) + tabular (contexto grounded por evento).

**LLM grounded [4]**
- [x] Generador redacta el brief SOLO desde la evidencia (nombres, palabras cualitativas, duración legible, confianza); las cifras **nunca pasan por el modelo** (viven en tablas verbatim). Hipótesis de acople **etiquetadas como hipótesis no confirmadas**; nunca afirma causa raíz (D4/D3).
- [x] Dos guardarraíles en serie, veredicto = AND: **precheck** léxico determinista + **juez** LLM-as-judge (D5). Bloquea lo no soportado. Certificado contra un golden de 18 casos etiquetados a mano: precisión 1.0, recall 1.0 (**prueba de existencia**, no garantía estadística). Generador sobre los 120 eventos: 120/120 PASS.

**Demo + README [5]**
- [ ] ⚠️ **Nivel "Demo" desde scores cacheados — RETIRADO.** Sustituido por un **único camino de datos** (decisión del usuario, 2026-07-12): un artefacto se commitea solo si recalcularlo cuesta **dinero o una dependencia externa (API key)**, nunca si solo cuesta **tiempo**. Consecuencia: quien quiere **entender** lee el notebook **horneado** en GitHub (0 setup, 0 datos, 0 key); quien quiere **ejecutar** descarga Zenodo y recomputa en vivo (preproceso ~29 min + train ~11 min, idempotentes). Única excepción committeada: `data/cached/m4_llm_cache.json` (coste = API key + modelo no determinista). *Pendiente: el horneado.*
- [x] README completo, legible por recruiter técnico: entrada + resultados + quickstart + limitaciones. El deep-dive vive en el notebook, no se duplica.
- [x] Seeds fijadas (42), `requirements.txt`, resultados trazables al dataset. Suite de regresión verde (56 tests).

**Criterio "hecho":** los 5 componentes corren end-to-end sobre Misión2 ligero, reproducibles, README completo. **Falta: horneado + clean-room test.**

## 6. Features detalladas

| # | Feature | Qué hace | Quién usa | Datos que necesita | Fallback si falla |
|---|---|---|---|---|---|
| 1 | Ingesta + detector modular | Carga M2 ligero, corre Windowed iForest (`subsequence_if`, pyod), emite score por ventana tras interfaz fija D7 | Autor (pipeline) | CSV Zenodo M2 canales 18-28 | Scores cacheados en repo (D9) |
| 2 | Capa de incertidumbre | Convierte score crudo en confianza calibrada + banda | Operador | Score del detector + set de calibración | Reportar sin calibrar + avisar en README |
| 3 | Explicabilidad por canal | Atribuye qué canales dominan cada detección | Operador | Ventana + contribución por feature | Ranking crudo por magnitud |
| 4 | Capa LLM (generador + juez) | Informe grounded + guardrail anti-alucinación | Operador | Ventana + canales + U (nunca el dato crudo completo) | Plantilla determinista sin LLM |
| 5 | README + demo | Recorrido reproducible + entregable nº1 | Recruiter | Scores cacheados + figuras | — |

## 7. Lo que NO hace (anti-scope)

- No es un producto ni servicio desplegado.
- No busca batir el state-of-the-art en detección (busca demostrar la capa trustworthy sobre detección sólida).
- No entrena modelos gigantes ni requiere GPU cluster para el MVP.
- No diagnostica causa raíz (¿POR QUÉ pasa? = juicio del operador — D3).
- No afirma despliegue real a bordo (edge se argumenta, no se certifica).
- No sustituye el dataset de ESA por otro benchmark (NASA SMAP/MSL, etc. — innegociable).
- No usa Misión3 (el paper la descarta: anomalías triviales/escasas, gaps).

## 8. Mapa de lógica

| Feature | Dónde vive la lógica | Por qué |
|---|---|---|
| [1] Detección | Python local (CPU, `pyod`) | Windowed iForest (`subsequence_if`) es CPU, corre en Mac; no necesita servidor |
| [2] Incertidumbre | Python local (MAPIE/conformal) | Post-proceso del score, ligero |
| [3] Explicabilidad | Python local (atribución + matplotlib/plotly) | Cálculo + visualización sobre la ventana |
| [4] LLM generador+juez | Capa LLM vía API (o modelo local para argumento edge/offline) | Requiere modelo de lenguaje; prompt de grounding estricto |
| [5] Demo/README | Notebook + Markdown | Entregable, README-first |

## 9. Arquitectura técnica

```
Telemetría ESA-ADB (Misión2 ligero, canales 18-28)
      │
      ▼
[1] Detector — Windowed iForest (`subsequence_if`, pyod, CPU)  ──►  score de anomalía por ventana
      │                                          [interfaz fija D7: scores + ventana + datos]
      ▼
[2] Incertidumbre (conformal/MAPIE o MC-dropout)  ──►  confianza calibrada + banda U
      │
      ▼
[3] Atribución por canal (feature contribution)  ──►  ranking de canales responsables
      │
      ▼
[4] Capa LLM (grounded, refuse-when-unsure)
      ├── Generador: ventana+canales+U  ──►  informe operador (sugiere-con-etiqueta)
      └── Juez: informe + datos  ──►  ¿todo soportado? → aprueba / marca / bloquea
      │
      ▼
[5] Salida: notebook/README con casos de ejemplo
```

Núcleo diferenciador: [2]+[3]+[4]. [1] se apoya en código existente (`subsequence_if` + código de referencia de ESA-ADB) para no reinventar. Interfaz modular D7 hace el detector intercambiable (Windowed iForest ↔ DC-VAE-ESA oficial) sin rehacer el proyecto.

**Stack:** Python 3.9, `pyod` (Isolation Forest estándar con ventanas = algoritmo `subsequence_if` de ESA-ADB; es el que cita el paper, Liu 2008), MAPIE/conformal (o MC-dropout propio), matplotlib/plotly, LLM vía API con prompt de grounding estricto. `requirements.txt` pinneado, seeds fijadas.

## 10. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Scope creep | No termina en timebox | Core es [2]+[3]+[4]; [1] se apoya en `subsequence_if`. No pulir de más |
| Hardware del stack oficial (Linux+GPU NVIDIA+512GB) no corre en Mac | Bloquea detección | Windowed iForest (`subsequence_if`, pyod) CPU en Mac da baseline oficial en M2 ligero; solo necesita `pyod` (sin GPU/Docker); stack Docker deep es Fase 2 opcional (GPU cloud) |
| "Un par de días" → una semana | Se come otras prioridades | Timebox duro, stop 24 jul |
| Overclaiming (fingir a-bordo/datos falsos) | Hunde credibilidad ante ESA | Framing honesto: edge se argumenta; resultados trazables |
| Repo a medias | Peor que ninguno | Sale con calidad dentro del timebox o no se menciona |
| Licencia del dataset Zenodo sin verificar | Bloqueo legal al publicar | Verificar licencia del dataset antes de publicar (código repo es MIT, verificado) |

## 11. Orden de construcción y fases

**Fase 1 — MVP (5 días, en Mac, garantiza el proyecto):**

| Día | Entregable |
|---|---|
| 1 | Ingesta M2 ligero (canales 18-28) + Windowed iForest (`subsequence_if`, pyod) corriendo + interfaz modular D7 |
| 2 | Capa de incertidumbre calibrada sobre el score |
| 3 | Atribución por canal + visualizaciones |
| 4 | Capa LLM (generador + juez) + casos "no sé" |
| 5 | README, demo reproducible, limpieza, publicar repo |

Justificación del orden (valor/riesgo/dependencias/coste/aprendizaje): [1] es dependencia dura de todo lo demás y el más incierto (datos+entorno) → primero. [2]→[3]→[4] es cadena de valor creciente hacia el diferenciador. [5] empaqueta. Cada día produce algo demostrable.

**Fase de empaquetado — repo limpio (tras cerrar los módulos [1]-[5], antes de publicar):**

Objetivo: que alguien clone el repo, abra el notebook y corra TODO el proceso **sin `esa-adb` y sin descargar los 3.8 GB crudos**. Tareas:

1. **Copiar a `src/` el código de ESA que usamos**, con cabecera de licencia MIT + `NOTICE` (crédito a kplabs-pl/ESA-ADB). Cumple D10 (citar, no forkear):
   - Detector: `subsequence_if/algorithm.py` (1 archivo, solo pyod) → `src/m1_detection/vendor/`.
   - Métrica: `ESA_ADB_metrics.py` + `metric.py` + `metrics/utils.py` + `affiliation_based_metrics_repo/` (~14 archivos autocontenidos) → `src/m1_detection/vendor/metrics/` (ajustar rutas de import).
2. **Repuntar imports:** `model.py` y `evaluation.py` apuntan al código copiado, no a `esa-adb/`.
3. **Preproceso:** NO copiar sus clases pesadas (`DatasetManager`/`DatasetAnalyzer`). Se deja como paso de una vez documentado (clonar ESA + correr script) + se cachean los datos. Alternativa futura: recortar el preproceso para quitar esa dependencia.
4. **Cachear artefactos** en `data/cached/` (pocos MB, sí caben en repo): scores del detector + segmentos de datos de los casos demo + labels. Los CSV de 850 MB y los 3.8 GB crudos NO van al repo (documentar descarga Zenodo).
5. **Borrar `esa-adb/`** entero. Quitar su ignore del `.gitignore`.
6. **Re-correr los tests → confirmar `EW_F_0.50 = 0.9487`** desde el código copiado (success-test tras cortar esa-adb). Si cambia, algo se rompió al copiar.
7. **Notebook `notebooks/demo.ipynb`**: corre [1]→[5] desde lo cacheado, en segundos, sin esa-adb.
8. **README + requirements**: instrucciones de clon→notebook; `requirements.txt` ya sin `eif` (pyod).

**Fase 2 — opcional (solo si sobra tiempo tras día 5, no bloquea MVP):** GPU cloud (~40 €), correr detector deep oficial (DC-VAE-ESA/Telemanom-ESA), enchufarlo vía D7, reproducir métrica oficial → sello. Y/o someter a Kaggle para métrica pública verificable.

**Reproducibilidad en 3 niveles (D9):** Demo (scores cacheados, sin GPU, cualquiera) · Ligero (VAE propio en Mac/PC) · Oficial (Docker/GPU, documentado).

**Stop duro: 24 jul.** Si no llega a calidad, la candidatura (envío 28 jul) va sin el repo; la carta cubre el hueco. El link entra en la carta solo cuando el repo esté vivo y público.

## 12. Métricas de éxito

- **Reproducible:** alguien clona, sigue el README, obtiene los mismos resultados.
- **Comparable:** detección iguala o se acerca al baseline publicado de ESA-ADB (referencia F0.5 0.949 en M2 ligero).
- **Diferenciado:** incertidumbre calibrada (métrica de calibración reportada) + explicabilidad real, no decorativa.
- **Honesto:** el informe LLM nunca afirma más de lo que la señal soporta; casos "no sé" incluidos.
- **Legible:** README entendible por recruiter técnico en 3 minutos.

---

## Apéndice A — Extensiones futuras (NO en MVP)

Streaming/online detection, despliegue real en hardware edge, comparación multi-baseline, y capa híbrida umbral determinista + ML (D1).

**Exploratorio "mejorar el benchmark" (post-MVP, sin promesas):**
- *Vía 1 — algoritmo:* Fable barre SOTA de TSAD + primeros principios de iForest. Norte factible: el paper prueba que el postprocesado/thresholding pesa más que la red base (Telemanom-ESA-Pruned ganó por dynamic thresholding NDT). Mejor thresholding sobre el Windowed iForest = palanca real y barata.
- *Vía 2 — datos:* data augmentation intra-misión (tractable) · canales no-target como contexto (tractable) · transfer entre misiones (research real, traicionero — estructuras distintas, no se apilan con `concat`).
- *Avisos:* M2 ligero ya en 0.949 (margen escaso); donde mejorar importa es el set completo (~0.07, problema abierto — no prometer batirlo). NO usar Misión3. La mejora REAL y garantizada es la capa [2]+[3]+[4], no estas dos vías.

## Apéndice B — Fuentes y licencia

- **Dataset:** ESA-ADB, telemetría real anotada (~17,5 años, 844 eventos, 148 anomalías en las 2 misiones del benchmark). Zenodo completo (3 misiones): `zenodo.org/records/15237121`. Carpetas M1/M2 del README: `doi.org/10.5281/zenodo.12528696`. ~3-4 GB por misión, ligeros para Mac.
- **Código oficial:** `github.com/kplabs-pl/ESA-ADB` (framework sobre TimeEval, licencia **MIT** verificada).
- **Paper:** `arxiv.org/abs/2406.17826` (9 requisitos operativos, 5 métricas; hallazgo: algoritmos estándar aún no sirven para deployment real).
- **Kaggle:** `kaggle.com/competitions/esa-adb-challenge` (métrica pública verificable).
- **Licencia dataset Zenodo:** verificar antes de publicar. Citar ESA/ESOC + Airbus DS + KP Labs en el README.
