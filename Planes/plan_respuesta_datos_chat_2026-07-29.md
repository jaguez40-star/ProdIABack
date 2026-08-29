# Plan ejecutable v2 (auditado) — Respuesta de datos del chat «Titular + métricas»

> Traduce `resp.md` (spec React 19 + TS + Sass) al stack real: **vanilla JS en
> `static/js/multitab_shell.js` + CSS plano en `static/css/colapsable.css`**.
> Precedente idéntico: `plan_chat_asimetrico_esencial_2026-07-09.md` (mismo chat, misma traducción).
> **Alcance:** SOLO la burbuja del bot que responde una consulta de producción con cifras
> (`__cnRespuestaHtml`, `static/js/multitab_shell.js:3197`). No toca desambiguación, «Entidad
> identificada», zoom D-D5, huella ni el panel derecho.
>
> **Cobertura: campos de entrada 15 → renderizados 15.** Ninguno se descarta en silencio
> (ver §0.1 A2/A3: `encabezado`, `pie` y `avisos` sobrevivían solo en el plan v1 de palabra).
>
> **v2 = v1 + auditoría contra el código.** El v1 asumía un vocabulario de estados y una forma de
> `lineas` que **no son los reales**. Los seis hallazgos están en §0.1 con archivo:línea.

---

## §0 · Decisiones (CERRADAS tras la auditoría)

El spec se dibujó sobre **CASTILLA**, que tiene **un solo producto con meta**. Verificado contra la BD,
ese supuesto no se sostiene:

| Entidad | Productos con meta | Situación |
|---|---:|---|
| CASTILLA · RUBIALES | 1 | El diseño funciona tal cual |
| **CUPIAGUA** | **3** | Crudo 94,6% · Gas 79,0% · Blancos 152,1% — **tres estados distintos** |
| **CUSIANA** | **0** | Produce los 3, ninguno tiene PPTO |

**D1 · Multi-producto → «titular + filas compactas».** El producto TITULAR conserva el bloque grande
(cifra 27 px + grilla de métricas). Los demás bajan a **una línea** (`GAS · 9,87 MSCF/mes · 79,0% · Foco`).
Se descartaron «una tarjeta por producto» (CUPIAGUA daría 3 bloques apilados) y «solo el dominante»
(un gas al 79 % desaparecería — deshonesto).

**🔴 D1.1 · Elección del titular — CORREGIDA en v2.** El v1 elegía *«el de mayor `real`»*. Eso compara
**unidades distintas**: el gas crudo de la BD (9.868.310) es numéricamente mayor que el crudo en barriles
(6.860.389) **siempre**, así que el gas se habría quedado de titular en casi toda entidad con meta de gas.
Regla nueva, **libre de unidades y determinista**: *el **primer** producto **con meta y con dato** en el
orden de negocio que ya emite el backend (`CRUDO → GAS → BLANCOS`,
`analisis/api.py:560`); si ninguno tiene meta, el primero con dato.* Si el usuario pidió un producto
concreto, `lineas` ya viene filtrada a uno → el titular es ese, sin lógica extra.

**🔴 D2 · Narración LLM → se RETIRA de esta burbuja + apagar el flag en 139.** Es coherente con lo que
pide `resp.md` §7 (no repetir en prosa lo que ya está en las métricas) y con el objetivo del rediseño
(la prosa era justo donde proyección y presupuesto se confundían).
⚠️ **Corrección del v1:** el v1 afirmaba que «`narracion.py` sigue sirviendo a otros mensajes» y que
retirarla «deja de pagar la latencia de Ollama». **Ambas cosas son falsas**, verificado:
`narrar()` se invoca en **un solo lugar** (`consulta/maquina.py:240`) y se llama **siempre**, antes de
que el frontend decida qué pintar. Con el flag encendido, retirar la prosa haría que 139 **pague el LLM
y tire el resultado** — estrictamente peor que hoy.
→ **Acción de ops obligatoria, no opcional:** poner `CONSULTA_NARRA_LLM=false` en el `.env` de 139
(`config.py:21`, default ya es `false`). Cero código.
→ **Consecuencia declarada (no enterrada):** con eso `narracion.py` queda **inactivo**. NO se borra —
es reversible con una línea del `.env` y su salvaguarda D-N5 sigue documentada. Si se prefiere conservar
la voz personalizada («Javier, en RUBIALES…»), esto es lo que hay que revertir.

**🔴 D3 · Unidad del GAS → convención del panel.** Hoy el chat imprime el gas **crudo y sin unidad**
(`ejecucion._fmt`, miles con punto); el panel usa **MSCF = valor ÷ 1e6** desde el 21-jul
(`multitab_shell.js:2102`). Al poner la etiqueta de unidad que pide el spec, `9.868.310 MSCF` sería falso.
→ Se adopta `esGas ? __cnGasM : __cnMilesEC` + `MSCF/mes` vs `bbl/mes`, igual que el panel.
🔑 **D3 solo es seguro porque D2 retira la prosa:** con la narración encendida, la burbuja diría
`9,87 MSCF` en la tarjeta y `9.868.310` en el párrafo — **contradicción dentro del mismo mensaje**.
Las dos decisiones van juntas o no van.

**🔴 D4 · La rama B (filial) NO se rediseña — conserva su render de lista.** El v1 la mandaba al caso
«sin meta», lo que **borraba todo su contenido**: una filial no tiene presupuesto, tiene *proyección de
cierre vs su promedio 2026*, y la variación (`+5,2 %`) **solo existe dentro de `l.texto`** — el backend
no la expone como campo (`ejecucion.py:68-81`). Reescribirla como tarjeta dejaría «12.345 bbl» a secas.
→ `if (resp.nivel === "filial" || resp.modo === "tendencia_filial")` sale por el render actual.
*(Opción futura, fuera de este plan: exponer `variacion_pct`/`referencia` en `_linea_filial` — 2 líneas
de backend — y darle su propia tarjeta.)*

**D5 · Un solo umbral para el juicio.** La frase de cierre se deriva del **mismo `estado`** que pinta el
chip, nunca de un `>= 100` propio. Es exactamente el defecto que ya se reportó en las tarjetas P50
(«no cumplen y sin embargo están en verde»): dos umbrales independientes para el mismo juicio terminan
contradiciéndose en pantalla.

---

## §0.1 · Auditoría v2 — hallazgos con evidencia

| # | Hallazgo | Evidencia | Efecto si no se corrige |
|---|---|---|---|
| **A1** 🔴 | **El vocabulario de estados del v1 no existe.** El backend emite `"Alineado" / "Rezagado" / "Foco" / "sin meta"`; el v1 mapeaba `alineado/ajustado/actuar/por debajo`. | `ejecucion.py:15` (`_ESTADO_LABEL`), umbrales en `analisis/api.py:635` (`ok≥90`, `warn≥75`, `alert<75`) | **Rezagado y Foco quedan SIN chip** — justo los dos casos que importan. Silencioso. |
| **A2** 🔴 | El v1 **descartaba `resp.pie`**, que es el descargo de proyección («la cifra es del mes completo y el reporte lleva 17 de 31 días»). | `ejecucion.py:198-205, 223-227` | Regresión sobre una decisión de honestidad **explícita** del 16-jul: leer una proyección como acumulado ya fue un error real. |
| **A3** 🟠 | Rama B **no trae `mes`** ni `cumplimiento`, y su comparación vive en `l.texto`. | `ejecucion.py:117-130` | Ver D4 — la burbuja de filial quedaba vacía de contenido. |
| **A4** 🟠 | `__daNum(null)` devolvía `null` y se concatenaba: la burbuja imprimía la palabra **`null`**. | v1 §2 PASO 2.0 | Texto roto en cualquier campo nulo. → devuelve `—`. |
| **A5** 🟠 | El filtro «vivos» del v1 (`real > 0`) **excluía a los productos con meta y real = 0**. | ARAUCA/gas y PAUTO SUR/blancos, verificados el 25-jul como **paros reales** | Desaparecería de la respuesta el peor caso posible (0 % de la meta). → el filtro admite `ppto > 0`. |
| **A6** 🟠 | Con `mtd = null` (todo lo que no sea CRUDO: `ejecucion.py:33-51`), el v1 pintaba **el mismo número dos veces** (titular + primera celda) y rotulaba una proyección como «Cierre». | — | Duplicación y etiqueta falsa. → la grilla es de 1/2/3 celdas según lo que exista. |
| **A7** ✅ | `esc`, `__cnMilesEC`, `__cnGasM`, `__cnNivelLabel` están en el **mismo IIFE** que `__cnRespuestaHtml` → visibles sin cambios de scope. | `multitab_shell.js:26, 1522, 2102, 858` | — |
| **A8** ✅ | El prefijo `.da__` **no colisiona** (verificado sobre los 5 CSS del proyecto; `.date-cell`/`.database-source` son selectores exactos distintos). | `grep` sobre `static/css/*.css` | — |
| **A9** ✅ | El texto a reemplazar del PASO 2.1 coincide **literal** con el archivo. `node --check` verde en el estado actual. | `multitab_shell.js:3210-3221` | — |

### Coherencia a respetar (NO romper)

- La burbuja base, avatares y filas de acción son de `chat.md` (`.rb-chat*`) → **se conservan**. Este
  plan solo cambia el CONTENIDO interno de la burbuja del bot.
- `__cnRespuestaHtml` sigue devolviendo la nota honesta en `!resp` y `!resp.aplica` (`:3199-3200`).
- **`avisos` se pintan siempre** (`av`): llevan la declaración D-A4 de campos que producen sin meta.
  Nunca pasan por el LLM y el frontend los pinta verbatim — esa cadena no se toca.
- Se conserva el `console.log("[narración] …")` aunque la prosa no se pinte: es el único rastro de por
  qué el LLM cae al fallback.
- El HTML que devuelve esta función se concatena con las filas de acción y el zoom en `__cnRender`
  (`:3328-3330`) → el nodo raíz debe seguir siendo un solo `<div>`.

---

## §1 · Estilos — `static/css/colapsable.css` (AL FINAL del archivo)

```css
/* [2026-07-29] Respuesta de datos del chat — «Titular + métricas» (spec resp.md, artboard A).
   Reemplaza el párrafo en prosa por jerarquía: cabecera → dato principal → métricas → cierre.
   El defecto que ataca: en prosa, proyección (6.860.389) y presupuesto (6.679.262) eran
   indistinguibles. REGLA DE CONTRASTE (§2 del spec): ningún texto <=12px en gris claro; el
   mínimo es #3C4A44 (~8.6:1 sobre blanco). Etiquetas nunca por debajo de 10.5px.
   El color de estado entra por --da-st/--da-st-soft, que fija el JS por respuesta. */
.da__head { display:flex; align-items:center; gap:8px; margin-bottom:11px; flex-wrap:wrap; }
.da__eyebrow { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-size:10.5px;
  font-weight:700; letter-spacing:.7px; color:#3C4A44; text-transform:uppercase; }
.da__entidad { font-size:14.5px; font-weight:800; color:#1A2A24; }
.da__chip { margin-left:auto; display:inline-flex; align-items:center; gap:5px; font-size:11px;
  font-weight:700; border-radius:20px; padding:3px 9px; color:var(--da-st); background:var(--da-st-soft); }
.da__chip i { font-size:10px; }

.da__headline { padding-bottom:12px; border-bottom:1px solid #EEF2EF; }
.da__periodo { font-size:11px; font-weight:600; color:#3C4A44; }
.da__big { display:flex; align-items:baseline; gap:7px; margin-top:3px; flex-wrap:wrap; }
.da__big b { font-size:27px; font-weight:800; color:#1A2A24; letter-spacing:-.8px; line-height:1;
  font-variant-numeric:tabular-nums; }
.da__big span { font-size:12px; font-weight:600; color:#3C4A44; }
.da__ritmo { font-size:11.5px; color:#3C4A44; margin-top:5px; }
.da__ritmo b { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-weight:700; color:#3C4A44; }

/* A6 · la grilla tiene 1, 2 o 3 celdas según lo que exista (nunca repite el número del titular) */
.da__grid { display:grid; gap:10px; padding:12px 0; margin:0; }
.da__grid--1 { grid-template-columns:1fr; }
.da__grid--2 { grid-template-columns:1fr 1fr; }
.da__grid--3 { grid-template-columns:1fr 1fr 1fr; }
.da__grid dd { margin:0; }
.da__m-label { font-size:10.5px; font-weight:700; letter-spacing:.4px; text-transform:uppercase; color:#3C4A44; }
.da__m-value { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-size:13.5px;
  font-weight:800; color:#1A2A24; margin-top:3px; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.da__m-value.is-hero { font-size:15px; color:var(--da-st); }
.da__m-unit { font-size:10.5px; color:#3C4A44; margin-top:1px; }

/* D1 · productos NO titulares: una línea cada uno, sin competir con el titular */
.da__otros { padding-top:10px; border-top:1px solid #EEF2EF; display:flex; flex-direction:column; gap:6px; }
.da__otro { display:flex; align-items:baseline; gap:8px; font-size:11.5px; color:#3C4A44; flex-wrap:wrap; }
.da__otro-prod { font-weight:700; color:#1A2A24; min-width:62px; }
.da__otro-val { font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; font-weight:700; }
.da__otro-est { margin-left:auto; font-weight:700; color:var(--da-st2); }

.da__cierre { margin:0; padding-top:11px; border-top:1px solid #EEF2EF; font-size:12px;
  line-height:1.5; color:#3C4A44; }
.da__cierre b { font-weight:700; color:var(--da-st); }

@media (max-width:380px) { .da__grid--3 { grid-template-columns:1fr 1fr; } }
```

---

## §2 · JS — `static/js/multitab_shell.js`

### PASO 2.0 — Helpers. Insertar **justo antes** de `function __cnRespuestaHtml(resp) {` (línea ~3197):

```js
  // ===== [2026-07-29] Respuesta de datos «Titular + métricas» (spec resp.md) =====
  // A1 · Vocabulario REAL del backend: ejecucion._ESTADO_LABEL = Alineado/Rezagado/Foco/"sin meta"
  // (umbrales de analisis.api._estado: ok>=90, warn>=75, alert<75). NO son las claves de
  // __CP_STATUS. "sin meta" cae en null a propósito → sin chip, que es lo honesto.
  var __DA_EST = {
    "alineado": { label: "Alineado", color: "#1E9E5A", soft: "#E9F3EC", icon: "check-circle-fill" },
    "rezagado": { label: "Rezagado", color: "#E8912B", soft: "#FBF1E4", icon: "exclamation-triangle-fill" },
    "foco":     { label: "Foco",     color: "#C5311E", soft: "#FBECEA", icon: "exclamation-octagon-fill" }
  };
  function __daEst(txt) { return __DA_EST[String(txt || "").trim().toLowerCase()] || null; }

  // D3 · misma convención que el panel: GAS en MSCF (÷1e6), el resto en bbl exactos. Evita que el
  // chat y el tablero digan cosas distintas del mismo número. A4: null NO se concatena como "null".
  function __daNum(v, prod) {
    if (v == null) return "—";
    return (String(prod).toUpperCase() === "GAS") ? __cnGasM(v) : __cnMilesEC(Math.round(v));
  }
  function __daUni(prod, porMes) {
    var u = (String(prod).toUpperCase() === "GAS") ? "MSCF" : "bbl";
    return porMes ? (u + "/mes") : u;
  }
  // A5 · "vivo" = produjo, o tiene curva diaria, o TIENE META (real=0 con meta es el peor caso
  // posible — ARAUCA/gas, PAUTO SUR/blancos — y debe verse, no desaparecer).
  function __daVivo(l) {
    return (l.real != null && l.real > 0) || l.mtd != null || (l.ppto != null && l.ppto > 0);
  }
  // D1.1 · titular = el PRIMERO con meta en el orden de negocio que ya emite el backend
  // (CRUDO→GAS→BLANCOS); si ninguno tiene meta, el primero con dato. NO se compara por volumen:
  // el gas crudo de la BD es numéricamente mayor que el crudo en barriles SIEMPRE (unidades
  // distintas), así que "el de mayor real" habría hecho titular al gas casi siempre.
  function __daTitular(lineas) {
    var vivos = (lineas || []).filter(__daVivo);
    if (!vivos.length) return null;
    for (var i = 0; i < vivos.length; i++) if (vivos[i].cumplimiento != null) return vivos[i];
    return vivos[0];
  }
```

### PASO 2.1 — Reemplazar en `__cnRespuestaHtml` **exactamente** desde
`if (resp.narracion && resp.narracion.texto) {` hasta el `return` final de la función (líneas ~3210-3221) por:

```js
    // [2026-07-29 · D2] La prosa del LLM se RETIRA de esta burbuja (resp.md §7: no repetir en texto
    // lo que ya está en las métricas). El log de diagnóstico de arriba SE CONSERVA. ⚠️ Ops: con
    // CONSULTA_NARRA_LLM=true el backend seguiría generando la prosa para tirarla — apagar el flag
    // en el .env de 139 (maquina.py llama narrar() SIEMPRE, antes de que el frontend decida).

    // D4 · Rama B (filial): no tiene presupuesto sino "proyección vs su promedio 2026", y la
    // variación solo existe dentro de l.texto (el backend no la expone como campo). La tarjeta la
    // perdería → conserva el render de lista, que es TODO su contenido.
    if (resp.nivel === "filial" || resp.modo === "tendencia_filial") {
      var lisF = (resp.lineas || []).map(function (l) {
        return '<li class="cn-answer__row">' + esc(l.texto) + '</li>';
      }).join("");
      return '<div class="cn-answer">' +
        '<div class="cn-answer__head">' + esc(resp.encabezado || "") + '</div>' +
        '<ul class="cn-answer__list">' + lisF + '</ul>' +
        (resp.pie ? '<p class="rb-chat__note">' + esc(resp.pie) + '</p>' : "") + av + '</div>';
    }

    var L = resp.lineas || [];
    var t = __daTitular(L);
    if (!t) {   // ninguna línea con dato → nota honesta, no una tarjeta vacía (spec §8)
      return '<div class="cn-answer"><p class="rb-chat__note">' +
        esc(resp.encabezado || "") + '</p>' + av + '</div>';
    }
    var mes = resp.mes || {};
    var mesTxt = esc((mes.nombre || "") + (mes.anio ? " " + mes.anio : "")).trim();
    var est = __daEst(t.estado);
    var S = est || { color: "#3C4A44", soft: "#F1F4F1" };
    var nivLbl = (__cnNivelLabel[resp.nivel] || "").replace(/\s*\(.*\)\s*/, "");   // F4: sin paréntesis
    var esProy = !!resp.proyeccion;

    // --- Cabecera: nivel + entidad + chip de estado del titular (D-A5: el nivel se DICE) ---
    var head = '<div class="da__head">' +
      (nivLbl ? '<span class="da__eyebrow">' + esc(nivLbl) + '</span>' : "") +
      '<span class="da__entidad">' + esc(resp.entidad || "") + '</span>' +
      (est ? '<span class="da__chip"><i class="bi bi-' + est.icon + '"></i> ' + est.label + '</span>' : "") +
      '</div>';

    // --- Dato principal. A6: si hay curva diaria (solo CRUDO) el titular es lo PRODUCIDO y la
    // proyección baja a la grilla; si no, el titular ES la cifra del mes y NO se repite abajo.
    var hayMtd = (t.mtd != null);
    var bigVal = hayMtd ? t.mtd : t.real;
    var bigLbl = hayMtd
      ? ('Producido' + (mesTxt ? ' · ' + mesTxt : '') +
         (mes.dias_con_data ? ' · ' + mes.dias_con_data + ' de ' + mes.dias_del_mes + ' días con reporte' : ''))
      : ((esProy ? 'Proyección de cierre' : 'Cierre') + (mesTxt ? ' · ' + mesTxt : ''));
    var headline = '<div class="da__headline">' +
      '<div class="da__periodo">' + bigLbl + '</div>' +
      '<div class="da__big"><b>' + __daNum(bigVal, t.producto) + '</b>' +
        '<span>' + __daUni(t.producto, false) + ' de ' + esc(String(t.producto).toLowerCase()) + '</span></div>' +
      (t.bopd_avg != null
        ? '<div class="da__ritmo">ritmo promedio <b>' + __cnMilesEC(t.bopd_avg) + '</b> BOPD-avg</div>'
        : "") +
      '</div>';

    // --- Grilla: 1, 2 o 3 celdas según lo que EXISTA (nunca repite el número del titular) ---
    var uMes = __daUni(t.producto, true);
    var celda = function (lbl, val, uni, hero) {
      return '<div><dt class="da__m-label">' + lbl + '</dt>' +
        '<dd class="da__m-value' + (hero ? ' is-hero' : '') + '">' + val + '</dd>' +
        '<dd class="da__m-unit">' + uni + '</dd></div>';
    };
    var conMeta = (t.cumplimiento != null);
    var pctTxt = conMeta ? (String(t.cumplimiento).replace(".", ",") + "%") : "";
    var celdas = [];
    if (hayMtd) celdas.push(celda(esProy ? "Proyección de cierre" : "Cierre real",
                                  __daNum(t.real, t.producto), uMes, false));
    if (conMeta) {
      celdas.push(celda("Presupuesto", __daNum(t.ppto, t.producto), uMes, false));
      celdas.push(celda("Cumplimiento", pctTxt, "de la meta", true));
    }
    var grid = celdas.length
      ? '<dl class="da__grid da__grid--' + celdas.length + '">' + celdas.join("") + '</dl>' : "";

    // --- D1 · los demás productos con dato, una línea cada uno ---
    var otros = L.filter(function (l) { return l !== t && __daVivo(l); }).map(function (l) {
      var e2 = __daEst(l.estado);
      return '<div class="da__otro" style="--da-st2:' + (e2 ? e2.color : "#3C4A44") + '">' +
        '<span class="da__otro-prod">' + esc(l.producto) + '</span>' +
        '<span class="da__otro-val">' + __daNum(l.real, l.producto) + ' ' + __daUni(l.producto, true) + '</span>' +
        '<span class="da__otro-est">' + (l.cumplimiento != null
          ? String(l.cumplimiento).replace(".", ",") + '% · ' + esc(l.estado || "")
          : 'sin meta') + '</span></div>';
    }).join("");
    var bloqueOtros = otros ? '<div class="da__otros">' + otros + '</div>' : "";

    // --- Cierre: UNA oración, derivada del MISMO estado que pinta el chip (D5). Con un umbral
    // propio (>=100) un chip verde "Alineado" al 95,6% habría quedado junto a "por debajo de la
    // meta" — el mismo defecto ya reportado en las tarjetas P50. ---
    var cierre = "";
    if (conMeta) {
      cierre = 'Cerraría <b>' +
        (t.cumplimiento >= 100 ? "por encima de la meta"
          : (est && est.label === "Alineado" ? "alineado con la meta" : "por debajo de la meta")) +
        '</b> (' + pctTxt + ').';
    }
    // Productos que la entidad NO reporta (real 0 y sin meta): se declaran, no se ocultan.
    var mudos = L.filter(function (l) { return !__daVivo(l); }).map(function (l) { return l.producto; });
    if (mudos.length) cierre += (cierre ? " " : "") + "No reporta " + esc(mudos.join(" ni ")) + " en el periodo.";
    var pieCierre = cierre ? '<p class="da__cierre">' + cierre + '</p>' : "";

    // A2 · `pie` SE CONSERVA: es el descargo de proyección del 16-jul ("la cifra es del mes completo
    // y el reporte lleva N de M días"). Sin él se vuelve a leer una proyección como acumulado.
    var pieNota = resp.pie ? '<p class="rb-chat__note">' + esc(resp.pie) + '</p>' : "";

    return '<div class="cn-answer da" style="--da-st:' + S.color + ';--da-st-soft:' + S.soft + '">' +
      head + headline + grid + bloqueOtros + pieCierre + pieNota + av + '</div>';
```

> **Nota para el Executor:** el bloque `if (resp.narracion) { … console.log … }` de más arriba
> **se conserva intacto**; solo desaparece `if (resp.narracion && resp.narracion.texto) { return … }`.
> La variable `av` (avisos) ya está declarada arriba y se sigue usando en **todas** las salidas.

### PASO 2.2 — Cache-buster en `templates/main.html`: `?v=20260729p4` → `?v=20260729q1` (líneas 5 y 82, CSS y JS).

---

## §3 · Matriz de casos borde — todos verificados contra datos reales

| Caso | Entidad real | Qué debe pasar |
|---|---|---|
| 1 producto con meta | CASTILLA, RUBIALES | Titular CRUDO, chip «Alineado», grilla de 3, cierre + «No reporta GAS ni BLANCOS» |
| **3 productos con meta, 3 estados** | **CUPIAGUA** | Titular CRUDO (94,6 %, no el gas — D1.1); GAS y BLANCOS como filas con su propio color |
| **0 metas, 3 producen** | **CUSIANA** | Titular = el primero con dato; **sin chip**; grilla de 1 (o ninguna); sin frase «Cerraría» |
| **Meta con real = 0** | ARAUCA/gas, PAUTO SUR/blancos | Aparece con `0,0 % · Foco` — **no desaparece** (A5) |
| Mes cerrado | `proyeccion:false` | Dice «Cierre real», nunca «Proyección» |
| Sin curva diaria (`mtd` null) | GAS/BLANCOS titulares | Titular = cifra del mes rotulada según `esProy`; grilla de 2, **sin número repetido** (A6) |
| **Filial (rama B)** | Hocol, America, Permian | **Render de lista actual, intacto** (D4) |
| Entidad sin datos | — | `!resp.aplica` → nota simple (sin tocar) |
| Nulos sueltos | cualquiera | Se pinta `—`, nunca la palabra `null` (A4) |

---

## §4 · Backend y ops

**Código backend: NINGUNO.** No se toca `ejecucion.py`, `narracion.py`, `maquina.py` ni ningún endpoint.

**Ops (obligatorio, va con D2):** en el `.env` de **139**, `CONSULTA_NARRA_LLM=false`. Sin esto el
servidor genera prosa que nadie muestra — y es el camino que hoy devuelve 502 por arranque en frío de
Ollama (~342 s). No aplica en dev (el default ya es `false`).

---

## §5 · Verificación (ejecutar y reportar)

1. `node --check static/js/multitab_shell.js` → OK.
2. **Harness node** (mismo patrón que el test de las tarjetas P50, en scratchpad): extraer
   `__cnRespuestaHtml` + helpers **del archivo real** y renderizar los 9 casos de §3. Aserciones:
   - **A1:** un payload con `estado:"Foco"` produce chip rojo. *(Con el mapa del v1 esto falla — es la
     prueba de regresión del hallazgo.)*
   - **A2:** el HTML contiene el texto de `resp.pie`.
   - **A4:** el HTML **no** contiene la subcadena `>null<` ni `null bbl`.
   - **A5:** una línea `{real:0, ppto:1000, cumplimiento:0.0, estado:"Foco"}` aparece en la salida.
   - **A6:** con `mtd:null`, el número del titular aparece **una sola vez**; la etiqueta es
     «Proyección de cierre» si `proyeccion:true`.
   - **D1.1:** con CRUDO(meta) y GAS(meta, real 40× mayor), el titular es **CRUDO**.
   - **D4:** con `nivel:"filial"`, la salida contiene `cn-answer__list` y **no** contiene `da__head`.
   - **D5 (invariante):** nunca coexisten `#1E9E5A` (verde) y la frase `por debajo de la meta`.
3. **Navegador** (usuario): «analiza campo castilla», «producción de cupiagua», «producción de cusiana»,
   una filial (Hocol) y una entidad con producto en 0. Comparar contra el artboard A.
4. **No regresión:** desambiguación (Hocol), «Entidad identificada», zoom D-D5 y las filas de acción
   («Analizar X», «Ver el reporte de un día») deben verse **idénticas**.

---

## §6 · Fuera de alcance

- §3 (estructura de archivos React), §5 (tipos TS), §6 pasos 1 y 9 (componentes React), §10 (Vitest)
  del spec: no aplican al stack. El §10 se sustituye por el harness node de §5.
- Tarjeta propia para filiales (requiere exponer `variacion_pct` en `_linea_filial`) — ver D4.
- El badge «SOLO DÍAS CON REPORTE» a 10 px (paso 7 del spec) es de `chat.md`, no de esta burbuja.
- Borrar `narracion.py` o el flag: **no**. Queda inactivo y reversible (D2).
- Warm-up de Ollama en 139: sigue siendo su propia tarea pendiente del 29-jul.
