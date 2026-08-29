# Plan ejecutable (AUDITADO) — Dashboard de la entidad resuelta en el panel derecho de Consulta

> **Fecha:** 2026-07-08 · **Versión:** 2 (reformulada tras auditoría adversarial)
> **Objetivo:** cuando el chat de **Consulta** resuelve una entidad (status `completo`), pintar en el
> **panel derecho** (`#cn-viewer-area`, ya existe) un **dashboard** con **Densidad temporal** (heatmap) y
> **Cobertura del reporte** (tabla por familias), reutilizando las funciones de render de la pestaña Análisis.
> **Alcance:** frontend `static/js/multitab_shell.js` + 1 línea de cache-buster en `templates/main.html`.
> **NO toca** el backend FastAPI (`analisis/api.py`), ni `maquina.py`/`resolver.py`.

## Decisiones cerradas (con el usuario)
- **Render en `completo`** (no al aparecer los botones). Sin ambigüedad → se pinta de inmediato; con
  ambigüedad → al elegir el botón. Mientras hay botones (`pendiente`) → **aviso guía** en el panel.
- **Gate por rama:** **A** → densidad + cobertura; **B (filial)** → cobertura + nota "cifra consolidada,
  sin grano diario ECP" (coherente con `_huella`, que ya distingue rama A/B).

---

## §0 · Auditoría (hallazgos que ESTE plan ya incorpora)

- **F1 · CRÍTICO — colisión de nombre `rama`.** En `__cnRender`, bloque `completo`, YA existe una variable
  local `var rama` que es **texto de display** (`"ECP (rama A)"` / `"Filial (rama B)"`), NO `"A"/"B"`.
  → El dashboard es una función aparte `__cnDashboard(intent)` con su propio scope y lee **`intent.rama`
  crudo** (`"A"`/`"B"`) desde `d.intent`. **El Executor NO debe pasar ni reutilizar la `rama` de display.**
- **F2 · Defecto corregido.** Una sola versión de `__cnDashHint` (escribe SOLO dentro de `#cn-viewer-area`).
- **F3 · Mejora incorporada.** En `pendiente` se hace `__cnLastIntent = null` para no repintar un dashboard
  viejo si el usuario cambia de pestaña a mitad de la desambiguación.
- **F4 · Mejora operativa.** Subir el cache-buster de `multitab_shell.js` en `main.html`.
- **F5 · Verificado.** `var __cnLastIntent` (hoisted) es referenciable por `renderViewer` (definido antes)
  sin TDZ; en runtime ya está inicializado. `window.__cnDashboard` existe cuando `renderViewer` corre.
- **F6 · Verificado.** Un fetch de cobertura (~10s) rezagado escribe en un nodo ya desprendido → inofensivo;
  gana el último render. No se necesita AbortController en v1.
- **F7 · Decisión.** En `reformular`/`error` se DEJA el último dashboard (último panorama válido).
- **F8 · Descartado.** No pasar `d.huella` al dashboard (evita dos resúmenes que puedan discrepar con el de
  `/densidad`). Se acepta R-A (abajo).
- **Frontera LLM/Python:** intacta. El dashboard es Python (endpoints) + JS de presentación; el LLM no interviene.

### Contratos verificados (no reimplementar — llamar)
- `__anRenderDensidad(d)` → HTML de densidad (incluye `<div id="an-heatmap">`). Local, en scope.
- `__anHeatmap(por_mes, dias)` → pinta el Plotly en `#an-heatmap`. Local, en scope.
- `__anRenderCobertura(cob)` → HTML de cobertura. Local, en scope.
- `GET /api/analisis/densidad?entidad=<valor>` → `{aplica_ecp, resumen, semaforo, por_mes, dias, entidad}`.
- `GET /api/analisis/cobertura?entidad=<valor>` → lo que consume `__anRenderCobertura`.
- Valor a pasar: `intent.valor` (funciona para todos los niveles rama A; endpoints resuelven multi-columna + vice_id).

### Riesgos aceptados en v1 (documentar, NO intentar arreglar)
- **R-A:** el chat (`_huella`) cuenta por columna exacta del nivel; `/densidad` cuenta multi-columna →
  posible diferencia menor en entidades cuyo nombre aparezca en varias columnas (para Hocol-operador ambos=173).
  Fase 2: pasar `nivel` a `/densidad`.
- **R-B:** `/cobertura` no es identity-aware (combina ECP-operador + hojas de filial). Para la filial es lo útil.
- **R-C:** el id `an-heatmap` se reutiliza entre Consulta y Análisis (no coexisten montados → sin colisión).
  **No renombrar.**

---

## §1 · Cambios

### PASO 1 — Helpers + estado (en `static/js/multitab_shell.js`, JUSTO DESPUÉS de la función `__cnConNombre`)

Insertar:

```js
  var __cnLastIntent = null;   // último intent resuelto → para repintar el dashboard al volver a la pestaña
  function __cnViewerArea() { return el("cn-viewer-area"); }

  // Aviso guía en el panel derecho (estado pendiente / previo a resolver). Escribe SOLO dentro de
  // #cn-viewer-area; la cabecera verde del viewer la mantiene renderViewer.
  function __cnDashHint(texto) {
    var a = __cnViewerArea(); if (!a) return;
    a.innerHTML =
      '<div class="rb-cp-vempty"><div class="rb-cp-vempty__inner">' +
      '  <div class="rb-cp-vempty__chip"><i class="bi bi-hand-index"></i></div>' +
      '  <div class="rb-cp-vempty__eyebrow">Panorama</div>' +
      '  <p class="rb-cp-vempty__hint">' + esc(texto) + '</p>' +
      '</div></div>';
  }
```

### PASO 2 — La función del dashboard (INMEDIATAMENTE DESPUÉS de `__cnDashHint`)

```js
  // Dashboard de la entidad resuelta. USA intent.rama CRUDO ("A"/"B") — NO el texto de display de __cnRender.
  window.__cnDashboard = function (intent) {
    __cnLastIntent = intent;
    var a = __cnViewerArea(); if (!a || !intent) return;
    var ent = intent.valor || intent.entidad;
    var esFilial = (intent.rama === "B");
    var nivelLabel = __cnNivelLabel[intent.nivel] || intent.nivel;

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

    // Densidad: SOLO rama A (ECP). Rama B (filial) → nota, sin heatmap (coherente con _huella).
    var dEl = el("cn-dash-densidad");
    if (esFilial) {
      if (dEl) dEl.innerHTML = '<div class="alert alert-warning small mb-0">Es una <strong>empresa filial</strong>: ' +
        'su producción se reporta como <strong>cifra consolidada</strong> (sin grano diario ECP). ' +
        'Revisa su presencia abajo, en <strong>Cobertura del reporte</strong>.</div>';
    } else {
      fetch("/api/analisis/densidad?entidad=" + encodeURIComponent(ent))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!dEl) return;
          dEl.innerHTML = __anRenderDensidad(d);
          if (d.aplica_ecp !== false && d.dias && d.dias.length) __anHeatmap(d.por_mes, d.dias);
        })
        .catch(function () { if (dEl) dEl.innerHTML = '<div class="alert alert-danger small mb-0">Error calculando la densidad.</div>'; });
    }

    // Cobertura: ambas ramas (para la filial es lo más útil).
    var cEl = el("cn-dash-cobertura");
    fetch("/api/analisis/cobertura?entidad=" + encodeURIComponent(ent))
      .then(function (r) { return r.json(); })
      .then(function (cob) { if (cEl) cEl.innerHTML = __anRenderCobertura(cob); })
      .catch(function () { if (cEl) cEl.innerHTML = '<div class="alert alert-danger small mb-0">Error cargando la cobertura.</div>'; });
  };
```

### PASO 3 — Enganchar en `__cnRender` (2 ediciones EXACTAS)

**3a · rama `pendiente`.** Reemplazar EXACTO esta línea:

```js
      __cnBubble("assistant", esc(__cnConNombre(d.pregunta)) + '<div class="mt-2">' + btns + '</div>'); return;
```

por:

```js
      __cnBubble("assistant", esc(__cnConNombre(d.pregunta)) + '<div class="mt-2">' + btns + '</div>');
      __cnLastIntent = null;   // F3: olvida cualquier dashboard previo mientras se elige
      __cnDashHint("Elige una de las opciones para ver su panorama de datos.");
      return;
```

**3b · rama `completo`.** Es el ÚLTIMO `__cnBubble(...)` del bloque, que termina en
`…el cálculo del número es Fase 3.)</div>');`. INMEDIATAMENTE DESPUÉS de ese `);`, añadir:

```js
      if (d.intent) window.__cnDashboard(d.intent);   // pinta el dashboard (usa intent.rama CRUDO "A"/"B")
```

(No modificar el texto de la burbuja; solo añadir la línea después de cerrarla.)

### PASO 4 — Persistencia en `renderViewer` (rama `consulta`)

En `renderViewer`, en el `else if (state.activeTab === "consulta")`, el `viewer.innerHTML = …` termina en la
línea `'  </div></div></div>';`. INMEDIATAMENTE DESPUÉS de esa línea (aún dentro del `else if`), añadir:

```js
      if (__cnLastIntent) window.__cnDashboard(__cnLastIntent);   // repinta el dashboard si ya se resolvió
```

### PASO 5 — Cache-buster (`templates/main.html`)

Localizar el `<script>` de `multitab_shell.js` (tiene `?v=20260701`) y cambiar SOLO el valor de la query:

```
?v=20260701   →   ?v=20260708
```

---

## §2 · Verificación (ejecutar y reportar)

- **V1 · Sintaxis:** `node --check static/js/multitab_shell.js` → OK.
- **V2 · Rama A directa:** *"producción de Castilla"* → panel derecho: **Panorama de CASTILLA** con heatmap +
  tabla de meses + cobertura. El nº de días de la densidad ~ coherente (~173) con la huella del chat.
- **V3 · Rama A vía botón:** *"hocol"* → **Operación (ECP)** → densidad 173 días (heatmap) + cobertura.
- **V4 · Rama B (filial):** *"hocol"* → **Empresa / filial** → Densidad = **nota de filial** (sin heatmap) +
  Cobertura poblada (INICIO / POP Filiales / Producción filiales = 138 rep).
- **V5 · Estado pendiente:** con los 2 botones de Hocol a la vista (sin elegir) → panel derecho = **aviso guía**.
- **V6 · Persistencia:** con un dashboard pintado, ir a la pestaña **Análisis** y volver a **Consulta** → el
  dashboard sigue ahí; el historial del chat también.
- **V7 · F3:** pedir Hocol (aparecen botones, NO elegir) → cambiar a Análisis y volver → panel derecho muestra
  el **aviso guía** (NO un dashboard viejo).
- **V8 · No regresión:** pestaña **Análisis** (Catálogo/Densidad/Cobertura con su selector) intacta; **Ingesta**
  y **Control** intactas; consola sin errores nuevos.

## §3 · Caveats (dejar registrados)
R-A (conteo chat vs densidad multi-columna), R-B (cobertura no identity-aware), R-C (`an-heatmap` reutilizado).
Todos aceptados en v1.

## §4 · Fuera de alcance (Fase 2+)
Densidad/cobertura identity-aware en backend; preview lado a lado de las 2 identidades; cálculo del número (Fase 3).
