# Plan: Tarjetas KPI de cierre (CRUDO/GAS/BLANCOS) — Nivel 1 del Análisis Ejecutivo

Fecha: 2026-07-21 · Modo: `plan:` (§0.1 CLAUDE.md de INGESTA) · Autor: Claude (auditoría, sin código aplicado)

Autocontenido: un agente sin contexto previo de esta conversación puede ejecutar este documento
al pie de la letra. Todas las rutas son absolutas.

---

## 0. Hallazgos de auditoría (§0.2 — LEER ANTES DE APROBAR)

La tarea de origen fijaba 2 reglas que la auditoría del código real contradice. No se puede
seguir la letra literal de esas reglas sin romper otra cosa, así que se documenta el hallazgo y
la resolución propuesta. **Esto requiere tu visto bueno explícito además del "¿Aprobado?" general.**

### Hallazgo A — `dim_tipo_producto` NO tiene columna de unidad

La regla 3 original pide: *"Unidad POR producto desde `dim_tipo_producto`"*. Verificado contra
`c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\db\ddl_v2_postgres.sql`
línea 127-130:

```sql
CREATE TABLE core.dim_tipo_producto (
    tipo_producto_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre            VARCHAR(50)  NOT NULL UNIQUE      -- CRUDO | GAS | BLANCOS
);
```

Solo tiene `nombre`. No hay `unidad` en ninguna tabla del esquema. Además, la unidad del GAS
lleva **pendiente sin confirmar desde 2026-07-15** (`backend/app/features/consulta/narracion.py`
línea 20: *"KPC/KPCD ambiguo hasta confirmar por spot-check → el prompt narra sin unidad si viene
vacía"*), y la bitácora del CLAUDE.md padre repite "unidad del GAS (KPC/KPCD)" como pendiente en
al menos 3 entradas (2026-07-15, 2026-07-16).

**Lectura de la regla 3:** "GAS = TODO visible" se interpreta aquí como **TO-DO visible** (un
pendiente declarado en la UI), no como un valor de unidad — coherente con "NO hardcodear 'bbl'
para Gas" y con el precedente de `narracion.py` de no fabricar unidad cuando no está confirmada.

**Resolución propuesta:** unidad por un diccionario Python **en código** (no en BD, no hay de
dónde leerla), y el frontend marca visiblemente el caso GAS como pendiente en vez de mostrar un
número desnudo o inventar una unidad:

```python
_UNIDADES_PRODUCTO = {"CRUDO": "bbl", "BLANCOS": "bbl", "GAS": None}
```

Si más adelante se confirma la unidad del GAS (spot-check pendiente), el cambio es de una línea
en este diccionario — no requiere migración.

### Hallazgo B — "formato compacto" choca con una decisión ya tomada en este mismo panel

La regla 5 pide *"número formateado compacto (Intl.NumberFormat / helper)"*. El código de
`static/js/multitab_shell.js` (líneas 1719-1726, comentario del commit del 2026-07-16) documenta
que este panel **YA probó** notación compacta (M/k) para las cifras de producción y la **revirtió**
dos veces porque escondía el dato real:

> *"primero todo se dividía por 1e6 con 1 decimal ('faltó 0,0 M' para 3.085 barriles: no
> informaba); luego M/k dinámico, que seguía redondeando ('faltó 1,0 M' escondía 21.211 barriles
> de los 1.021.211 reales)... Se acabó: aquí también va la cifra exacta."*

**Resolución propuesta:** usar el helper YA existente `__cnMilesEC()` (línea 1268 de
`multitab_shell.js`, `Number(n).toLocaleString("es-CO",{maximumFractionDigits:0})`) — cifra
EXACTA con separador de miles, sin notación M/k. Esto cumple la letra de la regla ("helper" —
la propia regla ofrece esa alternativa a Intl compact) y mantiene consistencia con el resto del
mismo panel (el gráfico de balance justo al lado, `__ejFmtVal`, usa el mismo criterio).

Si se prefiere notación compacta pese a este precedente, dilo explícitamente al aprobar — cambia
una función en el paso 3 de la Especificación.

---

## 1. Contexto

El panel "Análisis Ejecutivo (IA)" (pestaña Consulta → Desempeño del mes / Desempeño Filiales)
hoy abre con 3 "chips" de semáforo (uno por CRUDO/GAS/BLANCOS) que solo muestran el % de
cumplimiento y un texto corto (Alineado/Rezagado/Foco). Se piden en su lugar 3 **tarjetas KPI**
con barra de progreso, cifra de meta y microcopy explicativo, para comunicar de un vistazo cuánto
falta o sobra para la meta del mes — sin tocar el resto del panel (secciones de texto, gráficos
de respaldo por campo/filial).

El endpoint `GET /analisis/ejecutivo` (`ejecutivo()` para segmento ECP, `_ejecutivo_filiales()`
para segmento filiales) ya calcula `titular`: un array de 3 objetos
`{producto, real, ppto, valor_pct, estado, texto}` donde:
- `real` = la **proyección de cierre de mes** que trae el reporte (NO el acumulado a la fecha de
  corte — ver `backend/app/features/consulta/ejecucion.py` líneas 134-142 y el commit `7c47480`
  de la bitácora padre, que prueba que REAL mensual de meses cerrados = Σ curva diaria, y que en
  un mes en curso REAL/PPTO ya refleja el % de cierre proyectado, no el MTD).
- `ppto` = la meta del mes: PPTO (presupuesto) en segmento ECP, PROGRAMA en segmento filiales
  (mismo campo, distinto origen — ver comentario en `_fil_intermedios`, `analisis/api.py` ~L1573).

Las tarjetas nuevas se derivan de estos 2 números — no se ejecuta ninguna consulta SQL nueva.

## 2. Objetivo

Reemplazar los 3 chips-semáforo del encabezado del panel ejecutivo por 3 tarjetas KPI
(barra + meta + microcopy), con un eje de estado propio (alineado/ajustado/actuar) separado del
que ya usan los chips/tabs existentes, sin tocar el resto del panel ni crear endpoints nuevos.

## 3. Prerequisitos

- Backend corriendo: `cd c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`
  → `uv run uvicorn app.main:app --port 8000 --reload`
- App padre (Flask) corriendo en `:8020` (o `iniciar_backends.bat` desde la raíz del repo padre).
- BD Postgres `daily_report_prod` local con datos de al menos un mes cerrado o en curso con
  cierre mensual (para que `titular` no venga vacío — condición `sin_cierre` en `desempeno()`,
  ver H5 en la bitácora).
- Ningún cambio de DDL, ETL, ni endpoint nuevo. Solo Python (`analisis/api.py`), JS
  (`multitab_shell.js`), CSS (`colapsable.css`) y Settings (`config.py`).

## 4. Inventario de archivos

| Archivo | Acción |
|---|---|
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\core\config.py` | Añadir 1 setting |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | Añadir 3 funciones puras + 1 línea en 2 `return` existentes |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` | Reemplazar el bloque de `chips` por tarjetas; nueva función `__cnTarjetasKpiHtml` |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\css\colapsable.css` | Nuevas clases `.cn-kpi__*` |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\tests\test_analisis_tarjetas_kpi.py` | NUEVO — tests puros (sin BD/LLM), mismo estilo que `test_analisis_ejecutivo_tesis.py` |
| `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html` | Bump del cache-buster `?v=` de `multitab_shell.js`/`colapsable.css` |

No se toca `routes/api.py` (el proxy Flask `/api/analisis/ejecutivo` ya reenvía el JSON completo
sin filtrar campos — verificar que efectivamente no whitelist-ea claves antes de dar por sentado
que `tarjetas` llegará al frontend sin tocarlo).

## 5. Especificación

### 5.1 `config.py` — nuevo umbral (eje de estado PROPIO, no toca `_estado()`)

Insertar después de la línea `ejecutivo_fallback: bool = True` (línea 24) y antes de
`def get_settings()`:

```python
    # Tarjetas KPI de cierre (Nivel 1, plan_tarjetas_kpi_cierre_2026-07-21): eje de estado PROPIO
    # (alineado/ajustado/actuar), independiente de _estado() (L596 de analisis/api.py, que sirve
    # los chips/tabs existentes con otros umbrales — 90/75). Ámbar desde meta*0.93; rojo (actuar)
    # por debajo; verde (alineado) en o sobre la meta. Calibrado a ojo con mayo-2026 (Rubiales
    # 95.6% -> ajustado, APIAY 50.7% -> actuar); recalibrar aquí si hace falta, nunca en el código.
    kpi_cierre_ambar_pct: float = 0.93
```

### 5.2 `analisis/api.py` — 3 funciones puras nuevas

Insertar entre la línea 599 (`return "ok" if pct >= 90 else (...)`) y la línea 601
(`def _detectar_valle(serie):`), es decir justo después de `_estado()`:

```python
# ============================================================================
# Tarjetas KPI de cierre (Nivel 1 del panel ejecutivo) — plan_tarjetas_kpi_cierre_2026-07-21.
# Eje de estado PROPIO (alineado/ajustado/actuar), independiente de _estado() de arriba (que
# sigue sirviendo los chips/tabs existentes con sus propios umbrales 90/75 — NO SE TOCA).
# Unidad: dim_tipo_producto NO tiene columna de unidad (solo `nombre`, ver ddl_v2_postgres.sql
# L127-130) — se declara en código. GAS queda sin unidad confirmada (KPC/KPCD, ver
# consulta/narracion.py L20); se marca visible como pendiente, nunca se fabrica "bbl" para Gas.
# ============================================================================
_UNIDADES_PRODUCTO = {"CRUDO": "bbl", "BLANCOS": "bbl", "GAS": None}

def _estado_cierre(proyectado, meta):
    """alineado (>=meta) / ajustado (>=meta*umbral_ambar) / actuar (por debajo) / "" (sin meta)."""
    if not meta:
        return ""
    pct = proyectado / meta
    umbral = get_settings().kpi_cierre_ambar_pct
    if pct >= 1.0:
        return "alineado"
    if pct >= umbral:
        return "ajustado"
    return "actuar"

def _tarjetas_kpi(titular):
    """Tarjeta por producto para el Nivel 1. proyectado_cierre = t['real'] SIN recalcular:
    titular.real YA es la proyección de cierre del mes completo (ejecucion.py L134-142,
    commit 7c47480) -- sumarle días de más lo infla. Meta = t['ppto'] (PPTO en ECP, PROGRAMA
    en filiales -- mismo campo, ver _fil_intermedios). No redondea aquí: meta_mes/proyectado_cierre
    quedan crudos para que el frontend pueda verificar igualdad byte a byte contra titular.real
    (gate de no-divergencia); relleno_pct sí se redondea (es solo para el ancho de la barra)."""
    out = []
    for t in titular:
        producto = t["producto"]; meta = t.get("ppto") or 0.0; proy = t.get("real") or 0.0
        relleno = round(min(proy / meta, 1.0) * 100, 1) if meta else 0.0
        out.append({
            "producto": producto,
            "unidad": _UNIDADES_PRODUCTO.get(producto),
            "meta_mes": meta,
            "proyectado_cierre": proy,
            "brecha_abs": meta - proy,
            "relleno_pct": relleno,
            "alcanza": meta > 0 and proy >= meta,
            "estado": _estado_cierre(proy, meta),
            "metodo": "proyeccion_de_cierre_del_reporte",
        })
    return out
```

Agregar `"tarjetas": _tarjetas_kpi(titular),` a las 2 respuestas existentes:

**(a)** En el `return` de `ejecutivo()` (ECP), alrededor de la línea 1515-1523 — el dict actual es:

```python
        return {
            "entidad": entidad, "encontrada": True,
            "meta": {"scope": entidad or "Global (toda la producción ECP)",
                     "periodo": periodo, "corte": corte, "generado_por": generado,
                     "llm_diag": llm_diag},
            "titular": titular, "gap_por_producto": gap_full,   # gráficos: los 3 productos (F2)
            "valle": valle, "eventos": eventos, "eventos_extra": eventos_extra,
            "pace_crudo": pace, "flags": flags, "secciones": secciones,
        }
```

Añadir `"tarjetas": _tarjetas_kpi(titular),` en cualquier punto del dict (p. ej. justo después de
`"titular": titular,`).

**(b)** En el `return` de `_ejecutivo_filiales()`, alrededor de la línea 1888-1895 — el dict actual es:

```python
    return {
        "entidad": None, "encontrada": True,
        "meta": {"scope": _FIL_SCOPE, "periodo": periodo, "corte": corte,
                 "generado_por": generado, "llm_diag": llm_diag},
        "titular": titular, "gap_por_producto": gap_full,
        "valle": valle, "eventos": [], "eventos_extra": {"campos": 0, "pozos_aprox": 0},
        "pace_crudo": pace, "flags": flags, "secciones": secciones,
    }
```

Misma adición: `"tarjetas": _tarjetas_kpi(titular),` junto a `"titular": titular,`.

### 5.3 `static/js/multitab_shell.js` — reemplazo del bloque de chips

Función `__cnRenderEjecutivo(d)`. El bloque actual (líneas 1536-1541):

```javascript
    var chips = (d.titular || []).map(function (t) {
      var sem = __cnSemColor(t.valor_pct);
      var pct = (t.valor_pct == null) ? "—" : (t.valor_pct + "%");
      return '<div class="cn-ins__chip ' + sem + '"><div class="cn-ins__chip-top">' + esc(t.producto) + '</div>' +
        '<div class="cn-ins__chip-bot"><strong>' + esc(t.texto || "") + '</strong> · ' + pct + '</div></div>';
    }).join("");
```

se **elimina** (no se necesita `chips` en ningún otro punto de la función — verificado, solo se
consumía en la línea 1570).

La línea 1570 actual:

```javascript
      '<div class="cn-ins__chips">' + chips + '</div>';
```

se reemplaza por:

```javascript
      '<div class="cn-kpi__row">' + __cnTarjetasKpiHtml(d.tarjetas || []) + '</div>';
```

Nueva función, insertarla inmediatamente ANTES de `function __cnRenderEjecutivo(d) {` (línea 1534):

```javascript
  // Nivel 1: tarjetas KPI de cierre (barra + meta + microcopy), 1 por producto. Reemplaza los 3
  // chips-semáforo. proyectado_cierre/meta_mes ya vienen calculados del backend
  // (ejecutivo() -> _tarjetas_kpi) -- esta función SOLO formatea y pinta, 0 recálculo.
  // Formato de cifras: __cnMilesEC (exacto, separador de miles) -- NO notación compacta M/k
  // (este mismo panel ya la probó y la revirtió dos veces, ver __ejFmtVal más abajo en el archivo).
  function __cnTarjetasKpiHtml(tarjetas) {
    if (!tarjetas || !tarjetas.length) return "";
    return tarjetas.map(function (k) {
      var unidad = k.unidad ? (" " + esc(k.unidad)) : "";
      var sem = k.estado === "alineado" ? "is-ok" : (k.estado === "ajustado" ? "is-warn" :
                 (k.estado === "actuar" ? "is-bad" : ""));
      var pct = Math.round(k.relleno_pct == null ? 0 : k.relleno_pct);
      var micro;
      if (!k.meta_mes) {
        micro = "Sin meta definida para " + esc(k.producto.toLowerCase()) + ".";
      } else if (k.alcanza) {
        micro = "Superaría la meta por " + __cnMilesEC(k.proyectado_cierre - k.meta_mes) + unidad + ".";
      } else {
        micro = "Faltarían " + __cnMilesEC(k.brecha_abs) + unidad + " para la meta.";
      }
      var unidadNota = !k.unidad
        ? ' <span class="cn-kpi__unit-pend" title="Unidad de Gas por confirmar (KPC/KPCD)">unidad por confirmar</span>'
        : "";
      return '<div class="cn-kpi__card ' + sem + '">' +
        '<div class="cn-kpi__top">' + esc(k.producto) + unidadNota + '</div>' +
        '<div class="cn-kpi__bar"><div class="cn-kpi__fill" style="width:' + pct + '%"></div></div>' +
        '<div class="cn-kpi__nums">' + __cnMilesEC(k.proyectado_cierre) + unidad +
        '<span class="cn-kpi__of">de ' + __cnMilesEC(k.meta_mes) + unidad + '</span></div>' +
        '<div class="cn-kpi__micro">' + micro + '</div>' +
        '</div>';
    }).join("");
  }

```

Nota: `esc()` (línea 26) y `__cnMilesEC()` (línea 1268) ya existen en el mismo scope (misma IIFE)
— no requieren import ni redefinición.

### 5.4 `static/css/colapsable.css` — nuevas clases

Insertar después de la línea 1119 (`.cn-ins__chip-bot { ... }`), reusando los MISMOS tokens de
color que ya usa `.cn-ins__chip.is-ok/.is-warn/.is-bad` para no introducir una paleta nueva:

```css
.cn-kpi__row { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; padding: 8px 10px; }
@media (max-width: 900px) { .cn-kpi__row { grid-template-columns: 1fr; } }
.cn-kpi__card { border-radius: 8px; padding: 8px 10px; background: #f4f7f5; border-left: 3px solid #9aa7a0; }
.cn-kpi__card.is-ok { background: #eaf6ef; border-left-color: #1e9e63; }
.cn-kpi__card.is-warn { background: #fbf1e4; border-left-color: #E8912B; }
.cn-kpi__card.is-bad { background: #fbeaea; border-left-color: #d9534f; }
.cn-kpi__top { font-size: .68rem; font-weight: 700; letter-spacing: .04em; color: #6b7a72;
  text-transform: uppercase; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.cn-kpi__unit-pend { font-size: .6rem; font-weight: 600; text-transform: none; color: #8a6d1f;
  background: #fdf6e3; border-radius: 4px; padding: 1px 5px; cursor: help; }
.cn-kpi__bar { position: relative; height: 8px; border-radius: 4px; background: #e3e8e5;
  margin: 6px 0 4px; overflow: hidden; }
.cn-kpi__fill { height: 100%; border-radius: 4px; background: #9aa7a0; }
.cn-kpi__card.is-ok .cn-kpi__fill { background: #1e9e63; }
.cn-kpi__card.is-warn .cn-kpi__fill { background: #E8912B; }
.cn-kpi__card.is-bad .cn-kpi__fill { background: #d9534f; }
.cn-kpi__nums { font-size: .8rem; font-weight: 700; color: #2f3d36; }
.cn-kpi__of { font-weight: 500; color: #6b7a72; font-size: .7rem; margin-left: 4px; }
.cn-kpi__micro { font-size: .7rem; color: #5c6b63; margin-top: 2px; }
```

(`.cn-ins__chip*` NO se elimina: sigue habiendo semáforos con esa clase en otras vistas —
verificar con grep antes de borrar nada de la sección vieja; este plan solo AÑADE clases nuevas.)

### 5.5 Cache-buster

`templates/main.html` referencia `multitab_shell.js` y `colapsable.css` con `?v=<algo>` para
evitar caché del navegador (ver bitácora, patrón repetido en cada sesión de este panel). Localizar
las 2 líneas `<script src=".../multitab_shell.js?v=...">` y `<link ... colapsable.css?v=...">` e
incrementar el sufijo (p. ej. `?v=20260721a`).

### 5.6 Tests puros nuevos

`c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\tests\test_analisis_tarjetas_kpi.py`
(mismo estilo que `test_analisis_ejecutivo_tesis.py`: sin BD, sin LLM, import directo de las
funciones puras):

```python
"""Tests puros de las tarjetas KPI de cierre (plan_tarjetas_kpi_cierre_2026-07-21).
No tocan BD ni LLM."""
from app.features.analisis.api import _tarjetas_kpi, _estado_cierre, _UNIDADES_PRODUCTO


def _t(producto, real, ppto):
    return {"producto": producto, "real": real, "ppto": ppto, "valor_pct": None, "estado": "", "texto": ""}


def test_alineado_cuando_supera_meta():
    assert _estado_cierre(120, 100) == "alineado"


def test_ajustado_en_la_banda_ambar():
    assert _estado_cierre(95, 100) == "ajustado"   # 95% >= umbral 93%
    assert _estado_cierre(93, 100) == "ajustado"


def test_actuar_bajo_el_umbral_ambar():
    assert _estado_cierre(92.9, 100) == "actuar"
    assert _estado_cierre(50.7, 100) == "actuar"    # caso real APIAY


def test_sin_meta_no_es_actuar():
    """Meta 0 (producto sin PPTO/PROGRAMA) NO debe leerse como 'actuar' (rojo) -- neutral."""
    assert _estado_cierre(500, 0) == ""


def test_no_divergencia_proyectado_cierre_es_titular_real():
    titular = [_t("CRUDO", 12357703, 12928000)]
    tarjetas = _tarjetas_kpi(titular)
    assert tarjetas[0]["proyectado_cierre"] == titular[0]["real"]
    assert tarjetas[0]["meta_mes"] == titular[0]["ppto"]


def test_relleno_topa_en_100_sin_desbordar():
    titular = [_t("CRUDO", 150, 100)]
    t = _tarjetas_kpi(titular)[0]
    assert t["relleno_pct"] == 100.0
    assert t["alcanza"] is True
    assert t["brecha_abs"] == -50   # meta - proy, negativo = excedente


def test_unidad_crudo_blancos_bbl_gas_sin_confirmar():
    titular = [_t("CRUDO", 1, 1), _t("GAS", 1, 1), _t("BLANCOS", 1, 1)]
    tarjetas = _tarjetas_kpi(titular)
    by = {t["producto"]: t for t in tarjetas}
    assert by["CRUDO"]["unidad"] == "bbl"
    assert by["BLANCOS"]["unidad"] == "bbl"
    assert by["GAS"]["unidad"] is None   # NUNCA "bbl" para Gas


def test_producto_sin_meta_no_fabrica_cumplimiento():
    titular = [_t("GAS", 500, 0)]
    t = _tarjetas_kpi(titular)[0]
    assert t["alcanza"] is False
    assert t["estado"] == ""
    assert t["relleno_pct"] == 0.0
```

Ejecutar: `cd c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend && uv run pytest tests/test_analisis_tarjetas_kpi.py -v`
→ esperado: 8 passed.

## 6. Orden de ejecución

1. `config.py` (5.1) — no rompe nada, es aditivo.
2. `analisis/api.py` (5.2) — funciones puras + 2 líneas en los `return` existentes.
3. `test_analisis_tarjetas_kpi.py` (5.6) — correr, confirmar 8 passed, ANTES de tocar frontend.
4. `multitab_shell.js` (5.3) — reemplazo del bloque de chips + nueva función.
5. `colapsable.css` (5.4) — nuevas clases.
6. `main.html` (5.5) — bump cache-buster.
7. Reiniciar backend FastAPI (`--reload` ya lo hace solo) y refrescar el navegador con hard-reload.
8. Verificación manual en navegador (ver §8).

## 7. Reglas no negociables

1. `proyectado_cierre` de cada tarjeta = `titular.real` sin recalcular (nunca sumar
   `real_acum + prom_7d*dias`). Ver `ejecucion.py:134-142`, commit `7c47480`.
2. El estado de la tarjeta (alineado/ajustado/actuar) vive en `_estado_cierre()`, función NUEVA
   y separada. NO se toca `_estado()` (L596) ni sus consumidores (`__cnSemColor`, los tabs y el
   `cn-ejec__prod-hd` del gráfico de respaldo siguen usando `valor_pct`/`_estado()` tal cual).
3. Unidad por producto: diccionario en código (`_UNIDADES_PRODUCTO`), no en BD (no existe la
   columna — Hallazgo A). CRUDO/BLANCOS = `"bbl"`. GAS = `None`, y el frontend lo marca VISIBLE
   como "unidad por confirmar" — nunca se muestra ni se fabrica "bbl" para Gas.
4. Sobrecumplimiento: `relleno_pct` topa en 100 (`min(proy/meta,1)*100`) sin desbordar la barra;
   color verde (`is-ok`, ya que `alcanza=true` implica `estado="alineado"`); microcopy
   "Superaría la meta por {excedente} {unidad}."
5. Cifras con separador de miles vía `__cnMilesEC()` (Hallazgo B) — nunca notación compacta M/k
   para estos números (precedente documentado en el propio archivo, líneas 1719-1726).

## 8. Validaciones (gate)

**G1 — No-divergencia (automatizable, backend):** los 8 tests de `test_analisis_tarjetas_kpi.py`
pasan, en particular `test_no_divergencia_proyectado_cierre_es_titular_real`.

**G2 — No-divergencia end-to-end (navegador, consola):**
```js
fetch('/api/analisis/ejecutivo?entidad=RUBIALES').then(r=>r.json()).then(d=>{
  console.log(d.tarjetas, d.titular);
  d.tarjetas.forEach(k => {
    var t = d.titular.find(x => x.producto === k.producto);
    console.assert(k.proyectado_cierre === t.real, 'diverge en ' + k.producto);
  });
});
```
0 asserts fallidos esperado.

**G3 — Visual (navegador real, pestaña Consulta → analizar una entidad con cierre mensual):**
- Renderizan 3 tarjetas (no 3 chips) en el encabezado del panel ejecutivo.
- Colores: verde/ámbar/rojo consistentes con `estado`.
- Barra no desborda el contenedor en un caso de sobrecumplimiento (buscar una entidad/mes con
  algún producto ≥100% del PPTO/PROGRAMA, o forzar con datos de prueba).
- Microcopy correcto en los 4 casos: alineado (superaría), ajustado (aún falta poco), actuar
  (falta bastante), sin meta (declarado, no fabricado).
- GAS muestra el badge "unidad por confirmar"; CRUDO/BLANCOS muestran "bbl".
- ⚠️ **Esperado, no es regresión:** el badge NUEVO puede decir "ajustado" para un producto que el
  chip/tab VIEJO (todavía visible en pestañas/gráficos, `_estado()`) sigue llamando "Alineado" —
  son ejes distintos con umbrales distintos a propósito (90/75 vs 93). Ejemplo conocido: Rubiales
  95.6% del PPTO → chip viejo "Alineado" (>=90), tarjeta nueva "ajustado" (<100, >=93×meta). No
  reportar esto como bug.

**G4 — No regresión del resto del panel:** secciones (Insights/Oportunidades/Puntos de
atención/Decisiones), gráficos de respaldo por campo/filial (bullet + divergente) y el panel de
error de Gemma (`generado_por==="error"`) renderizan igual que antes — 0 cambios fuera de lo
especificado en §5.

**G5 — pytest completo sin regresión:**
`cd .../backend && uv run pytest -q` → mismo conteo previo + 8 tests nuevos, 0 fallos nuevos.

## 9. Fuera de alcance

- Confirmar la unidad real del GAS (KPC vs KPCD) — sigue pendiente, declarado explícitamente en
  el frontend en vez de resuelto.
- Añadir una columna `unidad` a `dim_tipo_producto` (tocaría DDL → dispararía §0.2 completo,
  fuera del alcance de este plan de UI).
- Migrar `_estado()`/los chips/tabs viejos al nuevo eje de umbrales — quedan intactos.
- Tarjetas para segmentos distintos de ECP/Filiales (no existen otros).
- Recalibrar el umbral 0.93 con datos reales de mayo más allá de una revisión visual manual (no
  hay un dataset de referencia versionado para un test de regresión numérica de este umbral).

---

**¿Aprobado?** Responde con el visto bueno explícito a los Hallazgos A y B (§0) además de al
resto del plan, o indica qué cambiar antes de que el Executor implemente.
