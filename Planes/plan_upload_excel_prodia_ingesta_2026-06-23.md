# Plan (executor) — Carga manual de Excel desde ProdIA → ingesta vía FastAPI INGESTA → `daily_report_prod`

> **Modo:** ejecutable por un agente externo sin contexto previo. Rutas absolutas, código completo,
> decisiones cerradas. Sigue el orden de ejecución y valida cada paso con su criterio de aceptación.
> **Versión auditada (v2)** — incorpora los hallazgos F1–F7 del flujo profesional (§0).

---

## 0. Hallazgos de auditoría incorporados (flujo profesional §0.2)

Verificados contra el código real antes de escribir este plan:

- **F1 (crítico):** `core.config_reporte.fecha_reporte` es `DATE NOT NULL UNIQUE` (DDL línea 145) y
  `get_reporte()` deriva la fecha del nombre con `re.search(r"(\d{8})", path.name)` → si el nombre **no**
  trae `YYYYMMDD`, intenta insertar `NULL` y **viola NOT NULL**. → El endpoint **valida `\d{8}` y rechaza
  con 422** antes de ingerir.
- **F2:** `data_dir` = `INGESTA\Rep_Prod\data` (misma carpeta del corpus). → Los subidos se guardan en
  **`data\uploads\`** para no sobrescribir corpus/muestras.
- **F3:** la ingesta se envuelve en `try/except` → error **500 con mensaje legible**.
- **F4:** `Path` ya está importado en `api.py`; solo se añaden `re, shutil` y `UploadFile, File`.
- **F5:** verificaciones usan **`$env:PGPASSWORD`** + el python de `.venv` de INGESTA (evita el `>` de la
  clave en PowerShell y garantiza `psycopg`).
- **F6:** dependencia con **`uv add python-multipart`** (persiste en `pyproject`).
- **F7:** `routes\api.py` **no** importa `os` → se añade.

**No se modifica** el pipeline ETL (`services.py`, `detector.py`, `transforms.py`, `shared/utils.py`),
el DDL, ni las decisiones D1–D3.

---

## 1. Contexto

Dos aplicaciones en el mismo equipo Windows, bajo `c:\APLICACIONES\ProdIA\12112025_prodIA\`:

- **ProdIA** (raíz): **Flask + SocketIO** (puerto **8020**), front server-side (Jinja2 + JS vanilla). Se
  arranca con `python app.py` desde su `venv`. API montada con `url_prefix="/api"` (`app.py:81`).
- **INGESTA** (`INGESTA\Rep_Prod\`): **FastAPI** (puerto **8000**) con el ETL ya construido que lee un
  `.xlsm` de *Reporte Diario de Producción* y lo escribe en PostgreSQL (`bronze`/`core`). Se arranca con
  `uv run uvicorn app.main:app --port 8000` desde `INGESTA\Rep_Prod\backend`.

BD destino: **`daily_report_prod`** en **PostgreSQL 18.4 @ `10.100.26.139:5432`** (usuario `postgres`).
DDL ya cargado (4 tablas `bronze` + 21 `core` + 7 vistas).

La API de ingesta hoy **solo ingiere archivos ya presentes en `data/`**; **no** hay endpoint de subida.

## 2. Objetivo

Desde el **panel izquierdo de la vista "Análisis avanzado de producción diaria"** de ProdIA, el usuario
**selecciona manualmente** un Excel y lo carga. ProdIA **reenvía** (proxy server-to-server) el archivo al
FastAPI de INGESTA, que lo **ingiere** en `daily_report_prod` y devuelve el conteo de filas por tabla,
mostrado en pantalla.

**Decisiones cerradas (no reabrir):**
- D1 — front↔back vía **proxy de Flask** (`/api/ingesta/upload` → `http://localhost:8000/ingesta/upload`).
  **Sin CORS.**
- D2 — ingesta **síncrona**; el endpoint responde al terminar con `ResultadoIngesta`. Archivos NEW pueden
  tardar minutos.
- D3 — **"CPF"** es **solo etiqueta visual**.
- D4 — `.env` de INGESTA apunta a `daily_report_prod` @ `10.100.26.139`.
- D5 — el nombre del archivo **debe** contener la fecha `YYYYMMDD` (obligatoria por F1).

## 3. Prerequisitos

| # | Prerequisito | Comando (PowerShell) | Esperado |
|---|---|---|---|
| P1 | Servidor 139 alcanzable | `Test-NetConnection 10.100.26.139 -Port 5432 -InformationLevel Quiet` | `True` |
| P2 | BD con tablas | Validación V0 (§7) | `[('bronze', 4), ('core', 21)]` |
| P3 | `venv` ProdIA OK | `& "c:\APLICACIONES\ProdIA\12112025_prodIA\venv\Scripts\python.exe" --version` | `Python 3.13.x` |
| P4 | `requests` en ProdIA | `& "c:\APLICACIONES\ProdIA\12112025_prodIA\venv\Scripts\python.exe" -c "import requests;print('ok')"` | `ok` |
| P5 | `uv` disponible | `uv --version` | versión |
| P6 | `psycopg` v3 en `.venv` INGESTA | `dir "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\.venv\Lib\site-packages\psycopg"` | existe |

> Si P1 falla, detener: la BD es remota; confirmar red/VPN.

## 4. Inventario de archivos

**Se modifican:**
- `c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\.env`
- `c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\api.py`
- `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py`
- `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js`

**Se instala:** `python-multipart` en el `.venv` de INGESTA.

**No se tocan:** ETL (`services.py`, `detector.py`, `transforms.py`, `shared/utils.py`), DDL, frontend
React de INGESTA, base de datos (solo se escribe vía ingesta).

## 5. Especificación (código completo)

### 5.1 — `INGESTA\Rep_Prod\.env` (reemplazar contenido completo)

> La contraseña real de `postgres` es `y~87z0?>Ri6w`. En `DATABASE_URL` va **URL-encodeada**
> (`?`→`%3F`, `>`→`%3E`); en `PG*`, en texto plano.

```
# Conexión a PostgreSQL daily_report_prod en el servidor 139 (NO versionar — está en .gitignore)
DATABASE_URL=postgresql+psycopg://postgres:y~87z0%3F%3ERi6w@10.100.26.139:5432/daily_report_prod?sslmode=disable
PGHOST=10.100.26.139
PGPORT=5432
PGDATABASE=daily_report_prod
PGUSER=postgres
PGPASSWORD=y~87z0?>Ri6w
```

### 5.2 — Endpoint de upload en INGESTA

Archivo: `INGESTA\Rep_Prod\backend\app\features\ingesta\api.py`

**(a)** Añadir estos imports junto a los existentes del inicio (`Path` ya está importado en la línea 1):

```python
import re, shutil
from fastapi import UploadFile, File
```

**(b)** Añadir al final del archivo (después de `estado_job`):

```python
UPLOAD_SUBDIR = "uploads"
_FECHA_RE = re.compile(r"\d{8}")

@router.post("/upload", response_model=ResultadoIngesta)
def upload_archivo(file: UploadFile = File(...)):
    """Recibe un .xlsm/.xlsx subido, lo guarda en data/uploads/ y lo ingiere de inmediato.
    Ingesta SÍNCRONA. El nombre DEBE contener la fecha YYYYMMDD (la usa core.config_reporte,
    que es NOT NULL)."""
    nombre = Path(file.filename or "").name
    if not nombre.lower().endswith((".xlsm", ".xlsx")):
        raise HTTPException(400, "solo se aceptan archivos .xlsm o .xlsx")
    if not _FECHA_RE.search(nombre):
        raise HTTPException(422, "el nombre del archivo debe contener la fecha en formato YYYYMMDD "
                                 "(p. ej. '20260531_Reporte...'). Es obligatoria para el linaje del reporte.")
    destino_dir = Path(get_settings().data_dir) / UPLOAD_SUBDIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nombre
    try:
        with destino.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()
    try:
        return services.ingerir_archivo(destino)
    except Exception as e:
        raise HTTPException(500, f"fallo de ingesta para {nombre}: {e}")
```

> `ResultadoIngesta`, `services`, `get_settings`, `HTTPException`, `router` y `Path` ya están importados.

### 5.3 — Proxy en ProdIA

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py`

**(a)** Añadir `import os` cerca de los imports del inicio (confirmado: hoy NO está).

**(b)** Después de `api_bp = Blueprint("api", __name__)` añadir:

```python
INGESTA_API_URL = os.environ.get("INGESTA_API_URL", "http://localhost:8000")
```

**(c)** Añadir la ruta (después de la definición de `api_bp`):

```python
@api_bp.route("/ingesta/upload", methods=["POST"])
def ingesta_upload():
    """Proxy: reenvía el archivo subido al FastAPI de INGESTA para su ingesta en daily_report_prod."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "no se envió ningún archivo"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "archivo sin nombre"}), 400
    try:
        resp = requests.post(
            f"{INGESTA_API_URL}/ingesta/upload",
            files={"file": (f.filename, f.stream, f.mimetype or "application/octet-stream")},
            timeout=900,  # archivos NEW grandes pueden tardar varios minutos
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {"success": False, "error": f"respuesta no-JSON de INGESTA: {resp.text[:300]}"}
        return jsonify(payload), resp.status_code
    except requests.RequestException as e:
        return jsonify({"success": False, "error": f"INGESTA no disponible en {INGESTA_API_URL}: {e}"}), 502
```

### 5.4 — UI de carga en el panel izquierdo (ProdIA)

Archivo: `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js`

Reemplazar **íntegramente** la función existente `window.startAdvancedDailyAnalysis = function ...`
(hasta su `};` de cierre) por esta versión (define también el handler de carga):

```javascript
window.startAdvancedDailyAnalysis = function startAdvancedDailyAnalysis() {
  console.log("📈 startAdvancedDailyAnalysis called");

  const chatMessages = document.getElementById("chat-messages");
  const welcomeSection = document.querySelector(".chat-welcome-section");
  const chatBanner = document.querySelector(".chat-banner");

  if (welcomeSection) welcomeSection.style.display = "none";
  if (chatBanner) chatBanner.style.display = "none";

  // En esta vista NO se muestra el input del chat (solo aquí)
  const chatInputAdv = document.querySelector(".chat-input-container");
  if (chatInputAdv) chatInputAdv.style.display = "none";

  // Inyectar el formulario de carga en el panel izquierdo
  if (chatMessages) {
    chatMessages.style.display = "block";
    chatMessages.classList.remove("empty-chat");
    chatMessages.classList.add("has-content");
    chatMessages.innerHTML = `
      <div style="padding:1rem;">
        <h6 style="font-weight:700; color:#0b6e4f;">Cargar Reporte Diario de Producción</h6>
        <p class="text-muted" style="font-size:.85rem;">El archivo se enviará a la ingesta y se cargará en la base de datos. El nombre debe incluir la fecha (YYYYMMDD).</p>
        <label class="form-label" style="font-weight:600;">Archivo XLSX</label>
        <input type="file" id="ingesta-file" class="form-control" accept=".xlsm,.xlsx">
        <div class="mt-2"><span class="badge bg-secondary">CPF</span></div>
        <button id="ingesta-upload-btn" class="btn btn-success mt-3 w-100"
                onclick="handleIngestaUpload()">Cargar e ingerir</button>
        <div id="ingesta-status" class="mt-3"></div>
      </div>`;
  }

  // Título del panel derecho SOLO en esta vista
  const panelTitleAdv = document.getElementById("analytics-panel-title");
  if (panelTitleAdv) panelTitleAdv.textContent = "Análisis avanzado de producción diaria";

  // Panel derecho en blanco
  const emptyState = document.getElementById("analytics-empty-state");
  const chartsArea = document.getElementById("charts-display-area");
  if (emptyState) emptyState.style.display = "none";
  if (chartsArea) { chartsArea.style.display = "block"; chartsArea.innerHTML = ""; }
};

window.handleIngestaUpload = async function handleIngestaUpload() {
  const input = document.getElementById("ingesta-file");
  const status = document.getElementById("ingesta-status");
  const btn = document.getElementById("ingesta-upload-btn");
  if (!input || !input.files.length) {
    if (status) status.innerHTML = '<div class="alert alert-warning py-2">Selecciona un archivo primero.</div>';
    return;
  }
  const fd = new FormData();
  fd.append("file", input.files[0]);
  if (btn) btn.disabled = true;
  status.innerHTML = '<div class="d-flex align-items-center gap-2"><div class="spinner-border spinner-border-sm"></div> Ingiriendo… (los archivos grandes pueden tardar varios minutos)</div>';
  try {
    const r = await fetch("/api/ingesta/upload", { method: "POST", body: fd });
    const data = await r.json();
    if (r.ok && data.reporte_id) {
      const filas = Object.entries(data.filas_por_tabla || {})
        .map(([k, v]) => `<li>${k}: <strong>${v}</strong></li>`).join("");
      status.innerHTML = `<div class="alert alert-success">
        ✅ <strong>${data.archivo}</strong> (${data.tipo_archivo}) → reporte_id <strong>${data.reporte_id}</strong>
        <ul class="mb-0 mt-2">${filas}</ul></div>`;
    } else {
      status.innerHTML = `<div class="alert alert-danger">Error: ${data.error || (data.detail || JSON.stringify(data))}</div>`;
    }
  } catch (e) {
    status.innerHTML = `<div class="alert alert-danger">Fallo de red: ${e}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
};
```

## 6. Orden de ejecución

1. **Editar** `INGESTA\Rep_Prod\.env` con §5.1.
2. **Instalar** `python-multipart` en INGESTA:
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv add python-multipart
   ```
   (Fallback si `uv add` falla: `uv pip install python-multipart`.)
3. **Editar** `...\ingesta\api.py` según §5.2.
4. **Editar** `routes\api.py` según §5.3.
5. **Editar** `static\js\chat.js` según §5.4.
6. **Arrancar INGESTA** (Terminal 1):
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run uvicorn app.main:app --port 8000
   ```
7. **Arrancar ProdIA** (Terminal 2):
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA"
   .\venv\Scripts\python.exe app.py
   ```
8. Ejecutar **Validaciones** (§7).

## 7. Validaciones (criterios de aceptación)

> **V0 — BD lista.** En PowerShell (clave por variable de entorno; usa el python de INGESTA que tiene `psycopg`):
> ```powershell
> $env:PGPASSWORD='y~87z0?>Ri6w'
> cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
> uv run python -c "import psycopg; c=psycopg.connect(host='10.100.26.139',port=5432,user='postgres',dbname='daily_report_prod',sslmode='disable'); cur=c.cursor(); cur.execute(\"select table_schema,count(*) from information_schema.tables where table_schema in ('bronze','core') and table_type='BASE TABLE' group by 1 order by 1\"); print(cur.fetchall())"
> ```
> **Esperado:** `[('bronze', 4), ('core', 21)]`

| # | Validación | Comando | Esperado |
|---|---|---|---|
| V1 | INGESTA responde | `curl.exe http://localhost:8000/health` | `{"status":"ok"}` |
| V2 | Upload + ingesta directa (muestra STD) | comando V2 abajo | JSON con `reporte_id`, `tipo_archivo`, `filas_por_tabla` |
| V2b | Rechazo por nombre sin fecha | comando V2b abajo | **HTTP 422** con mensaje "...formato YYYYMMDD..." |
| V3 | Proxy de ProdIA | comando V3 abajo | mismo JSON con `reporte_id` |
| V4 | Datos en BD | comando V4 abajo | `config_reporte:` ≥ 1 |
| V5 | UI en navegador | abrir `http://localhost:8020`, clic en **"Análisis avanzado de producción diaria"** | panel izq. con "Archivo XLSX", botón "Cargar e ingerir", badge "CPF" |
| V6 | Flujo end-to-end UI | en V5, elegir `INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm` y "Cargar e ingerir" | alert verde `✅ ... (STD) → reporte_id N` con conteos |

**Comando V2** (archivo STD que ingiere en segundos):
```powershell
curl.exe -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8000/ingesta/upload
```

**Comando V2b** (nombre SIN fecha → debe rechazar con 422, sin abrir el archivo):
```powershell
"x" | Out-File -Encoding ascii "$env:TEMP\archivo.xlsx"
curl.exe -i -F "file=@$env:TEMP\archivo.xlsx" http://localhost:8000/ingesta/upload
```

**Comando V3** (vía proxy de ProdIA):
```powershell
curl.exe -F "file=@c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm" http://localhost:8020/api/ingesta/upload
```

**Comando V4** (conteo de reportes ingeridos):
```powershell
$env:PGPASSWORD='y~87z0?>Ri6w'
cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
uv run python -c "import psycopg; c=psycopg.connect(host='10.100.26.139',port=5432,user='postgres',dbname='daily_report_prod',sslmode='disable'); cur=c.cursor(); cur.execute('select count(*) from core.config_reporte'); print('config_reporte:', cur.fetchone()[0])"
```

## 8. Reglas no negociables

1. **No modificar** el ETL (`services.py`, `detector.py`, `transforms.py`, `shared/utils.py`), el DDL ni
   el frontend React de INGESTA.
2. **No habilitar CORS** ni llamar directo a `:8000` desde el navegador. Todo por el proxy de Flask (D1).
3. **No** cambiar la firma ni el comportamiento de `services.ingerir_archivo`.
4. La contraseña en `DATABASE_URL` va **URL-encodeada** (`%3F`/`%3E`); en `PG*`, en plano; en comandos de
   verificación, vía `$env:PGPASSWORD` (nunca embebida en línea por el `>`).
5. El upload guarda en **`data\uploads\`** (no en la raíz de `data\`), valida **extensión** y **fecha
   `YYYYMMDD`** en el nombre antes de ingerir.
6. **No** versionar el `.env` (ya en `.gitignore`); no imprimir la contraseña en logs.
7. Archivos protegidos con etiqueta IRM/RMS **fallarán** en `openpyxl`: comportamiento esperado, no
   corregir aquí (devolverá 500 con mensaje).
8. No renombrar rutas (`/api/ingesta/upload`, `/ingesta/upload`) ni IDs del DOM (`ingesta-file`,
   `ingesta-upload-btn`, `ingesta-status`).

## 9. Fuera de alcance

- Ingesta **asíncrona** con barra de progreso por job (`/ingesta/jobs`). Aquí es síncrona (D2).
- Lógica real del campo **CPF**.
- Descifrado de archivos RMS/IRM.
- Límite de tamaño de subida (`MAX_CONTENT_LENGTH`) y limpieza de `data\uploads\`.
- Autenticación/control de acceso del endpoint, reintentos, colas.
- Validación del contenido del Excel más allá de extensión + fecha en el nombre.
