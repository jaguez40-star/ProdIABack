# Plan ejecutable v2 (auditado) — Visor genérico de tablas por hoja (`core.fact_tabla_hoja`) + UI clicable

> Modo **plan:** (executor sin contexto). Rutas absolutas, código completo, decisiones cerradas,
> criterios verificables. **Base escalable**: P50 pasa a ser el primer caso de un patrón reutilizable.
> Decisiones del dueño: **1.A** (visor ancho tipo Excel), **2.** etiquetas literales "Tabla 1/Tabla 2",
> **3.** solo tabla (sin gráfico), **4.a** efímero (los ítems se arman tras ingerir; el contenido siempre
> se trae de la BD al hacer clic).

---

## 0. Hallazgos de auditoría (verificados contra el código real)

- **C1 — INGESTA: routers con prefijo** montados en `backend/app/main.py` (`ingesta`, `reportes`,
  `kpis-prod`). Los endpoints de lectura usan `get_engine().connect()` + `sa.text(...).mappings().all()`
  (patrón de `features/reportes/api.py`). ⇒ se añade un router nuevo `tablas` igual.
- **C2 — ProdIA: proxy ya existe.** `routes/api.py` tiene `api_bp` (Blueprint, prefijo `/api`),
  `import requests`, `INGESTA_API_URL` (línea 18) y el patrón `requests.<m>(f"{INGESTA_API_URL}/…")
  → jsonify(resp.json()), resp.status_code` (ver `/ingesta/upload`). ⇒ se añaden 2 proxies GET.
- **C3 — Front: el panel derecho** existe: `charts-display-area` y `analytics-panel-title` los maneja
  `startAdvancedDailyAnalysis()` en `static/js/chat.js`. ⇒ ahí se pinta la tabla.
- **C4 — El loader P50 ya produce la forma genérica** (tabla, dims, fecha, valor). Migrarlo a
  `fact_tabla_hoja` es redirigir su salida; los helpers `_p50_contig_months` y el parseo con `to_date`
  se conservan. `s`, `num`, `to_date`, `sa`, `re`, `json` ya están importados en `services.py`.
- **C5 — JSONB ↔ Python:** con psycopg3, una columna `JSONB` se devuelve como `dict` en Python; para
  insertar, se pasa `json.dumps(...)` y `CAST(:dims AS jsonb)`. (Patrón seguro, sin adaptadores.)
- **C6 — `fact_p50_quemado` solo lo usa el loader actual** (que se reemplaza) — ninguna otra ruta/UI lo
  referencia (verificado por búsqueda). ⇒ se puede DROP sin romper nada.

### 0.b Verificaciones load-bearing del v2 (probadas en vivo, no de memoria)
- **D1 — JSONB ↔ `dict`: VERIFICADO.** Con el stack real (`get_engine()` + `sa.text` + psycopg3), un
  `SELECT …::jsonb` devuelve un **`dict`** Python, y `INSERT … CAST(:d AS jsonb)` con `json.dumps()`
  round-trip correcto (incluye acentos). ⇒ el endpoint `/tablas/datos` (`r["dims"].keys()`) es seguro.
- **D2 — IDs del DOM existen: VERIFICADO.** `charts-display-area` y `analytics-empty-state` están en
  `templates/components/analytics.html`; `analytics-panel-title` en `templates/main.html`. ⇒ el visor
  tiene dónde pintar.
- **D3 — Schema: VERIFICADO.** `ResultadoIngesta.filas_por_tabla` es `dict[str, int]` (acepta keys
  arbitrarias) ⇒ la key `tabla_hoja::<hoja>` no rompe Pydantic.
- **D4 — Anclaje del front: VERIFICADO.** El bloque `else { … .ingesta-analisis … }` de
  `renderIngestaProgress` (hoy líneas ~375-385) coincide exacto con el que reemplaza §4.8(a).
- **D5 — Incoherencia cosmética (aceptada).** `jsonb` **no preserva el orden de claves** (Postgres las
  normaliza). ⇒ en el visor, las columnas de dimensión saldrán en orden normalizado (p.ej. area, vice,
  activos, producto, escenario), **no** en el orden visual del Excel. Es **solo cosmético** (datos y
  etiquetas correctos). Fix futuro barato en §8. **No** se prefijan las claves (mantener `dims->>'area'`
  limpio para SQL/validaciones).

---

## 1. Contexto y objetivo

Hoy la hoja P50 carga 2 tablas a `core.fact_p50_quemado` (tabla **específica**). Queremos un **patrón
escalable**: una tabla **genérica** `core.fact_tabla_hoja` (formato largo + `dims` JSONB), un **registro**
de extractores por hoja, **endpoints genéricos** de lectura, y una **UI genérica** que muestre las tablas
de cada hoja como ítems clicables y pinte su contenido (ancho, tipo Excel) en el panel derecho.

**Meta:** agregar una hoja nueva en el futuro = escribir **solo su extractor** + 1 línea en el registro.
Cero endpoints/UI/tablas nuevas.

## 2. Prerequisitos (si falla, DETENERSE y reportar)

- **P1** — Archivos: `…\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`,
  `…\backend\app\main.py`, `…\backend\app\features\reportes\api.py` (referencia),
  `…\db\ddl_v2_postgres.sql`, `…\db\migrations\` (con `001_…`, `002_fact_p50_quemado.sql`),
  `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py`, `…\static\js\chat.js`.
- **P2** — BD 139: host `10.100.26.139`, db `daily_report_prod`, user `postgres`, pass `y~87z0?>Ri6w`
  (PowerShell: usar `$env:PGPASSWORD`). Ya existe `core.fact_p50_quemado` con datos de reporte 1 y 7.
- **P3** — Backends: INGESTA FastAPI :8000 (`cd backend; uv run uvicorn app.main:app --port 8000`),
  ProdIA Flask :8020. Reiniciar ambos tras editar.
- **P4** — Archivo de prueba: `…\data\20241004_Reporte New Diario de Producción.xlsm`.

## 3. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\db\migrations\003_fact_tabla_hoja.sql` | **CREAR** (tabla genérica + DROP de `fact_p50_quemado`) y **ejecutar** en la BD. |
| `…\db\ddl_v2_postgres.sql` | **MODIFICAR**: reemplazar el bloque `fact_p50_quemado` por `fact_tabla_hoja`. |
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: extractor genérico + registro + `load_tablas_hoja`; reemplazar el hook P50. |
| `…\backend\app\features\tablas\__init__.py` y `…\tablas\api.py` | **CREAR** (router de lectura genérico). |
| `…\backend\app\main.py` | **MODIFICAR**: incluir el router `tablas`. |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\routes\api.py` | **MODIFICAR**: 2 proxies GET a INGESTA. |
| `…\static\js\chat.js` | **MODIFICAR**: ítems clicables + visor de tabla ancha en el panel derecho. |

**NO se toca:** `land_landing`, otros facts/loaders, `api.py` de INGESTA (el de ingesta), autenticación.

## 4. Especificación (código completo)

### 4.1 Migración `db\migrations\003_fact_tabla_hoja.sql`

```sql
-- 003_fact_tabla_hoja.sql — tabla GENÉRICA para tablas modeladas de cualquier hoja (formato largo).
-- dims JSONB guarda las dimensiones variables por hoja/tabla (p.ej. {"area":"BORANDA","vice":"VFS",...}).
CREATE TABLE IF NOT EXISTS core.fact_tabla_hoja (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id  INTEGER NOT NULL REFERENCES core.config_reporte(reporte_id),
    hoja        TEXT    NOT NULL,
    tabla_idx   INTEGER NOT NULL,
    tabla_label TEXT    NOT NULL,
    dims        JSONB   NOT NULL DEFAULT '{}'::jsonb,
    fecha       DATE    NOT NULL,
    valor       NUMERIC
);
CREATE INDEX IF NOT EXISTS ix_tabla_hoja ON core.fact_tabla_hoja (reporte_id, hoja, tabla_idx);
-- Retirar la tabla específica anterior (su loader se reemplaza por el genérico).
DROP TABLE IF EXISTS core.fact_p50_quemado;
```

Ejecutar SOLO esta migración:
```powershell
$env:PGPASSWORD='y~87z0?>Ri6w'
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 10.100.26.139 -U postgres -d daily_report_prod `
  -v ON_ERROR_STOP=1 -f "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\db\migrations\003_fact_tabla_hoja.sql"
```
(Alternativa psycopg si no hay `psql.exe`: leer el archivo y `c.execute(...)`/`c.commit()` como en planes previos.)

### 4.2 DDL maestro `db\ddl_v2_postgres.sql`

Localizar el bloque `CREATE TABLE IF NOT EXISTS core.fact_p50_quemado (…)` + su índice (≈ líneas 635-650)
y **reemplazarlo** por el `CREATE TABLE core.fact_tabla_hoja (…)` + índice de §4.1 (sin el `DROP`). Solo
para instalaciones nuevas; no se ejecuta aquí.

### 4.3 `services.py` — extractor genérico + registro + loader (reemplaza el sistema P50)

**(a)** Mantener `_p50_contig_months(...)` tal cual. **Eliminar** `P50_SHEET_RE`, la función
`load_p50_quemado` completa, y el bloque hook P50 de §4.4-viejo. **Agregar** (cerca de los loaders):

```python
def _p50_grid(ws):
    grid, maxr = {}, 0
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for c, v in enumerate(row, start=1):
            if v is not None and str(v).strip() != "":
                grid[(r, c)] = v
                if r > maxr:
                    maxr = r
        if r > 250:
            break
    return grid, maxr

def _p50_extract(ws):
    """Extractor de la hoja 'P50 Quemado <año> ECP y Filiales'. Contrato genérico:
    devuelve [{tabla_idx, tabla_label, dims(dict), fecha(date), valor(float)}].
    Tabla 1='quemado' (escenario/producto/vice/activos/area); Tabla 2='filiales' (producto/empresa).
    Lee por posición; meses contiguos (corta antes de la tabla VR/GER); descarta subtotales y Promedio Año."""
    grid, maxr = _p50_grid(ws)
    rows = []
    # --- Tabla 1 ---
    m1 = _p50_contig_months(grid, 2, 6)
    for r in range(3, maxr + 1):
        area = grid.get((r, 5))
        if area is None or str(area).strip().lower().startswith("total"):
            continue
        dims = {"escenario": s(grid.get((r, 1))), "producto": s(grid.get((r, 2))),
                "vice": s(grid.get((r, 3))), "activos": s(grid.get((r, 4))), "area": s(area)}
        for c, d in m1:
            val = num(grid.get((r, c)))
            if val is None:
                continue
            rows.append({"tabla_idx": 1, "tabla_label": "Tabla 1", "dims": dims, "fecha": d, "valor": val})
    # --- Tabla 2 ---
    title = next(((r, c) for (r, c), v in grid.items()
                  if isinstance(v, str) and v.strip().lower() == "p50 filiales"), None)
    if title:
        tr, tc = title
        hdr = tr + 1
        m2 = _p50_contig_months(grid, hdr, tc + 3)
        for r in range(hdr + 1, maxr + 1):
            empresa = grid.get((r, tc + 2))
            if empresa is None:
                continue
            producto = grid.get((r, tc))
            if producto and str(producto).strip().lower().startswith("total"):
                continue
            dims = {"producto": s(producto), "empresa": s(empresa)}
            for c, d in m2:
                val = num(grid.get((r, c)))
                if val is None:
                    continue
                rows.append({"tabla_idx": 2, "tabla_label": "Tabla 2", "dims": dims, "fecha": d, "valor": val})
    return rows

# === Registro de hojas modeladas: (regex_nombre_hoja, extractor) ===
# Agregar una hoja nueva en el futuro = una línea aquí + su función _xxx_extract(ws).
HOJAS_MODELADAS = [
    (re.compile(r"(?i)^P50 Quemado \d{4} ECP y Filiales$"), _p50_extract),
]

def load_tablas_hoja(conn, wb, reporte_id):
    """Por cada hoja del registro presente en el libro: extrae filas (contrato genérico), deduplica por
    (tabla_idx, dims, fecha) last-wins, reemplaza en core.fact_tabla_hoja (DELETE+INSERT por hoja) y
    devuelve resúmenes [{hoja, tablas:[{tabla_idx,tabla_label,filas}], total}] para el front."""
    resumen = []
    for pat, extractor in HOJAS_MODELADAS:
        hoja = next((sh for sh in wb.sheetnames if pat.match(sh)), None)
        if not hoja:
            continue
        filas = extractor(wb[hoja])
        by_key = {}
        for f in filas:
            k = (f["tabla_idx"], json.dumps(f["dims"], sort_keys=True, ensure_ascii=False), f["fecha"])
            by_key[k] = f
        out = list(by_key.values())
        conn.execute(sa.text("DELETE FROM core.fact_tabla_hoja WHERE reporte_id=:r AND hoja=:h"),
                     {"r": reporte_id, "h": hoja})
        if out:
            conn.execute(sa.text("""
                INSERT INTO core.fact_tabla_hoja (reporte_id, hoja, tabla_idx, tabla_label, dims, fecha, valor)
                VALUES (:r, :h, :idx, :label, CAST(:dims AS jsonb), :fecha, :valor)
            """), [{"r": reporte_id, "h": hoja, "idx": f["tabla_idx"], "label": f["tabla_label"],
                    "dims": json.dumps(f["dims"], ensure_ascii=False),
                    "fecha": f["fecha"], "valor": f["valor"]} for f in out])
        cont = {}
        for f in out:
            kk = (f["tabla_idx"], f["tabla_label"])
            cont[kk] = cont.get(kk, 0) + 1
        tablas = [{"tabla_idx": i, "tabla_label": l, "filas": n} for (i, l), n in sorted(cont.items())]
        resumen.append({"hoja": hoja, "tablas": tablas, "total": len(out)})
    return resumen
```

### 4.4 `services.py` — hook en `ingerir_archivo` (reemplaza el bloque P50)

Sustituir el bloque actual `# ---- P50 Quemado (2 tablas -> core.fact_p50_quemado) ----` (dentro del
`with get_engine().begin() as conn:`, antes de `wb.close()`, indent 8 espacios) por:

```python
        # ---- Hojas modeladas -> core.fact_tabla_hoja (registro escalable) ----
        for _res in load_tablas_hoja(conn, wb, reporte_id):
            filas[f"tabla_hoja::{_res['hoja']}"] = _res["total"]
            _log_ingesta(conn, reporte_id, _res["hoja"], "core.fact_tabla_hoja",
                         _res["total"], _res["total"])
            log.info("ingesta.tablahoja", hoja=_res["hoja"], total=_res["total"])
            _emit({"tipo": "hoja", "hoja": _res["hoja"], "estado": "ok",
                   "tabla": "fact_tabla_hoja", "filas": _res["total"],
                   "reporte_id": reporte_id, "tablas": _res["tablas"]})
```

### 4.5 Nuevo router de lectura — crear `backend\app\features\tablas\__init__.py` (vacío) y `…\tablas\api.py`

```python
from fastapi import APIRouter, HTTPException
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/tablas", tags=["tablas"])

@router.get("")
def listar(reporte_id: int, hoja: str):
    """Tablas lógicas de una hoja modelada (para los ítems clicables)."""
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT tabla_idx, tabla_label, count(*) AS filas
            FROM core.fact_tabla_hoja WHERE reporte_id=:r AND hoja=:h
            GROUP BY tabla_idx, tabla_label ORDER BY tabla_idx"""),
            {"r": reporte_id, "h": hoja}).mappings().all()
    return [dict(x) for x in rows]

@router.get("/datos")
def datos(reporte_id: int, hoja: str, tabla_idx: int):
    """Contenido de una tabla en formato ANCHO (dims como filas, meses como columnas)."""
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT dims, fecha, valor FROM core.fact_tabla_hoja
            WHERE reporte_id=:r AND hoja=:h AND tabla_idx=:i ORDER BY fecha"""),
            {"r": reporte_id, "h": hoja, "i": tabla_idx}).mappings().all()
    if not rows:
        raise HTTPException(404, "sin datos para esa tabla")
    dim_keys = []
    for r in rows:                       # orden estable de columnas de dimensión
        for k in (r["dims"] or {}).keys():
            if k not in dim_keys:
                dim_keys.append(k)
    meses = sorted({r["fecha"].isoformat() for r in rows})
    by_dims = {}
    for r in rows:
        dd = r["dims"] or {}
        key = tuple(dd.get(k) for k in dim_keys)
        if key not in by_dims:
            by_dims[key] = {"dims": {k: dd.get(k) for k in dim_keys}, "valores": {}}
        by_dims[key]["valores"][r["fecha"].isoformat()] = (
            float(r["valor"]) if r["valor"] is not None else None)
    filas = [{"dims": v["dims"], "valores": [v["valores"].get(m) for m in meses]}
             for v in by_dims.values()]
    return {"dimensiones": dim_keys, "meses": meses, "filas": filas}
```

### 4.6 `backend\app\main.py` — incluir el router

Agregar junto a los demás imports/include:
```python
from app.features.tablas.api import router as tablas_router
```
y, tras `app.include_router(kpis_prod_router)`:
```python
app.include_router(tablas_router)
```

### 4.7 ProdIA `routes\api.py` — 2 proxies GET (tras los proxies de ingesta)

```python
@api_bp.route("/tablas-hoja")
def tablas_hoja_listar():
    """Proxy: lista de tablas lógicas de una hoja (reporte_id, hoja)."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/tablas",
                            params={"reporte_id": request.args.get("reporte_id"),
                                    "hoja": request.args.get("hoja")}, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502

@api_bp.route("/tablas-hoja/datos")
def tablas_hoja_datos():
    """Proxy: contenido ancho de una tabla (reporte_id, hoja, tabla_idx)."""
    try:
        resp = requests.get(f"{INGESTA_API_URL}/tablas/datos",
                            params={"reporte_id": request.args.get("reporte_id"),
                                    "hoja": request.args.get("hoja"),
                                    "tabla_idx": request.args.get("tabla_idx")}, timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

### 4.8 Front `static\js\chat.js` — ítems clicables + visor

**(a)** En `renderIngestaProgress`, en la rama Core (`if (ev.tipo === "hoja" && ev.estado === "ok")`,
bloque `else` donde hoy se crea `.ingesta-analisis`), **reemplazar ese `else`** por: si llega
`ev.tablas` (caso `fact_tabla_hoja`), renderizar un encabezado + un ítem clicable por tabla; si no,
mantener la línea verde única actual.

```javascript
    } else {
      // Core: quitar "cargando…" temporal
      const p = kids.querySelector(".ingesta-avance"); if (p) p.remove();
      if (Array.isArray(ev.tablas) && ev.tablas.length) {
        if (!kids.querySelector(".ingesta-tablas")) {
          const wrap = document.createElement("div");
          wrap.className = "ingesta-tablas";
          const head = document.createElement("div");
          head.className = "text-success fw-semibold";
          head.textContent = `📊 Para análisis (${ev.tablas.length} tabla${ev.tablas.length > 1 ? "s" : ""}):`;
          wrap.appendChild(head);
          ev.tablas.forEach((t) => {
            const item = document.createElement("a");
            item.href = "#";
            item.className = "ingesta-tabla-item d-block text-primary ms-3";
            item.style.textDecoration = "none";
            item.textContent = `📄 ${t.tabla_label} · ${Number(t.filas).toLocaleString("es-CO")} filas`;
            item.addEventListener("click", (e) => {
              e.preventDefault();
              window.verTablaHoja(ev.reporte_id, ev.hoja, t.tabla_idx, t.tabla_label);
            });
            wrap.appendChild(item);
          });
          kids.appendChild(wrap);
        }
      } else if (!kids.querySelector(`.ingesta-analisis[data-tabla="${ev.tabla}"]`)) {
        const a = document.createElement("div");
        a.className = "ingesta-analisis text-success fw-semibold";
        a.dataset.tabla = ev.tabla;
        a.innerHTML = `📊 Para análisis → <span class="font-monospace">${ev.tabla}</span>${filasTxt}`;
        kids.appendChild(a);
      }
    }
```

**(b)** Agregar (nivel `window.*`, junto a las demás funciones de ingesta):

```javascript
window.verTablaHoja = async function verTablaHoja(reporteId, hoja, tablaIdx, label) {
  const area = document.getElementById("charts-display-area");
  const titleEl = document.getElementById("analytics-panel-title");
  const empty = document.getElementById("analytics-empty-state");
  if (titleEl) titleEl.textContent = `${hoja} — ${label}`;
  if (empty) empty.style.display = "none";
  if (!area) return;
  area.style.display = "block";
  area.innerHTML = '<div class="d-flex align-items-center gap-2 p-3"><div class="spinner-border spinner-border-sm"></div> Cargando tabla…</div>';
  try {
    const url = `/api/tablas-hoja/datos?reporte_id=${encodeURIComponent(reporteId)}&hoja=${encodeURIComponent(hoja)}&tabla_idx=${encodeURIComponent(tablaIdx)}`;
    const r = await fetch(url);
    const data = await r.json();
    if (!r.ok) {
      area.innerHTML = `<div class="alert alert-danger m-3">Error: ${data.error || data.detail || r.status}</div>`;
      return;
    }
    window.renderTablaAncha(area, data, `${hoja} — ${label}`);
  } catch (e) {
    area.innerHTML = `<div class="alert alert-danger m-3">Fallo de red: ${e}</div>`;
  }
};

window.renderTablaAncha = function renderTablaAncha(area, data, titulo) {
  const dims = data.dimensiones || [];
  const meses = data.meses || [];
  const fmtMes = (iso) => { const [y, m] = iso.split("-"); return `${m}/${y.slice(2)}`; };
  const fmtNum = (v) => (v == null ? "" : Number(v).toLocaleString("es-CO", { maximumFractionDigits: 1 }));
  let h = `<div class="p-2"><h6 class="fw-bold text-success mb-2">${titulo}</h6>
    <div class="table-responsive" style="max-height:72vh;overflow:auto;">
    <table class="table table-sm table-hover enhanced-table" style="font-size:.78rem;white-space:nowrap;">
    <thead class="table-light" style="position:sticky;top:0;z-index:1;"><tr>`;
  dims.forEach((d) => (h += `<th>${d}</th>`));
  meses.forEach((m) => (h += `<th class="text-end">${fmtMes(m)}</th>`));
  h += "</tr></thead><tbody>";
  (data.filas || []).forEach((f) => {
    h += "<tr>";
    dims.forEach((d) => (h += `<td>${f.dims[d] == null ? "" : f.dims[d]}</td>`));
    (f.valores || []).forEach((v) => (h += `<td class="text-end">${fmtNum(v)}</td>`));
    h += "</tr>";
  });
  h += `</tbody></table></div><div class="text-muted small mt-1">${(data.filas || []).length} filas × ${meses.length} meses</div></div>`;
  area.innerHTML = h;
};
```

## 5. Orden de ejecución

1. **Auditar** `services.py`: ubicar `_p50_contig_months`, `P50_SHEET_RE`, `load_p50_quemado` y el bloque
   hook P50 dentro de `ingerir_archivo`. Confirmar que `json` está importado (línea 10 `import re, json`).
2. Migración **§4.1** + ejecutarla en la BD (verificar **X1**). DDL maestro **§4.2** (no ejecutar).
3. `services.py`: aplicar **§4.3** (extractor+registro+loader, eliminando lo de P50 específico) y **§4.4**
   (hook nuevo).
4. Crear **§4.5** (router `tablas`) y **§4.6** (incluirlo en `main.py`).
5. ProdIA **§4.7** (2 proxies). Front **§4.8** (ítems + visor).
6. Reiniciar INGESTA :8000 y ProdIA :8020.
7. Re-ingerir el NEW-2024 por CLI para poblar `fact_tabla_hoja`:
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   $archivo=(Get-Item "..\data\20241004*New*.xlsm").FullName
   uv run python -m app.cli archivo "$archivo"
   ```
   > **Continuidad de datos (D-DROP):** el `DROP` de §4.1 borra el P50 anterior de TODOS los reportes
   > (1 y 7). Tras el DROP, `fact_tabla_hoja` solo tendrá lo que se re-ingiera. Para repoblar también el
   > STD-2023 (reporte 1), re-ingerir su archivo (rápido, ~30s):
   > `uv run python -m app.cli archivo "..\data\20231231 Reportes Diario de Producción.xlsm"`
   > (Opcional pero recomendado para no dejar reportes previos sin sus tablas.)
8. Validaciones **X1–X6**.

## 6. Validaciones (comando → esperado; reportar REAL vs esperado). `$env:PGPASSWORD='y~87z0?>Ri6w'`

- **X1 — Esquema:** `fact_tabla_hoja` existe y `fact_p50_quemado` ya NO:
  ```sql
  SELECT
    (SELECT count(*) FROM information_schema.tables WHERE table_schema='core' AND table_name='fact_tabla_hoja') AS nueva,
    (SELECT count(*) FROM information_schema.tables WHERE table_schema='core' AND table_name='fact_p50_quemado') AS vieja;
  ```
  Esperado: `nueva=1, vieja=0`.
- **X2 — Carga (reporte_id 7):**
  ```sql
  SELECT tabla_idx, tabla_label, count(*) FROM core.fact_tabla_hoja
  WHERE reporte_id=7 AND hoja='P50 Quemado 2024 ECP y Filiales' GROUP BY tabla_idx, tabla_label ORDER BY tabla_idx;
  ```
  Esperado: `1 | Tabla 1 | 1053` y `2 | Tabla 2 | 84`.
- **X3 — Spot-check dims/valor:**
  ```sql
  SELECT valor FROM core.fact_tabla_hoja
  WHERE reporte_id=7 AND hoja='P50 Quemado 2024 ECP y Filiales' AND tabla_idx=1
    AND dims->>'area'='BORANDA' AND fecha='2024-01-31';   -- esperado 141.905
  ```
- **X4 — Endpoint INGESTA (lista):**
  `curl -s "http://localhost:8000/tablas?reporte_id=7&hoja=P50%20Quemado%202024%20ECP%20y%20Filiales"`
  → JSON con 2 entradas (`Tabla 1` filas 1053, `Tabla 2` filas 84).
- **X5 — Endpoint datos (ancho) vía proxy ProdIA:**
  `curl -s "http://localhost:8020/api/tablas-hoja/datos?reporte_id=7&hoja=P50%20Quemado%202024%20ECP%20y%20Filiales&tabla_idx=1"`
  → JSON con `dimensiones=["escenario","producto","vice","activos","area"]`, `meses` (12 fechas
  2024-01-31..2024-12-31) y `filas` (~89), donde la fila de `area=BORANDA` tiene `valores[0]=141.905`.
- **X6 (manual, navegador):** http://localhost:8020 → "Análisis avanzado de producción diaria" →
  **Ctrl+F5** (JS nuevo) → subir un archivo con hoja P50. **Para una prueba rápida usar el STD-2023**
  (`20231231 Reportes Diario de Producción.xlsm`, ~30s) en vez del NEW (varios minutos) — ambos disparan
  el emit con `tablas`/`reporte_id`. Bajo la hoja `P50 Quemado <año> ECP y Filiales` ver **📊 Para
  análisis (2 tablas):** con **📄 Tabla 1** y **📄 Tabla 2** clicables → clic en Tabla 1 muestra a la
  derecha la tabla ancha (columnas de dimensión + 12 meses) con valores correctos. (El **orden** de las
  columnas de dimensión es el normalizado de JSONB, no el del Excel — ver D5; es esperado.)

## 7. Reglas no negociables

1. **No cambiar la lógica de extracción P50** (posición, meses contiguos con `to_date`, descartar
   subtotales/Promedio Año, omitir VR/GER): solo se **reempaqueta** su salida al contrato genérico
   `{tabla_idx, tabla_label, dims, fecha, valor}`.
2. **`dims` JSONB**: insertar con `json.dumps(...)` + `CAST(:dims AS jsonb)`; al leer, es `dict`.
3. **Idempotencia** por `DELETE WHERE reporte_id=? AND hoja=?` + dedup por clave natural (last-wins).
4. **No agregar imports** en `services.py` (re/json/sa/s/num/to_date ya están). Hook **dentro** del
   `with conn`, indent 8, antes de `wb.close()`.
5. **No tocar** `land_landing`, `api.py` de ingesta, otros facts, ni autenticación. El router nuevo va
   **después** de los existentes en `main.py`.
6. **Front**: solo extender `renderIngestaProgress` (rama Core) y añadir `verTablaHoja`/`renderTablaAncha`.
   No romper la línea verde única de las hojas SIN `ev.tablas` (filiales/comentarios/etc.).
7. Tras editar JS, la validación de UI requiere **Ctrl+F5**.
8. Si la auditoría revela nombres/firmas distintos, **adaptar a los reales** (no inventar).

## 8. Fuera de alcance (siguientes iteraciones)

- Persistencia (4.b): reconstruir los ítems al recargar (necesita selector de reporte / `GET /tablas`
  desde el front al abrir la vista). El endpoint `/tablas` ya queda listo para eso.
- **Orden de columnas de dimensión tipo Excel (D5):** hoy salen en orden normalizado de JSONB. Fix futuro
  barato: que `/tablas/datos` acepte `&orden=col1,col2,…` (el front lo pasa) o un mapa de orden por
  `(hoja,tabla_idx)`; **no** prefijar claves (ensuciaría `dims->>'…'`).
- Gráficos a partir de la tabla; export; otras hojas (Bitácora, Balance de blancos) → cada una = un
  `_xxx_extract` + 1 línea en `HOJAS_MODELADAS`.
- Migrar datos previos de `fact_p50_quemado` (se regeneran re-ingiriendo; el DROP los elimina).
```
