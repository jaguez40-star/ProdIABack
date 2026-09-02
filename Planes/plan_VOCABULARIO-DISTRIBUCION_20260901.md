# plan_VOCABULARIO-DISTRIBUCION_20260901 — Que el motor entienda que le piden la distribución

> Plan **v3** auditado (flujo profesional §10 de CLAUDE.md). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación. **Dos hipótesis del diagnóstico inicial
> resultaron FALSAS y están corregidas en §1** — por eso este plan no se parece al que
> sugería `vocabulario_distribucion_error.md` §6.
>
> **Cambios de v2 → v3** (segunda pasada de verificación contra el código):
> 1. 🔴 El comando del golden en §6.1 usaba claves que `ejecutar()` NO devuelve (`ok`/`total`);
>    habría fallado con KeyError en el paso 5. Corregido con las claves reales.
> 2. 🟠 Descubierto un **cambio de comportamiento no documentado** (H9): pregunta de
>    distribución + entidad nombrada pasa de N1 a declinación honesta. Se fija con test.
> 3. ➕ Incorporada la **medición de valor** con `core.clasificacion_log` (H10): baseline PRE
>    en Pruebas y medición POST con veredictos de usuario — el plan ya no se mide solo contra
>    las 25 variantes sintéticas.
> 4. 🟢 Verificado que `norm()` NO elimina `%` (solo pliega acentos y colapsa espacios), así
>    que el token `%` de `_DISTRIBUCION` es viable tal como estaba especificado.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**solo el backend**, y dentro de él **un solo archivo de producción**.

**Raíz:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete vive en `backend\backend\app\...`.

**El problema:** el panel de distribución porcentual por campo **ya existe y está completo**
(dona con el Top 5, participación individual, cola declarada «Otros (125 campos) 58,1%»). Pero
el gate de `cuantificar/ranking.py:102-107` exige un **superlativo** para activarse. Resultado
medido: **13 de 25 formas de pedir la distribución no la activan**.

Ver el hallazgo completo en `jerarquias_sup_error.md`'s hermano:
`C:\APLICACIONES\ProdIA\Repo ProdIA\vocabulario_distribucion_error.md`.

**Convenciones del módulo destino** (`cuantificar/ranking.py`):
- El matching es por **token exacto**, nunca substring (criterio AF-3.7, comentado en `:46`).
  `_tokens()` (`:83-84`) parte por espacios y hace `strip(_PUNCT)`.
- `_PUNCT` (`:68`) **no incluye `%`**: `"en %,"` → token `%`; `"40%"` → token `40%`.
- Las tuplas de vocabulario van en MAYÚSCULAS sin acentos (el texto entra por `norm()`).

**Cómo correr los tests** (consola normal, sin admin):
```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
```
Los tests `V-DETECT` son puros (sin BD) y corren en local. Los `V-CALC` tocan Postgres y se
saltan solos si no hay conexión.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🟢 H1 — El riesgo que motivó el plan NO EXISTE

El hallazgo original advertía: *«DISTRIBUCIÓN o REPARTO pueden capturar preguntas que hoy van
bien a ANALIZAR»*. **Es falso, y la arquitectura lo impide:**

- `maquina_q.py:579-584` — solo la rama `elif grupo == "cuantificar"` llama a
  `respuesta_cuantificar.responder()`.
- `respuesta_cuantificar.py:213` — `rk = _ranking.detectar(texto)` es la primera línea de esa
  función.

⇒ **`detectar()` solo se ejecuta si el clasificador YA decidió `cuantificar`.** Añadir palabras
a `ranking.py` **no puede mover ninguna pregunta de grupo**. El riesgo de reclasificación es
**nulo** por esta vía; vivía todo en `patrones_grupo.yaml`, que este plan NO toca.

Corolario: **el golden de 92 casos no puede romperse con este cambio.** Se mide igual (§6),
pero por higiene, no por riesgo.

### 🔴 H2 — El riesgo REAL va en la dirección contraria

El peligro no es que estas preguntas se vayan a Analizar, sino que **no lleguen a Cuantificar**.
`patrones.py:63-64`: si ningún patrón de Capa 1 atrapa, devuelve `None` → Capa 2 (LLM).

Verificado para los casos reales del usuario: *«Cómo se distribuye **la producción** de crudo,
%, entre los campos productores»* contiene `PRODUCCION`, que matchea `'\bPRODUCCION\b'`
(`patrones_grupo.yaml:155`) → clasifica `cuantificar` → **sí llega** a `detectar()`.

⚠️ Pero la forma telegráfica `distribución % crudo por campo` **no contiene** `PRODUCCION` ni
ningún otro patrón de cuantificar → depende del LLM para siquiera llegar. **Eso queda fuera de
alcance de este plan** (§7) y se anota como pendiente separado.

### 🔴 H3 — `PESO`/`PESA` está ARBITRADA por el usuario en dirección contraria

Tres evidencias independientes de que esa semántica es **causal**, no distributiva:

| Ubicación | Qué dice |
|---|---|
| `patrones_grupo.yaml:206` | `'QUE\s+CAMPOS?\s+PESA[N]?'` es patrón de **ANALIZAR** |
| `patrones_grupo.yaml:66-71` | Exclusión `(?!...\|PESA\|APORTA\|EXPLICA)` **deliberada**, con el comentario: *«"¿cuántos campos PESAN más en el gap?" sigue siendo ANALIZAR (decisión del usuario: ahí gana el gap)»* |
| `analizar/subrouter.py:21` | `PESAN`/`PESA` en `_CAUSAL_EXPL` |

Vigilada por 4 casos del golden (`:70`, `:142`, `:153`, `:226`) y 1 de `analizar_golden.yaml:9`.

⇒ **`PESA`/`PESAN` NO se añaden.** Contradice una decisión cerrada del 2026-08-24. El
sustantivo `PESO` («el peso de cada campo») es distinto del verbo y sería defendible, pero por
token exacto son tokens distintos: **se deja fuera igual**, por prudencia. La variante #6 del
Cluster A seguirá fallando, y es correcto que así sea.

### 🟠 H4 — `DESGLOSE` daría cobertura parcial e inexplicable

- `patrones_grupo.yaml:93` la reclama para **JERARQUIZAR** cuando la forma es
  `DESGLOS* <nivel> … POR <nivel>`.
- `respuesta_analizar.py:57` la usa en `_RX_POR_CAMPOS` para abrir el panel de desglose de
  Analizar.

Resultado: *«desglósame la producción de crudo por campo»* → llega (el primer sustantivo es
PRODUCCION, no un nivel). *«desglósame el activo Castilla por campo»* → jerarquizar, nunca
llega. **La misma palabra funcionaría o no según el sustantivo que la siga.**

⇒ **Se añade igual** (la forma que llega es la útil), pero **se documenta en el código** para
que nadie la lea como cobertura total. La variante #5 del Cluster A quedará cubierta.

### 🟡 H5 — `PORCENTAJE` ≠ `PORCENTUAL` ≠ `%`

Por token exacto, son tres tokens distintos. Hay que listar **las tres formas** o el resto no
se captura. `PORCENTAJE` aparece en `cuantificar/validador.py:14` pero como **nombre de
unidad**, no como señal de intención: sin conflicto.

Sobre `%`: `_PUNCT` (`:68`) no lo incluye, así que `"en %,"` tokeniza a `%` limpio, pero
`"40%"` quedaría como `40%`. Añadir `%` como token es seguro y cubre la forma «, %,» del
usuario.

### 🟢 H6 — El cálculo NO hay que tocarlo

Verificado en `ranking.py:254-261` y `:370-382`: con `metrica="real"` y `direccion="top"`, el
resultado es **exactamente** el panel de distribución que ya funciona. `direccion` solo cambia
el rótulo en la rama `metrica="gap"`, que no aplica aquí.

⇒ **Basta con abrir el gate.** Cero cambios en SQL, en el cálculo o en el formateador.

### 🟢 H7 — 20 palabras verificadas como 100% seguras

Cero apariciones en `patrones_grupo.yaml` (310 líneas), en `subrouter.py`, en los 92 casos del
golden, y en el grep global de `consulta_v2`:

`DISTRIBUYE` · `DISTRIBUCION` · `DISTRIBUYEN` · `REPARTE` · `REPARTO` · `REPARTEME` ·
`PARTICIPACION` · `PORCENTUAL` · `PORCENTUALMENTE` · `CONTRIBUCION` · `CONTRIBUYE` ·
`FRACCION` · `SHARE` · `PROPORCION` · `ENCABEZAN` · `ENCABEZA` · `LIDERO` · `LIDERAN` ·
`LIDERA` · `PUNTEROS`

### 🟠 H9 — Cambio de comportamiento con entidad nombrada (verificado, se acepta y se fija)

`respuesta_cuantificar.py:228-234` — la guarda (3) del dispatcher: si el texto del ranking
nombra una entidad resoluble, **declina honesto** («El ranking DENTRO de «X» llega en una
próxima fase…»). Verificado que existe y corre DESPUÉS de `detectar()`.

Consecuencia del cambio: *«¿qué porcentaje aporta **el campo Castilla**?»*

| | Hoy | Con el cambio |
|---|---|---|
| `detectar()` | `None` (sin superlativo) → sigue a N1 | atrapa (`PORCENTAJE`+`CAMPO`) |
| Respuesta | Cifra de Castilla (sin %) | **Declinación honesta** de la guarda (3) |

Ni hoy ni después responde el porcentaje pedido; pero el comportamiento CAMBIA de «cifra
correcta a otra pregunta» a «declino». Se acepta: la declinación es más honesta que responder
otra cosa, y **el caso catastrófico NO ocurre** (jamás respondería el ranking global RUBIALES
a quien preguntó por Castilla — la guarda lo corta). Se fija con test (§3.4) para que el
comportamiento sea deliberado y vigilado, no accidental.

### ➕ H10 — El valor se mide contra uso real, no solo contra las 25 variantes

`consulta_v2/log.py:23-37` — **toda pregunta clasificada se registra** en
`core.clasificacion_log` (texto, grupo, capa, entidad), y los botones ✓/✗ del chat guardan el
veredicto humano (`poner_veredicto`, `:39`). Eso permite medir el valor de este plan contra
preguntas REALES de usuarios, no contra nuestra lista sintética:

- **Baseline PRE** (paso 0-bis): cuántas preguntas registradas contienen vocabulario de
  distribución y en qué terminaron.
- **Medición POST** (§6.3): mismas cuentas tras desplegar + veredictos ✓/✗ sobre esas
  preguntas concretas.

Si el baseline PRE da ~0, este plan es **preventivo** (nadie pregunta así todavía) y su
prioridad baja frente a las brechas de `jerarquias_sup_error.md`. Ese dato lo decide el
usuario, no el plan.

### 🟡 H8 — `DOMINA`/`DOMINAN`: vecindad con el detector de capacidades

`capacidades.py:57` usa `DOMINAS` dentro de `\bQUE\s+TEMAS\b.{0,24}\b(…|DOMINAS|SABES)\b`, y
ese detector es el **primer guard del motor** (`maquina_q.py:132`). Exige `QUE TEMAS` a ≤24
caracteres, así que no colisiona con «¿qué campos dominan la producción?».

⇒ Se añaden `DOMINAN`/`DOMINA` (no `DOMINAS`), con nota en el código.

---

## 2. Estado actual

`backend\backend\app\features\consulta_v2\cuantificar\ranking.py`:

- `_SUPERLATIVO` (`:38-40`), `_BOTTOM_TOK` (`:48-50`), `_TOP_GAP_TOK` (`:53`) — el vocabulario.
- El gate (`:102-107`): filtro 1 = superlativo; filtro 2 = token de nivel (`nivel is None →
  return None`).
- `_NIVEL_DIFERIDO` (`:70-76`) — gerencia y VP **declinan honestamente**, explicando el
  level-shift. No se toca: es correcto.
- Dirección y `top_n` (`:117-127`) — `direccion = "bottom" if es_bottom else "top"`;
  `top_n = 1 if singular else 5`.

Tests: `tests\test_cuantificar_ranking.py`, 27 tests. Los de `V-DETECT` son puros.

---

## 3. Especificación

### 3.1 AÑADIR dos tuplas en `ranking.py`, tras `_TOP_GAP_PHRASE` (línea ~54)

**No se tocan `_SUPERLATIVO` ni `_BOTTOM_TOK`.** «Distribución» no es un superlativo, y
mezclarlas haría que el código mienta sobre lo que detecta.

```python
# [2026-09-01] DISTRIBUCIÓN — familia ORTOGONAL al superlativo. Una distribución no pide el
# extremo, pide el reparto: no tiene dirección (las lista todas), así que NO entra en
# _SUPERLATIVO ni en _BOTTOM_TOK. Cae en el default metrica=real · direccion=top, que es
# exactamente el panel de participación que el motor ya sabe pintar (dona + % individual +
# cola declarada) — ver ranking.py:303 y el bullet _b_concentracion.
# Medido: 13 de 25 formas de pedir la distribución no activaban el ranking (ver
# vocabulario_distribucion_error.md).
# ⚠️ NO incluir PESA/PESAN: 'QUE CAMPOS PESAN' es patrón de ANALIZAR (patrones_grupo.yaml:206)
# y la exclusión de :66-71 es una decisión explícita del usuario del 2026-08-24. Se respeta.
# ⚠️ PORCENTAJE / PORCENTUAL / PORCENTUALMENTE / % son 4 TOKENS distintos (match exacto,
# AF-3.7): hay que listarlos todos. `_PUNCT` (:68) no incluye '%', así que "en %," tokeniza
# a '%' limpio.
# ⚠️ DESGLOS*: cobertura PARCIAL a propósito. "desglósame la producción por campo" llega aquí;
# "desglósame el activo Castilla por campo" lo atrapa antes jerarquizar (patrones_grupo.yaml:93)
# y "desglose por campo" del gap lo usa el panel de Analizar (respuesta_analizar.py:57).
_DISTRIBUCION = ("DISTRIBUYE", "DISTRIBUYEN", "DISTRIBUCION", "DISTRIBUIDA", "DISTRIBUIDO",
                 "REPARTE", "REPARTEN", "REPARTO", "REPARTEME", "REPARTIDA", "REPARTIDO",
                 "PARTICIPACION", "PARTICIPA", "PARTICIPAN",
                 "PORCENTAJE", "PORCENTUAL", "PORCENTUALMENTE", "%",
                 "CONTRIBUCION", "CONTRIBUYE", "CONTRIBUYEN",
                 "PROPORCION", "FRACCION", "SHARE",
                 "DESGLOSE", "DESGLOSA", "DESGLOSAME",
                 "REPRESENTA", "REPRESENTAN")

# [2026-09-01] DOMINANCIA — verbos de liderazgo. SÍ son superlativos semánticos (piden el
# extremo), pero se agrupan aparte para que el diff diga de dónde salió cada palabra.
# ⚠️ NO incluir DOMINAS: 'QUE TEMAS ... DOMINAS' es el detector de capacidades
# (capacidades.py:57), el primer guard del motor. DOMINA/DOMINAN no colisionan (aquel exige
# 'QUE TEMAS' a ≤24 chars).
_DOMINANCIA = ("ENCABEZA", "ENCABEZAN", "LIDERA", "LIDERAN", "LIDERO", "LIDERARON",
               "PUNTEROS", "PUNTERAS", "DOMINA", "DOMINAN")
```

### 3.2 MODIFICAR el gate (`ranking.py:102-107`)

Añadir las dos familias a la condición del filtro 1. **El filtro 2 (token de nivel) no se
toca**: sigue exigiendo `CAMPO`/`CAMPOS`/`ACTIVO`/… , que es el guardián correcto.

```python
    if not (any(s in toks for s in _SUPERLATIVO) or any(s in toks for s in _BOTTOM_TOK)
            or any(s in toks for s in _TOP_GAP_TOK)
            or any(s in toks for s in _DISTRIBUCION) or any(s in toks for s in _DOMINANCIA)
            or "TOP" in t or "RANKING" in t):
        return None
```

### 3.3 Efecto sobre `direccion` y `top_n` — verificado, no requiere cambios

- `direccion`: las palabras nuevas no están en `_BOTTOM_TOK` → `es_bottom = False` →
  `direccion = "top"` (`:122`). Correcto: la distribución se lee de mayor a menor.
- `top_n`: `singular = "CAMPO" in toks and "CAMPOS" not in toks` (`:125-127`). Las preguntas
  de distribución dicen «campos» (plural) → `top_n = 5`. **Decisión del usuario: Top 5.** ✅
- `metrica`: `"gap" if any(k in toks for k in _METRICA_GAP) else "real"` → `real`. Correcto.

### 3.4 AÑADIR tests en `tests\test_cuantificar_ranking.py`

Sección nueva al final. Todos son `V-DETECT` (puros, sin BD):

```python
# --- V-DETECT · DISTRIBUCIÓN y DOMINANCIA (2026-09-01) -------------------------------------

def test_distribucion_activa_el_ranking():
    """El caso real del usuario: no dice ningún superlativo, pide el reparto."""
    r = RK.detectar("como se distribuye la produccion de crudo, %, entre los campos productores")
    assert r is not None
    assert r["nivel_ranking"] == "campo"
    assert r["metrica"] == "real" and r["direccion"] == "top"
    assert r["top_n"] == 5

def test_distribucion_porcentualmente():
    r = RK.detectar("como se distribuye la produccion de crudo, porcentualmente, entre los campos")
    assert r is not None and r["direccion"] == "top"

def test_distribucion_participacion():
    r = RK.detectar("que participacion tiene cada campo en la produccion total de crudo")
    assert r is not None and r["nivel_ranking"] == "campo"

def test_distribucion_share_y_fraccion():
    assert RK.detectar("dame el share de cada campo sobre la produccion de crudo") is not None
    assert RK.detectar("que fraccion del crudo produce cada campo") is not None

def test_dominancia_verbos_de_liderazgo():
    """encabezan / lidero / punteros: superlativos semánticos que faltaban."""
    assert RK.detectar("que campos encabezan la produccion de aceite en agosto") is not None
    assert RK.detectar("que campo lidero la produccion durante agosto") is not None
    assert RK.detectar("muestrame los campos punteros en crudo para agosto") is not None

def test_distribucion_sigue_exigiendo_nivel():
    """El filtro 2 no se relaja: sin CAMPO/ACTIVO no es un ranking (H1 del plan)."""
    assert RK.detectar("como se distribuye la produccion de crudo") is None

def test_pesa_sigue_siendo_de_analizar():
    """🔒 REGRESIÓN: PESA/PESAN NO entran en _DISTRIBUCION — patrones_grupo.yaml:206 y la
    exclusión de :66-71 son una decisión del usuario del 2026-08-24 (ver H3 del plan)."""
    assert RK.detectar("que campos pesan en el gap") is None

def test_no_es_ranking_sin_ninguna_senal():
    """Regresión del gate: sin superlativo NI distribución NI dominancia, sigue None."""
    assert RK.detectar("cuanto crudo produjo Rubiales") is None

def test_distribucion_con_entidad_es_deteccion_y_la_guarda_decide():
    """H9 del plan: «¿qué porcentaje aporta el campo Castilla?» AHORA es detectada como
    ranking (PORCENTAJE + CAMPO). La declinación honesta la pone la guarda (3) del
    dispatcher (respuesta_cuantificar.py:228-234), que corre después y consulta la BD —
    por eso aquí SOLO se fija que detectar() devuelve algo (el cambio de comportamiento
    es deliberado, no accidental). El caso catastrófico —responder el ranking global a
    quien preguntó por Castilla— lo impide esa guarda, no este módulo."""
    r = RK.detectar("que porcentaje del crudo aporta el campo Castilla")
    assert r is not None and r["nivel_ranking"] == "campo"
```

⚠️ Nota para el executor sobre este último test: NO intentes probar la declinación completa
(`responder()`) en local — la guarda (3) llama a `resolver_unico`, que toca la BD. La
validación end-to-end de la declinación es humana, en Pruebas (§6.2).

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline de tests: `pytest tests/test_cuantificar_ranking.py -q` | anotar N pasados | DETENTE: roto de antes |
| 0-bis | **Baseline de USO real** (H10) — lo corre el USUARIO en Pruebas, no el executor: script de §6.3-PRE contra `core.clasificacion_log`. El executor lo pide y ANOTA el resultado en su reporte; si no está disponible, lo declara y sigue | número de preguntas reales con vocabulario de distribución + en qué terminaron | no bloquea: se declara «baseline de uso no disponible» |
| 1 | §3.1 — las dos tuplas | `py_compile` OK | revisar sintaxis |
| 2 | §3.2 — el gate | suite **igual al baseline** | una palabra nueva colisiona: revisar cuál |
| 3 | §3.4 — tests nuevos | los 9 pasan | ajustar según el `detectar()` real |
| 4 | Suite completa: `pytest tests/ -q` | mismos 10 fallos preexistentes, ni uno más | comparar con baseline |
| 5 | Golden (§6.1, comando corregido) | ≥90%, y **sin cambio respecto al baseline** | si baja: revertir. No debería (H1) |

**Corte de fase:** no lo hay — es un cambio atómico de un archivo. Si el paso 2 rompe algo, se
revierte entero.

⚠️ El paso 5 requiere BD (el golden resuelve entidades). En **local da resultados no
representativos** (BD congelada): si el executor corre en local, ejecuta el golden igualmente
para detectar crashes, pero **la cifra que vale es la de Pruebas** — anotarlo así en el reporte.

---

## 5. Reglas no negociables

1. **NO tocar `patrones_grupo.yaml`.** Ahí vive el 100% del riesgo de reclasificación (H1).
2. **NO añadir `PESA`/`PESAN`** — decisión cerrada del usuario, vigilada por 5 casos golden (H3).
3. **NO añadir `DOMINAS`** — pertenece al detector de capacidades (H8).
4. **NO tocar `_SUPERLATIVO` ni `_BOTTOM_TOK`.** Las familias nuevas van en tuplas propias:
   una distribución no es un superlativo y el código debe seguir diciendo la verdad.
5. **NO tocar el filtro 2** (token de nivel). Es lo que impide que «cuánto crudo produjo
   Rubiales» se convierta en ranking.
6. **NO tocar el cálculo, el SQL ni el formateador** (H6): el panel ya es correcto.
7. **NO tocar `_NIVEL_DIFERIDO`**: gerencia y VP declinan honestamente y eso está bien
   mientras las brechas de `jerarquias_sup_error.md` sigan abiertas.
8. Token exacto siempre, jamás substring (AF-3.7).

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\cuantificar\ranking.py
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

Golden — **antes y después**, aunque H1 diga que no puede moverse (se mide, no se supone).
⚠️ Comando corregido en v3: `ejecutar()` devuelve `pct` y `aciertos` — **no** existen `ok` ni
`total` (verificado en `run_golden.py:46-53`; el comando de v2 moría con KeyError):

```powershell
.venv\Scripts\python.exe -c "from app.features.consulta_v2.golden.run_golden import ejecutar; r=ejecutar(); print('pct:', r['pct'], '· aciertos:', r['aciertos'])"
```

Esperado: 9 tests nuevos en verde; baseline intacto; golden sin cambio (la cifra válida es la
de Pruebas — ver la nota del paso 5).

### 6.2 Humana (usuario) — en PRUEBAS

La BD local está congelada: el `detectar()` se prueba en local, pero **la respuesta completa se
valida en Pruebas**. Tras `git pull` + reiniciar INGESTA:

| Pregunta | Esperado |
|---|---|
| «¿Cómo se distribuye la producción de crudo, %, entre los campos productores?» | Panel de distribución con dona, Top 5 y cola declarada |
| «¿Qué participación tiene cada campo en la producción total de crudo?» | Ídem |
| «¿Qué campos encabezan la producción de aceite en agosto?» | Ranking Top 5 |
| «¿Qué campos pesan en el gap?» | **Sigue yendo a ANALIZAR** (regresión clave) |
| «¿Cuánto crudo produjo Rubiales?» | Cifra única, sin ranking |
| «¿Qué porcentaje del crudo aporta el campo Castilla?» | **Declinación honesta** de la guarda (3) — H9. Nunca el ranking global |

**El único que marca ✅ es el usuario.** Hasta entonces: «implementado, PENDIENTE de validación
humana».

### 6.3 Medición de VALOR — contra uso real, no solo contra la lista sintética (H10)

**Cobertura sintética** (nivel 1, débil pero reproducible): de las 25 variantes medidas,
**fallan 13 hoy → fallarán 2**.

| Variante | Tras el cambio |
|---|---|
| Cluster A #6 («¿qué **peso** tiene cada campo?») | ❌ a propósito (H3) |
| Telegráfica `distribución % crudo por campo` | ❌ no llega a Cuantificar (H2, fuera de alcance) |
| Las otras 11 | ✅ |

**Baseline PRE** (nivel 2, el que importa) — en **Pruebas**, carpeta
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell aparte, de una vez.
Solo lee; salida esperada: un conteo y hasta 25 líneas `[grupo|veredicto] pregunta`:

```powershell
@'
from app.core.db import get_engine
import sqlalchemy as sa
PAL = ("DISTRIBU","REPART","PARTICIPACION","PORCENTA","CONTRIBU","FRACCION","SHARE",
       "PROPORCION","ENCABEZ","LIDER","PUNTERO")
e = get_engine()
with e.connect() as c:
    rows = c.execute(sa.text(
        "SELECT texto_pregunta, grupo_asignado, veredicto "
        "FROM core.clasificacion_log ORDER BY id DESC LIMIT 3000")).all()
hit = [r for r in rows if any(p in (r[0] or "").upper() for p in PAL)]
print("Registradas:", len(rows), "· con vocab. distribucion:", len(hit))
for r in hit[:25]:
    print("  [%s|%s] %s" % (r[1], r[2], (r[0] or "")[:80]))
'@ | Set-Content -Path chk_uso.py -Encoding utf8
.venv\Scripts\python.exe chk_uso.py
```

Cómo leerlo: **~0 hits** → el plan es preventivo, no correctivo (prioridad discutible frente
a `jerarquias_sup_error.md`); **varios hits** → ese es el baseline con las palabras reales de
los usuarios — cotejarlas contra `_DISTRIBUCION` por si usan formas que no anticipamos.

**Medición POST** (a los ~7-14 días de desplegado): re-correr el mismo script y comparar —
(a) cuántas preguntas con ese vocabulario entraron, (b) cuántas terminaron en `cuantificar`
con panel de ranking, (c) el veredicto ✓/✗ que el usuario les puso en el chat. **El criterio
de éxito no es «pasan los tests»: es que las preguntas reales de distribución terminen en el
panel de distribución y con veredicto ✓.**

### 6.4 Despliegue — pipeline configurado, sin desvíos

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → validar §6.2 →
`migrar-a-azure` (3 tiempos; el default ya publica en `prodiav2`) → en el 139: `git pull` +
**reiniciar INGESTA** (el vocabulario se carga con el módulo). El gate del endpoint
`/consulta2/golden` no se ve afectado (H1); Flask no necesita reinicio (no cambia contrato
ni frontend).

---

## 7. Fuera de alcance

- **La forma telegráfica sin «producción»** (`distribución % crudo por campo`): requiere un
  patrón nuevo en `patrones_grupo.yaml.cuantificar`, que es donde vive el riesgo de
  reclasificación. Merece su propio plan y su propia medición de golden.
- **`PESO`/`PESA`**: decisión del usuario, no un bug.
- **Temporales relativos** («mes pasado»): sin soporte en `slots.py`, responde el mes vigente
  en silencio. Es el hallazgo colateral §4 del documento — más grave que este y con su propia
  naturaleza.
- **Ranking por gerencia/VP**: bloqueado por las brechas de `jerarquias_sup_error.md`. El
  motor ya declina honestamente; ampliarlo aquí sería construir sobre el catálogo roto.
- Cualquier cambio en el cálculo, el SQL, el panel o el frontend.
