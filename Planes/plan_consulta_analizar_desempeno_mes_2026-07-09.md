# Plan ejecutable — Consulta · "Analizar {entidad}" → Desempeño del mes (MVP, Producción ECP)

> **Cobertura:** N/A (feature de análisis de lectura; NO toca DDL, ETL ni el grano de las tablas fuente).
> **Tipo:** backend (1 endpoint nuevo de solo lectura) + 1 proxy Flask + frontend (JS/CSS/cache-buster).
> **Estado:** v2 auditado (flujo §0.2). Reutiliza la resolución de entidad de `/analisis/densidad`.
> **Alcance MVP:** módulos **(1) KPIs REAL vs PPTO por producto** + **(2) curva diaria REAL** +
> **(3) barras Real vs Presupuesto**. El módulo "Plan (Programa)", mix ECP/SOCIOS y Top movers quedan
> para Fase 2 (ver §10).

---

## 1. Contexto

En la pestaña **Consulta** del MultiTab Shell, al resolver una entidad aparece la tarjeta «Entidad
identificada» con el botón **"Analizar {entidad}"** — hoy es **placeholder** (`onclick="window.__cnEnDiseno(this)"`
→ "En diseño — pronto"). Este plan lo convierte en un **tablero de desempeño del último mes** para el
segmento **Producción ECP**, pintado en el visor DERECHO (`#cn-viewer-area`), reemplazando el Panorama
(Densidad+Cobertura) con un enlace **"← Volver al panorama"** (reusa `window.__cnVolverPanorama`, ya existe).

Los datos salen de las 3 tablas tipadas del segmento:
- `core.fact_produccion_dia_ecp` (REAL diario, 5 medidas) → **curva diaria** + promedio BPD + días con reporte.
- `core.fact_produccion_mes_ecp` (multi-escenario) → **REAL vs PPTO** por producto (KPIs + barras).
- (`core.fact_programa_ecp` → Plan, **Fase 2**.)

**Números reales verificados (Abril 2026, mes cerrado):** cumplimiento CRUDO 95.8% (85.4M/89.2M),
GAS 82.7% (66.7M/80.6M), BLANCOS 91.6% (0.92M/1.00M). El `día` REAL cuadra con `mes` REAL en Abril
(84.98M vs 85.42M CRUDO) → la reconciliación día↔mes es sana.

---

## 2. Objetivo

`GET /api/analisis/desempeno?entidad=<E>` devuelve, para el **último mes con dato** de la entidad:
1. **Por producto (CRUDO/GAS/BLANCOS):** REAL (mensual), PPTO (mensual), **% cumplimiento** — TODO de `mes`.
2. **Curva diaria REAL** por producto (SOLO forma/tendencia; no alimenta los KPIs — ver H2).
3. Metadata del mes (nombre, días con dato / días del mes, `completo`, `sin_cierre`).

El frontend lo pinta como **KPI cards + barras Real/Presupuesto + gráfico de línea diaria** (Plotly).

**Decisiones cerradas:**
- **D1 — Mes objetivo:** el ÚLTIMO mes con dato diario de la entidad (o, si es filial sin grano diario,
  el último mes con REAL mensual). Se devuelve `completo` (días_con_data ≥ días_del_mes) para que el
  frontend etiquete "mes en curso (17/31)" cuando aplique. **KPIs de cumplimiento SIEMPRE desde `mes`**
  (REAL vs PPTO mensual) — NO se suman días parciales (evita distorsión del mes en curso).
- **D2 — Filial / vicepresidencia sin grano diario:** se devuelve `aplica_diario=false`; el frontend
  oculta la curva diaria y muestra solo KPIs + barras (desde `mes`), con una nota.
- **D3 — Productos:** exactamente `CRUDO`, `GAS`, `BLANCOS` (los 3 `dim_tipo_producto`).
- **D4 — Resolución de entidad:** MISMO criterio que `/analisis/densidad` (fuente_id por 6 columnas de
  `dim_fuente` + `vice_id`). Si no resuelve → `{encontrada:false}`.

---

## 3. Prerequisitos

- Backend INGESTA `:8000` + Flask `:8020` arriba.
- BD con datos ECP (dev local: `fact_produccion_dia_ecp` 435k filas, rango hasta 17-may-2026).
- Entrar a Consulta y resolver una entidad con grano diario (rama A ECP), p. ej. **Castilla** (Campo).

---

## 4. Inventario de archivos

**Se MODIFICA:**

| Archivo (ruta absoluta) | Cambio |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | + endpoint `desempeno()` (append al final) |
| `...\routes\api.py` | + proxy `/api/analisis/desempeno` |
| `...\static\js\multitab_shell.js` | wire botón "Analizar" + funciones de render |
| `...\static\css\colapsable.css` | bloque CSS `.cn-desemp*` (append) |
| `...\templates\main.html` | cache-buster `?v=20260709h` → `?v=20260709i` |

**Se REUTILIZA (NO se toca):**
- Patrón de resolución de entidad de `analisis/api.py` `densidad()` (líneas 103–136).
- `MESES_ES` (ya definido en `analisis/api.py`, usado en `densidad`).
- `window.__cnVolverPanorama()` y `window.__cnDashboard(intent)` (multitab_shell.js).
- `window.Plotly` (vendorizado y cargado; ya usado por el heatmap de la pestaña Análisis).
- Helpers del IIFE: `el`, `esc`, `__cnViewerArea`, var `__cnLastIntent`.

---

## 5. Hallazgos de auditoría VERIFICADOS contra la BD (H1–H8)

> Auditoría ejecutada con consultas reales sobre `daily_report_prod` (dev local). Los hallazgos H1/H2
> **corrigen bugs de correctitud** del plan v1; el resto endurece robustez/coherencia.

- **H1 (CORRECTITUD — verificado) — `volumen` por producto vive en UN solo proceso.** En
  `fact_produccion_mes_ecp`, cada `(producto, escenario)` tiene `volumen` en un único `proceso`:
  **CRUDO→PROD_TOTAL, GAS→VENTA-GRAVABLE, BLANCOS→GAS CONVERTIDO MME** (los demás procesos = NULL, 0 filas
  con valor). ⇒ `SUM(m.volumen)` **sin filtrar proceso** NO doble-cuenta y es **robusto al mapeo** (no hay
  que hard-codear el proceso por producto). Confirmado: REAL/CRUDO Abril = 85.417.841 tanto con SUM(todos)
  como con solo PROD_TOTAL. **Regla:** NO agregar filtro de proceso; NO cambiar por un CASE por producto.
- **H2 (CORRECTITUD — verificado) — NO mezclar `día` y `mes` en el KPI.** `día` y `mes` usan **medidas
  distintas** para algún producto: BLANCOS Abril = **1.924.803 (día)** vs **916.592 (mes)** (~2×), mientras
  CRUDO/GAS sí cuadran (día≈mes). ⇒ **Todos los KPIs (REAL, cumplimiento) salen 100% de `mes`.** Se
  **eliminó** el "BPD prom" derivado de `día` (además la unidad de `volumen` no es bpd — 85M/30 ≠ tasa
  real → no afirmar unidades no validadas). `día` se usa **solo para la forma de la curva**, con nota al pie.
- **H3 (idiom del repo) — Proxy pasa `entidad` solo si viene** (como `analisis_densidad`/`_huella`).
  Pasar `entidad=""` caería en `{encontrada:false}` en vez de global.
- **H4 (robustez UI) — Guarda de Plotly con mensaje** (igual que `__anHeatmap` línea 713), no `return` mudo.
- **H5 (robustez datos) — Mes sin cierre.** Si el mes objetivo no tiene fila mensual REAL/PPTO (`sin_cierre`),
  el frontend muestra un aviso en vez de 3 tarjetas vacías.
- **H6 (`bindparam` expanding)** — `fuente_id IN :ids` usa `sa.bindparam("ids", expanding=True)`, aplicado
  SOLO cuando hay `ids` (helper `_bind`). Si resolvió solo por `vice_id`, no hay `ids` (sin IN vacío).
- **H7 (alias por tabla en WHERE)** — `día`/`mes` comparten `fuente_id`/`vice_id`; el WHERE se arma con
  prefijo de alias (`d.`, `m.`) vía `where(alias)` — sin `str.replace` frágil. `fin de mes` exacto con
  `calendar.monthrange`.
- **H8 (contigüidad de anclas — verificado)** — el ancla del frontend `// ---- Panorama: densidad ...`
  sigue **presente y única** (línea ~1107) tras el plan anterior (Ver reporte del día); el bloque nuevo
  queda contiguo a `__cnVerReporteDia`/`__cnVerTabla`. `window.Plotly` **confirmado disponible** en el
  shell (`__anHeatmap` lo usa). Solo cambia el `onclick` del botón "Analizar" (no se toca "Ver reporte").

---

## 6. Especificación

### 6.1 Backend — nuevo endpoint en `analisis\api.py`

**Agregar al FINAL de** `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py`:

```python


# ============================================================================
# Desempeño del mes (MVP · segmento Producción ECP). Solo lectura, sin LLM.
# Módulos: (1) KPIs REAL vs PPTO por producto (mes) + (2) curva diaria REAL (día).
# Resolución de entidad = MISMO criterio que /densidad (fuente_id 6 cols + vice_id).
# ============================================================================
@router.get("/desempeno")
def desempeno(entidad: str | None = Query(None)):
    import calendar

    def _bind(sql, params):
        t = sa.text(sql)
        if "ids" in params:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return t

    eng = get_engine()
    with eng.connect() as c:
        ids, vid = [], None
        if entidad:
            E = entidad.strip().upper()
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
                   OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
                   OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E}).all()]
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"),
                {"e": E}).scalar()
            if not ids and vid is None:
                return {"entidad": entidad, "encontrada": False}

        base = {}
        if ids:
            base["ids"] = ids
        if vid is not None:
            base["vid"] = vid

        def where(alias):
            p = (alias + ".") if alias else ""
            cs = []
            if ids:
                cs.append(f"{p}fuente_id IN :ids")
            if vid is not None:
                cs.append(f"{p}vice_id = :vid")
            return ("(" + " OR ".join(cs) + ")") if cs else "TRUE"

        # --- mes objetivo: último mes con dato diario (o REAL mensual si es filial) ---
        maxd = c.execute(_bind(
            f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {where('')}", base), base).scalar()
        aplica_diario = maxd is not None
        if maxd is None:
            maxd = c.execute(_bind(f"""
                SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE es.nombre = 'REAL' AND {where('m')}""", base), base).scalar()
        if maxd is None:
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}

        y, mo = maxd.year, maxd.month
        dim = calendar.monthrange(y, mo)[1]
        ini = f"{y:04d}-{mo:02d}-01"
        fin = f"{y:04d}-{mo:02d}-{dim:02d}"

        # --- Módulo 1: REAL vs PPTO por producto (SOLO mensual — VERIFICADO H1) ---
        # H1: el `volumen` de cada producto vive en UN SOLO proceso (CRUDO→PROD_TOTAL,
        # GAS→VENTA-GRAVABLE, BLANCOS→GAS CONVERTIDO MME); los demás procesos van en NULL.
        # Por eso SUM(m.volumen) sobre TODOS los procesos NO doble-cuenta y es ROBUSTO al mapeo
        # (no hay que hard-codear el proceso por producto). NO filtrar por proceso.
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_bind(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1, 2""", pm), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)

        # --- Módulo 2: curva diaria REAL (SOLO forma/tendencia — NO alimenta los KPIs, H2) ---
        # H2: día y mes usan MEDIDAS distintas para algunos productos (BLANCOS: día≈1.9M vs mes≈0.9M).
        # Por eso los KPIs (REAL/cumplimiento) salen 100% de `mes`, y `día` se usa SOLO para la curva.
        curva = {}
        curva_fechas, dias_rep = [], 0
        if aplica_diario:
            pd = dict(base); pd["ini"] = ini; pd["fin"] = fin
            rows = c.execute(_bind(f"""
                SELECT d.fecha, tp.nombre prod, SUM(d.volumen) vol
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                GROUP BY 1, 2 ORDER BY 1""", pd), pd).all()
            for f, prod, vol in rows:
                iso = f.isoformat()
                curva.setdefault(iso, {})[prod] = float(vol or 0)
            curva_fechas = sorted(curva.keys())
            dias_rep = len(curva_fechas)

        productos = ["CRUDO", "GAS", "BLANCOS"]
        por_producto = []
        for p in productos:
            real = kpi.get(p, {}).get("REAL", 0.0)
            ppto = kpi.get(p, {}).get("PPTO", 0.0)
            cumpl = round(real / ppto * 100.0, 1) if ppto else None
            por_producto.append({"producto": p, "real": real, "ppto": ppto, "cumplimiento": cumpl})
        series = {p: [curva.get(f, {}).get(p, 0.0) for f in curva_fechas] for p in productos}
        sin_cierre = not any(kpi.get(p) for p in productos)   # H5: sin fila mensual REAL/PPTO para el mes

        return {
            "entidad": entidad, "encontrada": True, "aplica_diario": aplica_diario,
            "sin_cierre": sin_cierre,
            "mes": {"anio": y, "mes": mo, "nombre": MESES_ES[mo],
                    "dias_con_data": dias_rep, "dias_del_mes": dim, "completo": dias_rep >= dim},
            "por_producto": por_producto,
            "curva": {"fechas": curva_fechas, "series": series},
        }
```

> El router `analisis` ya está registrado en `app/main.py` con prefix `/analisis` → la ruta queda en
> `/analisis/desempeno`. `sa`, `Query`, `get_engine`, `MESES_ES` ya están importados en el archivo.

### 6.2 Flask — proxy en `routes\api.py`

**Buscar** el proxy de densidad (~línea 150):

```python
@api_bp.route("/analisis/densidad")
def analisis_densidad():
```

**Insertar ANTES de esa función** (o después de `analisis_catalogo`) el siguiente proxy:

```python
@api_bp.route("/analisis/desempeno")
def analisis_desempeno():
    """Proxy: desempeño del mes (KPIs REAL vs PPTO + curva diaria) de una entidad."""
    try:
        params = {}
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent   # H3: idiom del repo — solo pasar entidad si viene (evita ""→no encontrada)
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno", params=params, timeout=45)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

### 6.3 Frontend — `multitab_shell.js`

**(a) Wire del botón "Analizar".** Buscar (~línea 1188):

```js
      var btnAnalizar = '<li><button type="button" class="rb-chat__option" onclick="window.__cnEnDiseno(this)">' +
        '<span class="rb-chat__option-tile"><i class="bi bi-bar-chart-line"></i></span>' +
        '<span class="rb-chat__option-body"><span class="rb-chat__option-title">Analizar ' + entName + '</span>' +
        '<span class="rb-chat__option-desc">Cuánto produce, cómo ha cambiado y qué campos aportan más</span></span>' +
        '<i class="rb-chat__option-chev bi bi-chevron-right"></i></button></li>';
```

Reemplazar la 1ª línea (el `onclick`) por una llamada a `__cnAnalizar` con la entidad:

```js
      var entArg = (it.valor || it.entidad || "").replace(/'/g, "\\'");
      var btnAnalizar = '<li><button type="button" class="rb-chat__option" onclick="window.__cnAnalizar(\'' + entArg + '\')">' +
        '<span class="rb-chat__option-tile"><i class="bi bi-bar-chart-line"></i></span>' +
        '<span class="rb-chat__option-body"><span class="rb-chat__option-title">Analizar ' + entName + '</span>' +
        '<span class="rb-chat__option-desc">Cuánto produce, cómo ha cambiado y qué campos aportan más</span></span>' +
        '<i class="rb-chat__option-chev bi bi-chevron-right"></i></button></li>';
```

**(b) Funciones de render.** Insertar ESTE bloque JUSTO ANTES del comentario
`// ---- Panorama: densidad (KPIs + matriz de días, CSS puro, sin Plotly) ----` (el mismo ancla del plan
anterior; queda contiguo a las funciones `__cnVerReporteDia`/`__cnVerTabla`):

```js
  // ============================================================
  // Consulta · "Analizar {entidad}": Desempeño del mes (Producción ECP) en el panel DERECHO.
  // Módulos MVP: KPIs REAL vs PPTO + barras Real/Presupuesto + curva diaria REAL (Plotly).
  // ============================================================
  var __cnDesempData = null;   // cache del payload para el selector de producto de la curva

  window.__cnAnalizar = function (entidad) {
    var a = __cnViewerArea(); if (!a) return;
    a.innerHTML =
      '<div class="cn-desemp">' +
      '  <div class="cn-rep__bar">' +
      '    <button type="button" class="cn-rep__back" onclick="window.__cnVolverPanorama()">' +
      '      <i class="bi bi-arrow-left"></i> Volver al panorama</button>' +
      '    <span class="cn-rep__date"><i class="bi bi-bar-chart-line-fill"></i> Desempeño de ' + esc(entidad) + '</span>' +
      '  </div>' +
      '  <div id="cn-desemp-body" class="cn-desemp__body">' +
      '    <div class="d-flex align-items-center gap-2 p-3 text-muted small">' +
      '      <div class="spinner-border spinner-border-sm"></div> Calculando desempeño del mes…</div></div>' +
      '</div>';
    fetch("/api/analisis/desempeno?entidad=" + encodeURIComponent(entidad))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var body = el("cn-desemp-body"); if (!body) return;
        if (!d || d.encontrada === false) { body.innerHTML = '<div class="p-3 text-muted small">No reconocí «' + esc(entidad) + '» como entidad con producción ECP.</div>'; return; }
        if (d.sin_datos) { body.innerHTML = '<div class="p-3 text-muted small">Sin datos de producción para esta entidad.</div>'; return; }
        if (d.sin_cierre) { body.innerHTML = '<div class="p-3 text-muted small">' + esc((d.mes||{}).nombre||"") + ' ' + ((d.mes||{}).anio||"") + ' aún no tiene cierre mensual (REAL/PPTO) para esta entidad.</div>'; return; }   // H5
        __cnDesempData = d;
        body.innerHTML = __cnRenderDesemp(d);
        __cnCurvaPlot("CRUDO");   // curva por defecto en CRUDO [A5]
      })
      .catch(function () {
        var body = el("cn-desemp-body");
        if (body) body.innerHTML = '<div class="alert alert-danger m-3">Error calculando el desempeño.</div>';
      });
  };

  function __cnMilesEC(n) { return Number(n || 0).toLocaleString("es-CO", { maximumFractionDigits: 0 }); }
  function __cnSemColor(pct) { return pct == null ? "" : (pct >= 95 ? "is-ok" : (pct >= 85 ? "is-warn" : "is-bad")); }

  function __cnRenderDesemp(d) {
    var m = d.mes || {};
    var etiqueta = esc(m.nombre) + " " + m.anio + (m.completo ? "" : " · en curso (" + m.dias_con_data + "/" + m.dias_del_mes + ")");
    // KPI cards + barras Real/Presupuesto
    var cards = "", bars = "";
    (d.por_producto || []).forEach(function (p) {
      var sem = __cnSemColor(p.cumplimiento);
      var pct = (p.cumplimiento == null) ? "—" : (p.cumplimiento + "%");
      cards +=
        '<div class="cn-desemp__kpi ' + sem + '">' +
        '  <div class="cn-desemp__kpi-prod">' + esc(p.producto) + '</div>' +
        '  <div class="cn-desemp__kpi-real">' + __cnMilesEC(p.real) + '</div>' +
        '  <div class="cn-desemp__kpi-sub">Volumen REAL del mes</div>' +   /* H2: sin "BPD" (unidad no validada) ni mezcla con día */
        '  <div class="cn-desemp__kpi-cumpl ' + sem + '">' + pct + ' <span>del presupuesto</span></div>' +
        '</div>';
      var w = (p.cumplimiento == null) ? 0 : Math.max(0, Math.min(100, p.cumplimiento));
      bars +=
        '<div class="cn-desemp__bar-row">' +
        '  <div class="cn-desemp__bar-lbl">' + esc(p.producto) + '</div>' +
        '  <div class="cn-desemp__bar-track"><div class="cn-desemp__bar-fill ' + sem + '" style="width:' + w + '%"></div></div>' +
        '  <div class="cn-desemp__bar-val">' + __cnMilesEC(p.real) + ' / ' + __cnMilesEC(p.ppto) + '</div>' +
        '</div>';
    });
    var curva = "";
    if (d.aplica_diario && d.curva && d.curva.fechas && d.curva.fechas.length) {
      curva =
        '<div class="cn-desemp__card">' +
        '  <div class="cn-desemp__card-hd"><span><i class="bi bi-graph-up"></i> Producción diaria REAL · ' +
        m.dias_con_data + '/' + m.dias_del_mes + ' días</span>' +
        '    <span class="cn-desemp__prodsel">' +
        ["CRUDO", "GAS", "BLANCOS"].map(function (p, i) {
          return '<button type="button" class="cn-desemp__prodbtn' + (i === 0 ? " is-active" : "") +
            '" onclick="window.__cnCurvaPlot(\'' + p + '\', this)">' + p + '</button>';
        }).join("") +
        '    </span></div>' +
        '  <div id="cn-desemp-plot" class="cn-desemp__plot"></div>' +
        '  <div class="cn-desemp__foot">Muestra la <strong>forma diaria</strong>; el total mensual REAL está en las tarjetas de arriba (día y mes pueden usar medidas distintas por producto — H2).</div>' +
        '</div>';
    } else {
      curva = '<div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-graph-up"></i> Producción diaria</span></div>' +
        '<div class="p-3 text-muted small">Esta entidad no tiene grano diario ECP (es consolidada). Se muestra solo el resumen mensual.</div></div>';
    }
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__kpis">' + cards + '</div>' +
      '<div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
      '  <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva
    );
  }

  // Dibuja la curva diaria del producto elegido (Plotly). [A5] un solo producto a la vez (escalas dispares).
  window.__cnCurvaPlot = function (producto, btn) {
    if (btn) {
      var wrap = btn.parentNode;
      if (wrap) wrap.querySelectorAll(".cn-desemp__prodbtn").forEach(function (b) { b.classList.remove("is-active"); });
      btn.classList.add("is-active");
    }
    var d = __cnDesempData, elp = el("cn-desemp-plot");
    if (!d || !elp) return;
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }   // H4: guarda con mensaje (como __anHeatmap)
    var x = d.curva.fechas, y = (d.curva.series || {})[producto] || [];
    Plotly.newPlot(elp, [{
      x: x, y: y, type: "scatter", mode: "lines+markers",
      line: { color: "#1f6b4a", width: 2 }, marker: { size: 4 },
      hovertemplate: "%{x}<br>%{y:,.0f}<extra></extra>"
    }], {
      margin: { l: 56, r: 12, t: 8, b: 36 }, height: 240,
      xaxis: { tickangle: -45, tickfont: { size: 10 } },
      yaxis: { tickfont: { size: 10 }, separatethousands: true },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)"
    }, { displayModeBar: false, responsive: true });
  };

```

### 6.4 CSS — append en `colapsable.css`

**Agregar al FINAL de** `...\static\css\colapsable.css`:

```css
/* ============================================================
   Consulta · Desempeño del mes (Analizar {entidad})
   ============================================================ */
.cn-desemp { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.cn-desemp__body { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 14px; }
.cn-desemp__monthlbl { font-size: .9rem; font-weight: 700; color: #2f4a3d; margin-bottom: 10px; }
.cn-desemp__kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.cn-desemp__kpi { border: 1px solid var(--rb-border, #e3e8e5); border-left: 4px solid #9aa7a0;
  border-radius: 10px; background: #fff; padding: 12px 14px; }
.cn-desemp__kpi.is-ok { border-left-color: #1e9e63; }
.cn-desemp__kpi.is-warn { border-left-color: #E8912B; }
.cn-desemp__kpi.is-bad { border-left-color: #d9534f; }
.cn-desemp__kpi-prod { font-size: .72rem; font-weight: 700; letter-spacing: .04em; color: #6b7a72; text-transform: uppercase; }
.cn-desemp__kpi-real { font-size: 1.5rem; font-weight: 800; color: #1f2d27; line-height: 1.1; }
.cn-desemp__kpi-sub { font-size: .72rem; color: #8a968f; margin-bottom: 6px; }
.cn-desemp__kpi-cumpl { font-size: 1.05rem; font-weight: 800; }
.cn-desemp__kpi-cumpl span { font-size: .68rem; font-weight: 500; color: #8a968f; }
.cn-desemp__kpi-cumpl.is-ok { color: #1e9e63; }
.cn-desemp__kpi-cumpl.is-warn { color: #E8912B; }
.cn-desemp__kpi-cumpl.is-bad { color: #d9534f; }
.cn-desemp__card { border: 1px solid var(--rb-border, #e3e8e5); border-radius: 10px; background: #fff; margin-bottom: 14px; overflow: hidden; }
.cn-desemp__card-hd { display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 9px 12px; font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .02em;
  color: #3a4a42; background: var(--rb-green-soft, #eef5f1); border-bottom: 1px solid var(--rb-border, #e3e8e5); }
.cn-desemp__bars { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
.cn-desemp__bar-row { display: grid; grid-template-columns: 84px 1fr auto; align-items: center; gap: 10px; }
.cn-desemp__bar-lbl { font-size: .78rem; font-weight: 600; color: #4a5a52; }
.cn-desemp__bar-track { height: 14px; background: #eef2f0; border-radius: 7px; overflow: hidden; }
.cn-desemp__bar-fill { height: 100%; background: #9aa7a0; border-radius: 7px; }
.cn-desemp__bar-fill.is-ok { background: #1e9e63; }
.cn-desemp__bar-fill.is-warn { background: #E8912B; }
.cn-desemp__bar-fill.is-bad { background: #d9534f; }
.cn-desemp__bar-val { font-family: monospace; font-size: 11.5px; font-weight: 700; color: #4a5a52; white-space: nowrap; }
.cn-desemp__prodsel { display: inline-flex; gap: 4px; }
.cn-desemp__prodbtn { border: 1px solid var(--rb-border, #cdd8d1); background: #fff; border-radius: 6px;
  padding: 2px 8px; font-size: .68rem; font-weight: 700; color: #6b7a72; cursor: pointer; }
.cn-desemp__prodbtn.is-active { background: var(--rb-green, #1f6b4a); color: #fff; border-color: var(--rb-green, #1f6b4a); }
.cn-desemp__plot { padding: 6px; min-height: 240px; }
.cn-desemp__foot { padding: 6px 12px 10px; font-size: .72rem; color: #8a968f; line-height: 1.35; }
@media (max-width: 720px) { .cn-desemp__kpis { grid-template-columns: 1fr; } }
```

### 6.5 `main.html` — cache-buster

**Buscar:** `...multitab_shell.js') }}?v=20260709h"></script>`
**Reemplazar por:** `...multitab_shell.js') }}?v=20260709i"></script>`

---

## 7. Orden de ejecución

1. `analisis\api.py` §6.1 (endpoint).
2. `routes\api.py` §6.2 (proxy).
3. **Reiniciar el backend INGESTA `:8000`** (hay código Python nuevo → `iniciar_backends.bat` o reinicio del uvicorn). El Flask `:8020` solo necesita recargar si estaba corriendo (los proxies se recargan con `--reload`; si no, reiniciarlo también).
4. `multitab_shell.js` §6.3, `colapsable.css` §6.4, `main.html` §6.5.
5. Navegador **Ctrl+F5**.

---

## 8. Reglas no negociables

- **Solo lectura**: el endpoint NO escribe. NO tocar DDL/ETL/grano.
- Resolver la entidad con el **mismo criterio que `/densidad`** (fuente 6 cols + vice_id). [D4]
- KPIs de cumplimiento **desde `fact_produccion_mes_ecp`** (REAL vs PPTO), NO sumando días parciales. [A1]
- Aplicar `bindparam("ids", expanding=True)` **solo si hay ids**. [A2]
- NO tocar "Ver el reporte de un día" ni el chatbot principal. Solo el `onclick` del botón "Analizar". [A6]
- Vanilla JS ES5 en el frontend; sin dependencias nuevas (Plotly ya está vendorizado).

---

## 9. Validaciones (comando → resultado esperado)

**V1 — Sintaxis JS:** `node --check ...\static\js\multitab_shell.js` → exit 0.

**V2 — Endpoint directo (backend):**
`curl "http://localhost:8000/analisis/desempeno?entidad=Castilla"`
→ JSON con `encontrada:true`, `mes.nombre`, `por_producto` (3 items CRUDO/GAS/BLANCOS con
`real`,`ppto`,`cumplimiento`; **sin `bpd_prom`** — H2), `curva.fechas` no vacío, `aplica_diario:true`,
`sin_cierre:false`.
**Sanity (verificado en auditoría, mes cerrado Abril):** CRUDO REAL=85.417.841 / PPTO=89.173.224 →
cumplimiento **95.8**; GAS **82.7**; BLANCOS **91.6**. La suma de `curva.series.CRUDO` ≈ REAL de CRUDO
(cuadra); para BLANCOS la curva NO cuadra con el REAL (medida distinta — esperado, H2).

**V3 — Proxy Flask:** `curl "http://localhost:8020/api/analisis/desempeno?entidad=Castilla"` → mismo JSON.

**V4 — Navegador (flujo feliz):** Consulta → "produccion de Castilla" → clic **"Analizar CASTILLA"**.
→ El visor derecho muestra: barra "← Volver al panorama", etiqueta del mes, **3 KPI cards** (CRUDO/GAS/
BLANCOS con REAL, BPD prom y % cumplimiento con semáforo), **barras Real vs Presupuesto**, y **gráfico de
línea diaria** (Plotly) con selector CRUDO/GAS/BLANCOS (CRUDO activo por defecto). 0 errores de consola.

**V5 — Selector de producto:** clic en "GAS" → la curva se repinta con la serie de GAS.

**V6 — Volver:** clic "← Volver al panorama" → reaparece el dashboard Densidad+Cobertura.

**V7 — Entidad sin grano diario (filial):** resolver una filial (ej. Hocol rama B) → "Analizar" muestra
KPIs+barras desde `mes` y la tarjeta de curva con la nota "es consolidada" (sin gráfico), sin error.

**V8 — No regresión:** "Ver el reporte de un día", Ingesta, Control, Análisis siguen OK.

---

## 10. Fuera de alcance (Fase 2)

- **Módulo "Plan (Programa)":** superponer la meta de `fact_programa_ecp` (versión vigente) sobre la
  curva y en las barras (Real vs Presupuesto **vs Plan**). Requiere lógica de selección de versión.
- **Mix ECP/SOCIOS** (`grupo_prod`) y por **concepto** (dona/apiladas).
- **Top movers** (pozos/campos con mayor variación vs mes anterior o vs plan).
- **Selector de mes** (hoy = último mes con dato; sin navegación a meses previos).
- Reconciliación oficial de unidades día↔mes↔programa (validada informalmente: día≈mes REAL en Abril).
- El "número real" conversacional en el chat (sigue en la burbuja "el número llega en la siguiente fase").
```
