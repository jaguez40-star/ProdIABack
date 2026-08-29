# PLAN EJECUTABLE — Objetivo Primario: Fundación visible en la pestaña Análisis

> **Modo:** ejecutable por un agente externo (sin contexto ni acceso previo al repo) al pie de la letra.
> **Fecha:** 2026-07-08 · **Diseño de referencia:** `DISENO_CAPA_CONVERSACIONAL.md` (raíz del repo padre).
> **Cobertura:** N/A (no modela hojas Excel ni toca ETL/DDL/grano). Agrega **2 endpoints read-only**
> (`/analisis/catalogo`, `/analisis/densidad`) + **2 proxies Flask** + **relleno de la pestaña Análisis**
> del MultiTab Shell con 2 módulos. **NO usa el LLM** (el Primario es pura data + UI).
> **Auditoría §0.2:** no aplica el pre-audit obligatorio — ningún disparador se cumple (sin cambios de
> esquema/ETL/grano). Igual se corrió una **validación del plan** (§0) contra el código real.

---

## 0. Auditoría de validación del plan (2026-07-08)

Verificado contra el código real ANTES de dar el plan por bueno:

- ✅ `backend/app/main.py`: los `include_router` van antes de `app.mount("/", StaticFiles...)` → el router
  `analisis` no queda tapado por el static.
- ✅ Blueprint Flask `api_bp` registrado con `url_prefix="/api"` (`app.py`) → `/api/analisis/*` es correcto.
- ✅ Las 4 features existentes tienen `__init__.py` → **A1 (crear `analisis/__init__.py`) es obligatorio**.
- ✅ Plotly se carga global en `templates/base.html` (vendored + fallback CDN) y `main.html` extiende
  `base.html` → `window.Plotly` disponible; el heatmap renderiza (el fallback queda como defensa).
- ✅ `fact_produccion_dia_ecp.fuente_id` es NOT NULL → `COUNT(DISTINCT fuente_id)` es limpio.
- ✅ Anclas de los 3 cambios en `multitab_shell.js` coinciden con el archivo real; `nfCtrl`/`esc`/`el`
  en scope; funciones hoisteadas; sin colisión con la delegación `[data-action]` del panel.

Reformulaciones aplicadas tras la auditoría (mejoras, no correcciones de rotura):
- **H1** severidad: `gerencia` cuenta como colisión **dura** (misma magnitud de agregación que `activo`).
- **H2** densidad: heatmap coloreado por **# de pozos (`fuentes`) con data/día** (cobertura real), no por
  conteo de filas.
- **H3** semáforo: se devuelve como **lista ordenada de 5 familias** `{familia, nivel, necesita_continuidad}`.
- **H4** UI catálogo: etiqueta explícita "Jerarquía ECP" + lista de Filiales (árbol disjunto).
- **H5** forward: se documenta `/analisis/resolver` como necesidad del Secundario (fuera de este plan).

---

## 1. Contexto

- **Repo padre (Flask, ProdIA):** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
  - Flask corre en `http://localhost:8020` (arranca con `iniciar_backends.bat`).
  - Proxy a INGESTA en `routes/api.py` (blueprint `api_bp`, base `INGESTA_API_URL=http://localhost:8000`).
  - MultiTab Shell: `static/js/multitab_shell.js` (window.MultiTabShell). CSS: `static/css/colapsable.css`.
- **Sub-proyecto INGESTA (FastAPI):** `...\INGESTA\Rep_Prod\backend\`
  - FastAPI corre en `http://localhost:8000` (`uv run uvicorn app.main:app --port 8000 --reload`).
  - BD Postgres local `daily_report_prod` (conexión vía `.env`, leída por `app.core.db.get_engine()`).
  - Vertical slicing: cada feature = `backend/app/features/<nombre>/api.py` con `router = APIRouter(...)`,
    registrado en `backend/app/main.py`.
- **Datos ya cargados (verificado):** 138 reportes NEW (Ene–May 2026). `core.dim_fuente` = 253 filas.
  `core.fact_produccion_dia_ecp` ~435K filas. `core.dim_tipo_producto` = {CRUDO, GAS, BLANCOS} (NO hay agua).

## 2. Objetivo

En la pestaña **Análisis** del MultiTab Shell, mostrar **2 módulos** con data real de producción:
1. **Catálogo de entidades** (de `dim_fuente` + `dim_vicepresidencia` + `dim_empresa`): cardinalidad por
   nivel, resumen de colisiones (dura/media/blanda) y la lista de nombres que disparan contrapregunta.
2. **Densidad temporal** (de `fact_produccion_dia_ecp`): heatmap calendario, días/huecos por mes, y
   **semáforo por familia estadística**.

Los endpoints son de **doble uso**: el módulo los pinta hoy, y el Objetivo Secundario (slot-filling) los
consumirá después. **Orden interno:** Catálogo primero, Densidad después.

## 3. Prerequisitos

- FastAPI :8000 y Flask :8020 operativos (`iniciar_backends.bat` en la raíz del repo padre).
- Postgres local con `daily_report_prod` poblada (dim_fuente=253, fact_produccion_dia_ecp>0).
- `uv` disponible. NO se requiere Ollama para este plan.
- Verificación previa (debe pasar antes de empezar):
  ```
  curl -s http://localhost:8000/health
  ```
  Esperado: `{"status":"ok"}`

## 4. Inventario de archivos

| # | Archivo | Acción |
|---|---------|--------|
| A1 | `...\INGESTA\Rep_Prod\backend\app\features\analisis\__init__.py` | **CREAR** (vacío) |
| A2 | `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | **CREAR** (código §5.1) |
| A3 | `...\INGESTA\Rep_Prod\backend\app\main.py` | **EDITAR** (registrar router, §5.2) |
| A4 | `...\12112025_prodIA\routes\api.py` | **EDITAR** (2 proxies, §5.3) |
| A5 | `...\12112025_prodIA\static\js\multitab_shell.js` | **EDITAR** (3 cambios, §5.4) |

Ninguna otra ruta se toca. Sin migraciones, sin DDL.

---

## 5. Especificación (código de referencia completo)

### 5.1 · A2 — Crear `backend/app/features/analisis/api.py`

Contenido íntegro del archivo:

```python
from fastapi import APIRouter
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/analisis", tags=["analisis"])

MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Mapeo dim_tipo_producto -> término de negocio del conversacional.
# 'agua' NO existe en dim_tipo_producto (solo CRUDO/GAS/BLANCOS) -> se rechazará en el slot-filling.
PRODUCTOS_VALIDOS = [
    {"termino": "aceite", "dim": "CRUDO"},
    {"termino": "gas", "dim": "GAS"},
    {"termino": "blancos", "dim": "BLANCOS"},
]


def _severidad(niveles):
    """Regla de contrapregunta: dura/media = contrapreguntar; blanda = default 'campo' + aviso.
    'gerencia' se trata como DURA (agrega muchos campos/pozos, misma magnitud que 'activo')."""
    if "activo" in niveles or "gerencia" in niveles:
        return "dura"     # colisiona en nivel de gran agregación (cientos de pozos vs uno)
    if "area" in niveles:
        return "media"    # colisiona area+campo
    return "blanda"       # típicamente campo<->fuente


@router.get("/catalogo")
def catalogo():
    """Catálogo de entidades para el Objetivo Primario (visible) y el Secundario (slot-filling).
    Fuente: core.dim_fuente (jerarquía ECP) + dim_vicepresidencia + dim_empresa (filiales)."""
    eng = get_engine()
    with eng.connect() as c:
        card_rows = c.execute(sa.text("""
            SELECT 'gerencia' nivel, COUNT(DISTINCT NULLIF(TRIM(gerencia),'')) n FROM core.dim_fuente
            UNION ALL SELECT 'activo', COUNT(DISTINCT NULLIF(TRIM(activos),'')) FROM core.dim_fuente
            UNION ALL SELECT 'area',   COUNT(DISTINCT NULLIF(TRIM(grupo1),''))  FROM core.dim_fuente
            UNION ALL SELECT 'campo',  COUNT(DISTINCT NULLIF(TRIM(campo),''))   FROM core.dim_fuente
            UNION ALL SELECT 'fuente', COUNT(DISTINCT NULLIF(TRIM(nombre),''))  FROM core.dim_fuente
        """)).mappings().all()
        card = {r["nivel"]: r["n"] for r in card_rows}
        card["vicepresidencia"] = c.execute(
            sa.text("SELECT COUNT(*) FROM core.dim_vicepresidencia")).scalar() or 0

        col_rows = c.execute(sa.text("""
            WITH niveles AS (
                SELECT DISTINCT UPPER(TRIM(gerencia)) v, 'gerencia' niv FROM core.dim_fuente WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(activos)), 'activo' FROM core.dim_fuente WHERE NULLIF(TRIM(activos),'') IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(grupo1)),  'area'   FROM core.dim_fuente WHERE NULLIF(TRIM(grupo1),'')  IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(campo)),   'campo'  FROM core.dim_fuente WHERE NULLIF(TRIM(campo),'')   IS NOT NULL
                UNION SELECT DISTINCT UPPER(TRIM(nombre)),  'fuente' FROM core.dim_fuente WHERE NULLIF(TRIM(nombre),'')  IS NOT NULL
            )
            SELECT v AS nombre, COUNT(*) n_niveles, array_agg(niv ORDER BY niv) niveles
            FROM niveles GROUP BY v HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC, v
        """)).mappings().all()

        colisiones = []
        resumen = {"dura": 0, "media": 0, "blanda": 0}
        for r in col_rows:
            nivs = list(r["niveles"])
            sev = _severidad(nivs)
            resumen[sev] += 1
            colisiones.append({"nombre": r["nombre"], "niveles": nivs,
                               "n_niveles": r["n_niveles"], "severidad": sev})
        resumen["total"] = len(colisiones)

        filiales = [x[0] for x in c.execute(
            sa.text("SELECT nombre FROM core.dim_empresa ORDER BY nombre")).all()]

    cardinalidad = [{"nivel": k, "n": card.get(k, 0)} for k in
                    ["vicepresidencia", "gerencia", "activo", "area", "campo", "fuente"]]
    return {"cardinalidad": cardinalidad, "productos_validos": PRODUCTOS_VALIDOS,
            "colisiones": colisiones, "resumen_colisiones": resumen, "filiales": filiales}


@router.get("/densidad")
def densidad():
    """Auditoría de densidad temporal sobre core.fact_produccion_dia_ecp (usa idx_dia_fecha)."""
    import calendar
    from collections import OrderedDict

    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text("""
            SELECT fecha, COUNT(*) AS filas, COUNT(DISTINCT fuente_id) AS fuentes
            FROM core.fact_produccion_dia_ecp
            GROUP BY fecha ORDER BY fecha
        """)).mappings().all()

    dias = [{"fecha": r["fecha"].isoformat(), "filas": r["filas"], "fuentes": r["fuentes"]} for r in rows]
    fechas = [r["fecha"] for r in rows]

    por_mes_map = OrderedDict()
    for f in fechas:
        por_mes_map.setdefault((f.year, f.month), set()).add(f.day)
    por_mes = []
    huecos_totales = 0
    for (a, m), dset in por_mes_map.items():
        dim = calendar.monthrange(a, m)[1]
        huecos = dim - len(dset)
        huecos_totales += huecos
        por_mes.append({
            "anio": a, "mes": m, "mes_nombre": MESES_ES[m],
            "dias_con_data": len(dset), "dias_del_mes": dim, "huecos": huecos,
            "rango": ["%04d-%02d-%02d" % (a, m, min(dset)), "%04d-%02d-%02d" % (a, m, max(dset))],
        })

    max_racha = 0
    cur = 0
    prev = None
    for f in fechas:
        cur = cur + 1 if (prev is not None and (f - prev).days == 1) else 1
        max_racha = max(max_racha, cur)
        prev = f

    nivel = "verde" if max_racha >= 20 else ("amarillo" if max_racha >= 7 else "rojo")
    # Semáforo como LISTA ordenada por las 5 familias estadísticas (orden canónico). Movimiento y
    # Anomalías dependen de la racha de días CONTINUOS; las otras 3 funcionan con cualquier data.
    semaforo = [
        {"familia": "La foto (totales/promedios/rankings)", "nivel": "verde", "necesita_continuidad": False},
        {"familia": "El movimiento (Δ%, tendencias, rachas)", "nivel": nivel, "necesita_continuidad": True},
        {"familia": "Concentración / Pareto", "nivel": "verde", "necesita_continuidad": False},
        {"familia": "Anomalías (z-scores, cierres, outliers)", "nivel": nivel, "necesita_continuidad": True},
        {"familia": "Descomposición del cambio (waterfall)", "nivel": "verde", "necesita_continuidad": False},
    ]
    resumen = {
        "total_dias": len(fechas),
        "rango": [fechas[0].isoformat(), fechas[-1].isoformat()] if fechas else [None, None],
        "huecos_totales": huecos_totales, "racha_maxima": max_racha,
    }
    return {"dias": dias, "por_mes": por_mes, "resumen": resumen, "semaforo": semaforo}
```

**Notas de diseño (no cambiar sin escalar):**
- Semáforo (lista ordenada de 5 familias): *foto/concentración/descomposición* siempre verde;
  *movimiento/anomalías* dependen de la racha máxima de días consecutivos (≥20 verde · ≥7 amarillo ·
  resto rojo) porque esas familias requieren días **continuos**.
- Densidad coloreada por `fuentes` (pozos distintos con data ese día) = señal de cobertura real, mejor
  que el conteo de filas. `fact_produccion_dia_ecp` es todo ESCENARIO=REAL (filtrado en el ETL).
- `array_agg` de Postgres llega como lista Python (psycopg) → `list(r["niveles"])` es seguro.

### 5.2 · A3 — Editar `backend/app/main.py` (registrar el router)

**Buscar** el bloque de imports de routers y **añadir** la línea `analisis`:

```python
from app.features.tablas.api import router as tablas_router
```
**Reemplazar por:**
```python
from app.features.tablas.api import router as tablas_router
from app.features.analisis.api import router as analisis_router
```

**Buscar** el bloque de `include_router` y **añadir**:
```python
app.include_router(tablas_router)
```
**Reemplazar por:**
```python
app.include_router(tablas_router)
app.include_router(analisis_router)
```
⚠️ Debe quedar ANTES del `app.mount("/", StaticFiles(...))` final (los routers van antes del static, o el
static tapa la API).

### 5.3 · A4 — Editar `routes/api.py` (2 proxies Flask)

**Buscar** el final del proxy `tablas_hoja_arbol_detalle` (la función que termina con
`return jsonify({"error": f"INGESTA no disponible: {e}"}), 502` justo antes de
`@api_bp.route("/database/info")`) y **añadir DESPUÉS** de esa función (antes de `/database/info`):

```python
@api_bp.route("/analisis/catalogo")
def analisis_catalogo():
    """Proxy: catálogo de entidades (cardinalidad + colisiones) desde INGESTA."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/analisis/catalogo", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502


@api_bp.route("/analisis/densidad")
def analisis_densidad():
    """Proxy: auditoría de densidad temporal desde INGESTA."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/analisis/densidad", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

### 5.4 · A5 — Editar `static/js/multitab_shell.js` (3 cambios)

**CAMBIO 1** — en `renderPanelBody()`, **buscar**:
```javascript
    } else if (state.activeTab === "control") {
      body.innerHTML = renderControlBody();
      fetchArbolReportes();
    } else {
      body.innerHTML = renderEmptyBody(tabDef(state.activeTab));
    }
```
**Reemplazar por:**
```javascript
    } else if (state.activeTab === "control") {
      body.innerHTML = renderControlBody();
      fetchArbolReportes();
    } else if (state.activeTab === "analisis") {
      body.innerHTML = renderAnalisisBody();
    } else {
      body.innerHTML = renderEmptyBody(tabDef(state.activeTab));
    }
```

**CAMBIO 2** — en `renderViewer()`, **buscar** el `else` final:
```javascript
    } else {
      viewer.innerHTML = viewerEmpty("graph-up-arrow", "Análisis",
        "Vistas y KPIs avanzados de producción", true,
        "clipboard2-data", "Análisis Avanzado de Producción Diaria");
    }
```
**Reemplazar por:**
```javascript
    } else if (state.activeTab === "analisis") {
      viewer.innerHTML =
        '<div class="rb-cp-vhead">' +
        '  <i class="bi bi-clipboard2-data" aria-hidden="true"></i>' +
        '  <span class="rb-cp-vhead__title is-gold">Análisis Avanzado de Producción Diaria</span></div>' +
        '<div id="charts-display-area" style="flex:1;min-height:0;overflow:auto;padding:12px 14px;">' +
        '  <div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
        '    <div class="rb-cp-vempty__chip"><i class="bi bi-hand-index"></i></div>' +
        '    <div class="rb-cp-vempty__eyebrow">Selecciona un módulo</div>' +
        '    <p class="rb-cp-vempty__hint">Catálogo de entidades o Densidad temporal</p>' +
        '  </div></div></div>';
    } else {
      viewer.innerHTML = viewerEmpty("graph-up-arrow", "Análisis",
        "Vistas y KPIs avanzados de producción", true,
        "clipboard2-data", "Análisis Avanzado de Producción Diaria");
    }
```

**CAMBIO 3** — **añadir** estas funciones justo ANTES de la línea final
`window.MultiTabShell = { mount: mount, unmount: unmount };`:

```javascript
  // ============ Pestaña ANÁLISIS (Objetivo Primario: catálogo + densidad) ============
  function renderAnalisisBody() {
    return (
      '<div style="padding:1rem;">' +
      '  <div class="rb-cp-ctrl-head">' +
      '    <i class="bi bi-graph-up-arrow" aria-hidden="true"></i>' +
      '    <div><strong>Análisis</strong><small>Fundación de datos</small></div>' +
      '  </div>' +
      '  <div class="mt-3 d-grid gap-2">' +
      '    <button type="button" class="ig-trow" onclick="window.__anShowCatalogo()">' +
      '      <i class="bi bi-diagram-3"></i><span class="ig-trow__name">Catálogo de entidades</span></button>' +
      '    <button type="button" class="ig-trow" onclick="window.__anShowDensidad()">' +
      '      <i class="bi bi-calendar-week"></i><span class="ig-trow__name">Densidad temporal</span></button>' +
      '  </div>' +
      '</div>'
    );
  }

  function __anArea() { return el("charts-display-area"); }
  function __anLoading(msg) {
    var a = __anArea();
    if (a) a.innerHTML = '<div class="d-flex align-items-center gap-2 p-3 text-muted">' +
      '<div class="spinner-border spinner-border-sm"></div> ' + esc(msg) + '</div>';
  }
  function __anError(e) {
    var a = __anArea();
    if (a) a.innerHTML = '<div class="alert alert-danger m-2">Error: ' + esc(String(e)) + '</div>';
  }
  var __anSevBadge = { dura: "ig-badge--green", media: "ig-badge--blue", blanda: "ig-badge--gray" };
  var __anSemColor = { verde: "#198754", amarillo: "#fd7e14", rojo: "#dc3545" };

  window.__anShowCatalogo = function () {
    __anLoading("Cargando catálogo…");
    fetch("/api/analisis/catalogo").then(function (r) { return r.json(); }).then(function (d) {
      var a = __anArea(); if (!a) return;
      var kpis = d.cardinalidad.map(function (x) {
        return '<div style="flex:1;min-width:90px;border:1px solid #dee2e6;border-radius:8px;padding:8px 10px;text-align:center;">' +
          '<div style="font-size:1.4rem;font-weight:700;">' + nfCtrl(x.n) + '</div>' +
          '<div class="text-muted" style="font-size:.72rem;text-transform:uppercase;">' + esc(x.nivel) + '</div></div>';
      }).join("");
      var rc = d.resumen_colisiones;
      var duras = d.colisiones.filter(function (c) { return c.severidad === "dura" || c.severidad === "media"; });
      var filas = duras.map(function (c) {
        return '<tr><td><strong>' + esc(c.nombre) + '</strong></td>' +
          '<td><span class="ig-badge ' + (__anSevBadge[c.severidad] || "ig-badge--gray") + '">' + c.severidad + '</span></td>' +
          '<td class="text-muted small">' + esc(c.niveles.join(", ")) + '</td></tr>';
      }).join("");
      var prods = d.productos_validos.map(function (p) {
        return '<span class="ig-badge ig-badge--green">' + esc(p.termino) + ' (' + esc(p.dim) + ')</span>';
      }).join(" ");
      a.innerHTML =
        '<h6 class="mb-2"><i class="bi bi-diagram-3"></i> Catálogo de entidades</h6>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">' + kpis + '</div>' +
        '<div class="text-muted small mb-2">Jerarquía ECP (VP→gerencia→activo→area→campo→fuente). ' +
        'Filiales aparte: ' + esc(d.filiales.join(", ")) + '.</div>' +
        '<div class="mb-2">Productos válidos (diario): ' + prods +
        ' <span class="text-muted small">— agua NO disponible a grano diario</span></div>' +
        '<div class="mb-2">Colisiones: <strong>' + rc.total + '</strong> total · ' +
        '<span class="ig-badge ig-badge--green">' + rc.dura + ' duras</span> ' +
        '<span class="ig-badge ig-badge--blue">' + rc.media + ' medias</span> ' +
        '<span class="ig-badge ig-badge--gray">' + rc.blanda + ' blandas</span></div>' +
        '<div class="text-muted small mb-1">Requieren contrapregunta (dura + media):</div>' +
        '<table class="table table-sm"><thead><tr><th>Nombre</th><th>Severidad</th><th>Niveles</th></tr></thead>' +
        '<tbody>' + filas + '</tbody></table>';
    }).catch(__anError);
  };

  window.__anShowDensidad = function () {
    __anLoading("Calculando densidad temporal…");
    fetch("/api/analisis/densidad").then(function (r) { return r.json(); }).then(function (d) {
      var a = __anArea(); if (!a) return;
      var res = d.resumen;
      var semHtml = d.semaforo.map(function (s) {
        return '<div style="margin:2px 0;">' +
          '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' +
          (__anSemColor[s.nivel] || "#999") + ';margin-right:6px;"></span>' + esc(s.familia) +
          (s.necesita_continuidad ? ' <span class="text-muted small">(requiere días continuos)</span>' : '') +
          '</div>';
      }).join("");
      var filas = d.por_mes.map(function (m) {
        return '<tr><td>' + esc(m.mes_nombre) + ' ' + m.anio + '</td>' +
          '<td>' + m.dias_con_data + ' / ' + m.dias_del_mes + '</td>' +
          '<td>' + (m.huecos > 0 ? '<span class="text-danger">' + m.huecos + '</span>' : '0') + '</td>' +
          '<td class="small text-muted">' + esc(m.rango[0]) + ' → ' + esc(m.rango[1]) + '</td></tr>';
      }).join("");
      a.innerHTML =
        '<h6 class="mb-2"><i class="bi bi-calendar-week"></i> Densidad temporal</h6>' +
        '<div class="mb-2">Días con data: <strong>' + nfCtrl(res.total_dias) + '</strong> · ' +
        'Rango: ' + esc(res.rango[0]) + ' → ' + esc(res.rango[1]) + ' · ' +
        'Huecos: <strong>' + res.huecos_totales + '</strong> · Racha máx: <strong>' + res.racha_maxima + '</strong> días</div>' +
        '<div class="mb-2 small">Semáforo por familia: ' + semHtml + '</div>' +
        '<div id="an-heatmap" style="width:100%;height:360px;"></div>' +
        '<table class="table table-sm mt-2"><thead><tr><th>Mes</th><th>Días</th><th>Huecos</th><th>Rango</th></tr></thead>' +
        '<tbody>' + filas + '</tbody></table>';
      __anHeatmap(d.por_mes, d.dias);
    }).catch(__anError);
  };

  function __anHeatmap(porMes, dias) {
    var cont = el("an-heatmap");
    if (!cont) return;
    if (!window.Plotly) { cont.innerHTML = '<div class="text-muted small">(Plotly no disponible; ver tabla)</div>'; return; }
    var mp = {}; dias.forEach(function (d) { mp[d.fecha] = d.fuentes; });   // color = # pozos (fuentes) con data ese día
    var y = porMes.map(function (m) { return m.mes_nombre; });
    var z = porMes.map(function (m) {
      var row = [];
      for (var day = 1; day <= 31; day++) {
        var key = String(m.anio) + "-" + String(m.mes).padStart(2, "0") + "-" + String(day).padStart(2, "0");
        row.push(mp[key] !== undefined ? mp[key] : null);
      }
      return row;
    });
    var x = []; for (var day = 1; day <= 31; day++) x.push(day);
    window.Plotly.newPlot(cont, [{
      type: "heatmap", z: z, x: x, y: y, colorscale: "YlGnBu", hoverongaps: false,
      colorbar: { title: "pozos" }
    }], { margin: { l: 70, r: 20, t: 10, b: 40 }, xaxis: { title: "Día del mes", dtick: 1 }, height: 360 },
      { displayModeBar: false });
  }
```

---

## 6. Orden de ejecución

1. Crear `A1` (`__init__.py` vacío) y `A2` (`api.py`).
2. Editar `A3` (`main.py`) — registrar router.
3. Editar `A4` (`routes/api.py`) — 2 proxies.
4. Editar `A5` (`multitab_shell.js`) — 3 cambios.
5. **Reiniciar ambos backends:** ejecutar `iniciar_backends.bat` en la raíz del repo padre
   (`c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`). Esperar a que :8000 y :8020 respondan.
6. Correr las Validaciones (§8).

## 7. Reglas no negociables

- **No** tocar DDL, ETL, ni ninguna tabla `fact_*` en escritura. Todo es **read-only**.
- **No** usar `core.fact_tabla_hoja` (EAV de ~62M filas, lenta). La densidad va sobre
  `core.fact_produccion_dia_ecp` (tipada, ~435K, indexada por `fecha`).
- **No** añadir `agua` a `productos_validos` (no existe en `dim_tipo_producto`).
- Los proxies Flask deben devolver **502** si INGESTA no responde (mismo patrón que los existentes).
- Los `include_router` van **antes** del `app.mount("/", StaticFiles...)`.
- El heatmap debe **degradar** si `window.Plotly` no existe (mostrar la tabla igual, sin romper).
- Respetar el estilo del archivo JS (IIFE, `var`, concatenación de strings, handlers `window.__...`).

## 8. Validaciones (comando → resultado esperado)

**V1 — Endpoint catálogo (FastAPI directo):**
```
curl -s http://localhost:8000/analisis/catalogo
```
Esperado (JSON): `cardinalidad` con `{"nivel":"fuente","n":185}`, `{"nivel":"campo","n":139}`,
`{"nivel":"activo","n":18}`, `{"nivel":"vicepresidencia","n":11}`; `resumen_colisiones.total` ≈ **151**;
> NOTA (corregido 2026-07-08 tras hallazgo del Executor): `dim_vicepresidencia` tiene **11** filas reales
> (no 7). El DDL siembra 7 (VRC/VRO/VAO/VFS/VPI/VEX/VAS) pero el ETL agregó 4 códigos reales de la data
> 2026 (**GGN/GPU/GOX/GGS**, nombre_completo=NULL). Los dominantes en el fact son GGN/GPU/GOX/GGS; de los
> 7 sembrados, 4 (VRC/VRO/VAO/VPI) tienen 0 filas. El endpoint es correcto (reporta el conteo real).
en `colisiones`, `RUBIALES`/`CASTILLA`/`CHICHIMENE`/`CUSIANA`/`APIAY` con `"severidad":"dura"`;
`productos_validos` = aceite/gas/blancos (sin agua).

**V2 — Endpoint densidad (FastAPI directo):**
```
curl -s http://localhost:8000/analisis/densidad
```
Esperado: `dias[]` con `fecha`/`filas`/`fuentes`; `por_mes` con entradas para 2026-01..2026-05
(Enero…Mayo), cada una con `dias_con_data`/`dias_del_mes`/`huecos`; `resumen.total_dias` > 0 y
`resumen.rango` dentro de 2026-01-01…2026-05-31; `semaforo` como **lista de 5** objetos
`{familia, nivel, necesita_continuidad}` (movimiento y anomalías con `necesita_continuidad:true`).

**V3 — Proxies Flask:**
```
curl -s http://localhost:8020/api/analisis/catalogo
curl -s http://localhost:8020/api/analisis/densidad
```
Esperado: mismo JSON que V1/V2 (HTTP 200). Si INGESTA está caído → `{"error":"INGESTA no disponible: ..."}` 502.

**V4 — Frontend (manual, en navegador):**
1. Abrir `http://localhost:8020` (login si aplica).
2. Clic en "Análisis avanzado de producción diaria" → monta el MultiTab Shell.
3. Clic en la pestaña **Análisis** del riel.
4. Zona 2: aparecen 2 botones ("Catálogo de entidades", "Densidad temporal").
5. Clic en **Catálogo** → zona 3 muestra KPIs por nivel + tabla de colisiones duras (Rubiales, etc.).
6. Clic en **Densidad** → zona 3 muestra resumen + semáforo + **heatmap Plotly** + tabla por mes.
7. Botón "Volver" → restaura el layout de 2 paneles sin errores en consola.

**V5 — No regresión:** las pestañas **Ingesta** y **Control** siguen funcionando igual
(cargar archivo / navegar árbol de reportes).

## 9. Fuera de alcance (explícito)

- El **Objetivo Secundario** (slot-filling / pestaña Consulta) — plan aparte.
- La **vista canónica** y la ejecución de consultas (Fase 3).
- Cualquier uso del LLM / Ollama.
- Materializar el catálogo como tabla física (por ahora se computa on-the-fly; `dim_fuente`=253 → barato).
- Filtros/paginación avanzados en las tablas del visor (MVP: lista simple).
- **Forward (Objetivo Secundario):** endpoint `/analisis/resolver?nombre=` que dado CUALQUIER nombre
  devuelva su(s) nivel(es) y severidad (no solo los que colisionan) — necesario para validar entidades
  no ambiguas en el Paso 2 del slot-filling. NO se construye en este plan.

---

## 10. Notas para actualizar la documentación al terminar

- `INGESTA/Rep_Prod/CLAUDE.md` §12: nueva fila de bitácora (feature `analisis`, endpoints
  `/analisis/catalogo` y `/analisis/densidad`).
- `CLAUDE.md` (raíz) §10: fila de bitácora (pestaña Análisis del MultiTab con 2 módulos).
- `DISENO_CAPA_CONVERSACIONAL.md`: marcar Objetivo Primario como implementado; anotar los números
  reales de densidad que arroje V2 (días/huecos por mes).
