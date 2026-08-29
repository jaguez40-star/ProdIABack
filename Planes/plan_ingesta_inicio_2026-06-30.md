# Plan ejecutable (v2) — Modelado de la hoja "INICIO" (tabla REAL PROMEDIO MES YTD Filiales) → `core.fact_tabla_hoja`

> **Cobertura: Tablas: entrada 1 → salida 1** (solo la tabla que el usuario pidió; el resto de INICIO
> son parámetros/lookups de setup, fuera de alcance justificado).
> **Coexistencia (v2):** esta tabla YA la modela `load_promedios`→`fact_promedio_validado` (70 filas,
> excluye Total); este plan la añade a `fact_tabla_hoja` (80 filas, incluye Total) para el visor
> genérico. Targets distintos, sin conflicto (ver §0.g).
> **Modo:** Planner (este archivo NO edita código; lo aplica el Executor).
> **Fecha:** 2026-06-30 · **Autor:** Claude · **Hoja:** `INICIO`
> **Único archivo a tocar:** `backend/app/features/ingesta/services.py`
> **Migración:** NINGUNA. **Frontend / api.py:** SIN cambios (modo "fechas" del visor, ya probado).

---

## 0. Auditoría (datos reales, 3 archivos)

La hoja **INICIO** es de **configuración/setup** ("LLENAR SOLO LOS CAMPOS EN NARANJA"). Solo se ingiere
**1 tabla**, la que el usuario definió: **"REAL PROMEDIO MES (YTD) Filiales"** (su título dice *"unico
dato que se incluye a mano"*). El resto (parámetros escalares A2-C30, lookups AA-AC) NO se ingiere
(config/referencia, no datos de producción).

**Estructura de la tabla:** producto(A) × empresa(B) × mes (cols C…), temporal `fecha=mes`. 8 filas:
Crudo/Gas/Blancos × Hocol/EAI/Permian + `Total`. Header con 12 meses (C-N); valores **YTD** (solo hasta
el mes de corte).

### 🔴 Hallazgo crítico — la tabla se DESPLAZA entre archivos
| Archivo | Título | Header | Datos | Meses con dato |
|---------|:------:|:------:|:-----:|:--------------:|
| 2024-10-04 (NEW) | r34 | r35 | **r36-43** | 10 (Ene-Oct, YTD) → 80 celdas |
| 2024-02-11 (STD) | r38 | r39 | **r40-47** | 2 (Ene-Feb, YTD) → 16 celdas |
| 2023-12-31 (STD) | r38 | r39 | r40-47 | 12 (año completo) → 96 celdas |

⇒ **Filas fijas (34-43) romperían en STD.** Por eso el extractor **ancla por el título** (busca
`"REAL PROMEDIO MES (YTD) Filiales"` en col A) y detecta **meses dinámicamente** (header + corte YTD).
Mismo patrón que `_p50_extract` para localizar su tabla 'filiales'. Verificado: captura la tabla
correcta en los 3 archivos.

### No-breakage
- `fecha=mes` (todas las filas con fecha real) → visor en modo "fechas" (ya probado). Sin `None.isoformat()`.
- Cada `(producto,empresa)` es único → sin colisiones (incl. la fila `Total`, con empresa ausente).
- 11ª hoja con el MISMO pipeline ⇒ 0 riesgo de regresión. pytest no aserta nº de hojas modeladas.

### 0.g — Flujo profesional v2: coexistencia con loaders pre-existentes (hallazgo clave)
🔴 **Esta tabla YA se ingiere** por código pre-existente (services.py):
- `load_promedios` (línea ~352) → `core.fact_promedio_validado`: misma sección "REAL PROMEDIO MES
  (YTD)", **70 filas** (ancla por el header `Producto/Empresa`; **EXCLUYE la fila `Total`**, línea 364;
  exige lookup válido de producto/empresa). Documentado en CLAUDE.md §5/§6.
- `update_config_inicio` (línea ~375) → `core.config_reporte`: lee los parámetros escalares de INICIO
  (fecha_corte, mes_inicio/fin, version_semana, anio_inicio, dias_anio). **Mi extractor NO toca esto.**

**Resolución — añadir a `fact_tabla_hoja` igualmente (coexistencia), por:**
- **Target distinto**: `load_promedios`→`fact_promedio_validado` (KPIs); este plan→`fact_tabla_hoja`
  (visor genérico "Para análisis"). El `DELETE` de `load_tablas_hoja` está acotado a
  `(reporte_id, hoja)` sobre `fact_tabla_hoja` → **no toca `fact_promedio_validado`. Sin conflicto.**
- **Mismo patrón ya aceptado** que POP (`load_pop`→`fact_plan_mensual` + extractor→`fact_tabla_hoja`).
- **Solo así la tabla es visible** en el visor genérico (lee `fact_tabla_hoja`, no `fact_promedio_validado`).
- ⚠️ **Diferencia de conteo intencional**: este plan = **80** (incluye `Total`, por D3 "preservar todo" y
  porque el visor se beneficia del total); `load_promedios` = 70 (excluye Total). NO es un error.
- **Doble evento de progreso** para hoja "INICIO" (uno por `fact_promedio_validado`, otro por
  `fact_tabla_hoja` con `tablas` → clicable). Igual que POP; cosmético, sin impacto funcional.

---

## 1. Cambio de código (aplicar EXACTAMENTE)

### 1.1 — Nueva función `_inicio_extract` (insertar después de `_calculo_trimestre_extract`, antes del
bloque `# === Registro de hojas modeladas: ...`)

```python
def _inicio_extract(ws):
    """Extractor de la hoja 'INICIO' → 1 tabla: 'REAL PROMEDIO MES (YTD) Filiales' (único dato a mano).
    Temporal mensual (fecha=mes, YTD), dims producto×empresa. Se ANCLA POR TÍTULO (no por filas fijas)
    porque la tabla se desplaza entre archivos NEW (~fila 34) y STD (~fila 38). Meses dinámicos por el
    header (corta en 'Promedio Año'/no-fecha); valores YTD hasta el corte. El resto de INICIO
    (parámetros/lookups de setup) NO se ingiere. Contrato extendido {"rows":..., "tablas":DECLARED}."""
    grid, maxr = _p50_grid(ws)
    DECLARED = [(1, "REAL PROMEDIO MES (YTD) Filiales")]
    trow = None
    for r in range(1, maxr + 1):
        v = s(grid.get((r, 1)))
        if v and v.upper().startswith("REAL PROMEDIO MES (YTD) FILIALES"):
            trow = r
            break
    if trow is None:
        return {"rows": [], "tablas": DECLARED}
    hdr = trow + 1
    months = _p50_contig_months(grid, hdr, 3)          # meses desde col C (3); corta en no-fecha
    rows = []
    r = hdr + 1
    while r <= maxr and s(grid.get((r, 1))) is not None:
        a = s(grid.get((r, 1)))
        dims = {"producto": a}
        b = s(grid.get((r, 2)))
        if b is not None:
            dims["empresa"] = b
        for c, d in months:
            v = num(grid.get((r, c)))
            if v is not None:
                rows.append({"tabla_idx": 1, "tabla_label": "REAL PROMEDIO MES (YTD) Filiales",
                             "dims": dims, "fecha": d, "valor": v})
        r += 1
    return {"rows": rows, "tablas": DECLARED}
```

### 1.2 — Registrar en `HOJAS_MODELADAS` (añadir UNA línea después de la de CALCULO DE TRIMESTRE)

```python
    # INICIO: hoja de setup; se ingiere SOLO la tabla 'REAL PROMEDIO MES (YTD) Filiales' (único dato a
    # mano), anclada por título (se desplaza entre NEW/STD). producto×empresa×mes, YTD. Dato redundante.
    (re.compile(r"(?i)^INICIO$"), _inicio_extract),
```

**NO** agregar imports (`s`, `num`, `_p50_grid`, `_p50_contig_months` ya existen).
**NO** tocar DDL, migraciones, `load_tablas_hoja`, `api.py` ni el frontend.

---

## 2. Pre-condiciones (auditar antes de aplicar)
1. `_calculo_trimestre_extract` existe y `HOJAS_MODELADAS` está justo después.
2. `s`, `num`, `_p50_grid`, `_p50_contig_months` existen en services.py.
3. Nombre exacto de la hoja: `INICIO` (regex `^INICIO$`).
Si algo difiere, **DETENERSE y reportar**.

---

## 3. Validaciones (archivo canónico `2024-10-04`; tomar `<rid>` de la ingesta)

- **X1 — 1 tabla:** `GET /tablas?...&hoja=INICIO` → 1 ítem (idx 1, "REAL PROMEDIO MES (YTD) Filiales").
- **X2 — conteo:** **80 filas** (8 filas-dato × 10 meses YTD Ene-Oct).
- **X3 — filas distintas:** `count(DISTINCT dims)` = **8** (Crudo/Gas/Blancos × Hocol/EAI/Permian + Total).
- **X4 — meses:** **10** fechas distintas, `2024-01-31 … 2024-10-31` (YTD); 0 filas con `fecha IS NULL`.
- **X5 — spot-checks (2024-10-04):**
  - `producto='Crudo'`,`empresa='Hocol'`,`2024-01-31` → `17205.79`.
  - `producto='Total'`,`2024-01-31` (empresa NULL) → `134281.679162…`.
- **X6 — idempotencia:** re-ingerir → mismos conteos.
- **X7 — no-breakage:** las 10 hojas modeladas previas + COMENTARIOS intactas; `uv run pytest -q` verde.
- **X8 — pipeline pre-existente intacto:** `core.fact_promedio_validado` sigue con **70 filas** para `<rid>`
  (`load_promedios` no se ve afectado por el nuevo extractor; targets distintos).

```sql
-- X2/X3
SELECT count(*), count(DISTINCT dims) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='INICIO';
-- X4 (10 meses, 0 nulos)
SELECT count(DISTINCT fecha), count(*) FILTER (WHERE fecha IS NULL) FROM core.fact_tabla_hoja
 WHERE reporte_id=:rid AND hoja='INICIO';
-- X5
SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='INICIO'
   AND fecha='2024-01-31' AND dims->>'producto'='Crudo' AND dims->>'empresa'='Hocol';   -- 17205.79
SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=:rid AND hoja='INICIO'
   AND fecha='2024-01-31' AND dims->>'producto'='Total' AND dims->>'empresa' IS NULL;    -- 134281.68
-- X8 pipeline pre-existente intacto (esperado: 70)
SELECT count(*) FROM core.fact_promedio_validado WHERE reporte_id=:rid;
```

---

## 4. Reglas no negociables
- **4.1** Aplicar §1.1 y §1.2 TAL CUAL. Ingerir SOLO esa tabla; el resto de INICIO NO se toca.
- **4.2** **Anclar por título** (no por filas fijas) — la tabla se desplaza entre NEW/STD. Si no se
  encuentra el título, devolver 0 filas (no inventar posición).
- **4.3** Meses dinámicos por `_p50_contig_months` (header); `fecha=mes` real (nunca NULL).
- **4.4** No commit/push salvo que se pida. No tocar prod 139.
- **4.5** Si una validación falla, **DETENERSE y reportar el delta**.

---

## 5. Fuera de alcance
- Parámetros escalares (A2-C30: fechas de corte, rangos, Versión Semana, Días del año…) y lookups
  (AA-AC: nombres/números de mes): son setup/referencia, no datos de producción.
