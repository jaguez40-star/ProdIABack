# plan_UNIDADES-BARRILES-EQUIVALENTES_20260908 — v2

| | |
|---|---|
| **ID tarea** | `UNIDADES-BARRILES-EQUIVALENTES` |
| **Fecha** | 2026-09-08 |
| **Versión** | **v2** — re-auditada contra el código y la BD. **La v1 era incorrecta en su núcleo** (ver §0.0). |
| **Alcance** | Backend `ProdIABack` + Frontend `ProdIAWebFront` |
| **Raíces** | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\` y `...\frontend\` |

---

## §0.0 · Qué cambia respecto a la v1 (leer primero)

La re-auditoría midió lo que la v1 daba por supuesto. Tres errores de la v1, todos con evidencia en §1:

| v1 decía | La medición dice | Consecuencia |
|---|---|---|
| Leer `fact_produccion_mes_ecp.volumen` + convertir gas ÷5,7 en Python | `volumen` mensual es un **volumen del mes**, no un caudal: da **49.775** (×101). La columna **`bpdeq_m` ya trae el gas convertido** (`bpd_m` 516,9 / `bpdeq_m` 90,7 = **5,70**) | Los pasos 3.2/3.4/3.5 de la v1 habrían mostrado cifras ×101 |
| «Tres lectores de la medida» | Son **21**: 11 mensuales, 8 diarios, 2 en `ranking.py` | La v1 dejaba 18 sin tocar → el sistema se contradecía |
| «Acumulados: en otro plan» | Con `bpdeq_m` el mensual pasa de **volumen** a **caudal**. `niveles.py:70` suma caudales → N2 mostraría sinsentidos | El acumulado **entra** en este plan (era la decisión D7 del usuario; la v1 la desplazó mal) |

Y un hallazgo que **simplifica**: `fact_produccion_mes_ecp.bpdeq_m` con 3 conceptos y el gas en proceso `VENTA-GRAVABLE` **reproduce `DATOS_MES` exacto** en total, VP, gerencia y campo, para los cuatro escenarios (§1 H3-H6). No hace falta leer `fact_tabla_hoja` en runtime: `DATOS_MES` pasa a ser el **oráculo de los tests**.

### ⚠️ Cuatro puntos que esta re-auditoría pone sobre la mesa — requieren tu OK antes de ejecutar

| # | Decisión previa | Lo que cambia | Recomendación |
|---|---|---|---|
| **P1** | D4: «total/gerencia/activo → `DATOS_MES`» | Mismos números desde `fact_mes.bpdeq_m`, **con campo y con escenarios**. `DATOS_MES` solo en tests. | Aceptar: menos piezas, misma cifra, sin perder campo |
| **P2** | D10: «PPTO por campo **pendiente**» | `_gap_campo`, `_campos_sin_meta` y el ranking gap leen REAL **y** PPTO por campo del mismo fact. Al cambiar la medida cambia para los dos: **no es implementable como pendiente**. PPTO abril por campo desde `bpdeq_m` = 510,2 = `DATOS_MES` ✓ | Darlo por resuelto de facto (viene gratis y cuadra) |
| **P3** | Objetivos 10-11 (jerarquía `wells_attributes`, mapeo 91%) | Servían para casar `DATOS_MES` con el catálogo. Si `DATOS_MES` no es fuente en runtime, **no se necesitan para este cambio** | Mover a plan propio (§7) |
| **P4** | BLANCOS mensual | `fact_mes.bpdeq_m` da **5,4** vs 13,8 de la lámina (deuda «blancos ×2», `yaml:154`). El **diario** sí cuadra (13,4 = 13,4 en agosto). | Blancos mensual = **promedio del diario del mes** (`vol_estimado`, 3 conceptos ÷ días). Es el 2,4 % del total |

**El plan de abajo está escrito bajo P1-P4 recomendadas.** Si alguna cambia, se ajusta antes de ejecutar.

---

## Decisiones cerradas del usuario

| # | Decisión |
|---|---|
| **D1** | Unidad de producción: **`kboepd`** (miles de barriles equivalentes por día). Rótulo literal, minúscula. |
| **D2** | Gas → barriles equivalentes con factor **5,7**, para todos los tipos de gas. Medido constante en 8 activos (H3). |
| **D3** | Se **revierte** la decisión del 2026-07-21 («NUNCA bbl para Gas»). |
| **D4** | Fuente por nivel (ver P1). |
| **D5** | Conceptos sumables `DERECO + PROPIEDAD + REGALIADISP` en **todos** los niveles. **Nunca se entrega una cifra inflada.** |
| **D6** | Diario: medida **`vol_estimado`** (la que reconcilia). |
| **D7** | Acumulados en **volumen**: `kboepd × días del mes`; mes en curso `× días cargados`. Ver `calendar.md`. |
| **D8** | «Los últimos N meses» = N meses **cerrados**. |
| **D9** | Diferidas también a barriles equivalentes, mismo factor. |
| **D10** | PPTO por campo — ver P2. |

---

# §0 · Contexto para el agente EXECUTOR

## 0.1 Qué es esto

**ProdIA**: aplicación de producción de Ecopetrol. Dos procesos:

| | `frontend/` | `backend/` |
|---|---|---|
| Stack | Flask + Jinja2 + JS | FastAPI (`uv`) |
| Puerto | 5029 | 5030 |

El proyecto `uv` del backend vive en `backend\backend\` (doble carpeta, no es error).

## 0.2 El contrato de datos que este plan establece

**Todo lo que sale del backend hacia el chat y los paneles está en `kboepd`.** El frontend **no escala nada**: solo formatea.

| Grano | Fuente | Medida | Conversión (en backend) | Semántica |
|---|---|---|---|---|
| Mensual (KPI, series, ranking, gap) | `fact_produccion_mes_ecp` | `bpdeq_m` | `÷ 1000` | **caudal** (kboepd) |
| Diario (curvas, valles, pace) | `fact_produccion_dia_ecp` | `vol_estimado` | gas `÷ 5,7`, luego `÷ 1000` | **caudal del día** (kboepd) |
| Acumulado (N2) | suma de mensuales | — | `Σ (kboepd × días)` | **volumen** (kbbl-eq) |
| Diferidas | SQLite `AVM_DATADIF` | `ACEITE/GAS_PERDIDO` | gas `÷ 5,7` | **volumen** (bbl-eq) |

Filtros comunes a mensual y diario: `concepto IN ('DERECO','PROPIEDAD','REGALIADISP')` y `grupo_prod = 'ECOPETROL'`.
Solo mensual: gas en proceso `VENTA-GRAVABLE` (el diario no tiene columna `proceso_id`).

## 0.3 Archivos que se tocan

```
BACKEND  (C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\)
  app\core\unidades.py                                          NUEVO
  app\features\analisis\api.py
  app\features\consulta_v2\cuantificar\validador.py
  app\features\consulta_v2\cuantificar\ranking.py
  app\features\consulta_v2\cuantificar\slots.py
  app\features\consulta_v2\cuantificar\niveles.py
  app\features\consulta_v2\cuantificar\ejecutor.py
  app\features\consulta_v2\analizar\plantilla.py
  app\features\consulta_v2\analizar\p50_referencia.py
  app\features\consulta_v2\analizar\diferidas.py
  app\features\consulta_v2\config\variables_cuantificables.yaml
  tests\test_unidades_beq.py                                    NUEVO

FRONTEND (C:\APLICACIONES\ProdIA\Repo ProdIA\frontend\)
  static\js\multitab_shell.js
  routes\api.py
```

## 0.4 Convenciones

- **JS: ES5 clásico.** `var` + `function`. Prohibido: arrow functions, template literals, `const`/`let`, `??`, `?.`.
- **Todo en español**, código y comentarios. Comas decimales es-CO en la salida.
- Cada cambio lleva la marca `[BEQ-2026-09-08]` en el comentario.

## 0.5 Cómo correr

```powershell
# desde C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend
uv run pytest tests/test_unidades_beq.py -v
uv run pytest tests/ -q
```

---

# §1 · Hallazgos de la auditoría (v2)

## 🔴 H1 — `volumen` mensual NO es un caudal; `bpdeq_m` sí, y ya trae el gas convertido

Medido en abril 2026, reporte 148, REAL, ECOPETROL:

| medida | conceptos | CRUDO | GAS | BLANCOS |
|---|---|---|---|---|
| `volumen` | 3 | 49.775,0 | 50.331,3 | 517,9 |
| `bpd_m` | 3 | **492,4** | 516,9 | 5,4 |
| `bpdeq_m` | 3 | **492,4** | **90,7** | 5,4 |

`516,9 / 90,7 = 5,70`. **El factor está en la fuente.** Usar `volumen` + `÷5,7` (v1) da ×101.

## 🔴 H2 — Para GAS hay que filtrar el proceso `VENTA-GRAVABLE`

El comentario de `api.py:557-558` afirma que cada producto vive en un solo proceso. **Es falso para gas hoy**:

| proceso | producto | `bpdeq_m` |
|---|---|---|
| PROD_TOTAL | CRUDO | 967,3 |
| VENTA-GRAVABLE | GAS | 153,4 |
| **CONSUMO** | GAS | **28,0** |
| GAS CONVERTIDO MME | BLANCOS | 7,6 |

Con 3 conceptos: `VENTA-GRAVABLE` solo → **76,7** (abril) y **80,6** (agosto), exacto contra `DATOS_MES`. Con `CONSUMO` sumado → 90,7 (mal).

## 🟢 H3 — El factor 5,7 es constante (8 de 8 activos)

Agosto, gas, fact diario 3 conceptos ÷31 contra `DATOS_MES`: PIEDEMONTE 5,70 · OPERADOS 5,70 · CUSIANA 5,70 · CATATUMBO 5,70 · DE MARES 5,70 · MENORES 5,70 · HUILA-TOLIMA 5,70 · CIRA-TECA 5,70.

## 🟢 H4 — `fact_mes.bpdeq_m` reproduce `DATOS_MES` en todos los escenarios

Abril, 3 conceptos, ECOPETROL, gas `VENTA-GRAVABLE`:

| escenario | CRUDO fact / DATOS_MES | GAS fact / DATOS_MES |
|---|---|---|
| REAL | 492,4 / 492,4 | 76,7 / 76,7 |
| PPTO | 510,2 / 510,2 | 74,2 / 74,2 |
| OPERATIVO | 515,0 / 515,0 | 76,2 / 76,2 |

## 🟢 H5 — Nivel gerencia: `dim_fuente.gerencia` reproduce `DATOS_MES.vice` (11 de 13)

CRUDO abril: CPV, DFL, GAA, GCT, GLH, GOR, GPA, GRM, GTA, GXO, PRP **exactas**. GAN y GNS se intercambian 4,48 (un campo atribuido a distinta gerencia en cada fuente; la suma es idéntica). Nivel VP: GPU 421,9 + GGN 52,5 + GGS 17,6 + GOX 0,4 = 492,4 ✓.

## 🔴 H6 — BLANCOS mensual NO reconcilia desde `fact_mes` (5,4 vs 13,8)

Ninguna combinación de medida/conceptos del mensual da 13,8. El **diario** sí: `vol_estimado`, 3 conceptos, ÷31 = 13,4 = `DATOS_MES` agosto. Ver P4.

## 🔴 H7 — Son 21 lectores de la medida, no 3

**Mensuales (`SUM(m.volumen)` → deben pasar a `bpdeq_m`)**:
`api.py:477` (`_campos_sin_meta`) · `:564` (KPI `desempeno`) · `:610` (`ritmo_mensual`) · `:700` (`escenario_mes`) · `:1240` (`desempeno_insight` KPI) · `:1293` (insight gap campo) · `:1748` (`ejecutivo` KPI) · `:1825` (`hist_anio`) · `:1847` (`_gap_campo`) · `ranking.py:226-236` · `ranking.py:237-249`.

**Diarios (`SUM(d.volumen)` → deben pasar a `vol_estimado` + conversión)**:
`api.py:580` (curva `desempeno`) · `:927` (valle por pozo) · `:1256` (insight serie crudo) · `:1767` (`ejecutivo` serie crudo) · `:1806` (pace) · `:2769` (`produccion_dia`) · `:2797` (`curva_dia_mes`) · `:2829` (`curva_dia_rango`).

`escenario_mes` **no es endpoint** y no aparece al buscar `/desempeno`. Los 21 cambian **juntos** o el sistema se contradice.

## 🔴 H8 — El mensual pasa de VOLUMEN a CAUDAL: 5 fórmulas mezclan granos

| Ruta:línea | Hoy | Con `bpdeq_m` |
|---|---|---|
| `api.py:636` | `_esp = REAL * (dias_rep / dim)` | REAL ya es caudal → `_esp = REAL * dias_rep` |
| `api.py:637` | `promedio_dia = Σ REAL_mes / Σ días` | media de caudales **ponderada** por días |
| `api.py:1814` | `_mtd <= _real * 1.05` (volumen vs caudal) | `_mtd / _nd <= _real * 1.05` |
| `api.py:1815` | `_req = (_ppto - _mtd) / _rest` | `_req = (_ppto * dim - _mtd) / _rest` |
| `niveles.py:70` | `total_real += fila["real"]` | `+= fila["real"] * días` (D7) |

## 🔴 H9 — `round()` a entero destruye la precisión en kboepd

`api.py:623,627,637` (series/promedios) · `:1889-1897` (`_gap_campo`) · `ranking.py:364-365`. Con kboepd, 492,4 → 492 y un campo de 0,4 → **0**. Pasan a `round(x, 1)`.

## 🔴 H10 — Sufijos `/día` y `/mes` que quedan mal sobre una unidad que ya es caudal

**JS**: `2356, 2430, 2439, 2454, 2467, 2520, 2605, 2611, 2837, 3256, 3262, 3621, 3640, 7861`.
**Python**: `validador.py:75`, `plantilla.py:180-182, 320-322, 450, 460`.
"kboepd/mes" no existe. Se quitan.

## 🔴 H11 — 14 divisiones `÷1e6` hardcodeadas fuera de `__cnGasM` + 13 selectores `esGas ? __cnGasM : ...`

Divisiones: `2410-2413, 2596-2597, 2668, 3124, 3252-3253, 4513, 4589, 4646, 4705`.
Selectores de formato: `2375, 2409, 2593, 3011, 3251, 3619, 3620, 3766, 3814, 4512, 4588, 4645, 4704, 4797, 4836, 4981, 6853, 7857`.
Todos pasan a un único `__cnBeq`.

## 🔴 H12 — Rótulos `"MSCF"` literales en JS: `2347, 3116, 3249, 4545, 4615, 4673, 4733, 2890, 3010, 7860`. `3632` deriva `BOPD/MSCFD` por string.

## 🟡 H13 — `fmt_valor` (`validador.py:21`) y `_UNIDADES` (`:14`) calibrados para MSCF. `__cnFmtKpi/__cnFmtBopd` (`JS:3498-3507`) conmutan en 1e6/1e3 y con kboepd caen a `__cnMilesEC` (sin decimal). Se sustituyen por el formateador único.

## 🟡 H14 — Cinco copias del mapa de unidad en Python (`yaml:60,68,77` · `ranking.py:299` · `api.py:734,2622` · `plantilla.py:9` · `p50_referencia.py:24`). Se centralizan en `app/core/unidades.py`.

## 🟡 H15 — Diferidas: `GAS_PERDIDO` está en la misma unidad que la producción (`routes/api.py:707-709`, verificado banda 0,4-0,8 %). Se convierte con 5,7 en `diferidas.py` (`_top`, `_prod`) y en `routes/api.py` (`_impacto`). Es **volumen**, no caudal → rótulo `bbl-eq`.

## 🟢 H16 — Umbrales relativos sobreviven sin tocar
`tendencia.py:16,20,23,25` · `api.py:800` (valle 0,997) · `api.py:724` (90/75) · `ranking.py:404-449` (50/75/30). Todos cocientes o conteos.

## 🟢 H17 — `_UNIDAD_VP`, `_fmt_vp`, `_kbpe`, `/president`, `p50_2026` **NO se tocan**: ya están en kbpe/kboepd sin `÷1e6`. Blindado por `test_p50_referencia.py:365-388`.

## 🟡 H18 — `map_campo_activo` tiene **0 filas en local** (se perdió en el truncate). El nivel activo (`fuentes_de_activo`, ranking «activo») **no se puede validar aquí**; sí en pruebas/139.

## 🟡 H19 — El React de `kpis_prod/api.py:11-14` y las vistas `vw_wa_*` siguen sumando 5 conceptos. Quedan **fuera** (§7) pero inconsistentes con el chat hasta su propio plan.

---

# §2 · Estado actual (lo que el executor va a encontrar)

`api.py:563-570` — KPI mensual, sin filtro de concepto, medida `volumen`:
```python
        for r in c.execute(_bind(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1, 2""", pm), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
```

`validador.py:17-26` — el `÷1e6` del texto. `multitab_shell.js:3512-3516` — el `÷1e6` del panel. Ambos desaparecen.

---

# §3 · Especificación

> **Regla**: localizar el texto EXACTO y sustituirlo por el texto EXACTO. Si un `LOCALIZAR` no aparece literal, **DETENERSE y reportar**. Donde varios sitios comparten texto idéntico, se indica el número de línea: editar **uno por uno** y verificar con `grep -c` que solo cambió una ocurrencia.

---

## 3.1 · AÑADIR — `app/core/unidades.py` (archivo completo)

```python
"""core/unidades.py — punto UNICO de verdad para unidades de produccion.

Contrato: todo lo que sale del backend esta en kboepd (miles de barriles equivalentes por
dia). El frontend NO escala, solo formatea.

  Mensual  -> fact_produccion_mes_ecp.bpdeq_m   (el gas YA viene en beq)      -> /1000
  Diario   -> fact_produccion_dia_ecp.vol_estimado  (gas /5.7)                -> /1000
  Acumulado-> SUM(kboepd_mes x dias_mes)  -> VOLUMEN en kbbl-eq (no caudal)
  Diferidas-> AVM_DATADIF.*_PERDIDO       (gas /5.7)  -> VOLUMEN en bbl-eq

Ver backend/Planes/plan_UNIDADES-BARRILES-EQUIVALENTES_20260908.md
"""

# Factor gas -> barriles equivalentes. Medido: bpd_m/bpdeq_m = 5,70 en el fact mensual y
# constante en 8 activos del fact diario contra DATOS_MES (plan v2 §1 H1, H3).
FACTOR_GAS_BEQ = 5.7

# El fact entrega unidades sueltas (bpd); se muestran miles.
ESCALA_K = 1000.0

# Rotulos. D1 (2026-09-08), revierte la decision del 2026-07-21 (D3).
UNIDAD = "kboepd"          # caudal: mes puntual, dia, series, ranking, gap
UNIDAD_ACUM = "kbbl-eq"    # volumen: acumulados (D7)
UNIDAD_DIF = "bbl-eq"      # volumen: diferidas (D9)

UNIDADES_PRODUCTO = {"CRUDO": UNIDAD, "GAS": UNIDAD, "BLANCOS": UNIDAD}

# Conceptos que SI suman. MONETIZACION y CAMPOS_REG_ESP son atribuciones del MISMO volumen:
# sumarlos duplica (crudo 968 en vez de 492). Plan v2 §1 H1; HALLAZGO_concepto_multiplicidad.md.
CONCEPTOS_SUMABLES = ("DERECO", "PROPIEDAD", "REGALIADISP")
SQL_CONCEPTOS = "co.nombre IN ('DERECO','PROPIEDAD','REGALIADISP')"

# Solo mensual: el gas de CONSUMO no es produccion (plan v2 §1 H2). El diario no tiene proceso.
PROCESO_GAS = "VENTA-GRAVABLE"
SQL_PROCESO_GAS = "(tp.nombre <> 'GAS' OR pr.nombre = 'VENTA-GRAVABLE')"


def a_beq(valor, producto):
    """Volumen crudo del fact DIARIO -> barriles equivalentes. Gas /5.7; crudo y blancos igual."""
    if valor is None:
        return None
    v = float(valor)
    return v / FACTOR_GAS_BEQ if str(producto).upper() == "GAS" else v


def kboepd_mes(valor):
    """bpdeq_m (ya equivalente, bpd) -> kboepd."""
    return None if valor is None else float(valor) / ESCALA_K


def kboepd_dia(valor, producto):
    """vol_estimado de UN dia (bpd bruto) -> kboepd."""
    v = a_beq(valor, producto)
    return None if v is None else v / ESCALA_K


def fmt(n, dec=1):
    """Formato es-CO: punto de miles, coma decimal. 492,4 · 52.430,9 · 0,2."""
    try:
        s = "{:,.{d}f}".format(float(n), d=dec)
        return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    except Exception:
        return str(n)
```

---

## 3.2 · MODIFICAR — `analisis/api.py`, import

**LOCALIZAR** la línea `from app.core.db import get_engine` (primera aparición en el archivo) y **AÑADIR justo debajo**:
```python
from app.core import unidades as _u          # [BEQ-2026-09-08] punto unico de unidades
```

---

## 3.3 · MODIFICAR — `api.py:556-570` — KPI mensual de `desempeno` (+ corregir el comentario H1)

**LOCALIZAR**:
```python
        # --- Módulo 1: REAL vs PPTO por producto (SOLO mensual — VERIFICADO H1) ---
        # H1: el `volumen` de cada producto vive en UN SOLO proceso (CRUDO→PROD_TOTAL,
        # GAS→VENTA-GRAVABLE, BLANCOS→GAS CONVERTIDO MME); los demás procesos van en NULL.
        # Por eso SUM(m.volumen) sobre TODOS los procesos NO doble-cuenta y es ROBUSTO al mapeo
        # (no hay que hard-codear el proceso por producto). NO filtrar por proceso.
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_bind(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1, 2""", pm), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
```
**SUSTITUIR POR**:
```python
        # --- Módulo 1: REAL vs PPTO por producto (SOLO mensual) ---
        # [BEQ-2026-09-08] Medida = bpdeq_m (barriles EQUIVALENTES por dia; el gas ya viene /5,7
        # desde la fuente). Conceptos: solo los 3 sumables. Proceso: el gas de CONSUMO no es
        # produccion (medido: 28,0 de 90,7 en abril) -> solo VENTA-GRAVABLE para GAS.
        # El comentario anterior ("los demas procesos van en NULL") era falso para gas.
        # Resultado en kboepd (CAUDAL). Reproduce DATOS_MES exacto (plan v2 §1 H1-H4).
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_bind(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.bpdeq_m) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
            JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO')
              AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
              AND {where('m')}
            GROUP BY 1, 2""", pm), pm):
            kpi.setdefault(r[0], {})[r[1]] = _u.kboepd_mes(r[2] or 0)
```

---

## 3.4 · MODIFICAR — `api.py:579-586` — curva diaria de `desempeno`

**LOCALIZAR**:
```python
            rows = c.execute(_bind(f"""
                SELECT d.fecha, tp.nombre prod, SUM(d.volumen) vol
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                GROUP BY 1, 2 ORDER BY 1""", pd), pd).all()
            for f, prod, vol in rows:
                iso = f.isoformat()
                curva.setdefault(iso, {})[prod] = float(vol or 0)
```
**SUSTITUIR POR**:
```python
            # [BEQ-2026-09-08] Diario: vol_estimado (la unica medida que reconcilia con el mensual,
            # plan v2 §1 H3), 3 conceptos, ECOPETROL. Gas /5,7 y todo /1000 -> kboepd del dia.
            rows = c.execute(_bind(f"""
                SELECT d.fecha, tp.nombre prod, SUM(d.vol_estimado) vol
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {_u.SQL_CONCEPTOS}
                  AND d.grupo_prod = 'ECOPETROL' AND {where('d')}
                GROUP BY 1, 2 ORDER BY 1""", pd), pd).all()
            for f, prod, vol in rows:
                iso = f.isoformat()
                curva.setdefault(iso, {})[prod] = _u.kboepd_dia(vol or 0, prod)
```

---

## 3.5 · MODIFICAR — `api.py:609-616` — `ritmo_mensual`

**LOCALIZAR**:
```python
        mrows = c.execute(_bind(f"""
            SELECT EXTRACT(month FROM m.fecha)::int AS mes, tp.nombre AS prod, SUM(m.volumen) AS vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :yy AND {where('m')}
            GROUP BY 1, 2 ORDER BY 1""", pr), pr).all()
        real_mes = {}      # {mes: {prod: vol}}
        for _mes, _prod, _vol in mrows:
            real_mes.setdefault(int(_mes), {})[_prod] = float(_vol or 0)
```
**SUSTITUIR POR**:
```python
        # [BEQ-2026-09-08] Mismo contrato que el Modulo 1: bpdeq_m, 3 conceptos, ECP, gas VENTA-GRAVABLE.
        mrows = c.execute(_bind(f"""
            SELECT EXTRACT(month FROM m.fecha)::int AS mes, tp.nombre AS prod, SUM(m.bpdeq_m) AS vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
            JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
            WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :yy
              AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
              AND {where('m')}
            GROUP BY 1, 2 ORDER BY 1""", pr), pr).all()
        real_mes = {}      # {mes: {prod: kboepd}}
        for _mes, _prod, _vol in mrows:
            real_mes.setdefault(int(_mes), {})[_prod] = _u.kboepd_mes(_vol or 0)
```

---

## 3.6 · MODIFICAR — `api.py:623-637` — series, promedios y reconciliación (H8, H9)

**LOCALIZAR**:
```python
            ritmo["series"][p] = [round(real_mes[m][p]) if real_mes.get(m, {}).get(p) else None
                                  for m in meses_ord]
```
**SUSTITUIR POR**:
```python
            ritmo["series"][p] = [round(real_mes[m][p], 1) if real_mes.get(m, {}).get(p) else None
                                  for m in meses_ord]   # [BEQ] 1 decimal: kboepd
```

**LOCALIZAR**:
```python
            ritmo["promedio_mes"][p] = round(sum(v for _m, v in cerr) / len(cerr)) if cerr else None
```
**SUSTITUIR POR**:
```python
            ritmo["promedio_mes"][p] = round(sum(v for _m, v in cerr) / len(cerr), 1) if cerr else None
```

**LOCALIZAR**:
```python
            _dd = sum(calendar.monthrange(y, _m)[1] for _m, _ in cerr)
            _mtd_dia = sum(v for v in series.get(p, []) if v)                    # acumulado de la curva del mes
            _esp = (kpi.get(p, {}).get("REAL", 0.0) * (dias_rep / dim)) if dim else 0.0  # MTD esperado (mensual)
            _reconc = _esp > 0 and _mtd_dia <= _esp * 1.15
            ritmo["promedio_dia"][p] = round(sum(v for _m, v in cerr) / _dd) if (_dd and _reconc) else None
```
**SUSTITUIR POR**:
```python
            _dd = sum(calendar.monthrange(y, _m)[1] for _m, _ in cerr)
            _mtd_dia = sum(v for v in series.get(p, []) if v)                    # Σ kboepd de los dias = kbbl-eq MTD
            # [BEQ-2026-09-08] REAL mensual ya es CAUDAL (kboepd): el MTD esperado es caudal x dias
            # reportados (antes: volumen x fraccion del mes). Plan v2 §1 H8.
            _esp = (kpi.get(p, {}).get("REAL", 0.0) * dias_rep) if dim else 0.0
            _reconc = _esp > 0 and _mtd_dia <= _esp * 1.15
            # [BEQ] promedio diario del anio = media de caudales mensuales PONDERADA por dias.
            ritmo["promedio_dia"][p] = (round(sum(v * calendar.monthrange(y, _m)[1] for _m, v in cerr) / _dd, 1)
                                        if (_dd and _reconc) else None)
```

---

## 3.7 · MODIFICAR — `api.py:473-487` — `_campos_sin_meta`

**LOCALIZAR**:
```python
    q = sa.text("""
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), TRIM(f.nombre)) campo, tp.nombre producto,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) real,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) ppto
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_fuente f        ON f.fuente_id        = m.fuente_id
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND m.fuente_id IN :ids
        GROUP BY 1, 2
        HAVING SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) > 0
           AND SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) = 0
        ORDER BY 3 DESC
    """).bindparams(sa.bindparam("ids", expanding=True))
    return [{"campo": r[0], "producto": r[1], "real": float(r[2] or 0)}
            for r in c.execute(q, {"fin": fin, "ids": ids})]
```
**SUSTITUIR POR**:
```python
    # [BEQ-2026-09-08] bpdeq_m, 3 conceptos, ECP, gas VENTA-GRAVABLE. /1000 en SQL -> kboepd.
    q = sa.text(f"""
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), TRIM(f.nombre)) campo, tp.nombre producto,
               SUM(CASE WHEN es.nombre='REAL' THEN m.bpdeq_m ELSE 0 END) / 1000.0 real,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.bpdeq_m ELSE 0 END) / 1000.0 ppto
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_fuente f        ON f.fuente_id        = m.fuente_id
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_concepto co      ON co.concepto_id      = m.concepto_id
        JOIN core.dim_proceso pr       ON pr.proceso_id       = m.proceso_id
        WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND m.fuente_id IN :ids
          AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
        GROUP BY 1, 2
        HAVING SUM(CASE WHEN es.nombre='REAL' THEN m.bpdeq_m ELSE 0 END) > 0
           AND SUM(CASE WHEN es.nombre='PPTO' THEN m.bpdeq_m ELSE 0 END) = 0
        ORDER BY 3 DESC
    """).bindparams(sa.bindparam("ids", expanding=True))
    return [{"campo": r[0], "producto": r[1], "real": float(r[2] or 0)}
            for r in c.execute(q, {"fin": fin, "ids": ids})]
```

---

## 3.8 · MODIFICAR — `api.py:699-712` — `escenario_mes`

**LOCALIZAR**:
```python
        t = sa.text(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.volumen) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN :escs AND {whr}
            GROUP BY 1, 2""").bindparams(sa.bindparam("escs", expanding=True))
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        out = {}
        for prod, esc, vol in c.execute(t, params):
            out.setdefault(prod, {})[esc] = float(vol or 0)
        return out
```
**SUSTITUIR POR**:
```python
        # [BEQ-2026-09-08] Lector NO-endpoint: alimenta "vs el operativo" y "contra el contable".
        # Cambia junto con los otros 20 (plan v2 §1 H7) o el cumplimiento contra el cierre contable
        # -la cifra oficial auditada- sale absurdo.
        t = sa.text(f"""
            SELECT tp.nombre prod, es.nombre esc, SUM(m.bpdeq_m) vol
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
            JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
            WHERE m.fecha = :fin AND es.nombre IN :escs
              AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
              AND {whr}
            GROUP BY 1, 2""").bindparams(sa.bindparam("escs", expanding=True))
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        out = {}
        for prod, esc, vol in c.execute(t, params):
            out.setdefault(prod, {})[esc] = _u.kboepd_mes(vol or 0)
        return out
```

---

## 3.9 · MODIFICAR — `api.py:734` y `:2622` — mapas de unidad

**LOCALIZAR** `_UNIDADES_PRODUCTO = {"CRUDO": "bbl", "BLANCOS": "bbl", "GAS": "MSCF"}`
**SUSTITUIR POR** `_UNIDADES_PRODUCTO = dict(_u.UNIDADES_PRODUCTO)   # [BEQ-2026-09-08] todos kboepd`

**LOCALIZAR** `            "unidades": {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}}`
**SUSTITUIR POR** `            "unidades": dict(_u.UNIDADES_PRODUCTO)}   # [BEQ-2026-09-08]`

---

## 3.10 · MODIFICAR — `api.py:924-931` — valle por pozo (CRUDO)

**LOCALIZAR**:
```python
        WITH dd AS (
          SELECT f.nombre pozo, d.fecha, SUM(d.volumen) v
          FROM core.fact_produccion_dia_ecp d
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
          JOIN core.dim_fuente f ON f.fuente_id = d.fuente_id
          WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where_d}
          GROUP BY 1, 2)
```
**SUSTITUIR POR**:
```python
        WITH dd AS (
          SELECT f.nombre pozo, d.fecha, SUM(d.vol_estimado) / 1000.0 v
          FROM core.fact_produccion_dia_ecp d
          JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
          JOIN core.dim_fuente f ON f.fuente_id = d.fuente_id
          JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
          WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where_d}
            AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL'
          GROUP BY 1, 2)
```
> `f"""` ya es f-string en esta consulta (usa `{where_d}`). Solo crudo: no hace falta el factor gas.

---

## 3.11 · MODIFICAR — `api.py:1239-1246` — KPI de `desempeno_insight`

**LOCALIZAR**:
```python
        for r in c.execute(_b(f"""
            SELECT tp.nombre, es.nombre, SUM(m.volumen)
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1,2"""), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
```
> ⚠️ Este texto aparece **dos veces** (línea 1239 y línea 1747). Editar **la de 1239** aquí; la de 1747 en 3.14.

**SUSTITUIR POR**:
```python
        for r in c.execute(_b(f"""
            SELECT tp.nombre, es.nombre, SUM(m.bpdeq_m)
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
            JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO')
              AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
              AND {where('m')}
            GROUP BY 1,2"""), pm):
            kpi.setdefault(r[0], {})[r[1]] = _u.kboepd_mes(r[2] or 0)   # [BEQ-2026-09-08]
```

---

## 3.12 · MODIFICAR — `api.py:1255-1261` — serie diaria crudo de `desempeno_insight`

**LOCALIZAR**:
```python
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.volumen)
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
            GROUP BY 1 ORDER BY 1"""), pd).all()
```
> ⚠️ Texto **idéntico** en 1255 y 1766 salvo el nombre del parámetro (`pd` vs `pd_`). Este es el de **`pd`**.

**SUSTITUIR POR**:
```python
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.vol_estimado) / 1000.0
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
              AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL'
            GROUP BY 1 ORDER BY 1"""), pd).all()   # [BEQ-2026-09-08] kboepd
```

---

## 3.13 · MODIFICAR — `api.py:1289-1298` — gap por campo de `desempeno_insight`

**LOCALIZAR**:
```python
            grows = c.execute(_b(f"""
                SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS campo,
                       SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
                       SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                JOIN core.dim_fuente f ON f.fuente_id = m.fuente_id
                WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND tp.nombre = :prod AND {where('m')}
                GROUP BY 1"""), pg).all()
```
> ⚠️ Texto **idéntico** en 1289 y 1843. Editar **1289** aquí; **1843** en 3.16.

**SUSTITUIR POR**:
```python
            grows = c.execute(_b(f"""
                SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS campo,
                       SUM(CASE WHEN es.nombre='REAL' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vreal,
                       SUM(CASE WHEN es.nombre='PPTO' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vppto
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                JOIN core.dim_fuente f ON f.fuente_id = m.fuente_id
                JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
                JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
                WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND tp.nombre = :prod AND {where('m')}
                  AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
                GROUP BY 1"""), pg).all()   # [BEQ-2026-09-08] kboepd
```

---

## 3.14 · MODIFICAR — `api.py:1747-1754` — KPI de `ejecutivo`

Mismo `LOCALIZAR` que 3.11 (segunda ocurrencia, línea **1747**). Mismo `SUSTITUIR POR`.

---

## 3.15 · MODIFICAR — `api.py:1766-1772` — serie diaria crudo de `ejecutivo`

Mismo bloque que 3.12 pero con **`pd_`** en vez de `pd`:

**LOCALIZAR**:
```python
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.volumen)
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
            GROUP BY 1 ORDER BY 1"""), pd_).all()
```
**SUSTITUIR POR**:
```python
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.vol_estimado) / 1000.0
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
              AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL'
            GROUP BY 1 ORDER BY 1"""), pd_).all()   # [BEQ-2026-09-08] kboepd
```

---

## 3.16 · MODIFICAR — `api.py:1843-1852` — `_gap_campo` de `ejecutivo`

Mismo `LOCALIZAR` que 3.13 (segunda ocurrencia, línea **1843**). Mismo `SUSTITUIR POR`.

---

## 3.17 · MODIFICAR — `api.py:1805-1817` — pace (H8)

**LOCALIZAR**:
```python
        for _nom, _nd, _mtd in c.execute(_b(f"""
                SELECT tp.nombre, COUNT(DISTINCT d.fecha), SUM(d.volumen)
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                GROUP BY 1"""), pd_).all():
            _nd = int(_nd or 0); _mtd = float(_mtd or 0)
            _real = kpi.get(_nom, {}).get("REAL", 0.0); _ppto = kpi.get(_nom, {}).get("PPTO", 0.0)
            _rest = dim - _nd
            if _nd and _rest > 0 and _ppto and _real and _mtd <= _real * 1.05:
                _prom = _mtd / _nd; _req = (_ppto - _mtd) / _rest
                pace_por_prod[_nom] = {"promedio_dia": round(_prom), "requerido_dia": round(_req),
```
**SUSTITUIR POR**:
```python
        for _nom, _nd, _mtd in c.execute(_b(f"""
                SELECT tp.nombre, COUNT(DISTINCT d.fecha), SUM(d.vol_estimado)
                FROM core.fact_produccion_dia_ecp d
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
                JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
                WHERE d.fecha BETWEEN :ini AND :fin AND {where('d')}
                  AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL'
                GROUP BY 1"""), pd_).all():
            _nd = int(_nd or 0); _mtd = _u.kboepd_dia(_mtd or 0, _nom)        # Σ kboepd de los dias (kbbl-eq MTD)
            _real = kpi.get(_nom, {}).get("REAL", 0.0); _ppto = kpi.get(_nom, {}).get("PPTO", 0.0)
            _rest = dim - _nd
            # [BEQ-2026-09-08] _real/_ppto son CAUDALES (kboepd); _mtd es VOLUMEN del mes (kboepd·dia).
            # La guarda y el requerido se calculan caudal contra caudal (plan v2 §1 H8).
            if _nd and _rest > 0 and _ppto and _real and (_mtd / _nd) <= _real * 1.05:
                _prom = _mtd / _nd; _req = (_ppto * dim - _mtd) / _rest
                pace_por_prod[_nom] = {"promedio_dia": round(_prom, 1), "requerido_dia": round(_req, 1),
```

---

## 3.18 · MODIFICAR — `api.py:1824-1831` — `hist_anio`

**LOCALIZAR**:
```python
        for _nom, _mm, _v in c.execute(_b(f"""
                SELECT tp.nombre, EXTRACT(month FROM m.fecha)::int, SUM(m.volumen)
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :hy
                  AND EXTRACT(month FROM m.fecha) < :hmo AND {where('m')}
                GROUP BY 1, 2"""), {**base, "hy": y, "hmo": mo}).all():
            _v = float(_v or 0)
```
**SUSTITUIR POR**:
```python
        for _nom, _mm, _v in c.execute(_b(f"""
                SELECT tp.nombre, EXTRACT(month FROM m.fecha)::int, SUM(m.bpdeq_m)
                FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                JOIN core.dim_concepto co ON co.concepto_id = m.concepto_id
                JOIN core.dim_proceso pr ON pr.proceso_id = m.proceso_id
                WHERE es.nombre = 'REAL' AND EXTRACT(year FROM m.fecha) = :hy
                  AND EXTRACT(month FROM m.fecha) < :hmo AND {where('m')}
                  AND {_u.SQL_CONCEPTOS} AND m.grupo_prod = 'ECOPETROL' AND {_u.SQL_PROCESO_GAS}
                GROUP BY 1, 2"""), {**base, "hy": y, "hmo": mo}).all():
            _v = _u.kboepd_mes(_v or 0)   # [BEQ-2026-09-08]
```

---

## 3.19 · MODIFICAR — `api.py:1889-1897` — redondeos de `_gap_campo` (H9)

**LOCALIZAR**:
```python
                "faltante_bruto": round(gap_detr_total),
                "excedente_bruto": round(gap_comp_total),
```
**SUSTITUIR POR**:
```python
                "faltante_bruto": round(gap_detr_total, 1),    # [BEQ] kboepd: 1 decimal
                "excedente_bruto": round(gap_comp_total, 1),
```

**LOCALIZAR**:
```python
                "detractores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3]),
                                  "eventos": _comentarios_campo_mes(c, d[0], ini, fin)}
                                for d in detr],
                "compensadores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])}
                                  for d in comp],
                "extremos": [{"campo": d[0], "real": round(d[2]), "meta": round(d[3])} for d in _ext],
```
**SUSTITUIR POR**:
```python
                "detractores": [{"campo": d[0], "gap": round(d[1], 1), "real": round(d[2], 1), "meta": round(d[3], 1),
                                  "eventos": _comentarios_campo_mes(c, d[0], ini, fin)}
                                for d in detr],
                "compensadores": [{"campo": d[0], "gap": round(d[1], 1), "real": round(d[2], 1), "meta": round(d[3], 1)}
                                  for d in comp],
                "extremos": [{"campo": d[0], "real": round(d[2], 1), "meta": round(d[3], 1)} for d in _ext],
```

---

## 3.20 · MODIFICAR — `api.py:1360` y `:2125` — anotación del valle

**LOCALIZAR** `            anotaciones["punto"]["label"] = f"mín · {mv/1e6:.2f}M"`
**SUSTITUIR POR** `            anotaciones["punto"]["label"] = f"mín · {mv:.1f} kboepd"   # [BEQ-2026-09-08]`

**LOCALIZAR** `                      "label": f"mín · {valle['min_valor']/1e6:.2f}M"},`
**SUSTITUIR POR** `                      "label": f"mín · {valle['min_valor']:.1f} kboepd"},   # [BEQ-2026-09-08]`

---

## 3.21 · MODIFICAR — `api.py:2768-2773` — `produccion_dia`

**LOCALIZAR**:
```python
        rows = c.execute(_b(f"""
            SELECT tp.nombre prod, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha = :f AND {whr} GROUP BY 1"""), p)
        por = {k: float(v or 0) for k, v in rows}
```
**SUSTITUIR POR**:
```python
        rows = c.execute(_b(f"""
            SELECT tp.nombre prod, SUM(d.vol_estimado) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
            WHERE d.fecha = :f AND {whr}
              AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL' GROUP BY 1"""), p)
        por = {k: _u.kboepd_dia(v or 0, k) for k, v in rows}   # [BEQ-2026-09-08]
```

---

## 3.22 · MODIFICAR — `api.py:2796-2801` — `curva_dia_mes`

**LOCALIZAR**:
```python
        t = sa.text(f"""
            SELECT d.fecha, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha BETWEEN :ini AND :fin AND UPPER(tp.nombre) = :p AND {whr}
            GROUP BY d.fecha ORDER BY d.fecha""")
```
> ⚠️ Texto **idéntico** en 2796 y 2828. Editar **ambos** (3.22 y 3.23) con el mismo reemplazo.

**SUSTITUIR POR**:
```python
        t = sa.text(f"""
            SELECT d.fecha, SUM(d.vol_estimado) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            JOIN core.dim_concepto co ON co.concepto_id = d.concepto_id
            WHERE d.fecha BETWEEN :ini AND :fin AND UPPER(tp.nombre) = :p AND {whr}
              AND {_u.SQL_CONCEPTOS} AND d.grupo_prod = 'ECOPETROL'
            GROUP BY d.fecha ORDER BY d.fecha""")   # [BEQ-2026-09-08]
```

En **la misma función**, la línea de retorno. Hay dos funciones con retorno distinto:

`curva_dia_mes` — **LOCALIZAR** la línea que empieza por `        return [(f, float(v or 0))` dentro de `curva_dia_mes` y **SUSTITUIR** `float(v or 0)` por `_u.kboepd_dia(v or 0, producto)`.

---

## 3.23 · MODIFICAR — `api.py:2828-2836` — `curva_dia_rango`

Mismo `LOCALIZAR`/`SUSTITUIR` del SQL que 3.22 (segunda ocurrencia).

**LOCALIZAR**:
```python
        return [(f, float(v or 0)) for f, v in c.execute(t, p)]
```
**SUSTITUIR POR**:
```python
        return [(f, _u.kboepd_dia(v or 0, producto)) for f, v in c.execute(t, p)]   # [BEQ-2026-09-08]
```

---

## 3.24 · MODIFICAR — `cuantificar/ranking.py:226-249` — `_SQL` (2 consultas)

**LOCALIZAR** (bloque completo):
```python
_SQL = {
    "campo": """
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               MAX(f.operador) AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
    "activo": """
        SELECT a.activo AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               NULL AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        JOIN core.map_campo_activo a
             ON a.campo_norm = UPPER(COALESCE(NULLIF(TRIM(f.campo),''), f.nombre))
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
}
```
**SUSTITUIR POR**:
```python
# [BEQ-2026-09-08] bpdeq_m, 3 conceptos, ECP, gas VENTA-GRAVABLE, /1000 -> kboepd (plan v2 §1 H1-H2).
_SQL_FILTROS = """
          AND co.nombre IN ('DERECO','PROPIEDAD','REGALIADISP')
          AND m.grupo_prod = 'ECOPETROL'
          AND (tp.nombre <> 'GAS' OR pr.nombre = 'VENTA-GRAVABLE')"""
_SQL = {
    "campo": """
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vppto,
               MAX(f.operador) AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        JOIN core.dim_concepto co      ON co.concepto_id      = m.concepto_id
        JOIN core.dim_proceso pr       ON pr.proceso_id       = m.proceso_id
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')""" + _SQL_FILTROS + """
        GROUP BY 1""",
    "activo": """
        SELECT a.activo AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.bpdeq_m ELSE 0 END) / 1000.0 AS vppto,
               NULL AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        JOIN core.dim_concepto co      ON co.concepto_id      = m.concepto_id
        JOIN core.dim_proceso pr       ON pr.proceso_id       = m.proceso_id
        JOIN core.map_campo_activo a
             ON a.campo_norm = UPPER(COALESCE(NULLIF(TRIM(f.campo),''), f.nombre))
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')""" + _SQL_FILTROS + """
        GROUP BY 1""",
}
```

---

## 3.25 · MODIFICAR — `ranking.py:299` y `:364-365` — unidad y redondeo

**LOCALIZAR** `    unidad = "MSCF" if prod == "gas" else "bbl"`
**SUSTITUIR POR**:
```python
    from app.core.unidades import UNIDAD as _UNIDAD_BEQ     # [BEQ-2026-09-08] antes hardcodeaba MSCF/bbl
    unidad = _UNIDAD_BEQ
```

**LOCALIZAR**:
```python
        items.append({"pos": i, "entidad": d[0], "valor": round(d[1]), "ppto": round(d[2]),
                      "gap": round(d[1] - d[2]), "operador": ol["txt"], "es_ecp": ol["es_ecp"]})
```
**SUSTITUIR POR**:
```python
        items.append({"pos": i, "entidad": d[0], "valor": round(d[1], 1), "ppto": round(d[2], 1),
                      "gap": round(d[1] - d[2], 1), "operador": ol["txt"], "es_ecp": ol["es_ecp"]})   # [BEQ] kboepd
```

---

## 3.26 · MODIFICAR — `cuantificar/validador.py` — `_UNIDADES`, `fmt_valor`, N1DSER, N2

**LOCALIZAR** `_UNIDADES = ("barril", "bbl", "mscf", "%", "porcentaje", "presupuesto", "millones", "millón")`
**SUSTITUIR POR**:
```python
# [BEQ-2026-09-08] Lista negra del intro (H13): se anaden los rotulos nuevos; "mscf" se queda por si
# un modelo lo arrastra de ejemplos viejos.
_UNIDADES = ("barril", "bbl", "mscf", "kboepd", "boepd", "beq", "kbbl-eq", "bbl-eq", "equivalente",
             "%", "porcentaje", "presupuesto", "millones", "millón")
```

**LOCALIZAR**:
```python
def fmt_valor(n, producto) -> str:
    """Literal es-CO por producto. GAS = ÷1e6 'MSCF' (mirror __cnGasM); CRUDO/BLANCOS = bbl raw."""
    try:
        if producto == "gas":
            m = float(n) / 1e6
            d = 1 if abs(m) >= 1 else 2
            return f"{m:.{d}f}".replace(".", ",")
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)
```
**SUSTITUIR POR**:
```python
def fmt_valor(n, producto) -> str:
    """Literal es-CO en kboepd, IGUAL para los tres productos: '492,4' · '80,6' · '0,2'.

    [BEQ-2026-09-08] Antes el gas iba en MSCF (÷1e6) y crudo/blancos en bbl. Ahora TODO llega ya
    en kboepd desde analisis/api.py (contrato §0.2 del plan): aqui solo se formatea. `producto`
    se conserva en la firma por los ~20 call sites; ya no cambia el formato.
    """
    from app.core.unidades import fmt
    return fmt(n, 1)
```

**LOCALIZAR** (línea 75):
```python
                 f"{fmt_valor(res.get('promedio_dia') or 0, prod)} {unidad}/día "
```
**SUSTITUIR POR**:
```python
                 f"{fmt_valor(res.get('promedio_dia') or 0, prod)} kboepd "
```
> El total de N1DSER (`resultado.valor`) es una SUMA de días = volumen; su `{unidad}` la fija 3.31 en `kbbl-eq`. El promedio es caudal: `kboepd` literal.

**LOCALIZAR**:
```python
    if nivel == "N2":                                   # ACUMULADO (meses cerrados)
        n = res["meses_cerrados"]
```
**SUSTITUIR POR**:
```python
    if nivel == "N2":                                   # ACUMULADO (meses cerrados)
        # [BEQ-2026-09-08] El acumulado es VOLUMEN (kbbl-eq, D7): formato con miles.
        from app.core.unidades import fmt as _fmt_u
        real = _fmt_u(res["resultado"]["valor"], 1)
        ppto = _fmt_u(res["referencia_valor"], 1) if res.get("referencia_valor") else None
        n = res["meses_cerrados"]
```

---

## 3.27 · MODIFICAR — `cuantificar/slots.py:576-581` — ancla de la ventana (D8)

**LOCALIZAR**:
```python
    else:                                 # mes: se retrocede por calendario, no por 30 días
        y, mo = fin.year, fin.month - (cant - 1)
        while mo < 1:
            y, mo = y - 1, mo + 12
        ini = _dt.date(y, mo, 1)
```
**SUSTITUIR POR**:
```python
    else:
        # [BEQ-2026-09-08] "Los ultimos N meses" = N meses CERRADOS (D8). Antes anclaba en el
        # ultimo dia CON REPORTE e incluia el mes en curso: pedias 3 y respondia 2, con el rotulo
        # equivocado (plan v2 §1 H10). Se cierra el rango en el ultimo dia del ultimo mes cerrado.
        import calendar as _cal
        y, mo = fin.year, fin.month - 1
        while mo < 1:
            y, mo = y - 1, mo + 12
        fin = _dt.date(y, mo, _cal.monthrange(y, mo)[1])
        y, mo = fin.year, fin.month - (cant - 1)
        while mo < 1:
            y, mo = y - 1, mo + 12
        ini = _dt.date(y, mo, 1)
```

---

## 3.28 · MODIFICAR — `cuantificar/niveles.py:69-72` — acumulado en volumen (D7, H8)

**LOCALIZAR**:
```python
        if m < ultimo or dm["mes"]["completo"]:
            total_real += fila["real"]
            total_ppto += (fila["ppto"] or 0)
            meses.append(_MESES[m])
```
**SUSTITUIR POR**:
```python
        if m < ultimo or dm["mes"]["completo"]:
            # [BEQ-2026-09-08] fila["real"] es CAUDAL (kboepd). Un acumulado es VOLUMEN: caudal x dias.
            # Mes cerrado -> dias del calendario; mes con reporte parcial -> dias con dato (D7,
            # calendar.md §3). Resultado en kbbl-eq.
            _dias = dm["mes"]["dias_del_mes"] if dm["mes"].get("cerrado", True) else dm["mes"]["dias_con_data"]
            total_real += fila["real"] * _dias
            total_ppto += (fila["ppto"] or 0) * _dias
            meses.append(_MESES[m])
```

---

## 3.29 · MODIFICAR — `cuantificar/ejecutor.py:186-187` — unidad del N2

**LOCALIZAR**:
```python
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")

    # [2026-09-03 · VENTANA-MESES] «los últimos N meses» acota DÓNDE EMPIEZA el acumulado.
```
**SUSTITUIR POR**:
```python
    producto = slots["producto"]
    from app.core.unidades import UNIDAD_ACUM
    unidad = UNIDAD_ACUM          # [BEQ-2026-09-08] acumulado = VOLUMEN (kbbl-eq), no caudal

    # [2026-09-03 · VENTANA-MESES] «los últimos N meses» acota DÓNDE EMPIEZA el acumulado.
```

---

## 3.30 · MODIFICAR — `ejecutor.py:236-239` — el aviso de ventana ya no habla del «último día con reporte»

**LOCALIZAR**:
```python
        avisos.append(f"«Los últimos {ven['cantidad']} meses» cuentan hacia atrás desde "
                      f"{ven['fin']}, el último día con reporte; el acumulado suma los meses "
                      f"CERRADOS dentro de esa ventana.")
```
**SUSTITUIR POR**:
```python
        avisos.append(f"«Los últimos {ven['cantidad']} meses» son los {ven['cantidad']} meses "
                      f"cerrados hasta {ven['fin']}; el mes en curso no entra.")   # [BEQ] D8
```

---

## 3.31 · MODIFICAR — `ejecutor.py:471` — unidad del N1DSER (total = volumen)

**LOCALIZAR** (línea **471** — el texto es idéntico en 394 y 520: **solo 471**):
```python
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
```
**SUSTITUIR POR**:
```python
        "producto": producto, "unidad": "kbbl-eq",   # [BEQ-2026-09-08] N1DSER: el total es Σ dias = VOLUMEN
```

---

## 3.32 · MODIFICAR — `analizar/plantilla.py` — `_UNIDAD` y sufijos (H10, H14)

**LOCALIZAR** `_UNIDAD = {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}`
**SUSTITUIR POR**:
```python
from app.core.unidades import UNIDADES_PRODUCTO as _UNIDAD, UNIDAD_DIF as _UNIDAD_DIF   # [BEQ-2026-09-08]
```

**LOCALIZAR** (línea 56, dentro de `_split_lineas` — diferidas): `    u = _UNIDAD.get(prod, "bbl")`
> ⚠️ Hay 4 líneas con este texto (43, 56, 93, 159). Solo **56** y **351** son de diferidas.
**SUSTITUIR** la de **56** por: `    u = _UNIDAD_DIF          # [BEQ] diferidas = VOLUMEN perdido (bbl-eq), no caudal`
**SUSTITUIR** la de **351** por: `        u = _UNIDAD_DIF      # [BEQ] diferidas = VOLUMEN perdido (bbl-eq)`

**LOCALIZAR**:
```python
                lineas.append(f"  · Para cerrar crudo en presupuesto se necesitan {_fmt(f['requerido_dia'], 'CRUDO')} bbl/día "
```
**SUSTITUIR POR**:
```python
                lineas.append(f"  · Para cerrar crudo en presupuesto se necesitan {_fmt(f['requerido_dia'], 'CRUDO')} kboepd "
```
**LOCALIZAR** `                              f"actual de {_fmt(f.get('promedio_dia'), 'CRUDO')} bbl/día.")`
**SUSTITUIR POR** `                              f"actual de {_fmt(f.get('promedio_dia'), 'CRUDO')} kboepd.")`

**LOCALIZAR**:
```python
    u = "bbl"
    linea = (f"para cerrar {periodo}, el crudo requiere {_fmt(req, 'CRUDO')} {u}/día en los "
             f"{rest} días restantes; va a un ritmo de {_fmt(prom, 'CRUDO')} {u}/día")
```
**SUSTITUIR POR**:
```python
    u = _UNIDAD["CRUDO"]                       # [BEQ] kboepd ya es caudal: sin "/dia"
    linea = (f"para cerrar {periodo}, el crudo requiere {_fmt(req, 'CRUDO')} {u} en los "
             f"{rest} días restantes; va a un ritmo de {_fmt(prom, 'CRUDO')} {u}")
```

**LOCALIZAR** (líneas 450 y 460, texto idéntico — **editar ambas**):
```python
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}/mes.")
```
**SUSTITUIR POR**:
```python
                  f"Promedio del periodo: {_fmt(t['media'], producto)} {u}.")   # [BEQ] caudal, sin "/mes"
```

---

## 3.33 · MODIFICAR — `analizar/p50_referencia.py:22-24` — solo `_UNIDAD` (H17)

**LOCALIZAR**:
```python
# Unidades del FACT OPERATIVO (fact_produccion_mes_ecp) — las usa el DECLINAR, cuyas cifras vienen
# de `analisis.ejecutivo`. Ahí el gas va en volumen crudo y se muestra en MSCF (÷1e6, vía _fmt).
_UNIDAD = {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}   # mismo dict que analizar/plantilla.py
```
**SUSTITUIR POR**:
```python
# Unidades del FACT OPERATIVO (fact_produccion_mes_ecp) — las usa el DECLINAR, cuyas cifras vienen
# de `analisis.ejecutivo`. [BEQ-2026-09-08] Ahora kboepd. OJO: _UNIDAD_VP (abajo) es de la HOJA
# P50 y NO cambia — nunca llevo ÷1e6 (bug dd8ffa2, test_p50_referencia.py:365-388).
from app.core.unidades import UNIDADES_PRODUCTO as _UNIDAD
```

---

## 3.34 · MODIFICAR — `config/variables_cuantificables.yaml`

**LOCALIZAR** (59-60):
```yaml
  produccion_crudo:
    unidad: bbl
```
**SUSTITUIR POR**:
```yaml
  produccion_crudo:
    unidad: kboepd                   # [BEQ-2026-09-08] miles de barriles equivalentes por dia
```
**LOCALIZAR** (67-69):
```yaml
  produccion_gas:
    unidad: MSCF                     # ✅ CONFIRMADO por el usuario 2026-08-02 (decisión de dominio)
    unidad_confirmada: true
```
**SUSTITUIR POR**:
```yaml
  produccion_gas:
    unidad: kboepd                   # [BEQ-2026-09-08] REVIERTE la decision del 2026-07-21 (D3).
    unidad_confirmada: true          # gas -> barriles equivalentes, factor 5,7 (ya en bpdeq_m)
```
**LOCALIZAR** (76-77):
```yaml
  produccion_blancos:
    unidad: bbl
```
**SUSTITUIR POR**:
```yaml
  produccion_blancos:
    unidad: kboepd                   # [BEQ-2026-09-08]
```

---

## 3.35 · MODIFICAR — `analizar/diferidas.py` — gas ÷5,7 (D9, H15)

**LOCALIZAR** (dentro de `_top`):
```python
    def _top(idx):
        vals = [((r[0] or "Sin clasificar"), float(r[idx] or 0)) for r in rows]
```
**SUSTITUIR POR**:
```python
    def _top(idx):
        # [BEQ-2026-09-08] idx 2 = GAS_PERDIDO, misma unidad que la produccion (routes/api.py:707-709):
        # se convierte a barriles equivalentes con el mismo factor. Resultado en bbl-eq (VOLUMEN).
        from app.core.unidades import FACTOR_GAS_BEQ
        _k = FACTOR_GAS_BEQ if idx == 2 else 1.0
        vals = [((r[0] or "Sin clasificar"), float(r[idx] or 0) / _k) for r in rows]
```

**LOCALIZAR** (dentro de `_prod`):
```python
    def _prod(idx):
        np_ = pl_ = 0.0
        for r in rows:
            cat = (r[0] or "").strip().lower()   # 'planeada' | 'no planeada' | 'control de producción' | ''
            v = float(r[idx] or 0)
```
**SUSTITUIR POR**:
```python
    def _prod(idx):
        from app.core.unidades import FACTOR_GAS_BEQ          # [BEQ-2026-09-08] gas -> bbl-eq
        _k = FACTOR_GAS_BEQ if idx == 2 else 1.0
        np_ = pl_ = 0.0
        for r in rows:
            cat = (r[0] or "").strip().lower()   # 'planeada' | 'no planeada' | 'control de producción' | ''
            v = float(r[idx] or 0) / _k
```

---

## 3.36 · MODIFICAR — `frontend/routes/api.py:706-712` — `_impacto` (Flask, D9)

**LOCALIZAR**:
```python
    # Crudo = ACEITE_PERDIDO (bbl). Gas = GAS_PERDIDO (misma unidad que la producción — verificado: la
    # fracción perdido/producido da ~0,4-0,8%, la misma banda que el crudo → el frontend lo muestra en
    # MSCF con ÷1e6). Blancos NO tiene columna de volumen (el frontend conserva "Pozos afectados").
    def _impacto(idx):
        vals = [((r[0] or "Sin clasificar"), float(r[idx] or 0)) for r in imp_rows]
```
**SUSTITUIR POR**:
```python
    # Crudo = ACEITE_PERDIDO (bbl). Gas = GAS_PERDIDO (misma unidad que la producción — verificado: la
    # fracción perdido/producido da ~0,4-0,8%, la misma banda que el crudo).
    # [BEQ-2026-09-08] El gas se entrega ya en barriles equivalentes (÷5,7, mismo factor que el
    # backend en app/core/unidades.py — Flask no puede importarlo, se replica la constante).
    # Blancos NO tiene columna de volumen (el frontend conserva "Pozos afectados").
    _FACTOR_GAS_BEQ = 5.7
    def _impacto(idx):
        _k = _FACTOR_GAS_BEQ if idx == 2 else 1.0
        vals = [((r[0] or "Sin clasificar"), float(r[idx] or 0) / _k) for r in imp_rows]
```

---

## 3.37 · MODIFICAR — `multitab_shell.js:3512-3516` — formateador único

**LOCALIZAR**:
```js
  function __cnGasM(v, dec) {
    var m = (Number(v) || 0) / 1e6, a = Math.abs(m);
    var d = (dec != null) ? dec : (a >= 1 ? 1 : 2);   // 3,3 · 72,3 · 0,08 (default 1 decimal ≥1)
    return m.toFixed(d).replace(".", ",");
  }
```
**SUSTITUIR POR**:
```js
  // [BEQ-2026-09-08] El backend YA entrega kboepd (y kbbl-eq en acumulados). Aqui NO se escala:
  // solo se formatea es-CO con punto de miles y coma decimal: "492,4" · "52.430,9" · "0,2".
  // Sustituye a __cnGasM (÷1e6 para MSCF), __cnFmtKpi y __cnFmtBopd en todos los paneles de
  // produccion. __cnGasM se conserva como alias para no romper call sites.
  function __cnBeq(v, dec) {
    var n = Number(v) || 0;
    var d = (dec != null) ? dec : 1;
    var s = Math.abs(n).toFixed(d);
    var partes = s.split(".");
    var ent = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    var out = ent + (partes.length > 1 ? "," + partes[1] : "");
    return (n < 0 ? "-" : "") + out;
  }
  function __cnGasM(v, dec) { return __cnBeq(v, dec); }
```

---

## 3.38 · MODIFICAR — `multitab_shell.js` — las 14 divisiones `÷1e6` (H11)

Donde había `esGas ? X/1e6 : X` queda `X`. Uno por uno, por línea:

| # | Línea | LOCALIZAR | SUSTITUIR POR |
|---|---|---|---|
| 1 | 2410 | `var yPlot = esGas ? valores.map(function (v) { return v == null ? null : v / 1e6; }) : valores;` | `var yPlot = valores;   // [BEQ] backend ya entrega kboepd` |
| 2 | 2411 | `var refPlot = esGas ? ref / 1e6 : ref;` | `var refPlot = ref;   // [BEQ]` |
| 3 | 2412 | `var pptoPlot = (pptoDia != null) ? (esGas ? pptoDia / 1e6 : pptoDia) : null;` | `var pptoPlot = (pptoDia != null) ? pptoDia : null;   // [BEQ]` |
| 4 | 2413 | `var promMesPlot = (promMesRef != null && promMesRef > 0) ? (esGas ? promMesRef / 1e6 : promMesRef) : null;` | `var promMesPlot = (promMesRef != null && promMesRef > 0) ? promMesRef : null;   // [BEQ]` |
| 5 | 2596 | `var yPlot = esGas ? valores.map(function (v) { return v == null ? null : v / 1e6; }) : valores;` | `var yPlot = valores;   // [BEQ]` |
| 6 | 2597 | `var refPlot = (esGas && ref) ? ref / 1e6 : ref;` | `var refPlot = ref;   // [BEQ]` |
| 7 | 2668 | `var esc1 = esGas ? 1e6 : 1;` | `var esc1 = 1;   // [BEQ] backend ya entrega kboepd` |
| 8 | 3124 | `return esGas ? (n / 1e6).toFixed(2).replace(".", ",") : __cnMilesEC(Math.round(n));` | `return __cnBeq(n);   // [BEQ] mismo formato para los tres productos` |
| 9 | 3252 | `var yPlot = esGas ? y.map(function (v) { return v == null ? null : v / 1e6; }) : y;` | `var yPlot = y;   // [BEQ]` |
| 10 | 3253 | `var promPlot = (esGas && prom) ? prom / 1e6 : prom;` | `var promPlot = prom;   // [BEQ]` |
| 11 | 4513 | `var esc1 = function (v) { return (v == null) ? null : (esGas ? v / 1e6 : v); };` | `var esc1 = function (v) { return v; };   // [BEQ]` |
| 12 | 4589 | (idéntico a 11) | (idéntico a 11) |
| 13 | 4646 | (idéntico a 11) | (idéntico a 11) |
| 14 | 4705 | (idéntico a 11) | (idéntico a 11) |

---

## 3.39 · MODIFICAR — `multitab_shell.js` — selectores de formato (H11, H13)

Todos pasan al formateador único. Por línea:

| Línea | LOCALIZAR | SUSTITUIR POR |
|---|---|---|
| 2375 | `var fmtD = esGas ? __cnGasM : function (v) { return __cnMilesEC(Math.round(v)); };` | `var fmtD = __cnBeq;   // [BEQ]` |
| 2409 | (idéntico) | (idéntico) |
| 2593 | (idéntico) | (idéntico) |
| 4512 | (idéntico) | (idéntico) |
| 4588 | (idéntico) | (idéntico) |
| 4645 | (idéntico) | (idéntico) |
| 4704 | (idéntico) | (idéntico) |
| 3011 | `var fmt = esGas ? function (v) { return __cnGasM(v); } : function (v) { return __cnMilesEC(Math.round(v)); };` | `var fmt = function (v) { return __cnMilesEC(Math.round(v)); };   // [BEQ] diferidas: bbl-eq enteros` |
| 3251 | `var fmtV = esGas ? __cnGasM : __cnFmtKpi;   // GAS en MSCF (÷1e6)` | `var fmtV = __cnBeq;   // [BEQ] kboepd` |
| 3619 | `var fmtV = esGas ? __cnGasM : __cnFmtKpi;                          // volumen mensual` | `var fmtV = __cnBeq;                                                 // [BEQ] kboepd` |
| 3620 | `var fmtR = esGas ? function (v) { return __cnGasM(v, 2); } : __cnFmtBopd;  // ritmo diario` | `var fmtR = __cnBeq;                                                 // [BEQ] kboepd` |
| 4797 | `var fmtV = esGas ? function (v) { return __cnGasM(v); } : function (v) { return __cnMilesEC(Math.round(v)); };` | `var fmtV = __cnBeq;   // [BEQ]` |
| 4836 | (idéntico a 4797) | (idéntico) |
| 6853 | `var bt = (a0.PROD === "GAS") ? __cnGasM(tj.brecha_abs) : __cnFmtKpi(tj.brecha_abs);` | `var bt = __cnBeq(tj.brecha_abs);   // [BEQ]` |
| 7857 | `return (String(prod).toUpperCase() === "GAS") ? __cnGasM(v) : __cnMilesEC(Math.round(v));` | `return __cnBeq(v);   // [BEQ]` |

Para **3766** y **3814** (dos líneas cada uno, empiezan por `var fmtV = esGas ? function (v) { return __cnGasM(v); }`): LOCALIZAR esa línea y la siguiente (que cierra con `: function (v) { ... };`), y SUSTITUIR el par por `    var fmtV = __cnBeq;   // [BEQ]`.

Para **4981** (`: (esGas ? function (v) { return __cnGasM(v); } : function (v) { return __cnMilesEC(Math.round(v)); });`): SUSTITUIR por `      : __cnBeq);   // [BEQ]`.

---

## 3.40 · MODIFICAR — `multitab_shell.js` — mapas `U` y rótulos (H12)

| Línea | LOCALIZAR | SUSTITUIR POR |
|---|---|---|
| 2347 | `var U = { CRUDO: "bbl", GAS: "MSCF", BLANCOS: "bbl" }[prod] \|\| "";` | `var U = "kboepd";   // [BEQ] los tres productos comparten unidad` |
| 3116 | `var U = { CRUDO: "bbl", GAS: "MSCF", BLANCOS: "bbl" }[prod] \|\| "";   // gas MSCF · crudo/blancos bbl` | `var U = "kboepd";   // [BEQ]` |
| 3249 | `var U = { CRUDO: "bbl", GAS: "MSCF", BLANCOS: "bbl" }[producto] \|\| "";` | `var U = "kboepd";   // [BEQ]` |
| 2890 | `var uni = esGas ? "MSCF" : "bbl";` | `var uni = "bbl-eq";   // [BEQ] diferidas: volumen perdido en barriles equivalentes` |
| 3010 | `var uni = esGas ? "MSCF" : "bbl";` | `var uni = "bbl-eq";   // [BEQ]` |
| 4545 | `title: { text: "Acumulado (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },` | `title: { text: "Acumulado (kbbl-eq)", font: { size: 11 } },   // [BEQ] volumen` |
| 4615 | `title: { text: "Producción (" + (esGas ? "MSCF" : unidad) + ")", font: { size: 11 } },` | `title: { text: "Producción (kboepd)", font: { size: 11 } },   // [BEQ]` |
| 4673 | (idéntico a 4615) | (idéntico) |
| 4733 | (idéntico a 4615) | (idéntico) |
| 7860 | `var u = (String(prod).toUpperCase() === "GAS") ? "MSCF" : "bbl";` | `var u = "kboepd";   // [BEQ]` |
| 3632 | `var duni = k.unidad === "bbl" ? "BOPD" : (k.unidad === "MSCF" ? "MSCFD" : (k.unidad ? k.unidad + "/d" : "/d"));` | `var duni = k.unidad \|\| "kboepd";   // [BEQ] la unidad YA es caudal diario: sin sufijo` |
| 7996 | `? '<div class="da__ritmo">ritmo promedio <b>' + __cnMilesEC(t.bopd_avg) + '</b> BOPD-avg</div>'` | `? '<div class="da__ritmo">ritmo promedio <b>' + __cnBeq(t.bopd_avg) + '</b> kboepd</div>'   // [BEQ]` |

---

## 3.41 · MODIFICAR — `multitab_shell.js` — sufijos `/día` y `/mes` (H10)

`kboepd` ya es un caudal: el sufijo se quita.

| Línea | LOCALIZAR (fragmento exacto) | SUSTITUIR POR |
|---|---|---|
| 2356 | `y: "Producción (" + (U \|\| "unidades") + "/día)" }` | `y: "Producción (" + (U \|\| "kboepd") + ")" }` |
| 2430 | `name: nombre + " · " + fmtD(valor) + uni + "/día",` | `name: nombre + " · " + fmtD(valor) + uni,` |
| 2439 | `text: refNom + " · " + fmtD(ref) + uni + "/día",` | `text: refNom + " · " + fmtD(ref) + uni,` |
| 2454 | `text: "PPTO · " + fmtD(pptoDia) + uni + "/día",` | `text: "PPTO · " + fmtD(pptoDia) + uni,` |
| 2467 | `text: "media del mes · " + fmtD(promMesRef) + uni + "/día",` | `text: "media del mes · " + fmtD(promMesRef) + uni,` |
| 2520 | `"%{customdata[0]}<br>%{customdata[1]}" + uni + "/día<extra></extra>"` | `"%{customdata[0]}<br>%{customdata[1]}" + uni + "<extra></extra>"` |
| 2605 | `"%{x}<br>%{customdata[0]}" + uni + "/mes%{customdata[1]}<extra></extra>"` | `"%{x}<br>%{customdata[0]}" + uni + "%{customdata[1]}<extra></extra>"` |
| 2611 | `text: (refTxt \|\| "promedio mensual") + " · " + fmtD(ref) + uni + "/mes",` | `text: (refTxt \|\| "promedio mensual") + " · " + fmtD(ref) + uni,` |
| 2837 | `{ x: "Mes", y: "Producción (" + unidad + "/mes)" });` | `{ x: "Mes", y: "Producción (" + unidad + ")" });` |
| 3256 | `return [fmtV(y[i]) + " " + U + "/mes", esProy[i]];` | `return [fmtV(y[i]) + " " + U, esProy[i]];` |
| 3262 | `+ " (" + fmtV(prom) + " " + U + "/mes)",` | `+ " (" + fmtV(prom) + " " + U + ")",` |
| 3621 | `var unidad = k.unidad ? (" " + esc(k.unidad) + "/mes") : "";` | `var unidad = k.unidad ? (" " + esc(k.unidad)) : "";   // [BEQ]` |
| 3640 | `figVal = fmtV(may) + ' <span class="cp-mes__kpi-unit">' + esc(k.unidad \|\| "") + '/mes</span>';` | `figVal = fmtV(may) + ' <span class="cp-mes__kpi-unit">' + esc(k.unidad \|\| "") + '</span>';` |
| 7861 | `return porMes ? (u + "/mes") : u;` | `return u;   // [BEQ] caudal: sin sufijo` |

> Para 2356 el fragmento está dentro de una línea más larga: LOCALIZAR solo el fragmento indicado y sustituirlo en su sitio.

---

## 3.42 · AÑADIR — `tests/test_unidades_beq.py` (archivo completo)

```python
"""tests/test_unidades_beq.py — blinda el contrato de unidades (plan v2).

Cifras de referencia medidas contra la BD local (reporte 148) y la lamina
"Produccion Equivalente G.E. 2026" (§1 H1-H6 del plan).
"""
import pytest

from app.core import unidades as u


def test_factor_gas_es_5_7():
    assert u.FACTOR_GAS_BEQ == 5.7


def test_bpd_m_entre_bpdeq_m_es_el_factor():
    """Medido en fact_produccion_mes_ecp abril 2026: bpd_m 516,9 / bpdeq_m 90,7."""
    assert 516.9 / 90.7 == pytest.approx(5.7, abs=0.01)


def test_a_beq_gas_si_crudo_blancos_no():
    assert u.a_beq(570.0, "GAS") == pytest.approx(100.0)
    assert u.a_beq(570.0, "gas") == pytest.approx(100.0)
    assert u.a_beq(570.0, "CRUDO") == pytest.approx(570.0)
    assert u.a_beq(570.0, "BLANCOS") == pytest.approx(570.0)
    assert u.a_beq(None, "GAS") is None


def test_kboepd_mes_solo_escala():
    """bpdeq_m ya es equivalente: solo /1000."""
    assert u.kboepd_mes(492_450.0) == pytest.approx(492.45)
    assert u.kboepd_mes(None) is None


def test_kboepd_dia_convierte_y_escala():
    # gas: 459_420 bpd brutos de un dia -> /5.7 /1000 = 80.6
    assert u.kboepd_dia(459_420.0, "GAS") == pytest.approx(80.6, abs=0.01)
    assert u.kboepd_dia(498_900.0, "CRUDO") == pytest.approx(498.9)


def test_unidad_es_kboepd_y_no_mscf():
    """Revierte la decision del 2026-07-21 (D3)."""
    assert u.UNIDAD == "kboepd"
    assert set(u.UNIDADES_PRODUCTO.values()) == {"kboepd"}
    assert u.UNIDAD_ACUM == "kbbl-eq"
    assert u.UNIDAD_DIF == "bbl-eq"


def test_conceptos_y_proceso():
    assert u.CONCEPTOS_SUMABLES == ("DERECO", "PROPIEDAD", "REGALIADISP")
    assert "MONETIZACION" not in u.CONCEPTOS_SUMABLES
    assert u.PROCESO_GAS == "VENTA-GRAVABLE"
    assert "VENTA-GRAVABLE" in u.SQL_PROCESO_GAS and "<> 'GAS'" in u.SQL_PROCESO_GAS


def test_formato_es_co():
    assert u.fmt(492.45) == "492,5"
    assert u.fmt(80.6) == "80,6"
    assert u.fmt(0.2) == "0,2"
    assert u.fmt(52430.9) == "52.430,9"
    assert u.fmt(-17.8) == "-17,8"


def test_acumulado_feb_abr_2026():
    """calendar.md §4: kboepd x dias. Medido: 52.430,9 kbbl-eq."""
    meses = [(591.0, 28), (593.4, 31), (582.9, 30)]
    assert sum(v * d for v, d in meses) == pytest.approx(52430.9, rel=1e-4)


def test_lamina_abril_2026():
    """Oraculo: DATOS_MES REAL abril = lamina = 582,9 kboepd."""
    assert 492.4 + 76.7 + 13.8 == pytest.approx(582.9, abs=0.05)
```

---

## 3.43 · AÑADIR — test de oráculo contra la BD (solo corre si hay BD)

Añadir **al final** de `tests/test_unidades_beq.py`:

```python
# ---------------------------------------------------------------------------------------------
# Oraculo contra la BD: la formula del plan reproduce DATOS_MES. Se salta si no hay conexion.
# ---------------------------------------------------------------------------------------------
def _bd():
    try:
        import sqlalchemy as sa
        from app.core.db import get_engine
        c = get_engine().connect()
        c.execute(sa.text("select 1"))
        return c
    except Exception:
        return None


@pytest.mark.skipif(_bd() is None, reason="sin BD")
def test_oraculo_fact_mes_vs_datos_mes():
    import sqlalchemy as sa
    c = _bd()
    rid = c.execute(sa.text("select max(reporte_id) from core.fact_tabla_hoja where hoja='DATOS_MES'")).scalar()
    if rid is None:
        pytest.skip("sin DATOS_MES cargada")
    ref = {r[0]: float(r[1]) / 1000 for r in c.execute(sa.text("""
        select dims->>'producto', sum(valor) from core.fact_tabla_hoja
        where hoja='DATOS_MES' and reporte_id=:r and dims->>'escenario'='REAL'
          and fecha=(select max(fecha) from core.fact_tabla_hoja
                     where hoja='DATOS_MES' and reporte_id=:r and dims->>'escenario'='REAL')
        group by 1"""), {"r": rid})}
    fact = {r[0]: float(r[1]) / 1000 for r in c.execute(sa.text(f"""
        select tp.nombre, sum(m.bpdeq_m) from core.fact_produccion_mes_ecp m
        join core.dim_tipo_producto tp on tp.tipo_producto_id=m.tipo_producto_id
        join core.dim_escenario es on es.escenario_id=m.escenario_id
        join core.dim_concepto co on co.concepto_id=m.concepto_id
        join core.dim_proceso pr on pr.proceso_id=m.proceso_id
        where m.reporte_id=:r and es.nombre='REAL' and m.grupo_prod='ECOPETROL'
          and {u.SQL_CONCEPTOS} and {u.SQL_PROCESO_GAS}
          and m.fecha=(select max(m2.fecha) from core.fact_produccion_mes_ecp m2
                       join core.dim_escenario e2 on e2.escenario_id=m2.escenario_id
                       where m2.reporte_id=:r and e2.nombre='REAL')
        group by 1"""), {"r": rid})}
    for p in ("CRUDO", "GAS"):
        assert fact[p] == pytest.approx(ref[p], abs=0.15), f"{p}: fact={fact[p]} DATOS_MES={ref[p]}"
```

---

# §4 · Orden de ejecución

| # | Acción | § |
|---|---|---|
| 1 | AÑADIR `app/core/unidades.py` | 3.1 |
| 2 | AÑADIR `tests/test_unidades_beq.py` (3.42 + 3.43) y **correr** `uv run pytest tests/test_unidades_beq.py -v` → 10 PASSED (+1 skip o pass) | 3.42-3.43 |
| 3 | `api.py`: import | 3.2 |
| 4-21 | `api.py`: los 18 bloques, **en orden de línea** 3.7 → 3.3 → 3.4 → 3.5 → 3.6 → 3.8 → 3.9 → 3.10 → 3.11 → 3.12 → 3.13 → 3.14 → 3.15 → 3.16 → 3.17 → 3.18 → 3.19 → 3.20 → 3.21 → 3.22 → 3.23 | |
| 22 | `ranking.py` | 3.24, 3.25 |
| 23 | `validador.py` | 3.26 |
| 24 | `slots.py` | 3.27 |
| 25 | `niveles.py` | 3.28 |
| 26 | `ejecutor.py` | 3.29, 3.30, 3.31 |
| 27 | `plantilla.py` | 3.32 |
| 28 | `p50_referencia.py` | 3.33 |
| 29 | `variables_cuantificables.yaml` | 3.34 |
| 30 | `diferidas.py` | 3.35 |
| 31 | **Correr** `uv run pytest tests/test_unidades_beq.py -v` y los imports de §6.1 V3-V5 | |
| 32 | `frontend/routes/api.py` | 3.36 |
| 33 | `multitab_shell.js`: `__cnBeq` **primero** | 3.37 |
| 34 | `multitab_shell.js`: divisiones, selectores, mapas, sufijos | 3.38 → 3.39 → 3.40 → 3.41 |
| 35 | **Correr** la suite completa y los greps de §6.1 | |

> Los pasos 4-21 se hacen **en la misma sesión, sin commit intermedio**: son los 21 lectores (H7). A medias, el sistema se contradice.

---

# §5 · Reglas no negociables

1. **JS en ES5 clásico.** `var` + `function`. Nada de arrow functions, template literals, `const`/`let`.
2. **Todo en español.**
3. **Si un `LOCALIZAR` no aparece literal, DETENERSE y reportar.** El plan se auditó contra el código del 2026-09-08; una desviación significa que el archivo cambió.
4. **Los 21 lectores (pasos 4-22) van juntos.** Ninguno se deja «para después».
5. **NO tocar** `_UNIDAD_VP`, `_fmt_vp`, `_kbpe`, `/president`, `p50_2026` (H17).
6. **NO tocar** `kpis_prod/api.py` (React), las vistas `vw_wa_*`, `frontend/chatbot/`, `master_prompts.yaml`, la ingesta ni el esquema SQL.
7. En los sitios con texto idéntico (3.11/3.14, 3.12/3.15, 3.13/3.16, 3.22/3.23, 3.31, 3.32, 3.38 #11-14, 3.39, 3.40 #4615/4673/4733), editar **por número de línea** y verificar con `grep -c` que solo cambió una ocurrencia. **Las líneas se desplazan** a medida que se edita: recalcular con `grep -n` antes de cada edición, no confiar en el número del plan.
8. **No arreglar los tests que rompen** (§6.1 V9): listarlos.
9. Al terminar, el estado es **«implementado, PENDIENTE de validación humana»**.

---

# §6 · Validación

## 6.1 Estática — EXECUTOR

| # | Comando (desde `backend\backend`) | Esperado |
|---|---|---|
| V1 | `uv run pytest tests/test_unidades_beq.py -v` | 10 PASSED; el oráculo PASSED (con BD) o SKIPPED |
| V2 | `uv run python -c "from app.core import unidades as u; print(u.UNIDAD, u.FACTOR_GAS_BEQ, u.PROCESO_GAS)"` | `kboepd 5.7 VENTA-GRAVABLE` |
| V3 | `uv run python -c "import app.features.analisis.api"` | sin error |
| V4 | `uv run python -c "import app.features.consulta_v2.cuantificar.validador, app.features.consulta_v2.cuantificar.ranking, app.features.consulta_v2.analizar.plantilla, app.features.consulta_v2.analizar.p50_referencia, app.features.consulta_v2.analizar.diferidas"` | sin error |
| V5 | `grep -c "SUM(m.volumen)" app/features/analisis/api.py app/features/consulta_v2/cuantificar/ranking.py` | **0 y 0** |
| V6 | `grep -c "SUM(d.volumen)" app/features/analisis/api.py` | **0** |
| V7 | `grep -rn '"MSCF"' app/features/` | sin resultados |
| V8 | `grep -c "1e6" ../../frontend/static/js/multitab_shell.js` | **≤ 6** (solo `__cnFmtKpi`, `__cnFmtBopd` y comentarios) |
| V9 | `grep -n 'GAS: "MSCF"\|esGas ? "MSCF"\|esGas ? __cnGasM' ../../frontend/static/js/multitab_shell.js` | sin resultados |
| V10 | `grep -n '/día"\|/mes"\|"/día\|"/mes' ../../frontend/static/js/multitab_shell.js` | sin resultados (salvo comentarios) |
| V11 | `uv run pytest tests/ -q` | ver nota |

> **Nota V11 — tests que rompen y es ESPERADO** (assertan `"MSCF"` o cifras en la escala vieja):
> `test_cuantificar.py` (219-263, 286-291) · `test_analizar_tendencia.py:138-143` · `test_analisis_tarjetas_kpi.py:44-50,68-69,83` · `test_curva_acumulada.py:269,330,341` · `test_analisis_focos_gap.py:59-65` · `test_analisis_focos_filiales.py:47` · `test_consulta_narracion.py` (motor v1) · `test_cuantificar_ranking.py` · `test_cuantificar_dia.py` · `test_p50_referencia.py:386` (el assert `"MSCF" not in txt` pasa trivialmente).
> El executor **los lista**, no los toca. El usuario decide si se actualizan las cifras esperadas.

## 6.2 Humana — USUARIO (navegador, F12 → Console en 0 errores)

> 🔴 R3: build verde ≠ feature verificada. La app real corre en el **servidor de pruebas**. En local, `map_campo_activo` está vacío (H18): H4 y H5 solo se validan en pruebas.

| # | Pregunta | Debe verse |
|---|---|---|
| H1 | «¿Cuánto crudo produjo Castilla?» | kboepd, ~la mitad de antes, **un** decimal |
| H2 | «¿Cuál es el acumulado de gas de Cusiana?» | `kbbl-eq`, con miles; NO `0,00`, NO `MSCF` |
| H3 | «Muéstrame la producción de GAS, mes a mes en PAUTO SUR» | texto, eje Y, anotación del promedio y nota al pie — **los cuatro** en kboepd, sin `/mes` |
| H4 | «Analiza el comportamiento de gas en Agosto 2026» | los **tres** sub-paneles de la fila coherentes: mismo orden de magnitud, mismo formato |
| H5 | «¿Cuál es el activo que más crudo produce?» | dot plot en kboepd |
| H6 | «¿Cuánto produjo X en los últimos 3 meses?» (en septiembre) | **junio–agosto**, 3 meses cerrados, en kbbl-eq |
| H7 | «¿Cuánto produjo X en agosto vs el operativo?» | cumplimiento razonable (no 0 % ni 10.000 %) |
| H8 | «¿Cuáles son las causas de las diferidas en Cusiana?» | volumen perdido en `bbl-eq` |
| H9 | Total ECP abril | **582,9 kboepd** = lámina |
| H10 | «¿Vamos a cerrar en meta?» | requerido y ritmo en kboepd, veredicto coherente con H1 |

---

# §7 · Fuera de alcance

| Qué | Por qué |
|---|---|
| **Jerarquía desde `ops.wells_attributes`** (objetivos 10-11, mapeo 91 %, alias GLH→GCH) | Servía para casar `DATOS_MES` con el catálogo. Con `fact_mes.bpdeq_m` no hace falta para este cambio (P3). El mapeo medido y el CSV quedan para su propio plan. |
| **BLANCOS mensual desde el diario** (P4) | Este plan deja blancos leyendo `bpdeq_m` (5,4 vs 13,8). Si P4 se aprueba, es un paso adicional en `desempeno` (Módulo 1) que sustituye el REAL de BLANCOS por `AVG` del diario del mes. Se especifica cuando el usuario decida. |
| **React `kpis_prod/api.py:11-14`** y **vistas `vw_wa_*`** (WhatsApp) | Siguen sumando 5 conceptos en `vol_estimado`. Inconsistentes con el chat hasta su propio plan (H19). |
| **`map_campo_activo` vacío en local** (H18) | Entorno, no código. Se repuebla con la migración 008 o desde `dim_fuente.activos`. |
| **«80,9 % del faltante · 2 campos»** (`api.py:1547` top-2 vs panel de 5) | Decisión del usuario: se deja. |
| **Doble eje de filiales** (`__cnFilSeriePlot:1681`) | Cosmético; con unidad única sobra, pero no rompe. |
| **Los tests rojos de V11** | El executor los lista; el usuario decide. |
| **`jerarquias_sup_error.md`** | Brecha anterior, sin relación. |

---

# Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee completo el plan
backend/Planes/plan_UNIDADES-BARRILES-EQUIVALENTES_20260908.md (v2)
y ejecutalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones al plan. Orden secuencial (§4).
- Si un LOCALIZAR no aparece LITERAL en el archivo, DETENTE y reporta: no adaptes el texto.
- Las lineas del plan son del 2026-09-08 y se desplazan al editar: antes de cada edicion
  en un sitio con texto repetido, recalcula la linea con grep -n y verifica con grep -c
  que solo cambio UNA ocurrencia.
- Los 21 lectores de la medida (pasos 4-22) van juntos, sin commit intermedio.
- NO arregles los tests que fallan en V11: listalos.
- NO toques nada de §7 ni de §5.5-5.6.

Reporta: ✅/❌ Paso N (una linea por paso).
Al final: archivos tocados + salida de V1-V10 + lista de tests rojos de V11
+ "Implementado, PENDIENTE de validacion humana (§6.2). ¿Hago commit?"
```
