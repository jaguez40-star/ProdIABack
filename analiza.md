# analiza.md — Motor de Análisis (Grupo 3 de motor_Q)

> **Qué es este documento:** especificación de implementación del **Grupo 3 · Analizar**
> del Motor Q v2 — desde que el clasificador enruta una pregunta a "analizar" hasta que sale la
> narrativa **HECHO → CAUSA → ACCIÓN** con su nivel de confianza. Es el hermano de `cuant.md`.
>
> **Audiencia:** Claude Code / el desarrollador que construya el responder de Analizar.
>
> **Regla madre (idéntica a Cuantificar):** *Python calcula y decide la tesis; el LLM solo redacta.*
> Aquí es aún más crítico: el LLM analista **tiende a inventar un rezago que no existe** (caso real
> verificado — ver §9). La disciplina anti-alucinación ya está codificada (`_reglas_tesis`) y se reusa.
>
> **Fecha:** 2026-08-02 · **Versión:** 1 (DRAFT para revisión)
> **Hallazgo central:** a diferencia de Cuantificar (que **construye** calculadoras), Analizar
> **ENVUELVE un motor que ya existe y corre en 139**: el endpoint `analisis.ejecutivo`. El trabajo es
> integración + decisión de alcance, no construir un motor. Es —potencialmente— el responder más
> rápido de montar de los tres, PERO el template dibujado pide 3 datos que la BD actual no tiene (§6).
>
> **Estado de verificación:** cada pieza reusable de este documento se leyó del código real
> (`analisis/api.py`, `routes/api.py`, `consulta_v2/`) el 2026-08-02, con número de línea. Los 3
> bloqueos de datos vienen de la sesión de análisis del 2026-07-30 (bitácora CLAUDE.md padre).

---

## 0. Resumen ejecutivo

"Analizar" responde el **por qué** y el **hacia dónde**: causas del rezago, campos que pesan,
proyección de cierre, recuperación de un valle, diferidas. La conclusión de la auditoría es una
**inversión respecto a Cuantificar**:

- **El motor ya está construido y afinado.** El endpoint [`ejecutivo()`](backend/app/features/analisis/api.py)
  (línea 1620) produce HOY, con Python y cifras reconciliadas: KPIs REAL/PPTO por producto, **gap
  descompuesto por campo** (bbl + %), **valle** de crudo, **pace de cierre**, **flags de severidad**,
  y una **síntesis** (rezago transitorio vs estructural, foco vs sistémico). Corre en 139.
- **Como responder de v2 está en CERO.** No existe `respuesta_analizar.py`; `maquina_q.py` solo
  nombra "analizar" en el diccionario de etiquetas. Clasificas "analizar" y no pasa nada.
- **El template del diagrama pide 3 líneas que los datos no sostienen** (DELTA vs snapshot previo,
  diferidas nuevas del mes, residuo de blancos) — §6. Hay que **redefinirlas o quitarlas**, no
  implementarlas contra datos inexistentes.

**Dos decisiones de arquitectura que gobiernan todo:**

1. **REUSAR `analisis.ejecutivo` por IMPORT directo — NO forkear.** `analisis` es el motor VIVO del
   tablero, no la v1 congelada. La regla "cero imports de `consulta/`" es sobre v1, no sobre
   `analisis`. Importarlo es el **Anillo 2 concretado** y **garantiza** que el chat y el panel den la
   MISMA lectura (misma función, imposible que deriven). Esto es MEJOR que Cuantificar, que forkea.
2. **"Analizar" NO es una intención, son cuatro** (§3). El responder necesita un **sub-router** que
   mande cada sub-intención a la pieza correcta del motor. Tres de las cuatro las cubre el ejecutivo;
   diferidas es una ruta aparte; economía (EBITDA) es la vía robustez de Cuantificar.

---

## 1. Arquitectura y ubicación

### 1.1 Dónde vive
Módulo nuevo en `backend/app/features/consulta_v2/`, simétrico a `respuesta_jerarquizar.py`:

```
consulta_v2/
  respuesta_analizar.py    # entrada del grupo: responder(texto, usuario) — como jerarquizar/cuantificar
  analizar/
    subrouter.py     # clasifica la sub-intención (causal / proyeccion / diferidas / economia) — Python
    causal.py        # envuelve analisis.ejecutivo → template HECHO/CAUSA/ACCIÓN
    proyeccion.py    # pace_crudo + valle_activo → "vamos camino de…" / "se recupera el…"
    diferidas.py     # lector de ECP_DIFERIDAS (crudo/gas por causa NV04) — reusa la ruta Flask
    confianza.py     # asigna ALTA/MEDIA/SIN_DATOS por bloque, RUNTIME (§7)
    plantilla.py     # arma la narrativa 4-bloques desde el JSON del motor
  # NO hay narracion.py propio: la prosa la produce ejecutivo.secciones (LLM-o-fallback, ya existe)
```

**🔑 NO hay endpoint nuevo, NO hay calculadora nueva.** El flujo es el único que ya existe:
frontend → `POST /consulta2/preguntar` → `maquina_q.clasificar()` → **inline** dentro de
`clasificar()`, patrón EXACTO de jerarquizar ([`maquina_q.py:217`](backend/app/features/consulta_v2/maquina_q.py#L217)):

```python
elif grupo == "analizar" and log:
    r = respuesta_analizar.responder(texto, usuario=usuario)
    if r:
        mensaje = r
```

### 1.2 Cómo se llama al motor (gotcha de FastAPI)
`ejecutivo()` es una **función-endpoint** (`entidad=Query(None), …`). Llamarla como Python plano NO
da `None` en los defaults: `Query(None)` devuelve un `FieldInfo`, no `None`. **Dos salidas limpias:**
(a) extraer el cuerpo de `ejecutivo` a una función plana `_ejecutivo_core(c, entidad, nivel, periodo)`
y que el endpoint la llame (refactor de 3 líneas, sin cambiar el tablero); o (b) invocar pasando los
args explícitos `ejecutivo(entidad="RUBIALES", nivel="campo", periodo=None)`. **Recomendación: (a)** —
deja una API interna limpia para consulta_v2 y no arriesga el comportamiento del endpoint.

### 1.3 Frontera LLM / Python (idéntica a Cuantificar, ya implementada en el motor)
| Etapa | Quién | Dónde ya existe |
|-------|-------|-----------------|
| Resolución de entidad + periodo | Python | `_ambito(c, entidad, nivel, periodo)` (coherencia chat↔tablero) |
| HECHO (severidad) | Python | `_flags_ejecutivo` (api.py:1308) |
| CAUSA (gap por campo) | Python | `_gap_campo` (api.py:1750) + `_comentarios_campo_mes` (evidencia) |
| Tesis (transitorio/estructural, foco/sistémico) | Python | bloque `sintesis` (api.py:1834) |
| Redacción de la prosa | LLM (o fallback) | `_reglas_tesis` + `_ejec_fallback` (api.py:997 / 1332) |
| Anti-alucinación | Python | REGLA CERO en `_reglas_tesis` (api.py:1024) |

---

## 2. El pipeline (texto → narrativa causal)

```
Clasificador (Etapa A) enruta a "analizar"
        │  (llega: texto + entidad_cruda opcional)
        ▼
1. SUB-INTENCIÓN  subrouter.py — Python: ¿causal / proyección / diferidas / economía? (§3)
        ▼
2. ENTIDAD        _ambito(entidad, nivel, periodo) — reusa el resolver del tablero
        │            sin entidad → alcance GLOBAL ECP (el ejecutivo lo soporta: scope="Global")
        ▼
3. MOTOR          causal/proyeccion → analisis.ejecutivo(...)  ·  diferidas → lector SQLite
        ▼
4. CONFIANZA      confianza.py — ALTA/MEDIA/SIN_DATOS por bloque, RUNTIME (§7)
        ▼
5. PLANTILLA      plantilla.py — HECHO/CAUSA/ACCIÓN(/DELTA) desde el JSON del motor
        ▼
6. ENVOLTORIO     intro cordial (LLM) + narrativa (hechos del motor) + cierre (contra-pregunta)
        │            reusa respuesta_base.py (el mismo envoltorio de jerarquizar/cuantificar)
        ▼
   Respuesta (contrato §8)
```

---

## 3. "Analizar" son CUATRO sub-intenciones (el sub-router)

Los patrones del clasificador ([`patrones_grupo.yaml:67`](backend/app/features/consulta_v2/config/patrones_grupo.yaml#L67))
mezclan cuatro preguntas distintas bajo una etiqueta. El sub-router (Python, por keywords sobre el
texto ya normalizado) las separa:

| Sub-intención | Dispara con | Motor que responde | Confianza |
|---------------|-------------|--------------------|-----------|
| **causal** | "por qué", "a qué se debe", "qué campos pesan", "detractores", "causas de", "explica" | `ejecutivo` → gap_campo + valle + comentarios | 🟢/🟡 |
| **proyección** | "cómo vamos", "vamos a llegar/cerrar", "proyección", "se ve recuperación", "tendencia" | `ejecutivo` → pace_crudo + valle_activo | 🟢 (crudo) |
| **diferidas** | "diferidas", "qué pasó con", "mantenimientos" | lector ECP_DIFERIDAS (NV04, crudo/gas) | 🟡 dev · 🔴 139 |
| **economía** | "EBITDA", "margen", "plata" | vía robustez (la misma de Cuantificar §5) | 🟡 |

🔑 **Tres de las cuatro ya las produce el ejecutivo en una sola llamada** — el `subrouter` decide qué
BLOQUE del JSON del ejecutivo se pinta, no llama a motores distintos. Solo **diferidas** y **economía**
salen de otra fuente.

---

## 4. Inventario de piezas reusables (auditado, con línea real)

Todo esto ya existe en `backend/app/features/analisis/api.py` y se consume, no se reescribe:

| Pieza | Línea | Qué entrega | Mapea a |
|-------|-------|-------------|---------|
| `ejecutivo()` | 1620 | el JSON completo (titular, gap_por_producto, valle, pace, flags, secciones, focos) | **todo el motor** |
| `_ambito()` | (usado 1633) | entidad→ids/vid, nivel+periodo aware | resolución + coherencia |
| `_flags_ejecutivo()` | 1308 | `producto_critico`/`gap_concentrado`/`valle_activo`/`pace_exigente` | **HECHO** |
| `_gap_campo()` | 1750 | detractores/compensadores por campo (gap bbl, real, meta, `concentracion_pct`, `eventos`) | **CAUSA/DELTA** |
| `_comentarios_campo_mes()` | (usado 1794) | comentarios del reporte por campo/mes | evidencia de CAUSA |
| `_valle_diagnostico_entidad()` | 824 | valle explicado POR la entidad | CAUSA (crudo) |
| `sintesis` (bloque) | 1834 | transitorio/estructural · foco/sistémico | la **tesis** |
| `_reglas_tesis()` | 997 | prompt ramificado + **REGLA CERO** | disciplina LLM |
| `_ejec_fallback()` | 1332 | las 4 secciones sin LLM (H4, default) | **ACCIÓN/prosa** |
| `hist_anio` (bloque) | 1731 | promedio de meses anteriores con REAL, por producto | **DELTA redefinido** (§6) |
| Ruta `/api/diferidas/frecuencia` | routes/api.py:375 | `impacto` por CAUSE_NIVEL4 en volumen (ACEITE/GAS_PERDIDO) | sub-intención diferidas |

**Forma del retorno de `ejecutivo` (verificada, api.py:1927):**
```
{ entidad, encontrada, meta{scope,periodo,corte,generado_por,llm_diag},
  titular:[{producto,real,ppto,valor_pct,estado,texto} ×3],
  tarjetas, gap_por_producto{PROD:{detractores:[{campo,gap,real,meta,eventos}],
     compensadores, concentracion_pct, faltante_bruto, excedente_bruto}},
  valle{desde,hasta,min_fecha,magnitud_pct,dias}, eventos, pace_crudo{mtd,promedio_dia,
     requerido_dia,delta_pct,restantes}, flags:[…], secciones{insights,oportunidades,
     puntos_atencion,decisiones}, focos, sin_foco }
```

---

## 5. El template redefinido — HECHO / CAUSA / ACCIÓN (/DELTA)

El diagrama pide HECHO/CAUSA/ACCIÓN/DELTA. Contrastado con los datos disponibles, así queda cada
bloque (lo que **sí** se puede llenar hoy, con su fuente):

- **HECHO** 🟢 — *"CRUDO cerró mayo al 96,8% del presupuesto; {n} días bajo umbral / valle del 6 al 12
  de mayo."* Fuente: `flags` + `titular`. Determinista, Python. **Confianza ALTA.**
- **CAUSA** 🟢/🟡 — *"El faltante se concentra en CAJÚA (−1,2M bbl) y CPO-09; ~64% del déficit está en
  esos 2 campos."* Fuente: `gap_campo.detractores` + `concentracion_pct`. En crudo/gas: **ALTA**.
  La **evidencia textual** (`eventos` = comentarios del reporte) tiene **cobertura ~33%** sobre los
  detractores reales (medido) → cuando falta, se declara *"sin evento asociado en comentarios"* (ya lo
  hace `_ejec_fallback`), **no se inventa**. **Confianza MEDIA** en el *por qué* documentado.
- **ACCIÓN** 🟡 — *"Priorizar intervención en los 2 campos que concentran el faltante."* Fuente:
  sección `decisiones` (derivada del carácter del rezago). Es **consultiva, no prescriptiva** — hay
  que rotularla como tal. **Confianza MEDIA.**
- **DELTA** — el diagrama pide *"vs último push del mismo trigger"* → **IMPOSIBLE** (§6.1). **Se
  REDEFINE** a *"el mes vs su propio promedio del año en curso"* — dato que **sí existe** (`hist_anio`,
  api.py:1731). Ej.: *"CRUDO va en 88,9M vs promedio 2026 de 86,7M = +2,2M (por encima de su propia
  historia, aunque el PPTO lo marque corto)."* Esta redefinición es la que **acordaste el 30-jul**
  ("tres productos vs su promedio 2026"). **Confianza ALTA.**

---

## 6. Las 3 líneas bloqueadas por datos (sesión 30-jul) — decisión requerida

**No son bugs; son ausencias de datos.** Cada una necesita una decisión tuya:

### 6.1 DELTA "vs último snapshot del mismo reporte" → IMPOSIBLE con el esquema actual
`uk_mes UNIQUE` **NO incluye `reporte_id`** y el `ON CONFLICT DO UPDATE` reasigna `reporte_id`
(`ddl_v2_postgres.sql:287`) → **cada reporte diario SOBRESCRIBE la fila del mes**; no existe "cómo se
veía mayo hace 7 días" y **el histórico anterior ya se perdió**. Habilitarlo = añadir `reporte_id` a
`uk_mes` + re-ingerir, y **solo daría historia hacia adelante**.
→ **Decisión A1 — CERRADA (usuario 2026-08-02):** DELTA se redefine a **"vs promedio del año en
curso (2026)"** (§5, dato ya existe en `hist_anio`). El cambio de esquema (opción b) queda fuera de v1.

### 6.2 "Diferidas NUEVAS del mes" → sin solape temporal
La BD `ECP_DIFERIDAS` termina en **jul-2025**; para un mes de 2026 no hay diferidas "nuevas" que
cruzar. Lo que SÍ hay es el **histórico estructural** por causa NV04 (crudo/gas), que ya se pinta en
la pestaña Diferidas.
→ **Decisión A2 — CERRADA (usuario 2026-08-02):** la sub-intención diferidas responde el **patrón
histórico** ("las causas que más pesan históricamente son Formación 22,8%…"), **rotulado como histórico
2023–2025, NO del mes**. El enlace causa↔desviación-del-mes-puntual queda fuera de v1 (requeriría los
comentarios, cobertura 33%).

### 6.3 Residuo/causa de BLANCOS → no existe la fuente
`AVM_DATADIF` no tiene columna de blancos perdido (solo `ACEITE_PERDIDO`/`GAS_PERDIDO`). El **gap por
campo** de blancos SÍ existe (mensual, `gap_campo` lo calcula), pero su **atribución causal** (diferidas)
no.
→ **Decisión A3 — CERRADA (usuario 2026-08-02):** blancos responde HECHO + CAUSA-por-campo (dónde
falta), pero **declara** que no hay atribución de causa por evento ("no se dispone de diferidas de
blancos"). Sin inventar.

---

## 7. Niveles de confianza — RUNTIME, no hardcodeados

El tag `[confianza | fuente]` que pediste el 30-jul debe calcularse **en vivo**, porque depende del
entorno:

| Nivel | Significado | Cómo se decide |
|-------|-------------|----------------|
| 🟢 **ALTA** | cifra reconciliada, Python | HECHO, DELTA-vs-2026, CAUSA-por-campo de crudo/gas |
| 🟡 **MEDIA** | hay dato con salvedad | evidencia textual (cobertura 33%), diferidas históricas, ACCIÓN consultiva |
| 🔴 **SIN_DATOS** | no hay fuente | diferidas en 139 (BD 954MB **no subida**), economía en INGESTA, causa de blancos |

🔑 **La confianza de "diferidas" es MEDIA en dev y SIN_DATOS en 139** — porque la BD de 954 MB no está
en el servidor. `confianza.py` debe **probar la conexión** (¿responde el lector SQLite / la ruta
Flask?) y degradar el tag, no asumir. Un gerente en 139 ve el tercer nivel; hay que decirlo honesto.

---

## 8. Contrato de respuesta (JSON)

```json
{
  "grupo": "analizar",
  "sub_intencion": "causal | proyeccion | diferidas | economia",
  "entidad": { "nombre": "CAJUA", "nivel": "campo", "fue_asumida": false },
  "periodo": "mayo 2026",
  "bloques": {
    "hecho":  { "texto": "…", "confianza": "ALTA",  "fuente": "flags+titular" },
    "causa":  { "texto": "…", "confianza": "MEDIA", "fuente": "gap_campo+comentarios",
                "detractores": [ {"campo":"CAJUA","faltante":1200000,"pct":42} ] },
    "accion": { "texto": "…", "confianza": "MEDIA", "fuente": "decisiones" },
    "delta":  { "texto": "…", "confianza": "ALTA",  "fuente": "hist_anio",
                "base": "promedio 2026" }
  },
  "situacion_general": "hay_rezago | sin_rezago",
  "avisos": [ "diferidas: histórico 2023–2025, no del mes en curso", "…" ],
  "prosa": "string — la narrativa causal, redactada por el LLM (ejecutivo.secciones) o fallback",
  "cierre": "¿Quieres ver el detalle por campo, o la proyección de cierre de {entidad}?"
}
```

**Rol del LLM:** redactar la narrativa desde el JSON YA calculado — **nunca** decidir el HECHO, la
CAUSA ni la dirección (transitorio/estructural). Eso lo fija Python (`sintesis` + `situacion_general`).
El fallback determinista (`_ejec_fallback`) es el entregable por defecto.

---

## 9. Reglas de honestidad (aplican a TODA respuesta)

1. **REGLA CERO — prohibido inventar un rezago.** Ya codificada (`_reglas_tesis`, api.py:1024). Caso
   real: CASTILLA al 102,7% y Gemma narró *"déficit significativo"* — la alucinación es lo grave.
   Cuando `situacion_general = sin_rezago`, el prompt se ramifica y el motor NO pide "la historia del
   déficit". **Reusar tal cual.**
2. **La CAUSA documentada ≠ la CAUSA inferida.** Si no hay comentario del reporte para el campo
   detractor, se dice *"sin evento asociado, requiere validación en campo"* — no se fabrica el porqué.
3. **Diferidas = histórico, rotulado.** Nunca presentar el patrón 2023–2025 como la causa del mes en
   curso (§6.2).
4. **Blancos sin causa por evento** (§6.3) — HECHO y CAUSA-por-campo sí; atribución causal no.
5. **DELTA es "vs promedio 2026", no "vs snapshot previo"** (§6.1) — y se dice cuál.
6. **Confianza siempre visible y runtime** (§7) — el gerente sabe si está viendo dato duro o inferencia.
7. **P50 solo a nivel ECP-global** (misma regla que Cuantificar) — nunca "vs P50" a nivel campo.
8. **Coherencia con el tablero** — como se REUSA `ejecutivo` (no fork), el número del chat y el del
   panel son el mismo por construcción. Nunca escribir SQL propio de gap/valle/pace.

---

## 10. NO soportado (rechazo explícito)

| Petición | Motivo |
|----------|--------|
| "¿por qué está corto?" como intención pura de causa sin entidad | resolver primero la entidad (contrapregunta) |
| atribución causal de blancos por evento | `AVM_DATADIF` sin columna de blancos (§6.3) |
| "diferidas de este mes / nuevas" | BD hasta jul-2025, sin solape 2026 (§6.2) |
| DELTA vs cómo se veía el mes en un reporte anterior | esquema no guarda historia por reporte (§6.1) |
| impacto económico / margen / NOPAT | sin modelo económico en INGESTA (solo EBITDA robustez, aceite) |
| valle de gas/blancos | el motor detecta valle SOLO sobre la serie diaria de CRUDO |
| causa a grano pozo | el grano de pozo no existe en INGESTA (alias de fuente) |

---

## 11. Fases de implementación

**FASE 1 — Causal + Proyección 🟢 (envolver el ejecutivo, la celda más sólida).**
1. Refactor `_ejecutivo_core` (§1.2) — función plana invocable desde consulta_v2.
2. `respuesta_analizar.py` + `subrouter.py` (causal/proyección) + `plantilla.py` (HECHO/CAUSA/ACCIÓN
   + DELTA-vs-2026) + `confianza.py`.
3. Envoltorio cordial (reusar `respuesta_base.py` — el mismo de jerarquizar/cuantificar).
4. Wiring inline en `maquina_q.clasificar()` + `_CTX` (memoria simétrica, como jerarquizar).
- **Gate:** golden ≥10 casos con entidad verificada a mano: (a) un rezago real (CAJÚA/crudo) →
  HECHO+CAUSA+concentración correctos; (b) una entidad EN META (CASTILLA 102,7%) → **NO inventa
  rezago** (prueba de REGLA CERO); (c) una proyección ("¿vamos a cerrar?") → pace correcto, verbo
  "va camino de"; (d) DELTA vs promedio 2026. `responder(log=False)` en golden/pytest (patrón H3).
  Paridad qwen2.5/gemma4.

**FASE 2 — Diferidas (histórica, rotulada).** `diferidas.py` (lector SQLite con `os.path.abspath`,
CWD-independiente — lección 24-jul; o proxy a la ruta Flask). Confianza runtime (MEDIA dev / SIN_DATOS
139 hasta subir la BD). Solo crudo/gas.

**FASE 3 — Economía (vía robustez).** Comparte `ejecutor_robustez.py` con Cuantificar (EBITDA, aceite,
rotulado "universo robustez"). Coordinar con el agente de Cuantificar para no duplicar el lector.

**FASE 4 (opcional, requiere decisión A1) — DELTA histórico real.** Solo si se decide añadir
`reporte_id` a `uk_mes` + re-ingerir. Da historia hacia adelante. Grande; fuera de v1 salvo pedido.

---

## 12. Riesgos y decisiones abiertas

| # | Riesgo / decisión | Estado |
|---|-------------------|--------|
| A1 | **DELTA vs snapshot previo imposible** (esquema) | ✅ **CERRADA**: DELTA = "vs promedio 2026" (`hist_anio`); esquema fuera de v1 |
| A2 | **Diferidas del mes** sin solape (BD → jul-2025) | ✅ **CERRADA**: histórico rotulado 2023–2025; enlace al mes fuera de v1 |
| A3 | **Causa de blancos** sin fuente | ✅ **CERRADA**: declarar ausencia; HECHO+CAUSA-por-campo sí |
| A4 | Cobertura de comentarios ~33% sobre detractores | Declarar "sin evento asociado"; ya lo hace el fallback — mitigado |
| A5 | Confianza depende del entorno (diferidas en 139) | `confianza.py` runtime, no hardcode — cablear |
| A6 | LLM inventa rezago inexistente | REGLA CERO reusada (`_reglas_tesis`) — mitigado |
| A7 | Llamar al endpoint como Python plano (Query gotcha) | Refactor `_ejecutivo_core` (§1.2) — cerrado con la solución (a) |
| A8 | `respuesta_base.py` (envoltorio compartido) aún no extraído | Depende del refactor propuesto para jerarquizar/cuantificar |
| A9 | Warm-up de Ollama (arranque frío gemma@139 ~342s) | ✅ ya existe (`warmup.py`), verificar habilitado en 139 |

---

## 13. Resumen para quien implemente

1. **El motor ya existe** (`analisis.ejecutivo`) — se REUSA por import, NO se reconstruye ni se forkea.
2. **"Analizar" son 4 sub-intenciones** — un sub-router Python las separa; 3 las cubre el ejecutivo.
3. **HECHO/CAUSA/ACCIÓN sí; DELTA se redefine** a "vs promedio 2026" (el "vs snapshot previo" es
   imposible con el esquema actual — y ya se acordó esa redefinición el 30-jul).
4. **La honestidad es el producto**: REGLA CERO (no inventar rezago), confianza runtime, diferidas
   rotulado como histórico. Reusar la disciplina ya codificada.
5. **Empezar por causal+proyección** (Fase 1) — es envolver, no construir; probablemente el responder
   más rápido de los tres.
6. **Coherencia chat↔tablero gratis** — al reusar `ejecutivo`, el chat y el panel no pueden divergir.

---

*Documento de diseño v1 (DRAFT). Piezas verificadas contra `analisis/api.py` el 2026-08-02 con línea.
Bloqueos de datos: sesión de análisis del 2026-07-30 (bitácora CLAUDE.md padre). Hermano de `cuant.md`.*
