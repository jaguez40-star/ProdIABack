# Plan (executor) v3 — Listado de hojas al seleccionar (A) + contador de ingesta EN VIVO por hoja (B1)

> **Modo:** ejecutable por un agente externo sin contexto previo. Rutas absolutas, código completo,
> decisiones cerradas. **Requiere que el plan v2** (`plan_upload_excel_prodia_ingesta_2026-06-23.md`)
> ya esté aplicado y funcionando (endpoint `/ingesta/upload`, proxy, UI base). Este plan lo **amplía**.
> **Versión auditada (v2)** — incorpora los hallazgos G1/G4 del flujo profesional (§0).

---

## 0. Hallazgos de auditoría incorporados (flujo profesional §0.2)

Verificados contra el código real:

- **G1 (bug, corregido):** el SSE debe declarar **UTF-8**. Sin charset, `requests` decodifica latin-1 y
  los nombres de hoja con tilde (`Producción filiales`, `POP Filiales y Exploración`, `REPORTE DE
  PRODUCCIÓN`, `NEW MES-AÑO`…) llegan mojibake y **no casan** con `data-hoja` → no se marcan. → FastAPI
  emite `media_type="text/event-stream; charset=utf-8"` y el proxy Flask fija `resp.encoding="utf-8"`.
- **G4 (mejora):** el frontend maneja el evento **`inicio`** como *fallback* para construir la lista de
  hojas si JSZip falló (archivos muy grandes / límites del navegador).
- **G2 (verificado OK):** `room=user_id` es coherente — `auth.py` setea `session["user_id"]` al login y
  tanto `connect` como la ruta nueva leen la misma clave.
- **G3 (verificado OK):** el hook gzip de `app.py` retorna antes de tocar el cuerpo si no es
  `application/json`; el SSE (`text/event-stream`) no se ve afectado.
- **G6 (verificar en vivo):** la emisión SocketIO desde background-task con `async_mode="threading"` es
  soportada; se confirma en la validación W6. Fallback si fallara: ver §8 nota.

---

## 1. Contexto

Tras el plan v2, ProdIA (Flask :8020) tiene una vista "Análisis avanzado de producción diaria" con un
panel de carga que sube un `.xlsm` a INGESTA (FastAPI :8000), que lo ingiere en `daily_report_prod`
(PostgreSQL @ `10.100.26.139`). La ingesta v2 es **síncrona** y devuelve todo al final.

Este plan añade:
- **(A)** Al seleccionar el archivo, listar **debajo** las hojas del Excel (en el navegador, sin subirlo).
- **(B1)** Un **contador en vivo por hoja**: a medida que la ingesta procesa cada hoja, se marca ✅ y se
  actualiza un contador `X / N`.

**Hechos verificados del entorno (no reabrir):**
- ProdIA SocketIO usa `async_mode="threading"` (no eventlet) → background threads y streaming son seguros.
- En `connect`, el servidor hace `join_room(session["user_id"])` (`app.py:137`). El navegador ya está en
  ese room. → el progreso se emite con `room=user_id`.
- La instancia de SocketIO está en `current_app.extensions["socketio"]` (Flask-SocketIO la registra ahí).
- `chat.js` crea el socket en `this.socket = io(...)` y registra listeners con `this.socket.on(...)`.
- Los `<script>` se incluyen en `templates/main.html` (chat.js en la línea 73).

## 2. Arquitectura (decisión cerrada)

```
(A)  navegador → JSZip lee xl/workbook.xml del archivo → lista de hojas (instantáneo, sin subir)

(B1) navegador → POST /api/ingesta/upload_stream (Flask)         [responde 202 al instante]
        Flask: socketio.start_background_task(...)
            → POST archivo a FastAPI /ingesta/upload_stream (SSE, stream=True)
            → por cada evento SSE: socketio.emit("ingesta_progress", ev, room=user_id)
     navegador (ya conectado por SocketIO) escucha "ingesta_progress" → marca cada hoja y el contador
     FastAPI /ingesta/upload_stream:
        ingerir_archivo(path, progress_cb=...) en un HILO + cola → yield SSE por hoja + evento "fin"
```

**Decisiones:**
- D1 — progreso al navegador por **SocketIO** (reusa el room existente); SSE solo **Flask↔FastAPI**.
- D2 — **único cambio al ETL:** parámetro **opcional** `progress_cb` en `ingerir_archivo` (default `None`
  = comportamiento idéntico al actual). NO cambia transacciones ni idempotencia.
- D3 — se **añaden** endpoints `_stream`; los endpoints v2 (`/ingesta/upload`, `/api/ingesta/upload`) se
  conservan intactos (las validaciones V2/V3 del plan v2 siguen pasando).
- D4 — JSZip vendorizado localmente (sin CDN en runtime).

## 3. Prerequisitos

| # | Prerequisito | Comando | Esperado |
|---|---|---|---|
| P1 | Plan v2 aplicado | `findstr /C:"def upload_archivo" "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\api.py"` | encuentra la línea |
| P2 | INGESTA arranca | `curl.exe http://localhost:8000/health` | `{"status":"ok"}` |
| P3 | Internet (para bajar JSZip) | — | acceso a cdnjs |

## 4. Inventario de archivos

**Se crean:** `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\vendor\jszip-3.10.1.min.js`

**Se modifican:**
- `...\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py` (callback `progress_cb`, aditivo)
- `...\INGESTA\Rep_Prod\backend\app\features\ingesta\api.py` (endpoint `/ingesta/upload_stream`)
- `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py` (ruta `/ingesta/upload_stream` + SocketIO)
- `c:\APLICACIONES\ProdIA\12112025_prodIA\templates\main.html` (incluir JSZip antes de chat.js)
- `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` (Feature A + listener + render)

## 5. Especificación (código completo)

### 5.1 — Vendorizar JSZip

```powershell
curl.exe -L -o "c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\vendor\jszip-3.10.1.min.js" https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js
```

### 5.2 — ETL: callback de progreso (services.py)

Archivo: `...\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`

**(a)** Cambiar la firma y añadir el helper `_emit` + evento "inicio". Reemplazar:

```python
def ingerir_archivo(path: Path) -> ResultadoIngesta:
    """Ingesta completa de un .xlsm (NEW o STD). Devuelve ResultadoIngesta con filas_por_tabla."""
    wb = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    raw = tiene_raw(set(wb.sheetnames))
    filas: dict[str, int] = {}
```

por:

```python
def ingerir_archivo(path: Path, progress_cb=None) -> ResultadoIngesta:
    """Ingesta completa de un .xlsm (NEW o STD). Devuelve ResultadoIngesta con filas_por_tabla.
    Si progress_cb se provee, se invoca por hoja con dicts {"tipo":"hoja","hoja":..,"estado":..,..}."""
    def _emit(ev):
        if progress_cb:
            try: progress_cb(ev)
            except Exception: pass
    wb = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    raw = tiene_raw(set(wb.sheetnames))
    filas: dict[str, int] = {}
    _emit({"tipo": "inicio", "archivo": path.name, "hojas": list(wb.sheetnames),
           "total": len(wb.sheetnames), "tipo_archivo": "NEW" if raw else "STD"})
```

**(b)** En el bucle Bronze tipado (raw), reemplazar:

```python
        if raw:
            for sheet, table, cols in [("BDP_datos_dia", "bdp_datos_dia", BZ_DIA),
                                       ("BDP_datos_mes", "bdp_datos_mes", BZ_MES),
                                       ("BDP_Programa",  "bdp_programa",  BZ_PRG)]:
                n = land_bronze_typed(conn, wb[sheet], table, cols, reporte_id)
                _log_ingesta(conn, reporte_id, sheet, f"bronze.{table}", n, n)
                filas[f"bronze.{table}"] = n
                log.info("ingesta.bronze", tabla=table, filas=n)
```

por:

```python
        if raw:
            for sheet, table, cols in [("BDP_datos_dia", "bdp_datos_dia", BZ_DIA),
                                       ("BDP_datos_mes", "bdp_datos_mes", BZ_MES),
                                       ("BDP_Programa",  "bdp_programa",  BZ_PRG)]:
                _emit({"tipo": "hoja", "hoja": sheet, "estado": "procesando"})
                n = land_bronze_typed(conn, wb[sheet], table, cols, reporte_id)
                _log_ingesta(conn, reporte_id, sheet, f"bronze.{table}", n, n)
                filas[f"bronze.{table}"] = n
                log.info("ingesta.bronze", tabla=table, filas=n)
                _emit({"tipo": "hoja", "hoja": sheet, "estado": "ok",
                       "tabla": f"bronze.{table}", "filas": n})
```

**(c)** En el bucle Bronze landing, reemplazar:

```python
        hojas_landing = 0
        for sheet in wb.sheetnames:
            if sheet in RAW_SHEETS: continue
            n = land_landing(conn, wb[sheet], sheet, reporte_id)
            _log_ingesta(conn, reporte_id, sheet, "bronze.hoja_landing", n, n)
            hojas_landing += 1
        filas["bronze.hoja_landing"] = hojas_landing
        log.info("ingesta.landing", hojas=hojas_landing)
```

por:

```python
        hojas_landing = 0
        for sheet in wb.sheetnames:
            if sheet in RAW_SHEETS: continue
            _emit({"tipo": "hoja", "hoja": sheet, "estado": "procesando"})
            n = land_landing(conn, wb[sheet], sheet, reporte_id)
            _log_ingesta(conn, reporte_id, sheet, "bronze.hoja_landing", n, n)
            hojas_landing += 1
            _emit({"tipo": "hoja", "hoja": sheet, "estado": "ok",
                   "tabla": "bronze.hoja_landing", "filas": n})
        filas["bronze.hoja_landing"] = hojas_landing
        log.info("ingesta.landing", hojas=hojas_landing)
```

> Cada hoja del archivo se emite **exactamente una vez** (raw en el bucle (b), el resto en (c)). El
> contador del frontend casa por **nombre** de hoja. No se modifica nada más del ETL.

### 5.3 — Endpoint SSE en INGESTA (api.py)

Archivo: `...\INGESTA\Rep_Prod\backend\app\features\ingesta\api.py`

**(a)** Añadir imports junto a los existentes:

```python
import json, queue, threading
from fastapi.responses import StreamingResponse
```

**(b)** Añadir al final del archivo (reusa `UPLOAD_SUBDIR` y `_FECHA_RE` definidos por el plan v2):

```python
@router.post("/upload_stream")
def upload_stream(file: UploadFile = File(...)):
    """Como /upload pero emite el progreso por hoja vía SSE (text/event-stream)."""
    nombre = Path(file.filename or "").name
    if not nombre.lower().endswith((".xlsm", ".xlsx")):
        raise HTTPException(400, "solo se aceptan archivos .xlsm o .xlsx")
    if not _FECHA_RE.search(nombre):
        raise HTTPException(422, "el nombre del archivo debe contener la fecha en formato YYYYMMDD")
    destino_dir = Path(get_settings().data_dir) / UPLOAD_SUBDIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nombre
    try:
        with destino.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    q: "queue.Queue" = queue.Queue()
    _SENT = object()
    box: dict = {}

    def _cb(ev):
        q.put(ev)

    def _worker():
        try:
            res = services.ingerir_archivo(destino, progress_cb=_cb)
            box["resultado"] = res.model_dump()
        except Exception as e:
            box["error"] = str(e)
        finally:
            q.put(_SENT)

    def _sse():
        threading.Thread(target=_worker, daemon=True).start()
        while True:
            ev = q.get()
            if ev is _SENT:
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        fin = {"tipo": "fin"}
        fin.update({"resultado": box["resultado"]} if "resultado" in box
                   else {"error": box.get("error", "desconocido")})
        yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"

    return StreamingResponse(_sse(), media_type="text/event-stream; charset=utf-8")
```

### 5.4 — Ruta reenviadora en ProdIA (routes/api.py)

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py`

**(a)** Asegurar `import json` cerca de los imports del inicio (si no está; `os` y `requests` ya están
por el plan v2).

**(b)** Añadir la ruta (después de `api_bp` y de la constante `INGESTA_API_URL` del plan v2):

```python
@api_bp.route("/ingesta/upload_stream", methods=["POST"])
def ingesta_upload_stream():
    """Recibe el archivo, lo reenvía al SSE de INGESTA y retransmite el progreso por SocketIO."""
    from flask import current_app
    if "file" not in request.files:
        return jsonify({"success": False, "error": "no se envió ningún archivo"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "archivo sin nombre"}), 400
    user_id = session.get("user_id") or (session.get("user", {}) or {}).get("username", "default")
    data = f.read()
    filename = f.filename
    mimetype = f.mimetype or "application/octet-stream"
    socketio = current_app.extensions["socketio"]

    def _task(sio, room, blob, fname, mtype):
        try:
            with requests.post(
                f"{INGESTA_API_URL}/ingesta/upload_stream",
                files={"file": (fname, blob, mtype)},
                stream=True, timeout=1800,
            ) as resp:
                if resp.status_code != 200:
                    sio.emit("ingesta_progress",
                             {"tipo": "fin", "error": f"INGESTA respondió {resp.status_code}: {resp.text[:300]}"},
                             room=room)
                    return
                resp.encoding = "utf-8"   # G1: nombres de hoja con tilde llegan correctos
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    sio.emit("ingesta_progress", ev, room=room)
        except requests.RequestException as e:
            sio.emit("ingesta_progress",
                     {"tipo": "fin", "error": f"INGESTA no disponible en {INGESTA_API_URL}: {e}"},
                     room=room)

    socketio.start_background_task(_task, socketio, user_id, data, filename, mimetype)
    return jsonify({"success": True, "started": True}), 202
```

### 5.5 — Incluir JSZip en el template (main.html)

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\templates\main.html`

Insertar, **antes** del comentario `<!-- Report modules (must load before chat.js) -->` (línea ~65):

```html
<!-- JSZip: lectura de hojas del .xlsm en el navegador -->
<script src="{{ url_for('static', filename='js/vendor/jszip-3.10.1.min.js') }}"></script>
```

### 5.6 — Frontend (chat.js): Feature A + listener + render

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js`

Reemplazar **íntegramente** el bloque `window.startAdvancedDailyAnalysis = function ... };` **y** el
bloque `window.handleIngestaUpload = async function ... };` (ambos creados en el plan v2) por el
siguiente conjunto de funciones:

```javascript
window.startAdvancedDailyAnalysis = function startAdvancedDailyAnalysis() {
  const chatMessages = document.getElementById("chat-messages");
  const welcomeSection = document.querySelector(".chat-welcome-section");
  const chatBanner = document.querySelector(".chat-banner");
  if (welcomeSection) welcomeSection.style.display = "none";
  if (chatBanner) chatBanner.style.display = "none";
  const chatInputAdv = document.querySelector(".chat-input-container");
  if (chatInputAdv) chatInputAdv.style.display = "none";

  if (chatMessages) {
    chatMessages.style.display = "block";
    chatMessages.classList.remove("empty-chat");
    chatMessages.classList.add("has-content");
    chatMessages.innerHTML = `
      <div style="padding:1rem;">
        <h6 style="font-weight:700; color:#0b6e4f;">Cargar Reporte Diario de Producción</h6>
        <p class="text-muted" style="font-size:.85rem;">El archivo se enviará a la ingesta y se cargará en la base de datos. El nombre debe incluir la fecha (YYYYMMDD).</p>
        <label class="form-label" style="font-weight:600;">Archivo XLSX</label>
        <input type="file" id="ingesta-file" class="form-control" accept=".xlsm,.xlsx" onchange="onIngestaFileChange(event)">
        <div class="mt-2"><span class="badge bg-secondary">CPF</span></div>
        <button id="ingesta-upload-btn" class="btn btn-success mt-3 w-100" onclick="handleIngestaUpload()">Cargar e ingerir</button>
        <div id="ingesta-sheets" class="mt-3"></div>
        <div id="ingesta-status" class="mt-3"></div>
      </div>`;
  }

  const panelTitleAdv = document.getElementById("analytics-panel-title");
  if (panelTitleAdv) panelTitleAdv.textContent = "Análisis avanzado de producción diaria";
  const emptyState = document.getElementById("analytics-empty-state");
  const chartsArea = document.getElementById("charts-display-area");
  if (emptyState) emptyState.style.display = "none";
  if (chartsArea) { chartsArea.style.display = "block"; chartsArea.innerHTML = ""; }

  if (window.ChatManager && window.ChatManager.socket && !window.__ingestaListenerSet) {
    window.__ingestaListenerSet = true;
    window.ChatManager.socket.on("ingesta_progress", (ev) => window.renderIngestaProgress(ev));
  }
};

window.onIngestaFileChange = async function onIngestaFileChange(e) {
  const sheetsBox = document.getElementById("ingesta-sheets");
  const status = document.getElementById("ingesta-status");
  if (status) status.innerHTML = "";
  const file = e.target.files && e.target.files[0];
  if (!file || !sheetsBox) return;
  sheetsBox.innerHTML = '<div class="text-muted small"><div class="spinner-border spinner-border-sm"></div> Leyendo hojas…</div>';
  try {
    const names = await window.readSheetsFromXlsm(file);
    window.__ingestaTotal = names.length;
    window.__ingestaDone = 0;
    const RAW = ["BDP_datos_dia", "BDP_datos_mes", "BDP_Programa"];
    const esNew = RAW.every((r) => names.includes(r));
    const items = names.map((n) =>
      `<li data-hoja="${n.replace(/"/g, "&quot;")}" class="d-flex align-items-center gap-2 py-1">
         <span class="ingesta-ic">⏳</span><span>${n}</span></li>`).join("");
    sheetsBox.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <strong>Hojas del archivo (${names.length}) — ${esNew ? "NEW" : "STD"}</strong>
        <span class="badge bg-primary" id="ingesta-counter">0 / ${names.length}</span>
      </div>
      <ul id="ingesta-sheet-list" class="list-unstyled small mt-2 mb-0">${items}</ul>`;
  } catch (err) {
    sheetsBox.innerHTML = `<div class="alert alert-warning py-2">No se pudieron leer las hojas: ${err}</div>`;
  }
};

window.readSheetsFromXlsm = async function readSheetsFromXlsm(file) {
  const buf = await file.arrayBuffer();
  const zip = await JSZip.loadAsync(buf);
  const entry = zip.file("xl/workbook.xml");
  if (!entry) throw new Error("no es un .xlsx/.xlsm válido");
  const xml = await entry.async("string");
  const decode = (s) => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  return [...xml.matchAll(/<sheet[^>]*\bname="([^"]+)"/g)].map((m) => decode(m[1]));
};

window.handleIngestaUpload = async function handleIngestaUpload() {
  const input = document.getElementById("ingesta-file");
  const status = document.getElementById("ingesta-status");
  const btn = document.getElementById("ingesta-upload-btn");
  if (!input || !input.files.length) {
    if (status) status.innerHTML = '<div class="alert alert-warning py-2">Selecciona un archivo primero.</div>';
    return;
  }
  window.__ingestaDone = 0;
  document.querySelectorAll("#ingesta-sheet-list li").forEach((li) => {
    const ic = li.querySelector(".ingesta-ic"); if (ic) ic.textContent = "⏳";
    delete li.dataset.contado;
  });
  const counter = document.getElementById("ingesta-counter");
  if (counter && window.__ingestaTotal) counter.textContent = `0 / ${window.__ingestaTotal}`;

  const fd = new FormData();
  fd.append("file", input.files[0]);
  if (btn) btn.disabled = true;
  status.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm"></div> Ingiriendo…</div>';
  try {
    const r = await fetch("/api/ingesta/upload_stream", { method: "POST", body: fd });
    if (r.status !== 202) {
      const d = await r.json().catch(() => ({}));
      status.innerHTML = `<div class="alert alert-danger">Error al iniciar: ${d.error || r.status}</div>`;
      if (btn) btn.disabled = false;
    }
    // El progreso por hoja y el resultado final llegan por SocketIO (renderIngestaProgress).
  } catch (e) {
    status.innerHTML = `<div class="alert alert-danger">Fallo de red: ${e}</div>`;
    if (btn) btn.disabled = false;
  }
};

window.renderIngestaProgress = function renderIngestaProgress(ev) {
  const status = document.getElementById("ingesta-status");
  const btn = document.getElementById("ingesta-upload-btn");
  const counter = document.getElementById("ingesta-counter");
  if (!ev || !ev.tipo) return;

  // G4: si la lista no se pintó (JSZip falló), construirla desde el evento "inicio" del backend
  if (ev.tipo === "inicio") {
    const box = document.getElementById("ingesta-sheets");
    if (box && !document.getElementById("ingesta-sheet-list") && Array.isArray(ev.hojas)) {
      window.__ingestaTotal = ev.total || ev.hojas.length;
      window.__ingestaDone = 0;
      const items = ev.hojas.map((n) =>
        `<li data-hoja="${String(n).replace(/"/g, "&quot;")}" class="d-flex align-items-center gap-2 py-1">
           <span class="ingesta-ic">⏳</span><span>${n}</span></li>`).join("");
      box.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
          <strong>Hojas del archivo (${window.__ingestaTotal}) — ${ev.tipo_archivo || ""}</strong>
          <span class="badge bg-primary" id="ingesta-counter">0 / ${window.__ingestaTotal}</span>
        </div>
        <ul id="ingesta-sheet-list" class="list-unstyled small mt-2 mb-0">${items}</ul>`;
    }
    return;
  }

  if (ev.tipo === "hoja") {
    let li = null;
    document.querySelectorAll("#ingesta-sheet-list li").forEach((x) => {
      if (x.dataset.hoja === ev.hoja) li = x;
    });
    if (!li) return;
    const ic = li.querySelector(".ingesta-ic");
    if (ev.estado === "ok") {
      if (ic) ic.textContent = "✅";
      if (!li.dataset.contado) {
        li.dataset.contado = "1";
        window.__ingestaDone = (window.__ingestaDone || 0) + 1;
        if (counter && window.__ingestaTotal)
          counter.textContent = `${window.__ingestaDone} / ${window.__ingestaTotal}`;
      }
      if (typeof ev.filas === "number") {
        const extra = document.createElement("span");
        extra.className = "text-muted ms-1";
        extra.textContent = `(${ev.filas} → ${ev.tabla || ""})`;
        li.appendChild(extra);
      }
    }
  } else if (ev.tipo === "fin") {
    if (btn) btn.disabled = false;
    if (ev.error) {
      status.innerHTML = `<div class="alert alert-danger">Error: ${ev.error}</div>`;
      return;
    }
    const res = ev.resultado || {};
    const filas = Object.entries(res.filas_por_tabla || {})
      .map(([k, v]) => `<li>${k}: <strong>${v}</strong></li>`).join("");
    status.innerHTML = `<div class="alert alert-success">
      ✅ <strong>${res.archivo || ""}</strong> (${res.tipo_archivo || ""}) → reporte_id <strong>${res.reporte_id}</strong>
      <ul class="mb-0 mt-2">${filas}</ul></div>`;
  }
};
```

## 6. Orden de ejecución

1. Vendorizar JSZip (§5.1).
2. Editar `services.py` (§5.2 a/b/c).
3. Editar `api.py` de INGESTA (§5.3).
4. Editar `routes\api.py` de ProdIA (§5.4).
5. Editar `main.html` (§5.5).
6. Editar `chat.js` (§5.6).
7. (Re)arrancar **INGESTA** (Terminal 1): `cd "...\INGESTA\Rep_Prod\backend"; uv run uvicorn app.main:app --port 8000`
8. (Re)arrancar **ProdIA** (Terminal 2): `cd "c:\APLICACIONES\ProdIA\12112025_prodIA"; .\venv\Scripts\python.exe app.py`
9. Validaciones (§7). En el navegador, **Ctrl+F5** para recargar el JS nuevo.

## 7. Validaciones (criterios de aceptación)

| # | Validación | Comando / acción | Esperado |
|---|---|---|---|
| W1 | JSZip vendorizado | `dir "c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\vendor\jszip-3.10.1.min.js"` | archivo > 80 KB |
| W2 | `ingerir_archivo` acepta `progress_cb` | comando W2 abajo | `True` |
| W3 | SSE de INGESTA emite por hoja | comando W3 abajo | varias líneas `data: {"tipo":"hoja"...}` y una `data: {"tipo":"fin"...}` |
| W4 | Proxy ProdIA inicia el job | comando W4 abajo | `HTTP/1.1 202` + `{"success": true, "started": true}` |
| W5 | UI: hojas al seleccionar | navegador → vista → elegir archivo de muestra | aparece "Hojas del archivo (N) — STD/NEW" con la lista y `0 / N` |
| W6 | UI: contador en vivo | pulsar "Cargar e ingerir" | las hojas pasan a ✅ una a una, el contador sube `…/N` hasta `N/N`, y al final alert verde con `reporte_id`. **Verificar explícitamente que una hoja con tilde** (ej. `Producción filiales`) **también se marca ✅** (prueba del fix G1) |

**W2** (firma del ETL):
```powershell
cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
uv run python -c "import inspect; from app.features.ingesta.services import ingerir_archivo; print('progress_cb' in inspect.signature(ingerir_archivo).parameters)"
```

**W3** (stream SSE directo; `-N` = sin buffer):
```powershell
curl.exe -N -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8000/ingesta/upload_stream
```

**W4** (proxy; debe responder 202 inmediato — el progreso va por SocketIO, no en esta respuesta):
```powershell
curl.exe -i -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8020/api/ingesta/upload_stream
```

## 8. Reglas no negociables

1. El cambio al ETL es **solo** el parámetro opcional `progress_cb` y las llamadas `_emit`. NO alterar la
   lógica de carga, claves naturales, transacciones ni idempotencia.
2. **No** eliminar los endpoints v2 (`/ingesta/upload`, `/api/ingesta/upload`): se conservan.
3. El progreso al navegador va por **SocketIO** (`room=user_id`); el SSE es solo Flask↔FastAPI.
4. JSZip se sirve **local** (`static/js/vendor/`), no por CDN en runtime.
5. No renombrar eventos (`ingesta_progress`), rutas (`/ingesta/upload_stream`, `/api/ingesta/upload_stream`)
   ni IDs del DOM (`ingesta-file`, `ingesta-sheets`, `ingesta-sheet-list`, `ingesta-counter`,
   `ingesta-status`, `ingesta-upload-btn`).
6. El contador casa hojas **por nombre** (`data-hoja`); no cambiar a índices.
7. **UTF-8 obligatorio** en el SSE: `charset=utf-8` en FastAPI y `resp.encoding="utf-8"` en el proxy (G1).
   No omitir, o las hojas con tilde no se marcarán.

> **Nota fallback (G6):** si en W6 el navegador **no** recibe los eventos `ingesta_progress` (emisión
> SocketIO desde background-task no entregada por el servidor dev en modo `threading`), la solución es
> arrancar SocketIO con un *message queue* (p. ej. Redis) **o** devolver el SSE directamente al navegador
> desde Flask (`Response(stream_with_context(gen), mimetype="text/event-stream; charset=utf-8")`) y leerlo
> con `fetch`+`ReadableStream`. No aplicar salvo que W6 falle.

## 9. Fuera de alcance

- Barra de progreso por filas dentro de cada hoja (solo por hoja).
- Persistir/mostrar histórico de cargas.
- Cancelar una ingesta en curso.
- Multiusuario concurrente sobre el mismo archivo.
- Reintentos automáticos / colas.
