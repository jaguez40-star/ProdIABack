# Plan ejecutable — Rediseño «Desempeño del mes» · FASE 1: tarjetas KPI con anillo

> **Para un Executor sin contexto previo del repo.** Ejecuta este plan al pie de la letra.
> Es un **rediseño de PRESENTACIÓN**: los datos NO cambian (mismo backend, mismos campos). Solo se
> reescribe cómo se pintan las 3 tarjetas KPI (Crudo/Gas/Blancos) del panel «Desempeño del mes»:
> de 2 barras + texto → **anillo SVG de % cumplimiento + chip de estado con icono + 1 barra de
> proyección + microcopy de gap**. Basado en el diseño aprobado `anal.md` (propuesta A+C).
> **Alcance = SOLO Fase 1** (KPI). Los Focos con pills master-detail son la Fase 2 (otro plan).

---

## Contexto

- App: ProdIA / «Consulta de Producción», panel derecho «Desempeño del mes» del MultiTab Shell.
- Este panel es **vanilla JS** (no React): vive en `static/js/multitab_shell.js` (funciones `__cn*`),
  estilos en `static/css/colapsable.css`, servido por Flask. El spec `anal.md` está escrito para React
  pero **se traduce a este stack** (mismo patrón que ya se hizo con el chat «Asimétrico esencial»).
- Las 3 tarjetas hoy las pinta `__cnTarjetasKpiHtml(tarjetas, periodo)`. Los números
  (`proyectado_cierre`, `meta_mes`, `relleno_pct`, `estado`, `bopd`, `hist_prom`, `brecha_abs`,
  `alcanza`, `unidad`) ya vienen calculados del backend (`/api/analisis/ejecutivo` → `_tarjetas_kpi`);
  esta función SOLO formatea. **No se toca el backend.**

## Objetivo

Reemplazar el cuerpo de `__cnTarjetasKpiHtml` por el render de anillo (clases `cp-mes__kpi*`), añadir los
helpers `__cnRing` + `__cnKpiStatus`, y agregar el CSS `.cp-mes__kpi*`. Sin cambiar los 3 puntos de
llamada, ni el backend, ni los focos/gráficas.

## Auditoría previa (flujo §0.2 · con datos reales del endpoint, 2026-07-24)

Verificado contra `GET /api/analisis/ejecutivo` (ECP y `?segmento=filiales`) en dev:

| # | Hallazgo | Resolución en este plan |
|---|---|---|
| A | La función real es **líneas 1848–1941** (`__cnKpiLabel` está en 1847 justo encima; 1842 es `__cnGasM`). | Anclas por **string**, no por número (abajo). |
| B | Los **3** call sites envuelven en `<div class="cn-kpi__row">`: `1165` (panel Filiales), `2074` (Desempeño del mes), `2113–2114` (`__cnPorFilialHtml`, desglose por filial). | No se tocan; el render nuevo encaja en ese grid. |
| C | **Ningún** JS lee `.cn-kpi__*` por `querySelector`/`getElementsBy` (solo aparecían dentro de la función a reemplazar). | Reemplazar el markup es seguro; no rompe pipelines. |
| D | **Bootstrap Icons cargado** (`templates/base.html`, `bootstrap-icons@1.11.3`). | Iconos `bi bi-*` disponibles. |
| E | **🔴 Bug de estado:** en la rama Blancos/filiales, derivar el estado de `may < hist` marca rojo un 94% que el backend ya clasificó **ajustado** (banda ámbar ≥93%). Caso real: CRUDO de Hocol (`relleno=94, estado="ajustado"`, pero `proy<hist_prom`). | **Usar `k.estado`** del backend vía `__cnKpiStatus(k)` (mapea `actuar→"bajo"` solo sin ritmo diario). |
| F | Datos reales ECP: CRUDO `ajustado/bopd/relleno=94.7`; GAS `actuar/bopd/relleno=87`; BLANCOS `actuar/bopd=False/hist=828212/proy=618914/relleno=58.5`. Anillo Blancos = `may/hist`≈75% (mockup 72), barra = `relleno`≈58.5% (mockup 56). | Semántica preservada por rama; anillo Blancos = vs **promedio del año** (rotulado). |
| G | Filiales: `bopd=False` en todas (rama Blancos) y `meta_mes == hist_prom` (sin PPTO → la meta ES el promedio 2026). | El render de anillo aplica igual; el fix E evita falsos rojos. |
| H | **🟡 Mejora:** capar el % del anillo a 100 oculta el sobre-cumplimiento (>100%). | `__cnRing` topa el **arco** en 100 pero muestra el **texto** real. |

## Prerequisitos

- Rutas absolutas de trabajo (Windows):
  - JS: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js`
  - CSS: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\css\colapsable.css`
  - HTML: `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html`
- Node disponible para `node --check` (validación de sintaxis JS).
- Bootstrap Icons (`<i class="bi bi-...">`) YA está cargado en la app (se usan `bi-activity`,
  `bi-droplet-half`, etc.). Los iconos nuevos (`droplet-fill`, `fire`, `droplet`, `check-circle-fill`,
  `exclamation-triangle-fill`, `exclamation-octagon-fill`, `arrow-down-circle-fill`) son de ese set.
- Reinicio de Flask :8020 (procedimiento WDAC): matar el PID que escucha en 8020 y relanzar con el
  intérprete BASE de uv + PYTHONPATH:
  ```bash
  netstat -ano | grep ":8020" | grep LISTENING           # obtener PID
  taskkill //F //PID <PID>
  cd "c:/APLICACIONES/ProdIA/12112025_prodIA/12112025_prodIA"
  PYF="C:/Users/jague/AppData/Roaming/uv/python/cpython-3.13-windows-x86_64-none/python.exe"
  export PYTHONPATH="$(pwd)/venv/Lib/site-packages"
  nohup "$PYF" app.py > /tmp/flask.log 2>&1 &
  ```

## Inventario de archivos

| Archivo | Cambio |
|---|---|
| `static/js/multitab_shell.js` | (1) Añadir helper `__cnRing` + mapas `__CP_STATUS`/`__CP_PROD`. (2) Reemplazar TODO el cuerpo de `__cnTarjetasKpiHtml`. |
| `static/css/colapsable.css` | Añadir bloque `.cp-mes__kpi*` (al final del archivo). |
| `templates/main.html` | Cache-buster `?v=20260724c2` → `?v=20260724d1` (líneas 5 y 82). |

**NO tocar:** el backend, los 3 puntos de llamada a `__cnTarjetasKpiHtml` (siguen envueltos en
`<div class="cn-kpi__row">…</div>`), las funciones de focos/gráficas, ni las clases `.cn-kpi__*`
existentes (quedan sin uso pero **no se borran** — inocuas).

---

## Especificación

### 1. `static/js/multitab_shell.js` — helpers `__cnRing`, `__cnKpiStatus` + mapas

Insertar este bloque **inmediatamente ANTES** de la línea `function __cnTarjetasKpiHtml(tarjetas, periodo) {`
(hoy línea **1848**; justo encima está `var __cnKpiLabel = {...};` en la 1847, y `__cnGasM` termina antes).
Anclar por ese string, no por número. Código completo a pegar:

```js
  // ===== [2026-07-24] Rediseño A+C · Fase 1: anillo de % cumplimiento + estado color-codeado =====
  // Tokens y labels tomados de anal.md §4 (status.ts). El color/soft se inyecta por --cp-st/--cp-st-soft.
  var __CP_STATUS = {
    ok:       { label: "En meta",    color: "#1E9E5A", soft: "#E9F3EC", icon: "check-circle-fill" },
    ajustado: { label: "Ajustado",   color: "#E8912B", soft: "#FBF1E4", icon: "exclamation-triangle-fill" },
    actuar:   { label: "Actuar",     color: "#C5311E", soft: "#FBECEA", icon: "exclamation-octagon-fill" },
    bajo:     { label: "Por debajo", color: "#C5311E", soft: "#FBECEA", icon: "arrow-down-circle-fill" },
    neutral:  { label: "",           color: "#98A69E", soft: "#F1F4F1", icon: "" }
  };
  var __CP_PROD = { CRUDO: { icon: "droplet-fill" }, GAS: { icon: "fire" }, BLANCOS: { icon: "droplet" } };

  // [Hallazgo E] Estado = el `estado` que YA calculó el backend con la banda ámbar (≥93% ajustado).
  // NO derivar de "may<hist" (marcaría un 94% ajustado como rojo). En la rama sin ritmo diario
  // (Blancos/filiales) el "actuar" se rotula "Por debajo" (bajo); en Crudo/Gas se rotula "Actuar".
  // "" = producto sin meta comparable → neutral (anillo gris, sin chip).
  function __cnKpiStatus(k) {
    var e = k.estado;
    if (e === "alineado") return "ok";
    if (e === "ajustado") return "ajustado";
    if (e === "actuar")   return (k.bopd && k.bopd.requerido) ? "actuar" : "bajo";
    return "neutral";
  }

  // Anillo SVG 66x66 (anal.md §7): track gris + arco de color, linecap round, rotado -90°, % al centro.
  // [Hallazgo H] El ARCO topa en 100% (no desborda); el TEXTO muestra el % REAL (p. ej. 108%) — no
  // oculta el sobre-cumplimiento.
  function __cnRing(pct, color) {
    var raw = Math.round(pct == null ? 0 : pct);
    var arc = Math.max(0, Math.min(100, raw)), txt = Math.max(0, raw);
    var size = 66, r = (size - 8) / 2, c = 2 * Math.PI * r, cx = size / 2;
    var dash = (c * arc / 100).toFixed(1) + " " + c.toFixed(1);
    return '<svg class="cp-mes__ring" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" ' +
      'role="img" aria-label="Cumplimiento ' + txt + '%">' +
      '<circle cx="' + cx + '" cy="' + cx + '" r="' + r + '" fill="none" stroke="#E4E9E5" stroke-width="7"/>' +
      '<circle cx="' + cx + '" cy="' + cx + '" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="7" ' +
      'stroke-linecap="round" stroke-dasharray="' + dash + '" transform="rotate(-90 ' + cx + ' ' + cx + ')"/>' +
      '<text x="' + cx + '" y="' + cx + '" text-anchor="middle" dominant-baseline="central" ' +
      'font-size="16" font-weight="800" fill="#17241E">' + txt + '%</text></svg>';
  }
```

### 2. `static/js/multitab_shell.js` — reemplazar `__cnTarjetasKpiHtml`

**Reemplazar la función COMPLETA** — desde la línea `function __cnTarjetasKpiHtml(tarjetas, periodo) {`
(línea **1848**) hasta su cierre `}).join("");` + `}` (línea **1941**, justo antes del comentario
`// Nivel 2: franja "Focos de atención".` en la 1943). Sustituir todo ese cuerpo por:

```js
  function __cnTarjetasKpiHtml(tarjetas, periodo) {
    if (!tarjetas || !tarjetas.length) return "";
    var mesWord = periodo ? String(periodo).split(" ")[0] : "el mes";
    var yearWord = (periodo && String(periodo).split(" ")[1]) ? String(periodo).split(" ")[1] : "el año";
    return tarjetas.map(function (k) {
      var esGas = k.producto === "GAS";
      var fmtV = esGas ? __cnGasM : __cnFmtKpi;                          // volumen mensual
      var fmtR = esGas ? function (v) { return __cnGasM(v, 2); } : __cnFmtBopd;  // ritmo diario
      var unidad = k.unidad ? (" " + esc(k.unidad) + "/mes") : "";
      var nombre = k.producto.charAt(0).toUpperCase() + k.producto.slice(1).toLowerCase();
      var prodIcon = (__CP_PROD[k.producto] || {}).icon || "circle";
      var statusKey = __cnKpiStatus(k), S = __CP_STATUS[statusKey] || __CP_STATUS.neutral;   // [Hallazgo E]

      // --- anillo + fila superior según la rama de datos (NO se cambia el significado del número) ---
      var ringPct, figLbl, figVal, pptoLbl, pptoVal;
      if (k.bopd && k.bopd.requerido) {                     // CRUDO / GAS: ritmo diario real vs PPTO
        ringPct = Math.round(k.bopd.real / k.bopd.requerido * 100);
        var duni = k.unidad === "bbl" ? "BOPD" : (k.unidad === "MSCF" ? "MSCFD" : (k.unidad ? k.unidad + "/d" : "/d"));
        figLbl = "Producción actual diaria";
        figVal = fmtR(k.bopd.real) + ' <span class="cp-mes__kpi-unit">' + duni + '</span>';
        pptoLbl = "PPTO"; pptoVal = fmtR(k.bopd.requerido);
      } else {                                              // BLANCOS / filiales: mes vs promedio del año
        var hist = k.hist_prom || 0, may = k.proyectado_cierre || 0;
        ringPct = hist ? Math.round(may / hist * 100) : (k.meta_mes ? Math.round(may / k.meta_mes * 100) : 0);
        figLbl = "Producción de " + esc(mesWord);
        figVal = fmtV(may) + ' <span class="cp-mes__kpi-unit">' + esc(k.unidad || "") + '/mes</span>';
        pptoLbl = "Promedio " + esc(yearWord); pptoVal = hist ? fmtV(hist) : "—";
      }

      // --- proyección de cierre + microcopy de gap ---
      var proyPct = Math.max(0, Math.min(100, Math.round(k.relleno_pct == null ? 0 : k.relleno_pct)));
      var proyTxt = k.meta_mes
        ? (fmtV(k.proyectado_cierre) + " / " + fmtV(k.meta_mes) + unidad)
        : (fmtV(k.proyectado_cierre) + unidad + " · sin meta");
      var closeMicro = !k.meta_mes
        ? "Sin meta definida para " + esc(nombre.toLowerCase()) + "."
        : (k.alcanza
            ? 'Cerraría <span class="cp-mes__kpi-gap">' + fmtV(k.proyectado_cierre - k.meta_mes) + unidad + '</span> por encima de la meta.'
            : 'Cerraría <span class="cp-mes__kpi-gap">' + fmtV(k.brecha_abs) + unidad + '</span> por debajo de la meta.');
      var chip = statusKey === "neutral" ? ""
        : '<span class="cp-mes__kpi-badge"><i class="bi bi-' + S.icon + '"></i> ' + S.label + '</span>';

      return '<div class="cp-mes__kpi cp-mes__kpi--' + statusKey + '" style="--cp-st:' + S.color + ';--cp-st-soft:' + S.soft + '">' +
        '<div class="cp-mes__kpi-hd">' +
          '<span class="cp-mes__kpi-chip"><i class="bi bi-' + prodIcon + '"></i></span>' +
          '<span class="cp-mes__kpi-name">' + esc(nombre) + '</span>' + chip +
        '</div>' +
        '<div class="cp-mes__kpi-mid">' + __cnRing(ringPct, S.color) +
          '<div class="cp-mes__kpi-fig">' +
            '<div class="cp-mes__kpi-figlbl">' + figLbl + '</div>' +
            '<div class="cp-mes__kpi-figval">' + figVal + '</div>' +
            '<div class="cp-mes__kpi-ppto">' + pptoLbl + ' <b>' + pptoVal + '</b></div>' +
          '</div>' +
        '</div>' +
        '<div class="cp-mes__kpi-sep"></div>' +
        '<div class="cp-mes__kpi-proyhd"><span>Proyección de cierre</span>' +
          '<span class="cp-mes__kpi-proyval">' + proyTxt + '</span></div>' +
        '<div class="cp-mes__meter"><span style="width:' + proyPct + '%;background:' + S.color + '"></span></div>' +
        '<div class="cp-mes__kpi-close">' + closeMicro + '</div>' +
        '</div>';
    }).join("");
  }
```

> Notas de fidelidad al dato (NO cambiar):
> - **Anillo % = "cumplimiento"** que ya calculaba cada rama: CRUDO/GAS = `bopd.real/bopd.requerido`;
>   BLANCOS/filiales = `proyectado_cierre/hist_prom` (mes vs promedio del año). No forzar BLANCOS a un
>   "diario vs PPTO" (su diario NO reconcilia — por eso el backend lo trata aparte).
> - **Barra de proyección = `relleno_pct`** (clamp 0–100). El microcopy de gap usa `brecha_abs`/`alcanza`.
> - Las 3 llamadas a `__cnTarjetasKpiHtml` (incluida la de **filiales**) comparten esta función →
>   filiales también recibe el render de anillo (consistente y correcto: caen por la rama BLANCOS).

### 3. `static/css/colapsable.css` — añadir al FINAL del archivo

```css
/* ===== [2026-07-24] Rediseño A+C · Fase 1: tarjetas KPI con anillo (anal.md §4/§7) ===== */
.cp-mes__kpi { display: flex; flex-direction: column; background: #fff; border: 1px solid #E4E9E5;
  border-radius: 14px; padding: 15px 16px; box-shadow: 0 1px 2px rgba(20,40,30,.04); min-width: 0; }
.cp-mes__kpi-hd { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; }
.cp-mes__kpi-chip { width: 26px; height: 26px; border-radius: 8px; display: inline-flex;
  align-items: center; justify-content: center; background: var(--cp-st-soft); flex: 0 0 auto; }
.cp-mes__kpi-chip i { font-size: 14px; color: var(--cp-st); }
.cp-mes__kpi-name { font-size: 15px; font-weight: 800; color: #17241E; }
.cp-mes__kpi-badge { margin-left: auto; display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 700; color: var(--cp-st); background: var(--cp-st-soft);
  border-radius: 20px; padding: 3px 10px; white-space: nowrap; }
.cp-mes__kpi-badge i { font-size: 10px; }
.cp-mes__kpi-mid { display: flex; align-items: center; gap: 14px; }
.cp-mes__ring { flex: 0 0 auto; }
.cp-mes__kpi-fig { min-width: 0; }
.cp-mes__kpi-figlbl { font-size: 11px; font-weight: 600; color: #98A69E; }
.cp-mes__kpi-figval { font-size: 22px; font-weight: 800; color: #17241E; letter-spacing: -.5px; line-height: 1.15; }
.cp-mes__kpi-unit { font-size: 11.5px; font-weight: 600; color: #6E7C75; letter-spacing: 0; }
.cp-mes__kpi-ppto { font-size: 11px; color: #98A69E; margin-top: 1px; }
.cp-mes__kpi-ppto b { color: #3C4A44; font-weight: 700; }
.cp-mes__kpi-sep { height: 1px; background: #EEF2EF; margin: 13px 0 11px; }
.cp-mes__kpi-proyhd { display: flex; justify-content: space-between; align-items: baseline;
  font-size: 11px; font-weight: 600; color: #98A69E; }
.cp-mes__kpi-proyval { font-family: ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-size: 11px; color: #6E7C75; }
.cp-mes__meter { height: 7px; border-radius: 7px; background: #EEF2EF; overflow: hidden; margin-top: 5px; }
.cp-mes__meter > span { display: block; height: 100%; border-radius: 7px; }
.cp-mes__kpi-close { font-size: 11.5px; color: #3C4A44; margin-top: 9px; }
.cp-mes__kpi-gap { font-weight: 700; color: var(--cp-st); }
@media (prefers-reduced-motion: reduce) { .cp-mes__kpi * { transition: none !important; } }
```

> El contenedor `.cn-kpi__row` (grid de 3 columnas responsive) NO se toca: sigue envolviendo las tarjetas
> desde los puntos de llamada. Las nuevas `.cp-mes__kpi` encajan en ese grid.

### 4. `templates/main.html` — cache-buster

Reemplazar **ambas** ocurrencias (línea 5 = CSS, línea 82 = JS): `?v=20260724c2` → `?v=20260724d1`.

---

## Orden de ejecución

1. Editar `static/js/multitab_shell.js`: insertar el bloque §1 (mapas + `__cnRing`) antes de
   `__cnTarjetasKpiHtml`; luego reemplazar la función completa por la de §2.
2. Añadir el CSS §3 al final de `static/css/colapsable.css`.
3. Cambiar el cache-buster en `templates/main.html` (§4).
4. `node --check static/js/multitab_shell.js` → debe imprimir sin errores.
5. Reiniciar Flask :8020 (ver Prerequisitos).
6. Validar (abajo).

## Reglas no negociables

- **NO tocar el backend** ni el significado de ningún número (es rediseño de presentación).
- **NO tocar** los 3 puntos de llamada a `__cnTarjetasKpiHtml`, ni las funciones de focos/gráficas
  (`__cnFocosHtml`, `__cnDailyInto`, `__cnDiferidasInto`, etc.) — eso es Fase 2.
- **NO borrar** las clases `.cn-kpi__*` existentes.
- Verde PRODIA; estado SOLO en ámbar (#E8912B) / rojo (#C5311E). Nada de azul.
- Todo texto en español con tildes. Escapar siempre con `esc(...)` los valores de texto.
- Accesibilidad: el anillo lleva `role="img"` + `aria-label="Cumplimiento N%"`; el estado se comunica
  con icono + etiqueta (no solo color); el % va como texto dentro del anillo.

## Validaciones (comando → resultado esperado)

1. **Sintaxis JS:** `node --check static/js/multitab_shell.js` → sin salida (OK).
2. **Payload backend intacto** (con Flask arriba): 
   `curl -s "http://127.0.0.1:8020/api/analisis/ejecutivo" | python -c "import sys,json;d=json.load(sys.stdin);print([(t['producto'],t.get('estado'),t.get('relleno_pct'),bool(t.get('bopd'))) for t in d.get('tarjetas',[])])"`
   → lista con los 3 productos y sus campos (CRUDO/GAS con `bopd` truthy; BLANCOS con `bopd` None).
   (No cambia respecto a hoy — sirve para confirmar que la función tiene los datos que consume.)
3. **Navegador ECP** (tras hard-refresh Ctrl+F5): pestaña Consulta → global → panel «Desempeño del mes».
   Verificar en las 3 tarjetas (valores reales auditados en dev):
   - **Crudo:** anillo con el % del ritmo diario, chip **Ajustado** (ámbar `#E8912B`, icono
     `exclamation-triangle-fill`), cifra `2,85M BOPD` + `PPTO 3,…M`, barra proyección ámbar ≈ **95%**
     (`relleno_pct=94.7`), microcopy "Cerraría **4,9M bbl/mes** por debajo de la meta."
   - **Gas:** chip **Actuar** (rojo `#C5311E`, `exclamation-octagon-fill`), `2,34 MSCFD`, barra ≈ **87%**,
     gap **10,8 MSCF/mes**.
   - **Blancos:** anillo ≈ **75%** (`may/hist` = 618914/828212, vs **promedio del año**), chip
     **Por debajo** (rojo, `arrow-down-circle-fill`), `619k bbl/mes` + `Promedio … 828k`, barra ≈ **58%**
     (`relleno_pct=58.5`, vs meta), gap **438k bbl/mes**.
4. **Regresión filiales [Hallazgo E — el que motivó el fix]:** en «Desempeño Filiales» y en el desglose
   «Comportamiento por filial», las tarjetas renderizan como anillo (rama Blancos, `bopd=False`). Verificar
   que el **CRUDO de Hocol** (`estado="ajustado"`, `relleno=97.2`) sale **Ajustado (ámbar)**, NO rojo
   "Por debajo" (con la lógica vieja `may<hist` salía rojo — esa es la incoherencia corregida).
   GAS/BLANCOS de filiales en `alineado` → **En meta** (verde). 0 errores de consola.
5. **Consola del navegador:** 0 errores JS. `#cn-kpi__row` / focos / gráficas y sección Diferidas
   siguen intactos (no se tocaron).

## Fuera de alcance (NO hacer en Fase 1)

- Focos con pills master-detail (Fase 2, plan aparte).
- Panel Mantenimientos mock (Fase 2).
- Gráficas de comportamiento (se quedan como están, en Plotly).
- Cambios de datos, backend, o del significado de los KPIs.
- Cargar la fuente Inter (se usa la tipografía ya presente en el shell; solo el valor de proyección va
  en mono del sistema).
