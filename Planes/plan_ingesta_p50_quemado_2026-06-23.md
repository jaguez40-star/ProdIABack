# Plan ejecutable v2 — Ingesta de la hoja "P50 Quemado … ECP y Filiales" (2 tablas) → `core.fact_p50_quemado`

> Modo: **plan:** (para un executor sin contexto del repo). Rutas absolutas, código completo,
> decisiones cerradas, criterios verificables. **Versión auditada v2** — ver §0.

---

## 0. Hallazgos de auditoría (verificados contra el CÓDIGO y los DATOS reales)

### 0.a Auditoría de datos (openpyxl `data_only`, solo lectura)
- **A1 — La hoja existe en los 3 archivos legibles, con nombre variable por año.** `20231231…xlsm`
  → `P50 Quemado 2023 ECP y Filiales`; `20240211…xlsm` y `20241004…xlsm` → `P50 Quemado 2024 ECP y Filiales`.
  ⇒ **NO hardcodear "2024"**; casar por patrón `^P50 Quemado \d{4} ECP y Filiales$`.
- **A2 — Las 2 tablas están en posición idéntica** en los 3 archivos: Tabla 1 (`ESCENARIO`) fila 2 col A;
  Tabla 2 (título `P50 Filiales`) fila 3 col T (20).
- **A3 — Los 12 meses tienen valores reales** en los 3 archivos (incl. STD/pivote). Spot:
  BORANDA ene/2024=141.905, Crudo·Hocol ene/2024=22967.
- **A4 — Tabla 2 y Tabla 3 (VR/GER) comparten la fila de encabezado** → un barrido por rango fijo se
  cuela en la Tabla 3. **Solución obligatoria:** barrer meses **contiguos** y cortar en la 1ª no-fecha.
- **A5 — Las fechas válidas están en la fila 2 / título+1**, NO en la fila 1 (números de día `31 29…`).

### 0.b Auditoría de código (cruce del plan v1 contra `services.py`, `cli.py`, DDL — corregido en v2)
- **B1 — Re-iteración `read_only`: SEGURA (verificado).** `land_landing` ya itera la hoja P50; el loader
  la vuelve a iterar. Test real: 1ª=151, 2ª(mismo ws)=151, 3ª(fresco)=151 filas. ⇒ sin cambios extra.
- **B2 — Imports: NO se agrega nada.** `re` (línea 10), `sa` (14), y `s/num/to_date` (26) **ya están
  importados**. El plan v1 proponía `from datetime import …` que **chocaba** con `import datetime as dt`
  (línea 11). **Corrección v2:** reutilizar el helper del repo **`to_date`** (maneja int `YYYYMMDD`,
  `datetime`, y `"20240930.0"`) y **eliminar** el `_p50_to_date` propio. Cero imports nuevos.
- **B3 — DDL: NO ejecutar el archivo completo.** `ddl_v2_postgres.sql` usa `CREATE TABLE` **sin**
  `IF NOT EXISTS` (línea 45 `CREATE TABLE bronze.bdp_datos_dia`…). Correrlo entero **falla** por objetos
  existentes. **Corrección v2:** crear migración `db/migrations/002_fact_p50_quemado.sql` (convención del
  repo, ya existe `001_ingesta_job.sql`) y ejecutar **solo esa**; además append al `.sql` maestro para
  instalaciones nuevas.
- **B4 — Ubicación del hook: DENTRO del `with get_engine().begin() as conn:`.** En `services.py` el
  último bloque del `with` es el de `INICIO` (líneas 499-506); `wb.close()` (línea 508, indent 4) está
  **fuera** del `with`. El plan v1 decía "antes de `wb.close()`" → ambiguo y **riesgoso** (pondría el hook
  fuera de la transacción, con `conn` cerrado). **Corrección v2:** insertar **tras la línea 506**
  (después del `_emit` de INICIO), a **8 espacios** de indentación, como último bloque del `with`.
- **B5 — Idempotencia y duplicados: dedup defensivo.** La Tabla 1 tiene filas que **repiten la clave
  natural** (mismo escenario/producto/vice/activos/area en los 12 meses: 12 colisiones en NEW-2024). Sin
  dedup, el `INSERT` violaría `uk_p50` y **abortaría la ingesta**. **Corrección v2:** el loader acumula en
  un dict por clave natural (**last-wins**) antes de insertar. Idempotencia entre corridas = `DELETE
  WHERE reporte_id=?` + `INSERT`.
- **B6 — CLI confirmado:** `cli.py` soporta `python -m app.cli archivo <ruta>` (línea 10-11). La firma de
  orquestación es `ingerir_archivo(path, progress_cb=None)`; `_log_ingesta(conn, reporte_id, hoja,
  destino, leidas, ins, …)` (firma usada por el hook, correcta).

### 0.c Conteos esperados — RE-SIMULADOS con `to_date` + dedup (autoridad de validación)
| Archivo | quemado | filiales | TOTAL |
|---|---|---|---|
| 20231231 (STD-2023) | 1063 | 84 | **1147** |
| 20240211 (STD-2024) | 1053 | 84 | **1137** |
| 20241004 (NEW-2024, reporte_id 7) | **1053** | **84** | **1137** |

---

## 1. Contexto

Proyecto **INGESTA / Rep_Prod** (FastAPI + SQLAlchemy Core + PostgreSQL, Medallion bronze/core). ETL en
`c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`.
Hoy la hoja "P50 Quemado … ECP y Filiales" **solo cae en `bronze.hoja_landing`** y **pierde el detalle
mensual** (su encabezado son números de día duplicados que colapsan las 12 columnas). Este plan agrega un
loader que ingiere **2 de sus 3 tablas** a una tabla Core nueva, limpia, leyendo **por posición**.

Decisiones cerradas del dueño: **(1) descartar subtotales**, **(2) omitir "Promedio Año"**, **(3) omitir
la Tabla 3 (VR/GER)**, **(4) una sola tabla Core con discriminador `tabla`**.

## 2. Objetivo

1. Crear `core.fact_p50_quemado` (migración + append al DDL maestro).
2. Agregar `load_p50_quemado(conn, ws, reporte_id)` en `services.py` y engancharlo en `ingerir_archivo`,
   emitiendo el destino Core (línea verde en la UI).
3. Resultado: al ingerir cualquier archivo con la hoja P50 (NEW o STD), sus 2 tablas quedan en
   `core.fact_p50_quemado` en formato largo (una fila por celda mensual), idempotente.

## 3. Prerequisitos (si alguno falla, DETENERSE y reportar)

- **P1** — Existe `…\backend\app\features\ingesta\services.py`.
- **P2** — Existe `…\db\ddl_v2_postgres.sql` y la carpeta `…\db\migrations\` (con `001_ingesta_job.sql`).
- **P3** — BD (de `INGESTA\Rep_Prod\.env`): host `10.100.26.139`, puerto `5432`, db `daily_report_prod`,
  user `postgres`, pass `y~87z0?>Ri6w`. `core.config_reporte` ya tiene `reporte_id` 1 (STD-2023) y 7
  (NEW-2024). En PowerShell la pass lleva `>` → usar `$env:PGPASSWORD`, nunca inline.
- **P4** — `uv` instalado; backend se levanta con
  `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000` (reiniciar tras editar).
- **P5** — Existe `…\data\20241004_Reporte New Diario de Producción.xlsm`.

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\db\migrations\002_fact_p50_quemado.sql` | **CREAR** (DDL de la tabla) y **EJECUTAR** en la BD del 139. |
| `…\db\ddl_v2_postgres.sql` | **MODIFICAR**: append del mismo `CREATE TABLE` (para instalaciones nuevas). |
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: loader `load_p50_quemado` + hook en `ingerir_archivo`. |

**NO se toca:** `api.py`, frontend, `land_landing`, imports (ya están), ni la lógica/claves de los demás
facts. La hoja sigue cayendo en `bronze.hoja_landing` (respaldo); este plan **solo añade** el destino Core.

## 5. Especificación (código completo)

### 5.1 Migración — crear `db\migrations\002_fact_p50_quemado.sql` con este contenido exacto

```sql
-- 002_fact_p50_quemado.sql
-- P50 Quemado: 2 tablas de la hoja "P50 Quemado <año> ECP y Filiales", formato largo (unpivot 12 meses).
--   tabla='quemado'  -> dims: escenario, producto, vice, activos, area
--   tabla='filiales' -> dims: producto, empresa  (vice/activos/area NULL)
-- Subtotales y "Promedio Año" NO se ingieren (decisión del proyecto).
CREATE TABLE IF NOT EXISTS core.fact_p50_quemado (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id  INTEGER NOT NULL REFERENCES core.config_reporte(reporte_id),
    tabla       TEXT    NOT NULL,           -- 'quemado' | 'filiales'
    escenario   TEXT,
    producto    TEXT,
    vice        TEXT,
    activos     TEXT,
    area        TEXT,
    empresa     TEXT,
    fecha       DATE    NOT NULL,
    valor       NUMERIC,
    CONSTRAINT uk_p50 UNIQUE NULLS NOT DISTINCT
        (reporte_id, tabla, escenario, producto, vice, activos, area, empresa, fecha)
);
CREATE INDEX IF NOT EXISTS ix_p50_reporte ON core.fact_p50_quemado (reporte_id);
```

> `UNIQUE … NULLS NOT DISTINCT` requiere PostgreSQL ≥ 15 (servidor 139 = PG18 → OK).

**Ejecutar SOLO la migración** (no el DDL maestro completo — B3):
```powershell
$env:PGPASSWORD='y~87z0?>Ri6w'
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 10.100.26.139 -U postgres -d daily_report_prod `
  -v ON_ERROR_STOP=1 -f "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\db\migrations\002_fact_p50_quemado.sql"
```
Si `psql.exe` no está en esa ruta, ejecutar la migración vía `psycopg`:
```powershell
cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
uv run --with "psycopg[binary]" python -c "import psycopg; c=psycopg.connect(host='10.100.26.139',port=5432,dbname='daily_report_prod',user='postgres',password='y~87z0?>Ri6w',sslmode='disable'); c.execute(open(r'..\db\migrations\002_fact_p50_quemado.sql',encoding='utf-8').read()); c.commit(); print('migracion 002 OK')"
```

### 5.2 DDL maestro — append a `db\ddl_v2_postgres.sql`

Agregar al **final** del archivo (sección core) el **mismo** bloque `CREATE TABLE core.fact_p50_quemado
(…)` + `CREATE INDEX …` de §5.1 (sin el comentario de cabecera de la migración). Solo es para
instalaciones nuevas; **no** se ejecuta aquí.

### 5.3 Loader — agregar a `services.py`

**NO agregar imports** (`re`, `sa`, `s`, `num`, `to_date` ya están importados — B2). Colocar la función
cerca de los demás `load_*`, **antes** de `def ingerir_archivo(`. Pegar tal cual:

```python
P50_SHEET_RE = re.compile(r"(?i)^P50 Quemado \d{4} ECP y Filiales$")

def _p50_contig_months(grid, hdr_row, start_col):
    """Columnas de mes CONTIGUAS desde start_col en hdr_row; corta en la 1ª no-fecha.
    Crítico (auditoría A4): evita cruzar a la tabla VR/GER que comparte fila de encabezado.
    Usa to_date (helper del repo): int YYYYMMDD / datetime / '20240930.0' -> date; otro -> None."""
    out, c = [], start_col
    while True:
        d = to_date(grid.get((hdr_row, c)))
        if d is None:
            break
        out.append((c, d))
        c += 1
    return out

def load_p50_quemado(conn, ws, reporte_id):
    """Ingiere las 2 tablas de la hoja P50 a core.fact_p50_quemado (formato largo).
    Lee por POSICIÓN (no por encabezado). Descarta subtotales y 'Promedio Año'. Idempotente.
    Deduplica por clave natural (last-wins) para no violar uk_p50 (auditoría B5)."""
    # Materializar la hoja (pequeña: <160 filas, ~50 cols)
    grid, maxr = {}, 0
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for c, v in enumerate(row, start=1):
            if v is not None and str(v).strip() != "":
                grid[(r, c)] = v
                if r > maxr:
                    maxr = r
        if r > 250:
            break

    # dict por clave natural -> fila (last-wins). Clave = (tabla,esc,prod,vice,activos,area,empresa,fecha)
    by_key = {}

    # ----- TABLA 1: 'quemado'. dims A:E (1..5); meses contiguos desde F(6) con fechas en fila 2 -----
    m1 = _p50_contig_months(grid, 2, 6)
    for r in range(3, maxr + 1):
        area = grid.get((r, 5))
        if area is None or str(area).strip().lower().startswith("total"):
            continue  # subtotales no tienen AREA o su rótulo empieza por 'Total' -> descartar
        escenario = s(grid.get((r, 1))); producto = s(grid.get((r, 2)))
        vice = s(grid.get((r, 3))); activos = s(grid.get((r, 4))); area_v = s(area)
        for c, d in m1:
            val = num(grid.get((r, c)))
            if val is None:
                continue
            key = ("quemado", escenario, producto, vice, activos, area_v, None, d)
            by_key[key] = {"tabla": "quemado", "escenario": escenario, "producto": producto,
                           "vice": vice, "activos": activos, "area": area_v, "empresa": None,
                           "fecha": d, "valor": val, "rep": reporte_id}

    # ----- TABLA 2: 'filiales'. título 'P50 Filiales'; dims Producto/VICE(vacío)/Empresa -----
    title = next(((r, c) for (r, c), v in grid.items()
                  if isinstance(v, str) and v.strip().lower() == "p50 filiales"), None)
    if title:
        tr, tc = title
        hdr = tr + 1                          # encabezado: Producto | VICE | Empresa | fechas…
        col_prod, col_emp = tc, tc + 2        # Producto = tc ; Empresa = tc+2 ; VICE (tc+1) viene vacío
        m2 = _p50_contig_months(grid, hdr, tc + 3)   # meses contiguos tras las 3 dims; corta en 'Promedio Año'
        for r in range(hdr + 1, maxr + 1):
            empresa = grid.get((r, col_emp))
            if empresa is None:
                continue  # subtotales ('Total Crudo'…/'Total general') no tienen Empresa -> descartar
            producto = grid.get((r, col_prod))
            if producto and str(producto).strip().lower().startswith("total"):
                continue
            prod_s, emp_s = s(producto), s(empresa)
            for c, d in m2:
                val = num(grid.get((r, c)))
                if val is None:
                    continue
                key = ("filiales", None, prod_s, None, None, None, emp_s, d)
                by_key[key] = {"tabla": "filiales", "escenario": None, "producto": prod_s,
                               "vice": None, "activos": None, "area": None, "empresa": emp_s,
                               "fecha": d, "valor": val, "rep": reporte_id}

    # ----- Idempotencia: borrar lo previo de este reporte e insertar lo deduplicado -----
    conn.execute(sa.text("DELETE FROM core.fact_p50_quemado WHERE reporte_id = :rep"),
                 {"rep": reporte_id})
    out = list(by_key.values())
    if out:
        conn.execute(sa.text("""
            INSERT INTO core.fact_p50_quemado
                (reporte_id, tabla, escenario, producto, vice, activos, area, empresa, fecha, valor)
            VALUES (:rep, :tabla, :escenario, :producto, :vice, :activos, :area, :empresa, :fecha, :valor)
        """), out)
    return len(out)
```

### 5.4 Hook en la orquestación `ingerir_archivo` (ubicación EXACTA — B4)

Insertar **inmediatamente después del bloque `if "INICIO" in wb.sheetnames:`** (justo tras el `_emit({…
"tabla": "fact_promedio_validado" …})`) y **antes** de la línea `wb.close()`. Debe quedar a **8 espacios**
de indentación, es decir **DENTRO** del `with get_engine().begin() as conn:` (mismo nivel que el bloque
`if "INICIO"…`). NO ponerlo después de `wb.close()`.

```python
        # ---- P50 Quemado (2 tablas -> core.fact_p50_quemado) ----
        p50_sheet = next((sh for sh in wb.sheetnames if P50_SHEET_RE.match(sh)), None)
        if p50_sheet:
            n = load_p50_quemado(conn, wb[p50_sheet], reporte_id)
            _log_ingesta(conn, reporte_id, p50_sheet, "core.fact_p50_quemado", n, n)
            filas["fact_p50_quemado"] = n
            log.info("ingesta.p50", hoja=p50_sheet, filas=n)
            _emit({"tipo": "hoja", "hoja": p50_sheet, "estado": "ok",
                   "tabla": "fact_p50_quemado", "filas": n})
```

> `_emit`, `_log_ingesta`, `filas`, `reporte_id`, `conn`, `wb`, `log` ya existen en esa función (mismos
> que usan los bloques COMENTARIOS/FILIALES/INICIO). La hoja P50 seguirá cayendo en `bronze.hoja_landing`
> por el loop de landing (no se toca); este hook solo AÑADE el destino Core → en la UI aparecerán dos
> líneas bajo la hoja: 🗄️ Respaldo (Bronze) y 📊 Para análisis → `fact_p50_quemado` (Core).

## 6. Orden de ejecución

1. **Auditar** `services.py`: confirmar que la función de orquestación es `ingerir_archivo(path,
   progress_cb=None)`, que el último bloque del `with get_engine().begin() as conn:` es `if "INICIO"…`
   (líneas ~499-506) y que `wb.close()` está fuera del `with`. Verificar Prerequisitos §3; si P1/P2/P3
   fallan, DETENERSE.
2. Crear y ejecutar la **migración §5.1** en la BD del 139. Verificar **X1**.
3. Append del DDL maestro **§5.2** (no ejecutar).
4. Agregar **§5.3** (loader, sin imports nuevos) y **§5.4** (hook, indentación 8 espacios dentro del `with`).
5. Reiniciar el backend FastAPI.
6. Re-ingerir el archivo NEW-2024 (idempotente) para poblar `reporte_id` 7:
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm"
   ```
7. Ejecutar validaciones **X2–X5**.

## 7. Validaciones (comando → esperado; reportar REAL vs esperado). `$env:PGPASSWORD='y~87z0?>Ri6w'`

- **X1 — Tabla creada:**
  ```sql
  SELECT count(*) FROM information_schema.tables
  WHERE table_schema='core' AND table_name='fact_p50_quemado';   -- esperado 1
  ```
- **X2 — Conteo tras ingerir NEW-2024 (reporte_id 7):**
  ```sql
  SELECT tabla, count(*) FROM core.fact_p50_quemado WHERE reporte_id=7 GROUP BY tabla ORDER BY tabla;
  ```
  Esperado: `filiales = 84`, `quemado = 1053` (TOTAL **1137**).
- **X3 — Spot-checks (deben coincidir con el Excel):**
  ```sql
  SELECT valor FROM core.fact_p50_quemado
   WHERE reporte_id=7 AND tabla='quemado' AND area='BORANDA' AND fecha='2024-01-31';   -- esperado 141.905
  SELECT valor FROM core.fact_p50_quemado
   WHERE reporte_id=7 AND tabla='filiales' AND producto='Crudo' AND empresa='Hocol' AND fecha='2024-01-31'; -- 22967
  ```
- **X4 — Subtotales descartados y 12 meses exactos:**
  ```sql
  SELECT count(*) FROM core.fact_p50_quemado
   WHERE reporte_id=7 AND (lower(coalesce(area,'')) LIKE 'total%' OR lower(coalesce(producto,'')) LIKE 'total%'); -- 0
  SELECT count(DISTINCT fecha) FROM core.fact_p50_quemado WHERE reporte_id=7;   -- esperado 12
  ```
- **X5 — Idempotencia:** repetir el paso 6 y volver a correr X2 → conteos **idénticos** (1053/84), sin duplicar.
- **X6 (manual, opcional):** http://localhost:8020 → "Análisis avanzado de producción diaria" → subir el
  NEW → bajo la hoja `P50 Quemado 2024 ECP y Filiales` deben verse **dos líneas**: 🗄️ Respaldo y
  📊 Para análisis → `fact_p50_quemado`. (Requiere el front de carga manual ya desplegado; si no, omitir.)

## 8. Reglas no negociables

1. **Leer por posición, no por encabezado.** Tabla 1 dims = A:E (1..5), meses contiguos desde F(6) con
   fechas de la **fila 2**. Tabla 2 = localizar título `P50 Filiales`, encabezado en la fila siguiente,
   dims Producto(tc)/VICE(tc+1, vacío)/Empresa(tc+2), meses contiguos desde tc+3.
2. **Barrido de meses CONTIGUO con corte en la 1ª no-fecha** (A4). Prohibido rangos de columnas fijos que
   crucen a la tabla VR/GER. Usar el helper **`to_date`** del repo (no reimplementar parseo de fechas).
3. **Ignorar la fila 1** (números de día). **Descartar subtotales** (sin AREA/sin Empresa, o rótulo
   `Total…`) y **omitir "Promedio Año"** (el barrido contiguo ya lo excluye). **No** ingerir la Tabla 3.
4. **No hardcodear el año** (usar `P50_SHEET_RE`). **No agregar imports** (ya existen).
5. **Hook DENTRO del `with conn`** (8 espacios), nunca tras `wb.close()`.
6. **Deduplicar por clave natural (last-wins)** antes de insertar; idempotencia por `DELETE WHERE
   reporte_id=?` en la misma transacción `conn`.
7. **No modificar** `land_landing`, `api.py`, el frontend, ni la lógica/claves de los demás facts. Único
   cambio al ETL: tabla nueva + loader + hook + 1 emit.
8. **No ejecutar el DDL maestro completo** (rompe por objetos existentes); solo la migración 002.
9. Si la auditoría del paso 1 revela nombres/firmas distintos, **adaptar a los reales** (no inventar).

## 9. Fuera de alcance

- Tabla 3 (VR/GER), columna "Promedio Año", botones/gráficos sobre `fact_p50_quemado`.
- Corregir el landing genérico para otras hojas anchas (otro plan).
- Archivos cifrados de `data\Prot\`.
```
