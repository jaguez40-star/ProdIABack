# plan_PANEL-N1-ENRIQUECIDO — 2026-09-08 · v2 (auditado y corregido)

**ID tarea:** PANEL-N1-ENRIQUECIDO
**Fecha:** 2026-09-08
**Repos:** `ProdIABack` (`C:\APLICACIONES\ProdIA\Repo ProdIA\backend`) y
`ProdIAWebFront` (`C:\APLICACIONES\ProdIA\Repo ProdIA\frontend`)
**Alcance:** el panel de una pregunta puntual mensual (nivel **N1**) pasa del KPI escueto
actual al panel de dos columnas `cuant_dia_panel` (tarjeta KPI + curva diaria), que **ya
existe y está en producción**.

**Qué NO se toca:** el clasificador, `maquina_q.py`, el drill, los niveles N1D/N1DSEL/N1DSER/
N2/N3/N4/NCMP/N3P, los goldens, la BD, el ETL, el proxy Flask (`routes/api.py`).

### Decisiones cerradas del usuario (no se re-discuten)

1. El panel de N1 debe mostrar la **curva diaria del mes** con sus líneas de referencia, en la
   disposición horizontal real (tarjeta KPI a la izquierda, gráfico a la derecha).
2. La tarjeta KPI incluye **Proyección de cierre**.
3. La referencia **cambia con el nivel**: P50 en VP y global; PPTO en campo/activo/gerencia.
4. El **P50 se dibuja también como línea** en el gráfico, no solo como cifra en la tarjeta.

### Modelo visual aprobado

`https://claude.ai/code/artifact/3b0c91f3-30d4-4c9c-9596-72119e065c4b`

---

## §0.0 · Changelog v1 → v2

El v1 se auditó recorriendo la cadena de llamadas real del frontend. Salieron **cuatro
errores**, dos de ellos capaces de dejar el panel en blanco:

| # | Qué decía el v1 | Qué se midió | Efecto si no se corrige |
|---|---|---|---|
| C-1 | Cambio 7: declarar `var p50Ref = meta.p50…` junto a `var promMes` | 🔴 **`var promMes` vive en `__cnDailyInto` (`:2362`), pero las líneas se dibujan en `__cnDailyPlot` (`:2422-2560`). Son DOS funciones distintas**, y `__cnDailyInto(prod, hostEl, d, tarjetas)` **no recibe `meta`** | **`ReferenceError: meta is not defined`.** El gráfico deja de pintar por completo — no solo el P50 |
| C-2 | Propagar el P50 metiéndolo en `edScoped.meta` | 🔴 Ese objeto nunca llega al dibujo: la cadena es `__cnPaintFocoStk(blk, ed, dd, sufijo)` → `__cnDailyInto(f.producto, day, dd, ed.tarjetas)`. **Solo viajan `dd` y `ed.tarjetas`** | La línea del P50 **nunca aparece**, sin ningún error visible |
| C-3 | «Añadir `p50Ref` a la lista de candidatos del eje» y «leer la expresión del archivo» | 🟡 Se localizó exacta (`:2504`) y se cerró con código literal. También `pptoPlot` (`:2429`), que era una asignación directa | El executor habría tenido que improvisar en dos puntos — prohibido por §5 |
| C-4 | Un solo call site de `__cnPaintFocoStk` | 🟡 Hay **tres**: `:459`, `:4218`, `:4327`. El de `:459` es la **repintada al restaurar el DOM** (volver de otra pestaña) | La línea del P50 desaparecería al cambiar de pestaña y volver |

**El precedente que resuelve C-1 y C-2 ya está en el código.** El PPTO diario tuvo exactamente
este problema —venía de otro endpoint y no llegaba al dibujo— y se resolvió **añadiendo un
parámetro** a la cadena. Está documentado en `:2286-2288`:

> «Viene de `ed.tarjetas` (payload de /ejecutivo), NO de `d` (payload de /desempeno) — son dos
> endpoints distintos; **por eso entra como parámetro opcional y los dos call sites lo pasan**.»

El v2 clona ese patrón en vez de inventar uno nuevo (§3.2).

---

## §0 · Contexto para el agente EXECUTOR

**Proyecto ProdIA** (Ecopetrol). Dos repos hermanos, **dos procesos**:

| | `frontend\` | `backend\` |
|---|---|---|
| Repo | ProdIAWebFront | ProdIABack |
| Stack | Flask + Jinja2 | FastAPI (`uv`) |
| Puerto | 5029 | 5030 |

El navegador **nunca** habla con el 5030: Flask hace de proxy. Este plan **no añade rutas
nuevas** — los dos endpoints que usa el panel (`/api/analisis/desempeno` y
`/api/analisis/ejecutivo`) ya están expuestos y en uso.

**El Motor Q v2** clasifica en cuatro grupos. Dentro de Cuantificar hay *niveles temporales*:
**N1** (un mes puntual), N2 (acumulado), N3 (serie), N4 (variación), N1D (un día), etc. Cada
nivel elige su panel en un mapa. **N1 es el único sin panel gráfico**, y es la pregunta más
frecuente del sistema.

**Archivos que se tocan (rutas absolutas):**

| # | Acción | Ruta |
|---|---|---|
| 1 | MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` |
| 2 | MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\static\js\multitab_shell.js` |
| 3 | MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html` *(una línea: el cache-buster, §3.4)* |
| 4 | CREAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_panel_n1_enriquecido.py` |

⚠️ **Son DOS repos distintos** → **DOS commits**, uno por repo. Nunca mezclarlos.

**Convenciones obligatorias:**

- **JS ES5 clásico**: `var` + `function`. **Sin** arrow functions, **sin** template literals,
  **sin** `const`/`let`. El archivo entero está escrito así.
- Todo el código y **todos los comentarios en español**.
- Python: se ejecuta con `uv run` desde `...\backend\backend`.
- Los comentarios de este proyecto explican **por qué**, con la evidencia medida
  (archivo:línea). Los bloques nuevos llevan la marca `[2026-09-08 · PANEL-N1]`.
- **Si algo del plan no calza con el código real, DETENERSE y reportar. No improvisar.**

---

## §1 · Hallazgos de la auditoría

### 🟢 H-01 (confirmación) — El panel entero ya existe. No se construye nada.

`grep` sobre el frontend: el gráfico de la captura del usuario es el panel
**`cuant_dia_panel`**, ya en producción.

| Pieza | Dónde | Estado |
|---|---|---|
| Dibujo (curva + 3 líneas de referencia + etiquetas anti-colisión) | `multitab_shell.js:2319-2484` | ✅ existe |
| Rejilla 2 columnas (`30fr / 70fr`, alto `375px`) | `colapsable.css:2505-2529` | ✅ existe |
| Constructor del bloque | `multitab_shell.js:3901-3923` (`__cnCompProdHtml`) | ✅ existe |
| Cargador + caché de navegador | `multitab_shell.js:4261-4330` (`__cnCompProdCargar`) | ✅ existe |
| Despacho por tipo de panel | `multitab_shell.js:4366` y `:4469` | ✅ existe |
| Endpoints de datos | `/api/analisis/desempeno`, `/api/analisis/ejecutivo` | ✅ existen |

**Hoy solo se activa cuando la pregunta menciona un DÍA.** El mapa de
`respuesta_cuantificar.py:64-70` da `cuant_dia_panel` a N1D/N1DSEL/N1DSER, y N1 cae al
`cuant_kpi` por defecto. El propio código lo declara como deuda:

```python
"NCMP": "cuant_cmp", "N3P": "cuant_serie_ppto"}   # N1 -> "cuant_kpi" (Fase 3)
```

### 🟢 H-02 (confirmación) — N1 ya tiene las 6 claves que el panel pide

El contrato de `cuant_dia_panel` (leído en `__cnCompProdCargar`) exige: `entidad`, `nivel`,
`segmento`, `periodo`, `productos`, `dia_marcado`.

El bloque que las arma para N1D (`respuesta_cuantificar.py:161-170`) las deriva de datos que
**N1 también posee**: `res["entidad"]["nombre"]`, `res["entidad"]["nivel"]`, y el mes desde
`res["mes"]`.

**La única diferencia:** `dia_marcado` va en `None` — no hay un día que resaltar. Ese caso
**ya está soportado**: es exactamente lo que hace `N1DSER` (`:131-152`), cuyo comentario dice
*«lo único que no se emite es `dia_marcado` — no hay un día que resaltar, la respuesta ES la
curva completa»*.

### 🟢 H-03 (confirmación) — La tarjeta KPI no se borró: se desactivó

`__cnCompProdHtml` (`:3908-3915`) activa el modificador `--solo` (curva a ancho completo)
**solo cuando no recibe tarjetas**. Hoy `__cnCompProdCargar` le pasa `[]` a propósito, con
este comentario (`:4318-4324`):

> «QV2-PANEL-DIA · SIN tarjeta KPI: se pasa `[]` a propósito (decisión del usuario). La
> pregunta es por UN DÍA y la tarjeta hablaba del MES […] **Para volver a mostrarla basta con
> devolver `ed.tarjetas` aquí.**»

Ese razonamiento **no aplica a N1**: aquí la pregunta *es* por el mes, así que la tarjeta y el
texto hablan de lo mismo. Se reactiva **solo para N1**, sin tocar el comportamiento de N1D.

### 🔴 H-04 (BLOQUEANTE) — El P50 está en BPD; la curva en kbopd. NO se pueden mezclar.

Este es el hallazgo que determina toda la §3.2.

`p50_referencia.py:28-39` documenta, con cifras medidas contra la BD, que la hoja del P50
(`NEW MES-AÑO` t8) está en **promedio diario, en BPD**, y que **ningún ratio con el fact
operativo es 1e6**:

```
CRUDO  t8 = 509.804,5  ·  REPORTE_PRESIDENT base_p50 = 521,8 kbpe  ⇒ t8 son BPD
```

Por eso ese módulo tiene su **propia unidad** (`_UNIDAD_VP = {"CRUDO": "bpd", ...}`), su
**propio formateador** (`_fmt_vp`, cifra tal cual) y marca sus payloads con **`fmt: "vp"`**.

⚠️ **El precedente es un bug real, `dd8ffa2`**, y el comentario advierte por qué no se
detectó: *«las verificaciones en navegador solo usaron GOR y Rubiales, ambos CRUDO, que no se
divide»*. En gas, la cifra salió **mil veces menor, sin error visible**.

**Consecuencia para este plan:** el valor P50 **debe dividirse entre 1000** antes de dibujarlo
junto a una curva en kbopd. No hacerlo pinta la línea fuera de escala por un factor de 1000.
Se hace **una sola vez, en el backend**, y se emite ya convertido — el frontend no debe
conocer esta conversión.

### 🔴 H-05 (BLOQUEANTE) — El P50 no existe por campo. La referencia depende del nivel.

`p50_referencia.py:6-7` y `:19-20`:

```python
_NIVELES_OK = (None, "vicepresidencia")   # None = global ECP
```

> «NO se define por campo/activo/gerencia en NINGUNA de las 16 hojas del reporte — a esos
> niveles se DECLINA, honesto, y se ofrecen las vecinas que EXISTAN.»

`nivel_soportado(nivel, resuelta)` acepta además `gerencia` **si** trae `puente`.

**Consecuencia:** el panel **no puede** rotular «REAL / P50» en un campo. La regla es:

| Nivel de la entidad | Referencia del anillo | Línea extra en el gráfico |
|---|---|---|
| `vicepresidencia`, global, `gerencia` con puente | **P50** | sí |
| `campo`, `activo`, `gerencia` sin puente, operador | **PPTO** | no |

⚠️ Esa decisión se toma **llamando a `nivel_soportado()`**, nunca con una comprobación propia
(ver H-08).

### 🟡 H-06 (relevante) — `serie_por_vp` sí da el P50 del mes preguntado

`p50_referencia.py:165-250`. Devuelve `serie`: una lista de `{fecha, p50, real}` con **los 12
meses**, no solo el último. Así que para «¿cuánto produjo la VRO en abril?» se toma el punto
de abril, no el del corte. Ya tiene caché en proceso (`_SERIE_VP_CACHE`).

⚠️ `real` es `None` en los meses sin dato, y su docstring es explícita: *«el trazo se corta
ahí, NUNCA se interpola ni se rellena con 0»*. Este plan **solo usa `p50`**, que sí está
completo los 12 meses.

### 🟡 H-07 (relevante) — El gráfico admite una 4ª línea, pero hay que redistribuir etiquetas

Las líneas de referencia se dibujan como bloques independientes de Plotly
(`multitab_shell.js:2455-2486`), cada uno con su `if`:

```javascript
if (pptoPlot)    { shapes.push(...); anns.push({ xanchor: "right",  ... }); }
if (promMesPlot) { shapes.push(...); anns.push({ xanchor: "center", ... }); }
// promedio 2026:                    anns.push({ xanchor: "left",   ... });
```

Añadir la cuarta es **un bloque más del mismo patrón**. Dos condicionantes ya documentados:

1. **Las tres anclas están tomadas** (left / center / right). El comentario de `:2456-2458`
   explica que se repartieron así justamente para que no se solapen. La cuarta obliga a
   redistribuir.
2. **El eje Y se calcula desde las series Y las referencias** (`:2492-2500`), con un caso
   medido: *«CASTILLA·mayo: curva ~210-225k, promedio 220.918, PPTO 215.460 → se diferencian
   en ~2% pero el eje llegaba a 250k»*. Y advierte que sin meter el PPTO en el `max`, su línea
   **quedaba fuera del área visible**. El P50 debe entrar en ese mismo cálculo.

### 🟡 H-08 (relevante) — La brecha de jerarquías obliga a delegar la decisión de nivel

`CLAUDE.md §6` documenta la brecha prioritaria abierta: **conviven tres catálogos de entidades
y el resolutor de Cuantificar lee el más pobre**. Síntoma medido: «el activo CASTILLA»
devuelve las cifras del **campo** CASTILLA.

**Consecuencia:** una comprobación propia del tipo `if nivel == "vicepresidencia"` dentro del
panel heredaría esa brecha. La decisión se delega **siempre** en
`p50_referencia.nivel_soportado()`, que ya la resuelve bien (incluye la rama `gerencia` +
`puente`) y es el único sitio donde vive esa regla.

### 🟡 H-09 (relevante) — Coste: N1 es la pregunta más frecuente y el panel hace 2 fetch

`__cnCompProdCargar` dispara `/api/analisis/desempeno` **y** `/api/analisis/ejecutivo`. Hoy N1
no hace ninguno. Mitigantes ya presentes: `__cnDesempCache` y `__cnEjecCache` (caché de
navegador por entidad+nivel+periodo, compartida con el tablero).

No es bloqueante —N1D ya paga ese coste—, pero **debe medirse en pruebas** (V-8 de la §6.2).

### 🟢 H-10 (confirmación) — Blancos/gas: las guardas ya existen, no se replican

`multitab_shell.js:2330-2336`: la curva diaria y la cifra mensual **no reconcilian** en
BLANCOS (factor 2,10-3,06×), y `promedio_dia == null` funciona de semáforo: *«si él no se fía
del mensual para este producto, el PPTO tampoco vale»*. Este plan **no toca** esa lógica.

### 🔴 H-11 (BLOQUEANTE) — 🆕 v2 · El P50 no llega solo al dibujo: hay que propagarlo

Es el hallazgo que corrige C-1 y C-2. La cadena real, medida:

```
__cnCompProdCargar(blk, datos, sufijo)                    :4261   datos.p50
  └─ __cnPaintFocoStk(blk, ed, dd, sufijo)                :2274   ← solo ed, dd, sufijo
       └─ __cnDailyInto(prod, hostEl, d, tarjetas)        :2303   ← solo dd y ed.tarjetas
            └─ __cnDailyPlot(elp, …, promMesRef, conLeyenda)  :2422   ← 13 posicionales
                 └─ shapes/anns: aquí se dibujan las líneas    :2455-2486
```

**Ningún objeto compartido une el payload del panel con el dibujo.** `__cnDailyInto` no recibe
`meta`, así que el `var p50Ref = meta.p50…` del v1 lanzaba `ReferenceError` y **el gráfico
entero dejaba de pintar** — no solo la línea nueva.

**El precedente exacto ya está resuelto en el código** (`:2286-2288`), para el PPTO diario:

> «Viene de `ed.tarjetas` (payload de /ejecutivo), NO de `d` (payload de /desempeno) — son dos
> endpoints distintos; **por eso entra como parámetro opcional y los dos call sites lo pasan**.»

El v2 clona ese patrón: `p50Dia` como **parámetro opcional al final** de las tres firmas. Al ir
al final, los call sites ajenos (el panel de Análisis) reciben `undefined` y no cambian.

### 🟡 H-12 (relevante) — 🆕 v2 · `__cnPaintFocoStk` tiene TRES call sites, no uno

`grep -n "__cnPaintFocoStk("` → `:459`, `:4218`, `:4327`.

| Línea | Quién | ¿Pasa el P50? |
|---|---|---|
| `:4327` | `__cnCompProdCargar` — el camino normal de una pregunta | **sí** |
| `:459` | **repintada al restaurar el DOM** (volver de otra pestaña) | **sí**, desde `blk.__cnAnzP50` |
| `:4218` | `__cnAnzCargarFoco` — panel de Análisis | **no**, y no debe |

Sin el `:459`, la línea del P50 **desaparecería al cambiar de pestaña y volver**: ese repintado
no pasa por `__cnCompProdCargar`. Por eso el Cambio 11 guarda el valor en el bloque
(`blk.__cnAnzP50`), junto a `__cnAnzEd`/`__cnAnzDd`, que existen para exactamente lo mismo.

⚠️ La línea `blk.__cnAnzEd = edScoped; …` aparece **dos veces idéntica** (`:4228` y `:4335`).
Solo se toca la de `:4335`.

### 🟢 H-13 (confirmación) — Cache-buster obligatorio

Memoria del proyecto: al cambiar `multitab_shell.js` hay que subir el `?v=` de su `<script>`,
o el navegador sirve la versión vieja y el panel «no pinta» con la consola limpia.

---

## §2 · Estado actual

```
respuesta_cuantificar.py:64-70     _PANEL_TIPO — N1 NO está en el mapa → "cuant_kpi"
respuesta_cuantificar.py:122-215   _panel_datos() — N1 emite solo 4 claves útiles:
                                     real · ppto · cumplimiento_pct · estado
respuesta_cuantificar.py:531       tipo = _PANEL_TIPO.get(res.get("nivel"), "cuant_kpi")

multitab_shell.js:4366             despacho: "cuant_dia_panel" → placeholder
multitab_shell.js:4469             carga:    "cuant_dia_panel" → __cnCompProdCargar
multitab_shell.js:4324             host.innerHTML = __cnCompProdHtml(focosF, ed.meta, [], sufijo)
                                                                                   ↑ sin tarjeta
multitab_shell.js:2455-2486        3 líneas de referencia (promedio 2026 · media mes · PPTO)
```

Lo que el ejecutor N1 **ya calcula y el panel descarta** (`ejecutor.py:159-176`):
`huella.registros`, `huella.dias_del_mes`, `huella.es_proyeccion`, `referencia_label`,
`mes`, `zoom`, `avisos`.

---

## §3 · Especificación

### 3.1 · BACKEND · `respuesta_cuantificar.py` — N1 pasa a `cuant_dia_panel`

#### Cambio 1 de 4 — Importar el módulo del P50

**LOCALIZAR** (bloque de imports, al principio del archivo):

```python
from app.features.consulta_v2.cuantificar import ranking as _ranking
```

**INSERTAR INMEDIATAMENTE DESPUÉS:**

```python
# [2026-09-08 · PANEL-N1] El P50 para la tarjeta y la línea del panel. Se importa el MÓDULO,
# no una copia de su regla: `nivel_soportado()` es el único sitio donde vive «qué niveles
# tienen P50» (campo/activo NO lo tienen — p50_referencia.py:6-7,19-20). Duplicar esa
# comprobación aquí heredaría la brecha de jerarquías de CLAUDE.md §6, donde «el activo
# CASTILLA» resuelve como el CAMPO CASTILLA.
from app.features.consulta_v2.analizar import p50_referencia as _p50
```

#### Cambio 2 de 4 — El helper del P50

**LOCALIZAR:**

```python
def _panel_datos(res: dict) -> dict:
```

**INSERTAR INMEDIATAMENTE ANTES** de esa línea:

```python
# [2026-09-08 · PANEL-N1] Escala de la hoja P50 -> escala del panel.
# 🔑 NO es un factor cosmético. La hoja «NEW MES-AÑO» t8 está en BPD (promedio diario), y el
#    panel dibuja en kbopd/kboepd. p50_referencia.py:28-39 lo mide contra la BD y advierte que
#    NINGÚN ratio con el fact operativo es 1e6. Mezclar las dos escalas pinta la línea del P50
#    mil veces fuera de sitio. El precedente es el bug dd8ffa2, que NO se detectó en navegador
#    «porque las verificaciones solo usaron GOR y Rubiales, ambos CRUDO».
# 🔑 La conversión se hace UNA vez, AQUÍ, y el payload viaja ya en la escala del panel: el
#    frontend no debe conocer esta unidad (si la conociera habría dos criterios que se
#    desincronizan — la lección de `_forma_no_soportada_ranking`).
_P50_BPD_A_KBPD = 1000.0


def _p50_del_mes(resuelta: dict, res: dict) -> dict | None:
    """{'valor','label'} del compromiso P50 para la entidad y el MES de la pregunta, ya en la
    escala del panel. None si ese nivel no tiene P50 (campo/activo) o no hay dato.

    El mes sale de la SERIE, no del corte: `serie_por_vp` devuelve los 12 meses, así que
    «¿cuánto produjo la VRO en abril?» compara contra el P50 de ABRIL (H-06). Respetar el
    periodo de la pregunta es una regla del proyecto (CLAUDE.md §7) y la fuente de varios bugs
    silenciosos.
    """
    nivel = resuelta.get("nivel")
    if not _p50.nivel_soportado(nivel, resuelta):
        return None
    vice = resuelta.get("valor") if nivel == "vicepresidencia" else None
    if nivel == "gerencia":
        vice = (resuelta.get("puente") or {}).get("vp") or None
    if not vice:
        return None
    serie = _p50.serie_por_vp(vice, (res.get("producto") or "crudo").upper())
    if not serie or not serie.get("serie"):
        return None
    mes = res.get("mes") or {}
    anio, num = mes.get("anio"), mes.get("mes")
    if not (anio and num):
        return None
    clave = f"{anio:04d}-{num:02d}"
    for punto in serie["serie"]:
        if str(punto.get("fecha", "")).startswith(clave) and punto.get("p50"):
            return {"valor": float(punto["p50"]) / _P50_BPD_A_KBPD, "label": "P50"}
    return None
```

#### Cambio 3 de 4 — `_panel_datos` emite el contrato de `cuant_dia_panel` para N1

**LOCALIZAR** (la rama `else` final de `_panel_datos`):

```python
    else:                                   # N1/N2 (KPI)
        d.update({"real": res["resultado"]["valor"], "ppto": res["referencia_valor"],
                  "cumplimiento_pct": res["cumplimiento_pct"], "estado": res["estado"]})
```

**SUSTITUIR POR:**

```python
    else:                                   # N1/N2 (KPI)
        d.update({"real": res["resultado"]["valor"], "ppto": res["referencia_valor"],
                  "cumplimiento_pct": res["cumplimiento_pct"], "estado": res["estado"]})
        # [2026-09-08 · PANEL-N1] N1 pasa al panel de dos columnas (tarjeta KPI + curva diaria).
        # Las 6 claves del contrato de `cuant_dia_panel` son las MISMAS que arma N1D arriba
        # (:161-170) y N1 ya las tiene todas.
        # 🔑 `dia_marcado` va en None a propósito: no hay un día que resaltar, la respuesta ES
        #    el mes. El caso ya está soportado — es lo que hace N1DSER, cuyo comentario dice
        #    «lo único que no se emite es dia_marcado […] la respuesta ES la curva completa».
        # 🔑 El periodo sale del MES DE LA PREGUNTA, no del último mes con datos: mismo criterio
        #    que N1D (decisión del usuario, 2026-08-25). Si preguntan por abril, la curva es de
        #    abril.
        if nivel == "N1":
            _m = res.get("mes") or {}
            d.update({
                "entidad": res["entidad"]["nombre"],
                "nivel_entidad": res["entidad"]["nivel"],
                "segmento": "ecp",
                "periodo": f"{_MESES_PANEL[_m['mes']]} {_m['anio']}",
                "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
                "dia_marcado": None,
                # Respaldo de confianza de la cifra: no es lo mismo un mes con 30 de 30 días
                # reportados que con 12. Ya lo calcula el ejecutor y hoy se descarta.
                "dias_con_dato": (res.get("huella") or {}).get("registros"),
                "dias_del_mes": (res.get("huella") or {}).get("dias_del_mes"),
                "es_proyeccion": (res.get("huella") or {}).get("es_proyeccion"),
                "referencia_label": res.get("referencia_label", "presupuesto"),
                # `p50` solo viaja si el NIVEL lo tiene (H-05). En un campo va None y el panel
                # rotula PPTO — nunca se inventa un compromiso que no existe.
                "p50": res.get("p50"),
            })
```

> ⚠️ **`nivel_entidad`, no `nivel`.** La clave `nivel` del payload ya la ocupa el nivel
> temporal (`"N1"`), fijado en la primera línea de `_panel_datos`. N1D la pisa con el nivel de
> entidad; aquí **no se pisa** para no romper a quien lea `d["nivel"]`. El frontend leerá
> `nivel_entidad` (§3.2, Cambio 6).

#### Cambio 4 de 4 — `responder()` calcula el P50 antes de armar el panel

**LOCALIZAR:**

```python
    mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
    tipo = _PANEL_TIPO.get(res.get("nivel"), "cuant_kpi")
    return {"mensaje": mensaje, "panel": {"tipo": tipo, "datos": _panel_datos(res)}}
```

**SUSTITUIR POR:**

```python
    mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
    # [2026-09-08 · PANEL-N1] El P50 se resuelve AQUÍ (no dentro de _panel_datos) porque hace
    # falta `resuelta` —el dict del resolutor, con `nivel` y `puente`— y esa función solo
    # recibe `res`. Se adjunta a `res` para que _panel_datos lo emita sin cambiar su firma.
    # Best-effort: si el P50 falla o no aplica, el panel sale con PPTO y la respuesta NO se
    # degrada (mismo criterio que el backstop de entidad: informativo, nunca bloquea).
    if res.get("nivel") == "N1":
        try:
            res["p50"] = _p50_del_mes(resuelta, res)
        except Exception:
            res["p50"] = None
    tipo = _PANEL_TIPO.get(res.get("nivel"), "cuant_kpi")
    if res.get("nivel") == "N1":
        tipo = "cuant_dia_panel"        # [2026-09-08 · PANEL-N1] salda la deuda de :70
    return {"mensaje": mensaje, "panel": {"tipo": tipo, "datos": _panel_datos(res)}}
```

### 3.2 · FRONTEND · `multitab_shell.js`

#### Cambio 5 de 11 — La tarjeta KPI reaparece en N1

**LOCALIZAR** (dentro de `__cnCompProdCargar`, ~`:4324`):

```javascript
      host.innerHTML = __cnCompProdHtml(focosF, ed.meta, [], sufijo);
```

**SUSTITUIR POR:**

```javascript
      // [2026-09-08 · PANEL-N1] En una pregunta MENSUAL (N1) la tarjeta SÍ va: el comentario de
      // arriba la quitó porque la pregunta era por UN DÍA y la tarjeta hablaba del MES —dos
      // cifras casi iguales, una al lado de otra—. Aquí la pregunta ES por el mes, así que
      // tarjeta y texto hablan de lo mismo. `dia_marcado === null` es la marca de que la
      // pregunta es mensual (lo emite el backend, respuesta_cuantificar.py).
      var _esMes = datos.dia_marcado == null;
      var _tarj = _esMes ? (ed.tarjetas || []) : [];
      host.innerHTML = __cnCompProdHtml(focosF, ed.meta, _tarj, sufijo);
```

> ### 🔴 Antes de tocar el frontend: la cadena de propagación (C-1, C-2)
>
> El P50 nace en el payload del panel (`datos.p50`) y tiene que llegar hasta donde se dibujan
> las líneas. **No hay ningún objeto compartido que las una**: hay que pasarlo de mano en mano,
> exactamente como se hizo con el PPTO diario (`:2286-2288`).
>
> ```
> __cnCompProdCargar(blk, datos, sufijo)          datos.p50  ← lo emite el backend
>   └─ __cnPaintFocoStk(blk, ed, dd, sufijo)      ① +p50 como parámetro
>        └─ __cnDailyInto(prod, host, d, tarj)    ② +p50 como parámetro
>             └─ __cnDailyPlot(… , promMesRef, conLeyenda)   ③ +p50 como parámetro
>                  └─ aquí se dibuja la línea      ④
> ```
>
> Los Cambios 6 a 9 recorren esa cadena **de abajo arriba**: primero quien dibuja, luego quien
> le pasa el dato. Así el archivo nunca queda invocando algo que aún no acepta ese parámetro.

#### Cambio 6 de 11 — `__cnDailyPlot` acepta el P50 y lo dibuja

**LOCALIZAR** (`:2422`, la firma — verificada, 13 parámetros):

```javascript
  function __cnDailyPlot(elp, fechas, valores, ref, unidad, esGas, refEsAnio, col, holgura, ejes, pptoDia, promMesRef, conLeyenda) {
```

**SUSTITUIR POR:**

```javascript
  // [2026-09-08 · PANEL-N1] +p50Dia: 4ª línea de referencia, el COMPROMISO P50. Entra como
  // parámetro por la misma razón que `pptoDia` (:2286-2288): viene de un payload distinto al de
  // la curva y no hay objeto compartido que los una. Va al FINAL de la firma para no correr las
  // 13 posiciones existentes — es una función posicional con 4 call sites.
  // 🔑 Llega YA en la escala del gráfico (kbopd): el ÷1000 desde los BPD de la hoja P50 lo hizo
  //    el backend. Aquí NO se vuelve a escalar (H-04).
  function __cnDailyPlot(elp, fechas, valores, ref, unidad, esGas, refEsAnio, col, holgura, ejes, pptoDia, promMesRef, conLeyenda, p50Dia) {
```

#### Cambio 7 de 11 — La 4ª línea del gráfico: el P50

**LOCALIZAR** (bloque de la media del mes, ~`:2480-2486`):

```javascript
    if (promMesPlot) {
      shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: promMesPlot, y1: promMesPlot,
        line: { color: "#5A6B7A", width: 1.5, dash: "dashdot" } });
      if (conLeyenda) refLeyenda("media del mes", promMesRef, "#5A6B7A", "dashdot");
      else anns.push({ x: 0.5, y: promMesPlot, xref: "paper", yref: "y", xanchor: "center", yanchor: "bottom",
        text: "media del mes · " + fmtD(promMesRef) + uni,
        showarrow: false, font: { size: 10, color: "#5A6B7A" } });
    }
```

**SUSTITUIR POR:**

```javascript
    if (promMesPlot) {
      shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: promMesPlot, y1: promMesPlot,
        line: { color: "#5A6B7A", width: 1.5, dash: "dashdot" } });
      if (conLeyenda) refLeyenda("media del mes", promMesRef, "#5A6B7A", "dashdot");
      // [2026-09-08 · PANEL-N1] Ancla a la DERECHA cuando hay P50: la cuarta línea necesita
      // sitio y el centro es el hueco más ancho. Sin P50, se queda centrada como siempre.
      else anns.push({ x: (p50Plot ? 1 : 0.5), y: promMesPlot, xref: "paper", yref: "y",
        xanchor: (p50Plot ? "right" : "center"), yanchor: "bottom",
        text: "media del mes · " + fmtD(promMesRef) + uni,
        showarrow: false, font: { size: 10, color: "#5A6B7A" } });
    }
    // [2026-09-08 · PANEL-N1] COMPROMISO P50 — la 4ª línea. Es la referencia que MANDA cuando
    // existe (VP y global), así que va en rojo corporativo y con el trazo más grueso de las
    // cuatro: el resto son contexto, esta es el compromiso.
    // 🔑 Solo se dibuja si el backend la mandó. En un CAMPO no llega (el P50 no está definido a
    //    ese nivel — p50_referencia.py:6-7) y el panel se queda con sus tres líneas de siempre.
    // 🔑 La cifra llega YA en la escala del panel (kbopd): el backend la convirtió desde los BPD
    //    de la hoja P50. Aquí NO se vuelve a escalar — hacerlo dividiría dos veces.
    // 🔑 `dash` largo (12 4) para distinguirla del `dash` (8 6) del promedio 2026, del `dashdot`
    //    de la media y del `dot` del PPTO: las cuatro deben leerse por su trazo en blanco y negro.
    if (p50Plot) {
      shapes.push({ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: p50Plot, y1: p50Plot,
        line: { color: "#C5311E", width: 2, dash: "12px 4px" } });
      if (conLeyenda) refLeyenda("compromiso P50", p50Dia, "#C5311E", "dash");
      else anns.push({ x: 0.5, y: p50Plot, xref: "paper", yref: "y", xanchor: "center", yanchor: "bottom",
        text: "compromiso P50 · " + fmtD(p50Dia) + uni,
        showarrow: false, font: { size: 10, color: "#C5311E" } });
    }
```

#### Cambio 8 de 11 — Declarar `p50Plot` y meterlo en el eje

**LOCALIZAR** (`:2429`, verificado — es una asignación directa):

```javascript
    var pptoPlot = (pptoDia != null) ? pptoDia : null;   // [BEQ]
```

**INSERTAR INMEDIATAMENTE DESPUÉS:**

```javascript
    // [2026-09-08 · PANEL-N1] Misma proyección que pptoPlot: el P50 se dibuja en el mismo eje y
    // ya viene en su escala. Se declara AQUÍ, junto a las otras tres referencias y ANTES del
    // cálculo del rango: con `var`, declararlo después lo dejaría en `undefined` dentro de ese
    // cálculo por hoisting, y la línea quedaría fuera del área visible sin ningún error — el
    // mismo fallo silencioso que documenta el guard de `prom2026` en :2336.
    var p50Plot = (p50Dia != null && p50Dia > 0) ? p50Dia : null;
```

**Y ADEMÁS**, el P50 debe entrar en el cálculo del rango del eje Y.

**LOCALIZAR** (`:2504`, verificado):

```javascript
    var refs = [refPlot, pptoPlot, promMesPlot].filter(function (v) { return v != null && v > 0; });
```

**SUSTITUIR POR:**

```javascript
    // [2026-09-08 · PANEL-N1] `p50Plot` entra en el rango por la MISMA razón que el PPTO: es una
    // META y suele estar POR ENCIMA de la curva. El comentario de arriba lo documenta con el caso
    // medido —«sin esto su línea quedaba fuera del área visible, justo el caso de CRUDO y GAS»—;
    // el P50, que está aún más alto que el PPTO, se saldría igual.
    var refs = [refPlot, pptoPlot, promMesPlot, p50Plot].filter(function (v) { return v != null && v > 0; });
```

#### Cambio 9 de 11 — `__cnDailyInto` acepta el P50 y se lo pasa al dibujo

**LOCALIZAR** (`:2303`, la firma):

```javascript
  function __cnDailyInto(prod, hostEl, d, tarjetas) {
```

**SUSTITUIR POR:**

```javascript
  // [2026-09-08 · PANEL-N1] +p50Dia: viaja de aquí a __cnDailyPlot. Mismo tratamiento que
  // `tarjetas` — parámetro opcional al final, y los call sites que no lo tengan pasan undefined.
  function __cnDailyInto(prod, hostEl, d, tarjetas, p50Dia) {
```

**Y ADEMÁS**, pasárselo a `__cnDailyPlot`. La llamada termina en `:2383` con el argumento
`conLeyenda` (que es `!esCompProd`). `p50Dia` es el **14.º y último**, así que va **después**.

**LOCALIZAR** (`:2383`, verificado — línea única):

```javascript
                  !esCompProd);
```

**SUSTITUIR POR:**

```javascript
                  !esCompProd,
                  p50Dia);   // [2026-09-08 · PANEL-N1] 14.º y último: el compromiso P50
```

#### Cambio 10 de 11 — `__cnPaintFocoStk` propaga el P50 a sus dos dibujos

**LOCALIZAR** (`:2274-2282`, la función completa):

```javascript
  function __cnPaintFocoStk(blk, ed, dd, sufijo) {
    if (!blk || !ed || !ed.focos || !dd || !dd.curva) return;
    ed.focos.forEach(function (f) {
      var day = blk.querySelector("#cn-foco-day-" + f.rank + sufijo);
      var mon = blk.querySelector("#cn-foco-mon-" + f.rank + sufijo);
      if (day) __cnDailyInto(f.producto, day, dd, ed.tarjetas);   // ed.tarjetas → línea de PPTO diario
      if (mon) __cnGapCampoInto(f.producto, mon, ed, dd, f);
    });
  }
```

**SUSTITUIR POR:**

```javascript
  // [2026-09-08 · PANEL-N1] +p50Dia: el compromiso P50 del panel, que viaja hasta la curva.
  // Opcional: los call sites que no lo pasen (el de :459, la repintada al restaurar el DOM)
  // reciben undefined y el gráfico se dibuja con sus 3 líneas de siempre.
  function __cnPaintFocoStk(blk, ed, dd, sufijo, p50Dia) {
    if (!blk || !ed || !ed.focos || !dd || !dd.curva) return;
    ed.focos.forEach(function (f) {
      var day = blk.querySelector("#cn-foco-day-" + f.rank + sufijo);
      var mon = blk.querySelector("#cn-foco-mon-" + f.rank + sufijo);
      if (day) __cnDailyInto(f.producto, day, dd, ed.tarjetas, p50Dia);   // ed.tarjetas → PPTO diario · p50Dia → compromiso
      if (mon) __cnGapCampoInto(f.producto, mon, ed, dd, f);
    });
  }
```

#### Cambio 11 de 11 — Los call sites pasan el P50 (y sobrevive al cambio de pestaña)

`__cnPaintFocoStk` tiene **tres** call sites (verificado: `:459`, `:4218`, `:4327`).

**(a)** ⚠️ La llamada `__cnPaintFocoStk(blk, edScoped, dd, sufijo);` aparece **DOS VECES**
(`:4218` y `:4327`). Se distinguen por la línea que va **justo debajo**: solo la de `:4327`
lleva `__cnCompProdMarcarDia`. **Ese es el ancla — el fragmento de DOS líneas, que sí es
único** (verificado). La de `:4218` no se toca (es el panel de Análisis, ver (d)).

**LOCALIZAR** (fragmento completo de dos líneas):

```javascript
        __cnPaintFocoStk(blk, edScoped, dd, sufijo);
        __cnCompProdMarcarDia(blk, datos.dia_marcado);
```

**SUSTITUIR POR:**

```javascript
        // [2026-09-08 · PANEL-N1] `datos.p50` lo emite el backend solo si el NIVEL tiene P50.
        __cnPaintFocoStk(blk, edScoped, dd, sufijo, (datos.p50 || {}).valor);
        __cnCompProdMarcarDia(blk, datos.dia_marcado);
```

**(b)** **LOCALIZAR** (`:459` — la repintada al restaurar el DOM tras cambiar de pestaña):

```javascript
            if (b.__cnAnzEd && b.__cnAnzDd) __cnPaintFocoStk(b, b.__cnAnzEd, b.__cnAnzDd, b.__cnAnzSufijo || "");
```

**SUSTITUIR POR:**

```javascript
            // [2026-09-08 · PANEL-N1] El P50 se guarda en el bloque junto a `ed`/`dd`: sin esto
            // la línea del compromiso desaparecía al salir de la pestaña y volver — el bloque se
            // repinta desde aquí, no desde __cnCompProdCargar.
            if (b.__cnAnzEd && b.__cnAnzDd) __cnPaintFocoStk(b, b.__cnAnzEd, b.__cnAnzDd, b.__cnAnzSufijo || "", b.__cnAnzP50);
```

**(c)** Para que (b) tenga el dato, hay que guardarlo en el bloque.

⚠️ **La línea a modificar aparece DOS VECES, idéntica** (`:4228` y `:4335`). Solo se toca la
de **`:4335`**, que es la de `__cnCompProdCargar`; la de `:4228` pertenece a
`__cnAnzCargarFoco` (panel de Análisis) y **no se toca**. Como el texto no es único, el
executor debe **posicionarse por número de línea**, no por búsqueda global.

**LOCALIZAR** — la ocurrencia de **`:4335`**, y solo esa:

```javascript
        blk.__cnAnzEd = edScoped; blk.__cnAnzDd = dd; blk.__cnAnzSufijo = sufijo;
```

**SUSTITUIR POR:**

```javascript
        blk.__cnAnzEd = edScoped; blk.__cnAnzDd = dd; blk.__cnAnzSufijo = sufijo;
        // [2026-09-08 · PANEL-N1] El P50 se guarda junto a ed/dd para que la repintada de :459
        // (al volver de otra pestaña) pueda volver a dibujar la línea del compromiso.
        blk.__cnAnzP50 = (datos.p50 || {}).valor;
```

> **(d)** El call site de `:4218` (`__cnAnzCargarFoco`, panel de Análisis) **no se toca**: no es
> de Cuantificar y no recibe `datos.p50`. Al no pasar el parámetro recibe `undefined` y
> conserva su comportamiento actual — esa es la razón de que `p50Dia` vaya al final de cada
> firma y sea opcional.

### 3.3 · La tarjeta KPI: proyección de cierre y referencia por nivel

`__cnTarjetasKpiHtml` (`:3663-3720`) **ya pinta** el anillo, la cifra, la fila de PPTO y la
proyección de cierre (`proyectado_cierre`, `meta_mes`, `brecha_abs`, `alcanza` —
`analisis/api.py:832-836`). **No se modifica en este plan.**

El único cambio de rótulo que exige la decisión 3 del usuario es el del anillo (REAL/PPTO vs
REAL/P50), y depende de `meta.p50`. **Queda FUERA de esta v1** (§7): se aborda cuando la línea
del gráfico esté validada en pruebas, para no mezclar dos cambios de significado en una sola
entrega.

### 3.4 · Cache-buster · 🔴 sin esto el panel «no pinta» con la consola limpia

Al cambiar `multitab_shell.js` hay que subir su `?v=`, o el navegador sirve la versión vieja.
Es un fallo conocido del proyecto y **no da ningún error visible**.

Ubicación verificada el 2026-09-08 (`grep` sobre `frontend\templates\`): el `<script>` **no**
está en `consulta.html`, sino en **`main.html:88`**.

**LOCALIZAR** en `C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\templates\main.html`:

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908c"></script>
```

**SUSTITUIR POR** (misma línea, la letra final avanza una posición):

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260908d"></script>
```

> ⚠️ Hay además un `<link rel="prefetch">` del mismo archivo en `login.html:43`, con una
> versión **distinta y más antigua** (`?v=20260903i`). Es solo una precarga y **no se toca**:
> cambiarla no afecta a qué versión se ejecuta, y tocarla sin necesidad añade ruido al diff.

### 3.5 · CREAR `backend\tests\test_panel_n1_enriquecido.py`

```python
"""N1 pasa al panel de dos columnas con curva diaria (2026-09-08 · PANEL-N1).

Sin BD ni LLM: se sustituyen el resolver, el ejecutor y `p50_referencia` por dobles, igual que
en test_cuantificar_panorama.py. Lo que se fija:
  · N1 emite `cuant_dia_panel` con las 6 claves del contrato y `dia_marcado` en None
  · el P50 solo viaja en los niveles que lo tienen, y YA CONVERTIDO de BPD a kbopd
  · los demás niveles (N2/N3/N1D) NO cambian de panel
"""
import pytest

from app.features.consulta_v2 import respuesta_cuantificar as _rc


def _res_n1(nivel_ent="campo", entidad="CASTILLA"):
    """El dict que devuelve el ejecutor para un N1, con lo mínimo que usa _panel_datos."""
    return {
        "aplica": True, "nivel": "N1",
        "entidad": {"nombre": entidad, "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": "el Campo " + entidad,
        "producto": "crudo", "unidad": "kbopd",
        "resultado": {"valor": 55.0}, "referencia_valor": 52.1,
        "cumplimiento_pct": 105.5, "estado": "Alineado",
        "referencia": "PPTO", "referencia_label": "presupuesto",
        "mes": {"anio": 2026, "mes": 4, "nombre": "abril", "dias_del_mes": 30,
                "dias_con_data": 30, "completo": True, "cerrado": True},
        "huella": {"registros": 30, "dias_del_mes": 30, "es_proyeccion": False},
        "avisos": [], "zoom": [],
    }


# --- el contrato del panel --------------------------------------------------------------

def test_n1_emite_el_panel_de_curva_diaria():
    d = _rc._panel_datos(_res_n1())
    for clave in ("entidad", "segmento", "periodo", "productos", "dia_marcado"):
        assert clave in d, f"falta la clave {clave!r} del contrato de cuant_dia_panel"
    assert d["dia_marcado"] is None       # mensual: no hay día que resaltar
    assert d["periodo"] == "Abril 2026"   # el mes de la PREGUNTA, no el del corte
    assert d["productos"] == ["CRUDO"]
    assert d["nivel"] == "N1"             # el nivel TEMPORAL no se pisa
    assert d["nivel_entidad"] == "campo"  # el de la entidad viaja en su propia clave


def test_n1_lleva_la_huella_que_antes_se_descartaba():
    d = _rc._panel_datos(_res_n1())
    assert d["dias_con_dato"] == 30 and d["dias_del_mes"] == 30
    assert d["es_proyeccion"] is False
    assert d["referencia_label"] == "presupuesto"


def test_los_demas_niveles_no_cambian():
    """N2 sigue siendo KPI acumulado: este plan solo toca N1."""
    res = _res_n1(); res["nivel"] = "N2"
    res.update({"periodo_label": "enero-agosto 2026", "meses_cerrados": 8,
                "serie_acum": [], "anio": 2026})
    d = _rc._panel_datos(res)
    assert "dia_marcado" not in d
    assert d["periodo_label"] == "enero-agosto 2026"


# --- el P50: escala y nivel (H-04, H-05) ------------------------------------------------

_SERIE_VP = {"vice": "VRO", "producto": "crudo", "unidad": "bpd", "fmt": "vp",
             "serie": [{"fecha": "2026-03-01", "p50": 54000.0, "real": 53000.0},
                       {"fecha": "2026-04-01", "p50": 55400.0, "real": 52300.0}]}


@pytest.fixture
def p50_vp(monkeypatch):
    monkeypatch.setattr(_rc._p50, "nivel_soportado", lambda n, r=None: n == "vicepresidencia")
    monkeypatch.setattr(_rc._p50, "serie_por_vp", lambda v, p="CRUDO": _SERIE_VP)


def test_p50_se_convierte_de_bpd_a_la_escala_del_panel(p50_vp):
    """🔴 H-04: la hoja P50 está en BPD y el panel dibuja en kbopd. Sin el ÷1000 la línea sale
    mil veces fuera de escala — el bug dd8ffa2, invisible en crudo."""
    res = _res_n1(nivel_ent="vicepresidencia", entidad="VRO")
    p50 = _rc._p50_del_mes({"nivel": "vicepresidencia", "valor": "VRO"}, res)
    assert p50 is not None
    assert p50["valor"] == pytest.approx(55.4)     # 55.400 bpd -> 55,4 kbopd
    assert p50["valor"] < 100                      # jamás en el orden de 10⁴


def test_p50_toma_el_mes_de_la_pregunta_no_el_ultimo(p50_vp):
    """H-06: la serie trae 12 meses. Abril debe compararse contra el P50 de ABRIL."""
    res = _res_n1(nivel_ent="vicepresidencia", entidad="VRO")
    res["mes"] = {"anio": 2026, "mes": 3, "nombre": "marzo", "dias_del_mes": 31,
                  "dias_con_data": 31, "completo": True, "cerrado": True}
    p50 = _rc._p50_del_mes({"nivel": "vicepresidencia", "valor": "VRO"}, res)
    assert p50["valor"] == pytest.approx(54.0)     # el de marzo, no el de abril


def test_un_campo_no_tiene_p50(p50_vp):
    """🔴 H-05: el P50 NO se define por campo. Inventarlo sería el fallo silencioso que el
    proyecto persigue: una cifra creíble comparada contra un compromiso que no existe."""
    res = _res_n1(nivel_ent="campo", entidad="CASTILLA")
    assert _rc._p50_del_mes({"nivel": "campo", "valor": "CASTILLA"}, res) is None


def test_sin_p50_el_panel_sale_igual_sin_la_clave(p50_vp):
    """Best-effort: sin P50 el panel se pinta con sus 3 líneas de siempre."""
    res = _res_n1(nivel_ent="campo")
    res["p50"] = None
    d = _rc._panel_datos(res)
    assert d["p50"] is None
```

---

## §4 · Orden de ejecución

Secuencial. Si un paso falla, **DETENERSE** y reportar.

| # | Paso | Detalle |
|---|---|---|
| 1 | Situarse | `cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'` |
| 2 | Árbol limpio en AMBOS repos | `git status --short` en `backend\` y en `frontend\` |
| 3 | **Línea base de tests** | `uv run pytest tests\ -q` → **anotar** la cifra de passed/failed ANTES de tocar nada |
| 4 | Backend · Cambio 1 (import) | §3.1 |
| 5 | Backend · Cambio 2 (helper `_p50_del_mes`) | §3.1 — va antes de su call site |
| 6 | Backend · Cambio 3 (`_panel_datos`) | §3.1 |
| 7 | Backend · Cambio 4 (`responder`) | §3.1 |
| 8 | Backend · crear los tests | §3.5 |
| 9 | **Validación backend** | §6.1, V-1 → V-4. **No seguir al frontend si algo falla** |
| 10 | Frontend · Cambio 6 (firma de `__cnDailyPlot`) | §3.2 — el dibujo primero |
| 11 | Frontend · Cambio 8 (`p50Plot` + eje) | §3.2 |
| 12 | Frontend · Cambio 7 (la 4ª línea) | §3.2 |
| 13 | Frontend · Cambio 9 (`__cnDailyInto`) | §3.2 |
| 14 | Frontend · Cambio 10 (`__cnPaintFocoStk`) | §3.2 |
| 15 | Frontend · Cambio 11 (los call sites) | §3.2 — (a), (b), (c) |
| 16 | Frontend · Cambio 5 (tarjeta KPI en N1) | §3.2 |
| 17 | Frontend · cache-buster | §3.4 |
| 18 | **Validación frontend** | §6.1, V-5 → V-8 |

> 🔑 **El orden 10 → 15 recorre la cadena DE ABAJO ARRIBA** (quien dibuja primero, quien pasa
> el dato después). No es una preferencia: aplicado al revés, el archivo queda en un estado
> donde una función pasa un argumento que la de abajo todavía no acepta. Dentro del bloque del
> dibujo, el 11 va antes del 12 porque `p50Plot` se usa en la 4ª línea.

---

## §5 · Reglas no negociables

1. **CERO modificaciones** fuera de los 4 archivos de la §0.
2. **DOS commits, uno por repo.** `ProdIABack` y `ProdIAWebFront` son repos distintos; la
   carpeta `Repo ProdIA` **no** es un repo git. Nunca mezclar.
3. **JS en ES5**: `var` + `function`. Sin arrow functions, sin template literals, sin
   `const`/`let`.
4. **El ÷1000 del P50 se hace UNA vez, en el backend.** El frontend recibe la cifra ya en la
   escala del panel y **no** vuelve a escalarla (H-04).
5. **La decisión de si hay P50 la toma `p50_referencia.nivel_soportado()`.** Prohibido
   escribir una comprobación de nivel propia (H-08).
6. **No tocar** `respuesta_jerarquizar.py`, `p50_referencia.py`, `analisis/api.py`,
   `colapsable.css`, ni la lógica de blancos/gas de `:2330-2336`.
7. **Si algo no calza con el código real, DETENERSE y reportar.** Las 9 anclas de la §3 se
   verificaron una a una contra los archivos el 2026-09-08 y todas son **únicas**. Si alguna no
   aparece o aparece dos veces, el archivo cambió desde entonces: parar, no adaptar a ojo.
8. Código y comentarios **en español**, con la marca `[2026-09-08 · PANEL-N1]`.
9. Copiar los bloques de la §3 **literalmente**, incluidos los comentarios.
10. **No hacer commit.** Al terminar, reportar archivos tocados y preguntar «¿Hago commit?».

---

## §6 · Validación

### 6.1 · Estática (la ejecuta el EXECUTOR)

Backend, desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`; frontend desde
`C:\APLICACIONES\ProdIA\Repo ProdIA\frontend`. Línea por línea, PowerShell normal.

| # | Comando | Resultado esperado |
|---|---|---|
| V-1 | `uv run python -c "import app.features.consulta_v2.respuesta_cuantificar"` | Sin salida |
| V-2 | `uv run pytest tests\test_panel_n1_enriquecido.py -q` | **8 passed** |
| V-3 | `uv run pytest tests\test_cuantificar_dia.py tests\test_cuantificar_panorama.py -q` | Igual que la línea base del paso 3 |
| V-4 | `uv run pytest tests\ -q` | Misma cifra que la línea base del paso 3 |
| V-5 | `Select-String -Path static\js\multitab_shell.js -Pattern 'p50Dia' -CaseSensitive` | **≥7 líneas**: 3 firmas + 1 uso en `__cnDailyInto` + 2 en el bloque de la línea + 1 en `p50Plot` |
| V-6 | `Select-String -Path static\js\multitab_shell.js -Pattern 'p50Plot' -CaseSensitive` | **3 líneas**: declaración + `refs` del eje + guard de la línea |
| V-7 | `Select-String -Path static\js\multitab_shell.js -Pattern '__cnPaintFocoStk' -CaseSensitive` | **4 líneas**: 1 definición + 3 call sites. Si sale otra cifra, se añadió o perdió un call site |
| V-8 | `node --check static\js\multitab_shell.js` | Sin salida (sintaxis válida). **Si no hay `node`, es OBLIGATORIO anotarlo en el reporte**: sin este check, un error de sintaxis deja el shell entero en blanco y no lo detecta ninguna otra validación |

⚠️ **Sobre V-4:** el repo tiene fallos **preexistentes** por datos que la BD local (congelada
en 2026-05-18) no tiene. Un fallo ahí no es necesariamente una regresión. Para distinguirlo:
`git stash`, volver a correr, comparar, `git stash pop` — desde
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend`, **no** desde `Repo ProdIA`.

### 6.2 · Humana (la ejecuta el USUARIO, en el servidor de pruebas)

⚠️ **R3 · El executor NO puede marcar esto como verificado.** No tiene navegador ni datos
reales, y la app real corre en pruebas, no en local. El estado correcto al terminar la §6.1 es
**«implementado, PENDIENTE de validación humana»**.

En `C:\APLICACIONES\ProdIA\Repo ProdIA\backend` y en `...\frontend`:

```powershell
git pull origin main
```

Luego **reiniciar los DOS procesos** (`iniciar_backend.bat` e `iniciar_frontend.bat`) y en el
navegador **Ctrl+F5** (se tocó JS).

| # | Prueba | Resultado esperado |
|---|---|---|
| H-1 | «¿Cuánto produjo Castilla en abril?» | Panel de **dos columnas**: tarjeta KPI izquierda + curva diaria derecha |
| H-2 | La curva de H-1 | Es de **abril**, no del mes del corte |
| H-3 | Las líneas de H-1 | **Tres**: promedio 2026, media del mes, PPTO. **Sin** línea de P50 (es un campo) |
| H-4 | El anillo de H-1 | Rotula **REAL / PPTO** |
| H-5 | «¿Cuánto produjo la VRO en abril?» | **Cuatro** líneas: las tres + **compromiso P50** en rojo |
| H-6 | La cifra del P50 en H-5 | Del orden de **decenas o centenas** (kbopd). Si sale en decenas de miles, el ÷1000 no se aplicó → **detener** |
| H-7 | «¿Cuánto produjo Cupiagua en abril?» (gas) | La curva se pinta o se omite **igual que hoy** — sin líneas nuevas raras (H-10) |
| H-8 | **Tiempo de respuesta** de H-1 | Comparable al de una pregunta por día. Si se degrada de forma notoria, reportarlo (H-09) |
| H-9 | Preguntar de nuevo lo mismo | La segunda vez debe ser **más rápida** (caché de navegador) |
| H-10 | Tras H-5, **irse a otra pestaña y volver** a Consulta | El panel se repinta **con sus cuatro líneas**, P50 incluido (C-4: la repintada de `:459` es otro camino) |
| H-11 | Tras H-1, mirar el panel del **Análisis** («Desempeño del mes» en el riel) | Igual que hoy, sin líneas nuevas — no debe contagiarse (C-4d) |
| H-12 | F12 → Console | **0 errores** |

H-3 y H-5 son la pareja crítica: la **misma** pregunta a distinto nivel debe traer distinto
número de líneas. H-6 es el que atrapa el bug de escala, y es el más importante de todos —
en crudo un error de mil pasa desapercibido si no se mira la cifra.

---

## §7 · Fuera de alcance

- **El rótulo del anillo REAL/P50 en la tarjeta KPI.** Se aborda cuando la línea del gráfico
  esté validada en pruebas (§3.3). Esta v1 deja el anillo como está hoy.
- **El desglose «Dentro de CASTILLA»** (los hijos del `zoom`). Propuesto en el modelo, pero es
  un bloque nuevo de UI: entrega aparte.
- **La curva del acumulado (N2) que no se pinta.** El backend emite `serie_acum` y el panel
  `cuant_acum` está construido para dibujarla sin fetch, pero en la captura del usuario no
  aparece. **Es un diagnóstico pendiente, no parte de este plan.**
- **La brecha de jerarquías** (`jerarquias_sup_error.md`) y **el vocabulario de distribución**
  (`vocabulario_distribucion_error.md`). Siguen abiertas; este plan las esquiva delegando en
  `nivel_soportado()`.
- **La hoja `POP Filiales`** de `core.fact_tabla_hoja`.
- Cualquier cambio en el clasificador, el drill, los goldens, la BD o el ETL.
