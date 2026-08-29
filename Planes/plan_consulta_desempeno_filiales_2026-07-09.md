# Plan ejecutable — Consulta · "Analizar {filial}" → Desempeño del mes (Filiales)

> **Cobertura:** N/A (feature de análisis de lectura; NO toca DDL/ETL/grano).
> **Tipo:** backend (1 endpoint nuevo, solo lectura) + 1 proxy Flask + frontend (JS + cache-buster).
> **CSS:** REUSA `.cn-desemp*` del panel ECP → **sin CSS nuevo**.
> **Estado:** v2 auditado (§0.2). Datos verificados contra `daily_report_prod` (dev local).
> **Alcance MVP:** KPIs por filial + barras Real vs Programa + curva diaria Real vs Programa (2 líneas).

---

## 1. Contexto

En la pestaña **Consulta**, el botón **"Analizar {entidad}"** hoy siempre llama `window.__cnAnalizar(entidad)`
(panel de desempeño **ECP**). Pero el segmento **Filiales** (hojas *INICIO*, *POP Filiales y Exploración*,
*Producción filiales*) NO vive en el star schema ECP: vive en tablas propias, y su comparación natural es
**Real vs Programa** (no Real vs Presupuesto).

Este plan añade un **panel de desempeño Filiales** y hace que **"Analizar {entidad}" enrute por rama**:
- `rama === "B"` (filial: America/Hocol/Permian) → **panel Filiales** (este plan).
- otra rama (ECP) → panel ECP existente (`__cnAnalizar`).

**Hechos verificados (BD dev):**
- **3 filiales**: America, Hocol, Permian (`dim_empresa`).
- **`fact_produccion_diaria`**: 2.457 filas, rango 2025-11-30 → **2026-05-31**, trae **Real Y Programa** en la
  MISMA tabla (`dim_tipo_registro` = 'Real' | 'Programa'), ambos **diarios**. En Mayo: Real 17 días,
  Programa 31 días. Grano: `empresa × producto × tipo × fecha` (`uk_fil`).
- **`fact_plan_mensual`** (POP): `pop_kbd` sí, **`ppto_kbd` = NULL** (pendiente conocido) → NO se usa PPTO.
- **`fact_promedio_validado`** (INICIO YTD): contexto (Fase 2).

---

## 2. Objetivo

`GET /api/analisis/desempeno_filiales?entidad=<E>` devuelve, para el **último mes con Real** del scope:
1. **Por unidad** (global → las 3 filiales; con filial → sus productos): Real a la fecha, Programa
   (sobre los MISMOS días con Real), **% cumplimiento**.
2. **Curva diaria**: Real (línea, se corta en el último día con dato) + Programa (línea, mes completo).
3. Metadata del mes.

**Decisiones cerradas:**
- **DF1 — Eje = Real vs Programa** (PPTO de filiales es NULL). El "presupuesto" del panel ECP se sustituye
  por "programa".
- **DF2 — Cumplimiento justo "a la fecha":** `real / programa_sobre_días_con_Real`. NO comparar Real (17d)
  contra Programa (31d).
- **DF3 — Unidad de las tarjetas:** global → **filial** (America/Hocol/Permian); con filial → **producto**
  (solo los que la filial produce; sin tarjetas en 0).
- **DF4 — Enrutado por rama:** el botón "Analizar" decide por `intent.rama` ("B" → Filiales; otra → ECP).
  La carga GLOBAL de Consulta sigue siendo el desempeño **ECP** (no cambia).
- **DF5 — Curva:** total del scope (global = las 3 filiales; filial = todos sus productos), 2 líneas.
  Selector por unidad/producto → Fase 2.

---

## 3. Prerequisitos

- Backend INGESTA `:8000` + Flask `:8020` arriba.
- BD con datos de filiales (dev: `fact_produccion_diaria` 2.457 filas hasta 31-may).
- Entrar a Consulta y resolver una **filial** (ej. "Hocol" → elegir la opción **filial**, rama B; o "Permian").

---

## 4. Inventario de archivos

**Se MODIFICA:**

| Archivo (ruta absoluta) | Cambio |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | + endpoint `desempeno_filiales()` (append) |
| `...\routes\api.py` | + proxy `/analisis/desempeno_filiales` |
| `...\static\js\multitab_shell.js` | + router por rama + funciones de render Filiales; wire del botón |
| `...\templates\main.html` | cache-buster `?v=20260709k` → `?v=20260709l` |

**Se REUTILIZA (NO se toca):**
- CSS `.cn-desemp*` (layout compacto de 2 columnas, KPI cards, barras, `.cn-desemp__plot/__foot`) — **sin CSS nuevo**.
- Helpers del IIFE: `el`, `esc`, `__cnViewerArea`, `__cnLastIntent`, `__cnVolverPanorama`, `__cnMilesEC`,
  `__cnSemColor`, `window.Plotly`, `MESES_ES` (backend).
- Resolución: `dim_empresa` por `UPPER(TRIM(nombre))`.

---

## 5. Hallazgos de auditoría VERIFICADOS contra BD + código (FIL1–FIL8)

> Auditoría ejecutada con consultas reales y lectura del JS actual. **No se hallaron bugs de correctitud**
> (a diferencia del plan ECP): la mayoría son CONFIRMACIONES. FIL8 es una simplificación consciente.

- **FIL1 (verificado) — Eje = Real vs Programa.** PPTO de filiales es NULL → se usa Programa. Ambos viven
  en `fact_produccion_diaria` (diarios). ✅
- **FIL2 (verificado — métrica correcta) — Cumplimiento sobre días con Real.** `real / SUM(Programa donde
  fecha ∈ días_con_Real)`. **Comprobado en BD (Permian, Mayo):** CRUDO 744.227/727.695 = **102.3%**,
  BLANCOS **105.7%**, GAS **114.8%** — números sensatos "a la fecha" (17 días vs 17 días). Se computa en
  Python (tabla chica). ✅
- **FIL3 (verificado — nombres exactos)** — `dim_tipo_registro` = exactamente **['Real','Programa']**;
  `dim_empresa` = **['America','Hocol','Permian']**; **Real MAX = 2026-05-17** (mes objetivo = Mayo,
  `dias_real=17`), **Programa MAX = 2026-05-31**. Productos: America(CRUDO,GAS), Hocol(CRUDO,GAS),
  Permian(BLANCOS,CRUDO,GAS). ✅
- **FIL4 (verificado — anclas del JS)** — `btnAnalizar` está en **L1432-1433** con el texto exacto del edit
  §6.3(a); el ancla `// ---- Panorama: densidad` está en **L1232** (única); el proxy `analisis_desempeno`
  en `routes/api.py` **L147** (insertar el nuevo después). `__cnMilesEC`/`__cnSemColor` son *function
  declarations* (hoisted) → disponibles para el bloque nuevo. ✅
- **FIL5 (verificado — rama "A"/"B")** — el contrato real es `intent.rama === "B"` (L933
  `esFilial = intent.rama === "B"`; L1416 `ramaCorta`). El router por rama es coherente con el código
  existente. Hocol dual: rama B → Filiales; rama A → ECP. America/Permian se resuelven vía `dim_empresa`
  (rama B; el resolver ya indexa `dim_empresa` — S19). ✅
- **FIL6 (robustez — case-insensitive)** — el match `UPPER(TRIM(nombre))=:e` con `E=entidad.strip().upper()`
  hace que el case de `it.valor` (p. ej. "HOCOL" vs "Hocol") **no importe**. Si no matchea ninguna filial →
  `{encontrada:false}` + mensaje. Proxy pasa `entidad` solo si viene.
- **FIL7 (UI — barra >100%)** — el cumplimiento puede superar 100% (over-performance, p. ej. GAS 114.8%);
  la barra se capa a 100% (lleno = cumplido/superado) y el semáforo queda verde. Correcto.
- **FIL8 (simplificación consciente — curva agregada)** — la curva suma **todos los productos del scope**
  en 2 líneas (Real/Programa). Para una filial multi-producto (o el global) esto **mezcla productos de
  distinta unidad** (CRUDO+GAS+BLANCOS). Es aceptable como vista de "seguimiento GENERAL" (el desglose por
  producto/unidad está en las tarjetas KPI); el **selector por producto** queda para Fase 2. La nota al pie
  lo hace explícito ("suma de todos los productos del scope").

**Conclusión de la auditoría:** el plan es correcto tal cual; solo se refuerza el copy de la nota al pie
(FIL8) y se documentan las cifras de sanity verificadas. Sin cambios de lógica.

---

## 6. Especificación

### 6.1 Backend — nuevo endpoint en `analisis\api.py`

**Agregar al FINAL de** `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py`:

```python


# ============================================================================
# Desempeño del mes — FILIALES (America/Hocol/Permian). Eje = Real vs Programa
# (fact_produccion_diaria trae ambos, diarios). PPTO de filiales es NULL → no se usa.
# ============================================================================
@router.get("/desempeno_filiales")
def desempeno_filiales(entidad: str | None = Query(None)):
    import calendar
    from collections import defaultdict

    eng = get_engine()
    with eng.connect() as c:
        emp_id = None
        if entidad:
            E = entidad.strip().upper()
            emp_id = c.execute(sa.text(
                "SELECT empresa_id FROM core.dim_empresa WHERE UPPER(TRIM(nombre))=:e"),
                {"e": E}).scalar()
            if emp_id is None:
                return {"entidad": entidad, "encontrada": False}

        wemp = "AND f.empresa_id = :emp" if emp_id is not None else ""
        pe = {"emp": emp_id} if emp_id is not None else {}

        # mes objetivo: último mes con Real (del scope)
        maxd = c.execute(sa.text(f"""
            SELECT MAX(f.fecha) FROM core.fact_produccion_diaria f
            JOIN core.dim_tipo_registro tr ON tr.tipo_id = f.tipo_id
            WHERE tr.nombre = 'Real' {wemp}"""), pe).scalar()
        if maxd is None:
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        y, mo = maxd.year, maxd.month
        dim = calendar.monthrange(y, mo)[1]
        ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"

        pr = dict(pe); pr["ini"] = ini; pr["fin"] = fin
        rows = c.execute(sa.text(f"""
            SELECT f.fecha, em.nombre AS empresa, tp.nombre AS prod, tr.nombre AS tipo,
                   f.valor_produccion AS val
            FROM core.fact_produccion_diaria f
            JOIN core.dim_empresa em ON em.empresa_id = f.empresa_id
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = f.producto_id
            JOIN core.dim_tipo_registro tr ON tr.tipo_id = f.tipo_id
            WHERE f.fecha BETWEEN :ini AND :fin {wemp}"""), pr).all()

        por_filial = (emp_id is None)   # global → unidad=filial; con filial → unidad=producto
        real_dayset = {r.fecha.isoformat() for r in rows if r.tipo == "Real"}

        agg = defaultdict(lambda: {"real": 0.0, "prog": 0.0})
        curva_real = defaultdict(float)
        curva_prog = defaultdict(float)
        for r in rows:
            unidad = r.empresa if por_filial else r.prod
            iso = r.fecha.isoformat()
            v = float(r.val or 0)
            if r.tipo == "Real":
                agg[unidad]["real"] += v
                curva_real[iso] += v
            elif r.tipo == "Programa":
                curva_prog[iso] += v
                if iso in real_dayset:                 # FIL2: solo días con Real
                    agg[unidad]["prog"] += v

        orden = ["America", "Hocol", "Permian"] if por_filial else ["CRUDO", "GAS", "BLANCOS"]
        por_unidad = []
        for u in orden:
            if u not in agg:                            # DF3: sin tarjetas en 0
                continue
            real = agg[u]["real"]; prog = agg[u]["prog"]
            cumpl = round(real / prog * 100.0, 1) if prog else None
            por_unidad.append({"unidad": u, "real": real, "programa": prog, "cumplimiento": cumpl})

        fechas = sorted(set(list(curva_real.keys()) + list(curva_prog.keys())))
        serie_real = [curva_real.get(f) for f in fechas]     # None en días sin Real → gap en Plotly (FIL4)
        serie_prog = [curva_prog.get(f) for f in fechas]

        return {
            "entidad": entidad, "encontrada": True,
            "escala": "filial" if por_filial else "producto",
            "mes": {"anio": y, "mes": mo, "nombre": MESES_ES[mo],
                    "dias_real": len(real_dayset), "dias_del_mes": dim,
                    "completo": len(real_dayset) >= dim},
            "por_unidad": por_unidad,
            "curva": {"fechas": fechas, "real": serie_real, "programa": serie_prog},
        }
```

### 6.2 Flask — proxy en `routes\api.py`

**Insertar tras** `analisis_desempeno` (o tras `analisis_huella`):

```python
@api_bp.route("/analisis/desempeno_filiales")
def analisis_desempeno_filiales():
    """Proxy: desempeño del mes de filiales (Real vs Programa)."""
    try:
        params = {}
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno_filiales", params=params, timeout=45)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

### 6.3 Frontend — `multitab_shell.js`

**(a) Enrutar el botón "Analizar" por rama.** Buscar el bloque del botón (introducido por el plan de
desempeño ECP):

```js
      var entArg = (it.valor || it.entidad || "").replace(/'/g, "\\'");
      var btnAnalizar = '<li><button type="button" class="rb-chat__option" onclick="window.__cnAnalizar(\'' + entArg + '\')">' +
```

Reemplazar esas 2 líneas por (añade la rama y llama al router):

```js
      var entArg = (it.valor || it.entidad || "").replace(/'/g, "\\'");
      var ramaArg = (it.rama || "").replace(/'/g, "\\'");
      var btnAnalizar = '<li><button type="button" class="rb-chat__option" onclick="window.__cnAnalizarEntidad(\'' + entArg + '\',\'' + ramaArg + '\')">' +
```

**(b) Router + funciones de render Filiales.** Insertar ESTE bloque JUSTO ANTES del comentario
`// ---- Panorama: densidad (KPIs + matriz de días, CSS puro, sin Plotly) ----`:

```js
  // Router de "Analizar {entidad}": rama B (filial) → panel Filiales; otra → panel ECP.
  window.__cnAnalizarEntidad = function (entidad, rama) {
    if (rama === "B") window.__cnFiliales(entidad);
    else window.__cnAnalizar(entidad);
  };

  // ============================================================
  // Consulta · Desempeño del mes — FILIALES (Real vs Programa). Reusa el layout .cn-desemp*.
  // ============================================================
  var __cnFilData = null;

  window.__cnFiliales = function (entidad) {
    var a = __cnViewerArea(); if (!a) return;
    var backBtn = __cnLastIntent
      ? '<button type="button" class="cn-rep__back" onclick="window.__cnVolverPanorama()">' +
        '<i class="bi bi-arrow-left"></i> Volver al panorama</button>' : '';
    a.innerHTML =
      '<div class="cn-desemp">' +
      '  <div class="cn-rep__bar">' + backBtn +
      '    <span class="cn-rep__date"><i class="bi bi-building"></i> Desempeño de ' + esc(entidad) + ' · Filial (Real vs Programa)</span>' +
      '  </div>' +
      '  <div id="cn-desemp-body" class="cn-desemp__body">' +
      '    <div class="d-flex align-items-center gap-2 p-3 text-muted small">' +
      '      <div class="spinner-border spinner-border-sm"></div> Calculando desempeño de la filial…</div></div>' +
      '</div>';
    fetch("/api/analisis/desempeno_filiales" + (entidad ? "?entidad=" + encodeURIComponent(entidad) : ""))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var body = el("cn-desemp-body"); if (!body) return;
        if (!d || d.encontrada === false) { body.innerHTML = '<div class="p-3 text-muted small">No reconocí «' + esc(entidad || "") + '» como filial.</div>'; return; }
        if (d.sin_datos) { body.innerHTML = '<div class="p-3 text-muted small">Sin producción de filiales para este scope.</div>'; return; }
        __cnFilData = d;
        body.innerHTML = __cnRenderFiliales(d);
        __cnFilCurvaPlot();
      })
      .catch(function () {
        var body = el("cn-desemp-body");
        if (body) body.innerHTML = '<div class="alert alert-danger m-3">Error calculando el desempeño de filiales.</div>';
      });
  };

  function __cnRenderFiliales(d) {
    var m = d.mes || {};
    var etiqueta = esc(m.nombre) + " " + m.anio + (m.completo ? "" : " · a la fecha (" + m.dias_real + "/" + m.dias_del_mes + ")");
    var cards = "", bars = "";
    (d.por_unidad || []).forEach(function (p) {
      var sem = __cnSemColor(p.cumplimiento);
      var pct = (p.cumplimiento == null) ? "—" : (p.cumplimiento + "%");
      cards +=
        '<div class="cn-desemp__kpi ' + sem + '">' +
        '  <div class="cn-desemp__kpi-prod">' + esc(p.unidad) + '</div>' +
        '  <div class="cn-desemp__kpi-real">' + __cnMilesEC(p.real) + '</div>' +
        '  <div class="cn-desemp__kpi-sub">Real a la fecha</div>' +
        '  <div class="cn-desemp__kpi-cumpl ' + sem + '">' + pct + ' <span>del programa</span></div>' +
        '</div>';
      var w = (p.cumplimiento == null) ? 0 : Math.max(0, Math.min(100, p.cumplimiento));
      bars +=
        '<div class="cn-desemp__bar-row">' +
        '  <div class="cn-desemp__bar-lbl">' + esc(p.unidad) + '</div>' +
        '  <div class="cn-desemp__bar-track"><div class="cn-desemp__bar-fill ' + sem + '" style="width:' + w + '%"></div></div>' +
        '  <div class="cn-desemp__bar-val">' + __cnMilesEC(p.real) + ' / ' + __cnMilesEC(p.programa) + '</div>' +
        '</div>';
    });
    var curva =
      '<div class="cn-desemp__card">' +
      '  <div class="cn-desemp__card-hd"><span><i class="bi bi-graph-up"></i> Real vs Programa · ' +
      m.dias_real + '/' + m.dias_del_mes + ' días</span></div>' +
      '  <div id="cn-desemp-plot" class="cn-desemp__plot"></div>' +
      '  <div class="cn-desemp__foot"><strong>Real</strong> (línea) se corta en el último día con dato; ' +
      '<strong>Programa</strong> cubre el mes completo. Suma de <strong>todos los productos</strong> del scope ' +
      '(el desglose por producto está en las tarjetas). El % de cada tarjeta compara Real vs Programa sobre los mismos días — FIL8.</div>' +
      '</div>';
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__layout">' +
      '  <div class="cn-desemp__kpis">' + cards + '</div>' +
      '  <div class="cn-desemp__right">' +
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Programa (a la fecha)</span></div>' +
      '      <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva +
      '  </div>' +
      '</div>'
    );
  }

  // Curva Filiales: 2 líneas (Real sólida + Programa punteada), con leyenda.
  window.__cnFilCurvaPlot = function () {
    var d = __cnFilData, elp = el("cn-desemp-plot");
    if (!d || !elp) return;
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    var x = d.curva.fechas;
    Plotly.newPlot(elp, [
      { x: x, y: d.curva.real, name: "Real", type: "scatter", mode: "lines+markers",
        line: { color: "#1f6b4a", width: 2 }, marker: { size: 3 },
        hovertemplate: "%{x}<br>Real %{y:,.0f}<extra></extra>" },
      { x: x, y: d.curva.programa, name: "Programa", type: "scatter", mode: "lines",
        line: { color: "#9aa7a0", width: 2, dash: "dash" },
        hovertemplate: "%{x}<br>Programa %{y:,.0f}<extra></extra>" }
    ], {
      margin: { l: 54, r: 10, t: 6, b: 30 }, height: 150,
      showlegend: true, legend: { orientation: "h", y: 1.18, x: 0, font: { size: 10 } },
      xaxis: { tickangle: -45, tickfont: { size: 10 } },
      yaxis: { tickfont: { size: 10 }, separatethousands: true },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)"
    }, { displayModeBar: false, responsive: true });
  };

```

### 6.4 `main.html` — cache-buster

**Buscar:** `...multitab_shell.js') }}?v=20260709k"></script>`
**Reemplazar por:** `...multitab_shell.js') }}?v=20260709l"></script>`

---

## 7. Orden de ejecución

1. `analisis\api.py` §6.1 (endpoint).
2. `routes\api.py` §6.2 (proxy).
3. **Reiniciar backend INGESTA `:8000`** (código Python nuevo). Recargar Flask `:8020` si no está con `--reload`.
4. `multitab_shell.js` §6.3 (a)+(b).
5. `main.html` §6.4 (cache-buster).
6. Navegador **Ctrl+F5**.

---

## 8. Reglas no negociables

- **Solo lectura**; NO tocar DDL/ETL/grano.
- **DF1/FIL2:** eje Real vs Programa; cumplimiento sobre días con Real (NO 17 vs 31).
- **DF4/FIL5:** el botón "Analizar" enruta por `it.rama`; NO cambiar la carga GLOBAL (sigue ECP).
- **NO** tocar el panel ECP (`__cnAnalizar`), "Ver el reporte de un día", ni el chatbot principal.
- **Sin CSS nuevo:** reusar `.cn-desemp*`. Vanilla JS ES5. Plotly ya vendorizado.

---

## 9. Validaciones (comando → resultado)

**V1 — Sintaxis JS:** `node --check ...\static\js\multitab_shell.js` → exit 0.

**V2 — Endpoint por filial (backend):**
`curl "http://localhost:8000/analisis/desempeno_filiales?entidad=Permian"`
→ `encontrada:true`, `escala:"producto"`, `mes.nombre:"Mayo"`, `mes.dias_real:17`, `por_unidad` con productos
de Permian (BLANCOS/CRUDO/GAS) con `real`,`programa`,`cumplimiento`; `curva.real` con `null` al final y
`curva.programa` completo (31 días). **Sanity (verificado en BD):** Permian CRUDO real=744.227 /
programa=727.695 → **cumplimiento 102.3**; BLANCOS 105.7; GAS 114.8.

**V3 — Endpoint global:** `curl "http://localhost:8000/analisis/desempeno_filiales"`
→ `escala:"filial"`, `por_unidad` = America/Hocol/Permian.

**V4 — Proxy:** `curl "http://localhost:8020/api/analisis/desempeno_filiales?entidad=Hocol"` → mismo JSON.

**V5 — Navegador:** Consulta → "Hocol" → elegir opción **filial** (rama B) → **"Analizar HOCOL"**
→ panel Filiales: KPI cards por producto + barras Real vs Programa + curva de **2 líneas** (Real sólida
corta en el día 17, Programa punteada mes completo, leyenda). "← Volver al panorama" funciona.

**V6 — Enrutado ECP intacto:** resolver "Castilla" (campo, ECP) → "Analizar CASTILLA" sigue mostrando el
panel **ECP** (Real vs Presupuesto), NO el de filiales.

**V7 — No regresión:** carga global ECP, "Ver el reporte de un día", Ingesta/Control/Análisis OK. 0 errores consola.

---

## 10. Fuera de alcance (Fase 2)

- **PPTO de filiales** (hoy NULL) → cuando se cargue, añadir Real vs Presupuesto además de vs Programa.
- **POP mensual** (`fact_plan_mensual`) y **promedios YTD** (`fact_promedio_validado`) como módulos de contexto.
- **Selector de unidad/producto** en la curva (hoy es el total del scope).
- **Exploración/segmento Exploración** (VEX) — fuera del grano actual de filiales.
- Toggle explícito "ECP | Filiales" (hoy el enrutado es automático por rama).
```
