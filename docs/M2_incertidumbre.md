# M2 — Incertidumbre, explicado simple

Objetivo de M2: coger el resultado del detector (M1) y convertirlo en algo de fiar —
una **confianza en %** por cada aviso, y la capacidad de decir **"no sé"** cuando dudamos.

---

## 1. El problema

M1 (el detector) da un **número por ventana**: el "score". Por ejemplo, +0.09.

Ese número, solo, **no significa nada** para una persona:
- ¿+0.09 es mucho o poco?
- ¿Es anomalía segura, o casi normal?
- ¿Cómo de seguro está el sistema?

El score solo **ordena** (más alto = más raro), pero no te dice **cuánto** de raro en términos que entiendas. M2 arregla eso.

---

## 2. De dónde sale el score (rápido)

El detector es un Isolation Forest. Aísla puntos con cortes al azar:
- Un punto **raro** se separa con **pocos** cortes (está solo).
- Un punto **normal** necesita **muchos** cortes (está en medio del montón).

El score mide eso. En nuestros datos va de **-0.15 (muy normal)** a **+0.24 (muy raro)**. Pero
el valor exacto es **arbitrario**: en otro satélite el rango sería otro. Por eso el número
crudo no sirve tal cual — hay que darle significado.

---

## 3. La idea central: comparar contra lo normal (esto es "p")

**Analogía de alturas.** Mides a 1000 personas normales. Casi todas rondan 1,70 m.
Llega una persona nueva y quieres saber si es rara. **Comparas:**

> Cuentas cuántas de las 1000 normales son **igual de altas o más** que la nueva.

- Nueva = 1,72 m → 450 de 1000 son igual o más altas → **normal**.
- Nueva = 2,10 m → solo 1 de 1000 llega → **rara**.

Ese "cuántos de lo normal son igual o más extremos" es **p**:

```
p = (nº de datos normales igual o más raros que el punto nuevo) / (total de normales)
```

- **p grande** (0.45) → mucho de lo normal es así → **normal**.
- **p pequeño** (0.001) → casi nada normal es así → **anomalía**.

Para calcular p necesitas una lista de scores de datos **normales** de referencia — el
**conjunto de calibración** (datos normales que el detector no usó para entrenar).

---

## 4. La confianza en % sale directa de p

El porcentaje que le enseñas al operador es **100 − p**:

| p (contando) | Qué dices |
|---|---|
| p = 0,001 | "Solo el 0,1% de lo normal es así de raro → **99,9% de confianza** en que NO es normal" |
| p = 0,45 | "El 45% de lo normal es así → nada raro, normal" |

No hay paso mágico: **la confianza ya estaba en p, solo le das la vuelta (100 − p).**

> Matiz honesto: ese "99,9%" es confianza en que **no es normal** (control de falsas alarmas),
> no una probabilidad exacta de que sea una anomalía real. Decir "probabilidad de anomalía"
> requeriría saber cada cuánto ocurren, que no tenemos. Lo decimos claro, sin inflar.

---

## 5. α — la línea que decides tú

Al final hay que **decidir**: ¿aviso o no? Para eso pones una línea, **α**.

> "Aviso de anomalía cuando p < α" (por ejemplo α = 0.05).

α **lo eliges tú**, no sale de los datos. Es tu **presupuesto de falsas alarmas**:
- α bajo (0.01) → pocas alarmas, pero se te escapan más anomalías.
- α alto (0.10) → cazas más, pero más falsas alarmas.

Lo bonito: como p está bien calibrado, **elegir α = 0.05 te da ~5% de falsas alarmas**. La
línea significa algo. (Con el score crudo, cortar "en 0.09" no te decía nada.)

---

## 6. La decisión de 3 vías (el diferenciador)

En vez de forzar solo 0/1, M2 usa dos líneas y añade el **"no sé"**:

```
p:   0 ───── 0.05 ──────── 0.20 ───────── 1
     │ ANOMALÍA │  "NO SÉ"   │   NORMAL     │
     │  aviso   │ míralo tú  │  todo bien   │
```

Distingue tres estados: **seguro que SÍ**, **no tengo ni idea**, **seguro que NO**. Un flag
ciego (M1) no sabe hacer esto — siempre dice 0 o 1, aunque dude.

---

## 7. Comprobar que no mentimos (calibración)

**Analogía del meteorólogo.** Uno bien calibrado dice "70% de lluvia" y de esos días llueve
el 70%. Si dice 70% y llueve el 40%, miente sin querer (mal calibrado).

Nuestro sistema hace una promesa parecida: *"con α = 0.05 tendré 5% de falsas alarmas"*.
Hay que **comprobarlo**: coges datos que sabes normales y cuentas cuántos marca mal.

```
Promesa:  5% de falsas alarmas
Medido:   6.2%   (en nuestros datos)
```

Como el meteorólogo que dice 70% y llueve el 62%: cerca, pero no clavado. **Lo medimos y lo
reportamos tal cual** — no prometemos 5% y nos callamos que en realidad es 6.2%.

---

## 8. Por qué no es exacto (honestidad)

La garantía del 5% es **exacta** si los datos de calibración y los nuevos son "parecidos".
Pero son **series temporales**: ventanas vecinas se parecen, y el satélite cambia de régimen
con el tiempo. Eso rompe un poco la suposición → la garantía es **aproximada** (por eso 6.2%
y no 5.0%). Lo decimos abierto, y mencionamos que hay versiones para series temporales como
mejora futura, sin prometerlas.

---

## 9. Cómo conecta con M1

M1 ya daba un 0/1 usando un umbral **automático** que puso la librería (PyOD), colocado en el
**6% de contaminación** (la tasa de anomalías que había en el entrenamiento). Ese umbral es
**arbitrario**: no tiene garantía, no da confianza por punto, no sabe decir "no sé".

**M2 reemplaza ese umbral automático** por α (elegido con criterio) sobre los p-valores
calibrados. Misma palanca, pero ahora **con significado, confianza graduada y "no sé".**

---

## 10. Nota sobre falsos negativos (criterio del autor)

La métrica de ESA (F0.5) premia la **precisión** → penaliza las falsas alarmas. Pero
operativamente, un **falso negativo** (perderse una anomalía real en un satélite) suele ser
**peor**. Mantenemos F0.5 como métrica principal (para poder compararnos con el 0.949 de ESA),
pero **reportamos también el recall** y añadimos un comentario defendiendo este punto de vista.
La zona "no sé" ayuda: los casos dudosos van a revisión humana en vez de descartarse en silencio.

---

## Resumen en 5 líneas

1. El detector da un score que solo **ordena** rareza (número arbitrario).
2. **p** = comparas ese score contra datos normales → "qué porción de lo normal es igual o más raro".
3. **Confianza = 100 − p**, directa. p pequeño → confianza alta de anomalía.
4. **α** = la línea que eliges (tu presupuesto de falsas alarmas); da 3 vías: anomalía / no sé / normal.
5. **Calibración** = comprobar que la promesa (5% falsas alarmas) se cumple de verdad — y reportar el número real.
