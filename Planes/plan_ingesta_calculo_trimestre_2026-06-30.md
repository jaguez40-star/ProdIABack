# Plan ejecutable (v2) — Modelado de la hoja "CALCULO DE TRIMESTRE" → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 8 → salida 8** (exactamente las 8 que definió el usuario; nada omitido).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `CALCULO DE TRIMESTRE`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA (usa `core.fact_tabla_hoja`; `fecha`/`valor` nullable).
> **Frontend / api.py:** SIN cambios (modos "fechas" y "matriz" del visor, ya probados).

---

## 0. Auditoría (datos reales, 3 archivos — layout 100% estable, maxr=94, maxc=O)

Hoja **intermedia de cálculo** (r2 = `***SOLO CALCULO`), heterogénea. Se ingieren las **8 tablas tal
como las definió el usuario**; valores cacheados TAL CUAL (no se recalcula). Coexiste con datos
duplicados de otras hojas — **autorizado por el usuario** ("duplica la información no hay problema") y
coherente con D3 ("ingerir todo, nada se pierde").

| T | Cols | Filas | Tipo | Modelo | Filas-dato (3 archivos) |
|--:|------|-------|------|--------|------------------------:|
| 1 | D-I | 8-22 | snapshot | **matriz** `fila×columna`, fecha=NULL | 19 |
| 2 | A-O | 23-31 | temporal | `fecha=mes`, dims `{producto}` | 84 |
| 3 | A-O | 34-48 | temporal | `fecha=mes`, dims `{producto,empresa}` | 156 |
| 4 | A-O | 50-51 | temporal | `fecha=mes`, dims `{concepto}` | 12 |
| 5 | A-E | 53-66 | trimestral | **matriz** `columna=1Q-4Q`, fila=concepto+bloque | 36 |
| 6 | H-L | 54-68 | trimestral | **matriz** `columna=1Q-4Q`, fila=concepto+bloque | 56 |
| 7 | A-E | 75-82 | trimestral | **matriz** `columna=1Q-4Q`, fila=concepto | 24 |
| 8 | A-E | 86-94 | trimestral | **matriz** `columna=1Q-4Q`, fila=concepto | 28 |
|   |     |       |      | **TOTAL** | **415** |

**Decisiones técnicas internas (sin pérdida, sin pedir input al usuario):**
- **T1 heterogénea** (D-E PROGRAMA MES producto×valor + G-I FILIALES producto×empresa): se ingieren
  AMBAS bajo `tabla_idx=1` como matriz, distinguidas por `columna` ("Programa mes" vs "Filiales").
  fecha=NULL (snapshot; el as-of `B8` varía: 20231231/20240229/20241031, linaje por `reporte_id`).
- **T5/T6 conceptos repetidos** (CRUDO/GAS/BLANCOS aparecen en el bloque ECP filas<62 y en el bloque
  FILIALES filas≥62): se embebe el **bloque** en `dims.fila` (`CRUDO (ECP)` vs `CRUDO (FILIALES)`) →
  **0 colisiones**, ninguna fila se pierde. **[v2]** el sufijo se aplica **solo a las etiquetas que se
  repiten** dentro de la tabla → VDP/FILIALES/TOTAL/UPSTREAM/VEX… quedan limpias (sin "UPSTREAM
  (FILIALES)" engañoso). T7/T8 no repiten (sin sufijo).
- **Trimestres** (1Q/2Q/3Q/4Q): no son fechas → matriz `columna=trimestre`, `fecha=NULL`.
- **Escenario** (P50 631 / P50 621,9 / POP) va en el `tabla_label` POSICIONAL estable (no depende del
  valor del título, que en teoría podría cambiar entre años).
- **Temporales (T2/T3/T4):** meses por `_p50_contig_months` (corta en "Promedio Año", col O). Año-correcto.

Verificado (prototipo, 3 archivos): conteos **idénticos** (19/84/156/12/36/56/24/28 = 415), **0 colisiones**.

### No-breakage
- Cada `tabla_idx` es internamente homogéneo en `fecha` → el visor elige bien su modo (T2/T3/T4 →
  "fechas"; T1/T5/T6/T7/T8 → "matriz"). Ambos modos ya probados en hojas previas.
- 10ª hoja con el MISMO pipeline (extractor → contrato extendido → `load_tablas_hoja` → emit) ⇒ 0
  riesgo de regresión. pytest no aserta nº de hojas modeladas.

### 0.g — Flujo profesional v2: verificación de incoherencias / no-breakage (datos y código reales)
1. **Sin loader pre-existente** para esta hoja (grep en services.py) → **sin coexistencia/conflicto**
   (a diferencia de POP, que ya tenía `load_pop`→`fact_plan_mensual`). Esta hoja es nueva al pipeline.
2. **MEJORA aplicada (sufijo solo a duplicados)**: en T5/T6 el bloque ECP/FILIALES se añade únicamente a
   `CRUDO/GAS/BLANCOS` (las que se repiten); VDP/FILIALES/TOTAL/UPSTREAM/VEX… quedan limpias. Evita el
   `UPSTREAM (FILIALES)` engañoso. Verificado: conteos intactos (T5=36, T6=56), 0 colisiones.
3. **T1 robusto ante choque de etiquetas**: aunque una etiqueta del bloque D-E coincidiera con una del
   G-I, NO hay pérdida — distinta `columna` (`Programa mes` vs `Filiales`) ⇒ claves dedup distintas y,
   en el visor, comparten fila con dos columnas. (Verificado: 0 colisiones en los 3 archivos.)
4. **Inventario exhaustivo (§0.2)**: estructuras de la hoja y clasificación:
   - (a) encajan → T1..T8 (las 8 del usuario). **MODELADAS.**
   - (c) metadata, no-tablas → r2 `***SOLO CALCULO` (nota), **r6 'Días del año'** (días por mes, como la
     fila 1 de POP), r32 `Trimestre con…` (nota). No se ingieren (justificado).
   → **`Tablas: entrada 8 → salida 8`**.
5. **Sin disparadores de riesgo §0.2**: no toca DDL, ni clave natural (fact sin UNIQUE; dedup en código),
   ni `ON CONFLICT`, ni detección raw/STD. Extractor + 1 línea de registro.
6. **`auditoria:` (paridad)**: hoja intermedia de cálculo; se ingiere TAL CUAL (no se recalcula) →
   paridad 1:1 por construcción. `#REF!`/vacíos los anula `num()` (se saltan).
7. **Visor resalta totales**: filas como `VDP`, `TOTAL`, `UPSTREAM` no empiezan por "total" → no se
   resaltan; las que sí (`Total general`, `Total Crudo` en T1/T2/T3) sí. Comportamiento esperado, sin
   acción requerida.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_calculo_trimestre_extract` (insertar después de `_pop_filiales_extract`,
antes del bloque `# === Registro de hojas modeladas: ...`)

```python
def _calculo_trimestre_extract(ws):
    """Extractor de 'CALCULO DE TRIMESTRE' → 8 tablas (definidas por el usuario). Hoja intermedia de
    cálculo, heterogénea; valores cacheados TAL CUAL (NO recalcula). Contrato extendido.
    T1 (D-I, snapshot matriz): PROGRAMA MES (producto×valor, col 'Programa mes') + FILIALES
       (producto×empresa, col 'Filiales'); fecha=NULL.
    T2/T3/T4 (temporales, fecha=mes): producto×mes / producto×empresa×mes / GRUPO EMPRESA×mes.
       Meses por _p50_contig_months (corta en 'Promedio Año', col O).
    T5/T6/T7/T8 (trimestrales, matriz columna=1Q-4Q, fila=concepto): P50 631 PLAN / P50 631 REAL /
       P50 621,9 PLAN / POP PLAN. En T5/T6 el concepto se repite (bloque ECP filas<62 vs FILIALES
       filas>=62) -> se embebe el bloque en la fila para no perder filas (0 colisiones)."""
    grid, _maxr = _p50_grid(ws)
    DECLARED = [
        (1, "PROGRAMA MES + FILIALES"), (2, "PROYECCIÓN AÑO producto×mes"),
        (3, "PROYECCIÓN AÑO producto×empresa×mes"), (4, "GRUPO EMPRESA×mes"),
        (5, "P50 631 PLAN (trimestres)"), (6, "P50 631 REAL (trimestres)"),
        (7, "P50 621,9 PLAN (trimestres)"), (8, "POP PLAN (trimestres)"),
    ]
    LBL = {i: l for i, l in DECLARED}
    rows = []

    def emit(idx, dims, fecha, raw):
        v = num(raw)
        if v is None:
            return
        rows.append({"tabla_idx": idx, "tabla_label": LBL[idx],
                     "dims": dims, "fecha": fecha, "valor": v})

    # --- T1 (cols D-I, filas 8-22) — matriz snapshot, fecha=NULL ---
    for r in range(8, 23):
        a = s(grid.get((r, 4)))                       # D: producto (PROGRAMA MES)
        if a is not None:
            emit(1, {"fila": a, "columna": "Programa mes"}, None, grid.get((r, 5)))   # E
        gl = s(grid.get((r, 7)))                      # G: producto (FILIALES)
        if gl is not None:
            emp = s(grid.get((r, 8)))                 # H: empresa
            fila = f"{gl} · {emp}" if emp else gl
            emit(1, {"fila": fila, "columna": "Filiales"}, None, grid.get((r, 9)))     # I

    # --- T2/T3/T4 — temporales (fecha=mes; meses desde col C=3) ---
    for r in range(25, 32):                           # T2: producto × mes
        a = s(grid.get((r, 1)))
        if a is None:
            continue
        for c, d in _p50_contig_months(grid, 24, 3):
            emit(2, {"producto": a}, d, grid.get((r, c)))
    for r in range(36, 49):                           # T3: producto × empresa × mes
        a = s(grid.get((r, 1)))
        if a is None:
            continue
        dims = {"producto": a}
        b = s(grid.get((r, 2)))
        if b is not None:
            dims["empresa"] = b
        for c, d in _p50_contig_months(grid, 35, 3):
            emit(3, dims, d, grid.get((r, c)))
    for r in range(51, 52):                           # T4: GRUPO EMPRESA × mes
        a = s(grid.get((r, 1)))
        if a is None:
            continue
        for c, d in _p50_contig_months(grid, 50, 3):
            emit(4, {"concepto": a}, d, grid.get((r, c)))

    # --- T5/T6/T7/T8 — trimestrales (matriz columna=1Q-4Q, fila=concepto[+bloque en T5/T6]) ---
    QLABELS = ["1Q", "2Q", "3Q", "4Q"]
    # (tabla_idx, col_etiqueta, [cols_trimestre], rango_filas, usa_bloque)
    QSPECS = [
        (5, 1, [2, 3, 4, 5], range(55, 67), True),
        (6, 8, [9, 10, 11, 12], range(55, 69), True),
        (7, 1, [2, 3, 4, 5], range(77, 83), False),
        (8, 1, [2, 3, 4, 5], range(88, 95), False),
    ]
    for idx, lcol, qcols, rng, usa_bloque in QSPECS:
        # [v2] sufijar el bloque SOLO a las etiquetas que se repiten dentro de la tabla
        # (CRUDO/GAS/BLANCOS) -> VDP/FILIALES/TOTAL/UPSTREAM/VEX... quedan limpias. Sin imports nuevos.
        labels = [s(grid.get((r, lcol))) for r in rng]
        dups = {x for x in labels if x is not None and labels.count(x) > 1} if usa_bloque else set()
        for r in rng:
            a = s(grid.get((r, lcol)))
            if a is None:
                continue
            fila = f"{a} ({'ECP' if r < 62 else 'FILIALES'})" if a in dups else a
            for c, q in zip(qcols, QLABELS):
                emit(idx, {"fila": fila, "columna": q}, None, grid.get((r, c)))

    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de POP Filiales y Exploración)

```python
    # CALCULO DE TRIMESTRE: hoja intermedia, 8 tablas heterogéneas (1 snapshot + 3 temporales + 4
    # trimestrales 1Q-4Q). Valores ya calculados, se ingieren tal cual. Datos parcialmente duplicados
    # de otras hojas (autorizado por el usuario / D3).
    (re.compile(r"(?i)^C[AÁ]LCULO DE TRIMESTRE"), _calculo_trimestre_extract),
```

**NO** agregar imports (`s`, `num`, `to_date`, `_p50_grid`, `_p50_contig_months` ya existen).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_pop_filiales_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `to_date`, `_p50_grid`, `_p50_contig_months` existen en services.py.
3. Nombre exacto de la hoja: `CALCULO DE TRIMESTRE` (regex `^C[AÁ]LCULO DE TRIMESTRE`).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico `2024-10-04`; tomar `<rid>` de la ingesta)

- **X1 — 8 tablas:** `GET /tablas?...&hoja=CALCULO DE TRIMESTRE` → 8 ítems (idx 1..8).
- **X2 — conteos:** T1..T8 = **19, 84, 156, 12, 36, 56, 24, 28** ; **TOTAL = 415**.
- **X3 — colisiones:** 0 grupos `(tabla_idx,dims,fecha)` duplicados.
- **X4 — modos:** T2/T3/T4 → 12 meses `2024-01-31..2024-12-31` (fecha no NULL);
  T1/T5/T6/T7/T8 → todas `fecha IS NULL`.
- **X5 — spot-checks (2024-10-04):**
  - T3 `producto='Crudo'`,`empresa='Hocol'`,`2024-01-31` → `17205.79`.
  - T5 `dims->>'fila'='CRUDO (ECP)'`,`dims->>'columna'='1Q'` → `484590.863331`.
  - T1 `dims->>'fila'='Total general'`,`dims->>'columna'='Programa mes'` → `619674.519676`.
- **X6 — idempotencia:** re-ingerir → mismos conteos.
- **X7 — no-breakage:** las 9 hojas modeladas previas + COMENTARIOS intactas; `uv run pytest -q` verde.

```sql
-- X2 conteos
SELECT tabla_idx, count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='CALCULO DE TRIMESTRE' GROUP BY tabla_idx ORDER BY tabla_idx;
-- X3 colisiones (0 filas)
SELECT tabla_idx,dims,fecha,count(*) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='CALCULO DE TRIMESTRE'
 GROUP BY tabla_idx,dims,fecha HAVING count(*)>1;
-- X4 modos (idx con fecha no nula deben ser solo 2,3,4)
SELECT tabla_idx, count(*) FILTER (WHERE fecha IS NULL) nul, count(*) FILTER (WHERE fecha IS NOT NULL) fec
 FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='CALCULO DE TRIMESTRE' GROUP BY tabla_idx ORDER BY tabla_idx;
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. Ingerir las **8 tablas** definidas; no fusionar ni omitir.
- **4.2** Filas/columnas fijas (verificadas estables en 3 archivos). Si un archivo futuro desplaza
  filas, **re-auditar**.
- **4.3** Bloque ECP/FILIALES en T5/T6 por umbral de fila (<62 / >=62), aplicado SOLO a etiquetas
  duplicadas: NO quitarlo (evita colisión y pérdida de filas).
- **4.4** Temporales con `fecha=mes` (excluir 'Promedio Año'); trimestrales y T1 con `fecha=NULL`.
- **4.5** No commit/push salvo que se pida. No tocar prod 139.
- **4.6** Si una validación falla, **DETENERSE y reportar el delta**.
