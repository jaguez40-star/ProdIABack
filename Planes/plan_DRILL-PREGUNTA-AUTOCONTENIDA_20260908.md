# Plan — El drill deja de secuestrar preguntas autocontenidas

| | |
|---|---|
| **ID tarea** | `DRILL-PREGUNTA-AUTOCONTENIDA` |
| **Fecha** | 2026-09-08 |
| **Versión** | **v2** — verificada contra el código con el flujo profesional (`CLAUDE.md` §10). La v1 tenía **una regresión real** (rompía el drill de Analizar) y tres imprecisiones; están en §0.0 y corregidas aquí. |
| **Repo** | `ProdIABack` (backend). **El frontend NO se toca.** |
| **Alcance** | Que una pregunta **nueva y autocontenida** deje de heredar la entidad del turno anterior. Medido en la app: tras «¿cuánto produjo Rubiales hoy?», las dos preguntas siguientes respondieron sobre Rubiales aunque no lo nombraban. |
| **NO se toca** | El clasificador (`patrones_grupo.yaml`), `dominio.py`, `vocabulario_dominio.yaml`, `slots.py`, `ranking.py`, `respuesta_cuantificar.py`. Las 5 ramas de drill que hoy funcionan. Ningún golden. El frontend. |

### Decisiones cerradas (el executor NO las revisa, las implementa)

1. **Una pregunta con el verbo de producción en 1ª persona del plural («producimos», «produjimos») es autocontenida.** Trae su propio sujeto —nosotros, Ecopetrol— y no continúa nada.
2. **Una pregunta que el detector de RANKING reconoce es un ranking, salvo dentro de una conversación de Analizar** (ver V-02: ahí el cierre del propio sistema ofrece una frase que el detector confunde con ranking).
3. **Cambio ADITIVO y quirúrgico.** 107 asserts fijan el drill actual (medido). Se añaden dos guardas arriba; no se reescribe ninguna rama existente.
4. **Sin tocar el frontend ni el clasificador.** El bug vive entero en `maquina_q._continuacion`.

---

## §0.0 Qué cambió de la v1 a la v2

| # | Incoherencia de la v1 | Consecuencia si se hubiera ejecutado | Corrección en v2 |
|---|---|---|---|
| 1 | 🔴 La guarda 2 cortaba **toda** frase que `ranking.detectar` reconociera, sin mirar el contexto | **Rompía el drill de Analizar.** Su cierre ofrece literalmente *«¿Quieres ver qué campos explican el faltante?»*; el usuario responde con esa frase, `ranking.detectar` la reconoce (medido: `True`), la guarda la cortaba, y la frase viajaba desnuda perdiendo la entidad. Hoy se reescribe a `por que la produccion de CASTILLA esta corta` — correcto. | La guarda 2 **no aplica** con `ctx["grupo"] == "analizar"`. Test de regresión nuevo que lo fija. |
| 2 | 🟡 H-01 atribuía la pregunta 4 al «Drill N1 genérico» con `ctx` de cuantificar | Impreciso. En la sesión real, la pregunta 3 se reescribió a `que es RUBIALES` → respondió **jerarquizar** → el `ctx` pasó a ser el de jerarquizar (`{entidad, nivel, hijos, ofrece_produccion}`, **sin clave `grupo`**). La pregunta 4 cayó en la rama `ofrece_produccion` (`:332`), que **sustituye** el texto por `produccion de RUBIALES` — por eso se perdió «abril» entero y respondió septiembre. | Diagnóstico corregido (H-01). Las guardas van arriba del todo y cubren **ambos** caminos. Test nuevo con el `ctx` de jerarquizar. |
| 3 | 🟡 V-5 contaba 3 resultados con `Select-String`, que es **case-insensitive** | Los comentarios también dicen «produjimos» → habría dado 5 y el executor se habría detenido sin motivo. | Patrón con comillas: `'"PRODUJIMOS"'` → solo las dos tuplas. |
| 4 | 🟡 §6.2 encadenaba «¿y en mayo?» justo después de un ranking | Tras un ranking el `ctx` es el de ranking (sin entidad): «¿y en mayo?» no habría heredado nada y el usuario habría creído que el arreglo rompió la memoria. | Se inserta un paso que re-ancla una entidad antes de probar las continuaciones. |

Además: se confirmó que `ranking.detectar` es **puro** (líneas 119-201, sin BD) y que **ninguna de las 45 frases** que los 107 asserts pasan a `_continuacion` sería cortada por las guardas.

---

## §0. Contexto para el agente EXECUTOR

> El executor no tiene la conversación previa, ni el historial de git, ni memoria. Todo lo necesario está aquí.

### 0.1 Qué es ProdIA

Aplicación de producción de hidrocarburos de Ecopetrol. Dos procesos separados:

| | Frontend | Backend |
|---|---|---|
| Repo | `ProdIAWebFront` | `ProdIABack` |
| Raíz | `c:\APLICACIONES\ProdIA\Repo ProdIA\frontend\` | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\` |
| Puerto | **5029** (Flask) | **5030** (FastAPI con `uv`) |

**Este plan toca SOLO el backend: un archivo de código y un archivo de tests nuevo.**

### 0.2 Qué es el «drill» y por qué existe

`maquina_q.clasificar()` (`:640`) envuelve al clasificador con **memoria conversacional**. Si el turno anterior dejó contexto (`_CTX`), llama a `_continuacion(texto, ctx)` (`:113`), que **reescribe** una respuesta corta en una pregunta autocontenida antes de clasificarla:

```
Usuario: «¿cuánto produjo Castilla en abril?»   → _CTX = {grupo: cuantificar, entidad: CASTILLA, …}
Usuario: «¿y en mayo?»                          → reescrito a «produccion de CASTILLA y en mayo?»
```

**La función es necesaria y hace bien su trabajo en 5 ramas.** Este plan NO la desmonta: le añade dos guardas arriba.

Hay **tres formas de `ctx`** y las guardas deben convivir con las tres:

| Quién lo deja | Forma | Clave `grupo` |
|---|---|---|
| Cuantificar (con entidad) | `{grupo, entidad, producto, periodo_ctx}` | `cuantificar` |
| Cuantificar (ranking) | `{grupo, subgrupo: ranking, producto, direccion, …}` — **sin `entidad`** | `cuantificar` |
| Jerarquizar | `{entidad, nivel, hijos, ofrece_produccion: True}` — **sin `grupo`** | ausente |
| Analizar | `{grupo, entidad (puede ser None), sub, producto, vp}` | `analizar` |

Las respuestas **globales** de cuantificar (sin entidad) **no dejan `ctx`** (`:681`: solo si `entidad_cruda`).

La reescritura solo ocurre en **tráfico real** (`log=True` + `conversation_id`). Golden y tests pasan `log=False` — por eso este bug **no aparece en ningún golden** y solo se ve en la app.

### 0.3 Archivos que se tocan (rutas ABSOLUTAS)

| # | Archivo | Qué |
|---|---|---|
| A1 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\maquina_q.py` | `import re`, import de `ranking`, 1 constante, +conjugaciones en 2 tuplas, +2 guardas |
| A2 | `c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_drill_autocontenida.py` | **NUEVO**, 10 tests |

**Dos archivos, un repo, un commit.**

### 0.4 Convenciones OBLIGATORIAS

- Python 3.12. Todo en **español**: código, comentarios, mensajes y tu reporte.
- Comentarios que explican **por qué**, con la marca `[2026-09-08 · DRILL-AUTOCONTENIDA]`.
- **No se toca el frontend.**

### 0.5 Cómo correr las cosas (PowerShell, línea por línea, desde `backend\backend`)

```powershell
cd 'c:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
$env:PYTHONPATH='.'; uv run python -m pytest tests/test_drill_autocontenida.py -q
```

⚠️ **No corras `run_golden.py` ni `run_golden_cuantificar.py` en local**: abren Postgres y pueden llamar al LLM. Además **no miden el drill** (verificado: `run_golden.py` no menciona `ctx` ni `conversation_id`).

---

## §1. Hallazgos de la auditoría (v1, corregidos donde la verificación lo exigió)

### 🔴 H-01 — El bug, medido en la app y reproducido en local por su camino REAL

El usuario preguntó cuatro cosas seguidas en una conversación:

| # | Pregunta | Qué respondió | `ctx` que dejó | ¿Correcto? |
|---|---|---|---|---|
| 1 | «¿Cuánto producimos hoy?» | Panorama del mes | ninguno (global) | ✅ |
| 2 | «¿Cuánto produjo Rubiales hoy?» | Rechazo honesto por techo | cuantificar, RUBIALES | ✅ |
| 3 | «¿Cuáles campos produjeron más hoy?» | **Ficha jerárquica de RUBIALES** | **jerarquizar**, RUBIALES | ❌ |
| 4 | «¿Cuánto produjimos en abril?» | **Rubiales, en septiembre** | — | ❌ |

Reproducido en local, con cada `ctx` en su sitio:

```python
# Pregunta 3, con el ctx que dejó la 2:
_continuacion("Cuales campos produjeron mas hoy?", {"grupo":"cuantificar","entidad":"RUBIALES",...})
# -> 'que es RUBIALES'            ← rama ESTRUCTURAL (:338), por CAMPOS y CUAL

# Pregunta 4, con el ctx que dejó la 3 (jerarquizar, SIN 'grupo'):
_continuacion("Cuanto produjimos en abril?", {"entidad":"RUBIALES","nivel":"campo","hijos":[],"ofrece_produccion":True})
# -> 'produccion de RUBIALES'     ← rama ofrece_produccion (:332): SUSTITUYE el texto, "abril" desaparece
```

Eso explica **las dos** anomalías de la pregunta 4: Rubiales en vez del global, y septiembre en vez de abril — el texto se reemplazó entero y el mes no llegó nunca a `slots`.

⚠️ **El bug NO lo introdujo el trabajo del panorama** (`f873003`). Es deuda preexistente del drill (2026-08-02).

⚠️ **Con `ctx` de cuantificar la pregunta 4 también falla**, por otra rama (Drill N1 genérico, `:317`, que antepone `produccion de RUBIALES` al texto). Las guardas van **arriba del todo** y cubren ambos caminos. Los tests fijan los dos.

### 🔴 H-02 — Causa raíz 1: las conjugaciones en 1ª persona del plural NO están en el léxico del drill

`maquina_q.py:42-48`:
```python
_PROD_KW = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO",
            "CUANTO", "CUANTA", "CUANTOS", "CUANTAS")
_PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO")
```
Grep de `PRODUCIMOS`/`PRODUJIMOS` en `maquina_q.py`: **cero**. En «cuánto produjimos en abril» el único indicio de producción que ve el drill es el `CUANTO` ambiguo, que el propio código marca como tal (`:44-46`).

⚠️ El arreglo del panorama (`f873003`) añadió estas conjugaciones a `vocabulario_dominio.yaml` — **otro archivo, otro contrato** (filtro de dominio). Aquí faltan en el léxico del drill. Unificar las dos listas queda fuera (§7.5).

### 🔴 H-03 — Causa raíz 2: el ranking cae en la rama estructural por `CAMPOS`

`_ESTRUCT_KW` (`:51-53`) contiene `CAMPOS` y `CUAL`. La última rama (`:338`) reescribe a `que es {entidad}` cualquier frase ≤5 tokens con esas palabras que ninguna rama anterior capturó.

La asimetría que delató la causa (medido):

| Frase | Tokens | Resultado |
|---|---|---|
| «Cuales campos produjeron mas **hoy**?» | 5 | `que es RUBIALES` ❌ |
| «Cuales campos produjeron mas **en agosto**?» | 6 | `None` ✅ — **solo por pasar el corte de longitud** (`:180`) |

`ranking.detectar` reconoce las dos. **Y es puro** (`ranking.py:119-201`, sin BD) → se puede llamar en la ruta de cada mensaje sin coste.

### 🟡 H-04 — Hay precedente EXACTO de este arreglo, dos veces. Se clona.

- **Guarda de capacidades** (`:121-133`): *«…caían en la rama estructural y se reescribían a "que es {entidad}": el usuario pedía saber qué sabe hacer el bot y recibía la ficha jerárquica de CASTILLA.»* Mismo síntoma que H-03. Solución: `return None` temprano.
- **Ventana temporal** (`:144-153`): *«se consulta al DETECTOR REAL, no a una lista de palabras paralela. Un detector, dos consumidores.»* De ahí que la guarda 2 pregunte a `ranking.detectar`.

### 🔴 H-05 — 107 asserts fijan el drill. Medido: ninguno se rompe.

| Archivo | Asserts |
|---|---|
| `test_cuantificar.py` | 50 |
| `test_consulta_v2_clasificador.py` | 28 |
| `test_cuantificar_dia.py` | 10 |
| `test_curva_acumulada.py` | 9 |
| `test_p50_referencia.py` | 5 |
| `test_capacidades.py` · `test_incompleta.py` | 2 · 2 |
| `test_no_soportado.py` | 1 |

Se extrajeron las **45 frases** que esos tests pasan a `_continuacion` y se cruzaron con las dos guardas: **0 cortadas**. El más delicado, `test_cuantificar_dia.py:735` («produjo el campo en mayo» **sí** debe heredar aunque diga «campo»), pasa porque `ranking.detectar` devuelve `None` para él.

---

## §1-bis. Hallazgos de la VERIFICACIÓN (v2)

### 🔴 V-01 — La guarda 2 de la v1 rompía el drill de Analizar

El cierre de Analizar ofrece *«¿Quieres ver qué campos explican el faltante?»* (`respuesta_analizar.py:49`). Medido con `ctx = {grupo: analizar, entidad: CASTILLA, sub: proyeccion}`:

| Respuesta del usuario | Hoy (`_continuacion`) | `ranking.detectar` | v1 |
|---|---|---|---|
| «que campos explican el faltante» | `por que la produccion de CASTILLA esta corta` ✅ | **`True`** | cortaba → perdía CASTILLA ❌ |
| «si» / «los campos» / «el detalle por campo» | ídem ✅ | `False` | pasaba ✅ |

El detector de ranking ve «campos» + «faltante» (métrica gap) y cree que es un ranking. Dentro de una conversación de Analizar **no lo es**: es la aceptación de la oferta. **→ La guarda 2 se restringe a `ctx.get("grupo") != "analizar"`.** Con `ctx` de jerarquizar (sin clave `grupo`) y de cuantificar sigue aplicando, que es donde hace falta.

### 🟢 V-02 — Las guardas dejan pasar TODAS las continuaciones de los otros drills

Medido, 22 frases:

| Drill | Frases probadas | Resultado |
|---|---|---|
| Ranking (`:200`) | «para crudo», «y gas?», «blancos», «al revés», «cambiando el orden», «los que menos», «los peores», «invierte» | 8/8 pasan |
| Analizar (`:225`) | «si», «los campos», «el detalle por campo», «la proyección», «la vicepresidencia», «el presupuesto», «detractores» | 7/7 pasan (+ el de V-01, con la restricción) |
| Jerarquizar (`:338`) | «sus campos», «cuáles campos tiene», «a qué activo pertenece», «POE», «y sus pozos?», «cuántos pozos tiene» | 6/6 pasan |

### 🟢 V-03 — `ranking.detectar` es puro

`ranking.py:119-201`. Sin `get_engine`, `sa.text` ni `connect()` dentro de la función (las consultas están en `ejecutar`, otra función). Llamarlo en cada mensaje con contexto no cuesta nada.

### 🔴 V-04 — `re` NO está importado en `maquina_q.py`

Imports reales (`:10-23`): `datetime`, `sqlalchemy`, y módulos del proyecto. Cero usos de `re.compile`. La constante `_RX_SUJETO_PROPIO` lo necesita. **→ §3.3 lo añade.** También verificado: **no existe ningún import de `ranking`** en el módulo, el alias `_ranking_cont` está libre, y no hay ciclo (`ranking.py` no importa `maquina_q`).

### 🟡 V-05 — Las respuestas globales no dejan `ctx`

`:681`: `elif res.get("entidad_cruda"):` — el panorama del mes y cualquier respuesta global de cuantificar **no actualizan la memoria**. Consecuencia para §6.2: tras «¿cuánto produjimos en abril?» (global), «¿y en mayo?» hereda **lo que hubiera antes**, no «el global». No es de este plan (§7.9), pero la secuencia de validación debe tenerlo en cuenta o el usuario creerá que la memoria se rompió.

---

## §2. Estado actual — qué está mirando el executor

`_continuacion` (`maquina_q.py:113-340`) evalúa en este orden. Las guardas nuevas entran en 🆕:

```
:117   toks = norm(texto).split();  t = " ".join(toks)      ← `t` ya existe aquí
:132   guarda de CAPACIDADES            → return None
🆕     guarda 1 · SUJETO PROPIO         → return None       ← §3.2
🆕     guarda 2 · RANKING (no analizar) → return None       ← §3.2
:134   ent = entidad_en(texto)
:154   rama TEMPORAL
:175   excepción del ACUMULADO
:180   corte de 5 tokens
:183   frase que NOMBRA entidad
:200   drill de RANKING (ctx ranking)
:225   drill de ANALIZAR                ← «que campos explican el faltante» DEBE llegar aquí (V-01)
:285   drill de REFERENCIA
:292   drill N1→N2
:317   drill N1 GENÉRICO                ← captura «cuanto produjimos en abril» con ctx cuantificar ❌
:332   ofrece_produccion                ← captura «cuanto produjimos en abril» con ctx jerarquizar ❌
:338   rama ESTRUCTURAL                 ← captura «cuales campos produjeron mas hoy» ❌
:340   return None
```

---

## §3. Especificación

> **LOCALIZAR** es texto literal verificado con grep. Si no aparece **exactamente**, **DETENERSE y reportar**.

### §3.1 — MODIFICAR `maquina_q.py`: las conjugaciones que faltan

**Archivo A1.** Justificación: H-02.

**LOCALIZAR** (`:42-43` — solo estas dos líneas; el comentario que sigue NO se toca):
```python
_PROD_KW = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO",
            "CUANTO", "CUANTA", "CUANTOS", "CUANTAS")
```

**SUSTITUIR POR:**
```python
# [2026-09-08 · DRILL-AUTOCONTENIDA] +PRODUCIMOS/PRODUJIMOS/PRODUCEN/PRODUJERON. Medido: el
# léxico solo tenía 3ª persona del singular, así que en «¿cuánto PRODUJIMOS en abril?» el único
# indicio de producción que veía el drill era el CUANTO ambiguo — y la frase caía en el Drill N1
# genérico como si fuera un «¿y en abril?», heredando la entidad del turno anterior. El usuario
# preguntó por el global y recibió la cifra de RUBIALES, sin aviso (visto en la app, 2026-09-08).
_PROD_KW = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO",
            "PRODUCIMOS", "PRODUJIMOS", "PRODUCEN", "PRODUJERON",
            "CUANTO", "CUANTA", "CUANTOS", "CUANTAS")
```

**LOCALIZAR** (`:48`, una sola línea):
```python
_PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO")
```

**SUSTITUIR POR:**
```python
# [2026-09-08 · DRILL-AUTOCONTENIDA] Las mismas conjugaciones también aquí: esta tupla es el
# subconjunto SIN ambigüedad (nombra el verbo, no el CUANTO), y la usa `ambiguo_estructural`
# (:315) para decidir si «cuántos X en mayo» es producción o conteo. Sin las formas del plural,
# «cuántos campos produjeron más» parecía un conteo estructural puro.
_PROD_EXPLICITO = ("PRODUCCION", "PRODUJO", "PRODUCE", "PRODUCIDO",
                   "PRODUCIMOS", "PRODUJIMOS", "PRODUCEN", "PRODUJERON")
```

---

### §3.2 — MODIFICAR `maquina_q.py`: las dos guardas

**Archivo A1.** Justificación: H-01, H-03, H-04, H-05, V-01.

**LOCALIZAR** (`:132-134`):
```python
    if capacidades.detectar(texto, False) is not None:
        return None
    ent = respuesta_jerarquizar.entidad_en(texto)      # ¿nombra una entidad (hijo o cualquiera)?
```

**SUSTITUIR POR:**
```python
    if capacidades.detectar(texto, False) is not None:
        return None
    # [2026-09-08 · DRILL-AUTOCONTENIDA] GUARDA 1 · PREGUNTA CON SUJETO PROPIO.
    # «¿cuánto PRODUCIMOS hoy?» / «¿cuánto PRODUJIMOS en abril?» no continúan nada: el usuario
    # cambió de tema y preguntó por el GLOBAL. Medido en la app (2026-09-08), con el ctx de
    # jerarquizar que dejó el turno anterior: la frase caía en la rama `ofrece_produccion` de
    # abajo, que SUSTITUYE el texto por «produccion de RUBIALES» — y el usuario recibía DOS
    # respuestas equivocadas de una vez: la entidad (Rubiales en vez del global) y el mes
    # (septiembre en vez de abril, porque "abril" desaparecía con el texto). Con ctx de
    # cuantificar pasaba lo mismo por el Drill N1 genérico. Esta guarda va ARRIBA y cubre ambos.
    # 🔑 La 1ª persona del PLURAL es el discriminador, y no es un detalle gramatical: "producimos"
    #    tiene sujeto propio —nosotros, Ecopetrol— mientras que "produjo" lo tiene elidido y por
    #    eso SÍ admite heredarlo del contexto. «¿y cuánto produjo en mayo?» sigue heredando.
    # 🔑 Mismo patrón que la guarda de capacidades de arriba: `return None` temprano, para que la
    #    frase viaje ENTERA al clasificador y se resuelva sola. No se reescribe nada.
    if _RX_SUJETO_PROPIO.search(t):
        return None
    # [2026-09-08 · DRILL-AUTOCONTENIDA] GUARDA 2 · RANKING AUTOCONTENIDO.
    # «¿cuáles campos produjeron más hoy?» es un ranking completo, no una continuación. Sin esta
    # guarda matcheaba CAMPOS y CUAL en _ESTRUCT_KW, ninguna rama previa la capturaba y caía en la
    # rama ESTRUCTURAL (:338) -> «que es RUBIALES»: el usuario pedía un ranking y recibía la ficha
    # jerárquica de un campo. Es EXACTAMENTE el síntoma que la guarda de capacidades documenta
    # arriba (:127-129), entrando por otra puerta.
    # 🔑 La asimetría que delató la causa: la MISMA pregunta con «en agosto» (6 tokens) ya devolvía
    #    None — pero solo por pasar el corte de longitud de :180, no porque el drill la entendiera.
    #    Correcta por accidente. Esta guarda la hace correcta por contrato.
    # 🔑 Se consulta al DETECTOR REAL (puro, ranking.py:119-201), no a una lista de palabras
    #    paralela. Es la lección de la ventana temporal en :144-151: «Un detector, dos
    #    consumidores». Y NO basta con «¿menciona CAMPOS?»: «produjo el campo en mayo» menciona
    #    CAMPO y SÍ debe heredar (test_cuantificar_dia.py:735); para esa frase el detector da None.
    # 🔑 EXCEPTO en una conversación de ANALIZAR. Su cierre ofrece literalmente «¿Quieres ver qué
    #    campos explican el faltante?»; el usuario responde con esa frase, y el detector de
    #    ranking la reconoce (ve "campos" + "faltante"). Medido: sin esta excepción se cortaba y
    #    perdía la entidad — hoy el drill de analizar (:225) la reescribe bien. El ctx de
    #    jerarquizar no lleva clave "grupo" y el de cuantificar dice "cuantificar": en ambos la
    #    guarda aplica, que es donde hace falta.
    if ctx.get("grupo") != "analizar" and _ranking_cont.detectar(texto) is not None:
        return None
    ent = respuesta_jerarquizar.entidad_en(texto)      # ¿nombra una entidad (hijo o cualquiera)?
```

⚠️ **`t` ya está definido** en `:120`. **No lo redefinas.**

---

### §3.3 — MODIFICAR `maquina_q.py`: imports y constante

**Archivo A1.** Justificación: V-04.

**LOCALIZAR** (`:10-13`):
```python
from datetime import datetime, timezone
from datetime import date as _date

import sqlalchemy as sa
```

**SUSTITUIR POR:**
```python
import re
from datetime import datetime, timezone
from datetime import date as _date

import sqlalchemy as sa
```

**LOCALIZAR** (`:18`, una sola línea):
```python
from app.features.consulta_v2.dominio import nivel_dominio
```

**SUSTITUIR POR:**
```python
from app.features.consulta_v2.dominio import nivel_dominio
# [2026-09-08 · DRILL-AUTOCONTENIDA] El detector de ranking (PURO), para la guarda 2 de
# `_continuacion`. Se consulta al detector REAL en vez de duplicar su vocabulario aquí — misma
# razón que la ventana temporal (:144-151): dos listas paralelas se desincronizan.
from app.features.consulta_v2.cuantificar import ranking as _ranking_cont
```

**LOCALIZAR** (`:87`, una sola línea):
```python
_MES_ACTUAL_KW = ("ESTE MES", "MES ACTUAL", "MES EN CURSO", "PASADO", "ANTERIOR")
```

**SUSTITUIR POR:**
```python
_MES_ACTUAL_KW = ("ESTE MES", "MES ACTUAL", "MES EN CURSO", "PASADO", "ANTERIOR")

# [2026-09-08 · DRILL-AUTOCONTENIDA] Verbo de producción en 1ª persona del PLURAL: la marca de
# que la pregunta trae su propio sujeto (nosotros = Ecopetrol) y por tanto NO es una continuación
# que deba heredar la entidad del turno anterior. Ver la guarda 1 en `_continuacion`.
# 🔑 PRODU[CJ]: el pretérito cambia la raíz (produJimos). Con PRODUC\w* a secas, «produjimos»
#    no matchea — verificado.
_RX_SUJETO_PROPIO = re.compile(r"\bPRODU[CJ]IMOS\b")
```

---

### §3.4 — CREAR `tests/test_drill_autocontenida.py`

**Archivo A2, NUEVO.** Justificación: H-05 (fijar lo que no cambia), H-01 (los dos `ctx` reales), V-01 (la excepción de Analizar).

**CONTENIDO COMPLETO:**
```python
"""El drill no secuestra preguntas autocontenidas (2026-09-08 · DRILL-AUTOCONTENIDA).

Bug real visto en la app: tras «¿cuánto produjo Rubiales hoy?», las dos preguntas siguientes
—que NO nombraban a Rubiales— se respondieron sobre Rubiales. `_continuacion` las reescribía
heredando la entidad del contexto, por DOS caminos distintos según el ctx vigente.

Estos tests fijan las dos mitades del contrato:
  · las frases autocontenidas que deben romper el hilo (devolver None), con los DOS ctx reales
  · las continuaciones legítimas de los 4 drills, que deben seguir heredando intactas

`_continuacion` es PURA (sin BD ni LLM): recibe el ctx como argumento.
"""
from app.features.consulta_v2.maquina_q import _continuacion

# ctx que deja «¿cuánto produjo Rubiales hoy?» (cuantificar con entidad).
_CTX_CUANT = {"grupo": "cuantificar", "entidad": "RUBIALES", "producto": "crudo", "periodo_ctx": None}
# ctx que deja una ficha jerárquica («que es RUBIALES»): SIN clave "grupo". Es el que estaba
# vigente cuando el usuario preguntó «¿cuánto produjimos en abril?» y recibió Rubiales/septiembre.
_CTX_JERAR = {"entidad": "RUBIALES", "nivel": "campo", "hijos": [], "ofrece_produccion": True}
# ctx de una conversación de Analizar.
_CTX_ANALIZ = {"grupo": "analizar", "entidad": "CASTILLA", "sub": "proyeccion", "producto": None}


def test_sujeto_propio_rompe_el_hilo_con_ctx_cuantificar():
    for frase in ("Cuanto produjimos en abril?", "Cuanto producimos hoy?",
                  "cuanto producimos este mes?"):
        rw = _continuacion(frase, _CTX_CUANT)
        assert rw is None, f"{frase!r} heredó la entidad: {rw!r}"


def test_sujeto_propio_rompe_el_hilo_con_ctx_jerarquizar():
    """El camino REAL de la sesión del usuario: la rama ofrece_produccion SUSTITUÍA el texto."""
    for frase in ("Cuanto produjimos en abril?", "Cuanto producimos hoy?"):
        rw = _continuacion(frase, _CTX_JERAR)
        assert rw is None, f"{frase!r} se reescribió a {rw!r} y perdió su propio mes"


def test_ranking_no_se_convierte_en_ficha_jerarquica():
    for ctx in (_CTX_CUANT, _CTX_JERAR):
        for frase in ("Cuales campos produjeron mas hoy?", "cuales campos produjeron mas?",
                      "cuales activos produjeron menos?"):
            rw = _continuacion(frase, ctx)
            assert rw is None, f"{frase!r} se reescribió a {rw!r} en vez de viajar entera"


def test_ranking_con_mes_sigue_igual():
    """Ya funcionaba (por el corte de 5 tokens). No debe cambiar."""
    assert _continuacion("Cuales campos produjeron mas en agosto?", _CTX_CUANT) is None


def test_continuacion_temporal_sigue_heredando():
    """REGRESIÓN (test_cuantificar_dia.py:705): lo que el drill hace bien no puede romperse."""
    for frase in ("y en mayo?", "y en junio", "y mayo?"):
        rw = _continuacion(frase, _CTX_CUANT)
        assert rw is not None and "RUBIALES" in rw, f"{frase!r} perdió el hilo"


def test_continuacion_acumulado_y_referencia_siguen_heredando():
    assert _continuacion("y el acumulado?", _CTX_CUANT) == "acumulado de RUBIALES"
    rw = _continuacion("vs operativo", _CTX_CUANT)
    assert rw is not None and "RUBIALES" in rw


def test_continuacion_estructural_sigue_heredando():
    """«¿a qué activo pertenece?» SÍ es una continuación con pronombre elidido."""
    assert _continuacion("a que activo pertenece?", _CTX_CUANT) == "que es RUBIALES"
    assert _continuacion("sus campos?", _CTX_CUANT) == "que es RUBIALES"


def test_produccion_que_menciona_campo_sigue_heredando():
    """REGRESIÓN CRÍTICA (test_cuantificar_dia.py:735): «campo» genérico NO es un ranking."""
    rw = _continuacion("produjo el campo en mayo", _CTX_CUANT)
    assert rw is not None and rw.startswith("produccion de"), \
        f"regresión: producción real bloqueada por la guarda de ranking: {rw!r}"


def test_drill_de_ranking_sigue_funcionando():
    """Las continuaciones de un ranking («y gas?», «los que menos») no deben cortarse."""
    ctx_rank = {"grupo": "cuantificar", "subgrupo": "ranking", "producto": "crudo",
                "direccion": "top", "nivel_ranking": "campo", "metrica": "real"}
    assert _continuacion("y gas?", ctx_rank) == "cuales campos son los mayores productores de gas"
    assert _continuacion("los que menos", ctx_rank) == "cuales campos son los menores productores de crudo"


def test_oferta_de_analizar_sigue_heredando():
    """V-01: el cierre de Analizar ofrece «¿qué campos explican el faltante?». Responder con esa
    frase NO es un ranking aunque el detector lo crea: debe seguir al drill de analizar."""
    esperado = "por que la produccion de CASTILLA esta corta"
    assert _continuacion("que campos explican el faltante", _CTX_ANALIZ) == esperado
    assert _continuacion("si", _CTX_ANALIZ) == esperado
```

---

## §4. Orden de ejecución

| Paso | § | Archivo | Acción | Verificación inmediata |
|---|---|---|---|---|
| 0 | — | — | **Línea base**: V-1 | anotar passed/failed |
| 1 | 3.3 | `maquina_q.py` | `import re` + import de `ranking` + `_RX_SUJETO_PROPIO` | V-4, V-4b |
| 2 | 3.1 | `maquina_q.py` | +conjugaciones en las 2 tuplas | V-5 |
| 3 | 3.2 | `maquina_q.py` | las 2 guardas, tras la de capacidades | V-6 |
| 4 | 3.4 | `tests/test_drill_autocontenida.py` | crear | V-7 |
| 5 | — | — | **§6.1 completa** | todo verde |

⚠️ **El orden 1→2→3 importa**: la constante y el import deben existir antes de que las guardas los usen.

**Un repo (`ProdIABack`), un commit.**

---

## §5. Reglas no negociables

1. **Ancla que no aparece exactamente → DETENTE** y reporta ancla, archivo y lo hallado.
2. **Español** en código, comentarios y reporte.
3. **CERO cambios fuera de lo especificado.** No refactorices `_continuacion`, no reordenes sus ramas.
4. **NO se tocan**: frontend, `patrones_grupo.yaml`, `vocabulario_dominio.yaml`, `dominio.py`, `slots.py`, `ranking.py`, `respuesta_cuantificar.py`, ni ningún golden.
5. **Las 2 guardas van JUNTAS y ARRIBA**, justo tras la de capacidades.
6. **La guarda 2 lleva la excepción `ctx.get("grupo") != "analizar"`** (V-01). Sin ella rompe el drill de Analizar.
7. **La guarda 2 consulta `ranking.detectar`**, nunca una lista de palabras propia.
8. **`import re` se añade en §3.3 y solo ahí.** No añadas más imports.
9. **No corras `run_golden.py` ni `run_golden_cuantificar.py` en local.**
10. **Si V-3 falla en cualquier caso, DETENTE**: la guarda quedó demasiado ancha.
11. **Estado final: «implementado, PENDIENTE de validación humana».** Nunca «verificado».

---

## §6. Validación

### 6.1 Estática — la ejecuta el EXECUTOR (desde `backend\backend`, línea por línea)

| # | Qué | Comando | Esperado |
|---|---|---|---|
| **V-1** | Línea base (los 8 archivos que tocan el drill) | `uv run python -m pytest tests/test_cuantificar.py tests/test_consulta_v2_clasificador.py tests/test_cuantificar_dia.py tests/test_curva_acumulada.py tests/test_p50_referencia.py tests/test_capacidades.py tests/test_incompleta.py tests/test_no_soportado.py -q` | Anotar passed/failed |
| **V-2** | 🔴 Deben ROMPER el hilo, con los 2 ctx | ver bloque abajo | `[None, None, None, None, None, None]` |
| **V-3** | 🔴 Deben SEGUIR heredando (4 drills) | ver bloque abajo | ver el bloque |
| **V-4** | Imports y constante | `Select-String -Path app\features\consulta_v2\maquina_q.py -Pattern "^import re$\|_RX_SUJETO_PROPIO = re.compile\|import ranking as _ranking_cont"` | 3 resultados |
| **V-4b** | 🔴 El módulo arranca (sin import circular) | `$env:PYTHONPATH='.'; uv run python -c "import app.features.consulta_v2.maquina_q as m; print('import OK', bool(m._RX_SUJETO_PROPIO), bool(m._ranking_cont))"` | `import OK True True` |
| **V-5** | Conjugaciones en las 2 tuplas | `Select-String -Path app\features\consulta_v2\maquina_q.py -Pattern '"PRODUJIMOS"' -CaseSensitive` | **2** resultados (las dos tuplas; los comentarios no llevan comillas) |
| **V-6** | Guardas ARRIBA, antes de la rama estructural | `Select-String -Path app\features\consulta_v2\maquina_q.py -Pattern "_RX_SUJETO_PROPIO.search\|_ranking_cont.detectar\|que es \{ctx" \| Select-Object LineNumber` | Las 2 primeras líneas son **menores** que la tercera |
| **V-7** | 🔴 Los tests nuevos | `$env:PYTHONPATH='.'; uv run python -m pytest tests/test_drill_autocontenida.py -q` | **10 passed** |
| **V-8** | 🔴 Sin regresión | mismo comando de V-1 | **Mismo número de passed que V-1** |
| **V-9** | Frontend intacto | `git -C ..\..\frontend status --short` | Sin salida |

**Comando de V-2** (una línea):
```powershell
$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.maquina_q import _continuacion as f; c={'grupo':'cuantificar','entidad':'RUBIALES','producto':'crudo','periodo_ctx':None}; j={'entidad':'RUBIALES','nivel':'campo','hijos':[],'ofrece_produccion':True}; print([f('Cuanto produjimos en abril?',c), f('Cuanto producimos hoy?',c), f('Cuales campos produjeron mas hoy?',c), f('Cuanto produjimos en abril?',j), f('Cuanto producimos hoy?',j), f('Cuales campos produjeron mas hoy?',j)])"
```
Esperado literal: `[None, None, None, None, None, None]`

**Comando de V-3** (una línea):
```powershell
$env:PYTHONPATH='.'; uv run python -c "from app.features.consulta_v2.maquina_q import _continuacion as f; c={'grupo':'cuantificar','entidad':'RUBIALES','producto':'crudo','periodo_ctx':None}; r={'grupo':'cuantificar','subgrupo':'ranking','producto':'crudo','direccion':'top','nivel_ranking':'campo','metrica':'real'}; a={'grupo':'analizar','entidad':'CASTILLA','sub':'proyeccion','producto':None}; print([f('y en mayo?',c), f('y el acumulado?',c), f('a que activo pertenece?',c), f('vs operativo',c), f('produjo el campo en mayo',c), f('y gas?',r), f('que campos explican el faltante',a)])"
```
Esperado literal:
```
['produccion de RUBIALES y en mayo?', 'acumulado de RUBIALES', 'que es RUBIALES', 'produccion de RUBIALES vs operativo', 'produccion de RUBIALES produjo el campo en mayo', 'cuales campos son los mayores productores de gas', 'por que la produccion de CASTILLA esta corta']
```
⚠️ **Si alguno sale `None`, la guarda quedó demasiado ancha → DETENTE.** El último es la regresión de Analizar (V-01).

### 6.2 Humana — la valida el USUARIO, en el servidor de PRUEBAS

> 🔴 **R3: «build verde» NO es «feature verificada».** El drill solo actúa en tráfico real. Solo el usuario marca ✅.

En `http://localhost:5029`. Sin Ctrl+F5 (el JS no cambió). **Reiniciar el backend.**

🔑 **Todo en UNA SOLA conversación, en este orden.** El bug solo aparece con contexto vivo. El paso H-5 **re-ancla** una entidad a propósito: tras un ranking y un global, la memoria no tiene entidad que heredar (V-05), y sin ese paso el usuario creería que el arreglo rompió el hilo.

| # | Acción (misma conversación, en orden) | Esperado |
|---|---|---|
| H-1 | «¿Cuánto producimos hoy?» | Panorama del mes, 5 tarjetas |
| H-2 | «¿Cuánto produjo Rubiales hoy?» | Rechazo honesto por techo, sobre RUBIALES |
| H-3 | «¿Cuáles campos produjeron más hoy?» | **Un RANKING de campos.** NO la ficha de Rubiales |
| H-4 | «¿Cuánto produjimos en abril?» | **Global, y de ABRIL.** NO Rubiales, NO septiembre |
| H-5 | «¿Cuánto produjo Castilla en abril?» | Cifra de Castilla en abril (re-ancla la memoria) |
| H-6 | «¿y en mayo?» | **Castilla, mayo.** La memoria sigue viva |
| H-7 | «¿a qué activo pertenece?» | La ficha jerárquica de Castilla |
| H-8 | «¿y el acumulado?» | El acumulado de Castilla |
| H-9 | «¿Por qué está corto Castilla?» y luego responder **«qué campos explican el faltante»** | La segunda debe dar el **análisis causal de Castilla**, no perder la entidad (V-01) |
| H-10 | F12 → Console | 0 errores |

⚠️ **H-6 a H-9 son la mitad crítica**: si alguna pierde el hilo, el arreglo se pasó de ancho y hay que revertir.

---

## §7. Fuera de alcance

1. **Las otras 5 ramas del drill**: intactas.
2. **El corte de 5 tokens** (`:180`): se conserva.
3. **`ranking.detectar` con «hoy»** devuelve `periodo_texto: None` → el ranking responderá el **mes**. Límite del dato diario, no se toca.
4. **Ranking dentro de una conversación de Analizar**: con la excepción de V-01, «¿cuáles campos produjeron más?» tras un análisis sigue yendo al drill de analizar (comportamiento actual). Caso raro; se documenta, no se resuelve.
5. **Unificar `_PROD_KW` con `vocabulario_dominio.yaml`**: dos contratos distintos. Refactor aparte.
6. **El `periodo_ctx` heredado** (`:326-330`): no se toca.
7. **Goldens**: ninguno mide el drill. No se tocan.
8. **Migración `012_p50_2026_desglose.sql`** y **hoja POP Filiales**: hilos abiertos, ajenos.
9. **Que las respuestas globales dejen `ctx`** (V-05): «¿cuánto produjimos en abril?» → «¿y en mayo?» no hereda «global». Deuda propia, con su propio plan si se quiere.

---

## Prompt para el agente EXECUTOR

```
Eres un agente EXECUTOR. Lee COMPLETO el plan
c:\APLICACIONES\ProdIA\Repo ProdIA\backend\Planes\plan_DRILL-PREGUNTA-AUTOCONTENIDA_20260908.md
(versión v2) y ejecútalo AL PIE DE LA LETRA.

Reglas:
- CERO modificaciones fuera de lo especificado. NO se tocan: frontend, patrones_grupo.yaml,
  vocabulario_dominio.yaml, dominio.py, slots.py, ranking.py, respuesta_cuantificar.py,
  ni ningún golden.
- Orden secuencial de §4, empezando por el paso 0 (línea base V-1, son 8 archivos de test).
- `import re` NO está en maquina_q.py: lo añade §3.3, y solo ese.
- Las 2 guardas van JUNTAS y ARRIBA, justo tras la guarda de capacidades.
- La guarda 2 lleva la excepción `ctx.get("grupo") != "analizar"` y consulta ranking.detectar.
- `t` ya existe en :120 — no lo redefinas.
- Si un texto de LOCALIZAR no aparece EXACTAMENTE, DETENTE y reporta ancla, archivo y lo hallado.
- Si en V-3 alguno de los 7 casos sale None, la guarda quedó ancha: DETENTE.
- NO corras run_golden.py ni run_golden_cuantificar.py en local.
- Todo en español.

Reporta: ✅/❌ por cada Paso N de §4, y la tabla §6.1 completa con la salida REAL de cada
comando (no «OK»: la salida literal). V-2, V-3, V-7 y V-8 son los decisivos.

Al final: archivos tocados + "¿Hago commit?". Es UN repo (ProdIABack), un commit.
El estado que reportas es «implementado, PENDIENTE de validación humana (§6.2)» — NUNCA
«verificado» ni «completado».
```
