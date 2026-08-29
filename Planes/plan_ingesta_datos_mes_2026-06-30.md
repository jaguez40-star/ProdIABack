# Plan ejecutable (v2) — Modelado de la Tabla Dinámica MENSUAL "DATOS_MES" → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 1 → salida 1** (grano detalle del pivot; subtotales = derivados, excluidos).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `DATOS_MES`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA. **Frontend / api.py:** SIN cambios (modo "fechas" del visor, ya probado).

---

## 0. Auditoría (datos reales, 3 archivos)

`DATOS_MES` es la **Tabla Dinámica MENSUAL** (pivot de `BDP_datos_mes`, análogo a como `TD_datos_dia`
lo es de `BDP_datos_dia`). Se ingiere el **grano detalle** como tabla larga temporal:
`dims = {escenario, producto, vice, activos, area, campo}`, `fecha = fin de mes`, `valor` (BPDEQ_M).
Se **excluyen los subtotales** (filas "Total …" y la columna "Total general") por derivados recomputables.

### Estructura (cabeceras ancladas por CONTENIDO, no por fila/columna fija)
- **Filtros de página** (varían en nº y posición entre archivos): incluyen `GRUPOPROD = ECOPETROL` y
  (en NEW) `AÑO = 2024`. **No se modelan** (los agrega el pivot; no recuperables desde la celda).
- **Medida única**: `Suma de BPDEQ_M` (barriles/día equivalente, mensual). Constante → no va a `dims`.
- **Fila de cabecera** = la que tiene `ESCENARIO` en col A (NEW r27 / STD r37). Cols **A-F** = 6 niveles
  de fila `ESCENARIO/PRODUCTO/VICE/ACTIVOS/AREA/CAMPO`; desde col **G** las **12 fechas mensuales**
  (fin de mes, almacenadas como entero `yyyymmdd`; `to_date` las convierte). La columna `Total general`
  (no-fecha, p.ej. col S en NEW) se ignora.
- **Filas de datos** (desde la fila siguiente): A-F con **ffill de niveles padre**; filas con "Total …"
  en A-F → subtotal, se saltan.

### 🔴 Hallazgos críticos (por los que el extractor es dinámico)
1. **El layout difiere entre NEW y STD**: la cabecera cae en r27 (NEW) vs r37 (STD) y el nº de filtros
   de página cambia. → **Anclar por contenido** (`ESCENARIO` en col A; fechas detectadas por `to_date`).
   Verificado en los 3 archivos.
2. **`_p50_grid` NO sirve aquí**: corta en la fila 250 (`if r>250: break`) y DATOS_MES llega a ~1.275
   filas → truncaría. El extractor **construye su propio grid completo** (sin cap).
3. **`"(en blanco)"` es una categoría real** (p.ej. ACTIVOS en blanco). `s()` la trata como ruido
   (`NOISE`) y la borra → **2 colisiones en NEW** (dos `LORITO` distintos se fusionan, r846). Por eso los
   campos de fila usan un cleaner propio `rl()` que **preserva `"(en blanco)"`**. Verificado: **0 colisiones**.
4. **`ESCENARIO` es dimensión real** ∈ `{PPTO, REAL, OPERATIVO}` (presupuesto / real / operativo) → el
   valor de esta hoja es el comparativo mensual de escenarios a año completo. Se conserva en `dims`.
5. **Sin lector pre-existente** de `DATOS_MES` (grep services.py) → sin coexistencia/conflicto. (El crudo
   `BDP_datos_mes` se ingiere aparte a bronze, 314.952 filas; DATOS_MES es su pivot.)

### Conteos verificados (prototipo `rl()`, 3 archivos — 0 colisiones)
| Archivo | Filas | Meses | Rango |
|---------|------:|:-----:|-------|
| 2024-10-04 (NEW) | **7.776** | 12 | 2024-01-31 … 2024-12-31 |
| 2024-02-11 (STD) | 5.859 | 12 | 2024-01-31 … 2024-12-31 |
| 2023-12-31 (STD) | 8.455 | 12 | 2023-01-31 … 2023-12-31 |

⚠️ **Volumen alto** (miles de filas, proyección 12 meses × escenarios). **DE-RIESGADO**: `PROGRAMA` ya
ingiere **39.431 filas** por el MISMO `load_tablas_hoja` (verificado en reporte_id=4) → este orden está probado.

### No-breakage
- `fecha=mes` real en todas las filas → visor en modo "fechas" (ya probado). Sin `None.isoformat()`.
- 12ª hoja con el MISMO pipeline ⇒ 0 riesgo de regresión. pytest no aserta nº de hojas modeladas.
- No toca DDL, clave natural, `ON CONFLICT`, ni detección raw/STD. Extractor + 1 línea de registro.
- `rl()` aislado a este extractor (igual que en `_td_datos_dia_extract`); `s()` sigue intacto para el resto.

### 0.g — Flujo profesional v2: incoherencias / no-breakage (código y datos reales, 3 archivos)
1. 🔴 **Conflicto aparente con CLAUDE.md §7.5** (*"excluir filas … `(en blanco)`"*) → **RESUELTO**: la regla
   §7.5 trata `(en blanco)` como **fila de ruido** suelta. Aquí `(en blanco)` es el **valor de un nivel de
   jerarquía** del pivot (un pozo sin ACTIVOS asignado), categoría legítima. Borrarlo con `s()` causa **2
   colisiones en NEW** (dos `LORITO` distintos se fusionan, r846 — verificado). Por eso `rl()` lo preserva
   **solo en los campos de fila A-F**. Es la **misma decisión ya aceptada y en producción** en
   `_td_datos_dia_extract`. Desviación **intencional y documentada**, no una omisión.
2. **Aislamiento del pipeline raw verificado**: `load_tablas_hoja` hace `DELETE … WHERE reporte_id AND
   hoja='DATOS_MES'` sobre `core.fact_tabla_hoja` (services.py ~1310) → **no toca** el pipeline raw
   `BDP_datos_mes` → `core.fact_produccion_mes_ecp` (load_fact_mes, ~1391). `DATOS_MES` **no** está en
   `RAW_SHEETS` y `^DATOS_MES$` **no** matchea `BDP_datos_mes`. Sin interferencia. ✅
3. **Redundancia con el raw (esperada, aceptada)**: `DATOS_MES` es el pivot mensual de `BDP_datos_mes`
   (que alimenta `fact_produccion_mes_ecp`). Se añade a `fact_tabla_hoja` para el visor genérico — mismo
   patrón ya aceptado que `TD_datos_dia` (pivot de `BDP_datos_dia`). CLAUDE.md §116-117 confirma que el
   pivot mensual expone **"1 de 9" medidas** → la medida única `BPDEQ_M` es inherente al pivot, no recorte.
4. **Subtotales / gran total verificados en el tail**: las filas `Total general`, `Total REAL`,
   `Total BLANCOS`, `Total <VICE/ACTIVOS/AREA/CAMPO>` se **saltan** todas (heurística `startswith('total')`);
   **0 filas huérfanas** (con valor pero A-F vacías) en los 3 archivos. El ffill **no se corrompe**: los
   subtotales se saltan ANTES de actualizar los niveles padre. ✅
5. **Heurística de subtotal** (A-F empieza por "Total"): segura en este dominio (ningún ESCENARIO/PRODUCTO/
   VICE/ACTIVOS/AREA/CAMPO real empieza por "Total"). **Supuesto documentado** → re-auditar si un archivo
   futuro trae un valor real "Total …".
6. **Volumen DE-RIESGADO**: `PROGRAMA` ya ingiere **39.431 filas** por el mismo `load_tablas_hoja` (un
   `executemany`, sin chunking) → las ≤8.455 de DATOS_MES están holgadamente probadas. Sin límite de parámetros.
7. **Sin disparadores de riesgo §0.2**: no toca DDL, ni clave natural (`uk_mes`), ni `ON CONFLICT`, ni
   detección raw/STD (§4), ni el mapeo §5 (que va de `BDP_datos_mes`→fact, no de `DATOS_MES`). Extractor +
   1 línea de registro. El visor (`tablas/api.py` modo "fechas" + `renderTablaAncha`) es genérico sobre `dims`.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_datos_mes_extract` (insertar después de `_td_datos_dia_extract`, antes del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _datos_mes_extract(ws):
    """Extractor de la Tabla Dinámica MENSUAL 'DATOS_MES' (pivot de BDP_datos_mes) → 1 tabla larga
    temporal (fecha=fin de mes), grano DETALLE (escenario × producto × vice × activos × area × campo).
    EXCLUYE subtotales (filas 'Total …' y la columna 'Total general'). Cabeceras ANCLADAS POR CONTENIDO
    (el layout difiere NEW/STD): la fila de cabecera es la que tiene 'ESCENARIO' en col A; cols A-F = los
    6 niveles de fila; desde col G las fechas mensuales (enteros yyyymmdd). Medida única 'BPDEQ_M' y
    GRUPOPROD fijo=ECOPETROL son filtros del pivot (no se modelan como dims). '(en blanco)' se PRESERVA
    como categoría real (NO usar s() en los campos de fila). NO usar _p50_grid (corta en fila 250;
    DATOS_MES llega a ~1275). Verificado 0 colisiones en 3 archivos."""
    DECLARED = [(1, "DATOS_MES (detalle mensual)")]
    # grid COMPLETO (sin cap de filas)
    grid = {}
    maxr = maxc = 0
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for c, v in enumerate(row, start=1):
            if v is not None and str(v).strip() != "":
                grid[(r, c)] = v
                if r > maxr:
                    maxr = r
                if c > maxc:
                    maxc = c

    def rl(v):                                  # etiqueta de fila: preserva '(en blanco)'; '' / None = ausente
        if v is None:
            return None
        t = str(v).strip()
        return None if t == "" else t

    # --- fila de cabecera: la que tiene 'ESCENARIO' en col A ---
    hdr = None
    for r in range(1, maxr + 1):
        if (s(grid.get((r, 1))) or "").upper() == "ESCENARIO":
            hdr = r
            break
    if hdr is None:
        return {"rows": [], "tablas": DECLARED}

    # --- columnas de fecha (desde col 7); no-fecha (p.ej. 'Total general') → ignorada ---
    datecols = []                               # [(col, fecha)]
    for c in range(7, maxc + 1):
        d = to_date(grid.get((hdr, c)))
        if d:
            datecols.append((c, d))
    if not datecols:
        return {"rows": [], "tablas": DECLARED}

    # --- filas de datos: ffill niveles padre; saltar 'Total …' (subtotales) ---
    ROWF = ["escenario", "producto", "vice", "activos", "area", "campo"]
    rows = []
    ff = [None] * 6
    for r in range(hdr + 1, maxr + 1):
        vals = [rl(grid.get((r, c))) for c in range(1, 7)]
        if any(v and v.lower().startswith("total") for v in vals):
            continue                            # subtotal/gran total → derivado, se excluye
        for i in range(6):
            if vals[i] is not None:
                ff[i] = vals[i]
        base = {ROWF[i]: ff[i] for i in range(6) if ff[i] is not None}
        for c, d in datecols:
            v = num(grid.get((r, c)))
            if v is None:
                continue
            rows.append({"tabla_idx": 1, "tabla_label": "DATOS_MES (detalle mensual)",
                         "dims": dict(base), "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de TD_datos_dia)

```python
    # DATOS_MES: Tabla Dinámica MENSUAL (pivot de BDP_datos_mes). Grano detalle (6 niveles × mes);
    # subtotales excluidos. Cabeceras por contenido (ancla 'ESCENARIO'); '(en blanco)' preservado. Volumen alto.
    (re.compile(r"(?i)^DATOS_MES$"), _datos_mes_extract),
```

**NO** agregar imports (`s`, `num`, `to_date` ya existen). **NO** usar `_p50_grid` (cap 250).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_td_datos_dia_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `to_date` existen en services.py (import `from app.shared.utils import ...`).
3. Nombre exacto de la hoja: `DATOS_MES` (regex `^DATOS_MES$`; NO debe matchear `BDP_datos_mes`).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico `2024-10-04`; tomar `<rid>` de la ingesta)

- **X1 — 1 tabla:** `GET /tablas?...&hoja=DATOS_MES` → 1 ítem (idx 1, "DATOS_MES (detalle mensual)").
- **X2 — conteo:** **7776 filas**.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — modo/contenido:** **12** fechas distintas `2024-01-31 … 2024-12-31`, 0 con `fecha IS NULL`;
  `dims->>'escenario'` ∈ {PPTO, REAL, OPERATIVO}.
- **X5 — spot-checks (NEW 2024-10-04):**
  - `escenario=PPTO, producto=CRUDO, vice=VAO, activos=CAÑO SUR, area=CAÑO SUR, campo=CAÑO SUR ESTE`,
    `2024-01-31` → `39433.98`.
  - `escenario=REAL, vice=VEX, campo=LORITO`, `2024-09-30`, **dos filas distintas**:
    `activos=CPO-09` → `4.630633…` y `activos=(en blanco)` → `492.3778…`
    (prueba que `rl()` evita la colisión: dos LORITO distintos coexisten).
- **X6 — idempotencia:** re-ingerir → mismos conteos.
- **X7 — no-breakage:** las 12 hojas modeladas previas + COMENTARIOS intactas; `uv run pytest -q` verde.

```sql
-- X2/X3
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='DATOS_MES';   -- 7776
SELECT count(*) FROM (SELECT 1 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='DATOS_MES'
  GROUP BY tabla_idx,dims,fecha HAVING count(*)>1) x;                                    -- 0
-- X4
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL),
       count(DISTINCT dims->>'escenario')
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='DATOS_MES';                  -- 12, 0, 3
-- X5
SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='DATOS_MES'
   AND fecha='2024-01-31' AND dims->>'escenario'='PPTO' AND dims->>'campo'='CAÑO SUR ESTE';  -- 39433.98
SELECT dims->>'activos' activos, valor FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='DATOS_MES' AND fecha='2024-09-30'
   AND dims->>'escenario'='REAL' AND dims->>'vice'='VEX' AND dims->>'campo'='LORITO'
 ORDER BY 1;                                              -- (en blanco)→492.38 ; CPO-09→4.63
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. Grano DETALLE; excluir subtotales (filas 'Total …' y la
  columna 'Total general' / cualquier columna no-fecha desde G).
- **4.2** **Cabeceras por contenido** (ancla `ESCENARIO` en col A; fechas por `to_date`), NO por fila/
  columna fija (layout NEW≠STD).
- **4.3** Construir grid COMPLETO (NO `_p50_grid`, que corta en la fila 250).
- **4.4** Campos de fila con `rl()` (preserva `"(en blanco)"`); NO usar `s()` ahí (borraría la categoría).
- **4.5** `fecha=mes` real (nunca NULL). No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta**.

---

## 5. Fuera de alcance
- Subtotales del pivot (filas "Total …", incl. `Total general`/`Total REAL`/`Total BLANCOS`/`Total <X>`;
  columna "Total general"): derivados recomputables (consistente con §7.5 "excluir Total X").
- Medida única `BPDEQ_M` (constante) y `GRUPOPROD` fijo=ECOPETROL: filtros del pivot, no aportan a `dims`
  (el pivot mensual expone 1 de 9 medidas, CLAUDE.md §116-117).
- Dimensiones colapsadas por el pivot a filtro de página `(Todas)` (NODO, NEGOCIO, SOCIO, CONTRATO,
  GERENCIA, OPERACION, IDBDP, etc.): las **agrega el pivot mismo**, no recuperables desde la celda.
- Área de filtros de página y cabeceras del pivot: metadata, no datos.

> **Nota sobre `(en blanco)` (NO está fuera de alcance, ver §0.g.1):** a diferencia de §7.5, `(en blanco)`
> SÍ se ingiere cuando es el valor de un nivel de fila (categoría real del pivot). Solo se descarta como
> fila de ruido suelta, no como nivel de jerarquía. Misma regla que `_td_datos_dia_extract`.
