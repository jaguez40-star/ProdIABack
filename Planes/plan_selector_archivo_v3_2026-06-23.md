# Plan ejecutable — Selector de archivo **V3 (encabezado verde)** · 2026-06-23 · **v2 (auditado)**

> **Alcance estricto:** reskin de **SOLO la zona de selección de archivo** de la vista de ingesta de ProdIA
> (el bloque "Cargar Reporte Diario"), para que se vea **igual a la imagen V3** y **acorde a `selector.md`**.
> El **árbol de hojas** (`#ingesta-sheets`) y la **tabla** (ya reskineados), el **chat**, gráficos y todo lo
> demás quedan **EXACTAMENTE igual**. **Sin React** (se traduce la spec visual a vanilla JS + CSS, reusando
> los tokens `--g-*` ya presentes en `static/css/ingesta.css`). **Sin cambios de backend/BD.**

Modo: **plan para Executor** (sin contexto previo). Ejecutar al pie de la letra. Rutas absolutas.

---

## 0 · Contexto (código actual real)

El selector se inyecta en `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` dentro de
`chatMessages.innerHTML` (~L176-186): un `<h6>` + `<p>` + `<input type=file class="form-control">` + badge
`CPF` + botón Bootstrap "Cargar e ingerir", seguido de `#ingesta-sheets` (árbol) y `#ingesta-status`
(ResumenCard). Flujo: el `onchange` del input llama `onIngestaFileChange` (~L232) que lee las hojas con
JSZip (`readSheetsFromXlsm`), detecta NEW/STD y arma el árbol; `handleIngestaUpload` (~L271) hace el POST a
`/api/ingesta/upload_stream` usando `input.files[0]`.

El reskin previo ya dejó en `ingesta.css` los tokens `--g-*` y las clases `.ig-*`/`.rb-*` (reusar).

## 0.b · Decisiones cerradas (audit-first)

- **D1 — Fecha BLOQUEANTE:** "CARGAR E INGERIR" queda **deshabilitado** si el nombre del archivo no contiene
  una fecha **YYYYMMDD válida** (real, no solo el patrón → rechaza `20241340`). (Es lo que pide el doc §2/§8.)
- **D2 — Sin "máx 25 MB":** el subtítulo del dropzone del doc dice "máx 25 MB", **falso** para esta app (los
  reportes NEW pesan ~125 MB). Se usa solo `.xlsx · .xlsm` sin claim de tamaño.
- **D3 — Badge STD/NEW dinámico:** el tipo se detecta tras leer las hojas (JSZip), no al instante → el badge
  arranca **vacío** y se rellena (NEW/STD) cuando termina la lectura. La **fecha** sí sale al instante.
- **D4 — Vanilla:** sin React/TanStack; se reusan los tokens de `ingesta.css`. El destino se mantiene `CPF`
  (como hoy).

## 0.c · Hallazgos de auditoría (v2 — verificados contra el código real)

- **Seguridad de pipeline (PASS).** `onIngestaFileChange` solo aparece en su definición (L232) y en el
  `onchange` del input (L181) — ambos se reemplazan; **no hay callers huérfanos**. `ingesta-file` solo en el
  input y en `handleIngestaUpload` (reescrito). Los identificadores nuevos (`igSetFile`, `igRenderDropzone`,
  `igReadSheetsPreview`, `igPickFile`, `window.__ingestaFile`) **no existen** previamente → sin colisiones.
  Sin referencias en templates. El `inicio` de `renderIngestaProgress` solo reconstruye el **árbol** (no el
  selector) y solo si `#ingesta-sheet-list` no existe → no interfiere.
- **I-A (mejora).** El badge `#ingesta-mode-badge` arranca vacío → se vería un pill vacío. Se oculta con
  `#ingesta-mode-badge:empty{display:none}` (§4).
- **I-B (bug real corregido).** Re-seleccionar el **mismo** archivo con "Cambiar"/dropzone **no** dispara
  `onchange` (los navegadores no re-emiten change si el valor no cambia). Se introduce `igPickFile()` que
  **resetea `input.value` antes de `click()`** (§5.4), usado por el dropzone y por "Cambiar".

---

## 1 · Objetivo

Reemplazar el bloque del selector por el **card V3**: barra de encabezado **verde sólido** (icono
`cloud-arrow-up-fill` dorado + "Cargar Reporte Diario" + subtítulo mono + badge STD/NEW), **FileChip** (con
archivo: thumb XLSX + nombre truncado + línea de validación "✓ Fecha dd/mm/aaaa · destino CPF" + botón
**Cambiar**), **dropzone** (sin archivo: click + drag&drop), **estado error** (rojo), y botón **CARGAR E
INGERIR** verde 42px **deshabilitado hasta válido**.

## 2 · Prerequisitos (si falla, DETENER y reportar)

- **P1.** Existe `static/js/chat.js` con: el bloque selector (~L176-186), `onIngestaFileChange` (~L232),
  `readSheetsFromXlsm` (~L260), `handleIngestaUpload` (~L271).
- **P2.** Existe `static/css/ingesta.css` (del reskin previo) con el `:root{ --g-* }` y reglas `.ig-*`.
- **P3.** La ingesta funciona hoy (subir un `.xlsm` lee hojas, arma árbol y permite ingerir).

**Entorno:** Windows 11, PowerShell. ProdIA = Flask :8020 (estático; **sin build**). Ver cambios: `Ctrl+F5`.

## 3 · Inventario de archivos a modificar (2 archivos; sin backend)

| Archivo | Cambio |
|---|---|
| `static/css/ingesta.css` | **+** tokens `--g-red`/`--g-mist` y reglas `.rb-upload*`/`.rb-chip*`/`.ig-spin` (§4) |
| `static/js/chat.js` | Reescritura del bloque selector (§5.1), `onIngestaFileChange`→`igReadSheetsPreview` (§5.2), `handleIngestaUpload` (§5.3), + helpers `ig*` del selector (§5.4) |

**NO se toca:** nada más. El árbol, la tabla, el chat, el backend, otras funciones.

---

## 4 · `static/css/ingesta.css` — agregar al final (reusa los `--g-*` existentes)

Primero, **agregar 2 tokens** al bloque `:root{ … }` existente (junto a los demás `--g-*`):

```css
  --g-red:#C5311E; --g-mist:#BFE0CD;
```

Luego **agregar al final del archivo** estas reglas:

```css
/* ===== Selector de archivo V3 (dentro de chatMessages, encima del árbol) ===== */
.rb-upload{border:1px solid var(--g-line);border-radius:14px;overflow:hidden;background:#fff;box-shadow:0 1px 3px rgba(15,27,42,.05);}
.rb-upload__head{display:flex;align-items:center;gap:10px;padding:13px 16px;background:var(--g-green);}
.rb-upload__head .ic{color:var(--g-gold);font-size:18px;flex:none;}
.rb-upload__head .ttl{font-size:14px;font-weight:800;color:#fff;line-height:1.2;}
.rb-upload__head .sub{font-family:var(--g-mono);font-size:10.5px;color:var(--g-mist);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rb-upload__head .std{margin-left:auto;font-family:var(--g-mono);font-size:10px;font-weight:700;color:#fff;background:rgba(255,255,255,.18);padding:2px 8px;border-radius:5px;white-space:nowrap;text-align:center;}
#ingesta-mode-badge:empty{display:none;}  /* I-A: sin pill vacío hasta detectar NEW/STD */
.rb-upload__body{padding:14px 16px;}
.rb-chip{display:flex;align-items:center;gap:10px;border:1px solid var(--g-line);border-radius:11px;padding:10px 12px;background:var(--g-off);}
.rb-chip__thumb{width:36px;height:36px;border-radius:9px;background:var(--g-green-soft);display:grid;place-items:center;flex:0 0 auto;}
.rb-chip__thumb .bi{color:var(--g-green-mid);font-size:19px;}
.rb-chip__main{min-width:0;flex:1;}
.rb-chip__name{font-size:12px;font-weight:700;color:var(--g-ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rb-chip__val{display:flex;align-items:center;gap:6px;margin-top:2px;font-size:10.5px;font-weight:600;color:var(--g-green-mid);}
.rb-chip__val.is-error{color:var(--g-red);}
.rb-chip__change{margin-left:auto;height:30px;padding:0 10px;border:1px solid var(--g-line);background:#fff;border-radius:8px;font-size:11.5px;font-weight:700;color:var(--g-body);cursor:pointer;white-space:nowrap;flex:none;}
.rb-upload__drop{width:100%;border:1.5px dashed var(--g-green-ok);background:var(--g-green-soft);border-radius:11px;padding:18px 14px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;}
.rb-upload__drop.is-over{background:#d8eede;border-color:var(--g-green-mid);}
.rb-upload__drop .bi{color:var(--g-green-mid);font-size:26px;}
.rb-upload__drop .t1{font-size:12.5px;font-weight:700;color:var(--g-green);}
.rb-upload__drop .t2{font-size:10.5px;color:var(--g-muted);}
.rb-upload__submit{width:100%;height:42px;margin-top:13px;border:0;border-radius:10px;cursor:pointer;background:var(--g-green);color:#fff;font-size:13px;font-weight:800;letter-spacing:.4px;display:flex;align-items:center;justify-content:center;gap:8px;}
.rb-upload__submit .bi{font-size:15px;}
.rb-upload__submit:disabled{background:#C7D3CC;cursor:not-allowed;}
@keyframes ig-spin{to{transform:rotate(360deg);}}
.ig-spin{display:inline-block;animation:ig-spin .9s linear infinite;}
@media (prefers-reduced-motion:reduce){.ig-spin{animation:none;}}
```

---

## 5 · `static/js/chat.js`

### 5.1 Bloque selector — reemplazar `chatMessages.innerHTML = \`…\`` (~L176-186) por:

```javascript
    chatMessages.innerHTML = `
      <div style="padding:1rem;">
        <div class="rb-upload">
          <div class="rb-upload__head">
            <i class="bi bi-cloud-arrow-up-fill ic"></i>
            <div style="min-width:0">
              <div class="ttl">Cargar Reporte Diario</div>
              <div class="sub">nombre con fecha YYYYMMDD</div>
            </div>
            <span class="std" id="ingesta-mode-badge"></span>
          </div>
          <div class="rb-upload__body">
            <input type="file" id="ingesta-file" accept=".xlsm,.xlsx" hidden onchange="window.igOnFileInput(event)">
            <div id="ingesta-filezone"></div>
            <button id="ingesta-upload-btn" class="rb-upload__submit" disabled onclick="window.handleIngestaUpload()">
              <i class="bi bi-box-arrow-in-down"></i> CARGAR E INGERIR</button>
          </div>
        </div>
        <div id="ingesta-sheets" class="mt-3"></div>
        <div id="ingesta-status" class="mt-3"></div>
      </div>`;
    window.igRenderDropzone();
```

### 5.2 `onIngestaFileChange` (~L232-258) — reemplazar la función completa por `igReadSheetsPreview(file)`

(Misma lógica de lectura de hojas + armado del árbol; ahora recibe `file` y setea el badge STD/NEW.)

```javascript
window.igReadSheetsPreview = async function igReadSheetsPreview(file) {
  const sheetsBox = document.getElementById("ingesta-sheets");
  const status = document.getElementById("ingesta-status");
  const badge = document.getElementById("ingesta-mode-badge");
  if (status) status.innerHTML = "";
  if (!file || !sheetsBox) return;
  sheetsBox.innerHTML = '<div class="text-muted small"><div class="spinner-border spinner-border-sm"></div> Leyendo hojas…</div>';
  try {
    const names = await window.readSheetsFromXlsm(file);
    window.__ingestaTotal = names.length;
    window.__ingestaDone = 0;
    const RAW = ["BDP_datos_dia", "BDP_datos_mes", "BDP_Programa"];
    const esNew = RAW.every((r) => names.includes(r));
    if (badge) badge.textContent = esNew ? "NEW" : "STD";
    const items = names.map((n) => window.ingestaSheetLi(n)).join("");
    sheetsBox.innerHTML = `
      <div class="ig-tree__head">
        <span class="ig-tree__title">Hojas del archivo</span>
        <span class="ig-badge ig-badge--blue" id="ingesta-counter">0 / ${names.length}</span>
        <span class="ig-mode">${esNew ? "NEW" : "STD"}</span>
        <button class="ig-expand-btn" onclick="window.igExpandAll(this)" aria-pressed="true">
          <i class="bi bi-chevron-bar-contract"></i> Colapsar todo</button>
      </div>
      <ul id="ingesta-sheet-list" class="ig-tree__body">${items}</ul>`;
  } catch (err) {
    sheetsBox.innerHTML = `<div class="alert alert-warning py-2">No se pudieron leer las hojas: ${err}</div>`;
  }
};
```

### 5.3 `handleIngestaUpload` (~L271-302) — reemplazar la función completa por:

(Usa `window.__ingestaFile` en vez de `input.files[0]`; respeta el bloqueo por validez; estado "CARGANDO…".)

```javascript
window.handleIngestaUpload = async function handleIngestaUpload() {
  const status = document.getElementById("ingesta-status");
  const btn = document.getElementById("ingesta-upload-btn");
  const file = window.__ingestaFile;
  if (!file || (btn && btn.disabled)) {
    if (status) status.innerHTML = '<div class="alert alert-warning py-2">Selecciona un archivo con fecha válida (YYYYMMDD) primero.</div>';
    return;
  }
  window.__ingestaDone = 0;
  document.querySelectorAll("#ingesta-sheet-list li").forEach((li) => {
    const ic = li.querySelector(".ingesta-ic"); if (ic) ic.classList.add("is-pending");
    const cnt = li.querySelector(".ig-sheet__count"); if (cnt) cnt.style.display = "none";
    delete li.dataset.contado;
    const kids = li.querySelector(".ingesta-children"); if (kids) kids.innerHTML = "";
  });
  const counter = document.getElementById("ingesta-counter");
  if (counter && window.__ingestaTotal) counter.textContent = `0 / ${window.__ingestaTotal}`;

  const fd = new FormData();
  fd.append("file", file);
  const prev = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-arrow-repeat ig-spin"></i> CARGANDO…'; }
  status.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm"></div> Ingiriendo… (no cierres esta ventana; un archivo NEW puede tardar varios minutos)</div>';
  try {
    const r = await fetch("/api/ingesta/upload_stream", { method: "POST", body: fd });
    const data = await r.json();
    window.renderIngestaFinal(data);
  } catch (e) {
    status.innerHTML = `<div class="alert alert-danger">Fallo de red: ${e}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = prev; }
  }
};
```

### 5.4 Helpers nuevos del selector (agregar junto a los otros `window.ig*`, al final del archivo)

```javascript
// ---- Selector de archivo V3 ----
window.igParseFecha = function (name) {                 // YYYYMMDD real -> dd/mm/aaaa (o null)
  const m = String(name).match(/(\d{4})(\d{2})(\d{2})/);
  if (!m) return null;
  const [, y, mo, d] = m;
  const dt = new Date(+y, +mo - 1, +d);
  if (dt.getFullYear() !== +y || dt.getMonth() !== +mo - 1 || dt.getDate() !== +d) return null;
  return `${d}/${mo}/${y}`;
};
window.igTruncName = function (name) {                  // 14 + … + 9
  name = String(name);
  return name.length > 26 ? name.slice(0, 14) + "…" + name.slice(-9) : name;
};
window.igPickFile = function () {                       // I-B: reset value para que re-elegir el mismo archivo dispare onchange
  const i = document.getElementById("ingesta-file"); if (i) { i.value = ""; i.click(); }
};
window.igRenderDropzone = function () {
  const zone = document.getElementById("ingesta-filezone"); if (!zone) return;
  window.__ingestaFile = null;
  const btn = document.getElementById("ingesta-upload-btn"); if (btn) btn.disabled = true;
  const badge = document.getElementById("ingesta-mode-badge"); if (badge) badge.textContent = "";
  zone.innerHTML = `
    <div class="rb-upload__drop" role="button" tabindex="0" aria-label="Seleccionar archivo XLSX"
         onclick="window.igPickFile()"
         onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();window.igPickFile();}"
         ondragover="event.preventDefault();this.classList.add('is-over');"
         ondragleave="this.classList.remove('is-over');"
         ondrop="event.preventDefault();this.classList.remove('is-over');window.igSetFile(event.dataTransfer.files&&event.dataTransfer.files[0]);">
      <i class="bi bi-filetype-xlsx"></i>
      <div class="t1">Selecciona o arrastra el XLSX</div>
      <div class="t2">.xlsx · .xlsm</div>
    </div>`;
};
window.igOnFileInput = function (e) { window.igSetFile(e.target.files && e.target.files[0]); };
window.igSetFile = function (file) {
  const zone = document.getElementById("ingesta-filezone");
  const btn = document.getElementById("ingesta-upload-btn");
  if (!file || !zone) return;
  window.__ingestaFile = file;
  const ext = (String(file.name).match(/\.[^.]+$/) || [""])[0].toLowerCase();
  const extOk = ext === ".xlsx" || ext === ".xlsm";
  const fecha = extOk ? window.igParseFecha(file.name) : null;
  const valid = extOk && fecha !== null;
  const err = !extOk ? "Formato no permitido (.xlsx / .xlsm)" : "El nombre debe incluir la fecha YYYYMMDD";
  zone.innerHTML = `
    <div class="rb-chip">
      <div class="rb-chip__thumb"><i class="bi bi-filetype-xlsx"></i></div>
      <div class="rb-chip__main">
        <div class="rb-chip__name" title="${String(file.name).replace(/"/g, "&quot;")}">${window.igTruncName(file.name)}</div>
        <div class="rb-chip__val ${valid ? "" : "is-error"}" aria-live="polite">
          <i class="bi ${valid ? "bi-check-circle-fill" : "bi-exclamation-triangle-fill"}"></i>
          <span>${valid ? `Fecha ${fecha} · destino CPF` : err}</span>
        </div>
      </div>
      <button class="rb-chip__change" onclick="window.igPickFile()">Cambiar</button>
    </div>`;
  if (btn) btn.disabled = !valid;
  if (extOk) window.igReadSheetsPreview(file);          // preview del árbol (setea badge NEW/STD)
};
```

---

## 6 · Orden de ejecución

1. **Auditar** §2 (P1-P3). Si falla, DETENER.
2. Editar `static/css/ingesta.css`: tokens `--g-red`/`--g-mist` + reglas `.rb-*`/`.ig-spin` (§4).
3. Editar `static/js/chat.js`: §5.1 (bloque selector + `igRenderDropzone()`), §5.2 (reemplazar
   `onIngestaFileChange` por `igReadSheetsPreview`), §5.3 (`handleIngestaUpload`), §5.4 (helpers).
4. Sintaxis: desde `c:\APLICACIONES\ProdIA\12112025_prodIA` → `node --check static/js/chat.js`.
5. `Ctrl+F5` en `:8020` y correr Validaciones §7.

---

## 7 · Validaciones (criterios de aceptación, del doc §8)

- **V1.** Card con **barra verde**, icono `cloud-arrow-up-fill` **dorado**, "Cargar Reporte Diario",
  subtítulo mono "nombre con fecha YYYYMMDD", badge a la derecha. **Sin** el borde verde grueso anterior.
- **V2 (sin archivo).** Se ve el **dropzone** punteado verde con icono XLSX y textos; el botón CARGAR está
  **deshabilitado** (gris `#C7D3CC`).
- **V3 (drag&drop).** Arrastrar un `.xlsm` al dropzone lo selecciona (resalta al pasar por encima).
- **V4 (con archivo válido).** Aparece el **FileChip**: thumb XLSX + **nombre truncado** (`title` = nombre
  completo en hover) + "✓ Fecha dd/mm/aaaa · destino CPF" en verde + botón **Cambiar**. El badge del header
  muestra **NEW/STD** tras leer las hojas, y el **árbol** se arma debajo. Botón CARGAR **habilitado**.
- **V5 (fecha inválida).** Subir un archivo cuyo nombre **no** tenga YYYYMMDD válido (ej. `reporte.xlsm` o
  `20241340_x.xlsm`): la línea de validación sale en **rojo** con el mensaje, y CARGAR queda
  **deshabilitado**.
- **V6 (Cambiar).** El botón "Cambiar" reabre el selector de archivo y permite re-elegir **incluso el mismo
  archivo** (I-B: el `value` se resetea → el `onchange` vuelve a disparar). El badge vacío del header **no**
  se muestra hasta que hay archivo (I-A).
- **V7 (submit).** Con archivo válido, CARGAR muestra "CARGANDO…" con icono girando y dispara la ingesta
  (igual que hoy); al terminar, ResumenCard verde.
- **V8 (resto intacto).** El árbol, la tabla, el chat y los gráficos Plotly **siguen idénticos**.

---

## 8 · Reglas no negociables

1. **Solo** el selector de archivo. No tocar el árbol, la tabla, el chat, el backend, ni otras funciones de
   `chat.js`. CSS nuevo scopeado a `.rb-*`/`.ig-spin` en `ingesta.css`.
2. Sin React. Reusar los tokens `--g-*` existentes (no redefinirlos salvo los 2 nuevos `--g-red`/`--g-mist`).
3. **D1 bloqueante**, **D2 sin "25 MB"**, **D3 badge dinámico** (ver §0.b).
4. `readSheetsFromXlsm`, `ingestaSheetLi`, `renderIngestaProgress`, `renderIngestaFinal` y los helpers `ig*`
   del árbol/tabla **no se modifican**.
5. El submit usa `window.__ingestaFile` (no `input.files`); el input queda `hidden`.
6. No marcar nada como hecho sin la validación visual correspondiente.

## 9 · Fuera de alcance

- El árbol de hojas, la tabla optimizada, el chat, gráficos, login, backend, esquema o datos.
- Límite de tamaño de archivo (la app maneja ~125 MB; no se impone ni se muestra "máx 25 MB").
- Mostrar `sizeLabel` (tamaño en MB) en el chip — opcional, no en la imagen; se omite.
```
