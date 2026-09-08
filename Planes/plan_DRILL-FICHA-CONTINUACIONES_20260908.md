# plan_DRILL-FICHA-CONTINUACIONES — 2026-09-08 · v2 (auditado y corregido)

**ID tarea:** DRILL-FICHA-CONTINUACIONES
**Fecha:** 2026-09-08
**Repo:** `ProdIABack` — `C:\APLICACIONES\ProdIA\Repo ProdIA\backend`
**Alcance:** UN archivo de código (`maquina_q.py`) + UN archivo de tests nuevo.
**Qué NO se toca:** frontend (cero JS/CSS/plantillas), `respuesta_jerarquizar.py`,
`respuesta_cuantificar.py`, `respuesta_analizar.py`, `cuantificar/ranking.py`, YAMLs de
configuración, goldens, BD, ETL.

### Decisiones cerradas del usuario (no se re-discuten)

1. Tras la ficha jerárquica de una entidad, el chat debe aceptar **todo el drill de
   cuantificar**: acumulado, otro mes/ventana temporal, referencia (`vs operativo`) y el
   drill N1 genérico. No solo el acumulado.
2. El fallo que originó el trabajo es: ficha de CASTILLA → «¿y el acumulado?» →
   «No logré entender bien tu pregunta».

---

## §0.0 · Changelog v1 → v2

El v1 se auditó contra el código real ejecutándolo, no leyéndolo. Salieron **tres errores**,
dos de ellos capaces de romper funcionalidad que hoy funciona:

| # | Qué decía el v1 | Qué se midió | Efecto si no se corrige |
|---|---|---|---|
| C-1 | El Cambio 5 restringía `t in _AFIRM` a cuantificar «por si acaso» | 🔴 **«claro»/«dale»/«ok» tras una ficha YA funcionan hoy** (`-> "produccion de CASTILLA"`). El v1 los habría metido en la rama del acumulado, que corre ANTES de `:391` | **Regresión real.** Se rompe una respuesta que hoy es correcta. El propio test del v1 (`test_si_tras_ficha_sigue_dando_produccion`) habría fallado y detenido al executor |
| C-2 | H-04: «ampliar a `ctx.get("entidad")` metería Analizar en los drills de cuantificar» | 🟡 **Falso.** La rama de analizar (`:284`) corta SIEMPRE con `return None` en su `else` (`:317`). Analizar no puede alcanzar `:344`/`:351`/`:376`. Medido: `vs operativo`, `y el acumulado?`, `y en junio?` con ctx de analizar → todos `None` | Ninguno funcional, pero el plan justificaba su diseño con una razón falsa. La razón correcta es otra (ver H-04 v2) y sigue exigiendo la misma condición explícita |
| C-3 | V-3 esperaba «2 líneas» tras el cambio | 🟡 Hoy hay **5** ocurrencias (`:213`, `:235`, `:344`, `:351`, `:376`). Tras el v2 quedan **2**, pero por un motivo distinto al que el v1 suponía | El executor habría validado contra un número correcto por casualidad. Se reescribe el criterio para que mida lo que importa |

Lecciones aplicadas: el v2 **no toca el `t in _AFIRM`** de la rama del acumulado (C-1), y
todos los números de la §6.1 están medidos contra el archivo actual (C-3).

---

## §0 · Contexto para el agente EXECUTOR

**Proyecto ProdIA** (Ecopetrol). Dos repos hermanos: `frontend\` (Flask, :5029) y
`backend\` (FastAPI con `uv`, :5030). Este plan toca **solo el backend**.

El **Motor Q v2** clasifica cada pregunta en cuatro grupos (Cuantificar, Jerarquizar,
Analizar, OUT). Sobre esa clasificación hay una capa de **memoria conversacional**: la
función `_continuacion(texto, ctx)` en `maquina_q.py` reescribe mensajes cortos de
seguimiento («¿y en mayo?») convirtiéndolos en preguntas autocontenidas
(«produccion de CASTILLA y en mayo?») **antes** de clasificarlos. Ese mecanismo se llama
"el drill".

`_continuacion` es una **función pura**: recibe el `ctx` como argumento, no toca BD ni LLM.
Por eso se puede probar directamente, sin servidor y sin datos.

**Archivos que se tocan (rutas absolutas):**

| Acción | Ruta |
|---|---|
| MODIFICAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\maquina_q.py` |
| CREAR | `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_drill_ficha_continuaciones.py` |

**Convenciones obligatorias:**

- Todo el código y **todos los comentarios en español**.
- Python del backend: se ejecuta siempre con `uv run` desde
  `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`.
- Los comentarios de este proyecto explican **por qué**, citando la evidencia medida
  (archivo:línea). Mantener ese estilo: los bloques nuevos llevan la marca
  `[2026-09-08 · DRILL-FICHA]`.
- **Si algo del plan no calza con el código real, DETENERSE y reportar. No improvisar.**

---

## §1 · Hallazgos de la auditoría

### 🔴 H-01 (bloqueante) — Las cinco ramas útiles del drill exigen `grupo == "cuantificar"`

Medido con `grep -n 'grupo") == "cuantificar"'` sobre `maquina_q.py` — **5 ocurrencias, todas
relevantes**:

| Línea | Rama | Condición actual |
|---|---|---|
| `:213` | continuación TEMPORAL / ventana | `ctx.get("grupo") == "cuantificar" and ctx.get("entidad")` |
| `:235` | excepción de longitud del ACUMULADO | `ctx.get("grupo") == "cuantificar" and ctx.get("entidad")` |
| `:344` | drill de REFERENCIA (`vs operativo`) | `ctx.get("grupo") == "cuantificar"` |
| `:351` | drill de ACUMULADO (N1→N2) | `ctx.get("grupo") == "cuantificar"` |
| `:376` | drill N1 GENÉRICO | `ctx.get("grupo") == "cuantificar"` |

El `ctx` que deja una ficha jerárquica **no tiene la clave `grupo`** (ver H-02), así que las
cinco se saltan. La única rama que queda viva para ese ctx es `:391`:

```python
if ctx.get("ofrece_produccion") and (prod or t in _AFIRM):
    return f"produccion de {ctx['entidad']}"
```

que exige verbo de producción o una afirmación de `_AFIRM`. «¿y el acumulado?» no es ninguna
de las dos → cae a `return None` → Desconocido.

**Medido en local (función pura, sin BD), con el ctx de ficha de CASTILLA:**

```
'y el acumulado?'                       -> None
'el acumulado'                          -> None
'y el acumulado del ano?'               -> None
'si dame el acumulado del ano por favor'-> None
'vs operativo'                          -> None
'y en junio?'                           -> None
'claro'                                 -> 'produccion de CASTILLA'   <- YA funciona
'sus campos?'                           -> 'que es CASTILLA'          <- YA funciona
```

El fallo es **más amplio que el acumulado**: tras una ficha, ninguna continuación funciona
salvo las dos últimas. Esto justifica la decisión cerrada 1.

### 🔴 H-02 (bloqueante) — El ctx de la ficha no trae `producto` ni `periodo_ctx`

`respuesta_jerarquizar.py:720-730` construye exactamente:

```python
{"entidad": ..., "nivel": ..., "hijos": [...], "ofrece_produccion": True}
```

Consecuencia para el diseño de la §3: las ramas que se van a habilitar leen
`ctx.get("producto", "crudo")` y `ctx.get("periodo_ctx")`. Con el ctx de ficha eso da
**"crudo"** y **None**, que es el comportamiento correcto —una ficha no viene de una
conversación de gas ni de un mes concreto— y además es exactamente lo que ya hacen hoy con
un ctx de cuantificar incompleto. **No hay que añadir claves nuevas al ctx**, ni tocar
`respuesta_jerarquizar.py`.

### 🔴 H-03 (bloqueante) — 🆕 v2 · El `t in _AFIRM` de la rama del acumulado NO se debe tocar

Este es el hallazgo que corrige el error C-1 del v1, y es el único punto del plan con riesgo
real de regresión.

**Orden real de las ramas** (verificado leyendo el archivo): la rama del acumulado (`:351`)
corre **antes** que la rama de la ficha (`:391`). Su condición es:

```python
if ctx.get("grupo") == "cuantificar" and \
   (any(k in t for k in _ACUM_KW) or t in _AFIRM):
```

`_AFIRM = {"SI","DALE","OK","OKEY","CLARO","BUENO","LISTO","SIP","VALE","ESO","ESA"}`.

**Medido hoy, con ctx de ficha:** `«claro» -> "produccion de CASTILLA"`. Funciona porque el
`grupo == "cuantificar"` de `:351` lo excluye y la frase llega intacta a `:391`.

Si `:351` pasara a aceptar el ctx de ficha **con su `t in _AFIRM` incluido**, «claro»
devolvería `"acumulado de CASTILLA"`: el usuario que dice «sí» a la oferta literal de la
ficha —«¿Quieres ver la producción de CASTILLA?»— recibiría el acumulado del año. **Es una
regresión sobre algo que hoy funciona bien.**

**Decisión de diseño que esto impone:** el Cambio 5 amplía la condición del acumulado
**solo para `_ACUM_KW`**, dejando el `t in _AFIRM` atado a `grupo == "cuantificar"`. No es
una precaución: es el reparto correcto de significados.

> Un «sí» significa cosas distintas según quién preguntó:
> · tras un N1 de cuantificar, el cierre ofreció «¿Quieres el acumulado del año?» → acumulado.
> · tras una ficha, el cierre ofreció «¿Quieres ver la producción de X?» → producción.

### 🟡 H-04 (relevante) — 🆕 v2 · Por qué la condición nombra los dos ctx explícitamente

El v1 justificaba esto diciendo que un `ctx.get("entidad")` a secas metería las
conversaciones de **Analizar** en los drills de cuantificar. **Eso es falso** y se midió:

```
ctx de analizar + 'vs operativo'    -> None
ctx de analizar + 'y el acumulado?' -> None
ctx de analizar + 'y en junio?'     -> None
```

La rama de analizar (`:284`) **corta siempre** — su `else` final es `return None` (`:317`).
Analizar no puede alcanzar `:344`/`:351`/`:376`. La razón del v1 no se sostiene.

**La razón correcta, que sí se sostiene, es otra:** `ctx.get("entidad")` a secas sería un
criterio *implícito* que depende de que las ramas de arriba sigan cortando siempre. Hoy
cortan; si mañana alguien añade un `destino` nuevo a la rama de analizar sin `return`, o un
grupo nuevo con entidad, las ramas de cuantificar empezarían a capturar sus continuaciones
en silencio. Nombrar los dos ctx admitidos (`cuantificar` y `ofrece_produccion`) hace el
contrato **explícito y estable frente a cambios en otras ramas**.

Es el mismo criterio que el proyecto ya aplicó en `:181-184` («se consulta al detector REAL,
no a una lista paralela»): preferir el criterio que no se desincroniza.

### 🟡 H-05 (relevante) — El propio código ya anticipó esta unificación

`maquina_q.py:348-350`, comentario preexistente en la rama del acumulado:

> «Va ANTES del check de ofrece_produccion (abajo) — el ctx de cuantificar NUNCA lleva esa
> clave (solo la puebla jerarquizar), pero **el orden importa si en el futuro se unifican**:
> un "sí"/"acumulado" tras N1 debe ir a N2, no repetir N1.»

El orden de las ramas **ya está preparado** para que ambos ctx convivan. Esto determina el
diseño de la §3: **no se reordena nada**, solo se amplía la condición de entrada de cada
rama. Nótese que ese comentario habla justo del caso de H-03 y confirma su lectura.

### 🟢 H-06 (confirmación) — Las guardas de `37ac31f` siguen protegiendo

Las guardas del commit `37ac31f` (`:170` sujeto propio, `:191` ranking) corren **antes** de
todas las ramas que este plan modifica. Ampliar las condiciones de abajo **no las debilita**:
«¿cuánto produjimos en abril?» tras una ficha seguirá cortando en `:170`. Verificado por
lectura del orden del archivo, y fijado por test en la §3.2
(`test_guardas_siguen_activas_con_ficha`).

### 🟢 H-07 (confirmación) — El ctx de RANKING no lleva `entidad`

`ctx` de ranking: `{grupo:"cuantificar", subgrupo:"ranking", producto, direccion, ...}` — sin
`entidad`. Su rama (`:259`) corta siempre con return propio, y además el helper del Cambio 1
exige `bool(ctx.get("entidad"))`, así que nunca podría entrar en las ramas N1/N2 (que harían
`KeyError` sobre `ctx['entidad']`). Doble protección, ambas verificadas. Fijado por test.

### 🟢 H-08 (confirmación) — Los tests de regresión existentes cubren las ramas afectadas

`grep` sobre `backend\tests\`:

- `test_drill_autocontenida.py` (commit `37ac31f`): 10 casos, cubre las continuaciones
  legítimas de los 4 drills y las frases que deben romper el hilo.
- `test_cuantificar_dia.py:705` — continuación temporal hereda.
- `test_cuantificar_dia.py:735` — «produjo el campo en mayo» hereda (no es ranking).

Los tres deben seguir pasando sin cambios. Son el gate de esta tarea.

---

## §2 · Estado actual

En `maquina_q.py`, la función `_continuacion(texto, ctx)` (`:136-399`) evalúa sus ramas en
este orden. Las marcadas ← son las que este plan toca:

```
:155  guarda capacidades              -> return None
:170  guarda sujeto propio            -> return None      [37ac31f]
:191  guarda ranking autocontenido    -> return None      [37ac31f]
:193  ent = entidad_en(texto)
:213  continuación temporal/ventana                       ← Cambio 2
:234  excepción de longitud acumulado                     ← Cambio 3
:239  corte de 5 tokens               -> return None
:242  la frase nombra entidad propia
:259  drill de ranking                -> return propio SIEMPRE
:284  drill de analizar               -> return propio SIEMPRE (else: None, :317)
:344  drill de referencia                                 ← Cambio 4
:351  drill de acumulado (N1->N2)                         ← Cambio 5 (parcial, ver H-03)
:376  drill N1 genérico                                   ← Cambio 6
:391  ficha: ofrece_produccion + (prod o _AFIRM)          ← NO se toca (H-03)
:397  rama estructural                -> "que es {entidad}"
:399  return None
```

Los dos `ctx` relevantes:

```python
# lo que deja «¿cuánto produjo Castilla en abril?» (cuantificar con entidad)
{"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo", "periodo_ctx": "abril"}

# lo que deja «¿a qué activo pertenece?» (ficha jerárquica) — SIN clave "grupo"
{"entidad": "CASTILLA", "nivel": "campo", "hijos": ["CASTILLA NORTE"], "ofrece_produccion": True}
```

---

## §3 · Especificación

### 3.1 · MODIFICAR `maquina_q.py`

#### Cambio 1 de 6 — Añadir el helper

**LOCALIZAR** (línea que abre el bloque de guardas, tal cual está en el archivo):

```python
    if capacidades.detectar(texto, False) is not None:
        return None
```

**INSERTAR INMEDIATAMENTE ANTES** de esa línea:

```python
    # [2026-09-08 · DRILL-FICHA] ¿Este ctx puede alimentar los drills de CUANTIFICAR?
    # Sí en dos casos, y son los dos que aportan una ENTIDAD sobre la que seguir preguntando:
    #   · el ctx de cuantificar con entidad — el caso de siempre.
    #   · el ctx de una FICHA jerárquica (`ofrece_produccion`), que además ofrece por escrito
    #     «¿Quieres ver la producción de X?»: el usuario que responde «¿y el acumulado?» está
    #     aceptando esa oferta, solo que con más precisión de la que la rama :391 sabe leer.
    # Medido en la app (2026-09-08): ficha de CASTILLA -> «¿y el acumulado?» -> «No logré
    # entender bien tu pregunta». Y no era solo el acumulado: con ese ctx morían TODAS las
    # continuaciones («y en junio?», «vs operativo» también), porque las 5 ramas que saben
    # heredar exigían `grupo == "cuantificar"` y la ficha no lleva esa clave.
    # 🔑 Se nombran los DOS ctx admitidos en vez de usar `ctx.get("entidad")` a secas. Medido:
    #    hoy el ctx de ANALIZAR tampoco llegaría a esas ramas (la suya, :284, corta siempre con
    #    return propio), así que el criterio corto FUNCIONARÍA hoy — pero por un efecto colateral
    #    del orden, no por contrato. Si mañana la rama de analizar deja de cortar, sus
    #    continuaciones caerían en los drills de cuantificar EN SILENCIO. Nombrar los dos casos
    #    hace explícito qué se admite. Misma lección que :181-184: el criterio que no se
    #    desincroniza es el que se elige.
    # 🔑 `bool(ctx.get("entidad"))` no es redundante: el ctx de RANKING lleva grupo
    #    "cuantificar" pero NO lleva entidad, y las ramas N1/N2 harían KeyError sobre
    #    ctx['entidad'] (su rama :259 ya corta antes, pero el helper no depende de ese orden).
    _drill_cuant = bool(ctx.get("entidad")) and (
        ctx.get("grupo") == "cuantificar" or ctx.get("ofrece_produccion"))
```

#### Cambio 2 de 6 — Rama de continuación temporal / ventana

**LOCALIZAR:**

```python
    if (ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and (any(k in t for k in _TEMP_CONT_KW) or _es_ventana)
            and not any(k in t for k in _ESTRUCT_KW)):
```

**SUSTITUIR POR:**

```python
    if (_drill_cuant and not ent                          # [2026-09-08 · DRILL-FICHA]
            and (any(k in t for k in _TEMP_CONT_KW) or _es_ventana)
            and not any(k in t for k in _ESTRUCT_KW)):
```

#### Cambio 3 de 6 — Excepción de longitud del acumulado

**LOCALIZAR:**

```python
    if (len(toks) > 5 and len(toks) <= 8
            and ctx.get("grupo") == "cuantificar" and ctx.get("entidad") and not ent
            and any(k in t for k in _ACUM_KW)
            and not any(k in t for k in _REF_CONTINUA_KW)):
```

**SUSTITUIR POR:**

```python
    if (len(toks) > 5 and len(toks) <= 8
            and _drill_cuant and not ent                   # [2026-09-08 · DRILL-FICHA]
            and any(k in t for k in _ACUM_KW)
            and not any(k in t for k in _REF_CONTINUA_KW)):
```

#### Cambio 4 de 6 — Drill de REFERENCIA

**LOCALIZAR:**

```python
    if ctx.get("grupo") == "cuantificar" and any(k in t for k in _REF_CONTINUA_KW):
```

**SUSTITUIR POR:**

```python
    if _drill_cuant and any(k in t for k in _REF_CONTINUA_KW):   # [2026-09-08 · DRILL-FICHA]
```

#### Cambio 5 de 6 — Drill de ACUMULADO (N1→N2) · 🔴 EL DELICADO, LEER H-03

**LOCALIZAR:**

```python
    if ctx.get("grupo") == "cuantificar" and \
       (any(k in t for k in _ACUM_KW) or t in _AFIRM):
```

**SUSTITUIR POR:**

```python
    # [2026-09-08 · DRILL-FICHA] La condición se parte en dos MITADES DELIBERADAMENTE
    # ASIMÉTRICAS, y la asimetría es el corazón de este cambio:
    #   · _ACUM_KW ("acumulado", "del año", "YTD"...) -> vale para AMBOS ctx. Pedir el
    #     acumulado es inequívoco: lo pida tras un N1 o tras una ficha, quiere el acumulado.
    #   · t in _AFIRM ("sí", "claro", "dale") -> SOLO para el ctx de cuantificar.
    # 🔑 Por qué el «sí» NO se amplía. Un «sí» a secas acepta LA OFERTA QUE SE LE HIZO, y cada
    #    cierre ofrece algo distinto: el de cuantificar dice «¿Quieres el acumulado del año?»,
    #    el de la ficha dice «¿Quieres ver la producción de CASTILLA?». Medido HOY con ctx de
    #    ficha: «claro» -> «produccion de CASTILLA» (correcto, lo resuelve la rama :391, que
    #    corre DESPUÉS de esta). Si el «sí» entrara aquí, esta rama lo capturaría antes y el
    #    usuario recibiría el ACUMULADO donde pidió la PRODUCCIÓN: una regresión sobre algo
    #    que hoy funciona bien. Los tests `test_si_tras_ficha_sigue_dando_produccion` y
    #    `test_si_tras_cuantificar_sigue_dando_acumulado` fijan las dos mitades.
    if _drill_cuant and (any(k in t for k in _ACUM_KW)
                         or (t in _AFIRM and ctx.get("grupo") == "cuantificar")):
```

#### Cambio 6 de 6 — Drill N1 GENÉRICO

**LOCALIZAR:**

```python
    if ctx.get("grupo") == "cuantificar" and prod and not ambiguo_estructural:
```

**SUSTITUIR POR:**

```python
    if _drill_cuant and prod and not ambiguo_estructural:   # [2026-09-08 · DRILL-FICHA]
```

### 3.2 · CREAR `backend\tests\test_drill_ficha_continuaciones.py`

Archivo completo, tal cual:

```python
"""Tras una FICHA jerárquica, las continuaciones de cuantificar funcionan (2026-09-08 · DRILL-FICHA).

Bug real visto en la app: ficha de CASTILLA («¿a qué activo pertenece?») y luego «¿y el
acumulado?» -> «No logré entender bien tu pregunta». Las 5 ramas de `_continuacion` que saben
heredar la entidad exigían `ctx["grupo"] == "cuantificar"`, y el ctx de una ficha no lleva esa
clave: con ese ctx morían TODAS las continuaciones, no solo el acumulado.

El punto delicado (H-03 del plan) es el «sí»: acepta la oferta que se le hizo, y cada cierre
ofrece algo distinto. Tras cuantificar, el acumulado; tras una ficha, la producción. Los dos
tests espejo de la sección "lo que NO debe cambiar" fijan esa asimetría.

`_continuacion` es PURA (sin BD ni LLM): recibe el ctx como argumento.
"""
from app.features.consulta_v2.maquina_q import _continuacion

# ctx que deja una ficha jerárquica (respuesta_jerarquizar.py:720-730). SIN clave "grupo",
# SIN "producto" y SIN "periodo_ctx": por eso las ramas heredan "crudo" y ningún mes.
_FICHA = {"entidad": "CASTILLA", "nivel": "campo", "hijos": ["CASTILLA NORTE"],
          "ofrece_produccion": True}
# ctx de cuantificar, para comprobar que lo que ya funcionaba no cambia.
_CUANT = {"grupo": "cuantificar", "entidad": "CASTILLA", "producto": "crudo",
          "periodo_ctx": None}
# ctx de analizar: sus continuaciones son suyas (rama :284, que corta siempre).
_ANALIZ = {"grupo": "analizar", "entidad": "CASTILLA", "sub": "proyeccion", "producto": None}


# --- El bug que se arregla -------------------------------------------------------------

def test_acumulado_tras_ficha():
    """El caso exacto que falló en la app."""
    for frase in ("y el acumulado?", "el acumulado", "y el acumulado del ano?"):
        assert _continuacion(frase, _FICHA) == "acumulado de CASTILLA", \
            f"{frase!r} no heredó la entidad de la ficha"


def test_otro_mes_tras_ficha():
    """No era solo el acumulado: la continuación temporal también moría."""
    for frase in ("y en junio?", "y en mayo?", "y mayo?"):
        rw = _continuacion(frase, _FICHA)
        assert rw is not None and "CASTILLA" in rw, f"{frase!r} perdió el hilo: {rw!r}"


def test_referencia_tras_ficha():
    rw = _continuacion("vs operativo", _FICHA)
    assert rw is not None and "CASTILLA" in rw


def test_acumulado_largo_tras_ficha():
    """Excepción de longitud (>5 y <=8 tokens) con el ctx de ficha."""
    assert _continuacion("si dame el acumulado del ano por favor", _FICHA) == \
        "acumulado de CASTILLA"


# --- Lo que NO debe cambiar (H-03: la asimetría del «sí») -------------------------------

def test_si_tras_ficha_sigue_dando_produccion():
    """🔴 REGRESIÓN. Medido ANTES del cambio: «claro» con ctx de ficha ya devolvía
    «produccion de CASTILLA». La ficha ofreció la PRODUCCIÓN, no el acumulado. Si el
    `t in _AFIRM` de la rama del acumulado se hubiera ampliado, este test fallaría."""
    for frase in ("si", "claro", "dale", "ok"):
        assert _continuacion(frase, _FICHA) == "produccion de CASTILLA", \
            f"{frase!r} tras una ficha debe dar la producción, no el acumulado"


def test_si_tras_cuantificar_sigue_dando_acumulado():
    """El espejo: tras un N1 de cuantificar, la oferta abierta ES el acumulado del año."""
    for frase in ("si", "claro", "dale"):
        assert _continuacion(frase, _CUANT) == "acumulado de CASTILLA"


def test_estructural_tras_ficha_sigue_igual():
    """«¿y sus campos?» sigue siendo estructural, no una consulta de producción."""
    assert _continuacion("sus campos?", _FICHA) == "que es CASTILLA"


def test_analizar_conserva_sus_continuaciones():
    """Su rama (:284) corta siempre con return propio y va ANTES que las ampliadas."""
    esperado = "por que la produccion de CASTILLA esta corta"
    assert _continuacion("si", _ANALIZ) == esperado
    assert _continuacion("que campos explican el faltante", _ANALIZ) == esperado


def test_guardas_siguen_activas_con_ficha():
    """H-06: las guardas de 37ac31f corren ANTES y no se debilitan al ampliar las ramas."""
    assert _continuacion("Cuanto produjimos en abril?", _FICHA) is None    # sujeto propio
    assert _continuacion("Cuales campos produjeron mas hoy?", _FICHA) is None  # ranking


def test_ranking_no_rompe_por_falta_de_entidad():
    """H-07: el ctx de ranking NO lleva "entidad". `_drill_cuant` debe darlo por False y dejar
    que su propia rama lo atienda, sin KeyError."""
    ctx_rank = {"grupo": "cuantificar", "subgrupo": "ranking", "producto": "crudo",
                "direccion": "top", "nivel_ranking": "campo", "metrica": "real"}
    assert _continuacion("y gas?", ctx_rank) == "cuales campos son los mayores productores de gas"
    assert _continuacion("los que menos", ctx_rank) == \
        "cuales campos son los menores productores de crudo"
```

---

## §4 · Orden de ejecución

Secuencial. Si un paso falla, **DETENERSE** y reportar.

| # | Paso | Comando / acción |
|---|---|---|
| 1 | Situarse en el backend | `cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'` |
| 2 | Confirmar árbol limpio | `git status --short` — solo debe aparecer, sin seguir, el untracked `Planes/plan_SENDA-PROYECTADA-DIC_20260908.md` |
| 3 | **Anotar la línea base de V-6** | `uv run pytest tests\test_cuantificar_dia.py -q` y **anotar** la cifra de passed/failed ANTES de tocar nada |
| 4 | Aplicar Cambio 1 (helper) | §3.1 |
| 5 | Aplicar Cambio 2 (temporal) | §3.1 |
| 6 | Aplicar Cambio 3 (longitud acumulado) | §3.1 |
| 7 | Aplicar Cambio 4 (referencia) | §3.1 |
| 8 | Aplicar Cambio 5 (acumulado N1→N2) | §3.1 — **releer H-03 antes** |
| 9 | Aplicar Cambio 6 (N1 genérico) | §3.1 |
| 10 | Crear el archivo de tests | §3.2, completo |
| 11 | Validación estática | §6.1, en orden V-1 → V-6 |

El helper (paso 4) va **antes** que sus cinco call sites (pasos 5-9): así el archivo nunca
queda en un estado que invoque algo inexistente. El paso 3 va antes de todo cambio porque
una línea base tomada *después* no sirve para nada.

---

## §5 · Reglas no negociables

1. **CERO modificaciones** fuera de los dos archivos de la §0. Nada de frontend.
2. **No reordenar** ramas de `_continuacion`. Solo se cambian las condiciones indicadas.
3. **No tocar la rama `:391`** (`ofrece_produccion` + `_AFIRM`). Queda tal cual (H-03).
4. **No añadir claves** al ctx de jerarquizar. `respuesta_jerarquizar.py` no se toca (H-02).
5. Código y comentarios **en español**, con la marca `[2026-09-08 · DRILL-FICHA]`.
6. Copiar los bloques de la §3 **literalmente**, incluidos los comentarios: son la
   documentación del porqué y valen tanto como el código.
7. **Si algo no calza con el código real, DETENERSE y reportar.** No improvisar una variante.
8. No hacer commit. Al terminar, reportar archivos tocados y preguntar «¿Hago commit?».

---

## §6 · Validación

### 6.1 · Estática (la ejecuta el EXECUTOR)

Todo desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, línea por línea, PowerShell
normal (no requiere administrador).

| # | Comando | Resultado esperado |
|---|---|---|
| V-1 | `uv run python -c "import app.features.consulta_v2.maquina_q"` | Sin salida (importa limpio) |
| V-2 | `Select-String -Path app\features\consulta_v2\maquina_q.py -Pattern '_drill_cuant' -CaseSensitive` | **6 líneas**: 1 definición + 5 usos |
| V-3 | `Select-String -Path app\features\consulta_v2\maquina_q.py -Pattern 'grupo..\) == .cuantificar.' -CaseSensitive` | **2 líneas**. Antes del cambio hay **5** (`:213`,`:235`,`:344`,`:351`,`:376`); quedan solo la del `t in _AFIRM` del Cambio 5 y la de la rama de analizar de `:284`. Si salen 5, no se aplicó nada; si sale 1, se borró de más el Cambio 5 (H-03) |
| V-4 | `uv run pytest tests\test_drill_ficha_continuaciones.py -q` | **10 passed** |
| V-5 | `uv run pytest tests\test_drill_autocontenida.py -q` | **10 passed** (regresión del commit `37ac31f`) |
| V-6 | `uv run pytest tests\test_cuantificar_dia.py -q` | **La misma cifra anotada en el paso 4.3** |

⚠️ **Sobre V-6:** este repo tiene fallos **preexistentes** en tests que dependen de datos de
BD que la BD local (congelada en 2026-05-18) no tiene. Un fallo ahí **no es necesariamente
una regresión**. La forma de distinguirlo, si aparece alguno: `git stash`, volver a correr,
comparar, `git stash pop`. Si el fallo se reproduce con el código sin modificar, es
preexistente y no bloquea. ⚠️ El `git stash` debe correrse desde
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend` (la carpeta `Repo ProdIA` **no** es un repo git).

⚠️ **Si V-4 falla en `test_si_tras_ficha_sigue_dando_produccion`:** el Cambio 5 se aplicó mal
(se amplió el `t in _AFIRM`). Releer H-03 y el bloque del Cambio 5. **DETENERSE y reportar.**

### 6.2 · Humana (la ejecuta el USUARIO, en el servidor de pruebas)

⚠️ **R3: el executor NO puede marcar esto como verificado.** No tiene navegador ni datos
reales. El estado correcto al terminar la §6.1 es **«implementado, PENDIENTE de validación
humana»**.

Procedimiento, en `C:\APLICACIONES\ProdIA\Repo ProdIA\backend`:

```powershell
git pull origin main
```

Luego **reiniciar el backend** (`.\backend\iniciar_backend.bat`). No hace falta Ctrl+F5: no
se tocó JS ni CSS.

En **una sola conversación** del chat, en este orden:

| # | Pregunta | Resultado esperado |
|---|---|---|
| H-1 | ¿Cuánto produjo Castilla en abril? | 55,0 kbopd · Abril 2026 (ancla la memoria) |
| H-2 | ¿a qué activo pertenece? | Ficha de CASTILLA (Activo, Gerencia, VP, pozos) |
| H-3 | **¿y el acumulado?** | **Acumulado del año de CASTILLA** ← el bug que se arregla |
| H-4 | ¿a qué activo pertenece? | Ficha de CASTILLA otra vez (re-ancla en ficha) |
| H-5 | **¿y en junio?** | **Producción de CASTILLA en junio** ← segundo hueco |
| H-6 | ¿a qué activo pertenece? | Ficha de CASTILLA |
| H-7 | **sí** | **Producción de CASTILLA** (NO el acumulado) ← H-03, lo delicado |
| H-8 | ¿Cuánto produjo Castilla en abril? | Re-ancla en cuantificar |
| H-9 | **sí** | **Acumulado del año de CASTILLA** ← el espejo de H-7 |
| H-10 | ¿y sus campos? | Ficha / hijos de CASTILLA (sigue siendo estructural) |
| H-11 | ¿Cuánto produjimos en abril? | Global de Ecopetrol, Abril (guardas de `37ac31f`) |
| H-12 | F12 → Console | 0 errores |

H-3 y H-5 son el bug que se arregla. **H-7 y H-9 son la pareja crítica**: el mismo «sí» debe
dar cosas distintas según lo que se ofreció justo antes. Si H-7 devuelve el acumulado, el
Cambio 5 se aplicó mal.

---

## §7 · Fuera de alcance

- **El contenido de los paneles.** El usuario observó que los paneles de las respuestas de
  cuantificar muestran «información muy pobre». Es un tema **aparte**, anotado para después;
  este plan **no toca ningún panel** ni `respuesta_cuantificar.py`.
- **La brecha de jerarquías superiores a campo** (`jerarquias_sup_error.md`). Sigue abierta y
  es prioritaria, pero es independiente: este plan no toca el resolutor ni los catálogos.
- **El vocabulario de distribución** (`vocabulario_distribucion_error.md`).
- **La hoja `POP Filiales`** de `core.fact_tabla_hoja` (investigación parada).
- **El plan `SENDA-PROYECTADA-DIC`**, untracked en `Planes/`: no se añade, no se commitea,
  no se borra.
- Cualquier cambio en frontend, goldens, YAMLs de configuración, BD o ETL.
