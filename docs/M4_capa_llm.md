# M4 · Capa LLM — aviso trustworthy en dos momentos

Módulo [4] del agente. M1 detecta, M2 calibra confianza, M3 localiza canales; M4 convierte
todo eso en **el aviso que lee el operador** — y garantiza, de forma medible, que ese texto
no afirma nada que los datos no soporten. Es el diferenciador del proyecto (duties ESA:
*insights from mission data* + *AI trustworthiness*).

## Los dos momentos

```
telemetría (ventana a ventana) ──► el detector marca la 1ª ventana rara
   ▼
① INICIO — start-flag             plantilla determinista, SIN LLM, ~100 bytes
   "ANOMALY START t=... | ch 20,18,19 | intensity high (score 0.002) | conf>0.9999 (saturated)"
   por qué sin LLM: latencia cero + el evento está a medias + downlink mínimo
   ▼   ... el evento transcurre ... vuelve la calma (gap) → el evento CIERRA
② FIN — brief auditado            RAG + LLM + dos guardarraíles
   tabla de hechos (verbatim M3) + tabla de vecinos (retrieval) + brief (prosa auditada)
```

El pipeline (`pipeline.py`) es una **máquina de estados sin lookahead**: en la ventana N
solo usa información ≤ N. Streaming y batch difieren solo en el driver que la alimenta
(`for` sobre caches replay / `while` sobre feed vivo) — la lógica no puede distinguirlos.

## Los dos carriles de datos

Cada dato viaja por uno de dos carriles, nunca por ambos:

- **Carril determinista** → tablas del aviso: números exactos, verbatim de M3/retrieval
  (byte-igual, testeado). Ids de vecinos, similitudes, %, intensity, priority, timestamps.
- **Carril narrativo** → el LLM: SOLO nombres (canales, grupos, unidades) y palabras
  cualitativas **precalculadas por código** (familiaridad por umbrales fijos, duración
  humana, nota de saturación, frase de acople). Únicos números que ve: duración y
  confianza en %. **Si no puede leer un número, no puede alucinarlo** — cada modo de
  fallo real observado (re-copiar %, manglar qué canales comparten grupo, adjetivar
  novelty) desapareció al mover ese dato del carril narrativo al determinista.

**El tradeoff detrás de este diseño:** con datos específicos delante, el LLM alucinaba.
Un modelo más potente probablemente lo gestionaría — pero el objetivo es un **modelo
pequeño corriendo a bordo** (espacio y cómputo en un satélite mandan). En vez de comprar
músculo, se redujo la superficie probabilística: prosa simple que solo cita, números
deterministas que no pasan por el LLM. Prosa menos rica a cambio de prosa que no puede
mentir.

## Guardarraíles (veredicto = precheck AND juez)

1. **Precheck** (léxico, sin LLM): todo token `channel_N`/`id_N`/`group_N`, número y
   timestamp del brief debe existir literal en el evidence. Mismo extractor para ambos
   lados (no puede desincronizarse).
2. **Juez** (LLM-as-judge, postura de fiscal): audita frase a frase contra el evidence.
   Bloquea causa raíz (D3), hipótesis sin etiquetar (D4), overclaim de certeza, vecinos
   no recuperados, novedad deshonesta, y alucinación semántica sin token falso.
3. **BLOCK** = el aviso baja igualmente con las tablas + "brief retenido" + razones del
   juez. La prosa bloqueada no viaja ni en `m4_alerts.json` (invariante testeado).

## RAG (retrieval determinista, sin embeddings)

Corpus = 644 anomalías anotadas (labels ⋈ anomaly_types). Similitud = índice de Tversky
(α=1, β=0.05) sobre conjuntos de canales ponderados por atribución. Guard anti-leakage
R3: solo vecinos con `end < inicio_del_evento` (el corpus ES la verdad anotada; el guard
está testeado sobre los 120 eventos, 0 fugas). El RAG **caracteriza** (a qué se parece),
no detecta. Explicable en una pizarra, reproducible, sin GPU.

## Evaluación: la cadena metrológica (ver plan F9-bis)

Regla de sistemas: **se fija el patrón → se calibra el instrumento → se afina el sistema.**

```
GOLDEN (18 casos etiquetados a mano = verdad humana)   ← el patrón: solo se ENDURECE
   └── certifica al JUEZ: precisión 1.00 (7/7) · recall 1.00 (11/11)
        └── el juez puntúa al GENERADOR en producción (120 eventos reales):
             v1: 116 PASS / 4 BLOCK (todos paráfrasis-que-desliza, cero hechos falsos)
             v2 (= v1 + regla "QUOTE, don't paraphrase"):
                probada primero SOLO en los 4 fallidos (4/4) → campaña completa:
                120/120 PASS, cero regresión en los 116 held-out
```

Disciplina aplicada y sus porqués:

- **Primero el instrumento**: afinar el generador contra un juez sin certificar =
  optimizar contra ruido (Goodhart). El golden va delante siempre.
- **Prompt versioning**: una versión usada JAMÁS se edita — nueva versión = nuevo archivo
  `prompts/*_vN.md` + puntero con changelog. El cache LLM distingue versiones solo.
- **Higiene anti-leakage del prompt**: al prompt solo entra vocabulario del sistema,
  jamás hechos de eventos concretos. El LLM no aprende (pesos congelados): el prompt es
  el único canal de entrada de nuestros datos, y se vigila.
- **Dev vs held-out**: v2 se afinó mirando 4 eventos (in-sample, declarado); los 116
  restantes no influyeron → su 116/116 es la métrica honesta.
- **Cache LLM = referencia congelada**: cache-first siempre (una entrada canónica no se
  re-rola jamás); el toggle solo gobierna el miss (API o error). La demo corre offline,
  sin API key, determinista.

**Framing honesto:** el golden es una *prueba de existencia* del guardarraíl sobre 18
casos — NO una garantía estadística. El 120/120 es el scorecard sobre esta misión y esta
configuración, no un teorema.

## Downlink (medido)

1.24 MB de ventanas de evento → 280 KB de avisos (**~4×**, comparación conservadora contra
solo los tramos anómalos). Contra bajar el stream completo del tercio de test (~130 MB),
**~460×**. Matiz honesto: en eventos diminutos el aviso pesa más que su telemetría cruda
(p. ej. 1.4 KB → 1.8 KB); la ganancia vive en los eventos largos, que son los que pesan.

## Scenario & Assumptions (suposiciones declaradas ≠ alucinación oculta)

1. **A bordo argumentado, no certificado**: Groq (cloud) = proxy del modelo pequeño
   on-board. La demo prueba la arquitectura, no el hardware.
2. **Replay declarado**: ESA-ADB es un benchmark de tierra (histórico anotado); la demo
   reproduce sus ventanas en orden simulando directo. La máquina de estados es
   streaming-capaz por construcción (sin lookahead, testeado).
3. **Canales anonimizados**: el sistema no sabe qué mide `channel_18` y NO lo inventa
   (afirmarlo = BLOCK del juez, caso D8 del golden). Catálogo semántico = extensión.
4. El "por qué" (causa raíz) es del operador (D3): el sistema detecta, localiza y da
   contexto histórico; no diagnostica.

## Extensiones documentadas (no implementadas)

Catálogo semántico de canales · clustering en familias de anomalías · vector DB para
conocimiento textual (manuales) · self-refine en BLOCK (re-generar con el feedback del
juez) · holdout multi-modelo (el seam `llm.py` lo deja a 1 línea de config) · mini-LLM
en el momento ① · sugerencia de acción vía telecommands (los datos no lo sostienen hoy).

## Números de referencia (congelados en tests)

| Qué | Valor | Test |
|---|---|---|
| Corpus RAG | 644 anomalías | `test_corpus_shape` |
| Anti-leakage R3 | 0 fugas / 120 eventos | `test_r3_no_leakage` |
| sim top-1 evento 33 | 0.8977905587388094 (id_638) | `test_reference_sim_event33` |
| Juez vs golden | precisión 1.00 · recall 1.00 | `test_golden_from_cache` |
| Scorecard generador (v2) | 120 PASS / 0 FLAG / 0 BLOCK | `test_alerts_scorecard` |
| Presupuesto start-flag | ≤160 bytes (máx real 107) | `test_alerts_scorecard` |
