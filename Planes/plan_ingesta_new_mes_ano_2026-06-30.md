# Plan ejecutable v2 — Ingesta de la hoja "NEW MES-AÑO" (13 tablas) → `core.fact_tabla_hoja`

> **Cobertura: `Tablas: entrada 13 → salida 13`** (las confirmadas por el dueño: A–O = 7, S–AH = 6).
> Bloques de columnas **excluidos por decisión** (no son las 13): GRÁFICAS (AL–AX), META AÑO (AZ), serie
> diaria Grupo Empresarial (BC–CM) y columnas helper (P, AI/AJ) — §0.e.
>
> Modo: **plan:** (executor sin contexto del repo). **Auditado v2** contra el CÓDIGO real, el pipeline del
> visor y **prototipo corrido en 3 archivos** (STD-2023, STD-2024, NEW-2024): 13 tablas, **0 colisiones de
> dedup**, meses año-correctos, **render del visor verificado por simulación** (§0.i).

---

## 0. Hallazgos de auditoría (verificados contra CÓDIGO y DATOS reales)

### 0.a Estructura (estable en 3 archivos; anclas idénticas)
Hoja **densa**, ~116 filas × ~91 columnas, **sin PivotTables/ListObjects**, valores en su mayoría
**fórmulas** (296 vs 16 literal en muestreo) → se ingieren **valores cacheados** (`data_only=True`).
`#¡REF!`/`#N/A`/`(en blanco)` → `s()`/`num()`=None → en blanco. **13 tablas en 2 bloques de columnas:**

- **Bloque A–O (REAL + PROYECCIÓN), 7 tablas.** Etiquetas: `A`=producto/concepto, `B`=vice/empresa.
  Meses = encabezado de fechas en cols **C–N** (12). `O`=Promedio Año.
- **Bloque S–AH (P50 + POP), 6 tablas.** Etiquetas: `S`=índice (se ignora), `T`=producto, `U`=vice/empresa.
  Meses = encabezado de fechas en cols **V–AG** (12). `AH`=Promedio Año.

Anclas (fila del título/encabezado) **idénticas en los 3 archivos**: `REAL PROMEDIO MES`=A12, `P50 ECP`=T7,
`P50 Filiales`=T29, `POP ECP`=T58, `POP Filiales`=T83, etc.

### 0.b Las 13 tablas (idx, rango de filas, encabezado, dims) — verificadas
| idx | tabla (rango filas) | hdr (fechas) | datos | dims |
|---|---|---|---|---|
| 1 | Parámetros calendario (A–O 6–10) | f7 | 6,8,9,10 | `{concepto}` |
| 2 | REAL PROMEDIO MES ECP (A–O 12–35) | f13 | 14–35 | `{producto, vice}` |
| 3 | REAL PROMEDIO MES Filiales (A–O 38–47) | f39 | 40–47 | `{producto, empresa}` |
| 4 | PROYECCIÓN AÑO ECP (A–O 58–81) | f59 | 60–81 | `{producto, vice}` |
| 5 | PROYECCIÓN AÑO Filiales (A–O 83–97) | f84 | 85–97 | `{producto, empresa}` |
| 6 | POP/PROY EXPLORACIÓN+G.E. (A–O 99–105) | f99 | 99–105 | `{entidad}` |
| 7 | POP Filiales (A–O 109–116) | f112 | 113–116 | `{empresa}` |
| 8 | P50 ECP (S–AH 7–27) | f8 | 9–27 | `{producto, vice}` |
| 9 | P50 Filiales (S–AH 29–43) | f30 | 31–43 | `{producto, empresa}` |
| 10 | P50 EXPLORACIÓN+G.E. (S–AH 46–52) | f46 | 46–52 | `{entidad}` |
| 11 | POP ECP (S–AH 58–81) | f59 | 60–81 | `{producto, vice}` |
| 12 | POP Filiales (S–AH 83–97) | f84 | 85–97 | `{producto, empresa}` |
| 13 | POP EXPLORACIÓN+G.E. (S–AH 99–105) | f99 | 99–105 | `{entidad}` |

- **Incluyen filas de total/subtotal** (Total CRUDO, Total general, etc.; `B`/`U` vacío → dims solo con
  `producto`/`concepto`). Tal como aparecen (decisión del dueño).
- **Tablas de entidad (6, 10, 13):** entidad ∈ {`GON`,`GOO`,`VEX`} (en `B`/`U`) o `GRUPO EMPRESARIAL`
  (etiqueta contiene "GRUPO EMP"). El resto de filas del rango (títulos/sub-headers) se ignoran.

### 0.c 🔴 Decisión D-mesano-1 — excluir la columna "Promedio Año" (O / AH)
Es un **promedio anual derivado** (recomputable de los 12 meses) y **no es una fecha**. Incluirla obligaría a
mezclar `fecha=date` con `fecha=NULL` en la MISMA tabla, lo que **rompe el visor** (`/tablas/datos` hace
`r["fecha"].isoformat()` en modo fechas → `None` lo tumba). **Se excluye** (solo los 12 meses). *(Si el dueño
la quisiera, sería otra iteración con modelado distinto.)*

### 0.d Meses por fecha de encabezado — FIABLES (año-correctos)
Los meses se leen del encabezado (`YYYYMMDD`): archivo 2023 → 2023-01-31..2023-12-31; 2024 → 2024-…
Verificado en los 3 archivos. `fecha` = la fecha real del mes (a diferencia del as-of no fiable de Whatsapp).
**Variación legítima:** `REAL PROMEDIO MES` (T1/T2/T3) **acumula** meses según avanza el año (STD-feb ≈ 2
meses, NEW-oct ≈ 10, STD-dic = 12) → menos filas en archivos tempranos. **NO es error**; T4–T13
(PROYECCIÓN/P50/POP) cubren los 12 meses siempre.

### 0.e Cobertura: qué se excluye (regla anti-reducción §0.2)
La hoja tiene 5 bloques de columnas; el dueño scopeó 2 (A–O, S–AH = 13 tablas). **Excluidos por decisión:**
`***GRAFICAS***` (AL–AX, matriz mensual de gráficas), `META AÑO` (AZ), **serie diaria** Grupo Empresarial
(BC–CM, 01–31 del mes + P50/POP/PROYECCION resumen) y columnas helper (P, AI/AJ minúsculas). Son apoyos de
gráfica/diario, no tablas del inventario.

### 0.f Coherencia — solape con facts existentes (NO bloqueante)
`REAL PROMEDIO MES (YTD)` ya se carga desde **INICIO** → `fact_promedio_validado`; las **POP** alimentan
`fact_plan_mensual` desde *POP Filiales y Exploración*. Y **`P50 Acumulado` deriva de esta hoja**. Ingerir
NEW MES-AÑO a `fact_tabla_hoja` será una **copia paralela "tal como aparece"** (consistente con
PROGRAMA / P50 Acumulado). Aquí queda además la **fuente** del cubo P50.

### 0.g Auditoría de código
- **SIN tabla nueva, SIN migración, SIN DDL.** Reutiliza `core.fact_tabla_hoja` vía `HOJAS_MODELADAS`.
  Contrato `{tabla_idx,tabla_label,dims,fecha,valor}`.
- **SIN imports nuevos.** Reusa `_p50_grid`, `_p50_contig_months`, `s`, `num`, `to_date` (ya en `services.py`).
- **Contrato extendido** `{"rows":..., "tablas": DECLARED}` → el front lista **siempre las 13 tablas**.
- **Dedup/idempotencia** las maneja `load_tablas_hoja` (`DELETE WHERE reporte_id,hoja` + dedup por
  `(tabla_idx,dims,fecha)`). **Verificado: 0 colisiones en los 3 archivos.**

### 0.h Conteos esperados (autoridad de validación) — prototipo, por archivo
| idx | NEW-2024 | STD-2024 (feb) | STD-2023 (dic) | nota |
|---|---|---|---|---|
| 1 | 44 | 28 | 48 | calendario |
| 2 | 190 | 20 | 210 | REAL acumula |
| 3 | 80 | 16 | 96 | REAL acumula |
| 4 | 264 | 264 | 264 | estable |
| 5 | 156 | 156 | 156 | estable |
| 6 | 24 | 24 | 24 | estable |
| 7 | 48 | 48 | 48 | estable |
| 8 | 216 | 216 | 216 | estable |
| 9 | 156 | 156 | 156 | estable |
| 10 | 48 | 48 | 48 | estable |
| 11 | 216 | 216 | 216 | estable |
| 12 | 156 | 156 | 156 | estable |
| 13 | 48 | 48 | 48 | estable |
| **Total** | **1646** | **1396** | **1686** | |

> **Bloque estable T4–T13 = 1332 filas** en los 3 archivos. T1/T2/T3 varían por meses REAL elapsed.

### 0.i 🔧 Flujo profesional — verificación del visor y de no-breakage (v2)
- **Render del visor VERIFICADO por simulación** de la lógica real de `tablas/api.py::datos()` (modo fechas)
  sobre la salida del extractor (NEW-2024). Las **3 formas** de tabla renderizan sin crash:
  - `{producto, vice}` **con totales** (dims mixtas: las filas Total CRUDO/general traen `vice` ausente) →
    `dim_keys=[producto,vice]`, totales con `vice` en blanco. OK.
  - `{entidad}` (T6/10/13) y `{concepto}` (T1) → 1 columna de dimensión + meses. OK.
- 🔴 **D-mesano-1 (excluir 'Promedio Año') NO es cosmética: es NECESARIA.** El visor hace
  `meses = sorted({r["fecha"].isoformat() …})`; una fila con `fecha=NULL` (lo que sería el Promedio)
  lanzaría `AttributeError: 'NoneType'`. Al excluir el Promedio, **todas las filas tienen `fecha`** → el
  visor nunca recibe `None`. (Por eso §8.3 es regla dura.)
- **Sin nuevo camino de pipeline:** esta es la **6ª hoja modelada** y usa el MISMO flujo ya en producción
  (`HOJAS_MODELADAS` → `load_tablas_hoja` → evento `tablas[]` → chat.js clicable → `/api/tablas-hoja/datos`
  → `renderTablaAncha`). No se añade ni se altera ningún endpoint/función compartida → **0 riesgo de
  regresión** en las otras 5 hojas.
- **Fragilidad por filas fijas (documentada):** la spec usa rangos de fila hardcodeados — **igual que el
  extractor `_programa_extract` ya en producción** (patrón establecido). Mitigaciones: (a) anclas verificadas
  estables en los 3 archivos; (b) guarda `if not months: continue` (si una fila-encabezado deja de tener
  fechas, esa tabla se omite en vez de emitir basura). Si un archivo futuro desplaza filas, **re-auditar**
  (§8.7). Mejora opcional (no incluida para no divergir del patrón): anclar cada `hdr` por su texto-título.

---

## 1. Contexto

Proyecto **INGESTA / Rep_Prod**. ETL en
`C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`.
Hoy `NEW MES-AÑO` **solo cae en `bronze.hoja_landing`**. Este plan añade un **extractor** que la modela como
**13 tablas** en `core.fact_tabla_hoja` (formato largo: una fila por celda mensual), con valores **cacheados**.

## 2. Objetivo

1. Agregar `_mesano_extract(ws)` en `services.py`.
2. Registrarla en `HOJAS_MODELADAS` con `(?i)^NEW MES-?A[ÑN]O`.
3. Al ingerir un archivo con la hoja, sus 13 tablas quedan en `core.fact_tabla_hoja`, idempotente.

## 3. Prerequisitos (si falla alguno, DETENERSE y reportar)

- **P1** — `services.py` con `HOJAS_MODELADAS`, `load_tablas_hoja`, `_p50_grid`, `_p50_contig_months`, y
  `s`/`num`/`to_date` (de `app.shared.utils`).
- **P2** — `core.fact_tabla_hoja` existe. **NO** se crea/migra nada.
- **P3** — BD de `INGESTA\Rep_Prod\.env`. **No hardcodear contraseña** (`$env:PGPASSWORD` del `.env`).
- **P4** — `uv`; backend `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000`.
- **P5** — ≥1 `.xlsm` con la hoja `NEW MES-AÑO`.

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: añadir `_mesano_extract` + 1 línea en `HOJAS_MODELADAS`. |

**NO se toca:** DDL, migraciones, `api.py`, frontend, `load_tablas_hoja`, imports, ni otros extractores.

## 5. Especificación (código completo)

### 5.1 Extractor — agregar a `services.py`

**NO agregar imports.** Colocar **después de `_whatsapp_extract`** y **antes** del comentario
`# === Registro de hojas modeladas`. Pegar tal cual:

```python
def _mesano_extract(ws):
    """Extractor de 'NEW MES-AÑO' → 13 tablas (cubo fuente de P50/POP; valores cacheados TAL COMO APARECEN;
    NO recalcula; decisión usuario 2026-06-30). Contrato genérico [{tabla_idx,tabla_label,dims,fecha,valor}].

    2 bloques de columnas (anclas verificadas estables en 3 archivos):
      A–O (REAL + PROYECCIÓN), 7 tablas: etiquetas A=producto/concepto, B=vice/empresa; meses=fechas en C–N.
      S–AH (P50 + POP), 6 tablas: etiquetas T=producto, U=vice/empresa (S=índice, se ignora); meses=fechas V–AG.
    Meses por fila-encabezado de fechas (corte en 1ª no-fecha → excluye 'Promedio Año' O/AH, derivado, D-1).
    Incluye filas de total/subtotal (B/U vacío → dims solo con producto/concepto). Tablas de entidad
    (6/10/13): entidad ∈ {GON,GOO,VEX} o 'GRUPO EMPRESARIAL'; el resto de filas del rango se ignora.
    'REAL PROMEDIO MES' (1/2/3) acumula meses según el año del archivo (variación legítima).
    DECLARA siempre las 13 tablas. Excluye GRÁFICAS/META AÑO/serie diaria (otros bloques de columnas)."""
    grid, maxr = _p50_grid(ws)
    DECLARED = [
        (1, "T1 Parámetros calendario (A-O)"), (2, "T2 REAL PROMEDIO MES ECP (A-O)"),
        (3, "T3 REAL PROMEDIO MES Filiales (A-O)"), (4, "T4 PROYECCIÓN AÑO ECP (A-O)"),
        (5, "T5 PROYECCIÓN AÑO Filiales (A-O)"), (6, "T6 POP/PROY EXPLORACIÓN+G.E. (A-O)"),
        (7, "T7 POP Filiales (A-O)"), (8, "T8 P50 ECP (S-AH)"), (9, "T9 P50 Filiales (S-AH)"),
        (10, "T10 P50 EXPLORACIÓN+G.E. (S-AH)"), (11, "T11 POP ECP (S-AH)"),
        (12, "T12 POP Filiales (S-AH)"), (13, "T13 POP EXPLORACIÓN+G.E. (S-AH)"),
    ]
    EXPL = {"GON", "GOO", "VEX"}
    AO_ECP = [(1, "producto"), (2, "vice")];  AO_FIL = [(1, "producto"), (2, "empresa")]
    SAH_ECP = [(20, "producto"), (21, "vice")]; SAH_FIL = [(20, "producto"), (21, "empresa")]
    # (idx, hdr_fechas, fila_ini, fila_fin, col_ini_meses, dim_cols, kind)
    TABLES = [
        (1, 7, 6, 10, 3, [(1, "concepto")], "skiphdr"),
        (2, 13, 14, 35, 3, AO_ECP, ""), (3, 39, 40, 47, 3, AO_FIL, ""),
        (4, 59, 60, 81, 3, AO_ECP, ""), (5, 84, 85, 97, 3, AO_FIL, ""),
        (6, 99, 99, 105, 3, [(1, "a"), (2, "b")], "entidad"),
        (7, 112, 113, 116, 3, [(2, "empresa")], ""),
        (8, 8, 9, 27, 22, SAH_ECP, ""), (9, 30, 31, 43, 22, SAH_FIL, ""),
        (10, 46, 46, 52, 22, [(20, "a"), (21, "b")], "entidad"),
        (11, 59, 60, 81, 22, SAH_ECP, ""), (12, 84, 85, 97, 22, SAH_FIL, ""),
        (13, 99, 99, 105, 22, [(20, "a"), (21, "b")], "entidad"),
    ]
    LBL = {i: l for i, l in DECLARED}
    rows = []
    for idx, hdr, r0, r1, mstart, dim_cols, kind in TABLES:
        months = _p50_contig_months(grid, hdr, mstart)     # corta en 1ª no-fecha (excluye Promedio)
        if not months:
            continue
        for r in range(r0, r1 + 1):
            if kind == "skiphdr" and r == hdr:
                continue
            if kind == "entidad":
                la = s(grid.get((r, dim_cols[0][0]))); lb = s(grid.get((r, dim_cols[1][0])))
                ent = None
                if lb and lb.upper() in EXPL:
                    ent = lb.upper()
                elif la and "GRUPO EMP" in la.upper():
                    ent = "GRUPO EMPRESARIAL"
                elif lb and "GRUPO EMP" in lb.upper():
                    ent = "GRUPO EMPRESARIAL"
                if not ent:
                    continue
                dims = {"entidad": ent}
            else:
                dims = {}
                for col, name in dim_cols:
                    v = s(grid.get((r, col)))
                    if v is not None:
                        dims[name] = v
                if not dims:
                    continue
            for c, d in months:
                val = num(grid.get((r, c)))
                if val is None:
                    continue
                rows.append({"tabla_idx": idx, "tabla_label": LBL[idx],
                             "dims": dims, "fecha": d, "valor": val})
    return {"rows": rows, "tablas": DECLARED}
```

### 5.2 Registro — añadir 1 línea a `HOJAS_MODELADAS`

Después de la entrada de `Reporte Whatsapp` y antes del `]`:

```python
    # NEW MES-AÑO: 13 tablas (cubo fuente P50/POP). A-O REAL/PROYECCIÓN (7) + S-AH P50/POP (6).
    # Valores ya calculados, se ingieren tal cual. Meses por encabezado de fecha; excluye 'Promedio Año'.
    (re.compile(r"(?i)^NEW MES-?A[ÑN]O"), _mesano_extract),
```

## 6. Orden de ejecución

1. **Auditar** `services.py`: confirmar `HOJAS_MODELADAS`, `load_tablas_hoja`, `_p50_grid`,
   `_p50_contig_months`. Si P1/P2 fallan, DETENERSE.
2. Aplicar **§5.1** y **§5.2**. Sin imports nuevos.
3. **Tests:** `cd INGESTA\Rep_Prod\backend; uv run pytest -q` → **verde**.
4. Reiniciar el backend.
5. **Re-ingerir** un archivo NEW:
   ```powershell
   cd "C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm"
   ```
6. Validaciones **X1–X5**.

## 7. Validaciones (comando → esperado). `<HOST>`=127.0.0.1 (dev); `<REP>`=reporte_id del NEW

- **X1 — 13 tablas y conteos (NEW-2024):**
  ```sql
  SELECT tabla_idx, count(*) FROM core.fact_tabla_hoja
   WHERE hoja='NEW MES-AÑO' AND reporte_id=<REP> GROUP BY tabla_idx ORDER BY tabla_idx;
  ```
  Esperado (NEW): `44,190,80,264,156,24,48,216,156,48,216,156,48` → **TOTAL 1646**. (Bloque estable
  T4–T13 = 1332; T1/T2/T3 varían por meses REAL del archivo, §0.h.)
- **X2 — 12 meses año-correctos:**
  ```sql
  SELECT count(DISTINCT fecha), min(fecha), max(fecha) FROM core.fact_tabla_hoja
   WHERE hoja='NEW MES-AÑO' AND reporte_id=<REP>;   -- 12 ; 2024-01-31 ; 2024-12-31
  ```
- **X3 — Promedio Año excluido (todas las filas con fecha):**
  ```sql
  SELECT count(*) FILTER (WHERE fecha IS NULL) FROM core.fact_tabla_hoja
   WHERE hoja='NEW MES-AÑO' AND reporte_id=<REP>;   -- esperado 0
  ```
- **X4 — Spot-check (REAL PROMEDIO MES ECP, CRUDO/VAO, ene):**
  ```sql
  SELECT valor FROM core.fact_tabla_hoja WHERE hoja='NEW MES-AÑO' AND reporte_id=<REP>
    AND tabla_idx=2 AND dims->>'producto'='CRUDO' AND dims->>'vice'='VAO' AND fecha='2024-01-31';
  -- esperado ~160640.8
  ```
- **X5 — Idempotencia:** repetir el paso 5 y re-correr X1 → conteos **idénticos**, sin duplicar.

## 8. Reglas no negociables

1. **Valores cacheados tal como aparecen** (`data_only`); **prohibido recalcular**.
2. **13 tablas, 2 bloques** (A–O cols 1–15, S–AH cols 19–34). `tabla_label` estable; `DECLARED` == emitido.
3. **Meses por encabezado de fecha** (`_p50_contig_months`, corte en 1ª no-fecha) → **excluye 'Promedio Año'**
   (O/AH) — D-mesano-1. **No** mezclar `fecha=date` con `fecha=NULL` en una tabla.
4. **Incluir totales/subtotales**; tablas de entidad solo {GON,GOO,VEX}/GRUPO EMPRESARIAL.
5. **`#¡REF!`/`#N/A`/`(en blanco)` → en blanco** (`s()`/`num()`=None).
6. **Reutilizar `core.fact_tabla_hoja`**; sin tabla/migración/DDL; **sin imports nuevos**; no tocar
   `load_tablas_hoja`. **Devolver** `{"rows":..., "tablas": DECLARED}` (13 siempre).
7. Si la auditoría revela filas desplazadas (anclas distintas), **re-auditar** y adaptar los rangos (no
   inventar). Anclas verificadas estables en STD-2023/2024 y NEW-2024.

## 9. Fuera de alcance

- Columna **'Promedio Año'** (O/AH) — excluida (derivada; rompería el visor). Otra iteración si se requiere.
- Bloques **GRÁFICAS (AL–AX), META AÑO (AZ), serie diaria (BC–CM)** y helpers (P, AI/AJ) — no son tablas.
- Deduplicar contra `fact_promedio_validado`/`fact_plan_mensual` (solape §0.f): es copia paralela por decisión.
- UI/gráficos sobre estas tablas.
