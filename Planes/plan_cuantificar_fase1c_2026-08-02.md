# Plan de ejecución — Cuantificar · SUB-FASE 1c (la prosa honesta)

> **Tablas: N/A** — esta sub-fase NO toca ingesta ni tablas fuente (regla de cobertura §0.2 no aplica;
> es capa de respuesta/prosa sobre cifras ya calculadas en 1b).
>
> **Para:** un agente Executor SIN contexto del repo. Todo aquí es literal: rutas absolutas, código
> completo de referencia, decisiones cerradas y criterios verificables (comando → resultado esperado).
>
> **Precede:** `plan_cuantificar_fase1_2026-08-02.md` (plan madre, sub-fases 1a→1e). 1a y 1b YA están
> hechas y commiteadas (`f157a40`). Esta es la 1c.
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

Antes de cerrar el plan se auditó el código real. Cuatro hallazgos, ya incorporados abajo:

| # | Hallazgo (verificado contra el código) | Efecto en el plan |
|---|----------------------------------------|-------------------|
| **H1** | **`get_settings()` NO está cacheado** (`def get_settings(): return Settings()`, `config.py:50`). Cada llamada re-lee el env/.env; cada módulo captura su `_s` al importarse. | Las validaciones funcionan poniendo la env var **ANTES del import**. Se eliminan las notas "si pydantic cachea" (innecesarias). |
| **H2** | **`_llm` de jerarquizar lo usa SOLO `_intro_llm`** (`:325`). Al delegar en `respuesta_base`, mueren además `import json`, `import urllib.error/request`, `_OLLAMA_URL`, `_MODELO`, `_ENV_TIMEOUT` (verificado: son sus únicos usos, `:49-56`). | Edición **E** los retira TODOS (limpio; no cambia comportamiento). `_s` se conserva (lo usa el flag). |
| **H3** | **El ejemplo de no-regresión "cuantas gerencias…" es débil:** los CONTEOS NO viven en jerarquizar (su docstring lo dice) → devolvería `None` y la comparación V6 no probaría nada. | V0/V6 usan una pregunta VERIFICADA que da envoltorio completo: **"a que activo pertenece Rubiales"** (probada, len 207). |
| **H4** | **Retry 2× del intro = 60s de espera en gemma frío** (139): cada intento es un timeout de 30s. jerarquizar NO reintenta (llama `_intro_llm` una vez). | `_intro` **corta en el 1er retorno vacío** (timeout/off/fallo → no reintentar); solo reintenta si el LLM devolvió texto que falló la validación. |

---

## 1. Contexto

**Motor Q v2** vive en `INGESTA/Rep_Prod/backend/app/features/consulta_v2/` (edificio SEPARADO;
cero imports de `consulta/` v1 congelada — lo reusado se **forkea** con marca `# FORK de ...`).

El grupo **Cuantificar** ya responde la cifra real (sub-fase 1b): a "cuánto produjo Rubiales en abril"
devuelve **un string seco**:

```
el Campo RUBIALES produjo 10.966.768 bbl de crudo en Abril 2026 — 90.8% del presupuesto (Alineado) · mes cerrado. Presupuesto del mes: 12.074.849 bbl.
```

**Objetivo de 1c:** que esa respuesta salga con **envoltorio cordial**, igual que el grupo Jerarquizar:
**intro cálido (LLM) + cuerpo VERBATIM (Python) + cierre (Python)**, con un **validador** que garantiza
mecánicamente que el LLM NO tocó el número (regla madre: *Python calcula, el LLM solo redacta*).

**Cómo funciona hoy el envoltorio cordial de Jerarquizar** (a replicar/compartir), en
`.../consulta_v2/respuesta_jerarquizar.py`:
- `_llm(prompt)` → POST a Ollama (`format:"json"`, `temperature 0.8`, `num_predict 160`, timeout 30s).
- `PROMPT_ENV` → prompt del intro (pide `{"intro":"..."}`; prohíbe dar datos/repetir hechos).
- `_intro_llm(canonical, niv, usuario)` → gate por `_s.consulta_jerarq_llm`; si off o falla → `""`.
- `_envolver(canonical, niv, body, ofertas, usuario)` → `intro\n\n body\n\n cierre` (o sin intro si `""`).
- Flags en `.../app/core/config.py`: `consulta_ollama_url`, `consulta_llm_model`, `consulta_jerarq_llm`,
  `consulta_narra_llm`, `consulta_out_llm`, `consulta_warmup`. **NO existe** `consulta_cuant_llm` (se crea).

---

## 2. Objetivo (resultado observable)

Tras 1c, `respuesta_cuantificar.responder(...)` devuelve (ejemplo con el flag ON):

```
Claro, Javier, aquí tienes la cifra.

el Campo RUBIALES produjo 10.966.768 bbl de crudo en Abril 2026 — 90.8% del presupuesto (Alineado) · mes cerrado. Presupuesto del mes: 12.074.849 bbl.

¿Quieres verlo mes a mes?
```

Con el flag OFF (dev, qwen pobre) o si el LLM falla → **sin intro**, solo cuerpo + cierre (fallback
determinista, nunca se rompe). Un mes **en curso** narra "proyección". Un intro que invente un número
se **descarta** (validador) y cae a solo-cuerpo.

---

## 3. Prerequisitos

- Backend en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`.
- Ejecutar Python con **`uv run python`** desde ese directorio (tiene el venv con las deps).
- Postgres dev `daily_report_prod` accesible (lo lee `analisis.desempeno`, ya usado por 1b).
- **NO se necesita Ollama corriendo** para las validaciones (todas corren con el flag OFF → intro `""`,
  determinista). El camino LLM se prueba en 139/navegador, no aquí.

---

## 4. Inventario de archivos

| # | Acción | Ruta absoluta |
|---|--------|---------------|
| A | **CREAR** | `...\consulta_v2\respuesta_base.py` — envoltorio compartido (intro LLM + envolver) |
| B | **EDITAR** | `...\app\core\config.py` — añadir flag `consulta_cuant_llm` |
| C | **CREAR** | `...\consulta_v2\cuantificar\validador.py` — formatea cuerpo + valida intro |
| D | **EDITAR** | `...\consulta_v2\respuesta_cuantificar.py` — usar respuesta_base + validador |
| E | **EDITAR** | `...\consulta_v2\respuesta_jerarquizar.py` — refactor a respuesta_base (no-regresión) |

(Base de rutas: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features`)

---

## 5. Especificación (código completo de referencia)

### A. CREAR `respuesta_base.py`

Extrae el `_llm` + intro + envolver de `respuesta_jerarquizar.py`, generalizados (prompt y gate como
parámetros). Lo usarán **jerarquizar y cuantificar**.

```python
"""respuesta_base.py — envoltorio cordial COMPARTIDO (Motor Q v2).

intro (LLM, saludo dinámico) + cuerpo (hechos VERBATIM de Python) + cierre (Python, exacto).
Extraído de respuesta_jerarquizar.py para que jerarquizar y cuantificar compartan la misma máquina.
El LLM escribe SOLO el intro; jamás toca hechos/números. Si el flag está off o el LLM falla → intro "".
"""
import json
import urllib.error
import urllib.request

from app.core.config import get_settings

_s = get_settings()
_OLLAMA_URL = _s.consulta_ollama_url
_MODELO = _s.consulta_llm_model
_ENV_TIMEOUT = 30


def _llm(prompt: str) -> str:
    body = json.dumps({
        "model": _MODELO, "prompt": prompt, "stream": False, "format": "json",
        "options": {"temperature": 0.8, "num_predict": 160},
    }).encode()
    req = urllib.request.Request(_OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_ENV_TIMEOUT) as r:
        return json.load(r).get("response", "")


def intro_llm(prompt: str, activo: bool) -> str:
    """Intro cálido (una frase). '' si el flag está off o el LLM falla. El prompt debe pedir
    {"intro":"..."} con format:json. NUNCA lanza: cualquier fallo → '' (fallback determinista)."""
    if not activo:
        return ""
    try:
        data = json.loads((_llm(prompt) or "").strip())
        return (data.get("intro") or "").strip() if isinstance(data, dict) else ""
    except (json.JSONDecodeError, TypeError, urllib.error.URLError, OSError, TimeoutError):
        return ""
    except Exception:
        return ""


def envolver(intro: str, body: str, cierre: str) -> str:
    """intro (si hay) + body VERBATIM + cierre. Idéntico al _envolver de jerarquizar."""
    return f"{intro}\n\n{body}\n\n{cierre}" if intro else f"{body}\n\n{cierre}"
```

### B. EDITAR `config.py` — añadir el flag

Localizar el bloque de flags `consulta_*` (tras `consulta_jerarq_llm`, ~línea 31) e **insertar**:

```python
    # Motor Q v2 · grupo Cuantificar: el LLM ENVUELVE la cifra (saludo cordial dinámico); la cifra va
    # VERBATIM (Python) → el LLM no toca el número (regla madre + validador). Default true; false =
    # solo cuerpo + cierre. Si el LLM falla/está frío → fallback determinista (nunca se rompe).
    consulta_cuant_llm: bool = True
```

### C. CREAR `cuantificar/validador.py`

```python
"""cuantificar/validador.py — garantía mecánica de la regla madre + formato del cuerpo (Motor Q v2).

Dos responsabilidades:
  (a) formatear_cuerpo(res) — el cuerpo VERBATIM: Python arma el literal es-CO (12.074.849) y la regla
      de proyección. El LLM NUNCA lo toca (lección D-N5: 'redondea' a "12,3 millones").
  (b) intro_valido(intro)  — el intro es SOLO saludo: sin dígitos ni unidades. Si el LLM filtró un
      número, se descarta el intro (cae a solo-cuerpo). Es la red mecánica que hace cumplir la regla.
"""
import re

_TIENE_DIGITO = re.compile(r"\d")
_UNIDADES = ("barril", "bbl", "mscf", "%", "porcentaje", "presupuesto", "millones", "millón")


def _fmt(n) -> str:
    """Miles es-CO, 0 decimales (10966768 -> '10.966.768'). Igual criterio que el chat (__cnMilesEC)."""
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def formatear_cuerpo(res: dict) -> str:
    """Cuerpo VERBATIM desde el contrato §7 (dict de ejecutor.ejecutar_n1). Regla de proyección:
    si huella.es_proyeccion, el texto DICE 'proyección · N/total días'."""
    real = _fmt(res["resultado"]["valor"])
    pct = f"{res['cumplimiento_pct']}%" if res.get("cumplimiento_pct") is not None else "s/d"
    ppto = _fmt(res["referencia_valor"]) if res.get("referencia_valor") else None
    mes = res["mes"]
    corte = ("mes cerrado" if mes["completo"]
             else f"proyección · {mes['dias_con_data']}/{mes['dias_del_mes']} días")
    linea = (f"{res['entidad_cualificada']} produjo {real} bbl de crudo en {mes['nombre']} "
             f"{mes['anio']} — {pct} del presupuesto ({res['estado']}) · {corte}.")
    if ppto:
        linea += f" Presupuesto del mes: {ppto} bbl."
    for a in res.get("avisos", []):
        linea += f" ⚠️ {a}"
    return linea


def intro_valido(intro: str) -> bool:
    """El intro es SOLO saludo: sin dígitos (D-N5: el LLM no debe filtrar cifras) y sin unidades/lexicón
    de presupuesto. '' o None → inválido (no hay intro que envolver)."""
    if not intro:
        return False
    low = intro.lower()
    if _TIENE_DIGITO.search(intro):
        return False
    if any(u in low for u in _UNIDADES):
        return False
    return True
```

### D. EDITAR `respuesta_cuantificar.py`

Reemplazar el archivo COMPLETO por esta versión (usa respuesta_base + validador; el `_cuerpo`/`_fmt`
locales de 1b se retiran — ahora viven en validador.py):

```python
"""respuesta_cuantificar.py — respuesta del grupo CUANTIFICAR (Motor Q v2, Fase 1).

Sub-fase 1c (plan_cuantificar_fase1c): la PROSA HONESTA. La cifra (1b) sale ahora con envoltorio
cordial — intro cálido (LLM, respuesta_base) + cuerpo VERBATIM (Python, validador) + cierre (Python).
El validador garantiza que el LLM no filtró números en el intro; si falla/está off → solo cuerpo+cierre.

Pendiente: panel derecho (1d), N2 acumulado + memoria _CTX (1e). `catalogo.get()` al importar →
arranque ruidoso si el YAML está mal.
"""
from app.core.config import get_settings
from app.features.consulta_v2 import respuesta_base
from app.features.consulta_v2.cuantificar import catalogo as _catalogo
from app.features.consulta_v2.cuantificar import resolver as _resolver
from app.features.consulta_v2.cuantificar import slots as _slots
from app.features.consulta_v2.cuantificar import ejecutor as _ejecutor
from app.features.consulta_v2.cuantificar import validador as _validador

_catalogo.get()   # fuerza carga+validación del catálogo al importar (arranque del backend)
_s = get_settings()

# El LLM escribe SOLO el intro (calidez). Prohibido dar cifras — el cuerpo (aparte) las lleva; si el
# LLM las repite, el validador descarta el intro. Pide {"intro":"..."} con format:json (obligatorio
# en gemma@139, que en texto plano devuelve vacío).
PROMPT_CUANT = """Eres el asistente de producción de hidrocarburos de Ecopetrol: cordial, cercano y natural.
Voy a mostrar una CIFRA de producción de {entidad} — se muestra aparte, NO la repitas, NO inventes números.
Escribe UNA sola frase de presentación, cálida y BREVE, en español, del tipo "Claro, aquí tienes la cifra…".
Usa a veces el nombre del usuario ({usuario}). Varía el fraseo.
NO des ninguna cifra, NO menciones barriles ni porcentajes ni presupuesto, NO prometas nada. Solo saluda y anuncia que aquí está el dato.
Responde SOLO con JSON válido: {{"intro": "..."}}"""

_CIERRE = "¿Quieres verlo mes a mes?"   # ofrece N3/N4; en 1e alimentará la memoria _CTX


def _intro(res: dict, usuario) -> str:
    """Intro validado. '' si el flag está off, el LLM falla/timeout o el intro no pasa la validación.
    H4: corta en el 1er retorno vacío (timeout/off → reintentar sería otro timeout de 30s = 60s de
    espera en gemma frío). Solo reintenta 1 vez si el LLM SÍ devolvió texto pero traía un número."""
    if not _s.consulta_cuant_llm:
        return ""
    prompt = PROMPT_CUANT.format(entidad=res["entidad_cualificada"], usuario=usuario or "el usuario")
    for _ in range(2):
        cand = respuesta_base.intro_llm(prompt, True)
        if not cand:                        # timeout/off/fallo → no tiene sentido reintentar
            return ""
        if _validador.intro_valido(cand):
            return cand
    return ""                               # devolvió texto 2 veces pero con número → sin intro


def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None):
    """1c: resuelve → cifra (ejecutor) → intro cálido + cuerpo VERBATIM + cierre. Nunca None."""
    resuelta = _resolver.resolver_unico(entidad or texto)
    if resuelta is None:
        eco = f" No reconocí «{entidad}» en el catálogo." if entidad else ""
        return ("No identifiqué una entidad en tu pregunta para cuantificar." + eco
                + " ¿Puedes nombrar un campo, activo o gerencia?")
    if resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                "La desambiguación llega en una próxima fase; por ahora prueba con un nombre único.")

    res = _ejecutor.ejecutar_n1(resuelta, _slots.extraer_slots(texto))
    if not res.get("aplica"):
        return res.get("texto", "No pude cuantificar esa pregunta.")

    cuerpo = _validador.formatear_cuerpo(res)
    intro = _intro(res, usuario)
    return respuesta_base.envolver(intro, cuerpo, _CIERRE)
```

### E. EDITAR `respuesta_jerarquizar.py` — refactor a `respuesta_base` (no-regresión)

Objetivo: que jerarquizar use la MISMA máquina compartida, SIN cambiar su salida. Tres ediciones
quirúrgicas (el resto del archivo NO se toca):

**E.1** — Añadir el import (junto a los otros imports de `app.features.consulta_v2`, ~línea 28):
```python
from app.features.consulta_v2 import respuesta_base
```

**E.2** — **BORRAR** el plumbing del LLM que ahora vive en `respuesta_base` (verificado H2: son sus
únicos usos). Retirar:
- la función privada `_llm(prompt)` completa (~líneas 48-56, de `def _llm(prompt):` hasta
  `return json.load(r).get("response", "")`);
- las 3 asignaciones de módulo `_OLLAMA_URL = ...`, `_MODELO = ...`, `_ENV_TIMEOUT = 30` (~líneas 33-35);
- los imports que quedan MUERTOS: `import json` (~20), `import urllib.error` (~21), `import urllib.request` (~22).

⚠️ **CONSERVAR** `_s = get_settings()` (lo usa el flag en E.3), `PROMPT_ENV`, y los imports
`import sqlalchemy as sa`, `from app.core.config import get_settings`, `from app.core.db import get_engine`,
`from app.features.consulta_v2.normaliza import norm` (los usa el resto del archivo).

**E.3** — Reemplazar las funciones `_intro_llm` y `_envolver` (que hoy contienen la lógica cruda) por
estas versiones que delegan en `respuesta_base` (misma firma, misma salida). Copiar TAL CUAL:
```python
def _intro_llm(canonical, niv, usuario):
    """Solo el saludo/lead-in cálido y dinámico. '' si el LLM falla o está off (sin intro)."""
    prompt = PROMPT_ENV.format(entidad=canonical, nivel=niv, usuario=usuario or "el usuario")
    return respuesta_base.intro_llm(prompt, _s.consulta_jerarq_llm)


def _envolver(canonical, niv, body, ofertas, usuario):
    """intro (LLM, dinámico) + body (hechos VERBATIM) + cierre (Python, exacto)."""
    intro = _intro_llm(canonical, niv, usuario)
    cierre = f"¿Quieres {ofertas}?"
    return respuesta_base.envolver(intro, body, cierre)
```

(Los imports muertos ya se retiraron en E.2 — no quedan pendientes de limpieza.)

---

## 6. Orden de ejecución

1. **A** (`respuesta_base.py`) — crear.
2. **B** (`config.py`) — añadir flag.
3. **C** (`validador.py`) — crear.
4. **D** (`respuesta_cuantificar.py`) — reemplazar.
5. **E** (`respuesta_jerarquizar.py`) — refactor quirúrgico.
6. Correr TODAS las validaciones (§8). Si alguna falla → detener y reportar (no "arreglar y seguir").

---

## 7. Reglas no negociables

1. **El número es VERBATIM de Python.** El LLM escribe SOLO el intro. El cuerpo lo formatea
   `validador.formatear_cuerpo`. Prohibido que el LLM produzca/repita cifras.
2. **El validador es la red mecánica:** un intro con dígito o unidad → se descarta (solo-cuerpo).
3. **Fallback determinista SIEMPRE:** flag off o LLM caído → intro `""`, respuesta = cuerpo + cierre.
   Nunca se rompe ni se traga la respuesta.
4. **NO-REGRESIÓN de jerarquizar:** con el flag OFF (determinista), la salida de
   `responder_cordial` debe ser **byte-idéntica** antes y después del refactor E. Si difiere → detener.
5. **`format:"json"` en el intro** (gemma@139 devuelve vacío en texto plano).
6. **Edificio separado:** cuantificar NO importa de `consulta/` (v1). `respuesta_base` vive en
   `consulta_v2/` (raíz del edificio v2) y lo comparten jerarquizar y cuantificar — es v2, permitido.
7. **NO tocar** `maquina_q.py`, `ejecutor.py`, `resolver.py`, `slots.py`, `catalogo.py` (son de 1a/1b).

---

## 8. Validaciones (comando → resultado esperado)

Ejecutar desde `...\INGESTA\Rep_Prod\backend`. **`get_settings()` NO está cacheado (H1)** → basta poner
la env var ANTES del import; cada módulo lee su `_s` al importarse.

**V0 (línea base jerarquizar, ANTES de tocar E — hacerlo lo PRIMERO, sobre código pristino):** captura
la salida determinista (flag off → intro vacío). Pregunta VERIFICADA que da envoltorio completo (H3):
```bash
uv run python -c "import os; os.environ['CONSULTA_JERARQ_LLM']='false'; from app.features.consulta_v2 import respuesta_jerarquizar as j; print(repr(j.responder_cordial('a que activo pertenece Rubiales', usuario='Javier')))" > _base_jerarq.txt 2>NUL
type _base_jerarq.txt
```
→ **Esperado:** una cadena NO vacía (empieza con `'«RUBIALES» · Campo\n...'` y termina en un cierre
`¿Quieres ...?`). Si sale `None` → detener (la pregunta cambió de comportamiento; reportar).

**V1 — py_compile de todo lo nuevo/editado:**
```bash
uv run python -c "import py_compile as p; [p.compile('app/features/consulta_v2/'+f, doraise=True) for f in ['respuesta_base.py','cuantificar/validador.py','respuesta_cuantificar.py','respuesta_jerarquizar.py']]; import py_compile; py_compile.compile('app/core/config.py', doraise=True); print('py_compile OK')"
```
→ **Esperado:** `py_compile OK`.

**V2 — el flag existe y por defecto True:**
```bash
uv run python -c "from app.core.config import get_settings; print('consulta_cuant_llm =', get_settings().consulta_cuant_llm)"
```
→ **Esperado:** `consulta_cuant_llm = True`.

**V3 — validador (unitario, sin LLM):**
```bash
uv run python -c "from app.features.consulta_v2.cuantificar import validador as v; print(v.intro_valido('Claro, Javier, aquí tienes la cifra'), v.intro_valido('Produjo 10 millones de barriles'), v.intro_valido('El presupuesto fue alto'), v.intro_valido(''))"
```
→ **Esperado:** `True False False False`.

**V4 — respuesta cordial con flag OFF (determinista = solo cuerpo + cierre):**
```bash
uv run python -c "import os; os.environ['CONSULTA_CUANT_LLM']='false'; from app.features.consulta_v2 import respuesta_cuantificar as rc; print(rc.responder('cuanto produjo Rubiales en abril', entidad='RUBIALES', usuario='Javier'))"
```
→ **Esperado** (intro vacío → cuerpo + cierre; el número es el de 1b):
```
el Campo RUBIALES produjo 10.966.768 bbl de crudo en Abril 2026 — 90.8% del presupuesto (Alineado) · mes cerrado. Presupuesto del mes: 12.074.849 bbl.

¿Quieres verlo mes a mes?
```

**V5 — regla de proyección (mes en curso dice "proyección"):**
```bash
uv run python -c "import os; os.environ['CONSULTA_CUANT_LLM']='false'; from app.features.consulta_v2 import respuesta_cuantificar as rc; print(rc.responder('cuanto produjo Rubiales', entidad='RUBIALES'))"
```
→ **Esperado:** el cuerpo contiene `proyección · N/31 días` (N = días con reporte del último mes), o
`mes cerrado` si el último mes está completo. (Documentar cuál salió; ambos son válidos según el techo
de datos.)

**V6 — NO-REGRESIÓN jerarquizar (DESPUÉS de E):** repetir EXACTO el comando de V0 (misma pregunta) y comparar:
```bash
uv run python -c "import os; os.environ['CONSULTA_JERARQ_LLM']='false'; from app.features.consulta_v2 import respuesta_jerarquizar as j; print(repr(j.responder_cordial('a que activo pertenece Rubiales', usuario='Javier')))" > _post_jerarq.txt 2>NUL
fc _base_jerarq.txt _post_jerarq.txt
```
→ **Esperado:** `fc` reporta **sin diferencias** (salida byte-idéntica). Si difiere → DETENER y reportar.
Al terminar, borrar los temporales: `del _base_jerarq.txt _post_jerarq.txt`.

**V7 — pytest (no rompe el clasificador ni jerarquizar):**
```bash
uv run pytest tests/test_consulta_v2_clasificador.py -q
```
→ **Esperado:** `60 passed` (o el mismo número que antes de 1c; NINGÚN fallo nuevo).

**V8 — limpieza:** si alguna prueba escribió filas en `core.clasificacion_log` con `usuario` de prueba,
borrarlas (patrón robusto `with engine.begin()`):
```bash
uv run python -c "from app.core.db import get_engine; from sqlalchemy import text; e=get_engine(); c=e.begin(); conn=c.__enter__(); n=conn.execute(text(\"DELETE FROM core.clasificacion_log WHERE usuario IN ('Javier','verif')\")).rowcount; c.__exit__(None,None,None); print('borradas:', n)"
```
> (Las validaciones V4-V6 llaman `responder(...)` directo, NO `maquina_q.clasificar` → NO escriben en la
> libreta. Solo pytest podría; V8 es por si acaso. Si `borradas: 0`, perfecto.)

---

## 9. Fuera de alcance (explícito — NO hacer)

- **Panel derecho** (doble entregable): es 1d.
- **N2 acumulado + memoria `_CTX` + drill "mes a mes"**: es 1e (el cierre "¿Quieres verlo mes a mes?"
  se PINTA pero aún NO responde el follow-up).
- **Gas, blancos, filiales, N3/N4, referencias ≠ PPTO, conteos**: Fase 2-4.
- **Limpiar imports muertos** de jerarquizar o unificar más código: no es objetivo de 1c.
- **Tocar el LLM real / probar el intro cálido en vivo**: se verifica en 139/navegador (aquí todo con
  flag OFF, determinista). NO se requiere Ollama para las validaciones.

---

## 10. Criterio de cierre (COMPUERTA 1c)

V1-V7 verdes (con V6 = byte-idéntico) → 1c lista. El usuario verifica el intro cálido en navegador
(flag ON) por separado. Recién ahí se abre 1d.
```
```

---

## Decisión que necesita tu nod (no la cierro solo)

La edición **E** refactoriza `respuesta_jerarquizar.py` (código commiteado y funcionando) para compartir
`respuesta_base`. Es lo que pide el plan madre (H4) y la no-regresión V6 lo blinda (byte-idéntico con
flag off). **Alternativa más conservadora:** NO tocar jerarquizar en 1c — crear `respuesta_base`, que
solo cuantificar lo use, y unificar jerarquizar después. Menos DRY, cero riesgo sobre jerarquizar.
Mi recomendación: **hacer E con la V6** (es segura y evita deuda). Dime si prefieres la conservadora.
