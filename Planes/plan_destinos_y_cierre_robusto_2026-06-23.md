# Plan (executor) v4 — Destino Core por hoja + avance en vivo del `mes` + cierre determinista

> **Modo:** ejecutable por un agente externo sin contexto previo. Rutas absolutas, código completo,
> decisiones cerradas. **Requiere que los planes v2 y v3 ya estén aplicados** (endpoints `/ingesta/upload`
> y `/ingesta/upload_stream`, proxy, listado de hojas + contador en vivo). Este plan los **amplía**.
> **Versión auditada (v2)** — incorpora los hallazgos H1/H2 del flujo profesional (§0).

---

## 0. Hallazgos de auditoría incorporados (flujo profesional §0.2)

Verificados contra el código real:

- **H1 (riesgo descartado):** el proxy v4 **bloquea** la petición durante minutos; eso solo es seguro si
  el servidor Flask es multihilo. **Verificado:** Flask-SocketIO en modo `threading` arranca con
  `app.run(..., threaded=True, ...)` (`venv/Lib/site-packages/flask_socketio/__init__.py`, línea 660),
  por lo que el socket del navegador se sigue atendiendo en otros hilos mientras la subida bloquea →
  el progreso en vivo llega y el resultado vuelve por la respuesta HTTP. **Diseño válido, no se cambia.**
- **H2 (corregido):** `onIngestaFileChange` (ruta JSZip del plan v3) construía cada `<li>` sin
  `flex-wrap`; como v4 añade varios destinos por hoja (Bronze + Core + avance), se desbordaban. → §5.4(c)
  alinea su markup con `flex-wrap` (igual que el fallback `inicio`).
- **H3 (nota):** la petición bloqueada retiene un hilo + ~131 MB en memoria por subida concurrente.
  Aceptable para uso de pocos usuarios; no se aplica límite (fuera de alcance).
- **H4 (verificado):** el bloque FACTS a reemplazar está en `services.py` (indentación de 8 espacios) y
  `load_fact_mes` tiene un solo llamador → el reemplazo de §5.2 casa sin ambigüedad.

---

## 1. Contexto y problema observado

Tras el plan v3, al subir un `.xlsm` el panel izquierdo de ProdIA (Flask :8020) lista las hojas y muestra
un contador en vivo por hoja (fase **Bronze**), reenviando el progreso por SocketIO desde el SSE de
INGESTA (FastAPI :8000), que ingiere en `daily_report_prod` (PostgreSQL @ `10.100.26.139`).

Dos cosas observadas con un archivo **NEW** (`20241004`, 131 MB):
1. El contador llega a `24/24` (Bronze) pero la **fase de facts** (día/mes/programa + filiales/etc.) corre
   **varios minutos en silencio** (sin eventos), sobre todo `fact_produccion_mes_ecp` (~315k filas).
2. En ese silencio se **perdió el evento final** `fin` (emit SocketIO "disparar y olvidar") → el spinner
   quedó colgado **aunque la ingesta SÍ terminó y commiteó** (verificado en BD).

## 2. Objetivo

- **(A)** Mostrar, por hoja, **a qué tabla Core va su dato** (no solo el destino Bronze): cada hoja que
  alimenta un `fact_*` añade su destino Core + filas (conecta la lista con la tarjeta verde).
- **(B)** **Avance en vivo** durante la hoja lenta `BDP_datos_mes` (eventos por chunk).
- **(C)** **Cierre determinista**: el resultado final llega por la **respuesta HTTP** del proxy (no por un
  evento SocketIO que se pueda perder) → el spinner siempre cierra con la tarjeta verde o un error.

**Decisiones cerradas:**
- D1 — El progreso por hoja sigue por **SocketIO** (en vivo). El **resultado final** viaja por la
  **respuesta HTTP** del `fetch` (el proxy bloquea hasta terminar y devuelve el `fin`).
- D2 — Cambio al ETL **aditivo**: emits adicionales + un parámetro opcional `emit` en `load_fact_mes`.
  No se altera lógica de carga, claves, transacciones ni idempotencia.
- D3 — El contador `N/N` sigue contando **solo el paso Bronze** (uno por hoja). Los eventos Core **no**
  incrementan el contador; solo **añaden** el destino Core a la línea de la hoja.

## 3. Prerequisitos

| # | Prerequisito | Comando | Esperado |
|---|---|---|---|
| P1 | Plan v3 aplicado | `findstr /C:"upload_stream" "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\api.py"` | encuentra la línea |
| P2 | INGESTA arranca | `curl.exe http://localhost:8000/health` | `{"status":"ok"}` |
| P3 | Servidor 139 alcanzable | `Test-NetConnection 10.100.26.139 -Port 5432 -InformationLevel Quiet` | `True` |

## 4. Inventario de archivos

**Se modifican:**
- `...\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py` (emits Core por hoja + `emit` en `load_fact_mes`)
- `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py` (proxy: bloquea, reenvía progreso, devuelve el `fin`)
- `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` (await del resultado + render Core + avance)

**NO se tocan:** `api.py` de INGESTA (el SSE ya reenvía cualquier evento del `progress_cb` y el `fin` ya
lleva el resultado), `main.html`, JSZip, el DDL, el resto del ETL.

## 5. Especificación (código completo)

### 5.1 — services.py: `emit` por chunk en `load_fact_mes`

Archivo: `...\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`

**(a)** Cambiar la firma. Reemplazar:

```python
def load_fact_mes(conn, ws, reporte_id, caches):
```

por:

```python
def load_fact_mes(conn, ws, reporte_id, caches, emit=None):
```

**(b)** Emitir avance por chunk. Reemplazar:

```python
        if len(buf) >= CHUNK:
            ensure_fechas(conn, fechas); upsert_fuentes(conn, fuentes, reporte_id)
            conn.execute(MES, buf); buf.clear(); fuentes.clear(); fechas.clear()
            log.info("ingesta.mes.chunk", filas=total)
```

por:

```python
        if len(buf) >= CHUNK:
            ensure_fechas(conn, fechas); upsert_fuentes(conn, fuentes, reporte_id)
            conn.execute(MES, buf); buf.clear(); fuentes.clear(); fechas.clear()
            log.info("ingesta.mes.chunk", filas=total)
            if emit: emit({"tipo": "avance", "hoja": "BDP_datos_mes",
                           "tabla": "fact_produccion_mes_ecp", "filas": total})
```

### 5.2 — services.py: emits de destino Core en `ingerir_archivo`

Reemplazar **todo el bloque** que va desde `# ---- FACTS ECP (solo si raw) ----` hasta la última línea
`update_config_inicio(conn, wb["INICIO"], reporte_id)` (inclusive) por:

```python
        # ---- FACTS ECP (solo si raw) ----  [v4: emite el destino Core por hoja]
        if raw:
            n, sk = load_fact_dia(conn, wb["BDP_datos_dia"], reporte_id, (vice, socio, conc, tipo))
            _log_ingesta(conn, reporte_id, "BDP_datos_dia", "core.fact_produccion_dia_ecp", n+sk, n)
            filas["fact_produccion_dia_ecp"] = n
            log.info("ingesta.dia", filas=n, descartadas=sk)
            _emit({"tipo": "hoja", "hoja": "BDP_datos_dia", "estado": "ok",
                   "tabla": "fact_produccion_dia_ecp", "filas": n})

            n, sk = load_fact_mes(conn, wb["BDP_datos_mes"], reporte_id,
                                  (vice, socio, conc, tipo, esc, proc), emit=_emit)
            _log_ingesta(conn, reporte_id, "BDP_datos_mes", "core.fact_produccion_mes_ecp", n+sk, n)
            filas["fact_produccion_mes_ecp"] = n
            log.info("ingesta.mes", filas=n, descartadas=sk)
            _emit({"tipo": "hoja", "hoja": "BDP_datos_mes", "estado": "ok",
                   "tabla": "fact_produccion_mes_ecp", "filas": n})

            # pre-siembra de fuentes de programa que no estén aún (IDBDP nuevos) para no violar FK
            prg = wb["BDP_Programa"]
            it = prg.iter_rows(values_only=True); next(it, None)
            extra = {}
            for r in it:
                idb = num(r[10]) if r and len(r) > 10 else None
                if idb is not None: extra[int(idb)] = {"campo": s(r[7]), "grupo1": s(r[9]),
                                                        "gerencia": s(r[2]), "contrato": s(r[11])}
            upsert_fuentes(conn, extra, reporte_id)

            n, sk = load_fact_programa(conn, wb["BDP_Programa"], reporte_id, (vice, tipo))
            _log_ingesta(conn, reporte_id, "BDP_Programa", "core.fact_programa_ecp", n+sk, n)
            filas["fact_programa_ecp"] = n
            log.info("ingesta.programa", filas=n, descartadas=sk)
            _emit({"tipo": "hoja", "hoja": "BDP_Programa", "estado": "ok",
                   "tabla": "fact_programa_ecp", "filas": n})

        # ---- COMENTARIOS ----
        if "COMENTARIOS" in wb.sheetnames:
            n = load_comentarios(conn, wb["COMENTARIOS"], reporte_id, tipo)
            _log_ingesta(conn, reporte_id, "COMENTARIOS", "core.fact_comentarios_produccion", n, n)
            filas["fact_comentarios_produccion"] = n
            log.info("ingesta.comentarios", filas=n)
            _emit({"tipo": "hoja", "hoja": "COMENTARIOS", "estado": "ok",
                   "tabla": "fact_comentarios_produccion", "filas": n})

        # ---- FILIALES / POP / PROMEDIOS / CONFIG ----
        if "Producción filiales" in wb.sheetnames:
            n = load_filiales(conn, wb["Producción filiales"], reporte_id, emp, tipo, treg)
            _log_ingesta(conn, reporte_id, "Producción filiales", "core.fact_produccion_diaria", n, n)
            filas["fact_produccion_diaria"] = n
            log.info("ingesta.filiales", filas=n)
            _emit({"tipo": "hoja", "hoja": "Producción filiales", "estado": "ok",
                   "tabla": "fact_produccion_diaria", "filas": n})

        if "POP Filiales y Exploración" in wb.sheetnames:
            n = load_pop(conn, wb["POP Filiales y Exploración"], reporte_id, emp)
            _log_ingesta(conn, reporte_id, "POP Filiales y Exploración", "core.fact_plan_mensual", n, n)
            filas["fact_plan_mensual"] = n
            log.info("ingesta.pop", filas=n)
            _emit({"tipo": "hoja", "hoja": "POP Filiales y Exploración", "estado": "ok",
                   "tabla": "fact_plan_mensual", "filas": n})

        if "INICIO" in wb.sheetnames:
            n = load_promedios(conn, wb["INICIO"], reporte_id, emp, tipo)
            _log_ingesta(conn, reporte_id, "INICIO", "core.fact_promedio_validado", n, n)
            filas["fact_promedio_validado"] = n
            log.info("ingesta.promedios", filas=n)
            update_config_inicio(conn, wb["INICIO"], reporte_id)
            _emit({"tipo": "hoja", "hoja": "INICIO", "estado": "ok",
                   "tabla": "fact_promedio_validado", "filas": n})
```

> `_emit` ya existe (lo añadió el plan v3 al inicio de `ingerir_archivo`). Estos eventos Core reutilizan
> el mismo nombre de hoja → el frontend los **añade** a la línea ya existente de esa hoja.

### 5.3 — routes/api.py: proxy con cierre determinista

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py`

Reemplazar **toda** la función `ingesta_upload_stream` creada en el plan v3 (de `@api_bp.route("/ingesta/upload_stream"...)` hasta su `return ... 202`) por:

```python
@api_bp.route("/ingesta/upload_stream", methods=["POST"])
def ingesta_upload_stream():
    """Reenvía el archivo al SSE de INGESTA, retransmite el progreso por SocketIO y DEVUELVE el
    resultado final como respuesta HTTP (cierre determinista; el 'fin' no depende de un emit suelto)."""
    from flask import current_app
    if "file" not in request.files:
        return jsonify({"success": False, "error": "no se envió ningún archivo"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "archivo sin nombre"}), 400
    user_id = session.get("user_id") or (session.get("user", {}) or {}).get("username", "default")
    socketio = current_app.extensions["socketio"]
    files = {"file": (f.filename, f.read(), f.mimetype or "application/octet-stream")}
    final = {"success": False, "error": "sin respuesta de INGESTA"}
    try:
        with requests.post(f"{INGESTA_API_URL}/ingesta/upload_stream",
                           files=files, stream=True, timeout=1800) as resp:
            if resp.status_code != 200:
                return jsonify({"success": False,
                                "error": f"INGESTA respondió {resp.status_code}: {resp.text[:300]}"}), resp.status_code
            resp.encoding = "utf-8"   # nombres de hoja con tilde correctos (G1 del plan v3)
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if ev.get("tipo") == "fin":
                    final = {"success": ("error" not in ev), **ev}   # capturar, NO emitir
                else:
                    socketio.emit("ingesta_progress", ev, room=user_id)
    except requests.RequestException as e:
        return jsonify({"success": False, "error": f"INGESTA no disponible en {INGESTA_API_URL}: {e}"}), 502
    return jsonify(final), (200 if final.get("success") else 500)
```

> Esta ruta ahora **bloquea** hasta que la ingesta termina (minutos en archivos NEW) y devuelve el `fin`.
> El `import json`, `os`, `requests` y la constante `INGESTA_API_URL` ya existen (planes v2/v3).

### 5.4 — chat.js: await del resultado + render Core/avance

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js`

**(a)** Reemplazar **íntegramente** la función `window.handleIngestaUpload = async function ... };` por:

```javascript
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
    li.querySelectorAll(".ingesta-dest, .ingesta-avance").forEach((x) => x.remove());
  });
  const counter = document.getElementById("ingesta-counter");
  if (counter && window.__ingestaTotal) counter.textContent = `0 / ${window.__ingestaTotal}`;

  const fd = new FormData();
  fd.append("file", input.files[0]);
  if (btn) btn.disabled = true;
  status.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm"></div> Ingiriendo… (no cierres esta ventana; un archivo NEW puede tardar varios minutos)</div>';
  try {
    const r = await fetch("/api/ingesta/upload_stream", { method: "POST", body: fd });
    const data = await r.json();                 // cierre DETERMINISTA desde la respuesta HTTP
    window.renderIngestaFinal(data);
  } catch (e) {
    status.innerHTML = `<div class="alert alert-danger">Fallo de red: ${e}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
};

window.renderIngestaFinal = function renderIngestaFinal(data) {
  const status = document.getElementById("ingesta-status");
  if (!data || data.success === false) {
    status.innerHTML = `<div class="alert alert-danger">Error: ${(data && (data.error || data.detail)) || "desconocido"}</div>`;
    return;
  }
  const res = data.resultado || {};
  const filas = Object.entries(res.filas_por_tabla || {})
    .map(([k, v]) => `<li>${k}: <strong>${v}</strong></li>`).join("");
  status.innerHTML = `<div class="alert alert-success">
    ✅ <strong>${res.archivo || ""}</strong> (${res.tipo_archivo || ""}) → reporte_id <strong>${res.reporte_id}</strong>
    <ul class="mb-0 mt-2">${filas}</ul></div>`;
};
```

**(b)** Reemplazar **íntegramente** la función `window.renderIngestaProgress = function ... };` por
(añade `avance` y marca el destino Core; ya **no** maneja `fin` — eso lo hace `renderIngestaFinal`):

```javascript
window.renderIngestaProgress = function renderIngestaProgress(ev) {
  const counter = document.getElementById("ingesta-counter");
  if (!ev || !ev.tipo) return;

  // Fallback: construir la lista desde el backend si JSZip falló
  if (ev.tipo === "inicio") {
    const box = document.getElementById("ingesta-sheets");
    if (box && !document.getElementById("ingesta-sheet-list") && Array.isArray(ev.hojas)) {
      window.__ingestaTotal = ev.total || ev.hojas.length;
      window.__ingestaDone = 0;
      const items = ev.hojas.map((n) =>
        `<li data-hoja="${String(n).replace(/"/g, "&quot;")}" class="d-flex flex-wrap align-items-center gap-1 py-1">
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

  const findLi = (hoja) => {
    let li = null;
    document.querySelectorAll("#ingesta-sheet-list li").forEach((x) => { if (x.dataset.hoja === hoja) li = x; });
    return li;
  };

  // Avance intra-hoja (ej. BDP_datos_mes por chunk)
  if (ev.tipo === "avance") {
    const li = findLi(ev.hoja); if (!li) return;
    let prog = li.querySelector(".ingesta-avance");
    if (!prog) { prog = document.createElement("span"); prog.className = "ingesta-avance text-primary ms-1"; li.appendChild(prog); }
    prog.textContent = `… ${Number(ev.filas).toLocaleString()} filas`;
    return;
  }

  if (ev.tipo === "hoja" && ev.estado === "ok") {
    const li = findLi(ev.hoja); if (!li) return;
    const ic = li.querySelector(".ingesta-ic"); if (ic) ic.textContent = "✅";
    const esCore = String(ev.tabla || "").startsWith("fact_");
    if (!esCore && !li.dataset.contado) {              // el contador cuenta SOLO el paso Bronze
      li.dataset.contado = "1";
      window.__ingestaDone = (window.__ingestaDone || 0) + 1;
      if (counter && window.__ingestaTotal) counter.textContent = `${window.__ingestaDone} / ${window.__ingestaTotal}`;
    }
    if (typeof ev.filas === "number") {
      if (esCore) { const p = li.querySelector(".ingesta-avance"); if (p) p.remove(); }
      const span = document.createElement("span");
      span.className = "ingesta-dest ms-1 " + (esCore ? "text-success fw-semibold" : "text-muted");
      span.textContent = `(${ev.filas} → ${ev.tabla || ""})`;
      li.appendChild(span);
    }
  }
};
```

**(c)** [H2] En la función existente `onIngestaFileChange` (creada en el plan v3), para que cada hoja
admita varios destinos sin desbordarse, reemplazar el `class` del `<li>` que arma la lista:

```javascript
        `<li data-hoja="${n.replace(/"/g, "&quot;")}" class="d-flex align-items-center gap-2 py-1">
```

por:

```javascript
        `<li data-hoja="${n.replace(/"/g, "&quot;")}" class="d-flex flex-wrap align-items-center gap-1 py-1">
```

## 6. Orden de ejecución

1. Editar `services.py` (§5.1 a/b y §5.2).
2. Editar `routes\api.py` (§5.3).
3. Editar `static\js\chat.js` (§5.4 a/b/c).
4. (Re)arrancar **INGESTA** (Terminal 1): `cd "...\INGESTA\Rep_Prod\backend"; uv run uvicorn app.main:app --port 8000`
5. (Re)arrancar **ProdIA** (Terminal 2): `cd "c:\APLICACIONES\ProdIA\12112025_prodIA"; .\venv\Scripts\python.exe app.py`
6. Validaciones (§7). En el navegador, **Ctrl+F5**.

## 7. Validaciones (criterios de aceptación)

| # | Validación | Comando / acción | Esperado |
|---|---|---|---|
| X1 | Emits Core en el ETL | `findstr /C:"fact_produccion_diaria" /C:"fact_promedio_validado" "...\services.py"` | aparecen en líneas `_emit(...)` |
| X2 | `load_fact_mes` con `emit` | `findstr /C:"def load_fact_mes(conn, ws, reporte_id, caches, emit=None)" "...\services.py"` | encuentra la línea |
| X3 | SSE emite destinos Core | comando X3 abajo (STD) | eventos con `"tabla":"fact_..."` (p.ej. `fact_produccion_diaria`, `fact_plan_mensual`, `fact_promedio_validado`, `fact_comentarios_produccion`) + un `fin` con `resultado` |
| X4 | Proxy devuelve el resultado (cierre determinista) | comando X4 abajo (STD) | **HTTP 200** + `{"success": true, "tipo":"fin", "resultado": {... "reporte_id": .., "filas_por_tabla": {...}}}` |
| X5 | UI: destino Core por hoja | navegador → cargar muestra STD | `Producción filiales` muestra **dos** destinos: `(… → bronze.hoja_landing)` y `(… → fact_produccion_diaria)` en verde |
| X6 | UI: avance + cierre con NEW | cargar `20241004_Reporte New...xlsm` | `BDP_datos_mes` muestra `… N filas` subiendo; al final **tarjeta verde** (sin spinner colgado) con los facts ECP |

**X3** (SSE directo; STD tiene 4 destinos Core: filiales, POP, promedios, comentarios):
```powershell
curl.exe -N -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8000/ingesta/upload_stream
```

**X4** (proxy de ProdIA; ahora BLOQUEA hasta terminar y devuelve el `fin`):
```powershell
curl.exe -i -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8020/api/ingesta/upload_stream
```

## 8. Reglas no negociables

1. Cambios al ETL **solo** los de §5.1/§5.2 (emits + parámetro `emit`); NO alterar lógica de carga,
   claves naturales, transacciones ni idempotencia.
2. El contador `N/N` cuenta **solo** los eventos Bronze (uno por hoja); los eventos Core (`tabla` que
   empieza por `fact_`) **no** incrementan, solo **añaden** el destino a la línea.
3. El resultado final se renderiza desde la **respuesta HTTP** del `fetch` (`renderIngestaFinal`), NO
   desde un evento `fin` por SocketIO. El proxy **captura** el `fin` y **no** lo reemite.
4. Mantener `resp.encoding="utf-8"` y `charset=utf-8` (no regresar el bug de tildes del plan v3).
5. No renombrar eventos (`ingesta_progress`), tipos (`hoja`/`avance`/`inicio`/`fin`), rutas ni IDs del DOM.
6. No tocar `api.py` de INGESTA: el SSE ya reenvía cualquier evento del `progress_cb` y el `fin` ya lleva
   el `resultado`.

> **Nota (H1):** el diseño bloqueante depende de que el servidor sea multihilo. **Verificado:** Flask-SocketIO
> en modo `threading` corre `app.run(threaded=True)`, así que el progreso por SocketIO se entrega mientras la
> subida bloquea. NO arrancar ProdIA con otro servidor (eventlet/gevent) sin re-evaluar este diseño.
> **Nota (H3):** cada subida en curso retiene un hilo + el archivo en memoria; con archivos NEW (~131 MB) y
> pocos usuarios es aceptable. Para alta concurrencia haría falta una cola/worker (fuera de alcance).

## 9. Fuera de alcance

- Cambiar `bronze.hoja_landing` para que cuente filas en vez de hojas (queda como está).
- Avance intra-hoja para `dia`/`programa` (son rápidas; solo `mes` lleva avance).
- Cancelar una ingesta en curso; multiusuario concurrente sobre el mismo archivo.
- Barra de porcentaje (se muestra conteo de filas, no %).
