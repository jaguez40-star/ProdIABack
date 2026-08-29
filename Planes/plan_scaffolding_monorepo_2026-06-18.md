# Plan — Scaffolding del monorepo (backend) · Robustez V2.0 (Reporte Diario de Producción)

> ID: `plan_scaffolding_monorepo_2026-06-18` · **v2 (auditado con flujo profesional §0.2)**
> Modo: para agente **EXECUTOR**. Ejecutar al pie de la letra, en orden. Si un paso falla, DETENERSE y reportar.
> Idioma: español. Comentarios de código en español.
> **v2 — hallazgos integrados:** H1 (COPIAR, no mover — legacy intacto), H2 (usar `core.db.get_engine`,
> sin `load_dotenv`/`create_engine` propios), H3 (acumular conteos), H4 (`[tool.uv] package=false`),
> H5 (puerto 8000), H6 (structlog, no `print`), H7 (sin flag en el servicio), H8 (batch cronológico por
> fecha), H10 (`transforms.py` explícito), H12 (batch masivo solo por CLI). Detalle en §10.

---

## 1. Contexto

Proyecto de **ingesta del Reporte Diario de Producción** (Excel `.xlsm` → PostgreSQL). Hoy el código
vive suelto en la raíz; este plan lo reorganiza en un **backend FastAPI con vertical-slicing** (según
el diagrama "Robustez V2.0") donde el ETL pasa a ser la feature `ingesta`, más features para consultar
lo ingerido. **No incluye frontend** (plan aparte).

Estado actual del repo (raíz = `c:\Users\user\Documents\Rep_Prod\`):
- `db/ddl_v2_postgres.sql` — DDL v2 ya ejecutado en la BD.
- `etl/ingesta_prototipo.py` — ETL funcional, validado end-to-end (NEW + STD).
- `.env` — `DATABASE_URL=postgresql+psycopg://postgres:***@localhost:5432/robustez` (en `.gitignore`).
- `data/{2023,2024,2025}/*.xlsm` — 37 archivos del corpus.
- `Doc_Desing/` — documentos de diseño.
- BD `robustez` operativa en PostgreSQL 18.4 local (`localhost:5432`).

Stack objetivo: Python 3.14 (gestionado por `uv`), FastAPI, Pydantic v2, SQLAlchemy 2.0 **Core**
(sin ORM), structlog. Package manager: **uv** (NO pip; PEP 668 bloquea pip global).

## 2. Objetivo

Dejar un **backend ejecutable** con esta estructura, sin romper la funcionalidad de ingesta actual:

```
Rep_Prod/
└─ backend/
   ├─ pyproject.toml              # proyecto uv + dependencias
   ├─ README.md
   ├─ app/
   │  ├─ __init__.py
   │  ├─ main.py                  # FastAPI: monta routers + /health
   │  ├─ cli.py                   # CLI: ingerir 1 archivo o batch del corpus
   │  ├─ core/
   │  │  ├─ __init__.py
   │  │  ├─ config.py             # pydantic-settings, lee DATABASE_URL del .env raíz
   │  │  ├─ db.py                 # engine SQLAlchemy Core + helper de conexión
   │  │  └─ logging.py            # structlog JSON
   │  ├─ features/
   │  │  ├─ __init__.py
   │  │  ├─ ingesta/              # el ETL, modularizado
   │  │  │  ├─ __init__.py
   │  │  │  ├─ api.py             # POST /ingesta/archivo, POST /ingesta/batch (background)
   │  │  │  ├─ services.py        # orquesta la carga de un archivo (lógica de ingesta_prototipo)
   │  │  │  ├─ detector.py        # detectar raw/STD por presencia de hoja
   │  │  │  ├─ transforms.py      # parseo fecha/num, split empresa/producto, unpivot, helpers
   │  │  │  └─ schemas.py         # Pydantic: ResultadoIngesta
   │  │  ├─ reportes/             # consultar config_reporte / cobertura
   │  │  │  ├─ __init__.py
   │  │  │  ├─ api.py             # GET /reportes, GET /reportes/cobertura
   │  │  │  ├─ services.py
   │  │  │  └─ schemas.py
   │  │  └─ kpis_prod/            # consultar facts de producción
   │  │     ├─ __init__.py
   │  │     ├─ api.py             # GET /kpis-prod/produccion-dia?fecha=...
   │  │     ├─ services.py
   │  │     └─ schemas.py
   │  └─ shared/
   │     ├─ __init__.py
   │     └─ utils.py              # NOISE, num(), s(), to_date() reutilizables
   └─ tests/
      ├─ __init__.py
      ├─ test_health.py
      └─ test_transforms.py
```

**H1 — `etl/ingesta_prototipo.py` y `db/` se CONSERVAN intactos y FUNCIONALES.** La lógica se **COPIA**
(no se corta) hacia la feature `ingesta`. Durante esta fase el prototipo y la feature coexisten
(duplicación temporal deliberada); el prototipo se borrará en un paso posterior, tras validación humana.
Cortar helpers del prototipo está PROHIBIDO (rompería el pipeline actual).

## 3. Prerequisitos (verificar antes de empezar)

| Check | Comando | Esperado |
|-------|---------|----------|
| uv instalado | `uv --version` | `uv 0.11.x` |
| BD viva | `& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -p 5432 -d robustez -c "SELECT 1;"` (con `$env:PGPASSWORD` del `.env`) | `1` |
| `.env` raíz existe | `Test-Path .\.env` | `True` |
| ETL actual existe | `Test-Path .\etl\ingesta_prototipo.py` | `True` |

## 4. Decisiones cerradas (el executor NO decide)

- D-a: Carpeta del backend = `backend/` en la raíz del repo.
- D-b: SQLAlchemy **Core** (sin ORM). Reusar el patrón de `etl/ingesta_prototipo.py` (text() + executemany).
- D-c: Config con `pydantic-settings`, leyendo el **`.env` de la raíz** (`../.env` relativo a `backend/`).
- D-d: La API NO ejecuta la ingesta pesada de forma síncrona en request: `POST /ingesta/batch` corre en
  `BackgroundTasks`. `POST /ingesta/archivo` acepta un path y devuelve el resumen.
- D-e: Mantener idempotencia "última gana" y claves naturales ya validadas (`uk_dia/uk_mes/uk_prog`).
- D-f: NO tocar el DDL ni la BD. NO borrar `etl/` ni `db/`.
- D-g: Dependencias en `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `psycopg[binary]`,
  `pydantic-settings`, `openpyxl`, `structlog`, `typer`; dev: `pytest`, `httpx`.
- D-h (H4): `pyproject.toml` lleva `[tool.uv] package = false` (es una **aplicación**, no un paquete a construir).
- D-i (H2): `services` y `cli` obtienen la conexión SOLO de `app.core.db.get_engine()`. **Prohibido**
  `load_dotenv()` o `sa.create_engine()` dentro de la feature. La config sale de `app.core.config`.
- D-j (H1): COPIAR la lógica del prototipo, nunca cortarla. El prototipo queda funcional.
- D-k (H5): puerto de la API = **8000** (default), configurable por env `API_PORT`. NO usar 6024.
- D-l (H6): el progreso/diagnóstico va por `structlog` (`app.core.logging.log`), nunca `print()` en `services`.
- D-m (H8): el batch ordena por la **fecha extraída del nombre** (`\d{8}`) ascendente → "última gana" correcta.

## 5. Especificación de archivos nuevos (código de referencia)

### 5.1 `backend/pyproject.toml`
```toml
[project]
name = "robustez-ingesta-backend"
version = "0.1.0"
description = "Backend de ingesta del Reporte Diario de Producción"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy>=2",
    "psycopg[binary]",
    "pydantic-settings",
    "openpyxl",
    "structlog",
    "typer",
]

[dependency-groups]
dev = ["pytest", "httpx"]

[tool.uv]
package = false          # H4: es una aplicación, NO un paquete a construir → evita fallo de uv sync

[tool.pytest.ini_options]
pythonpath = ["."]
```

### 5.2 `backend/app/core/config.py`
```python
"""Configuración central (pydantic-settings), lee el .env de la raíz del repo."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"  # backend/app/core -> raíz

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")
    database_url: str
    data_dir: str = str(Path(__file__).resolve().parents[3] / "data")
    app_name: str = "Robustez Ingesta API"

def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

### 5.3 `backend/app/core/db.py`
```python
"""Engine SQLAlchemy Core compartido."""
import sqlalchemy as sa
from app.core.config import get_settings

_engine: sa.Engine | None = None

def get_engine() -> sa.Engine:
    global _engine
    if _engine is None:
        _engine = sa.create_engine(get_settings().database_url, future=True, pool_pre_ping=True)
    return _engine
```

### 5.4 `backend/app/core/logging.py`
```python
"""structlog en JSON."""
import logging, structlog

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[structlog.processors.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer()],
    )

log = structlog.get_logger()
```

### 5.5 `backend/app/shared/utils.py`  (H1: COPIAR, no cortar del prototipo)
> COPIAR desde `etl/ingesta_prototipo.py` las funciones `NOISE`, `s()`, `num()`, `to_date()` tal cual
> (sin alterar su comportamiento). El prototipo conserva las suyas. Reutilizables por `ingesta` y tests.

### 5.5b `backend/app/features/ingesta/transforms.py`  (H10: ubicación fija)
> COPIAR aquí: las constantes `BZ_DIA`, `BZ_MES`, `BZ_PRG`, y los normalizadores de filiales
> `EMP_NORM`, `PROD_NORM`, `norm_emp()`, `norm_prod()`, `split_label()`. Importan de `app.shared.utils`
> lo que necesiten. NO meter aquí acceso a BD.

### 5.6 `backend/app/features/ingesta/services.py`  (H1/H2/H3/H6/H7)
> COPIAR el grueso de `etl/ingesta_prototipo.py` (`DimCache`, `upsert_fuentes`, `ensure_fechas`,
> `get_reporte`, `land_bronze_typed`, `land_landing`, `load_fact_dia/mes/programa`, `load_comentarios`,
> `load_filiales`, `load_pop`, `load_promedios`, `update_config_inicio`). Esas funciones YA reciben
> `conn` como primer argumento → el refactor es mínimo. Reglas obligatorias del refactor:
>
> - **H2:** NO usar `load_dotenv()` ni `sa.create_engine()`. Obtener el engine con
>   `from app.core.db import get_engine`. Importar helpers de `app.shared.utils` y `app.features.ingesta.transforms`.
> - **H6:** reemplazar TODOS los `print(...)` por `from app.core.logging import log` → `log.info("ingesta.mes", filas=total)`.
> - **H7:** NO incluir el flag `--solo-derivadas` ni lectura de `sys.argv`. El servicio siempre hace ingesta completa.
> - **H3:** la función pública acumula los conteos que devuelve cada cargador en un `dict`:
>
> ```python
> from pathlib import Path
> from openpyxl import load_workbook
> from app.core.db import get_engine
> from app.core.logging import log
> from app.features.ingesta.detector import tiene_raw
> from app.features.ingesta.schemas import ResultadoIngesta
>
> def ingerir_archivo(path: Path) -> ResultadoIngesta:
>     wb = load_workbook(path, read_only=True, data_only=True, keep_links=False)
>     raw = tiene_raw(set(wb.sheetnames))
>     filas: dict[str, int] = {}
>     with get_engine().begin() as conn:
>         reporte_id, _ = get_reporte(conn, path, raw)
>         # ... (mismo orden que el prototipo: bronze → dims → facts ECP → comentarios →
>         #      filiales → pop → promedios → update_config_inicio), pero SIN prints:
>         #   filas["fact_produccion_dia_ecp"] = load_fact_dia(conn, wb["BDP_datos_dia"], reporte_id, caches)[0]
>         #   ... etc., guardando cada conteo en `filas`.
>     wb.close()
>     tipo = "NEW" if raw else "STD"
>     log.info("ingesta.ok", archivo=path.name, reporte_id=reporte_id, tipo=tipo, filas=filas)
>     return ResultadoIngesta(archivo=path.name, reporte_id=reporte_id,
>                             tipo_archivo=tipo, tiene_raw=raw, filas_por_tabla=filas)
> ```
> Mantener EXACTO el orden y la lógica de carga del prototipo (incl. la pre-siembra de fuentes de
> `BDP_Programa` antes de `load_fact_programa`). No cambiar claves, FKs ni `ON CONFLICT`.

### 5.7 `backend/app/features/ingesta/detector.py`
```python
"""Detección raw/STD por presencia de hoja."""
from openpyxl import load_workbook

RAW = {"BDP_datos_dia", "BDP_datos_mes", "BDP_Programa"}

def tiene_raw(sheetnames: set[str]) -> bool:
    return RAW.issubset(sheetnames)
```

### 5.8 `backend/app/features/ingesta/schemas.py`
```python
from pydantic import BaseModel

class ResultadoIngesta(BaseModel):
    archivo: str
    reporte_id: int
    tipo_archivo: str          # NEW | STD
    tiene_raw: bool
    filas_por_tabla: dict[str, int]
```

### 5.9 `backend/app/features/ingesta/api.py`
```python
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.core.config import get_settings
from app.features.ingesta.services import ingerir_archivo
from app.features.ingesta.schemas import ResultadoIngesta

router = APIRouter(prefix="/ingesta", tags=["ingesta"])

@router.post("/archivo", response_model=ResultadoIngesta)
def ingestar_archivo(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"No existe: {path}")
    return ingerir_archivo(p)

@router.post("/batch")
def ingestar_batch(bg: BackgroundTasks):
    # H12: SOLO para lotes pequeños / dev. El batch productivo de los 37 archivos va por CLI
    # (el de 125 MB tarda ~3 min; 37 archivos colgarían un worker HTTP ~20-40 min).
    # H8: orden cronológico por la fecha del nombre para que "última gana" sea correcta.
    archivos = _archivos_ordenados(Path(get_settings().data_dir))
    for a in archivos:
        bg.add_task(ingerir_archivo, a)
    return {"encolados": len(archivos)}
```

> Helper compartido por `api.py` y `cli.py` (definir en `services.py`), **H8**:
> ```python
> import re
> def _archivos_ordenados(data_dir: Path) -> list[Path]:
>     """Todos los .xlsm bajo data_dir ordenados por la fecha YYYYMMDD del nombre (asc)."""
>     def fecha(p: Path) -> str:
>         m = re.search(r"(\d{8})", p.name); return m.group(1) if m else "00000000"
>     return sorted(data_dir.rglob("*.xlsm"), key=fecha)
> ```

### 5.10 `backend/app/features/reportes/api.py`
```python
from fastapi import APIRouter
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("")
def listar_reportes():
    with get_engine().connect() as c:
        rows = c.execute(sa.text(
            "SELECT reporte_id, fecha_reporte, tipo_archivo, tiene_raw, nivel_detalle "
            "FROM core.config_reporte ORDER BY fecha_reporte")).mappings().all()
    return [dict(r) for r in rows]

@router.get("/cobertura")
def cobertura():
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT r.reporte_id, r.tipo_archivo,
              (SELECT count(*) FROM core.fact_produccion_mes_ecp f WHERE f.reporte_id=r.reporte_id) AS ecp_mes,
              (SELECT count(*) FROM core.fact_produccion_dia_ecp f WHERE f.reporte_id=r.reporte_id) AS ecp_dia,
              (SELECT count(*) FROM core.fact_produccion_diaria f WHERE f.reporte_id=r.reporte_id) AS filiales
            FROM core.config_reporte r ORDER BY r.reporte_id""")).mappings().all()
    return [dict(r) for r in rows]
```

### 5.11 `backend/app/features/kpis_prod/api.py`
```python
from fastapi import APIRouter
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/kpis-prod", tags=["kpis_prod"])

@router.get("/produccion-dia")
def produccion_dia(fecha: str):
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT tp.nombre AS tipo_producto, SUM(e.vol_estimado) AS vol_estimado
            FROM core.fact_produccion_dia_ecp e
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = e.tipo_producto_id
            WHERE e.fecha = :f AND e.grupo_prod = 'ECOPETROL'
            GROUP BY tp.nombre ORDER BY tp.nombre"""), {"f": fecha}).mappings().all()
    return [dict(r) for r in rows]
```

### 5.12 `backend/app/main.py`
```python
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.features.ingesta.api import router as ingesta_router
from app.features.reportes.api import router as reportes_router
from app.features.kpis_prod.api import router as kpis_prod_router

configure_logging()
app = FastAPI(title=get_settings().app_name)
app.include_router(ingesta_router)
app.include_router(reportes_router)
app.include_router(kpis_prod_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

### 5.13 `backend/app/cli.py`
```python
"""CLI de ingesta. Uso: uv run python -m app.cli archivo <ruta> | batch"""
import sys
from pathlib import Path
from app.core.config import get_settings
from app.features.ingesta.services import ingerir_archivo, _archivos_ordenados

def main():
    if len(sys.argv) < 2:
        print("uso: python -m app.cli {archivo <ruta>|batch}"); return
    if sys.argv[1] == "archivo":
        print(ingerir_archivo(Path(sys.argv[2])).model_dump())
    elif sys.argv[1] == "batch":
        archivos = _archivos_ordenados(Path(get_settings().data_dir))  # H8: cronológico
        new = std = 0
        for a in archivos:
            r = ingerir_archivo(a)
            new += r.tiene_raw; std += (not r.tiene_raw)
            print(f"{a.name}: reporte={r.reporte_id} {r.tipo_archivo} {r.filas_por_tabla}")
        print(f"\nTOTAL: {len(archivos)} archivos | NEW={new} STD={std}")  # H11: resumen de cobertura

if __name__ == "__main__":
    main()
```

### 5.14 `backend/tests/test_health.py`
```python
from fastapi.testclient import TestClient
from app.main import app

def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
```

### 5.15 `backend/tests/test_transforms.py`
```python
import datetime as dt
from app.shared.utils import to_date, num, s

def test_to_date_yyyymmdd():
    assert to_date(20240930) == dt.date(2024, 9, 30)

def test_num_noise():
    assert num("#REF!") is None and num("1,5".replace(",", ".")) == 1.5

def test_s_blank():
    assert s("(en blanco)") is None
```

## 6. Orden de ejecución

1. Crear estructura de carpetas + todos los `__init__.py` vacíos.
2. Crear `backend/pyproject.toml` (§5.1) y `cd backend; uv sync`.
3. Crear `core/` (config, db, logging) — §5.2–5.4.
4. Crear `shared/utils.py` MOVIENDO `NOISE/s/num/to_date` desde `etl/ingesta_prototipo.py` (§5.5).
5. Crear feature `ingesta`: `detector.py`, `transforms.py`, `schemas.py`, `services.py` (§5.6–5.9).
   Mover la lógica del ETL; `services.ingerir_archivo(path)` reemplaza a `main()` del prototipo.
6. Crear features `reportes` y `kpis_prod` (§5.10–5.11).
7. Crear `main.py` y `cli.py` (§5.12–5.13).
8. Crear `tests/` (§5.14–5.15).
9. Ejecutar validaciones §7.

## 7. Validaciones (criterios de aceptación)

| # | Comando (desde `backend/`) | Resultado esperado |
|---|----------------------------|--------------------|
| V1 | `uv sync` | instala sin error |
| V2 | `uv run pytest -q` | todos los tests PASAN |
| V3 | `uv run python -m app.cli archivo "../data/2024/20241206_Reporte Diario de Producción.xlsm"` | imprime `reporte=…` con `filas_por_tabla` no vacío; sin excepción |
| V4 | `uv run uvicorn app.main:app --port 8000` (en background) y `curl http://localhost:8000/health` | `{"status":"ok"}` |
| V5 | `curl "http://localhost:8000/reportes"` | JSON con ≥1 reporte |
| V6 | `curl "http://localhost:8000/kpis-prod/produccion-dia?fecha=2024-10-03"` | JSON con CRUDO/GAS/BLANCOS |
| V7 | `Select-String -Path ..\etl\ingesta_prototipo.py -Pattern "def to_date","def num","def s\(" ` (H1) | 3 matches → el prototipo legacy conserva sus helpers (se COPIÓ, no se cortó) |

## 8. Reglas no negociables

- NO borrar ni modificar `etl/ingesta_prototipo.py`, `db/`, `data/`, `.env`, `CLAUDE.md`.
- NO tocar la BD ni el DDL (solo lectura/escritura vía el ETL ya existente).
- NO usar pip; solo `uv`.
- NO declarar "completado" sin pasar V1–V6.
- Comentarios y mensajes en español.

## 9. Fuera de alcance

- Frontend React (plan aparte).
- Autenticación / RBAC / LDAP.
- Reemplazar/eliminar el ETL legacy (se hará tras validación humana).
- Optimización con COPY a staging (pendiente del ETL).
- Batch productivo de los 37 archivos (se podrá lanzar con `app.cli batch`, pero su ejecución
  masiva NO es parte de este plan de scaffolding).

## 10. Auditoría v2 — hallazgos integrados (flujo profesional §0.2)

Reformulación del plan v1 tras auditar contra el código real (`etl/ingesta_prototipo.py`) y los
hallazgos del análisis del corpus (S7). Cada hallazgo quedó cableado en las secciones indicadas:

| # | Sev | Hallazgo | Corrección en el plan |
|---|-----|----------|-----------------------|
| H1 | 🔴 | "Mover" helpers rompería el ETL legacy | §2, §5.5/§5.6, D-j: **COPIAR**, no cortar. V7 lo valida |
| H2 | 🔴 | `services` heredaría `load_dotenv`+`create_engine` propios | D-i, §5.6: usar `core.db.get_engine`; prohibido dotenv/create_engine |
| H3 | 🟠 | `ingerir_archivo` no acumulaba conteos | §5.6: acumular en `filas_por_tabla` y devolver `ResultadoIngesta` |
| H4 | 🟠 | `uv sync` falla sin declarar app | §5.1, D-h: `[tool.uv] package = false` |
| H5 | 🟡 | Puerto 6024 es de otro proyecto | D-k, §7: puerto **8000**, configurable `API_PORT` |
| H6 | 🟡 | `print()` se pierde en API/Background | D-l, §5.6: `structlog` (`app.core.logging.log`) |
| H7 | 🟡 | Flag `--solo-derivadas` no aplica al servicio | §5.6: el servicio siempre hace ingesta completa |
| H8 | 🟢 | (S7) batch debe ir cronológico | D-m, §5.9, §5.13: ordenar por fecha `\d{8}` del nombre |
| H9 | 🟢 | (S7) detectar por hoja, no tamaño/nombre | §5.7 `detector.tiene_raw` (ya cumple) — reforzado |
| H10 | 🟢 | Ubicación de `BZ_*`/normalizadores ambigua | §5.5b: `transforms.py` explícito |
| H11 | 🟢 | (S7) observabilidad de cobertura | §5.13: CLI batch imprime resumen NEW/STD |
| H12 | 🟡 | Batch HTTP cuelga el worker | §5.9: endpoint solo dev; batch real por CLI |

**Decisiones D1–D3 (CLAUDE.md §6):** sin afectación. El plan no toca el DDL, la BD, ni las claves
naturales validadas; solo reorganiza y expone el ETL existente. No hay escalamiento requerido.
