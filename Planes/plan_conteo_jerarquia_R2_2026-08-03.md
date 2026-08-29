# Plan B (auditado) — Cuantificar: puente level-shift gerencia→vicepresidencia (R2)

> **Modo:** ejecutable por un Executor externo. Rutas ABSOLUTAS. Código de referencia COMPLETO.
> **Fecha:** 2026-08-03 · **Planner:** Claude · **Auditado** (§0.2 del CLAUDE.md de INGESTA — la
> auditoría contra BD real se hizo ANTES de escribir la especificación, no en una ronda posterior).
> Cierra 2.3 del `HALLAZGO_clasificador_conteo_jerarquia.md`. Complementa el Plan A (R1+R3, commit
> `a0db67e`) — **R1 ya resolvió el GOR del CONTEO** (lo enruta a Jerarquizar, que lo trata como VP).
> Este plan cierra el GOR de la **PRODUCCIÓN** ("cuánto produjo GOR" → hoy dice "la Gerencia GOR").

**Cobertura: 1 pieza → 1** (R2, puente en Cuantificar). Sin recortes.

---

## 0. Auditoría (contra BD real, 2026-08-03) — por qué el fix NO es "relabel incondicional"

**El defecto, verificado vigente:** `cuantificar/resolver.py` resuelve "GOR" a
`{'nivel': 'gerencia', 'rama': 'A', 'valor': 'GOR'}` (única identidad — su índice viene de
`core.dim_fuente.gerencia`, que en INGESTA está literalmente etiquetada "gerencia"). Ese `nivel`
alimenta `_NIVEL_TEXTO["gerencia"] = "la Gerencia"` en `cuantificar/ejecutor.py`, que aparece VERBATIM
en cada respuesta: *"la Gerencia GOR produjo 45.262 bbl..."* En la jerarquía oficial (`core.
map_campo_robustez`, fuente de verdad desde la sesión S28), GOR es una **Vicepresidencia**.

**🔑 Hallazgo que reduce el alcance del fix — `dim_fuente.gerencia` NO es una lista pura de
vicepresidencias mal-nombradas.** Cruce verificado de los 17 valores distintos contra
`map_campo_robustez.rob_vicepresidencia` / `rob_gerencia`:

| Categoría | Valores | Acción |
|---|---|---|
| **VP-robustez sin ambigüedad** (8) | DFL, GAA, GCT, GOR, GPA, GRM, GTA, PRP | Relabel a "la Vicepresidencia" |
| **Ambiguo** (3) | **CPV, GAN, GXO** — existen como `rob_vicepresidencia` **y** como `rob_gerencia` en robustez (`rob_vicepresidencia ∩ rob_gerencia = {CPV, GAN, GXO}`, verificado por intersección de conjuntos, no solo revisando GOR aisladamente) | **NO relabel** — mismo criterio de desempate que ya usa `respuesta_jerarquizar._elegir` (nivel más específico gana cuando el usuario no desambigua: `_ORDEN` pone gerencia antes que vicepresidencia) |
| **Sin match en robustez** (6) | GAO, GAR, GDA, GEE, GLH, GNS — terceros/no-ECP, fuera del universo que `map_campo_robustez` modela (ceiling ya documentado en S28: solo 80/139 campos) | **NO relabel** — no hay evidencia de robustez para corregir; la etiqueta actual ("la Gerencia") queda como estaba, sin inventar una verdad que no se puede verificar |

⚠️ **Autocorrección de esta misma auditoría (ronda de verificación, 2026-08-03):** un primer barrido
había etiquetado CPV y GXO como "VP sin ambigüedad" (comprobando solo `if valor in rob_vicepresidencia`
sin cruzar TAMBIÉN contra `rob_gerencia`) — es decir, el mismo tipo de error de "regla demasiado
amplia" que H1 encontró en el Plan A. La **lógica del código** (`vps - gers`, diferencia de conjuntos,
ver RS1) siempre fue correcta y calcula esto en vivo — pero la narrativa del plan y la validación V5
tenían el número equivocado. Corregido aquí; V5 ahora afirma explícitamente que CPV/GAN/GXO quedan
FUERA (guarda de regresión permanente, mismo principio que las guardas de R1).

**Decisión de diseño — SIN frase-puente educativa (a diferencia de Jerarquizar):**
`respuesta_jerarquizar._con_puente` construye *"Lo que en el reporte diario llamas «la gerencia
GOR»..."* usando la palabra EXACTA que el usuario escribió antes de la entidad (`_label_previo`,
rastrea el token previo en el texto). El resolver de Cuantificar **no tiene esa mecánica** — resuelve
por nombre, no rastrea con qué palabra lo calificó el usuario. Construir la misma frase aquí
**asumiría** que el usuario dijo "gerencia" cuando pudo haber escrito "vicepresidencia GOR", "VP GOR"
o solo "GOR" a secas — le atribuiría una palabra que no usó. Por eso R2 hace una **corrección
silenciosa de la etiqueta** (el texto simplemente dice "la Vicepresidencia GOR", sin comentar sobre
qué dijo el usuario), no una frase educativa. Esto resuelve el defecto EXACTO que reporta el hallazgo
(la etiqueta incorrecta en la respuesta) sin el riesgo de inventar contexto.

**Ocurrencia hermana, verificada, FUERA de alcance:** `respuesta_analizar.py` (grupo Analizar)
también usa `cuantificar.resolver` y construye `alcance = f"el {nivel} {ent_valor}".strip()` —mismo
bug potencial. Pero su exposición es mucho menor: `alcance` solo alimenta el prompt del LLM
(`PROMPT_ANALIZA`), que tiene instrucción explícita *"NO lo repitas"* — no aparece verbatim en la
respuesta al usuario, a diferencia de Cuantificar donde `entidad_cualificada` SÍ es texto directo.
Se documenta pero **no se toca** (el hallazgo 2.3 solo nombra a Cuantificar).

**Verificado — `niveles.py` (N2/N3/N4) no construye su propia etiqueta de texto**: solo calcula
números (real/ppto/serie/deltas); la etiqueta se arma ÚNICAMENTE en `ejecutor.py` (4 sitios, uno por
nivel). Arreglar esos 4 sitios es la corrección COMPLETA — no hace falta tocar `niveles.py`.

**Verificado — el `nivel` de QUERY no cambia.** `resuelta["nivel"]` sigue siendo `"gerencia"` en todo
momento (se sigue filtrando `dim_fuente.gerencia = 'GOR'` en `analisis.desempeno`/`escenario_mes`) —
el fix es **puramente de texto/display**, nunca toca qué columna consulta la SQL. Esto es
deliberado: cambiar `nivel` a "vicepresidencia" rompería la query (GOR no vive en la columna de
vicepresidencia de `dim_fuente`, solo en la de gerencia).

**Verificado — todos los llamadores de `_NIVEL_TEXTO` y `resolver_unico`, exhaustivo (grep en todo
`consulta_v2/`):** `_NIVEL_TEXTO` SOLO se lee en `ejecutor.py` (los 4 sitios de este plan) — ningún
otro archivo lo importa. `resolver_unico` tiene 3 llamadores: `respuesta_cuantificar.py` (en
alcance), `respuesta_analizar.py` (documentado, fuera de alcance, ver abajo) y
`golden/run_golden_cuantificar.py`.

**Verificado — el golden de Cuantificar NO necesita tocarse.** Existe un caso
(`cuantificar_golden.yaml`: *"¿cuánto produjo la gerencia GOR?"*, `entidad: GOR`), pero
`run_golden_cuantificar.py::_clasificar_resultado` solo valida **estructura** (nivel_temporal /
producto / referencia / categoría `aplica`|`rechazo_*`|`ambiguo`) — **nunca** compara el texto de la
etiqueta. El caso sigue dando `aplica` (GOR se resuelve y ejecuta igual) → sigue en verde sin
editar el archivo. (Ese runner además trae su propia advertencia: NO correr en dev, abre varias
conexiones a Postgres — no forma parte de las validaciones §6 de este plan.)

---

## 1. Objetivo

Que Cuantificar, al resolver una entidad con `nivel="gerencia"` cuyo valor es **inequívocamente** una
vicepresidencia en `core.map_campo_robustez` (sin colisión con una gerencia real), muestre **"la
Vicepresidencia {valor}"** en el texto de la respuesta (y en el panel) — en vez de "la Gerencia
{valor}". El `nivel` usado para consultar la BD no cambia.

---

## 2. Prerequisitos + baseline

Desde `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`:

```
uv run python -c "import app.features.consulta_v2.cuantificar.resolver, app.features.consulta_v2.cuantificar.ejecutor; print('IMPORTS OK')"
```
Esperado: `IMPORTS OK`.

**Baseline (capturar ANTES de editar):**
```
uv run pytest tests/test_cuantificar.py tests/test_cuantificar_rango.py -q
```
Anotar el resumen (se compara en V4).

**Regla de entorno:** en dev NO se levanta backend ni LLM. Validación estática: `py_compile` + tests
puros. `_cargar_vp_robustez` (nuevo) usa `get_engine()` — MISMA BD que ya usa todo `cuantificar/`
(NO es cross-DB como R3; no requiere `robustez_v02`). Se testea con monkeypatch, sin BD real.

---

## 3. Inventario de archivos

(`...` = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

| Archivo (ruta absoluta) | Acción |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\resolver.py` | **EDITAR** (lookup VP-no-ambigua + marcar `puente` en `resolver_unico`) |
| `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\ejecutor.py` | **EDITAR** (`_etiqueta_nivel` helper, 4 call-sites) |
| `...\INGESTA\Rep_Prod\backend\tests\test_puente_gerencia_vp.py` | **CREAR** (tests puros) |

**NO se toca:** `slots.py`, `niveles.py`, `validador.py`, `respuesta_cuantificar.py`,
`respuesta_analizar.py` (ocurrencia hermana documentada, fuera de alcance), `patrones_grupo.yaml`,
`respuesta_jerarquizar.py`, `dominio.py`, `maquina_q.py`, `no_soportado.py`, migraciones, frontend.

---

## 4. Especificación (código literal)

### 4.1 — EDITAR `cuantificar/resolver.py`

Ruta: `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\resolver.py`

**RS1 — insertar el lookup + el helper de marcado.** Insertar INMEDIATAMENTE ANTES de la línea
`def resolver_unico(texto: str) -> dict | None:`

```python
# R2 (2026-08-03, HALLAZGO_clasificador_conteo_jerarquia.md §2.3): core.dim_fuente.gerencia NO es una
# lista pura de "gerencias reales" — varios de sus valores son, en la jerarquía oficial de robustez
# (core.map_campo_robustez), VICEPRESIDENCIAS mal-nombradas "gerencia" en el esquema fuente de INGESTA
# (mismo level-shift que respuesta_jerarquizar.py ya puentea — sesión S28). Verificado contra BD:
# de 17 valores, 8 son VP-robustez SIN ambigüedad (DFL/GAA/GCT/GOR/GPA/GRM/GTA/PRP); 3 (CPV/GAN/GXO)
# son AMBIGUOS (existen como VP *y* como gerencia real distinta en robustez — `rob_vicepresidencia ∩
# rob_gerencia`; NO se relabelean, mismo criterio de desempate "nivel más específico gana" que ya usa
# respuesta_jerarquizar._elegir); 6 no tienen match en robustez (terceros fuera de su universo
# ECP-operado, sin evidencia para corregir). La resta de conjuntos (vps - gers, abajo) calcula esto en
# VIVO — NO hardcodear la lista: si robustez cambia, el cálculo se actualiza solo.
_VP_ROBUSTEZ = None   # cache por proceso: {norm(codigo)} — SOLO los exclusivamente vicepresidencia


def _cargar_vp_robustez():
    global _VP_ROBUSTEZ
    if _VP_ROBUSTEZ is not None:
        return _VP_ROBUSTEZ
    try:
        eng = get_engine()
        with eng.connect() as c:
            vps = set(v for (v,) in c.execute(sa.text(
                "SELECT DISTINCT rob_vicepresidencia FROM core.map_campo_robustez "
                "WHERE rob_vicepresidencia IS NOT NULL")))
            gers = set(v for (v,) in c.execute(sa.text(
                "SELECT DISTINCT rob_gerencia FROM core.map_campo_robustez "
                "WHERE rob_gerencia IS NOT NULL")))
    except Exception:
        _VP_ROBUSTEZ = set()   # degradación con gracia: sin evidencia -> no relabel (nunca lanza)
        return _VP_ROBUSTEZ
    _VP_ROBUSTEZ = {norm(v) for v in (vps - gers) if v}   # excluye ambiguos (CPV/GAN/GXO hoy)
    return _VP_ROBUSTEZ


def _marcar_puente(r: dict) -> dict:
    """R2: si el nivel resuelto es 'gerencia' pero el valor es EXCLUSIVAMENTE una vicepresidencia en
    robustez, marca r['puente']=True. El nivel de QUERY (r['nivel']) NO se toca — solo afecta cómo se
    ROTULA la entidad en el texto (ver ejecutor._etiqueta_nivel). Muta y devuelve `r`."""
    if r.get("nivel") == "gerencia" and norm(r["valor"]) in _cargar_vp_robustez():
        r["puente"] = True
    return r
```

**RS2 — aplicar `_marcar_puente` en los 2 puntos de retorno de `resolver_unico` que producen una
identidad única.** Texto ACTUAL a reemplazar:

```python
    if len(ids) == 1:
        r = dict(ids[0]); r["zoom"] = []
        return r
    modo, rep, reps = _resolver_colision(ids, clave_fisica)
    zoom = []
    if modo == "ask":
        rep_campo, zoom = _prioridad_campo(reps)
        if rep_campo is not None:
            modo, rep = "auto", rep_campo
    if modo == "auto":
        r = dict(rep); r["zoom"] = zoom
        return r
    return {"ambiguo": reps}
```

Texto NUEVO (reemplazo EXACTO):

```python
    if len(ids) == 1:
        r = dict(ids[0]); r["zoom"] = []
        return _marcar_puente(r)
    modo, rep, reps = _resolver_colision(ids, clave_fisica)
    zoom = []
    if modo == "ask":
        rep_campo, zoom = _prioridad_campo(reps)
        if rep_campo is not None:
            modo, rep = "auto", rep_campo
    if modo == "auto":
        r = dict(rep); r["zoom"] = zoom
        return _marcar_puente(r)
    return {"ambiguo": reps}
```

(El caso `{"ambiguo": reps}` NUNCA lleva `puente` — no aplica, no se construye `entidad_cualificada`
para una entidad no resuelta.)

### 4.2 — EDITAR `cuantificar/ejecutor.py`

Ruta: `...\INGESTA\Rep_Prod\backend\app\features\consulta_v2\cuantificar\ejecutor.py`

**EJ1 — insertar el helper de etiqueta.** Insertar INMEDIATAMENTE ANTES de la línea
`def _valor_referencia(ref, fila, d, quiero, resuelta, slots, escenario_fn):`

```python
def _etiqueta_nivel(nivel, resuelta):
    """R2: si el resolver marcó 'puente' (gerencia que en robustez es vicepresidencia, sin
    ambigüedad), usa la etiqueta REAL en el texto. `nivel` (la columna que ya usó la query) NO
    cambia — esto es solo el rótulo mostrado al usuario en entidad_cualificada."""
    if resuelta.get("puente"):
        return _NIVEL_TEXTO.get("vicepresidencia", "")
    return _NIVEL_TEXTO.get(nivel, "")
```

**EJ2 — reemplazar los 4 call-sites** (uno por función N1-N4). Cada reemplazo es de 1 línea.

*En `ejecutar_n1`* — texto ACTUAL:
```python
    nivel = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel, "")
```
texto NUEVO:
```python
    nivel = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel, resuelta)
```

*En `ejecutar_n2`* — texto ACTUAL:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    ms = ac["meses"]
```
texto NUEVO:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    ms = ac["meses"]
```

*En `ejecutar_n3`* — texto ACTUAL:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if s.get("proyeccion_mes"):
```
texto NUEVO:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if s.get("proyeccion_mes"):
```

*En `ejecutar_n4`* — texto ACTUAL:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if v.get("proyeccion_mes"):
```
texto NUEVO:
```python
    nivel_ent = resuelta.get("nivel")
    etiqueta = _etiqueta_nivel(nivel_ent, resuelta)
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if v.get("proyeccion_mes"):
```

⚠️ **Atención al aplicar EJ2 en N3 y N4:** ambos bloques `nivel_ent = resuelta.get("nivel")` +
`etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")` son TEXTUALMENTE IDÉNTICOS por sí solos (aparecen 2 veces
en el archivo) — por eso el texto ACTUAL de cada uno incluye 3 líneas MÁS de contexto (el bloque
`avisos`/`if slots.get("descargo")`/la condición siguiente) para que cada reemplazo sea único e
inequívoco. Verificar que cada reemplazo aplica en la función correcta (N3 tiene `if s.get(...)`, N4
tiene `if v.get(...)` — son las líneas que distinguen ambos bloques).

**NADA más de `ejecutor.py` cambia.** `_NIVEL_TEXTO` (el diccionario) NO se toca.

### 4.3 — CREAR `test_puente_gerencia_vp.py`

Ruta: `...\INGESTA\Rep_Prod\backend\tests\test_puente_gerencia_vp.py`

```python
"""Tests del puente level-shift gerencia→vicepresidencia en Cuantificar (R2). Mayoría PUROS (sin BD,
monkeypatch); 1 test opcional contra BD real (se salta con gracia si Postgres no está — mismo patrón
`_engine_o_skip` que ya usa tests/test_consulta_v2_clasificador.py)."""
import pytest

import app.features.consulta_v2.cuantificar.resolver as R
import app.features.consulta_v2.cuantificar.ejecutor as E


# --- resolver._marcar_puente: solo marca cuando es EXCLUSIVAMENTE vicepresidencia -----------------
def test_marca_puente_si_exclusivamente_vp(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR", "CPV"})
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GOR"})
    assert r.get("puente") is True


def test_no_marca_si_no_es_vp(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GNS"})   # sin match en robustez
    assert "puente" not in r


def test_no_marca_si_ambiguo_gan_excluido_del_lookup(monkeypatch):
    # _cargar_vp_robustez ya excluye los ambiguos (vps - gers) — GAN nunca debe estar en el set.
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})   # simula que GAN quedó fuera
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GAN"})
    assert "puente" not in r


def test_no_marca_si_nivel_no_es_gerencia(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"CASTILLA"})   # aunque "coincida" el valor
    r = R._marcar_puente({"nivel": "campo", "rama": "A", "valor": "CASTILLA"})
    assert "puente" not in r


def test_cargar_vp_robustez_degrada_sin_lanzar(monkeypatch):
    # Si get_engine() falla (BD no disponible), NUNCA lanza -> set vacío -> ningún relabel.
    R._VP_ROBUSTEZ = None
    def _boom():
        raise RuntimeError("BD no disponible")
    monkeypatch.setattr(R, "get_engine", _boom)
    assert R._cargar_vp_robustez() == set()
    R._VP_ROBUSTEZ = None   # limpiar el cache para no afectar otros tests


# --- ejecutor._etiqueta_nivel: el texto usa "la Vicepresidencia" SOLO si puente=True --------------
def test_etiqueta_usa_vicepresidencia_si_puente():
    assert E._etiqueta_nivel("gerencia", {"puente": True}) == "la Vicepresidencia"


def test_etiqueta_normal_sin_puente():
    assert E._etiqueta_nivel("gerencia", {}) == "la Gerencia"
    assert E._etiqueta_nivel("campo", {}) == "el Campo"
    assert E._etiqueta_nivel("vicepresidencia", {}) == "la Vicepresidencia"


# --- GUARDA DE REGRESIÓN contra BD real: CPV/GAN/GXO excluidos, GOR incluido ----------------------
# Mismo error que la auditoría de este plan cometió en su primer borrador (revisar solo
# rob_vicepresidencia sin cruzar rob_gerencia) — verificado 2026-08-03: rob_vicepresidencia ∩
# rob_gerencia = {CPV, GAN, GXO}. Se saltan con gracia si Postgres no está disponible.
def _engine_o_skip():
    try:
        from app.core.db import get_engine
        import sqlalchemy as sa
        eng = get_engine()
        with eng.connect() as c:
            c.execute(sa.text("SELECT 1"))
        return eng
    except Exception:
        pytest.skip("Postgres no disponible")


def test_bd_real_gor_incluido_cpv_gan_gxo_excluidos():
    _engine_o_skip()
    R._VP_ROBUSTEZ = None   # forzar recarga (no reusar cache de otro test)
    vps = R._cargar_vp_robustez()
    assert "GOR" in vps, "GOR (caso insignia, sin ambigüedad) debe estar"
    for amb in ("CPV", "GAN", "GXO"):
        assert amb not in vps, f"{amb} es AMBIGUO (también rob_gerencia) — NO debe relabelearse"
    R._VP_ROBUSTEZ = None   # limpiar para no afectar otros tests
```

---

## 5. Orden de ejecución

1. Prerequisitos + baseline (§2).
2. Editar `cuantificar/resolver.py` (§4.1 — RS1, luego RS2).
3. Editar `cuantificar/ejecutor.py` (§4.2 — EJ1, luego los 4 call-sites de EJ2 en orden N1→N2→N3→N4).
4. Crear `test_puente_gerencia_vp.py` (§4.3).
5. Validaciones (§6).

---

## 6. Validaciones (comando → esperado)

Desde `...\INGESTA\Rep_Prod\backend`.

**V1 — compilación:**
```
uv run python -m py_compile app/features/consulta_v2/cuantificar/resolver.py app/features/consulta_v2/cuantificar/ejecutor.py
```
Esperado: sin salida, exit 0.

**V2 — import:**
```
uv run python -c "from app.features.consulta_v2.cuantificar.resolver import _marcar_puente, _cargar_vp_robustez; from app.features.consulta_v2.cuantificar.ejecutor import _etiqueta_nivel; print('OK')"
```
Esperado: `OK`.

**V3 — tests nuevos:**
```
uv run pytest tests/test_puente_gerencia_vp.py -q
```
Esperado: **`8 passed`** si hay Postgres local disponible (7 puros + 1 contra BD real), o
**`7 passed, 1 skipped`** si no lo hay (`_engine_o_skip` degrada con gracia). En este entorno de
desarrollo SÍ hay Postgres local (ya usado en R1/R3 sin problema — es una query ligera, no el
backend+LLM que prohíbe la regla de RAM) → se espera `8 passed`.

**V4 — no regresión:**
```
uv run pytest tests/test_cuantificar.py tests/test_cuantificar_rango.py -q
```
Esperado: mismo resumen del baseline de §2 (0 fallos nuevos).

**V5 — 🔑 humo contra BD real + GUARDA DE REGRESIÓN (única validación de este plan que toca la BD).
Esta es la validación MÁS IMPORTANTE del plan: confirma que los 3 códigos ambiguos (CPV/GAN/GXO)
quedan EXCLUIDOS — el error real que la propia auditoría cometió en su primer barrido (revisar solo
`rob_vicepresidencia` sin cruzar `rob_gerencia`) y que este plan corrigió antes de codificar:**
```
uv run python -c "
from app.features.consulta_v2.cuantificar.resolver import _cargar_vp_robustez
vps = sorted(_cargar_vp_robustez())
print(vps)
assert 'GOR' in vps, 'GOR (el caso insignia, sin ambiguedad) debe estar'
for amb in ('CPV', 'GAN', 'GXO'):
    assert amb not in vps, f'{amb} es AMBIGUO (tambien rob_gerencia) -- NO debe relabelearse'
print('OK: GOR incluido, CPV/GAN/GXO excluidos (guarda de regresion del error de auditoria)')
"
```
Esperado: imprime la lista completa (informativa — puede variar si `map_campo_robustez` cambia, eso
NO es un fallo) y termina con `OK: GOR incluido, CPV/GAN/GXO excluidos...`. Si CUALQUIERA de los 3
asserts de exclusión falla, **es una regresión real** (el relabel volvería a ser demasiado amplio,
igual que el error que esta misma auditoría encontró y corrigió) — detenerse y reportar.

**V6 — humo end-to-end (resolver real + etiqueta):**
```
uv run python -c "
from app.features.consulta_v2.cuantificar.resolver import resolver_unico
from app.features.consulta_v2.cuantificar.ejecutor import _etiqueta_nivel
r = resolver_unico('GOR')
print(r)
print(_etiqueta_nivel(r.get('nivel'), r))
"
```
Esperado: `r` incluye `'puente': True` y la 2ª línea imprime `la Vicepresidencia`.

Si cualquier validación falla: **detenerse** y reportar comando + salida completa.

---

## 7. Fuera de alcance (explícito)

- **`respuesta_analizar.py`** (ocurrencia hermana, `alcance = f"el {nivel} {ent_valor}"`): mismo
  resolver, mismo bug potencial, pero exposición mucho menor (solo alimenta el prompt del LLM, que
  tiene instrucción de no repetirlo verbatim). El hallazgo 2.3 solo nombra a Cuantificar. Deuda
  anotada, no se toca.
- **Frase-puente educativa** ("Lo que en el reporte diario llamas..."): decisión explícita de NO
  añadirla — Cuantificar no rastrea la palabra que el usuario usó para calificar la entidad (a
  diferencia de Jerarquizar), así que construirla arriesgaría atribuirle al usuario un término que no
  usó. Se prefiere la corrección silenciosa de la etiqueta.
- **El código ambiguo GAN**: sigue mostrando "la Gerencia GAN" (comportamiento sin cambios) — no hay
  evidencia inequívoca en robustez para decidir en qué sentido corregirlo.
- **Los 6 códigos sin match en robustez** (GAO/GAR/GDA/GEE/GLH/GNS): sin cambios, por la misma razón.
- **Verificación en navegador / LLM en vivo / deploy 139**: las hace el usuario en el servidor de
  pruebas tras el commit.

---

## 8. Cierre (commit + documentación)

Commit sugerido:
```
fix(consulta_v2): Cuantificar rotula correctamente gerencia=vicepresidencia (R2)

cuantificar/resolver.py: nuevo _marcar_puente(), marca puente=True cuando un nivel resuelto
'gerencia' es EXCLUSIVAMENTE una vicepresidencia en core.map_campo_robustez (8 codigos
verificados: DFL/GAA/GCT/GOR/GPA/GRM/GTA/PRP, via diferencia de conjuntos vps-gers, calculada en
vivo). Excluye los 3 ambiguos CPV/GAN/GXO (VP y gerencia real distintas en robustez -- hallazgo de
la propia verificacion de este plan, que en su primer borrador solo habia detectado GAN) y los 6
sin match (terceros fuera del universo de robustez).

cuantificar/ejecutor.py: nuevo _etiqueta_nivel() usa "la Vicepresidencia" en el texto cuando hay
puente, en los 4 niveles (N1-N4). El nivel de QUERY no cambia (sigue filtrando dim_fuente.gerencia)
-- es una correccion PURAMENTE de texto/display.

Decision de diseño: SIN frase-puente educativa (a diferencia de respuesta_jerarquizar.py) -- Cuantificar
no rastrea la palabra que el usuario uso para calificar la entidad, asi que esa frase arriesgaria
atribuirle un termino no usado. Correccion silenciosa de la etiqueta en su lugar.

Cierra 2.3 de HALLAZGO_clasificador_conteo_jerarquia.md. respuesta_analizar.py tiene la misma
ocurrencia (menor exposicion, solo alimenta el prompt del LLM) -- documentada, no se toca.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

Tras el commit: bitácora + marcar 2.3 del `HALLAZGO_clasificador_conteo_jerarquia.md` como resuelto
(el hallazgo completo — 2.1+2.2+2.3 — queda cerrado entre este plan y el Plan A).
