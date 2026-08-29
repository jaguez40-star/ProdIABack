# Plan · Panel derecho para JERARQUIZAR (árbol jerárquico)

**Fecha:** 2026-08-11 · **Estado:** **v2 auditado** (2ª ronda contra el código real; 8 hallazgos, 4 de
ellos corrigen el diseño de la v1). Sin LLM, sin backend levantado, sin BD — solo lectura de archivos.
**Tipo:** backend (2 archivos) + frontend (3). Sin migración, sin SQL nuevo, sin contrato nuevo.
**Cobertura: sub-tipos de entrada 5 → salida 5.** Identidad/composición (campo·activo·gerencia·VP),
operador, ranking estructural, ranking que declina, y sin-entidad. Los 2 últimos **no** producen
panel a propósito (§6); ninguno se omite en silencio.

---

## 1. Contexto

Las preguntas de **Jerarquizar** ("¿qué campos tiene el activo Castilla?", "¿a qué activo pertenece
Cajúa?") responden hoy **solo en el chat**: `maquina_q` deja `panel = None` para este grupo
(`maquina_q.py:341`, comentario "SOLO cuantificar lo puebla"). El panel derecho no muestra nada,
mientras Cuantificar sí apila su bloque.

**Decisiones del usuario (cerradas):**

| # | Decisión |
|---|---|
| D1 | Jerarquizar **sí** produce panel, apilado igual que Cuantificar. |
| D2 | Formato: **árbol jerárquico**, no ficha de atributos. |

---

## 2. Auditoría — hallazgos que definieron el diseño

Los marcados 🔴 **invalidan** decisiones de la v1 de este plan.

| # | Hallazgo | Evidencia | Efecto |
|---|---|---|---|
| **H1** | **Los datos ya están estructurados**: `_cargar()` arma `_DATA` con todos los índices (`campo_row`, `act_campos`, `ger_activos`, `ger_campos`, `vp_ger`, `vp_activos`, `op_campos`, `*_fields`). | `respuesta_jerarquizar.py:64-127` | El panel se arma leyendo `_DATA`. **Cero SQL nuevo, cero refactorización** del formateo de texto. |
| **H2** | `_resolver(texto)` → `(niv, canonical, puente, data)`; y ya existe `contexto()` que resuelve y devuelve `{entidad, nivel, hijos}` vía `_hijos()`. | `:468`, `:571-595` | **Precedente exacto** del helper a escribir. |
| **H3** | Los tests de Jerarquizar llaman a **`responder()`**, no a `responder_cordial()`. Y los 2 `assert panel is None` del repo son de **Cuantificar** (rangos), no de este grupo. | `tests/test_jerarquizar_ranking.py:144,158,166,172`; `tests/test_cuantificar_rango.py:41,58` | Se puede añadir el panel **sin tocar un solo test**. |
| **H4** | `maquina_q` solo inspecciona el panel para `cuant_rank` (memoria del drill). | `maquina_q.py:436-438` | Un `tipo` nuevo **no interfiere** con la memoria conversacional. |
| 🔴 **H5** | **El mensaje muestra datos que la v1 del panel omitía:** `_cuerpo` incluye **conteo de pozos** en los 4 niveles (`_contar_pozos`) y, para campo, los **campos hermanos** del activo. | `:389-460` | Sin ellos, el árbol mostraría **menos** que el texto de al lado — incoherencia visible. **El contrato del panel los incorpora.** |
| 🔴 **H6** | **La jerarquía NO es lineal:** `_padres` devuelve **conjuntos** de gerencias y VPs — *"un activo puede colgar de >1 gerencia"* (docstring literal), y `_uno_o_varios` formatea ese plural. | `:181-190`, `:200-205` | Una `ruta` de un elemento por nivel sería **falsa**. El contrato usa **listas por nivel** y el árbol las pinta todas. |
| 🔴 **H7** | **`_contar_pozos` NO tiene caché** y abre conexión a **otra BD** (`get_ops_engine()` → `robustez_v02.ops.wells_attributes`, `COUNT(DISTINCT uwi)`). | `:208-230`; sin `lru_cache` en el módulo | **Prohibido recalcularlo para el panel.** Mismo patrón que el hallazgo A1 del plan causal (SCAN de 11 s → caché obligatoria). El panel **reusa el valor ya calculado**, no vuelve a consultar. |
| 🔴 **H8** | **`operador` NO es un nivel de la jerarquía** — el propio `_cuerpo` lo rotula *"Operador (empresa, no un nivel de la jerarquía)"*. | `:456-459` | Pintarlo como nivel del árbol sería incorrecto y contradiría el mensaje. Tiene **su propia forma de panel** (lista de campos que opera). |
| **H9** | `_rank_calcular` **ya devuelve el contrato estructurado** que la v1 quería construir: `{aplica, subject, conteo, asc, items:[{pos,entidad,n}], total}`. | `:339-365` | El `_panel_rank()` de la v1 **sobra**: se pasa `res` tal cual. Menos código y una sola fuente. |
| **H10** | `_rank_cuerpo` añade un descargo obligatorio: *"El conteo de pozos es de REGISTRO (atemporal), no de producción del mes"*. | `:379-380` | El panel **debe conservarlo** o afirmaría algo distinto que el chat. |
| **H11** | `_con_puente` corrige el nivel del usuario: *"lo que llamas «la gerencia GOR» es, oficialmente, la Vicepresidencia GOR"*. | `:482-489` | El panel debe rotular el **nivel oficial**, no el que dijo el usuario. |
| **H12** | El intro LLM está **ON por defecto** (`consulta_jerarq_llm: bool = True`) y bloquea la respuesta (~30 s documentados). | `core/config.py:31` | El panel se calcula **antes** de `_envolver` (fuera del tramo lento). No añade latencia. |
| **H13** | Las clases `.cn-rank*` son **genéricas** (`__pos`, `__ent`, `__val`, `__foot`, `__aviso`), no atadas a producción. | `colapsable.css:1879-1889` | El ranking estructural las **reusa tal cual** → menos CSS y consistencia visual con el N5. |
| **H14** | Existe un árbol CSS completo (`.ct-*`) con plegado y chevrons. | `colapsable.css:800-849` | **NO se reusa**: es navegación interactiva año→mes→día con `onclick`. Aquí son 4 niveles fijos de lectura. Decisión consciente. |

---

## 3. Decisión de diseño

**`responder_cordial` pasa a devolver `{mensaje, panel}`**, igual que `respuesta_cuantificar.responder`.
`maquina_q` ya sabe consumir ese patrón (`:378-381`).

**Una sola resolución (H7).** El panel se arma **dentro del mismo flujo** que ya resolvió la entidad y
ya contó los pozos: `_cuerpo` calcula `npz` y el panel **reutiliza ese valor**. Llamar a
`_contar_pozos` otra vez duplicaría una consulta cross-DB sin caché en cada pregunta.

**Implementación:** `_cuerpo` pasa a devolver `(texto, hechos)` — el mismo string de siempre más un
dict con los datos que ya calculó (pozos, padres, hijos). El panel se arma desde `hechos`.
- ⚠️ `_cuerpo` tiene **2 call sites** (`responder()` :535 y `responder_cordial()` :562). El primero
  debe seguir recibiendo solo el texto → se ajusta con `[0]`. Verificado: no hay más llamadas.
- Alternativa descartada: un `_panel_arbol` que recalcule desde `_DATA`. Duplicaría la lógica de
  `_padres`/`_lista` y **volvería a llamar a `_contar_pozos`** (H7).

---

## 4. Especificación

### 4.1 Contrato del panel — `jerarq_arbol`

```
{"tipo": "jerarq_arbol", "datos": {
  "entidad": "CASTILLA",
  "nivel": "activo",                    # nivel OFICIAL (H11), no el que dijo el usuario
  "puente": "gerencia" | null,          # nivel que usó el usuario, si difiere (H11)
  "padres": [                           # LISTAS por nivel (H6), de la raíz hacia abajo
    {"nivel": "vicepresidencia", "items": ["GAA"]},
    {"nivel": "gerencia",        "items": ["PPC"]}
  ],
  "hijos": {"nivel": "campo", "items": [...], "total": 2, "truncado": false},
  "pozos": 128 | null,                  # REUSADO de _cuerpo (H7). null = ops no disponible
  "operador": "FRONTERA ENERGY" | null, # solo campos de terceros
  "fuera_estructura": false             # true = campo sin activo/gerencia/vp (caso CAJÚA)
}}
```

Por nivel (todo desde `hechos`, sin consultas nuevas):
- **campo** → `padres` = VP/gerencia/activo del `campo_row` (los que existan); `hijos` = **campos
  hermanos** del activo (H5), rotulados como tales; `operador`/`fuera_estructura` para terceros.
- **activo** → `padres` = gerencias y VPs (**listas**, H6); `hijos` = sus campos.
- **gerencia** → `padres` = sus VPs; `hijos` = activos (o campos si no hay activos).
- **vicepresidencia** → sin `padres`; `hijos` = sus gerencias.
- **operador** (H8) → `tipo: "jerarq_operador"`, sin árbol: nombre + lista de campos que opera +
  la nota de que no es un nivel de la jerarquía.

**Truncado:** `_lista()` corta en 14 (`:138`). El panel usa el mismo tope y **declara** el resto
(`total` + `truncado:true` → "+N más"), nunca recorta en silencio.

### 4.2 Contrato del panel — `jerarq_rank`

`{"tipo": "jerarq_rank", "datos": res}` con el `res` de `_rank_calcular` **tal cual** (H9), más la
nota de registro atemporal cuando `conteo == "pozos"` (H10).

### 4.3 `responder_cordial` — 5 salidas

| Caso | `mensaje` | `panel` |
|---|---|---|
| Sin tabla (`_cargar` falla) | — | devuelve `None` entero (igual que hoy) |
| Ranking aplicable | el de hoy | `jerarq_rank` |
| Ranking que declina (`aplica:False`) | `res["texto"]` | `None` |
| `_NOENT` (sin entidad) | `_NOENT` | `None` |
| Entidad resuelta | el de hoy | `jerarq_arbol` / `jerarq_operador` |

**`responder()` NO se toca** (H3): sigue devolviendo string.

### 4.4 `maquina_q.py`

Un único cambio, en `:368-370`, al patrón de cuantificar (`:378-381`):
```python
r = respuesta_jerarquizar.responder_cordial(texto, usuario=usuario)
if isinstance(r, dict):
    mensaje = r.get("mensaje") or mensaje
    panel = r.get("panel")
elif r:
    mensaje = r          # compatibilidad si alguna vez devolviera str
```
Actualizar el comentario de `:341` (ya no es "solo cuantificar").

### 4.5 Frontend — `multitab_shell.js`

Tres ramas nuevas en el dispatcher (`:2601-2604`) y tres constructores **puros**:
- **`__cnJerArbolHtml(d)`** — árbol. Padres arriba con sangría creciente (varios por nivel si los
  hay, H6), la entidad consultada **destacada**, hijos debajo. Chip de nivel por fila; pie con
  pozos (si no es `null`) y el "+N más" si `truncado`. Si `fuera_estructura` → nota con el operador
  en vez de un árbol vacío. Si `puente` → línea de corrección de nivel (H11).
- **`__cnJerOperadorHtml(d)`** (H8) — nombre + campos que opera + nota "no es un nivel".
- **`__cnJerRankHtml(d)`** — **reusa `.cn-rank*`** (H13); molde exacto: `__cnCuantRankHtml` (`:2540`).

La cabecera (nº · pregunta · hora) ya la pone `__cnPintarPanelCuant`.

⚠️ `__cnPintarPanelCuant` queda con nombre impreciso. **No se renombra aquí** (1 call site, pero
mezcla ruido con el cambio funcional). Se anota en su comentario como deuda menor.

### 4.6 Frontend — `colapsable.css`

Solo lo del árbol (el ranking reusa `.cn-rank*`, H13): `.cn-jer`, `.cn-jer__row`, `.cn-jer__lvl`
(chip), `.cn-jer__name`, `.cn-jer__row--self`, `.cn-jer__kids`, `.cn-jer__more`, `.cn-jer__nota`,
`.cn-jer__foot`. Sangría por `padding-left`. **Sin `overflow` propio** (el único scroller es `.cn-col`).

---

## 5. Orden de ejecución

1. `respuesta_jerarquizar.py` — `_cuerpo` devuelve `(texto, hechos)`; ajustar sus **2** call sites.
2. `respuesta_jerarquizar.py` — `_panel_desde_hechos(...)` (puro) + `responder_cordial` → dict.
3. `maquina_q.py:368-370` — consumir el dict; actualizar comentario `:341`.
4. `multitab_shell.js` — 3 constructores + 3 ramas.
5. `colapsable.css` — bloque `.cn-jer*`.
6. `templates/main.html` — bump `?v=` (2 líneas).
7. Validación estática (§7).

---

## 6. Reglas no negociables

- **`responder()` NO se toca** — lo usan los tests (H3).
- **Prohibido volver a llamar a `_contar_pozos`** para el panel: se reusa el valor de `_cuerpo` (H7).
- **Sin SQL nuevo**: todo sale de `_DATA` y de los hechos ya calculados.
- **El panel jamás pasa por el LLM** (regla madre: Python calcula, el LLM solo redacta el intro).
- **Sin entidad / ranking que declina → `panel: None`**, nunca un bloque vacío.
- **`operador` NO se pinta como nivel del árbol** (H8).
- **Padres en LISTA, no ruta única** (H6).
- **El truncado se DECLARA** (`total`), no se recorta en silencio.
- **`.cn-jer*` sin `overflow`** — un solo scroller.
- No se toca: el ranking de Cuantificar, Test Clas, el golden set, `analizar`, `OUT`.

---

## 7. Validaciones (100 % estáticas — sin LLM, sin backend, sin BD)

- `python -m py_compile respuesta_jerarquizar.py maquina_q.py`.
- `node --check static/js/multitab_shell.js`.
- Balance de llaves CSS + presencia de `.cn-jer*`.
- **grep de no-regresión (obligatorio):**
  - `_cuerpo(` tiene exactamente **2** call sites y ambos ajustados.
  - `_contar_pozos(` sigue con sus llamadas originales, **ninguna nueva**.
  - `def responder(` de jerarquizar conserva su firma (devuelve str).
  - Los 4 tipos `cuant_*` siguen en el dispatcher del frontend.
  - `assert r["panel"] is None` de `test_cuantificar_rango.py` intacto.

**Verificación en el servidor de pruebas (usuario), tras commit+push:**

| # | Pregunta | Esperado |
|---|---|---|
| 1 | `¿Qué campos tiene el activo Castilla?` | Árbol GAA → PPC → **CASTILLA** → 2 campos, con pozos al pie |
| 2 | `¿A qué activo pertenece Cajúa?` | **CAJÚA** con nota "fuera de la estructura ECP" + operador |
| 3 | `¿Qué vicepresidencia tiene más gerencias?` | Ranking con estilo idéntico al de producción |
| 4 | `¿Cuáles son los campos con más pozos?` | Ranking **con la nota de "registro atemporal"** (H10) |
| 5 | `¿De qué gerencia es el campo Rubiales?` | Árbol con la ruta ascendente |
| 6 | Una entidad con >1 gerencia | **Varias** gerencias en el nivel, no una sola (H6) |
| 7 | `¿qué es Marte?` (sin entidad) | **Sin bloque nuevo**; el panel no cambia |
| 8 | Luego una de Cuantificar | Se apila normal; los árboles anteriores intactos |
| 9 | Panorama de arriba | Intacto en todas |

---

## 8. Fuera de alcance (declarado, no enterrado)

- **Árbol navegable/plegable**: el panel es de lectura. La navegación ya existe por conversación
  (la memoria `_CTX` resuelve "¿y de CASTILLA NORTE?").
- **Renombrar `__cnPintarPanelCuant`**: deuda menor anotada.
- **Panel para ANALIZAR y OUT**: siguen sin panel (`analizar` devuelve str, `maquina_q.py:390`).
- **Conteo de pozos por activo/gerencia/VP en el ranking**: ya está diferido por el propio módulo
  (`_RANK_POZOS_DIFERIDO`, `:269`); el panel refleja lo que hay, no lo adelanta.
- **Caché para `_contar_pozos`** (H7): sería una mejora real de latencia, pero es un cambio de
  rendimiento del módulo existente, ajeno a esta tarea. **Anotado como deuda.**
