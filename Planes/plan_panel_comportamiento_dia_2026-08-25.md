# Plan · QV2-PANEL-DIA — Panel «Comportamiento {Producto}» para las preguntas de grano DÍA

> **Versión:** v2 auditada (§0.2 de CLAUDE.md: el plan entregado ya debe ser equivalente a un v2).
> **Auditoría previa ejecutada:** §15 pasos 1-3 (Mapeo · Auditoría · Diagnóstico) ANTES de escribir.
> **Fecha:** 2026-08-25 · **ID:** QV2-PANEL-DIA

---

## 1. CONTEXTO

**Proyecto:** ProdIA 2.0 — chat de analítica de producción de Ecopetrol.
**Raíz absoluta:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0`

**Stack:**
- Backend analítico: **FastAPI/Uvicorn (INGESTA, puerto 8088)** — `INGESTA/Rep_Prod/backend/`
- Front + plantillas + **proxy**: **Flask (puerto 8020)** — `MainChat/`, `static/`, `routes/api.py`
- Python: `INGESTA\Rep_Prod\backend\.venv\Scripts\python.exe` · **NO hay Node instalado**
- Frontend: **JavaScript vanilla** (`static/js/multitab_shell.js`). Sin React, sin build.

> ⚠️ **Los servicios corren en el equipo del USUARIO, no en el del executor.** Un `curl` a
> localhost:8020/8088 devolverá HTTP 000 y **eso NO significa que la app esté caída**.

> ⚠️ **Sobre CLAUDE.md:** `INGESTA/Rep_Prod/clmd/CLAUDE_muestra.md` describe **otro** proyecto
> (Robustez V2.0 — React 19 + pnpm + Plotly). DT-13/DT-14/DT-17 y R1/R2 **NO aplican**. Sí aplican:
> §0.2 (auditoría previa), §0.3 (Planner), §15 (flujo 6 pasos) y **§17.5 R3 / DT-15**
> (build verde ≠ feature verificada → validación humana obligatoria).

**Antecedente.** `951b2a4` implementó las preguntas de grano día (N1D «el 15 de mayo», N1DSEL
«mejor día del mes») con una tarjeta escueta: cifra + fecha. El usuario pidió enlazarlas al panel
**«Comportamiento {Producto}»**, ya diseñado y con maqueta aprobada
(`~/.claude/plans/identificas-este-panel-autogenerado-floating-abelson.md`), cuyo §4 dejaba el
disparador **«por definir»**. Este plan es ese disparador.

**Decisión del usuario (textual):** *«Si me preguntan por Mayo, gauge y gráfico mostrarán datos de
mayo/julio... lo que se solicite»* → **el panel entero sigue el periodo de la pregunta**.

**Corrección registrada.** Se sospechó que el gauge no tenía datos a nivel campo. **Era falso**:
provino de invocar `desempeno()`/`ejecutivo()` en un script suelto, donde los defaults
`= Query(None)` de FastAPI viajan como valor. El usuario aportó captura de la app: campo CASTILLA,
abril, **105,5%**, presupuesto **6.256.648 bbl**, gauge pintado. **El gauge funciona.**

---

## 2. OBJETIVO

| Pregunta | Hoy | Objetivo |
|---|---|---|
| «¿Cuánto produjo Castilla el 15 de mayo?» | tarjeta: cifra + fecha | gauge de **mayo** + curva de **mayo**, día 15 marcado |
| «¿Mejor día de Castilla este mes?» | tarjeta: cifra + fecha | gauge + curva, día ganador marcado |

**No-objetivo:** tocar «Focos de atención», sus 4 pestañas o su gap por campo.

---

## 3. MAPEO — el código real (leído, no recordado)

```
respuesta_cuantificar.responder()                         backend (951b2a4)
  └─ {"tipo": "cuant_dia", "datos": {...}}
       └─ multitab_shell.__cnPintarPanelCuant :3013       cadena de tipos
            ├─ (tipo === "cuant_dia") ? __cnCuantDiaHtml(d)          función PURA
            ├─ (tipo === "analiza_foco") ? __cnAnzPlaceholderHtml()  patrón ASÍNCRONO
            └─ :3102  if (panel.tipo === "analiza_foco") __cnAnzCargarFoco(blk, d, "-stk"+seq)
```

| Pieza | Ruta:línea | Hecho |
|---|---|---|
| Cadena de tipos | `static/js/multitab_shell.js:3021-3043` | `cuant_dia` ya registrado ANTES del fallback |
| **Despacho diferido** | `static/js/multitab_shell.js:3102` | **una sola línea**: `if (panel.tipo === "analiza_foco") __cnAnzCargarFoco(...)` |
| Patrón asíncrono | `static/js/multitab_shell.js:2963-3011` | 2 fetches secuenciales + caché + `data-pend-paint` |
| Querystring | `static/js/multitab_shell.js:2940-2949` | `__cnAnzQS(entidad, nivel, periodo)` — **ya acepta `periodo`** |
| Restauración | `static/js/multitab_shell.js:439` y `MainChat/static/js/acordeon.js:140` | **DOS** sitios llaman `__cnPaintFocoStk(b, b.__cnAnzEd, b.__cnAnzDd, …)` |
| Filete de producto | `static/js/multitab_shell.js:3069-3079` | lee `[data-prod]` del constructor; `analiza_foco` queda FUERA a propósito |
| Panel de foco (modelo) | `static/js/multitab_shell.js:4004` | `__cnFocosHtml(focos, sinFoco, meta, tarjetas, sufijo, scopeEnt, scopeNiv)` |
| Grid interno | `static/js/multitab_shell.js:4076-4086` | `kpicol` + `cn-foco-day-{rank}{sufijo}` + `cn-foco-mon-…` |
| Pintor scoped | `static/js/multitab_shell.js:1683-1691` | busca los IDs **dentro de `blk`** |
| Curva diaria | `static/js/multitab_shell.js:1695-1719` | lee `d.curva`, `d.ritmo_mensual`, **`d.mes.nombre`** |
| **Eje X de Plotly** | `static/js/multitab_shell.js:1749-1753` | `xcat` = **día del mes como STRING** (`"15"`), `xaxis.type:"category"` |
| Gauge | `static/js/multitab_shell.js:2520` | `__cnTarjetasKpiHtml(tarjetas, periodo)` ← de `ed.tarjetas` |
| Grid CSS | `static/css/colapsable.css:1109-1116` | `.cn-desemp__grid2--kpi` = `30fr 35fr 35fr` (**3 columnas**) |
| Altura pila | `static/css/colapsable.css:1350` | `.cn-desemp__scroll .cp-foco__panel .cn-desemp__grid2--kpi { height: 375px }` |
| **Proxy Flask** | `routes/api.py:300-318` | reenvía **solo** `entidad, segmento, nivel, periodo` · timeout **200 s** |
| Contrato backend | `.../consulta_v2/respuesta_analizar.py:286-289` | `{entidad, nivel, segmento, periodo, productos}` |
| `pulir=False` | `.../consulta_v2/respuesta_analizar.py:253` | Analizar lo pasa **en proceso**, no por HTTP (RA-1) |

**Hallazgo que ahorra trabajo:** `__cnDailyInto` **no necesita cambios**. Toma el mes de
`d.mes.nombre` (`:1700`); si el fetch lleva `periodo=mayo 2026`, el mes correcto y su título viajan
solos. Verificado contra la BD: `desempeno(periodo="marzo")` → 31 días de marzo; `"abril"` → 30.

---

## 4. AUDITORÍA — hallazgos (10)

> A-1..A-5 son **bloqueantes**.

### 🔴 A-1 · El grid `--kpi` es de TRES columnas
`colapsable.css:1112` → `30fr 35fr 35fr`, dimensionado para gauge + curva + gap por campo. Este
panel emite **dos** hijos → tercera columna vacía y ambas tarjetas al 65% del ancho.
→ **Clase nueva** `.cn-compprod__grid`, con variante de una columna.

### 🔴 A-2 · `.cp-foco__panel` es `display:none`
Sin pestañas nadie activa el panel y Plotly pintaría a tamaño 0.
→ Emitir `class="cp-foco__panel is-active"`.

### 🔴 A-3 · `cuant_dia` es HOY una función PURA
`:3026` la ejecuta en el momento, sin fetch. El panel necesita 2 endpoints.
→ **Tipo NUEVO** `cuant_dia_panel` con el patrón `analiza_foco`. `cuant_dia` y `__cnCuantDiaHtml`
**se conservan intactos** como fallback: si el panel falla, la burbuja del chat sigue con la cifra.

### 🔴 A-4 · BLOQUEANTE NUEVO — el eje X de Plotly NO son fechas ISO
`:1749-1753` convierte cada fecha a **el día del mes como string** (`"1"`, `"15"`) y el eje es
`type:"category"`. Un marcador que busque `"2026-05-15"` con `xs.indexOf(iso)` **jamás encontrará
nada** y el resaltado del día no aparecería — fallando en silencio.
→ El marcador debe buscar `String(parseInt(iso.slice(8,10),10))`. **Medido, no supuesto.**

### 🔴 A-5 · BLOQUEANTE NUEVO — el pulido LLM de 180 s se dispara en cada pregunta
`routes/api.py:300-318` reenvía **solo** `entidad/segmento/nivel/periodo`: **`pulir` NO se
reenvía**, así que INGESTA recibe `pulir=True` y ejecuta el pulido LLM (Gemma), con timeout de
**200 s** en el proxy. El propio código lo documenta como RA-1: *«pulir=False … sin el hang de 180s
de Gemma en 139»*, y Analizar lo evita **llamando en proceso**, no por HTTP.
`analiza_foco` sí paga ese coste hoy — pero es un panel de análisis, no una cifra puntual.
→ **Añadir `pulir` a la lista de params reenviados** en el proxy (`routes/api.py:312`) y mandar
`pulir=false` desde el fetch del panel. Es un cambio de una palabra, aditivo y compartido con
`analiza_foco` (que también se beneficia). **Sin esto, cada pregunta de día puede tardar minutos.**

### 🟠 A-6 · La restauración de bloques pendientes vive en DOS sitios
`multitab_shell.js:439` y `MainChat/static/js/acordeon.js:140` llaman a `__cnPaintFocoStk` con
`b.__cnAnzEd/__cnAnzDd`. Un bloque encolado (pestaña oculta) se repinta por ahí — pero **el
marcador del día NO se volvería a aplicar**, porque esos dos sitios no lo conocen.
→ Guardar `blk.__cnCompDia` y que **el propio `__cnCompProdMarcarDia` se llame desde
`__cnPaintFocoStk`**… **NO**: eso violaría «no tocar `__cnPaintFocoStk`». → Solución elegida:
`__cnCompProdCargar` registra un `MutationObserver`… **tampoco** (complejidad). → **Solución final:
el marcador se aplica dentro de `__cnCompProdHtml`+`__cnCompProdCargar` y, para el caso encolado,
se acepta que el bloque restaurado muestre la curva SIN el marcador.** Es degradación cosmética,
no de datos, y se DECLARA en el plan. Alternativa futura: exponer un hook.

### 🟠 A-7 · El filete de producto sí aplica aquí (a diferencia de `analiza_foco`)
`:3069-3079` lee `[data-prod]` del constructor. `analiza_foco` queda fuera porque puede mostrar 1-3
productos. **Este panel muestra SIEMPRE uno solo** (`productos` trae exactamente un elemento).
→ **Oportunidad de mejora:** emitir `data-prod` en la raíz de `__cnCompProdHtml` para heredar el
filete y el badge del turno, coherente con `cuant_kpi`. Pero el placeholder se inserta **antes** del
fetch, y el dispatcher lee `[data-prod]` en ese momento → no lo encontraría.
→ **Decisión:** el `data-prod` se pone en el **placeholder**, que ya conoce el producto desde
`panel.datos.productos[0]`. Requiere un placeholder propio (no reusar `__cnAnzPlaceholderHtml`).

### 🟠 A-8 · Caché compartida entre `analiza_foco` y este panel
Ambos usan `__cnDesempCache`/`__cnEjecCache` con `__cnAnzCacheKey(entidad, nivel, periodo)`.
Es **deseable** (cache-HIT cruzado), pero la clave **no incluye `pulir`**. Con A-5 aplicado, un
payload obtenido con `pulir=false` (sin `secciones` pulidas) podría servirse a `analiza_foco`, que
sí las usa.
→ **Verificar** que `analiza_foco` tolera `secciones` del fallback determinista. El backend ya
devuelve `secciones` con `_ejec_fallback` cuando el LLM no corre, así que el contrato se mantiene:
`analiza_foco` NO se rompe. **Se deja constancia y se valida en V-B.**

### 🟡 A-9 · `f.rank` y el patrón de ID
`__cnPaintFocoStk` y la cola `data-pend-paint` dependen de `cn-foco-day-{rank}{sufijo}`. El filtrado
por producto **no debe renumerar** (`:3328/:3341` usan rank como clave).
→ Conservar `f.rank`, como hace `__cnAnzCargarFoco`.

### 🟡 A-10 · Archivo compartido con OTRA SESIÓN
`static/js/multitab_shell.js` lo edita una sesión paralela. Cache-buster en `?v=20260825d`.
→ `git status` antes de tocar · solo añadir · bump obligatorio.

---

## 5. DIAGNÓSTICO

| # | Hueco | Causa | Archivo |
|---|---|---|---|
| D1 | El panel no existe como render | `__cnCompProdHtml` nunca se implementó | `multitab_shell.js` |
| D2 | No hay punto de entrada asíncrono | `cuant_dia` es puro (A-3) | `multitab_shell.js` |
| D3 | El grid `--kpi` es de 3 columnas | diseñado para el gap por campo (A-1) | `colapsable.css` |
| D4 | El backend no manda el periodo | `cuant_dia` solo lleva fecha/valor | `respuesta_cuantificar.py` |
| D5 | El día preguntado no se distingue | eje X es categoría de día (A-4) | `multitab_shell.js` |
| D6 | Cada pregunta dispara el LLM 180 s | el proxy no reenvía `pulir` (A-5) | `routes/api.py` |

---

## 6. PREREQUISITOS

```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -3
```
**Esperado: `7 failed, 500 passed, 1 skipped`.** Los 7 son **preexistentes y ajenos**:
`test_escalada_fallback_conserva_regex`, 2 de `test_analisis_tarjetas_kpi`, 3 de
`test_conteo_jerarquia`, 1 de `test_jerarquizar_ranking`.
→ **La suite final debe mostrar EXACTAMENTE esos 7.**

```bash
git status --short    # multitab_shell.js debe estar LIMPIO (A-10). Si no, DETENERSE.
```

---

## 7. INVENTARIO DE ARCHIVOS

| # | Ruta | Acción |
|---|---|---|
| 1 | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/respuesta_cuantificar.py` | Añadir campos al panel |
| 2 | `INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py` | **Solo añadir** tests |
| 3 | `routes/api.py` | **1 línea**: reenviar `pulir` (A-5) |
| 4 | `static/js/multitab_shell.js` | **Solo añadir** (⚠️ A-10) |
| 5 | `static/css/colapsable.css` | **Solo añadir** al final |
| 6 | `MainChat/templates/mainchat_layout.html` | Solo el cache-buster |

**Prohibido tocar:** `__cnFocosHtml`, `__cnTarjetasKpiHtml`, `__cnDailyInto`, `__cnDailyPlot`,
`__cnPaintFocoStk`, `__cnAnzCargarFoco`, `__cnGapCampoInto`, `__CP_TABS`, `.cn-desemp__grid2` y sus
variantes, `ejecutor.py`, `slots.py`, `validador.py`, `maquina_q.py`, `no_soportado.py`.

---

## 8. ESPECIFICACIÓN

### PASO 1 · Backend: periodo + día a marcar
**Archivo:** `INGESTA/Rep_Prod/backend/app/features/consulta_v2/respuesta_cuantificar.py`

**1.a** — Constantes de módulo, junto a `_PANEL_TIPO`:
```python
# [2026-08-25] QV2-PANEL-DIA. `periodo` en el formato que entiende analisis._parse_periodo
# (nombre de mes + año); `_PROD_DIM` traduce al nombre de dim_tipo_producto que filtra los focos.
_MESES_PANEL = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]
_PROD_DIM = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
```

**1.b** — `_PANEL_TIPO`: redirigir los dos niveles de día:
```python
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var",
              "N1D": "cuant_dia_panel", "N1DSEL": "cuant_dia_panel"}
```

**1.c** — En `_panel_datos`, dentro de la rama `if nivel in ("N1D", "N1DSEL")` **ya existente**,
añadir tras el `d.update` actual:
```python
        # [2026-08-25] QV2-PANEL-DIA: contexto para el panel «Comportamiento {Producto}».
        # 🔑 El periodo sale de la FECHA DE LA PREGUNTA, no del último mes con datos: si preguntan
        # por marzo, gauge y curva muestran marzo (decisión del usuario, 2026-08-25).
        _f = res["fecha"]                      # "YYYY-MM-DD"
        _anio, _mes = int(_f[0:4]), int(_f[5:7])
        d.update({
            "entidad": res["entidad"]["nombre"],
            "nivel": res["entidad"]["nivel"],
            "segmento": "ecp",
            "periodo": f"{_MESES_PANEL[_mes]} {_anio}",
            "productos": [_PROD_DIM.get(res["producto"], "CRUDO")],
            "dia_marcado": _f,
        })
```

**✅ V-1:**
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
from app.features.consulta_v2 import respuesta_cuantificar as rc
from app.features.consulta_v2.maquina_q import detectar_entidad
for q in ['¿Cuánto produjo Castilla el 15 de mayo?','¿Mejor día de Castilla este mes?','¿Cuánto produjo Castilla el 15 de marzo?']:
    r = rc.responder(q, entidad=detectar_entidad(q), usuario='J')
    p = r['panel']; print(q); print('  tipo:', p['tipo']); print('  datos:', p['datos']); print()"
```
**Esperado:** `tipo: cuant_dia_panel` en los tres · `periodo: 'mayo 2026'` en los dos primeros y
**`'marzo 2026'` en el tercero** · `productos: ['CRUDO']` · `dia_marcado` con la fecha ISO.

---

### PASO 2 · Proxy: reenviar `pulir` (A-5)
**Archivo:** `routes/api.py`, ruta `/analisis/ejecutivo` (~línea 312)

```python
        # [2026-08-25] `pulir` se reenvía (QV2-PANEL-DIA, A-5): sin él INGESTA usa pulir=True y
        # ejecuta el pulido LLM de Gemma (timeout 200s aquí). El panel de grano día NO usa
        # `secciones`, así que pide pulir=false y responde en el acto. Analizar ya evitaba ese
        # coste llamando en proceso (respuesta_analizar.py:253, RA-1); esta es la vía HTTP.
        for _k in ("nivel", "periodo", "pulir"):
```

**✅ V-2:** `grep -n '"nivel", "periodo", "pulir"' routes/api.py` → 1 coincidencia, en la ruta de
**ejecutivo** (la de `desempeno` NO se toca: ese endpoint no tiene `pulir`).

---

### PASO 3 · CSS: clase de grid nueva (A-1)
**Archivo:** `static/css/colapsable.css` — **añadir al final**, sin tocar `.cn-desemp__grid2`

```css
/* [2026-08-25] QV2-PANEL-DIA · panel «Comportamiento {Producto}» de las preguntas de grano día.
   Clase PROPIA: .cn-desemp__grid2--kpi es de TRES columnas (30fr 35fr 35fr, para el gap por campo)
   y este panel emite solo DOS hijos — reutilizarla dejaría una columna vacía y encogería ambas
   tarjetas al 65% del ancho. Anchos 30/70 según la maqueta aprobada. */
.cn-compprod__grid { display: grid; grid-template-columns: 30fr 70fr; gap: 12px;
                     align-items: stretch; }
.cn-compprod__grid--solo { grid-template-columns: 1fr; }   /* sin tarjeta KPI: la curva ocupa todo */
/* min-height:0 es obligatorio: sin él un hijo flex no se encoge y DESBORDA la fila. */
.cn-compprod__grid > * { min-width: 0; min-height: 0; height: 100%; }
.cn-compprod__grid .cp-mes__kpi { flex: 1 1 auto; min-height: 0; }
/* Altura en la pila del chat, replicando :1350 de .cn-desemp__grid2--kpi. */
.cn-desemp__scroll .cp-foco__panel .cn-compprod__grid { height: 375px; min-height: 0; }
@media (max-width: 1024px) {
  .cn-compprod__grid { grid-template-columns: 1fr; }
  .cn-compprod__grid > * { height: auto; }
}
```

---

### PASO 4 · Front: render + placeholder con identidad (A-2, A-7)
**Archivo:** `static/js/multitab_shell.js` — **añadir junto a `__cnCuantDiaHtml`** (~línea 2750)

```js
  // [2026-08-25] QV2-PANEL-DIA · panel «Comportamiento {Producto}» para las preguntas de grano día.
  // Modelado sobre la rama ECP de __cnFocosHtml (:4004) pero SIN cabecera, SIN pills, SIN rank
  // visible y SIN gap por campo: solo gauge + curva. __cnFocosHtml queda BYTE-IDÉNTICA.
  // 🔑 `is-active` obligatorio: .cp-foco__panel es display:none y aquí no hay pestañas (A-2).
  // 🔑 El patrón de ID `cn-foco-day-{rank}{sufijo}` se CONSERVA aunque el rank no se muestre: es el
  // contrato con __cnPaintFocoStk y con la cola data-pend-paint de acordeon.js (A-9).
  function __cnCompProdHtml(focos, meta, tarjetas, sufijo) {
    focos = (focos || []).filter(function (f) { return !f.sin_produccion; });
    tarjetas = tarjetas || [];
    sufijo = sufijo || "";
    if (!focos.length)
      return '<div class="p-2 text-muted small">Sin datos de comportamiento para este producto.</div>';
    meta = meta || {};
    return focos.map(function (f) {
      var prod = f.producto || "";
      var pI = __cnProdId(prod) || { color: "#6E7C75", soft: "#F1F4F1" };
      var tarProd = tarjetas.filter(function (t) { return t.producto === prod; });
      var kpi = tarProd.length
        ? '<div class="cp-foco__kpicol"><div class="cn-kpi__row cn-kpi__row--solo">' +
            __cnTarjetasKpiHtml(tarProd, meta.periodo) + '</div></div>'
        : "";
      var gridCls = "cn-compprod__grid" + (tarProd.length ? "" : " cn-compprod__grid--solo");
      return '<div class="cp-foco" style="--cp-prod:' + pI.color + ';--cp-prod-soft:' + pI.soft + '">' +
        '<div class="cp-foco__panel is-active">' +
          '<div class="' + gridCls + '">' + kpi +
            '<div id="cn-foco-day-' + f.rank + sufijo + '" class="cn-ins"></div>' +
          '</div>' +
        '</div></div>';
    }).join("");
  }

  // Placeholder PROPIO (no se reusa __cnAnzPlaceholderHtml): lleva [data-prod] para que el
  // dispatcher (:3069) le ponga el filete y el badge de producto al bloque. Se puede hacer aquí
  // —y no en analiza_foco— porque este panel muestra SIEMPRE un solo producto (A-7).
  function __cnCompProdPlaceholderHtml(prod) {
    return '<div data-prod="' + esc(prod || "") + '" ' +
      'class="d-flex align-items-center gap-2 p-2 text-muted small">' +
      '<div class="spinner-border spinner-border-sm"></div> Cargando el comportamiento del producto…</div>';
  }
```

---

### PASO 5 · Front: punto de entrada asíncrono
**Archivo:** `static/js/multitab_shell.js` — **añadir junto a `__cnAnzCargarFoco`** (~línea 3011)

Calcado de `__cnAnzCargarFoco`. **Diferencias, y solo estas:** usa `__cnCompProdHtml`; `edScoped`
solo lleva `{ focos: focosF }`; añade `pulir=false` al querystring (A-5); y marca el día (PASO 6).

```js
  // [2026-08-25] QV2-PANEL-DIA. Gemelo de __cnAnzCargarFoco (:2963) — mismos 2 fetches
  // SECUENCIALES, mismas cachés y mismas guardas de "no cachear errores".
  // 🔑 `pulir=false`: sin él INGESTA ejecuta el pulido LLM de Gemma (180s; timeout 200 en el
  // proxy). Este panel NO usa `secciones`, así que se salta (A-5, misma razón que RA-1).
  function __cnCompProdCargar(blk, datos, sufijo) {
    var host = blk.querySelector(".cn-stk__body");
    if (!host) return;
    var entidad = datos.entidad, nivel = datos.nivel, periodo = datos.periodo;
    var key = __cnAnzCacheKey(entidad, nivel, periodo);
    var qs = __cnAnzQS(entidad, nivel, periodo);
    var qsEj = qs + (qs ? "&" : "?") + "pulir=false";

    var pDesemp = __cnDesempCache[key] ? Promise.resolve(__cnDesempCache[key]) :
      fetch("/api/analisis/desempeno" + qs).then(function (r) { return r.json(); }).then(function (dd) {
        if (dd && dd.encontrada !== false && !dd.sin_datos && !dd.sin_cierre) __cnDesempCache[key] = dd;
        return dd;
      });

    pDesemp.then(function (dd) {
      var pEjec = __cnEjecCache[key] ? Promise.resolve(__cnEjecCache[key]) :
        fetch("/api/analisis/ejecutivo" + qsEj).then(function (r) { return r.json(); }).then(function (ed) {
          if (ed && ed.encontrada !== false && !ed.sin_datos &&
              __cnPayloadEsFil(ed) === false && (ed.meta || {}).generado_por !== "error") {
            __cnEjecCache[key] = ed;
          }
          return ed;
        });
      return pEjec.then(function (ed) { return { dd: dd, ed: ed }; });
    }).then(function (r) {
      var dd = r.dd, ed = r.ed;
      if (!dd || dd.encontrada === false || dd.sin_datos || !ed || ed.encontrada === false || ed.sin_datos) {
        host.innerHTML = '<div class="p-2 text-muted small">No se pudo cargar el comportamiento del producto.</div>';
        return;
      }
      var productos = datos.productos || [];
      var focosF = productos.length
        ? (ed.focos || []).filter(function (f) { return productos.indexOf(f.producto) !== -1; })
        : (ed.focos || []);
      host.innerHTML = __cnCompProdHtml(focosF, ed.meta, ed.tarjetas, sufijo);
      var edScoped = { focos: focosF };
      if (blk.isConnected) {
        __cnPaintFocoStk(blk, edScoped, dd, sufijo);
        __cnCompProdMarcarDia(blk, datos.dia_marcado);
        __cnStackScroll(blk);
      } else {
        // A-6: el bloque se restaura por multitab_shell.js:439 / acordeon.js:140, que llaman a
        // __cnPaintFocoStk pero NO conocen el marcador → la curva se repinta SIN el punto
        // resaltado. Degradación cosmética aceptada y declarada; los datos son los correctos.
        blk.dataset.pendPaint = "1";
        blk.__cnAnzEd = edScoped; blk.__cnAnzDd = dd; blk.__cnAnzSufijo = sufijo;
      }
    }).catch(function () {
      host.innerHTML = '<div class="p-2 text-danger small">Fallo de red cargando el comportamiento del producto.</div>';
    });
  }
```

**Registrar en la cadena** de `__cnPintarPanelCuant` (~línea 3025), **ANTES del fallback**:
```js
             : (panel.tipo === "cuant_dia_panel") ? __cnCompProdPlaceholderHtml((d.productos || [])[0])
```

**Despachar la carga** en `:3102`, junto a la línea existente:
```js
    if (panel.tipo === "analiza_foco") __cnAnzCargarFoco(blk, d, "-stk" + __cnStackSeq);
    if (panel.tipo === "cuant_dia_panel") __cnCompProdCargar(blk, d, "-stk" + __cnStackSeq);
```

Exportar `__cnCompProdCargar` en `window.MultiTabShell` (~línea 5922).

---

### PASO 6 · Marcar el día sobre la curva (A-4)
**Archivo:** `static/js/multitab_shell.js`

```js
  // [2026-08-25] Resalta el día que la pregunta nombró. Se hace con Plotly.addTraces SOBRE la curva
  // ya pintada — __cnDailyPlot NO se toca (es compartida con el panel de Focos).
  // 🔑 A-4: el eje X NO son fechas ISO. __cnDailyPlot (:1749-1753) mapea cada fecha al DÍA DEL MES
  // como STRING ("1","15") con xaxis.type="category". Buscar la ISO completa nunca calzaría y el
  // marcador no aparecería, fallando en silencio. Medido en el código, no supuesto.
  function __cnCompProdMarcarDia(blk, iso) {
    if (!iso || !window.Plotly) return;
    var host = blk.querySelector(".cn-ins .cn-ins__plot");
    if (!host || !host.data || !host.data.length) return;
    var dia = String(parseInt(String(iso).slice(8, 10), 10));   // "2026-05-15" -> "15"
    var xs = host.data[0].x || [], ys = host.data[0].y || [];
    var i = xs.indexOf(dia);
    if (i < 0) return;
    try {
      window.Plotly.addTraces(host, {
        x: [xs[i]], y: [ys[i]], type: "scatter", mode: "markers",
        marker: { size: 13, color: "#F7DB17", line: { color: "#004236", width: 2 } },
        hoverinfo: "skip", showlegend: false
      });
    } catch (e) { /* el marcador es decorativo: jamás debe tumbar el panel */ }
  }
```

---

### PASO 7 · Cache-buster
`MainChat/templates/mainchat_layout.html:113` → `?v=20260825d` **→** `?v=20260825e`.

---

### PASO 8 · Tests
**Archivo:** `INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py` — **añadir**, sin tocar los 28.

1. `_panel_datos` N1D → `periodo == "mayo 2026"`, `productos == ["CRUDO"]`,
   `dia_marcado == "2026-05-15"`, `entidad`/`nivel`/`segmento` presentes.
2. Idem N1DSEL + `orden`/`mes_label`/`dias_con_dato`/`rango`.
3. **El periodo sigue a la PREGUNTA:** contrato con `fecha="2026-03-15"` → `periodo == "marzo 2026"`.
4. `_PANEL_TIPO["N1D"] == _PANEL_TIPO["N1DSEL"] == "cuant_dia_panel"`.
5. Producto gas → `productos == ["GAS"]`.

---

## 9. VALIDACIONES

### V-A · Contrato del backend
| Caso | Esperado |
|---|---|
| «el 15 de mayo» | `cuant_dia_panel` · `periodo='mayo 2026'` · `dia_marcado='2026-05-15'` |
| «mejor día este mes» | `cuant_dia_panel` · `periodo='mayo 2026'` · `dia_marcado='2026-05-08'` |
| **«el 15 de marzo»** | **`periodo='marzo 2026'`** ← el mes de la pregunta, no el del techo |
| «blancos el 15 de mayo» | sigue rechazando, sin panel |

### V-B · NO ROMPER
```
¿Cuánto crudo produjo Castilla?      → cuant_kpi · 6.860.389 bbl · 102.7%
¿Cuánto produjo Castilla en abril?   → cuant_kpi · 6.473.184 bbl · 103.5%
acumulado del año                    → cuant_kpi N2
serie mensual                        → cuant_serie
los 5 campos que más crudo producen  → cuant_rank
¿Cuánto produjo Castilla ayer?       → rechazo citando el techo, sin panel
```
- **A-8:** `analiza_foco` sigue recibiendo `secciones` (del fallback determinista si el LLM no
  corre) → no se rompe. Comprobar que el proxy sin `pulir` se comporta igual que hoy.
- **JS:** balance de llaves/paréntesis **idéntico a `git show HEAD:static/js/multitab_shell.js`**
  (el archivo tiene un desbalance preexistente de 8 paréntesis por comentarios; comparar **relativo**).

### V-C · Suite
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -3
```
**EXACTAMENTE los 7 fallos preexistentes.** Un 8.º = regresión → **DETENERSE**.

### V-D · Validación humana en navegador — **OBLIGATORIA** (§17.5 R3 / DT-15)
> Los servicios corren en el equipo del usuario; el executor **no puede** validar esto.

1. Reiniciar INGESTA (8088) · Ctrl+F5.
2. «¿Cuánto produjo Castilla el 15 de mayo?» → gauge de **mayo** + curva de **mayo**, día 15 marcado.
3. **«¿Cuánto produjo Castilla el 15 de marzo?»** → gauge y curva de **marzo (31 días)**. ⬅ prueba
   la decisión del usuario.
4. «¿Mejor día de Castilla este mes?» → día 8 marcado.
5. **Tiempo de respuesta del panel: segundos, no minutos** (si tarda ~3 min, A-5 no quedó resuelto).
6. Ambas tarjetas a la misma altura, **sin columna vacía a la derecha** (sería A-1).
7. Plotly con tamaño correcto al primer render, no colapsado a 0 px (sería A-2).
8. El bloque lleva el **filete verde de crudo** (A-7).
9. «Focos de atención» conserva sus 4 pestañas y sus 3 bloques.
10. F12 Console: **0 errores**.

---

## 10. REGLAS NO NEGOCIABLES

1. **`__cnFocosHtml`, `__cnTarjetasKpiHtml`, `__cnDailyInto`, `__cnDailyPlot` y `__cnPaintFocoStk`
   quedan BYTE-IDÉNTICAS.**
2. **Clase de grid NUEVA.** No reutilizar `.cn-desemp__grid2--kpi` (A-1: 3 columnas).
3. **`is-active` obligatorio** en `.cp-foco__panel` (A-2).
4. **El marcador busca el DÍA como string**, no la fecha ISO (A-4).
5. **`pulir=false` en el fetch de ejecutivo** + reenvío en el proxy (A-5).
6. **Conservar `f.rank`** y el patrón `cn-foco-day-{rank}{sufijo}` (A-9).
7. **El periodo lo manda el backend** desde la fecha de la pregunta. Nunca el último mes con datos.
8. **`cuant_dia` y `__cnCuantDiaHtml` se conservan** como fallback (A-3).
9. **El tipo nuevo se registra ANTES del fallback** de `__cnPintarPanelCuant`.
10. **Bump del cache-buster**, o el cambio no se ve.
11. **No commit, no push.**

---

## 11. FUERA DE ALCANCE

- «Focos de atención» y sus 4 pestañas.
- Preguntas mensuales (N1/N2/N3/N4) y ranking N5: conservan sus paneles.
- El marcador del día en bloques restaurados desde pestaña oculta (A-6, degradación declarada).
- `patrones_grupo.yaml`, `maquina_q.py`, jerarquizar, analizar.
- Reformatear código existente.

---

## 12. PROMPT EXECUTOR

```
Eres un agente EXECUTOR. Lee COMPLETO el plan en
INGESTA/Rep_Prod/Planes/plan_panel_comportamiento_dia_2026-08-25.md
y ejecútalo AL PIE DE LA LETRA, en orden: PASO 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.

CONTEXTO (no tienes historial previo; todo lo necesario está en el plan)
- Raíz: c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0
- Backend FastAPI en INGESTA/Rep_Prod/backend · Flask (proxy + plantillas) en routes/ y MainChat/
- Frontend JS vanilla. NO hay Node, NO hay build.
- Python: INGESTA\Rep_Prod\backend\.venv\Scripts\python.exe
- Ejecuta SIEMPRE así:
    cd INGESTA/Rep_Prod/backend && PYTHONPATH="$PWD" ./.venv/Scripts/python.exe ...
- Comunicación y comentarios de código: 100% en ESPAÑOL.

REGLAS DURAS
1. NO modifiques el plan. Las decisiones están cerradas; tú solo implementas.
2. PRIMERO toma la línea base de §6 (pytest + git status) y anótala. La suite final debe tener
   EXACTAMENTE los mismos 7 fallos preexistentes. Un 8.º = regresión → DETENTE y reporta.
3. Si cualquier verificación (V-1, V-2, V-A, V-B, V-C) falla, DETENTE y reporta. No improvises.
4. Respeta las 11 REGLAS NO NEGOCIABLES de §10. Las cinco más fáciles de violar:
   · __cnFocosHtml / __cnTarjetasKpiHtml / __cnDailyInto / __cnDailyPlot / __cnPaintFocoStk NO se tocan.
   · Clase de grid NUEVA — .cn-desemp__grid2--kpi es de 3 columnas, no sirve.
   · `is-active` en .cp-foco__panel, o Plotly pinta a tamaño 0.
   · El marcador del día busca el DÍA como string ("15"), NO la fecha ISO — el eje X es categoría.
   · `pulir=false` en el fetch + reenviarlo en el proxy, o cada pregunta cuelga ~3 minutos.
5. static/js/multitab_shell.js lo edita OTRA SESIÓN: corre `git status` ANTES de tocarlo. Si sale
   modificado, DETENTE y reporta. Si está limpio, AÑADE solo lo del plan y no reformatees nada.
   Verifica el balance de llaves/paréntesis CONTRA `git show HEAD:static/js/multitab_shell.js`,
   no en absoluto (hay un desbalance preexistente de 8 paréntesis por comentarios).
6. LOS SERVICIOS (Flask 8020 / INGESTA 8088) CORREN EN EL EQUIPO DEL USUARIO, NO EN EL TUYO.
   Un `curl` a localhost dará HTTP 000 y eso NO significa que la app esté caída. NO intentes
   verificar por HTTP ni concluyas nada de ese fallo.
7. NO importes endpoints FastAPI (`desempeno`, `ejecutivo`) para llamarlos desde un script suelto:
   sus defaults `= Query(None)` viajan como valor y devuelven ceros FALSOS. Si necesitas medir el
   backend, hazlo por la ruta real (`respuesta_cuantificar.responder`).
8. Mide contra el motor real; no deduzcas del código. Si una cifra no la mediste, no la afirmes.
9. NO hagas commit ni push.
10. Al terminar NO declares la feature completada: queda PENDIENTE DE VALIDACIÓN HUMANA (V-D,
    regla §17.5 R3 / DT-15). El panel es VISUAL y solo el usuario puede validarlo.

ARCHIVOS QUE PUEDES MODIFICAR (solo estos 6)
  1. INGESTA/Rep_Prod/backend/app/features/consulta_v2/respuesta_cuantificar.py
  2. INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py     (solo AÑADIR tests)
  3. routes/api.py                                              (1 línea: reenviar `pulir`)
  4. static/js/multitab_shell.js                                (solo AÑADIR)
  5. static/css/colapsable.css                                  (solo AÑADIR al final)
  6. MainChat/templates/mainchat_layout.html                    (solo el cache-buster)

REPORTA
- ✅/❌ por paso, con la SALIDA REAL de cada verificación (no la esperada).
- Las tablas V-A y V-B rellenas con lo que devolvió el motor.
- Línea base vs suite final, lado a lado.
- Aviso explícito: V-D (navegador) queda PENDIENTE del usuario.
```
