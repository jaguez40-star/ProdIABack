# Plan ejecutable (v2) — Modelado de la Tabla Dinámica "TD_datos_dia" → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 1 → salida 1** (el grano detalle del pivot; subtotales = derivados, excluidos).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `TD_datos_dia`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA. **Frontend / api.py:** SIN cambios (modo "fechas" del visor, ya probado).

---

## 0. Auditoría (datos reales, 3 archivos)

`TD_datos_dia` es una **Tabla Dinámica de Excel** (pivot) de los datos diarios. Se ingiere el **grano
detalle** como tabla larga temporal: `dims = {tipoproducto, vice, activos, grupo1, fuente, grupoprod,
medida}`, `fecha = día`, `valor`. Se **excluyen los subtotales** (filas "Total …" y columnas de total
por fecha / gran total) por ser derivados recomputables (mismo criterio que `_p50_extract`).

### Estructura (cabeceras ancladas por CONTENIDO, no por columna fija)
- **Columnas** (fila 19 FECHA, fila 20 medida `Suma de <X>`, fila 21 GRUPOPROD): cada columna de
  **detalle** = `GRUPOPROD ∈ {ECOPETROL, SOCIOS}` con fecha y medida vigentes (ffill). Medida = quitar
  `"Suma de "` → `VOLDISMEZ / VOL_ESTIMADO / PROMEDIO`. Columnas sin grupoprod (subtotal/gran total) → ignoradas.
- **Filas** (desde 22): campos A-E = `TIPOPRODUCTO/VICE/ACTIVOS/GRUPO1/FUENTE` con **ffill de niveles
  padre**; filas con "Total …" en A-E → subtotal, se saltan.

### 🔴 Hallazgos críticos (por los que el extractor es dinámico)
1. **El layout difiere entre NEW y STD**: NEW (2024-10-04) = 6 filtros de página, 24 cols detalle, 4
   días, fechas combinadas; STD (2402/2023) = 13 filtros, 222 cols detalle, 37 días, fechas repetidas.
   → **Anclar por contenido** (no por columna/fila fija). Verificado en los 3.
2. **`_p50_grid` NO sirve aquí**: corta en la fila 250 (`if r>250: break`) y TD llega a ~590 filas →
   truncaría. El extractor **construye su propio grid completo** (sin cap).
3. **`"(en blanco)"` es una categoría real** (p. ej. ACTIVOS en blanco). `s()` la trata como ruido
   (`NOISE`) y la borra → causaría colisión (dos "LORITO" distintos se fusionarían). Por eso los campos
   de fila usan un cleaner propio `rl()` que **preserva `"(en blanco)"`**. Verificado: **0 colisiones**.
4. **Sin lector pre-existente** de TD_datos_dia (grep services.py) → sin coexistencia/conflicto. (El
   crudo `BDP_datos_dia` se ingiere aparte a bronze; TD es su pivot.)

### Conteos verificados (prototipo, 3 archivos — 0 colisiones)
| Archivo | Filas | Cols detalle | Días | Medidas | Grupos |
|---------|------:|-------------:|-----:|---------|--------|
| 2024-10-04 (NEW) | **5.209** | 24 | 4 (Sep30–Oct3) | VOLDISMEZ/VOL_ESTIMADO/PROMEDIO | ECOPETROL/SOCIOS |
| 2024-02-11 (STD) | 38.961 | 222 | 37 (Ene5–Feb10) | idem | idem |
| 2023-12-31 (STD) | 48.816 | 222 | 37 (Nov24–Dic30) | idem | idem |

⚠️ **Volumen alto** (decenas de miles de filas en STD): es un pivot diario detallado. **DE-RIESGADO**:
`PROGRAMA` ya ingiere **39.431 filas** por el MISMO `load_tablas_hoja` (verificado en reporte_id=4) →
las 38.961 de TD (STD) son del mismo orden y están probadas en producción.

### No-breakage
- `fecha=día` en todas las filas → visor en modo "fechas". 11ª hoja con el MISMO pipeline ⇒ 0 regresión.
- pytest no aserta nº de hojas modeladas.

### 0.g — Flujo profesional v2: verificación de incoherencias / no-breakage (datos y código reales)
1. **Volumen probado**: `load_tablas_hoja` hace un único `executemany` (no chunking), pero `PROGRAMA`
   (39.431 filas) demuestra que el camino soporta este orden. No hay riesgo de límite de parámetros
   (executemany ejecuta por fila, no un VALUES gigante). ✅
2. **Grano = el que muestra el pivot (CLAUDE.md §3/§4, líneas 116-117)**: en estas TD/pivots
   "IDBDP/socio/concepto quedan como filtros → se pierden; día expone 3 de 5 medidas". Es decir, el
   **pivot mismo** agrega esas dimensiones (filtros de página `(Todas)`); este extractor captura
   exactamente lo presentado (TIPOPRODUCTO/VICE/ACTIVOS/GRUPO1/FUENTE × día × grupoprod × 3 medidas).
   **La limitación de grano es inherente al pivot, no del extractor.** Coherente con "los valores que presenta".
3. **Heurística de subtotal** (`A-E` empieza por "Total"): segura en este dominio (ningún valor real de
   producto/vice/activos/grupo1/fuente empieza por "Total"; los "Total …" son siempre subtotales del
   pivot). **Supuesto documentado** → re-auditar si algún archivo futuro trae un valor real "Total …".
4. **Columnas con FECHA "(en blanco)"** (registros sin fecha en la fuente): se excluyen (un valor sin
   fecha no puede ir a una tabla temporal). Marginal; documentado.
5. **`s()` vs `rl()`**: `s()` borra `"(en blanco)"` (NOISE) → correcto para grupoprod/medida (descarta el
   bloque sin grupo), pero **erróneo para campos de fila** (es categoría real). Por eso `rl()` solo en A-E.
   Aislado a este extractor; no afecta a otras hojas.
6. **Sin disparadores de riesgo §0.2**: no toca DDL, ni clave natural, ni `ON CONFLICT`, ni detección
   raw/STD; sin lector pre-existente de TD. Extractor + 1 línea de registro.
7. **Payload del visor a escala**: para STD, `/tablas/datos` devuelve ~39K filas → JSON grande y render
   ancho (~1.000 filas × 37 fechas). Funcional (igual que PROGRAMA, ya visible), pero pesado en STD;
   el archivo NEW (5.209) es liviano. Sin acción requerida.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_td_datos_dia_extract` (insertar después de `_inicio_extract`, antes del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _td_datos_dia_extract(ws):
    """Extractor de la Tabla Dinámica 'TD_datos_dia' → 1 tabla larga temporal (fecha=día), grano DETALLE
    (filas-hoja × ECOPETROL/SOCIOS × día). EXCLUYE subtotales (filas 'Total …' y columnas de total por
    fecha/gran total: derivados). Cabeceras ANCLADAS POR CONTENIDO (el layout difiere NEW/STD):
      fila 19 = FECHA (ffill desde la última fecha real); fila 20 = medida 'Suma de <X>' (ffill;
      X ∈ VOLDISMEZ/VOL_ESTIMADO/PROMEDIO); fila 21 = GRUPOPROD (ECOPETROL/SOCIOS) → columna de detalle.
    Campos de fila A-E = TIPOPRODUCTO/VICE/ACTIVOS/GRUPO1/FUENTE (ffill de niveles padre). '(en blanco)'
    se PRESERVA como categoría real (NO usar s() en los campos de fila). dims = 5 niveles + grupoprod +
    medida. NO usar _p50_grid (corta en fila 250; TD tiene ~590). Verificado 0 colisiones en 3 archivos."""
    DECLARED = [(1, "TD_datos_dia (detalle diario)")]
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

    # --- columnas de detalle: grupoprod ∈ {ECOPETROL,SOCIOS} con fecha y medida vigentes ---
    detail = []                                 # [(col, fecha, medida, grupoprod)]
    cur_date = cur_meas = None
    for c in range(6, maxc + 1):
        d = to_date(grid.get((19, c)))
        if d:
            cur_date = d
        m = s(grid.get((20, c)))
        if m and m.lower().startswith("suma de "):
            cur_meas = m[8:].strip()
        gp = s(grid.get((21, c)))
        if gp in ("ECOPETROL", "SOCIOS") and cur_date and cur_meas:
            detail.append((c, cur_date, cur_meas, gp))
    if not detail:
        return {"rows": [], "tablas": DECLARED}

    # --- filas de datos (desde 22): ffill niveles padre; saltar 'Total …' (subtotales) ---
    ROWF = ["tipoproducto", "vice", "activos", "grupo1", "fuente"]
    rows = []
    ff = [None] * 5
    for r in range(22, maxr + 1):
        vals = [rl(grid.get((r, c))) for c in range(1, 6)]
        if any(v and v.lower().startswith("total") for v in vals):
            continue                            # subtotal/gran total → derivado, se excluye
        for i in range(5):
            if vals[i] is not None:
                ff[i] = vals[i]
        base = {ROWF[i]: ff[i] for i in range(5) if ff[i] is not None}
        for c, d, meas, gp in detail:
            v = num(grid.get((r, c)))
            if v is None:
                continue
            dims = dict(base)
            dims["grupoprod"] = gp
            dims["medida"] = meas
            rows.append({"tabla_idx": 1, "tabla_label": "TD_datos_dia (detalle diario)",
                         "dims": dims, "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de INICIO)

```python
    # TD_datos_dia: Tabla Dinámica diaria (pivot). Grano detalle (5 niveles × ECOPETROL/SOCIOS × medida
    # × día); subtotales excluidos. Cabeceras ancladas por contenido (layout NEW/STD difiere). Volumen alto.
    (re.compile(r"(?i)^TD_datos_dia$"), _td_datos_dia_extract),
```

**NO** agregar imports (`s`, `num`, `to_date` ya existen). **NO** usar `_p50_grid` (cap 250).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_inicio_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `to_date` existen en services.py.
3. Nombre exacto de la hoja: `TD_datos_dia` (regex `^TD_datos_dia$`; NO debe matchear `BDP_datos_dia`).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico `2024-10-04`; tomar `<rid>` de la ingesta)

- **X1 — 1 tabla:** `GET /tablas?...&hoja=TD_datos_dia` → 1 ítem (idx 1).
- **X2 — conteo:** **5209 filas**.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — modo/contenido:** 4 fechas distintas `2024-09-30 … 2024-10-03`, 0 con `fecha IS NULL`;
  `dims->>'medida'` ∈ {VOLDISMEZ, VOL_ESTIMADO, PROMEDIO}; `dims->>'grupoprod'` ∈ {ECOPETROL, SOCIOS}.
- **X5 — spot-checks (2024-09-30, VOLDISMEZ, ECOPETROL):**
  - `tipoproducto=CRUDO, vice=VEX, activos=CPO-09, grupo1=CPO-09, fuente=LORITO` → `138.919`.
  - `tipoproducto=CRUDO, vice=VEX, activos=(en blanco), grupo1=CPO-09, fuente=LORITO` → `553.4045`
    (LORITO distinto bajo ACTIVOS '(en blanco)' — prueba que el fix evita la colisión).
- **X6 — idempotencia:** re-ingerir → mismos conteos.
- **X7 — no-breakage:** hojas modeladas previas + COMENTARIOS intactas; `uv run pytest -q` verde.

```sql
-- X2/X3
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='TD_datos_dia';
SELECT count(*) FROM (SELECT 1 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='TD_datos_dia'
  GROUP BY tabla_idx,dims,fecha HAVING count(*)>1) x;                      -- 0
-- X4
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL),
       count(DISTINCT dims->>'medida'), count(DISTINCT dims->>'grupoprod')
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='TD_datos_dia';  -- 4, 0, 3, 2
-- X5
SELECT dims->>'activos' activos, valor FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='TD_datos_dia' AND fecha='2024-09-30'
   AND dims->>'medida'='VOLDISMEZ' AND dims->>'grupoprod'='ECOPETROL'
   AND dims->>'fuente'='LORITO' ORDER BY 1;                                 -- (en blanco)→553.40 ; CPO-09→138.92
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. Grano DETALLE; excluir subtotales (filas 'Total …' y columnas
  sin grupoprod).
- **4.2** **Cabeceras por contenido** (fila 19/20/21), NO por columna fija (layout NEW≠STD).
- **4.3** Construir grid COMPLETO (NO `_p50_grid`, que corta en la fila 250).
- **4.4** Campos de fila con `rl()` (preserva `"(en blanco)"`); NO usar `s()` ahí (borraría la categoría).
- **4.5** `fecha=día` real (nunca NULL). No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta**.

---

## 5. Fuera de alcance
- Subtotales del pivot (filas "Total …", columnas de total por fecha, gran total): derivados recomputables.
- Columnas con FECHA `"(en blanco)"` (registros sin fecha): no caben en una tabla temporal; marginales.
- Dimensiones colapsadas por el pivot a filtro de página `(Todas)` (IDBDP, SOCIO, GERENCIA, OPERACION,
  ESCENARIO, etc.): las **agrega el pivot mismo** (CLAUDE.md §3/§4), no son recuperables desde la celda.
- Filtros de página (r4-16) y el área de cabeceras: metadata del pivot, no datos.
