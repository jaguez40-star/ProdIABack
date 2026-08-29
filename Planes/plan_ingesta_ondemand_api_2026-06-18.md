# Plan EXECUTOR — API de ingesta por demanda (orquestación para frontend)

> **Versión:** v2 (re-auditada contra el código real; correcciones C1–C5 en §11)
> **Fecha:** 2026-06-18
> **Modo:** este documento es **autocontenido**. El agente EXECUTOR no tiene contexto previo ni
> memoria del proyecto: ejecútalo al pie de la letra, en el orden indicado.

---

## 1. Contexto

`Robustez V2.0` es una plataforma que ingiere reportes Excel `.xlsm` (producción de petróleo/gas,
Ecopetrol) a PostgreSQL (esquema estrella, esquemas `bronze` + `core`). Ya existe:

- **BD `robustez`** en PostgreSQL 18 local (`localhost:5432`, user `postgres`), con el DDL v2 aplicado.
- **Backend FastAPI** en `c:\Users\user\Documents\Rep_Prod\backend\` (vertical-slicing). La feature
  `ingesta` ya ingiere un `.xlsm` end-to-end (detección NEW/STD, Bronze, facts ECP, filiales,
  comentarios, config; upsert idempotente "última gana").
- **Corpus** de 37 archivos en `c:\Users\user\Documents\Rep_Prod\data\{2023,2024,2025}\`.

**Problema que este plan resuelve:** la ingesta hoy solo es disparable con (a) un endpoint que
recibe una **ruta absoluta del servidor** (inseguro, el frontend no conoce rutas) y (b) un endpoint
`/batch` *fire-and-forget* sin forma de seguir el progreso. El frontend (pendiente de diseño)
necesita: **listar** lo disponible, **disparar por nombre seguro** y **seguir el progreso** de un lote.

## 2. Objetivo

Añadir a la feature `ingesta` la **capa de orquestación para UI**, sin tocar el motor de ingesta ya
validado:

1. `GET /ingesta/disponibles` — lista los `.xlsm` de `data/` con `{nombre, tipo NEW/STD, fecha, ya_ingerido}`.
2. `POST /ingesta/archivo` — recibe **`{nombre}`** (no ruta), lo resuelve de forma segura dentro de
   `data/`, ingiere uno y devuelve `ResultadoIngesta`.
3. **Jobs asíncronos persistidos** para lotes con progreso consultable:
   - `POST /ingesta/jobs` → crea job, encola proceso en segundo plano, devuelve `{job_id, total}`.
   - `GET /ingesta/jobs/{job_id}` → estado/progreso `{estado, procesados, total, errores, resultado}`.
   - `GET /ingesta/jobs` → últimos jobs.

## 3. Prerequisitos (verificar ANTES de empezar)

Ejecuta y confirma cada uno; si alguno falla, **DETENTE y reporta**:

| # | Comando (PowerShell) | Esperado |
|---|---|---|
| P1 | `Test-Path 'c:\Users\user\Documents\Rep_Prod\backend\app\features\ingesta\services.py'` | `True` |
| P2 | `Test-Path 'c:\Users\user\Documents\Rep_Prod\db\ddl_v2_postgres.sql'` | `True` |
| P3 | `Test-Path 'c:\Users\user\Documents\Rep_Prod\.env'` | `True` |
| P4 | `(Get-ChildItem 'c:\Users\user\Documents\Rep_Prod\data' -Recurse -Filter *.xlsm).Count` | `≥ 30` |
| P5 | `Test-Path 'C:\Program Files\PostgreSQL\18\bin\psql.exe'` | `True` |
| P6 | `cd 'c:\Users\user\Documents\Rep_Prod\backend'; uv run pytest -q` | tests en verde (baseline) |

**Herramientas:** SOLO `uv` (nunca `pip`). PostgreSQL via `psql.exe`. Comentarios y mensajes en
**español**. Puerto de la API = **8000**.

🔴 **Secretos:** la contraseña de Postgres vive en `.env`. **NUNCA** la escribas en claro en ningún
archivo (ni en este plan, ni en SQL, ni en código). Para `psql`, cárgala a `$env:PGPASSWORD`
**leyéndola del `.env`** (ver §6 paso 1), solo para la sesión.

## 4. Inventario de archivos

| Acción | Ruta absoluta |
|---|---|
| **CREAR** | `c:\Users\user\Documents\Rep_Prod\db\migrations\001_ingesta_job.sql` |
| **EDITAR (append)** | `c:\Users\user\Documents\Rep_Prod\db\ddl_v2_postgres.sql` |
| **EDITAR (append)** | `c:\Users\user\Documents\Rep_Prod\backend\app\features\ingesta\detector.py` |
| **REEMPLAZAR** | `c:\Users\user\Documents\Rep_Prod\backend\app\features\ingesta\schemas.py` |
| **EDITAR (append)** | `c:\Users\user\Documents\Rep_Prod\backend\app\features\ingesta\services.py` |
| **REEMPLAZAR** | `c:\Users\user\Documents\Rep_Prod\backend\app\features\ingesta\api.py` |
| **CREAR** | `c:\Users\user\Documents\Rep_Prod\backend\tests\test_ingesta_api.py` |

❌ **NO tocar:** `etl/`, `data/`, `.env`, `CLAUDE.md`, la BD salvo la migración de §6.1, ni la función
`services.ingerir_archivo(...)` (su firma `(path: Path) -> ResultadoIngesta` y su cuerpo quedan
**idénticos**).

## 5. Especificación (código de referencia COMPLETO)

### 5.1 Migración DDL — `db/migrations/001_ingesta_job.sql` (CREAR)

```sql
-- 001_ingesta_job.sql — tabla de jobs de ingesta (orquestación para UI).
-- Idempotente: CREATE TABLE IF NOT EXISTS. Esquema core, convenciones del DDL v2.
CREATE TABLE IF NOT EXISTS core.ingesta_job (
    job_id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    estado          VARCHAR(12)  NOT NULL DEFAULT 'PENDIENTE'
                                 CHECK (estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','ERROR')),
    total           INT          NOT NULL DEFAULT 0,
    procesados      INT          NOT NULL DEFAULT 0,
    errores         INT          NOT NULL DEFAULT 0,
    archivos        JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- nombres solicitados
    resultado       JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- [{archivo, reporte_id?, tipo?, error?}]
    mensaje         TEXT,
    creado_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizado_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### 5.2 Append al DDL maestro — `db/ddl_v2_postgres.sql` (para rebuilds limpios)

Añade **al final del archivo** exactamente el mismo bloque `CREATE TABLE IF NOT EXISTS core.ingesta_job (...)`
de §5.1, precedido por un comentario de sección:

```sql

-- ============================================================================
-- INGESTA_JOB — orquestación de ingesta por demanda (añadido 2026-06-18)
-- ============================================================================
-- (pegar aquí el bloque CREATE TABLE IF NOT EXISTS core.ingesta_job de §5.1)
```

### 5.3 `detector.py` (EDITAR — solo AÑADIR, no borrar lo existente)

El archivo hoy contiene `from openpyxl import load_workbook`, `RAW` y `tiene_raw(...)`.
**(a)** Añade `import zipfile` y `from xml.etree import ElementTree as ET` **junto a los imports del
tope** del archivo (estilo del repo: imports arriba). **(b)** Añade la función al final:

```python
_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

def nombres_de_hojas(path) -> set[str]:
    """Nombres de hoja de un .xlsm leyendo SOLO xl/workbook.xml del zip (sin cargar celdas).
    Rápido incluso en archivos de 125 MB. Devuelve set vacío si el archivo no es un OOXML válido."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("xl/workbook.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        return set()
    root = ET.fromstring(xml)
    return {sh.get("name") for sh in root.iter(f"{{{_NS_MAIN}}}sheet") if sh.get("name")}
```

### 5.4 `schemas.py` (REEMPLAZAR contenido completo)

```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel

class ResultadoIngesta(BaseModel):
    archivo: str
    reporte_id: int
    tipo_archivo: str          # NEW | STD
    tiene_raw: bool
    filas_por_tabla: dict[str, int]

class ArchivoDisponible(BaseModel):
    nombre: str
    tipo: str                  # NEW | STD
    fecha: str | None          # YYYY-MM-DD derivada del nombre
    ya_ingerido: bool

class IngestaRequest(BaseModel):
    nombre: str                # nombre de archivo dentro de data/ (sin ruta)

class JobRequest(BaseModel):
    nombres: list[str] | None = None   # None / [] => todos los disponibles

class JobCreado(BaseModel):
    job_id: int
    total: int

class JobEstado(BaseModel):
    job_id: int
    estado: str                # PENDIENTE | EN_PROCESO | COMPLETADO | ERROR
    total: int
    procesados: int
    errores: int
    archivos: list[str] | None = None
    resultado: list[dict[str, Any]] | None = None
    mensaje: str | None = None
    creado_at: datetime
    actualizado_at: datetime
```

### 5.5 `services.py` (EDITAR — dos cambios; NO modificar nada existente)

⚠️ Confirmado leyendo el archivo: `services.py` importa `re, json, dt, Path, sa, load_workbook,
get_engine, log, tiene_raw, ResultadoIngesta`, transforms y `NOISE, s, num, to_date`. **NO** importa
`get_settings`. Define `ingerir_archivo` y `_archivos_ordenados(data_dir: Path)` (que recibe el
`data_dir` como argumento, no lo resuelve solo).

**🔴 C1 — Paso obligatorio (no opcional):** en el bloque de imports del tope de `services.py`, añade:

```python
from app.core.config import get_settings
```

Sin esto, `listar_disponibles()`/`_nombres_en_data()` lanzan `NameError` y V3 falla.

**Luego añade al final del archivo:**

```python
# ================================================================ ORQUESTACIÓN PARA UI (jobs)
from app.features.ingesta.detector import nombres_de_hojas, tiene_raw

def _nombres_en_data() -> set[str]:
    """Set barato de nombres de .xlsm en data/ (NO abre los libros). Para validar solicitudes."""
    return {p.name for p in Path(get_settings().data_dir).rglob("*.xlsm")}

def listar_disponibles() -> list[dict]:
    """Lista los .xlsm de data/ con tipo NEW/STD (por hoja) y si ya fueron ingeridos.
    C2: to_date() devuelve dt.date y config_reporte.fecha_reporte es DATE → la comparación
    `fecha in ya` es date==date (correcta). NO cambiar a datetime."""
    base = Path(get_settings().data_dir)
    with get_engine().connect() as c:
        ya = {r[0] for r in c.execute(sa.text("SELECT fecha_reporte FROM core.config_reporte"))}
    out = []
    for p in _archivos_ordenados(base):
        m = re.search(r"(\d{8})", p.name)
        fecha = to_date(m.group(1)) if m else None
        raw = tiene_raw(nombres_de_hojas(p))   # C4: si el zip falla, set() => se reporta STD
        out.append({"nombre": p.name, "tipo": "NEW" if raw else "STD",
                    "fecha": fecha.isoformat() if fecha else None,
                    "ya_ingerido": fecha in ya})
    return out

def crear_job(nombres: list[str]) -> int:
    with get_engine().begin() as conn:
        return conn.execute(sa.text(
            "INSERT INTO core.ingesta_job (estado, total, archivos) "
            "VALUES ('PENDIENTE', :t, CAST(:a AS jsonb)) RETURNING job_id"),
            {"t": len(nombres), "a": json.dumps(nombres, ensure_ascii=False)}).scalar()

def _job_estado(job_id: int, estado: str, mensaje: str | None = None):
    with get_engine().begin() as c:
        c.execute(sa.text("UPDATE core.ingesta_job SET estado=:e, mensaje=:m, actualizado_at=now() "
                          "WHERE job_id=:j"), {"e": estado, "m": mensaje, "j": job_id})

def _job_progreso(job_id: int, procesados: int, errores: int, resultado: list[dict]):
    with get_engine().begin() as c:
        c.execute(sa.text("UPDATE core.ingesta_job SET procesados=:p, errores=:e, "
                          "resultado=CAST(:r AS jsonb), actualizado_at=now() WHERE job_id=:j"),
                  {"p": procesados, "e": errores,
                   "r": json.dumps(resultado, ensure_ascii=False), "j": job_id})

def procesar_job(job_id: int, paths: list[Path]):
    """Worker de BackgroundTasks: ingiere los archivos en orden, actualizando progreso por archivo."""
    _job_estado(job_id, "EN_PROCESO")
    resultado, procesados, errores = [], 0, 0
    try:
        for p in paths:
            try:
                r = ingerir_archivo(p)
                resultado.append({"archivo": p.name, "reporte_id": r.reporte_id, "tipo": r.tipo_archivo})
            except Exception as e:   # un archivo no debe tumbar el lote
                errores += 1
                resultado.append({"archivo": p.name, "error": str(e)})
                log.error("job.archivo.error", job=job_id, archivo=p.name, error=str(e))
            procesados += 1
            _job_progreso(job_id, procesados, errores, resultado)
        _job_estado(job_id, "COMPLETADO")
        log.info("job.completado", job=job_id, total=len(paths), errores=errores)
    except Exception as e:           # fallo inesperado a nivel job
        _job_estado(job_id, "ERROR", str(e))
        log.error("job.error", job=job_id, error=str(e))

def obtener_job(job_id: int) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(sa.text("SELECT * FROM core.ingesta_job WHERE job_id=:j"),
                      {"j": job_id}).mappings().first()
    return dict(r) if r else None

def listar_jobs(limite: int = 20) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(sa.text(
            "SELECT job_id, estado, total, procesados, errores, mensaje, creado_at, actualizado_at "
            "FROM core.ingesta_job ORDER BY job_id DESC LIMIT :l"), {"l": limite}).mappings().all()
    return [dict(r) for r in rows]
```

> Nota: `get_settings` ya está importado en `services.py` (lo usa `_archivos_ordenados`/config). Si al
> ejecutar aparece `NameError: get_settings`, añade `from app.core.config import get_settings` en la
> cabecera de imports y vuelve a validar. (Verifícalo leyendo la cabecera antes de asumir.)

### 5.6 `api.py` (REEMPLAZAR contenido completo)

```python
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.core.config import get_settings
from app.features.ingesta import services
from app.features.ingesta.schemas import (
    ResultadoIngesta, ArchivoDisponible, IngestaRequest, JobRequest, JobCreado, JobEstado)

router = APIRouter(prefix="/ingesta", tags=["ingesta"])

def _resolver_nombre(nombre: str) -> Path:
    """Resuelve un nombre de archivo a una ruta DENTRO de data/. Bloquea path traversal."""
    if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
        raise HTTPException(400, "nombre inválido")
    base = Path(get_settings().data_dir).resolve()
    candidatos = [p for p in base.rglob(nombre) if p.is_file()]
    if not candidatos:
        raise HTTPException(404, f"No existe en data/: {nombre}")
    p = candidatos[0].resolve()
    if base != p.parent and base not in p.parents:
        raise HTTPException(400, "fuera de data/")
    return p

@router.get("/disponibles", response_model=list[ArchivoDisponible])
def disponibles():
    return services.listar_disponibles()

@router.post("/archivo", response_model=ResultadoIngesta)
def ingestar_archivo(req: IngestaRequest):
    return services.ingerir_archivo(_resolver_nombre(req.nombre))

@router.post("/jobs", response_model=JobCreado)
def crear_job(req: JobRequest, bg: BackgroundTasks):
    # C3: validar con el set BARATO de nombres (no abrir los 37 zips en cada POST).
    en_data = services._nombres_en_data()
    nombres = req.nombres or sorted(en_data)
    invalidos = [n for n in nombres if n not in en_data]
    if invalidos:
        raise HTTPException(400, f"no están en data/: {invalidos}")
    paths = [_resolver_nombre(n) for n in nombres]
    job_id = services.crear_job(nombres)
    bg.add_task(services.procesar_job, job_id, paths)
    return {"job_id": job_id, "total": len(nombres)}

@router.get("/jobs", response_model=list[JobEstado])
def listar_jobs():
    return services.listar_jobs()

@router.get("/jobs/{job_id}", response_model=JobEstado)
def estado_job(job_id: int):
    j = services.obtener_job(job_id)
    if not j:
        raise HTTPException(404, "job no existe")
    return j
```

> ⚠️ Esto **reemplaza** los endpoints anteriores `POST /ingesta/archivo?path=...` y `POST /ingesta/batch`.
> El batch productivo de los 37 archivos sigue disponible por **CLI** (`python -m app.cli batch`), que
> **no se modifica**. Decisión cerrada: el HTTP por demanda usa el modelo de jobs; el lote masivo va por CLI.

### 5.7 `tests/test_ingesta_api.py` (CREAR)

```python
from pathlib import Path
import pytest
from fastapi import HTTPException
from app.features.ingesta.api import _resolver_nombre
from app.features.ingesta.detector import nombres_de_hojas, tiene_raw

def test_resolver_rechaza_traversal():
    for malo in ["", "../x.xlsm", "..\\x.xlsm", "sub/dir.xlsm", "sub\\dir.xlsm"]:
        with pytest.raises(HTTPException):
            _resolver_nombre(malo)

def test_resolver_archivo_inexistente():
    with pytest.raises(HTTPException):
        _resolver_nombre("no_existe_zzz_12345.xlsm")

_MUESTRAS = list(Path(r"c:\Users\user\Documents\Rep_Prod\Doc_Desing").glob("*.xlsm"))

@pytest.mark.skipif(not _MUESTRAS, reason="no hay .xlsm de muestra en Doc_Desing")
def test_nombres_de_hojas_lee_del_zip():
    hojas = nombres_de_hojas(_MUESTRAS[0])
    assert isinstance(hojas, set) and len(hojas) > 0
    # tiene_raw debe devolver bool sin lanzar
    assert isinstance(tiene_raw(hojas), bool)
```

## 6. Orden de ejecución

1. **Aplicar migración DDL.** Crea `db/migrations/001_ingesta_job.sql` (§5.1). Carga la contraseña
   desde `.env` SIN imprimirla y aplica:
   ```powershell
   $env:PGPASSWORD = (Select-String -Path 'c:\Users\user\Documents\Rep_Prod\.env' -Pattern '^PGPASSWORD=(.+)$').Matches[0].Groups[1].Value
   if (-not $env:PGPASSWORD) {
     # fallback: extraer del DATABASE_URL postgresql+psycopg://postgres:<pwd>@...
     $env:PGPASSWORD = (Select-String -Path 'c:\Users\user\Documents\Rep_Prod\.env' -Pattern ':\/\/postgres:([^@]+)@').Matches[0].Groups[1].Value
   }
   & 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -d robustez -v ON_ERROR_STOP=1 -f 'c:\Users\user\Documents\Rep_Prod\db\migrations\001_ingesta_job.sql'
   ```
2. **Append** el bloque a `db/ddl_v2_postgres.sql` (§5.2).
3. **Editar** `detector.py` (§5.3, solo añadir).
4. **Reemplazar** `schemas.py` (§5.4).
5. **Editar** `services.py` (§5.5, solo añadir al final).
6. **Reemplazar** `api.py` (§5.6).
7. **Crear** `tests/test_ingesta_api.py` (§5.7).
8. Ejecutar **Validaciones** §7 en orden.

## 7. Validaciones (criterio de aceptación: comando → resultado esperado)

Todas desde `c:\Users\user\Documents\Rep_Prod\backend` salvo indicación.

| # | Comando | Esperado |
|---|---|---|
| **V1** | `& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -d robustez -c "\d core.ingesta_job"` (con `$env:PGPASSWORD` seteado) | Muestra la tabla con columnas `job_id, estado, total, procesados, errores, archivos, resultado, mensaje, creado_at, actualizado_at` |
| **V2** | `uv run pytest -q` | Todos los tests en verde (los previos + los 3 nuevos; el de hojas puede `skip` si no hay muestra) |
| **V3** | Arrancar `uv run uvicorn app.main:app --port 8000` y `Invoke-RestMethod 'http://127.0.0.1:8000/ingesta/disponibles'` | Lista de ≥30 items, cada uno con `nombre/tipo(NEW\|STD)/fecha/ya_ingerido` |
| **V4** | `Invoke-RestMethod 'http://127.0.0.1:8000/ingesta/archivo' -Method Post -ContentType 'application/json' -Body '{"nombre":"<un STD existente de data/>"}'` | `200` con `ResultadoIngesta` (`tipo_archivo`, `filas_por_tabla`) |
| **V4b** | `Invoke-RestMethod 'http://127.0.0.1:8000/ingesta/archivo' -Method Post -ContentType 'application/json' -Body '{"nombre":"../x.xlsm"}'` | `400` (rechazo de traversal) |
| **V5** | `POST /ingesta/jobs` con `{"nombres":["<un STD existente>"]}` → guardar `job_id`; luego `GET /ingesta/jobs/<job_id>` | El job pasa a `COMPLETADO`, `procesados=1`, `resultado` con 1 item |
| **V6** | `(Get-Content 'c:\Users\user\Documents\Rep_Prod\etl\ingesta_prototipo.py' \| Measure-Object -Line).Lines` **y** `Select-String -Path '...\ingesta\services.py' -Pattern 'def ingerir_archivo\(path: Path\) -> ResultadoIngesta'` | ETL legacy con su mismo nº de líneas (intacto) **y** la firma de `ingerir_archivo` sin cambios |

Para V4/V5 elige un archivo **STD** (rápido, sin ECP). Para identificarlo: en `GET /ingesta/disponibles`,
cualquiera con `tipo:"STD"` (p. ej. uno de `data/2023/`).

Si **cualquier** validación falla: **DETENTE**, reporta `❌ Vn` con el error exacto, no improvises
arreglos fuera de este plan.

## 8. Reglas no negociables

1. **NO** modificar `services.ingerir_archivo` (firma ni cuerpo), `etl/`, `data/`, `.env`, `CLAUDE.md`.
2. La feature `ingesta` **no** puede usar `load_dotenv()` ni `sa.create_engine()` propios: el engine
   sale de `app.core.db.get_engine()`.
3. **Solo `uv`** (jamás `pip`). Comentarios y mensajes de log en **español**. Puerto API = **8000**.
4. **NUNCA** escribir la contraseña de Postgres en claro en ningún archivo; cargarla a
   `$env:PGPASSWORD` desde `.env` solo para la sesión.
5. `core.ingesta_job` se crea con `CREATE TABLE IF NOT EXISTS` (idempotente).
6. El worker de jobs usa **`BackgroundTasks` de FastAPI** (no APScheduler en este incremento).
7. Orden secuencial. Si un paso falla, detente y reporta.

## 9. Fuera de alcance (NO hacer en este plan)

- Frontend (pendiente de diseño) — solo se cierra el contrato HTTP.
- APScheduler / cron / colas externas / multi-worker. (Los `BackgroundTasks` viven en el proceso del
  worker; suficiente para un solo Uvicorn. Escalar es un incremento posterior.)
- WebSocket/SSE para progreso en vivo (el frontend hará *polling* a `GET /ingesta/jobs/{id}`).
- Subida (*upload*) de `.xlsm` nuevos desde el navegador.
- Autenticación / permisos (feature `auth` aparte).
- Suite de Paridad Numérica y KPIs.
- Reproceso por hash (`config_reporte.hash_archivo` existe pero su uso queda para otro incremento).

---

## 11. Hallazgos de la re-auditoría (v1 → v2)

Auditoría audit-first (§0.2) del propio plan contra el código real (`services.py`, `shared/utils.py`,
`detector.py`, DDL). Disparadores: el plan toca la **detección raw/STD** y añade tabla al **DDL**.

| # | Severidad | Hallazgo | Corrección en v2 |
|---|---|---|---|
| **C1** | 🔴 Defecto | `services.py` NO importa `get_settings`; `listar_disponibles` lo usa → `NameError`, V3 falla. La v1 lo dejaba como nota opcional. | §5.5: **paso duro** que añade `from app.core.config import get_settings` a los imports. |
| **C2** | 🟢 Verificado | Riesgo de que `ya_ingerido` diera siempre `False` por `date` vs `datetime`. `to_date()` devuelve `dt.date` (utils.py L28/34) y `fecha_reporte` es `DATE` → comparación correcta. | Sin cambio de lógica; comentario en código para no "corregirlo" mal. |
| **C3** | 🟠 Coste | `POST /jobs` validaba nombres con `listar_disponibles()`, que abre los 37 zips (incl. 125 MB) en cada POST. | §5.5 helper `_nombres_en_data()` (solo `rglob`, sin abrir libros); §5.6 lo usa para validar. |
| **C4** | 🟡 Robustez | Un `.xlsm` corrupto/bloqueado → `nombres_de_hojas` devuelve `set()` → se reporta como **STD**. | Aceptado y documentado (no rompe el lote; el archivo igual se intenta ingerir). |
| **C5** | 🟡 Estilo | Imports de `detector.py` iban a mitad de archivo. | §5.3: `zipfile`/`ElementTree` al tope, como el resto del repo. |

**Coherencia de pipelines verificada:** (a) `services.ingerir_archivo` y `_archivos_ordenados` quedan
intactos → CLI (`python -m app.cli batch`/`archivo`) sigue funcional. (b) Ningún test ni `main.py`
referencia los endpoints viejos (`?path=`, `/batch`); `test_health.py` solo toca `/health`. (c) El
worker sync corre en *threadpool* de Starlette (no bloquea el event loop); cada ingesta toma su
conexión del pool del engine singleton; el upsert idempotente "última gana" tolera solapamientos.

---

## 10. Prompt para el agente EXECUTOR (copiar tal cual)

```
Eres un agente EXECUTOR. Trabajas en c:\Users\user\Documents\Rep_Prod\.
Lee COMPLETO el plan Planes/plan_ingesta_ondemand_api_2026-06-18.md y ejecútalo AL PIE DE LA LETRA, en el orden de §6.

Reglas no negociables (§8):
- NO modifiques services.ingerir_archivo (firma ni cuerpo), ni etl/, data/, .env, CLAUDE.md.
- En la feature ingesta PROHIBIDO load_dotenv()/sa.create_engine(): usa app.core.db.get_engine().
- Solo `uv` (nunca pip). Comentarios y logs en español. Puerto API = 8000.
- NUNCA escribas la contraseña de Postgres en claro; cárgala a $env:PGPASSWORD desde .env solo para la sesión.
- core.ingesta_job se crea con CREATE TABLE IF NOT EXISTS. Worker de jobs = BackgroundTasks de FastAPI.

Ejecuta los pasos 1–8 de §6. Luego corre las validaciones V1–V6 de §7.
Si un paso o validación falla: DETENTE y reporta "❌ Vn/Paso n" con el error exacto. No improvises fuera del plan.

Al terminar: lista de archivos creados/editados + tabla de resultados V1–V6 + "¿Hago commit?".
```
