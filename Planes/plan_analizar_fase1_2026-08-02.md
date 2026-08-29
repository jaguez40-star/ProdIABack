# Plan de ejecución — Analizar · FASE 1 (causal + proyección, envolver el ejecutivo)

> **Tablas: N/A** — no toca ingesta ni tablas fuente (capa de respuesta sobre un motor ya existente).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Motor Q v2 · Fase 1 (clasificador) + Cuantificar Fases 1-4 completas. El grupo
> **Analizar** clasifica correcto (patrones en `patrones_grupo.yaml`) pero **NO responde**: `maquina_q`
> solo tiene `"analizar"` en el diccionario de etiquetas → cae al texto genérico "en construcción".
> Esta Fase 1 le da voz a las **dos sub-intenciones más sólidas**: **causal** (por qué el rezago) y
> **proyección** (cómo vamos a cerrar). Diferidas y economía → Fase 2/3 (fuera de alcance).
>
> **Diseño base:** `INGESTA/Rep_Prod/analiza.md` (decisiones A1/A2/A3 cerradas). ⚠️ Sus **números de
> línea están desactualizados ~40 posiciones** (Fase 4 de Cuantificar añadió código a `analisis/api.py`);
> este plan trae las líneas REALES verificadas hoy. Además REVISA una recomendación del doc (§0, AF-A2).
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario, INVIOLABLE):** NO usar el LLM local de dev ni levantar
> la app en dev. En dev: solo `py_compile` y pruebas de DATOS puntuales contra Postgres (sin LLM), en
> procesos AISLADOS (uno a la vez). pytest, golden con LLM y navegador → **servidor de pruebas**.
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02, con línea REAL)

| # | Hallazgo (verificado en el código) | Efecto en el plan |
|---|-----------------------------------|-------------------|
| **AF-A1** | `ejecutivo()` vive en `analisis/api.py:1660`, firma `ejecutivo(entidad=Query(None), segmento=Query("ecp"), nivel=Query(None), periodo=Query(None))`. Abre su propia conexión (`get_engine()`, 1672) y delega filiales al tope (`if segmento=="filiales"`). | El motor YA existe y corre en 139. Analizar lo **consume**, no lo reescribe. |
| **AF-A2 · NO refactorizar `_ejecutivo_core`** 🔴 | `analiza.md §1.2` recomienda extraer un `_ejecutivo_core` para evitar el gotcha de `Query()`. **Pero el patrón PROBADO del repo es otro:** `cuantificar/ejecutor.py` llama `desempeno(...)` y `escenario_mes(...)` como **funciones normales con los args EXPLÍCITOS** (v1 lo usa desde 2026-07-15; Cuantificar Fases 1-4 igual). Pasar todos los args evita que los `Query(...)` se filtren como default. | **NO se crea `_ejecutivo_core`.** Analizar llama `ejecutivo(entidad=…, segmento="ecp", nivel=…, periodo=…)` explícito. ⚠️ **REVISADO por RA-1:** sí se añade UN param aditivo `pulir` (byte-idéntico para el tablero) — ver §0.1. |
| **AF-A3 · forma del retorno de `ejecutivo`** | Verificada (`api.py:1968-1979`): `{entidad, encontrada, meta{scope,periodo,corte,generado_por,llm_diag}, titular:[{producto,real,ppto,valor_pct,estado,texto}×3], tarjetas, gap_por_producto{PROD:{gap_kpi,concentracion_pct,detractores:[{campo,gap,real,meta,eventos}],compensadores,faltante_bruto,excedente_bruto,extremos}}, valle, eventos, eventos_extra, pace_crudo, flags, secciones, focos, sin_foco}`. | La plantilla lee de aquí. **`gap_por_producto` = `gap_full`** (los 3 productos, F2), no solo rezagados. |
| **AF-A4 · `hist_anio` NO está top-level** 🟠 | El promedio del año (`hist_anio`, base del DELTA-vs-2026 de `analiza.md §5`) se calcula (`api.py:1772`) pero **NO se retorna** en el nivel superior — se expone POR TARJETA: `tarjetas[i].hist_prom` (`_tarjetas_kpi`, `api.py:746`) y `tarjetas[i].proyectado_cierre` (= `real`, línea 738). | **DELTA lee `tarjetas`**, no un `hist_anio` inexistente. `delta = proyectado_cierre − hist_prom` por producto. Sin tocar `ejecutivo`. |
| **AF-A5 · `situacion_general` NO está top-level** 🔴 | Se calcula (`api.py:1903`) y va al **prompt del LLM** (`ctx`, 1907) pero **NO al retorno**. Es la base de la REGLA CERO (no inventar rezago). | La plantilla **RE-DERIVA** la situación desde `titular` (que sí se retorna): hay rezago ⇔ algún `titular` con `valor_pct` no nulo y `< 100`. Trivial, sin tocar `ejecutivo`. |
| **AF-A6 · `secciones` siempre poblado en dev** | `secciones` es `None` solo en el modo prueba (`EJECUTIVO_USAR_LLM=true` **y** `EJECUTIVO_FALLBACK=false`). Por default (`usar_llm=false`, `fallback=true`) → `_ejec_fallback` llena las 4 arrays (`api.py:1964`). | La plantilla NO depende de `secciones` para el entregable (lo arma determinista de la data estructurada). `secciones` queda como enriquecimiento OPCIONAL — si viene, se puede citar; si no, no pasa nada. **Fase 1 NO llama a Gemma para la prosa.** |
| **AF-A7 · `respuesta_base.py` ya extraído** | `respuesta_base.py` existe (`intro_llm(prompt, activo)` + `envolver(intro, body, cierre)`), creado en Cuantificar 1c. `format:json`, timeout 30s, jamás lanza. | Analizar reusa el MISMO envoltorio cordial que jerarquizar/cuantificar (riesgo A8 de `analiza.md` → **CERRADO**). |
| **AF-A8 · frontend YA renderiza analizar** | El chat pinta `d.mensaje` como `.v2-msg` (multilínea, `white-space:pre-line`) y el badge naranja "Analizar" ya sale (visto en navegador). `panel` es aditivo (HD4): si Analizar no manda panel, el visor no cambia. | **Fase 1 es BACKEND-ONLY.** Cero JS/CSS/cache-buster. Analizar devuelve solo texto (sin panel). |
| **AF-A9 · resolución de entidad + caso GLOBAL** 🔴 | `ejecutivo(entidad=None)` es VÁLIDO → `scope="Global (toda la producción ECP)"`. Pero `cuantificar.resolver.resolver_unico("texto sin entidad")` devuelve `None`, que en Cuantificar es un ERROR ("no identifiqué entidad"). | En Analizar, **sin entidad ⇒ scope GLOBAL** (NO error) — "¿cómo vamos?" es una pregunta legítima global. Diferencia explícita con Cuantificar (§5.1). |
| **AF-A10 · `_situacion_general`/REGLA CERO ya probada** | El caso real: CASTILLA campo al 102,7% y Gemma narró "déficit significativo" (alucinación). Python ya declara la verdad (`_situacion_general`) y `_reglas_tesis` ramifica el prompt. | Fase 1 replica la disciplina en la PLANTILLA determinista: si no hay rezago, el bloque CAUSA dice "sin rezago que explicar", NUNCA fabrica un faltante. |

### 0.1 Segunda ronda de auditoría (adversarial · 2026-08-02) — reformulación

| # | Incoherencia detectada (podría romper el pipeline / colgar el chat) | Reformulación |
|---|--------------------------------------------------------------------|---------------|
| **RA-1 · LANDMINE de latencia** 🔴🔴 | `ejecutivo()` llama a Gemma con **`timeout=180s`** (`api.py:1948`) cuando `EJECUTIVO_USAR_LLM=true` — **flag que está ENCENDIDO en 139** (bitácora S21). Fase 1 **DESCARTA** `secciones` (la prosa del LLM), pero mi plan original llamaba a `ejecutivo()` con los defaults → en 139 el chat de Analizar **esperaría hasta 180s** generando una prosa que se tira (y con Gemma en frío, 342s → cuelga hasta el timeout). Latencia inaceptable para un chat. | **Se añade UN parámetro aditivo `pulir: bool = Query(True)` a `ejecutivo`** (§5.0). El endpoint (tablero) no lo pasa → `True` → **byte-idéntico**. Analizar llama `pulir=False` → salta el bloque LLM → `_ejec_fallback` (determinista, rápido) rellena `secciones`. Esto REVISA AF-A2/Regla 3: sigue SIN refactor de `_ejecutivo_core`, pero **este único param aditivo es OBLIGATORIO** (el hang de 180s es peor que un cambio de 2 tokens que no altera el tablero). |
| **RA-2 · GLOBAL silencioso** 🟠 | Mi `responder` original caía a **scope GLOBAL** cuando `resolver_unico` devolvía `None`. Pero `resolver_unico` puede devolver `None` porque (a) el usuario NO nombró entidad (→ global correcto) o (b) nombró una entidad que el catálogo de Cuantificar NO resuelve (p.ej. `POE`, una gerencia SOLO-robustez por el level-shift — `HALLAZGO_clasificador_conteo_jerarquia.md §2.3`). El caso (b) caería SILENCIOSO a global → analiza otra cosa sin avisar. | Se distingue: si `entidad` (el arg del clasificador) **venía poblado** y no resuelve → **fallo honesto** ("no pude ubicar «X» para analizar"). Solo si `entidad` era `None` desde el inicio → GLOBAL. |
| **RA-3 · acoplamiento innecesario a `slots`** 🟡 | Mi plan importaba `cuantificar.slots` SOLO para `_periodo_texto` (función PRIVADA). Fase 1 casi nunca recibe un mes explícito ("¿por qué está corto Cajúa?" = mes en curso). | **Se elimina el import de `slots` y el parseo de periodo** (siempre `periodo=None` = mes actual). Menos acoplamiento, sin reach-in a privados. El mes explícito ("¿por qué estuvo corto en abril?") queda para Fase 2. |
| **RA-4 · redacción REGLA CERO** 🟡 | En la rama "sin rezago", si NINGÚN producto tiene meta, el texto decía "todo producto con meta va en o sobre ella (sin meta definida)" — contradictorio. | La plantilla ramifica: "sin rezago" (hay productos con meta, todos ≥100) vs "ningún producto tiene meta en el periodo" (caso aparte). |
| **RA-5 · sin riesgo circular** ✅ | Verificado: `analisis/api.py` **NO importa `consulta_v2`**. Añadir `respuesta_analizar → analisis.api` en `maquina_q` no crea ciclo (y `analisis.api` ya está en la cadena de imports vía `cuantificar.ejecutor`). | Sin cambios; se confirma seguro. |
| **RA-6 · fechas ISO en HECHO** 🟡 | El HECHO del valle decía "del 2026-05-06 al 2026-05-12" (ISO crudo, feo para un gerente). | Helper de 3 líneas `_dia_mes()` → "del 6 al 12 de mayo". Cosmético, barato. |

---

## 1. Contexto

Motor Q v2 · Grupo 3 (Analizar). Edificio SEPARADO en `consulta_v2/` (cero imports de `consulta/` v1).
**Regla madre:** *Python calcula y decide la tesis; el LLM solo redacta el intro.* El motor
(`analisis.ejecutivo`) ya reconcilia gap por campo / valle / pace con Python y corre en 139 — la
coherencia chat↔tablero es **por construcción** (misma función). Analizar es "envolver", no "construir".

## 2. Objetivo

Que **causal** ("¿por qué está corto CAJÚA?" · "¿qué campos pesan?") y **proyección** ("¿cómo vamos?" ·
"¿vamos a cerrar?") respondan con:

- **causal** → narrativa **HECHO / CAUSA / ACCIÓN / DELTA** (determinista, desde `ejecutivo`), con
  REGLA CERO (si va en meta, lo dice; NO inventa rezago) + envoltorio cordial (intro LLM opcional).
- **proyección** → "para cerrar, CRUDO requiere X bbl/día; va a Y/día (Z% por encima/debajo) → {va
  camino de cerrar en meta | necesita acelerar}", desde `pace_crudo`.
- **diferidas / economía** (si el sub-router las detecta) → mensaje honesto "esa vista llega en una
  próxima fase; por ahora puedo con causas del rezago y proyección de cierre".

## 3. Prerequisitos

- Motor Q v2 + Cuantificar presentes. Backend en
  `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend` (`uv run python` desde `backend/`).
- `analisis.ejecutivo` operativo (dev + 139). BD dev `daily_report_prod` arriba (solo pruebas de datos).
- `respuesta_base.py` presente (AF-A7). `cuantificar/resolver.py` y `cuantificar/validador.py` presentes.

## 4. Inventario de archivos

Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2`

| Acción | Ruta |
|--------|------|
| EDITAR | `...\backend\app\features\analisis\api.py` — **1 param aditivo** `pulir: bool = Query(True)` en `ejecutivo` (RA-1); tablero byte-idéntico |
| CREAR | `...\consulta_v2\analizar\__init__.py` (vacío) |
| CREAR | `...\consulta_v2\analizar\subrouter.py` — `sub_intencion(texto)` determinista |
| CREAR | `...\consulta_v2\analizar\plantilla.py` — bloques causal (HECHO/CAUSA/ACCIÓN/DELTA) + proyección |
| CREAR | `...\consulta_v2\respuesta_analizar.py` — dispatcher: resolver → sub-intención → ejecutivo(pulir=False) → plantilla → envolver |
| EDITAR | `...\backend\app\core\config.py` — flag `consulta_analiza_llm: bool = True` |
| EDITAR | `...\consulta_v2\maquina_q.py` — import + `elif grupo == "analizar" and log:` |
| CREAR | `...\consulta_v2\golden\analizar_golden.yaml` + `run_golden_analizar.py` |
| CREAR | `...\backend\tests\test_analizar.py` |
| NO TOCAR | `_ejecutivo_core` (NO se crea — AF-A2), la query de KPIs/gap/valle/pace de `ejecutivo` (solo se añade el param `pulir`), `cuantificar/*` (solo se IMPORTA `resolver`+`validador.fmt_valor`), flujo v1, frontend (AF-A8) |

## 5. Especificación (código de referencia)

### 5.0 — `analisis/api.py` (EDITAR — 1 param aditivo `pulir`, RA-1) 🔴 PRIMERO

**El único cambio a `analisis/api.py`.** Mata el landmine de 180s SIN tocar la query de datos ni el
comportamiento del tablero (byte-idéntico con el default).

**(a)** Firma de `ejecutivo` (`api.py:1661-1662`). Reemplazar EXACTAMENTE:
```python
def ejecutivo(entidad: str | None = Query(None), segmento: str = Query("ecp"),
             nivel: str | None = Query(None), periodo: str | None = Query(None)):
```
por:
```python
def ejecutivo(entidad: str | None = Query(None), segmento: str = Query("ecp"),
             nivel: str | None = Query(None), periodo: str | None = Query(None),
             pulir: bool = Query(True)):
    # pulir=False (solo lo usa consulta_v2/Analizar): SALTA el pulido LLM de `secciones` (Gemma,
    # timeout 180s) y sirve el fallback determinista. El endpoint/tablero no pasa `pulir` → True →
    # comportamiento byte-idéntico. Evita que el chat de Analizar cuelgue esperando una prosa que
    # descarta (RA-1).
```
**(b)** Gate del LLM (`api.py:1946`). Reemplazar EXACTAMENTE:
```python
        if get_settings().ejecutivo_usar_llm:
```
por:
```python
        if pulir and get_settings().ejecutivo_usar_llm:
```
**(c)** Rama de modo-prueba (`api.py:1961`). Reemplazar EXACTAMENTE:
```python
            if _st.ejecutivo_usar_llm and not _st.ejecutivo_fallback:
```
por:
```python
            if pulir and _st.ejecutivo_usar_llm and not _st.ejecutivo_fallback:
```
> Con `pulir=False`: (a) no se entra al bloque LLM → `secciones=None`; (c) la rama "error" se salta →
> `else` → `_ejec_fallback` rellena `secciones` determinista. Analizar igual descarta `secciones`, pero
> el retorno queda bien formado. **El resto de `ejecutivo` (KPIs, gap por campo, valle, pace, tarjetas,
> focos) NO se toca.** Verificación de no-regresión: V0 (§8).

### 5.1 — `respuesta_analizar.py` (CREAR — dispatcher)

Reusa `cuantificar.resolver.resolver_unico` (resolución D-D5) y `respuesta_base` (envoltorio). 🔑
Diferencias con Cuantificar: **entidad NO nombrada ⇒ scope GLOBAL** (RA-2), **entidad nombrada pero
irresoluble ⇒ fallo honesto** (RA-2), y **`ejecutivo(..., pulir=False)`** para no colgar el chat (RA-1).

```python
"""respuesta_analizar.py — respuesta del grupo ANALIZAR (Motor Q v2, Grupo 3, Fase 1).

Envuelve `analisis.ejecutivo` (motor ya existente y afinado; corre en 139). Regla madre: Python
calcula y decide la tesis (REGLA CERO: NO inventar rezago); el LLM solo redacta el intro cordial.

Coherencia chat↔tablero: se llama `ejecutivo(...)` con los args EXPLÍCITOS (patrón probado por
Cuantificar y v1; NO se refactoriza `_ejecutivo_core` — AF-A2). 🔑 `pulir=False` (RA-1): salta el
pulido LLM de `secciones` (que Fase 1 descarta) → sin el hang de 180s de Gemma en 139.

GLOBAL vs FALLO (RA-2): sin entidad nombrada ⇒ análisis GLOBAL ECP; entidad nombrada que el catálogo
no resuelve (p.ej. una gerencia solo-robustez) ⇒ fallo honesto, NO global silencioso.

Fase 1: sub-intenciones `causal` y `proyeccion`. `diferidas`/`economia` → mensaje honesto de fase.
"""
from app.core.config import get_settings
from app.features.analisis.api import ejecutivo as _ejecutivo_ep
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.analizar import subrouter as _subrouter
from app.features.consulta_v2.analizar import plantilla as _plantilla

_s = get_settings()

# El LLM escribe SOLO el intro (calidez). Prohibido cifras — los bloques (aparte) las llevan.
PROMPT_ANALIZA = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial y natural.
Voy a mostrar un ANÁLISIS de {alcance} — se muestra aparte, NO lo repitas, NO inventes números ni causas.
Escribe UNA sola frase de presentación, cálida y BREVE, en español ("Con gusto, aquí tienes el análisis…").
Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO des cifras, NO menciones porcentajes ni campos, NO adelantes conclusiones. Solo saluda y anuncia el análisis.
Responde SOLO con JSON válido: {{"intro": "..."}}"""

_CIERRE = "¿Quieres el detalle por campo, o la proyección de cierre?"
_CIERRE_PROY = "¿Quieres ver qué campos explican el faltante?"


def _intro(alcance: str, usuario) -> str:
    """Intro validado (sin dígitos). '' si el flag está off o el LLM falla/mete un número."""
    if not _s.consulta_analiza_llm:
        return ""
    prompt = PROMPT_ANALIZA.format(alcance=alcance, usuario=usuario or "el usuario")
    cand = respuesta_base.intro_llm(prompt, True)
    # Red mecánica: el intro es SOLO saludo. Si trae dígitos, se descarta (regla madre).
    return cand if (cand and not any(ch.isdigit() for ch in cand)) else ""


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
              _ejecutivo_fn=None) -> str:
    """Devuelve SIEMPRE un str (nunca None). `_ejecutivo_fn` = inyección para tests (evita BD/LLM)."""
    fn = _ejecutivo_fn or _ejecutivo_ep

    # 1) Sub-intención (determinista). diferidas/economia → mensaje honesto de fase.
    sub = _subrouter.sub_intencion(texto)
    if sub in ("diferidas", "economia"):
        que = "las diferidas" if sub == "diferidas" else "el EBITDA/margen"
        return (f"El análisis de {que} llega en una próxima fase. Por ahora puedo explicarte las "
                "causas de un rezago (qué campos pesan) o la proyección de cierre del mes. "
                "¿Cuál de las dos te sirve?")

    # 2) Entidad (RA-2). resolver_unico busca por el arg o escaneando el texto.
    resuelta = _resolver.resolver_unico(entidad or texto)
    if resuelta and resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                "Nómbrala de forma única para analizarla.")
    if resuelta and resuelta.get("rama") == "B":
        return (f"«{resuelta['valor']}» es una filial; su análisis llega en una próxima fase. "
                "Por ahora analizo la producción ECP.")
    if resuelta is None:
        # RA-2: distinguir "no nombró entidad" (→ GLOBAL) de "nombró algo irresoluble" (→ fallo honesto).
        if entidad:
            return (f"No pude ubicar «{entidad}» en el catálogo para analizarla. "
                    "¿Puedes nombrar un campo, activo o gerencia del reporte ECP?")
        ent_valor, nivel, alcance = None, None, "la producción global ECP"   # GLOBAL
    else:
        ent_valor = resuelta["valor"]; nivel = resuelta.get("nivel")
        alcance = f"el {nivel} {ent_valor}".strip()

    # 3) Motor: ejecutivo con args explícitos + pulir=False (AF-A2 + RA-1). periodo=None = mes actual
    #    (RA-3: el mes explícito llega en Fase 2).
    d = fn(entidad=ent_valor, segmento="ecp", nivel=nivel, periodo=None, pulir=False)
    if not d.get("encontrada"):
        return f"No encontré datos de producción para «{entidad or texto}» para analizar."
    if d.get("sin_datos"):
        return f"«{ent_valor or 'ECP'}» no tiene datos suficientes en ese periodo para un análisis."

    # 4) Cuerpo determinista por sub-intención (VERBATIM de la data del ejecutivo).
    if sub == "proyeccion":
        cuerpo = _plantilla.proyeccion(d, ent_valor)
        cierre = _CIERRE_PROY
    else:                                                    # causal (default)
        cuerpo = _plantilla.causal(d, ent_valor)
        cierre = _CIERRE

    # 5) Envoltorio cordial (intro LLM opcional + cuerpo VERBATIM + cierre).
    intro = _intro(alcance, usuario)
    return respuesta_base.envolver(intro, cuerpo, cierre)
```

> ⚠️ **El test/golden inyecta `_ejecutivo_fn`. Ese fake DEBE aceptar `pulir` en su firma** (`def
> fake(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False)`), o el call de la línea
> `fn(..., pulir=False)` reventará con TypeError. Ver §5.9.

### 5.2 — `analizar/subrouter.py` (CREAR — sub-intención determinista)

```python
"""analizar/subrouter.py — separa las sub-intenciones de "analizar" (Python, sin LLM).

El clasificador (Etapa A) mete 4 preguntas bajo "analizar"; el sub-router elige la ruta. Fase 1
responde causal + proyeccion; diferidas/economia devuelven mensaje honesto de fase (el dispatcher
las intercepta). Match por TOKEN/FRASE sobre texto normalizado (mismo criterio que slots, AF-3.7)."""
from app.features.consulta_v2.normaliza import norm

_PROY = ("COMO VAMOS", "VAMOS A LLEGAR", "VAMOS A CERRAR", "VAMOS A ALCANZAR",
         "PROYECCION", "SE VE RECUPERACION", "VA A CERRAR", "COMO VA A CERRAR",
         "PROYECTA", "CAMINO DE", "TENDENCIA")
_DIFERIDAS = ("DIFERIDAS", "MANTENIMIENTO", "MANTENIMIENTOS")
_ECON = ("EBITDA", "NOPAT", "MARGEN", "RENTABILIDAD", "PLATA")


def sub_intencion(texto: str) -> str:
    """causal (default) | proyeccion | diferidas | economia. Precedencia: economia/diferidas
    ganan (son fuentes distintas), luego proyeccion, luego causal."""
    t = norm(texto or "")
    if any(k in t for k in _ECON):
        return "economia"
    if any(k in t for k in _DIFERIDAS):
        return "diferidas"
    if any(k in t for k in _PROY):
        return "proyeccion"
    return "causal"
```

### 5.3 — `analizar/plantilla.py` (CREAR — bloques verbatim)

Reusa `cuantificar.validador.fmt_valor` (formato producto-aware: gas MSCF ÷1e6; crudo/blancos bbl).

```python
"""analizar/plantilla.py — arma la narrativa VERBATIM desde el JSON de `analisis.ejecutivo`.

TODO número sale de la data del motor (reconciliada por Python, coherente con el tablero). REGLA
CERO (AF-A5/A10): si NINGÚN producto va por debajo de su meta, se DECLARA "sin rezago" — NUNCA se
fabrica un faltante. La prosa del LLM (secciones) NO se usa aquí (Fase 1 es determinista).
"""
from app.features.consulta_v2.cuantificar.validador import fmt_valor

_UNIDAD = {"CRUDO": "bbl", "GAS": "MSCF", "BLANCOS": "bbl"}
_PROD_L = {"CRUDO": "crudo", "GAS": "gas", "BLANCOS": "blancos"}
_MES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre", "diciembre"]


def _fmt(valor, prod) -> str:
    """fmt producto-aware: 'crudo'→bbl es-CO; 'gas'→MSCF (÷1e6). fmt_valor espera el nombre en
    minúscula ('gas'), no el del titular ('GAS')."""
    return fmt_valor(valor, _PROD_L.get(prod, "crudo"))


def _dia_mes(iso) -> str:
    """'2026-05-06' -> '6 de mayo' (RA-6: legible). Devuelve el ISO crudo si no parsea."""
    try:
        _, m, d = str(iso).split("-")
        return f"{int(d)} de {_MES[int(m)]}"
    except Exception:
        return str(iso)


def _rezagados(d) -> list:
    """Productos con meta y por debajo de ella (valor_pct < 100). REGLA CERO se apoya en esto."""
    return [t for t in d.get("titular", []) if t.get("valor_pct") is not None and t["valor_pct"] < 100]


def _delta_texto(d, prod) -> str | None:
    """DELTA vs promedio del año (AF-A4): tarjetas[prod].proyectado_cierre − hist_prom. None si falta."""
    tar = next((x for x in d.get("tarjetas", []) if x.get("producto") == prod), None)
    if not tar or tar.get("hist_prom") in (None, 0) or tar.get("proyectado_cierre") is None:
        return None
    real = tar["proyectado_cierre"]; hist = tar["hist_prom"]
    dif = real - hist
    signo = "por encima de" if dif >= 0 else "por debajo de"
    u = _UNIDAD.get(prod, "bbl")
    return (f"va en {_fmt(real, prod)} {u} vs su promedio {2026} de {_fmt(hist, prod)} {u} "
            f"({'+' if dif >= 0 else '−'}{_fmt(abs(dif), prod)} {u}, {signo} su propia historia)")


def causal(d, entidad) -> str:
    """HECHO / CAUSA / ACCIÓN / DELTA. Alcance = entidad o Global. REGLA CERO si no hay rezago."""
    scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")
    periodo = (d.get("meta") or {}).get("periodo") or "el periodo"
    rez = _rezagados(d)

    # --- REGLA CERO: sin rezago, se DECLARA (no se inventa) — RA-4: ramificar por "hay meta o no" ---
    if not rez:
        con_meta = [t for t in d.get("titular", []) if t.get("valor_pct") is not None]
        lineas = [f"📊 {scope} · {periodo}"]
        if con_meta:
            estado = ", ".join(f"{_PROD_L.get(t['producto'], t['producto'])} {t['valor_pct']}%" for t in con_meta)
            lineas.append(f"HECHO: no hay rezago — todo producto con meta va en o sobre ella ({estado}).")
            # DELTA igual aporta contexto (vs su propia historia), aunque no haya rezago.
            for t in con_meta:
                dl = _delta_texto(d, t["producto"])
                if dl:
                    lineas.append(f"DELTA · {_PROD_L.get(t['producto'], t['producto'])}: {dl}.")
        else:
            lineas.append("HECHO: ningún producto tiene meta definida en el periodo — no hay "
                          "cumplimiento que evaluar ni rezago que explicar.")
        return "\n".join(lineas)

    # --- Con rezago: HECHO/CAUSA/ACCIÓN/DELTA del(los) producto(s) rezagado(s) ---
    lineas = [f"📊 {scope} · {periodo}"]
    gap = d.get("gap_por_producto", {})
    for t in rez:
        p = t["producto"]; pl = _PROD_L.get(p, p); u = _UNIDAD.get(p, "bbl")
        g = gap.get(p, {})
        detr = g.get("detractores", [])
        conc = g.get("concentracion_pct")

        # HECHO — RA-7: usar la etiqueta HUMANA (titular.texto = "Foco"/"Rezagado"/"Alineado"),
        # NO el código crudo (titular.estado = "alert"/"warn"/"ok").
        hecho = f"{pl} cerró {periodo} al {t['valor_pct']}% del presupuesto ({t.get('texto', '—')})"
        if p == "CRUDO" and d.get("valle"):
            v = d["valle"]
            hecho += f"; hubo un valle del {_dia_mes(v.get('desde'))} al {_dia_mes(v.get('hasta'))}"
        lineas.append(f"HECHO · {pl}: {hecho}.")

        # CAUSA (detractores + concentración + evidencia de comentarios, cobertura ~33% → declara)
        if detr:
            piezas = "; ".join(f"{x['campo']} (−{_fmt(abs(x['gap']), p)} {u})" for x in detr)
            causa = f"el faltante se concentra en {piezas}"
            if conc is not None:
                causa += f" — ~{conc}% del déficit está en esos {len(detr)} campos"
            # evidencia textual del reporte (si existe) — no se inventa
            ev = next((x.get("eventos") for x in detr if x.get("eventos")), None)
            if ev:
                lineas.append(f"CAUSA · {pl}: {causa}. Reporte: «{str(ev[0])[:160]}».")
            else:
                lineas.append(f"CAUSA · {pl}: {causa}. Sin evento asociado en comentarios "
                              "(requiere validación en campo).")
        else:
            lineas.append(f"CAUSA · {pl}: sin desglose por campo disponible para el faltante.")

        # ACCIÓN (consultiva, no prescriptiva)
        if conc is not None and conc >= 70 and detr:
            lineas.append(f"ACCIÓN · {pl}: intervención focalizada en los {len(detr)} campos que "
                          "concentran el faltante (consultivo).")
        elif detr:
            lineas.append(f"ACCIÓN · {pl}: el faltante está distribuido; revisión más amplia "
                          "(consultivo).")

        # DELTA (vs promedio 2026)
        dl = _delta_texto(d, p)
        if dl:
            lineas.append(f"DELTA · {pl}: {dl}.")

    return "\n".join(lineas)


def proyeccion(d, entidad) -> str:
    """Proyección de cierre de CRUDO desde pace_crudo. Si no hay pace fiable, lo declara."""
    scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")
    periodo = (d.get("meta") or {}).get("periodo") or "el periodo"
    pace = d.get("pace_crudo")
    if not pace:
        return (f"📊 {scope} · {periodo}\nNo tengo una proyección diaria fiable de crudo para este "
                "periodo (puede ser un mes ya cerrado o sin curva diaria que reconcilie).")
    prom = pace.get("promedio_dia"); req = pace.get("requerido_dia"); dpc = pace.get("delta_pct")
    rest = pace.get("restantes")
    u = "bbl"
    linea = (f"para cerrar {periodo}, el crudo requiere {_fmt(req, 'CRUDO')} {u}/día en los "
             f"{rest} días restantes; va a un ritmo de {_fmt(prom, 'CRUDO')} {u}/día")
    if dpc is not None:
        if dpc <= 0:
            veredicto = "va camino de cerrar en meta (el ritmo actual alcanza)"
        else:
            veredicto = f"necesita acelerar {dpc}% (el ritmo actual queda corto)"
        linea += f" → {veredicto}"
    return f"📊 {scope} · {periodo}\nPROYECCIÓN · crudo: {linea}."
```

### 5.4 — `analizar/__init__.py` (CREAR — vacío)

```python
```

### 5.5 — `config.py` (EDITAR — flag del grupo)

En `app/core/config.py`, tras `consulta_cuant_llm` (`config.py:35`), añadir:

```python
    # Motor Q v2 · grupo Analizar: el LLM ENVUELVE el análisis (saludo cordial dinámico); los HECHOS/
    # CAUSAS/números van VERBATIM (Python) → el LLM no toca el análisis (regla madre + red anti-dígitos).
    # Default true; false = solo cuerpo + cierre. Si el LLM falla/está frío → fallback determinista.
    consulta_analiza_llm: bool = True
```

### 5.6 — `maquina_q.py` (EDITAR — import + wiring)

**(a)** En los imports (junto a `respuesta_cuantificar`, `maquina_q.py:22`):
```python
from app.features.consulta_v2 import respuesta_analizar
```
**(b)** En `_clasificar_core`, tras el bloque `elif grupo == "cuantificar" and log:` (`maquina_q.py:276-286`),
añadir el bloque simétrico de jerarquizar:
```python
    elif grupo == "analizar" and log:
        # ANALIZAR — Fase 1 (plan_analizar_fase1_2026-08-02.md): envuelve analisis.ejecutivo (motor
        # ya existente) → HECHO/CAUSA/ACCIÓN/DELTA (causal) o proyección de cierre. Los HECHOS son
        # deterministas; el LLM solo el intro cordial. Solo tráfico real; devuelve str (sin panel).
        r = respuesta_analizar.responder(texto, entidad=entidad, usuario=usuario,
                                         conversation_id=conversation_id)
        if r:
            mensaje = r
```
> El `return` de `_clasificar_core` NO cambia: Analizar deja `panel = None` (aditivo, HD4). Frontend
> ya renderiza `mensaje` multilínea (AF-A8).

### 5.7 — `golden/analizar_golden.yaml` (CREAR)

Casos con `entidad` (lo que `detectar_entidad` habría hallado) + `sub` esperada + `contiene` (subcadenas
que el cuerpo DEBE traer). No fija cifras (BD mutable) — valida ESTRUCTURA y la REGLA CERO.

```yaml
# Golden de ANALIZAR (Motor Q v2 · Grupo 3 · Fase 1). Gate: >=90%.
# Corre con run_golden_analizar.py (SIN LLM: fuerza CONSULTA_ANALIZA_LLM=false). Valida sub-intención
# determinista (subrouter, sin BD) + estructura del cuerpo con un `_ejecutivo_fn` FAKE inyectado.

# --- sub-intención (determinista, sin BD) ---
- pregunta: "¿por qué está corto Cajúa?"
  entidad: "CAJUA"
  sub: causal
- pregunta: "¿qué campos pesan en el faltante?"
  entidad: null
  sub: causal
- pregunta: "¿a qué se debe el rezago de crudo?"
  entidad: null
  sub: causal
- pregunta: "¿cómo vamos este mes?"
  entidad: null
  sub: proyeccion
- pregunta: "¿vamos a cerrar en meta?"
  entidad: null
  sub: proyeccion
- pregunta: "¿cuál es la proyección de cierre?"
  entidad: null
  sub: proyeccion
- pregunta: "¿qué pasó con las diferidas?"
  entidad: null
  sub: diferidas
- pregunta: "¿cuál es el EBITDA de Castilla?"
  entidad: "CASTILLA"
  sub: economia
```

### 5.8 — `golden/run_golden_analizar.py` (CREAR)

```python
"""Gate del grupo ANALIZAR (Motor Q v2 · Fase 1). SIN LLM (fuerza CONSULTA_ANALIZA_LLM=false).

Valida (1) la sub-intención determinista (subrouter, sin BD) y (2) que las rutas causal/proyeccion
producen un cuerpo con la estructura esperada usando un `_ejecutivo_fn` FAKE (sin BD ni LLM).

⚠️ NO correr en dev con la BD (regla de RAM). Uso, desde backend/, en el SERVIDOR DE PRUEBAS:
    PYTHONPATH=. uv run python app/features/consulta_v2/golden/run_golden_analizar.py
"""
import os
os.environ.setdefault("CONSULTA_ANALIZA_LLM", "false")

import pathlib
import yaml

from app.features.consulta_v2.analizar import subrouter as _subrouter


def main():
    p = pathlib.Path(__file__).with_name("analizar_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok = 0
    fallos = []
    for c in casos:
        sub = _subrouter.sub_intencion(c["pregunta"])
        acierto = sub == c["sub"]
        ok += acierto
        marca = "OK " if acierto else "XX "
        extra = "" if acierto else f"  -> sub={sub}"
        print(f"{marca}[{c['sub']:<11}] {c['pregunta']}{extra}")
        if not acierto:
            fallos.append(c["pregunta"])
    n = len(casos)
    pct = 100 * ok // n if n else 0
    print(f"\nEXACTITUD (sub-intención): {ok}/{n} = {pct}%   (gate: >=90%)")
    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
```

### 5.9 — `tests/test_analizar.py` (CREAR)

Todo con `_ejecutivo_fn` FAKE → sin BD, sin LLM. Prueba clave: **REGLA CERO** (entidad en meta → NO
inventa rezago).

```python
"""Tests de ANALIZAR (Motor Q v2 · Grupo 3 · Fase 1). Sub-router (puro) + plantilla con ejecutivo FAKE.

⚠️ Importa respuesta_analizar (-> analisis.api -> sqlalchemy) al cargar el módulo, aunque ninguna
prueba toque Postgres (los datos vienen inyectados vía _ejecutivo_fn). Por la regla de RAM: se corre
en el SERVIDOR DE PRUEBAS, no en dev.
"""
import os
os.environ.setdefault("CONSULTA_ANALIZA_LLM", "false")   # sin intro LLM en tests

from app.features.consulta_v2.analizar import subrouter as _subrouter
from app.features.consulta_v2.analizar import plantilla as _plantilla
from app.features.consulta_v2 import respuesta_analizar as _ra


# ---------------- sub-router (determinista, sin BD) ----------------

def test_sub_causal_por_que():
    assert _subrouter.sub_intencion("¿por qué está corto Cajúa?") == "causal"

def test_sub_proyeccion_como_vamos():
    assert _subrouter.sub_intencion("¿cómo vamos este mes?") == "proyeccion"

def test_sub_proyeccion_gana_a_causal():
    assert _subrouter.sub_intencion("¿vamos a cerrar el crudo?") == "proyeccion"

def test_sub_diferidas():
    assert _subrouter.sub_intencion("¿qué pasó con las diferidas?") == "diferidas"

def test_sub_economia():
    assert _subrouter.sub_intencion("¿cuál es el EBITDA de Castilla?") == "economia"


# ---------------- fakes de ejecutivo ----------------
# ⚠️ RA-1: la firma DEBE aceptar `pulir` (respuesta_analizar llama fn(..., pulir=False)).

def _fake_con_rezago(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
    return {
        "entidad": entidad, "encontrada": True,
        "meta": {"scope": entidad or "Global (toda la producción ECP)", "periodo": "mayo 2026"},
        "titular": [
            {"producto": "CRUDO", "real": 8000.0, "ppto": 10000.0, "valor_pct": 80.0,
             "estado": "alert", "texto": "Foco"},
            {"producto": "GAS", "real": 5000.0, "ppto": 4900.0, "valor_pct": 102.0,
             "estado": "ok", "texto": "Alineado"},
            {"producto": "BLANCOS", "real": 300.0, "ppto": None, "valor_pct": None,
             "estado": "", "texto": "—"},
        ],
        "tarjetas": [
            {"producto": "CRUDO", "proyectado_cierre": 8000.0, "hist_prom": 7500.0},
            {"producto": "GAS", "proyectado_cierre": 5000.0, "hist_prom": 4800.0},
        ],
        "gap_por_producto": {
            "CRUDO": {"gap_kpi": -2000, "concentracion_pct": 75.0,
                      "detractores": [{"campo": "CAJUA", "gap": -1200, "real": 1000, "meta": 2200,
                                       "eventos": ["Paro por falla de equipo del 6 al 12"]},
                                      {"campo": "CPO-09", "gap": -800, "real": 500, "meta": 1300,
                                       "eventos": []}],
                      "compensadores": [], "faltante_bruto": -2000, "excedente_bruto": 0, "extremos": []},
        },
        "valle": {"desde": "2026-05-06", "hasta": "2026-05-12"},
        "pace_crudo": {"mtd": 4000, "dias": 17, "restantes": 14, "promedio_dia": 235,
                       "requerido_dia": 428, "delta_pct": 82.0},
        "flags": [], "secciones": None, "focos": [], "sin_foco": False,
    }


def _fake_en_meta(entidad=None, segmento="ecp", nivel=None, periodo=None, pulir=False):
    d = _fake_con_rezago(entidad, segmento, nivel, periodo)
    d["titular"][0]["valor_pct"] = 102.7; d["titular"][0]["estado"] = "ok"; d["titular"][0]["real"] = 10270.0
    d["tarjetas"][0]["proyectado_cierre"] = 10270.0
    d["gap_por_producto"] = {}       # sin rezagados
    d["valle"] = None
    return d


# ---------------- causal ----------------

def test_causal_hecho_causa_accion_delta():
    r = _ra.responder("¿por qué está corto Cajúa?", entidad="CAJUA",
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k))
    assert "HECHO" in r and "CAUSA" in r and "ACCIÓN" in r and "DELTA" in r
    assert "CAJUA" in r and "75" in r          # concentración
    assert "Paro por falla" in r               # evidencia del comentario

def test_causal_sin_evento_declara():
    # el 2º detractor (CPO-09) no tiene eventos; el 1º sí — el cuerpo cita el que existe, no inventa
    r = _ra.responder("¿qué campos pesan?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k))
    assert "CPO-09" in r


# ---------------- REGLA CERO (la prueba crítica) ----------------

def test_regla_cero_no_inventa_rezago():
    r = _ra.responder("¿por qué está corto Castilla?", entidad="CASTILLA",
                      _ejecutivo_fn=lambda **k: _fake_en_meta(**k))
    assert "no hay rezago" in r.lower()
    # nunca debe hablar de faltante/déficit cuando va en meta
    assert "faltante" not in r.lower() and "déficit" not in r.lower()


# ---------------- proyección ----------------

def test_proyeccion_pace():
    r = _ra.responder("¿cómo vamos?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k))
    assert "PROYECCIÓN" in r and "día" in r
    assert "acelerar" in r.lower()             # delta_pct 82 > 0 → necesita acelerar


# ---------------- fase: diferidas/economia responden honesto ----------------

def test_diferidas_mensaje_de_fase():
    r = _ra.responder("¿qué pasó con las diferidas?", entidad=None,
                      _ejecutivo_fn=lambda **k: _fake_con_rezago(**k))
    assert "próxima fase" in r.lower()
```

## 6. Orden de ejecución

1. `analisis/api.py` (5.0, param `pulir` — 3 ediciones exactas). **`py_compile`.** Correr **V0**
   (no-regresión del tablero) ANTES de seguir — si el tablero cambia, DETENERSE.
2. `analizar/__init__.py` (5.4) → `analizar/subrouter.py` (5.2) → `analizar/plantilla.py` (5.3) →
   `respuesta_analizar.py` (5.1). **`py_compile` de los 4.**
3. `config.py` (5.5) + `maquina_q.py` (5.6, import + elif). **`py_compile` de ambos.**
4. golden (5.7) + runner (5.8) + tests (5.9). **`py_compile` del runner y el test.**
5. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **El número/hecho es VERBATIM de Python** (desde `ejecutivo`); el LLM solo el intro cordial.
2. **REGLA CERO** (AF-A5/A10): si no hay rezago, se DECLARA; NUNCA se fabrica un faltante/déficit.
3. **A `analisis/api.py` SOLO se le añade el param `pulir`** (RA-1): NO se refactoriza
   `_ejecutivo_core`, NO se toca la query de KPIs/gap/valle/pace. El tablero (sin `pulir`) queda
   byte-idéntico (V0). `ejecutivo(..., pulir=False)` mata el hang de 180s de Gemma. DELTA lee
   `tarjetas` (AF-A4); situación se re-deriva de `titular` (AF-A5).
4. **Entidad NO nombrada ⇒ GLOBAL; entidad nombrada irresoluble ⇒ fallo honesto** (RA-2) — nunca
   global silencioso.
5. **Coherencia chat↔tablero gratis:** al reusar `ejecutivo` (no fork), el chat y el panel no divergen.
6. **Edificio separado:** cero imports de `consulta/` v1. Reusar `respuesta_base`, `cuantificar.resolver`,
   `cuantificar.validador.fmt_valor` (todo intra-v2, permitido). **NO** importar `cuantificar.slots`
   (RA-3: periodo se dejó fuera de Fase 1).
7. **Fase 1 = causal + proyección, BACKEND-ONLY, sin panel, sin memoria _CTX.** Diferidas/economía →
   mensaje honesto de fase. (Memoria/panel/diferidas = fases posteriores.)
8. **NO usar el LLM local de dev**; runtime/navegador/pytest → servidor de pruebas.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo «servidor»)

- **V0** (dev, datos, no-regresión del tablero — RA-1) 1 SOLO proceso aislado:
  `ejecutivo(entidad="RUBIALES", segmento="ecp", nivel="campo", periodo=None)` (SIN `pulir`, como el
  endpoint) → devuelve el mismo `titular`/`gap_por_producto`/`valle` que antes del cambio
  (p.ej. CRUDO `real`/`valor_pct` coherentes con el panel); y
  `ejecutivo(..., pulir=False)` → devuelve la MISMA data estructural + `secciones` NO nula
  (fallback determinista) + `meta.generado_por != "llm"`. Confirma que `pulir` no altera el tablero.
- **V1** (estático) `py_compile` de `analisis/api.py` + `subrouter/plantilla/respuesta_analizar/config/maquina_q` → OK.
- **V2** (dev, puro Python, SIN BD) `subrouter.sub_intencion`:
  `"¿por qué está corto Cajúa?"→causal`; `"¿cómo vamos?"→proyeccion`; `"¿vamos a cerrar?"→proyeccion`;
  `"¿qué pasó con las diferidas?"→diferidas`; `"¿EBITDA de Castilla?"→economia`.
- **V3** (dev, puro Python, SIN BD — `_ejecutivo_fn` FAKE) `respuesta_analizar.responder(...,
  _ejecutivo_fn=fake_con_rezago)` → el str trae `HECHO`, `CAUSA`, `ACCIÓN`, `DELTA`, `CAJUA`, `75`.
- **V4** (dev, puro Python, SIN BD — REGLA CERO) `responder(..., _ejecutivo_fn=fake_en_meta)` →
  contiene "no hay rezago"; **NO** contiene "faltante" ni "déficit".
- **V5** (dev, datos, SIN LLM — 1 SOLO proceso aislado, con `CONSULTA_ANALIZA_LLM=false`) llamar
  `respuesta_analizar.responder("¿por qué está corto CAJUA?", entidad="CAJUA")` contra la BD real (sin
  inyección) → devuelve un str no vacío con `HECHO`/`CAUSA` y cifras coherentes con el panel de CAJÚA,
  **en <5s** (confirma que `pulir=False` evita el hang de Gemma — RA-1). Confirma también AF-A2
  (`ejecutivo` llamado como función con args explícitos + `pulir`).
- **V6** (servidor) `run_golden_analizar.py` → ≥90%; pytest `tests/test_analizar.py` verde.
- **V7** (servidor, navegador) Motor v2: "¿por qué está corto Cajúa?" → HECHO/CAUSA/ACCIÓN/DELTA con
  intro cálido; "¿está corto Castilla?" (en meta) → "no hay rezago" (REGLA CERO, NO inventa); "¿cómo
  vamos?" → proyección de cierre. Jerarquizar/Cuantificar/OUT sin regresión. Paridad qwen/gemma4 del intro.

## 9. Fuera de alcance (NO hacer)

- **Diferidas** (lector `ECP_DIFERIDAS`, histórico rotulado — `analiza.md` Fase 2) y **economía/EBITDA**
  (vía robustez — Fase 3). En Fase 1 devuelven mensaje honesto "próxima fase".
- **Panel derecho** para Analizar (el visor no cambia; Fase 1 es solo texto).
- **Memoria _CTX / drills conversacionales** para Analizar (fase posterior; evita la clase de bugs de
  colisión entre drills ya vista en Cuantificar).
- **Refactor `_ejecutivo_core`** (AF-A2: se llama con args explícitos). El ÚNICO cambio a
  `analisis/api.py` es el param aditivo `pulir` (RA-1) — nada más de ese archivo se toca.
- **Rama B (filiales)**, **valle de gas/blancos** (el motor solo detecta valle de crudo), **causa a
  grano pozo** (no existe en INGESTA), **DELTA vs snapshot de reporte previo** (esquema no lo guarda —
  `analiza.md` §6.1, decisión A1 cerrada: DELTA = vs promedio 2026).
- **Editar `patrones_grupo.yaml`** (el clasificador ya enruta "analizar"; no se toca).
- **Pulido LLM de la prosa** (`secciones`): Fase 1 es determinista; el LLM solo redacta el intro.
```
