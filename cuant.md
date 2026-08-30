# cuant.md — Motor de Cuantificación (Grupo 2 de motor_Q)

> **Qué es este documento:** especificación de implementación del **Grupo 2 · Cuantificar**
> del Motor Q v2 — desde que el clasificador enruta una pregunta a "cuantificar" hasta que
> sale el número con su huella. Es el handoff para poner el desarrollo en productivo.
>
> **Audiencia:** el desarrollador que construya el responder de Cuantificar.
>
> **Regla madre (no negociable):** *Python calcula, el LLM solo redacta.* El LLM nunca
> calcula, nunca genera SQL, nunca inventa números ni elige una variable. El **catálogo**
> (`catalogo_cuantificar_DRAFT.yaml`), no el LLM, decide qué es una variable, con qué
> referencia y a qué grano.
>
> **Fecha:** 2026-08-02 · **Versión:** 1 (DRAFT para revisión)
> **Documentos fuente:** `AUDITORIA_VIABILIDAD_CUANTIFICAR.md` (los 5 ejes verificados
> contra la BD), `catalogo_cuantificar_DRAFT.yaml` (el contrato máquina), `motor_Q.md`
> (§4 Grupo 2, la interfaz), `DISENO_CAPA_CONVERSACIONAL.md`.
>
> **Estado de verificación:** cada cifra y cada celda de confianza de este documento fue
> verificada contra la BD en vivo (`daily_report_prod`, `robustez_v02`, `ECP_DIFERIDAS.db`)
> el 2026-08-02. No hay nada "de memoria".

---

## 0. Resumen ejecutivo

Cuantificar responde **magnitudes medibles** de producción: valores, acumulados, series y
variaciones. La conclusión central de la auditoría de viabilidad es que **Cuantificar NO son
"14 variables × 4 modos"** sino **3 productos reales** (crudo, gas, blancos) con un mapa de
confianza muy desigual, más un conjunto de variables satélite (conteos de jerarquía, economía,
diferidas) que viven en **otras bases** y **no reconcilian entre sí**.

El motor descansa sobre **dos decisiones de enrutamiento** que gobiernan todo:

1. **Fuente por defecto = REPORTE DIARIO (INGESTA / `daily_report_prod`).** Es la cifra
   oficial que ve la gerencia, la más completa (incluye terceros, tiene gas+blancos, grano
   día+mes, referencias PPTO/P50). **Robustez** (`robustez_v02`) es el **especialista** — se
   baja a él SOLO para pozo, economía (EBITDA) y agua, siempre **rotulado**. Los dos mundos
   **NO reconcilian (~6,5×)**: nunca se suman en una misma respuesta.

2. **Referencia/meta por defecto = PPTO.** Hay 5 referencias de plan (PPTO, OPERATIVO,
   CONTABLE, PROGRAMA, P50) y **no coinciden**. PPTO es el default; las demás son explícitas
   y rotuladas; PROGRAMA está bloqueado (versionado).

---

## 1. Arquitectura y ubicación

### 1.1 Dónde vive
Módulo nuevo dentro del **edificio separado** `backend/app/features/consulta_v2/` (el mismo
que aloja el clasificador). Cero imports de `consulta/` (v1 congelada); lo que se reuse de v1
se **forkea** con marca `# FORK de consulta/<archivo>`.

Estructura propuesta (nombre `respuesta_cuantificar`, **simétrico a `respuesta_jerarquizar`**):
```
consulta_v2/
  respuesta_base.py          # NUEVO · compartido: envoltorio intro(LLM)+cuerpo(verbatim)+cierre(Python)
                             #   — extraído de respuesta_jerarquizar; lo usan jerarquizar Y cuantificar
  respuesta_cuantificar.py   # entrada del grupo: responder(texto, usuario) — como respuesta_jerarquizar
  cuantificar/
    catalogo.py        # carga y valida variables_cuantificables.yaml (1 vez al arranque)
    slots.py           # extracción de slots (LLM extrae, Python valida contra catálogo)
    resolver.py        # (FORK de consulta/resolver) — VER §1.4 (un solo resolver, D-D5)
    niveles.py         # N1-N4: puntual / acumulado / serie / variación
    ejecutor.py        # 🔑 REUSA/FORKEA analisis.desempeno + analisis._ambito para REAL/PPTO mes
                        #    (coherencia chat↔tablero, §1.4). SQL NUEVO solo para lo que el tablero
                        #    NO calcula: N2 multi-mes, N3 serie, N4 variación.
    ejecutor_robustez.py  # vía especialista (get_ops_engine): pozo/EBITDA/agua
    conteos.py         # jerarquía: gerencias/activos/campos/pozos
    narracion.py       # (FORK de consulta/narracion) — VER §1.4 (format:"json" obligatorio)
    validador.py       # validación pre-render (garantía mecánica de la regla madre)
  config/
    variables_cuantificables.yaml   # = catalogo_cuantificar_DRAFT.yaml sin el _DRAFT
```

**🔑 NO hay endpoint nuevo.** El flujo real es único: frontend → `POST /consulta2/preguntar` →
`maquina_q.clasificar()`, y cada grupo responde **inline** dentro de `clasificar()` (patrón
`elif grupo == "cuantificar" and log:` → `respuesta_cuantificar.responder(...)`), igual que
jerarquizar (`maquina_q.py:217`). Un endpoint aparte duplicaría el enrutamiento y exigiría tocar
`multitab_shell.js`. Solo se justifica si el JSON de §7 se va a renderizar estructurado en el
frontend (y entonces hay que especificar ese cambio de front).

### 1.2 Conexiones a datos (ya existen — no hay que construir plumbing)
- `get_engine()` → `daily_report_prod` (default). Ya conectado.
- `get_ops_engine()` en `core/db.py` → `robustez_v02` (schema `ops`). **YA EXISTE**, lo usa
  el feature `ebitda`. El motor lo reusa para pozo/EBITDA/agua. Solo lectura.
- `ECP_DIFERIDAS.db` (SQLite) → el backend FastAPI aún NO la lee (solo el Flask, en
  `/api/diferidas/frecuencia`). **Dependencia EXPLÍCITA de la Fase 4** (sin este lector,
  `volumen_diferidas` no funciona): construir un lector SQLite directo o un proxy a la ruta Flask.
  Esfuerzo menor, pero **bloqueante para diferidas** — no es "pendiente suelto".

### 1.3 Frontera LLM / Python (inviolable)
| Etapa | Quién | Qué hace |
|-------|-------|----------|
| Extracción de slots | LLM | propone {variable, entidad, nivel, rango, referencia} — **texto → JSON** |
| Grounding de slots | Python | valida cada slot contra el catálogo; descarta lo que no exista |
| Resolución de entidad | Python | hash + trgm contra el catálogo jerárquico |
| Cálculo | Python | ejecuta la operación (N1-N4) sobre la fuente correcta |
| Redacción | LLM | escribe la prosa DESDE el JSON ya calculado |
| Validación pre-render | Python | ningún número/entidad de la prosa puede faltar en el JSON |

### 1.4 Lecciones de integración con el edificio ya construido (NO reinventar)

Estas cuatro son deuda pagada por v1/el clasificador — reusarlas, no repetir el error:

1. **Coherencia chat↔tablero (la lección más cara).** El REAL/PPTO del mes NO se calcula con SQL
   propio: `consulta/ejecucion.py` **reusa `analisis.desempeno`** (+`analisis._ambito` para
   nivel+periodo) justamente para que la cifra del chat y la del panel **no puedan divergir**. Si
   `ejecutor.py` filtra distinto (concepto/escenario/ámbito), el usuario ve dos números en la misma
   pantalla. → **Forkear la ruta `ejecucion.py`/`analisis._ambito`** (marca `# FORK`) para el núcleo
   REAL/PPTO mes; SQL nuevo SOLO para lo que el tablero no calcula (N2 multi-mes, N3, N4).
2. **`_CTX` simétrico (memoria de sesión).** `maquina_q.py:31/259-263` mantiene `_CTX`
   (conversation_id → {entidad, nivel, …}) pero **solo jerarquizar lo puebla**. Si el usuario abre
   con "cuánto produjo Castilla" y sigue con "¿y a qué activo pertenece?", el pronombre elidido
   muere. → **Cuantificar DEBE guardar {entidad, nivel} en `_CTX` al resolver**, igual que
   jerarquizar (`_continuacion()` ya lee de ahí). Simétrico y barato.
3. **`narracion.py` (2 gotchas de v1).** (a) 🔑 **gemma4@139 devuelve VACÍO en texto plano** por
   `/api/generate`; SOLO responde con `format:"json"` (fix `bde9524`) → pedir `{"narracion":"…"}` y
   extraer. (b) El flag sigue el patrón `CONSULTA_*` de `config.py` con **fallback determinista** (la
   plantilla) si el LLM falla; el validador (§8) es la versión mejorada de la salvaguarda D-N5.
4. **Un solo resolver (evitar dos verdades).** Jerarquizar resuelve sobre `map_campo_robustez`;
   Cuantificar sobre `dim_fuente` (fork de v1). El mismo nombre puede resolver distinto (o existir en
   uno solo). → Reusar la **prioridad D-D5 (Campo gana)** de v1, y documentar el caso "la entidad solo
   existe en robustez" (p. ej. la gerencia POE — ver §6 / R11).

---

## 2. El pipeline (texto → número)

```
Clasificador (Etapa A) enruta a "cuantificar"
        │  (llega: texto + entidad_cruda opcional)
        ▼
1. SLOTS   slots.py — LLM extrae {variable, nivel N1-N4, rango, referencia, grano}
        │            Python los aterriza contra el catálogo (grounding)
        ▼
2. ENTIDAD resolver.py — entidad → nivel canónico (assume & declare en colisión)
        │            si ambigua/no encontrada → contrapregunta y TERMINA
        ▼
3. RUTA    catalogo.py decide fuente por (variable, grano):
        │            producción → INGESTA · pozo/EBITDA/agua → robustez · diferidas → SQLite
        ▼
4. HUELLA  ejecutor.py — registros, rango real disponible, días sin reporte, techo de datos
        ▼
5. CÁLCULO niveles.py — N1 lookup · N2 Σ · N3 serie · N4 deltas   (respetando cero traicionero)
        ▼
6. PROSA   respuesta_base.py — intro(LLM cálido) + cuerpo(Python VERBATIM: nº ya formateado+huella) + cierre(Python)
        ▼
7. VALIDAR validador.py — nº/entidad/unidad de la prosa ⊆ JSON; si falla 2× → render sin prosa
        ▼
   Respuesta (contrato §5)
```

---

## 3. Slots del grupo

| Slot | Tipo | Default | Notas |
|------|------|---------|-------|
| `entidad` | duro | — | de Etapa B. Sin entidad → contrapreguntar |
| `variable` | duro | — | del catálogo YAML; si no se detecta → menú de variables |
| `producto` | blando | **volumen dominante** de la entidad | 🔑 NO "aceite" fijo (mata el riesgo Hocol). Declarar siempre el asumido |
| `nivel` (N1-N4) | blando | N1 | por señales del texto (§4) |
| `rango_temporal` | blando | mes actual | **el PERIODO** (qué ventana): un mes o rango de meses. v1 NO parsea año/trimestre/semana. **≠ grano** |
| `grano` | blando | mes | **la resolución DENTRO del periodo**: día o mes. `"día a día en mayo"` = grano día en periodo mes → **soportado** (crudo/gas) |
| `referencia` | blando | **PPTO** | REAL/PPTO/OPERATIVO/CONTABLE/P50; P50 solo a nivel ECP-global |

> 🔑 **Periodo ≠ grano** (corrección de claridad): "v1 solo MES" limita el **periodo** (no se
> entienden "2025", "primer trimestre", "última semana"). NO limita el **grano**: una serie diaria
> dentro de un mes (crudo/gas) está soportada. Ej.: "producción de crudo día a día en mayo" = N3,
> grano día, periodo mayo → válido. Lo único vetado a día es **blancos** (§4.1).

Detección del nivel N1-N4 (señales, Python — de motor_Q §4.2):
- **N4** (variación): "cómo varió", "variación", "creció/cayó/aumentó/disminuyó"
- **N3** (serie): "mes a mes", "día a día", "desglosado por mes"
- **N2** (acumulado): "acumulado", "total de", "entre X y Y"
- **N1** (puntual): default
Evaluar N4→N3→N2→N1 (del más específico al default).

---

## 4. El catálogo (contrato de datos) — `variables_cuantificables.yaml`

El detalle máquina está en el YAML. Resumen de qué responde y con qué confianza:

### 4.1 Productos de producción (fuente: INGESTA)
| Producto | Unidad | Grano MES | Grano DÍA |
|----------|--------|-----------|-----------|
| **crudo** | bbl | 🟢 N1-N4 | 🟢 N1-N4 (reconcilia 0,99) |
| **gas** | MSCF | 🟢 N1-N4 | 🟢 N1-N4 (REAL = venta-gravable+consumo) |
| **blancos** | bbl | 🟡 N1-N4 (agregado "GAS CONVERTIDO MME") | 🔴 (día ×4 vs mes ×2 = 2,10, irreconciliable) |

### 4.2 Referencias (modos)
| Referencia | Fuente | Cobertura | Uso |
|------------|--------|-----------|-----|
| **PPTO** | fact_mes | 12 meses | **default** |
| REAL | fact_mes | **18 meses (dic-2024→may-2026)** | lo producido; mes en curso = proyección. (Los 5 meses ene-may son solo el tramo 2026; N4 inter-anual usa 2025) |
| OPERATIVO | fact_mes | 12 meses | presupuesto revisado (~PPTO +1%) |
| CONTABLE | fact_mes | solo meses cerrados | cierre contable |
| P50 | reporte_president | corporativo | **SOLO nivel ECP-global** (kbpe, no baja a campo) |
| promedio-año | derivada | — | referencia de blancos |
| PROGRAMA | fact_programa_ecp | — | **BLOQUEADO** (versionado V1..V19; sumar sin filtrar infla 8×) |

### 4.3 Niveles N1-N4 × grano (verificado)
Cobertura: MES = 18 meses continuos (dic-2024→may-2026, 3 productos). DÍA = 174 días
continuos, 0 huecos agregados (nov-2025→17-may-2026), REAL puro.

| Nivel | MES | DÍA |
|-------|-----|-----|
| N1 puntual | 🟢 cerrado · 🟡 en curso = proyección | 🟢 crudo/gas · 🔴 blancos |
| N2 acumulado | 🟢 cerrados · 🟡 curso ≠ proyección | 🟢 crudo · 🟡 gas · 🔴 blancos |
| N3 serie | 🟢 los 3 | 🟢 crudo/gas · 🔴 blancos |
| N4 variación | 🟢 (⚠ salto 2025→26) | 🟡 crudo/gas · 🔴 blancos |

### 4.4 Derivadas
- **gap** = REAL − referencia (default PPTO), bbl, mes, 🟢
- **cumplimiento** = REAL / referencia × 100, %, mes, 🟢
- **volumen_diferidas** (crudo/gas, SIN blancos): ECP_DIFERIDAS, histórico 2023→jul-2025,
  por incidentes (grano día-pozo), 🟡

---

## 5. Vía especialista — Robustez (pozo · economía · agua)

Se activa SOLO cuando la pregunta pide pozo, EBITDA/breakeven/revenue o agua. **Siempre
rotulada** ("universo robustez, ECP-neto"). Fuente `robustez_v02.ops` vía `get_ops_engine()`.

| Variable | Tabla | Nota |
|----------|-------|------|
| producción por pozo | `flow_rates` | oil/water/blend; **sin gas**; mensual 2025-01→2026-06 |
| EBITDA / breakeven / revenue | `financial_results` | kUSD/USD-bbl; **solo aceite**; **NOPAT no existe** (hay util_neta) |
| agua | `flow_rates` (water) | mismo dato que `produccion_agua` a grano mes |

**Regla dura:** los números de robustez NO reconcilian con el reporte (crudo abril: fact 85,4M
vs flow_rates blend 13,2M). Jamás sumar los dos mundos en una respuesta.

---

## 6. Conteos de jerarquía (cuántos pozos / gerencias / activos / campos)

Fuente de verdad = `robustez_v02.ops.wells_attributes` + `core.map_campo_robustez`. Reglas
(auditadas J-1…J-5):

- **J-1 · Solo ECP-operado** (**81 campos marcados `es_ecp`, 78 con `rob_field` real** — 3 sin match:
  ORIPAYA, CUPIAGUA SUR, PACHAQUIARO NORTE; de 139 totales). Toda respuesta declara *"no incluye
  operados por terceros"* (los terceros = ~⅓ de la producción, sin jerarquía robustez).
- **J-2 · Pozos activos:** partición 1 estado/pozo por prioridad **ACT>SUS>INACT>ABA** (el grano
  real es uwi×zona; 27% de pozos son mixtos). Activos = 6.989. Es estado de REGISTRO, no "produjo".
- **J-3 · Siempre `COUNT(DISTINCT uwi)`** al nivel pedido — nunca SUM de subconteos (747 uwi en
  >1 campo). Las columnas vice/management de wells están **aliaseadas** (GOR/POE≡VAO/ORIENTE;
  112/118 campos multi-etiqueta) → la jerarquía canónica se toma del **mapa**, no de wells.
- **J-4 · "Cuántos pozos" es REGISTRO (atemporal); "cuántos produjeron en {mes}" es `flow_rates`**
  (universo robustez). No confundir con el volumen del reporte.
- **J-5 · Level-shift (opción A · educar suave):** lo que el reporte llama "gerencia" (GOR, GAA…)
  es la **vicepresidencia** en robustez; la gerencia real es `management` (POE, PPC…). Aceptar el
  término del usuario y tender puente sin negarlo. El puente es 1:muchos en 5 de 11 gerencias
  (data-driven desde el mapa).

Conteos de estructura (gerencias/activos/campos) salen de `map_campo_robustez` **sin cross-DB**;
solo el conteo de pozos exige `get_ops_engine()`.

**🔑 El level-shift también toca PRODUCCIÓN, no solo conteos (R11 — RESUELTA).** "¿Cuánto **produce** la
gerencia POE / la VP GOR?" es una pregunta de volumen, pero ese nivel **no existe como columna en
INGESTA**. **✅ DECISIÓN (2026-08-02):** resolver el término org (gerencia/VP/activo) a sus campos vía
`map_campo_robustez` → **sumar esos campos en INGESTA** → declarar el nivel (educar suave J-5: "la
gerencia POE agrupa RUBIALES…"). **Unifica con los conteos** (mismo mapa, misma resolución). 🔑 **El
número es COMPLETO, no parcial:** los niveles robustez son ECP-only por construcción, así que no hay
terceros faltantes dentro de ellos (verificado: POE = {RUBIALES}, 10,97M crudo abril, presente en el
fact). El resolver (§1.4·4) debe reconocer términos org de robustez además de `dim_fuente`.

---

## 7. Contrato de respuesta (JSON)

```json
{
  "grupo": "cuantificar",
  "variable": "produccion_crudo",
  "nivel": "N2",
  "entidad": { "nombre": "CASTILLA", "nivel": "campo", "fue_asumida": false },
  "producto": "crudo",
  "referencia": "PPTO",
  "unidad": "bbl",
  "grano": "dia | mes",
  "universo": "reporte_diario | robustez",
  "huella": {
    "registros": 0,
    "rango_pedido": ["ISO", "ISO"],
    "rango_disponible": ["ISO", "ISO"],
    "dias_sin_reporte": 0,
    "recorte_declarado": "string | null",
    "es_proyeccion": false
  },
  "resultado": {
    "valor": "number (N1/N2) | null",
    "serie": [ {"periodo": "string", "valor": 0} ],
    "variaciones": [ {"periodo": "string", "delta_abs": 0, "delta_pct": 0.0} ]
  },
  "referencia_valor": 0,
  "cumplimiento_pct": 0.0,
  "defaults_asumidos": [ "producto=crudo (mayor volumen)", "referencia=PPTO" ],
  "avisos": [ "string — descargos obligatorios del catálogo" ],
  "intro":  "string — LLM, calidez dinámica (SIN números ni entidades no presentes en el JSON)",
  "cuerpo": "string — Python VERBATIM: la cifra YA formateada (12.357.703 bbl) + huella + referencia",
  "cierre": "string — Python exacto: '¿Quieres verlo mes a mes?' (ofrece N3/N4 y alimenta _CTX)",
  "panel":  { "tipo": "kpi | acumulado | serie | variacion", "widget": "cnP50CardHtml | cnGapCampoInto | cnMonthlyPlot | cnDailyPlot | ejecDiverg",
              "grano": "dia | mes", "datos": "los MISMOS ya calculados — el panel NO recalcula (§7.5)" }
}
```

**🔑 Envoltorio conversacional (consistencia con jerarquizar — `respuesta_base.py` compartido).**
Cuantificar NO responde con una prosa seca de ≤15 palabras: usa el MISMO patrón que
`respuesta_jerarquizar.py` (intro + body + cierre). Reparto de roles:
- **intro** — LLM, saludo/lead-in cálido y dinámico. Es lo ÚNICO que escribe el LLM. `''` si falla/off.
- **cuerpo (hechos VERBATIM)** — 🔑 **Python formatea el número al literal de display** ("12.357.703 bbl")
  y lo entrega **ya formateado**; el LLM NO lo toca (lección D-N5: el LLM tiende a escribir "12,3
  millones" → validación falla o pasa con redondeo engañoso). El cuerpo lleva número + huella + referencia.
- **cierre** — Python exacto, ofrece la continuación ("¿Quieres verlo mes a mes?" → N3/N4) y **alimenta
  `_CTX`** para que la memoria sepa continuar. NO lo escribe el LLM (en jerarquizar el LLM inventó
  "producción de GNL" en el cierre — por eso es de Python).

→ Extraer intro+cuerpo+cierre a **`respuesta_base.py`** (nuevo, compartido por jerarquizar y cuantificar).

---

## 7.5 Doble entregable — el panel derecho (potenciación espacial)

Igual que Analizar (`motor_Q §5.3`: narrativa + paneles a la par), Cuantificar es **doble entregable**:
el **número en el chat** (panel izquierdo) + su **visualización en el visor derecho**. Principio
heredado *"no duplicar, anclar"*: el panel **no repite** el número, lo **contextualiza**.

### 7.5.1 El panel es CONSCIENTE DEL NIVEL (N1-N4)
Cada nivel sugiere su gráfico natural, y cada uno **reusa un widget que ya existe** en
`multitab_shell.js` (no se construye nada nuevo):

| Nivel | Panel derecho | Widget reusado |
|-------|---------------|----------------|
| **N1 Puntual** | Tarjeta KPI (número + vs PPTO + semáforo) **+ el punto ubicado en su serie** | `__cnP50CardHtml` · `__cnKpiStatus` |
| **N2 Acumulado** | Barra acumulado vs meta **+ la curva que suma a él + composición por campo** | `__cnGapCampoInto` · `__cnDailyPlot` |
| **N3 Serie** | Gráfico línea/barras de la serie vs referencia | `__cnMonthlyPlot` / `__cnDailyPlot` |
| **N4 Variación** | Barras divergentes (Δ rojo baja / verde sube) | `__ejecDiverg` (vía `__cnEjecCharts`) |

### 7.5.2 El panel muestra un nivel MÁS de contexto que el número
Un número solo es delgado; el panel agrega lo que el chat no puede:
- **Tendencia** — ¿este mes es alto o bajo vs sus 18 meses de historia?
- **Composición** — ¿qué campos/fuentes arman el número? (aportantes/detractores)
- **Referencia visual** — vs PPTO como bullet/semáforo, no solo el "%".
- **Textura diaria** — la curva detrás del número mensual.

### 7.5.3 Regla de coherencia (liga con §1.4·1)
🔑 **UN solo cálculo → chat + panel.** El número del chat y el del panel salen de la **misma
ejecución** (`analisis.desempeno` reusado, §1.4), **nunca de dos queries** — como ya hace
`__cnDashboard`. Los formateadores (`__cnMilesEC` bbl · `__cnGasM` MSCF · `__cnKbpe`) son **los mismos**
en ambos lados; si no, el chat diría "5.234.891" y el panel "5,2M" para la misma cifra.

### 7.5.4 El cierre navega el panel (drill-path N1→N4)
El **cierre** (§7, Python) ofrece la continuación y alimenta `_CTX` — convirtiendo los 4 niveles en un
recorrido que mueve chat Y panel juntos:
```
N1 "cuánto hoy" →[¿acumulado?]→ N2 →[¿mes a mes?]→ N3 →[¿cómo varió?]→ N4
   KPI en panel     barra+curva      serie             variación divergente
```
Cada "¿quieres…?" reescribe el chat **y** repinta el panel al siguiente nivel: conversación y
visualización evolucionan como una sola cosa.

### 7.5.5 Enganche técnico
El campo `panel` del contrato (§7) viaja con los datos YA calculados; `respuesta_cuantificar` lo pinta en
el visor derecho reusando el widget indicado, mientras el chat pone intro+cuerpo+cierre a la izquierda.
El panel es **automático** (se abre a la par, como en Analizar), no bajo demanda.

---

## 8. Reglas de honestidad (aplican a TODA respuesta)

1. **Huella primero, número segundo** — el valor va siempre con registros/rango real/días sin dato.
2. **Declarar la referencia** (PPTO por defecto) — sin ella "cumplimiento" es ambiguo.
3. **Mes en curso = PROYECCIÓN** — distinguir "va acumulado X (N días)" de "proyecta cerrar Y".
   🔑 **Si `huella.es_proyeccion=true`, la prosa DEBE contener la palabra "proyección" o la marca
   "al corte del día {N}/{total}"** — el validador (§8, abajo) lo verifica; no es opcional.
   (Verificado: mayo diario 17d = 48,5M vs mayo mensual REAL = 88,9M.)
4. **Cero traicionero** — SIN_REPORTE ≠ 0; los huecos por entidad no se coaccionan a 0.
5. **Variación inter-anual** — avisar del salto 2025→2026 (~+30%, posible cambio de alcance).
6. **Default de producto por volumen dominante** — nunca "aceite" fijo (riesgo Hocol).
7. **Techo de datos** — recortar a lo disponible y declararlo (día → 2026-05-17).
8. **P50 solo a nivel ECP-global** — nunca ofrecer "vs P50" a nivel campo/activo/gerencia.
9. **No mezclar universos** — reporte diario y robustez no reconcilian; robustez siempre rotulado.

**El validador pre-render (`validador.py`) es la garantía mecánica.** Dos capas:
1. **El cuerpo (número) es VERBATIM de Python** → no puede mentir por construcción (el LLM no lo escribe).
   Python **pre-formatea la cifra al literal exacto** ("12.357.703 bbl", con separadores es-CO) — nunca
   entrega el número crudo `12357703` (la lección D-N5: si el LLM redondea a "12,3 millones", la
   validación falla o pasa con redondeo engañoso).
2. **El intro (LLM) se valida:** ningún número ni entidad del intro puede faltar en el JSON; si falla
   2 veces → se descarta el intro y se renderiza cuerpo+cierre (Python) sin él. **El dato siempre sale;
   el intro es opcional.**

---

## 9. NO soportado (rechazo explícito — se cablea, no se descubre en runtime)

| Petición | Motivo |
|----------|--------|
| producción de agua en el reporte diario | no está en INGESTA (solo robustez) |
| blancos a grano día | ×2 irreconciliable |
| pozos que produjeron, en unidades del reporte | robustez no reconcilia con el fact |
| gas por pozo | `flow_rates` no tiene gas |
| NOPAT / margen / plata en INGESTA | sin modelo económico (EBITDA solo en robustez, aceite) |
| mantenimientos / workover | vocabulario reconocido, sin fuente (mock) |
| diferidas de blancos | `AVM_DATADIF` no tiene columna de blancos perdido |
| año / trimestre / semana | v1 solo parsea MES |
| año / trimestre / semana | v1 solo parsea MES |

**✅ Filiales (rama B) — R12 RESUELTA: SÍ soportada** (sale de esta lista). "¿Cuánto produce Hocol?" se
responde desde las **consolidadas** (`fact_produccion_diaria`: 3 filiales, REAL y PROGRAMA,
nov-2025→may-2026; verificado Hocol Real 5,59M / Programa 6,38M), **referencia = REAL vs PROGRAMA** (las
filiales NO tienen PPTO), reusando la máquina de análisis (`_fil_intermedios`/`__cnFilSeriePlot`).
🔑 **Hocol es identidad DUAL** (operador ECP en rama A, sí produce en el fact diario; + filial en rama B)
— el resolver desambigua con **assume&declare**, como el caso más viejo de v1. *(Alternativa de alcance:
diferir filiales a fase posterior si se quiere v1 solo-ECP.)*

---

## 10. Fases de implementación

**FASE 1 — Núcleo 🟢 (crudo, la celda más sólida).**
1. `catalogo.py` (carga + valida el YAML) · `slots.py` (LLM extrae + grounding).
2. `resolver.py` (fork de v1) · `niveles.py` (N1-N4).
3. `ejecutor.py` para **crudo, INGESTA, vs PPTO** (N1/N2 mes primero).
4. `respuesta_base.py` (intro+cuerpo+cierre) + `validador.py`.
5. **Panel derecho N1/N2** (§7.5): tarjeta KPI + barra acumulado — reusar `__cnP50CardHtml`/
   `__cnGapCampoInto` con los datos YA calculados (misma ejecución que el número del chat).
- **Gate:** golden set de **≥10 casos** (crudo puro; motor_Q pide 10/grupo, y 5 no cubre las celdas
  🟡/🔴 donde están las trampas), con **al menos uno por nivel N1-N4** y **dos casos deliberados de
  descargo: (a) mes en curso → debe salir "proyección"; (b) rango que excede el techo (p. ej.
  "junio") → debe recortar y declararlo**. Cada cifra verificada a mano contra la BD, con huella y
  referencia declarada. **Paridad qwen2.5/gemma4.** 🔑 **El golden runner y pytest llaman
`responder(..., log=False)`** (patrón H3 del clasificador) — sin eso cada corrida mete filas basura a
la libreta de clasificación.

**FASE 2 — Completar productos y niveles.** gas (día+mes) · blancos (solo mes) · N3 serie · N4
variación (con aviso inter-anual). Referencias OPERATIVO/CONTABLE/promedio-año. gap/cumplimiento.

**FASE 3 — Vías satélite.** (a) **Especialista robustez** `ejecutor_robustez.py` (get_ops_engine): pozo,
EBITDA, agua — siempre rotulado; requiere confirmar robustez_v02 en 139. (b) **Filiales / rama B (R12)**:
ruta a `fact_produccion_diaria` (REAL vs PROGRAMA), reusa `_fil_intermedios`; resolver desambigua Hocol
dual. (c) **Producción por nivel org (R11)**: término→campos vía mapa→suma en INGESTA.

**FASE 4 — Conteos de jerarquía.** `conteos.py` con reglas J-1…J-5. **Lector de `ECP_DIFERIDAS.db`**
(dependencia explícita, §1.2): si es SQLite directo en FastAPI, abrir con **`os.path.abspath`
(CWD-independiente)** — la lección del 24-jul en la ruta Flask; o proxy a la ruta Flask existente.

Cada fase se valida contra la BD (¿la respuesta es correcta?), no solo contra etiquetas.

---

## 11. Checklist para PRODUCTIVO (139)

- [ ] Renombrar `catalogo_cuantificar_DRAFT.yaml` → `config/variables_cuantificables.yaml`.
- [ ] Confirmar unidad del gas ya está fija = **MSCF** (hecho).
- [ ] `CONSULTA_OLLAMA_URL` / `CONSULTA_LLM_MODEL` apuntando a gemma4@139 (ya usados por v1).
- [x] **Warm-up de Ollama** — ✅ **YA IMPLEMENTADO** (`consulta_v2/warmup.py`, gated por
      `CONSULTA_WARMUP` en `config.py`/`main.py`). Verificar que esté habilitado en 139.
- [ ] **robustez_v02 en 139:** confirmar que existe y está poblada (para la vía especialista). El
      `map_campo_robustez` ya se materializó en `daily_report_prod` (no necesita robustez_v02 para
      conteos de estructura, sí para conteo de pozos).
- [ ] **`ECP_DIFERIDAS.db` (954 MB):** subir a 139 (bloqueo conocido: no cabe en Git). Sin ella,
      volumen_diferidas = SIN_DATOS en prod.
- [ ] Aplicar migraciones pendientes vía `desplegar_version.bat`.
- [ ] Golden set de Cuantificar (≥5 casos por fase, verificados a mano) en verde con AMBOS modelos.

---

## 12. Riesgos y decisiones abiertas

| # | Riesgo / decisión | Estado |
|---|-------------------|--------|
| R1 | Default `producto=aceite` en entidades gas-dominantes | Regla de volumen dominante (§3) — mitigado |
| R2 | 5 referencias de meta que no coinciden | Default PPTO fijado; resto rotuladas — cerrado |
| R3 | Unidad del gas | **MSCF confirmado** (usuario 2026-08-02) — cerrado |
| R4 | Techo de datos 2026-05-17 (.xlsm cifrados) | Declarar recorte — mitigado; resolver ingesta es externo |
| R5 | Robustez no reconcilia con el reporte (~6,5×) | Regla "no mezclar universos" + rótulo — mitigado |
| R6 | PROGRAMA versionado | Bloqueado hasta definir regla de versión |
| R7 | Prioridad de estados J-2 (ACT>SUS>INACT>ABA) | Default adoptado; revisable |
| R8 | Blancos-día irreconciliable | NO soportado a día (decisión de negocio pendiente para reconciliar) |
| R9 | 139: robustez_v02 poblada + diferidas subida | Operativo, pendiente de verificar/ejecutar |
| R10 | Arranque en frío de Ollama (~342s medido) | ✅ **MITIGADO — `consulta_v2/warmup.py` ya existe** (gated `CONSULTA_WARMUP`). Solo verificar habilitado en 139 |
| R11 | Level-shift en producción (gerencia/VP no existe como columna en INGESTA) | ✅ **RESUELTA (§6):** resolver el término→campos vía `map_campo_robustez`→sumar en INGESTA; número COMPLETO (robustez=ECP-only); declarar nivel. El resolver debe reconocer términos org de robustez |
| R12 | Filiales / rama B ("cuánto produce Hocol"); Hocol dual | ✅ **RESUELTA (§9):** SÍ soportada vía `fact_produccion_diaria` (REAL vs PROGRAMA), reusa máquina de análisis; resolver desambigua Hocol operador/filial (assume&declare) |

---

## 13. Resumen para quien implemente

1. **El catálogo manda, no el LLM.** El LLM extrae slots y redacta prosa; todo lo demás es Python.
2. **Empezar por el núcleo 🟢** (crudo, INGESTA, vs PPTO, N1/N2 mes) y extender.
3. **Dos mundos, nunca mezclados:** reporte diario (default) y robustez (especialista, rotulado).
4. **Cada respuesta lleva su huella y su referencia declarada** — es la diferencia entre un número
   y un número honesto.
4b. **Doble entregable (§7.5):** número en el chat + visualización en el panel derecho, consciente del
   nivel (N1→KPI, N2→barra, N3→serie, N4→divergente). Un solo cálculo alimenta ambos; el cierre navega
   el panel por los 4 niveles. Reusa widgets `__cn*` que ya existen.
5. **El plumbing de datos ya existe** (`get_engine`/`get_ops_engine`); lo que falta es el responder.
6. **Todo está verificado contra la BD** en `AUDITORIA_VIABILIDAD_CUANTIFICAR.md` — no rediseñar,
   implementar contra esa evidencia y contra el YAML.

---

*Documento de diseño v1 (DRAFT). Los números son los verificados en la sesión del 2026-08-02.
Compañero máquina: `catalogo_cuantificar_DRAFT.yaml`. Fuente de evidencia:
`AUDITORIA_VIABILIDAD_CUANTIFICAR.md`.*
