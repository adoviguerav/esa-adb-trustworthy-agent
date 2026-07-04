# Skills Usage Guide — Por fases

Cómo usar skills + commands en cada fase de un proyecto. Skill por skill, con por qué y cuándo.

---

## Capas que carga Claude Code

Tres capas. User es `~/.claude/`, se carga siempre en cualquier proyecto. BASE es `<repo>/.claude/`, solo cuando copias plantilla "En la carpeta del proyecto". SaaS overlay encima de BASE solo cuando montas un proyecto con monetización (pagos, landing, emails).

---

## Fase 0 — Filtro de idea

Antes de invertir tiempo en una idea, decides si vale la pena.

**`torneo-ideas`** (Cowork, no Claude Code). Por qué: filtra ideas por potencial puro usando frameworks Thiel, Blank, YC, Bezos, Blue Ocean, Lean Startup. Cuándo: tienes una chispa de idea, no has hablado con nadie aún. Output: ranking comparativo. Es Paso 0 del pipeline "De chispazo a plan de entrada".

Solo pasa de aquí lo que sobrevive el ranking.

---

## Fase 1 — Discovery y validación con personas

Idea filtrada, ahora valida con humanos reales.

**`office-hours`**. Por qué: brainstorming estructurado tipo YC con 6 preguntas forzosas (demand reality, status quo, desperate specificity, narrowest wedge, observation, future-fit). Cuándo: la idea está cruda y necesitas atacar premisas antes de codear nada. Output: design doc. No escribe código.

Si lead clínica: `devon-investigar-clinica`, `devon-preparar-discovery`, `devon-analizar-discovery`. Si lead healthtech: `devon-investigar-healthtech`.

---

## Fase 2 — Arrancar repo

Idea validada, montas proyecto.

Primero copias plantilla BASE al repo nuevo. Si es SaaS, copias overlay encima.

**`/define_project`**. Por qué: Q&A guiado genera PRD.md + CLAUDE.md + README.md sin asumir nada. Lee templates de `.claude/templates/` y los ofrece como base. Cuándo: repo recién creado, sin código aún.

**`plan-ceo-review`**. Por qué: critica scope en modo CEO. Cuatro modos — EXPANSION (sueña más grande), SELECTIVE (cherry-pick expansiones), HOLD (rigor máximo del scope actual), REDUCTION (corta al mínimo viable). Cuándo: tienes plan inicial y dudas si es ambicioso/ajustado.

**`plan-eng-review`**. Por qué: critica plan técnico — arquitectura, data flow, edge cases, cobertura tests, performance. Cuándo: vas a empezar a codear y quieres bloquear errores de diseño antes.

**`plan-design-review`**. Por qué: critica decisiones de UI en plan mode antes de implementar. Cuándo: el proyecto tiene componente visual.

---

## Fase 3 — Implementar feature

Plan validado, toca codear.

**`/plan <feature>`**. Por qué: análisis profundo del codebase + research externo + plan de implementación con tareas paso a paso. Cuándo: feature no trivial.

Si el plan necesita review extra: pasas otra vez por `plan-ceo-review` o `plan-eng-review`. Son skills distintas del command — `/plan` GENERA el plan, los review skills lo CRITICAN.

**`/implement <ruta-del-plan>`**. Por qué: ejecuta el plan generado, va por las tareas en orden, valida, corre tests. Cuándo: tienes plan aprobado.

Mientras codeas, varias skills se activan solas según contexto:

**`security-review` (modo inline)**. Por qué: 10 secciones con patrones concretos en TypeScript/Next/zod/Supabase (secrets, input validation, SQL injection, auth, XSS, CSRF, rate limiting, sensitive data exposure, blockchain, dependencies). Cuándo: estás tocando auth, pagos, secrets, file uploads, APIs nuevas.

**`tdd-workflow`**. Por qué: workflow TDD estricto con cobertura mínima 80%. Cuándo: trabajas a TDD.

**`backend-patterns`, `postgresql-table-design`, `supabase-postgres-best-practices`, `typescript-advanced-types`, `vercel-react-best-practices`, `coding-standards`**. Por qué: skills de referencia técnica que cargan cuando tocas su dominio. No las invocas — Claude las consulta sola cuando ve patrones relevantes.

---

## Fase 4 — Debug

Algo se rompe.

**`investigate`**. Por qué: 5 fases con Iron Law — NO HAY FIX SIN ROOT CAUSE. Investiga, analiza patrones (race condition, nil propagation, state corruption, integration failure, config drift, stale cache), prueba hipótesis, implementa fix mínimo, verifica con regression test. 3-strike rule: si 3 hipótesis fallan, para y replantea arquitectura. Cuándo: hay bug, error, stack trace, "iba ayer y hoy no".

**`security-review` (modo audit)**. Por qué: si el bug huele a vulnerabilidad, carga `audit.md` — 7 fases sistemáticas (attack surface, secrets archaeology, dependencies, CI/CD, webhooks, LLM security, OWASP Top 10). Confidence calibration: solo reporta findings con confianza ≥8/10 en modo diario. Cuándo: sospechas de exploit, alguien reportó algo raro, antes de deploy a prod.

**`qa-only`**. Por qué: testea webapp en navegador y genera reporte con screenshots + repro steps, NO toca código. Cuándo: quieres solo el inventario de bugs sin que Claude empiece a arreglar nada.

Si compartes el reporte: `make-pdf`.

---

## Fase 5 — QA visual (proyectos con UI)

UI implementada, toca pulir.

Aquí no hay skill para crear visuales — eso lo hace **Claude Design** (Anthropic Labs, abril 2026). Claude Design construye design system automático leyendo tu codebase, genera HTML/React/SVG nativo, explora variantes con sliders custom. Sustituye lo que harían skills tipo design-consultation, design-html, design-shotgun (por eso no están). Acceso: Claude Pro / Max / Team / Enterprise.

Lo que SÍ tienes en skill:

**`design-review`**. Por qué: audita visualmente un site DESPLEGADO, encuentra inconsistencias de spacing, jerarquía, AI slop patterns, slow interactions, y los arregla iterativamente en código con commits atómicos + screenshots before/after. Cuándo: el site ya existe en vivo y necesitas pulir visualmente.

**`plan-design-review`** (ya en Fase 2 también). Por qué: cuando hay decisiones de diseño en un plan y quieres criticarlas antes de implementar. Cuándo: estás en plan mode con scope UI.

---

## Fase 6 — Auditoría periódica

Cada cierto tiempo, mides salud.

**`health`**. Por qué: dashboard 0-10 con trend. Wrappea linter, type checker, test runner, dead code detector, shell linter del proyecto. Cuándo: quieres ver si el código está mejor o peor que la semana pasada.

**`security-review` (modo audit)**. Por qué: misma skill que en debug pero ejecutada periódicamente. Modo diario es 8/10 confidence gate (zero noise). Modo comprehensive (mensual) es 2/10 bar (full coverage). Cuándo: cierre de sprint, antes de release, o calendar reminder mensual.

**`retro`**. Por qué: analiza git log + métricas de la semana, identifica qué shipeaste, growth areas per-person (team-aware). Argumentos: default 7d, también 24h/14d/30d/compare. Cuándo: fin de semana de trabajo o fin de sprint.

Si compartes el retro con cliente o equipo: `make-pdf`.

---

## Fase 7 — Pausar y retomar

Cambias de contexto.

**`context-save`**. Por qué: snapshot del estado de sesión — git state, decisiones tomadas, work-in-progress, archivos abiertos. Cuándo: dejas la sesión a medias y quieres retomarla limpiamente más tarde.

**`context-restore`**. Por qué: carga el snapshot más reciente. Cuándo: arrancas sesión nueva donde dejaste la anterior.

**`/context`** (command, no skill). Por qué: lee el estado VIVO del proyecto AHORA — git, archivos modificados últimos 7 días, TODOs/FIXMEs. NO restaura sesión guardada, lee la realidad actual. Cuándo: abres un proyecto que no tocas desde hace meses y necesitas orientarte.

`/context` y `context-save/context-restore` no se solapan. Uno lee proyecto, el otro lee tu memoria de trabajo.

---

## Fase transversal — Guardarraíles

Activos siempre en background.

**`careful`**. Por qué: avisa antes de ejecutar comandos destructivos — `rm -rf`, `DROP TABLE`, `git reset --hard`, `git push --force`, `kubectl delete`, `docker system prune`, `dd if=/dev`. Excepciones seguras pre-configuradas (`rm -rf node_modules`, `.next`, `dist`, etc.). Override siempre disponible. Cuándo: SIEMPRE. Es defensa en profundidad — además del hook de settings.json que ya bloquea patrones críticos a nivel sistema.

**`security-review` (inline)**. Ya descrita. Se activa sola cuando ve código sensible.

---

## Utilidades sueltas

**`make-pdf`**. Por qué: markdown → PDF profesional con TOC, headers, page numbers, watermark DRAFT diagonal, curly quotes, em dashes. No es draft, es entregable. Cuándo: vas a compartir reporte/análisis/retro con cliente o equipo y quieres formato decente.

**`scrape`**. Por qué: pull data read-only de URLs. Para mutating (form fills, clicks), no usar esta. Cuándo: necesitas extraer info recurrente de una página. Para un fetch puntual, mejor `WebFetch` (built-in, más simple).

---

## Slash commands en User (`~/.claude/commands/`)

Disponibles en TODO proyecto sin copiar.

**`/context`**. Lee estado actual del proyecto. Empezar sesión, orientarte.

**`/define_project`**. Q&A para generar PRD/CLAUDE/README. Arrancar repo sin código.

**`/plan <feature>`**. Plan profundo con análisis de codebase + research. Antes de implementar feature no trivial.

**`/implement <plan>`**. Ejecuta plan generado por `/plan`. Después de tener plan validado.

---

## Skills propias en Cowork

Plano distinto al de Claude Code. No interfieren.

`torneo-ideas` (Paso 0 del pipeline de ideas, ya descrita en Fase 0). Los `devon-*` son CRM/discovery/leads para clínicas y healthtech — investigar clínica, preparar discovery, analizar reunión, escribir mensajes warm, cold emails, posts LinkedIn, revisar pipeline. `outreach-system` para contactos masivos. `copywriting-ai` para landings y emails. `skill-creator` para crear nuevas skills.

---

## Anti-patterns

No metas todo en User. Skills universales solo si aplican a CUALQUIER proyecto. Skills de frontend van a BASE. Skills de monetización van a SaaS overlay.

No dupliques. Si una skill nueva solapa con una existente, elige una. Pasó con `cso` (descartada) vs `security-review` (mejorada con conceptos de cso).

No @importes esta guía en CLAUDE.md. Es referencia para ti, no contexto que se carga en cada sesión.

Vigila ~12 skills por scope. Progressive disclosure solo carga name + description en metadata, pero pasado 12 skills Claude empieza a fallar al elegir.

---

## Budget actual — cuándo recortar

11 skills en User + 11 en BASE = 22 metadata cargadas al arrancar proyecto. Techo del sweet spot Anthropic.

Recorta solo si notas degradación real (Claude elige mal o falla al invocar).

Primer recorte (user): `scrape` y `make-pdf`. Usos esporádicos.

Segundo recorte (user): `retro` si no haces retrospectivas semanales.

Último recurso (BASE): mover `design-review`, `plan-design-review`, `qa-only` a addon `addons/frontend-toolkit/` que solo copies a proyectos con UI.

No optimices preventivamente.

---

## Cuándo crear skill nueva

Cuatro criterios. Has hecho esta tarea 3+ veces dando siempre el mismo contexto. La tarea tiene pasos repetibles y verificables. No existe skill que lo cubra. La description puede ser específica con triggers claros.

Si cumple, `skill-creator` o las [best practices de Anthropic](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
