# plan_BUG2-NIVEL-EXPLICITO_20260903 — Que «el activo X» responda el ACTIVO X, no el campo homónimo

> Plan **v2** auditado (flujo profesional §10 de `CLAUDE.md`). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación. **Todas las cifras de §1 están medidas
> contra el código y la BD reales.**
>
> **Cambios de v1 → v2** (segunda pasada: se simuló el arreglo completo end-to-end en vez de
> razonarlo):
> 1. 🔴 **`import re` es OBLIGATORIO, no condicional.** Verificado: `resolver.py` importa solo
>    `sqlalchemy`, `get_engine` y `norm`. El plan v1 lo dejaba como «si falta»; es un hecho.
> 2. 🔴 **El cache `_FUENTE_SETS` afecta la PRIMERA colisión del proceso** (H10, nuevo). En
>    frío, `_resolver_colision` para «el activo APIAY» devolvió `reps=[]` (el `_ACTIVO_KEY` aún
>    no estaba poblado); en caliente devuelve `reps=[campo, activo]`. En producción INGESTA
>    lleva minutos vivo → siempre caliente → el arreglo funciona. Pero **los tests deben
>    calentar el cache o ser puros sin BD**, o dan un falso rojo dependiente del orden.
> 3. ✅ **El arreglo se SIMULÓ completo con cache caliente** (H1-bis): «el activo APIAY» →
>    `nivel=activo, zoom=[campo]`; «APIAY» → `nivel=campo, zoom=[activo]`. La lógica de §3.2 es
>    correcta tal como está escrita.
>
> **Es el bug 2 de `jerarquias_sup_error.md`**, el primero del orden acordado 2 → 1 → 3
> (§7-BIS de ese documento). Se ataca primero porque es **el único que ya devuelve cifras
> equivocadas en silencio**, y porque arreglar el bug 1 antes lo empeoraría: más entidades en
> el índice = más nombres colisionando en dos niveles.
>
> **Decisión del usuario (2026-09-03), cerrada:** cuando el usuario escribe «el activo X», se
> responde **el activo** y el texto dice explícitamente que es el activo. **No** se le vuelve a
> preguntar: ya desambiguó al escribirlo.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**solo el backend**.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete Python vive en `backend\backend\app\...`.

**Archivo de producción a modificar (UNO):**
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\app\features\consulta_v2\cuantificar\resolver.py`

**Archivo de tests:**
`C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend\tests\test_cuantificar.py`

### Cómo correr las cosas

Desde `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend`, PowerShell normal, **sin admin**:

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_cuantificar.py -q
```

⚠️ **La BD local está congelada (mayo 2026) y tiene `fact_produccion_mes_ecp.producto` VACÍO**
(el producto se modela por `tipo_producto_id`). Los tests de este plan son **puros, sin BD**.
La verificación en barriles es humana, en Pruebas (§6.2).

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — Reproducido: decir «el activo» no cambia NADA

Medido con `resolver_unico()` contra la BD local:

```
'CASTILLA'                                    -> nivel: campo, valor: CASTILLA, zoom:[activo CASTILLA]
'el activo CASTILLA'                          -> nivel: campo, valor: CASTILLA, zoom:[activo CASTILLA]
'la produccion del activo CASTILLA mes a mes' -> IDÉNTICO
'APIAY'                                       -> nivel: campo, valor: APIAY,    zoom:[activo APIAY]
'el activo APIAY'                             -> IDÉNTICO
```

**Las tres formas dan el mismo dict.** Y el detalle que define la corrección: **el activo
correcto YA está calculado**, dentro de `zoom` — y se descarta.

⇒ No hay que construir nada nuevo: hay que **elegir bien entre dos cosas que ya existen**.
Es el patrón «conectar antes que construir» del `CLAUDE.md` §7.

### 🔴 H2 — Causa raíz, en dos piezas

1. **No existe detector de nivel pedido.** Verificado por grep en TODO `consulta_v2`: **cero
   coincidencias** de `nivel_pedido`, `nivel_explicito`, `nivel_solicitado`. La palabra
   «activo» que el usuario escribió nunca entra en la decisión.
2. **El desempate es ciego al texto**: prioridad fija (`resolver.py:132`,
   `_PRIORIDAD = {"campo": 5, "activo": 3, ...}`) más **D-D5** (`_prioridad_campo`,
   `:147-158`): si hay exactamente un campo y ninguna rama B, gana Campo y los activos bajan
   a `zoom`.

D-D5 es **correcta** para «CASTILLA» a secas. Deja de serlo para «el activo CASTILLA».

### 🔴 H3 — El alcance real es MAYOR que el documentado: APIAY, no CASTILLA

`jerarquias_sup_error.md` solo registró CASTILLA (1 campo omitido). **Medido contra
`core.dim_fuente`, hay 5 nombres duales** (existen como campo *y* como activo):

| Nombre | Campos que agrupa el activo | Campos OMITIDOS al responder como campo |
|---|---:|---|
| **APIAY** | **13** | APIAY ESTE, AUSTRAL, GAVAN, GUATIQUIA, LIBERTAD, LIBERTAD NORTE, PACHAQUIARO, PACHAQUIARO NORTE, POMPEYA, SAURIO, SURIA, SURIA SUR (**12**) |
| CASTILLA | 2 | CASTILLA NORTE (1) |
| CHICHIMENE | 2 | CHICHIMENE SW (1) |
| CUSIANA | 1 | ninguno (campo = activo) |
| RUBIALES | 1 | ninguno (campo = activo) |

⇒ **El caso grave es APIAY: preguntar por el activo devuelve 1 de 13 campos**, y nadie lo
había visto. CUSIANA y RUBIALES son inocuos (el activo tiene un solo campo), lo que explica
por qué el bug pasó desapercibido: los dos nombres más consultados no lo manifiestan.

⚠️ **La cifra en barriles NO se pudo medir en local** (BD congelada + `producto` vacío). Es
material de §6.2, en Pruebas.

### 🟢 H4 — El nivel `activo` YA funciona end-to-end: no hay que tocar la query

- `clave_fisica()` (`:123-124`) ya resuelve `activo` vía `_get_fuente_sets()[_ACTIVO_KEY]`.
- `_NIVEL_TEXTO` (`ejecutor.py:18`) ya tiene **`"activo": "el Activo"`**.
- El `zoom` que hoy se descarta es un dict `{"nivel": "activo", "rama": "A", "valor": "APIAY"}`
  perfectamente formado, del mismo tipo que el que se devuelve.

⇒ **Cero cambios en SQL, en el ejecutor o en el formateador.** Solo en la selección.

### 🟢 H5 — Existe un precedente EXACTO del mecanismo: `_marcar_puente` (R2)

`resolver.py:194-200` resuelve un problema de la misma familia (rotular una «gerencia» que en
robustez es vicepresidencia):

```python
def _marcar_puente(r: dict) -> dict:
    """R2: ... El nivel de QUERY (r['nivel']) NO se toca — solo afecta cómo se ROTULA."""
    if r.get("nivel") == "gerencia" and norm(r["valor"]) in _cargar_vp_robustez():
        r["puente"] = True
    return r
```

⇒ **El plan clona este patrón**, no inventa otro: una señal que se calcula en el resolver y
viaja dentro del dict. La diferencia es que aquí sí cambia el nivel de query (es el punto),
pero el lugar y la forma son los mismos.

### 🔴 H6 — Hay 4 call sites de `resolver_unico`, no 1: la firma NO puede romperse

Medido con grep (excluyendo `__pycache__`):

| Call site | Qué pasa |
|---|---|
| `respuesta_cuantificar.py:245` | el camino principal de Cuantificar |
| `respuesta_cuantificar.py:230` | la guarda (3) del ranking scoped |
| `respuesta_analizar.py:154` | Analizar resuelve su entidad igual |
| `golden/run_golden_cuantificar.py:51` | el golden de estructura |

Los cuatro llaman `resolver_unico(texto)` con **un solo argumento posicional**.

⇒ **La detección del nivel va DENTRO de `resolver_unico`, sobre el texto que ya recibe.** No
se añade parámetro obligatorio, no se cambia la firma, no se toca ningún call site. Los cuatro
se benefician del arreglo sin editarlos — incluido Analizar, que hoy tiene el mismo bug.

### 🟡 H7 — D-D5 es una decisión del usuario del 2026-07-15, vigilada en DOS módulos

| Test | Qué fija |
|---|---|
| `tests/test_cuantificar.py:22-30` | campo+activo → gana campo, activo a `zoom` (**caso APIAY literal**) |
| `tests/test_cuantificar.py:34-40` | con rama B (filial) no decide |
| `tests/test_consulta_desambiguacion.py:46-63` | lo mismo para el módulo v1 (`consulta/maquina.py`) |
| `tests/test_analizar.py:301` | «¿EBITDA de Castilla?» (sin «activo») → `"el Campo CASTILLA"` |

🔑 **Los tres primeros prueban `_prioridad_campo(reps)` con reps directos, SIN texto.** Por eso
**no bloquean este cambio**: la corrección actúa antes, sobre el texto. Pero fijan que **sin
señal explícita el default sigue siendo Campo**, y eso se respeta.

⚠️ `test_analizar.py:301` usa «de Castilla» **sin la palabra «activo»** → sigue dando Campo.
**Ese test debe seguir verde sin tocarlo.** Es el guardián de que no nos pasamos de ancho.

⇒ **Este plan NO modifica `_prioridad_campo` ni `_PRIORIDAD`.** Añade un paso previo.

### 🟡 H8 — El módulo v1 (`consulta/`) tiene el MISMO bug y queda fuera de alcance

`consulta/maquina.py:135` y `consulta/meta.py:148` son el fork v1 del resolver, con su propio
`_prioridad_campo`. Tienen el mismo defecto.

⇒ **No se tocan.** `consulta_v2` es el motor vivo (el chat va por ahí); v1 es el fork
histórico. Tocar ambos duplicaría el riesgo sin beneficio medible hoy. Se anota en §7.

### 🔴 H10 — El cache `_FUENTE_SETS` envenena la PRIMERA colisión del proceso

`clave_fisica()` para un `activo` consulta `_get_fuente_sets()[_ACTIVO_KEY]`, un cache
perezoso por proceso (`_FUENTE_SETS`, construido en la primera llamada). Medido:

```
# PRIMERA llamada del proceso, en frío:
'el activo APIAY' -> _resolver_colision -> reps=[]          ← el activo aún no está poblado
# ya caliente (2ª llamada en adelante):
'el activo APIAY' -> _resolver_colision -> reps=[campo, activo]   ✅
```

⇒ **No es un bug del arreglo, es un artefacto de medición y de test.** En producción INGESTA
lleva minutos vivo cuando llega la primera pregunta: el cache siempre está caliente. Simulado
el arreglo con `_get_fuente_sets()` llamado antes: funciona perfecto (H1-bis del header).

⚠️ **Consecuencia para §3.4:** los tests que ejerciten `resolver_unico`/`_resolver_colision`
end-to-end **deben calentar el cache** (`_resolver._get_fuente_sets()` en un fixture o al
inicio del test) o exigen BD. Por eso los 4 tests del plan son **puros sobre `_nivel_explicito`
y `_prioridad_campo`** (que no tocan el cache) — no sobre `resolver_unico` completo. La prueba
end-to-end de `resolver_unico` es humana, en Pruebas (§6.2), donde el cache está caliente.

### 🟠 H9 — «activo» es palabra común: el detector debe exigir adyacencia

`ACTIVO` aparece en el vocabulario estructural del filtro de dominio y en patrones de
jerarquizar. Un detector laxo (`"ACTIVO" in texto`) capturaría *«¿qué campos tiene el activo
Castilla?»* (que es **jerarquizar**, no cuantificar) o frases donde «activo» es adjetivo
(«el pozo activo»).

⇒ El detector exige **el sustantivo de nivel inmediatamente antes del nombre**, con artículo
opcional: `(?:EL|LA|LOS|LAS)?\s*ACTIVOS?\s+<NOMBRE>`. No basta con que la palabra aparezca en
la frase.

⚠️ Y por seguridad de alcance: la señal **solo se aplica si el nombre detectado existe
realmente en ese nivel**. Si alguien dice «el activo RUBIALES» y RUBIALES no fuera un activo,
no se fuerza nada — se cae al comportamiento actual.

**Medido (v2)** — el detector sobre casos límite:

| Texto | `_nivel_explicito` | ¿Problema? |
|---|---|---|
| `el activo APIAY` | `activo` | ✅ el bug que arreglamos |
| `APIAY` | `None` | ✅ D-D5 decide (default Campo) |
| `el campo CASTILLA` | `campo` | ✅ refuerza el default, no lo cambia |
| `cuantos campos tiene el activo Castilla` | `activo` | ✅ inocuo: esa pregunta va por JERARQUIZAR, no llega a este resolver |
| `los 5 campos que mas crudo producen` | `campo` | ✅ inocuo: es ranking N5 (sin colisión dual, `reps` no tiene un campo que filtrar) |
| `como se distribuye el crudo entre los campos` | `None` | ✅ «campos» al final, sin nombre detrás |

🔑 **La regla `ACTIVO` va PRIMERO en la tupla**: en «cuántos campos tiene el activo X» ganan
ambos, pero el activo es el correcto. Como esa forma no llega a este resolver, es doblemente
seguro. **El regex `CAMPO` nunca cambia el resultado de D-D5** (que ya daba Campo por
default): solo lo hace explícito. Su valor real es documental y de simetría.

---

## 2. Estado actual

`app/features/consulta_v2/cuantificar/resolver.py`:

- `_PRIORIDAD` (`:132`) — `{"campo": 5, "activo": 3, "gerencia": 2, "fuente": 1, "pozo": 1}`.
- `_prioridad_campo(reps)` (`:147-158`) — D-D5.
- `_marcar_puente(r)` (`:194-200`) — el precedente del mecanismo (H5).
- `resolver_unico(texto)` (`:203-230`) — la política completa. Devuelve
  `{nivel, valor, rama, zoom}` o `{"ambiguo": [...]}` o `None`.

Import ya presente en el módulo: `norm` (usado por `_marcar_puente` y `clave_fisica`).

---

## 3. Especificación

### 3.1 AÑADIR el detector de nivel explícito, junto a `_marcar_puente`

**Ubicación:** en `resolver.py`, **inmediatamente ANTES** de `def resolver_unico` (es decir,
después de `_marcar_puente`).

🔴 **Primero, AÑADIR `import re`** (verificado en v2: el módulo NO lo importa — solo tiene
`sqlalchemy`, `get_engine`, `norm` en las líneas 14-16). Ponerlo como primera línea de import,
antes de `import sqlalchemy as sa`:

```python
import re

import sqlalchemy as sa
```

```python
# --- Nivel EXPLÍCITO en el texto (bug 2 de jerarquias_sup_error.md, 2026-09-03) --------------
# El usuario que escribe «el activo CASTILLA» YA desambiguó: pedirle que lo repita sería no
# escucharlo (decisión del usuario, 2026-09-03). Hasta hoy esa palabra no entraba en la
# decisión —grep: cero `nivel_pedido` en todo consulta_v2— y D-D5 respondía el campo homónimo.
# Medido: el activo APIAY agrupa 13 campos y la respuesta entregaba 1.
#
# 🔑 EXIGE ADYACENCIA (nivel + nombre), no la mera presencia de la palabra: 'ACTIVO' es
# vocabulario estructural y adjetivo común. Sin esto se tragaría «¿qué campos tiene el activo
# Castilla?» (que es JERARQUIZAR) y «el pozo activo».
# 🔑 NO altera D-D5 (_prioridad_campo): actúa ANTES y solo cuando hay señal explícita. Sin
# señal, el default sigue siendo Campo — que es la decisión del usuario del 2026-07-15,
# vigilada por tests/test_cuantificar.py:22 y tests/test_consulta_desambiguacion.py:46.
_NIVEL_EXPLICITO_RX = (
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*ACTIVOS?\s+", re.I), "activo"),
    (re.compile(r"\b(?:EL|LA|LOS|LAS)?\s*CAMPOS?\s+", re.I), "campo"),
)


def _nivel_explicito(texto: str):
    """Nivel que el usuario nombró justo antes de la entidad, o None.

    Devuelve 'activo' | 'campo' | None. Solo mira el TEXTO; que ese nivel exista de verdad
    para la entidad lo comprueba quien llama (no se fuerza un nivel inexistente).
    """
    t = norm(texto or "")
    for rx, nivel in _NIVEL_EXPLICITO_RX:
        if rx.search(t):
            return nivel
    return None
```

### 3.2 MODIFICAR `resolver_unico` para honrar el nivel explícito

**No se toca la firma.** Se insertan dos bloques dentro de la función existente.

**(a)** Justo después de `ids = resolver(texto)` … del bloque que ya resuelve `ids` (es decir,
**después** de la guarda `if not ids: return None`), calcular la señal una sola vez:

```python
    nivel_pedido = _nivel_explicito(texto)
```

**(b)** Sustituir el bloque de colisión existente:

```python
    modo, rep, reps = _resolver_colision(ids, clave_fisica)
    zoom = []
    if modo == "ask":
        rep_campo, zoom = _prioridad_campo(reps)
        if rep_campo is not None:
            modo, rep = "auto", rep_campo
```

por este otro, que añade el desempate explícito **antes** de D-D5:

```python
    modo, rep, reps = _resolver_colision(ids, clave_fisica)
    zoom = []
    if modo == "ask":
        # (1) NIVEL EXPLÍCITO gana sobre D-D5: el usuario ya dijo cuál quiere. Solo si ese
        #     nivel existe de verdad entre los candidatos (H9) — nunca se fuerza uno ausente.
        elegido = ([r for r in reps if r["nivel"] == nivel_pedido] if nivel_pedido else [])
        if len(elegido) == 1:
            modo, rep = "auto", elegido[0]
            zoom = [r for r in reps if r is not elegido[0]]
        else:
            # (2) sin señal explícita -> D-D5 intacta (default Campo, decisión 2026-07-15)
            rep_campo, zoom = _prioridad_campo(reps)
            if rep_campo is not None:
                modo, rep = "auto", rep_campo
```

⚠️ **`len(elegido) == 1` es deliberado**: si hubiera dos candidatos del mismo nivel pedido, la
señal no desempata y se cae a D-D5 (y de ahí a `ambiguo` si D-D5 tampoco decide). Nunca se
elige uno al azar.

### 3.3 Lo que NO hay que hacer y por qué (verificado)

| Tentación | Por qué NO |
|---|---|
| Subir `activo` en `_PRIORIDAD` | Rompería el default Campo sin señal — decisión del usuario 2026-07-15 (H7) |
| Modificar `_prioridad_campo` | Sus 3 tests la prueban sin texto; la corrección va antes (H7) |
| Añadir un parámetro a `resolver_unico` | 4 call sites la llaman con 1 argumento (H6) |
| Tocar la query / el ejecutor | El nivel `activo` ya funciona end-to-end (H4) |
| Tocar `consulta/` (v1) | Fork histórico, mismo bug, fuera de alcance (H8) |

### 3.4 AÑADIR tests en `tests/test_cuantificar.py`

Sección nueva **al final del archivo**. `_resolver` YA está importado (verificado v2,
`test_cuantificar.py:14`) — **no duplicar el import**. `test_cuantificar.py` **no tiene helper
de skip-sin-catálogo genérico** (verificado v2), por eso los 4 tests son **puros**: ejercitan
`_nivel_explicito` (solo texto) y `_prioridad_campo` (reps directos). **Ninguno llama
`resolver_unico` completo**, que necesitaría cache caliente o BD (H10). La prueba end-to-end de
`resolver_unico` es humana, en Pruebas (§6.2).

```python
# --- Nivel EXPLÍCITO (bug 2 de jerarquias_sup_error.md, 2026-09-03) ------------------------

def test_nivel_explicito_detecta_activo_y_campo():
    """Puro: solo lee el texto. Exige adyacencia nivel+nombre (H9 del plan)."""
    assert _resolver._nivel_explicito("el activo CASTILLA") == "activo"
    assert _resolver._nivel_explicito("la produccion del activo APIAY mes a mes") == "activo"
    assert _resolver._nivel_explicito("el campo CASTILLA") == "campo"


def test_nivel_explicito_none_sin_senal():
    """Sin sustantivo de nivel pegado al nombre, no hay señal -> D-D5 decide como siempre."""
    assert _resolver._nivel_explicito("CASTILLA") is None
    assert _resolver._nivel_explicito("cuanto crudo produjo Rubiales") is None


def test_activo_explicito_gana_a_dd5():
    """🔑 EL BUG: con «activo» explícito, el activo gana y el campo baja a zoom.
    Es el inverso exacto de test_prioridad_campo_campo_mas_activo_da_zoom (mismo caso APIAY)."""
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "APIAY"},
        {"nivel": "activo", "rama": "A", "valor": "APIAY"},
    ]
    elegido = [r for r in reps if r["nivel"] == _resolver._nivel_explicito("el activo APIAY")]
    assert len(elegido) == 1 and elegido[0]["nivel"] == "activo"


def test_dd5_sigue_intacta_sin_senal():
    """🔒 REGRESIÓN: sin señal explícita, D-D5 manda (decisión del usuario 2026-07-15).
    Este test es el guardián de que la corrección no se pasó de ancho."""
    reps = [
        {"nivel": "campo", "rama": "A", "valor": "APIAY"},
        {"nivel": "activo", "rama": "A", "valor": "APIAY"},
    ]
    rep_campo, zoom = _resolver._prioridad_campo(reps)
    assert rep_campo is not None and rep_campo["nivel"] == "campo"
    assert len(zoom) == 1 and zoom[0]["nivel"] == "activo"
```

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/ -q` | anotar el conteo (esperado: **644 pasan, 10 fallan**) | DETENTE: árbol sucio |
| 0-bis | Golden **ANTES** (§6.1) | anotar `pct`/`aciertos` (esperado 92 / 85 en local) | DETENTE |
| 1 | §3.1 — `import re` (OBLIGATORIO, H1) + detector `_nivel_explicito` | `py_compile` OK | revisar sintaxis |
| 2 | §3.2 — los dos bloques en `resolver_unico` | `pytest tests/test_cuantificar.py -q` **sin fallos nuevos** | comparar contra baseline |
| 3 | §3.4 — los tests nuevos | los 4 pasan | ajustar al `_resolver` real |
| 4 | Suite completa: `pytest tests/ -q` | **exactamente 10 fallos**, ninguno nuevo | ⚠️ ver nota |
| 5 | Golden **DESPUÉS** | **sin cambio** respecto al 0-bis | si baja: revertir y reportar |

⚠️ **Cómo leer un fallo nº 11.** Los candidatos son `test_analizar.py:301` («EBITDA de
Castilla» debe seguir dando `"el Campo CASTILLA"`) y los 3 de D-D5. Si alguno cae, **el
detector se pasó de ancho** (probablemente capturando «activo» sin adyacencia): se estrecha el
regex, **nunca se toca el test** — fijan decisiones del usuario de julio.

---

## 5. Reglas no negociables

1. **NO cambiar la firma de `resolver_unico`** — 4 call sites (H6).
2. **NO modificar `_prioridad_campo` ni `_PRIORIDAD`** — decisión del usuario 2026-07-15 (H7).
3. **NO tocar ningún test existente.** Si uno se pone rojo, el que está mal es el detector.
4. **NO tocar `consulta/` (v1)** — fuera de alcance (H8).
5. **NO tocar la query, el ejecutor ni el formateador** — el nivel `activo` ya funciona (H4).
6. **NO forzar un nivel que no exista** entre los candidatos (H9): sin match exacto, D-D5.
7. El detector **exige adyacencia** nivel+nombre, no la presencia de la palabra (H9).
8. Todo lo nuevo lleva **comentario explicando qué NO debe capturar**, como el resto del módulo.

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\cuantificar\resolver.py
.venv\Scripts\python.exe -m pytest tests/test_cuantificar.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -c "from app.features.consulta_v2.golden.run_golden import ejecutar; r=ejecutar(); print('pct:', r['pct'], '· aciertos:', r['aciertos'])"
```

⚠️ Claves reales del golden: **`pct` y `aciertos`** (verificado en `run_golden.py:46-53`).

Comprobación directa del arreglo (puro, sin BD):

```powershell
.venv\Scripts\python.exe -c "import app.features.consulta_v2.cuantificar.resolver as R; print(R.resolver_unico('el activo APIAY')); print(R.resolver_unico('APIAY'))"
```

Esperado: el primero con `'nivel': 'activo'`; el segundo con `'nivel': 'campo'` (sin cambio).

### 6.2 Humana (usuario) — en PRUEBAS

Tras `git pull` + **reiniciar INGESTA**:

| Pregunta | Esperado |
|---|---|
| «Producción de crudo del **activo APIAY**, mes a mes 2026» | Dice **«el Activo APIAY»** y la cifra **suma los 13 campos** — debe ser notablemente mayor que la de hoy |
| «Producción de crudo de **APIAY**» (sin «activo») | Sigue diciendo **«el Campo APIAY»** ← regresión clave |
| «Producción del **activo CASTILLA**» | «el Activo CASTILLA», incluye **CASTILLA NORTE** |
| «Producción del **campo CASTILLA**» | «el Campo CASTILLA», **sin** CASTILLA NORTE |
| «¿Qué campos tiene el activo Castilla?» | Sigue en **JERARQUIZAR** (panel de estructura) ← H9 |
| «¿Cuál es el EBITDA de Castilla?» | Sigue diciendo **«el Campo CASTILLA»** |

🔑 **La verificación que zanja el bug**: comparar la cifra del **activo APIAY** contra la del
**campo APIAY**. Si son iguales, el arreglo no está aplicado (o INGESTA no se reinició).

**El único que marca ✅ es el usuario.**

### 6.3 Medición de valor

El bug es **silencioso**: nadie lo reportó nunca (§«Por qué nadie lo reportó» del hallazgo).
Por eso `core.clasificacion_log` **no sirve** aquí como baseline — no hay veredictos ✗ que
contar, porque las respuestas parecían correctas.

La medición válida es directa: **para los 3 nombres duales con más de un campo (APIAY,
CASTILLA, CHICHIMENE), la cifra del activo debe ser > la del campo**. Hoy son idénticas. Eso
es binario y se comprueba en 3 preguntas.

### 6.4 Despliegue

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → **reiniciar INGESTA** →
validar §6.2 → `migrar-a-azure` en 3 tiempos (el default publica en `prodiav2`) → en el 139:
`git pull` + reiniciar INGESTA. Flask no necesita reinicio.

---

## 7. Fuera de alcance

- **El módulo v1 `consulta/`** (`maquina.py:135`, `meta.py:148`): mismo bug, fork histórico.
  Candidato a su propio plan si alguna vez vuelve a usarse (H8).
- **Bug 1 de `jerarquias_sup_error.md`** (20 de 24 gerencias no resuelven): es el siguiente del
  orden acordado, y se apoya en que este esté cerrado.
- **Bug 3** (universo de campos divergente por VP): el último del orden.
- **Gerencia y VP explícitas** («la gerencia PPC»): hoy declinan honestamente por
  `_NIVEL_DIFERIDO`; ampliarlas depende del bug 1.
- **La desambiguación interactiva** (rama `{"ambiguo": [...]}`): sigue como está.
- Cualquier cambio en la query, el panel o el frontend.
