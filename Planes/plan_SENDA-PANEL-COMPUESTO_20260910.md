# Plan SENDA-PANEL-COMPUESTO — el panel de senda pasa a contexto + detalle + cifras

| | |
|---|---|
| **ID tarea** | SENDA-PANEL-COMPUESTO |
| **Fecha** | 2026-09-10 |
| **Versión** | v2 — auditado contra el ancho REAL de la pila y contra los pipelines |
| **Alcance** | Panel `analiza_senda` **del chat**: de un gráfico de barras apiladas a un panel de tres piezas (año en líneas · zoom con la brecha · tabla de cifras) con leyenda compartida. Backend: la serie completa viaja al panel. CSS nuevo. Cache-busters. |
| **Qué NO se toca** | 🔴 **`__cnSendaPlotInto`** (compartida con el tablero), `__cnPaintSenda`, `__cnSendaHtml`, el **tablero de Analizar** (sigue con sus barras apiladas), `analisis/api.py`, `plantilla.senda()` (el texto no cambia), `__cnPanelMesHtml` y las reglas de `.cn-compprod__grid` |
| **Predecesores** | `plan_SENDA-CHAT_20260910.md` (`0a09915`/`f41caef`) y `plan_SENDA-SOLO-FUTURO_20260910.md` (`6cc3439`/`5abfb20`). Este los extiende; no los revierte. |
| **Mockup aprobado** | `https://claude.ai/code/artifact/c70c75da-9127-4604-b5b1-a14defcb6354` |

### Decisiones cerradas del usuario

1. **El panel del chat pasa a líneas**, en tres piezas: contexto anual · detalle oct-dic con la brecha sombreada · tabla de cifras.
2. **El texto de la respuesta no cambia**: sigue hablando solo de los meses futuros.
3. **La banda sombreada del año arranca en la línea de proyectado**, no un mes después.
4. **En la tabla, Ecopetrol y filiales van sin color e indentadas**: no se dibujan, son los componentes que suman al total.
5. **El tablero de Analizar no cambia** en este plan.

---

## §0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — chat de producción de Ecopetrol. Dos repos git hermanos:

| | Ruta | Stack | Puerto |
|---|---|---|---|
| Frontend | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | Flask + Jinja2 + JS ES5 | 5029 |
| Backend | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\` | FastAPI (`uv`) | 5030 |

**Archivos que se tocan — SON SEIS:**

| # | Archivo | Qué |
|---|---|---|
| A | `backend\backend\app\features\consulta_v2\respuesta_analizar.py` | la serie COMPLETA + los meses futuros viajan al panel |
| B | `frontend\static\js\multitab_shell.js` | constructor y pintores nuevos del panel |
| C | `frontend\static\css\colapsable.css` | bloque CSS nuevo, al final |
| D | `frontend\MainChat\templates\mainchat_layout.html` | cache-buster **CSS + JS** |
| E | `frontend\templates\main.html` | cache-buster **CSS + JS** |
| F | `frontend\templates\login.html` | cache-buster **CSS + JS** (prefetch) |

**Convenciones obligatorias:**

- JS **ES5 clásico**: `var` + `function`. Prohibido `const`, `let`, arrow functions, template literals. El ternario sí vale.
- Comentarios **en español**, prefijo `[2026-09-10 · SENDA-PANEL]`.
- 🔴 **PROHIBIDO escribir la cadena `CLAUDE.md` en comentarios de código**: `migrar_a_azure.ps1:87,181` la detecta (case-insensitive) y aborta el despliegue entero. Escribir «la guía del proyecto §N».
- Anclas «LOCALIZAR» copiadas del archivo real. Si una no aparece literal → **DETENERSE y reportar**.
- Tras tocar el `.py`: **reiniciar el backend** (uvicorn corre sin `--reload`).

---

## §1. Hallazgos de la auditoría

### 🔴 H1 — Tres columnas iguales NO caben en la pila del chat
El mockup se diseñó a **1240 px**, que es el ancho del **tablero**. La pila del chat es mucho más estrecha. Cadena de contenedores medida sobre el CSS fuente (`colapsable.css`): `.main-content` (`style.css:226`, `--sidebar-width: 280px`) → `.rb-cp__rail` 60 px (`:124`) → `.rb-cp__panel` **581 px** (`:212`) → `.cn-railbar` 51 px (`:1547`) → `.cn-stack` padding 28 px (`:1601`) → `.cn-stk` bordes+padding 26 px (`:1603`).

| Vista / viewport | Ancho útil del panel |
|---|---|
| `/mainchat` a 1920 | **≈915 px** |
| `/` clásico a 1920 | **≈813 px** |
| `/` clásico a 1366 | **≈259 px** |

Tres columnas de 400 px piden 1224 px: **no caben en ningún escenario**. Y el propio CSS ya lo documenta para otro panel (`colapsable.css:2266-2270`): *«entre 1280 y 1440px de viewport solo dispone de ~323-403px una vez descontados el rail, el chat y los paddings»*.

**Determina §3.C**: el layout NO son tres columnas. Es **el año a ancho completo arriba** (que es quien necesita el ancho: doce meses) y **zoom + tabla abajo en dos columnas adaptativas**. Con `repeat(auto-fit, minmax(...))`, igual que `.cn-dif__cols` (`colapsable.css:1742`).

### 🔴 H2 — La altura está capada en 375 px y lo que sobra se recorta EN SILENCIO
`colapsable.css:2560` → `.cn-stk__body .cp-foco__panel .cn-compprod__grid { height: 375px; }` y `.cn-ins` lleva `overflow: hidden` (`:1231`). El panel compuesto necesita ~520 px: dentro de ese envoltorio se cortaría **sin lanzar error**, el fallo silencioso de siempre.

**Determina §3.B**: el panel nuevo **no usa `__cnPanelMesHtml`**. Construye su propio envoltorio, con el precedente ya resuelto de `__cnDifPanelHtml` (`multitab_shell.js:2989-3002`), que monta `.cn-difblk` con su propia cabecera y su propio host sin pasar por el grid mensual.

### 🔴 H3 — `__cnSendaPlotInto` es COMPARTIDA con el tablero: no se toca
Cadena verificada: el tablero llega por `__cnPaintSenda` (`:6474`, call sites `:2213` y `:3557`) y el chat por `__cnSendaMesInto` (`:6502`); **ambos terminan en `__cnSendaPlotInto` (`:6306`)**. Su cabecera lo declara: *«Una sola función = una sola paleta, un solo layout, un solo sitio donde arreglar»*.

Tocarla cambiaría el tablero, que en este plan **no cambia**. **Determina §3.B**: funciones nuevas (`__cnSendaCtxInto`, `__cnSendaZoomInto`, `__cnSendaTablaHtml`), y solo se reescriben `__cnAnzSendaHtml` y `__cnSendaMesInto`. El tablero queda bit a bit idéntico y no hay que revalidarlo.

### 🔴 H4 — El frontend necesita los DOCE meses; hoy le llegan tres
Tras `plan_SENDA-SOLO-FUTURO`, `respuesta_analizar.py:511` manda `_s_chat` con la serie recortada a oct-dic. El panel de contexto necesita ene-dic.

**Pero el corte no se duplica**: el backend sigue siendo el único que decide qué es futuro, y **manda la lista** (`meses_futuros`). El frontend no recalcula la regla — la obedece. Así se conserva la propiedad que ganamos en el plan anterior (un solo filtro) aunque ahora haya dos consumidores del dato. **Determina §3.A.**

### 🔴 H5 — Los tres `?v=` de `colapsable.css` están desincronizados
Verificado:

| Archivo:línea | Token |
|---|---|
| `templates\main.html:5` | `20260908b` |
| `templates\login.html:39` | `20260831a` |
| `MainChat\templates\mainchat_layout.html:13` | `20260907b` |

Como el CSS nuevo es imprescindible para el layout, **si no se suben los tres el panel se pinta sin estilos** justo en `/mainchat`, que es donde hay ancho. Se suben también los tres del JS. **Determina §3.D-F**: 6 ediciones en 3 archivos.

### 🟡 H6 — Precedentes limpios para las tres piezas nuevas
No hay que inventar nada:

| Pieza | Precedente | Dónde |
|---|---|---|
| Grid adaptativo | `.cn-dif__cols` — `repeat(auto-fit, minmax(250px, 1fr))` | `colapsable.css:1742` |
| Tabla en un panel de pila | `.cn-dif__tbl` + `.cn-dif__tblscroll` (`overflow-x` solo) | `colapsable.css:1748-1763` |
| Leyenda horizontal al pie | `.gpm__legend` / `.gpm__lg` / `.gpm__chip` | `colapsable.css:1394-1398` |
| Panel de pila con envoltorio propio | `__cnDifPanelHtml` → `.cn-difblk` | `multitab_shell.js:2989` |

### 🔴 H6-BIS — Hay DOS `colapsable.css` y solo se toca uno
| Ruta | Tamaño | Lo sirve |
|---|---|---|
| `frontend\static\css\colapsable.css` | **144 591 B** | `url_for('static', …)` — **ESTE es el que se toca** |
| `frontend\Colapsable\static\css\colapsable.css` | 15 587 B | `url_for('colapsable.static', …)`, blueprint `colapsable`, solo en `/layout/colapsable` |

El nombre idéntico invita al error. El del blueprint **no se toca** y su `?v=20260701` se queda como está: no ve el CSS nuevo y no lo necesita. **Determina la regla 9 de §5 y la validación V12.**

### 🟡 H7 — Regla de oro: un solo scroller
`colapsable.css:1589-1593` y `:2558-2559`: ni `.cn-stack` ni sus hijos pueden llevar `overflow` propio; el único scroller es `.cn-col`. La tabla nueva lleva **`overflow-x: auto` y nada de `overflow-y`**, como `.cn-dif__tblscroll`.

### 🟢 H8 — El namespace `cn-sendap` está libre
`grep -c "cn-sendap"` en `colapsable.css` y en `multitab_shell.js` → **0 y 0**. Tampoco hay ninguna regla de `table` colgando de `.cn-stk` (las únicas son `.rb-cp-vtable` y `.cn-rep__table`, de otros contenedores), así que la tabla nueva no compite con nada.

### 🟢 H12 — Los pipelines de despliegue no se rompen
Verificado uno por uno:

| Pipeline | Veredicto |
|---|---|
| `verificar_deploy.ps1` | **Ni lo mira.** Sus dos chequeos de tamaño son por número de líneas y sobre `login.css`/`login.js`; su regex de estáticos captura solo el interior de `filename='…'`, así que el `?v=` le es invisible. No estorba — pero tampoco protege |
| `migrar_a_azure.ps1` | **Sin límite de tamaño de archivo** y `.css` no está excluido: `static/css/colapsable.css` migra normal, de 144 KB a ~147 KB |
| Build / minificación | **No existe.** Sin `package.json`, webpack, gulp ni postcss en `frontend\`: el CSS se sirve tal cual |
| Caché de estáticos en `app.py` | **Sin configurar** (`SEND_FILE_MAX_AGE_DEFAULT`, `Cache-Control`: cero coincidencias). El `?v=` es el único mecanismo fiable, y sigue siendo necesario |
| Chequeo de trazas | Los 4 archivos de frontend están **limpios hoy** de `claude`/`jaguez40`. El riesgo es solo del texto NUEVO → regla 2 de §5 y validación V11 |

### 🟡 H13 — El origen debe estar commiteado antes de migrar
`migrar_a_azure.ps1:234-239` aborta con `throw` si `git status --porcelain` no está vacío. Los seis archivos van commiteados en GitHub **antes** de invocar el skill.

### 🟡 H15 — Nada de alturas animadas dentro del bloque de la pila
`colapsable.css:1507-1514` documenta que el bloque apilado mide su altura con `ResizeObserver` y espera un margen de calma. Una `transition` o `animation` sobre alturas dentro del panel le rompe la medición. **Determina la regla 10 de §5 y la validación V14.**

### 🟡 H14 — El proyecto documenta cada cambio de CSS en la bitácora
`frontend\BITACORA.md` lleva una tabla `| fecha | descripción | archivos tocados |` y **cada cambio que tocó `colapsable.css` tiene su entrada**. `BITACORA.md` y `data/bitacora` están excluidos de la migración, así que actualizarla es seguro y no viaja a Azure. **Determina §3.G.**

### 🟢 H9 — Constantes reutilizables, ya en el archivo
`__CN_SENDA_COL` (`:6292-6296`, la paleta), `__CN_MES_ABR` (`:6298-6299`) y `__cnKbpe` (`:3788`, formatea con coma decimal). El plan los reusa; no se duplican.

### 🟢 H10 — La paleta pasa los seis chequeos de color
Validado con el script del método: `#00874A`, `#6FBF93`, `#C77F1B` → *ALL CHECKS PASS*. El único aviso (contraste del verde claro de filiales) se releva con etiquetas directas y tabla — ambas presentes. `#1B2A2E` es línea de referencia, no serie categórica.

### 🟡 H11 — El ancho real hay que MEDIRLO, no calcularlo
Los números de H1 salen del CSS fuente, en local, sin navegador. **El plan incluye la medición como primer paso de validación humana (H-0)**, con un comando decisivo. Si el ancho real difiere, lo único que cambia es el `minmax()` de §3.C, no el diseño.

---

## §2. Estado actual

**Backend** (`respuesta_analizar.py:489-511`): calcula `_fut` (meses futuros), arma `_s_chat` con **solo esos meses** y lo manda al panel.

**Frontend** — el panel del chat hoy (`multitab_shell.js:6489-6505`, literal):
```js
  function __cnAnzSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) return "";
    return __cnPanelMesHtml(d, "cn-senda-mes");
  }

  // Pintor diferido del panel de senda en la pila (se llama desde __cnPanelMesPintar, con el
  // bloque ya conectado). Sin el título del tablero: el texto de la respuesta ya lo dice.
  function __cnSendaMesInto(hostEl, d) {
    hostEl.innerHTML = '<div class="cn-p50-senda-plot"></div>';
    __cnSendaPlotInto(hostEl.querySelector(".cn-p50-senda-plot"), d);
  }
```
→ barras apiladas de tres meses, dentro del envoltorio mensual de 375 px.

---

## §3. Especificación

### §3.A — MODIFICAR `respuesta_analizar.py` (archivo A)

**LOCALIZAR** (líneas 495-511, literal):
```python
        _s_chat = dict(_s or {})
        _s_chat["serie"] = _fut
        cuerpo = _plantilla.senda(_s_chat, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        # [2026-09-10 · SENDA-CHAT] El panel viaja con la respuesta del endpoint, igual que
        # `p50_cards` con /analisis/president: el frontend ya sabe pintarla (__cnSendaPlotInto) y
        # no hay que re-fetchear lo que ya está en la mano. Antes devolvía `panel: None` y la
        # senda salía solo como texto — la gráfica existía, pero solo en el tablero.
        # [2026-09-10 · SENDA-SOLO-FUTURO] Al CHAT viaja `_s_chat` (solo meses futuros). El filtro
        # vive aquí y no en el JS a propósito: __cnSendaPlotInto está COMPARTIDA con el tablero,
        # que llega por otro camino (__cnPaintSenda fetchea el endpoint por su cuenta) y debe
        # seguir pintando los 12 meses. Filtrando el dato en origen, el tablero ni se entera y no
        # hace falta meterle una bandera a una función que el propio archivo declara que debe
        # tener "un solo layout, un solo sitio donde arreglar" (multitab_shell.js:6301-6305).
        return {"mensaje": mensaje, "panel": {"tipo": "analiza_senda", "datos": _s_chat}}
```

**SUSTITUIR POR:**
```python
        _s_chat = dict(_s or {})
        _s_chat["serie"] = _fut
        cuerpo = _plantilla.senda(_s_chat, ent_valor)
        intro = _intro(alcance, usuario)
        mensaje = respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el detalle de un mes, o la brecha contra el P50?")
        # [2026-09-10 · SENDA-CHAT] El panel viaja con la respuesta del endpoint, igual que
        # `p50_cards` con /analisis/president: el frontend ya sabe pintarla y no hay que
        # re-fetchear lo que ya está en la mano.
        # [2026-09-10 · SENDA-PANEL] El panel pasó de un gráfico a TRES piezas (año en líneas,
        # zoom de la proyección, tabla), así que necesita la serie COMPLETA — la mitad de
        # contexto dibuja enero a diciembre. Pero el corte NO se duplica en el JS: el backend
        # sigue siendo el único que decide qué es futuro y manda la LISTA ya resuelta en
        # `meses_futuros`. El frontend la obedece, no la recalcula.
        # 🔑 Si el JS reimplantara la regla `mes > ultimo_mes_real + 1`, habría dos versiones de
        #    la misma decisión y bastaría tocar una para que el texto y la gráfica dejaran de
        #    coincidir. Es exactamente el fallo que el plan anterior vino a cerrar.
        # 🔑 El TEXTO se sigue construyendo con `_s_chat` (solo futuros): no cambia ni una coma.
        _s_panel = dict(_s or {})
        _s_panel["meses_futuros"] = [m.get("mes") for m in _fut]
        return {"mensaje": mensaje, "panel": {"tipo": "analiza_senda", "datos": _s_panel}}
```

> `_s_panel` conserva `serie` completa (12 meses), `anio`, `unidad`, `ultimo_mes_real` y `avisos` tal como los devuelve el endpoint, y añade `meses_futuros`.

### §3.B — MODIFICAR `multitab_shell.js` (archivo B)

Un solo reemplazo: se sustituyen las dos funciones actuales por el constructor, los dos pintores de gráfico, la tabla y el orquestador. **`__cnSendaPlotInto`, `__cnSendaHtml` y `__cnPaintSenda` no se tocan.**

**LOCALIZAR** (líneas 6489-6505, literal):
```js
  // [2026-09-10 · SENDA-CHAT] Constructor PURO del panel de senda en la PILA del chat. Reusa el
  // envoltorio mensual (__cnPanelMesHtml): es el que da altura al grid en la pila — MEDIDO el
  // 2026-08-25 (:4694-4697) que sin él Plotly monta un SVG de 10 px sin lanzar error. `producto`
  // no existe en la senda (es corporativa, con gas convertido): __cnProdId(undefined) devuelve
  // null y el envoltorio cae al gris neutro (:3643, :4705). Los `avisos` del endpoint son
  // strings y el envoltorio ya los pinta.
  function __cnAnzSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) return "";
    return __cnPanelMesHtml(d, "cn-senda-mes");
  }

  // Pintor diferido del panel de senda en la pila (se llama desde __cnPanelMesPintar, con el
  // bloque ya conectado). Sin el título del tablero: el texto de la respuesta ya lo dice.
  function __cnSendaMesInto(hostEl, d) {
    hostEl.innerHTML = '<div class="cn-p50-senda-plot"></div>';
    __cnSendaPlotInto(hostEl.querySelector(".cn-p50-senda-plot"), d);
  }
```

**SUSTITUIR POR:**
```js
  // [2026-09-10 · SENDA-PANEL] Panel compuesto de la senda en la PILA del chat: el año en
  // líneas (contexto) + el zoom de la proyección con la brecha sombreada + la tabla de cifras,
  // bajo una leyenda compartida.
  //
  // 🔴 NO reusa __cnPanelMesHtml: ese envoltorio queda capado a 375px de alto
  //    (colapsable.css:2560) y .cn-ins recorta lo que sobre SIN lanzar error (:1231). Este panel
  //    pide ~556px con la fila de abajo en dos columnas, y ~800px cuando cae a una sola. Se
  //    monta envoltorio propio, igual que hace __cnDifPanelHtml (:2989) para las diferidas.
  //    Verificado: .cn-stk no tiene max-height ni overflow, así que el bloque crece libre.
  // 🔴 NO llama a __cnSendaPlotInto: esa función la comparte el TABLERO (vía __cnPaintSenda) y
  //    pinta barras apiladas. Cambiarla movería el tablero, que en este plan no cambia.
  // 🔑 `meses_futuros` lo manda el BACKEND ya resuelto; aquí no se recalcula qué es futuro.
  //    Dos implementaciones de la misma regla es como el texto y la gráfica dejan de coincidir.
  function __cnAnzSendaHtml(d) {
    if (!d || !d.serie || !d.serie.length) return "";
    var avisos = (d.avisos || []).map(function (a) {
      return '<div class="cq-aviso">⚠️ ' + esc(a) + '</div>';
    }).join("");
    return '<div class="cn-sendap">' +
      '<div class="cn-sendap__ctx">' +
        '<div class="cn-sendap__lbl">Contexto <em>· el año completo</em></div>' +
        '<div class="cn-sendap__plot" data-rol="ctx"></div>' +
      '</div>' +
      '<div class="cn-sendap__row">' +
        '<div class="cn-sendap__cell">' +
          '<div class="cn-sendap__lbl">Detalle <em>· la brecha contra el P50</em></div>' +
          '<div class="cn-sendap__plot" data-rol="zoom"></div>' +
        '</div>' +
        '<div class="cn-sendap__cell">' +
          '<div class="cn-sendap__lbl">Cifras <em>· ' + esc(d.unidad || "kboepd") + '</em></div>' +
          // 🔑 __tblHOST, no __tbl: `.cn-sendap__tbl` es la clase del <table> de dentro. Si el
          //    host llevara la misma, la regla del <table> (width/border-collapse) pisaría su
          //    `min-width: 0` y la celda dejaría de poder encogerse -> la fila desborda.
          '<div class="cn-sendap__tblhost" data-rol="tabla"></div>' +
        '</div>' +
      '</div>' +
      '<div class="cn-sendap__leg">' +
        '<span class="cn-sendap__lg"><i class="cn-sendap__chip cn-sendap__chip--real"></i>' +
          'Real (mes cerrado)</span>' +
        '<span class="cn-sendap__lg"><i class="cn-sendap__chip cn-sendap__chip--proy"></i>' +
          'Proyectado</span>' +
        '<span class="cn-sendap__lg"><i class="cn-sendap__chip cn-sendap__chip--p50"></i>' +
          'Meta P50</span>' +
        '<span class="cn-sendap__lg"><i class="cn-sendap__chip cn-sendap__chip--gap"></i>' +
          'Brecha contra el compromiso</span>' +
      '</div>' +
      (avisos ? '<div class="cq-avisos">' + avisos + '</div>' : "") +
      '</div>';
  }

  // Meses que el BACKEND marcó como futuros. Sin la lista no se inventa una regla: se devuelve
  // vacío y el zoom declara que no hay proyección — mejor que adivinar el corte.
  function __cnSendaFuturos(d) {
    var ids = (d && d.meses_futuros) || [];
    if (!ids.length) return [];
    return (d.serie || []).filter(function (m) {
      return ids.indexOf(m.mes) !== -1 && m.total !== null && m.total !== undefined;
    });
  }

  // Layout común de los dos gráficos del panel. Sin leyenda de Plotly: la leyenda es HTML y
  // está compartida al pie (patrón de .gpm__legend, colapsable.css:1394).
  function __cnSendaLayout(rango, unidad) {
    var C = __CN_SENDA_COL;
    return {
      margin: { t: 16, r: 14, b: 26, l: 46 },
      xaxis: { tickfont: { size: 10.5, color: C.tick }, showgrid: false, zeroline: false,
               showline: true, linecolor: C.grid },
      yaxis: { title: { text: String(unidad || "kboepd").toUpperCase(),
                        font: { size: 9, color: C.tick } },
               range: rango, gridcolor: C.grid, griddash: "dot", zeroline: false,
               tickfont: { size: 10, color: C.tick } },
      showlegend: false,
      plot_bgcolor: "rgba(0,0,0,0)", paper_bgcolor: "rgba(0,0,0,0)",
      hovermode: "x unified"
    };
  }

  // Margen del eje: se calcula sobre los valores REALMENTE dibujados, nunca fijo. Con el eje
  // recortado se aprecia una variación del 0,4% que desde cero quedaba plana -- y recortar aquí
  // es legítimo porque NO hay segmentos apilados que distorsionar (el motivo por el que el
  // tablero sí arranca en cero, comentario de :6393).
  function __cnSendaRango(vals, aire) {
    var lo = null, hi = null;
    for (var i = 0; i < vals.length; i++) {
      var v = vals[i];
      if (v === null || v === undefined) { continue; }
      if (lo === null || v < lo) { lo = v; }
      if (hi === null || v > hi) { hi = v; }
    }
    if (lo === null) { return [0, 800]; }
    var m = (hi - lo) * aire;
    if (m < 4) { m = 4; }                 // series casi planas: un margen minimo o no se ve nada
    return [Math.floor((lo - m) / 5) * 5, Math.ceil((hi + m) / 5) * 5];
  }

  // ---- Mitad 1: el año completo. Real solido, proyectado punteado, banda sobre lo proyectado.
  function __cnSendaCtxInto(node, d) {
    if (!node || !window.Plotly || !d || !d.serie || !d.serie.length) { return; }
    try { window.Plotly.purge(node); } catch (e) { /* nodo nuevo */ }
    var C = __CN_SENDA_COL;
    var meses = [], p50 = [], real = [], proy = [], corte = -1, todos = [];
    d.serie.forEach(function (m, i) {
      meses.push(__CN_MES_ABR[m.mes] || m.mes_nombre);
      p50.push(m.p50);
      todos.push(m.total); todos.push(m.p50);
      if (m.es_real) { real.push(m.total); proy.push(null); }
      else {
        real.push(null); proy.push(m.total);
        if (corte === -1) { corte = i; }
      }
    });
    // El tramo proyectado repite el ULTIMO real para que las dos lineas se toquen; sin esto
    // queda un hueco visual entre lo medido y lo proyectado.
    if (corte > 0) { proy[corte - 1] = real[corte - 1]; }

    var shapes = [], anots = [];
    // 🔑 DOS condiciones distintas, no una:
    //    · La BANDA se dibuja siempre que haya algo proyectado (corte >= 0). Si TODO el año lo
    //      es (corte === 0, alcanzable en enero o si la migración del P50 no está aplicada y
    //      ningún mes trae REAL), sombrear el gráfico entero es la verdad, y callarlo dejaría
    //      un gráfico donde no se distingue lo medido de lo proyectado.
    //    · El SEPARADOR y el empalme sí exigen corte > 0: sin meses reales delante no hay nada
    //      que separar, y `corte - 1` sería índice -1.
    if (corte >= 0) {
      // La banda ES la zona proyectada: arranca EXACTAMENTE en el separador. Empezarla mas
      // tarde dejaba la linea punteada suelta a su izquierda, como dos marcas de lo mismo.
      shapes.push({ type: "rect", xref: "x", yref: "paper",
                    x0: corte - 0.5, x1: meses.length - 0.5, y0: 0, y1: 1,
                    fillcolor: "rgba(199,127,27,0.09)", line: { width: 0 }, layer: "below" });
      anots.push({ x: corte - 0.42, y: 1.01, xref: "x", yref: "paper", text: "PROYECTADO",
                   showarrow: false, xanchor: "left", yanchor: "bottom",
                   font: { size: 9, color: C.ecpProy } });
    }
    if (corte > 0) {
      shapes.push({ type: "line", xref: "x", yref: "paper",
                    x0: corte - 0.5, x1: corte - 0.5, y0: 0, y1: 1,
                    line: { color: C.ecpProy, width: 1, dash: "dot" } });
    }

    var lay = __cnSendaLayout(__cnSendaRango(todos, 0.12), d.unidad);
    lay.shapes = shapes;
    lay.annotations = anots;

    window.Plotly.newPlot(node, [
      { x: meses, y: p50, name: "Meta P50", type: "scatter", mode: "lines",
        line: { color: C.p50, width: 2 },
        hovertemplate: "P50 %{y:.1f}<extra></extra>" },
      { x: meses, y: real, name: "Real", type: "scatter", mode: "lines+markers",
        line: { color: C.ecpReal, width: 2.5 }, marker: { size: 6, color: C.ecpReal },
        connectgaps: false, hovertemplate: "Real %{y:.1f}<extra></extra>" },
      { x: meses, y: proy, name: "Proyectado", type: "scatter", mode: "lines+markers",
        line: { color: C.ecpProy, width: 2.5, dash: "dash" },
        marker: { size: 6, color: C.ecpProy },
        connectgaps: false, hovertemplate: "Proyectado %{y:.1f}<extra></extra>" }
    ], lay, { displayModeBar: false, responsive: true });
  }

  // ---- Mitad 2: el zoom de la proyeccion, con el area entre total y P50 = la brecha.
  function __cnSendaZoomInto(node, d, fut) {
    if (!node || !window.Plotly) { return; }
    try { window.Plotly.purge(node); } catch (e) { /* nodo nuevo */ }
    if (!fut.length) {
      node.innerHTML = '<div class="cn-sendap__na">Sin meses proyectados por delante.</div>';
      return;
    }
    var C = __CN_SENDA_COL;
    var meses = [], tot = [], p50 = [], todos = [], anots = [];
    fut.forEach(function (m) {
      meses.push(__CN_MES_ABR[m.mes] || m.mes_nombre);
      tot.push(m.total); p50.push(m.p50);
      todos.push(m.total); todos.push(m.p50);
    });
    // La brecha, en cifra, DENTRO del area: es la magnitud que el texto de la respuesta nombra.
    var hayP50 = fut.every(function (m) { return m.p50 !== null && m.p50 !== undefined; });
    if (hayP50) {
      fut.forEach(function (m, i) {
        var g = m.total - m.p50;
        anots.push({ x: meses[i], y: (m.total + m.p50) / 2, xref: "x", yref: "y",
                     text: (g > 0 ? "+" : "−") + __cnKbpe(Math.abs(g)), showarrow: false,
                     font: { size: 10.5, color: C.ecpProy } });
      });
    }
    var lay = __cnSendaLayout(__cnSendaRango(todos, 0.35), d.unidad);
    lay.annotations = anots;

    var trazas = [
      { x: meses, y: p50, name: "Meta P50", type: "scatter", mode: "lines+markers+text",
        line: { color: C.p50, width: 2 },
        marker: { size: 7, color: "#FFFFFF", line: { color: C.p50, width: 2 } },
        text: p50.map(function (v) { return v === null ? "" : __cnKbpe(v); }),
        textposition: "top center", textfont: { size: 10, color: C.tick },
        hovertemplate: "P50 %{y:.1f}<extra></extra>" },
      { x: meses, y: tot, name: "Proyectado", type: "scatter", mode: "lines+markers+text",
        line: { color: C.ecpProy, width: 2.5, dash: "dash" },
        marker: { size: 8, color: C.ecpProy },
        text: tot.map(function (v) { return v === null ? "" : __cnKbpe(v); }),
        textposition: "bottom center", textfont: { size: 10, color: C.ecpProy },
        hovertemplate: "Proyectado %{y:.1f}<extra></extra>" }
    ];
    // El relleno cuelga de la traza ANTERIOR (tonexty), asi que el P50 tiene que ir primero.
    if (hayP50) { trazas[1].fill = "tonexty"; trazas[1].fillcolor = "rgba(199,127,27,0.14)"; }

    window.Plotly.newPlot(node, trazas, lay, { displayModeBar: false, responsive: true });
  }

  // ---- Mitad 3: la tabla. Devuelve el desglose Ecopetrol/filiales, que es lo UNICO que se
  // perdio al dejar las barras apiladas. No repite el grafico: añade lo que el grafico no pinta.
  // 🔑 Ecopetrol y filiales van SIN color y con sangria: no estan dibujados, y un cuadrito de
  //    color significaria "buscalo en el grafico". La sangria dice lo que si es verdad -- son
  //    los componentes que suman al total.
  function __cnSendaTablaHtml(fut) {
    if (!fut.length) { return '<div class="cn-sendap__na">Sin cifras proyectadas.</div>'; }
    var cab = "", fEcp = "", fFil = "", fTot = "", fP50 = "", fGap = "";
    fut.forEach(function (m) {
      var g = (m.p50 === null || m.p50 === undefined) ? null : m.total - m.p50;
      // 🔑 MISMA fuente de etiqueta que los ejes de los dos gráficos (__CN_MES_ABR), no
      //    `mes_nombre.slice(0,3)`: si el backend cambiara la capitalización, las cabeceras de
      //    la tabla dejarían de coincidir con el eje X del panel de al lado.
      cab  += "<th>" + esc(__CN_MES_ABR[m.mes] || m.mes_nombre || "") + "</th>";
      fEcp += "<td>" + (m.ecopetrol == null ? "—" : __cnKbpe(m.ecopetrol)) + "</td>";
      fFil += "<td>" + (m.filiales == null ? "—" : __cnKbpe(m.filiales)) + "</td>";
      fTot += "<td>" + (m.total == null ? "—" : __cnKbpe(m.total)) + "</td>";
      fP50 += "<td>" + (m.p50 == null ? "—" : __cnKbpe(m.p50)) + "</td>";
      fGap += "<td>" + (g === null ? "—" : (g > 0 ? "+" : "−") + __cnKbpe(Math.abs(g))) + "</td>";
    });
    return '<div class="cn-sendap__tblscroll"><table class="cn-sendap__tbl">' +
      "<thead><tr><th>Serie</th>" + cab + "</tr></thead><tbody>" +
      '<tr class="comp"><td>Ecopetrol</td>' + fEcp + "</tr>" +
      '<tr class="comp"><td>Filiales</td>' + fFil + "</tr>" +
      '<tr class="suma"><td><i class="cn-sendap__sw cn-sendap__sw--proy"></i>Total</td>' +
        fTot + "</tr>" +
      '<tr><td><i class="cn-sendap__sw cn-sendap__sw--p50"></i>Meta P50</td>' + fP50 + "</tr>" +
      '<tr class="gap"><td>Brecha</td>' + fGap + "</tr>" +
      "</tbody></table></div>";
  }

  // Pintor diferido del panel (lo llama __cnPanelMesPintar con el bloque ya conectado: Plotly
  // necesita un contenedor con ancho real).
  function __cnSendaMesInto(hostEl, d) {
    if (!hostEl || !d) { return; }
    if (!window.Plotly) {
      hostEl.innerHTML = '<div class="cn-sendap__na">No se pudo cargar Plotly.</div>';
      return;
    }
    var fut = __cnSendaFuturos(d);
    __cnSendaCtxInto(hostEl.querySelector('[data-rol="ctx"]'), d);
    __cnSendaZoomInto(hostEl.querySelector('[data-rol="zoom"]'), d, fut);
    var t = hostEl.querySelector('[data-rol="tabla"]');
    if (t) { t.innerHTML = __cnSendaTablaHtml(fut); }
  }
```

#### B.2 — El pintor recibe el bloque, no el host interno

`__cnPanelMesPintar` busca hoy `.cn-senda-mes`, clase que el constructor nuevo ya no emite.

**LOCALIZAR** (líneas 5048-5052, literal):
```js
    } else if (tipo === "analiza_senda") {
      var hsd = blk.querySelector(".cn-senda-mes");
      if (hsd) __cnSendaMesInto(hsd, d);
    }
  }
```

**SUSTITUIR POR:**
```js
    } else if (tipo === "analiza_senda") {
      // [2026-09-10 · SENDA-PANEL] El host es el panel entero (.cn-sendap), no un div de plot:
      // dentro hay DOS gráficos y una tabla, y cada pintor busca el suyo por [data-rol].
      var hsd = blk.querySelector(".cn-sendap");
      if (hsd) __cnSendaMesInto(hsd, d);
    }
  }
```

#### B.3 — Actualizar el comentario del ternario (el tipo no cambia)

**LOCALIZAR** (líneas 4605-4610, literal):
```js
             // [2026-09-10 · SENDA-CHAT] "analiza_senda" (Analizar/senda): barra apilada ECP+Filiales
             // real+proyectado con línea P50, la misma del tablero. Constructor PURO; los datos
             // (respuesta cruda de /analisis/president/senda) ya viajan en panel.datos. Registrado
             // ANTES del fallback por la razón de siempre: __cnCuantCardHtml NO valida el tipo y
             // pintaría una tarjeta KPI leyendo campos que este contrato no tiene.
             : (panel.tipo === "analiza_senda")    ? __cnAnzSendaHtml(d)
```

**SUSTITUIR POR:**
```js
             // [2026-09-10 · SENDA-PANEL] "analiza_senda" (Analizar/senda): panel compuesto —
             // el año en líneas, el zoom de la proyección con la brecha, y la tabla de cifras.
             // Constructor PURO; los datos (serie de 12 meses + `meses_futuros`) ya viajan en
             // panel.datos. Registrado ANTES del fallback por la razón de siempre:
             // __cnCuantCardHtml NO valida el tipo y pintaría una tarjeta KPI con campos ajenos.
             : (panel.tipo === "analiza_senda")    ? __cnAnzSendaHtml(d)
```

### §3.C — AÑADIR CSS al final de `colapsable.css` (archivo C)

**LOCALIZAR** (las últimas 4 líneas del archivo, literal — hoy termina en la línea 2589):
```css
@media (max-width: 1024px) {
  .cn-compprod__grid { grid-template-columns: 1fr; }
  .cn-compprod__grid > * { height: auto; }
}
```

**SUSTITUIR POR** (se conserva el bloque y se añade todo lo nuevo debajo):
```css
@media (max-width: 1024px) {
  .cn-compprod__grid { grid-template-columns: 1fr; }
  .cn-compprod__grid > * { height: auto; }
}

/* ============================================================================
   [2026-09-10 · SENDA-PANEL] Panel compuesto de la senda en la pila del chat.
   Tres piezas: el año en líneas (contexto), el zoom de la proyección con la
   brecha sombreada, y la tabla de cifras. Leyenda compartida al pie.

   🔑 ENVOLTORIO PROPIO, no .cn-compprod__grid: aquel está capado a 375px
      (:2560) y .cn-ins recorta lo que sobre SIN error (:1231). Este panel pide
      ~520px. Mismo camino que .cn-difblk, que también monta el suyo.
   🔑 EL AÑO VA A ANCHO COMPLETO y el zoom+tabla debajo, no tres columnas: la
      pila del chat da ~915px en /mainchat y ~813px en la vista clásica a
      1920px (y ~259px a 1366px — ver el comentario medido de :2266). Tres
      columnas iguales pedirían 1224px. El año es quien necesita el ancho:
      doce meses; el zoom son tres y la tabla cuatro columnas.
   🔑 auto-fit + minmax como .cn-dif__cols (:1742): a un ancho corto la fila de
      abajo cae sola a una columna, sin media query que mantener.
   🔑 REGLA DE ORO (:1589): ningún scroller propio dentro de .cn-col. La tabla
      lleva overflow-x y NADA de overflow-y.
   ========================================================================= */
.cn-sendap { display: flex; flex-direction: column; gap: 10px; padding: 2px 2px 0; }
.cn-sendap__ctx, .cn-sendap__cell { min-width: 0; display: flex; flex-direction: column; }
.cn-sendap__row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px; align-items: stretch; }
.cn-sendap__lbl {
  font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
  color: #8b948e; font-weight: 700; padding: 0 2px 4px; }
.cn-sendap__lbl em {
  font-style: normal; font-weight: 400; text-transform: none; letter-spacing: 0;
  font-size: 11px; color: #9aa39d; }
/* Alturas fijas: Plotly necesita un contenedor con alto real, y el bloque de la
   pila no lo hereda de ningún sitio. Suma: 2 padding + 18 rótulo + 236 plot + 10
   gap + 18 rótulo + 236 plot + 10 gap + 26 leyenda ≈ 556px con la fila de abajo
   en DOS columnas. Cuando cae a una (panel < 500px), la tabla se apila bajo el
   zoom y el panel llega a ~800px — sigue sin recortarse porque .cn-stk crece
   libre (verificado: sin max-height ni overflow).
   ⚠️ NADA de transition ni animation sobre alturas aquí dentro: el bloque de la
      pila mide con ResizeObserver y una altura animada le rompe la medición
      (documentado en :1507-1514). */
.cn-sendap__plot { width: 100%; height: 236px; min-width: 0; }
.cn-sendap__tblhost { min-width: 0; }
.cn-sendap__na { padding: 16px 8px; font-size: 12px; color: #8b948e; }

/* tabla — clonada de .cn-dif__tbl (:1748), que ya resolvió este mismo problema */
.cn-sendap__tblscroll { overflow-x: auto; }
.cn-sendap__tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.cn-sendap__tbl thead th {
  text-align: right; font-size: 9.5px; letter-spacing: .04em; text-transform: uppercase;
  color: #8b948e; font-weight: 700; padding: 0 6px 7px; border-bottom: 1px solid #e4e6df; }
.cn-sendap__tbl thead th:first-child { text-align: left; }
.cn-sendap__tbl tbody td {
  padding: 6px; border-bottom: 1px solid #eef0ea; text-align: right;
  font-variant-numeric: tabular-nums; color: #1c231f; }
.cn-sendap__tbl tbody td:first-child { text-align: left; white-space: nowrap; }
.cn-sendap__tbl tbody tr:last-child td { border-bottom: none; }
/* componentes: sangrados y en gris — NO se dibujan en el panel, así que no llevan
   muestra de color. La sangría dice lo que sí es cierto: suman al total. */
.cn-sendap__tbl tbody tr.comp td { color: #8b948e; }
.cn-sendap__tbl tbody tr.comp td:first-child { padding-left: 18px; }
.cn-sendap__tbl tbody tr.suma td { border-top: 1px solid #c9d2cd; font-weight: 700; }
.cn-sendap__tbl tbody tr.gap td { color: #C77F1B; }
.cn-sendap__tbl tbody tr.gap td:first-child { color: #566; font-weight: 400; }
.cn-sendap__sw {
  display: inline-block; width: 8px; height: 8px; border-radius: 2px;
  margin-right: 6px; flex: 0 0 auto; }
.cn-sendap__sw--proy { background: #C77F1B; }
.cn-sendap__sw--p50 { background: #fff; border: 2px solid #1B2A2E; width: 6px; height: 6px; }

/* leyenda compartida — clonada de .gpm__legend (:1394). Es lo que hace que las
   tres piezas se lean como UN panel y no como tres gráficos apilados. */
.cn-sendap__leg {
  display: flex; flex-wrap: wrap; gap: 6px 16px;
  padding-top: 9px; border-top: 1px solid #EEF2EF; }
.cn-sendap__lg { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #6E7C75; }
.cn-sendap__chip { width: 16px; height: 3px; border-radius: 2px; display: inline-block;
  flex: 0 0 auto; }
.cn-sendap__chip--real { background: #00874A; }
.cn-sendap__chip--proy {
  background: repeating-linear-gradient(90deg, #C77F1B 0 5px, transparent 5px 8px); }
.cn-sendap__chip--p50 { background: #1B2A2E; }
.cn-sendap__chip--gap {
  height: 10px; background: rgba(199,127,27,0.16); border: 1px solid #C77F1B; }

/* Muy estrecho (pila clásica a 1366px ≈ 259px útiles): los gráficos se achatan
   antes que desaparecer, y la tabla es lo último que se sacrifica porque las
   cifras siguen siendo legibles donde una curva de 12 puntos ya no lo es. */
@media (max-width: 1440px) {
  .cn-sendap__plot { height: 210px; }
}
```

### §3.D — MODIFICAR `mainchat_layout.html` (archivo D) 🔴 EL CRÍTICO

**D.1 — CSS. LOCALIZAR** (línea 13, literal):
```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260907b">
```
**SUSTITUIR POR:**
```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260910c">
```

**D.2 — JS. LOCALIZAR** (línea 323, literal):
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b"></script>
```
**SUSTITUIR POR:**
```html
<script defer src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910c"></script>
```

### §3.E — MODIFICAR `main.html` (archivo E)

**E.1 — CSS. LOCALIZAR** (línea 5, literal):
```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260908b">
```
**SUSTITUIR POR:**
```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260910c">
```

**E.2 — JS. LOCALIZAR** (línea 88, literal):
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b"></script>
```
**SUSTITUIR POR:**
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910c"></script>
```

### §3.F — MODIFICAR `login.html` (archivo F)

**F.1 — CSS. LOCALIZAR** (línea 39, literal):
```html
    <link rel="prefetch" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260831a">
```
**SUSTITUIR POR:**
```html
    <link rel="prefetch" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260910c">
```

**F.2 — JS. LOCALIZAR** (línea 43, literal):
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910b">
```
**SUSTITUIR POR:**
```html
    <link rel="prefetch" href="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260910c">
```

### §3.G — AÑADIR entrada en `frontend\BITACORA.md` (archivo G)

Convención del proyecto: todo cambio que toca `colapsable.css` deja fila en la tabla «Cambios de la sesión». El archivo está **excluido de la migración a Azure**, así que es seguro.

**LOCALIZAR** (línea 544, literal — la última fila de la tabla de la sesión del 30-ago):
```
| 30-ago | Publicado a Azure DevOps `dev` desde el servidor de pruebas: 251 archivos verificados hash por hash, sin trazas del repositorio de trabajo | commit Azure `244ea27` |
```

**SUSTITUIR POR** (se conserva la fila y se añade la nueva debajo):
```
| 30-ago | Publicado a Azure DevOps `dev` desde el servidor de pruebas: 251 archivos verificados hash por hash, sin trazas del repositorio de trabajo | commit Azure `244ea27` |
| 10-sep | Panel de senda del chat: de barras apiladas a panel compuesto — el año en líneas (contexto, con la banda de proyección arrancando en el separador), el zoom de la proyección con la brecha sombreada, y la tabla que devuelve el desglose Ecopetrol/filiales que las líneas no dibujan. Envoltorio propio porque el mensual está capado a 375 px y recorta sin avisar. El tablero de Analizar NO cambia: `__cnSendaPlotInto` es compartida y no se toca. Los tres `?v=` de `colapsable.css` estaban desalineados pese al contrato de `login.html:31` — se unifican | `static/js/multitab_shell.js`, `static/css/colapsable.css`, `MainChat/templates/mainchat_layout.html`, `templates/main.html`, `templates/login.html`, y en el repo backend `app/features/consulta_v2/respuesta_analizar.py` |
```

---

## §4. Orden de ejecución

| Paso | Archivo | Acción | Verificación |
|---|---|---|---|
| 1 | A `respuesta_analizar.py` | §3.A | V1, V2 |
| 2 | B `multitab_shell.js` | §3.B (B.1 → B.2 → B.3) | V4, V5, V6, V7 |
| 3 | C `colapsable.css` | §3.C | V8, V9, V12 |
| 4 | D `mainchat_layout.html` | D.1 y D.2 | V10 |
| 5 | E `main.html` | E.1 y E.2 | V10 |
| 6 | F `login.html` | F.1 y F.2 | V10 |
| 7 | G `BITACORA.md` | §3.G | V13 |
| 8 | — | §6.1 completa | todo verde |

Paso 1 en el repo `backend\`; 2-7 en `frontend\`. **Dos commits**, uno por repo.

---

## §5. Reglas no negociables

1. **CERO cambios fuera de §3.** En particular NO tocar `__cnSendaPlotInto`, `__cnSendaHtml`, `__cnPaintSenda`, `__cnPanelMesHtml`, `analisis/api.py` ni `plantilla.py`.
2. 🔴 **PROHIBIDO escribir la cadena `CLAUDE.md` en comentarios de código** (aborta la migración a Azure). Escribir «la guía del proyecto §N».
3. **JS ES5 clásico**: `var` + `function`. Sin `const`/`let`/arrow/template literals. Ternario sí.
4. **Los SEIS cache-busters al mismo valor** `20260910c` (3 de CSS + 3 de JS).
5. **Nada de `overflow-y`** en el CSS nuevo: solo `overflow-x` en el scroll de la tabla (regla de oro de `colapsable.css:1589`).
6. **Anclas literales.** Si un «LOCALIZAR» no aparece exacto, DETENERSE y reportar.
7. **El texto de la respuesta no cambia.** Si alguna validación muestra un texto distinto al de hoy, es una regresión.
8. Comentarios nuevos **en español** con prefijo `[2026-09-10 · SENDA-PANEL]`.
9. **El CSS va en `frontend\static\css\colapsable.css` (144 KB).** Existe un segundo archivo con el MISMO nombre en `frontend\Colapsable\static\css\colapsable.css` (15 KB, del blueprint): **no se toca** (H6-BIS, validación V12).
10. **Ni `transition` ni `animation` sobre alturas** dentro del bloque nuevo: la pila mide con `ResizeObserver` y una altura animada le rompe la medición (`colapsable.css:1507-1514`).

---

## §6. Validación

### §6.1 Estática (executor, en local, sin BD)

Carpeta `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\`:

**V1 — el panel recibe los 12 meses y la lista de futuros; el texto NO cambia**
```powershell
uv run python -c "from app.features.consulta_v2 import respuesta_analizar as ra; S=[{'mes':m,'mes_nombre':n,'ecopetrol':e,'filiales':f,'total':t,'p50':q,'es_real':r} for m,n,e,f,t,q,r in [(7,'Julio',590.4,117.8,708.2,747.0,True),(8,'Agosto',593.1,121.4,714.5,740.4,True),(9,'Septiembre',604.3,122.1,726.4,735.0,False),(10,'Octubre',606.8,126.8,733.6,741.8,False),(11,'Noviembre',606.5,125.3,731.8,738.3,False),(12,'Diciembre',604.3,125.6,729.9,733.3,False)]]; F={'anio':2026,'unidad':'kboepd','serie':S,'ultimo_mes_real':8,'avisos':[],'fuentes':{}}; r=ra.responder_con_panel('cuanto vamos a producir en los proximos meses hasta diciembre?', _senda_fn=lambda anio=2026: F); dd=r['panel']['datos']; print('meses_serie =', len(dd['serie'])); print('meses_futuros =', dd['meses_futuros']); print('tipo =', r['panel']['tipo']); print('TEXTO_OK' if ('octubre' in r['mensaje'] and 'septiembre' not in r['mensaje']) else 'TEXTO_MAL')"
```
Esperado: `meses_serie = 6` (los que trae el fake), `meses_futuros = [10, 11, 12]`, `tipo = analiza_senda`, `TEXTO_OK`.

**V2 — sin meses futuros sigue declinando, sin panel**
```powershell
uv run python -c "from app.features.consulta_v2 import respuesta_analizar as ra; F={'anio':2026,'unidad':'kboepd','ultimo_mes_real':11,'serie':[{'mes':12,'mes_nombre':'Diciembre','ecopetrol':604.3,'filiales':125.6,'total':729.9,'p50':733.3,'es_real':False}],'avisos':[],'fuentes':{}}; r=ra.responder_con_panel('como se ve el cierre de año?', _senda_fn=lambda anio=2026: F); print(r['panel']); print('OK' if r['panel'] is None and 'No tengo la senda' in r['mensaje'] else 'MAL')"
```
Esperado: `None` y `OK`.

**V3 — suite y goldens sin regresión**
```powershell
uv run pytest tests/test_analizar.py tests/test_analizar_tendencia.py tests/test_consulta_v2_clasificador.py -q
```
```powershell
$env:PYTHONPATH='.'; uv run python app/features/consulta_v2/golden/run_golden.py
```
Esperado: **los 2 fallos preexistentes de siempre** y `93/100 = 93%`. Cualquier fallo distinto → DETENERSE.

Carpeta `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\`:

| # | Comando | Esperado |
|---|---|---|
| V4 | `node -e "new Function(require('fs').readFileSync('static/js/multitab_shell.js','utf8'));console.log('JS OK')"` | `JS OK` |
| V5 | `(Select-String -Path static\js\multitab_shell.js -Pattern '__cnSendaPlotInto').Count` | **3** — definición + los 2 usos del TABLERO. Hoy son **4** (el cuarto es el del chat, que este plan retira). Si sigue en 4+, el panel nuevo la está llamando y arrastraría el tablero → DETENERSE |
| V6 | `(Select-String -Path static\js\multitab_shell.js -Pattern 'cn-senda-mes').Count` | **0** (la clase vieja desapareció) |
| V7 | `(Select-String -Path static\js\multitab_shell.js -Pattern 'cn-sendap').Count` | **≥ 12** |
| V8 | `(Select-String -Path static\css\colapsable.css -Pattern 'cn-sendap').Count` | **≥ 25** |
| V9 | `(Select-String -Path static\css\colapsable.css -Pattern 'overflow-y').Count` | **7** — los mismos preexistentes, medidos antes de tocar nada. El CSS nuevo no añade ninguno (regla 5 de §5) |
| V10 | `(Select-String -Path templates\main.html,templates\login.html,MainChat\templates\mainchat_layout.html -Pattern '20260910c').Count` | **6** |
| V11 | `(Select-String -Path static\js\multitab_shell.js,static\css\colapsable.css,templates\main.html,templates\login.html,MainChat\templates\mainchat_layout.html -Pattern 'claude\|jaguez40' -CaseSensitive:$false).Count` | **1** — solo el preexistente de `multitab_shell.js:2208`. Si sale 2+, el texto nuevo introdujo un término prohibido y **aborta la migración entera** → DETENERSE |
| V12 | `(Select-String -Path Colapsable\static\css\colapsable.css -Pattern 'cn-sendap').Count` | **0** — el CSS va en `static\css\colapsable.css` (144 KB), NO en el del blueprint (15 KB). Si sale >0, se editó el archivo equivocado → DETENERSE |
| V13 | `(Select-String -Path BITACORA.md -Pattern '10-sep').Count` | **≥ 1** |
| V14 | `(Select-String -Path static\css\colapsable.css -Pattern 'transition\|animation' -Context 0,0 \| Select-String 'cn-sendap').Count` | **0** — nada de altura animada dentro del bloque nuevo (H15: el `ResizeObserver` de la pila mide mal si la altura anima) |

### §6.2 Humana (el usuario, en el **servidor de pruebas**)

Tras `git pull` en ambos repos y **reiniciar los dos backends**.

**H-0 · LA MEDICIÓN, ANTES QUE NADA.** Los anchos de H1 salen del CSS, no del navegador. Con una respuesta de senda ya en la pila, F12 → Console, **una línea**, en `/mainchat` y en `/`:
```js
(()=>{const s=document.getElementById('cn-stack'),p=document.querySelector('.cn-sendap'),g=document.querySelector('.cn-sendap__plot');return{viewport:innerWidth,stack:s&&s.clientWidth,panel:p&&p.clientWidth,plot:g&&[g.clientWidth,g.clientHeight]}})()
```
Si `panel` < 500 px, la fila de abajo caerá a una sola columna: es el comportamiento previsto, no un fallo. Pegar las dos salidas.

| # | Acción | Esperado |
|---|---|---|
| H-1 | `Cuánto vamos a producir en los próximos meses hasta diciembre?` | **Arriba**: el año ene-dic, verde sólido hasta agosto, ámbar punteado desde septiembre, banda sombreada **empezando en la línea punteada**. **Abajo izquierda**: oct-nov-dic con el área de la brecha y las cifras −8,2 / −6,5 / −3,4 dentro. **Abajo derecha**: la tabla con Ecopetrol y filiales sangrados y sin color. **Al pie**: la leyenda de 4 entradas. Console: 0 errores |
| H-2 | Leer el texto de la respuesta | **Idéntico al de hoy**: octubre, noviembre y diciembre. Sin septiembre |
| H-3 | **Tablero de Analizar** (Insights, vista global) | 🔴 **SIN CAMBIOS**: barras apiladas verde/ámbar de los 12 meses, leyenda «Real Ecopetrol» / «Real filiales» |
| H-4 | `¿Cómo se ve el cierre de año?` | El mismo panel |
| H-5 | Preguntar H-1 dos veces | Dos paneles, los dos pintados completos |
| H-6 | Cambiar de pestaña y volver | El panel sigue pintado |
| H-7 | Estrechar el navegador a media pantalla | Zoom y tabla se apilan; nada se recorta ni desborda |
| H-8 | F12 → Network | `colapsable.css?v=20260910c` y `multitab_shell.js?v=20260910c` |

⚠️ **H-3 es el control crítico**: si el tablero cambió, se tocó `__cnSendaPlotInto` y hay que revertir.
⚠️ **H-8 valida H5**: con un token viejo, todo lo demás que se vea es un falso negativo.

**Estado al terminar el executor: «implementado, PENDIENTE de validación humana».** Solo el usuario marca ✅.

---

## §7. Fuera de alcance

- **El tablero de Analizar**: conserva sus barras apiladas. Unificarlo con el panel del chat es otro plan, y obligaría a revalidar el tablero entero.
- **El texto de la respuesta**: no se toca ni una coma.
- **El endpoint `president_senda`**: sigue devolviendo los 12 meses tal cual.
- **Los 6 comentarios con `CLAUDE.md` que bloquean `migrar-a-azure`** (`multitab_shell.js:2208`, `subrouter.py:52`, `respuesta_cuantificar.py:35,146,292,487`): siguen pendientes de decisión del usuario. Este plan solo se compromete a **no añadir ninguno más** (V11).
- **Prefetch desfasado de otros estáticos en `login.html`** (`mainchat.css`, `acordeon.css`, `historial.css`): mismo problema de H5 en otros archivos, ajeno a esta tarea.
- **Tests automáticos del panel**: no existen para ningún panel de la pila; este plan no inaugura la práctica.
