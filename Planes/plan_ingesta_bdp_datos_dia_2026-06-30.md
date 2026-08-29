# Plan ejecutable (v2) — Modelado RAW de "BDP_datos_dia" → `core.fact_tabla_hoja` + cap de 1000 filas en el visor

> **Cobertura: Tablas: entrada 1 → salida 1** (grano RAW completo por unpivot de 5 medidas).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `BDP_datos_dia` (solo archivos NEW)
> **Archivos a tocar (3):**
> 1. `backend/app/features/ingesta/services.py` — nuevo extractor + 1 línea de registro.
> 2. `backend/app/features/tablas/api.py` — cap de **1000 filas** en el payload del visor (+ `total_filas`).
> 3. `static/js/chat.js` (app ProdIA) — `renderTablaAncha`: indicador "mostrando 1.000 de N".
> **Migración:** NINGUNA. **DDL:** SIN cambios.

---

## 0. Auditoría (datos reales)

`BDP_datos_dia` es una de las **3 hojas RAW planas** (`RAW_SHEETS`), **no un pivot**. **8.628 filas × 30
columnas**, 1 fila = 1 registro atómico. **Solo existe en archivos NEW** (los STD no la traen). Decisión
del usuario: **opción A** — modelar el grano RAW completo en `fact_tabla_hoja` para inspección fina, **+**
limitar el visor a **1.000 filas** (la BD guarda todo; el visor solo muestra las primeras 1.000).

### Estructura (cabecera en fila 1; columnas por NOMBRE, robusto a reordenamiento)
- **25 descriptivas**: CONCEPTO, SOCIO, OPERADOR, TIPOCONTRATO, CONTRATO, FUENTE, IDBDP, FUENTECONTRATO,
  FECHA, MES, AÑO, ESCENARIO, PROPIETARIO, GRUPOPROD, PRODUCTO, TIPOPRODUCTO, GERENCIA, MODALIDAD,
  OPERACION, NACIONALIDAD, GRUPO1, GRUPO2, GRUPO3, VICE, ACTIVOS.
- **5 medidas**: `VOLUMEN, PORCENTAJE, VOLDISMEZ, VOL_ESTIMADO, PROMEDIO`.
- `FECHA` = entero `yyyymmdd`. **4 fechas** (2024-09-30 … 2024-10-03). `ESCENARIO` = **solo REAL**.

### Modelo (unpivot de las 5 medidas → 1 tabla larga temporal)
- `dims` = las descriptivas **excepto FECHA/MES/AÑO** (la fecha se extrae; MES/AÑO son derivadas) **+
  `medida`** = **23 claves**. `fecha = día`. `valor` = valor de la medida.
- Cada fila raw es **atómica** (no hay subtotales ni ffill) → se usa `s()` (no `rl()`); un atributo vacío
  simplemente no aparece en `dims`.
- **Emite 1 fila por (registro × medida con valor no nulo)**, conservando 0 reales (D3).

### Conteos verificados (prototipo, archivo NEW canónico — 0 colisiones)
| Métrica | Valor |
|---|---|
| Filas largas emitidas | **40.236** |
| Colisiones `(tabla_idx,dims,fecha)` | **0** (40.236 claves distintas) |
| Fechas | 4 (2024-09-30 … 2024-10-03), 0 NULL |
| Por medida | VOLUMEN 7.989 · PORCENTAJE 8.628 · VOLDISMEZ 8.628 · VOL_ESTIMADO 8.544 · PROMEDIO 6.447 |
| dim-keys | 23 (22 descriptivas + `medida`) |

⚠️ **Volumen ~40K** (mismo orden que PROGRAMA=39.431, probado por el mismo `load_tablas_hoja`).

### Redundancia (consciente, aceptada — opción A)
El dato ya vive en `fact_produccion_dia_ecp` (8.628), en el pivot `TD_datos_dia` (5.209, ya en el visor)
y en `bronze.bdp_datos_dia` (8.628). Esta es la 4ª copia, al grano RAW fino, para inspección.

### No-breakage
- `fecha=día` real → visor en modo "fechas". 13ª hoja con el MISMO pipeline ⇒ 0 regresión.
- Cabecera por NOMBRE (no por índice fijo) → robusto si cambia el orden de columnas entre archivos NEW.
- El cap del visor es **solo de presentación**: la ingesta guarda las 40.236 filas completas.

### 0.g — Flujo profesional v2: incoherencias / no-breakage (código y BD reales)
1. ✅ **Proxy Flask es PASS-THROUGH** (`routes/api.py:101` → `jsonify(resp.json())`): reenvía el JSON tal
   cual, así que `total_filas` llega al frontend **sin tocar el proxy**. Confirmado.
2. ✅ **Orquestación sin conflicto**: `load_tablas_hoja` (services.py:1523) corre sobre TODO el registro,
   **independiente** del pipeline raw (`load_fact_dia` :1453 → `fact_produccion_dia_ecp`) y del bronze
   tipado (`land_bronze_typed` :1431 → `bronze.bdp_datos_dia`). Añadir `BDP_datos_dia` al registro = una 3ª
   escritura sobre la MISMA hoja a una tabla distinta (`fact_tabla_hoja`); el `DELETE` de `load_tablas_hoja`
   está acotado a `(reporte_id, hoja)`. Sin colisión.
3. 🟡 **Export/Search operan sobre lo mostrado** (`igExportCSV` chat.js:4692, `igSearch` :4678 leen
   `__igTable.filas`, ya capado). Con el cap, **exportar y buscar usan las 1.000 cargadas**, no las 40.236.
   NO es truncación silenciosa: el pie dice "mostrando las primeras 1.000 de N". El grano completo queda en
   la BD para SQL/endpoints. Decisión documentada (alternativa futura: endpoint de export full sin cap).
4. 🔴 **El cap GLOBAL afecta a más hojas que BDP_datos_dia** — transparencia (principio "no silent caps").
   Medido en la BD: en el estado NEW real se capan las tablas con >1000 combos en el visor:
   **`TD_datos_dia`** (~1.302 combos = 5.209 filas / 4 días) **y `BDP_datos_dia`** (la nueva). En cambio
   **`DATOS_MES`** (~648 combos = 7.776 / 12 meses) y el resto quedan **por debajo de 1.000 → sin cap**. El
   indicador del pie lo deja explícito en cada tabla. (Coherente con "no hay necesidad mostrar todo".)
5. 🔴 **Deriva del entorno dev (no causada por este cambio, pero afecta la verificación)**: `config_reporte`
   muestra que **`reporte_id=4` fue sobrescrito** por `20241004_..._TEST (1).xlsm` (ingestado 2026-06-30
   16:15), detectado **STD/SIN_ECP** → su `DATOS_MES` es un cubo de 97 meses (46.196 filas) y **no trae
   `BDP_datos_dia`** (0 filas). Como `reporte_id` se llavea por fecha de reporte (2024-10-04), **al ejecutar
   este plan se re-ingiere el archivo NEW real** "20241004_Reporte New Diario de Producción.xlsm" →
   `reporte_id=4` vuelve a su estado NEW (BDP_datos_dia raw presente, DATOS_MES=7776, etc.). ⚠️ Esto
   **reemplaza los datos del TEST en `reporte_id=4`**: requiere visto bueno del usuario antes de ejecutar.
   La validación usa el `<rid>` REAL devuelto por la ingesta (no asume 4).
6. ✅ **Sin disparadores de riesgo §0.2 propios**: no toca DDL, clave natural, `ON CONFLICT`, ni la
   detección raw/STD (§4). El extractor lee `BDP_datos_dia` por su cuenta; el pipeline raw lo sigue leyendo
   para `fact_produccion_dia_ecp` (sin cambios). `_p50_grid` no se usa.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_bdp_datos_dia_extract` (insertar después de `_datos_mes_extract`, antes del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _bdp_datos_dia_extract(ws):
    """Extractor de la hoja RAW plana 'BDP_datos_dia' (solo archivos NEW) → 1 tabla larga temporal
    (fecha=día) por UNPIVOT de las 5 medidas (VOLUMEN/PORCENTAJE/VOLDISMEZ/VOL_ESTIMADO/PROMEDIO).
    dims = columnas descriptivas (excluye FECHA/MES/AÑO y las medidas) + 'medida'. Cabecera en la fila 1
    (mapa nombre→índice, robusto a reordenamiento de columnas). fecha=FECHA (entero yyyymmdd). Emite una
    fila por cada (registro × medida con valor no nulo), conservando 0 reales (~40K filas). Grano RAW
    completo (D3). Cada fila raw es atómica → se usa s() (no hay subtotales ni ffill). Redundante con
    fact_produccion_dia_ecp y con el pivot TD_datos_dia; aquí al grano fino para el visor."""
    DECLARED = [(1, "BDP_datos_dia (detalle diario RAW)")]
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
    MEAS = ["VOLUMEN", "PORCENTAJE", "VOLDISMEZ", "VOL_ESTIMADO", "PROMEDIO"]
    if "FECHA" not in upper or not any(m in upper for m in MEAS):
        return {"rows": [], "tablas": DECLARED}
    fecha_i = upper["FECHA"]
    EXCLUDE = {"FECHA", "MES", "AÑO", "ANO"} | set(MEAS)
    dim_idx = [(i, name_at[i].lower()) for i in sorted(name_at)
               if name_at[i].upper() not in EXCLUDE]
    meas_idx = [(upper[m], m) for m in MEAS if m in upper]
    rows = []
    for row in it:
        d = to_date(row[fecha_i]) if fecha_i < len(row) else None
        if d is None:
            continue
        base = {}
        for i, key in dim_idx:
            if i < len(row):
                val = s(row[i])
                if val is not None:
                    base[key] = val
        for mi, mname in meas_idx:
            v = num(row[mi]) if mi < len(row) else None
            if v is None:
                continue
            dims = dict(base)
            dims["medida"] = mname
            rows.append({"tabla_idx": 1, "tabla_label": "BDP_datos_dia (detalle diario RAW)",
                         "dims": dims, "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de DATOS_MES)

```python
    # BDP_datos_dia: hoja RAW plana (solo archivos NEW). Unpivot de 5 medidas -> ~40K filas largas
    # (fecha=día). Grano RAW completo; redundante con fact_produccion_dia_ecp y el pivot TD_datos_dia.
    (re.compile(r"(?i)^BDP_datos_dia$"), _bdp_datos_dia_extract),
```

**NO** agregar imports (`s`, `num`, `to_date` ya existen). **NO** usar `_p50_grid`.

### 1.3 — Cap de 1000 filas en el visor: `backend/app/features/tablas/api.py`

Añadir, **justo después de** `router = APIRouter(prefix="/tablas", tags=["tablas"])`:

```python
CAP_FILAS = 1000   # el visor solo muestra las primeras N filas (la BD guarda todo); ver total_filas
```

Y en `def datos(...)`, **cada uno de los 3 `return` con `filas`** (texto, matriz, fechas) debe capar la
lista y reportar el total. Reemplazar EXACTAMENTE:

- **Modo texto** — reemplazar:
  ```python
        return {"modo": "texto", "dimensiones": ["producto", "activos", "area"],
                "meses": cols, "filas": filas}
  ```
  por:
  ```python
        return {"modo": "texto", "dimensiones": ["producto", "activos", "area"],
                "meses": cols, "filas": filas[:CAP_FILAS], "total_filas": len(filas)}
  ```

- **Modo matriz** — reemplazar:
  ```python
        return {"modo": "matriz", "dimensiones": ["fila"], "meses": cols, "filas": filas}
  ```
  por:
  ```python
        return {"modo": "matriz", "dimensiones": ["fila"], "meses": cols,
                "filas": filas[:CAP_FILAS], "total_filas": len(filas)}
  ```

- **Modo fechas** (último return) — reemplazar:
  ```python
    return {"dimensiones": dim_keys, "meses": meses, "filas": filas}
  ```
  por:
  ```python
    return {"dimensiones": dim_keys, "meses": meses,
            "filas": filas[:CAP_FILAS], "total_filas": len(filas)}
  ```

> El cap es GLOBAL (todas las tablas): tablas ≤1000 filas no cambian (total_filas == filas mostradas);
> tablas >1000 (BDP_datos_dia, PROGRAMA) se muestran capadas con indicador. La BD conserva todo.

### 1.4 — Indicador en el frontend: `static/js/chat.js`, función `renderTablaAncha`

Dentro de `renderTablaAncha`, tras la línea `const meses = data.meses || [];`, añadir:

```javascript
  const _total = (typeof data.total_filas === "number") ? data.total_filas : (data.filas || []).length;
  const _capped = _total > (data.filas || []).length;
  const _nf = (n) => Number(n).toLocaleString("es-CO");
```

Reemplazar el `<span class="ig-dt__count">` (el del título) EXACTAMENTE:
- de:
  ```javascript
        <span class="ig-dt__count">${data.filas.length} filas × ${meses.length} ${(esMatriz || esTexto) ? "columnas" : "meses"}</span></div>
  ```
- a:
  ```javascript
        <span class="ig-dt__count">${_nf(data.filas.length)}${_capped ? ` de ${_nf(_total)}` : ""} filas × ${meses.length} ${(esMatriz || esTexto) ? "columnas" : "meses"}</span></div>
  ```

Reemplazar el `<div class="ig-dt__foot">` EXACTAMENTE:
- de:
  ```javascript
      <div class="ig-dt__foot"><span id="ig-visible">${data.filas.length}</span>&nbsp;filas visibles
  ```
- a:
  ```javascript
      <div class="ig-dt__foot"><span id="ig-visible">${data.filas.length}</span>&nbsp;filas visibles${_capped ? ` · <strong>mostrando las primeras ${_nf(data.filas.length)} de ${_nf(_total)}</strong> (límite del visor; la base guarda todo)` : ""}
  ```

> Búsqueda/exportar operan sobre las filas cargadas (las 1.000 mostradas) — comportamiento esperado del cap.

**NO** tocar DDL, migraciones, `load_tablas_hoja`, ni la ruta proxy Flask `/api/tablas-hoja/datos`.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_datos_mes_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `to_date` existen en services.py.
3. `tablas/api.py` tiene `def datos(...)` con los 3 `return` indicados (texto/matriz/fechas).
4. `static/js/chat.js` tiene `renderTablaAncha` con las líneas a reemplazar (título y foot) TAL CUAL.
5. Nombre exacto de la hoja: `BDP_datos_dia` (regex `^BDP_datos_dia$`; NO debe matchear `BDP_datos_mes`
   ni `DATOS_MES`).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico NEW `2024-10-04`; tomar `<rid>` de la ingesta)

> ⚠️ **Pre-paso obligatorio (v2):** re-ingerir el archivo NEW REAL
> `"../data/20241004_Reporte New Diario de Producción.xlsm"` (NO el `_TEST`). Tomar el `<rid>` REAL del log
> de ingesta (`reporte_id=…`) y usarlo en TODAS las consultas (no asumir 4). Tras la ingesta, `config_reporte`
> para `<rid>` debe mostrar `tipo_archivo=NEW`, `tiene_raw=true`, `archivo_nombre` SIN `_TEST`.

- **X1 — 1 tabla:** `GET /tablas?...&hoja=BDP_datos_dia` → 1 ítem (idx 1, "BDP_datos_dia (detalle diario RAW)").
- **X2 — conteo (BD, NO capado):** **40236 filas** en `core.fact_tabla_hoja`.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — contenido:** 4 fechas distintas `2024-09-30 … 2024-10-03`, 0 `fecha IS NULL`;
  `dims->>'medida'` ∈ {VOLUMEN, PORCENTAJE, VOLDISMEZ, VOL_ESTIMADO, PROMEDIO}; `dims->>'escenario'`=REAL.
- **X5 — spot-check:** `idbdp='38752', concepto='PROPIEDAD', propietario='SOCIOS', medida='PORCENTAJE',
  fecha='2024-09-30'` → `0.344`.
- **X6 — idempotencia:** re-ingerir → mismos conteos (40236).
- **X7 — no-breakage (post re-ingesta del archivo NEW real):** las 12 hojas previas + DATOS_MES + COMENTARIOS
  vuelven a sus valores NEW (DATOS_MES=**7776**, TD_datos_dia=5209, …); `fact_produccion_mes_ecp`=314952,
  `fact_produccion_dia_ecp`=8628, `fact_comentarios_produccion`=35; `uv run pytest -q` verde.
- **X8 — cap del visor:** `GET /tablas/datos?...&hoja=BDP_datos_dia&tabla_idx=1` → `len(filas)` = **1000**
  y `total_filas` > 1000. Para una tabla pequeña (p.ej. `hoja=INICIO`) → `len(filas)` == `total_filas`
  (sin cap). El frontend muestra "mostrando las primeras 1.000 de N".
- **X9 — cap-impact reconfirmado (estado NEW real):** en `<rid>`, las únicas hojas con >1000 filas de
  visor son `BDP_datos_dia` (~varios miles) y `TD_datos_dia` (~1302); `DATOS_MES` (~648) y el resto quedan
  por debajo de 1000 (sin cap). Confirma que el cap global no recorta tablas que antes se veían completas
  salvo `TD_datos_dia` (esperado y señalizado).

```sql
-- X2/X3
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_dia';   -- 40236
SELECT count(*) FROM (SELECT 1 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_dia'
  GROUP BY tabla_idx,dims,fecha HAVING count(*)>1) x;                                        -- 0
-- X4
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL),
       count(DISTINCT dims->>'medida'), count(DISTINCT dims->>'escenario')
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_dia';                  -- 4,0,5,1
-- X5
SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_datos_dia'
   AND fecha='2024-09-30' AND dims->>'idbdp'='38752' AND dims->>'concepto'='PROPIEDAD'
   AND dims->>'propietario'='SOCIOS' AND dims->>'medida'='PORCENTAJE';                        -- 0.344
```

Para X8, llamar al endpoint (curl o el proxy Flask) y comprobar `len(filas)` y `total_filas`.

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1–§1.4 TAL CUAL. Grano RAW completo en la BD (40236); el cap es SOLO de presentación.
- **4.2** Cabecera por NOMBRE (fila 1), no por índice fijo. `fecha=día` real (nunca NULL).
- **4.3** `s()` en los campos (no `rl()`): la hoja raw es atómica, sin subtotales ni `(en blanco)` de pivot.
- **4.4** El cap `CAP_FILAS=1000` es global y SOLO afecta el payload del visor; `load_tablas_hoja` y la BD
  guardan todas las filas. No cambiar la ruta proxy Flask.
- **4.5** No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta**.

---

## 5. Fuera de alcance
- Las columnas FECHA/MES/AÑO como dims (fecha se extrae; MES/AÑO son derivadas redundantes).
- Recalcular/normalizar medidas (se ingieren tal cual desde la celda).
- Paginación real del visor (scroll infinito / "cargar más"): el cap simple de 1.000 cubre el requisito;
  la BD conserva el grano completo para análisis vía SQL/endpoints.
