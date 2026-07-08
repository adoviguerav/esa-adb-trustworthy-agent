# M2 — Hallazgo de la deriva (p fijo vs rolling) y camino al F0.5 ideal

Registro del hallazgo sobre calibración conformal en presencia de deriva temporal, y de
cómo se pasa de lo que hay hoy (Fases 1-3b) al F0.5 óptimo (Fase 4-5). Ver gráfico:
`results/m2_drift.png`.

---

## 1. Punto de partida: qué es un p-valor y las dos variantes

El detector da un **score continuo** por ventana (más alto = más raro; escala arbitraria).
El p-valor conformal lo traduce comparándolo con una **referencia de scores normales**:

```
p = (nº de scores normales de referencia >= score + 1) / (n_referencia + 1)
```

p pequeño → raro vs lo normal → anomalía. p grande → común → normal. `P(p<α) ≤ α` sobre
datos normales (bajo intercambiabilidad) → cortar en α controla la tasa de falsas alarmas.

Dos formas de construir esa **referencia**:

- **p FIJO (`conformal.py`):** una sola referencia congelada = ventanas normales
  independientes (1 de cada 17) del **tercio 1** del test. Se calcula una vez y no cambia.
- **p ROLLING (`rolling.py`):** referencia **móvil y causal**. Para cada bloque de ~20.000
  ventanas, se recalibra contra las 20.000 ventanas normales independientes más recientes
  **estrictamente en el pasado** (nunca el futuro). Imita a un detector online que se
  re-ajusta con telemetría normal reciente.

---

## 2. Qué está pasando (el hallazgo)

**La distribución de "lo normal" NO es estable en el tiempo — tiene ráfagas.** Hay episodios
donde telemetría **etiquetada como normal** puntúa alto (parece rara), y luego vuelve a
calmarse. No es deriva lenta de nivel: la **media** del score normal es plana en todo el test;
lo que se mueve en ráfagas es la **cola superior** (ver panel superior del gráfico: el p95 del
score normal pica muy por encima del umbral congelado del tercio 1, mientras la media no varía).

Causa raíz: **el detector mide rareza, y rareza ≠ anomalía.** El IForest da score alto tanto
a "raro-anómalo" como a "raro-pero-normal", y no los distingue. Las ráfagas son episodios
**localizados** de telemetría rara-pero-normal; entre ellas, el tercio 3 es tan calmado como
el tercio 1 (medido: la fracción de normales del tercio 3 por encima del umbral del tercio 1
es 0.039, < 0.05 → en agregado NO es "todo lo posterior más raro", solo lo son las ráfagas).

**Consecuencia:** en las ráfagas, montones de ventanas normales superan el umbral → falsas
alarmas → la cobertura por bloque salta (hasta 0.3–0.98 en bloque fino; ~0.14 si se promedian
bloques gruesos, que ocultan los picos; objetivo 0.05). Entre ráfagas, ~0.

**Rolling NO lo arregla:** está pensado para deriva gradual; los saltos son más rápidos que
su bloque de refresco. Medido: vaivén por bloque similar (rolling std ≈ fijo std, ambos
malos). El agregado (~5%) ENGAÑA porque promedia picos altos con valles a cero.

**Esto NO invalida M2.** La calibración funciona la mayor parte del tiempo (entre ráfagas);
el fallo es del detector+datos, no de conformal; y M2 aporta confianza graduada + abstención
+ **autodiagnóstico honesto** (pillamos el problema PORQUE M2 mide su propia cobertura). Las
ráfagas "raro-pero-normal" incluso podrían señalarse como *"telemetría inusual, revisar"*.

**Reencuadre clave (medido): el punto de operación que reportamos SORTEA la deriva.** La deriva
golpea el **α-garantía** (0.05 → FP 0.153 en validación), pero NO el **α-óptimo de F0.5** (2e-5).
Motivo: los eventos reales tienen p en el **suelo** (más raros que TODA la calibración); las
ráfagas normales quedan un pelín por encima. Al cortar en el extremo (α≈suelo) esquivas la
mayoría de ráfagas. Medido en validación con α*=2e-5:

```
marcadas 1.25% de ventanas · precisión 0.85 · recall 0.95 · F0.5 0.868
```

Recall 0.95 y precisión 0.85 — **los dos altos**, no "alta precisión / recall bajo". Caza el 95%
de los eventos con 85% de precisión. Subir α a 4e-5 → la precisión se hunde a 0.61 (entran las
ráfagas): confirma que el buen punto está justo en el suelo. (Todo en validación; test-final lo
confirma en la Fase 5.)

---

## 3. Decisión: probar AMBAS para el F0.5

Como ninguna gana claramente en cobertura y lo que importa para el benchmark es el **F0.5
event-wise**, no elegimos a ojo. **Dejamos las dos calculadas** (`p_test.npy` fijo,
`p_test_rolling.npy` rolling) y **que decida el número**: en Fase 4 se optimiza α sobre las
dos y se reporta la que dé mejor F0.5. La **fija** queda como primaria para el relato de
cobertura (simple, transparente); **rolling** como comparación honesta del intento de
corregir deriva. NO se tunean sus parámetros mirando el test (peeking).

---

## 4. De lo que hay hoy al F0.5 ideal (Fase 4-5)

Estado actual (cacheado en `data/cached/`):
- `scores_continuous.npy` — score continuo por ventana (Fase 1).
- `split.npz` — tercios calib/valid/test + máscara de ventanas normales (Fase 2).
- `p_valid.npy` / `p_test.npy` — p FIJO (Fase 3).
- `p_valid_rolling.npy` / `p_test_rolling.npy` — p ROLLING (Fase 3b).

Camino al F0.5 óptimo:

```
Para cada variante de p (fijo, rolling):
  1. Rejilla de α, fina y BAJA (log ~1e-4 → 0.05; NO 5%, que da eventos falsos a montones).
  2. Para cada α:
       binariza VALIDACIÓN: anomalía si p < α
       mapea ventana→punto con el mismo np.pad(ws//2) que ESA
       calcula EW_F_0.50 con ESAScores (event-wise) en validación
  3. α* = el que maximiza F0.5 en VALIDACIÓN (nunca en test → no peeking).
Elegir la variante (fijo/rolling) con mejor F0.5 en validación.
Reportar en TEST-FINAL (una vez):
  - EW_F_0.50 con α* + recall + F2
  - baseline M1@tercio-final (predict binario de M1 por la MISMA ESAScores) → comparación justa
  - cobertura real por ventana + comentario honesto de la deriva/ráfagas (este hallazgo)
```

Notas clave:
- **α óptimo ≠ α de la garantía del 5%.** El de la garantía es por ventana; el de F0.5 es por
  evento y sale mucho más bajo. Son dos historias separadas (ver `.agents/plans/m2-uncertainty.md`).
- El ballpark inicial de α sale de la tasa de anomalías (~3.6% de puntos), pero el ideal se
  **optimiza** en validación.
- El F0.5 de M2 se mide sobre el tercio-final → es un número aparte del 0.9487 de M1 (full
  test). Por eso el baseline M1@tercio-final: para comparar peras con peras.
