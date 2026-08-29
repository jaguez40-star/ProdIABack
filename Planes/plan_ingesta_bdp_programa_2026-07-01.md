# Plan ejecutable (v2) — Modelado RAW de "BDP_Programa" → `core.fact_tabla_hoja` (1 fila por registro, 14 columnas)

> **Cobertura: Tablas: entrada 1 → salida 1** (grano RAW del programa; **1 fila por registro**, SIN unpivot →
> 13.822 filas. Decisión explícita del usuario: "13.823 filas × 14 columnas, esa es la ingesta". M = N, sin
> reducción de alcance; las 3 medidas y las 14 columnas se preservan íntegras → D3).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-07-01 · **Autor:** Claude · **Hoja:** `BDP_Programa` (solo archivos NEW)
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA. **DDL / api.py / frontend:** SIN cambios (visor genérico ya soporta el modo "fechas";
> el troceado de `load_tablas_hoja` ya está aplicado en una sesión previa → este plan NO lo toca).

---

## 0. Auditoría (datos reales, archivo NEW canónico `20241004`)

`BDP_Programa` es una de las **3 hojas RAW planas** (`RAW_SHEETS`), **solo en archivos NEW** (detección por
presencia de hoja, §4/§4c). Es el **programa de producción** (horizonte a futuro). **13.822 filas × 14 columnas**,
1 fila = 1 registro atómico (pozo/producto × fecha del programa). Coincide con **§4b** del CLAUDE.md (13.822×14,
3 medidas). Ya alimenta la estrella `core.fact_programa_ecp` (`load_fact_programa`, §5) y su landing
`bronze.bdp_programa`.

### Decisión de modelado (usuario): 1 fila por registro (13.822), SIN unpivot, 14 columnas preservadas
`fact_tabla_hoja` tiene **un** `valor` por fila. Se modela **1 fila por registro** con la medida cabecera del
programa **`Volumen`** (cuota ECP programada) como `valor`. Para **no perder ninguna columna** (14 en total),
las otras 2 medidas **`Produccion_total`** y **`Part_ECP`** se **preservan como `dims`** (texto). El unpivot de
las 3 medidas (que daría 41.466 filas) queda **descartado** por decisión del usuario.

### Estructura (cabecera en la fila 1; columnas por NOMBRE, robusto a reordenamiento)
Header exacto (= `BZ_PRG` posicional): `Fecha, VICE, GERENCIA, VERSION, Fecha Version, Estado, Volumen, Campo,
Producto, AREA, IDBDP, Contrato, Produccion_total, Part_ECP`. Reparto de las 14 columnas:

| Columna hoja | Destino | Cómo |
|---|---|---|
| `Fecha` | **`fecha`** | `to_date` (string `yyyymmdd` → date) |
| `Volumen` | **`valor`** | `num` — medida principal (cuota ECP programada) |
| `VICE`,`GERENCIA`,`VERSION`,`Fecha Version`,`Estado`,`Campo`,`Producto`,`AREA`,`IDBDP`,`Contrato` | **`dims`** | `rl()`; clave = header en minúsculas con espacios→`_` (`Fecha Version` → `fecha_version`) |
| `Produccion_total`, `Part_ECP` | **`dims`** | `rl()` — preservadas como dims (medidas secundarias) |

### Conteos verificados (simulación del extractor propuesto, archivo NEW canónico)
| Métrica | Valor |
|---|---|
| Filas leídas / emitidas | 13.822 / **13.822** (1 por registro) |
| Claves `(tabla_idx, dims, fecha)` distintas | **13.822** |
| **Colisiones** | **0** (las 12 dims + fecha identifican unívocamente cada registro) |
| `valor = Volumen` NULL | 0 |
| Fechas | **61** (`2024-10-01 … 2024-11-30`, horizonte del programa a futuro), 0 NULL |
| Dims presentes (unión, tras normalización de clave) | `area, campo, fecha_version, gerencia, idbdp, part_ecp, produccion_total, producto, version, vice` |
| `produccion_total` / `part_ecp` como dim | 13.822 / 13.822 filas (preservadas en TODAS) |
| `estado` / `contrato` como dim | 0 / 0 (columnas **vacías** en este archivo → no aparecen; el extractor las mapea si otro archivo las puebla) |
| Combos de dims distintos (filas del visor "fechas") | **9.130** |
| Productos | 3: CRUDO, GAS, BLANCOS · Vices | 6: VAO, VEX, VFS, VPI, VRC, VRO |
| Filas `Total`/`Subtotal`/`(en blanco)` | **0** (verificado: tabla plana atómica, sin subtotales) |

### 0.g — Flujo profesional: incoherencias / no-breakage / trade-offs
1. 🟡 **`Produccion_total`/`Part_ECP` como `dims`, no como medidas** (trade-off principal, decidido con el
   usuario). Como `fact_tabla_hoja` tiene un solo `valor` y el usuario exige preservar las 14 columnas, las 2
   medidas secundarias van a `dims` (texto). **Consecuencia en el visor "fechas":** al variar por fecha, el
   agrupamiento por dims produce **9.130 combos** (algunos con 1 sola fecha poblada) en vez de un pivote
   compacto pozo×fecha. Es **fiel** (D3, ninguna columna se pierde) y es lo pedido; la granularidad extra del
   visor es la contrapartida. Sin acción. (Alternativa "solo Volumen" descartada por el usuario.)
2. **0 colisiones verificado**: con las 12 dims + fecha cada registro es único → se ingieren exactamente
   13.822 filas, sin pérdida por el dedup last-wins de `load_tablas_hoja`.
3. **Aislamiento del pipeline raw**: `load_tablas_hoja` hace `DELETE … WHERE reporte_id AND hoja='BDP_Programa'`
   sobre `core.fact_tabla_hoja` → **no toca** `core.fact_programa_ecp` (`load_fact_programa`, pipeline raw) ni
   `bronze.bdp_programa`. `BDP_Programa` sigue en `RAW_SHEETS` alimentando la estrella; este extractor es una
   escritura adicional **independiente** a `fact_tabla_hoja`.
4. 🔴 **Colisión de regex con la hoja `PROGRAMA` (verificado disjunto)**: ya existe `_programa_extract` con
   `re.compile(r"(?i)^PROGRAMA$")` (la hoja de pivots "PROGRAMA", distinta de esta RAW). El nuevo regex
   **`^BDP_Programa$`** NO matchea `PROGRAMA` (anclado a inicio) y `^PROGRAMA$` NO matchea `BDP_Programa`. Son
   disjuntos → cada hoja va a su extractor. (Con `(?i)`, ambos case-insensitive.) X7 lo confirma (PROGRAMA=39431 sin cambio).
5. **§1.3 (troceado de `load_tablas_hoja`) YA aplicado** en sesión previa (services.py ~1495-1504, `CHUNK=10_000`).
   Este plan **no** lo modifica. Con 13.822 filas el INSERT usa **2 lotes** (ya es el camino de código actual;
   sin riesgo). No hay cambio compartido → el riesgo de regresión en otras hojas es nulo (aun así X7 lo verifica).
6. **Redundancia consciente (D3)**: 3.ª copia del dato (estrella `fact_programa_ecp` + `bronze.bdp_programa` +
   este raw en `fact_tabla_hoja`). Autorizado por el usuario. Sin pérdida: valor + 2 medidas-dim + 9 descriptivas.
7. **Sin disparadores §0.2 que crucen D1–D3**: no toca DDL, clave natural (`uk_prog`), `ON CONFLICT`, ni la
   detección raw/STD. `_p50_grid` no se usa. Extractor + 1 línea de registro.
8. ✅ **Ruido/subtotales verificados = 0** (§7.5): 0 filas con `Total`/`Subtotal`/`(en blanco)`, 0 sin fecha,
   0 sin idbdp, 0 sin producto. **No se requiere lógica de exclusión**; `rl()` (descarta NOISE) es suficiente
   defensa para otros archivos.
9. ✅ **Estabilidad de layout (§0.2)**: la estrella `load_fact_programa` ya lee `BDP_Programa` **por posición**
   (`row[0]..row[13]`) sobre los **16 archivos NEW** del corpus en producción → el **orden de columnas es
   estable**. Este extractor usa cabecera **por NOMBRE** (aún más robusto a reordenamientos). Localmente solo
   hay 1 archivo NEW (`20241004`), pero el esquema está DDL-validado (§4b) y el pipeline estrella prueba la
   estabilidad en el corpus. Los conteos de las validaciones (13.822/61/9.130) son **específicos de `20241004`**;
   otros NEW traen otras cifras (§4c) — el extractor NO fija conteos (sin hardcode), solo nombres de columna.

### No-breakage
- **Solo NEW**: `BDP_Programa ∈ RAW_SHEETS` → los STD (`20231231`, `20240211`) no la tienen; el regex no matchea
  → extractor no dispara en STD (0 regresión).
- `fecha` real (nunca NULL; filas sin fecha se omiten) → visor modo "fechas". **16.ª hoja** con el MISMO
  pipeline ⇒ 0 regresión. `pytest` no aserta nº de hojas.
- Cabecera por NOMBRE (no índice fijo) → robusto si cambia el orden de columnas entre archivos NEW.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_bdp_programa_extract` (insertar **después** de `_bdp_datos_mes_extract`, **antes** del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _bdp_programa_extract(ws):
    """Extractor de la hoja RAW plana 'BDP_Programa' (solo archivos NEW) → 1 tabla larga temporal
    (fecha = fecha del programa), 1 FILA POR REGISTRO (13.822; SIN unpivot de las 3 medidas). valor = Volumen
    (cuota ECP programada). dims = las 12 columnas restantes, incluyendo Produccion_total y Part_ECP
    preservadas como dims (para no perder ninguna columna: decisión del usuario '13.823x14 = la ingesta').
    Cabecera en la fila 1 (mapa nombre→índice, robusto a reordenamiento); clave de dim = header en minúsculas
    con espacios→'_' (p.ej. 'Fecha Version' -> 'fecha_version'). fecha=Fecha (string yyyymmdd). rl() pasa fechas
    descriptivas a ISO y descarta ruido/'(en blanco)'. 0 colisiones (dims+fecha únicos). Tabla plana atómica
    (0 subtotales verificados). Grano RAW completo (D3); 3.er destino, redundante con bronze.bdp_programa y la
    estrella core.fact_programa_ecp."""
    DECLARED = [(1, "BDP_Programa (programa RAW)")]
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
    if "FECHA" not in upper or "VOLUMEN" not in upper:
        return {"rows": [], "tablas": DECLARED}
    fecha_i = upper["FECHA"]
    val_i = upper["VOLUMEN"]
    # dims = todas las columnas con cabecera excepto FECHA (→fecha) y VOLUMEN (→valor).
    # Produccion_total y Part_ECP quedan como dims (no se pierde ninguna de las 14 columnas).
    # clave = header.lower() con espacios→'_' (limpia 'Fecha Version' -> 'fecha_version').
    EXCLUDE = {"FECHA", "VOLUMEN"}
    dim_idx = [(i, name_at[i].lower().replace(" ", "_")) for i in sorted(name_at)
               if name_at[i].upper() not in EXCLUDE]

    def rl(v):                                  # dim: fecha→ISO; ruido/'(en blanco)'/'' / None = ausente
        if v is None:
            return None
        if isinstance(v, (dt.date, dt.datetime)):
            return v.isoformat()
        t = str(v).strip()
        return None if t in NOISE else t

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
        rows.append({"tabla_idx": 1, "tabla_label": "BDP_Programa (programa RAW)",
                     "dims": dims, "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea **después** de la de BDP_datos_mes)

```python
    # BDP_Programa: hoja RAW plana del PROGRAMA (solo archivos NEW). 1 fila por registro (13.822 filas),
    # valor=Volumen; dims=12 (incl. Produccion_total y Part_ECP preservadas). Horizonte a futuro (fecha del
    # programa). 3.er destino, redundante con core.fact_programa_ecp y bronze.bdp_programa. Regex disjunto de ^PROGRAMA$.
    (re.compile(r"(?i)^BDP_Programa$"), _bdp_programa_extract),
```

**NO** agregar imports (`s`, `num`, `to_date`, `NOISE`, `dt` ya existen). **NO** usar `_p50_grid`.
**NO** tocar DDL, migraciones, `api.py`, el frontend, ni `load_tablas_hoja` (su troceado ya está aplicado).

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_bdp_datos_mes_extract` existe y el bloque `# === Registro de hojas modeladas: ...` / `HOJAS_MODELADAS`
   está justo después (insertar el nuevo extractor entre ambos).
2. `s`, `num`, `to_date`, `NOISE` y `dt` (import `datetime as dt`) existen en services.py.
3. Nombre exacto de la hoja: `BDP_Programa` (regex `^BDP_Programa$`; NO debe matchear `PROGRAMA` ni
   `BDP_datos_dia`/`BDP_datos_mes`). Ya existe `(re.compile(r"(?i)^PROGRAMA$"), _programa_extract)` — dejarla intacta.
4. `load_tablas_hoja` **ya trocea** el INSERT (`for _i in range(0, len(out), CHUNK)`, `CHUNK=10_000`). Si NO
   troceara, **DETENERSE** (este plan asume el troceado ya aplicado; no lo re-aplica).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico NEW `2024-10-04`; tomar `<rid>` REAL de la ingesta)

> ⚠️ Re-ingerir el archivo NEW real `"../data/20241004_Reporte New Diario de Producción.xlsm"` y tomar el
> `<rid>` del log (no asumir). Confirmar que ese `<rid>` es **tipo NEW** en `core.config_reporte`
> (`SELECT tipo_archivo FROM core.config_reporte WHERE reporte_id=:rid` → `NEW`); si sale STD, se ingirió el
> archivo equivocado (BDP_Programa no existiría) → **DETENERSE**.

- **X1 — 1 tabla:** `GET /tablas?...&hoja=BDP_Programa` → 1 ítem (idx 1, `"BDP_Programa (programa RAW)"`).
- **X2 — conteo (BD):** **13822 filas** en `core.fact_tabla_hoja`.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — contenido:** **61** fechas distintas `2024-10-01 … 2024-11-30`, 0 `fecha IS NULL`;
  `dims->>'producto'` ∈ {CRUDO, GAS, BLANCOS} (3); `dims->>'vice'` (6).
- **X5 — spot-check (verifica valor + preservación de las 2 medidas + clave limpia como dims):**
  `idbdp='47023', producto='CRUDO', fecha='2024-10-02'` → `valor = 119.5402`,
  `dims->>'produccion_total' = '225.5475'`, `dims->>'part_ecp' = '53'`, `dims->>'area' = 'SURORIENTE'`,
  `dims->>'fecha_version' = '20240927'` (clave sin espacio).
- **X6 — idempotencia:** re-ingerir → mismos conteos (13822, 0 colisiones).
- **X7 — no-breakage (crítico):** las 15 hojas previas + COMENTARIOS intactas. En particular
  `PROGRAMA`=**39431** (la hoja de pivots, NO debe cambiar por el nuevo `BDP_Programa` → confirma regex disjunto),
  `BDP_datos_mes`=314952, `BDP_datos_dia`=40236, `DATOS_MES`=7776, `TD_datos_dia`=5209, `INICIO`=80. Facts
  estrella **sin cambio** respecto al valor previo a aplicar el plan (este extractor no los toca):
  `fact_programa_ecp` (igual que antes), `fact_produccion_mes_ecp`=314952, `fact_produccion_dia_ecp`=8628,
  `fact_comentarios_produccion`=35. `uv run pytest -q` verde (6 passed / 1 skipped).
- **X8 — visor:** `GET /tablas/datos?...&hoja=BDP_Programa&tabla_idx=1` → `len(filas)`=**100** (cap CAP_FILAS)
  y `total_filas`=**9130** (combos de dims). Carga rápida (13.822 < FETCH_MAX=50.000 → sin truncar).

```sql
-- X2/X3
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_Programa';        -- 13822
SELECT count(*) FROM (SELECT 1 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_Programa'
  GROUP BY tabla_idx,dims,fecha HAVING count(*)>1) x;                                            -- 0
-- X4
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL),
       count(DISTINCT dims->>'producto'), count(DISTINCT dims->>'vice')
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_Programa';                       -- 61, 0, 3, 6
-- X5
SELECT valor, dims->>'produccion_total', dims->>'part_ecp', dims->>'area', dims->>'fecha_version'
  FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='BDP_Programa'
   AND fecha='2024-10-02' AND dims->>'idbdp'='47023' AND dims->>'producto'='CRUDO';              -- 119.5402, 225.5475, 53, SURORIENTE, 20240927
-- X7 (la hoja de pivots PROGRAMA no debe cambiar)
SELECT count(*) FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='PROGRAMA';             -- 39431
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. **1 fila por registro** (NO unpivot de las 3 medidas). `valor=Volumen`;
  `Produccion_total` y `Part_ECP` como **dims** (no descartar: son 2 de las 14 columnas).
- **4.2** Cabecera por NOMBRE (fila 1), no por índice fijo. `fecha` real (nunca NULL; filas sin fecha se omiten).
- **4.3** `rl()` en las dims (fecha→ISO; descarta ruido/`"(en blanco)"`). Clave de dim = `header.lower()` con
  espacios→`_`. Excluir solo `FECHA` (→fecha) y `VOLUMEN` (→valor); TODO lo demás va a dims.
- **4.4** No commit/push salvo que se pida. No tocar prod 139. No modificar `load_tablas_hoja` (ya trocea).
- **4.5** Si una validación falla, **DETENERSE y reportar el delta**. En especial: X2 debe dar 13822; si
  `PROGRAMA` (X7) cambia de 39431, hay cross-match de regex → reportar sin "arreglar".

---

## 5. Fuera de alcance
- El unpivot de las 3 medidas (daría 41.466 filas): descartado por decisión del usuario (1 fila por registro).
- Modelar `Volumen`/`Produccion_total`/`Part_ECP` como 3 filas con dim `medida`: descartado (14 columnas, 1 fila).
- `FECHA` como dim (se extrae a `fecha`). `Estado`/`Contrato` no se listan como dims obligatorias (vacías aquí;
  el extractor las incluye automáticamente si un archivo futuro las puebla).
- Cambios en el visor / paginación real: el cap de 100 (CAP_FILAS) y el `FETCH_MAX=50.000` ya cubren la
  presentación (mejora futura fuera de este plan).
```
