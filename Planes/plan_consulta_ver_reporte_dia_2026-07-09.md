# Plan ejecutable — Consulta · "Ver el reporte de un día" (árbol + visor de tabla)

> **Cobertura:** N/A (feature de UI; NO toca ingesta, DDL, ETL ni tablas de la fuente).
> **Tipo:** solo frontend (JavaScript + CSS + cache-buster). **Sin cambios de backend.**
> **Estado:** v2 auditado (flujo profesional §0.2). Hallazgos F1–F8 incorporados abajo.

---

## 1. Contexto

Proyecto **ProdIA / INGESTA**. El **MultiTab Shell** (`static/js/multitab_shell.js`) tiene 4 pestañas
(Ingesta / Control / Análisis / **Consulta**). En la pestaña **Consulta**, el chat vive en el panel
IZQUIERDO y el visor de "respuestas elaboradas" en el DERECHO (`#cn-viewer-area`).

Cuando el usuario resuelve una entidad (ej. *Castilla*), aparece la tarjeta **"Entidad identificada"**
con dos acciones. Una de ellas, **"Ver el reporte de un día"**, muestra un `<input type="date">`
acotado al rango de la huella y validado contra los días con reporte (`__cnValidarDia` +
`__cnDiasByEnt`). **Hoy ese input NO hace nada útil** (el contenedor dispara el placeholder
`__cnEnDiseno` → "En diseño — pronto").

El objetivo es **conectar** ese selector: al elegir una fecha válida, el visor DERECHO muestra
**dos tarjetas lado a lado**:

- **Izquierda — Árbol del reporte:** todas las hojas/tablas de ese día (como la pestaña Control).
- **Derecha — Visor de la tabla:** la tabla que el usuario elige en el árbol (como el visor de
  Control/Ingesta, reusando `renderTablaAncha`).

Todo se apoya en endpoints y funciones que **ya existen** (ver §4). El único cambio de datos es
resolver `fecha → reporte_id`.

---

## 2. Objetivo

En la pestaña **Consulta**, al seleccionar una fecha válida en **"Ver el reporte de un día"**:

1. Resolver el `reporte_id` de esa fecha (vía `/api/ingesta/check_existing`).
2. Pintar en `#cn-viewer-area` dos tarjetas: **árbol** (hojas/tablas del reporte) + **visor de tabla**.
3. Al hacer clic en una tabla del árbol → renderizarla en la tarjeta derecha.
4. Un enlace **"← Volver al panorama"** restaura el dashboard (Densidad + Cobertura) de la entidad.

**Sin backend nuevo. Sin tocar la ruta numérica de la Fase 3 (el "número real" sigue pendiente).**

---

## 3. Prerequisitos

- Backend INGESTA (`:8000`) y Flask (`:8020`) arriba (`iniciar_backends.bat`).
- BD con al menos un reporte que tenga hojas modeladas (`core.fact_tabla_hoja` con filas) para poder
  ver el árbol con tablas. (Los reportes "solo encabezado" devuelven árbol vacío → se maneja con un
  mensaje, ver F-handling.)
- Navegador con login (bypass dev). Entrar a la pestaña **Consulta** y resolver una entidad con grano
  diario ECP (rama A), p. ej. escribir **"produccion de Castilla"** → aparece "Ver el reporte de un día".

---

## 4. Inventario de archivos (lo que se toca y lo que se reutiliza)

**Se MODIFICA:**

| Archivo (ruta absoluta) | Cambio |
|---|---|
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` | 1 edición + 1 bloque nuevo de funciones |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\css\colapsable.css` | 1 bloque CSS nuevo (append) |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html` | bump del cache-buster de `multitab_shell.js` |

**Se REUTILIZA tal cual (NO se toca):**

- Endpoint proxy `GET /api/ingesta/check_existing?fecha=YYYYMMDD` → `{exists, reporte_id, archivo, tipo, ingested_at}`
  (`routes/api.py:45`). ⚠️ **Exige `fecha` con `\d{8}` SIN guiones** (ver F1).
- Endpoint proxy `GET /api/tablas-hoja/arbol/<int:reporte_id>` → `{hojas:[{hoja, tablas:[{tabla_idx, tabla_label, filas}]}]}`
  (`routes/api.py:127`).
- Endpoint proxy `GET /api/tablas-hoja/datos?reporte_id=&hoja=&tabla_idx=` (`routes/api.py:104`).
- `window.renderTablaAncha(area, data, titulo)` de `static/js/chat.js:487` — **ya recibe `area` como
  parámetro** (no está atado a un id fijo). Cargado DESPUÉS de `multitab_shell.js` en `main.html`.
- `window.__ctToggle(hd)` de `multitab_shell.js:199` — expand/collapse genérico (solo togglea `is-open`).
- Helpers en scope del IIFE de `multitab_shell.js`: `el(id)`, `esc(s)`, `nfCtrl(n)`, `__cnFmtFecha(iso)`,
  `__cnViewerArea()`, `__cnDashboard(intent)`, `__cnDashHint(txt)`, var `__cnLastIntent`, `window.__cnValidarDia(input)`.
- Estilos existentes `.ct-node/.ct-hd/.ct-hd--leaf/.ct-chev/.ct-kids/.ct-leaf`, `.ig-trow/.ig-trow__name`,
  `.ig-badge/.ig-badge--gray`, `.ig-dt*` (tabla), `.rb-cp-vempty*` (estado vacío).

---

## 5. Hallazgos de auditoría incorporados (F1–F8)

- **F1 (CRÍTICO) — Formato de fecha:** el `<input type="date">` entrega `value` en **`YYYY-MM-DD`**,
  pero `check_existing` hace `re.search(r"\d{8}", fecha)` → **no matchea con guiones**. Solución:
  `var yyyymmdd = v.replace(/-/g, "");` antes de llamar al endpoint.
- **F2 — No reusar `verTablaHoja`:** `window.verTablaHoja` (chat.js:467) está **hardcodeado a
  `#charts-display-area`** (visor de Ingesta/Control, que en Consulta no es el destino). Se crea
  `window.__cnVerTabla` que reusa **`renderTablaAncha`** apuntando a la tarjeta derecha de Consulta.
- **F3 — No reusar `buildHojasHtml`:** genera `onclick="window.verTablaHoja(...)"`. Se clona como
  `__cnBuildHojas` con `onclick="window.__cnVerTabla(...)"`. (El expand/collapse sí reusa `__ctToggle`.)
- **F4 — Volver al panorama:** el botón llama `window.__cnDashboard(__cnLastIntent)`. ⚠️ Esto
  **re-dispara** la carga de Densidad + Cobertura (la Cobertura es un ILIKE ~10s). Es el MISMO costo
  que ya ocurre al cambiar de pestaña y volver → aceptable para v1. Documentado en Fuera de alcance.
- **F5 — Rewire del onchange:** cambiar `onchange="window.__cnValidarDia(this)"` →
  `onchange="window.__cnVerReporteDia(this)"` (que internamente **llama a `__cnValidarDia` primero**,
  preservando la validación y el mensaje de "día sin reporte"). Y quitar el `onclick` placeholder
  `__cnEnDiseno` del contenedor de ese botón (ya deja de ser placeholder). El botón **"Analizar {ent}"
  SIGUE siendo placeholder** (`__cnEnDiseno`) — NO tocar.
- **F6 — Reporte solo-encabezado:** si el árbol viene vacío (`hojas.length === 0`, típico de días
  "de vitrina"), mostrar "Sin hojas modeladas para este reporte." (no error).
- **F7 — Transitorio:** la vista de reporte del día NO se persiste al cambiar de pestaña; al volver a
  Consulta, `renderViewer()` repinta el dashboard vía `__cnLastIntent` (comportamiento actual). OK v1.
- **F8 — Helpers en scope:** `esc`, `nfCtrl`, `el`, `__cnFmtFecha`, `__cnViewerArea`, `__cnDashboard`,
  `__cnDashHint`, `__cnLastIntent` están todos en el MISMO IIFE. El bloque nuevo se inserta DESPUÉS de
  `__cnLoadCobertura` (todos definidos arriba) → sin problemas de referencia.

---

## 6. Especificación (código exacto)

### 6.1 EDIT en `multitab_shell.js` — rewire del botón "Ver el reporte de un día"

**Buscar este bloque EXACTO** (está dentro del `if (d.status === "completo")`, ~línea 1194):

```js
      var btnDia = "";
      if (h.aplica) {
        btnDia = '<li><div role="button" class="rb-chat__option" onclick="window.__cnEnDiseno(this)">' +
          '<span class="rb-chat__option-tile"><i class="bi bi-calendar-event"></i></span>' +
          '<div class="rb-chat__option-body"><span class="rb-chat__option-title">Ver el reporte de un día</span>' +
          '<span class="rb-chat__option-desc">Consulta puntual de una fecha</span>' +
          '<div class="rb-chat__date" onclick="event.stopPropagation();">' +
          '<input type="date" aria-label="Fecha del reporte" min="' + esc(h.desde) + '" max="' + esc(h.hasta) + '" ' +
          'data-ent="' + esc(it.valor || it.entidad) + '" onchange="window.__cnValidarDia(this)">' +
          '<span class="rb-chat__date-badge">solo días con reporte</span></div>' +
          '</div><i class="rb-chat__option-chev bi bi-chevron-right"></i></div></li>';
      }
```

**Reemplazar por** (quita el placeholder del contenedor y cambia el `onchange`):

```js
      var btnDia = "";
      if (h.aplica) {
        btnDia = '<li><div class="rb-chat__option">' +
          '<span class="rb-chat__option-tile"><i class="bi bi-calendar-event"></i></span>' +
          '<div class="rb-chat__option-body"><span class="rb-chat__option-title">Ver el reporte de un día</span>' +
          '<span class="rb-chat__option-desc">Consulta puntual de una fecha</span>' +
          '<div class="rb-chat__date" onclick="event.stopPropagation();">' +
          '<input type="date" aria-label="Fecha del reporte" min="' + esc(h.desde) + '" max="' + esc(h.hasta) + '" ' +
          'data-ent="' + esc(it.valor || it.entidad) + '" onchange="window.__cnVerReporteDia(this)">' +
          '<span class="rb-chat__date-badge">solo días con reporte</span></div>' +
          '</div><i class="rb-chat__option-chev bi bi-chevron-right"></i></div></li>';
      }
```

### 6.2 EDIT en `multitab_shell.js` — bloque de funciones nuevo

**Buscar este ancla EXACTO** (fin de `__cnLoadCobertura`, ~línea 986, seguido del comentario del
panorama de densidad):

```js
      .catch(function () { var c2 = el("cn-dash-cobertura"); if (c2) c2.innerHTML =
        '<div class="alert alert-danger small mb-0">Error cargando la cobertura.</div>'; });
  };

  // ---- Panorama: densidad (KPIs + matriz de días, CSS puro, sin Plotly) ----
  function __cnPanoDensidad(d) {
```

**Insertar el siguiente bloque ENTRE `};` y el comentario `// ---- Panorama: densidad ...`**
(es decir, justo después del cierre de `__cnLoadCobertura` y antes de `function __cnPanoDensidad`):

```js
  // ============================================================
  // Consulta · "Ver el reporte de un día": 2 tarjetas (árbol + visor de tabla) en el panel DERECHO.
  // Reusa /api/ingesta/check_existing (fecha→reporte_id), /api/tablas-hoja/arbol/<id> y renderTablaAncha.
  // ============================================================

  // onchange del <input type=date>. Valida (reusa __cnValidarDia), resuelve reporte_id y pinta las 2 tarjetas.
  window.__cnVerReporteDia = function (input) {
    if (!input) return;
    window.__cnValidarDia(input);          // valida y limpia el value si el día no tiene reporte
    var v = input.value;                    // ISO YYYY-MM-DD; queda "" si fue rechazado
    if (!v) return;
    var yyyymmdd = v.replace(/-/g, "");      // [F1] check_existing exige \d{8} SIN guiones
    var a = __cnViewerArea(); if (!a) return;
    a.innerHTML =
      '<div class="cn-rep">' +
      '  <div class="cn-rep__bar">' +
      '    <button type="button" class="cn-rep__back" onclick="window.__cnVolverPanorama()">' +
      '      <i class="bi bi-arrow-left"></i> Volver al panorama</button>' +
      '    <span class="cn-rep__date"><i class="bi bi-calendar-event"></i> Reporte del ' + esc(__cnFmtFecha(v)) + '</span>' +
      '  </div>' +
      '  <div class="cn-rep__grid">' +
      '    <div class="cn-rep__tree">' +
      '      <div class="cn-rep__card-hd"><i class="bi bi-diagram-3"></i> Hojas del reporte</div>' +
      '      <div id="cn-rep-tree" class="cn-rep__tree-body">' +
      '        <div class="d-flex align-items-center gap-2 p-2 text-muted small">' +
      '          <div class="spinner-border spinner-border-sm"></div> Cargando hojas…</div></div>' +
      '    </div>' +
      '    <div class="cn-rep__table">' +
      '      <div class="cn-rep__card-hd" id="cn-rep-thd"><i class="bi bi-table"></i> Selecciona una tabla</div>' +
      '      <div id="cn-rep-tabla" class="cn-rep__table-body">' +
      '        <div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
      '          <div class="rb-cp-vempty__chip"><i class="bi bi-hand-index"></i></div>' +
      '          <div class="rb-cp-vempty__eyebrow">Selecciona una tabla</div>' +
      '          <p class="rb-cp-vempty__hint">Haz clic en una tabla del árbol para ver sus datos.</p>' +
      '        </div></div></div>' +
      '    </div>' +
      '  </div>' +
      '</div>';
    fetch("/api/ingesta/check_existing?fecha=" + yyyymmdd)
      .then(function (r) { return r.json(); })
      .then(function (info) {
        var treeEl = el("cn-rep-tree");
        if (!info || !info.exists || info.reporte_id == null) {
          if (treeEl) treeEl.innerHTML = '<div class="p-2 text-muted small">No hay reporte ingerido para esta fecha.</div>';
          return;
        }
        return fetch("/api/tablas-hoja/arbol/" + info.reporte_id)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            var hojas = (data && data.hojas) || [];
            var t2 = el("cn-rep-tree"); if (!t2) return;
            t2.innerHTML = hojas.length
              ? '<ul class="ct-root">' + __cnBuildHojas(info.reporte_id, hojas) + '</ul>'
              : '<div class="p-2 text-muted small">Sin hojas modeladas para este reporte.</div>';   // [F6]
          });
      })
      .catch(function () {
        var t3 = el("cn-rep-tree");
        if (t3) t3.innerHTML = '<div class="p-2 text-danger small">Error cargando el reporte.</div>';
      });
  };

  // Vuelve del reporte del día al Panorama (Densidad + Cobertura) de la entidad ya resuelta. [F4]
  window.__cnVolverPanorama = function () {
    if (__cnLastIntent) window.__cnDashboard(__cnLastIntent);
    else __cnDashHint("Elige una entidad para ver su panorama.");
  };

  // [F3] Clon de buildHojasHtml (Control) pero con onclick a __cnVerTabla (NO verTablaHoja, atado a
  // #charts-display-area). Reusa __ctToggle (genérico) y los estilos .ct-*/.ig-trow/.ig-badge.
  function __cnBuildHojas(reporteId, hojas) {
    var h = "";
    hojas.forEach(function (hoja) {
      h += '<li class="ct-node ct-hoja">' +
        '<div class="ct-hd ct-hd--leaf" onclick="window.__ctToggle(this)">' +
        '<i class="bi bi-chevron-right ct-chev"></i>' +
        '<i class="bi bi-file-earmark"></i> ' + esc(hoja.hoja) +
        ' <span class="ig-badge ig-badge--gray">' + hoja.tablas.length +
        (hoja.tablas.length === 1 ? " tabla" : " tablas") + '</span></div>' +
        '<ul class="ct-kids">';
      hoja.tablas.forEach(function (t) {
        h += '<li class="ct-leaf">' +
          '<button type="button" class="ig-trow" onclick="window.__cnVerTabla(' +
          reporteId + ',\'' + esc(hoja.hoja).replace(/'/g, "\\'") + '\',' +
          t.tabla_idx + ',\'' + esc(t.tabla_label).replace(/'/g, "\\'") + '\')">' +
          '<i class="bi bi-table"></i>' +
          '<span class="ig-trow__name">' + esc(t.tabla_label) + '</span>' +
          '<span class="ig-badge ig-badge--gray">' + nfCtrl(t.filas) + ' filas</span>' +
          '</button></li>';
      });
      h += '</ul></li>';
    });
    return h;
  }

  // [F2] Render de la tabla elegida en la tarjeta DERECHA del reporte. Reusa renderTablaAncha (chat.js).
  window.__cnVerTabla = function (reporteId, hoja, tablaIdx, label) {
    var area = el("cn-rep-tabla"); if (!area) return;
    var thd = el("cn-rep-thd");
    if (thd) thd.innerHTML = '<i class="bi bi-table"></i> ' + esc(hoja) + ' — ' + esc(label);
    area.innerHTML = '<div class="d-flex align-items-center gap-2 p-3">' +
      '<div class="spinner-border spinner-border-sm"></div> Cargando tabla…</div>';
    var url = "/api/tablas-hoja/datos?reporte_id=" + encodeURIComponent(reporteId) +
              "&hoja=" + encodeURIComponent(hoja) + "&tabla_idx=" + encodeURIComponent(tablaIdx);
    fetch(url)
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; }); })
      .then(function (res) {
        if (!res.ok) {
          area.innerHTML = '<div class="alert alert-danger m-3">Error: ' +
            esc(String(res.data.error || res.data.detail || res.status)) + '</div>';
          return;
        }
        window.renderTablaAncha(area, res.data, hoja + " — " + label);
      })
      .catch(function (e) {
        area.innerHTML = '<div class="alert alert-danger m-3">Fallo de red: ' + esc(String(e)) + '</div>';
      });
  };

```

### 6.3 APPEND en `colapsable.css` — estilos de las 2 tarjetas

**Agregar al FINAL del archivo** `static\css\colapsable.css`:

```css
/* ============================================================
   Consulta · Reporte de un día (2 tarjetas: árbol + visor de tabla)
   ============================================================ */
.cn-rep { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.cn-rep__bar { display: flex; align-items: center; gap: 12px; padding: 10px 14px;
  border-bottom: 1px solid var(--rb-border, #e3e8e5); flex: 0 0 auto; }
.cn-rep__back { border: 1px solid var(--rb-border, #cdd8d1); background: #fff; border-radius: 8px;
  padding: 5px 10px; font-size: .82rem; color: var(--rb-green, #1f6b4a); cursor: pointer; white-space: nowrap; }
.cn-rep__back:hover { background: var(--rb-green-soft, #eef5f1); }
.cn-rep__date { font-size: .85rem; color: #4a5a52; font-weight: 600; }
.cn-rep__grid { flex: 1 1 auto; min-height: 0; display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr; gap: 12px; padding: 12px 14px; }
.cn-rep__tree, .cn-rep__table { border: 1px solid var(--rb-border, #e3e8e5); border-radius: 10px;
  background: #fff; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.cn-rep__card-hd { flex: 0 0 auto; padding: 9px 12px; font-size: .78rem; font-weight: 700;
  letter-spacing: .02em; text-transform: uppercase; color: #3a4a42;
  background: var(--rb-green-soft, #eef5f1); border-bottom: 1px solid var(--rb-border, #e3e8e5); }
.cn-rep__tree-body { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 8px; }
.cn-rep__table-body { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 10px 12px; }
.cn-rep .ct-root { list-style: none; margin: 0; padding: 0; }
@media (max-width: 720px) {
  .cn-rep__grid { grid-template-columns: 1fr; grid-auto-rows: minmax(180px, auto); }
}
```

> Nota: los `var(--rb-*, #hex)` llevan **fallback hex**; si el proyecto usa otro nombre de token,
> el fallback aplica igual (no rompe). El Executor PUEDE alinear los nombres a los tokens reales del
> archivo si existen (`--rb-green`, `--rb-green-soft`, `--rb-border`), pero NO es obligatorio.

### 6.4 EDIT en `main.html` — cache-buster

**Buscar** (línea ~82):

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260709g"></script>
```

**Reemplazar por:**

```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260709h"></script>
```

---

## 7. Orden de ejecución

1. Editar `multitab_shell.js` §6.1 (rewire del botón).
2. Editar `multitab_shell.js` §6.2 (bloque de funciones nuevo).
3. Editar `colapsable.css` §6.3 (append CSS).
4. Editar `main.html` §6.4 (cache-buster `g` → `h`).
5. Recargar el navegador con **Ctrl+F5**. (No requiere reiniciar backends: todo es frontend.)

---

## 8. Reglas no negociables

- **NO** tocar backend (endpoints, FastAPI, DDL, ETL). Todo se resuelve con proxies existentes.
- **NO** modificar `window.verTablaHoja` ni `window.buildHojasHtml` (son de Control/Ingesta). Se
  CLONAN con nombres `__cn*`. [F2/F3]
- **NO** convertir la fecha con guiones al llamar `check_existing`: usar `v.replace(/-/g,"")`. [F1]
- **NO** romper la validación de días: `__cnVerReporteDia` DEBE llamar `__cnValidarDia(input)` primero. [F5]
- **NO** tocar el botón "Analizar {entidad}" (sigue placeholder `__cnEnDiseno`).
- **NO** tocar el chatbot principal (`.two-panel-layout`) ni las pestañas Ingesta/Control/Análisis.
- Respetar el estilo del archivo: **vanilla JS ES5** (var, function), sin dependencias nuevas.

---

## 9. Validaciones (comando → resultado esperado)

**V1 — Sintaxis JS:** el archivo carga sin error.
`node --check c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js`
→ sin salida (exit 0).

**V2 — Flujo feliz (navegador):**
1. Login → activar "Análisis avanzado de producción diaria" → pestaña **Consulta**.
2. Escribir **"produccion de Castilla"** → aparece tarjeta "Entidad identificada" con "Ver el reporte de un día".
3. En el `<input type=date>` elegir un día **dentro del rango con dato** (ej. dentro de dic-2025…may-2026).
→ El visor DERECHO muestra la barra "← Volver al panorama" + "Reporte del <fecha>", y **2 tarjetas**:
   izquierda "Hojas del reporte" (con la lista de hojas), derecha "Selecciona una tabla" (estado vacío).

**V3 — Árbol → tabla:** expandir una hoja (ej. *P50 Acumulado*) y hacer clic en una tabla.
→ La tarjeta derecha muestra la tabla (cabecera "Hoja — Tabla", buscador, filas × meses) vía
`renderTablaAncha`. La cabecera `#cn-rep-thd` refleja "Hoja — Tabla".

**V4 — Volver:** clic en "← Volver al panorama".
→ El visor derecho vuelve a mostrar **Densidad + Cobertura** de la entidad (dashboard).

**V5 — Día sin reporte (hueco):** elegir un día del rango pero sin dato.
→ El input se limpia y aparece el mensaje "Ese día no tiene reporte — elige uno con dato." (validación
existente intacta). NO se pintan las tarjetas.

**V6 — Reporte solo-encabezado:** elegir (si aplica) un día cuyo reporte no tenga hojas modeladas.
→ Tarjeta izquierda muestra "Sin hojas modeladas para este reporte." (sin error de consola). [F6]

**V7 — No regresión:** pestañas **Ingesta / Control / Análisis** siguen funcionando; el drill-down de
**Control** (que usa `verTablaHoja` → `#charts-display-area`) sigue pintando en su visor. **0 errores
de consola** en todo el flujo.

---

## 10. Fuera de alcance (explícito)

- **Filtrado del árbol por entidad:** el árbol muestra el reporte COMPLETO del día (todas las hojas),
  no solo donde aparece la entidad. (Decisión del usuario, confirmada con adjuntos.)
- **Persistencia de la vista de reporte** al cambiar de pestaña: es transitoria; al volver a Consulta
  se repinta el dashboard. [F7]
- **Costo de "Volver al panorama":** re-dispara Densidad + Cobertura (ILIKE ~10s). Igual que hoy al
  cambiar de pestaña. Optimización (cachear cobertura) queda fuera. [F4]
- **El "número real"** (Fase 3) y el botón "Analizar {entidad}" siguen como placeholder.
- **Backend / endpoints nuevos:** ninguno.
```
