# PLAN EJECUTABLE — Fase 2 · Focos master-detail (pills) + Mantenimientos mock

> Rediseño A+C (`anal.md` §8-§9). Reemplaza el **acordeón anidado de 3 secciones** de cada foco
> ECP ("Comportamiento diario / Diferidas / Mantenimientos" apiladas, que empujan el layout) por
> **3 pills segmentadas (tablist) + UN panel de detalle** (master-detail: solo un panel visible;
> cambiar de pill intercambia el contenido sin colapsar/expandir). Es un **rediseño de
> presentación**: los datos NO cambian. Continúa la Fase 1 (tarjetas KPI con anillo, ya en prod).

## Traducción de stack (igual que Fase 1)

`anal.md` está escrito para **React 19 / TS / Sass**, pero el panel vive en **vanilla JS**
(`static/js/multitab_shell.js`) + **CSS plano** (`static/css/colapsable.css`). Se traduce §8-§9 a
funciones/clases vanilla, exactamente como se hizo con `chat.md` ("Asimétrico esencial") y con la
Fase 1. **Se descartan** §2/§3/§10/§13 (archivos React, Sass, Vitest) y §9.1 (reescribir los 2
gráficos a CSS/SVG): las gráficas Plotly del foco YA funcionan y están pintadas por
`__cnPaintFocoCharts` — se **reusan tal cual** dentro del panel Comportamiento. Fase 2 = solo la
reestructuración a pills; no se tocan los charts ni el backend.

---

## Auditoría previa (verificada contra código y payload real 2026-07-24)

| # | Hallazgo | Consecuencia para el plan |
|---|----------|---------------------------|
| **A** | El bloque a cambiar es la **rama ECP** de `__cnFocosHtml`, **líneas 1983-2016** (tras el `if (__cnEsFil()) {…return…}` que cierra en 1981). La función local `sec()` (1989-1995) y `var vacia` viven SOLO en ese bloque. | Editar solo 1983-2016. **NO tocar** la rama filial (1962-1981) ni `__cnFilialToggle`/`__cnFocoToggle`/`__cnSeriesToggle`. |
| **B** | `__cnPaintFocoCharts()` (1401) pinta buscando por ID `cn-foco-day-{rank}` / `cn-foco-mon-{rank}` (getElementById) y corre DESPUÉS de insertar el HTML (llamado desde `__cnPaintDesemp` 1391 y del fetch de ejecutivo). | El panel Comportamiento **debe conservar esos IDs exactos** y estar montado + **visible por defecto** (Plotly pinta a tamaño 0 si está `display:none`). Diseño: los 3 paneles montados, solo el activo `display:block`; Comportamiento = activo inicial. |
| **B2** | Secuencia de render verificada — `__cnPaintEjec(d)` (1814-1819): (1) `body.innerHTML = __cnRenderEjecutivo(d)` inserta el HTML de focos en el contenedor **`cn-ejec-body`** y fija `__cnEjecD`; (2) `__cnEjecCharts(d)`; (3) `__cnPaintComportIzq()`→`__cnPaintFocoCharts()`. El HTML entra al DOM **antes** del pintado por ID → sin condición de carrera. El guard `if(!ed.focos||!dd.curva)return` deja que pinte quien termine último (ejecutivo o desempeño). | Confirma que preservar los IDs + Comportamiento visible es **suficiente y necesario**. No hay que tocar la secuencia; solo el marcado interno del foco. |
| **C** | La altura de las 2 gráficas la daba `.cn-foco__acc .cn-desemp__grid2 { min-height:300px }` + `.cn-foco__acc .cn-ins { height:auto }`. El nuevo marcado **no** tiene `.cn-foco__acc`. | Replicar esas 2 reglas bajo `.cp-foco__panel` o las gráficas colapsan a 0. |
| **D** | Campos reales del foco (payload `/api/analisis/ejecutivo`): `rank`, `producto` (GAS/BLANCOS/CRUDO), `entidades` (array, `campos = .length`), `peso_relativo_pct` (=share, ej. 88.2), `titulo`, `faltante_abs`, `tipo:"gap"`. **No** hay `share`/`campos` con esos nombres. | Header §8.1: `peso_relativo_pct` → "{n}% del faltante"; `entidades.length` → "{n} campos"; `entidades.join(" + ")` → fields. |
| **E** | La sección **Diferidas** ya está construida (endpoint `/api/diferidas/frecuencia`, `__cnDiferidasInto`, lazy). Hoy se dispara desde `__cnFilialToggle` al abrir la sección del acordeón. | El nuevo `__cnFocoTab` debe replicar ese gancho lazy (marcar `data-loaded="1"` + `__cnDiferidasInto`) al mostrar la pill Diferidas, y el resize Plotly al mostrar Comportamiento. |
| **F** | **Mantenimientos NO tiene fuente de datos real** (ninguna hoja del reporte lo trae). Decisión del usuario: usar **datos MOCK** como la imagen de referencia mientras se diseña, rotulados como ejemplo. | Panel Mantto = tabla mock (§9.3) con banda visible "datos de ejemplo · sin fuente real" (misma honestidad que el badge "EN PRUEBAS" del Análisis Ejecutivo). |
| **G** | Los 3 call sites de focos ECP pasan por `__cnPaintDesemp`→`__cnFocosHtml`; `__cnLastIntent`, `__cnNivel`, `__cnEsFil`, `esc`, `__CP_PROD`, `__CP_STATUS` (Fase 1) están todos en scope de módulo. | Reusar `__CP_PROD` (Fase 1) extendiéndolo con `color`; añadir `__CP_TABS` y el mock cerca de esos mapas. |
| **H** | El badge "N eventos" de la pill Diferidas (spec §5) exige el conteo, que solo llega tras el fetch lazy (caro, RAM 8GB). | v1: sublínea estática "frecuencia histórica"; el conteo real (`meta.total_incidentes`) queda como mejora opcional (Fuera de alcance). Sin fetch eager. |

---

## Archivos a modificar

### 1. `static/js/multitab_shell.js`

**1.a — Extender `__CP_PROD` con color + añadir metadatos de pills y mock** (JUSTO DESPUÉS de la
línea `var __CP_PROD = {…}` de Fase 1, ~1858; anclar por el string `var __CP_PROD =`):

Reemplazar la línea `var __CP_PROD = { CRUDO: { icon: "droplet-fill" }, GAS: { icon: "fire" }, BLANCOS: { icon: "droplet" } };`
por:

```js
  var __CP_PROD = { CRUDO: { icon: "droplet-fill", color: "#E8912B" },
                    GAS:     { icon: "fire",         color: "#C5311E" },
                    BLANCOS: { icon: "droplet",      color: "#D9503B" } };
  // [2026-07-24] Fase 2 · las 3 pills temáticas del foco (master-detail). Iconos anal.md §8.2.
  var __CP_TABS = [
    { key: "comport", icon: "graph-up",     titulo: "Comportamiento diario", sub: "" },
    { key: "dif",     icon: "droplet-half", titulo: "Diferidas",             sub: "frecuencia histórica" },
    { key: "mantto",  icon: "tools",        titulo: "Mantenimientos",        sub: "3 de ejemplo" }
  ];
  // Mantenimientos: NO existe fuente real → datos de EJEMPLO (rotulados). Reemplazar cuando haya dato.
  var __CP_MANTTO_MOCK = [
    { pozo: "CUS-14", tipo: "Workover",        estado: "En ejecución", fin: "22 May" },
    { pozo: "CUP-07", tipo: "Cambio de bomba", estado: "Programado",   fin: "26 May" },
    { pozo: "CUS-31", tipo: "Estimulación",    estado: "Programado",   fin: "29 May" }
  ];
  function __cnManttoMockHtml() {
    var rows = __CP_MANTTO_MOCK.map(function (m) {
      var enEjec = m.estado === "En ejecución";
      return '<div class="cp-foco__mrow">' +
        '<span class="cp-foco__mpozo">' + esc(m.pozo) + '</span>' +
        '<span class="cp-foco__mtipo">' + esc(m.tipo) + '</span>' +
        '<span class="cp-foco__mest ' + (enEjec ? "is-ejec" : "is-prog") + '">' +
          '<i class="cp-foco__mdot"></i>' + esc(m.estado) + '</span>' +
        '<span class="cp-foco__mfin">' + esc(m.fin) + '</span></div>';
    }).join("");
    return '<div class="cp-foco__mock"><i class="bi bi-info-circle"></i> Datos de ejemplo · sin fuente real conectada</div>' +
      '<div class="cp-foco__mtbl">' + rows + '</div>';
  }
```

**1.b — Reemplazar la rama ECP de `__cnFocosHtml` (líneas 1983-2016)**, desde el comentario
`// ECP: renglón limpio + acordeón por foco.` hasta el `}` que cierra la función (incluye `sec()`,
`var vacia`, `var filas` y el `return` final), por:

```js
    // ECP [Fase 2]: renglón + 3 pills temáticas (master-detail). Panel activo default = Comportamiento.
    // Los 3 paneles se montan; solo el activo es visible. Se conservan los IDs cn-foco-day/mon/dif-{rank}.
    meta = meta || {};
    var cp = String(meta.corte || "").split("/");
    var enCurso = cp.length === 2 && cp[0] !== cp[1];
    var etiqueta = (meta.periodo || "") + (enCurso ? " · en curso (" + meta.corte + ")" : "");
    var badgeComp = meta.corte ? (esc(meta.corte) + (enCurso ? " en curso" : "")) : "histórico";
    var difEntG = (__cnLastIntent && (__cnLastIntent.valor || __cnLastIntent.entidad)) || "";

    var filas = focos.map(function (f) {
      var prod = f.producto || "";
      var pI = __CP_PROD[prod] || { icon: "circle", color: "#6E7C75" };
      var campos = (f.entidades && f.entidades.length) || 0;
      var fields = campos ? f.entidades.map(esc).join(" + ") : "";
      var share = (f.peso_relativo_pct != null) ? (String(f.peso_relativo_pct).replace(".", ",") + "%") : "—";
      var uid = "cpf-" + f.rank;

      // --- Panel 1: Comportamiento (activo por default; conserva los IDs que pinta __cnPaintFocoCharts) ---
      var pComp = '<div id="' + uid + '-comport" class="cp-foco__panel is-active" role="tabpanel" ' +
        'data-tab="comport" aria-labelledby="' + uid + '-comport-tab">' +
        '<div class="cp-foco__phd"><i class="bi bi-graph-up"></i><b>Comportamiento diario</b>' +
        '<span class="cp-foco__pmeta">· ' + esc(etiqueta) + '</span></div>' +
        '<div class="cn-desemp__grid2">' +
          '<div id="cn-foco-day-' + f.rank + '" class="cn-ins"></div>' +
          '<div id="cn-foco-mon-' + f.rank + '" class="cn-desemp__right"></div></div></div>';

      // --- Panel 2: Diferidas (lazy; reusa el contenedor .cn-dif con data-attrs) ---
      var difEnt = difEntG;
      var difCampos = (!difEnt && campos) ? f.entidades.join("|") : "";
      var pDif = '<div id="' + uid + '-dif" class="cp-foco__panel" role="tabpanel" ' +
        'data-tab="dif" aria-labelledby="' + uid + '-dif-tab">' +
        '<div class="cp-foco__phd"><i class="bi bi-droplet-half"></i><b>Diferidas</b>' +
        '<span class="cp-foco__pmeta">· histórico 2023–2025</span></div>' +
        '<div id="cn-foco-dif-' + f.rank + '" class="cn-dif" data-loaded="0" data-ent="' +
        esc(difEnt) + '" data-niv="' + esc(__cnNivel || "") + '" data-campos="' + esc(difCampos) + '"></div></div>';

      // --- Panel 3: Mantenimientos (MOCK rotulado) ---
      var pMan = '<div id="' + uid + '-mantto" class="cp-foco__panel" role="tabpanel" ' +
        'data-tab="mantto" aria-labelledby="' + uid + '-mantto-tab">' +
        '<div class="cp-foco__phd"><i class="bi bi-tools"></i><b>Mantenimientos</b>' +
        '<span class="cp-foco__pmeta">· datos de ejemplo</span></div>' +
        __cnManttoMockHtml() + '</div>';

      // --- Pills (tablist; la primera activa) ---
      var pills = __CP_TABS.map(function (t, i) {
        var on = i === 0;
        return '<button type="button" role="tab" id="' + uid + '-' + t.key + '-tab" ' +
          'aria-controls="' + uid + '-' + t.key + '" aria-selected="' + (on ? "true" : "false") + '" ' +
          'class="cp-foco__pill' + (on ? " is-active" : "") + '" data-tab="' + t.key + '" ' +
          'onclick="window.__cnFocoTab(this)">' +
          '<span class="cp-foco__ptile"><i class="bi bi-' + t.icon + '"></i></span>' +
          '<span class="cp-foco__ptxt"><span class="cp-foco__ptit">' + t.titulo + '</span>' +
          '<span class="cp-foco__psub">' + esc(t.key === "comport" ? badgeComp : t.sub) + '</span></span>' +
          '<i class="bi bi-check-circle-fill cp-foco__pcheck"></i></button>';
      }).join("");

      return '<div class="cp-foco">' +
        '<div class="cp-foco__hd">' +
          '<span class="cp-foco__rk">' + f.rank + '</span>' +
          '<i class="bi bi-' + pI.icon + ' cp-foco__prod" style="color:' + pI.color + '"></i>' +
          '<span class="cp-foco__tit">' + esc(prod) + (fields ? ' · ' + fields : "") + '</span>' +
          '<span class="cp-foco__meta">' + share + ' del faltante · ' + campos + ' campo' + (campos === 1 ? "" : "s") + '</span>' +
        '</div>' +
        '<div class="cp-foco__pills" role="tablist" aria-label="Temáticas del foco">' + pills + '</div>' +
        '<div class="cp-foco__panels">' + pComp + pDif + pMan + '</div>' +
      '</div>';
    }).join("");
    return '<div class="cn-foco__wrap"><div class="cn-foco__hdr">Focos de atención · rankeados por impacto</div>' + filas + '</div>';
  }
```

**1.c — Añadir `window.__cnFocoTab`** (JUSTO ANTES de `window.__cnFilialToggle = function`, ~2018;
anclar por ese string). No modificar `__cnFilialToggle`:

```js
  // [Fase 2] master-detail del foco: intercambia pill/panel activos. Lazy-load Diferidas + resize
  // Plotly al mostrar (mismo gancho que tenía __cnFilialToggle). Estado independiente por foco.
  window.__cnFocoTab = function (btn) {
    var foco = btn.closest(".cp-foco"); if (!foco) return;
    var key = btn.getAttribute("data-tab");
    foco.querySelectorAll(".cp-foco__pill").forEach(function (p) {
      var on = p === btn;
      p.classList.toggle("is-active", on);
      p.setAttribute("aria-selected", on ? "true" : "false");
    });
    var activo = null;
    foco.querySelectorAll(".cp-foco__panel").forEach(function (pan) {
      var on = pan.getAttribute("data-tab") === key;   // match directo pill↔panel (robusto al orden)
      pan.classList.toggle("is-active", on);
      if (on) activo = pan;
    });
    if (!activo) return;
    var dif = activo.querySelector(".cn-dif[data-loaded='0']");   // lazy la 1ª vez que se muestra Diferidas
    if (dif) { dif.dataset.loaded = "1"; try { __cnDiferidasInto(dif); } catch (e) {} }
    if (window.Plotly) {                                          // Plotly pintado en oculto → resize al mostrar
      activo.querySelectorAll(".js-plotly-plot").forEach(function (p) {
        try { window.Plotly.Plots.resize(p); } catch (e) {}
      });
    }
  };
```

> Nota: cada pill lleva `data-tab="{key}"` y su panel gemelo también → `__cnFocoTab` empareja por
> `data-tab` (no por id ni por orden). `aria-controls`/`aria-labelledby` quedan enlazados por id
> `"{uid}-{key}"` para accesibilidad, pero NO se usan en la lógica de conmutación.

**1.d — `node --check static/js/multitab_shell.js`** tras editar.

### 2. `static/css/colapsable.css` — añadir al FINAL

```css
/* ===== [2026-07-24] Fase 2 · Focos master-detail (anal.md §8-§9) ===== */
.cp-foco { background:#fff; border:1px solid #E4E9E5; border-radius:14px; overflow:hidden; margin:0 10px 14px; }
.cp-foco__hd { display:flex; align-items:center; gap:12px; padding:13px 16px; }
.cp-foco__rk { width:24px; height:24px; border-radius:7px; background:#0E5C3A; color:#fff; flex:0 0 auto;
  display:inline-flex; align-items:center; justify-content:center;
  font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-size:12px; font-weight:800; }
.cp-foco__prod { font-size:14px; flex:0 0 auto; }
.cp-foco__tit { font-size:14px; font-weight:800; color:#17241E; text-transform:uppercase;
  min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cp-foco__meta { margin-left:auto; font-size:11.5px; color:#6E7C75; white-space:nowrap; flex:0 0 auto; }
.cp-foco__pills { display:flex; gap:8px; padding:0 16px 14px; }
.cp-foco__pill { flex:1; min-width:0; display:flex; align-items:center; gap:9px; text-align:left; cursor:pointer;
  border:1px solid #E4E9E5; background:#fff; border-radius:11px; padding:10px 12px;
  transition:border-color .15s, background .15s; }
.cp-foco__pill:hover { border-color:#7FB79A; }
.cp-foco__pill.is-active { border-color:#1E9E5A; background:#F3F9F4; }
.cp-foco__pill:focus-visible { outline:none; box-shadow:0 0 0 2px rgba(30,158,90,.5); }
.cp-foco__ptile { width:30px; height:30px; border-radius:8px; flex:0 0 auto; display:inline-flex;
  align-items:center; justify-content:center; background:#F3F9F4; }
.cp-foco__ptile i { font-size:15px; color:#15794C; }
.cp-foco__pill.is-active .cp-foco__ptile { background:#0E5C3A; }
.cp-foco__pill.is-active .cp-foco__ptile i { color:#fff; }
.cp-foco__ptxt { display:flex; flex-direction:column; min-width:0; }
.cp-foco__ptit { font-size:12.5px; font-weight:800; color:#17241E; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cp-foco__psub { font-size:10.5px; color:#6E7C75; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cp-foco__pcheck { margin-left:auto; font-size:14px; color:#1E9E5A; flex:0 0 auto; display:none; }
.cp-foco__pill.is-active .cp-foco__pcheck { display:inline; }
.cp-foco__panel { display:none; padding:16px; background:#F6F8F5; border-top:1px solid #E4E9E5; }
.cp-foco__panel.is-active { display:block; }
.cp-foco__panel .cn-desemp__grid2 { min-height:300px; }   /* [Hallazgo C] repone la altura de .cn-foco__acc */
.cp-foco__panel .cn-ins { height:auto; }
.cp-foco__phd { display:flex; align-items:center; gap:7px; margin-bottom:11px; font-size:12px; font-weight:800; color:#0A4A2E; }
.cp-foco__phd i { font-size:13px; color:#15794C; }
.cp-foco__pmeta { font-weight:600; color:#98A69E; font-size:11px; }
.cp-foco__mock { font-size:11px; font-style:italic; color:#8b948e; margin-bottom:8px; }
.cp-foco__mock i { font-size:11px; }
.cp-foco__mtbl { border:1px solid #E4E9E5; border-radius:10px; overflow:hidden; background:#fff; }
.cp-foco__mrow { display:grid; grid-template-columns:90px 1fr 120px 70px; align-items:center; gap:12px;
  padding:9px 13px; border-top:1px solid #EEF2EF; }
.cp-foco__mrow:first-child { border-top:none; }
.cp-foco__mpozo { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-size:12px; font-weight:700; color:#17241E; }
.cp-foco__mtipo { font-size:12.5px; color:#3C4A44; }
.cp-foco__mest { display:inline-flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600; }
.cp-foco__mdot { width:6px; height:6px; border-radius:50%; background:#98A69E; display:inline-block; flex:0 0 auto; }
.cp-foco__mest.is-ejec { color:#E8912B; }
.cp-foco__mest.is-ejec .cp-foco__mdot { background:#E8912B; }
.cp-foco__mest.is-prog { color:#6E7C75; }
.cp-foco__mfin { font-size:11.5px; color:#6E7C75; text-align:right; }
@media (max-width:720px) {
  .cp-foco__pills { flex-direction:column; }
  .cp-foco__mrow { grid-template-columns:1fr 1fr; }
}
@media (prefers-reduced-motion: reduce) { .cp-foco * { transition:none !important; } }
```

> Las clases del acordeón viejo (`.cn-foco--acc`, `.cn-foco__acc`, y el uso de `.cn-filial*` dentro
> del foco) quedan **sin uso en ECP** pero NO se borran (las sigue usando la rama Filiales). Inocuas.

### 3. `templates/main.html` — cache-buster

`?v=20260724d1` → `?v=20260724e1` (líneas 5 y 82).

---

## Reglas no negociables

- **NO** tocar el backend, ni `/api/analisis/ejecutivo`, ni `/api/diferidas/frecuencia`, ni los datos.
- **NO** tocar la rama Filiales de `__cnFocosHtml` (1962-1981), ni `__cnFilialToggle`,
  `__cnFocoToggle`, `__cnSeriesToggle`, ni `__cnPaintFocoCharts`/`__cnDailyInto`/`__cnMonthlyInto`
  (las gráficas se reusan intactas).
- **Conservar los IDs** `cn-foco-day-{rank}`, `cn-foco-mon-{rank}`, `cn-foco-dif-{rank}` con el
  mismo formato y el contenedor `.cn-dif` con sus `data-ent/data-niv/data-campos` (el lazy y el
  pintado dependen de ellos).
- Comportamiento = **panel activo por defecto y visible** (si queda `display:none`, Plotly pinta a 0).
- Mantenimientos = mock **rotulado** como ejemplo (honestidad); nunca presentarlo como dato real.
- Español con tildes; `esc()` en todo texto de dato; estado solo en verde/ámbar/rojo, sin azul.

---

## Verificación

1. `node --check static/js/multitab_shell.js` → sin errores.
2. Reiniciar **Flask :8020** (procedimiento WDAC: matar PID en 8020 + relanzar con el python base de
   uv + `PYTHONPATH=venv/Lib/site-packages`) y **Ctrl+F5**.
3. Navegador → Consulta → **global** → "Desempeño del mes":
   - **2 focos** (#1 GAS · CUSIANA + CUPIAGUA · "88,2% del faltante · 2 campos"; #2 BLANCOS ·
     CUSIANA + PAUTO SUR · "76,4% del faltante · 2 campos") con badge de rango verde + icono de producto.
   - **3 pills** por foco (Comportamiento / Diferidas / Mantenimientos), la 1ª activa con check verde
     y tile verde relleno; sublíneas "17/31 en curso" · "frecuencia histórica" · "3 de ejemplo".
   - **Comportamiento activo por default**: las **2 gráficas Plotly** (diaria + mensual) se ven al
     abrir (no colapsadas). Cambiar de pill **intercambia el panel** sin colapsar/saltar el layout.
   - **Diferidas**: al activar la pill por 1ª vez, carga (lazy) las 3 tarjetas históricas (Pareto +
     tendencia + pozos). Volver a Comportamiento → las gráficas se **re-dimensionan** (no quedan a 0).
   - **Mantenimientos**: tabla mock (CUS-14 "En ejecución" en ámbar; CUP-07 / CUS-31 "Programado"),
     con la banda "Datos de ejemplo · sin fuente real conectada".
   - Estado independiente por foco: cambiar la pill del foco #1 NO cambia la del foco #2.
4. **Regresión**: "Desempeño Filiales" SIN cambio (sigue con su acordeón `.cn-filial` y "Ver →");
   las tarjetas KPI con anillo de Fase 1 intactas; consola con 0 errores JS.

---

## Fuera de alcance (v1)

- Reescribir los 2 gráficos a CSS/SVG (§9.1): se reusan los Plotly existentes.
- Badge "N eventos/incidentes" real en la pill Diferidas (exige el conteo lazy; queda "frecuencia
  histórica"). Mejora opcional: que `__cnDiferidasInto` actualice la sublínea con `meta.total_incidentes`.
- Fuente real de Mantenimientos (no existe dato) — el mock se reemplaza cuando llegue.
- Navegación por teclado ←/→ entre pills (roving tabindex, §11): v1 deja click + focus visible;
  las pills ya son `role="tab"` con `aria-selected`/`aria-controls` y los paneles `role="tabpanel"`.
- Header verde / riel / contenedor `max-width:1280px` (§6): ya existen en el shell; no se rehacen.
