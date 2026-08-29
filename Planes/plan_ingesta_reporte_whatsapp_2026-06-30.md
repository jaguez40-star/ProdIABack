# Plan ejecutable v2 — Ingesta de la hoja "Reporte Whatsapp" (12 tablas) → `core.fact_tabla_hoja`

> **Cobertura: `Tablas: entrada 12 → salida 12`** (M = N, sin reducción de alcance). Las columnas
> auxiliares **H y J** (apoyo, fuera de las 12 tablas confirmadas por el dueño; contienen los 6 `#¡REF!`)
> NO son tablas y se excluyen con justificación explícita (§0.e).
>
> Modo: **plan:** (para un executor sin contexto del repo). Rutas absolutas, código completo, decisiones
> cerradas, criterios verificables. **Versión auditada v2** — auditoría verificada contra el CÓDIGO real y
> contra **3 archivos** del corpus (estabilidad de layout, §0.2.5 del CLAUDE.md). Ver §0.

---

## 0. Hallazgos de auditoría (verificados contra CÓDIGO y DATOS reales)

### 0.a Auditoría de datos — estabilidad de layout entre **3 archivos** (disciplina §0.2.5)
Prototipo del extractor corrido sobre los 3 archivos del corpus con la hoja `Reporte Whatsapp`
(STD-2023, STD-2024, NEW-2024). **Anclajes y posiciones de columna IDÉNTICOS en los 3**; 0 colisiones de
dedup en los 3; siempre 12 tablas declaradas.

| Archivo | Tipo | Total filas | Observación |
|---|---|---|---|
| `20231231 Reportes Diario…` | STD | 288 | T1=0 (PROGRAMA todo `#¡REF!`), sin sección Equivalente (T9/T12=0) |
| `20240211 Reportes Diario…` | STD | 321 | T1=17 (parcial), sin sección Equivalente |
| `20241004_Reporte New…` | NEW | **438** | completo: 6×27 + T7 160 / T8 12 / T9 12 / T10 80 / T11 6 / T12 6 |

- **A1 — La hoja `Reporte Whatsapp` existe** (nombre 16 chars → no se trunca). Casar por prefijo
  `(?i)^Reporte\s+Whatsapp`.
- **A2 — SIN PivotTables ni ListObjects.** Todas las celdas son **fórmulas** que referencian otras hojas
  (INICIO, Nuevo Whatsapp, etc.). **Decisión del dueño: ingerir los VALORES CACHEADOS tal como aparecen,
  sin recalcular** (`data_only=True`).
- **A3 — 12 tablas (confirmado por el dueño)** en 2 bloques separados por columnas vacías:
  - **Bloque C–F (cols 3–6): 6 tablas consolidadas** apiladas (Ecopetrol/Filiales/Upstream ×
    Crudo/Gas/Blancos), **9 filas × 3 métricas (D/E/F)** c/u. Títulos en col C.
  - **Bloque L–T: 6 tablas por activo.** Las **cols Q y R están vacías y separan izquierda/derecha**
    (directriz del dueño): 3 secciones (Crudo, Gas, Equivalente) × 2 lados → izquierda **L–P** (4 métricas
    M/N/O/P) y derecha **S–T** (2 métricas S/T).

### 0.b 🔴 Hallazgo crítico — los títulos C–F **varían entre archivos** (mes/trimestre)
Los 6 títulos de col C NO son fijos:

| idx | 20231231 | 20240211 | 20241004 | Naturaleza |
|---|---|---|---|---|
| 1 | PROGRAMA | PROGRAMA | PROGRAMA | estable |
| 2 | **Junio** | **Febrero** | **Octubre** | **mes en curso** (cambia) |
| 3 | **PROY Junio** | **PROY Febrero** | **PROY Octubre** | **proyección mes** (cambia) |
| 4 | **4Q** | **1Q** | **4Q** | **trimestre** (cambia) |
| 5 | YTD | YTD | YTD | estable |
| 6 | AÑO | AÑO | AÑO | estable |

⇒ **`tabla_label` DEBE ser ESTABLE/posicional** (no el literal del mes). Si se usara el literal, además de
quedar erróneo en otros meses, **rompería la reconciliación de conteos** de `load_tablas_hoja` (que casa
`cont[(idx,label)]` contra `DECLARED`): el front mostraría 0 filas en tablas con datos. **Fix v2:** etiquetas
estables idénticas en `DECLARED` y en las filas emitidas; el mes/trimestre real se recupera del
`reporte_id` (fecha del archivo) o de `dims.metrica` (que conserva el rótulo literal, p.ej. "Real día 3 Oct").

### 0.c 🔴 Hallazgo crítico — la fecha as-of de la hoja **NO es fiable** → `fecha = NULL`
La celda `Producción al:` del archivo `20231231` reporta **2026-06-22** (sus valores cacheados fueron
re-calculados al abrir el archivo en jun-2026; **no** son de dic-2023, y sus títulos dicen "Junio"). Usar esa
fecha como `fact_tabla_hoja.fecha` **contaminaría el linaje** (quedaría 2026-06-22 bajo un `reporte_id` de
2023-12-31) y podría chocar analíticamente con un archivo real de esa fecha.
⇒ **Fix v2:** `fecha = NULL`. El linaje temporal lo da `reporte_id → config_reporte.fecha_reporte` (fecha del
archivo). El patrón `fecha=None` ya está probado (tablas matriz de `_filiales_extract`). La temporalidad fina
vive en `dims.metrica`/`dims.columna`. **(Decisión D-whatsapp-1: confirmar.)**

### 0.d Robustez ante cobertura heterogénea (verificada, NO es bug)
- La **sección "Producción equivalente por filial"** (T9/T12) **solo existe en NEW-2024**; en STD-2023/2024
  no está → T9/T12 = 0. El patrón **"DECLARA siempre las 12 tablas"** lo maneja (el front las lista con 0).
- En STD hay **celdas `#¡REF!`/vacías** (T1=0 en 2023, T1/T5=17 en 2024). `s()`/`num()` del repo tratan
  `#¡REF!`/`#N/A`/`(en blanco)` como **None** (constante `NOISE`) → la celda **se deja en blanco**
  (no se emite fila). Esto **cumple exactamente** la directriz del dueño ("`#¡REF!` → en blanco").

### 0.e Inventario exhaustivo y cobertura (regla anti-reducción §0.2)
- **12 tablas → 12 tablas.** Ninguna se omite.
- **Columnas auxiliares H y J:** NO son tablas (son celdas de apoyo intermedias; ahí viven los 6 `#¡REF!`:
  H18/H26/H34, J16/J24/J32). Excluidas con justificación (no aportan una tabla del inventario del dueño).
  Si el dueño quisiera ingerirlas sería otra iteración (columna `fecha=NULL`, dims `{fila, columna}`).

### 0.f Desviación DELIBERADA de la regla de ruido §5#5 (declarar, no enterrar)
El CLAUDE.md (§5#5, §7.5) dice "excluir filas `Total X`/`(en blanco)`". **Aquí se INCLUYEN** las filas de
total/subtotal (Ecopetrol/Filiales/Upstream y los `Total` de cada tabla) **por decisión explícita del dueño**
("ingerir los valores tal como aparecen, incluidas las filas de totales"). Es una desviación consciente, no
un descuido — para que un revisor no la "corrija".

### 0.g Auditoría de código (cruce contra `services.py`)
- **B1 — SIN tabla nueva, SIN migración, SIN DDL.** Reutiliza `core.fact_tabla_hoja` vía `HOJAS_MODELADAS`
  (igual que P50/Filiales/Bitacora/P50 Acumulado/PROGRAMA). Contrato `{tabla_idx,tabla_label,dims,fecha,valor}`.
- **B2 — SIN imports nuevos.** `s`/`num` (de `app.shared.utils`) y `_p50_grid` ya están en `services.py`.
  (`to_date` ya no se usa: `fecha=NULL`.)
- **B3 — Contrato extendido** `{"rows":[...], "tablas": DECLARED}` → el front lista **siempre 12 tablas**.
- **B4 — Dedup/idempotencia las maneja `load_tablas_hoja`**: dedup por `(tabla_idx, dims, fecha)` +
  `DELETE … WHERE reporte_id=? AND hoja=?`. **Verificado: 0 colisiones en los 3 archivos** (las dims
  incluyen `columna`, garantizando unicidad aunque `metrica` se repita —p.ej. 'Real' diario vs acum-mes).

### 0.h Conteos esperados (autoridad de validación) — referencia NEW-2024
| idx | tabla_label (estable) | NEW-2024 | Detalle |
|---|---|---|---|
| 1 | T1 PROGRAMA (consolidado) | 27 | 9 filas × 3 |
| 2 | T2 Mes en curso (consolidado) | 27 | 9 × 3 |
| 3 | T3 Proyección mes (consolidado) | 27 | 9 × 3 |
| 4 | T4 Trimestre (consolidado) | 27 | 9 × 3 |
| 5 | T5 YTD (consolidado) | 27 | 9 × 3 |
| 6 | T6 Año (consolidado) | 27 | 9 × 3 |
| 7 | T7 Crudo por activo (izq L-P) | 160 | 40 activos × 4 |
| 8 | T8 Gas por activo (izq L-P) | 12 | 3 × 4 |
| 9 | T9 Equivalente por filial (izq L-P) | 12 | 3 × 4 |
| 10 | T10 Crudo por activo (der S-T) | 80 | 40 × 2 |
| 11 | T11 Gas por activo (der S-T) | 6 | 3 × 2 |
| 12 | T12 Equivalente por filial (der S-T) | 6 | 3 × 2 |
| | **TOTAL NEW-2024** | **438** | |

> En archivos **STD** los conteos son **menores** (datos parciales/secciones ausentes): STD-2023=288,
> STD-2024=321. **Las 12 tablas se declaran siempre.** Spot-checks (NEW-2024, cacheado, sin recalcular):
> `T1` Ecopetrol/Crudo/col D = **494.90322268936495**; `T7` RUBIALES/col M = **101.06170999999999**;
> `T10` RUBIALES/col T = **101.44629**; `T9` PERMIAN/col M = **100.25893503386172**.

---

## 1. Contexto

Proyecto **INGESTA / Rep_Prod** (FastAPI + SQLAlchemy Core + PostgreSQL, Medallion bronze/core). ETL en
`C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py`.
Hoy la hoja `Reporte Whatsapp` **solo cae en `bronze.hoja_landing`**. Este plan añade un **extractor** que la
modela como **12 tablas** en `core.fact_tabla_hoja` (formato largo, una fila por celda numérica), con los
valores **ya calculados** de la hoja (sin recalcular).

## 2. Objetivo

1. Agregar `_whatsapp_extract(ws)` en `services.py`.
2. Registrarla en `HOJAS_MODELADAS` con `(?i)^Reporte\s+Whatsapp`.
3. Al ingerir cualquier archivo con la hoja, sus 12 tablas quedan en `core.fact_tabla_hoja` y aparecen en el
   visor "Para análisis", idempotente.

## 3. Prerequisitos (si alguno falla, DETENERSE y reportar)

- **P1** — Existe `…\backend\app\features\ingesta\services.py` con `HOJAS_MODELADAS`, el helper `_p50_grid`,
  los helpers `s`/`num` (de `app.shared.utils`) y `load_tablas_hoja`.
- **P2** — `core.fact_tabla_hoja` **ya existe**. **NO** se crea ni migra nada.
- **P3** — BD destino de `INGESTA\Rep_Prod\.env` (`DATABASE_URL`). **No hardcodear la contraseña**: usar
  `$env:PGPASSWORD` leído del `.env`.
- **P4** — `uv` instalado; backend con `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000`
  (reiniciar tras editar).
- **P5** — Existe ≥1 `.xlsm` con la hoja `Reporte Whatsapp` (p.ej. `20241004_Reporte New…xlsm`).

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: añadir `_whatsapp_extract` + 1 línea en `HOJAS_MODELADAS`. |

**NO se toca:** DDL, migraciones, `api.py`, frontend, `land_landing`, imports, ni los demás extractores/
facts. **NO se modifica `load_tablas_hoja`** (la firma `extractor(ws)` se respeta; por eso `fecha=NULL` se
fija dentro del extractor, sin pasar `reporte_id`).

## 5. Especificación (código completo)

### 5.1 Extractor — agregar a `services.py`

**NO agregar imports.** Colocar la función **después de `_programa_extract`** y **antes** del comentario
`# === Registro de hojas modeladas`. Pegar tal cual:

```python
def _whatsapp_extract(ws):
    """Extractor de 'Reporte Whatsapp' → 12 tablas (valores cacheados TAL COMO APARECEN; NO recalcula;
    decisión usuario 2026-06-30). Contrato genérico [{tabla_idx,tabla_label,dims,fecha,valor}].

    Bloque C–F (cols 3..6) — 6 tablas consolidadas apiladas (idx 1..6; Ecopetrol/Filiales/Upstream ×
      Crudo/Gas/Blancos). 9 filas × 3 métricas D/E/F. dims={segmento, concepto, columna(D/E/F), metrica}.
      ⚠ Los títulos de col C varían entre archivos (mes/trimestre: Junio/Febrero/Octubre, 1Q/4Q); por eso
      las etiquetas son ESTABLES/posicionales y deben coincidir con DECLARED (si no, load_tablas_hoja
      reportaría 0 filas). El segmento se deriva de las filas de subtotal (Ecopetrol/Filiales/Upstream).
    Bloque L–T — 6 tablas por activo (idx 7..12). Las cols Q/R (vacías) separan izquierda L–P (4 métricas
      M/N/O/P) de derecha S–T (2 métricas S/T). 3 secciones (1=Crudo, 2=Gas, 3=Equivalente) ancladas por
      L=='ACTIVOS'; blancos internos NO cortan; cierra en la nota '**…' o el siguiente 'ACTIVOS'.
      dims={activo, columna, metrica} (columna garantiza unicidad cuando metrica se repite: 'Real' diario
      vs acum-mes). La sección Equivalente puede faltar (STD) → T9/T12 quedan vacías (se declaran igual).

    fecha=NULL: la celda 'Producción al:' es poco fiable (en archivos STD viejos trae valores re-calculados
    de otra época); el linaje temporal lo da reporte_id→config_reporte. Celdas #¡REF!/#N/A/(en blanco) →
    s()/num()=None (NOISE) → NO se emiten (se dejan en blanco), según la directriz del dueño. Incluye las
    filas de total/subtotal (decisión del dueño; desvía de la regla de ruido §5#5 a propósito).
    DECLARA siempre las 12 tablas. Anclajes verificados estables en 3 archivos (STD-2023/2024, NEW-2024)."""
    grid, maxr = _p50_grid(ws)
    DECLARED = [
        (1, "T1 PROGRAMA (consolidado)"), (2, "T2 Mes en curso (consolidado)"),
        (3, "T3 Proyección mes (consolidado)"), (4, "T4 Trimestre (consolidado)"),
        (5, "T5 YTD (consolidado)"), (6, "T6 Año (consolidado)"),
        (7, "T7 Crudo por activo (izq L-P)"), (8, "T8 Gas por activo (izq L-P)"),
        (9, "T9 Equivalente por filial (izq L-P)"), (10, "T10 Crudo por activo (der S-T)"),
        (11, "T11 Gas por activo (der S-T)"), (12, "T12 Equivalente por filial (der S-T)"),
    ]
    LBL = {i: l for i, l in DECLARED}
    rows = []
    FECHA = None   # linaje por reporte_id; as-of de la hoja no fiable (ver docstring / §0.c del plan)

    # ===== Bloque C–F (cols 3..6): 6 tablas consolidadas apiladas =====
    HDR_KW = ("real", "plan", "proy", "delta", "programa", "pop")
    SEG_ORDER = ["Ecopetrol", "Filiales", "Upstream"]
    # fila-título = C con texto y D con un rótulo de encabezado (Real/Plan/Proy/Delta/Programa/POP)
    cf_titles = [r for r in range(1, maxr + 1)
                 if s(grid.get((r, 3))) and s(grid.get((r, 4)))
                 and any(k in s(grid.get((r, 4))).lower() for k in HDR_KW)]
    for ti, trow in enumerate(cf_titles[:6]):
        idx = ti + 1                                   # idx posicional ESTABLE (1..6)
        metrics = [(cc, ll, s(grid.get((trow, cc)))) for cc, ll in ((4, "D"), (5, "E"), (6, "F"))]
        metrics = [(cc, ll, m) for cc, ll, m in metrics if m]
        seg_i, r = 0, trow + 1
        while r <= maxr:
            lab = s(grid.get((r, 3)))
            if lab is None:                            # blanco/ruido en col C = fin de la tabla
                break
            lu = lab.upper()
            if lu == "ECOPETROL":
                seg, con, seg_i = "Ecopetrol", "Total", 1
            elif lu == "FILIALES":
                seg, con, seg_i = "Filiales", "Total", 2
            elif lu == "UPSTREAM":
                seg, con = "Upstream", "Total"
            else:
                seg, con = SEG_ORDER[seg_i], lab       # Crudo/Gas/Blancos del segmento actual
            for cc, ll, m in metrics:
                val = num(grid.get((r, cc)))
                if val is None:
                    continue
                rows.append({"tabla_idx": idx, "tabla_label": LBL[idx],
                             "dims": {"segmento": seg, "concepto": con, "columna": ll, "metrica": m},
                             "fecha": FECHA, "valor": val})
            if lu == "UPSTREAM":                       # Upstream cierra la tabla
                break
            r += 1

    # ===== Bloque L–T: secciones ancladas por L=='ACTIVOS' (col 12); Q/R separan izq/der =====
    LEFT = [(13, "M"), (14, "N"), (15, "O"), (16, "P")]      # izquierda L–P (4 métricas)
    RIGHT = [(19, "S"), (20, "T")]                           # derecha S–T (2 métricas)
    SEC = [(7, 10), (8, 11), (9, 12)]                        # orden estable: 1=Crudo, 2=Gas, 3=Equivalente
    sec_hdrs = [r for r in range(1, maxr + 1) if s(grid.get((r, 12))) == "ACTIVOS"]
    for si, hdr in enumerate(sec_hdrs[:3]):
        lidx, ridx = SEC[si]
        lmet = [(cc, ll, s(grid.get((hdr, cc)))) for cc, ll in LEFT]
        rmet = [(cc, ll, s(grid.get((hdr, cc)))) for cc, ll in RIGHT]
        r, blanks = hdr + 1, 0
        while r <= maxr:
            act = s(grid.get((r, 12)))
            if act is None:                            # blanco interno (f14/25/36) NO corta
                blanks += 1
                if blanks >= 3:                        # 3 blancos seguidos = fin de sección
                    break
                r += 1
                continue
            if act.startswith("**") or act == "ACTIVOS":   # nota '**…' o sig. encabezado
                break
            blanks = 0
            for cc, ll, m in lmet:
                val = num(grid.get((r, cc)))
                if val is None:
                    continue
                rows.append({"tabla_idx": lidx, "tabla_label": LBL[lidx],
                             "dims": {"activo": act, "columna": ll, "metrica": m},
                             "fecha": FECHA, "valor": val})
            for cc, ll, m in rmet:
                val = num(grid.get((r, cc)))
                if val is None:
                    continue
                rows.append({"tabla_idx": ridx, "tabla_label": LBL[ridx],
                             "dims": {"activo": act, "columna": ll, "metrica": m},
                             "fecha": FECHA, "valor": val})
            r += 1

    return {"rows": rows, "tablas": DECLARED}
```

### 5.2 Registro — añadir 1 línea a `HOJAS_MODELADAS`

Dentro de `HOJAS_MODELADAS`, **después** de la entrada de `PROGRAMA` y **antes** del `]`:

```python
    # Reporte Whatsapp: 12 tablas (6 consolidadas C-F + 6 por activo L-T, izq/der separadas por Q-R).
    # Valores ya calculados, se ingieren tal cual. fecha=NULL (as-of de la hoja no fiable en STD viejos).
    # Etiquetas estables (los títulos de mes/trimestre cambian entre archivos). Nombre 16 chars → sin truncar.
    (re.compile(r"(?i)^Reporte\s+Whatsapp"), _whatsapp_extract),
```

## 6. Orden de ejecución

1. **Auditar** `services.py`: confirmar `HOJAS_MODELADAS`, que `load_tablas_hoja` itera el registro y casa
   `cont[(idx,label)]` contra `DECLARED` (por eso las etiquetas deben coincidir), y que `_p50_grid`/`s`/`num`
   existen. Verificar §3; si P1/P2/P3 fallan, DETENERSE.
2. Aplicar **§5.1** y **§5.2**. Sin imports nuevos. No tocar `load_tablas_hoja`.
3. **Tests:** `cd INGESTA\Rep_Prod\backend; uv run pytest -q` → debe seguir **verde**.
4. Reiniciar el backend FastAPI.
5. **Re-ingerir** un archivo NEW (idempotente). Por CLI:
   ```powershell
   cd "C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm"
   ```
6. Ejecutar validaciones **X1–X6**.

## 7. Validaciones (comando → esperado). Credencial: `$env:PGPASSWORD` leído de `INGESTA\Rep_Prod\.env`

> `<HOST>` = `127.0.0.1` (dev) o `10.100.26.139` (prod); `<REP>` = `reporte_id` del archivo NEW ingerido.
> `psql.exe` en `C:\Program Files\PostgreSQL\18\bin\`.

- **X1 — 12 tablas declaradas y conteo (archivo NEW-2024):**
  ```sql
  SELECT tabla_idx, tabla_label, count(*) FROM core.fact_tabla_hoja
   WHERE hoja='Reporte Whatsapp' AND reporte_id=<REP>
   GROUP BY tabla_idx, tabla_label ORDER BY tabla_idx;
  ```
  Esperado (NEW): `27,27,27,27,27,27,160,12,12,80,6,6` → **TOTAL 438**. (En STD los conteos son menores;
  ver §0.h. Las 12 etiquetas deben ser exactamente las de `DECLARED`.)
- **X2 — Total:** `SELECT count(*) … reporte_id=<REP>;` → **438** (NEW).
- **X3 — fecha NULL:** `SELECT count(*) FILTER (WHERE fecha IS NULL) AS nulos, count(*) AS tot … reporte_id=<REP>;`
  → `nulos = tot` (todas NULL).
- **X4 — Spot-check consolidado (col D = valor real/proy):**
  ```sql
  SELECT valor FROM core.fact_tabla_hoja
   WHERE hoja='Reporte Whatsapp' AND reporte_id=<REP> AND tabla_idx=1
     AND dims->>'segmento'='Ecopetrol' AND dims->>'concepto'='Crudo' AND dims->>'columna'='D';
  -- esperado ~494.9032
  ```
- **X5 — Spot-check por activo (izq y der):**
  ```sql
  SELECT tabla_idx, dims->>'columna' col, valor FROM core.fact_tabla_hoja
   WHERE hoja='Reporte Whatsapp' AND reporte_id=<REP>
     AND dims->>'activo'='RUBIALES' AND tabla_idx IN (7,10) ORDER BY tabla_idx, col;
  -- T7 col M ~101.0617 ; T10 col T ~101.4463
  ```
- **X6 — Idempotencia:** repetir el paso 6 y re-correr X1/X2 → conteos **idénticos** (438), sin duplicar.
- **X7 (manual, opcional):** http://localhost:8020 → subir el archivo → bajo `Reporte Whatsapp` deben verse
  **12 tablas** en "Para análisis".

## 8. Reglas no negociables

1. **Valores CACHEADOS tal como aparecen** (`data_only`); **prohibido recalcular** desde las hojas fuente.
2. **`tabla_label` ESTABLE/posicional** (no el literal del mes/trimestre) e **idéntico en `DECLARED` y en
   las filas emitidas** (si difieren, `load_tablas_hoja` reporta 0 filas). NO hardcodear "Octubre"/"4Q".
3. **`fecha = NULL`** (linaje por `reporte_id`). NO usar la celda `Producción al:` (no fiable en STD viejos).
4. **`#¡REF!`/`#N/A`/`(en blanco)` → en blanco** (`s()`/`num()`=None vía `NOISE` → no se emite fila).
   **No** ingerir las cols auxiliares **H y J**.
5. **Q y R separan izquierda (L–P) de derecha (S–T)**: tablas distintas (7/8/9 izq, 10/11/12 der). No fusionar.
6. **Blancos internos del bloque de activos (f14/25/36) NO cortan**; cortan la nota `**…`, el siguiente
   `ACTIVOS`, o 3 blancos seguidos. La **sección Equivalente puede faltar** (STD) → declarar T9/T12 vacías.
7. **INCLUIR las filas de total/subtotal** (decisión del dueño; desvía a propósito de §5#5).
8. **Reutilizar `core.fact_tabla_hoja`**; **no** crear tabla/migración/DDL. **No agregar imports.**
   **No modificar `load_tablas_hoja`.**
9. **Devolver** `{"rows":..., "tablas": DECLARED}` (declara las 12 tablas siempre).
10. **No hardcodear contraseñas**; conexión desde `INGESTA\Rep_Prod\.env`. Si la auditoría del paso 1 revela
    firmas/nombres distintos, **adaptar a los reales** (no inventar).

## 9. Fuera de alcance / caveats

- **Caveat de datos (no corregible aquí):** las hojas calculadas (Whatsapp) en archivos **STD antiguos**
  traen valores **re-calculados a la última apertura** (p.ej. `20231231` muestra jun-2026), no los de su
  fecha nominal. Ingerir "tal como aparece" de archivos viejos puede traer datos de otra época; en producción
  esto no afecta porque se ingiere el archivo **del día**. Mitigación: linaje por `reporte_id` + `fecha=NULL`.
- **Columnas auxiliares H y J** (apoyo; los 6 `#¡REF!`) — excluidas por decisión (no son tablas).
- Normalizar/trazar las hojas fuente (INICIO, Nuevo Whatsapp) a BDP raw — otro plan.
- Botones/gráficos sobre estas tablas; corrección del landing genérico de otras hojas.
- **3 archivos 2026** (`20260531/0601/0602`) dan error de ZIP al abrirse — incidencia a nivel de archivo
  (ajena a este extractor); reportar aparte si deben ingerirse.

---

### Decisión pendiente de confirmar
**D-whatsapp-1 — `fecha = NULL`** (vs. usar la celda `Producción al:`). Recomendado NULL por §0.c. Si el
dueño prefiere la as-of de la hoja, es 1 línea (se documenta que en STD viejos será de otra época).
