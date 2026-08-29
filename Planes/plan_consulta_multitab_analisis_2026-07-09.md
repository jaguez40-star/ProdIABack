# Plan ejecutable — Consulta: multi-tab de análisis (rail de previews + lienzo full-height)

> **Modo:** Executor. Frontend-only. **No toca backend, DB, ETL ni endpoints.**
> **Cobertura:** vista Consulta reestructurada; análisis reales = 1 (Desempeño del mes, ya existente),
> el resto entran como tarjetas "Próximamente". `Análisis: entrada 1 → salida 1 real + 3 placeholders`.
> **Estado: auditado v2** (flujo §0.2). Verificado contra el código real: los 4 consumidores del
> visor (`__cnDashboard`/`__cnDashHint`/`__cnVerReporteDia`/`__cnAnalizar`) renderizan vía
> `__cnViewerArea()` → redirigirla al canvas es seguro. Hallazgo **F1** (resalte incoherente del rail
> con intent activo) incorporado; **F2** (no romper el shell) como validación.

---

## 1. Contexto

App padre **ProdIA** (Flask :8020, vanilla JS). Dentro del **MultiTab Shell**
(`static/js/multitab_shell.js`, IIFE `window.MultiTabShell`) hay 4 pestañas en el riel:
Ingesta / Control / Análisis / **Consulta**.

En la pestaña **Consulta**, el visor DERECHO (`#cn-viewer-area`) hoy pinta un panel
**"Desempeño del mes"** que se auto-genera al cargar (global) o por entidad. Ese panel usa una
maqueta interna de **3 columnas** (`.cn-desemp__grid3`: Titular IA | KPIs | barras+curva). Esa
maqueta produce un **bug visual persistente**: la curva "Producción diaria REAL" (columna 3)
**queda con un hueco** (no llena su tarjeta) cuando el resumen del LLM despliega su contenido en
la columna 1, porque las columnas `fr` tienen mínimo implícito `auto` (= min-content) y la
columna 1 le roba ancho a la 3.

**Decisión de rediseño (ya tomada con el usuario):**
- La vista Consulta pasa a **lienzo único a altura completa**.
- Se agrega un **rail vertical de tarjetas-preview** a la izquierda del lienzo (estilo galería
  "GRÁFICOS"), con **previews estáticas (SVG inline)**.
- **v1:** tarjeta 1 = **Desempeño del mes** (real); tarjetas 2-4 = **Filiales / Robustez·EBITDA /
  Comentarios** como **"Próximamente"**.
- El desempeño se **re-maqueta a filas full-width apiladas** (la curva en su propia fila) →
  el hueco desaparece por construcción (no hay columnas compitiendo por ancho).
- **Render bajo demanda:** solo el análisis activo monta Plotly (protege RAM en dev).

---

## 2. Objetivo

1. Envolver el visor de Consulta en un **shell** `rail + canvas`.
2. Rail con **4 tarjetas** (1 activa real + 3 placeholders) con **SVG inline** de preview.
3. Re-maquetar `__cnRenderDesemp` de grid-3-columnas a **stack full-width** (mata el hueco).
4. Click en tarjeta placeholder → lienzo "Próximamente"; click en "Desempeño del mes" → repinta
   el desempeño.
5. Sin regresión del chat (el dashboard de entidad sigue pintando en el lienzo).

---

## 3. Prerequisitos

- Repo raíz: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`
- Node disponible para `node --check` (validación de sintaxis JS).
- Archivos a editar (rutas absolutas):
  - `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js`
  - `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\css\colapsable.css`
  - `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html`

**Helpers ya existentes en el IIFE de `multitab_shell.js`** (NO redefinir): `el(id)` (=`getElementById`),
`esc(t)`, `__cnLastIntent` (var), `window.__cnAnalizar(entidad)`, `window.__cnDashboard(intent)`,
`window.__cnDesempInsight(entidad)`, `__cnRenderDesemp(d)`, `__cnDesempData` (var).

---

## 4. Inventario de archivos y anclas exactas

### 4.1 `static/js/multitab_shell.js`

- **Ancla A** — rama `consulta` de `renderViewer` (≈ líneas 358-371). Bloque actual EXACTO a reemplazar
  (Cambio A).
- **Ancla B** — `function __cnViewerArea()` (≈ línea 914). Línea actual:
  `  function __cnViewerArea() { return el("cn-viewer-area"); }`
- **Ancla C** — línea `  var __cnDesempData = null;` (≈ línea 1112). Insertar bloque nuevo JUSTO
  DESPUÉS (Cambio C: `__CN_ANALISIS`, `__cnRailCards`, `__cnAnalisisTab`).
- **Ancla D** — el `return ( ... )` final de `function __cnRenderDesemp(d)` (≈ líneas 1196-1212),
  el que abre con `'<div class="cn-desemp__grid3">'`. Reemplazar el `return` completo (Cambio D).

### 4.2 `static/css/colapsable.css`

- **Ancla E** — final del bloque "Consulta · Titular ejecutivo (IA)". Insertar el bloque CSS nuevo
  (Cambio E) DESPUÉS de la línea `@media (max-width: 980px) { ... }` que cierra ese bloque
  (≈ líneas 1127-1130).

### 4.3 `templates/main.html`

- **Ancla F** — 2 cache-busters `?v=20260709p` (línea 5 CSS, línea 82 JS). Cambiar ambos a
  `?v=20260709q` (Cambio F).

---

## 5. Especificación de cambios (código exacto)

### CAMBIO A — `renderViewer` rama consulta

**BUSCAR (exacto):**
```js
    } else if (state.activeTab === "consulta") {
      // Panel DERECHO reservado: aquí se mostrarán respuestas elaboradas (gráficos/tablas) — Fase posterior.
      viewer.innerHTML =
        '<div class="rb-cp-vhead"><i class="bi bi-chat-dots rb-cp-vhead__icon"></i>' +
        '  <span class="rb-cp-vhead__title is-gold">Consulta de Producción (v1)</span></div>' +
        '<div id="cn-viewer-area" style="flex:1;min-height:0;overflow:auto;">' +
        '  <div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
        '    <div class="rb-cp-vempty__chip"><i class="bi bi-graph-up-arrow"></i></div>' +
        '    <div class="rb-cp-vempty__eyebrow">Respuestas elaboradas</div>' +
        '    <p class="rb-cp-vempty__hint">Escribe tu consulta en el panel izquierdo. Aquí se ' +
        '      visualizarán las respuestas detalladas (gráficos, tablas y trazabilidad).</p>' +
        '  </div></div></div>';
      if (__cnLastIntent) window.__cnDashboard(__cnLastIntent);   // repinta el dashboard si ya se resolvió
      else window.__cnAnalizar(null);   // al cargar sin entidad → Desempeño GLOBAL del mes (no queda vacío)
    }
```

**REEMPLAZAR POR:**
```js
    } else if (state.activeTab === "consulta") {
      // Lienzo full-height: rail de análisis (previews) + canvas del análisis activo.
      viewer.innerHTML =
        '<div class="rb-cp-vhead"><i class="bi bi-chat-dots rb-cp-vhead__icon"></i>' +
        '  <span class="rb-cp-vhead__title is-gold">Consulta de Producción (v1)</span></div>' +
        '<div id="cn-viewer-area" style="flex:1;min-height:0;overflow:hidden;">' +
        '  <div class="cn-shell">' +
        '    <div class="cn-rail" id="cn-rail">' + __cnRailCards(__cnLastIntent ? null : "desempeno") + '</div>' +
        '    <div class="cn-canvas" id="cn-canvas"></div>' +
        '  </div></div>';
      if (__cnLastIntent) window.__cnDashboard(__cnLastIntent);   // repinta el dashboard si ya se resolvió
      else window.__cnAnalizar(null);   // al cargar sin entidad → Desempeño GLOBAL del mes (no queda vacío)
    }
```

> **F1 (auditoría):** `__cnRailCards` recibe `activeKey`. Se pasa `"desempeno"` solo cuando NO hay
> intent (se pinta el desempeño); con intent se pasa `null` (se pinta el Panorama de la entidad →
> ninguna tarjeta del rail queda activa, evita el resalte incoherente).

### CAMBIO B — `__cnViewerArea()` apunta al canvas

**BUSCAR (exacto):**
```js
  function __cnViewerArea() { return el("cn-viewer-area"); }
```

**REEMPLAZAR POR:**
```js
  function __cnViewerArea() { return el("cn-canvas") || el("cn-viewer-area"); }
```

> Efecto: `__cnAnalizar`, `__cnDashboard`, `__cnVerReporteDia`, `__cnVolverPanorama` (todos usan
> `__cnViewerArea()`) pintan ahora dentro de `#cn-canvas` y el rail persiste. Fallback al id viejo
> si el shell no está montado.

### CAMBIO C — `__CN_ANALISIS`, `__cnRailCards`, `__cnAnalisisTab`

**BUSCAR (exacto):**
```js
  var __cnDesempData = null;   // cache del payload para el selector de producto de la curva
```

**REEMPLAZAR POR** (la misma línea, seguida del bloque nuevo):
```js
  var __cnDesempData = null;   // cache del payload para el selector de producto de la curva

  // ---- Multi-tab de análisis (rail de previews). v1: 1 real + 3 placeholders. ----
  // Previews ESTÁTICAS (SVG inline): cero render, cero red, protege la RAM en dev.
  var __CN_ANALISIS = [
    { key: "desempeno", titulo: "Desempeño del mes", estado: "activo",
      svg: '<svg viewBox="0 0 80 46" preserveAspectRatio="none"><polyline points="4,34 16,22 28,28 40,14 52,24 64,10 76,18" fill="none" stroke="#1f6b4a" stroke-width="2.5"/></svg>' },
    { key: "filiales", titulo: "Filiales", estado: "prox",
      svg: '<svg viewBox="0 0 80 46"><g fill="#1f6b4a"><rect x="6" y="20" width="7" height="20"/><rect x="15" y="12" width="7" height="28"/></g><g fill="#8fbf7f"><rect x="34" y="26" width="7" height="14"/><rect x="43" y="18" width="7" height="22"/></g><g fill="#1f6b4a"><rect x="62" y="16" width="7" height="24"/><rect x="71" y="24" width="6" height="16"/></g></svg>' },
    { key: "ebitda", titulo: "Robustez · EBITDA", estado: "prox",
      svg: '<svg viewBox="0 0 80 46"><g fill="#C9C82A"><rect x="6" y="30" width="9" height="10"/><rect x="20" y="24" width="9" height="16"/><rect x="34" y="18" width="9" height="22"/><rect x="48" y="12" width="9" height="28"/><rect x="62" y="8" width="9" height="32"/></g><polyline points="10,34 24,26 38,18 52,12 66,9" fill="none" stroke="#12324a" stroke-width="2" stroke-dasharray="3 2"/></svg>' },
    { key: "comentarios", titulo: "Comentarios", estado: "prox",
      svg: '<svg viewBox="0 0 80 46"><g fill="#9aa7a0"><rect x="8" y="12" width="52" height="4" rx="2"/><rect x="8" y="22" width="64" height="4" rx="2"/><rect x="8" y="32" width="40" height="4" rx="2"/></g><circle cx="70" cy="34" r="6" fill="#eef5f1" stroke="#1f6b4a" stroke-width="1.5"/></svg>' },
  ];

  // activeKey: clave a resaltar al construir (o null = ninguna, p.ej. cuando se muestra el Panorama). F1.
  function __cnRailCards(activeKey) {
    return __CN_ANALISIS.map(function (a) {
      var badge = a.estado === "activo"
        ? '<span class="cn-railcard__chk"><i class="bi bi-check-circle-fill"></i> Activo</span>'
        : '<span class="cn-railcard__prox">Próximamente</span>';
      return '<button type="button" class="cn-railcard' + (a.key === activeKey ? " is-active" : "") +
        '" data-key="' + a.key + '" onclick="window.__cnAnalisisTab(\'' + a.key + '\', this)">' +
        '<div class="cn-railcard__thumb">' + a.svg + '</div>' +
        '<div class="cn-railcard__meta"><span class="cn-railcard__title">' + esc(a.titulo) + '</span>' +
        badge + '</div></button>';
    }).join("");
  }

  // Cambia el análisis activo del rail. 'desempeno' = real; el resto = "Próximamente".
  window.__cnAnalisisTab = function (key, cardEl) {
    var rail = el("cn-rail");
    if (rail) rail.querySelectorAll(".cn-railcard").forEach(function (c) { c.classList.remove("is-active"); });
    if (cardEl) cardEl.classList.add("is-active");
    var canvas = el("cn-canvas"); if (!canvas) return;
    if (key === "desempeno") {
      var ent = __cnLastIntent ? (__cnLastIntent.valor || __cnLastIntent.entidad || null) : null;
      window.__cnAnalizar(ent);
    } else {
      var cfg = __CN_ANALISIS.filter(function (a) { return a.key === key; })[0] || {};
      canvas.innerHTML =
        '<div class="cn-prox"><div class="cn-prox__ic"><i class="bi bi-cone-striped"></i></div>' +
        '<div class="cn-prox__tt">' + esc(cfg.titulo || "Análisis") + '</div>' +
        '<div class="cn-prox__sub">Este análisis está en diseño. Pronto podrás explorarlo aquí.</div></div>';
    }
  };
```

### CAMBIO D — `__cnRenderDesemp`: stack full-width (mata el hueco)

**BUSCAR (exacto):**
```js
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__grid3">' +
      '  <div id="cn-ins" class="cn-ins">' +
      '    <div class="cn-ins__load"><span class="spinner-border spinner-border-sm"></span> Generando resumen ejecutivo…</div>' +
      '  </div>' +
      '  <div class="cn-desemp__kpis">' + cards + '</div>' +
      '  <div class="cn-desemp__right">' +
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
      '      <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva +
      '  </div>' +
      '</div>'
    );
```

**REEMPLAZAR POR:**
```js
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__stack">' +
      '  <div class="cn-desemp__kpisrow">' + cards + '</div>' +
      '  <div id="cn-ins" class="cn-ins">' +
      '    <div class="cn-ins__load"><span class="spinner-border spinner-border-sm"></span> Generando resumen ejecutivo…</div>' +
      '  </div>' +
      '  <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
      '    <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva +
      '</div>'
    );
```

> Ahora todo va **apilado full-width** en una sola columna: KPIs (fila de 3) → Titular IA →
> Real vs Presupuesto → **curva (fila propia full-width)**. La curva ya no compite por ancho →
> **no hay hueco**. `#cn-ins` sigue presente (lo llena `__cnDesempInsight`). No se toca
> `__cnRenderIns`, `__cnCurvaPlot`, `__cnInsCurvaPlot` ni `__cnDesempInsight`.

### CAMBIO E — CSS del shell + stack

**INSERTAR** el siguiente bloque en `static/css/colapsable.css` INMEDIATAMENTE DESPUÉS de:
```css
@media (max-width: 980px) {
  .cn-desemp__grid3 { grid-template-columns: 1fr; }
  .cn-ins__chips { grid-template-columns: repeat(3,1fr); }
}
```

**Bloque a insertar:**
```css
/* ============================================================
   Consulta · Multi-tab de análisis (rail de previews + lienzo)
   ============================================================ */
.cn-shell { display: flex; height: 100%; min-height: 0; }
.cn-rail { flex: 0 0 158px; width: 158px; overflow-y: auto; padding: 12px 10px; display: flex;
  flex-direction: column; gap: 10px; border-right: 1px solid var(--rb-border,#e3e8e5); background: #f6f8f7; }
.cn-canvas { flex: 1 1 auto; min-width: 0; overflow: auto; padding: 0; }
.cn-railcard { text-align: left; border: 1px solid var(--rb-border,#e3e8e5); background: #fff;
  border-radius: 10px; padding: 8px; cursor: pointer; display: flex; flex-direction: column; gap: 6px;
  transition: border-color .12s, box-shadow .12s; }
.cn-railcard:hover { border-color: var(--rb-green,#1f6b4a); }
.cn-railcard.is-active { border-color: var(--rb-chat-gold,#C9962E); box-shadow: 0 0 0 1px var(--rb-chat-gold,#C9962E); }
.cn-railcard__thumb { height: 46px; border-radius: 6px; background: #f1f5f3; display: grid;
  place-items: center; overflow: hidden; }
.cn-railcard__thumb svg { width: 100%; height: 100%; display: block; }
.cn-railcard__meta { display: flex; flex-direction: column; gap: 2px; }
.cn-railcard__title { font-size: .74rem; font-weight: 700; color: #2f4a3d; line-height: 1.15; }
.cn-railcard__chk { font-size: .64rem; color: #1e9e63; font-weight: 700; }
.cn-railcard__prox { font-size: .6rem; color: #8a968f; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; }
.cn-prox { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; color: #6b7a72; text-align: center; padding: 30px; }
.cn-prox__ic { width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center;
  background: var(--rb-green-soft,#eef5f1); color: var(--rb-chat-gold,#C9962E); font-size: 24px; }
.cn-prox__tt { font-size: 1rem; font-weight: 800; color: #2f4a3d; }
.cn-prox__sub { font-size: .82rem; max-width: 360px; }
.cn-desemp__stack { display: flex; flex-direction: column; gap: 12px; }
.cn-desemp__kpisrow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
@media (max-width: 720px) {
  .cn-desemp__kpisrow { grid-template-columns: 1fr; }
  .cn-rail { flex-basis: 120px; width: 120px; }
}
```

> Nota: `.cn-canvas { padding: 0 }` evita doble padding (el `.cn-desemp__body` ya pad-ea 14px y
> `.cn-prox` pad-ea 30px). Se conserva `.cn-desemp__grid3`/`.cn-desemp__kpis`/`.cn-desemp__right`
> en el CSS aunque queden sin uso (no romper otros posibles usos; no eliminar).

### CAMBIO F — cache-buster `p` → `q`

En `templates/main.html`:
- Línea 5: `css/colapsable.css') }}?v=20260709p` → `...?v=20260709q`
- Línea 82: `js/multitab_shell.js') }}?v=20260709p` → `...?v=20260709q`

---

## 6. Orden de ejecución

1. Cambio B (`__cnViewerArea`).
2. Cambio C (bloque `__CN_ANALISIS`/`__cnRailCards`/`__cnAnalisisTab`).
3. Cambio A (rama consulta de `renderViewer`).
4. Cambio D (`__cnRenderDesemp` stack).
5. Cambio E (CSS).
6. Cambio F (cache-buster).
7. Validaciones §8.

---

## 7. Reglas no negociables

- **Frontend-only.** NO tocar `INGESTA/Rep_Prod/backend/**`, endpoints, DB, ni `routes/api.py`.
- **No redefinir** helpers existentes (`el`, `esc`, `__cnLastIntent`, `__cnAnalizar`,
  `__cnDashboard`, `__cnDesempInsight`, `__cnRenderDesemp`, `__cnRenderIns`, `__cnCurvaPlot`,
  `__cnInsCurvaPlot`, `__cnDesempData`).
- **No eliminar** `.cn-desemp__grid3` ni sus reglas del CSS (quedan inertes).
- **Reemplazos EXACTOS** por los bloques BUSCAR indicados (respetar acentos y `…` unicode literal
  de "Generando resumen ejecutivo…").
- **No** montar Plotly de más: los placeholders NO renderizan gráficos.
- Mantener el auto-insight: `__cnAnalizar` ya llama `__cnDesempInsight` — no alterarlo.

---

## 8. Validaciones (comando → esperado)

- **V1 — Sintaxis JS:**
  `node --check "c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js"`
  → imprime nada / exit 0 (sin errores).
- **V2 — grep de anclas nuevas** (conteos exactos):
  - `__cnRailCards` aparece **2 veces** (definición `function __cnRailCards(activeKey)` + uso en Cambio A).
  - `window.__cnAnalisisTab = function` aparece **1 vez**.
  - `cn-desemp__stack` aparece **1 vez** en el JS + **1 vez** en el CSS.
  - `id="cn-canvas"` aparece **1 vez** en el JS.
  - `?v=20260709q` aparece **2 veces** en `templates/main.html`; `?v=20260709p` **0 veces**.
- **V2b — F2 (no romper el shell):** `el("cn-viewer-area")` NO debe existir en `multitab_shell.js`
  (solo `el("cn-canvas") || el("cn-viewer-area")` dentro de `__cnViewerArea`). Comprobar que no se
  introdujo ningún `el("cn-viewer-area")` suelto.
  Grep sugerido: `grep -n 'el("cn-viewer-area")' multitab_shell.js` → **1 sola** coincidencia (la de
  `__cnViewerArea`).
- **V3 — Navegador (Ctrl+F5 en http://localhost:8020, login dev):** activar pestaña **Consulta**:
  - El visor derecho muestra un **rail vertical** con **4 tarjetas** (Desempeño del mes con SVG de
    línea + "Activo"; Filiales / Robustez·EBITDA / Comentarios con "Próximamente").
  - El lienzo carga el **Desempeño del mes** apilado: fila de 3 KPIs → Titular IA → Real vs
    Presupuesto → **curva a todo el ancho SIN hueco a la derecha**.
  - **0 errores** en consola.
- **V4 — Interacción rail:** clic en **"Filiales"** → lienzo muestra tarjeta **"Próximamente"** y
  la tarjeta Filiales queda con borde dorado activo. Clic en **"Desempeño del mes"** → vuelve a
  pintar el desempeño (con su curva llena).
- **V5 — No regresión + F1:** las pestañas **Ingesta / Control / Análisis** siguen operando; escribir
  una consulta en el chat que resuelva una entidad → el **Panorama de entidad** (densidad/cobertura)
  se pinta en el lienzo **dentro del shell (rail intacto)**; "← Volver al panorama" sigue funcionando.
  **F1:** al reactivar Consulta con una entidad ya resuelta, se muestra el Panorama y **ninguna
  tarjeta del rail queda resaltada** (no el falso "Desempeño activo"). Con carga global (sin intent),
  la tarjeta **Desempeño del mes** sí queda resaltada.

---

## 9. Fuera de alcance (NO hacer en esta tanda)

- Implementar los análisis reales de Filiales / EBITDA / Comentarios (quedan "Próximamente").
- Colapsar/ocultar el panel de chat de Consulta (el visor tiene ancho suficiente con el rail de
  158px; se evaluará aparte).
- Persistir el análisis activo entre cambios de pestaña del riel (al reactivar Consulta arranca en
  Desempeño / o repinta el dashboard si había intent — comportamiento actual conservado).
- Cualquier cambio de backend, endpoints o SQL.
- Tocar el chatbot principal (`static/js/chat.js`) o el layout de 2 paneles.
```
