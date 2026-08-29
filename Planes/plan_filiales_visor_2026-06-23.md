# Plan ejecutable v2 (auditado) — "Producción filiales" → visor genérico (`core.fact_tabla_hoja`), estilo P50

> Modo **plan:** (executor sin contexto). Preserva las 3 tablas **diarias** (REAL/PROGRAMA/PROYECCIÓN)
> de la hoja "Producción filiales" en la tabla genérica `core.fact_tabla_hoja` y las muestra como
> ítems clicables + tabla ancha, **reutilizando el patrón ya construido para P50**. Plan **pequeño**:
> la infraestructura (tabla, loader genérico, endpoints, proxies, visor) ya existe.

---

## 0. Hallazgos de auditoría (verificados contra el código y los datos)

- **A1 — La hoja "Producción filiales" tiene 8 tablas con datos** (9 visuales; la 2ª "Desempeño" está
  vacía/fórmulas sin caché). Estructura **estable en los 3 archivos legibles** (mismas posiciones/marcadores).
- **A2 — Solo 3 son homogéneas y encajan en el modelo del visor** (`dims × fecha → valor`): **REAL**
  (f1), **PROGRAMA** (f13), **PROYECCIÓN** (f25) — empresa×producto × fechas diarias. Las matrices
  FILIALES/Desempeño tienen columnas **categóricas** (PPTO/POP/REAL/PROY), no fechas → **fuera de alcance**.
- **A3 — Reusar el parseo de `load_filiales`.** Esa función ya parsea esta hoja con `split_label`
  (`'Hocol (crudo)'→('Hocol','crudo')`), `norm_emp` (EAI→America) y `norm_prod` (CRUDO/GAS/BLANCOS), y
  `to_date` para las fechas. **Todos ya importados** en `services.py`. El extractor nuevo reusa esos
  helpers (mismo resultado, consistencia garantizada).
- **A4 — PROYECCIÓN NO está hoy en ninguna tabla Core.** `load_filiales` la **omite** (línea ~290:
  `if au.startswith("PROYEC"): tipo=None`). Solo REAL+PROGRAMA van a `fact_produccion_diaria`. ⇒ llevar
  PROYECCIÓN a `fact_tabla_hoja` es **información nueva** preservada (REAL/PROGRAMA serán copia para el
  visor; ver A7).
- **A5 — Las 2 tablas "simple" REAL/PROGRAMA (f56/f63) se auto-descartan**: sus etiquetas
  (`Hocol`/`America`/`Permian`, sin paréntesis) hacen que `split_label` devuelva `(None,None)` → se
  ignoran sin código extra. Solo se capturan las **detalladas** (f1/f13/f25). Verificado en seco.
- **A6 — Fechas DIARIAS**: el visor `renderTablaAncha` formatea hoy `MM/YY` (pensado para P50 mensual);
  con fechas diarias colapsaría todos los días del mes en "12/23". **Corrección**: formateador que
  detecta granularidad (mensual→`MM/YY`, diaria→`DD/MM`). Único cambio de front necesario.
- **A7 — Duplicación aceptada**: REAL/PROGRAMA quedarán también en `fact_tabla_hoja` (además de
  `fact_produccion_diaria`). Es intencional: `fact_produccion_diaria` es la fuente analítica;
  `fact_tabla_hoja` es la copia para el **visor** (UX consistente con P50). No es fuente de verdad.
- **A8 — Conteos esperados (simulación en seco del extractor):**
  | Archivo | Tabla 1 (REAL) | Tabla 2 (PROGRAMA) | Tabla 3 (PROYECCIÓN) |
  |---|---|---|---|
  | 20231231 (STD-2023, reporte 2) | **217** | **217** | **217** |
  | 20241004 (NEW-2024, reporte 1) | **28** | **217** | **217** |
  (7 filas empresa×producto × nº de días con dato; NEW-2024 REAL solo trae 4 días de actuals.)

### 0.b Verificaciones load-bearing del v2 (probadas en seco, no de memoria)
- **B1 — Spot-check VERIFICADO + valor exacto:** REAL Hocol·CRUDO 2023-12-01 = **17910.67** (≈17.911,
  coincide con el Excel). X3 ajustado a ese valor.
- **B2 — Sin contaminación de matrices/subtotales VERIFICADO:** las dims distintas son exactamente
  `{America,Hocol,Permian} × {CRUDO,GAS,BLANCOS}` (7 combos) y los labels solo las 3 tablas. `split_label`
  descarta solo (sin código extra) las filas FILIALES/HOCOL/TOTAL de las matrices y las tablas "simple".
- **B3 — Eje de fechas = ventana móvil, NO mes calendario.** Las fechas de REAL en STD-2023 son
  **2023-11-30 → 2023-12-30** (incluye el último día del mes anterior, falta 12-31). Es una característica
  real de la hoja, no un bug. ⇒ el formateador **DD/MM** del §4.3 lo muestra bien (30/11, 01/12, …); X5
  corregido al rango real.
- **B4 — Anclaje del front VERIFICADO:** `chat.js` línea 437 `const fmtMes = (iso) => {...}` coincide
  exacto con el reemplazo de §4.3.
- **B5 — Re-ingesta NEW-2024 es LENTA** (re-hace 314k filas de `fact_produccion_mes_ecp`, varios minutos).
  ⇒ se hace **OPCIONAL**: STD-2023 (rápido, datos completos 217/217/217) ya valida las 3 tablas. X2 queda
  opcional. (Evita que el executor se cuelgue en una ingesta larga.)

---

## 1. Objetivo

1. Agregar el extractor `_filiales_extract(ws)` y **una línea** en el registro `HOJAS_MODELADAS` de
   `services.py` → las 3 tablas diarias de "Producción filiales" se ingieren a `core.fact_tabla_hoja`.
2. Ajustar el formateador de fechas del visor (`renderTablaAncha`) para fechas diarias.
3. Resultado: bajo la hoja "Producción filiales" aparecen **3 ítems clicables** (Tabla 1/2/3) que abren
   la tabla ancha (empresa·producto × días) en el panel derecho — igual que P50.

**Sin** cambios de DDL, endpoints, proxies ni loader genérico (todo reutilizado).

## 2. Prerequisitos (si falla, DETENERSE y reportar)

- **P1** — Existe `…\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py` con: `_p50_grid`,
  `_p50_contig_months`, `_p50_extract`, `HOJAS_MODELADAS`, `load_tablas_hoja` (patrón P50 ya aplicado), y
  los imports `from app.features.ingesta.transforms import (... norm_emp, norm_prod, split_label)` +
  `from app.shared.utils import NOISE, s, num, to_date`.
- **P2** — Existe `core.fact_tabla_hoja` en la BD 139 (creada por el plan del visor). Endpoints
  `/tablas` y `/tablas/datos` activos en INGESTA :8000; proxies `/api/tablas-hoja[/datos]` en ProdIA.
- **P3** — `static\js\chat.js` tiene `window.renderTablaAncha` y `window.verTablaHoja`.
- **P4** — BD 139: `daily_report_prod`, user `postgres`, pass `y~87z0?>Ri6w` (PowerShell: `$env:PGPASSWORD`).
  Reportes existentes: 1=NEW-2024, 2=STD-2023.
- **P5** — Backends arriba; archivos `…\data\20231231 Reportes Diario de Producción.xlsm` y
  `…\data\20241004_Reporte New Diario de Producción.xlsm` presentes.

## 3. Inventario de archivos

| Archivo | Acción |
|---|---|
| `…\backend\app\features\ingesta\services.py` | **MODIFICAR**: agregar `_filiales_extract` + 1 línea en `HOJAS_MODELADAS`. |
| `…\static\js\chat.js` | **MODIFICAR**: formateador de fecha de `renderTablaAncha` (mensual vs diaria). |

**NO se toca:** DDL, `load_tablas_hoja`, endpoints, proxies, `load_filiales` ni los demás facts.

## 4. Especificación (código completo)

### 4.1 `services.py` — extractor nuevo (pegar junto a `_p50_extract`, antes de `HOJAS_MODELADAS`)

**NO agregar imports** (`s`, `num`, `to_date`, `split_label`, `norm_emp`, `norm_prod` ya están).

```python
def _filiales_extract(ws):
    """Extractor de 'Producción filiales': 3 tablas DIARIAS (REAL/PROGRAMA/PROYECCIÓN),
    empresa×producto × fecha. Reusa el parseo de load_filiales (split_label/norm_emp/norm_prod/to_date).
    Las tablas 'simple' (etiquetas sin paréntesis) y los subtotales 'Total ...' se descartan solos.
    Contrato genérico: [{tabla_idx, tabla_label, dims, fecha, valor}]."""
    rows = []
    seccion = None      # (idx, label) de la sección diaria en curso
    dates = []
    for row in ws.iter_rows(values_only=True):
        a = s(row[0]) if row else None
        if a is None:
            continue
        au = a.upper()
        if au == "REAL":
            seccion, dates = (1, "Tabla 1 (REAL)"), []; continue
        if au == "PROGRAMA":
            seccion, dates = (2, "Tabla 2 (PROGRAMA)"), []; continue
        if au.startswith("PROYEC"):
            seccion, dates = (3, "Tabla 3 (PROYECCIÓN)"), []; continue
        if au == "EMPRESA":
            dates = [to_date(v) for v in row[1:]]; continue
        if seccion is None or au.startswith("TOTAL"):
            continue
        emp_raw, prod_raw = split_label(a)
        empresa, producto = norm_emp(emp_raw), norm_prod(prod_raw)
        if not (empresa and producto):
            continue  # etiquetas sin 'Empresa (producto)' (tablas simple) -> ignorar
        idx, label = seccion
        dims = {"empresa": empresa, "producto": producto}
        for j, val in enumerate(row[1:]):
            f = dates[j] if j < len(dates) else None
            v = num(val)
            if f is None or v is None:
                continue
            rows.append({"tabla_idx": idx, "tabla_label": label, "dims": dims, "fecha": f, "valor": v})
    return rows
```

### 4.2 `services.py` — registrar la hoja (agregar la 2ª línea a `HOJAS_MODELADAS`)

```python
HOJAS_MODELADAS = [
    # ... (entrada P50 existente, NO modificar) ...
    (re.compile(r"(?i)^P50 Quemado \d{4} ECP y Fili"), _p50_extract),
    # Producción filiales: 3 tablas diarias REAL/PROGRAMA/PROYECCIÓN (nombre 19 chars, sin truncar)
    (re.compile(r"(?i)^Producci[oó]n filiales"), _filiales_extract),
]
```

### 4.3 `static\js\chat.js` — formateador de fecha sensible a granularidad

En `window.renderTablaAncha`, **reemplazar** la línea del formateador mensual:

```javascript
  const fmtMes = (iso) => { const [y, m] = iso.split("-"); return `${m}/${y.slice(2)}`; };
```

por un formateador que detecta mensual vs diaria:

```javascript
  const _isoMeses = (data.meses || []);
  const _mensual = new Set(_isoMeses.map((m) => m.slice(0, 7))).size === _isoMeses.length;
  const fmtMes = (iso) => {
    const [y, m, d] = iso.split("-");
    return _mensual ? `${m}/${y.slice(2)}` : `${d}/${m}`;   // mensual: MM/YY ; diaria: DD/MM
  };
```

(El resto de `renderTablaAncha` no cambia; sigue usando `fmtMes` para los encabezados de columna.)

## 5. Orden de ejecución

1. **Auditar** `services.py`: confirmar `_p50_grid`/`_p50_contig_months`/`HOJAS_MODELADAS`/`load_tablas_hoja`
   y los imports de §P1. Verificar Prerequisitos; si P1/P2 fallan, DETENERSE.
2. Aplicar **§4.1** (extractor), **§4.2** (registro), **§4.3** (front).
3. Reiniciar INGESTA :8000 (si no tiene `--reload`) y recargar el front (Ctrl+F5 al validar X6).
4. Re-ingerir por CLI para poblar `fact_tabla_hoja` con filiales:
   ```powershell
   cd "c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend"
   # OBLIGATORIO (rápido, ~30s, datos completos):
   uv run python -m app.cli archivo "..\data\20231231 Reportes Diario de Producción.xlsm"   # reporte 2 (STD-2023)
   # OPCIONAL (LENTO, varios minutos por el mes de 314k filas; solo confirma el caso de días parciales):
   # uv run python -m app.cli archivo "..\data\20241004_Reporte New Diario de Producción.xlsm" # reporte 1 (NEW-2024)
   ```
5. Validaciones **X1, X3, X4, X5** (y X6 manual). **X2 es opcional** (requiere la re-ingesta lenta de NEW-2024).

## 6. Validaciones (comando → esperado; reportar REAL vs esperado). `$env:PGPASSWORD='y~87z0?>Ri6w'`

- **X1 — Las 3 tablas diarias en `fact_tabla_hoja` (STD-2023, reporte 2):**
  ```sql
  SELECT tabla_idx, tabla_label, count(*) FROM core.fact_tabla_hoja
  WHERE reporte_id=2 AND hoja='Producción filiales' GROUP BY tabla_idx, tabla_label ORDER BY tabla_idx;
  ```
  Esperado: `1 | Tabla 1 (REAL) | 217`, `2 | Tabla 2 (PROGRAMA) | 217`, `3 | Tabla 3 (PROYECCIÓN) | 217`.
- **X2 — (OPCIONAL, requiere re-ingesta lenta de NEW-2024, reporte 1):** misma consulta con
  `reporte_id=1` → `217 / 217` para PROGRAMA/PROYECCIÓN y **28** para REAL (solo 4 días de actuals).
  Omitir si no se re-ingirió NEW-2024.
- **X3 — Spot-check (valor exacto verificado):**
  ```sql
  SELECT valor FROM core.fact_tabla_hoja WHERE reporte_id=2 AND hoja='Producción filiales'
   AND tabla_idx=1 AND dims->>'empresa'='Hocol' AND dims->>'producto'='CRUDO' AND fecha='2023-12-01';
  ```
  Esperado ≈ **17910.67** (= 17.911 redondeado; REAL Hocol crudo, 1-dic-2023). Reportar el valor real.
- **X4 — dims correctas (sin subtotales, sin tablas simple):**
  ```sql
  SELECT DISTINCT dims->>'empresa' e, dims->>'producto' p FROM core.fact_tabla_hoja
   WHERE reporte_id=2 AND hoja='Producción filiales' ORDER BY 1,2;
  ```
  Esperado: empresas ∈ {America, Hocol, Permian}; productos ∈ {BLANCOS, CRUDO, GAS}; **ningún** valor con
  paréntesis ni "Total".
- **X5 — Endpoint datos ancho (proxy ProdIA):**
  `curl -s "http://localhost:8020/api/tablas-hoja/datos?reporte_id=2&hoja=Producci%C3%B3n%20filiales&tabla_idx=3"`
  → JSON con `dimensiones=["empresa","producto"]`, `meses` = **31 fechas diarias en ventana
  2023-11-30 → 2023-12-30** (incluye el último día del mes anterior; ver B3) y `filas` (7).
- **X6 (manual, navegador):** http://localhost:8020 → "Análisis avanzado…" → **Ctrl+F5** → subir
  `20231231 Reportes Diario de Producción.xlsm` → bajo **Producción filiales** ver **📊 Para análisis
  (3 tablas):** con **Tabla 1 (REAL) / Tabla 2 (PROGRAMA) / Tabla 3 (PROYECCIÓN)** clicables → clic abre
  la tabla ancha (empresa·producto × días, columnas en formato **DD/MM**, no MM/YY). (También aparecerá
  la hoja P50 con sus 2 tablas — ambas coexisten.)

## 7. Reglas no negociables

1. **Reusar el parseo de filiales**: `split_label` + `norm_emp` + `norm_prod` + `to_date` (no reimplementar).
   No tocar `load_filiales`.
2. **Solo las 3 tablas diarias** (REAL/PROGRAMA/PROYECCIÓN, primeras ocurrencias). Las matrices
   FILIALES/Desempeño y las tablas "simple" quedan **fuera** (se descartan solas vía `split_label`).
3. **No agregar imports** en `services.py`. No cambiar DDL, `load_tablas_hoja`, endpoints ni proxies.
4. **Front**: solo cambiar el formateador `fmtMes` de `renderTablaAncha`; no romper el caso mensual (P50).
5. **Idempotencia** la maneja `load_tablas_hoja` (DELETE por reporte_id+hoja + dedup). No duplicar lógica.
6. Si la auditoría revela nombres/firmas distintos, **adaptar a los reales** (no inventar).

## 8. Fuera de alcance (siguientes iteraciones)

- Tablas matriciales FILIALES (mes/semana) y Desempeño Filiales (P50/POP/REAL/PROY): forma de columnas
  **categóricas**, no `dims × fecha`. Requerirían generalizar el eje "fecha" a "columna" en el modelo y el
  visor → otro plan.
- Tablas "simple" REAL/PROGRAMA (agregadas por empresa) y el gráfico de la hoja.
- Orden de columnas de dimensión tipo Excel (D5, heredado del visor).
