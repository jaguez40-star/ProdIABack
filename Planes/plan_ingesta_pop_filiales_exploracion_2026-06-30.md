# Plan ejecutable (v2) — Modelado de la hoja "POP Filiales y Exploración" → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 2 → salida 2** (ninguna tabla con datos omitida; ver §0.b/§0.g.5).
> **Decisión escalada (§0.h):** se INCLUYEN las filas de subtotal/total (criterio D3 "preservar todo").
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `POP Filiales y Exploración`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA (usa `core.fact_tabla_hoja`, ya existente).
> **Frontend / api.py:** SIN cambios (tabla temporal → modo "fechas" del visor, ya probado).

---

## 0. Flujo profesional — auditoría hecha (datos reales, 3 archivos)

### 0.a — Naturaleza
**2 tablas TEMPORALES** (serie mensual). A diferencia de DPP/Whatsapp, las **fechas son explícitas y
año-correctas** en la fila-cabecera → `fecha = mes` (NO NULL). Patrón idéntico a `_p50_acum`/tabla
'filiales' de `_p50_extract`. Valores cacheados, **no se recalculan**.

### 0.b — 2 tablas (layout idéntico en los 3 archivos)
| Tabla | Filas datos | Cabecera (fechas D–O) | Dimensiones | Meses |
|------:|-------------|-----------------------|-------------|-------|
| T1 **POP Filiales**     | 3–19  | fila 2  (`Producto`,`Empresa`) | `producto` × `empresa` | 12 |
| T2 **POP Exploración**  | 23–26 | fila 22 (`VR`,`GER`)           | `vr` × `ger`           | 12 |

- T1 filas: Crudo/Gas/Blancos × {Hocol, EAI, Permian} + subtotales (Total Crudo/Gas/Blancos),
  `Total general`, y totales por empresa (TOTAL HOCOL/EA/PERMIAN).
- T2 filas: VEX × {GOF, GON, GOO} + `Total VEX`.
- **Excluye:** columna **P "Promedio Año"** (derivada), fila 1 (días/mes) y columna A (índice) = metadata.

### 0.c — Constraints reales de la BD (verificados)
- `core.fact_tabla_hoja.fecha` → `DATE` (acepta fecha temporal). `valor` → `NUMERIC` nullable.
- No se inserta `fecha=NULL` (todas las celdas emitidas llevan su fecha de mes).

### 0.d — No-breakage del visor (sin cambios de front/api)
- El emit en `ingerir_archivo` (services.py ~1160) ya envía `"tablas"` → 2 ítems clicables.
- `GET /tablas/datos` modo **"fechas"** (api.py ~78): `meses = sorted({fecha.isoformat()})`; pivota
  `dims × fecha`. Todas las filas llevan fecha real → **no hay `None.isoformat()`, no revienta.**
- Las claves de dimensión mixtas (`{producto,empresa}` en hojas, `{producto}` en subtotales) las une
  `dim_keys` (api.py); las celdas faltantes se renderizan en blanco. Sin problema.
- 9ª hoja con el MISMO pipeline ⇒ **0 riesgo de regresión** en las 8 hojas modeladas previas.

### 0.e — Decisiones de fidelidad
1. **`fecha = mes`** leída de la cabecera con `_p50_contig_months` (corta en la 1ª no-fecha →
   **excluye "Promedio Año"** sin hardcodear). Year-correct (2023→2023, 2024→2024).
2. **Incluir subtotales/totales** (Total Crudo, Total general, TOTAL HOCOL…) → fiel a la fuente.
   Cada `(producto,empresa)` / `(vr,ger)` es único → **0 colisiones** (no se necesita prefijo de grupo).
3. **`empresa`/`ger` se omite** en filas de subtotal (col C vacía) → `dims = {producto}` / `{vr}`.
4. **Sin ruido `#REF!`** en esta hoja (solo números/0/vacío). `num()` anula vacíos → se saltan.

### 0.f — Conteos esperados (prototipo, 3 archivos — IDÉNTICOS)
| Archivo | T1 | T2 | TOTAL | Meses |
|---------|---:|---:|------:|-------|
| 2023-12-31 | 191 | 47 | **238** | 12 (2023-01-31…12-31) |
| 2024-02-11 | 191 | 47 | **238** | 12 (2024-01-31…12-31) |
| 2024-10-04 | 191 | 47 | **238** | 12 (2024-01-31…12-31) |

0 colisiones en los 3. Tabla excepcionalmente estable (mismos conteos siempre).

### 0.g — Flujo profesional: verificación de no-breakage
1. **Modo fechas ya probado** en otras hojas (P50 Acumulado, bloques de NEW MES-AÑO) → sin riesgo nuevo.
2. **pytest no se rompe**: los tests no asertan el nº de hojas modeladas.
3. **Sin disparadores de riesgo §0.2**: no toca DDL, ni clave natural (fact sin UNIQUE; dedup en código),
   ni `ON CONFLICT`, ni detección raw/STD. Solo extractor + 1 línea (patrón usado 8 veces).
4. **Reúso de helpers** `_p50_grid` y `_p50_contig_months` (ya existentes) → menos código nuevo, mismo
   comportamiento de corte de meses que el resto de extractores temporales.
5. **Cobertura exhaustiva (§0.2)**: (a) encajan → T1, T2 (MODELADAS). (c) no-tablas → col "Promedio Año"
   (derivada), fila de días/mes y columna índice (metadata). → **`Tablas: entrada 2 → salida 2`**.
6. **`auditoria:` (paridad numérica)**: hoja derivada que se ingiere TAL CUAL; paridad 1:1 por
   construcción (el fact reproduce el valor cacheado de cada celda mensual).
7. **Visor resalta totales (verificado)**: en modo "fechas" `rowLbl` une dims con " · " filtrando
   nulls e `isTotal` matchea `/^total/i` (chat.js:488-489) → `Total Crudo`, `Total general`,
   `TOTAL HOCOL`, `Total VEX` salen con ícono Σ automáticamente (igual que DPP).

### 0.h — Decisión ESCALADA: subtotales/totales (incoherencia detectada en la re-verificación)
🔴 **Hallazgo**: el extractor análogo `_p50_extract` (hoja 'filiales', misma forma `producto×empresa`)
**DESCARTA** las filas total (`if str(producto).lower().startswith("total"): continue`, services.py
~464). Mi plan las **INCLUYE**. Criterios opuestos para la misma forma de tabla.

**Resolución — INCLUIR (sin reducir alcance), por estos motivos:**
- **D3 (§6 CLAUDE.md) = "degradación elegante: se ingiere todo y nada se pierde"**. El default es
  preservar; **excluir filas sería una reducción de alcance que requiere visto bueno explícito**.
- **POP es un reporte de presentación** (como DPP, donde el usuario pidió incluir y resaltar los
  totales), no un cubo re-agregable aguas abajo. La divergencia con `_p50_extract` se justifica por el
  propósito de la hoja: P50 es cubo (sus subtotales se recalculan), POP es hoja-hoja de despliegue.
- **El visor las resalta** (§0.g.7) → valor de UX, no ruido.
- **Sin riesgo de doble-conteo silencioso**: los totales son **identificables por etiqueta**
  (`producto`/`vr` empieza por `Total`/`TOTAL`); un consumidor analítico puede excluirlos con
  `WHERE dims->>'producto' NOT ILIKE 'total%'`. Se documenta para evitar `SUM(valor)` ingenuo.

⚠️ **Si el usuario prefiere el criterio de cubo** (excluir totales, como `_p50_extract`), es un cambio
de 1 línea: añadir `if a.lower().startswith("total"): continue` tras leer `a`. Conteos pasarían de
**191/47 (TOTAL 238)** a **107/35 (TOTAL 142)** (solo filas de detalle). **Decisión del usuario** antes
de ejecutar. El plan, tal como está, asume **INCLUIR** (X2 = 191/47/238).

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_pop_filiales_extract` (insertar después de `_dpp_extract`, antes del bloque
`# === Registro de hojas modeladas: ...`)

```python
def _pop_filiales_extract(ws):
    """Extractor de 'POP Filiales y Exploración' → 2 tablas TEMPORALES mensuales (fecha=mes).
    Reporte derivado; NO recalcula (valores cacheados TAL CUAL). Contrato extendido:
    {"rows":[{tabla_idx,tabla_label,dims,fecha,valor}], "tablas":DECLARED}.

    T1 'POP Filiales'    (filas 3-19,  cabecera fila 2):  dims = producto(B) × empresa(C).
    T2 'POP Exploración' (filas 23-26, cabecera fila 22): dims = vr(B) × ger(C).
    Meses contiguos desde col D (4) por la fila-cabecera; _p50_contig_months corta en la 1ª no-fecha
    => EXCLUYE 'Promedio Año' (col P). Incluye subtotales/totales (col C vacía => dims sin 2ª clave;
    cada (producto,empresa)/(vr,ger) es único, 0 colisiones). Fila 1 (días/mes) y col A (índice): metadata."""
    grid, _maxr = _p50_grid(ws)
    DECLARED = [(1, "POP Filiales"), (2, "POP Exploración")]
    LBL = {i: l for i, l in DECLARED}
    # (tabla_idx, hdr_row, fila_ini, fila_fin, nombre_dim1(B), nombre_dim2(C))
    SPECS = [
        (1, 2, 3, 19, "producto", "empresa"),
        (2, 22, 23, 26, "vr", "ger"),
    ]
    rows = []
    for idx, hdr, r0, r1, name1, name2 in SPECS:
        months = _p50_contig_months(grid, hdr, 4)      # D..O ; corta antes de 'Promedio Año'
        if not months:
            continue
        for r in range(r0, r1 + 1):
            a = s(grid.get((r, 2)))                     # B = etiqueta principal
            if a is None:
                continue
            dims = {name1: a}
            b = s(grid.get((r, 3)))                     # C = empresa/ger (ausente en subtotales)
            if b is not None:
                dims[name2] = b
            for c, d in months:
                v = num(grid.get((r, c)))
                if v is None:
                    continue
                rows.append({"tabla_idx": idx, "tabla_label": LBL[idx],
                             "dims": dims, "fecha": d, "valor": v})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de Reporte DPP)

```python
    # POP Filiales y Exploración: 2 tablas temporales mensuales (T1 Producto×Empresa, T2 VR×GER).
    # Meses por cabecera (corta en 'Promedio Año'). Valores ya calculados, se ingieren tal cual.
    (re.compile(r"(?i)^POP Filiales y Explora"), _pop_filiales_extract),
```

**NO** agregar imports (`s`, `num`, `to_date`, `_p50_grid`, `_p50_contig_months` ya existen en el módulo).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. Confirmar que `_dpp_extract` existe y que `HOJAS_MODELADAS` está justo después.
2. Confirmar que `s`, `num`, `_p50_grid`, `_p50_contig_months` existen en services.py.
3. Confirmar el nombre exacto de la hoja: `POP Filiales y Exploración` (regex `^POP Filiales y Explora`).
Si algo difiere, **DETENERSE y reportar** (no inventar).

---

## 3. Validaciones (correr tras aplicar y re-ingerir)

> **Archivo canónico: `2024-10-04` (NEW).** Tomar `<rid>` del `reporte_id` que devuelve la ingesta.
> (Cualquiera de los 3 archivos da los mismos conteos 191/47/238.)

- **X1 — 2 tablas:** `GET /tablas?reporte_id=<rid>&hoja=POP Filiales y Exploración` → 2 ítems (idx 1,2).
- **X2 — conteos:** tabla_idx 1 → **191**, tabla_idx 2 → **47** ; **TOTAL = 238**.
- **X3 — meses:** 12 fechas distintas, `2024-01-31 … 2024-12-31`.
- **X4 — sin colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X5 — spot-check:**
  - T1: tabla_idx=1, `dims->>'producto'='Crudo'`, `dims->>'empresa'='Hocol'`, fecha `2024-01-31` → `22155`.
  - T2: tabla_idx=2, `dims->>'vr'='VEX'`, `dims->>'ger'='GON'`, fecha `2024-01-31` → `139.7`.
- **X6 — idempotencia:** re-ingerir → mismos conteos, sin duplicar.
- **X7 — no-breakage:** las 8 hojas modeladas previas y COMENTARIOS intactas; `uv run pytest -q` verde.

### SQL de verificación (psql, credencial vía `$env:PGPASSWORD` del `.env`, nunca inline)
```sql
-- X2 conteos  (esperado: 191, 47)
SELECT tabla_idx, count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='POP Filiales y Exploración' GROUP BY tabla_idx ORDER BY tabla_idx;
-- X3 meses  (esperado: 12 filas, 2024-01-31..2024-12-31)
SELECT DISTINCT fecha FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='POP Filiales y Exploración' ORDER BY fecha;
-- X4 colisiones  (debe dar 0 filas)
SELECT tabla_idx, dims, fecha, count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='POP Filiales y Exploración'
 GROUP BY tabla_idx, dims, fecha HAVING count(*)>1;
-- X5 spot-checks
SELECT valor FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='POP Filiales y Exploración' AND tabla_idx=1
   AND dims->>'producto'='Crudo' AND dims->>'empresa'='Hocol' AND fecha='2024-01-31';   -- 22155
SELECT valor FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='POP Filiales y Exploración' AND tabla_idx=2
   AND dims->>'vr'='VEX' AND dims->>'ger'='GON' AND fecha='2024-01-31';                  -- 139.7
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. No reordenar columnas ni cambiar etiquetas de dimensión.
- **4.2** Filas fijas (3–19, 23–26) y cabeceras (2, 22): patrón establecido. Si un archivo futuro
  desplaza filas, **re-auditar** (no adivinar).
- **4.3** Meses SIEMPRE por `_p50_contig_months` (excluye 'Promedio Año'). No hardcodear meses ni
  incluir la columna P.
- **4.4** `fecha` = mes real (date). No emitir `fecha=NULL` en esta hoja.
- **4.5** No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta** (no maquillar).

---

## 5. Fuera de alcance
- Columna "Promedio Año" (derivada), fila de días/mes (fila 1) y columna índice (A): metadata, no se ingieren.
- Recalcular o validar la aritmética de subtotales: se ingieren los valores cacheados tal cual.
