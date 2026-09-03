# plan_PANEL-ACTIVO-SINGULAR_20260903 — Que el singular no colapse el panel: campos del activo completos, y ranking de activos con reparto

> Plan **v2** auditado (flujo profesional §10 de `CLAUDE.md`). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación. **Los dos cambios están verificados contra
> el código real** (§1 H3 y H4).
>
> **Cambios de v1 → v2** (segunda pasada):
> 1. 🔴 **El `max` del v1 pisaba el número explícito del usuario.** Medido: «top 2 campos del
>    activo APIAY» → `max(2, 4) = 4`, ignorando el 2 que el usuario escribió. El v1 lo advertía
>    y luego lo aceptaba con una nota contradictoria — justo el anti-patrón que §10.5 del
>    CLAUDE.md prohíbe. **Corregido de raíz** (H9): `detectar()` marca si el `top_n` fue
>    explícito y el scope solo amplía cuando NO lo fue.
> 2. ✅ **La clave nueva es segura, verificado:** `detectar()` tiene UN solo consumidor
>    (`respuesta_cuantificar.py:228`), `calcular()` acepta claves extra sin romper, y ningún
>    test compara el dict completo (todos acceden por clave).
>
> **Origen (medido en Pruebas, 2026-09-03):** con el panel scoped y el fix de contenedor ya
> publicados, dos preguntas siguen devolviendo una cifra única en vez del panel:
> - «¿Qué **campo** del activo Castilla produce más crudo?» → `CASTILLA 6.738.232` (1 campo).
> - «¿Cuál es el **activo** que más crudo produce?» → `RUBIALES 12.176.071` (1 activo).
>
> **Decisión del usuario (2026-09-03), cerrada:**
> - Cuando la pregunta nombra un **activo-contenedor**, el panel muestra **TODOS los campos del
>   activo**, aunque el verbo sea singular («qué campo del activo X» → todos los campos de X).
> - Cuando se rankean **activos** y no hay número explícito, se muestra el **Top (5)**, no uno
>   (regla C: un activo es un agregado; ver el reparto entre activos aporta más que un nombre).
> - «¿Cuál es el **campo** que más produce?» (campo suelto, sin contenedor) **NO cambia**: sigue
>   devolviendo un nombre. Es una pregunta cotidiana que hoy funciona.

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**dos archivos de producción**, un bloque pequeño en cada uno.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete Python vive en `backend\backend\app\...`.

**Archivos de producción:**
- `...\backend\backend\app\features\consulta_v2\cuantificar\ranking.py` — regla C (pregunta 3).
- `...\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py` — scope completo (pregunta 2).

**Archivo de tests:** `...\backend\backend\tests\test_cuantificar_ranking.py`

### Cómo correr los tests

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
```

⚠️ **La BD local está congelada** (mayo 2026, sin datos de crudo densos): varios tests que
calculan sobre la BD harán `skip`. Eso es correcto. La verificación de cifras es humana, en
Pruebas (§6.2). Los tests de `detectar()` son puros y sí corren en local.

⚠️ **Estado del árbol:** puede haber cambios sin commitear de otro plano (`slots.py`,
`test_slots_ventana.py`). **NO los toques ni los incluyas en tu commit**: este plan solo toca
`ranking.py`, `respuesta_cuantificar.py` y `test_cuantificar_ranking.py`. Si al final el árbol
tiene más archivos modificados que esos tres, **repórtalo y NO hagas `git add -A`**: añade solo
tus tres archivos por nombre.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🔴 H1 — Dos problemas DISTINTOS, misma superficie (una cifra en vez de panel)

Medido con `detectar()`:

| Pregunta | `nivel_ranking` | `top_n` hoy | Tiene contenedor | Problema |
|---|---|---:|---|---|
| «qué **campo** del activo Castilla produce más» | campo | **1** | SÍ (`activo CASTILLA`) | el scope pasa top_n=1 → 1 campo |
| «cuál es el **activo** que más produce» | activo | **1** | NO | ranking global de activos con top_n=1 |

⇒ **Son dos arreglos en dos archivos**, no uno. El primero está en la guarda del scope
(`respuesta_cuantificar.py`); el segundo en la heurística de `top_n` (`ranking.py`).

### 🟢 H2 — La pregunta 2 SÍ entra en la guarda del scope (verificado)

`respuesta_cuantificar.py:245` resuelve la entidad con contexto. Medido:

```
"que campo del activo Castilla produce mas crudo" -> ent_det=CASTILLA, nivel=activo
```

⇒ Entra en la rama `if _res_ent.get("nivel") == "activo" and rk.get("nivel_ranking") == "campo"`
(`:251`). Ahí ya se calcula `_scope = campos_de_activo(...)`. **El único defecto es que pasa
`rk` con `top_n=1` sin ajustarlo al tamaño del scope.** El arreglo es de una línea.

### 🟢 H3 — Arreglo de la pregunta 2, VERIFICADO: `top_n = len(scope)`

Medido: `campos_de_activo("CASTILLA")` = 3 campos, `campos_de_activo("APIAY")` = 4. Forzar
`rk["top_n"] = len(_scope)` hace que el panel muestre TODOS los campos del activo, no solo el
máximo. El resto del contrato (dona, participación, «Otros») se recalcula solo sobre el
universo del scope (ya verificado en `plan_PANEL-SCOPED-ACTIVO`, H2: `_panel_rank` es
passthrough).

⚠️ **NO se usa `max`** (corregido en v2, ver H9): `max(2, 4) = 4` pisaría el «top 2» que el
usuario escribió. La ampliación al activo completo solo ocurre cuando el `top_n` NO fue pedido
a mano.

### 🔴 H9 — El `top_n` explícito debe distinguirse del gramatical (corrige el v1)

Medido: «top 2 campos del activo APIAY» → `detectar()` da `top_n=2` (por `if m:`), y
`campos_de_activo("APIAY")` da 4 campos. Con el `max` del v1 saldrían **4**, ignorando el 2.

⇒ Hace falta saber **de dónde vino el `top_n`**. Dos vías evaluadas:

| Vía | Veredicto |
|---|---|
| Repetir el `re.search` en `respuesta_cuantificar.py` | ❌ duplica el patrón en dos archivos; se desincronizan |
| **`detectar()` marca la procedencia en el dict** | ✅ una sola fuente de verdad |

**Verificado que la clave nueva es segura:**
- `ranking.detectar()` tiene **UN solo consumidor**: `respuesta_cuantificar.py:228` (grep).
- `calcular()` lee `slots` por clave — una clave extra no lo rompe (probado).
- **Ningún test compara el dict completo** de `detectar()` (todos acceden por clave), así que
  añadirla no pone rojo nada.
- El `rk` de `respuesta_jerarquizar.py` es **otro dict** (de jerarquizar), sin relación.

### 🟢 H4 — Arreglo de la pregunta 3 (regla C), VERIFICADO en 6 casos

En `ranking.py`, la heurística `:176-180` da `top_n=1` al singular. La regla C: **cuando lo que
se rankea son ACTIVOS y no hay número explícito, el mínimo es 5**. Medido:

```
  ok top_n=5 | cual es el activo que mas crudo produce      <- P3, ahora 5
  ok top_n=5 | los activos con mayor produccion             <- ya daba 5
  ok top_n=5 | el activo con mas produccion                 <- singular de activo, ahora 5
  ok top_n=1 | cual es el campo que mas crudo produce        <- CAMPO suelto: SIGUE 1 (no toca)
  ok top_n=1 | que campo produce mas gas                     <- campo: 1
  ok top_n=3 | top 3 activos por produccion                  <- número explícito manda
```

🔑 El caso que NO debe cambiar es «cuál es el **campo** que más produce» → sigue en 1. La regla
C solo mira `nivel == "activo"`, así que el campo suelto no se ve afectado. **Verificado.**

### 🟡 H5 — El «número explícito» ya está calculado arriba; hay que consultarlo, no recalcularlo

`ranking.py:156-158`: `m = re.search(...TOP \d+...) or re.search(...\d+ CAMPOS?/ACTIVOS?...)`.
Si `m` casó, `top_n` sale de ahí en `:157-158` y **nunca llega al `else` de `:166`**. Por eso
la regla C va DENTRO del `else` (donde `m is None` por construcción) y no necesita volver a
mirar si hay número: si estamos en el `else`, no lo hay. **No dupliques el `re.search`.**

### 🟢 H6 — El singular de activo hoy da 1 SOLO por la rama `nivel == "activo"` (H4 de un plan previo)

`ranking.py:176-177` — esa rama existe desde el fix de contenedor (2026-09-03) y su único
propósito era distinguir el activo-contenedor del activo-rankeado. La regla C se injerta ahí
mismo: es el lugar natural, no una excepción nueva encadenada.

### 🟠 H7 — El ranking de activos usa `map_campo_activo`, no `wells_attributes` (límite conocido)

El SQL `_SQL["activo"]` (`ranking.py`) hace `JOIN core.map_campo_activo`. Ese catálogo diverge
de `wells_attributes` (es el bug 3, medido: ~38% sin mapear). El panel de activos **funciona y
es útil** para ver quién manda, pero su total podría no cuadrar al 100% con la suma fina de
campos hasta que se unifique la jerarquía. **No se corrige aquí** — es el bug 3, su propio
trabajo. Se documenta para que nadie lea el panel de activos como reconciliación exacta.

### 🟡 H8 — El panel de 1 elemento NO se toca; el arreglo es que deje de haber 1 elemento

Hoy un ranking de 1 item se pinta como cifra (correcto: una participación «100% de 1» no dice
nada). Este plan **no cambia cómo se pinta 1 item** — cambia que estas dos preguntas dejen de
producir 1 item. Es la raíz, no el síntoma.

---

## 2. Estado actual

**`ranking.py`**, función `detectar()`:
- `:156-158` — número explícito (`if m:`), gana sobre todo.
- `:159-165` — `elif es_distribucion: top_n = 5` (fix distribución, 2026-09-03).
- `:166-180` — el `else`: rama `nivel == "activo"` / `else` (campo), y `top_n = 1 if singular else 5`.

**`respuesta_cuantificar.py`**, guarda (3) del scope (`:249-262`):
- `:251` — `if _res_ent.get("nivel") == "activo" and rk.get("nivel_ranking") == "campo":`
- `:252` — `_scope = _ranking.campos_de_activo(_res_ent["valor"])`
- `:254-256` — arma `rk` con `scope_label` y llama `calcular(rk, campos_scope=_scope)`.

Tests: `test_cuantificar_ranking.py`, 46 pasan / 3 fallan (BD) / 1 skip.

---

## 3. Especificación

### 3.1 MODIFICAR `ranking.py` — regla C (pregunta 3)

Localiza el bloque `else` **exacto** (`:176-180`):

```python
        if nivel == "activo":
            singular = "ACTIVO" in toks and "ACTIVOS" not in toks
        else:
            singular = "CAMPO" in toks and "CAMPOS" not in toks
        top_n = 1 if singular else 5
```

Reemplázalo por:

```python
        if nivel == "activo":
            # [2026-09-03 · regla C] Un ACTIVO es un agregado (agrupa campos): «¿cuál es el
            # activo que más produce?» pide ver el REPARTO entre los grandes, no un nombre
            # suelto. Medido en Pruebas: devolvía «RUBIALES 12.176.071» como cifra única. Sin
            # número explícito (ese caso ya salió por `if m:` arriba, :157), el ranking de
            # activos muestra el Top 5. El singular gramatical («cuál ES EL activo») no lo
            # colapsa a 1 — a diferencia del CAMPO suelto, que sí quiere un nombre.
            top_n = 5
        else:
            # CAMPO suelto sin contenedor: «¿cuál es el campo que más produce?» SÍ quiere un
            # nombre. El singular real manda. (El contenedor «del activo X» no llega hasta aquí
            # como singular: lo resuelve la guarda del scope en respuesta_cuantificar.py.)
            singular = "CAMPO" in toks and "CAMPOS" not in toks
            top_n = 1 if singular else 5
```

⚠️ **NO toques el `if m:` (:157) ni el `elif es_distribucion:` (:159).** La regla C vive solo
en la rama `nivel == "activo"` del `else`, que por construcción ya no tiene número explícito
(H5).

### 3.1-bis MODIFICAR `ranking.py` — marcar la procedencia del `top_n` (H9)

El `return` de `detectar()` (`:184-185`) hoy es:

```python
    return {"nivel_ranking": nivel, "metrica": metrica, "direccion": direccion,
            "top_n": top_n, "producto": producto, "periodo_texto": per}
```

Reemplázalo por:

```python
    return {"nivel_ranking": nivel, "metrica": metrica, "direccion": direccion,
            "top_n": top_n, "producto": producto, "periodo_texto": per,
            # [2026-09-03 · H9] ¿El top_n lo escribió el usuario («top 3 campos») o salió de la
            # heurística gramatical? La guarda del scope necesita distinguirlo: solo puede
            # ampliar el top_n al activo completo cuando NO fue pedido a mano. `m` es el match
            # del número explícito de :156; si casó, el top_n vino de ahí.
            "top_n_explicito": m is not None}
```

⚠️ `m` está en scope en ese punto (se asigna en `:156` y no se reasigna). **Verificado.**
La clave es aditiva: `calcular()` la ignora y ningún test compara el dict completo (H9).

### 3.2 MODIFICAR `respuesta_cuantificar.py` — scope completo (pregunta 2)

Localiza estas líneas **exactas** en la guarda (3) (`:252-256`):

```python
                _scope = _ranking.campos_de_activo(_res_ent["valor"])
                if _scope:
                    rk = dict(rk)
                    rk["scope_label"] = f"el Activo {_res_ent['valor']}"
                    res = _ranking.calcular(rk, campos_scope=_scope)
```

Reemplázalas por:

```python
                _scope = _ranking.campos_de_activo(_res_ent["valor"])
                if _scope:
                    rk = dict(rk)
                    rk["scope_label"] = f"el Activo {_res_ent['valor']}"
                    # [2026-09-03] Cuando el usuario nombra un activo-CONTENEDOR, el panel
                    # muestra TODOS sus campos aunque el verbo sea singular («qué campo del
                    # activo Castilla produce más» → los 3 campos de Castilla, no solo el
                    # máximo). Decisión del usuario 2026-09-03.
                    # 🔑 Solo si el top_n NO lo escribió el usuario (H9): «top 2 campos del
                    # activo APIAY» debe respetar el 2, no inflarse a los 4 del activo. Un
                    # `max()` ciego pisaría ese número — por eso detectar() marca la
                    # procedencia en `top_n_explicito`.
                    if not rk.get("top_n_explicito"):
                        rk["top_n"] = len(_scope)
                    res = _ranking.calcular(rk, campos_scope=_scope)
```

⚠️ **Asignación directa, NO `max`** — y solo bajo la guarda `if not top_n_explicito`. Los dos
casos quedan bien:

| Pregunta | `top_n` de `detectar()` | explícito | `top_n` final |
|---|---:|---|---:|
| «qué campo del activo Castilla produce más» | 1 | No | **3** (todos los campos) |
| «cuáles campos del activo APIAY producen más» | 5 | No | **4** (todos los campos) |
| «top 2 campos del activo APIAY» | 2 | **Sí** | **2** (se respeta) |

### 3.3 AÑADIR tests en `tests/test_cuantificar_ranking.py`

Sección al final. Los de `detectar()` son puros; los de panel scoped se saltan sin BD.

```python
# --- V-DETECT · regla C: ranking de activos no colapsa a 1 (2026-09-03) --------------------

def test_ranking_activos_singular_da_top5():
    """🔴 P3 (medido en Pruebas): «¿cuál es el activo que más produce?» daba top_n=1 y el chat
    respondía «RUBIALES 12.176.071» como cifra única. Un activo es un agregado: se muestra el
    Top 5 para ver el reparto. Regla C, decisión del usuario 2026-09-03."""
    r = RK.detectar("cual es el activo que mas crudo produce")
    assert r is not None and r["nivel_ranking"] == "activo" and r["top_n"] == 5


def test_ranking_activos_singular_variantes():
    a = RK.detectar("el activo con mas produccion")
    assert a is not None and a["nivel_ranking"] == "activo" and a["top_n"] == 5


def test_campo_suelto_singular_sigue_dando_1():
    """🔒 REGRESIÓN CENTRAL: «¿cuál es el campo que más produce?» NO cambia — sigue devolviendo
    un nombre. La regla C solo toca el nivel activo. Si esto se pone rojo, el plan se pasó de
    ancho a las preguntas de campo, que son cotidianas y funcionan."""
    r = RK.detectar("cual es el campo que mas crudo produce")
    assert r is not None and r["nivel_ranking"] == "campo" and r["top_n"] == 1


def test_campo_del_activo_singular_sigue_en_1_en_detectar():
    """🔑 «qué campo del activo Castilla produce más» sigue dando top_n=1 en detectar() —el
    scope lo AMPLÍA después, en respuesta_cuantificar. detectar() no cambia para este caso."""
    r = RK.detectar("que campo del activo Castilla produce mas crudo")
    assert r is not None and r["nivel_ranking"] == "campo" and r["top_n"] == 1


def test_numero_explicito_de_activos_manda():
    """🔒 «top 3 activos» respeta el 3, la regla C no lo pisa (sale por `if m:`, no por el else)."""
    r = RK.detectar("top 3 activos por produccion de crudo")
    assert r is not None and r["top_n"] == 3


def test_top_n_explicito_se_marca_en_el_contrato():
    """🔑 H9: la guarda del scope necesita saber si el top_n lo escribió el usuario, para no
    ampliarlo al activo completo cuando sí lo hizo. «top 2 campos del activo APIAY» debe
    respetar el 2."""
    con = RK.detectar("top 2 campos del activo APIAY")
    sin = RK.detectar("que campo del activo Castilla produce mas crudo")
    assert con is not None and con["top_n_explicito"] is True and con["top_n"] == 2
    assert sin is not None and sin["top_n_explicito"] is False


def test_top_n_explicito_tambien_por_la_forma_N_campos():
    """El regex de :156 tiene dos alternativas: «top N» y «N campos/activos». Ambas marcan."""
    r = RK.detectar("los 3 campos que mas crudo producen")
    assert r is not None and r["top_n_explicito"] is True and r["top_n"] == 3
```

⚠️ El efecto de §3.2 (scope amplía top_n a `len(scope)`) **requiere BD** para verse en cifras
—`campos_de_activo` sí corre en local, pero el panel necesita el fact—. Su prueba real es
humana (§6.2). No se añade un test de integración que dependa del fact congelado.

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/test_cuantificar_ranking.py -q` | anotar (esperado **46 pasan, 3 fallan, 1 skip**) | DETENTE |
| 0-bis | Golden **ANTES** (§6.1) | anotar `pct`/`aciertos` (92 / 85 en local) | DETENTE |
| 1 | §3.1 — regla C en `ranking.py` | `py_compile` OK | revisar |
| 1-bis | §3.1-bis — `top_n_explicito` en el `return` de `detectar()` | `py_compile` OK | `m` debe estar en scope (:156) |
| 2 | §3.2 — scope completo en `respuesta_cuantificar.py` | `py_compile` OK | revisar |
| 3 | §3.3 — los 7 tests nuevos | los 7 pasan | ajustar al `detectar()` real |
| 4 | Suite completa: `pytest tests/ -q` | **mismos 10 fallos**, ninguno nuevo | comparar con paso 0 |
| 5 | Golden **DESPUÉS** | **sin cambio** respecto al 0-bis | si baja: revertir |

⚠️ **Cómo leer un fallo nuevo.** El candidato es `test_singular_top1` (`:24`, «qué campo
produce la mayor cantidad» → 1) o cualquiera que fije el `top_n` de campo. Si cae, **la regla C
se filtró al campo**: revisa que solo esté en la rama `nivel == "activo"`. **NUNCA toques el
test.**

---

## 5. Reglas no negociables

1. **La regla C solo toca `nivel == "activo"`.** El campo suelto («cuál es el campo que más»)
   NO cambia (H4, test de regresión central).
2. **NO tocar `if m:` (:157) ni `elif es_distribucion:` (:159)** en `ranking.py`.
3. **El scope amplía el `top_n` SOLO si `not rk.get("top_n_explicito")`** (H9). Nada de `max`
   ciego: pisaría el número que el usuario escribió.
4. **NO tocar el cálculo, el SQL, la dona ni el formateador**: el contrato se recalcula solo
   sobre el universo del scope/top (H8).
5. **NO tocar `campos_de_activo` ni los filtros de `wells_attributes`.**
6. **NO tocar ningún test existente.** Si uno cae, el que está mal es el código.
7. **NO incluir en el commit archivos ajenos a este plan** (`slots.py`, `test_slots_ventana.py`
   pueden estar sin commitear de otro trabajo): `git add` solo tus 3 archivos por nombre (§0).

---

## 6. Validación

### 6.1 Estática (executor)

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m py_compile app\features\consulta_v2\cuantificar\ranking.py app\features\consulta_v2\respuesta_cuantificar.py
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -c "from app.features.consulta_v2.golden.run_golden import ejecutar; r=ejecutar(); print('pct:', r['pct'], '· aciertos:', r['aciertos'])"
```

Comprobación directa (pura, sin BD) — **la que zanja la regla C**:

```powershell
.venv\Scripts\python.exe -c "import app.features.consulta_v2.cuantificar.ranking as RK; [print(RK.detectar(q)['top_n'], '|', q) for q in ['cual es el activo que mas crudo produce','cual es el campo que mas crudo produce','que campo del activo Castilla produce mas crudo']]"
```

Esperado, en orden: **`5`** (activo → top 5), **`1`** (campo suelto → 1), **`1`** (campo con
contenedor → 1 en detectar; el scope lo amplía después).

### 6.2 Humana (usuario) — en PRUEBAS

Tras `git pull` + **reiniciar INGESTA**:

| # | Pregunta | Esperado |
|---|---|---|
| 1 | **¿Qué campo del activo Castilla produce más crudo?** | **Panel con los 3 campos** de Castilla (era 1 cifra) |
| 2 | **¿Cuál es el activo que más crudo produce?** | **Panel/ranking de activos** (Top 5) — era «RUBIALES» solo |
| 3 | ¿Cuál es el campo que más crudo produce? | **Una sola entidad** ← regresión clave: NO debe volverse panel |
| 4 | ¿Cuáles campos del activo APIAY producen más crudo? | Sigue mostrando el panel de APIAY (no se rompe) |
| 5 | ¿Cuáles son los 5 campos que más crudo producen? | Ranking global de 5, como siempre |

🔑 **Las dos que zanjan el plan son la 1 y la 2 (deben pasar a panel) contra la 3 (debe seguir
siendo una cifra).** Si la 3 se vuelve panel, la regla C se filtró al campo.

**El único que marca ✅ es el usuario.**

### 6.3 Medición de valor

Binaria y visible: las preguntas 1 y 2 pasan de cifra única a panel. No necesita
`clasificacion_log`.

### 6.4 Despliegue

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → **reiniciar INGESTA** →
validar §6.2 → `migrar-a-azure` (3 tiempos, default `prodiav2`) → en el 139: `git pull` +
reiniciar INGESTA.

---

## 7. Fuera de alcance

- ~~«top N campos del activo X» con N menor que el activo~~ — **resuelto en v2** (H9): el
  número explícito se respeta gracias a `top_n_explicito`. Ya no es un límite.
- **La divergencia del ranking de activos** (`map_campo_activo` vs `wells_attributes`, ~38%
  sin mapear): es el bug 3, su propio trabajo (H7). El panel de activos es útil pero no es la
  reconciliación fina.
- **«cuál es el campo que más produce»**: decisión del usuario de dejarlo como cifra. No es bug.
- **Cómo se pinta un panel de 1 elemento**: no se toca (H8).
- Cualquier cambio en el frontend, el cálculo, el SQL o el golden de clasificación.
