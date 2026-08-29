# Plan ejecutable v2 — Extender `COMENTARIOS`: preservar los 3 campos (E y G) + forward-fill

> **Cobertura: campos de comentario `entrada 3 → salida 3`** (hoy sale 1; se restauran `E`=COMENTARIO
> PROGRAMA y `G`=comentario extra) **+ forward-fill de `producto`**. Tabla: **1 → 1**. Decisión del dueño
> **D-coment-1 = Opción B (extender)**.
>
> Modo: **plan:** (executor sin contexto del repo). **Auditado v2** contra el CÓDIGO real, el DDL real, la
> BD dev en vivo y 3 archivos del corpus. Las decisiones de la v1 que el flujo profesional corrigió están en
> §0.e (orden físico de columnas, dependencia de orden migración↔ETL, backfill).

---

## 0. Hallazgos de auditoría (verificados contra CÓDIGO, DDL, BD viva y DATOS reales)

### 0.a Estructura de la hoja (estable en 3 archivos: STD-2023, STD-2024, NEW-2024)
- **1 sola tabla**, rango `A1:G106`, sin PivotTables/ListObjects, nada más allá de col G ni debajo de f106.
  Continua con categoría en col A: `CRUDO` (f2–58), `GAS` (f59–85), `BLANCOS` (f86–106), sin sub-encabezados
  ni subtotales intermedios.
- **Header f1:** `A=PRODUCTO · B=ACTIVOS · C=AREA · (D sin header) · E=COMENTARIO PROGRAMA`.
- **3 campos de texto distintos** (contenido real, NO duplicados):
  | Col | idx | Campo | Evidencia (f105, BLANCOS/CUPIAGUA) |
  |---|---|---|---|
  | `D` | 3 | comentario real/operativo | `"Venta total de GLP 7250.57 Bbls."` |
  | `E` | 4 | **COMENTARIO PROGRAMA** | `"Entregas de GLP de acuerdo a requerimiento de clientes."` |
  | `G` | 6 | comentario extra (disperso: f4/f41/f43) | `"En estabilización de producción posterior…"` |
- Celdas D/E/G: mezcla de fórmulas (0 `#¡REF!`) y texto literal → `data_only=True` da los valores cacheados;
  `s()` ya trata `#¡REF!`/`#N/A`/`(en blanco)` como None.
- **Fila con A en blanco** y comentario real (NEW f44: `B=OPERADOS, C=CAPACHOS`) ⇒ **forward-fill** de col A.

### 0.b Gaps del modelo actual (lo que se corrige)
`load_comentarios` hoy: `comentario = s(row[3]) or s(row[4])`, ignora `G`, sin forward-fill:
1. **Pierde `E`** cuando `D≠E` (2 filas/archivo; contenido real, casos GLP).
2. **Ignora `G`** (3 comentarios/archivo).
3. **Sin forward-fill** de `producto` (fila con A en blanco entra con `tipo_producto_id` NULL).
4. 🐛 **Bug `"0"`:** `s("0")="0"` es *truthy* → una fila con `D="0"` y `E` real se **descarta**. El extractor
   nuevo trata `"0"` como vacío y la **recupera** (explica el +1 en NEW-2024).

### 0.c Auditoría de código/DDL/BD viva
- **Tabla** `core.fact_comentarios_produccion` (BD dev `daily_report_prod`, user `robustez`,
  `localhost:5432`). Columnas **actuales** (verificadas en vivo, en este orden físico):
  `id, tipo_producto_id, activos, area, comentario(NOT NULL), reporte_id(NOT NULL)`. **Sin UNIQUE** →
  idempotencia por `DELETE WHERE reporte_id=?` + INSERT (ya implementado). **Aún NO tiene** las 2 columnas
  nuevas.
- **`comentario` es NOT NULL** ⇒ principal con cadena de respaldo `D→E→G`. Columnas nuevas **nullable**.
- **FK `tipo_producto_id` admite NULL** → el forward-fill resuelve `producto`; aunque no resolviera, no
  rompe la FK.
- **Único lector/escritor de la tabla en el código = `load_comentarios`** (INSERT con **columnas
  nombradas**) + su `DELETE`. **No existe ningún `SELECT *`** ni acceso posicional en la app → añadir
  columnas es **aditivo y seguro**; el cambio de conteo (+1) **no rompe** ningún test (los tests son
  `_resolver_nombre`/`transforms`/`health`, ninguno asserta comentarios).
- **No hay runner de migraciones ni Alembic**: las migraciones `db/migrations/00N_*.sql` (existen 001–004)
  se aplican **a mano con `psql`**. La nueva es **`005`**.

### 0.d Conteos esperados (autoridad de validación) — verificados por prototipo en 3 archivos
| Archivo (reporte_id) | filas nuevo | filas actual | `comentario_programa` no-NULL (≠ comentario) | `comentario_extra` no-NULL | forward-fill | `tipo_producto_id` NULL |
|---|---|---|---|---|---|---|
| STD-2023 (rep 3) | 31 | 31 | 30 (2) | 3 | 1 | 0 |
| STD-2024 | 24 | 24 | 24 (2) | 3 | 1 | 0 |
| **NEW-2024 (rep 4)** | **35** | 34 | **31 (2)** | **3** | **1** | **0** |

Spot-checks (NEW-2024): f105 `BLANCOS/CUPIAGUA` → `comentario="Venta total de GLP 7250.57 Bbls."`,
`comentario_programa="Entregas de GLP de acuerdo a requerimiento de clientes."`. Fila `OPERADOS/CAPACHOS`
(A en blanco) → `producto` forward-filled a **CRUDO**.

### 0.e 🔧 Correcciones del flujo profesional aplicadas (incoherencias v1 → v2)
1. **Orden físico de columnas:** `ALTER ADD COLUMN` **anexa al final** (tras `reporte_id`). La v1 las ponía
   a media tabla en el DDL canónico → BD migrada ≠ BD fresca. **v2: el DDL canónico las coloca DESPUÉS de
   `reporte_id`** para que ambos caminos den el **mismo orden físico**. (Hoy no hay `SELECT *`, así que es
   cosmético, pero se alinea para evitar deuda futura.)
2. **Dependencia de orden (crítica):** el ETL nuevo hace `INSERT` con las 2 columnas → **la migración 005
   DEBE aplicarse ANTES de desplegar/reiniciar el ETL nuevo**, o el `INSERT` falla por columna inexistente.
   Se fija como regla no negociable y como secuencia en §6.
3. **Backfill:** tras migrar, las filas ya ingeridas (rep 3 y 4) tendrán `comentario_programa`/`extra` en
   **NULL** hasta **re-ingerir** esos archivos (no es error, es estado pre-backfill). §6 lo hace explícito.

---

## 1. Contexto

Proyecto **INGESTA / Rep_Prod** (FastAPI + SQLAlchemy Core + PostgreSQL). ETL en
`C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`.
`COMENTARIOS` ya se ingiere a `core.fact_comentarios_produccion`, pero con 1 de sus 3 campos. Este plan
**extiende** tabla + ETL para preservar `E` y `G` y hacer forward-fill de `producto`. **No** crea tabla ni
usa `fact_tabla_hoja` (su `valor` es numérico; estos son textos).

## 2. Objetivo

1. **DDL:** +2 columnas nullable (`comentario_programa`, `comentario_extra`) vía **migración idempotente
   `005`** (BD existentes) **y** `CREATE TABLE` canónico (instalaciones nuevas), **con el mismo orden físico**.
2. **ETL:** reescribir `load_comentarios` (poblar los 3 campos + forward-fill + `"0"`/ruido = vacío).
3. Resultado idempotente; las filas re-ingeridas llevan los 3 campos.

## 3. Prerequisitos (si alguno falla, DETENERSE y reportar)

- **P1** — `…\backend\app\features\ingesta\services.py` con `load_comentarios(conn, ws, reporte_id, tipo_cache)`
  y el helper `s` (de `app.shared.utils`).
- **P2** — Tabla `core.fact_comentarios_produccion` existente (esquema §0.c). BD de `INGESTA\Rep_Prod\.env`
  (`DATABASE_URL`) — **dev = `daily_report_prod` local, user `robustez`**.
- **P3** — `psql.exe` (`C:\Program Files\PostgreSQL\18\bin\`). **Contraseña vía `$env:PGPASSWORD` leída del
  `.env`, nunca inline.**
- **P4** — `uv`; backend `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000`.
- **P5** — ≥1 `.xlsm` con `COMENTARIOS` (p.ej. `20241004_Reporte New…xlsm`).

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `INGESTA\Rep_Prod\db\migrations\005_fact_comentarios_extra.sql` | **CREAR** (migración idempotente). |
| `INGESTA\Rep_Prod\db\ddl_v2_postgres.sql` | **MODIFICAR** (CREATE TABLE: +2 columnas DESPUÉS de `reporte_id`). |
| `INGESTA\Rep_Prod\backend\app\features\ingesta\services.py` | **MODIFICAR** (`_coment_cell` + reescribir `load_comentarios`). |

**NO se toca:** otras tablas/extractores, `api.py`, frontend, ni la firma/invocación de `load_comentarios`.

## 5. Especificación (código completo)

### 5.1 Migración — crear `db\migrations\005_fact_comentarios_extra.sql`

```sql
-- 005: extiende core.fact_comentarios_produccion con los 2 campos de comentario adicionales de la hoja
-- COMENTARIOS (E = COMENTARIO PROGRAMA, G = comentario extra). Idempotente y re-ejecutable.
ALTER TABLE core.fact_comentarios_produccion
    ADD COLUMN IF NOT EXISTS comentario_programa text,
    ADD COLUMN IF NOT EXISTS comentario_extra    text;
```

### 5.2 DDL canónico — `db\ddl_v2_postgres.sql`

En el `CREATE TABLE core.fact_comentarios_produccion (...)`, insertar las 2 columnas **inmediatamente
DESPUÉS de la línea `reporte_id … NOT NULL,`** y **antes** del primer `FOREIGN KEY` (así el orden físico
coincide con el que produce el `ALTER` de §5.1):

```sql
    comentario          TEXT           NOT NULL,
    reporte_id          INT            NOT NULL,
    comentario_programa TEXT,
    comentario_extra    TEXT,
    FOREIGN KEY (tipo_producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (reporte_id)       REFERENCES core.config_reporte(reporte_id)
```

### 5.3 ETL — `services.py`: añadir `_coment_cell` y reemplazar `load_comentarios`

Colocar `_coment_cell` **inmediatamente antes** de `load_comentarios` y sustituir la función completa
(misma firma; sin imports nuevos — `s` ya está importado):

```python
def _coment_cell(row, i):
    """Celda de comentario en posición i: limpia ruido (#REF!/#N/A/(en blanco)) y trata '0' como vacío."""
    v = s(row[i]) if len(row) > i else None
    return None if v == "0" else v


def load_comentarios(conn, ws, reporte_id, tipo_cache):
    """'COMENTARIOS' -> core.fact_comentarios_produccion. 1 tabla continua (CRUDO/GAS/BLANCOS x activos x
    area) con 3 campos de texto: D=comentario (real), E=comentario_programa (COMENTARIO PROGRAMA, header f1),
    G=comentario_extra (disperso). Forward-fill de PRODUCTO (col A dispersa, p.ej. fila con A en blanco).
    'comentario' (NOT NULL) usa la cadena de respaldo D->E->G. Trata '0' y ruido como vacío (corrige el bug
    de cortocircuito '0' del modelo previo). Idempotente: DELETE por reporte_id + INSERT (sin UNIQUE)."""
    conn.execute(sa.text("DELETE FROM core.fact_comentarios_produccion WHERE reporte_id=:r"), {"r": reporte_id})
    stmt = sa.text("""INSERT INTO core.fact_comentarios_produccion
                      (tipo_producto_id, activos, area, comentario, comentario_programa, comentario_extra, reporte_id)
                      VALUES (:t, :a, :ar, :c, :cp, :ce, :r)""")
    buf, total, producto = [], 0, None
    it = ws.iter_rows(values_only=True); next(it, None)        # salta el encabezado (fila 1)
    for row in it:
        if row is None or len(row) < 4:
            continue
        a = s(row[0])
        if a:
            producto = a                                       # forward-fill del PRODUCTO (col A dispersa)
        com   = _coment_cell(row, 3)                           # D  comentario real
        prog  = _coment_cell(row, 4)                           # E  COMENTARIO PROGRAMA
        extra = _coment_cell(row, 6)                           # G  comentario extra (disperso)
        principal = com or prog or extra                       # comentario es NOT NULL -> respaldo D->E->G
        if not principal:
            continue
        buf.append({"t": tipo_cache.get(producto), "a": s(row[1]), "ar": s(row[2]),
                    "c": principal, "cp": prog, "ce": extra, "r": reporte_id})
        total += 1
    if buf:
        conn.execute(stmt, buf)
    return total
```

## 6. Orden de ejecución (la SECUENCIA importa — ver §0.e.2)

1. **Auditar** `services.py`: confirmar firma de `load_comentarios` y su invocación en `ingerir_archivo`
   (línea ~1023). Verificar §3; si P1/P2 fallan, DETENERSE.
2. **PRIMERO la migración 005** (idempotente) sobre la BD destino — ANTES de tocar el ETL:
   ```powershell
   # $env:PGPASSWORD leído de INGESTA\Rep_Prod\.env (NO inline)
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -U robustez -d daily_report_prod `
       -f "C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\db\migrations\005_fact_comentarios_extra.sql"
   ```
   (En prod: `-h 10.100.26.139 -U postgres`; la pass del bloque 139 del `.env`.)
3. Aplicar **§5.2** (DDL canónico) y **§5.3** (ETL). *(El ETL nuevo solo funciona si el paso 2 ya corrió.)*
4. **Tests:** `cd INGESTA\Rep_Prod\backend; uv run pytest -q` → **verde** (sin regresión).
5. Reiniciar el backend FastAPI.
6. **Re-ingerir** para poblar las nuevas columnas (idempotente). El archivo NEW (rep 4):
   ```powershell
   cd "C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm"
   ```
   **Backfill (§0.e.3):** repetir el `archivo` para **cada `.xlsm` ya ingerido con `COMENTARIOS`** (p.ej. el
   STD que dejó rep 3) para que sus filas dejen de tener `comentario_programa`/`extra` en NULL.
7. Ejecutar validaciones **X1–X6**.

## 7. Validaciones (comando → esperado). `<HOST>`=127.0.0.1 (dev); `<REP>`=reporte_id del NEW

- **X1 — columnas creadas (y al final del orden físico):**
  ```sql
  SELECT ordinal_position, column_name FROM information_schema.columns
   WHERE table_schema='core' AND table_name='fact_comentarios_produccion'
     AND column_name IN ('comentario_programa','comentario_extra') ORDER BY ordinal_position;
  -- esperado: 2 filas, posiciones 7 y 8 (después de reporte_id)
  ```
- **X2 — conteos (NEW, reporte_id=<REP>):**
  ```sql
  SELECT count(*) total, count(comentario_programa) prog, count(comentario_extra) extra,
         count(*) FILTER (WHERE tipo_producto_id IS NULL) sin_producto
    FROM core.fact_comentarios_produccion WHERE reporte_id=<REP>;
  -- esperado: total=35, prog=31, extra=3, sin_producto=0
  ```
- **X3 — spot-check D≠E (programa preservado):**
  ```sql
  SELECT comentario, comentario_programa FROM core.fact_comentarios_produccion
   WHERE reporte_id=<REP> AND area='CUPIAGUA (BLANCOS)';
  -- comentario ~ 'Venta total de GLP 7250.57 Bbls.' ; comentario_programa ~ 'Entregas de GLP ...'
  ```
- **X4 — forward-fill de producto:**
  ```sql
  SELECT tp.nombre, c.activos, c.area FROM core.fact_comentarios_produccion c
    JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id=c.tipo_producto_id
   WHERE c.reporte_id=<REP> AND c.area='CAPACHOS';   -- nombre esperado: CRUDO (no NULL)
  ```
- **X5 — comentario_extra (G):** `… WHERE reporte_id=<REP> AND comentario_extra IS NOT NULL;` → **3**.
- **X6 — idempotencia:** repetir el paso 6 (NEW) y re-correr X2 → **idéntico** (35/31/3/0), sin duplicar.

## 8. Reglas no negociables

1. **SECUENCIA:** aplicar **la migración 005 ANTES** de desplegar/reiniciar el ETL nuevo (el INSERT usa las
   2 columnas; si no existen, falla). Nunca al revés.
2. **Migración idempotente** (`ADD COLUMN IF NOT EXISTS`); aplicar **migración 005 Y** DDL canónico, con el
   **mismo orden físico** (columnas DESPUÉS de `reporte_id`). **No** recrear la tabla ni borrar datos.
3. **`comentario` sigue NOT NULL** → principal con cadena **D→E→G**. Columnas nuevas **nullable**.
4. **Preservar los 3 campos** (D, E, G) — no fundir/descartar `E`/`G` (cobertura §0.2). **Forward-fill** de
   `producto`. **`"0"`/ruido = vacío** (corrige el bug de cortocircuito).
5. **No cambiar la firma** `load_comentarios(conn, ws, reporte_id, tipo_cache)` ni su invocación. **Sin
   imports nuevos.** No tocar otros extractores/facts/frontend.
6. **No hardcodear contraseñas**; conexión desde `INGESTA\Rep_Prod\.env`. Si la auditoría del paso 1 revela
   firmas/nombres distintos, **adaptar a los reales** (no inventar).

## 9. Rollback / Fuera de alcance

- **Rollback** (no destructivo): `ALTER TABLE core.fact_comentarios_produccion DROP COLUMN IF EXISTS
  comentario_programa, DROP COLUMN IF EXISTS comentario_extra;` + revertir `load_comentarios`. Los datos de
  `comentario` no se tocan.
- **Fuera de alcance:** `fact_tabla_hoja` (numérico, no aplica a texto); normalizar/deduplicar comentarios o
  trazar sus fórmulas; UI para mostrar los nuevos campos; re-ingesta masiva del corpus (se valida con 1 NEW
  + el backfill de los ya ingeridos).
