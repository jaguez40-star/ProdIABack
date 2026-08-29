# Plan QV2-META — `capacidades.py`: responder «¿cuál es tu finalidad?» y «hola»

**ID tarea:** QV2-META
**Fecha:** 2026-08-25
**Versión:** v2 (auditada — flujo profesional §15, pasos 1-3 aplicados)
**Alcance:** Motor Q v2 · rama OUT de `maquina_q._clasificar_core` + guarda en `_continuacion`
**Decisiones cerradas del usuario:** solo burbuja (sin panel) · se cubre TAMBIÉN el saludo.

---

## 0. Contexto para el agente EXECUTOR

> El executor NO tiene acceso a conversaciones previas ni al historial de Git.
> Todo lo necesario está aquí.

**Proyecto:** ProdIA 2.0 — asistente conversacional de producción de hidrocarburos
de Ecopetrol. Backend FastAPI (INGESTA, puerto 8088) + Flask (puerto 8020).

**Raíz del backend a tocar:**
`c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\backend\`

**Módulo:** `app/features/consulta_v2/` — el «Motor Q v2», que clasifica cada pregunta
en 4 grupos (`jerarquizar` · `cuantificar` · `analizar` · `desconocido`) y responde.

**Flujo relevante** (`maquina_q.py`):

```
clasificar(texto, usuario, conversation_id, log)
  └─ _continuacion(texto, ctx)      ← reescribe respuestas CORTAS de continuación
  └─ _clasificar_core(...)
       ├─ Capa 1  patrones.py (regex/YAML)
       ├─ Capa 2  clasificador_llm.py (LLM, solo si Capa 1 no atrapa)
       ├─ filtro de dominio  dominio.py + detectar_entidad
       └─ rama OUT (grupo == "desconocido")
            (B) no_soportado.py   → capacidad no construida
            (C) incompleta.py     → frase mal formada
            (A) respuesta_out.py  → LLM redacta el "fuera de dominio"
```

**Convenciones del módulo (obligatorias):**
- Todo el código, comentarios y docstrings **en español**.
- `norm()` (`normaliza.py`) = UPPER + trim + colapsar espacios + plegar acentos.
  **⚠️ NO retira signos de puntuación** (ver Hallazgo H1).
- Los detectores deterministas (`dominio.py`, `no_soportado.py`, `incompleta.py`) son
  **módulos PUROS**: solo `re` + `norm`. Sin BD, sin LLM, sin YAML.
- Regex compilados en el import, sobre texto normalizado.

---

## 1. Problema (medido, no supuesto)

Se siguió «¿cuál es tu finalidad?» por el motor:

1. **Capa 1** — ningún patrón de `config/patrones_grupo.yaml` calza
   (`'QUE\s+ES\s+\w+'` exige `ES`, no `ERES`) → `clasificar_capa1` devuelve `None`.
2. **Capa 2 (LLM)** — el prompt de `clasificador_llm.py:29-31` lista explícitamente
   «saludos, texto suelto» como `desconocido` → **`grupo = desconocido`**.
3. **Rama OUT** (`maquina_q.py:408-437`) — sin entidad en `_CTX`, (B) no aplica;
   (C) no dispara (no hay verbo de acción) → cae en (A) `respuesta_out.redactar_out`.
4. Y ese prompt (`respuesta_out.py:30-36`) instruye literalmente:

   > «El usuario hizo una pregunta que está **FUERA de tu dominio**… Le explique con
   > amabilidad que ese tema **se sale del contexto** de este asistente.»

**Es un bug de TRATO, no de clasificación.** El motor responde que preguntarle *qué
sabe hacer* es un tema ajeno. Idéntico al bug que originó `incompleta.py` (su
docstring, líneas 9-11: *«La clasificación 'desconocido' es CORRECTA; lo que estaba
mal era el TRATO»*), pero en su forma más visible: es de lo primero que teclea un
usuario nuevo, y la respuesta lo despide.

Agravante: el prompt OUT ordena *«Mencione con tacto EL TEMA CONCRETO que preguntó»*
→ un modelo pequeño puede producir «sobre tu finalidad… eso se sale de mi contexto».

Lo mismo con **«hola»**, que el golden ya fija como `desconocido`
(`golden/clasificacion_golden.yaml:96-97`) y hoy recibe ese mismo despido.

---

## 2. 🔴 Hallazgos de la auditoría (§15 pasos 1-3)

> Estos 5 hallazgos se descubrieron auditando el código real y **cambian el diseño**.
> El executor debe leerlos: explican por qué el código de §4 es como es.

### 🔴 H1 — `norm()` NO retira signos de puntuación → el ancla `^` del saludo falla

`normaliza.py` solo pliega acentos y colapsa espacios. Medido:

| entrada | `norm()` |
|---|---|
| `¡Hola!` | `¡HOLA!` |
| `¿Hola?` | `¿HOLA?` |
| `¿cuál es tu finalidad?` | `¿CUAL ES TU FINALIDAD?` |

Un ancla `^(HOLA|...)` **NO matchea `¡HOLA!`** (medido: `False`). El regex del saludo
debe tolerar signos de apertura al inicio: `^[¡¿\s]*(...)`.

**No afecta al regex de capacidades:** `\b` sí maneja el `¿` pegado (medido:
`¿QUE PUEDES HACER?` → match `True`). Es la misma nota de `no_soportado.py:22-23`.

### 🔴 H2 — BLOQUEANTE: `_continuacion` secuestra 3 de las frases meta ANTES de la rama OUT

`clasificar()` llama a `_continuacion()` **antes** que `_clasificar_core()`. Si hay
contexto vivo (`_CTX[conversation_id]`) y la frase tiene ≤5 tokens, la reescribe.
La última rama usa `_ESTRUCT_KW`, que **contiene `"CUAL"` y `"A QUE"`**. Medido:

| frase | toks | ≤5 | hit en `_ESTRUCT_KW` | destino sin fix |
|---|---|---|---|---|
| `¿cuál es tu finalidad?` | 4 | ✔ | **`CUAL`** | → `"que es CASTILLA"` |
| `cuáles son tus capacidades` | 4 | ✔ | **`CUAL`** | → `"que es CASTILLA"` |
| `para qué sirves` | 3 | ✔ | **`A QUE`** (substring de «pARA QUÉ») | → `"que es CASTILLA"` |
| `¿qué puedes hacer?` | 3 | ✔ | — | (llega bien) |
| `hola` | 1 | ✔ | — | (llega bien) |

**Consecuencia:** a mitad de conversación, «¿cuál es tu finalidad?» devolvería la
ficha jerárquica de CASTILLA. El módulo nuevo **nunca se ejecutaría** —
`_clasificar_core` recibiría ya el texto reescrito.

**Fix obligatorio:** guarda al **inicio** de `_continuacion` (§4.3). Sin ella el plan
no cumple su objetivo en el caso más probable (usuario que ya venía conversando).

### 🟡 H3 — `QUE ES` / `QUIEN ES` son patrones jerarquizar VIVOS

`config/patrones_grupo.yaml` → `grupos.jerarquizar` incluye `'QUE\s+ES\s+\w+'` y
`'QUIEN\s+ES\b'`. Además `_continuacion` reescribe a `f"que es {ent}"` en **tres**
ramas (`maquina_q.py:110`, `:232`, y la estructural).
→ El regex de capacidades debe capturar **solo `QUE ERES` / `QUIEN ERES`**, jamás
`QUE ES` / `QUIEN ES`. Es el falso positivo más caro posible: rompería todo el drill
estructural del motor.

### 🟡 H4 — `usuario` en v2 llega por el body, NO por el riel `pendiente` de v1

`api.py::Preguntar.usuario` (POST body) → `maquina_q.clasificar(usuario=...)`.
**NO aplica** la advertencia de `consulta/meta.py:18-20` sobre `__cnConNombre` y el
guillemot inicial: ese riel es del motor **v1** (status `pendiente`). En v2 el
`mensaje` se sirve tal cual. Si se antepone vocativo, se hace en Python.

### 🟢 H5 — El contrato de salida ya soporta `panel: None`

`_clasificar_core` devuelve siempre `panel` (`maquina_q.py:495`), y OUT lo deja en
`None`. El frontend (`static/js/multitab_shell.js:4991`) ya consume esa forma.
→ «solo burbuja» **no exige ningún cambio de frontend ni de contrato**. Confirmado.

---

## 3. Diseño

Un **cuarto hermano** de la familia de detectores deterministas:

| módulo | pregunta que responde |
|---|---|
| `dominio.py` | ¿es del tema? |
| `no_soportado.py` | ¿está construido? |
| `incompleta.py` | ¿está completa la frase? |
| **`capacidades.py`** (nuevo) | **¿pregunta por mí mismo?** |

**Invariantes heredados (NO negociables):**

1. **Módulo PURO** — solo `re` + `normaliza.norm`.
2. **NO reclasifica.** El grupo sigue siendo `desconocido`; solo cambia el `mensaje`.
   Por eso el golden (que solo asevera el grupo) **no puede romperse**.
3. **Determinista, jamás por el LLM** (razón en §7).
4. **Regla H1 del proyecto** — el mensaje NUNCA termina en pregunta sí/no: un «sí»
   caería en el drill `_AFIRM` de `_continuacion` y devolvería un acumulado.
5. Regex compilados en el import, sobre texto normalizado.

---

## 4. Especificación

### 4.1 Archivo NUEVO — `app/features/consulta_v2/capacidades.py`

Crear con este contenido completo:

```python
"""capacidades.py — detector determinista de preguntas sobre EL ASISTENTE MISMO.

Cuarto hermano de dominio.py (¿es del tema?), no_soportado.py (¿está construido?) e
incompleta.py (¿está completa la frase?). Este responde: ¿la pregunta es sobre MÍ?

Caso de origen (2026-08-25): «¿cuál es tu finalidad?» y «hola» caían en la rama OUT y
las redactaba respuesta_out.py, cuyo prompt tiene la orden literal de decir que el tema
«se sale del contexto de este asistente». El motor respondía que preguntarle qué sabe
hacer es un tema ajeno. Mismo bug de TRATO que originó incompleta.py: la clasificación
'desconocido' es CORRECTA, lo que estaba mal era la respuesta.

🔑 NO reclasifica. El grupo sigue siendo 'desconocido' — solo cambia el mensaje. Por eso
el golden (que solo asevera el grupo, run_golden.py) no puede romperse por este módulo.

🔑 Determinista, JAMÁS por el LLM. La respuesta a «qué sabes hacer» es un INVENTARIO de
capacidades: si lo redacta qwen2.5:3b promete lo que no existe (rangos de días,
trimestres, años) y no_soportado.py se lo niega al turno siguiente — el motor se
contradiría. Mismo argumento que consulta/meta.py:9-16.

🔑 El mensaje NUNCA termina en pregunta sí/no (regla H1, igual que no_soportado.py e
incompleta.py): un "sí" cae en el drill _AFIRM de maquina_q._continuacion y se
reescribe a "acumulado de {entidad}". El cierre pide un SUSTANTIVO.

⚠️ norm() NO retira signos de puntuación (solo pliega acentos y colapsa espacios):
«¡Hola!» normaliza a «¡HOLA!» con el signo PEGADO. Por eso _RX_SALUDO tolera signos de
apertura al inicio — verificado 2026-08-25: sin esa tolerancia «¡Hola!» NO matcheaba.
En _RX_CAPACIDADES no hace falta: \\b sí maneja la frontera entre '¿' y letra.
"""
import re

from app.features.consulta_v2.normaliza import norm

# --- Forma 'capacidades' -----------------------------------------------------------------
# ⚠️ SOLO «QUE ERES»/«QUIEN ERES» — jamás «QUE ES»/«QUIEN ES»: son patrones jerarquizar
# VIVOS (config/patrones_grupo.yaml → grupos.jerarquizar) y además maquina_q._continuacion
# reescribe a f"que es {ent}" en TRES ramas distintas. Capturarlos aquí rompería todo el
# drill estructural del motor. Es el falso positivo más caro posible.
_RX_CAPACIDADES = re.compile(
    r"\b(TU|TUS|SU|SUS)\s+(FINALIDAD|PROPOSITO|FUNCION|FUNCIONES|OBJETIVO|UTILIDAD|"
    r"CAPACIDADES|ALCANCE)\b|"
    r"\bPARA\s+QUE\s+(SIRVES|SIRVE|ESTAS|ERES)\b|"
    r"\bQUE\s+(PUEDES|SABES)\s+(HACER|RESPONDER|DECIRME|CONTARME)\b|"
    r"\bQUE\s+HACES\b|"
    r"\b(EN|CON)\s+QUE\s+(ME\s+)?(PUEDES\s+)?AYUD\w+\b|"
    r"\bCOMO\s+(ME\s+)?(PUEDES\s+)?AYUD\w+\b|"
    r"\bQUIEN\s+ERES\b|\bQUE\s+ERES\b|"
    r"\bQUE\s+(PREGUNTAS|COSAS)\s+.{0,20}\b(HACER|RESPONDER|PREGUNTAR)\b|"
    r"\bDE\s+QUE\s+(ME\s+)?PUEDES\s+HABLAR\b")

# --- Forma 'saludo' ----------------------------------------------------------------------
# ANCLADO ^...$ a propósito: «hola» es un saludo; «hola, ¿cuánto produjo Castilla?» NO —
# lleva una pregunta real detrás y debe seguir su curso normal. El ancla lo resuelve sin
# excepciones. El prefijo [¡¿\s]* es el fix del hallazgo sobre norm() (ver docstring).
_RX_SALUDO = re.compile(
    r"^[¡¿\s]*(HOLA|BUENAS|BUEN\s+DIA|BUENOS\s+DIAS|BUENAS\s+TARDES|BUENAS\s+NOCHES|"
    r"QUE\s+TAL|QUE\s+HUBO|QUIUBO|SALUDOS|HEY|EPA)"
    r"[\s,\.!¡¿\?]*$")


def detectar(texto, hay_entidad):
    """'capacidades' | 'saludo' | None. Determinista y puro.

    `hay_entidad` la calcula el LLAMADOR (maquina_q._clasificar_core ya la tiene de
    detectar_entidad) — mismo criterio que incompleta.detectar, que recibe `hay_entidad`
    y `nivel` ya calculados en vez de recalcularlos.

    GUARDA DE ENTIDAD: si el texto nombra una entidad del catálogo NO es meta-bot.
    «¿qué puedes decirme de Castilla?» es una pregunta de dominio, no sobre el asistente.

    Orden: capacidades ANTES que saludo. El ancla ^...$ del saludo ya descarta
    «hola, ¿qué puedes hacer?», pero el orden lo deja explícito.
    """
    if hay_entidad:
        return None
    t = norm(texto or "")
    if not t:
        return None
    if _RX_CAPACIDADES.search(t):
        return "capacidades"
    if _RX_SALUDO.match(t):
        return "saludo"
    return None


# --- Mensajes ----------------------------------------------------------------------------
# Tres decisiones dentro del texto:
#   1. EJEMPLOS COPIABLES, no categorías abstractas. "cifras de producción" no enseña a
#      preguntar; «¿cuánto produjo RUBIALES en mayo?» sí. Los ejemplos se eligieron entre
#      formas que el motor HOY resuelve (verificadas contra patrones_grupo.yaml y el
#      golden), no entre formas plausibles.
#   2. REGLA H1: cierra pidiendo un SUSTANTIVO, nunca un sí/no.
#   3. NO PROMETE lo que no hay: sin rangos de días, sin trimestres, sin semanas, sin
#      comparar años — no_soportado.py los rechaza, y ofrecerlos aquí sería contradecirse
#      un turno después.
_MSG_CAPACIDADES = (
    "Soy el asistente de producción de Ecopetrol y trabajo sobre los reportes diarios. "
    "Te sirvo en tres frentes: la estructura de la operación —por ejemplo «¿qué es "
    "CASTILLA?» o «¿qué campos tiene el activo CHICHIMENE?»—, las cifras de crudo, gas y "
    "blancos contra el presupuesto —«¿cuánto produjo RUBIALES en mayo?», «el acumulado "
    "del año»— y el análisis del desempeño —«¿qué explica el faltante del mes?», «¿cuál "
    "es la proyección de cierre?»—. Nómbrame un campo, activo o gerencia y arrancamos "
    "por donde prefieras.")

_MSG_SALUDO = (
    "Hola. Soy el asistente de producción de Ecopetrol: te puedo contar cómo está armada "
    "la operación por campos y activos, darte las cifras de crudo, gas y blancos contra "
    "el presupuesto, y analizar el desempeño del mes. Nómbrame un campo, activo o "
    "gerencia, o dime cuál de esos tres frentes te interesa.")

_MENSAJES = {"capacidades": _MSG_CAPACIDADES, "saludo": _MSG_SALUDO}


def mensaje(codigo, usuario=None):
    """Texto determinista de la forma detectada. Jamás pasa por el LLM.

    `usuario` es el nombre que llega en el body del POST (api.py::Preguntar.usuario). Si
    viene, se antepone como vocativo EN PYTHON.
    ⚠️ NO aplica la advertencia de consulta/meta.py:18-20 sobre __cnConNombre y el
    guillemot inicial: ese riel es del motor v1 (status 'pendiente'). En v2 el mensaje se
    sirve tal cual.
    """
    txt = _MENSAJES.get(codigo, _MSG_CAPACIDADES)
    if usuario:
        # El saludo ya arranca con "Hola." → se funde el nombre en él en vez de duplicarlo.
        if codigo == "saludo":
            return txt.replace("Hola.", f"Hola, {usuario}.", 1)
        return f"{usuario}, {txt[0].lower()}{txt[1:]}"
    return txt
```

### 4.2 MODIFICAR — `maquina_q.py` · import

Añadir junto a sus hermanos (bloque de imports, junto a la línea 26
`from app.features.consulta_v2 import incompleta`):

```python
from app.features.consulta_v2 import capacidades
```

### 4.3 🔴 MODIFICAR — `maquina_q.py` · guarda en `_continuacion` (fix del hallazgo H2)

**Localizar** el inicio de la función `_continuacion` (línea ~59). Justo **después**
de las dos primeras líneas (`toks = norm(texto).split()` / `if not toks: return None`)
y **antes** de `t = " ".join(toks)`, insertar:

```python
    t = " ".join(toks)
    # [2026-08-25] QV2-META · GUARDA DE PREGUNTA META. Una pregunta sobre EL ASISTENTE
    # («¿cuál es tu finalidad?», «para qué sirves») NO es una continuación de la charla:
    # no se reescribe, se deja pasar entera para que la rama OUT la reconozca.
    # 🔑 SIN esta guarda el módulo capacidades NUNCA se ejecutaría a mitad de conversación.
    # Medido 2026-08-25 con ctx vivo: «¿cuál es tu finalidad?» (4 toks) y «cuáles son tus
    # capacidades» (4 toks) hacen hit en _ESTRUCT_KW por "CUAL", y «para qué sirves» (3
    # toks) por "A QUE" (substring de «pARA QUÉ») -> las tres caían en la rama estructural
    # de abajo y se reescribían a "que es {entidad}": el usuario pedía saber qué sabe hacer
    # el bot y recibía la ficha jerárquica de CASTILLA.
    # Va ANTES de TODAS las ramas (incluida la de ranking y la de analizar, que cortan con
    # return propio) porque ninguna debe verlas primero.
    if capacidades.detectar(texto, False) is not None:
        return None
```

> ⚠️ Se pasa `hay_entidad=False` **a propósito**: aquí solo interesa saber si la FORMA es
> meta. Si el texto nombrara una entidad, `_RX_CAPACIDADES` no matchearía de todos modos
> («qué puedes decirme de Castilla» no calza con ninguna alternativa del regex), y
> `entidad_en()` ya se evalúa más abajo para las ramas que sí la necesitan.

### 4.4 🔴 MODIFICAR — `maquina_q.py` · rama OUT

**Localizar** el bloque `if grupo == "desconocido" and log:` (línea ~408). Estado actual:

```python
        ctx = _CTX.get(conversation_id) if conversation_id else None
        ent_ctx = (ctx or {}).get("entidad")
        forma = no_soportado.detectar(texto) if ent_ctx else None
        if forma:
            mensaje = no_soportado.mensaje(forma, ent_ctx)
        elif incompleta.detectar(texto, bool(entidad), nivel_dominio(texto)):
            mensaje = incompleta.mensaje("accion_sin_objeto", ent_ctx)
        else:
            mensaje = respuesta_out.redactar_out(texto, usuario=usuario, contexto=ctx)["texto"]
```

**Insertar la rama (META) como PRIMERA de la cadena**, dejando (B), (C) y (A) intactas:

```python
        ctx = _CTX.get(conversation_id) if conversation_id else None
        ent_ctx = (ctx or {}).get("entidad")
        # (META) [2026-08-25] QV2-META. La pregunta es sobre EL ASISTENTE, no sobre
        #     producción («¿cuál es tu finalidad?», «hola»). Va PRIMERA de las cuatro: es
        #     la única que NO depende del contexto — es típicamente el PRIMER turno, cuando
        #     _CTX está vacío y (B) ni siquiera se consulta. Sin ella, el prompt de
        #     respuesta_out respondía que preguntar qué sabe hacer es un tema "fuera de
        #     contexto": el motor despedía al usuario en su primera frase.
        #     `entidad` ya está calculada arriba: no se recalcula (criterio de (C)).
        forma_meta = capacidades.detectar(texto, bool(entidad))
        forma = no_soportado.detectar(texto) if (ent_ctx and not forma_meta) else None
        if forma_meta:
            mensaje = capacidades.mensaje(forma_meta, usuario=usuario)
        elif forma:
            mensaje = no_soportado.mensaje(forma, ent_ctx)
        elif incompleta.detectar(texto, bool(entidad), nivel_dominio(texto)):
            mensaje = incompleta.mensaje("accion_sin_objeto", ent_ctx)
        else:
            mensaje = respuesta_out.redactar_out(texto, usuario=usuario, contexto=ctx)["texto"]
```

**Reglas duras de esta edición:**
- El gate `ent_ctx` de (B) **debe seguir intacto** — `no_soportado` solo se consulta con
  contexto de entidad (su docstring, líneas 12-15, explica por qué: en frío no se puede
  afirmar «no soportado» con honestidad).
- **NO tocar** `panel` — se queda en `None` (decisión del usuario: solo burbuja). El
  contrato de salida ya lo soporta (hallazgo H5).
- **NO tocar** `grupo`, `capa_resolutora`, `GRUPO_LABEL`, ni la Capa 2.

### 4.5 NO tocar `config/patrones_grupo.yaml` — deliberado

La pregunta **debe seguir cayendo en `desconocido`**; lo único que cambia es el mensaje.
Añadir patrones obligaría a tocar `GRUPO_LABEL`, la Capa 2 y el golden: mucho más riesgo
por cero beneficio. Además el YAML se carga una vez al arranque, y no tocarlo evita esa
clase entera de problemas.

---

## 5. Orden de ejecución

| # | Acción | Archivo |
|---|---|---|
| 1 | Crear el módulo | `app/features/consulta_v2/capacidades.py` |
| 2 | Añadir el import | `app/features/consulta_v2/maquina_q.py` |
| 3 | Guarda en `_continuacion` (§4.3) | `app/features/consulta_v2/maquina_q.py` |
| 4 | Rama (META) en OUT (§4.4) | `app/features/consulta_v2/maquina_q.py` |
| 5 | Crear los tests | `tests/test_capacidades.py` |
| 6 | Correr la suite (§6) | — |

---

## 6. Tests — `tests/test_capacidades.py` (crear)

Molde exacto de `tests/test_incompleta.py`: puros, sin BD ni LLM.

```python
"""Tests PUROS (sin BD, sin LLM) del detector de preguntas sobre EL ASISTENTE.

Cuarto hermano de test_no_soportado.py y test_incompleta.py. El caso de origen es real
(2026-08-25): «¿cuál es tu finalidad?» y «hola» recibían el rechazo de FUERA DE DOMINIO
de respuesta_out.py — el motor respondía que preguntarle qué sabe hacer es un tema ajeno.
"""
from app.features.consulta_v2 import capacidades


# --- detectar(): dispara ------------------------------------------------------------------
def test_dispara_pregunta_por_finalidad():
    assert capacidades.detectar("¿cuál es tu finalidad?", False) == "capacidades"
    assert capacidades.detectar("para qué sirves", False) == "capacidades"
    assert capacidades.detectar("cuáles son tus capacidades", False) == "capacidades"


def test_dispara_pregunta_por_ayuda():
    assert capacidades.detectar("¿en qué me puedes ayudar?", False) == "capacidades"
    assert capacidades.detectar("¿cómo puedes ayudarme?", False) == "capacidades"
    assert capacidades.detectar("¿qué puedes hacer?", False) == "capacidades"
    assert capacidades.detectar("quién eres", False) == "capacidades"


def test_dispara_saludo():
    assert capacidades.detectar("hola", False) == "saludo"
    assert capacidades.detectar("buenos días", False) == "saludo"
    assert capacidades.detectar("qué tal", False) == "saludo"
    assert capacidades.detectar("Hola,", False) == "saludo"


def test_saludo_tolera_signos_de_apertura():
    """norm() NO retira puntuación: «¡Hola!» queda «¡HOLA!» con el signo PEGADO. Sin el
    prefijo [¡¿\\s]* del ancla, estas dos NO matcheaban (medido 2026-08-25)."""
    assert capacidades.detectar("¡Hola!", False) == "saludo"
    assert capacidades.detectar("¿Hola?", False) == "saludo"


def test_norm_pliega_acentos():
    assert (capacidades.detectar("¿cuál es tu finalidad?", False)
            == capacidades.detectar("cual es tu finalidad", False))
    assert (capacidades.detectar("buenos días", False)
            == capacidades.detectar("buenos dias", False))


# --- detectar(): NO dispara — el riesgo real es el falso positivo -------------------------
def test_no_le_roba_nada_a_jerarquizar():
    """«QUE ES»/«QUIEN ES» son patrones jerarquizar VIVOS y _continuacion reescribe a
    f"que es {ent}" en TRES ramas. Capturarlos rompería todo el drill estructural."""
    assert capacidades.detectar("qué es CASTILLA", False) is None
    assert capacidades.detectar("que es POE", False) is None          # reescritura literal
    assert capacidades.detectar("quién es el operador de Rubiales", False) is None


def test_no_dispara_si_hay_entidad():
    assert capacidades.detectar("¿qué puedes decirme de Castilla?", True) is None


def test_saludo_con_pregunta_detras_no_dispara():
    """El ancla ^...$: «hola» es saludo, «hola, ¿cuánto produjo Castilla?» NO."""
    assert capacidades.detectar("hola, ¿cuánto produjo Castilla?", False) is None
    assert capacidades.detectar("buenos días, dame el acumulado", False) is None


def test_no_dispara_en_trafico_de_dominio():
    assert capacidades.detectar("cuánto produjo Rubiales en mayo", False) is None
    assert capacidades.detectar("por qué bajó la producción", False) is None
    assert capacidades.detectar("cuántos campos tiene el activo CHICHIMENE", False) is None


def test_bordes():
    assert capacidades.detectar("", False) is None
    assert capacidades.detectar(None, False) is None


# --- mensaje(): inventario honesto, sin sí/no (H1) ----------------------------------------
def test_mensaje_nombra_los_tres_frentes():
    m = capacidades.mensaje("capacidades")
    assert "estructura" in m.lower()
    assert "crudo" in m.lower()
    assert "análisis" in m.lower() or "desempeño" in m.lower()


def test_mensaje_no_despide_al_usuario():
    """EL BUG REPORTADO: se respondía "fuera de contexto" a quien pregunta qué sabe hacer."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod).lower()
        assert "fuera de" not in m
        assert "se sale" not in m
        assert "no logré entender" not in m


def test_mensaje_no_promete_capacidades_inexistentes():
    """no_soportado.py rechaza estas formas: ofrecerlas aquí sería contradecirse al turno
    siguiente."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod).lower()
        for prohibida in ("trimestre", "semana", "rango de días", "año completo"):
            assert prohibida not in m


def test_mensaje_regla_h1_sin_pregunta_si_no():
    """Un "sí" caería en el drill _AFIRM de _continuacion y daría un acumulado."""
    for cod in ("capacidades", "saludo"):
        assert "¿Quieres" not in capacidades.mensaje(cod)


def test_mensaje_determinista_sin_cifras():
    for cod in ("capacidades", "saludo"):
        assert not any(ch.isdigit() for ch in capacidades.mensaje(cod))


def test_mensaje_con_usuario_antepone_vocativo():
    m = capacidades.mensaje("saludo", usuario="Javier")
    assert "Javier" in m
    assert m.count("Hola") == 1          # no duplica el saludo
```

### 6.1 Suite completa a ejecutar

```bash
cd c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0\INGESTA\Rep_Prod\backend
python -m pytest tests/test_capacidades.py tests/test_incompleta.py tests/test_no_soportado.py tests/test_consulta_v2_clasificador.py -q
```

| Verificación | Resultado esperado |
|---|---|
| `tests/test_capacidades.py` | todos pasan |
| `tests/test_incompleta.py` | **sin cambios** (regresión de los hermanos) |
| `tests/test_no_soportado.py` | **sin cambios** — incluye `detectar("hola") is None`, que sigue siendo cierto: ese es `no_soportado`, otro módulo |
| `tests/test_consulta_v2_clasificador.py` | **sin cambios** — «hola» sigue esperando `desconocido` |

> 🔴 **Criterio de fallo:** si `test_consulta_v2_clasificador.py` se pone en rojo, el
> cambio está MAL HECHO — significa que se reclasificó en vez de solo cambiar el mensaje.
> Detener y revisar §4.4.

---

## 7. Por qué determinista y NO por el LLM

Argumento textual de `consulta/meta.py:9-16`:

> «Aquí NO hay nada que redactar: la respuesta ES la lista de hechos… El LLM solo podía
> aportar cosmética, y la pagaba con falsedades.»

Aplicado aquí: la respuesta a «qué sabes hacer» es un **inventario de capacidades**. Si
la redacta qwen2.5:3b va a **prometer lo que no existe** (rangos de días, trimestres,
comparar años) y un turno después `no_soportado.py` se lo va a negar. El motor se
contradiría a sí mismo. Es la misma falsedad estructural que ya se midió con
«CHICHIMENE SW» — y aquí ni siquiera hay una salvaguarda de nombres literales que
pudiera atraparla.

---

## 8. Validación en vivo (post-tests)

> ⚠️ **NO medir con llamadas en proceso a los endpoints FastAPI**: los defaults
> `Query(...)` falsean el resultado. Los backends corren en el equipo del usuario.

1. **Reiniciar los backends** (módulo nuevo).
2. **Turno en frío** (conversación nueva, `_CTX` vacío):
   - «¿cuál es tu finalidad?» → inventario de los 3 frentes, **NO** «fuera de contexto».
   - «hola» → saludo con los 3 frentes.
3. **🔴 Turno con contexto vivo** (la prueba del hallazgo H2):
   - «¿cuánto produjo Castilla en mayo?» → cifra (deja `_CTX` poblado).
   - **luego** «¿cuál es tu finalidad?» → inventario, **NO** la ficha de CASTILLA.
   - **luego** «para qué sirves» → inventario, **NO** la ficha de CASTILLA.
4. **Regresión del drill estructural** (lo que protege H3):
   - «¿qué es CASTILLA?» → sigue respondiendo jerarquizar.
   - En cadena: «CASTILLA» → «¿a qué activo pertenece?» → el drill sigue vivo.
5. **Regresión del saludo compuesto:**
   - «hola, ¿cuánto produjo Castilla en mayo?» → la cifra, no el saludo.
6. **Regresión de (B):** con contexto de entidad, «¿y la semana pasada?» → sigue dando el
   rechazo honesto de `no_soportado` (forma `semana`), no el inventario.

---

## 9. Reglas no negociables para el executor

1. **CERO modificaciones fuera de lo especificado.** Solo los 3 archivos de §5.
2. **NO tocar** `config/patrones_grupo.yaml`, `config/vocabulario_dominio.yaml`,
   `golden/`, `clasificador_llm.py`, `respuesta_out.py`.
3. **NO cambiar** `grupo`, `capa_resolutora` ni `GRUPO_LABEL`: el grupo sigue siendo
   `desconocido`.
4. **NO poblar `panel`** — se queda en `None` (decisión del usuario: solo burbuja).
5. **NO** llamar al LLM desde `capacidades.py`.
6. El gate `ent_ctx` de la rama (B) debe seguir intacto.
7. Todo comentario y docstring **en español**.
8. Si un test de los hermanos se pone en rojo → **DETENERSE** y reportar.

---

## 10. Fuera de alcance (explícito)

- **Panel de bienvenida** con tarjetas clicables — decisión del usuario: solo burbuja.
- **Reclasificar** a un grupo nuevo (`meta`): rompería golden, `GRUPO_LABEL` y Capa 2.
- **Despedidas** («gracias», «chao»): mismo molde, otra forma; no se pidió.
- **Deuda detectada, NO se toca aquí:** la cabecera de `no_soportado.py` (líneas 59-76)
  describe `dia`/`selector_dia` como capacidades ausentes, pero
  `respuesta_cuantificar._FORMAS_RECHAZO_RANKING` ya las excluye de la ruta de entidad
  (N1D/N1DSEL las construyen desde los commits del 2026-08-25). **El comportamiento es
  correcto**; solo el comentario quedó desfasado. Anotarlo como deuda, no corregirlo en
  esta tarea.
