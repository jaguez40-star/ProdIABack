# Plan ejecutable — Reskin de la **vista de ingesta** (árbol colapsable + tabla optimizada) · 2026-06-23 · **v2 (auditado)**

> **Alcance estricto:** reskin visual de **SOLO la vista de ingesta** de ProdIA (el árbol de hojas/tablas
> del panel izquierdo + la tabla que se abre al hacer clic, en el panel derecho), para que se vea **igual
> a la maqueta** y **acorde a `arbol_tabla.md`**. **TODO lo demás de ProdIA queda EXACTAMENTE igual.**
> Sin React: se traduce la especificación visual del doc (que está escrita para React/TanStack) a **vanilla
> JS + CSS**, reusando el front actual y el pipeline SocketIO existente. **Sin cambios de backend/BD.**

Modo: **plan para Executor** (sin contexto previo). Ejecutar al pie de la letra. Rutas absolutas.

---

## 0 · Contexto y traducción de stack (React del doc → vanilla del front actual)

La vista de ingesta de ProdIA está implementada **100% en vanilla JS** en
`c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` (inyecta HTML por DOM) + CSS, servido por Flask
en `:8020`. **NO es la app React de INGESTA.** Por tanto, del `arbol_tabla.md` se toma **la especificación
visual** (tokens, layout, componentes, reglas de la tabla, footer, accesibilidad, criterios §7) y se
**descarta su implementación** (React/Zustand/TanStack/SCSS). Equivalencias:

| Doc (React) | Implementación aquí (vanilla) |
|---|---|
| Componentes `.tsx` | Funciones que generan HTML en `chat.js` (ya existen: `ingestaSheetLi`, `renderTablaAncha`…) |
| Estado Zustand | `class`/atributos DOM + `is-open`/`is-active` por toggle |
| TanStack Table + virtualización | `<table>` construida en JS (las tablas son ≤ ~60 cols × ~20 filas → **sin** virtualización) |
| SCSS `$tokens` | CSS vars (`--g-*`) en un archivo nuevo **scopeado** `static/css/ingesta.css` |
| Bootstrap Icons `bi-*` | Se agrega Bootstrap Icons por CDN (aditivo; no afecta Font Awesome existente) |

**Anclaje del layout (NO cambiar el layout global):** el árbol se pinta dentro de `#ingesta-sheets`
(contenido inyectado en `chatMessages`, panel izquierdo) y la tabla dentro de `#charts-display-area`
(panel derecho, `templates/components/analytics.html`). El plan estiliza **el contenido** de esos dos
contenedores; **no** impone el grid `380px|1fr` del doc ni toca la maqueta de paneles de ProdIA.

**Dato ya garantizado por el backend:** `/api/tablas-hoja/datos` devuelve `valores` con `null` para
faltante y número (incl. `0`) para presente → permite distinguir **cero (`—`)** de **sin dato (hachura)**
(requisito clave del doc §8). No convertir `null`→`0`.

---

## 0.b · Hallazgos de auditoría (v2 — verificados contra el código real)

Un reskin rompe funciones si cambia clases/markup que otras funciones consultan. Auditado:

- **I1.** `ingestaMarkSoloRespaldo` (L215-227) selecciona `#ingesta-sheet-list li.ingesta-sheet`. El nuevo
  `ingestaSheetLi` DEBE conservar la clase **`ingesta-sheet`** (además de `ig-sheet`), o se pierde la nota
  "· sin tabla de análisis". **Corregido en §5.1.**
- **I2.** `handleIngestaUpload` (L274-278) resetea el icono con `ic.textContent = "⏳"`, que con el nuevo
  `<i class="bi …">` lo destruye. **Corregido en §5.0** (`ic.classList.add("is-pending")` + reset del badge).
- **I3.** La nota la añade `ingestaMarkSoloRespaldo` con clase `ingesta-solo` (NO `ig-solo`). **Se estiliza
  `.ingesta-solo` en el CSS (§3).** No modificar esa función.
- **I4.** El panel `#analytics-panel` ya tiene `.panel-header` (h5). Para evitar **doble barra de título**,
  el CSS oculta ese header SOLO cuando hay una tabla ig (`:has`), auto-revirtiendo para los gráficos del
  chat. **Regla añadida en §3.** (`:has()` es estándar en navegadores actuales; si faltara, degrada a dos
  barras, no rompe.)
- **Mejora.** El `<link>` de `ingesta.css` usa el patrón cache-bust `?v={{random}}` como los demás CSS del
  proyecto (§4). Bootstrap Icons va por CDN como Bootstrap/Font Awesome ya existentes (mismo riesgo).

Sin incoherencias con el backend ni con el pipeline del chat: el reskin es solo-frontend, todo el CSS va
scopeado a `.ig-*` y la única regla que toca un selector compartido (`#analytics-panel`) está acotada por
`:has(.ig-dt)`.

---

## 1 · Prerequisitos (verificar; si falla, DETENER y reportar)

- **P1.** Existe `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` con las funciones:
  `ingestaSheetLi` (~L204), `ingestaMarkSoloRespaldo` (~L215), `onIngestaFileChange` (~L229),
  `renderIngestaProgress` (~L312), `renderIngestaFinal` (~L297), `verTablaHoja` (~L411),
  `renderTablaAncha` (~L434).
- **P2.** Existe `templates/base.html` con `<head>` (para enlazar el CSS nuevo + Bootstrap Icons).
- **P3.** La ingesta funciona hoy: subir un `.xlsm` muestra el árbol y al hacer clic en una tabla se
  renderiza la tabla ancha. (Si no, DETENER: el reskin asume el pipeline operativo.)

**Entorno:** Windows 11, PowerShell. ProdIA = Flask :8020 (frontend estático; **no requiere rebuild** — son
archivos servidos directo). Para ver cambios: `Ctrl+F5` en el navegador (bust de caché).

---

## 2 · Inventario de archivos a modificar (3 archivos; sin backend)

| Archivo | Cambio |
|---|---|
| `static/css/ingesta.css` | **NUEVO** — todas las reglas `.ig-*` (árbol + tabla), tokens en CSS vars |
| `templates/base.html` | **+2 `<link>`** en `<head>`: Bootstrap Icons (CDN) + `ingesta.css` (aditivo) |
| `static/js/chat.js` | Reescritura de **solo** las funciones de la vista de ingesta (§4) + nuevos helpers `ig*` |

**NO se toca:** ningún otro archivo, ni otras funciones de `chat.js`, ni CSS global, ni el backend, ni la BD.

---

## 3 · `static/css/ingesta.css` (NUEVO — crear con este contenido EXACTO)

```css
/* ingesta.css — Reskin SOLO de la vista de ingesta (árbol + tabla). Todo scopeado a .ig-*. */
:root{
  --g-green:#0E5C3A; --g-green-mid:#15794C; --g-green-ok:#1E9E5A; --g-green-soft:#E6F4EC;
  --g-ink:#1B2A33; --g-body:#3D4D58; --g-muted:#74838E; --g-faint:#9AA8B0;
  --g-line:#E2E8EC; --g-line-soft:#EEF2F5; --g-off:#F6F9FB;
  --g-blue:#2563EB; --g-blue-soft:#EAF1FE; --g-gold:#F2C94C;
  --g-mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
}
/* ===== Árbol (panel izquierdo, dentro de #ingesta-sheets) ===== */
.ig-tree__head{display:flex;align-items:center;gap:8px;padding:8px 4px 10px;border-bottom:1px solid var(--g-line);}
.ig-tree__title{font-size:13px;font-weight:800;color:var(--g-ink);}
.ig-mode{font-family:var(--g-mono);font-size:10px;color:var(--g-faint);}
.ig-badge{display:inline-block;font-family:var(--g-mono);font-size:9.5px;font-weight:700;padding:1px 6px;border-radius:5px;white-space:nowrap;line-height:1.5;}
.ig-badge--gray{background:var(--g-line-soft);color:var(--g-muted);}
.ig-badge--blue{background:var(--g-blue-soft);color:var(--g-blue);}
.ig-badge--green{background:var(--g-green-soft);color:var(--g-green-mid);}
.ig-expand-btn{margin-left:auto;height:26px;display:inline-flex;align-items:center;gap:5px;padding:0 9px;font-size:11px;border:1px solid var(--g-line);background:var(--g-off);border-radius:7px;color:var(--g-body);cursor:pointer;}
.ig-tree__body{padding:8px 2px;list-style:none;margin:0;}
.ig-sheet{list-style:none;margin:0 0 2px;}
.ig-sheet__hd{display:flex;align-items:center;gap:7px;padding:7px 8px;border-radius:8px;border:1px solid transparent;cursor:pointer;}
.ig-sheet.is-open>.ig-sheet__hd{background:#fff;border-color:var(--g-line);}
.ig-sheet__name{font-size:13px;font-weight:700;color:var(--g-ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;}
.ig-chev{font-size:11px;color:var(--g-muted);transition:transform .18s ease;flex:none;}
.ig-sheet.is-open>.ig-sheet__hd .ig-chev{transform:rotate(90deg);}
.ig-ok{color:var(--g-green-ok);font-size:15px;flex:none;}
.ig-ok.is-pending{color:var(--g-faint);opacity:.5;}
.ig-sheet__kids{margin:3px 0 5px 17px;padding-left:11px;border-left:1.5px solid var(--g-line-soft);display:none;}
.ig-sheet.is-open>.ig-sheet__kids{display:block;}
.ig-respaldo{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--g-muted);padding:3px 0;}
.ig-respaldo .bi{color:var(--g-faint);}
.ig-solo,.ingesta-solo{font-style:italic;color:var(--g-faint);font-size:11px;}
.ig-destino{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--g-body);padding:3px 0;}
.ig-dot{width:8px;height:8px;border-radius:50%;background:var(--g-green-ok);flex:none;}
.ig-code{font-family:var(--g-mono);font-size:11px;background:var(--g-green-soft);color:var(--g-green-mid);padding:1px 6px;border-radius:5px;}
.ig-group__hd{display:flex;align-items:center;gap:6px;padding:4px 0;cursor:pointer;font-size:11.5px;font-weight:600;color:var(--g-body);}
.ig-group.is-open>.ig-group__hd .ig-chev{transform:rotate(90deg);}
.ig-group__kids{margin-left:6px;padding-left:9px;border-left:1.5px solid var(--g-line-soft);display:none;}
.ig-group.is-open>.ig-group__kids{display:block;}
.ig-trow{display:flex;align-items:center;gap:8px;width:100%;padding:5px 8px 5px 10px;border:0;border-radius:7px;background:transparent;cursor:pointer;text-align:left;}
.ig-trow:hover:not(.is-active){background:var(--g-off);}
.ig-trow.is-active{background:var(--g-green-soft);box-shadow:inset 2px 0 0 var(--g-green-ok);}
.ig-trow .bi{font-size:12px;color:var(--g-faint);flex:none;}
.ig-trow.is-active .bi{color:var(--g-green-mid);}
.ig-trow__name{font-size:12px;font-weight:500;color:var(--g-body);white-space:nowrap;}
.ig-trow.is-active .ig-trow__name{font-weight:700;color:var(--g-ink);}
.ig-trow__tag{font-size:11px;color:var(--g-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.ig-trow .ig-badge{margin-left:auto;}
/* ResumenCard */
.ig-resumen{background:var(--g-green-soft);border:1px solid rgba(30,158,90,.2);border-radius:10px;padding:10px 12px;margin-top:10px;}
.ig-resumen__hd{display:flex;align-items:flex-start;gap:7px;font-size:11.5px;font-weight:700;color:var(--g-ink);margin-bottom:6px;}
.ig-resumen__hd .bi{color:var(--g-green-ok);}
.ig-resumen__sub{display:block;color:var(--g-muted);font-weight:500;}
.ig-resumen__item{display:flex;align-items:center;gap:7px;font-family:var(--g-mono);font-size:11px;padding:2px 0;}
.ig-resumen__k{color:var(--g-body);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.ig-resumen__v{margin-left:auto;font-weight:800;color:var(--g-green-mid);}
.ig-resumen__item .ig-dot{width:5px;height:5px;}
/* ===== Tabla (panel derecho, dentro de #charts-display-area) ===== */
.ig-dt{display:flex;flex-direction:column;height:100%;min-height:0;background:#fff;}
.ig-dt__title{display:flex;align-items:center;gap:10px;padding:12px 18px;background:var(--g-green);color:#fff;}
.ig-dt__title .bi{font-size:16px;color:var(--g-gold);}
.ig-dt__title h6{margin:0;font-size:14px;font-weight:800;color:#fff;}
.ig-dt__count{margin-left:auto;font-family:var(--g-mono);font-size:11px;color:#bfe0cd;}
.ig-dt__toolbar{display:flex;align-items:center;gap:10px;padding:10px 16px;background:var(--g-off);border-bottom:1px solid var(--g-line);}
.ig-search{position:relative;width:240px;}
.ig-search .bi{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--g-muted);font-size:12px;}
.ig-search input{width:100%;height:30px;padding:0 10px 0 28px;border:1px solid var(--g-line);border-radius:7px;font-size:12px;}
.ig-dt__tools{margin-left:auto;display:flex;align-items:center;gap:8px;}
.ig-dt__tools .lbl{font-size:11px;color:var(--g-muted);}
.ig-seg{display:inline-flex;border:1px solid var(--g-line);border-radius:7px;overflow:hidden;}
.ig-seg button{border:0;background:#fff;font-size:11.5px;padding:5px 10px;cursor:pointer;color:var(--g-body);}
.ig-seg button.is-active{background:var(--g-green-soft);color:var(--g-green-mid);font-weight:700;}
.ig-btn{display:inline-flex;align-items:center;gap:5px;height:30px;padding:0 10px;border:1px solid var(--g-line);background:#fff;border-radius:7px;font-size:11.5px;color:var(--g-body);cursor:pointer;}
.ig-dt__scroll{flex:1;overflow:auto;position:relative;min-height:0;}
.ig-dt table{border-collapse:separate;border-spacing:0;min-width:100%;}
.ig-dt th.corner{position:sticky;left:0;top:0;z-index:5;background:var(--g-green);color:#fff;font-size:11px;font-weight:700;min-width:168px;width:168px;border-right:2px solid var(--g-green-mid);text-align:left;padding:0 14px;height:var(--ig-rowh,36px);}
.ig-dt thead th.col{position:sticky;top:0;z-index:3;background:var(--g-green-mid);color:#fff;font-family:var(--g-mono);font-size:11px;font-weight:600;min-width:78px;text-align:right;padding:0 12px;white-space:nowrap;height:var(--ig-rowh,36px);}
.ig-dt tbody th.rowlabel{position:sticky;left:0;z-index:2;width:168px;min-width:168px;background:inherit;border-right:2px solid var(--g-line);text-align:left;padding:0 14px;white-space:nowrap;font-size:var(--ig-fs,12.5px);font-weight:600;color:var(--g-ink);height:var(--ig-rowh,36px);}
.ig-dt td{font-family:var(--g-mono);font-variant-numeric:tabular-nums;font-size:var(--ig-fs,12.5px);text-align:right;padding:0 12px;border-bottom:1px solid var(--g-line-soft);white-space:nowrap;color:var(--g-body);height:var(--ig-rowh,36px);}
.ig-dt td.empty{color:var(--g-faint);background:repeating-linear-gradient(45deg,transparent 0 4px,var(--g-line-soft) 4px 5px);}
.ig-dt td.zero{color:var(--g-faint);}
.ig-dt tbody tr:not(.total):nth-child(even){background:var(--g-off);}
.ig-dt tbody tr:not(.total):hover{background:#EFF6F1;}
.ig-dt tbody tr.total{background:var(--g-green-soft);}
.ig-dt tbody tr.total th.rowlabel,.ig-dt tbody tr.total td{color:var(--g-green-mid);font-weight:700;}
.ig-dt.is-compact{--ig-rowh:28px;--ig-fs:11.5px;}
.ig-dt__foot{display:flex;align-items:center;gap:14px;padding:8px 16px;background:var(--g-off);border-top:1px solid var(--g-line);font-size:11px;color:var(--g-muted);}
.ig-foot__hatch{display:inline-block;width:14px;height:12px;border:1px solid var(--g-line);background:repeating-linear-gradient(45deg,transparent 0 4px,var(--g-line-soft) 4px 5px);vertical-align:middle;}
.ig-dt__foot .ig-foot__right{margin-left:auto;display:inline-flex;align-items:center;gap:5px;}
/* I4: una sola barra de título — oculta el header del panel SOLO con tabla ig (auto-revierte para gráficos) */
#analytics-panel:has(#charts-display-area .ig-dt) > .panel-header{display:none;}
@media (prefers-reduced-motion:reduce){.ig-chev{transition:none;}}
```

---

## 4 · `templates/base.html` — agregar 2 `<link>` en `<head>`

**Después** del `<link>` de `enhanced-tables.css` (~L16), agregar (no quitar nada; mismo patrón cache-bust `?v=`
que usan los CSS del proyecto, y orden de atributos `href … rel="stylesheet"` como los existentes):

```html
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/ingesta.css') }}?v={{ range(1000, 9999) | random }}" rel="stylesheet">
```

---

## 5 · `static/js/chat.js` — reescritura de funciones de ingesta (resto del archivo intacto)

### 5.0 `handleIngestaUpload` — fix del reset de icono (I2) (~L274-278)

Reemplazar el bloque `document.querySelectorAll("#ingesta-sheet-list li").forEach(…)` por:

```javascript
  document.querySelectorAll("#ingesta-sheet-list li").forEach((li) => {
    const ic = li.querySelector(".ingesta-ic"); if (ic) ic.classList.add("is-pending");  // I2: no usar textContent
    const cnt = li.querySelector(".ig-sheet__count"); if (cnt) cnt.style.display = "none";
    delete li.dataset.contado;
    const kids = li.querySelector(".ingesta-children"); if (kids) kids.innerHTML = "";
  });
```

### 5.1 `ingestaSheetLi` (reemplazar la función completa, ~L204-212)

```javascript
// Hoja colapsable: chevron + check + nombre + badge "N tablas"; contenedor de hijos.
// I1: conserva la clase 'ingesta-sheet' (la usa ingestaMarkSoloRespaldo) además de 'ig-sheet'.
window.ingestaSheetLi = function ingestaSheetLi(n) {
  const safe = String(n).replace(/"/g, "&quot;");
  return `<li class="ig-sheet ingesta-sheet is-open" data-hoja="${safe}">
    <div class="ig-sheet__hd" onclick="window.igToggleSheet(this)">
      <i class="bi bi-chevron-right ig-chev"></i>
      <i class="bi bi-check-circle-fill ig-ok is-pending ingesta-ic"></i>
      <span class="ig-sheet__name">${n}</span>
      <span class="ig-badge ig-badge--blue ig-sheet__count" style="display:none"></span>
    </div>
    <ul class="ig-sheet__kids ingesta-children list-unstyled mb-0"></ul>
  </li>`;
};
```

### 5.2 Header del árbol — en **dos** sitios

(a) En `onIngestaFileChange` (~L243-248) reemplazar el bloque `sheetsBox.innerHTML = \`…\`` por:

```javascript
    sheetsBox.innerHTML = `
      <div class="ig-tree__head">
        <span class="ig-tree__title">Hojas del archivo</span>
        <span class="ig-badge ig-badge--blue" id="ingesta-counter">0 / ${names.length}</span>
        <span class="ig-mode">${esNew ? "NEW" : "STD"}</span>
        <button class="ig-expand-btn" onclick="window.igExpandAll(this)" aria-pressed="true">
          <i class="bi bi-chevron-bar-contract"></i> Colapsar todo</button>
      </div>
      <ul id="ingesta-sheet-list" class="ig-tree__body">${items}</ul>`;
```

(b) En `renderIngestaProgress`, rama `ev.tipo === "inicio"` (~L322-328), reemplazar el `box.innerHTML = \`…\`` por el **mismo** bloque, usando `window.__ingestaTotal` y `(ev.tipo_archivo || "STD")`:

```javascript
      box.innerHTML = `
        <div class="ig-tree__head">
          <span class="ig-tree__title">Hojas del archivo</span>
          <span class="ig-badge ig-badge--blue" id="ingesta-counter">0 / ${window.__ingestaTotal}</span>
          <span class="ig-mode">${ev.tipo_archivo || "STD"}</span>
          <button class="ig-expand-btn" onclick="window.igExpandAll(this)" aria-pressed="true">
            <i class="bi bi-chevron-bar-contract"></i> Colapsar todo</button>
        </div>
        <ul id="ingesta-sheet-list" class="ig-tree__body">${items}</ul>`;
```

### 5.3 Icono de estado por hoja (~L357) — reemplazar `ic.textContent = "✅";` por:

```javascript
    if (ic) ic.classList.remove("is-pending");
```

### 5.4 Línea **Respaldo** (~L369-374) — reemplazar el bloque `if (!kids.querySelector(".ingesta-respaldo")) {…}` por:

```javascript
      if (!kids.querySelector(".ig-respaldo")) {
        const r = document.createElement("div");
        r.className = "ig-respaldo ingesta-respaldo";
        r.innerHTML = `<i class="bi bi-archive"></i><span>Respaldo</span>` +
          (typeof ev.filas === "number" ? `<span class="ig-badge ig-badge--gray">${nf(ev.filas)} filas</span>` : "");
        kids.appendChild(r);
      }
```

### 5.5 Bloque **tablas** (grupo "Para análisis") y **destino fact** (~L378-406)

Reemplazar el bloque completo `if (Array.isArray(ev.tablas) && ev.tablas.length) { … } else if (…) { … }` por:

```javascript
      if (Array.isArray(ev.tablas) && ev.tablas.length) {
        // badge "N tablas" en la cabecera de la hoja
        const cnt = li.querySelector(".ig-sheet__count");
        if (cnt) { cnt.textContent = `${ev.tablas.length} tablas`; cnt.style.display = ""; }
        if (!kids.querySelector(".ig-group")) {
          const g = document.createElement("li");
          g.className = "ig-group is-open";
          g.innerHTML = `<div class="ig-group__hd" onclick="window.igToggleGroup(this)">
              <i class="bi bi-chevron-right ig-chev"></i><i class="bi bi-diagram-3"></i>
              <span>Para análisis</span>
              <span class="ig-badge ig-badge--gray">${ev.tablas.length} tablas</span></div>
            <div class="ig-group__kids"></div>`;
          const kk = g.querySelector(".ig-group__kids");
          ev.tablas.forEach((t) => {
            const tag = String(t.tabla_label || "").replace(/^Tabla\s*\d+\s*\(?|\)?$/g, "").trim();
            const b = document.createElement("button");
            b.type = "button";
            b.className = "ig-trow";
            b.dataset.tablaIdx = t.tabla_idx;
            b.innerHTML = `<i class="bi bi-table"></i>
              <span class="ig-trow__name">${t.tabla_label}</span>` +
              (tag ? `<span class="ig-trow__tag">· ${tag}</span>` : "") +
              `<span class="ig-badge ig-badge--gray">${nf(t.filas)} filas</span>`;
            b.addEventListener("click", (e) => {
              e.preventDefault();
              window.igSelectTable(b, li);
              window.verTablaHoja(ev.reporte_id, ev.hoja, t.tabla_idx, t.tabla_label);
            });
            kk.appendChild(b);
          });
          kids.appendChild(g);
        }
      } else if (!kids.querySelector(`.ig-destino[data-tabla="${ev.tabla}"]`)) {
        const a = document.createElement("div");
        a.className = "ig-destino ingesta-analisis";
        a.dataset.tabla = ev.tabla;
        a.innerHTML = `<span class="ig-dot"></span><span>RAW →</span>
          <code class="ig-code">${ev.tabla}</code>` +
          (typeof ev.filas === "number" ? `<span class="ig-badge ig-badge--green">${nf(ev.filas)} filas</span>` : "");
        kids.appendChild(a);
      }
```

> Nota: `ingestaMarkSoloRespaldo` y su clase `.ingesta-respaldo`/`.ingesta-analisis` siguen funcionando
> (se conservaron como segundas clases). No modificar esa función.

### 5.6 `renderIngestaFinal` — ResumenCard (reemplazar el bloque `status.innerHTML = \`…success…\`` ~L307-309)

```javascript
  status.innerHTML = `
    <div class="ig-resumen">
      <div class="ig-resumen__hd"><i class="bi bi-check-circle-fill"></i>
        <span>${res.archivo || ""}<span class="ig-resumen__sub">(${res.tipo_archivo || ""}) → reporte_id ${res.reporte_id}</span></span>
      </div>
      ${Object.entries(res.filas_por_tabla || {}).map(([k, v]) =>
        `<div class="ig-resumen__item"><span class="ig-dot"></span>
          <span class="ig-resumen__k">${k}</span><span class="ig-resumen__v">${nf2(v)}</span></div>`).join("")}
    </div>`;
```

(Definir, una sola vez cerca del inicio de `renderIngestaFinal`: `const nf2 = (x) => Number(x).toLocaleString("es-CO");`)

### 5.7 `verTablaHoja` (reemplazar completa, ~L411-432) — sin cambios de red, solo deja el render al nuevo `renderTablaAncha`

```javascript
window.verTablaHoja = async function verTablaHoja(reporteId, hoja, tablaIdx, label) {
  const area = document.getElementById("charts-display-area");
  const titleEl = document.getElementById("analytics-panel-title");
  const empty = document.getElementById("analytics-empty-state");
  if (titleEl) titleEl.textContent = `${hoja} — ${label}`;
  if (empty) empty.style.display = "none";
  if (!area) return;
  area.style.display = "block";
  area.innerHTML = '<div class="d-flex align-items-center gap-2 p-3"><div class="spinner-border spinner-border-sm"></div> Cargando tabla…</div>';
  try {
    const url = `/api/tablas-hoja/datos?reporte_id=${encodeURIComponent(reporteId)}&hoja=${encodeURIComponent(hoja)}&tabla_idx=${encodeURIComponent(tablaIdx)}`;
    const r = await fetch(url);
    const data = await r.json();
    if (!r.ok) { area.innerHTML = `<div class="alert alert-danger m-3">Error: ${data.error || data.detail || r.status}</div>`; return; }
    window.renderTablaAncha(area, data, `${hoja} — ${label}`);
  } catch (e) {
    area.innerHTML = `<div class="alert alert-danger m-3">Fallo de red: ${e}</div>`;
  }
};
```

### 5.8 `renderTablaAncha` (reemplazar completa, ~L434-459) — nueva tabla optimizada

```javascript
window.renderTablaAncha = function renderTablaAncha(area, data, titulo) {
  const esMatriz = data.modo === "matriz";
  const dims = data.dimensiones || [];
  const meses = data.meses || [];
  if (data.vacia || !(data.filas || []).length) {
    area.innerHTML = `<div class="ig-dt"><div class="ig-dt__title"><i class="bi bi-table"></i><h6>${titulo}</h6></div>
      <div class="p-3 text-muted">Sin datos para esta tabla en este archivo.</div></div>`;
    return;
  }
  const _iso = esMatriz ? [] : meses;
  const _mensual = new Set(_iso.map((m) => m.slice(0, 7))).size === _iso.length;
  const fmtCol = (v) => { if (esMatriz) return v; const [y, m, d] = v.split("-"); return _mensual ? `${m}/${y.slice(2)}` : `${d}/${m}`; };
  const fmtNum = (v) => Number(v).toLocaleString("es-CO", { maximumFractionDigits: 1 });
  const cornerLbl = (dims.length ? dims.join(" / ") : "CAMPO / SERIE").toUpperCase();
  const rowLbl = (f) => dims.map((d) => f.dims[d]).filter((x) => x != null).join(" · ") || "—";
  const isTotal = (lbl) => /^(total|p50 objetivo|objetivo)/i.test(lbl);

  let head = `<tr><th class="corner">${cornerLbl}</th>`;
  meses.forEach((m) => (head += `<th class="col">${fmtCol(m)}</th>`));
  head += `</tr>`;
  let body = "";
  (data.filas || []).forEach((f) => {
    const lbl = rowLbl(f);
    body += `<tr class="${isTotal(lbl) ? "total" : ""}" data-name="${lbl.toLowerCase()}">`;
    body += `<th class="rowlabel" scope="row">${isTotal(lbl) ? '<i class="bi bi-sigma"></i> ' : ""}${lbl}</th>`;
    (f.valores || []).forEach((v) => {
      if (v == null) body += `<td class="empty" aria-label="sin dato">·</td>`;
      else if (v === 0) body += `<td class="zero">—</td>`;
      else body += `<td>${fmtNum(v)}</td>`;
    });
    body += `</tr>`;
  });

  area.innerHTML = `
    <div class="ig-dt" id="ig-dt">
      <div class="ig-dt__title"><i class="bi bi-table"></i><h6>${titulo}</h6>
        <span class="ig-dt__count">${data.filas.length} filas × ${meses.length} ${esMatriz ? "columnas" : "meses"}</span></div>
      <div class="ig-dt__toolbar">
        <div class="ig-search"><i class="bi bi-search"></i>
          <input type="text" placeholder="Buscar fila…" oninput="window.igSearch(this.value)"></div>
        <div class="ig-dt__tools">
          <span class="lbl">Densidad</span>
          <div class="ig-seg"><button class="is-active" onclick="window.igDensity(false,this)">Cómoda</button>
            <button onclick="window.igDensity(true,this)">Compacta</button></div>
          <button class="ig-btn" onclick="window.igExportCSV()"><i class="bi bi-download"></i> Exportar</button>
        </div>
      </div>
      <div class="ig-dt__scroll"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>
      <div class="ig-dt__foot"><span id="ig-visible">${data.filas.length}</span>&nbsp;filas visibles
        <span><span class="ig-foot__hatch"></span> = sin dato</span><span>— = cero</span>
        <span class="ig-foot__right"><i class="bi bi-arrow-left-right"></i> Desplaza para ver los ${meses.length} ${esMatriz ? "columnas" : "meses"} · 1ª columna fija</span></div>
    </div>`;
  window.__igTable = { cornerLbl, cols: meses.map(fmtCol), filas: data.filas, rowLbl, titulo };
};
```

### 5.9 Helpers nuevos `ig*` (agregar al final de `chat.js`, fuera de cualquier función)

```javascript
window.igToggleSheet = function (hd) { hd.closest(".ig-sheet").classList.toggle("is-open"); };
window.igToggleGroup = function (hd) { hd.closest(".ig-group").classList.toggle("is-open"); };
window.igExpandAll = function (btn) {
  const sheets = [...document.querySelectorAll("#ingesta-sheet-list .ig-sheet")];
  const open = !sheets.every((s) => s.classList.contains("is-open"));   // si no todas abiertas → abrir todas
  sheets.forEach((s) => s.classList.toggle("is-open", open));
  btn.setAttribute("aria-pressed", String(open));
  btn.innerHTML = open ? '<i class="bi bi-chevron-bar-contract"></i> Colapsar todo'
                       : '<i class="bi bi-chevron-bar-expand"></i> Expandir todo';
};
window.igSelectTable = function (row, sheetLi) {
  document.querySelectorAll("#ingesta-sheet-list .ig-trow.is-active").forEach((x) => x.classList.remove("is-active"));
  row.classList.add("is-active");
  // regla del doc: solo la hoja activa expandida
  document.querySelectorAll("#ingesta-sheet-list .ig-sheet").forEach((s) => s.classList.toggle("is-open", s === sheetLi));
};
window.igSearch = function (q) {
  q = (q || "").toLowerCase().trim();
  let vis = 0;
  document.querySelectorAll("#ig-dt tbody tr").forEach((tr) => {
    const ok = !q || (tr.dataset.name || "").includes(q);
    tr.style.display = ok ? "" : "none"; if (ok) vis++;
  });
  const c = document.getElementById("ig-visible"); if (c) c.textContent = vis;
};
window.igDensity = function (compact, btn) {
  const dt = document.getElementById("ig-dt"); if (dt) dt.classList.toggle("is-compact", compact);
  btn.parentElement.querySelectorAll("button").forEach((b) => b.classList.remove("is-active"));
  btn.classList.add("is-active");
};
window.igExportCSV = function () {
  const t = window.__igTable; if (!t) return;
  const esc = (s) => `"${String(s).replace(/"/g, '""')}"`;
  const head = [t.cornerLbl, ...t.cols].map(esc).join(",");
  const rows = t.filas.map((f) => [t.rowLbl(f), ...(f.valores || []).map((v) => v == null ? "" : v)].map(esc).join(","));
  const csv = "﻿" + [head, ...rows].join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = (t.titulo || "tabla").replace(/[^\w.-]+/g, "_") + ".csv";
  a.click(); URL.revokeObjectURL(a.href);
};
```

---

## 6 · Orden de ejecución

1. **Auditar** (§1 P1-P3). Si falla, DETENER.
2. Crear `static/css/ingesta.css` (§3).
3. Editar `templates/base.html` (§4).
4. Editar `static/js/chat.js` (§5.0 → 5.9) en orden, incluidos los fixes I1 (§5.1) e I2 (§5.0). **No tocar**
   ninguna otra función ni `ingestaMarkSoloRespaldo`.
5. Verificación de sintaxis JS: `cd c:\APLICACIONES\ProdIA\12112025_prodIA` →
   `node --check static/js/chat.js` → "sin errores".
6. Recarga dura en el navegador (`Ctrl+F5`) en `:8020` y correr Validaciones §7.

---

## 7 · Validaciones (criterios de aceptación, del doc §7)

- **V1.** Subir un `.xlsm` con hoja `(Bitacora)`/`Producción filiales`/`P50`: el árbol se ve con cabecera
  **"Hojas del archivo · N/N · MODE · Colapsar todo"**, hojas con chevron + check verde + badge "N tablas".
- **V2.** **Chevrons rotan**; clic en cabecera de hoja colapsa/expande; clic en "Para análisis" colapsa el
  grupo; botón **Expandir/Colapsar todo** alterna todas las hojas (y cambia su ícono/label).
- **V3.** Clic en un ítem de tabla: queda **resaltado** (fondo verde-soft + acento izq. verde + badge),
  **solo su hoja queda expandida**, y el panel derecho muestra esa tabla.
- **V4.** Tabla: **1ª columna congelada** al desplazar horizontal y **encabezado verde sticky** al
  desplazar vertical (ambos se mantienen). Zebra en filas; hover verde claro.
- **V5.** **Cero** se muestra `—` atenuado; **sin dato** con **hachura** `·`. (En `(Bitacora)` Tabla 2 de un
  archivo NEW hay celdas `0` reales → deben verse `—`, no hachura.)
- **V6.** Toolbar: **Buscar fila** filtra filas por nombre (actualiza "N filas visibles"); **Cómoda/Compacta**
  cambia alto/tamaño; **Exportar** descarga un CSV con la tabla.
- **V7.** **ResumenCard** verde al terminar la ingesta (archivo, reporte_id, items mono con valores verdes).
- **V8.** **El resto de ProdIA sigue idéntico**: abrir el chat normal, enviar una pregunta, ver gráficos
  Plotly/insights — sin cambios visuales ni de comportamiento (el header del panel **reaparece** con los
  gráficos del chat, gracias al `:has`). Iconos Bootstrap (`bi-*`) presentes.
- **V9 (regresión del audit).** (I3) Una hoja con respaldo pero sin destino fact (ej. `(Bitacora)`/`P50`)
  muestra "· sin tabla de análisis" en itálica atenuada. (I2) **Re-ingerir** el mismo archivo (botón Cargar
  e ingerir de nuevo): los iconos de hoja vuelven a estado pendiente y luego a check verde **sin** romperse
  (no aparece un "⏳" de texto dentro del icono), y los badges/árbol se reconstruyen bien.

---

## 8 · Reglas no negociables

1. **Solo** la vista de ingesta. No tocar otras funciones de `chat.js`, ni CSS global, ni `main.html`, ni
   backend/BD. Todo el CSS nuevo va scopeado a `.ig-*` en `ingesta.css`.
2. **Sin React/Zustand/TanStack** — vanilla JS + CSS. La virtualización del doc NO se implementa (tablas
   pequeñas).
3. **Preservar `null` vs `0`** en el render (hachura vs `—`). No convertir `null`→`0`.
4. Conservar las clases legacy `.ingesta-ic/.ingesta-children/.ingesta-respaldo/.ingesta-analisis` como
   segundas clases (las usa `ingestaMarkSoloRespaldo` y el handler) — no romper esa función.
5. `renderTablaAncha` debe seguir soportando **modo matriz** (filiales) y **modo fechas** (formato DD/MM o
   MM/YY) — no romper P50/filiales.
6. No marcar nada como hecho sin la validación visual correspondiente.

---

## 9 · Fuera de alcance

- El layout global de ProdIA (paneles, sidebar de conversaciones), el chat, gráficos Plotly, mapas, login.
- Virtualización de filas/columnas (innecesaria para estos tamaños).
- Cambios de backend, endpoints, esquema o datos.
- Filas "Total"/"Objetivo": se **estilizan si existen** (heurística por nombre), pero los extractores
  actuales (P50/filiales/Bitácora) excluyen subtotales → normalmente no aparecerán; es correcto.
```
