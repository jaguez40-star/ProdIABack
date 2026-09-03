# plan_PANEL-SCOPED-ACTIVO_20260903 — El panel de distribución, acotado a los campos del activo preguntado

> Plan **v2** auditado (flujo profesional §10 de `CLAUDE.md`). Mapeo + auditoría + diagnóstico
> ejecutados ANTES de escribir esta especificación. **Todas las cifras de §1 están medidas
> contra las dos BD reales**, y el panel + la cadena completa se simularon con datos reales.
>
> **Cambios de v1 → v2** (segunda pasada: se recorrió la cadena entera end-to-end, no solo el
> panel en aislamiento):
> 1. ✅ **El cruce de nombres wells↔fact FUNCIONA, verificado** — pero con matiz: el filtro
>    debe comparar contra `COALESCE(campo, nombre)`, no solo `campo`. `CASTILLA ESTE` vive en
>    `dim_fuente.nombre`, no en `.campo`. `datos` ya usa ese COALESCE, así que el filtro del
>    plan (`d[0].upper()`) opera sobre el valor correcto. Confirmado: los 3 campos de CASTILLA
>    cruzan 3/3 (H11).
> 2. 🟠 **17 de 118 campos de wells NO cruzan con el fact** (ABARCO BUFFER, exploratorios,
>    LISAMA PROFUNDO…): son buffers/exploratorios sin producción. No rompen el panel de un
>    activo con producción real, pero se documenta como límite conocido (H12).
> 3. ✅ **La cadena entera resuelve a `nivel=activo`, verificado end-to-end**: detectar_entidad
>    → `_resolver_con_contexto` → `nivel=activo` para las 3 formas de pregunta scoped (H13).
>    Sin esto el scope nunca se activaría — era el riesgo mayor y está descartado.
> 4. 🟢 **`total_universo` es `len(pool)`, derivado** — no un campo aparte. Con el scope
>    aplicado se vuelve el universo del activo automáticamente. §3.3 corregido (H10).
>
> **Origen (petición del usuario, 2026-09-03):** tras cerrar el bug 2, el chat responde bien
> «el Activo CASTILLA» (11.433.151 bbl) pero el panel derecho sigue mostrando **la
> distribución de los 128 campos de Ecopetrol**. Lo que se pide es el mismo panel —dona,
> participación %, volúmenes— **acotado a los campos de ese activo**.
>
> **Regla del usuario (2026-09-03), cerrada:** `ops.wells_attributes` es la **fuente única de
> verdad** de la jerarquía, y está actualizada. **Lo que no esté ahí, no existe.**

---

## 0. Contexto para el agente EXECUTOR

**Proyecto:** ProdIA — asistente conversacional de producción (Ecopetrol). Este plan toca
**solo el backend**.

**Raíz del repo:** `C:\APLICACIONES\ProdIA\Repo ProdIA\backend\`
⚠️ Doble anidamiento: el paquete Python vive en `backend\backend\app\...`.

**Archivos de producción a modificar (DOS):**
- `...\backend\backend\app\features\consulta_v2\cuantificar\ranking.py`
- `...\backend\backend\app\features\consulta_v2\respuesta_cuantificar.py`

**Archivo de tests:** `...\backend\backend\tests\test_cuantificar_ranking.py`

### 🔑 DOS bases de datos, no una

Esto es lo más importante que el executor debe entender antes de tocar nada:

| Motor | Función | Contenido |
|---|---|---|
| `get_engine()` | BD principal (`core.*`) | producción, fact, dim_fuente |
| **`get_ops_engine()`** | **BD de robustez/ops** | **`ops.wells_attributes`** — la jerarquía |

`app/core/db.py:16-24`. `get_ops_engine()` **lanza `RuntimeError`** si `OPS_DATABASE_URL` no
está configurada. Verificado: conecta desde local (PostgreSQL 18.6).

⚠️ **NO se puede hacer un JOIN SQL entre las dos**: son conexiones distintas. La jerarquía se
lee en una consulta aparte y se cruza **en Python**. Este plan lo hace así a propósito.

### Cómo correr los tests

```powershell
cd 'C:\APLICACIONES\ProdIA\Repo ProdIA\backend\backend'
.venv\Scripts\python.exe -m pytest tests/test_cuantificar_ranking.py -q
```

⚠️ La BD local está congelada: el mes con datos densos es **2025-11-30** (741 filas de REAL
crudo); 2026-05-31 solo tiene 8. Los tests de este plan son **puros o se saltan sin BD**.

---

## 1. Hallazgos de la auditoría (determinan la §3)

### 🟢 H1 — El punto de enganche ya existe y hoy declina prometiendo esto mismo

`respuesta_cuantificar.py:239-249`, guarda (3) del ranking:

```python
_hit = _resolver.buscar_en_texto(texto)
ent_det = entidad or (_hit[0] if _hit else None)
if ent_det and _resolver.resolver_unico(ent_det) is not None:
    return {"mensaje": (f"El ranking DENTRO de «{ent_det}» llega en una próxima fase. ...")}
```

⇒ La entidad ya está detectada y resuelta en ese punto. **Este plan sustituye esa declinación
por el ranking scoped** cuando el nivel resuelto es `activo`. No hay que detectar nada nuevo.

### 🟢 H2 — El cálculo, la dona y el formateador NO se tocan

`_panel_rank()` (`respuesta_cuantificar.py:342-346`) es un **passthrough**: copia 11 claves del
resultado de `calcular()`. La dona, el «Otros (N campos)», la participación individual y el
bullet de concentración se derivan de `items` + `total_universo` + `concentracion_pct`.

⇒ Si `calcular()` devuelve el contrato de siempre con menos items, **todo lo demás funciona
igual**. Cero cambios en el frontend, en el formateador y en el panel.

### 🟢 H3 — La jerarquía por activo está LIMPIA en `wells_attributes` (medido)

```
activo CASTILLA     -> 3 campos: ['CASTILLA', 'CASTILLA ESTE', 'CASTILLA NORTE']
activo APIAY        -> 4 campos: ['APIAY', 'APIAY ESTE', 'GAVAN', 'GUATIQUIA']
activo CHICHIMENE   -> 2 campos: ['CHICHIMENE', 'CHICHIMENE SW']
```

...**con dos filtros que son obligatorios** (H4 y H5).

### 🔴 H4 — Conviven DOS jerarquías en la tabla: hay que descartar la vieja

`wells_attributes` tiene VPs con prefijo `V` (VAO, VRC, VRO, VPI, VEX, VFS) y con `G` (GAA,
GPA, GRM…). **CASTILLA aparece en ambas**, con jerarquías distintas:

| Rama | Ejemplo CASTILLA | Pozos ACT (global) | Pozos ABA (global) |
|---|---|---:|---:|
| `V*` (vieja) | `vp=VRO, ger=CASTILLA` | **435** | 6.219 |
| `G*` (vigente) | `vp=GAA, ger=PPC` | **15.438** | 6.192 |

⇒ **Filtro obligatorio: `vice_presidency NOT LIKE 'V%'`.** Sin él, cada campo sale duplicado
con dos activos distintos y el panel sería incorrecto.

### 🔴 H5 — Hay filas basura con `vice_presidency = '0'`

De los 7 campos con más de un activo, **5 lo son por una rama con `vp='0', ger='0', act='0'`**
(GIRASOL, JAZMIN, NARE, UNDERRIVER, ABARCO BUFFER) frente a una rama válida.

⇒ **Segundo filtro obligatorio: `vice_presidency <> '0'`.**

Con ambos filtros quedan **2 ambigüedades reales**, no 7:
- `AULLADOR` → LISAMA vs LISAMA UNIFICADO
- `SARDINATA` → POB CATATUMBO vs SOT

Son campos pequeños. **No se resuelven en este plan** (§7): un campo que pertenece a dos
activos aparecerá en el panel de ambos, que es lo que dice la fuente.

### 🟢 H6 — El total del panel CUADRA con la cifra del texto (medido)

El riesgo que hizo posponer esto era «dos totales distintos en la misma pantalla». **No se
materializa**, verificado con producción real (2025-11-30, crudo):

```
TEXTO  (map_campo_activo, lo que usa el ejecutor hoy): 8,309,603 bbl
PANEL  (wells_attributes, lo que usaría este plan)   : 8,309,603 bbl
```

Coinciden porque para CASTILLA ambos catálogos listan los mismos 3 campos.

⚠️ **No está garantizado para todos los activos** — son catálogos distintos y solo se verificó
CASTILLA. Por eso §3.4 incluye un test que compara ambos universos, y §6.2 pide contrastar el
total del panel contra el del texto en Pruebas.

### 🟢 H7 — El panel simulado con datos reales es exactamente lo pedido

```
=== PANEL del activo CASTILLA (2025-11-30) ===
   CASTILLA                4,849,401   58.4%
   CASTILLA NORTE          3,460,202   41.6%
   CASTILLA ESTE                   0    0.0%
   TOTAL 8,309,603
```

### 🟠 H8 — El «cero traicionero» ya tiene política y hay que respetarla

CASTILLA ESTE sale con 0. `ranking.py:250` ya define la regla: *«CERO TRAICIONERO: 0 no es
"poca producción"»* — los separa en `con_real` y los cuenta en `sin_registro`.

⇒ El scoped **reusa esa lógica tal cual**. CASTILLA ESTE no aparecerá como item; se contará en
`sin_registro`, y el panel ya sabe declararlo.

### 🔴 H9 — `calcular()` NO acepta hoy un filtro de campos: hay que añadirlo sin romper la firma

`ranking.py:228` → `calcular(slots, _engine=None)`. El SQL de `campo` (`:201-211`) no filtra
por activo, y **no puede** (la jerarquía está en la otra BD).

⇒ Se añade un parámetro **opcional** `campos_scope: set|None`. Si es `None`, comportamiento
idéntico al actual. El filtrado se hace **en Python sobre `datos`**, después de la query — no
en SQL, porque cruzar dos motores en SQL es imposible (§0).

⚠️ **Lección del bug 2 (2026-09-03), aplicada aquí:** un parámetro nuevo debe ser opcional Y
hay que verificar quién hace `monkeypatch` de la función. Medido: `test_cuantificar_ranking.py`
llama `calcular()` directo (no la parchea), y `respuesta_cuantificar.py:251` es el único call
site de producción. Sin riesgo — pero el executor debe **volver a comprobarlo con grep**, no
fiarse de esta línea.

### 🟡 H10 — `total_universo` es `len(pool)`, se ajusta SOLO al aplicar el scope

**Corregido en v2.** El plan v1 asumía un `total_universo` fijo que declarar. **Falso**:
`ranking.py:302` lo calcula como `"total_universo": len(pool)`, y `pool` deriva de `con_real`,
que deriva de `datos`. Con el scope filtrando `datos`, **`total_universo` se vuelve el número
de campos del activo automáticamente** — no hay que tocarlo.

La concentración (`ranking.py:279-283`) también se recalcula sobre el universo reducido sola.

⇒ Lo único que hay que añadir es **`scope_label`** (§3.3) para que el panel pueda decir «los
3 campos del activo CASTILLA» en vez de un porcentaje sin base. Aditivo: si el frontend lo
ignora, no rompe nada.

### 🟢 H11 — El cruce de nombres wells↔fact funciona, con el COALESCE correcto (medido)

El filtro `d[0].upper() in campos_scope` cruza dos catálogos: `campos_scope` viene de
`wells_attributes.field`, `d[0]` viene de `datos`, que es
`COALESCE(NULLIF(TRIM(f.campo),''), f.nombre)` (`ranking.py:202, 248`).

⚠️ **Detalle que importa:** `CASTILLA ESTE` está en `dim_fuente.nombre`, NO en `.campo`.
Comparar solo contra `.campo` daría un falso negativo. Pero `datos` **ya usa el COALESCE**, así
que `d[0]` es el nombre correcto. Medido: CASTILLA cruza **3/3**.

```
wells CASTILLA: ['CASTILLA','CASTILLA ESTE','CASTILLA NORTE']
en el fact:     ['CASTILLA','CASTILLA ESTE','CASTILLA NORTE']   (3/3, cero faltantes)
```

### 🟠 H12 — 17 de 118 campos de wells no cruzan con el fact — límite conocido, no bloqueante

Medido con la expresión COALESCE real: **101 de 118 campos de `wells_attributes` cruzan** con
`dim_fuente`. Los 17 que no: `ABARCO BUFFER`, `CAMPO EXPLORATORIO MORITO-1`, `LISAMA PROFUNDO`,
`MEREY`, `CENCELLA`… — **buffers y exploratorios sin producción registrada**.

⇒ Para un activo con producción real (CASTILLA, APIAY, CHICHIMENE), el cruce es completo y el
panel es correcto. Un activo cuyos campos fueran todos exploratorios daría panel vacío →
`aplica=False` → declina (H1). **No rompe nada**, pero se documenta: el scope solo puede
mostrar lo que el fact tiene.

### 🟢 H13 — La cadena entera resuelve a `nivel=activo`, verificado end-to-end

El riesgo mayor del plan: que la pregunta scoped NO llegue a activar el scope. Medido con la
cadena real (`detectar_entidad` → `_resolver_con_contexto`):

```
"...los campos DEL ACTIVO Castilla"        -> ent=CASTILLA -> nivel=activo  ✅
"cuales campos DEL ACTIVO Castilla ..."    -> ent=CASTILLA -> nivel=activo  ✅
"...DEL ACTIVO APIAY por campo"            -> ent=APIAY    -> nivel=activo  ✅
```

Y `detectar()` sí dispara para esas frases (`rk["nivel_ranking"]=="campo"`), así que entran a
la guarda (3). **La cadena completa funciona** — este era el punto que hacía o rompía el plan.

⚠️ Depende del fix de `contexto` del 2026-09-03 (`resolver_unico(..., contexto=texto)`). Ya
está en `main`. Si por lo que sea `_resolver_con_contexto` devolviera `campo`, el scope no se
activa y se cae a la declinación — degradación segura, no error.

---

## 2. Estado actual

- `ranking.py:200-225` — `_SQL` con las variantes `campo` y `activo`. Sin filtro por activo.
- `ranking.py:228-…` — `calcular(slots, _engine=None)`; el filtrado de `con_real`/`sin_registro`
  está en `:247-256`.
- `respuesta_cuantificar.py:239-249` — la guarda (3) que declina el scoped.
- `respuesta_cuantificar.py:342-346` — `_panel_rank()`, passthrough de 11 claves.
- `app/core/db.py:16-24` — `get_ops_engine()`.

---

## 3. Especificación

### 3.1 AÑADIR el lector de jerarquía en `ranking.py`

Va **antes** de `calcular()`. Necesita `get_ops_engine`, que **hay que importar** — verificar
la línea de import existente (`from app.core.db import get_engine`) y ampliarla.

```python
# [2026-09-03] JERARQUÍA: ops.wells_attributes es la FUENTE ÚNICA DE VERDAD y está al día
# (regla del usuario, 2026-09-03): lo que no esté ahí, NO EXISTE. Vive en OTRA BD
# (get_ops_engine), así que NO se puede JOIN-ear con core.* — se lee aparte y se cruza en
# Python.
# ⚠️ DOS FILTROS OBLIGATORIOS, medidos el 2026-09-03:
#   1. `vice_presidency NOT LIKE 'V%'` — conviven DOS jerarquías. La rama V* es la VIEJA
#      (435 pozos activos y 6.219 abandonados, contra 15.438 activos de la G*). Sin este
#      filtro CASTILLA sale con dos activos distintos y el panel es incorrecto.
#   2. `vice_presidency <> '0'` — filas basura (vp/ger/act = '0') que duplican 5 campos.
# Quedan 2 ambigüedades reales (AULLADOR, SARDINATA): un campo en dos activos. Se respetan
# como dice la fuente — aparecerá en el panel de ambos. Fuera de alcance de este plan.
_SQL_CAMPOS_DE_ACTIVO = """
    SELECT DISTINCT UPPER(TRIM(field)) AS campo
    FROM ops.wells_attributes
    WHERE field IS NOT NULL
      AND vice_presidency NOT LIKE 'V%'
      AND vice_presidency <> '0'
      AND UPPER(TRIM(active)) = :activo
"""


def campos_de_activo(activo: str) -> set:
    """Campos que pertenecen al activo, según la fuente única (ops.wells_attributes).

    Devuelve un set de nombres NORMALIZADOS (UPPER, sin espacios extremos) o `set()` si la
    BD de robustez no está disponible o el activo no existe. Nunca lanza: sin jerarquía el
    llamador degrada al ranking global, que es el comportamiento de hoy.
    """
    if not activo:
        return set()
    try:
        eng = get_ops_engine()
        with eng.connect() as c:
            rows = c.execute(sa.text(_SQL_CAMPOS_DE_ACTIVO), {"activo": norm(activo)}).all()
        return {(r[0] or "").strip() for r in rows if r[0]}
    except Exception:
        return set()   # degradación con gracia (mismo criterio que _cargar_vp_robustez)
```

⚠️ `norm` ya está importado en `ranking.py` (`from ...normaliza import norm`, línea 32).
**Verificarlo** antes de usarlo.

### 3.2 MODIFICAR `calcular()` para aceptar el scope

Cambiar **solo la firma y el filtrado**, nada más:

```python
def calcular(slots: dict, _engine=None, campos_scope: set | None = None) -> dict:
```

Y justo **después** de la línea que construye `datos` (`ranking.py:247-249`) y **antes** de
`con_real = [...]`, insertar:

```python
    # [2026-09-03] SCOPE por activo: se filtra en PYTHON, no en SQL — la jerarquía vive en
    # otra BD (ops.wells_attributes) y no se puede JOIN-ear. `None` = ranking global (el
    # comportamiento de siempre); un set vacío NO llega aquí (el llamador degrada antes).
    if campos_scope:
        datos = [d for d in datos if d[0].upper() in campos_scope]
```

**No se toca nada más de `calcular()`**: `con_real`, `sin_registro`, la guarda de vacío, el
cálculo de concentración y el orden siguen exactamente igual, operando ya sobre el universo
reducido (H8: el «cero traicionero» se respeta solo).

### 3.3 AÑADIR `scope_label` al contrato (aditivo)

⚠️ **No hay que tocar `total_universo` ni `concentracion_pct`** (H10): ya son `len(pool)` y el
cálculo sobre `con_real`, ambos post-filtro, así que se ajustan solos al universo del activo.

Al **principio** de `calcular()` (junto a las otras lecturas de `slots`, ~`ranking.py:236`):

```python
    scope_label = slots.get("scope_label")   # p.ej. "el Activo CASTILLA"; None = ranking global
```

En el `return` del contrato exitoso (`ranking.py:297-304`, el dict con `"aplica": True`),
añadir la clave junto a las demás:

```python
        "scope_label": scope_label,     # None en el ranking global
```

Y en `_panel_rank()` (`respuesta_cuantificar.py:342-346`), añadir `"scope_label"` a la tupla
de claves copiadas.

⚠️ **Aditivo puro**: si el frontend ignora la clave, el panel se pinta como hoy. Que el
frontend la use es un cambio aparte (§7).

### 3.4 MODIFICAR la guarda (3) en `respuesta_cuantificar.py`

Sustituir el bloque de `respuesta_cuantificar.py:243-249` por:

```python
        _hit = _resolver.buscar_en_texto(texto)
        ent_det = entidad or (_hit[0] if _hit else None)
        _res_ent = _resolver_con_contexto(ent_det, texto) if ent_det else None
        if _res_ent is not None and not _res_ent.get("ambiguo"):
            # [2026-09-03] SCOPED por ACTIVO: el panel de distribución acotado a los campos
            # de ese activo. Antes esto se declinaba entero («llega en una próxima fase»).
            # Solo aplica a nivel=activo con nivel_ranking=campo: «los campos DEL activo X».
            # El resto (campo, gerencia, VP) sigue declinando — ver más abajo.
            if _res_ent.get("nivel") == "activo" and rk.get("nivel_ranking") == "campo":
                _scope = _ranking.campos_de_activo(_res_ent["valor"])
                if _scope:
                    rk = dict(rk)
                    rk["scope_label"] = f"el Activo {_res_ent['valor']}"
                    res = _ranking.calcular(rk, campos_scope=_scope)
                    if res.get("aplica"):
                        cuerpo = _ranking.formatear_cuerpo(res)
                        mensaje = respuesta_base.envolver(
                            _intro_ranking(res, usuario), cuerpo, _CIERRE_RANK)
                        return {"mensaje": mensaje,
                                "panel": {"tipo": "cuant_rank", "datos": _panel_rank(res)}}
                # sin jerarquía o sin datos → cae a la declinación honesta de abajo
            return {"mensaje": (
                f"El ranking DENTRO de «{ent_det}» llega en una próxima fase. Por ahora puedo "
                f"rankear sobre toda la operación —por ejemplo, «los 5 campos que más "
                f"{rk['producto']} producen»."), "panel": None}
```

🔑 **Tres degradaciones deliberadas**, todas a la declinación que ya existe:
1. La BD de robustez no responde → `campos_de_activo` devuelve `set()` → declina.
2. El activo no está en la fuente única → `set()` → declina.
3. El scope deja 0 campos con producción → `aplica=False` → declina.

⚠️ **`_resolver_con_contexto` ya existe** en ese módulo (creado el 2026-09-03) — reusarlo, no
llamar `resolver_unico` directo: es lo que permite que «el activo X» resuelva a `activo`.

### 3.5 AÑADIR tests en `tests/test_cuantificar_ranking.py`

Sección al final. Los que tocan BD deben saltarse limpio con el `_engine_o_skip` **que ya
existe en ese archivo** (`:92-101`) — no inventar otro.

```python
# --- V-SCOPE · ranking acotado al activo (2026-09-03) ---------------------------------------

def test_calcular_sin_scope_es_el_comportamiento_de_siempre():
    """🔒 REGRESIÓN: campos_scope=None -> ranking global, idéntico a antes del cambio."""
    eng = _engine_o_skip()
    a = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                     "top_n": 5, "producto": "crudo", "periodo_texto": None}, _engine=eng)
    b = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                     "top_n": 5, "producto": "crudo", "periodo_texto": None},
                    _engine=eng, campos_scope=None)
    assert a["items"] == b["items"] and a["total_universo"] == b["total_universo"]


def test_scope_reduce_el_universo():
    """El panel scoped ve SOLO los campos del scope."""
    eng = _engine_o_skip()
    res = RK.calcular({"nivel_ranking": "campo", "metrica": "real", "direccion": "top",
                       "top_n": 5, "producto": "crudo", "periodo_texto": None},
                      _engine=eng, campos_scope={"CASTILLA", "CASTILLA NORTE"})
    if not res.get("aplica"):
        pytest.skip("sin datos de crudo en el mes por defecto de esta BD")
    assert {it["entidad"] for it in res["items"]} <= {"CASTILLA", "CASTILLA NORTE"}
    assert res["total_universo"] <= 2


def test_campos_de_activo_castilla():
    """La fuente única (ops.wells_attributes) con los 2 filtros obligatorios (H4/H5)."""
    try:
        campos = RK.campos_de_activo("CASTILLA")
    except Exception:
        pytest.skip("BD de robustez no disponible")
    if not campos:
        pytest.skip("BD de robustez no disponible o sin datos")
    assert "CASTILLA" in campos and "CASTILLA NORTE" in campos
    # 🔑 La rama VIEJA (vp=VRO) daría otros activos; con el filtro no aparecen campos ajenos.
    assert all(c.startswith("CASTILLA") for c in campos)


def test_campos_de_activo_inexistente_no_lanza():
    """🔒 Degradación con gracia: lo que no está en la fuente única, no existe -> set()."""
    try:
        assert RK.campos_de_activo("NO_EXISTE_ESTE_ACTIVO_XYZ") == set()
    except Exception:
        pytest.skip("BD de robustez no disponible")


def test_campos_de_activo_vacio_o_none():
    """Puro, sin BD: guarda de entrada."""
    assert RK.campos_de_activo("") == set()
    assert RK.campos_de_activo(None) == set()
```

---

## 4. Orden de ejecución

| # | Paso | Verificación | Si falla |
|---|---|---|---|
| 0 | Baseline: `pytest tests/ -q` | anotar (esperado **650 pasan, 10 fallan**) | DETENTE |
| 0-bis | Golden **ANTES** (§6.1) | anotar `pct`/`aciertos` (92 / 85 en local) | DETENTE |
| 0-ter | `grep -rn "calcular(" --include=*.py app/ tests/` | confirmar los call sites de `_ranking.calcular` (H9) | si hay un monkeypatch, reportarlo antes de seguir |
| 1 | §3.1 — `campos_de_activo` + import de `get_ops_engine` | `py_compile` OK | revisar el import |
| 2 | §3.2 + §3.3 — `campos_scope` y `scope_label` | `pytest tests/test_cuantificar_ranking.py -q` sin fallos nuevos | comparar con baseline |
| 3 | §3.4 — la guarda (3) | `pytest tests/ -q` sin fallos nuevos | ver qué test cayó |
| 4 | §3.5 — los 5 tests nuevos | pasan o **skip limpio** si no hay BD | ajustar al `_engine_o_skip` real |
| 5 | Suite completa | **exactamente 10 fallos**, ninguno nuevo | comparar con paso 0 |
| 6 | Golden **DESPUÉS** | **sin cambio** respecto al 0-bis | si baja: revertir |

⚠️ **La BD local está congelada**: el mes por defecto puede no tener datos de crudo y varios
tests harán `skip`. **Eso es correcto, no es un fallo.** La verificación real es §6.2.

---

## 5. Reglas no negociables

1. **`ops.wells_attributes` es la fuente única de la jerarquía** (regla del usuario). No
   inventar mapeos ni completar con `map_campo_activo`/`map_campo_robustez`.
2. **Los dos filtros son obligatorios**: `vice_presidency NOT LIKE 'V%'` y `<> '0'` (H4/H5).
   Sin ellos el panel es incorrecto.
3. **NO hacer JOIN entre las dos BD** — son motores distintos. Cruce en Python (§0).
4. **`campos_scope` y `scope_label` son OPCIONALES**: sin ellos, comportamiento idéntico.
5. **NO tocar el cálculo, el orden, la concentración ni el formateador** (H2/H8).
6. **NO tocar el frontend** — `scope_label` es aditivo; pintarlo es otro cambio (§7).
7. **`campos_de_activo` nunca lanza**: sin jerarquía, `set()` y el llamador declina como hoy.
8. **NO tocar ningún test existente.** Si uno cae, el que está mal es el código.
9. Solo `nivel=activo`. Campo, gerencia y VP **siguen declinando** — gerencia y VP dependen del
   bug 1, que sigue abierto.

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

Comprobación directa de la fuente única (no necesita el fact):

```powershell
.venv\Scripts\python.exe -c "import app.features.consulta_v2.cuantificar.ranking as RK; print('CASTILLA ->', sorted(RK.campos_de_activo('CASTILLA'))); print('APIAY ->', sorted(RK.campos_de_activo('APIAY')))"
```

Esperado:
```
CASTILLA -> ['CASTILLA', 'CASTILLA ESTE', 'CASTILLA NORTE']
APIAY -> ['APIAY', 'APIAY ESTE', 'GAVAN', 'GUATIQUIA']
```

### 6.2 Humana (usuario) — en PRUEBAS

Tras `git pull` + **reiniciar INGESTA**:

| Pregunta | Esperado |
|---|---|
| «¿Cómo se distribuye la producción de crudo entre los campos **del activo CASTILLA**?» | Panel con **CASTILLA y CASTILLA NORTE** y sus %, no los 128 campos |
| «¿Cuáles campos **del activo APIAY** producen más crudo?» | Panel con los campos de APIAY |
| «¿Cuál es la producción del activo CASTILLA?» | Sigue dando **11.433.151 bbl** (bug 2, sin cambio) |
| «¿Cuáles son los 5 campos que más crudo producen?» | **Ranking global de siempre** ← regresión clave |
| «¿Cómo se distribuye la producción de crudo entre los campos?» | Global, 128 campos ← regresión clave |
| «Ranking de campos de la gerencia PPC» | Sigue **declinando** (depende del bug 1) |

🔑 **La verificación que zanja el plan**: el **total del panel scoped** debe coincidir con la
**cifra del texto** para ese activo (H6: medido 8.309.603 = 8.309.603 en local para CASTILLA).
Si no cuadran, los dos catálogos divergen para ese activo y hay que reportarlo.

**El único que marca ✅ es el usuario.**

### 6.3 Medición de valor

Binaria y visible: hoy preguntar por los campos de un activo **declina**; después devuelve el
panel. No necesita `clasificacion_log`.

Segundo indicador, más fino: que el total del panel cuadre con el del texto en los 3 activos
multi-campo (CASTILLA, APIAY, CHICHIMENE).

### 6.4 Despliegue

Backend solamente → commit a GitHub `main` → `git pull` en Pruebas → **reiniciar INGESTA** →
validar §6.2 → `migrar-a-azure` (3 tiempos, default `prodiav2`) → en el 139: `git pull` +
reiniciar INGESTA.

⚠️ **Requisito nuevo de entorno**: este plan hace que el chat dependa de `OPS_DATABASE_URL`
para el panel scoped. Ya existe (la usa `economia`), pero **verificar que esté definida en el
139** antes de publicar, o el panel degradará a la declinación sin explicar por qué.

---

## 7. Fuera de alcance

- **Pintar `scope_label` en el frontend**: la clave viaja en el contrato; usarla es un cambio
  de UI aparte.
- **Ranking scoped por gerencia o VP**: depende del **bug 1** de `jerarquias_sup_error.md`.
- **AULLADOR y SARDINATA** (un campo en dos activos, H5): se respeta lo que dice la fuente.
- **Migrar TODA la jerarquía a `wells_attributes`** (bugs 1 y 3): es el plan grande que este
  valida en pequeño. Si el panel funciona, ese plan se escribe con evidencia.
- **Los campos de terceros** (QUIFA, CAÑO LIMÓN, COHEMBI…): no están en la fuente única porque
  no son de Ecopetrol. Correcto por definición — no se completan.
- Cualquier cambio en el cálculo, el SQL de producción o el formateador.
