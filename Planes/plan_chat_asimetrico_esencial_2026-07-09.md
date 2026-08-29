# Plan ejecutable (AUDITADO v2) — Rediseño del chat de Consulta «Asimétrico esencial» (vanilla, NO React)

> **Fecha:** 2026-07-09 · **Versión:** 2 (reformulada tras auditoría adversarial)
> **Objetivo:** aplicar el diseño **A · Asimétrico esencial** (`chat.md` + mockup) al chat de la pestaña
> **Consulta**: burbujas asimétricas por emisor, avatares limpios (bot = chip verde + estrella dorada;
> usuario = inicial), opciones como filas con tile de icono verde + chevron (sin azul), kicker de éxito
> inline, badge de fecha. **Solo presentación; la lógica NO cambia.**
>
> ⚠️ **TRADUCCIÓN DE STACK.** `chat.md` está escrito para **React 19 + TS + Sass + Vitest**. Nuestro chat de
> Consulta es **VANILLA JS** en `static/js/multitab_shell.js`. **IGNORA** de la spec §3/§4/§6/§9/§10 (React).
> **NO crees** `.tsx`/`.scss` ni app React. Implementa el **diseño** en `multitab_shell.js` (render) +
> `static/css/colapsable.css` (estilos con `var(--rb-*)`). Alcance: frontend puro (backend §4 = opcional).

---

## §0 · Auditoría — hallazgos YA incorporados en este plan

- **F3 · CRÍTICO.** `.chat-messages` (style.css) da el **scroll** (`overflow-y:auto; flex:1; min-height:0`).
  Al migrar a `.rb-chat` HAY QUE reponerlo o el hilo deja de scrollear (`m.scrollTop=m.scrollHeight` no
  hace nada sin overflow). → `.rb-chat` incluye `flex:1; min-height:0; overflow-y:auto` (PASO 2).
- **F1.** El backend manda `emoji`, NO `icon`. Sin el PASO 5 (opcional) todas las opciones saldrían con el
  mismo icono. → Helper frontend `__cnOptIcon(o)` que deriva el icono del **nivel** (prefijo de `o.id`).
  Así los iconos salen correctos SIN tocar el backend (PASO 3.0 + 3.3).
- **F2.** Se dan los `old→new` exactos de cada edición.
- **F4.** `__cnValidarDia` inserta un `<div>` en `input.parentNode`; por eso la opción de fecha se mantiene
  como `<div role="button">` con **divs** internos (no spans) → anidamiento válido.
- **F5.** Iconos BI comunes (sin `building-gear`); `.rb-chat` NO existe hoy → sin colisión.

### Coherencia a respetar (NO romper)
- **C1 · Scoping:** clases NUEVAS `.rb-chat*`. **No toques `style.css` ni `.message*`** (las usa el chatbot
  principal). El chatbot principal debe quedar idéntico.
- **C2 · Lógica intacta:** no cambies el comportamiento de `__cnPreguntar/Responder/Render/Dashboard/Replay/
  DashHint/ValidarDia/EnDiseno/DisableOpts/EnableLastOpts`. Solo cambia el HTML que generan + el CSS.
- **C3 · Hooks de estado:** los botones de opción conservan **`cn-opt-btn`**; el input de fecha conserva
  **`data-ent`** + `min`/`max` + `onchange="window.__cnValidarDia(this)"`; los botones de acción del
  «completo» conservan `onclick="window.__cnEnDiseno(this)"`.
- **C4 · Auto-scroll:** `__cnAppendRaw` ya hace `m.scrollTop=m.scrollHeight` (no `scrollIntoView`). Mantener.
- **C5 · Bootstrap Icons ya cargado** (el shell usa `bi-*`). Iconos de opción: FontAwesome → `bi bi-*`.

---

## §1 · Tokens nuevos (`static/css/colapsable.css`)

Junto a los `--rb-*` (≈ líneas 85–99, con `--rb-white: #ffffff;`), añadir:

```css
  --rb-user-bg: #E9F3EC;
  --rb-gold: #C9962E;
```

## §2 · Estilos del chat (`static/css/colapsable.css`, AL FINAL). Nota F3: `.rb-chat` lleva el scroll.

```css
/* ===== Chat de Consulta — "Asimétrico esencial" (2026-07-09) ===== */
.rb-chat { flex:1; min-height:0; overflow-y:auto; background:var(--rb-off); padding:16px 14px 22px; }

.rb-chat__bot { display:flex; gap:9px; align-items:flex-start; margin-bottom:14px; }
.rb-chat__bot-bubble {
  max-width:86%; background:var(--rb-white); border:1px solid var(--rb-line);
  border-radius:4px 14px 14px 14px; padding:11px 13px;
  font-size:13px; line-height:1.5; color:var(--rb-body); box-shadow:0 1px 2px rgba(20,40,30,.04);
}
.rb-chat__bot-bubble strong { font-weight:700; color:var(--rb-ink); }
.rb-chat__bot-bubble em { font-style:italic; color:var(--rb-muted); }

.rb-chat__user { display:flex; gap:9px; justify-content:flex-end; align-items:flex-start; margin-bottom:14px; }
.rb-chat__user-bubble {
  max-width:80%; background:var(--rb-user-bg); border-radius:14px 4px 14px 14px;
  padding:9px 13px; font-size:13px; line-height:1.45; color:var(--rb-ink); font-weight:500;
}

.rb-chat__kicker {
  display:flex; align-items:center; gap:6px; margin-bottom:6px;
  font-size:11px; font-weight:800; letter-spacing:.4px; color:var(--rb-green-mid); text-transform:uppercase;
}
.rb-chat__kicker i { color:var(--rb-green-ok); font-size:13px; }

.rb-chat__options { display:flex; flex-direction:column; gap:8px; margin:11px 0 0; padding:0; list-style:none; }
.rb-chat__options li { list-style:none; }
.rb-chat__option {
  display:flex; align-items:center; gap:11px; width:100%; text-align:left; cursor:pointer;
  font-family:inherit; color:var(--rb-ink);
  border:1px solid var(--rb-line); border-radius:11px; background:var(--rb-white); padding:11px 12px;
  transition:border-color .15s, background .15s;
}
.rb-chat__option:hover { border-color:var(--rb-green-ok); background:var(--rb-green-softer); }
.rb-chat__option:focus-visible { outline:none; box-shadow:0 0 0 2px rgba(30,158,90,.5); }
.rb-chat__option-tile {
  width:36px; height:36px; border-radius:9px; background:var(--rb-green-soft);
  display:grid; place-items:center; flex:0 0 auto;
}
.rb-chat__option-tile i { font-size:16px; color:var(--rb-green-mid); }
.rb-chat__option-body { min-width:0; flex:1; }
.rb-chat__option-title { display:block; font-size:13px; font-weight:700; color:var(--rb-ink); }
.rb-chat__option-desc  { display:block; font-size:11.5px; color:var(--rb-muted); margin-top:1px; line-height:1.35; }
.rb-chat__option-chev  { flex:0 0 auto; align-self:center; color:var(--rb-faint); font-size:13px; }

.rb-chat__date { display:flex; align-items:center; gap:8px; margin-top:9px; flex-wrap:wrap; }
.rb-chat__date input {
  font-family:monospace; font-size:12px; color:var(--rb-ink); height:32px; padding:0 10px;
  border:1px solid var(--rb-line); border-radius:8px; background:var(--rb-white); color-scheme:light;
}
.rb-chat__date-badge {
  font-family:monospace; font-size:9.5px; font-weight:700; letter-spacing:.4px; color:var(--rb-muted);
  background:var(--rb-off); border:1px solid var(--rb-line); border-radius:6px; padding:3px 7px; text-transform:uppercase;
}

.rb-chat__note { margin:11px 0 0; font-size:11px; color:var(--rb-faint); font-style:italic; line-height:1.4; }

.rb-chat__avatar { width:28px; height:28px; border-radius:9px; display:grid; place-items:center; flex:0 0 auto; }
.rb-chat__avatar--bot { background:var(--rb-green); }
.rb-chat__avatar--bot i { font-size:14px; color:var(--rb-gold); }
.rb-chat__avatar--user { background:var(--rb-user-bg); color:var(--rb-green-mid); font-size:12px; font-weight:800; }

@media (prefers-reduced-motion: reduce) { .rb-chat * { transition:none !important; } }
```

## §3 · JS — `static/js/multitab_shell.js` (todas ediciones EXACTAS old→new)

### PASO 3.0 — Helper de icono por nivel (F1). Insertar junto a `var __cnNivelLabel = {…};`, DESPUÉS de esa línea:

```js
  var __cnNivelIcon = {operador:"diagram-3", filial:"building", fuente:"geo-alt", pozo:"geo-alt",
    campo:"hexagon", area:"map", activo:"box-seam", gerencia:"diagram-2", vicepresidencia:"building"};
  function __cnOptIcon(o) {   // usa o.icon si el backend lo manda; si no, lo deriva del nivel (prefijo de o.id)
    if (o.icon) return o.icon;
    var niv = String(o.id || "").split("::")[0];
    return __cnNivelIcon[niv] || "diagram-3";
  }
```

### PASO 3.1 — Contenedor del hilo (`renderConsultaBody`). Reemplazar EXACTO:
```js
      '<div class="chat-messages has-content" id="cn-messages" ' +
      '  style="max-height:none;flex:1;min-height:0;padding:10px;"></div>' +
```
por:
```js
      '<div class="rb-chat" id="cn-messages" style="flex:1;min-height:0;"></div>' +
```

### PASO 3.2 — Burbujas + avatares (`__cnAppendRaw`). Reemplazar EXACTO:
```js
    d.className = "message message-" + role;
    d.innerHTML = '<div class="message-content"><div class="message-avatar">' +
      (role === "user" ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>') +
      '</div><div class="message-text">' + html + '</div></div>';
```
por:
```js
    if (role === "user") {
      var ini = (__cnNombre().charAt(0) || "•").toUpperCase();
      d.className = "rb-chat__user";
      d.innerHTML = '<div class="rb-chat__user-bubble">' + html + '</div>' +
        '<div class="rb-chat__avatar rb-chat__avatar--user" aria-hidden="true">' + esc(ini) + '</div>';
    } else {
      d.className = "rb-chat__bot";
      d.innerHTML = '<div class="rb-chat__avatar rb-chat__avatar--bot" aria-hidden="true"><i class="bi bi-stars"></i></div>' +
        '<div class="rb-chat__bot-bubble">' + html + '</div>';
    }
```

### PASO 3.3 — Opciones de desambiguación (`__cnRender`, rama `pendiente`). Reemplazar EXACTO:
```js
      var btns = d.opciones.map(function (o) {
        var emoji = o.emoji ? (o.emoji + " ") : "";
        var desc = o.desc ? ('<div class="small text-muted" style="line-height:1.15;font-weight:400;">' +
          esc(o.desc) + '</div>') : "";
        return '<button type="button" class="btn btn-outline-primary text-start w-100 mb-2 cn-opt-btn" ' +
          'onclick="window.__cnResponder(\'' + esc(o.id) + '\',\'' + esc(o.label) + '\')">' +
          '<span style="font-weight:600;">' + emoji + esc(o.label) + '</span>' + desc + '</button>';
      }).join("");
      __cnBubble("assistant", esc(__cnConNombre(d.pregunta)) + '<div class="mt-2">' + btns + '</div>');
```
por:
```js
      var rows = d.opciones.map(function (o) {
        return '<li><button type="button" class="rb-chat__option cn-opt-btn" ' +
          'onclick="window.__cnResponder(\'' + esc(o.id) + '\',\'' + esc(o.label) + '\')">' +
          '<span class="rb-chat__option-tile"><i class="bi bi-' + esc(__cnOptIcon(o)) + '"></i></span>' +
          '<span class="rb-chat__option-body"><span class="rb-chat__option-title">' + esc(o.label) + '</span>' +
          (o.desc ? '<span class="rb-chat__option-desc">' + esc(o.desc) + '</span>' : '') +
          '</span><i class="rb-chat__option-chev bi bi-chevron-right"></i></button></li>';
      }).join("");
      __cnBubble("assistant", esc(__cnConNombre(d.pregunta)) +
        '<ul class="rb-chat__options" role="list">' + rows + '</ul>');
```
(NO cambiar las 3 líneas siguientes: `__cnOptsOpen = true;` / `__cnLastIntent = null;` / `__cnDashHint(...)` / `return;`.)

### PASO 3.4 — Mensaje «Entidad identificada» (`__cnRender`, rama `completo`).
Mantener `entName/nivel/ramaCorta/huella/avisos`. Reemplazar EXACTO desde `// Botón analítico…` hasta el
`__cnBubble("assistant", … siguiente fase.</div>');` (inclusive). Es decir, reemplazar:
```js
      // Botón analítico (absorbe cuánto produce / cómo ha cambiado / qué campos aportan). Placeholder no-op.
      var btnAnalizar =
        '<button type="button" class="btn btn-outline-primary text-start w-100 mb-2 cn-next-btn" ' +
        'onclick="window.__cnEnDiseno(this)"><span style="font-weight:600;">' +
        '<i class="fas fa-chart-column me-1"></i>Analizar ' + entName + '</span>' +
        '<div class="small text-muted" style="line-height:1.15;font-weight:400;">' +
        'Cuánto produce, cómo ha cambiado y qué campos aportan más</div></button>';
      // Botón "reporte de un día" (solo si hay grano diario). Placeholder no-op; selector acotado al rango.
      var btnDia = "";
      if (h.aplica) {
        btnDia =
          '<div role="button" class="btn btn-outline-primary text-start w-100 mb-2 cn-next-btn" ' +
          'onclick="window.__cnEnDiseno(this)"><span style="font-weight:600;">' +
          '<i class="fas fa-calendar-day me-1"></i>Ver el reporte de un día</span>' +
          '<div class="small text-muted" style="line-height:1.15;font-weight:400;">consulta puntual de una fecha</div>' +
          '<div class="mt-1" onclick="event.stopPropagation();"><input type="date" class="form-control form-control-sm d-inline-block" ' +
          'style="max-width:170px;vertical-align:middle;" min="' + esc(h.desde) + '" max="' + esc(h.hasta) + '" ' +
          'data-ent="' + esc(it.valor || it.entidad) + '" onchange="window.__cnValidarDia(this)"> ' +
          '<span class="small text-muted">solo días con reporte</span></div></div>';
      }
      __cnBubble("assistant",
        '<div class="mb-1"><i class="fas fa-circle-check text-success me-1"></i>' +
        '<strong class="text-success">Entidad identificada</strong></div>' +
        'Identifiqué a <strong>' + entName + '</strong> como <strong>' + esc(nivel) + '</strong> (' + esc(ramaCorta) + ').<br>' +
        huella + avisos +
        '<div class="mt-2 mb-2">Con eso ya puedo trabajar. <strong>¿Qué quieres saber de ' + entName + '?</strong></div>' +
        btnAnalizar + btnDia +
        '<div class="text-muted small mt-1">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</div>');
```
por:
```js
      // Botón analítico (absorbe cuánto produce / cómo ha cambiado / qué campos aportan). Placeholder no-op.
      var btnAnalizar = '<li><button type="button" class="rb-chat__option" onclick="window.__cnEnDiseno(this)">' +
        '<span class="rb-chat__option-tile"><i class="bi bi-bar-chart-line"></i></span>' +
        '<span class="rb-chat__option-body"><span class="rb-chat__option-title">Analizar ' + entName + '</span>' +
        '<span class="rb-chat__option-desc">Cuánto produce, cómo ha cambiado y qué campos aportan más</span></span>' +
        '<i class="rb-chat__option-chev bi bi-chevron-right"></i></button></li>';
      // Botón "reporte de un día" (solo si hay grano diario). F4: <div role=button> con DIVS (para el mensaje de validación).
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
      __cnBubble("assistant",
        '<div class="rb-chat__kicker"><i class="bi bi-check-circle-fill"></i>Entidad identificada</div>' +
        'Identifiqué a <strong>' + entName + '</strong> como <strong>' + esc(nivel) + '</strong> (' + esc(ramaCorta) + ').<br>' +
        huella + avisos +
        '<div class="mt-2">Con eso ya puedo trabajar. <strong>¿Qué quieres saber de ' + entName + '?</strong></div>' +
        '<ul class="rb-chat__options" role="list">' + btnAnalizar + btnDia + '</ul>' +
        '<p class="rb-chat__note">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</p>');
```
(NO tocar la línea siguiente `if (d.intent) window.__cnDashboard(d.intent);`.)

### PASO 3.5 — Icono de «reformular» (cosmético). Reemplazar EXACTO:
```js
      __cnBubble("assistant", '<i class="fas fa-circle-exclamation text-warning me-1"></i>' + esc(msg)); return;
```
por:
```js
      __cnBubble("assistant", '<i class="bi bi-exclamation-triangle-fill me-1" style="color:var(--rb-gold);"></i>' + esc(msg)); return;
```

## §4 · Cierre
- Subir el cache-buster de `multitab_shell.js` en `templates/main.html` (`?v=…` → `20260709c`).

## §5 · Backend (OPCIONAL — el frontend ya resuelve el icono por nivel, F1)
Solo si se quiere que el icono lo mande el backend: en `maquina.py`, añadir `"icon"` a cada entrada de
`_NIVEL_INFO` y emitir `"icon": info.get("icon", "diagram-3")` en `_salida` (rama pendiente). Reiniciar :8000.
**Si NO se hace, no pasa nada:** `__cnOptIcon` deriva el icono del nivel. NO es necesario para este plan.

---

## §6 · Verificación (ejecutar y reportar)
- **V1 · Sintaxis:** `node --check static/js/multitab_shell.js` → OK.
- **V2 · Scroll (F3):** con varios mensajes, el hilo **scrollea** y auto-baja al último.
- **V3 · Asimetría:** bot IZQ (avatar verde + estrella dorada, burbuja blanca borde fino, esquina sup-izq
  mordida); usuario DER (burbuja verde suave + avatar con inicial).
- **V4 · Desambiguación:** "hocol" → 2 filas `.rb-chat__option` con **iconos distintos** (Operación vs
  Empresa), tile verde + título Sentence case + desc + chevron. **Sin azul.** Hover verde.
- **V5 · Deshabilitar:** al elegir, ambas quedan deshabilitadas (sigue `cn-opt-btn`).
- **V6 · Entidad identificada:** kicker "✓ ENTIDAD IDENTIFICADA" inline + 2 filas de acción; la de fecha con
  input + badge "SOLO DÍAS CON REPORTE"; pie en cursiva.
- **V7 · Fecha:** validación intacta (elegir un hueco → lo rechaza, mensaje debajo); dashboard derecho OK.
- **V8 · No regresión chatbot principal:** el chat Robustez/Producción se ve IDÉNTICO (no heredó `.rb-chat`).

## §7 · Fuera de alcance
Input de composición inferior, lógica NLP, riel de pestañas, y todo lo React de `chat.md` (§3/§4/§6/§9/§10).
Alineación del chatbot principal al mismo look = decisión posterior.
