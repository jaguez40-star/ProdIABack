# Plan ejecutable (v2) — Modelado de la hoja "Reporte DPP" → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 5 → salida 5** (ninguna tabla útil omitida; ver §0.b/§0.g.5).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `Reporte DPP`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA (`valor` y `fecha` ya son nullable; ver §0.c).
> **Frontend / api.py:** SIN cambios (verificado: el emit propaga `tablas` y el visor ya pinta
> celdas `null` como "sin dato"; ver §0.d y §0.g).

---

## 0. Flujo profesional — verificación previa (auditoría hecha)

### 0.a — Naturaleza de la hoja
`Reporte DPP` es un **reporte comparativo derivado** (snapshot de KPIs), **no un cubo ni serie temporal**.
Es una **matriz SEGMENTO × métrica** para la fecha del reporte. Valores cacheados, **no se recalculan**.

### 0.b — 5 tablas (definidas por el usuario, verificadas a nivel celda en 3 archivos)
Filas Excel **9–12** = cabeceras (etiquetas/fechas); **13–22** = 10 filas de datos (segmentos con jerarquía).
Columna **B (SEGMENTO)** = dimensión-fila compartida. Cada tabla = sus columnas-métrica.

| Tabla | Cols Excel | Métricas (fila 10) |
|------:|-----------|--------------------|
| T1 COMPARATIVO DÍA   | C,D,E,F | PRODUCCIÓN REAL / PROGRAMA (día anterior y día actual) |
| T2 PROYECCIÓN MES    | H,I     | REAL mes / PROYECCIÓN MES |
| T3 CUMPLIMIENTO MES  | K,L,M   | P50(META) / DIFERENCIA / PRODUCCIÓN NECESARIA |
| T4 PROYECCIÓN AÑO    | O,P     | REAL año (YTD) / PROYECCIÓN AÑO |
| T5 CUMPLIMIENTO AÑO  | R,S,T   | P50(META) / DIFERENCIA / PRODUCCIÓN NECESARIA |

Excluye: columnas espaciadoras (G,J,N,Q,U,V,W,X,AB), bloque POP 727/725 (Y–AE) y filas 74–87
(**`#REF!` total** en los 3 archivos). **Cobertura: entrada 5 → salida 5.**

### 0.c — Constraints reales de la BD (verificados)
- `core.fact_tabla_hoja.valor` → `NUMERIC` **nullable** (DDL línea 645).
- `core.fact_tabla_hoja.fecha` → **nullable** desde `migrations/004_fact_tabla_hoja_matriz.sql`
  (`ALTER ... fecha DROP NOT NULL`). El `ddl_v2_postgres.sql` línea 644 muestra `NOT NULL` pero está
  **desactualizado**; la migración 004 es la autoritativa y ya está aplicada en dev y prod.
→ **`valor = NULL` y `fecha = NULL` no requieren migración nueva.**

### 0.d — No-breakage del visor (sin cambios de front/api) — VERIFICADO en código
- El emit en `ingerir_archivo` (services.py ~1160) ya envía `"tablas": _res["tablas"]` → las 5 tablas
  declaradas se vuelven ítems clicables "Para análisis" automáticamente.
- `GET /tablas/datos` modo **matriz** (api.py ~58) se activa cuando `all(fecha is None)`; pivota
  `dims.fila × dims.columna` y renderiza `valor` con `float(...) if valor is not None else None`.
- **Frontend** `renderTablaAncha` (static/js/chat.js ~503): `else if (v == null) → <td class="empty">·</td>`
  ("sin dato"). ⇒ **`valor=NULL` se pinta como celda en blanco, NO revienta.** (Verificado en el código,
  no de memoria.) Además `v === 0 → "—"` (cero) y número → formateado.
- 8ª hoja usando el MISMO pipeline (extractor → contrato extendido → `load_tablas_hoja` → emit) ⇒
  **0 riesgo de regresión** en las otras 7 hojas modeladas ni en COMENTARIOS.

### 0.e — Decisiones de fidelidad (acordadas con el usuario 2026-06-30)
1. **Errores Excel → `valor = NULL` (celda emitida).** Toda celda con valor de error
   (`#¡REF!`, `#N/A`, `#DIV/0!`, `#VALUE!`, `#NAME?`, …) se **inserta como fila con `valor = NULL`**
   (celda en blanco) — **NO se descarta**. Solo se **salta** la celda **vacía de verdad** (sin contenido).
   → Preserva la forma de la tabla: los 10 segmentos aparecen aunque sus valores estén rotos.
   (Difiere de Whatsapp/NEW, que saltaban las celdas de error.)
2. **`fecha = NULL`** (modo matriz; linaje por `reporte_id`). Las fechas embebidas no son fiables:
   el archivo `20231231` trae r11/r12 con fechas 2026-06 (valores recalculados a posteriori).
3. **`grupo` embebido en `dims.fila`** para evitar colisión de segmentos repetidos
   (CRUDO/GAS/BLANCOS existen bajo ECOPETROL **y** bajo FILIALES). Verificado: **0 colisiones**.
4. **Etiquetas de columna POSICIONALES estables** (no dependen del mes). Los textos de la hoja
   (`PROYECCIÓN MES Octubre`, `DEL 1 AL 3 Oct`, `DE ENE A Oct`) cambian entre archivos → se ignoran.

### 0.f — Conteos esperados (prototipo sobre 3 archivos, regla §0.e)
| Tabla | 2023-12-31 | 2024-02-11 | 2024-10-04 |
|------:|-----------:|-----------:|-----------:|
| T1 | 40 (40 NULL) | 40 (12 NULL) | 40 |
| T2 | 20 | 20 | 20 |
| T3 | 30 | 30 | 30 |
| T4 | 15 (6 NULL) | 15 (6 NULL) | 15 |
| T5 | 15 | 15 | 21 |
| **TOTAL** | **120** | **120** | **126** |

T1/T2/T3/T4 estables; **T5 varía legítimamente** (más celdas vacías reales en subtotales de archivos
viejos). NULL totales: 46 (2023), **18 (2024-02)**, 0 (2024-10). 0 colisiones en los 3.

### 0.g — Flujo profesional v2: verificación de incoherencias / no-breakage (con datos y código reales)
1. **Frontend `null`-safe — VERIFICADO** (chat.js:503): celda matriz `null` → "· sin dato". No crash.
2. **pytest no se rompe — VERIFICADO**: los tests (`test_transforms`, `test_health`, `test_ingesta_api`)
   NO asertan el nº de hojas modeladas ni iteran `HOJAS_MODELADAS`. Añadir DPP (8ª hoja) es inerte.
3. **Sin disparadores de riesgo del §0.2 (CLAUDE.md)**: NO toca DDL, NO cambia clave natural de ningún
   fact (`fact_tabla_hoja` no tiene UNIQUE; dedup en código), NO altera detección raw/STD, NO toca
   `ON CONFLICT`. Solo añade un extractor + 1 línea de registro (patrón ya usado 7 veces).
4. **MEJORA aplicada — filas total resaltadas**: el visor marca como total las filas cuya etiqueta
   empieza por `total` (chat.js:489, `isTotal`). Por eso los subtotales/total se nombran
   **`TOTAL ECOPETROL` / `TOTAL FILIALES` / `TOTAL UPSTREAM`** → el visor les pone ícono Σ y estilo de
   fila-total. Las filas hijas mantienen `<GRUPO> · <SEGMENTO>`. Sigue habiendo 0 colisiones.
5. **Cobertura exhaustiva (§0.2 — prohibido reducir alcance en silencio)**. Estructuras presentes en
   la hoja y su clasificación:
   - (a) **Encajan en el contrato** → T1..T5 (matriz segmento×métrica). **MODELADAS.**
   - (c) **Genuinamente irrelevante, con justificación** → bloque **POP 727/725** (cols Y–AE, filas
     13–22 y 74–87): **100% `#REF!` en los 3 archivos** (referencias rotas, no recuperables). Se omite.
   - Filas 1–7 (títulos/metadata) y columnas espaciadoras (G,J,N,Q,U,V,W,X,AB): no son datos.
   → **`Tablas: entrada 5 → salida 5`** (M = N; no se omite ninguna tabla con datos válidos).
6. **Nota sobre `auditoria:` (CLAUDE.md §0.1)**: la Suite de Paridad Numérica recalcula KPIs desde la BD
   y compara contra Excel. DPP es un **reporte derivado que se ingiere TAL CUAL** (no se recalcula), así
   que la paridad es 1:1 por construcción: el fact reproduce el valor cacheado de la celda. Los `#REF!`
   se ignoran (→ NULL), coherente con la regla "ignora celdas `#REF!`" de esa suite.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_dpp_extract` (insertar después de `_mesano_extract`, antes del bloque
`# === Registro de hojas modeladas: ...`)

```python
def _dpp_extract(ws):
    """Extractor de 'Reporte DPP' → 5 tablas MATRICIALES (segmento × métrica), fecha=NULL.
    Reporte comparativo derivado (snapshot de KPIs); NO recalcula (decisión usuario 2026-06-30).
    Contrato extendido: {"rows":[{tabla_idx,tabla_label,dims,fecha,valor}], "tablas":DECLARED}.

    Filas Excel 13-22 = 10 segmentos con jerarquía (ECOPETROL/FILIALES/UPSTREAM). El grupo se
    embebe en dims.fila para evitar colisiones de segmentos repetidos (CRUDO/GAS/BLANCOS x2).
    Columna B = segmento; cabeceras en filas 9-12 (no se emiten).

    REGLA DPP de celdas (acordada 2026-06-30): una celda con valor de error de Excel
    (#¡REF!/#N/A/#DIV0/#VALUE!/#NAME?...) se INSERTA como valor=NULL (celda en blanco, preserva la
    forma de la tabla); una celda VACÍA de verdad se salta. Etiquetas de columna POSICIONALES
    estables (no dependen del mes). Excluye POP 727/725 (cols Y-AE) y filas 74-87 (#REF! total)."""
    DECLARED = [
        (1, "COMPARATIVO DÍA"), (2, "PROYECCIÓN MES"), (3, "CUMPLIMIENTO MES"),
        (4, "PROYECCIÓN AÑO"), (5, "CUMPLIMIENTO AÑO"),
    ]
    # (fila_excel, etiqueta de fila con grupo embebido). Filas fijas verificadas estables en 3 archivos.
    # Las filas total se nombran "TOTAL ..." para que el visor las resalte (chat.js isTotal /^total/i).
    ROWS = [
        (13, "ECOPETROL · CRUDO"), (14, "ECOPETROL · GAS"), (15, "ECOPETROL · BLANCOS"),
        (16, "ECOPETROL · ECP EXPLORACIÓN"), (17, "TOTAL ECOPETROL"),
        (18, "FILIALES · CRUDO"), (19, "FILIALES · GAS"), (20, "FILIALES · BLANCOS"),
        (21, "TOTAL FILIALES"), (22, "TOTAL UPSTREAM"),
    ]
    # (tabla_idx, [(col_index_1based, etiqueta_columna_estable), ...]). Índices: C=3 D=4 E=5 F=6
    # H=8 I=9 K=11 L=12 M=13 O=15 P=16 R=18 S=19 T=20.
    TABLES = [
        (1, [(3, "REAL día anterior"), (4, "PROGRAMA día anterior"),
             (5, "REAL día actual"), (6, "PROGRAMA día actual")]),
        (2, [(8, "REAL mes"), (9, "PROYECCIÓN MES")]),
        (3, [(11, "P50 (META) mes"), (12, "DIFERENCIA mes"), (13, "PRODUCCIÓN NECESARIA mes")]),
        (4, [(15, "REAL año (YTD)"), (16, "PROYECCIÓN AÑO")]),
        (5, [(18, "P50 (META) año"), (19, "DIFERENCIA año"), (20, "PRODUCCIÓN NECESARIA año")]),
    ]
    LBL = {i: l for i, l in DECLARED}
    grid = {}
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if r > 22:
            break
        for c, v in enumerate(row, start=1):
            grid[(r, c)] = v
    rows = []
    for idx, cols in TABLES:
        for rexcel, fila in ROWS:
            for cidx, clabel in cols:
                raw = grid.get((rexcel, cidx))
                if raw is None:
                    continue
                if str(raw).strip() == "":
                    continue
                # número -> valor; error de Excel (no numérico, no vacío) -> NULL (celda en blanco)
                rows.append({"tabla_idx": idx, "tabla_label": LBL[idx],
                             "dims": {"fila": fila, "columna": clabel},
                             "fecha": None, "valor": num(raw)})
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de NEW MES-AÑO)

```python
    # Reporte DPP: 5 tablas matriciales (segmento × métrica), comparativo derivado. fecha=NULL.
    # Errores de Excel se ingieren como valor=NULL (celda en blanco, no se descarta). Nombre 11 chars.
    (re.compile(r"(?i)^Reporte\s+DPP"), _dpp_extract),
```

**NO** agregar imports (`num` ya está importado y usado por otros extractores).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. Confirmar que `_mesano_extract` existe y que `HOJAS_MODELADAS` está justo después (services.py).
2. Confirmar que `num` está importado en services.py (lo usan los otros extractores).
3. Confirmar el nombre exacto de la hoja: `Reporte DPP` (regex `^Reporte\s+DPP` la matchea).
Si algo difiere, **DETENERSE y reportar** (no inventar).

---

## 3. Validaciones (correr tras aplicar y re-ingerir)

> **Archivo canónico único: `2024-02-11` (STD)** — ejercita AMBOS caminos (números **y** NULL) en una
> sola ingesta. (Opcional secundario 2024-10-04 = todo numérico → T5=21, TOTAL=126.)
> Tomar `<rid>` del `reporte_id` que devuelve la ingesta de ese archivo.

- **X1 — 5 tablas:** `GET /tablas?reporte_id=<rid>&hoja=Reporte DPP` devuelve 5 ítems
  (tabla_idx 1..5) con sus labels. (Listadas aunque alguna tenga 0 filas.)
- **X2 — conteos (2024-02-11):** por tabla_idx → **40, 20, 30, 15, 15** ; **TOTAL = 120**.
- **X3 — errores → NULL (2024-02-11):** `COUNT(*) WHERE valor IS NULL` = **18** (T1:12 + T4:6).
  Ninguna fila se pierde **por error** (`#¡REF!`/`#N/A` → NULL conservan la fila).
- **X3b — filas distintas por tabla (2024-02-11):** `count(DISTINCT dims->>'fila')` = **10, 10, 10, 8, 7**
  (T1..T5). Que T4=8 y T5=7 es CORRECTO: en FILIALES las columnas AÑO (proyección/cumplimiento) están
  **vacías de verdad** (sin fórmula, NO error) → esas filas no aplican y no se emiten. No es pérdida.
- **X4 — matriz:** `0` filas de la hoja con `fecha IS NOT NULL`.
- **X5 — spot-check (2024-02-11):** tabla_idx=2, `dims->>'fila'='TOTAL UPSTREAM'`,
  `dims->>'columna'='REAL mes'` → `valor ≈ 706.3408`.
- **X6 — idempotencia:** re-ingerir el mismo archivo → mismos conteos, sin duplicar.
- **X7 — no-breakage:** `0` colisiones `(tabla_idx,dims,fecha)`; las otras 7 hojas modeladas y
  COMENTARIOS intactas; `uv run pytest -q` sigue verde.

### SQL de verificación (psql, credencial vía `$env:PGPASSWORD` del `.env`, nunca inline)
```sql
-- X2 conteos  (esperado: 40,20,30,15,15)
SELECT tabla_idx, count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='Reporte DPP' GROUP BY tabla_idx ORDER BY tabla_idx;
-- X3 NULL emitidos  (esperado: 18)
SELECT count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='Reporte DPP' AND valor IS NULL;
-- X3b filas distintas por tabla  (esperado: 10,10,10,8,7 — T4/T5 menos por columnas AÑO vacías en FILIALES)
SELECT tabla_idx, count(DISTINCT dims->>'fila') FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='Reporte DPP' GROUP BY tabla_idx ORDER BY tabla_idx;
-- X4 matriz  (debe dar 0)
SELECT count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='Reporte DPP' AND fecha IS NOT NULL;
-- X5 spot-check  (esperado ≈ 706.3408)
SELECT valor FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='Reporte DPP' AND tabla_idx=2
   AND dims->>'fila'='TOTAL UPSTREAM' AND dims->>'columna'='REAL mes';
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. No reordenar columnas ni cambiar etiquetas.
- **4.2** Filas fijas (13–22) y columnas fijas: patrón establecido (igual que `_programa_extract` /
  `_mesano_extract`). Si un archivo futuro desplaza filas, **re-auditar** (no adivinar).
- **4.3** Error de Excel ⇒ `valor=NULL` (fila emitida). Vacío real ⇒ saltar. No convertir a 0.
- **4.4** `fecha=NULL` siempre (no mezclar con fechas). No confiar en las fechas embebidas de la hoja.
- **4.5** No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta** (no maquillar).
