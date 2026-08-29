# Plan ejecutable (AUDITADO v2) — Panel derecho «Panorama de Producción» (KPIs + dot-matrix + medidores) · vanilla, NO React

> **Fecha:** 2026-07-09 · **Versión:** 2 (reformulada tras auditoría adversarial)
> **Objetivo:** rediseñar el visualizador del **panel derecho** del chat de Consulta (dashboard de la
> entidad resuelta) según `panelright.md` + mockup: **header/subheader** + **4 KPI cards** + **matriz de
> días (dot-matrix en CSS)** + **cobertura con medidores agrupada por capa** con % por grupo. Paleta verde.
>
> ⚠️ **TRADUCCIÓN DE STACK.** `panelright.md` está escrito para **React 19 + TS + Sass + Vitest**. Nuestro
> panel derecho es **VANILLA JS** en `static/js/multitab_shell.js` (función `__cnDashboard`). **IGNORA**
> §3/§4/§7-Sass/§10-Vitest de la spec. **NO crees** `.tsx`/`.scss` ni app React. Implementa el **diseño** en
> `multitab_shell.js` (funciones NUEVAS del dashboard) + `static/css/colapsable.css` (CSS con `var(--rb-*)`).
> **Frontend puro; sin cambios de backend** (los datos ya existen — ver §0).
>
> **Decisiones cerradas (con el usuario):**
> - **D-BADGE = exacto:** el badge «texto» se pone en TODA hoja resuelta vía landing (coincidencia por
>   texto), es decir todas MENOS las 3 RAW de «Producción ECP» (que son `facts`). El mockup solo lo pone en
>   Bronze, pero Filiales/Modeladas también son text-match → ser exactos es más honesto.
> - **D-SCOPE = solo Consulta:** se cambia SOLO el dashboard del panel derecho de Consulta. La pestaña
>   **Análisis** (que usa `__anRenderDensidad`/`__anHeatmap`/`__anRenderCobertura`) queda **INTACTA**.

---

## §0 · Auditoría — hallazgos YA incorporados

- **F-A · Tokens SIN colisión (verificado en `colapsable.css`):** `--rb-amber-text` (#c77f00) YA existe, pero
  el token nuevo se llama `--rb-amber` (#E8912B) → **nombres distintos, no colisiona**. `--rb-amber-soft`,
  `--rb-gold-soft`, `--rb-layer-*` NO existen → seguros. `--rb-chat-gold` (#C9962E) YA existe → se reusa para el
  KPI dorado + anillo hover (NO usar `--rb-gold`, que es #f2c94c del shell). `.rb-pano` NO existe → sin colisión.
- **F-B · Positivo:** quitar `__anHeatmap` de `__cnDashboard` elimina de paso el uso compartido del id
  `an-heatmap` en la vista de Consulta (menos acoplamiento) y saca Plotly de esta vista (menos RAM).
- **F-C · Caveat:** `por_mes` solo contiene **meses con ≥1 día de dato** (el backend lo construye desde las
  fechas). Un mes intermedio 100% vacío no tendría fila en la matriz. Para el corpus real no ocurre; aceptado.
- **F-D · Header:** se **DROPEA el header verde propio** del panorama (spec §6.1) para no duplicar el
  `rb-cp-vhead` del shell ("CONSULTA DE PRODUCCIÓN (V1)"); se usa SOLO el subheader blanco `.rb-pano__subhead`.
- **F-E · Robustez:** los valores de KPI se leen con `|| 0` defensivo.

### Datos y coherencia

- **Datos disponibles (verificado en `analisis/api.py`):** `/densidad` → `{aplica_ecp, dias[{fecha,filas,fuentes}],
  por_mes[{anio,mes,mes_nombre,dias_con_data,dias_del_mes,huecos,rango}], resumen{total_dias,rango,huecos_totales,
  racha_maxima}}`; `/cobertura` → `{entidad, total_hojas, hojas_con_entidad, categorias[{categoria, hojas[{hoja,
  reportes_total,reportes_entidad}]}]}`. **Todo lo que el diseño pide se deriva de aquí, sin tocar el backend.**
  - `mesesCompletos` = nº de `por_mes` con `dias_con_data===dias_del_mes`; `mesesTotal` = `por_mes.length`.
  - `presentDays` por mes = días de `dias[]` cuyo (año,mes) coincide.
  - `via` (facts/landing) = `categoria === "Producción ECP" ? facts : landing` (D-BADGE).
  - % por grupo = `round(Σreportes_entidad / Σreportes_total × 100)`.
- **C1 · Scoping:** funciones NUEVAS `__cnPanoDensidad`/`__cnPanoCobertura` usadas SOLO por `__cnDashboard`.
  **NO tocar** `__anRenderDensidad`/`__anHeatmap`/`__anRenderCobertura` (los usa la pestaña Análisis). CSS
  nuevo bajo prefijo **`.rb-pano*`** (no existe hoy → sin colisión). No tocar `style.css` ni el chatbot principal.
- **C2 · BONUS — quita Plotly de esta vista:** la matriz de días es CSS puro → en `__cnDashboard` se DEJA de
  llamar `__anHeatmap` (Plotly). Menos memoria (relevante por los crashes de RAM 8GB). El Análisis tab sigue
  usando `__anHeatmap` por su cuenta — no se elimina la función.
- **C3 · Preservar SÍ o SÍ** en la rama densidad: la línea que puebla **`__cnDiasByEnt`** (el validador de
  fecha del green box depende de ella), la **carga SECUENCIAL** densidad→cobertura (RAM), el **gate por rama**
  (filial sin densidad), y `__cnLastIntent`.
- **C4 · Tokens:** reusar los `--rb-*` existentes; el `$rb-gold` del diseño (#C9962E) = nuestro
  **`--rb-chat-gold`** (ya existe). Añadir amber/gold-soft/layer-colors (§1).

---

## §1 · Tokens (`static/css/colapsable.css`, junto a los `--rb-*`)

```css
  --rb-amber: #E8912B;        --rb-amber-soft: #FBF1E4;
  --rb-gold-soft: #FBF3DF;
  --rb-layer-ecp: #2563EB;    --rb-layer-fil: #1E9E5A;
  --rb-layer-mod: #E8912B;    --rb-layer-brz: #6B7A72;
```

## §2 · CSS del panorama (`static/css/colapsable.css`, AL FINAL)

```css
/* ===== Panel derecho "Panorama de Producción" (2026-07-09) ===== */
.rb-pano { background:var(--rb-off); font-size:13px; color:var(--rb-body); }
.rb-pano__subhead { display:flex; align-items:center; gap:9px; padding:11px 18px; background:var(--rb-white);
  border-bottom:1px solid var(--rb-line); }
.rb-pano__subhead i { color:var(--rb-green-mid); font-size:15px; }
.rb-pano__subhead-title { font-size:14px; font-weight:800; color:var(--rb-ink); }
.rb-pano__subhead-title strong { color:var(--rb-ink); }
.rb-pano__subhead-tipo { font-size:12px; color:var(--rb-faint); }
.rb-pano__body { padding:18px 20px 26px; }
.rb-pano__rule { height:1px; background:var(--rb-line); margin:20px 0; }
.rb-pano__loading, .rb-pano__empty { padding:14px; color:var(--rb-muted); font-size:12.5px; }
.rb-pano__empty i { color:var(--rb-green-mid); margin-right:6px; }
.rb-pano__eyebrow { display:flex; align-items:center; gap:8px; margin-bottom:12px;
  font-family:monospace; font-size:10.5px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:var(--rb-green-mid); }

/* KPI */
.rb-pano__kpis { display:flex; gap:10px; margin-bottom:18px; }
.rb-pano__kpi { flex:1; min-width:0; background:var(--rb-white); border:1px solid var(--rb-line); border-radius:13px; padding:13px 15px; }
.rb-pano__kpi-icon { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; margin-bottom:11px; }
.rb-pano__kpi-icon i { font-size:15px; }
.rb-pano__kpi--default .rb-pano__kpi-icon { background:var(--rb-green-softer); } .rb-pano__kpi--default .rb-pano__kpi-icon i { color:var(--rb-green-mid); }
.rb-pano__kpi--warn .rb-pano__kpi-icon { background:var(--rb-amber-soft); } .rb-pano__kpi--warn .rb-pano__kpi-icon i { color:var(--rb-amber); }
.rb-pano__kpi--gold .rb-pano__kpi-icon { background:var(--rb-gold-soft); } .rb-pano__kpi--gold .rb-pano__kpi-icon i { color:var(--rb-chat-gold); }
.rb-pano__kpi-value { font-size:23px; font-weight:800; color:var(--rb-ink); letter-spacing:-.5px; line-height:1; }
.rb-pano__kpi-label { font-size:10.5px; color:var(--rb-muted); margin-top:5px; font-weight:600; }

/* Matriz */
.rb-pano__matrix-card { background:var(--rb-white); border:1px solid var(--rb-line); border-radius:14px; padding:16px 18px; }
.rb-pano__matrix { overflow-x:auto; }
.rb-pano__matrix-row { display:flex; align-items:center; margin-bottom:3px; }
.rb-pano__matrix-mlabel { width:40px; flex:0 0 auto; font-size:10.5px; font-weight:700; color:var(--rb-body); text-align:right; padding-right:8px; }
.rb-pano__axis { width:15px; margin-right:3px; flex:0 0 auto; text-align:center; font-family:monospace; font-size:8px; color:var(--rb-faint); }
.rb-pano__dot { width:15px; height:15px; margin-right:3px; border-radius:50%; flex:0 0 auto; }
.rb-pano__dot--on { background:var(--rb-green-ok); }
.rb-pano__dot--off { background:var(--rb-line-soft); }
.rb-pano__dot--none { background:transparent; }
.rb-pano__dot--on:hover { box-shadow:0 0 0 2px var(--rb-chat-gold); cursor:pointer; }
.rb-pano__matrix-foot { display:flex; align-items:center; gap:14px; margin-top:12px; margin-left:40px; }
.rb-pano__leg { display:flex; align-items:center; gap:5px; font-size:10.5px; color:var(--rb-muted); }
.rb-pano__leg .rb-pano__dot { width:11px; height:11px; margin-right:0; }
.rb-pano__matrix-range { margin-left:auto; font-family:monospace; font-size:10.5px; color:var(--rb-faint); }

/* Cobertura */
.rb-pano__cov-title { font-size:14px; font-weight:800; color:var(--rb-ink); }
.rb-pano__cov-title b { color:var(--rb-green-mid); }
.rb-pano__cov-desc { margin:3px 0 14px; font-size:11px; color:var(--rb-muted); line-height:1.45; }
.rb-pano__cov-desc code { font-family:monospace; font-size:10.5px; color:var(--rb-green-mid); }
.rb-pano__cov-group { margin-bottom:16px; }
.rb-pano__cov-ghead { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.rb-pano__cov-ldot { width:9px; height:9px; border-radius:3px; flex:0 0 auto; }
.rb-pano__cov-ldot--ecp { background:var(--rb-layer-ecp); } .rb-pano__cov-ldot--fil { background:var(--rb-layer-fil); }
.rb-pano__cov-ldot--mod { background:var(--rb-layer-mod); } .rb-pano__cov-ldot--brz { background:var(--rb-layer-brz); }
.rb-pano__cov-ldot--com { background:var(--rb-muted); }
.rb-pano__cov-glabel { font-size:12.5px; font-weight:800; color:var(--rb-ink); }
.rb-pano__cov-gn { font-size:11px; color:var(--rb-faint); }
.rb-pano__cov-gpct { margin-left:auto; font-family:monospace; font-size:10.5px; font-weight:700; color:var(--rb-muted); }
.rb-pano__cov-row { display:grid; grid-template-columns:1fr 96px 52px; align-items:center; gap:12px; padding:7px 0; border-bottom:1px solid var(--rb-line-soft); }
.rb-pano__cov-name { font-size:12.5px; color:var(--rb-ink); font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.rb-pano__cov-badge { font-family:monospace; font-size:9px; color:var(--rb-faint); border:1px solid var(--rb-line); border-radius:4px; padding:0 4px; margin-left:6px; }
.rb-pano__meter { height:5px; border-radius:5px; background:var(--rb-line-soft); overflow:hidden; }
.rb-pano__meter-fill { display:block; height:100%; border-radius:5px; background:var(--rb-green-mid); }
.rb-pano__meter-fill--ecp { background:var(--rb-layer-ecp); } .rb-pano__meter-fill--fil { background:var(--rb-layer-fil); }
.rb-pano__meter-fill--mod { background:var(--rb-layer-mod); } .rb-pano__meter-fill--brz { background:var(--rb-layer-brz); }
.rb-pano__meter-fill--com { background:var(--rb-muted); }
.rb-pano__meter-fill.is-full { background:var(--rb-green-ok); }   /* full gana (va DESPUÉS de los modificadores) */
.rb-pano__cov-count { text-align:right; font-family:monospace; font-size:11.5px; font-weight:700; color:var(--rb-body); }
.rb-pano__cov-count.is-full { color:var(--rb-green-mid); }
.rb-pano__cov-count em { color:var(--rb-faint); font-weight:400; font-style:normal; }

@media (prefers-reduced-motion: reduce) { .rb-pano * { transition:none !important; } }
```

## §3 · JS — `static/js/multitab_shell.js`

### PASO 3.1 — Reemplazar el scaffold de `__cnDashboard`. Reemplazar EXACTO (líneas del `a.innerHTML = '<div class="p-3">'…'</div>';`):
```js
    a.innerHTML =
      '<div class="p-3">' +
      '  <h6 class="mb-1"><i class="bi bi-clipboard2-data"></i> Panorama de <strong>' + esc(ent) + '</strong> ' +
      '    <span class="text-muted small">· ' + esc(nivelLabel) + (esFilial ? " (filial)" : "") + '</span></h6>' +
      '  <hr class="my-2">' +
      '  <h6 class="small text-uppercase text-muted mb-2"><i class="bi bi-calendar-week"></i> Densidad temporal</h6>' +
      '  <div id="cn-dash-densidad"><div class="text-muted small p-2">' +
      '    <span class="spinner-border spinner-border-sm"></span> Calculando densidad…</div></div>' +
      '  <hr class="my-3">' +
      '  <h6 class="small text-uppercase text-muted mb-2"><i class="bi bi-grid-3x3"></i> Cobertura del reporte</h6>' +
      '  <div id="cn-dash-cobertura"><div class="text-muted small p-2">' +
      '    <span class="spinner-border spinner-border-sm"></span> Buscando presencia… (~10s)</div></div>' +
      '</div>';
```
por:
```js
    a.innerHTML =
      '<div class="rb-pano">' +
      '  <div class="rb-pano__subhead"><i class="bi bi-bar-chart-line-fill"></i>' +
      '    <span class="rb-pano__subhead-title">Panorama de <strong>' + esc(ent) + '</strong></span>' +
      '    <span class="rb-pano__subhead-tipo">· ' + esc(nivelLabel) + (esFilial ? " (filial)" : "") + '</span></div>' +
      '  <div class="rb-pano__body">' +
      '    <div id="cn-dash-densidad"><div class="rb-pano__loading">Calculando densidad…</div></div>' +
      '    <div class="rb-pano__rule"></div>' +
      '    <div id="cn-dash-cobertura"><div class="rb-pano__loading">Cobertura…</div></div>' +
      '  </div>' +
      '</div>';
```

### PASO 3.2 — Rama filial + "en cola" + render de densidad (SIN Plotly). Reemplazar EXACTO:
```js
    if (esFilial) {
      if (dEl) dEl.innerHTML = '<div class="alert alert-warning small mb-0">Es una <strong>empresa filial</strong>: ' +
        'su producción se reporta como <strong>cifra consolidada</strong> (sin grano diario ECP). ' +
        'Revisa su presencia abajo, en <strong>Cobertura del reporte</strong>.</div>';
      window.__cnLoadCobertura(ent);   // sin densidad concurrente → cargar de una
    } else {
      if (cEl) cEl.innerHTML = '<div class="text-muted small p-2"><span class="spinner-border spinner-border-sm"></span> ' +
        'Cobertura en cola (se carga tras la densidad)…</div>';
      fetch("/api/analisis/densidad?entidad=" + encodeURIComponent(ent))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (dEl) {
            dEl.innerHTML = __anRenderDensidad(d, true);   // slim: sin semáforo ni nota larga
            if (d.aplica_ecp !== false && d.dias && d.dias.length) {
              __anHeatmap(d.por_mes, d.dias);
              __cnDiasByEnt[String(ent).toUpperCase()] =   // para validar el selector de "un día"
                new Set(d.dias.map(function (x) { return x.fecha; }));
            }
          }
        })
        .catch(function () { if (dEl) dEl.innerHTML = '<div class="alert alert-danger small mb-0">Error calculando la densidad.</div>'; })
        .then(function () { window.__cnLoadCobertura(ent); });   // SECUENCIAL: cobertura tras densidad
    }
```
por (NOTA: se DROPEA `__anHeatmap` y se usa `__cnPanoDensidad`; se CONSERVA `__cnDiasByEnt`):
```js
    if (esFilial) {
      if (dEl) dEl.innerHTML = '<div class="rb-pano__empty"><i class="bi bi-building"></i>' +
        'Es una <strong>empresa filial</strong>: su producción es <strong>cifra consolidada</strong> ' +
        '(sin grano diario ECP). Revisa su presencia abajo, en <strong>Cobertura del reporte</strong>.</div>';
      window.__cnLoadCobertura(ent);
    } else {
      if (cEl) cEl.innerHTML = '<div class="rb-pano__loading">Cobertura en cola (se carga tras la densidad)…</div>';
      fetch("/api/analisis/densidad?entidad=" + encodeURIComponent(ent))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (dEl) dEl.innerHTML = __cnPanoDensidad(d);   // KPIs + dot-matrix (CSS, sin Plotly)
          if (d.aplica_ecp !== false && d.dias && d.dias.length) {
            __cnDiasByEnt[String(ent).toUpperCase()] =    // CONSERVAR: valida el selector de "un día"
              new Set(d.dias.map(function (x) { return x.fecha; }));
          }
        })
        .catch(function () { if (dEl) dEl.innerHTML = '<div class="rb-pano__empty">Error calculando la densidad.</div>'; })
        .then(function () { window.__cnLoadCobertura(ent); });
    }
```

### PASO 3.3 — En `__cnLoadCobertura`, cambiar el render. Reemplazar EXACTO:
```js
      .then(function (cob) { var c2 = el("cn-dash-cobertura"); if (c2) c2.innerHTML = __anRenderCobertura(cob, true); })
```
por:
```js
      .then(function (cob) { var c2 = el("cn-dash-cobertura"); if (c2) c2.innerHTML = __cnPanoCobertura(cob); })
```
(El spinner de carga de `__cnLoadCobertura` puede quedarse; opcionalmente cambiar sus clases a `rb-pano__loading`.)

### PASO 3.4 — Añadir las 2 funciones nuevas (INMEDIATAMENTE DESPUÉS de `window.__cnLoadCobertura = function… };`):

```js
  // ---- Panorama: densidad (KPIs + matriz de días, CSS puro, sin Plotly) ----
  function __cnPanoDensidad(d) {
    if (!d || d.aplica_ecp === false)
      return '<div class="rb-pano__empty"><i class="bi bi-clipboard2-data"></i>Sin huella de reporte a grano diario ECP para esta entidad.</div>';
    var res = d.resumen || {}, meses = d.por_mes || [];
    if (!res.total_dias) return '<div class="rb-pano__empty">Sin días con datos.</div>';
    var completos = meses.filter(function (m) { return m.dias_con_data === m.dias_del_mes; }).length;
    var kpis = [
      {i: "calendar-check", v: res.total_dias || 0, l: "Días con reporte", t: "default"},
      {i: "calendar-x", v: res.huecos_totales || 0, l: "Días sin dato", t: "warn"},
      {i: "lightning-charge", v: res.racha_maxima || 0, l: "Racha máxima", t: "gold"},
      {i: "check2-all", v: completos + "/" + meses.length, l: "Meses completos", t: "default"}
    ];
    var kpiHtml = kpis.map(function (k) {
      return '<div class="rb-pano__kpi rb-pano__kpi--' + k.t + '">' +
        '<div class="rb-pano__kpi-icon"><i class="bi bi-' + k.i + '"></i></div>' +
        '<div class="rb-pano__kpi-value">' + esc(String(k.v)) + '</div>' +
        '<div class="rb-pano__kpi-label">' + esc(k.l) + '</div></div>';
    }).join("");
    var present = {};   // "anio-mes" -> {dia:1}
    (d.dias || []).forEach(function (x) {
      var p = String(x.fecha).split("-");
      var key = p[0] + "-" + parseInt(p[1], 10);
      (present[key] = present[key] || {})[parseInt(p[2], 10)] = 1;
    });
    var axis = '<div class="rb-pano__matrix-row"><div class="rb-pano__matrix-mlabel"></div>';
    for (var a1 = 1; a1 <= 31; a1++) axis += '<div class="rb-pano__axis">' + (a1 % 5 === 0 ? a1 : "") + '</div>';
    axis += '</div>';
    var rows = meses.map(function (m) {
      var set = present[m.anio + "-" + m.mes] || {}, cells = "";
      for (var day = 1; day <= 31; day++) {
        if (day > m.dias_del_mes) cells += '<div class="rb-pano__dot rb-pano__dot--none"></div>';
        else if (set[day]) cells += '<div class="rb-pano__dot rb-pano__dot--on" title="' + esc(m.mes_nombre) + ' ' + day + ' · con reporte"></div>';
        else cells += '<div class="rb-pano__dot rb-pano__dot--off" title="' + esc(m.mes_nombre) + ' ' + day + ' · sin dato"></div>';
      }
      return '<div class="rb-pano__matrix-row"><div class="rb-pano__matrix-mlabel">' + esc(m.mes_nombre.slice(0, 3)) + '</div>' + cells + '</div>';
    }).join("");
    var rango = (res.rango && res.rango[0]) ? (__cnFmtFecha(res.rango[0]) + ' → ' + __cnFmtFecha(res.rango[1])) : "";
    var foot = '<div class="rb-pano__matrix-foot">' +
      '<span class="rb-pano__leg"><span class="rb-pano__dot rb-pano__dot--on"></span>con reporte</span>' +
      '<span class="rb-pano__leg"><span class="rb-pano__dot rb-pano__dot--off"></span>sin dato</span>' +
      '<span class="rb-pano__matrix-range">' + esc(rango) + '</span></div>';
    return '<div class="rb-pano__kpis">' + kpiHtml + '</div>' +
      '<div class="rb-pano__matrix-card">' +
      '<div class="rb-pano__eyebrow"><i class="bi bi-grid-3x3"></i>Densidad temporal · matriz de días</div>' +
      '<div class="rb-pano__matrix">' + axis + rows + '</div>' + foot + '</div>';
  }

  // ---- Panorama: cobertura (medidores agrupados por capa) ----
  var __cnLayerId = {"Producción ECP": "ecp", "Filiales": "fil", "Comentarios": "com",
    "Hojas modeladas (visor)": "mod", "Preservada en crudo (Bronze)": "brz"};
  function __cnPanoCobertura(cob) {
    if (!cob || !cob.categorias) return '<div class="rb-pano__empty">Sin datos de cobertura.</div>';
    var ent = cob.entidad || "";
    var head = '<div class="rb-pano__eyebrow"><i class="bi bi-grid-3x3-gap-fill"></i>Cobertura del reporte</div>' +
      '<div class="rb-pano__cov-title">Presencia de <strong>' + esc(ent) + '</strong> · <b>' +
      (cob.hojas_con_entidad || 0) + ' de ' + cob.total_hojas + ' hojas</b></div>' +
      '<div class="rb-pano__cov-desc">Nº de reportes donde cada hoja contiene la entidad. RAW vía ' +
      '<code>facts</code> (exacto); el resto vía coincidencia por texto.</div>';
    var groups = cob.categorias.map(function (c) {
      var hojas = c.hojas.filter(function (h) { return (h.reportes_entidad || 0) > 0; });   // hideEmpty
      if (!hojas.length) return "";
      var lid = __cnLayerId[c.categoria] || "brz";
      var esLanding = (c.categoria !== "Producción ECP");   // D-BADGE exacto
      var sumN = 0, sumT = 0;
      hojas.forEach(function (h) { sumN += (h.reportes_entidad || 0); sumT += (h.reportes_total || 0); });
      var pct = sumT ? Math.round(sumN / sumT * 100) : 0;
      var rows = hojas.map(function (h) {
        var n = h.reportes_entidad || 0, t = h.reportes_total || 0, full = (t > 0 && n >= t);
        var w = t ? Math.round(n / t * 100) : 0;
        var badge = esLanding ? '<span class="rb-pano__cov-badge">texto</span>' : "";
        return '<div class="rb-pano__cov-row">' +
          '<div class="rb-pano__cov-name">' + esc(h.hoja) + badge + '</div>' +
          '<div class="rb-pano__meter" role="meter" aria-valuenow="' + n + '" aria-valuemin="0" aria-valuemax="' + t + '" ' +
          'aria-label="' + esc(h.hoja) + ': ' + n + ' de ' + t + '">' +
          '<span class="rb-pano__meter-fill rb-pano__meter-fill--' + lid + (full ? ' is-full' : '') + '" style="width:' + w + '%;"></span></div>' +
          '<div class="rb-pano__cov-count' + (full ? ' is-full' : '') + '">' + n + '<em>/' + t + '</em></div></div>';
      }).join("");
      return '<div class="rb-pano__cov-group"><div class="rb-pano__cov-ghead">' +
        '<span class="rb-pano__cov-ldot rb-pano__cov-ldot--' + lid + '"></span>' +
        '<span class="rb-pano__cov-glabel">' + esc(c.categoria) + '</span>' +
        '<span class="rb-pano__cov-gn">' + hojas.length + ' hojas</span>' +
        '<span class="rb-pano__cov-gpct">' + pct + '%</span></div>' + rows + '</div>';
    }).join("");
    return head + groups;
  }
```

## §4 · Cierre
- Subir el cache-buster de `multitab_shell.js` en `templates/main.html` (`?v=…` → `20260709d`).

---

## §5 · Verificación (ejecutar y reportar)
- **V1 · Sintaxis:** `node --check static/js/multitab_shell.js` → OK.
- **V2 · KPIs:** al resolver "hocol" → Operación (ECP), el panel derecho muestra 4 KPI cards: **173** Días con
  reporte, **39** Días sin dato (tono ámbar), **173** Racha máxima (tono dorado), **5/7** Meses completos.
- **V3 · Matriz:** dot-matrix con 7 filas (Nov→May); Nov con solo ~5 puntos verdes (días 26-30) y el resto
  gris; días inexistentes (ej. Feb 29-31) transparentes; ejes cada 5 días; pie con leyenda + rango
  "26-nov-2025 → 17-may-2026". **Sin heatmap Plotly.**
- **V4 · Cobertura:** grupos por capa con punto de color + % agregado (Filiales/Modeladas 100 %, ECP ~26 %);
  medidor por hoja + `n/total`; badge **"texto"** en Filiales/Modeladas/Bronze (NO en las 3 de ECP);
  `REPORTE_Vicepresidente` con total **86** (no 138).
- **V5 · Validación de fecha (green box):** sigue funcionando (elige un hueco → lo rechaza) — `__cnDiasByEnt`
  se sigue poblando.
- **V6 · Filial:** "hocol" → Empresa/Filial → densidad muestra la nota de filial; cobertura poblada.
- **V7 · No regresión Análisis:** la pestaña **Análisis** (Catálogo/Densidad con heatmap Plotly/Cobertura)
  sigue **idéntica**; el chatbot principal intacto.

## §6 · Fuera de alcance
Hover que actualiza el pie con el día exacto (se usa `title` nativo en su lugar), riel de pestañas, lógica
NLP, y todo lo React de la spec. Alinear la pestaña Análisis al mismo look = decisión posterior.
