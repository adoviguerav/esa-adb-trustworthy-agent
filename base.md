# PRD — Trustworthy Anomaly Agent sobre ESA-ADB

**Autor:** Adolfo Viguera Varea
**Objetivo del artefacto:** proyecto público que prueba, con datos reales de ESA, que mi IA de entorno crítico (grounded, auditable, con incertidumbre) resuelve el problema exacto del AI & Data Science Section de ESTEC. Amplificador de la candidatura al Junior Professional in AI and Data Science (Req. 20687).

---

## 1. One-liner

Un agente que detecta anomalías en telemetría real de satélite (dataset oficial **ESA-ADB**), **cuantifica su incertidumbre**, **explica qué canales la provocan** y genera un **informe grounded y legible para el operador** mediante una capa LLM que no alucina. Pensado como bloque desplegable en edge/a bordo para reducir downlink y time-to-insight.

---

## 1.b Conceptos clave en lenguaje claro

Glosario del dominio, escrito para que se entienda sin saber de espacio.

- **Telemetría:** cientos de sensores del satélite (temperatura de batería, voltaje de panel, corriente de motor, orientación…) mandan su valor cada X segundos. Cada sensor es un **canal**. Es un Excel gigante: columnas = canales (224 en el dataset completo), filas = instantes de tiempo, años de filas.

- **Cuello de botella humano:** el operador tiene la telemetría pero no tiene ojos suficientes. No puede vigilar cientos de canales a la vez ni conocer el comportamiento normal de cada uno. Necesita software que trie por él.

- **Tipos de anomalía:**
  - *Por umbral (puntual):* un valor supera un límite fijo ("T batería > 80° → alarma"). Trivial, no necesita ML. **Ya existe** en operaciones reales (ver decisión D1).
  - *Contextual:* el valor está dentro de rango, pero es raro **en su contexto** (20° de batería es normal, salvo que el satélite acaba de entrar en sombra y debería estar enfriándose, no calentándose).
  - *Colectiva:* ningún canal solo está mal, pero **la combinación** es imposible (voltaje, corriente y temperatura individualmente normales, pero esos tres valores juntos nunca coexisten en un satélite sano).
  - Las anomalías contextuales y colectivas son las que justifican ML/DL: requieren aprender el **patrón normal multivariante a lo largo del tiempo**, no reglas por canal. Ahí es donde el umbral se queda ciego y el ML gana.

- **Falsos negativos vs falsos positivos:**
  - *Falso negativo:* no avisa de una anomalía real → peor escenario, satélite dañado. Es el error a minimizar.
  - *Falso positivo:* alarma cuando no la hay → molesto (despierta al equipo) pero recuperable.
  - **Matiz crítico:** demasiados falsos positivos generan *fatiga de alarmas* — el operador recibe cientos de alarmas falsas, deja de mirarlas, y una real se cuela. El exceso de falsos positivos **se convierte** en falsos negativos por vía humana. No es "minimizar FN a cualquier precio"; es equilibrio informado. Ahí es donde la incertidumbre aporta.

- **Por qué la incertidumbre (más allá de "sí/no"):** un score crudo confunde "seguro de que NO hay anomalía" con "no tengo ni idea porque nunca vi datos así". La capa de incertidumbre hace tres cosas: (1) **prioriza** las alarmas por confianza — ataca la fatiga; (2) es **honesta** — distingue confianza alta de ignorancia; (3) da al operador **contexto** para decidir, no un flag ciego.

- **ESA-ADB:** dataset con telemetría real de misiones de ESA **+ etiquetas de expertos** (dónde estaban las anomalías de verdad). Es la "verdad" contra la que te mides.

- **TimeEval:** el software/protocolo que corre tu detector sobre ESA-ADB con reglas fijas iguales para todos y calcula la métrica estándar. Es el "árbitro" que hace justas las comparaciones.

- **Edge / a bordo:** computar en el propio satélite en vez de bajar todo a Tierra. Reduce downlink (caro y lento) y da velocidad de reacción.

---

## 2. Por qué este proyecto (encaje con el puesto)

Golpea los tres duty areas del rol a la vez, sobre datos que ESA misma publicó, usando mi edge probado en sanidad regulada.

| Duty area del JD | Cómo lo cubre el proyecto |
|---|---|
| AI assistants a lo largo del ciclo de vida de misión | La capa LLM convierte cada alerta en un informe de anomalía para el operador — asistente agéntico grounded. |
| Insights de datos de misión (a bordo) | Detección sobre telemetría multivariante real, diseñada como edge-deployable para recortar downlink (value prop tipo PhiSat). |
| AI trustworthiness | Incertidumbre calibrada + explicabilidad por canal + grounding estricto. Es mi disciplina de GDPR/MDR/AI-Act transplantada a estándares espaciales. |

**Narrativa:** "Esto es literalmente lo que hago con datos clínicos —dato sucio y crítico → señal fiable y auditable— aplicado al propio benchmark de ESA." No demuestra afición al espacio; demuestra que resuelvo su problema con sus datos.

---

## 3. Objetivo y no-objetivos

**Objetivo:** un repo público, funcionando end-to-end, con README claro, que en el dataset ESA-ADB (1) detecte anomalías con rendimiento comparable a un baseline reconocido, (2) acompañe cada detección de una medida de incertidumbre calibrada, (3) señale los canales responsables, y (4) emita un informe en lenguaje natural grounded en la ventana y canales detectados.

**No-objetivos (fuera de alcance, explícito):**
- No es un producto ni un servicio desplegado.
- No busca batir el state-of-the-art en detección; busca demostrar la **capa trustworthy** encima de una detección sólida.
- No entrena modelos gigantes ni requiere GPU cluster.
- No inventa datos ni afirma despliegue real a bordo — el edge-deployability se argumenta, no se certifica.

---

## 4. Usuario y caso de uso

**Usuario:** ingeniero de operaciones de misión que recibe cientos de eventos de telemetría y necesita triar rápido cuáles son anomalías reales, con qué confianza y por qué.

**Flujo:** telemetría → detección → score + incertidumbre → canales responsables → informe legible ("Anomalía probable en canal X entre t1 y t2, confianza media-alta; patrón consistente con deriva de sensor; incertidumbre elevada por escasez de eventos similares"). El operador decide con contexto, no con un flag ciego.

---

## 4.b Decisiones de diseño (cerradas)

Decisiones tomadas al refinar el alcance. Definen qué construyes, qué reutilizas y dónde están las fronteras honestas.

**D1 — La detección por umbral es mundo externo, no tu proyecto.** El *limit checking* (límites fijos por canal) lo configuran los ingenieros de misión y existe en operaciones reales desde hace décadas. Tú asumes que existe y atacas lo que el umbral NO pilla (contextual/colectivo). *Opcional (extensión, no MVP):* añadir una capa híbrida "umbral determinista + ML" — es como se hace en sistemas críticos reales (defensa en profundidad) y da realismo operacional al README. No bloquea nada.

**D2 — Reutilizar > construir desde cero.** Norma profesional, no atajo. El flujo real hoy: partir de modelos pre-entrenados / código existente, hacer transfer learning o fine-tuning, ensamblar con librerías probadas (PyTorch, HuggingFace, scikit-learn, MAPIE), y escribir desde cero solo el pegamento y lo genuinamente propio. En 5 días, cada minuto en el detector es minuto robado a [2]+[3]+[4].
  - **[1] Detector:** se presta entero (código público, quizá se ajusta). Cero orgullo aquí.
  - **[2] Incertidumbre:** se presta la *herramienta* (MAPIE / conformal), pero el **aporte intelectual es propio** — elegir el método, aplicarlo bien y reportar la calibración. La librería es el martillo; el diseño y la validación son tuyos.

**D3 — Frontera de alcance: detectas y localizas, NO diagnosticas la causa raíz.** Cuatro niveles:
  | Nivel | Pregunta | ¿En alcance? |
  |---|---|---|
  | Detección | ¿Pasa algo? | ✅ [1] |
  | Localización | ¿Qué canales? | ✅ [3] |
  | Descripción de patrón | ¿A qué se parece? | ⚠️ [4], con etiqueta |
  | Diagnóstico de causa raíz | ¿POR QUÉ pasa? | ❌ Juicio de operador |

  El sistema dice *"anomalía en canales T y corriente entre t1-t2, confianza alta, patrón consistente con deriva de sensor"*. NO afirma *"el radiador falló"* — eso requiere conocimiento físico del satélite y es juicio del ingeniero. Cruzar esa frontera sería overclaiming: justo lo que el proyecto promete no hacer.

**D4 — El LLM describe y sugiere-con-etiqueta; nunca afirma como hecho lo no grounded.**
  - *Permitido:* sugerir hipótesis marcándolas — *"patrón consistente con deriva de sensor (hipótesis, no confirmada)"*. El conocimiento del LLM entra solo como conjetura explícitamente etiquetada.
  - *Prohibido:* afirmar una causa que los datos no soportan. Eso es alucinación con corbata.
  - Regla: grounded en los datos para lo que **afirma**; el conocimiento del modelo solo como hipótesis etiquetada. La frontera es *afirmar vs hipotetizar*, y se implementa en el prompt.

**D5 — LLM-as-judge como guardrail de grounding (parte de [4], no opcional).** Un segundo LLM (o el mismo con otro prompt) recibe el informe generado + los datos originales y verifica: *"¿cada afirmación está soportada por la ventana/canales/incertidumbre que se dieron? ¿afirma algo no grounded?"*. Si detecta afirmación no soportada → la marca o bloquea el informe. Es AI-trustworthiness tangible: no solo dices "no alucina", **demuestras y auditas el mecanismo**. Barato (un prompt más), multiplica el mensaje del rol ESA.

**D6 — Salida = 0/1 + confianza calibrada.** El detector da un score sucio; la capa [2] lo convierte en confianza *calibrada y honesta*. Con ese par (etiqueta + confianza) se prioriza (ordenar alarmas) y se alimenta al LLM para explicar con contexto. El % de confianza es producto de [2], no del detector.

**D7 — Arquitectura modular: el detector es una pieza intercambiable.** Todo lo que va después del detector ([2] incertidumbre, [3] explicabilidad, [4] LLM) recibe siempre la misma interfaz fija — *"scores + ventana + datos"* — y es indiferente al origen de esos scores. Cambiar el detector (de VAE casero a DC-VAE-ESA oficial) es enchufar una pieza, no rehacer el proyecto. Esta interfaz limpia se diseña desde el día 1 y es lo que hace viable el plan de dos fases (D8).

**D8 — Detector del MVP: Window iForest (CPU) sobre Misión2 subconjunto ligero (decisión sobre [1]).** Decisión respaldada por la Tabla 2 del paper (ver D11):
  - **Escenario:** Misión2, **subconjunto ligero** (canales 18-28). Los subconjuntos ligeros los diseñó ESA a propósito para "modelos simples, experimentos iniciales y posibles aplicaciones a bordo (on-board)" — pequeños, Mac-friendly, y puerta al argumento edge del PRD.
  - **Detector:** **Window iForest** (Isolation Forest con ventanas). En ese escenario es el **mejor de toda la Tabla 2**: F0.5 event-wise = **0.949**. Es de CPU (no deep), está en **PyOD** (`pip install pyod`), corre en el Mac M5 sin GPU/Docker/Linux, y es un **baseline publicado por ESA** → comparabilidad directa con su tabla.
  - *Corrección respecto a versiones previas de este doc:* se descarta "VAE propio" y "Misión1". Razón (D11): el mismo Window iForest saca 0.949 en Misión2 ligero pero **<0.001 en Misión1 ligero** (inunda de falsos positivos). En Misión1 ligero solo funciona el deep Telemanom-ESA-Pruned (0.786, requiere GPU). Por eso el MVP va a Misión2 ligero, donde un algoritmo CPU gana.
  - *Por qué el stack oficial NO corre en Mac (contexto):* los detectores deep oficiales (Telemanom-ESA, DC-VAE-ESA) son contenedores Docker atados a **CUDA** (exclusivo NVIDIA, inexistente en Mac) + exigen 32-64 GB RAM + ~512 GB disco. Pero **no los necesitamos**: Window iForest de PyOD da un baseline oficial mejor en este escenario, en Mac, gratis.
  - **Fase 2 (opcional, GPU cloud ~40 €, solo si sobra tiempo):** correr un detector deep oficial en otro escenario para ampliar comparación. Gracias a D7 (detector modular), enchufarlo es trivial. No bloquea el MVP.

**D11 — El rendimiento de un detector es empírico y data-dependiente ("No Free Lunch"). Es un pilar de la tesis.** No existe un algoritmo que gane siempre; el mejor depende del dato, y solo se sabe probando (por eso existen benchmarks como ESA-ADB). Evidencia dura de la Tabla 2: el **mismo** Window iForest saca **0.949** en Misión2 ligero y **<0.001** en Misión1 ligero; y en el **set completo TODOS fracasan** (el mejor, Telemanom-ESA-Pruned, apenas 0.061 en Misión1 y 0.071 en Misión2). Implicación para el proyecto: si ni los expertos saben qué detector fía sin probar, un operador **no puede confiar en un flag ciego** → la capa de incertidumbre/explicación [2]+[3]+[4] no es adorno, es la respuesta directa a esta realidad. Este es el hueco que el propio paper declara abierto.

**D10 — Repo nuevo, NO fork del oficial.** El proyecto es una capa *sobre* ESA-ADB, no una modificación de ESA-ADB. Un fork arrastraría la estructura pesada del oficial, enterraría el README propio (que es el entregable nº1) y confundiría autoría. Se crea un repo nuevo `esa-adb-trustworthy-agent` que **cita y enlaza** `kplabs-pl/ESA-ADB` (créditos + licencia MIT respetada), documenta la descarga de datos, y para la Fase 2 opcional referencia el oficial (o lo incluye como submódulo git para correr su detector) — nunca como fork. Narrativa: "construí una capa de confianza sobre el benchmark de ESA", no "modifiqué el benchmark de ESA".

**D9 — Reproducibilidad en tres niveles (clave para que sea open source usable).** Problema: el stack oficial exige hardware que casi nadie tiene; un repo que nadie puede lanzar no sirve. Solución de diseño: como las capas [2]+[3]+[4] solo consumen los *scores* del detector (no el detector en vivo), se **cachean los scores calculados en el repo** (CSV pequeño). Con eso:
  - **Nivel Demo:** el notebook corre [2]+[3]+[4]+[5] a partir de scores cacheados. Lo lanza **cualquiera**, incluido un recruiter, en un portátil sin GPU ni Docker. Es el entregable número uno (README-first).
  - **Nivel Ligero:** VAE propio + capas, entrena en Mac/PC normal. Reproducible sin hardware especial.
  - **Nivel Oficial (opcional):** stack Docker/GPU + detector oficial + sello, documentado para quien tenga Linux+GPU.
  El diferencial ([2]+[3]+[4]) es siempre reproducible sin hardware pesado. La ruta pesada es opcional para todos.

---

## 5. Alcance MVP

Construir, en orden de prioridad:

1. **Ingesta + detector modular.** Cargar los datos oficiales de ESA-ADB, **Misión2 subconjunto ligero (canales 18-28)** (CSV de Zenodo, corren en Mac). Detector = **Window iForest vía PyOD** (CPU, baseline publicado por ESA, F0.5 0.949), detrás de la interfaz fija de D7 (ver D8). Fase 2 opcional: enchufar un detector deep oficial vía GPU cloud para ampliar comparación.
2. **Capa de incertidumbre.** Añadir cuantificación calibrada sobre el score de anomalía (conformal prediction o MC-dropout / quantile). Salida: no solo "anomalía sí/no", sino "anomalía con confianza C y banda de incertidumbre U".
3. **Explicabilidad por canal.** Atribución de qué variables/canales dominan cada detección (contribución por feature / reconstrucción por canal). Salida visual + tabular.
4. **Capa LLM de informe grounded (generador + juez).**
   - *Generador:* recibe SOLO la ventana detectada, los canales responsables y la incertidumbre, y redacta el informe. Regla dura: si no hay señal suficiente, lo dice; nunca rellena con conocimiento externo no grounded. Puede sugerir patrones plausibles etiquetados como hipótesis (ver D4), nunca como hecho.
   - *Juez (LLM-as-judge):* audita el informe generado contra los datos originales y marca/bloquea cualquier afirmación no soportada (ver D5). Es el guardrail de grounding automatizado.
5. **README + demo.** Un notebook o script de demo reproducible sobre un subconjunto, y el README como pieza central.

**Criterio de "hecho":** los 5 componentes corren de principio a fin sobre al menos una misión de ESA-ADB, con resultados reproducibles y README completo.

---

## 6. Arquitectura (componentes)

```
Telemetría ESA-ADB
      │
      ▼
[1] Detector (baseline: Telemanom / VAE)  ──►  score de anomalía por ventana
      │
      ▼
[2] Incertidumbre (conformal / MC-dropout)  ──►  confianza + banda U
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
[5] Salida: dashboard/README con casos de ejemplo
```

El núcleo diferenciador es [2]+[3]+[4]. [1] se apoya en código existente del benchmark para no reinventar.

---

## 7. Datos

- **Dataset:** ESA Anomaly Detection Benchmark (ESA-ADB). Telemetría real anotada de misiones de ESA (~17,5 años, 844 eventos, 148 anomalías en las dos misiones del benchmark).
- **Repo oficial (canónico):** `github.com/kplabs-pl/ESA-ADB` — el del consorcio que lo construyó (KP Labs + Airbus DS + ESOC). Es el punto de referencia.
- **Regla:** cero datos inventados; todo resultado trazable al dataset.

### Qué necesitas para arrancar

- **Código:** `github.com/kplabs-pl/ESA-ADB` — framework de benchmarking sobre TimeEval; reproduce todos sus experimentos y admite que añadas tu propio algoritmo.
- **Dataset (ESA-AD):** en Zenodo. La versión completa (3 misiones, 224 canales, 1430 eventos anotados) está en `zenodo.org/records/15237121`. La que pide el README del repo son las carpetas `ESA-Mission1` / `ESA-Mission2` desde `doi.org/10.5281/zenodo.12528696`.
- **Paper:** `arxiv.org/abs/2406.17826` — leerlo antes de tocar código. Define 9 requisitos operativos y 5 métricas; hallazgo clave: los algoritmos estándar aún no sirven para deployment real (justo el hueco que ataca este proyecto con la capa trustworthy).
- **Atajo con feedback objetivo:** competición Kaggle activa `kaggle.com/competitions/esa-adb-challenge`. Someter ahí da una métrica pública verificable en su propio leaderboard, más diferencial que un notebook suelto.
- **Licencia:** el código del repo `kplabs-pl/ESA-ADB` es **MIT** (verificado) — permisiva, permite publicar encima. Falta verificar la del **dataset** en Zenodo antes de publicar. Citar a ESA/ESOC + Airbus + KP Labs en el README.
- **Tamaño de los datos:** ~3-4 GB por misión. **Ligeros — caben y se procesan en Mac sin problema.** Los 512 GB / 64 GB RAM del stack oficial NO son para el dato: son para correr su pipeline Docker completo (preprocesado + todos los experimentos + artefactos de todos los algoritmos). El dato es ligero; lo que pesa es su maquinaria.
- **Hardware del stack oficial (verificado en el repo):** los detectores oficiales (Telemanom-ESA, DC-VAE-ESA) son **contenedores Docker** que exigen **Linux/WSL2 + GPU NVIDIA (compute ≥7.1) + 32-64 GB RAM + ~512 GB disco**. No corren en Mac tal cual → requieren GPU cloud (Fase 2, ver D8). Los **datos** (CSV) sí se bajan y usan en cualquier máquina, incluido Mac.
- **Regla de dataset (innegociable):** el dato de ESA no se sustituye por otro benchmark (NASA SMAP/MSL, etc.). El activo del proyecto es "resuelvo el problema de ESA con los datos de ESA". Cambiar el dataset tiraría la narrativa que conecta el repo con el puesto. Lo que sí se sustituye es la *maquinaria pesada* (stack Docker/GPU) por un VAE propio ligero en Fase 1.

---

## 8. Stack técnico

Python. PyTorch o el framework que use el baseline del repo. Librerías de conformal prediction (p. ej. MAPIE) o implementación MC-dropout propia. Matplotlib/Plotly para las visualizaciones de atribución. Capa LLM vía API con prompt de grounding estricto (o modelo local si se prefiere offline, coherente con el argumento edge). Repo con `requirements.txt`, seeds fijadas, reproducibilidad.

---

## 9. Criterios de éxito (qué hace que el repo puntúe)

- **Reproducible:** alguien clona, sigue el README y obtiene los mismos resultados.
- **Comparable:** la detección iguala o se acerca a un baseline publicado en ESA-ADB (no hace falta ganar; hace falta ser serio).
- **Diferenciado:** la incertidumbre está calibrada (métrica de calibración reportada) y la explicabilidad es real, no decorativa.
- **Honesto:** el informe LLM nunca afirma más de lo que la señal soporta; casos de "no sé" incluidos a propósito.
- **Legible:** el README lo entiende un recruiter técnico en 3 minutos.

---

## 10. Estructura del repo y README (README-first)

El recruiter lee el README, no el código. Es el entregable número uno.

```
esa-adb-trustworthy-agent/
├── README.md            ← pieza central
├── requirements.txt
├── data/                ← instrucciones de descarga (no el dataset)
│   └── cached_scores/   ← scores del detector precalculados (D9) → demo sin GPU
├── src/
│   ├── detect.py        ← [1]
│   ├── uncertainty.py   ← [2]
│   ├── explain.py       ← [3]
│   └── report.py        ← [4] capa LLM
├── notebooks/
│   └── demo.ipynb       ← [5] recorrido reproducible
└── results/             ← figuras y métricas
```

**README — secciones:**
1. **Problema** (1 párrafo): triar anomalías de telemetría con confianza y contexto, no con flags ciegos.
2. **Qué hace** (bullets + un GIF/figura del informe).
3. **Por qué importa para operaciones espaciales** (grounding, incertidumbre, edge → menos downlink).
4. **Resultados** (tabla: detección vs baseline + métrica de calibración).
5. **Cómo reproducir** (comandos).
6. **Limitaciones y honestidad** (qué NO hace, qué es análogo/argumentado).
7. **Créditos y licencia** (ESA/ESOC, Airbus, KP Labs).

---

## 11. Plan y timebox

**Regla marco:** la candidatura (carta + CV + docs) se envía el **28 jul pase lo que pase**. Este proyecto va en paralelo y solo después de EF (6 jul) y de dejar la aplicación cerrada.

| Día | Entregable |
|---|---|
| 1 | Ingesta Misión2 ligero (canales 18-28, en Mac) + Window iForest de PyOD corriendo + interfaz modular de detector (D7) |
| 2 | Capa de incertidumbre calibrada sobre el score |
| 3 | Atribución por canal + visualizaciones |
| 4 | Capa LLM de informe grounded (generador + juez) + casos "no sé" |
| 5 | README, demo reproducible, limpieza, publicar repo |

**Fase 2 opcional (solo si sobra tiempo tras día 5):** montar GPU cloud (~40 €), correr el detector oficial DC-VAE-ESA/Telemanom-ESA, enchufarlo vía D7 y reproducir la métrica oficial → ganar el sello. Y/o someter a la competición Kaggle para métrica pública verificable. Nada de esto bloquea el MVP.

**Stop duro: 24 jul.** Si a esa fecha no llega a calidad, la aplicación se envía sin el repo y la carta cubre el hueco con el puente trustworthy-AI. El link al repo entra en la carta **solo** cuando esté vivo y público.

---

## 12. Riesgos y mitigaciones

- **Scope creep** → el core es [2]+[3]+[4]; [1] se apoya en código existente. No pulir de más.
- **Hardware del stack oficial** → el repo oficial exige Linux + GPU NVIDIA + 32-64 GB RAM + ~512 GB disco; no corre en Mac. Mitigación: plan de dos fases (D8) — Fase 1 VAE propio en Mac garantiza el proyecto; el stack oficial es Fase 2 opcional vía GPU cloud.
- **"Un par de días" se convierte en semana** → timebox duro y stop el 24 jul.
- **Overclaiming** (fingir despliegue a bordo o datos que no son) → framing honesto: edge-deployability se argumenta; resultados trazables al dataset.
- **Repo a medias hunde más que ninguno** → o sale con calidad dentro del timebox, o no sale y no se menciona.
- **Licencia del dataset** → verificar antes de publicar.

---

## 13. Extensiones futuras (NO ahora)

Streaming/online detection, despliegue real en hardware edge, comparación multi-baseline exhaustiva, y la **capa híbrida umbral determinista + ML** (D1). Todo esto es para después de aplicar; no bloquea nada.

**Extensión exploratoria "mejorar el benchmark" (post-MVP, SIN promesas).** Dos vías que el autor quiere probar tras montar los 5 módulos. Ambas son research empírico: se prueban, no se garantizan.

*Vía 1 — Mejora de algoritmo (Fable investiga SOTA + primeros principios).* Fable barre el SOTA reciente de TSAD y los primeros principios de Isolation Forest, propone modificaciones, y se prueban empíricamente.
  - **Norte factible:** el paper demuestra que el **postprocesado/thresholding pesa más que el algoritmo base** (Telemanom-ESA-Pruned ganó por su dynamic thresholding NDT, no por mejor red). Poner mejor thresholding/postprocesado sobre Window iForest es una palanca real y barata que el paper señala como decisiva → mover el número sin research imposible.
  - **Aviso:** un LLM no mejora por sí solo la métrica de detección; aporta ideas y código, la mejora se valida a mano.

*Vía 2 — Mejora de datos (combinar/aumentar datos para el mismo algoritmo).* Técnicas ordenadas de más a menos tractable:
  - **Data augmentation** dentro de la misma misión (ruido, time-warping). Tractable.
  - **Usar canales no-target como contexto** (el dataset los provee justo para "apoyar la detección"). Tractable.
  - **Transfer/combinación entre misiones.** La más ambiciosa y traicionera: Misión1 (76 canales/4 subsistemas) y Misión2 (100/5) tienen estructuras distintas, no se apilan con `concat`. Research real ("generalización", citada en el paper).

*Avisos comunes a ambas vías:*
- **Techo en Misión2 ligero:** ya está en 0.949 → margen escaso. Donde mejorar importa es el **set completo (~0.07)**, problema abierto que nadie ha resuelto. No prometer batirlo.
- **NO usar Misión3:** el paper la descarta explícitamente (anomalías triviales/escasas, muchos gaps y segmentos inválidos). Verificado en pág. 4.
- **La mejora REAL y garantizada** no está en estas dos vías, sino en la capa que ESA no tiene ([2]+[3]+[4]): hacer la detección fiable y auditable. Eso es "mejorar el benchmark" en el sentido que el propio paper pide. Las dos vías son bonus exploratorio, no el core.
