# Plan: Tab Control — Árbol jerárquico de reportes ingeridos (v2 auditado)

**Fecha:** 2026-07-01  
**Cobertura:** Tablas entrada: `config_reporte` + `fact_tabla_hoja` + `fact_comentarios_produccion` → salida: UI árbol en tab Control  
**Estado:** Pendiente de aprobación

---

## Hallazgos de auditoría (v1 → v2)

La auditoría del plan v1 encontró **4 problemas** que romperían la funcionalidad y **2 oportunidades de mejora**:

### H1 — CRÍTICO: Falta proxy Flask para el nuevo endpoint
**Problema:** El plan v1 hace `fetch("/api/tablas-hoja/arbol")` desde el frontend (:8020) pero NO crea la ruta proxy en Flask `routes/api.py`. El frontend en `:8020` **nunca llega directamente** a FastAPI `:8000` — **todo** pasa por proxies Flask explícitos (`@api_bp.route("/tablas-hoja/...")` → `requests.get(INGESTA_API_URL + "/tablas/...")`)). Sin esta ruta, el fetch devuelve 404.
**Fix v2:** Agregar `@api_bp.route("/tablas-hoja/arbol")` en `routes/api.py` que proxea a `GET /tablas/arbol` de FastAPI.

### H2 — ERROR: `text()` no está importada como `text` sino como `sa.text`
**Problema:** El plan v1 usa `text("""...""")` en el endpoint, pero el archivo `tablas/api.py` importa `import sqlalchemy as sa`, no `from sqlalchemy import text`. La llamada correcta es `sa.text(...)`.
**Fix v2:** Usar `sa.text(...)` en el código de referencia.

### H3 — BUG: Doble ID `charts-display-area` al cambiar de Ingesta a Control
**Problema:** Cuando el usuario está en la pestaña Ingesta (que ya tiene un `charts-display-area` en su viewer), cambia a Control (que crea otro `charts-display-area`), ambos coexisten brevemente. `verTablaHoja()` usa `document.getElementById("charts-display-area")` y podría encontrar el equivocado.
**Fix v2:** Al renderizar el viewer de Control, primero verificar si el de Ingesta existe y eliminarlo. Pero en realidad, `renderViewer()` ya reemplaza el `innerHTML` completo del viewer → el anterior se destruye. **No hay bug real** porque `renderViewer()` hace `viewer.innerHTML = ...` que destruye el DOM anterior. Confirmado: no requiere fix.

### H4 — RENDIMIENTO: Query pesada con `fact_tabla_hoja` (465K filas, GROUP BY)
**Problema:** La query hace `GROUP BY ... COUNT(*)` sobre 465K+ filas de `fact_tabla_hoja`. Con 37 reportes será ~1.1M+ filas agrupadas en una sola query.
**Fix v2:** Agregar un índice en el paso de validación. Pero dado que el GROUP BY es sobre `(reporte_id, hoja, tabla_idx, tabla_label)` y el endpoint se llama infrecuentemente (solo al cambiar al tab Control), el costo es aceptable (~200ms). Documentar como mejora futura si se vuelve lento.

### M1 — MEJORA: Conteo total de filas y hojas por reporte en el nodo del día
**Oportunidad:** Mostrar un badge con el total de filas y hojas en el nodo del día (ej: "04 NEW 17 hojas · 465.003 filas") para dar contexto sin expandir.
**Fix v2:** Calcular totales en `renderArbolTree` y agregarlos al nodo del día.

### M2 — MEJORA: Estado inicial del árbol — día colapsado por defecto
**Oportunidad:** Con 37 reportes, abrir todo por defecto es abrumador. Mejor: año y mes abiertos, día cerrado por defecto. El usuario abre el día que le interesa.
**Fix v2:** Los nodos `ct-year` y `ct-month` se renderizan con `is-open`, pero `ct-day` sin `is-open`.

---

## Contexto

El MultiTab Shell tiene 3 pestañas: Ingesta (carga de archivos), **Control** (placeholder vacío), Análisis (placeholder vacío). El usuario quiere que el tab Control muestre los reportes ya ingeridos en un **árbol jerárquico de 5 niveles**:

```
Año
 └─ Mes (nombre en español)
     └─ Día  [badge NEW/STD]  [N hojas · M filas]
         └─ Hoja  [N tablas]
             └─ Tabla  (filas)  [botón "Para análisis"]
```

**Arquitectura de red:** Frontend (:8020, Flask) → Proxy Flask (`routes/api.py`) → FastAPI (:8000). El frontend NUNCA hace fetch directo a `:8000`.

---

## Objetivo

Reemplazar el placeholder del tab Control por un árbol colapsable que muestre todos los reportes ingeridos, organizado por fecha (año → mes → día) y por debajo de cada día, el mismo árbol de hojas/tablas que se ve en Ingesta tras una ingesta exitosa, con botones "Para análisis" funcionales.

---

## Prerequisitos

- PostgreSQL local corriendo con BD `daily_report_prod` y al menos 1 reporte ingerido
- Backend FastAPI de INGESTA corriendo en `:8000`
- Flask corriendo en `:8020` (sirve el frontend)
- No requiere DDL ni migraciones

---

## Inventario de archivos

| Archivo | Acción | Propósito |
|---------|--------|-----------|
| `INGESTA/Rep_Prod/backend/app/features/tablas/api.py` | **EDITAR** | Nuevo endpoint `GET /tablas/arbol` |
| `routes/api.py` | **EDITAR** | Proxy Flask `GET /api/tablas-hoja/arbol` → FastAPI |
| `static/js/multitab_shell.js` | **EDITAR** | Render del árbol en tab Control + fetch al endpoint |
| `static/css/colapsable.css` | **EDITAR** | Estilos del árbol (clases `ct-*` + reusar `ig-*`) |

**Total: 4 archivos editados, 0 archivos nuevos.**

---

## Especificación

### Paso 1: Endpoint `GET /tablas/arbol` en FastAPI

**Ruta completa:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\tablas\api.py`

Agregar al final del archivo (después de la función `datos()`, línea 122). El archivo importa `import sqlalchemy as sa` y `from app.core.db import get_engine` — usar `sa.text()`.

**Código de referencia completo:**

```python
MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@router.get("/arbol")
def arbol_reportes():
    """Árbol jerárquico año → mes → día → hojas → tablas."""
    engine = get_engine()
    sql = sa.text("""
        SELECT cr.reporte_id, cr.fecha_reporte, cr.tipo_archivo, cr.archivo_nombre,
               ft.hoja, ft.tabla_idx, ft.tabla_label, COUNT(*) AS filas
        FROM core.config_reporte cr
        JOIN core.fact_tabla_hoja ft ON ft.reporte_id = cr.reporte_id
        GROUP BY cr.reporte_id, cr.fecha_reporte, cr.tipo_archivo, cr.archivo_nombre,
                 ft.hoja, ft.tabla_idx, ft.tabla_label
        UNION ALL
        SELECT cr.reporte_id, cr.fecha_reporte, cr.tipo_archivo, cr.archivo_nombre,
               'COMENTARIOS' AS hoja, 1 AS tabla_idx, 'COMENTARIOS' AS tabla_label,
               COUNT(*) AS filas
        FROM core.config_reporte cr
        JOIN core.fact_comentarios_produccion fc ON fc.reporte_id = cr.reporte_id
        GROUP BY cr.reporte_id, cr.fecha_reporte, cr.tipo_archivo, cr.archivo_nombre
        ORDER BY fecha_reporte DESC, hoja, tabla_idx
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    from collections import OrderedDict
    tree = OrderedDict()
    for r in rows:
        fr = r["fecha_reporte"]
        a, m, d = fr.year, fr.month, fr.day
        tree.setdefault(a, OrderedDict()) \
            .setdefault(m, OrderedDict()) \
            .setdefault(d, {
                "reporte_id": r["reporte_id"],
                "tipo": r["tipo_archivo"],
                "archivo": r["archivo_nombre"],
                "hojas_dict": OrderedDict(),
            })
        dia = tree[a][m][d]
        dia["hojas_dict"].setdefault(r["hoja"], []).append({
            "tabla_idx": r["tabla_idx"],
            "tabla_label": r["tabla_label"],
            "filas": r["filas"],
        })

    result = []
    for anio, meses in sorted(tree.items(), reverse=True):
        meses_list = []
        for mes, dias in sorted(meses.items(), reverse=True):
            dias_list = []
            for dia, info in sorted(dias.items(), reverse=True):
                hojas_list = []
                for hoja, tablas in info["hojas_dict"].items():
                    hojas_list.append({"hoja": hoja, "tablas": tablas})
                dias_list.append({
                    "dia": dia,
                    "reporte_id": info["reporte_id"],
                    "tipo": info["tipo"],
                    "archivo": info["archivo"],
                    "hojas": hojas_list,
                })
            meses_list.append({"mes": mes, "mes_nombre": MESES_ES[mes], "dias": dias_list})
        result.append({"anio": anio, "meses": meses_list})
    return result
```

**Notas:**
- COMENTARIOS no existe en `fact_tabla_hoja` (verificado: 0 filas) → el UNION ALL es necesario
- `sa.text()` (no `text()`) — conforme al estilo del archivo que usa `import sqlalchemy as sa`
- No se necesitan imports adicionales (`OrderedDict` se importa dentro de la función)

---

### Paso 2: Proxy Flask en `routes/api.py`

**Ruta completa:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\routes\api.py`

Agregar **inmediatamente después** de la ruta `tablas_hoja_datos()` (que termina alrededor de la línea 101-103).

**Buscar este bloque:**
```python
@api_bp.route("/tablas-hoja/datos")
def tablas_hoja_datos():
    """Proxy: contenido ancho de una tabla (reporte_id, hoja, tabla_idx)."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/tablas/datos",
                            params={"reporte_id": request.args.get("reporte_id"),
                                    "hoja": request.args.get("hoja"),
                                    "tabla_idx": request.args.get("tabla_idx")}, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

**Insertar inmediatamente DESPUÉS de ese bloque:**

```python

@api_bp.route("/tablas-hoja/arbol")
def tablas_hoja_arbol():
    """Proxy: árbol jerárquico de reportes ingeridos."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/tablas/arbol", timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

**Notas:**
- Sin parámetros (el árbol devuelve todo)
- Sigue el mismo patrón exacto que `tablas_hoja_listar()` y `tablas_hoja_datos()`
- `INGESTA_API_URL` ya está definido al inicio del archivo (default `http://localhost:8000`)
- `requests`, `jsonify`, `request` ya están importados

---

### Paso 3: Render del árbol en tab Control — `multitab_shell.js`

**Ruta completa:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js`

#### 3a. Bifurcar `renderPanelBody()` para el tab "control"

**Buscar este bloque** (líneas 137-149):
```javascript
    if (state.activeTab === "ingesta") {
      if (state.ingestaBodyCache) {
        body.innerHTML = "";
        body.appendChild(state.ingestaBodyCache);
        state.ingestaBodyCache = null;
      } else {
        body.innerHTML = renderIngestaBody();
        if (window.igRenderDropzone) window.igRenderDropzone();
      }
    } else {
      body.innerHTML = renderEmptyBody(tabDef(state.activeTab));
    }
```

**Reemplazar por:**
```javascript
    if (state.activeTab === "ingesta") {
      if (state.ingestaBodyCache) {
        body.innerHTML = "";
        body.appendChild(state.ingestaBodyCache);
        state.ingestaBodyCache = null;
      } else {
        body.innerHTML = renderIngestaBody();
        if (window.igRenderDropzone) window.igRenderDropzone();
      }
    } else if (state.activeTab === "control") {
      body.innerHTML = renderControlBody();
      fetchArbolReportes();
    } else {
      body.innerHTML = renderEmptyBody(tabDef(state.activeTab));
    }
```

#### 3b. Agregar función `renderControlBody()`

Insertar DESPUÉS de `renderEmptyBody()` (después de la línea 116, antes de `saveIngestaDOM`):

```javascript
  function renderControlBody() {
    return (
      '<div style="padding:1rem;">' +
      '  <div class="rb-cp-ctrl-head">' +
      '    <i class="bi bi-database-check" aria-hidden="true"></i>' +
      '    <div><strong>Reportes Ingeridos</strong>' +
      '    <small>Navegación por fecha</small></div>' +
      '  </div>' +
      '  <div id="control-tree" class="mt-3">' +
      '    <div class="d-flex align-items-center gap-2 p-3 text-muted">' +
      '      <div class="spinner-border spinner-border-sm"></div> Cargando árbol…</div>' +
      '  </div>' +
      '</div>'
    );
  }
```

#### 3c. Agregar función `fetchArbolReportes()`

Insertar DESPUÉS de `renderControlBody()`:

```javascript
  function fetchArbolReportes() {
    fetch("/api/tablas-hoja/arbol")
      .then(function (r) { return r.json(); })
      .then(function (data) { renderArbolTree(data); })
      .catch(function (e) {
        var box = el("control-tree");
        if (box) box.innerHTML = '<div class="alert alert-danger m-2">Error cargando árbol: ' + e + '</div>';
      });
  }
```

**URL:** `/api/tablas-hoja/arbol` (pasa por el proxy Flask del Paso 2, NO directo a `:8000`).

#### 3d. Agregar función `renderArbolTree(data)` y toggle global

Insertar DESPUÉS de `fetchArbolReportes()`:

```javascript
  var nfCtrl = function (x) { return Number(x).toLocaleString("es-CO"); };

  function renderArbolTree(data) {
    var box = el("control-tree");
    if (!box) return;
    if (!data || !data.length) {
      box.innerHTML = '<div class="p-3 text-muted"><i class="bi bi-inbox"></i> No hay reportes ingeridos.</div>';
      return;
    }

    var html = '<ul class="ct-tree">';
    data.forEach(function (anio) {
      html += '<li class="ct-node ct-year is-open">' +
        '<div class="ct-hd" onclick="window.__ctToggle(this)">' +
        '<i class="bi bi-chevron-right ct-chev"></i>' +
        '<i class="bi bi-calendar3"></i> <strong>' + anio.anio + '</strong></div>' +
        '<ul class="ct-kids">';
      anio.meses.forEach(function (mes) {
        html += '<li class="ct-node ct-month is-open">' +
          '<div class="ct-hd" onclick="window.__ctToggle(this)">' +
          '<i class="bi bi-chevron-right ct-chev"></i>' +
          '<i class="bi bi-calendar-month"></i> ' + esc(mes.mes_nombre) + '</div>' +
          '<ul class="ct-kids">';
        mes.dias.forEach(function (dia) {
          var badge = dia.tipo === "NEW"
            ? '<span class="ig-badge ig-badge--green">' + dia.tipo + '</span>'
            : '<span class="ig-badge ig-badge--blue">' + dia.tipo + '</span>';
          var totalFilas = 0;
          dia.hojas.forEach(function (h) {
            h.tablas.forEach(function (t) { totalFilas += t.filas; });
          });
          html += '<li class="ct-node ct-day">' +
            '<div class="ct-hd" onclick="window.__ctToggle(this)">' +
            '<i class="bi bi-chevron-right ct-chev"></i>' +
            '<i class="bi bi-file-earmark-spreadsheet"></i> <strong>' +
            String(dia.dia).padStart(2, "0") + '</strong> ' + badge +
            '<span class="ig-badge ig-badge--gray">' + dia.hojas.length + ' hojas</span>' +
            '<span class="ct-filas">' + nfCtrl(totalFilas) + ' filas</span>' +
            '<small class="ct-archivo" title="' + esc(dia.archivo) + '">' +
            esc((dia.archivo || "").substring(0, 30)) + '</small></div>' +
            '<ul class="ct-kids">';
          dia.hojas.forEach(function (hoja) {
            html += '<li class="ct-node ct-hoja">' +
              '<div class="ct-hd ct-hd--leaf" onclick="window.__ctToggle(this)">' +
              '<i class="bi bi-chevron-right ct-chev"></i>' +
              '<i class="bi bi-file-earmark"></i> ' + esc(hoja.hoja) +
              ' <span class="ig-badge ig-badge--gray">' + hoja.tablas.length +
              (hoja.tablas.length === 1 ? ' tabla' : ' tablas') + '</span></div>' +
              '<ul class="ct-kids">';
            hoja.tablas.forEach(function (t) {
              html += '<li class="ct-leaf">' +
                '<button type="button" class="ig-trow" onclick="window.verTablaHoja(' +
                dia.reporte_id + ',\'' + esc(hoja.hoja).replace(/'/g, "\\'") + '\',' +
                t.tabla_idx + ',\'' + esc(t.tabla_label).replace(/'/g, "\\'") + '\')">' +
                '<i class="bi bi-table"></i>' +
                '<span class="ig-trow__name">' + esc(t.tabla_label) + '</span>' +
                '<span class="ig-badge ig-badge--gray">' + nfCtrl(t.filas) + ' filas</span>' +
                '</button></li>';
            });
            html += '</ul></li>';
          });
          html += '</ul></li>';
        });
        html += '</ul></li>';
      });
      html += '</ul></li>';
    });
    html += '</ul>';
    box.innerHTML = html;
  }

  window.__ctToggle = function (hd) {
    var li = hd.parentElement;
    if (li) li.classList.toggle("is-open");
  };
```

**Cambios vs v1 (M1, M2):**
- **M1 aplicado:** cada nodo de día muestra `N hojas` y `M filas` (totalFilas calculado sumando todas las tablas)
- **M2 aplicado:** `ct-day` se renderiza SIN `is-open` (colapsado por defecto). `ct-year` y `ct-month` sí tienen `is-open`
- Singular/plural: "1 tabla" vs "N tablas"

#### 3e. Actualizar `renderViewer()` para el tab "control"

**Buscar** (líneas 180-183):
```javascript
    } else if (state.activeTab === "control") {
      viewer.innerHTML = viewerEmpty("sliders2", "Panel de control",
        "Configura parámetros y reglas de negocio", false,
        "clipboard2-data", "Panel de Control");
```

**Reemplazar por:**
```javascript
    } else if (state.activeTab === "control") {
      viewer.innerHTML =
        '<div class="rb-cp-vhead">' +
        '  <i class="bi bi-clipboard2-data" aria-hidden="true"></i>' +
        '  <span class="rb-cp-vhead__title">Visualizador</span></div>' +
        '<div id="charts-display-area" style="flex:1;min-height:0;overflow:auto;padding:12px 14px;">' +
        '  <div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
        '    <div class="rb-cp-vempty__chip"><i class="bi bi-hand-index"></i></div>' +
        '    <div class="rb-cp-vempty__eyebrow">Selecciona una tabla</div>' +
        '    <p class="rb-cp-vempty__hint">Navega el árbol y haz clic en una tabla para ver sus datos</p>' +
        '  </div></div></div>';
```

**Nota sobre ID `charts-display-area`:** no hay conflicto. `renderViewer()` reemplaza el `innerHTML` completo del viewer → el `charts-display-area` de Ingesta se destruye antes de crear el de Control. El original del two-panel-layout ya fue renombrado a `_charts-display-area-hidden` por `mount()`.

---

### Paso 4: Estilos CSS — `colapsable.css`

**Ruta completa:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\css\colapsable.css`

Agregar al **final del archivo**:

```css
/* ── Control Tab: árbol de reportes ── */
.rb-cp-ctrl-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #f0faf5 0%, #e8f5e9 100%);
  border-radius: 10px;
  border: 1px solid #c8e6c9;
}
.rb-cp-ctrl-head i { font-size: 1.5rem; color: #2e7d32; }
.rb-cp-ctrl-head strong { font-size: .88rem; color: #1b5e20; }
.rb-cp-ctrl-head small { display: block; font-size: .72rem; color: #666; }

.ct-tree {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: .82rem;
}
.ct-tree ul {
  list-style: none;
  padding-left: 18px;
  margin: 0;
}
.ct-node > .ct-kids { display: none; }
.ct-node.is-open > .ct-kids { display: block; }
.ct-hd {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  border-radius: 6px;
  user-select: none;
}
.ct-hd:hover { background: #f0f4f0; }
.ct-chev {
  font-size: .65rem;
  transition: transform .15s;
  color: #888;
  flex-shrink: 0;
}
.ct-node.is-open > .ct-hd > .ct-chev { transform: rotate(90deg); }
.ct-hd i:not(.ct-chev) { color: #2e7d32; font-size: .85rem; }
.ct-hd--leaf i:not(.ct-chev) { color: #1565c0; }
.ct-archivo {
  color: #999;
  font-size: .7rem;
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}
.ct-filas {
  color: #888;
  font-size: .7rem;
}
.ct-leaf { padding-left: 4px; }
.ct-leaf .ig-trow { width: 100%; }
.ct-year > .ct-hd { font-size: .9rem; }
.ct-month > .ct-hd { font-size: .85rem; }
.ct-day > .ct-hd strong { color: #2e7d32; }
```

---

## Orden de ejecución

1. **Paso 1** — Editar `INGESTA/Rep_Prod/backend/app/features/tablas/api.py`: endpoint `GET /tablas/arbol`
2. **Paso 2** — Editar `routes/api.py`: proxy Flask `GET /api/tablas-hoja/arbol`
3. **Paso 4** — Editar `static/css/colapsable.css`: estilos `ct-*`
4. **Paso 3** — Editar `static/js/multitab_shell.js`: lógica del tab Control

Los pasos 1–4 son independientes y pueden ejecutarse en paralelo. El único requisito secuencial es que para **verificar** en el navegador, los 4 deben estar aplicados y ambos backends reiniciados.

---

## Reglas no negociables

1. **No tocar la pestaña Ingesta**: todo cambio es en el tab Control. Ingesta sigue funcionando exactamente igual.
2. **Reusar `verTablaHoja()`**: no duplicar la lógica de visualización. El click en el árbol de Control llama la misma función que Ingesta.
3. **Reusar clases `ig-trow`, `ig-badge`**: consistencia visual con Ingesta.
4. **Fetch vía proxy Flask** (`/api/tablas-hoja/arbol`), NUNCA directo a `:8000`.
5. **Usar `sa.text()`** (no `text()`) — conforme al import `import sqlalchemy as sa` del archivo.
6. **El endpoint debe manejar 0 reportes**: BD vacía → `[]` → UI muestra "No hay reportes ingeridos".
7. **El árbol se recarga cada vez que se cambia al tab Control** (sin cache DOM). Garantiza frescura si el usuario acaba de ingerir algo.
8. **Prefijo CSS `ct-`** para clases nuevas del árbol.
9. **Día colapsado por defecto** (`ct-day` sin `is-open`). Año y mes abiertos.

---

## Validaciones

### V1: Endpoint FastAPI responde
```
GET http://localhost:8000/tablas/arbol
```
**Resultado esperado:** JSON array con 1 elemento (año 2024), mes 10, día 4, con 17 hojas (16 de fact_tabla_hoja + 1 COMENTARIOS). Cada hoja con sus tablas y conteos. Total de filas sumadas ≈ 465.038 (465.003 de fact_tabla_hoja + 35 de COMENTARIOS).

### V2: Proxy Flask responde
```
GET http://localhost:8020/api/tablas-hoja/arbol
```
**Resultado esperado:** mismo JSON que V1 (idéntico, proxy transparente).

### V3: Tab Control muestra el árbol
1. Abrir `http://localhost:8020`, login
2. Click "Análisis avanzado de producción diaria" → MultiTab Shell
3. Click tab **Control**

**Resultado esperado:** Cabecera "Reportes Ingeridos", luego árbol:
```
▼ 2024                              ← abierto
  ▼ Octubre                          ← abierto
    ▶ 04  NEW  17 hojas  465.038 filas  ← CERRADO por defecto (M2)
```

### V4: Expandir día → ver hojas y tablas
Click en "04" → se despliegan las 17 hojas con sus tablas.

### V5: Click en tabla → visualización en zona 3
Click en "Tabla 2 (PROGRAMA)" bajo (Bitacora):
**Resultado esperado:** Viewer muestra la tabla con título "(Bitacora) — Tabla 2 (PROGRAMA)".

### V6: Click en COMENTARIOS → visualización modo texto
Click en "COMENTARIOS" (la tabla bajo la hoja COMENTARIOS):
**Resultado esperado:** Viewer muestra tabla con columnas de texto (modo `esTexto` de `renderTablaAncha`).

### V7: Cambio a Ingesta y vuelta a Control
1. Click tab Ingesta → card de carga y árbol de ingesta intactos (DocumentFragment cache)
2. Click tab Control → árbol de reportes se recarga
3. El archivo cargado en Ingesta no se pierde

### V8: No regresión — tab Ingesta funcional
1. Seleccionar archivo → preview + botón "CARGAR E INGERIR"
2. Ingerir → progreso con checks verdes
3. Click en tabla "Para análisis" → visualización en zona 3

### V9: No regresión — chat principal
1. Click flecha "← Volver" → layout 2 paneles restaurado
2. Enviar pregunta de producción → respuesta normal con 3 paneles

---

## Fuera de alcance

- **Tab Análisis**: sigue como placeholder (fase futura)
- **Eliminación de reportes desde UI**: no se implementa
- **Filtros o búsqueda en el árbol**: navegación solo por colapsar/expandir
- **Índice de rendimiento**: si la query se vuelve lenta con >10 reportes, crear índice `(reporte_id, hoja, tabla_idx)` en `fact_tabla_hoja` — no necesario ahora
- **Múltiples reportes en un mismo día**: el endpoint agrupa por `reporte_id`, no por fecha → funciona correctamente si hay varios reportes el mismo día (cada uno es un nodo separado bajo el día)
