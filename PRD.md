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

**Detección [1]**
- [ ] Carga Misión2 subconjunto ligero (canales 18-28) desde datos oficiales de Zenodo.
- [ ] Windowed Extended Isolation Forest (librería `eif`, CPU) corre en Mac sin GPU/Docker y produce score por ventana.
- [ ] Métrica F0.5 event-wise reportada y comparable al baseline publicado por ESA (referencia: 0.949).
- [ ] Detector detrás de interfaz fija `scores + ventana + datos` (D7), intercambiable.

**Incertidumbre [2]**
- [ ] Score crudo convertido en confianza calibrada (conformal/MAPIE o MC-dropout/quantile).
- [ ] Métrica de calibración reportada.
- [ ] Salida = etiqueta 0/1 + confianza C + banda U.

**Explicabilidad [3]**
- [ ] Atribución por canal (contribución por feature) por cada detección.
- [ ] Salida visual + tabular.

**LLM grounded [4]**
- [ ] Generador redacta informe SOLO desde ventana+canales+U; dice "no sé" cuando falta señal; sugiere hipótesis etiquetadas, nunca afirma causa no grounded (D4).
- [ ] Juez LLM-as-judge audita el informe contra los datos y marca/bloquea afirmaciones no soportadas (D5).
- [ ] Casos "no sé" incluidos a propósito.

**Demo + README [5]**
- [ ] Notebook/script reproducible corre [2]+[3]+[4]+[5] desde scores cacheados, sin GPU (D9 nivel Demo).
- [ ] README completo, legible por recruiter técnico en 3 min.
- [ ] Seeds fijadas, `requirements.txt`, resultados trazables al dataset.

**Criterio "hecho":** los 5 componentes corren end-to-end sobre Misión2 ligero, reproducibles, README completo.

## 6. Features detalladas

| # | Feature | Qué hace | Quién usa | Datos que necesita | Fallback si falla |
|---|---|---|---|---|---|
| 1 | Ingesta + detector modular | Carga M2 ligero, corre windowed EIF (`eif`), emite score por ventana tras interfaz fija D7 | Autor (pipeline) | CSV Zenodo M2 canales 18-28 | Scores cacheados en repo (D9) |
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
| [1] Detección | Python local (CPU, `eif`) | Windowed EIF es CPU, corre en Mac; no necesita servidor |
| [2] Incertidumbre | Python local (MAPIE/conformal) | Post-proceso del score, ligero |
| [3] Explicabilidad | Python local (atribución + matplotlib/plotly) | Cálculo + visualización sobre la ventana |
| [4] LLM generador+juez | Capa LLM vía API (o modelo local para argumento edge/offline) | Requiere modelo de lenguaje; prompt de grounding estricto |
| [5] Demo/README | Notebook + Markdown | Entregable, README-first |

## 9. Arquitectura técnica

```
Telemetría ESA-ADB (Misión2 ligero, canales 18-28)
      │
      ▼
[1] Detector — windowed EIF (`eif`, CPU)  ──►  score de anomalía por ventana
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

Núcleo diferenciador: [2]+[3]+[4]. [1] se apoya en código existente (`eif` + código de referencia de ESA-ADB) para no reinventar. Interfaz modular D7 hace el detector intercambiable (windowed EIF ↔ DC-VAE-ESA oficial) sin rehacer el proyecto.

**Stack:** Python 3.9, `eif` (Extended Isolation Forest con ventanas, algoritmo `subsequence_if` de ESA-ADB), MAPIE/conformal (o MC-dropout propio), matplotlib/plotly, LLM vía API con prompt de grounding estricto. `requirements.txt` pinneado (cython<3, numpy 1.21.6), seeds fijadas.

## 10. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Scope creep | No termina en timebox | Core es [2]+[3]+[4]; [1] se apoya en `eif`. No pulir de más |
| Hardware del stack oficial (Linux+GPU NVIDIA+512GB) no corre en Mac | Bloquea detección | Windowed EIF CPU en Mac da baseline oficial mejor en M2 ligero (verificado: eif compila con Py3.9+cython<3); stack Docker es Fase 2 opcional (GPU cloud) |
| "Un par de días" → una semana | Se come otras prioridades | Timebox duro, stop 24 jul |
| Overclaiming (fingir a-bordo/datos falsos) | Hunde credibilidad ante ESA | Framing honesto: edge se argumenta; resultados trazables |
| Repo a medias | Peor que ninguno | Sale con calidad dentro del timebox o no se menciona |
| Licencia del dataset Zenodo sin verificar | Bloqueo legal al publicar | Verificar licencia del dataset antes de publicar (código repo es MIT, verificado) |

## 11. Orden de construcción y fases

**Fase 1 — MVP (5 días, en Mac, garantiza el proyecto):**

| Día | Entregable |
|---|---|
| 1 | Ingesta M2 ligero (canales 18-28) + windowed EIF (`eif`) corriendo + interfaz modular D7 |
| 2 | Capa de incertidumbre calibrada sobre el score |
| 3 | Atribución por canal + visualizaciones |
| 4 | Capa LLM (generador + juez) + casos "no sé" |
| 5 | README, demo reproducible, limpieza, publicar repo |

Justificación del orden (valor/riesgo/dependencias/coste/aprendizaje): [1] es dependencia dura de todo lo demás y el más incierto (datos+entorno) → primero. [2]→[3]→[4] es cadena de valor creciente hacia el diferenciador. [5] empaqueta. Cada día produce algo demostrable.

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
- *Vía 1 — algoritmo:* Fable barre SOTA de TSAD + primeros principios de iForest. Norte factible: el paper prueba que el postprocesado/thresholding pesa más que la red base (Telemanom-ESA-Pruned ganó por dynamic thresholding NDT). Mejor thresholding sobre el windowed EIF = palanca real y barata.
- *Vía 2 — datos:* data augmentation intra-misión (tractable) · canales no-target como contexto (tractable) · transfer entre misiones (research real, traicionero — estructuras distintas, no se apilan con `concat`).
- *Avisos:* M2 ligero ya en 0.949 (margen escaso); donde mejorar importa es el set completo (~0.07, problema abierto — no prometer batirlo). NO usar Misión3. La mejora REAL y garantizada es la capa [2]+[3]+[4], no estas dos vías.

## Apéndice B — Fuentes y licencia

- **Dataset:** ESA-ADB, telemetría real anotada (~17,5 años, 844 eventos, 148 anomalías en las 2 misiones del benchmark). Zenodo completo (3 misiones): `zenodo.org/records/15237121`. Carpetas M1/M2 del README: `doi.org/10.5281/zenodo.12528696`. ~3-4 GB por misión, ligeros para Mac.
- **Código oficial:** `github.com/kplabs-pl/ESA-ADB` (framework sobre TimeEval, licencia **MIT** verificada).
- **Paper:** `arxiv.org/abs/2406.17826` (9 requisitos operativos, 5 métricas; hallazgo: algoritmos estándar aún no sirven para deployment real).
- **Kaggle:** `kaggle.com/competitions/esa-adb-challenge` (métrica pública verificable).
- **Licencia dataset Zenodo:** verificar antes de publicar. Citar ESA/ESOC + Airbus DS + KP Labs en el README.
