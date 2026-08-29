# Plan ejecutable (v2) — Modelado RAW de "BDP_datos_mes" → `core.fact_tabla_hoja` (1 fila por registro)

> **Cobertura: Tablas: entrada 1 → salida 1** (grano RAW mensual; **1 fila por registro**, NO se despliegan
> las 10 medidas → 314.952 filas, decisión explícita del usuario, no el unpivot de 3,15M).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `BDP_datos_mes` (solo archivos NEW)
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA. **DDL / api.py / frontend:** SIN cambios (visor genérico ya soporta el modo "fechas").

---

## 0. Auditoría (datos reales, archivo NEW canónico)

`BDP_datos_mes` es una de las **3 hojas RAW planas** (`RAW_SHEETS`), **solo en archivos NEW**. **314.952
filas × 59 columnas**, 1 fila = 1 registro atómico. Es el **cubo mensual multi-año** que alimenta
`fact_produccion_mes_ecp`; su **pivot** `DATOS_MES` (12 meses 2024, 7.776 filas) y su landing
`bronze.bdp_datos_mes` ya existen.

### Decisión de modelado (usuario): 1 fila por registro (314.952), NO unpivot
`fact_tabla_hoja` tiene **un** `valor` por fila. Se modela **1 fila por registro** con la medida principal
**`BPDEQ_M`** (barriles/día equivalente mensual — la misma del pivot `DATOS_MES`, comparables) como `valor`.
Las otras 9 medidas (VOLUMEN, PORCENTAJE, VOLDISMEZ, BPD_M, BPDA_AC, BPDAC_5, BPD_A, BLSEQ, BPDEQ_A) **no**
se modelan aquí (ya están en `fact_produccion_mes_ecp` / `bronze.bdp_datos_mes`).

### Estructura (cabecera en la fila 1; columnas por NOMBRE, robusto a reordenamiento)
- **46 columnas descriptivas** → `dims`: CONCEPTO, SOCIO, BA_ID, OPERADOR, GRUPOOPERADOR, TIPOCONTRATO,
  CONTRATO, FUENTE, IDBDP, FUENTECONTRATOPLOT, FUENTECONTRATO, ESCENARIO, PROCESO, ROW_CHANGED_BY,
  PROPIETARIO, GRUPOPROD, PRODUCTO, TIPOPRODUCTO, NEGOCIO, NUEVAGERENCIA, SUPERINTENDENCIA, TAG, TIPOFUENTE,
  TAGDESCRIPCION, FECHAEFPROP, FECHAEXPROP, FECHAEFPDEN, FECHAEXPDEN, NEGOCIOVPR, GERENCIA, MODALIDAD,
  OPERACION, TIPOCRUDO, NACIONALIDAD, GRUPO1, GRUPO2, GRUPO3, NODO, DILUYENTE, LINEA_ESTRATEGICA,
  MEZCLA_SIV_GAS, PRODUCTO_YACIMIENTO, PROYECCION, ESC_PROY, VICE, ACTIVOS.
- **10 medidas** (cols AO-AX) → solo se usa `BPDEQ_M` como `valor`; el resto se excluye.
- `FECHA` = entero `yyyymmdd`. **97 fechas** (2020-12-31 … 2028-12-31, incluye proyecciones a futuro).
- **4 escenarios**: PPTO (114.725), REAL (75.605), CONTABLE (62.986), OPERATIVO (61.636).

### Conteos verificados (prototipo, archivo NEW canónico)
| Métrica | Valor |
|---|---|
| Filas leídas / emitidas | 314.952 / **314.952** (1 por registro) |
| Claves `(tabla_idx, dims, fecha)` distintas | **314.952** |
| **Colisiones** | **0** (las 46 dims + fecha identifican unívocamente cada registro) |
| `valor = BPDEQ_M` NULL | 0 (todas las filas con valor; 70% ≠0, 30% ceros reales) |
| Fechas | 97 (2020-12-31 … 2028-12-31), 0 NULL |

### 0.g — Flujo profesional v2: incoherencias / no-breakage
1. 🔴 **Incoherencia de escala en `load_tablas_hoja` (INSERT sin chunking)** — hallazgo principal.
   `load_tablas_hoja` (services.py ~1435-1441) es la **única** cargadora del archivo que NO trocea: arma el
   dedup dict completo + una lista de **314.952** param-dicts (con `json.dumps` por fila → **2×** por el key
   del dedup) y ejecuta **un solo `executemany`**. El resto de loaders usan `CHUNK=10_000` (líneas 116-118,
   173-177, 251-254, …). A 40K (PROGRAMA/BDP_datos_dia) es indiferente; a **314K (≈8×)** el pico de memoria
   sube a ~1-1.5 GB y el INSERT es un lote gigante. No es error de correctitud (psycopg canaliza; no hay
   límite de parámetros en `executemany`), pero es un riesgo de escala y una inconsistencia con el patrón del
   archivo. **→ v2 añade troceado a `load_tablas_hoja` (§1.3, `CHUNK=10_000`)**: acota memoria/lote, alinea
   con el resto del archivo y de-riesga ésta y futuras hojas grandes. Cambio seguro (DELETE una vez + INSERT
   por lotes; para hojas <10K es 1 sola iteración, idéntico a hoy). X7 verifica 0 regresión en las 14 hojas.
2. **0 colisiones verificado**: con las 46 dims + fecha cada registro es único → se ingieren exactamente
   314.952 filas, sin pérdida por el dedup last-wins de `load_tablas_hoja`.
3. **`rl()` preserva '(en blanco)'** en las dims (mismo cuidado que TD/DATOS_MES) y convierte fechas
   descriptivas (FECHAEFPROP/…) a ISO. Con esto el conteo distinto = 314.952 (validado). Aislado a este extractor.
4. **Aislamiento del pipeline raw**: `load_tablas_hoja` hace `DELETE … WHERE reporte_id AND hoja='BDP_datos_mes'`
   sobre `core.fact_tabla_hoja` → **no toca** `fact_produccion_mes_ecp` (load_fact_mes, pipeline raw). El
   regex `^BDP_datos_mes$` NO matchea `BDP_datos_dia` ni `DATOS_MES`. `BDP_datos_mes` en `RAW_SHEETS` sigue
   alimentando el fact estrella; este extractor es una escritura adicional independiente a `fact_tabla_hoja`.
5. **Redundancia consciente (D3)**: 4ª copia del dato (star `fact_produccion_mes_ecp` + `bronze` + pivot
   `DATOS_MES` + este raw fino). Autorizado por el usuario.
6. 🟡 **Peso del visor**: `/tablas/datos` carga TODAS las filas de la hoja para armar la tabla ancha y
   luego capa a 1.000. Para BDP_datos_mes son 314.952 filas → el backend tarda unos segundos por vista
   (el cap protege el payload/DOM, no la consulta). Funcional; limitación conocida (igual que BDP_datos_dia
   pero mayor). Sin acción en este plan.
7. **Sin disparadores §0.2 propios**: no toca DDL, clave natural, `ON CONFLICT`, ni la detección raw/STD.
   `_p50_grid` no se usa. Extractor + 1 línea de registro.

### No-breakage
- `fecha=mes` real → visor modo "fechas". 15ª hoja con el MISMO pipeline ⇒ 0 regresión. pytest no aserta nº de hojas.
- Cabecera por NOMBRE (no índice fijo) → robusto si cambia el orden de columnas entre archivos NEW.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_bdp_datos_mes_extract` (insertar después de `_bdp_datos_dia_extract`, antes del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _bdp_datos_mes_extract(ws):
    """Extractor de la hoja RAW mensual plana 'BDP_datos_mes' (solo archivos NEW) → 1 tabla larga temporal
    (fecha=fin de mes), 1 FILA POR REGISTRO (NO se despliegan las 10 medidas → 314.952 filas, no el unpivot).
    valor = BPDEQ_M (barriles/día equivalente mensual, la misma medida del pivot DATOS_MES). dims = 46
    columnas descriptivas (excluye FECHA/MES/AÑO y las 10 medidas). Cabecera en la fila 1 (mapa nombre→índice,
    robusto a reordenamiento). fecha=FECHA (entero yyyymmdd). rl() preserva '(en blanco)' y pasa fechas
    descriptivas a ISO → 0 colisiones (dims+fecha únicos). Cubo multi-año (97 meses 2020-2028, 4 escenarios).
    Grano RAW completo (D3); redundante con fact_produccion_mes_ecp y el pivot DATOS_MES. NO usar _p50_grid."""
    DECLARED = [(1, "BDP_datos_mes (detalle mensual RAW)")]
    it = ws.iter_rows(values_only=True)
    header = None
    for row in it:
        header = row
        break
    if header is None:
        return {"rows": [], "tablas": DECLARED}
    name_at = {}                                 # col-idx -> nombre de cabecera (no vacío)
    for i, h in enumerate(header):
        hn = s(h)
        if hn is not None:
            name_at[i] = hn
    upper = {hn.upper(): i for i, hn in name_at.items()}
    MEAS = ["VOLUMEN", "PORCENTAJE", "VOLDISMEZ", "BPD_M", "BPDA_AC", "BPDAC_5",
            "BPD_A", "BPDEQ_M", "BLSEQ", "BPDEQ_A"]
    if "FECHA" not in upper or "BPDEQ_M" not in upper:
        return {"rows": [], "tablas": DECLARED}
    fecha_i = upper["FECHA"]
    val_i = upper["BPDEQ_M"]
    EXCLUDE = {"FECHA", "MES", "AÑO", "ANO"} | set(MEAS)
    dim_idx = [(i, name_at[i].lower()) for i in sorted(name_at)
               if name_at[i].upper() not in EXCLUDE]

    def rl(v):                                  # dim: preserva '(en blanco)'; fecha→ISO; '' / None = ausente
        if v is None:
            return None
        if isinstance(v, (dt.date, dt.datetime)):
            return v.isoformat()
        t = str(v).strip()
        return None if t == "" else t

    rows = []
    for row in it:
        d = to_date(row[fecha_i]) if fecha_i < len(row) else None
        if d is None:
            continue
        v = num(row[val_i]) if val_i < len(row) else None
        dims = {}
        for i, key in dim_idx:
            if i < len(row):
                val = rl(row[i])
                if val is not None:
                    dims[key] = val
        rows.append({"tabla_idx": 1, "tabla_label": "BDP_datos_mes (detalle mensual RAW)",
                     "dims": dims, "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de BDP_datos_dia)

```python
    # BDP_datos_mes: hoja RAW mensual plana (solo archivos NEW). 1 fila por registro (~314.952 filas),
    # valor=BPDEQ_M; dims=46 descriptivas. Cubo multi-año (2020-2028, 4 escenarios). Redundante con
    # fact_produccion_mes_ecp y el pivot DATOS_MES. Volumen alto (~8x PROGRAMA).
    (re.compile(r"(?i)^BDP_datos_mes$"), _bdp_datos_mes_extract),
```

**NO** agregar imports (`s`, `num`, `to_date`, `dt` ya existen). **NO** usar `_p50_grid`.
**NO** tocar DDL, migraciones, `api.py` ni el frontend. `load_tablas_hoja` **solo** se modifica según §1.3.

### 1.3 — Trocear el INSERT de `load_tablas_hoja` (consistencia + memoria a escala)

En `load_tablas_hoja` (services.py), el bloque `if out:` hace un `executemany` sin trocear. Reemplazar
EXACTAMENTE:

```python
        if out:
            conn.execute(sa.text("""
                INSERT INTO core.fact_tabla_hoja (reporte_id, hoja, tabla_idx, tabla_label, dims, fecha, valor)
                VALUES (:r, :h, :idx, :label, CAST(:dims AS jsonb), :fecha, :valor)
            """), [{"r": reporte_id, "h": hoja, "idx": f["tabla_idx"], "label": f["tabla_label"],
                    "dims": json.dumps(f["dims"], ensure_ascii=False),
                    "fecha": f["fecha"], "valor": f["valor"]} for f in out])
```

por (trocea en lotes de `CHUNK`, ya definido = 10_000 en la cabecera del módulo):

```python
        if out:
            _ins_th = sa.text("""
                INSERT INTO core.fact_tabla_hoja (reporte_id, hoja, tabla_idx, tabla_label, dims, fecha, valor)
                VALUES (:r, :h, :idx, :label, CAST(:dims AS jsonb), :fecha, :valor)
            """)
            for _i in range(0, len(out), CHUNK):
                conn.execute(_ins_th,
                    [{"r": reporte_id, "h": hoja, "idx": f["tabla_idx"], "label": f["tabla_label"],
                      "dims": json.dumps(f["dims"], ensure_ascii=False),
                      "fecha": f["fecha"], "valor": f["valor"]} for f in out[_i:_i + CHUNK]])
```

- **Semántica idéntica**: `DELETE` (una vez, ya presente arriba) + INSERT de las mismas filas, ahora por
  lotes de 10.000. Para hojas con <10.000 filas es **una sola iteración** → comportamiento idéntico al actual.
- **No cambia** el dedup (`by_key`) ni el `resumen`/eventos: solo el bucle de INSERT.
- `CHUNK` ya existe (módulo, línea ~28) — **no** redefinir.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_bdp_datos_dia_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `to_date` y `dt` (import `datetime as dt`) existen en services.py.
3. Nombre exacto de la hoja: `BDP_datos_mes` (regex `^BDP_datos_mes$`; NO debe matchear `BDP_datos_dia`
   ni `DATOS_MES`).
4. `load_tablas_hoja` contiene el bloque `if out:` con el `executemany` único de §1.3 (sin trocear todavía)
   y `CHUNK = 10_000` está definido en la cabecera del módulo. Si el bloque ya trocea o difiere, **DETENERSE**.
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico NEW `2024-10-04`; tomar `<rid>` REAL de la ingesta)

> ⚠️ Re-ingerir el archivo NEW real `"../data/20241004_Reporte New Diario de Producción.xlsm"` y tomar el
> `<rid>` del log (no asumir). La ingesta de esta hoja tarda más (~30-60 s extra) por el volumen.

- **X1 — 1 tabla:** `GET /tablas?...&hoja=BDP_datos_mes` → 1 ítem (idx 1, "BDP_datos_mes (detalle mensual RAW)").
- **X2 — conteo (BD):** **314952 filas** en `core.fact_tabla_hoja`.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — contenido:** **97** fechas distintas `2020-12-31 … 2028-12-31`, 0 `fecha IS NULL`;
  `dims->>'escenario'` ∈ {PPTO, REAL, CONTABLE, OPERATIVO}.
- **X5 — spot-check:** `idbdp='38897', escenario='CONTABLE', concepto='PROPIEDAD', propietario='ECOPETROL',
  fecha='2023-05-31'` → `72.39096774193548`.
- **X6 — idempotencia:** re-ingerir → mismos conteos (314952).
- **X7 — no-breakage (crítico por §1.3, cambio compartido):** las 14 hojas previas + COMENTARIOS intactas.
  **Verificación especial de las hojas que ahora trocean (>10.000 filas):** `PROGRAMA`=**39431** y
  `BDP_datos_dia`=**40236** deben dar EXACTAMENTE el mismo conteo que antes del cambio (el troceado no altera
  filas). Además `DATOS_MES`=7776, `TD_datos_dia`=5209, `INICIO`=80, etc.; `fact_produccion_mes_ecp`=314952,
  `fact_produccion_dia_ecp`=8628, `fact_comentarios_produccion`=35; `uv run pytest -q` verde (6/1).
- **X8 — visor:** `GET /tablas/datos?...&hoja=BDP_datos_mes&tabla_idx=1` → `len(filas)`=**1000** y
  `total_filas` (nº de combos de dims) grande. (Puede tardar unos segundos por el volumen.)

```sql
-- X2/X3
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_mes';   -- 314952
SELECT count(*) FROM (SELECT 1 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_mes'
  GROUP BY tabla_idx,dims,fecha HAVING count(*)>1) x;                                        -- 0
-- X4
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL),
       count(DISTINCT dims->>'escenario')
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_mes';                  -- 97, 0, 4
-- X5
SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_mes'
   AND fecha='2023-05-31' AND dims->>'idbdp'='38897' AND dims->>'escenario'='CONTABLE'
   AND dims->>'concepto'='PROPIEDAD' AND dims->>'propietario'='ECOPETROL';                   -- 72.3909677...
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1, §1.2 y §1.3 TAL CUAL. **1 fila por registro** (NO desplegar las 10 medidas). `valor=BPDEQ_M`.
  El cambio §1.3 (troceado) NO altera dedup ni resumen; si tras aplicarlo alguna hoja previa cambia de conteo,
  **DETENERSE** (X7).
- **4.2** Cabecera por NOMBRE (fila 1), no por índice fijo. `fecha=mes` real (nunca NULL; filas sin fecha se omiten).
- **4.3** `rl()` en las dims (preserva `"(en blanco)"`, fechas→ISO). Excluir FECHA/MES/AÑO y las 10 medidas.
- **4.4** No commit/push salvo que se pida. No tocar prod 139.
- **4.5** Si una validación falla, **DETENERSE y reportar el delta**. En especial, X2 debe dar 314952
  (si da menos, hay colisiones → reportar sin "arreglar" recortando dims).

---

## 5. Fuera de alcance
- Las 9 medidas distintas de `BPDEQ_M` (ya en `fact_produccion_mes_ecp` / `bronze.bdp_datos_mes`).
- El unpivot de las 10 medidas (daría ~3,15M filas): descartado por decisión del usuario (1 fila por registro).
- FECHA/MES/AÑO como dims (fecha se extrae; MES/AÑO derivadas).
- Paginación real del visor / LIMIT a nivel SQL en `/tablas/datos`: el cap de 1.000 cubre la presentación;
  optimizar la carga del backend para tablas de cientos de miles de filas es mejora futura (no en este plan).
