# Plan ejecutable v2 — Ingesta de la hoja "P50 Acumulado" (2 tablas) → `core.fact_tabla_hoja`

> Modo: **plan:** (para un executor sin contexto del repo). Rutas absolutas, código completo,
> decisiones cerradas, criterios verificables. **Versión auditada v2** — ver §0.
>
> ⚠️ **Nota de estado:** este cambio **YA se aplicó y validó en DESARROLLO** (Postgres local
> `daily_report_prod`, 2026-06-29). Este plan existe para que el Executor lo **replique en
> PRODUCCIÓN (servidor 139)** y como registro formal del modelado de la hoja (§0.1 del CLAUDE.md).

---

## 0. Hallazgos de auditoría (verificados contra el CÓDIGO y los DATOS reales)

### 0.a Auditoría de datos (openpyxl `data_only`, solo lectura)
- **A1 — La hoja `P50 Acumulado` existe en archivos STD y NEW**, con nombre **idéntico** (14 chars, NO se
  trunca). Verificada en `20231231` (STD-2023), `20240211` (STD-2024) y `20241004` (NEW-2024). ⇒ casar por
  **prefijo** `(?i)^P50 Acumulado` (tolerante a sufijos/copias).
- **A2 — Son 2 tablas, NO PivotTables reales.** `sheet2.xml` (la hoja) **no tiene** relación a
  `pivotTable` (solo `drawing` + `printerSettings`). Las celdas son **fórmulas**
  `=SUMPRODUCT('NEW MES-AÑO'!$V$14:…, $C$6:…)/SUM($C$6:…)` (promedio acumulado **ponderado por días**).
  - Tabla 1 título **`P50`** (col A, fila 9); datos f11–f15.
  - Tabla 2 título **`P50 FILIALES`** (col A, fila 16); datos f18–f21.
  - **Decisión del dueño (2026-06-29): ingerir los VALORES YA CALCULADOS tal como aparecen, sin
    recalcular.** Por eso se leen valores cacheados (`data_only=True`), no las fórmulas.
- **A3 — 12 meses contiguos `YYYYMMDD`** en el encabezado (cols C..N), fila título+1 (f10 y f17). La
  columna **`PROMEDIO ACUMULADO`** (col O, solo Tabla 1) es el mes de corte `/1000` (auto-`HLOOKUP`):
  **se excluye** automáticamente porque el barrido de meses corta en la 1ª no-fecha.
- **A4 — Productos (col A) leídos tal cual, incluidos los totales:**
  - Tabla 1 (ECP): `CRUDO, GAS, BLANCOS, VEX CRUDO, Total VDP` (5).
  - Tabla 2 (FILIALES): `CRUDO, GAS, BLANCOS, Total Filiales` (4).
- **A5 — Layout estable en 4 archivos** (STD-2023, STD-2024, NEW-2024 — supera el ≥3 del §0.2.5). Anclas
  por título en col A + meses contiguos ⇒ robusto a desplazamiento de filas.

### 0.b Auditoría de código (cruce contra `services.py`)
- **B1 — SIN tabla nueva, SIN migración, SIN DDL.** Reutiliza la tabla genérica existente
  `core.fact_tabla_hoja` vía el registro `HOJAS_MODELADAS` (el mismo mecanismo de `P50 Quemado`,
  `Producción filiales` y `(Bitacora)`). Contrato por fila: `{tabla_idx, tabla_label, dims, fecha, valor}`.
- **B2 — SIN imports nuevos.** `re`, `s`, `num`, `to_date`, y los helpers `_p50_grid` /
  `_p50_contig_months` **ya están** en `services.py` (los usa el extractor de P50 Quemado).
- **B3 — Contrato extendido** `{"rows":[...], "tablas": DECLARED}` (como `_bitacora_extract`) para que el
  front liste **siempre las 2 tablas** aunque vengan vacías.
- **B4 — Dedup e idempotencia ya las maneja `load_tablas_hoja`**: dedup por `(tabla_idx, dims, fecha)`
  last-wins + `DELETE FROM core.fact_tabla_hoja WHERE reporte_id=? AND hoja=?` antes de insertar. El
  extractor NO necesita lógica extra.

### 0.c Conteos esperados (autoridad de validación) — por archivo
| Tabla | Filas | Detalle |
|---|---|---|
| Tabla 1 (P50 ECP) | **60** | 5 productos × 12 meses |
| Tabla 2 (P50 FILIALES) | **48** | 4 productos × 12 meses |
| **TOTAL** | **108** | |

Spot-check (cacheado, NEW-2024): `CRUDO` (ECP) `2024-01-31` = **489525.6011139999**;
`CRUDO` (filiales) `2024-01-31` = **80422.95999999999**.

---

## 1. Contexto

Proyecto **INGESTA / Rep_Prod** (FastAPI + SQLAlchemy Core + PostgreSQL, Medallion bronze/core). ETL en
`C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`.
Hoy la hoja `P50 Acumulado` **solo cae en `bronze.hoja_landing`**. Este plan añade un **extractor** que la
modela como **2 tablas** en `core.fact_tabla_hoja` (formato largo, una fila por celda mensual), tomando los
valores **ya calculados** de la hoja (sin recalcular).

## 2. Objetivo

1. Agregar la función `_p50_acum_extract(ws)` en `services.py`.
2. Registrarla en `HOJAS_MODELADAS` con el patrón `(?i)^P50 Acumulado`.
3. Resultado: al ingerir cualquier archivo con la hoja `P50 Acumulado` (NEW o STD), sus 2 tablas quedan en
   `core.fact_tabla_hoja` y aparecen en el visor "Para análisis", idempotente.

## 3. Prerequisitos (si alguno falla, DETENERSE y reportar)

- **P1** — Existe `…\backend\app\features\ingesta\services.py` con el registro `HOJAS_MODELADAS` y los
  helpers `_p50_grid` / `_p50_contig_months` y `load_tablas_hoja`.
- **P2** — La tabla `core.fact_tabla_hoja` **ya existe** en la BD destino (la usan `P50 Quemado`,
  `Producción filiales`, `(Bitacora)`). **NO** se crea ni migra nada.
- **P3** — BD destino tomada de `INGESTA\Rep_Prod\.env` (variable `DATABASE_URL`). **Producción** = bloque
  139 (`10.100.26.139:5432/daily_report_prod`); requiere VPN/red Ecopetrol. **No hardcodear la contraseña**
  en comandos: usar `$env:PGPASSWORD` leído del `.env`, nunca inline (la pass lleva `>` en PowerShell).
- **P4** — `uv` instalado; backend se levanta con
  `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000` (reiniciar tras editar).
- **P5** — Existe al menos un `.xlsm` con la hoja `P50 Acumulado` para re-ingerir.

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: añadir `_p50_acum_extract` + 1 línea en `HOJAS_MODELADAS`. |

**NO se toca:** DDL, migraciones, `api.py`, frontend, `land_landing`, imports, ni los demás extractores/
facts. La hoja sigue cayendo en `bronze.hoja_landing` (respaldo); este plan **solo añade** el destino Core
genérico.

## 5. Especificación (código completo)

### 5.1 Extractor — agregar a `services.py`

**NO agregar imports.** Colocar la función **junto a los demás `_*_extract`**, inmediatamente **después de
`_bitacora_extract`** y **antes** del comentario `# === Registro de hojas modeladas`. Pegar tal cual:

```python
def _p50_acum_extract(ws):
    """Extractor de 'P50 Acumulado' → 2 tablas de promedios P50 ACUMULADOS ya calculados en la hoja.
    NO recalcula: toma los valores cacheados TAL COMO APARECEN (decisión usuario 2026-06-29). La hoja
    es un cálculo derivado de 'NEW MES-AÑO', pero por requerimiento se ingieren sus valores tal cual.
    Contrato genérico [{tabla_idx,tabla_label,dims,fecha,valor}]:
      Tabla 1 'P50' (ECP):    productos × 12 meses (encabezado YYYYMMDD). dims={producto}.
      Tabla 2 'P50 FILIALES': productos × 12 meses.                       dims={producto}.
    Anclado por los títulos 'P50' y 'P50 FILIALES' en col A; meses = encabezado contiguo (to_date corta
    en la 1ª no-fecha → excluye la columna 'PROMEDIO ACUMULADO', que es el mes de corte /1000, no aporta
    dato nuevo). Incluye las filas de total ('Total VDP'/'Total Filiales') tal como aparecen.
    DECLARA siempre las 2 tablas para que el front las liste aunque vengan vacías."""
    grid, maxr = _p50_grid(ws)
    DECLARED = [(1, "Tabla 1 (P50 ECP)"), (2, "Tabla 2 (P50 FILIALES)")]
    rows = []

    def find_title(target):
        cand = [r for (r, c), v in grid.items()
                if c == 1 and isinstance(v, str) and v.strip().upper() == target]
        return min(cand) if cand else None

    def emit(idx, label, title_row):
        if title_row is None:
            return
        hdr = title_row + 1
        months = _p50_contig_months(grid, hdr, 3)      # meses contiguos desde col C
        if not months:
            return
        for r in range(hdr + 1, maxr + 1):
            ps = s(grid.get((r, 1)))
            if not ps:
                continue
            if ps.upper() == "P50 FILIALES":            # llegó el título de la 2ª tabla → cortar
                break
            dims = {"producto": ps}
            for c, d in months:
                v = num(grid.get((r, c)))
                if v is None:
                    continue
                rows.append({"tabla_idx": idx, "tabla_label": label,
                             "dims": dims, "fecha": d, "valor": v})

    emit(1, "Tabla 1 (P50 ECP)", find_title("P50"))
    emit(2, "Tabla 2 (P50 FILIALES)", find_title("P50 FILIALES"))
    return {"rows": rows, "tablas": DECLARED}
```

### 5.2 Registro — añadir 1 línea a `HOJAS_MODELADAS`

Dentro de la lista `HOJAS_MODELADAS`, **después** de la entrada de `(Bitacora)` y **antes** del `]`:

```python
    # P50 Acumulado: 2 tablas de promedios P50 acumulados (producto×mes). Valores ya calculados,
    # se ingieren tal cual (sin recalcular). Nombre 14 chars → sin truncar.
    (re.compile(r"(?i)^P50 Acumulado"), _p50_acum_extract),
```

> `load_tablas_hoja` recorre `HOJAS_MODELADAS`, localiza la hoja por el patrón, llama al extractor,
> deduplica y hace `DELETE+INSERT` en `core.fact_tabla_hoja`. No se requiere nada más.

## 6. Orden de ejecución

1. **Auditar** `services.py`: confirmar que existe `HOJAS_MODELADAS`, que `load_tablas_hoja` itera ese
   registro y escribe en `core.fact_tabla_hoja`, y que `_p50_grid` / `_p50_contig_months` existen.
   Verificar Prerequisitos §3; si P1/P2/P3 fallan, DETENERSE.
2. Aplicar **§5.1** (extractor) y **§5.2** (registro). Sin imports nuevos.
3. **Tests:** `cd INGESTA\Rep_Prod\backend; uv run pytest -q` → debe seguir **verde** (6 passed, 1 skipped).
4. Reiniciar el backend FastAPI (carga el código nuevo).
5. **Re-ingerir** un archivo con la hoja (idempotente). Por CLI:
   ```powershell
   cd "C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm"
   ```
   (o subiéndolo desde la UI con **CARGAR E INGERIR**).
6. Ejecutar validaciones **X1–X4**.

## 7. Validaciones (comando → esperado). Credencial: `$env:PGPASSWORD` leído de `INGESTA\Rep_Prod\.env`

> Sustituir `<HOST>` por `10.100.26.139` (prod) o `127.0.0.1` (dev), y `<REP>` por el `reporte_id` del
> archivo ingerido. `psql.exe` en `C:\Program Files\PostgreSQL\18\bin\`.

- **X1 — Conteo total por tabla:**
  ```sql
  SELECT tabla_label, count(*) FROM core.fact_tabla_hoja
   WHERE hoja='P50 Acumulado' AND reporte_id=<REP> GROUP BY tabla_label ORDER BY tabla_label;
  ```
  Esperado: `Tabla 1 (P50 ECP) = 60`, `Tabla 2 (P50 FILIALES) = 48` (TOTAL **108**).
- **X2 — 12 meses exactos:**
  ```sql
  SELECT count(DISTINCT fecha) FROM core.fact_tabla_hoja
   WHERE hoja='P50 Acumulado' AND reporte_id=<REP>;   -- esperado 12
  ```
- **X3 — Spot-check (debe coincidir con el Excel, sin recalcular):**
  ```sql
  SELECT valor FROM core.fact_tabla_hoja
   WHERE hoja='P50 Acumulado' AND reporte_id=<REP> AND tabla_idx=1
     AND dims->>'producto'='CRUDO' AND fecha='2024-01-31';   -- esperado ~489525.60
  ```
- **X4 — Idempotencia:** repetir el paso 6 (§6) y volver a correr X1 → conteos **idénticos** (60/48), sin
  duplicar.
- **X5 (manual, opcional):** http://localhost:8020 → subir el archivo → bajo la hoja `P50 Acumulado` deben
  verse **2 tablas** (`Tabla 1 (P50 ECP)`, `Tabla 2 (P50 FILIALES)`) en "Para análisis".

## 8. Reglas no negociables

1. **Ingerir valores CACHEADOS tal como aparecen** (`data_only`); **prohibido recalcular** los promedios.
2. **Anclar por título** (`P50` / `P50 FILIALES` en col A) + **meses contiguos** con corte en la 1ª
   no-fecha (esto excluye `PROMEDIO ACUMULADO`). Usar el helper **`to_date`** del repo (no reimplementar).
3. **Reutilizar `core.fact_tabla_hoja`**; **no** crear tabla, **no** migración, **no** tocar el DDL.
4. **No agregar imports** (ya existen). **No hardcodear el año** (patrón por prefijo).
5. **Devolver el contrato extendido** `{"rows":..., "tablas": DECLARED}` (declara las 2 tablas siempre).
6. **No hardcodear contraseñas** en comandos; tomar la conexión de `INGESTA\Rep_Prod\.env`.
7. **No modificar** `land_landing`, `api.py`, el frontend, ni los demás extractores/facts. Único cambio al
   ETL: 1 función + 1 línea de registro.
8. Si la auditoría del paso 1 revela firmas/nombres distintos, **adaptar a los reales** (no inventar).

## 9. Fuera de alcance

- La columna `PROMEDIO ACUMULADO` (mes de corte /1000) — excluida por decisión; si se requiere, sería otra
  iteración (columna `fecha=NULL`, dims `{producto, metrica}`).
- Trazar/normalizar la fuente upstream `NEW MES-AÑO` → BDP raw (otro plan).
- Botones/gráficos sobre estas tablas; corrección del landing genérico de otras hojas.
