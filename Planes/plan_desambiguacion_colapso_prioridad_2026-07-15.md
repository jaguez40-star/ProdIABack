# Plan ejecutable — Desambiguación por **COLAPSO** (feature `consulta`) · v2 (auditado, alcance reducido)

> Ejecutable por un agente externo sin contexto. Rutas absolutas, código completo, decisiones cerradas.
> **v2**: tras auditoría se REDUJO el alcance a lo provablemente coherente (colapso de redundantes + ask
> deduplicado). El "default campo + zoom" se DIFIERE (ver §0, F-C1). **Backend-only.** NO commitear.

---

## 0. Auditoría previa (§0.2 CLAUDE.md) — hallazgos

### Datos del catálogo (BD `daily_report_prod`, 265 nombres, 152 colisiones)
| Clase | Cant. | % | Política v2 |
|---|---:|---:|---|
| **REDUNDANTE** (mismo `fuente_id` en todos los niveles) | 106 | 70% | **Colapsar → auto-responder** ✅ este plan |
| **GENUINA · sets fuente distintos** (anidadas) | 45 | 30% | **Ask deduplicado** (default+zoom DIFERIDO) |
| **GENUINA · dual A/B (filial)** — solo `HOCOL` | 1 | 1% | **Preguntar** (nunca colapsa) |

### 🔴 F-C1 (crítico) — el cálculo es "ciego al nivel"
`ejecutar()` (Fase 3) calcula llamando `desempeno(entidad=<nombre>)`, y `desempeno` resuelve por **OR
sobre 6 columnas** (`nombre OR campo OR grupo1 OR activos OR gerencia OR operador = :e`) → **ignora el
nivel** y agrega la **UNIÓN** de todos los `fuente_id` con ese nombre. Por tanto:
- Un **zoom** campo→área→pozo mostraría **el mismo número** (la unión) en todos los niveles → falso.
- Un **default "campo"** mostraría la cifra de la **unión (área)**, no del campo → engañoso.

**Por qué Rubiales sí es coherente:** es redundante (los 4 niveles = 1 `fuente_id`), así que **unión ==
nivel**. El colapso solo dispara cuando todos los candidatos comparten el `fuente_id` → el número por
nombre coincide exactamente con el del nivel resuelto. **Coherente por construcción** (y coincide con el
tablero, que también usa `desempeno(name)`).

**Decisión (escalada y aceptada):** este plan hace **solo el colapso** (70%) + ask deduplicado. El
"default campo + zoom" (30% genuino) queda **DIFERIDO** porque exige volver **(nivel, nombre)-aware** todo
el pipeline (`resolver → huella → desempeno → tablero → chat`) — cambio arquitectónico coordinado, plan aparte.

### Otros hallazgos incorporados
- **H1 — norm() consistente:** el colapso usa el mismo `norm()` del resolver para las claves (acentos plegados).
- **H2 — nunca cruzar espacios:** el colapso jamás fusiona rama A↔B ni `vicepresidencia`↔`fuente`
  (preserva el dual `HOCOL`). Garantizado por `clave_fisica`.
- **H3 — cache por proceso:** el mapa de conjuntos se cachea al primer uso (como `_INDEX`); se reconstruye
  al reiniciar. Deuda conocida y aceptada (idéntica al índice actual).
- **H4 — coherencia probada del colapso:** el colapso dispara ⇔ un único conjunto de `fuente_id` ⇔ la
  respuesta por nombre (`desempeno`) == la del nivel resuelto. No introduce ninguna incoherencia nueva.

---

## 1. Objetivo

Cuando `resolver()` devuelve **varias identidades** para un nombre:
1. **auto** — todas apuntan al mismo `fuente_id` (redundante) → **auto-resolver** (label = nivel canónico,
   `campo` si está). Elimina el 70% de las desambiguaciones (Rubiales y 105 más).
2. **ask** — hay más de un conjunto físico (anidadas genuinas, o dual A/B) → **preguntar, pero deduplicado
   por grupo** (Chichimene 4→~3 botones; Hocol sigue con 2). Comportamiento honesto; sin over-claim.

**Sin cambios de frontend.** `auto` devuelve `status:"completo"` (render existente) y `ask` devuelve
`status:"pendiente"` (render existente). Aditivo puro sobre la máquina.

---

## 2. Decisiones cerradas

| ID | Decisión |
|----|----------|
| **D-D1** | Colapso = fusionar candidatos con **idéntico** conjunto de `fuente_id` (clave física). |
| **D-D2** | Representante canónico del grupo: prioridad `campo(5) > area(4) > activo(3) > gerencia(2) > fuente/pozo(1)`. |
| **D-D3** | El colapso NUNCA cruza rama A/B ni `vice`↔`fuente` (H2). `HOCOL` sigue preguntando. |
| **D-D4** | Si tras colapsar queda **1** grupo → auto-resolver. Si quedan **≥2** → preguntar (deduplicado). |
| **D-D5** | **DIFERIDO:** "default campo + zoom" para genuinas anidadas → requiere calc (nivel,nombre)-aware (F-C1). |
| **D-D6** | Aditivo y backend-only: no cambia el contrato de salida (`completo`/`pendiente` ya existen), ni el frontend. |

---

## 3. Prerequisitos

- Backend INGESTA en `:8088`; PostgreSQL `daily_report_prod` con datos.
- Línea base (ANTES): `POST /consulta/preguntar {"texto":"producción de Rubiales","conversation_id":"x"}` → hoy `status:"pendiente"` (4 opciones). Tras el plan → `completo`.

---

## 4. Inventario de archivos

Raíz = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.

| # | Archivo | Acción |
|---|---------|--------|
| B1 | `INGESTA\Rep_Prod\backend\app\features\consulta\resolver.py` | **EDIT** — cache de conjuntos `fuente_id` + `clave_fisica()`. |
| B2 | `INGESTA\Rep_Prod\backend\app\features\consulta\maquina.py` | **EDIT** — helpers de política + reemplazo del branch de colisión. |
| B3 | `INGESTA\Rep_Prod\backend\tests\test_consulta_desambiguacion.py` | **NUEVO** — unit tests de la política (sin BD, `clave_fn` inyectada). |

**Prohibido editar:** `extraccion.py`, `ejecucion.py`, `analisis\api.py`, `routes\api.py`, frontend,
CSS, `main.html`. **No hay cambios de frontend en este plan.**

---

## 5. Especificación

### B1 — EDIT `resolver.py`

Añadir al final del archivo (después de `termino_candidato`, línea 78):

```python

# ============================================================================
# Colapso de identidades: conjunto FÍSICO de fuente_id por (nivel, valor).
# Fusiona candidatos de una colisión que apuntan al MISMO fuente_id (colisión
# redundante por auto-nombrado, ej. RUBIALES = campo=area=activo=fuente).
# Usa el MISMO norm() del índice (H1). Cache por proceso (H3), como _INDEX.
# ============================================================================
_FUENTE_COL = {"fuente": "nombre", "campo": "campo", "area": "grupo1",
               "activo": "activos", "gerencia": "gerencia", "operador": "operador"}
_FUENTE_SETS = None   # {col: {nombre_norm: frozenset(fuente_id)}}


def _build_fuente_sets():
    global _FUENTE_SETS
    fs = {col: {} for col in _FUENTE_COL.values()}
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text(
            "SELECT fuente_id, nombre, campo, grupo1, activos, gerencia, operador "
            "FROM core.dim_fuente")).all()
    for r in rows:
        fid = r[0]
        for col, val in zip(_FUENTE_COL.values(), r[1:]):
            if val and str(val).strip():
                fs[col].setdefault(norm(val), set()).add(fid)
    _FUENTE_SETS = {col: {k: frozenset(v) for k, v in d.items()} for col, d in fs.items()}
    return _FUENTE_SETS


def _get_fuente_sets():
    return _FUENTE_SETS if _FUENTE_SETS is not None else _build_fuente_sets()


def clave_fisica(ident: dict):
    """Clave de identidad FÍSICA para agrupar candidatos de una misma colisión.
    - rama B (filial): espacio propio -> nunca se fusiona con rama A (preserva el dual Hocol, H2).
    - vicepresidencia: espacio propio (no es fuente_id).
    - niveles de fuente: por el CONJUNTO de fuente_id -> dos niveles con el mismo set se fusionan."""
    nivel, rama, valor = ident["nivel"], ident.get("rama"), ident["valor"]
    k = norm(valor)
    if rama == "B":
        return ("B", k)
    if nivel == "vicepresidencia":
        return ("VICE", k)
    col = _FUENTE_COL.get(nivel)
    if not col:
        return (nivel, k)
    return ("F", _get_fuente_sets()[col].get(k, frozenset()))
```

> `sa`, `get_engine`, `norm` ya están importados en la cabecera de `resolver.py` (líneas 1-3). No añadir imports.

### B2 — EDIT `maquina.py`

**Edición 1 — import de `clave_fisica`.** Línea 4, reemplazar:
```python
from app.features.consulta.resolver import resolver, buscar_en_texto, termino_candidato
```
por:
```python
from app.features.consulta.resolver import resolver, buscar_en_texto, termino_candidato, clave_fisica
```

**Edición 2 — helpers de política.** Insertar **justo después** de `_fijar_resuelta` (después de la
línea 51 `return intent`, antes de `def preguntar`):
```python

# --- Desambiguación por colapso (política determinista, D-D1..D-D4) ---
# Prioridad canónica para elegir el representante de un grupo colapsado (campo gana).
_PRIORIDAD = {"campo": 5, "area": 4, "activo": 3, "gerencia": 2, "fuente": 1, "pozo": 1}


def _rep(grupo):
    """Representante canónico de un grupo colapsado (mayor prioridad; campo gana)."""
    return max(grupo, key=lambda i: _PRIORIDAD.get(i["nivel"], 0))


def _resolver_colision(ids, clave_fn):
    """Política determinista. Devuelve (modo, rep, reps):
      ("auto", rep, reps)  -> 1 solo conjunto físico (redundante) -> auto-resolver.
      ("ask", None, reps)  -> >=2 conjuntos físicos -> preguntar (deduplicado por grupo).
    reps = un representante por grupo físico (deduplicado)."""
    grupos = {}
    for i in ids:
        grupos.setdefault(clave_fn(i), []).append(i)
    reps = [_rep(g) for g in grupos.values()]
    if len(reps) == 1:
        return ("auto", reps[0], reps)
    return ("ask", None, reps)
```

**Edición 3 — reemplazar el branch de colisión de `preguntar`.** Reemplazar el bloque `else:` (líneas 81-86):
```python
    else:
        # colisión → S2: emitir botones (una opción por identidad)
        intent["pendiente"] = {"slot": "nivel",
            "opciones": [{"id": f"{i['nivel']}::{i['valor']}", "label": _NIVEL_LABEL.get(i['nivel'], i['nivel']),
                          "nivel": i["nivel"], "rama": i["rama"], "valor": i["valor"]} for i in ids]}
        _guardar(cid, intent)
```
por:
```python
    else:
        # colisión → política de colapso (D-D1..D-D4). Redundante -> auto-resolver; genuina/dual -> preguntar (dedup).
        modo, rep, reps = _resolver_colision(ids, clave_fisica)
        if modo == "auto":
            intent["avisos"].append(
                f"Interpreté «{slots['entidad']}» como {_NIVEL_LABEL.get(rep['nivel'], rep['nivel'])}.")
            _fijar_resuelta(intent, rep)
        else:  # ask (genuina anidada o dual A/B) → preguntar por GRUPO (deduplicado)
            intent["pendiente"] = {"slot": "nivel",
                "opciones": [{"id": f"{r['nivel']}::{r['valor']}", "label": _NIVEL_LABEL.get(r['nivel'], r['nivel']),
                              "nivel": r["nivel"], "rama": r["rama"], "valor": r["valor"]} for r in reps]}
            _guardar(cid, intent)
```

> `responder` y `_salida` **NO se tocan** (no hay zoom ni `alternativas` en v2).

### B3 — NUEVO `test_consulta_desambiguacion.py`

Crear `INGESTA\Rep_Prod\backend\tests\test_consulta_desambiguacion.py`:
```python
from app.features.consulta.maquina import _resolver_colision, _rep


def _id(nivel, valor, rama="A"):
    return {"nivel": nivel, "rama": rama, "valor": valor}


def test_redundante_colapsa_a_campo():
    ids = [_id("fuente", "RUBIALES"), _id("campo", "RUBIALES"),
           _id("area", "RUBIALES"), _id("activo", "RUBIALES")]
    clave = lambda i: ("F", frozenset({1}))            # todos el mismo fuente_id
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "auto" and rep["nivel"] == "campo" and len(reps) == 1


def test_genuino_anidado_pregunta():
    ids = [_id("campo", "CHICHIMENE"), _id("area", "CHICHIMENE"), _id("fuente", "CHICHIMENE")]
    sets = {"campo": frozenset({1, 2}), "area": frozenset({1, 2, 3, 4}), "fuente": frozenset({7})}
    clave = lambda i: ("F", sets[i["nivel"]])
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and rep is None and len(reps) == 3


def test_area_activo_se_fusionan_reduce_botones():
    # area y activo comparten set -> 1 grupo; campo aparte -> quedan 2 opciones (no 3)
    ids = [_id("area", "X"), _id("activo", "X"), _id("campo", "X")]
    sets = {"area": frozenset({1, 2}), "activo": frozenset({1, 2}), "campo": frozenset({1, 2, 3})}
    clave = lambda i: ("F", sets[i["nivel"]])
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and len(reps) == 2


def test_dual_ab_pregunta():
    ids = [_id("operador", "HOCOL", "A"), _id("filial", "HOCOL", "B")]
    clave = lambda i: ("F", frozenset({9})) if i["rama"] == "A" else ("B", "hocol")
    modo, rep, reps = _resolver_colision(ids, clave)
    assert modo == "ask" and rep is None and len(reps) == 2


def test_rep_prioriza_campo():
    assert _rep([_id("fuente", "X"), _id("campo", "X"), _id("area", "X")])["nivel"] == "campo"
    assert _rep([_id("area", "Y"), _id("fuente", "Y")])["nivel"] == "area"   # sin campo -> area
```

---

## 6. Orden de ejecución

1. **V0** (pre-check): `producción de Rubiales` responde `status:"pendiente"` (línea base).
2. B1 → B2 → B3.
3. **V1**, **V2** (pytest). Luego **V3–V5** (round-trip). Reportar tabla PASS/FAIL. **No commitear.**

---

## 7. Reglas no negociables

- **H2 — el colapso nunca cruza espacios** (rama A↔B, vice↔fuente). `clave_fisica` lo garantiza; no
  alterarla. `HOCOL` debe seguir preguntando.
- **norm() único (H1):** usar el `norm` del resolver para todas las claves (ya está en `clave_fisica`).
- **No tocar** `responder`, `_salida`, ni ningún archivo fuera de B1/B2/B3. **Cero cambios de frontend.**
- **Aditivo:** solo cambia el branch de colisión de `preguntar`; los estados `completo`/`pendiente` y sus
  contratos quedan idénticos.
- **Frontera LLM/Python:** el LLM solo extrae; la política de colapso es Python determinista.

---

## 8. Validaciones (comando → esperado)

| ID | Acción | Esperado |
|----|--------|----------|
| **V0** | (antes de editar) `POST /consulta/preguntar {"texto":"producción de Rubiales","conversation_id":"v0"}` | `status:"pendiente"` (4 opciones) — línea base. |
| **V1** | `cd INGESTA\Rep_Prod\backend; uv run pytest tests/test_consulta_desambiguacion.py -q` | **5 passed.** |
| **V2** | `cd INGESTA\Rep_Prod\backend; uv run pytest -q` | Verde (sin regresión de `test_consulta_estado.py` ni `test_consulta_ejecucion.py`). |
| **V3** | `POST /consulta/preguntar {"texto":"producción de Rubiales","conversation_id":"v3"}` | `status:"completo"`, `intent.nivel:"campo"`, `intent.avisos` con "Interpreté", `respuesta.aplica:true`. **El % debe coincidir con `GET /analisis/desempeno?entidad=RUBIALES`.** |
| **V4** | `POST /consulta/preguntar {"texto":"producción de Chichimene","conversation_id":"v4"}` | `status:"pendiente"`, opciones **deduplicadas** (≈3, no 4; área/activo fusionados). |
| **V5** | `POST /consulta/preguntar {"texto":"producción de Hocol","conversation_id":"v5"}` | `status:"pendiente"` con 2 opciones (operador / filial) — **dual preservado**. |
| **V6** | Navegador, pestaña Consulta: "producción de Rubiales" | Responde **directo** con la cifra (sin los 4 botones). Hocol y Chichimene siguen preguntando. 0 errores de consola. (Sin cache-buster: no hubo cambios de frontend.) |

---

## 9. Fuera de alcance (DIFERIDO)

- **"Default campo + zoom reversible"** para genuinas anidadas (Chichimene, Castilla, Cusiana, Apiay): requiere
  hacer el cálculo **(nivel, nombre)-aware** en TODO el pipeline (`resolver`+`_huella`+`desempeno`+tablero+chat)
  para que el número del campo ≠ el de la unión y el zoom sea real (F-C1). **Plan aparte, coordinado con el tablero.**
- **Ranking por volumen/probabilidad numérica:** no aplica (la política es colapso + prioridad canónica).
- **Invalidación en caliente del cache** (sin reiniciar): no se implementa (H3).
- **Fusión de duales A/B:** explícitamente NO (H2).
```
