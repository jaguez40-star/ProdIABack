# Plan de ejecución — Analizar · FASE 3 (Economía — EBITDA/NOPAT vía robustez, envolver el waterfall)

> **Tablas: N/A** — no toca ingesta/ETL/DDL. Envuelve un endpoint ya existente (`/ebitda/unificado-waterfall`)
> + lee 2 tablas de mapeo ya existentes (`core.map_campo_robustez`, `core.map_campo_activo`).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Motor Q v2 · Analizar **Fase 1 CERRADA** (causal + proyección, `8c08680`) + **Fase 2
> CERRADA** (diferidas, `cb8e45b`, verificada en navegador). Esta Fase 3 conecta la sub-intención
> **economía** (hoy un stub "próxima fase") al EBITDA Inspector real.
>
> **Diseño base:** `INGESTA/Rep_Prod/analiza.md` §3/§11 (economía = "vía robustez, EBITDA/aceite,
> rotulado universo robustez"). ⚠️ Este plan **corrige DOS premisas desactualizadas** de `analiza.md`
> (H1: no existe `ejecutor_robustez.py` compartido con Cuantificar; H2: NOPAT sí está soportado) — ver §0.
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario, INVIOLABLE):** NO usar el LLM local de dev ni levantar
> la app en dev. En dev: solo `py_compile` y pruebas de DATOS puntuales (Postgres ProdIA + Postgres ops)
> en procesos AISLADOS (uno a la vez). pytest completo, golden y navegador → **servidor de pruebas**.
>
> **Fecha:** 2026-08-03 · **Estado:** v2 AUDITADO (§0 + §0.1, verificado contra la BD real) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (verificados 2026-08-03, con línea + datos reales)

| # | Hallazgo (verificado) | Efecto en el plan |
|---|-----------------------|-------------------|
| **H1 · "comparte `ejecutor_robustez.py` con Cuantificar" es FALSO** 🔴🔴 | `analiza.md §11` dice que Fase 3 "comparte `ejecutor_robustez.py` con Cuantificar". **Ese archivo NO existe** y **Cuantificar NO usa robustez** para nada (usa `analisis.desempeno` + `analisis.escenario_mes`, verificado en `cuantificar/ejecutor.py`). El lector REAL de EBITDA es la **feature `ebitda`**: `backend/app/features/ebitda/api.py::unificado_waterfall` (endpoint `GET /ebitda/unificado-waterfall`, registrado en `main.py:15,34`), que lee la BD ops (robustez) y produce el waterfall Ingresos→EBITDA→EBIT→NOPAT. | **Se ENVUELVE `unificado_waterfall`** por import directo con args explícitos (MISMO patrón que Fase 1 con `ejecutivo`: misma app FastAPI, sin HTTP). NO se crea ningún `ejecutor_robustez.py`, NO se toca la feature `ebitda`. |
| **H2 · NOPAT SÍ está soportado (`analiza.md §10` desactualizado)** | `analiza.md §10` lista "impacto económico / margen / NOPAT" como NO soportado ("sin modelo económico en INGESTA"). Pero el waterfall (`ebitda/api.py:36`) YA devuelve `util_neta` (= NOPAT), `ebitda`, `util_oper` (EBIT), `ingresos`, cada uno en `value_kusd` + `value_usd_bl`. Verificado en vivo: global mayo-2026 → EBITDA 703.669 kUSD, NOPAT 334.325 kUSD. | Fase 3 SÍ entrega EBITDA + NOPAT + margen. `analiza.md §10` se corrige al cerrar (nota en bitácora). |
| **H3 · el nombre robustez (`rob_field`) ≠ campo INGESTA en general** 🔴 | El waterfall filtra por `wells_attributes.active`/`field` (nombres de **robustez**), NO por el nombre de INGESTA. En Castilla/Rubiales coinciden (`rob_field='CASTILLA'/'RUBIALES'`, verificado), **pero no se puede asumir** (S28 documentó discrepancias: KIMERA→CPO-09, GIGANTE→NEIVA…). El puente es `core.map_campo_robustez` (`campo → rob_field/rob_activo`, PK `campo`, migración de S28). | Fase 3 **traduce** la entidad INGESTA → `rob_field` vía `core.map_campo_robustez` ANTES de llamar al waterfall. NUNCA pasa el nombre INGESTA crudo. |
| **H4 · cobertura 80/139 campos; terceros y 1 ECP sin reconciliar** 🔴 | Verificado: `core.map_campo_robustez` tiene 139 filas, **81 `es_ecp=true`**, **80 con `rob_field NOT NULL`** (1 ECP sin reconciliar = ORIPAYA, S28). Caño Limón → `es_ecp=false, rob_field=NULL` (tercero: SierraCol/Cepcolsa/… no están en robustez POR DISEÑO). | Si la entidad no reconcilia a NINGÚN `rob_field` (tercero o sin robustez) → **declinar honesto** ("no está en el universo de rentabilidad, que solo cubre campos operados por ECP"). Si un **activo mezcla** ECP + terceros → usar los ECP y **AVISAR** de los omitidos. |
| **H5 · el waterfall es CRUDO/aceite solamente** | `ebitda/api.py:122` fija `meta.producto="CRUDO"`; `revenue_oil_real`, `total_bbl_blend` → todo es aceite. No hay EBITDA de gas/blancos. | La respuesta lo **rotula** ("rentabilidad del crudo operado por ECP"). Preguntar EBITDA de gas/blancos: no existe la fuente — se declara. |
| **H6 · el período lo resuelve el propio waterfall (alineado con el tablero)** | Con `year=None, month=None`, `unificado_waterfall` llama `_ultimo_mes_prodia()` → último mes con REAL en `fact_produccion_mes_ecp` (mayo-2026, verificado). Es el MISMO criterio de período que `desempeno`/`ejecutivo` → coherencia con el resto del chat. | Fase 3 llama SIEMPRE con `year=None, month=None` (hereda el período del tablero). El mes se lee del `meta` que devuelve el waterfall (para rotular). |
| **H7 · en 139 `ops_database_url` puede estar vacía → el waterfall lanza HTTPException** 🔴 | `get_ops_engine()` (`core/db.py:22`) lanza `RuntimeError` si `OPS_DATABASE_URL` no está; `unificado_waterfall` (`ebitda/api.py:98`) lo captura y **relanza `HTTPException(503)`**. En dev SÍ está configurada (verificado: la key existe en el `.env`). En 139 puede no estarlo. | El wrapper de Fase 3 **captura CUALQUIER excepción** del waterfall y devuelve `{sin_datos:True, motivo}` — el chat degrada honesto ("no tengo la base de rentabilidad disponible"), NUNCA propaga un 503/500. |
| **H8 · el subrouter YA detecta "economia"; el early-return está ANTES de resolver entidad** | `analizar/subrouter.py:12,19` → `_ECON=("EBITDA","NOPAT","MARGEN","RENTABILIDAD","PLATA")` → `economia`. En `respuesta_analizar.py` (Fase 2), `if sub == "economia": return "…próxima fase…"` está ANTES de la resolución de entidad (economía no la necesitaba). Fase 3 SÍ la necesita (para el `rob_field`). | Igual que FB-5 hizo con diferidas: **mover** economía DESPUÉS de la resolución de entidad, reusando el MISMO bloque (ambiguo/filial/irresoluble/global). El subrouter NO se toca. |

### 0.1 Segunda ronda de auditoría (adversarial · 2026-08-03) — reformulación

| # | Incoherencia/riesgo detectado | Reformulación |
|---|-------------------------------|---------------|
| **EC-1 · sin riesgo circular** ✅ | Verificado: `ebitda/api.py` importa solo `fastapi`, `sqlalchemy`, `app.core.db` — **NO importa `consulta_v2`**. Añadir `economia.py → ebitda.api` no crea ciclo. El import es de una función (no ejecuta nada al importarse). | Sin cambios; confirmado seguro (igual que `respuesta_analizar → analisis.api` en Fase 1). |
| **EC-2 · degradar como diferidas, no propagar la HTTPException** 🟠 | Mi 1ª idea llamaba `unificado_waterfall` y dejaba que la `HTTPException(503)` subiera. En el contexto del chat (no un endpoint REST), esa excepción reventaría el pipeline de `maquina_q`. | El wrapper `impacto_economico()` devuelve el MISMO contrato que `diferidas.impacto_historico`: `{sin_datos:True, motivo}` / `{sin_datos:False, waterfall:{...}}`, capturando `except Exception`. La plantilla ramifica por `sin_datos` (idéntico a diferidas). |
| **EC-3 · dos fuentes para "campos de un activo" (deuda menor, NO bloqueante)** 🟡 | `diferidas.py` (Fase 2) obtiene los campos de un activo del **CSV** `Activo_campo.csv`; `economia.py` (Fase 3) los obtiene de la **tabla** `core.map_campo_activo` (BD). Ambas se sembraron de la misma fuente (migración 008), así que coinciden hoy — pero son dos caminos. | economía usa la **tabla** (no el CSV): trabaja en el espacio robustez y necesita el join a `map_campo_robustez` de todas formas, así que un solo query BD (activo→campos→rob_field) es lo natural y evita leer un CSV para robustez. Se DECLARA la deuda; unificar las dos fuentes queda para una limpieza posterior. |
| **EC-4 · período = MES puntual, no acumulado** 🟡 | El waterfall da el EBITDA del MES (mayo-2026), no el acumulado del año. Un gerente podría esperar el YTD. | Coherente con el resto del chat (Desempeño/causal/proyección son del mes). Se **rotula el mes** en la respuesta; el EBITDA acumulado del año queda en §9 (fuera de alcance, fase posterior). |
| **EC-5 · niveles soportados = campo/activo/global (declina gerencia/VP)** 🟡 | El waterfall soporta `nivel in (activo, campo)` + global. `robustez` SÍ tiene `rob_gerencia`/`rob_vicepresidencia`, así que gerencia/VP serían factibles agregando campos — pero es alcance nuevo. | Fase 3 mantiene **campo/activo/global** y **declina** gerencia/VP/operador/fuente (mismo criterio que diferidas Fase 2, función pura `nivel_soportado`). Gerencia/VP = extensión futura documentada. |
| **EC-6 · el margen puede ser negativo (informativo, no error)** ✅ | `margen = ebitda/ingresos*100`. Si un campo pierde plata, `ebitda<0` → margen negativo. Es un dato válido, no un fallo. `ingresos<=0` → margen `None` (no se muestra). | Sin cambios; la plantilla ya maneja `margen None`. |

### 0.2 TERCERA ronda — auditoría de DATOS contra la BD real (2026-08-03) · 🔴 2 fallos críticos en la v1 de ESTE plan

| # | Incoherencia detectada (verificada con datos reales) | Reformulación |
|---|------------------------------------------------------|---------------|
| **EC-7 · la cobertura parcial NO es marginal: es MASIVA — el aviso al pie MIENTE por omisión** 🔴🔴 | Medido en la BD: hay **8+ activos MIXTOS** y la omisión es brutal, no residual: **NARE 1 de 8 campos** con `rob_field` (12%), **LISAMA 1/6**, **NORORIENTE 1/5**, **SURIA 5/10**, **CASABE 3/5**, **OCCIDENTE 5/7**. Y **NARE y OCCIDENTE resuelven a `nivel='activo'`** (verificado) → esa ruta ES alcanzable justo con los peores casos. Mi v1 ponía la cobertura como **footnote al final** ("⚠️ 7 campo(s) … no se incluyen"): un gerente lee **«EBITDA de NARE = X»** cuando X es **1/8 del activo**. Es EXACTAMENTE el bug clase-APIAY de S23 (`dim_fuente.activos` agrupaba 13 campos en vez de 4 → «1.320.996 bl / 92.5% ERRÓNEO») y viola el precedente **D-A4 (rollup honesto)**, que obliga a DECLARAR lo que falta en vez de servir un agregado incompleto como si fuera el total. | **La cobertura sube a la CABECERA, no al pie.** Cuando `omitidos>0`: (a) 1ª línea del cuerpo = `⚠️ COBERTURA PARCIAL: N de M campos`; (b) se **NOMBRAN los campos incluidos** (son ≤10, es verificable por el usuario); (c) el titular de cifras dice explícitamente «de esos N campos», nunca «de {entidad}» a secas. Sin umbral mágico de rechazo: se **declara siempre y de forma prominente**, que es lo que D-A4 hizo con los 15 campos sin meta. |
| **EC-8 · la respuesta NO dice el NIVEL → ambigüedad Campo vs Activo (viola D-A5)** 🔴 | Verificado: `resolver_unico("APIAY")` → **`nivel='campo'`** (+`zoom` a activo), NO activo. Igual CASTILLA, SURIA, CASABE. Por **D-D5 (prioridad Campo)**, un nombre que es Campo y Activo resuelve a **Campo**. Consecuencias: (1) mi v1 rotulaba solo «APIAY», y **D-A5 existe precisamente porque «el Campo APIAY» (269.035 bl/50.7%) y «el Activo APIAY» (577.362 bl/108.8%) son indistinguibles sin el nivel**; (2) mi V6 afirmaba que *«rentabilidad de Apiay» → cifras del activo (4 campos)* — **es FALSO**, dará el Campo APIAY (1 campo). El plan estaba validando contra una expectativa incorrecta. | (a) La plantilla recibe `nivel` y la etiqueta dice **«el Campo APIAY»/«el Activo NARE»** (D-A5). (b) Los casos de prueba de la ruta ACTIVO usan nombres que **solo** son activo (**NARE** mixto 1/8, **OCCIDENTE** 5/7); los de cobertura COMPLETA usan **APIAY como activo** solo si se llega por `nivel='activo'` (verificado 4/4). (c) V6 corregido. |
| **EC-9 · el label GLOBAL sobre-promete** 🟡 | Sin entidad, el waterfall agrega **todo el universo robustez** (~80 campos ECP-operados), pero mi v1 rotulaba `"Global (toda la producción ECP)"` — que es la voz de causal/proyección, donde global sí son los 139 campos de INGESTA. Aquí NO es lo mismo. | El scope global de economía se rotula **«Global · universo robustez (crudo operado por Ecopetrol)»**. Se acepta la divergencia deliberada con FC-4 porque el conjunto REALMENTE es otro; el rótulo lo dice. |
| **EC-10 · campo sin fila en `map_campo_robustez` (no solo `rob_field` NULL)** ✅ | Medido: hay ~8 campos de `dim_fuente` sin fila en la tabla (además de los 58 con `es_ecp=false`). `rob_fields_de` devuelve entonces `([], 0)` — `total=0`, no `total=1`. | La guarda `if ent_valor and not rob_fields → declinar` ya cubre ambos casos con el mismo mensaje honesto. Sin cambios de código; se documenta para que el Executor no lo lea como bug. |

---

## 1. Contexto

Motor Q v2 · Grupo 3 (Analizar), Fase 3. Edificio SEPARADO (`consulta_v2/`), cero imports de `consulta/`
v1. **Regla madre (idéntica a Fases 1-2):** Python calcula y decide; el LLM solo redacta el intro. El
motor de rentabilidad (`ebitda.unificado_waterfall`) ya reconcilia el waterfall completo desde robustez
y corre en dev — la coherencia es por reuso (misma función que el EBITDA Inspector visual). Economía es
"envolver + traducir la entidad", no "construir".

## 2. Objetivo

Que preguntas como *"¿cuál es el EBITDA de Castilla?"*, *"¿cómo va la rentabilidad de Apiay?"* o
*"¿el NOPAT del mes?"* respondan con **EBITDA + NOPAT + margen** (universo robustez, crudo operado por
ECP, mes vigente), **rotulado** como tal. Si la entidad es un tercero / no reconcilia / el nivel no es
campo-activo / la BD de robustez no está disponible: la respuesta lo **declara honestamente**, nunca
inventa cifras. Si un activo mezcla campos ECP y terceros, usa los ECP y **avisa** de los omitidos.

## 3. Prerequisitos

- Motor Q v2 + Analizar Fases 1-2 presentes (`cb8e45b`).
- Backend en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`
  (`uv run python` desde `backend/`, con `PYTHONPATH="."`).
- Feature `ebitda` operativa (`GET /ebitda/unificado-waterfall`, ya registrada). BD ops (robustez)
  accesible vía `OPS_DATABASE_URL` (en dev SÍ; en 139 puede faltar — el código debe degradar).
- Tablas `core.map_campo_robustez` (S28) y `core.map_campo_activo` (migración 008) cargadas en la BD.

## 4. Inventario de archivos

Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2`

| Acción | Ruta |
|--------|------|
| CREAR | `...\consulta_v2\analizar\economia.py` — traduce entidad→rob_field + envuelve el waterfall (H1/H3/H4/H7) |
| EDITAR | `...\consulta_v2\analizar\plantilla.py` — añadir `economia(d, entidad, omitidos)` |
| EDITAR | `...\consulta_v2\respuesta_analizar.py` — mover economía tras la resolución de entidad (H8) + rama |
| EDITAR | `...\consulta_v2\golden\analizar_golden.yaml` — +1 caso economía (rentabilidad/NOPAT) |
| EDITAR | `...\backend\tests\test_analizar.py` — +6 tests (con datos / sin ops / tercero / nivel no soportado / omitidos / nivel_soportado puro) |
| NO TOCAR | `backend/app/features/ebitda/*` (se IMPORTA `unificado_waterfall`, no se modifica), `analisis/api.py`, `cuantificar/*` (solo se IMPORTA `resolver`), `analizar/subrouter.py` (ya detecta economía — H8), `analizar/diferidas.py`, frontend (backend-only, AF-A8) |

## 5. Especificación (código de referencia)

### 5.1 — `analizar/economia.py` (CREAR)

```python
"""analizar/economia.py — EBITDA/NOPAT por entidad (universo robustez), Analizar Fase 3.

Envuelve el EBITDA Inspector (feature `ebitda`, MISMO backend FastAPI) por import directo de
unificado_waterfall con args explícitos — patrón de Fase 1 con `ejecutivo`, NO HTTP (H1). El lector de
robustez ya existe y corre; aquí solo se TRADUCE la entidad INGESTA a nombres robustez (rob_field) y
se degrada con honestidad.

Level-shift (H3): rob_field != campo INGESTA en general -> se mapea vía core.map_campo_robustez. Solo
ECP-operado (H4): 80/139 campos reconcilian; terceros (es_ecp=false) y 1 ECP sin robustez -> se
declaran, no se inventan. El waterfall es CRUDO/aceite (H5); período = mes vigente del tablero (H6).
"""
import sqlalchemy as sa

from app.core.db import get_engine
from app.features.ebitda.api import unificado_waterfall as _waterfall_ep

_NIVELES_OK = (None, "campo", "activo")   # None = global (sin filtro)


def nivel_soportado(nivel: str | None) -> bool:
    """El waterfall solo filtra por campo/activo (o global). gerencia/VP/operador/fuente -> False
    (mismo criterio que diferidas.nivel_soportado; gerencia/VP = extensión futura, EC-5)."""
    return nivel in _NIVELES_OK


def rob_fields_de(nivel: str | None, valor: str | None) -> tuple[list[str], int]:
    """Traduce la entidad INGESTA a nombres de robustez (rob_field). Devuelve (rob_fields, total):
      - rob_fields: los rob_field NOT NULL del alcance (campos ECP que reconcilian con robustez).
      - total:      cuántos campos tiene el alcance en INGESTA (para declarar la cobertura, EC-7).
    El llamador calcula `omitidos = total - len(rob_fields)`.

    🔑 EC-7: `total` NO es cosmético. Hay activos donde la cobertura es brutalmente parcial (NARE 1 de
    8 campos, LISAMA 1/6, SURIA 5/10 — medido). Servir el EBITDA de 1 campo como «el EBITDA de NARE»
    sería el bug clase-APIAY de S23; por eso la cobertura viaja y se declara EN CABECERA.

    valor None (global) -> ([], 0): sin filtro, el waterfall agrega todo el universo robustez.
    EC-10: un campo sin FILA en map_campo_robustez da ([], 0) igual que un tercero -> misma declinación.
    Solo lee la BD de ProdIA (no toca ops)."""
    if not valor:
        return [], 0
    eng = get_engine()
    with eng.connect() as c:
        if nivel == "activo":
            # activo INGESTA -> sus campos (map_campo_activo) -> rob_field (map_campo_robustez).
            # Se traduce campo por campo (no se usa `rob_activo`): el activo del usuario es el de
            # INGESTA, y S28 documentó que los conjuntos de robustez pueden diferir.
            rows = c.execute(sa.text(
                "SELECT mcr.rob_field FROM core.map_campo_activo mca "
                "LEFT JOIN core.map_campo_robustez mcr ON mcr.campo_norm = mca.campo_norm "
                "WHERE UPPER(TRIM(mca.activo)) = UPPER(TRIM(:v))"), {"v": valor}).all()
        else:   # campo (otros niveles ya los filtró nivel_soportado aguas arriba)
            rows = c.execute(sa.text(
                "SELECT rob_field FROM core.map_campo_robustez "
                "WHERE UPPER(TRIM(campo)) = UPPER(TRIM(:v))"), {"v": valor}).all()
    rob_fields = [r[0] for r in rows if r[0]]      # rob_field NOT NULL = reconcilia con robustez
    return rob_fields, len(rows)


def impacto_economico(rob_fields: list[str] | None) -> dict:
    """Llama el EBITDA Inspector (mismo backend). rob_fields=[] o None -> global. year/month=None ->
    el inspector usa el ULTIMO mes REAL de ProdIA (H6, alineado con el tablero).

    Retorno (mismo contrato que diferidas.impacto_historico):
      {"sin_datos": True, "motivo": "..."}                 -- ops no disponible o error (H7)
      {"sin_datos": False, "waterfall": {...}}             -- con datos (dict de unificado_waterfall)

    SIEMPRE degrada (nunca lanza): captura la HTTPException(503) que unificado_waterfall relanza
    cuando OPS_DATABASE_URL falta (EC-2)."""
    entidad = "|".join(rob_fields) if rob_fields else None
    nivel = "campo" if rob_fields else None
    try:
        w = _waterfall_ep(year=None, month=None, nivel=nivel, entidad=entidad)
        return {"sin_datos": False, "waterfall": w}
    except Exception as e:
        return {"sin_datos": True, "motivo": f"BD de rentabilidad (robustez) no disponible: {e}"}
```

### 5.2 — `analizar/plantilla.py` (EDITAR — añadir `economia`)

Añadir al final del archivo (reusa `_MES` ya definido en Fase 1; helpers `_kusd`/`_usdbl` nuevos, locales):

```python
def _kusd(n) -> str:
    """Miles de USD, es-CO (703669 -> '703.669'). Sin decimales."""
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def _usdbl(n) -> str:
    """USD/BI con 2 decimales, coma es-CO (46.38 -> '46,38')."""
    try:
        return f"{float(n):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    except Exception:
        return str(n)


# D-A5 (S23): decir el NIVEL. "el Campo APIAY" y "el Activo APIAY" son cifras DISTINTAS y sin el
# nivel son indistinguibles. Por D-D5 un nombre que es Campo y Activo resuelve a Campo (EC-8).
_NIVEL_TXT = {"campo": "el Campo", "activo": "el Activo"}


def economia(d: dict, entidad: str | None, nivel: str | None = None,
             incluidos: list | None = None, total: int = 0) -> str:
    """EBITDA/NOPAT/margen desde el waterfall del EBITDA Inspector (universo robustez, crudo ECP).

    ROTULA: nivel + entidad (D-A5/EC-8), alcance real (robustez · crudo ECP · mes) y —si la cobertura
    es parcial— lo DECLARA EN CABECERA nombrando los campos incluidos (EC-7: NARE es 1 de 8 campos;
    un footnote convertiría esa cifra en un engaño). Degrada honesto si no hay ops (H7)."""
    incluidos = incluidos or []
    omitidos = max(0, total - len(incluidos))
    # EC-9: el global de economía NO son los 139 campos de INGESTA, es el universo robustez.
    scope = f"{_NIVEL_TXT.get(nivel, '')} {entidad}".strip() if entidad else "Global · universo robustez"
    etiqueta = (f"📊 {scope} · Rentabilidad (EBITDA/NOPAT) — universo robustez, "
                f"solo crudo operado por Ecopetrol")

    if d.get("sin_datos"):
        return f"{etiqueta}\nNo tengo la base de rentabilidad (robustez) disponible en este entorno."

    w = d["waterfall"]
    comps = {c["key"]: c for c in w["components"]}
    y = w["meta"]["year"]; mo = w["meta"]["month"]
    mes = f"{_MES[mo]} {y}" if (mo and 1 <= mo <= 12) else "el período"

    ing = comps.get("ingresos", {}).get("value_kusd")
    ebitda = comps.get("ebitda", {}).get("value_kusd")
    ebitda_bl = comps.get("ebitda", {}).get("value_usd_bl")
    nopat = comps.get("util_neta", {}).get("value_kusd")
    margen = round(ebitda / ing * 100, 1) if (ing and ebitda is not None and ing != 0) else None

    lineas = [f"{etiqueta} ({mes})"]

    # EC-7: cobertura parcial -> PRIMERA línea del cuerpo + campos nombrados (verificable).
    de_quien = "de esta entidad"
    if omitidos:
        lineas.append(f"⚠️ COBERTURA PARCIAL: {len(incluidos)} de {total} campos del alcance están en "
                      f"robustez. Las cifras cubren SOLO: {', '.join(incluidos)}. "
                      f"Los otros {omitidos} (terceros o sin reconciliar) NO están incluidos.")
        de_quien = f"de esos {len(incluidos)} campos"

    seg_margen = f", margen {margen}% de ingresos" if margen is not None else ""
    lineas.append(f"Ingresos {de_quien}: {_kusd(ing)} kUSD. EBITDA: {_kusd(ebitda)} kUSD "
                  f"({_usdbl(ebitda_bl)} USD/BI{seg_margen}).")
    lineas.append(f"Utilidad neta (NOPAT): {_kusd(nopat)} kUSD.")
    return "\n".join(lineas)
```

### 5.3 — `respuesta_analizar.py` (EDITAR — mover economía tras la entidad + nueva rama)

**(a)** Añadir el import, junto a los de `analizar`:
```python
from app.features.consulta_v2.analizar import economia as _economia
```

**(b)** En la firma de `responder`, añadir el parámetro de inyección para tests (junto a
`_ejecutivo_fn`/`_diferidas_fn`):
```python
def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
              _ejecutivo_fn=None, _diferidas_fn=None, _economia_fn=None) -> str:
    """... (docstring existente; añadir que _economia_fn inyecta el waterfall en tests) ..."""
    fn = _ejecutivo_fn or _ejecutivo_ep
    dif_fn = _diferidas_fn or _diferidas.impacto_historico
    econ_fn = _economia_fn or _economia.impacto_economico
```

**(c)** ELIMINAR el early-return de economía (H8). Reemplazar EXACTAMENTE:
```python
    # 1) Sub-intención (determinista). economia -> mensaje honesto de fase (Fase 3, sin cambios).
    sub = _subrouter.sub_intencion(texto)
    if sub == "economia":
        return ("El análisis del EBITDA/margen llega en una próxima fase. Por ahora puedo explicarte "
                "las causas de un rezago, la proyección de cierre o el histórico de diferidas. "
                "¿Cuál de esas te sirve?")

    # 2) Entidad (RA-2, Fase 1). Aplica por igual a causal/proyeccion/diferidas (FB-5: diferidas
    #    necesita la entidad para filtrar por campo/activo, a diferencia de Fase 1).
```
POR:
```python
    # 1) Sub-intención (determinista). Fase 3: economia YA no es stub -> se resuelve tras la entidad.
    sub = _subrouter.sub_intencion(texto)

    # 2) Entidad (RA-2, Fase 1). Aplica por igual a causal/proyeccion/diferidas/economia (FB-5/H8:
    #    diferidas y economia necesitan la entidad para filtrar por campo/activo).
```

**(d)** Justo DESPUÉS de la rama `if sub == "diferidas":` (la que termina en el `return respuesta_base.envolver(...)`
de diferidas) e INMEDIATAMENTE ANTES de `# 4) Motor: ejecutivo…`, insertar la rama de economía:

```python
    # 3b) ECONOMÍA (Fase 3): EBITDA/NOPAT vía robustez, NO usa `ejecutivo` (fuente propia: el waterfall
    #     del EBITDA Inspector). H3: traduce la entidad INGESTA a rob_field; H4: declina terceros /
    #     sin reconciliar; H8: la regla de nivel vive en economia.nivel_soportado().
    if sub == "economia":
        if not _economia.nivel_soportado(nivel):
            return (f"La rentabilidad (EBITDA/NOPAT) solo está disponible a nivel de campo o activo; "
                    f"«{ent_valor}» es {nivel}. ¿Quieres nombrar un campo o activo puntual?")
        rob_fields, total = _economia.rob_fields_de(nivel, ent_valor)
        # H4/EC-10: entidad nombrada que no reconcilia a NINGÚN campo robustez (tercero, sin fila, o
        # activo 100% de terceros) -> declinar honesto. NUNCA caer a global en silencio (RA-2).
        if ent_valor and not rob_fields:
            return (f"«{ent_valor}» no está en el universo de rentabilidad (robustez), que solo cubre "
                    "los campos de crudo operados por Ecopetrol. ¿Quieres su producción o sus diferidas?")
        datos = econ_fn(rob_fields)
        # EC-7/EC-8: la plantilla necesita el NIVEL (D-A5) y la COBERTURA (incluidos/total) para
        # declararla en cabecera — no como footnote.
        cuerpo = _plantilla.economia(datos, ent_valor, nivel, rob_fields, total)
        intro = _intro(alcance, usuario)
        return respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el desglose de causas del mes, o la proyección de cierre?")

    # 4) Motor: ejecutivo con args explícitos + pulir=False (AF-A2 + RA-1). periodo=None = mes actual
```

> El resto de la función (rama diferidas, llamada a `fn(...)`, causal/proyección, envoltorio) **NO
> cambia**. Numeración: la rama nueva es `# 3b)` para no re-numerar la de diferidas (`# 3)`).

### 5.4 — `golden/analizar_golden.yaml` (EDITAR — +1 caso)

El golden ya tiene `"¿cuál es el EBITDA de Castilla?" → economia`. Añadir una variante con otro
disparador de `_ECON` (verifica que "rentabilidad"/"NOPAT" también enrutan):
```yaml
- pregunta: "¿cómo va la rentabilidad de Apiay?"
  entidad: "APIAY"
  sub: economia
```

### 5.5 — `tests/test_analizar.py` (EDITAR — +6 tests)

Añadir el import junto a los de `analizar`:
```python
from app.features.consulta_v2.analizar import economia as _economia_mod
```

Añadir al final del archivo:
```python
# ---------------- economia (Fase 3) ----------------

def _fake_waterfall(rob_fields=None):
    return {"sin_datos": False, "waterfall": {
        "components": [
            {"key": "ingresos",  "label": "Ingresos", "value_kusd": 1_196_006, "value_usd_bl": 87.3, "type": "total"},
            {"key": "ebitda",    "label": "EBITDA",   "value_kusd": 703_669,   "value_usd_bl": 51.4, "type": "total"},
            {"key": "util_oper", "label": "EBIT",     "value_kusd": 586_569,   "value_usd_bl": 42.8, "type": "total"},
            {"key": "util_neta", "label": "NOPAT",    "value_kusd": 334_325,   "value_usd_bl": 24.4, "type": "total"},
        ],
        "total_bls": 13_692_957,
        "meta": {"year": 2026, "month": 5, "nivel": "campo", "entidad": "CASTILLA", "producto": "CRUDO"},
    }}

def _fake_waterfall_sin_ops(rob_fields=None):
    return {"sin_datos": True, "motivo": "BD de rentabilidad (robustez) no disponible: ..."}


def test_economia_con_datos_rotulado_y_nivel():
    # CASTILLA resuelve a nivel='campo' (D-D5 prioridad Campo, verificado) -> debe decirlo (D-A5/EC-8).
    r = _ra.responder("¿cuál es el EBITDA de Castilla?", entidad="CASTILLA",
                      _economia_fn=_fake_waterfall)
    assert "robustez" in r.lower() and "crudo operado por ecopetrol" in r.lower()
    assert "el Campo CASTILLA" in r                 # D-A5: el NIVEL va explícito
    assert "EBITDA" in r and "703.669" in r         # kUSD es-CO
    assert "NOPAT" in r and "334.325" in r
    assert "margen" in r.lower() and "58" in r      # 703669/1196006 = 58.8%
    assert "COBERTURA PARCIAL" not in r             # campo 1:1 -> cobertura completa

def test_economia_sin_ops_declara_honesto():
    r = _ra.responder("¿cuál es el EBITDA de Castilla?", entidad="CASTILLA",
                      _economia_fn=_fake_waterfall_sin_ops)
    assert "no tengo la base de rentabilidad" in r.lower()
    assert "703" not in r     # nunca inventa cifras si no hay datos

def test_economia_tercero_declina():
    # CAÑO LIMON es tercero (es_ecp=false, rob_field NULL) -> rob_fields_de -> ([], 1) -> declina.
    # NO se inyecta _economia_fn: rob_fields_de consulta la BD real (map_campo_robustez).
    r = _ra.responder("¿cuál es el EBITDA de Caño Limón?", entidad="CAÑO LIMON")
    assert "no está en el universo de rentabilidad" in r.lower()

def test_economia_nivel_no_soportado_declina():
    # "GOR" resuelve a nivel='gerencia' (verificado contra la BD) -> declina.
    r = _ra.responder("¿cuál es el EBITDA de la vicepresidencia GOR?", entidad="GOR")
    assert "solo está disponible a nivel de campo o activo" in r.lower()


# ---------------- EC-7: cobertura parcial EN CABECERA (la prueba crítica de honestidad) ----------

def test_economia_cobertura_parcial_en_cabecera():
    """NARE (activo, verificado): 8 campos en INGESTA, solo 1 con rob_field. La cifra NO puede
    presentarse como «el EBITDA de NARE» -- debe declarar 1 de 8 y nombrar el campo incluido."""
    txt = _plantilla.economia(_fake_waterfall(), "NARE", "activo", ["NARE"], 8)
    assert "COBERTURA PARCIAL" in txt and "1 de 8" in txt
    assert "el Activo NARE" in txt                  # D-A5
    assert "de esos 1 campos" in txt                # el titular NO dice "de NARE" a secas
    # la advertencia va ANTES de las cifras (cabecera, no footnote)
    assert txt.index("COBERTURA PARCIAL") < txt.index("EBITDA:")

def test_economia_cobertura_completa_sin_aviso():
    txt = _plantilla.economia(_fake_waterfall(), "APIAY", "activo",
                              ["APIAY", "APIAY ESTE", "GAVAN", "GUATIQUIA"], 4)
    assert "COBERTURA PARCIAL" not in txt and "el Activo APIAY" in txt

def test_economia_global_rotula_universo_robustez():
    # EC-9: sin entidad, el alcance es el universo robustez, NO los 139 campos de INGESTA.
    txt = _plantilla.economia(_fake_waterfall(), None, None, [], 0)
    assert "Global · universo robustez" in txt


# ---------------- nivel_soportado economia (Fase 3, puro, sin BD) ----------------

def test_economia_nivel_soportado_puro():
    assert _economia_mod.nivel_soportado("campo") is True
    assert _economia_mod.nivel_soportado("activo") is True
    assert _economia_mod.nivel_soportado(None) is True
    assert _economia_mod.nivel_soportado("gerencia") is False
    assert _economia_mod.nivel_soportado("vicepresidencia") is False
```

> ⚠️ `test_economia_tercero_declina` y `test_economia_nivel_no_soportado_declina` consultan la BD real
> (resolver de entidad + `rob_fields_de` en el 1º) — como los tests de Fase 1/2 con `entidad="CAJUA"`.
> Se corren en el SERVIDOR DE PRUEBAS. Si `"GOR"`/`"CAÑO LIMON"` no resuelven igual en ese entorno,
> ajustar el nombre; no bloquean la compuerta si los tests puros + los inyectados pasan.

## 6. Orden de ejecución

1. `analizar/economia.py` (5.1). **`py_compile`.**
2. `analizar/plantilla.py` (5.2, añadir 3 funciones). **`py_compile`.**
3. `respuesta_analizar.py` (5.3, quitar early-return + rama nueva + import). **`py_compile` + import real.**
4. `golden/analizar_golden.yaml` (5.4) + `tests/test_analizar.py` (5.5). **`py_compile` del test.**
5. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **Se ENVUELVE el waterfall, no se reconstruye** (H1): import directo de `ebitda.unificado_waterfall`
   con args explícitos (año/mes None, nivel/entidad). NO se crea `ejecutor_robustez.py`, NO se toca la
   feature `ebitda`, cero HTTP.
2. **Traducir SIEMPRE la entidad INGESTA → rob_field** (H3) vía `core.map_campo_robustez` antes de
   llamar al waterfall. NUNCA pasar el nombre INGESTA crudo.
3. **Honestidad, nunca cifras inventadas** (H4/H7): tercero/sin-reconciliar → "no está en robustez";
   ops ausente → "no tengo la base de rentabilidad"; nivel no soportado → declarar. Cada cifra sale
   VERBATIM del waterfall.
3b. 🔴 **COBERTURA PARCIAL EN CABECERA, jamás al pie** (EC-7, la regla que más importa): si el alcance
   tiene campos sin `rob_field`, la 1ª línea del cuerpo dice `⚠️ COBERTURA PARCIAL: N de M campos`,
   **nombra los incluidos** y el titular dice «de esos N campos». Medido: NARE=1/8, LISAMA=1/6,
   SURIA=5/10 — presentar eso como «el EBITDA de NARE» repetiría el bug clase-APIAY de S23.
3c. **Decir el NIVEL** (EC-8/D-A5): «el Campo X» / «el Activo X». Por D-D5 un nombre que es ambos
   resuelve a **Campo** — sin el rótulo, dos cifras muy distintas quedan indistinguibles.
4. **Rotular el alcance real** (H5/H6): "universo robustez · solo crudo operado por Ecopetrol · {mes}".
5. **El wrapper degrada, nunca lanza** (EC-2): `impacto_economico` captura `except Exception` y devuelve
   `{sin_datos:True, motivo}` — mismo contrato que `diferidas.impacto_historico`.
6. **Entidad se resuelve UNA vez, antes de la rama** (H8/FB-5): economía NO duplica la lógica de
   resolución (ambiguo/filial/irresoluble/global) que ya usan causal/proyección/diferidas.
7. **Edificio separado + backend-only:** cero imports de `consulta/` v1; sin panel, sin memoria `_CTX`,
   sin frontend. Reusar `respuesta_base`, `cuantificar.resolver`, `_MES` de plantilla.
8. **NO usar el LLM local de dev**; pytest/golden/navegador → servidor de pruebas.
9. **NO tocar** `ebitda/*`, `analisis/api.py`, `cuantificar/*`, `subrouter.py`, `diferidas.py`, frontend.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo «servidor»)

- **V1** (estático) `py_compile` de `economia.py` + `plantilla.py` + `respuesta_analizar.py` +
  `tests/test_analizar.py`; import real de `respuesta_analizar` → OK.
- **V2** (dev, 1 SOLO proceso aislado, **datos reales** — ops configurada en dev) desde `backend/`:
  `from app.features.consulta_v2.analizar import economia as e`
  · `e.nivel_soportado("campo")=True`, `e.nivel_soportado("gerencia")=False`.
  · `e.rob_fields_de("campo","CASTILLA")` → `(["CASTILLA"], 1)` (cobertura completa).
  · `e.rob_fields_de("campo","CAÑO LIMON")` → `([], 1)` (tercero → declina).
  · `e.rob_fields_de("activo","APIAY")` → `(4 rob_field, 4)` — completa.
  · **`e.rob_fields_de("activo","NARE")` → `(1 rob_field, 8)`** — EC-7, el caso crítico de cobertura
    parcial (medido en la BD). `e.rob_fields_de("activo","SURIA")` → `(5, 10)`.
  · `e.impacto_economico(["CASTILLA"])` → `sin_datos=False`, `waterfall.components` con `ebitda`≈78.629 kUSD.
  · `e.impacto_economico([])` (global) → EBITDA≈703.669 kUSD (coincide con la auditoría).
- **V3** (dev, puro Python, SIN BD — `_economia_fn` fake + plantilla directa) los tests de §5.5 que NO
  tocan BD (`test_economia_con_datos_rotulado`, `_sin_ops`, `_avisa_omitidos`, `_nivel_soportado_puro`):
  pasan sus asserts.
- **V4** (dev, 1 SOLO proceso aislado, simulando ops ausente — **sin tocar el `.env`**) monkeypatch en
  memoria: `e._waterfall_ep = lambda **k: (_ for _ in ()).throw(RuntimeError("ops off"))` →
  `e.impacto_economico(["CASTILLA"])` devuelve `{"sin_datos":True, ...}` sin propagar la excepción.
- **V5** (servidor) `run_golden_analizar.py` → ≥90% (10 casos); `pytest tests/test_analizar.py -v` →
  todos verdes (Fases 1-2-3).
- **V6** (servidor, navegador) Motor v2, selector v2:
  · *"¿cuál es el EBITDA de Castilla?"* → EBITDA + NOPAT + margen; encabezado **«el Campo CASTILLA»**
    (D-A5 — ⚠️ NO dirá «Activo»: por D-D5 el nombre resuelve a Campo, verificado).
  · *"¿cómo va la rentabilidad de Apiay?"* → ⚠️ **el Campo APIAY** (1 campo), **NO** el activo de 4
    campos (EC-8: la v1 de este plan afirmaba lo contrario y era FALSO).
  · **`¿EBITDA de NARE?` → el caso crítico EC-7:** debe abrir con *«⚠️ COBERTURA PARCIAL: 1 de 8
    campos… cubren SOLO: NARE»* ANTES de las cifras. Si sale la cifra sin ese encabezado, **es un
    fallo bloqueante** (sería el bug clase-APIAY).
  · *"¿el EBITDA de Caño Limón?"* → declina "no está en el universo de rentabilidad".
  · *"¿EBITDA de la vicepresidencia GOR?"* → declina "solo campo o activo".
  · Sin regresión de causal/proyección/diferidas/Jerarquizar/Cuantificar/OUT.

## 9. Fuera de alcance (NO hacer)

- **EBITDA acumulado del año (YTD)** — Fase 3 da el MES vigente (coherente con el tablero, EC-4). El
  acumulado queda para una fase posterior.
- **EBITDA de gas/blancos** — el waterfall es crudo/aceite (H5); no existe la fuente. Se declara.
- **Gerencia / vicepresidencia / operador / fuente** como nivel (EC-5) — se declina; robustez tiene
  `rob_gerencia`/`rob_vicepresidencia`, así que es una extensión futura (agregar sus campos), no Fase 3.
- **Waterfall completo de 18 componentes** en el chat — Fase 3 resume EBITDA/NOPAT/margen/ingresos; el
  desglose línea a línea es el EBITDA Inspector visual, no el chat.
- **Filiales (rama B)** — el bloque de resolución ya las intercepta ("es una filial, próxima fase").
- **Panel derecho / memoria `_CTX` / drills** para economía — backend-only, igual que Fases 1-2.
- **Tocar `ebitda/*`, `subrouter.py`, `patrones_grupo.yaml`** — el clasificador y el waterfall ya están.
- **Unificar las 2 fuentes de "campos de un activo"** (CSV en diferidas vs tabla en economía, EC-3) —
  deuda declarada, limpieza posterior.
