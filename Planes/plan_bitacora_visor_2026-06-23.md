# Plan ejecutable — Visor de la hoja `(Bitacora)` (3 tablas) · 2026-06-23 · **v2 (auditado)**

> **Cobertura: `Tablas: entrada 3 (+2 estructuras menores) → salida 3`** — REAL, PROGRAMA, PROYECCIÓN.
> Las 2 estructuras menores (columna agregada mensual a la derecha de las fechas; etiqueta vacía
> `GAS COMERCIAL`) se omiten **por decisión aprobada del usuario**.
> **Requisito duro del usuario: SIEMPRE 3 tablas clicables en el front**, aunque PROGRAMA venga vacía.

Modo: **plan para Executor** (sin contexto previo). Ejecutar al pie de la letra. Rutas absolutas.

---

## 0.b Hallazgos de auditoría (v2 — verificados contra el código real)

- **H1.** El árbol de tablas del front es **event-driven**: se arma desde `ev.tablas` del evento de
  ingesta (`chat.js` líneas 378-394) y el `forEach` **NO filtra `filas==0`**. ⟹ declarar las 3 tablas en
  el resumen de `load_tablas_hoja` produce **3 ítems clicables**, aunque PROGRAMA tenga 0 filas. El
  enfoque del plan es válido.
- **H2 (corrección de validación).** El endpoint REST `GET /tablas` (listar) es **DB-driven** (hace
  `GROUP BY` sobre `fact_tabla_hoja`) y **no lo consume nadie** en el front (`grep` sin coincidencias de
  `/api/tablas-hoja` salvo `/datos`). Para una tabla declarada-vacía devolvería 2, no 3. **No usar
  `/tablas` para validar "3 en el front"** (lo hace la X7 visual y la X6 por resumen). Divergencia
  conocida e **inocua** (endpoint sin uso); no se corrige.
- **H3.** PROGRAMA vacía se mostrará como `📄 Tabla 2 (PROGRAMA) · 0 filas` (cosmético, esperado). Al
  hacer clic abre el aviso "Sin datos…" (cambios 4.4 + 4.5).
- **H4.** Anclas confirmadas en código real: `load_tablas_hoja` línea **599** (`filas = extractor(...)`)
  y línea **618** (construcción de `tablas`); `/datos` líneas **29-30** (el `raise 404`). El contrato
  dict es **retrocompatible**: P50/filiales devuelven **listas** → `declared=None` → comportamiento
  idéntico. **Sin DDL** (la columna `fecha` ya es nullable y `(Bitacora)` siempre trae fecha). Sin
  regresión en el modo matriz ni en `load_filiales`.

---

## 1. Contexto

Proyecto INGESTA (`Rep_Prod`): FastAPI :8000 + PostgreSQL remoto + front Flask ProdIA :8020.
Ya existe un **patrón genérico "hoja por hoja"** que expone múltiples tablas de una hoja Excel:

- Tabla larga `core.fact_tabla_hoja (id, reporte_id, hoja, tabla_idx, tabla_label, dims JSONB, fecha DATE NULL, valor NUMERIC)`.
- Registro `HOJAS_MODELADAS = [(regex_hoja, extractor)]` en `services.py`. Loader genérico `load_tablas_hoja()`.
- Casos ya implementados: `_p50_extract` (hoja "P50 Quemado …") y `_filiales_extract` (hoja "Producción filiales", 8 tablas, incl. modo matriz).
- Endpoints feature `tablas`: `GET /tablas` (lista) y `GET /tablas/datos` (pivote ancho). Proxies ProdIA: `/api/tablas-hoja` y `/api/tablas-hoja/datos`.
- Front (`chat.js`): el árbol de la ingesta arma ítems clicables desde el array `tablas` del evento de ingesta; al hacer clic, `verTablaHoja()` → `/api/tablas-hoja/datos` → `renderTablaAncha()` pinta la tabla ancha.

Esta tarea agrega la hoja `(Bitacora)`. **Auditoría previa ya realizada** (no repetir; usar sus hallazgos):

- La hoja `(Bitacora)` tiene **3 bloques** con ancla en col A: `***REAL***` (fila 1), `***PROGRAMA***` (fila 29), `***PROYECCIÓN***` (fila 58).
- Cada bloque: fila de encabezado con col A=`TIPOPRODUCTO`, col B=`VICE`, y **31 columnas de fecha** (2023-12-01 → 2023-12-31) desde la col C. A la derecha de las fechas hay **1 columna agregada** rotulada `REAL` (total/promedio mensual) → se ignora.
- Filas de datos: `TIPOPRODUCTO` (CRUDO/GAS/BLANCOS) en col A **disperso** (solo en la 1ª fila de cada grupo) × `VICE` (VRC/VRO/VAO/VFS/VPI/VEX) en col B.
- **Subtotales a excluir**: filas con **VICE vacío** (`Total CRUDO`, `Total GAS`, `Total BLANCOS`, `Total general`). Hay una celda col A rotulada `TOTAL` en filas VEX que SÍ son datos → distinguir por **VICE presente**, no por col A.
- `PROGRAMA` viene **`#N/A` en archivos STD** (sin caché de programa) y **con datos en archivos NEW**. `#N/A`/blank se descartan solos vía `num()`.
- **Layout estable** verificado en 3 archivos del corpus (anclas idénticas 1/29/58).

---

## 2. Objetivo

1. Ingerir las **3 tablas** de `(Bitacora)` a `core.fact_tabla_hoja` con `dims={tipoproducto, vice}`, `fecha`, `valor`.
2. Que el front muestre **SIEMPRE 3 ítems clicables** bajo `(Bitacora)`, aunque PROGRAMA tenga 0 filas (archivos STD). Al hacer clic en una tabla vacía, mostrar un aviso limpio ("sin datos en este archivo"), no un error.
3. No tocar DDL, ni los extractores existentes (P50/filiales), ni `load_filiales`, ni el modo matriz.

---

## 3. Prerequisitos (verificar antes de empezar; si falla P1–P3, DETENER y reportar)

- **P1.** Backend INGESTA responde: `curl -s http://127.0.0.1:8000/health` → `{"status":"ok"}`.
- **P2.** En `c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\ingesta\services.py` existen: `HOJAS_MODELADAS`, `load_tablas_hoja`, `_p50_extract`, `_filiales_extract`, y los imports `from app.shared.utils import NOISE, s, num, to_date`.
- **P3.** `core.fact_tabla_hoja.fecha` es **nullable** (migración 004 ya aplicada). Comando de verificación en §6 (X0).
- **P4.** Archivos de prueba disponibles (al menos uno):
  - NEW (PROGRAMA con datos): `c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20241004_Reporte New Diario de Producción.xlsm`
  - STD (PROGRAMA #N/A): `c:\APLICACIONES\ProdIA\12112025_prodIA\INGESTA\Rep_Prod\data\20231231 Reportes Diario de Producción.xlsm`

**Entorno:** Windows 11, PowerShell. La contraseña de la BD contiene `>` → usar SIEMPRE `$env:PGPASSWORD`,
nunca inline. `psql` NO está local → validar con psycopg vía
`uv run --with "psycopg[binary]" python -c "..."`. BD: host `10.100.26.139`, puerto `5432`,
db `daily_report_prod`, user `postgres`, pass `y~87z0?>Ri6w`.

⚠️ **El backend con `uvicorn --reload` NO recarga de forma fiable los cambios en `services.py`.**
Tras editar, **reiniciar el proceso uvicorn** (matar por puerto :8000 y relanzar, idealmente SIN `--reload`).
Síntoma de no-recarga: el extractor da filas en dry-run pero `fact_tabla_hoja` queda en 0 para la hoja.

---

## 4. Inventario de archivos a modificar (4 archivos, sin DDL)

| Archivo | Cambio |
|---|---|
| `…\backend\app\features\ingesta\services.py` | (4.1) agregar `_bitacora_extract`; (4.2) 1 línea en `HOJAS_MODELADAS`; (4.3) `load_tablas_hoja` soporta tablas declaradas (0 filas incluidas) |
| `…\backend\app\features\tablas\api.py` | (4.4) `/datos`: si una tabla no tiene filas → devolver estructura vacía 200 (no 404) |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\static\js\chat.js` | (4.5) `renderTablaAncha`: si la tabla viene vacía → mensaje limpio |

**NO se toca:** DDL, `_p50_extract`, `_filiales_extract`, `load_filiales`, el modo matriz, los proxies de ProdIA (`routes/api.py` ya reenvía `/api/tablas-hoja*` tal cual).

---

## 5. Especificación (código de referencia — aplicar EXACTO)

### 4.1 — Nuevo extractor `_bitacora_extract` (en `services.py`)

Insertar **antes** de la definición de `HOJAS_MODELADAS`. No agrega imports nuevos.

```python
def _bitacora_extract(ws):
    """Extractor de la hoja '(Bitacora)' → 3 tablas TIPOPRODUCTO×VICE × fecha (Familia A, columnas=fechas).
    DECLARA siempre las 3 tablas (1 REAL, 2 PROGRAMA, 3 PROYECCIÓN) para que el front muestre 3 ítems
    aunque PROGRAMA venga #N/A (archivos STD → 0 filas). Reusa s/num/to_date. dims={tipoproducto,vice}.
    Excluye subtotales (filas con VICE vacío: 'Total CRUDO/GAS/BLANCOS', 'Total general') y la columna
    agregada mensual a la derecha de las fechas ('REAL' → to_date None). Layout estable en 3 archivos."""
    PRODUCTOS = {"CRUDO", "GAS", "BLANCOS"}
    VICES = {"VRC", "VRO", "VAO", "VFS", "VPI", "VEX"}
    DECLARED = [(1, "Tabla 1 (REAL)"), (2, "Tabla 2 (PROGRAMA)"), (3, "Tabla 3 (PROYECCIÓN)")]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    n = len(grid)
    rows = []

    def S(i, j):
        v = grid[i][j] if 0 <= i < n and 0 <= j < len(grid[i]) else None
        return s(v) or ""

    def block_of(label):
        u = label.upper()
        if "REAL" in u: return (1, "Tabla 1 (REAL)")
        if "PROGRAMA" in u: return (2, "Tabla 2 (PROGRAMA)")
        if "PROYEC" in u: return (3, "Tabla 3 (PROYECCIÓN)")
        return None

    i = 0
    while i < n:
        a = S(i, 0)
        if not a.startswith("***"):
            i += 1; continue
        blk = block_of(a)
        if blk is None:
            i += 1; continue
        idx, label = blk
        # encabezado de fechas: la fila cuyo col A == 'TIPOPRODUCTO'
        j = i + 1
        while j < n and S(j, 0).upper() != "TIPOPRODUCTO" and not S(j, 0).startswith("***"):
            j += 1
        if j >= n or S(j, 0).upper() != "TIPOPRODUCTO":
            i += 1; continue
        dates = [to_date(v) for v in grid[j][2:]]      # desde col C; la col 'REAL' (agregado) → None
        producto = None
        k = j + 1
        while k < n and not S(k, 0).startswith("***"):
            ca = S(k, 0).upper()
            if ca in PRODUCTOS:
                producto = ca                          # forward-fill del producto (col A dispersa)
            vice = S(k, 1).upper()
            if vice in VICES and producto:             # fila de datos sii hay VICE (excluye subtotales)
                for jj, val in enumerate(grid[k][2:]):
                    f = dates[jj] if jj < len(dates) else None
                    v = num(val)
                    if f is None or v is None:         # fecha inválida / #N/A / blank → se descarta
                        continue
                    rows.append({"tabla_idx": idx, "tabla_label": label,
                                 "dims": {"tipoproducto": producto, "vice": vice},
                                 "fecha": f, "valor": v})
            k += 1
        i = k
    return {"rows": rows, "tablas": DECLARED}
```

### 4.2 — Registrar la hoja en `HOJAS_MODELADAS` (en `services.py`)

Agregar **una línea** al final de la lista `HOJAS_MODELADAS`, sin tocar las existentes:

```python
    # (Bitacora): 3 tablas diarias TIPOPRODUCTO×VICE (REAL/PROGRAMA/PROYECCIÓN). El nombre real es "(Bitacora)".
    (re.compile(r"(?i)^\(?\s*bit[aá]cora"), _bitacora_extract),
```

### 4.3 — `load_tablas_hoja`: soportar tablas declaradas (en `services.py`)

El extractor ahora puede devolver **un dict** `{"rows": [...], "tablas": [(idx,label),...]}` además de la
lista actual. Cuando declara tablas, el resumen del front incluye TODAS (incluso con 0 filas) → 3 ítems.
**Retrocompatible:** P50/filiales devuelven listas y siguen igual.

En `load_tablas_hoja` (def en línea **590**), buscar la línea **599**:

```python
        filas = extractor(wb[hoja])
```

y reemplazarla por:

```python
        res = extractor(wb[hoja])
        if isinstance(res, dict):                       # contrato extendido: filas + tablas declaradas
            filas = res.get("rows", [])
            declared = res.get("tablas")                # [(idx,label),...] o None
        else:
            filas, declared = res, None
```

Y más abajo (línea **618**), donde se construye `tablas` desde `cont`, buscar:

```python
        tablas = [{"tabla_idx": i, "tabla_label": l, "filas": n} for (i, l), n in sorted(cont.items())]
```

y reemplazarlo por:

```python
        if declared:                                    # incluir todas las declaradas (aunque 0 filas)
            tablas = [{"tabla_idx": i, "tabla_label": l, "filas": cont.get((i, l), 0)} for i, l in declared]
        else:
            tablas = [{"tabla_idx": i, "tabla_label": l, "filas": n} for (i, l), n in sorted(cont.items())]
```

(El resto de `load_tablas_hoja` —dedup, DELETE/INSERT, `total`— queda IGUAL.)

### 4.4 — Endpoint `/datos`: tabla vacía → 200 (en `tablas\api.py`)

Para que un ítem declarado-vacío (PROGRAMA en STD) no devuelva 404. Buscar:

```python
    if not rows:
        raise HTTPException(404, "sin datos para esa tabla")
```

y reemplazar por:

```python
    if not rows:
        return {"vacia": True, "dimensiones": [], "meses": [], "filas": []}
```

### 4.5 — `renderTablaAncha`: mensaje para tabla vacía (en `chat.js`)

Al inicio de `window.renderTablaAncha = function renderTablaAncha(area, data, titulo) {`, justo después de
abrir la función, insertar:

```javascript
  if (data.vacia || !(data.filas || []).length) {
    area.innerHTML = `<div class="p-3"><h6 class="fw-bold text-success mb-2">${titulo}</h6>
      <div class="text-muted">Sin datos para esta tabla en este archivo.</div></div>`;
    return;
  }
```

---

## 6. Orden de ejecución

1. **Auditar** (no asumir): confirmar Prerequisitos §3 (P1–P4) y X0 (fecha nullable). Si algo falla, DETENER.
2. Aplicar **4.1**, **4.2**, **4.3** en `services.py`.
3. Aplicar **4.4** en `tablas\api.py`.
4. Aplicar **4.5** en `chat.js`.
5. **Verificación de sintaxis** backend: `cd …\backend` → `uv run python -c "import ast; ast.parse(open('app/features/ingesta/services.py',encoding='utf-8').read()); ast.parse(open('app/features/tablas/api.py',encoding='utf-8').read()); print('OK')"`.
6. **Reiniciar el backend** (NO confiar en `--reload`): matar lo que escuche en :8000 y relanzar
   `uv run uvicorn app.main:app --port 8000` (desde `…\backend`). Esperar `GET /health` → 200.
7. **Re-ingerir por CLI** el archivo NEW (3 tablas con datos) y, opcionalmente, el STD (PROGRAMA vacío):
   `cd …\backend` →
   `uv run python -c "import sys; sys.path.insert(0,'.'); from pathlib import Path; from app.features.ingesta.services import ingerir_archivo; r=ingerir_archivo(Path(r'..\data\20241004_Reporte New Diario de Producción.xlsm')); print([(k,v) for k,v in r.filas_por_tabla.items() if 'Bitacora' in k or 'bitacora' in k.lower()])"`
   Capturar el `reporte_id` del log `ingesta.ok` para las validaciones.
8. Correr Validaciones §7 (X0–X7). Reportar tabla `Validación | Esperado | Obtenido | OK/FALLO`.

---

## 7. Validaciones (comando → esperado; reportar REAL vs esperado)

> En los comandos psycopg, sustituir `<REP_NEW>` por el `reporte_id` de la ingesta NEW del paso 7.
> Conexión psycopg: `host=10.100.26.139 port=5432 dbname=daily_report_prod user=postgres password=<env>`.

- **X0 — fecha nullable:**
  `select is_nullable from information_schema.columns where table_schema='core' and table_name='fact_tabla_hoja' and column_name='fecha'` → **YES**.

- **X1 — 3 tablas presentes (NEW):**
  `select tabla_idx, tabla_label, count(*) from core.fact_tabla_hoja where reporte_id=<REP_NEW> and hoja='(Bitacora)' group by 1,2 order by 1`
  → 3 filas: idx **1 (REAL)**, **2 (PROGRAMA)**, **3 (PROYECCIÓN)**, las tres con `count > 0` (archivo NEW).

> **OJO (corregido tras ejecución):** el NEW `20241004` tiene ventana de fechas **Oct-2024**, no Dic-2023
> (eso se extrapoló del archivo `_TEST`). Además cada bloque tiene **su propia ventana** (REAL=3 días Oct,
> PROGRAMA=Oct–Nov, PROYECCIÓN=Oct). Usar la **primera fecha real** del bloque para el spot: `2024-10-01`.

- **X2 — spot REAL:** CRUDO·VRC·2024-10-01 →
  `select valor from core.fact_tabla_hoja where reporte_id=<REP_NEW> and hoja='(Bitacora)' and tabla_idx=1 and dims->>'tipoproducto'='CRUDO' and dims->>'vice'='VRC' and fecha='2024-10-01'`
  → **69807.556** (±0.01).

- **X3 — spot PROGRAMA:** CRUDO·VRC·2024-10-01 → mismo query con `tabla_idx=2`
  → **70763.979** (±0.01). (Confirma que PROGRAMA del NEW sí trae datos.)

- **X4 — dims limpios:**
  `select distinct dims->>'tipoproducto' as p, dims->>'vice' as v from core.fact_tabla_hoja where reporte_id=<REP_NEW> and hoja='(Bitacora)' order by 1,2`
  → productos ⊆ {CRUDO, GAS, BLANCOS}; vices ⊆ {VRC, VRO, VAO, VFS, VPI, VEX}; **sin** 'Total'/'TOTAL'/'general'/vacíos.

- **X5 — endpoint datos (modo fechas):** (paréntesis URL-encoded `%28..%29`)
  `curl -s "http://127.0.0.1:8000/tablas/datos?reporte_id=<REP_NEW>&hoja=%28Bitacora%29&tabla_idx=1"`
  → JSON con `dimensiones=["tipoproducto","vice"]`, `meses` = 31 fechas ISO (2023-12-01…2023-12-31), `filas` no vacío. (Sin `modo`, o `modo`≠"matriz".)

> **OJO (corregido tras ejecución):** el supuesto "PROGRAMA siempre `#N/A` en STD" es **falso** para
> `20231231` (trae **844 filas** reales). El código es correcto igual (descarta `#N/A`, captura lo que
> haya). El caso PROGRAMA-100%-vacío no lo disparan estos archivos → el mecanismo "siempre 3 / vacía→200"
> queda como **red de seguridad**, verificable con un `tabla_idx` inexistente (X6c) → 200 + `vacia:true`.

- **X6 — comportamiento en STD (PROGRAMA) + declaración de 3.** El árbol del front se arma desde el
  **resumen** de `load_tablas_hoja` (H1), NO desde `GET /tablas` (H2). Por eso aquí se valida el resumen y
  la BD, no el `/tablas` REST.
  - **X6a (declara 3):** dry-run del extractor sobre el STD —
    `cd …\backend` →
    `uv run --with openpyxl python -c "from openpyxl import load_workbook; from app.features.ingesta.services import _bitacora_extract; r=_bitacora_extract(load_workbook(r'..\data\20231231 Reportes Diario de Producción.xlsm', read_only=True, data_only=True)['(Bitacora)']); print('tablas:', r['tablas']); print('filas:', len(r['rows']))"`
    → `tablas` con **3 entradas** (idx 1,2,3); `filas` > 0 (REAL+PROYECCIÓN; PROGRAMA aporta 0 por `#N/A`).
  - **X6b (datos en BD):** ingerir el STD (capturar `<REP_STD>`), luego —
    `select tabla_idx, count(*) from core.fact_tabla_hoja where reporte_id=<REP_STD> and hoja='(Bitacora)' group by 1 order by 1`
    → idx **1** y **3** con filas > 0; idx **2 ausente** (0 filas en BD; el front igual lo muestra por declaración H1).
  - **X6c (tabla vacía → 200, no 404):**
    `curl -s -o NUL -w "%{http_code}" "http://127.0.0.1:8000/tablas/datos?reporte_id=<REP_STD>&hoja=%28Bitacora%29&tabla_idx=2"`
    → **200**, y el cuerpo es `{"vacia": true, ...}`.

- **X7 — FRONT (manual, requisito duro):** abrir ProdIA :8020, `Ctrl+F5`, subir el archivo por la UI.
  Bajo `(Bitacora)` deben aparecer **3 ítems clicables** (Tabla 1 REAL / Tabla 2 PROGRAMA / Tabla 3 PROYECCIÓN).
  Clic en cada uno → tabla ancha con columnas de **fecha (DD/MM)**. Si el archivo es STD, la Tabla 2
  (PROGRAMA) abre con el aviso "Sin datos para esta tabla en este archivo." (no error rojo).

**Criterio de cierre:** X0–X6 verde por comando + X7 confirmado visualmente (3 ítems). Si algo no
coincide, DETENER y reportar el output completo (no marcar como hecho sin evidencia).

---

## 8. Reglas no negociables

1. **Reusar** `s/num/to_date` de `app.shared.utils`; NO reimplementar parseo, NO agregar imports nuevos.
2. Solo las **3 tablas** REAL/PROGRAMA/PROYECCIÓN. Excluir subtotales (VICE vacío) y la columna agregada mensual.
3. **NO tocar** DDL, `_p50_extract`, `_filiales_extract`, `load_filiales`, el modo matriz, ni los proxies.
4. `load_tablas_hoja` debe seguir funcionando para P50 y filiales (que devuelven **listas**): el soporte de
   dict es **aditivo**.
5. El front debe mostrar **SIEMPRE 3 ítems** bajo `(Bitacora)` (requisito duro del usuario), incluso si
   PROGRAMA tiene 0 filas.
6. Tras editar `services.py`, **reiniciar uvicorn** (no confiar en `--reload`).
7. No marcar ninguna validación como OK sin el comando y su salida real.

---

## 9. Fuera de alcance

- La **columna agregada mensual** (rótulo `REAL` a la derecha de las 31 fechas) — redundante (derivable de las diarias).
- La etiqueta **`GAS COMERCIAL`** (sin filas de datos) — placeholder vacío.
- Cualquier cambio de DDL, de esquema, o al modo matriz / a otras hojas.
- Cruce/dedup de `(Bitacora)` contra `fact_produccion_dia_ecp` (son fuentes distintas; no se unifican aquí).
