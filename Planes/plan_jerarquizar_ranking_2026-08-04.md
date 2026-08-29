# Plan ejecutable — Motor Q v2 · JERARQUIZAR · RANKING ESTRUCTURAL

> **Modo:** ejecución literal por un agente sin contexto previo del repo. Todo lo necesario está aquí.
> **Fecha:** 2026-08-04 · **Planner:** Claude · **v2 AUDITADO — flujo §0.2 aplicado al plan mismo
> (2 rondas, 5 defectos corregidos, 4 verificados ejecutando código contra el repo/BD real).**
> Hermano del `plan_cuantificar_n5_ranking_2026-08-04.md` (ya implementado, commit `74c19e1`), pero
> en OTRO grupo y con OTRO eje. **Lee §11 (registro de auditoría) ANTES de codificar** — explica por
> qué el código es así y qué se probó que pasa si se hace de otro modo.

---

## 0. COBERTURA (§0.2 — prohibido reducir alcance en silencio)

Rankea entidades de la jerarquía por **conteo estructural** (nº de pozos, gerencias, activos, campos).
Es un eje **ortogonal** al ranking de Cuantificar N5 (que rankea por magnitud de PRODUCCIÓN):

| Eje | Grupo | Rankea por | Fuente |
|---|---|---|---|
| N5 (ya hecho) | Cuantificar | magnitud de producción (bbl/MSCF) | `fact_produccion_mes_ecp` |
| **este plan** | **Jerarquizar** | **conteo estructural** (pozos/gerencias/…) | `map_campo_robustez` + `ops.wells_attributes` |

| Forma | v1 (este plan) | Motivo |
|---|---|---|
| **campo** por nº de **pozos** ("campos con más pozos", "campos más grandes") | ✅ ENTREGA | 1 query `GROUP BY field` en ops |
| **vicepresidencia** por nº de **gerencias/activos/campos** ("qué VP tiene más gerencias") | ✅ ENTREGA | mapas ya en memoria (`vp_ger`/`vp_activos`/`vp_campos`) |
| **gerencia** por nº de **activos/campos** | ✅ ENTREGA | `ger_activos`/`ger_campos` (en memoria) |
| **activo** por nº de **campos** | ✅ ENTREGA | `act_campos` (en memoria) |
| **activo/gerencia/VP** por nº de **POZOS** | ⛔ DECLINA honesto | Doble conteo: un uwi vive en >1 campo (747 casos); sumar conteos por campo mentiría. Requiere un `COUNT(DISTINCT uwi)` por nivel con join field→nivel. v2. |
| combos sin sentido ("campo con más gerencias") | ⛔ DECLINA honesto | `gerencias` no es subdivisión de un campo |

**Ventaja sobre N5:** en N5 se DIFIRIÓ el nivel gerencia porque `dim_fuente.gerencia` está contaminado
(level-shift S28). **Aquí NO aplica:** Jerarquizar se apoya en `core.map_campo_robustez`, la jerarquía
**canónica** (`rob_gerencia` = POE/PPC reales) → rankear gerencias y VPs es limpio y correcto.

**Techo honesto (opuesto a N5):** robustez solo modela ECP-operado. El ranking estructural **excluye
terceros** (QUIFA/Caño Limón no tienen conteo). Se declara: *"sobre N … ECP-operados"*. (En N5 los
terceros SÍ entraban; aquí no. Misma disciplina, dirección opuesta.)

---

## 1. CONTEXTO

**Sub-proyecto:** `INGESTA\Rep_Prod\backend\` (FastAPI, `uv`). El grupo JERARQUIZAR del Motor Q v2 vive
en `backend\app\features\consulta_v2\respuesta_jerarquizar.py` y se apoya en `core.map_campo_robustez`
(reconciliación robustez↔reporte, S28) + `robustez_v02.ops.wells_attributes` (grano pozo, S32/R3).

**Datos verificados contra la BD dev (2026-08-04) — criterios de aceptación, no ilustración:**
- `core.map_campo_robustez`: **139 filas · 80 rob_field · 46 activos · 24 gerencias · 15 VPs** (81 es_ecp).
- **VPs por nº de gerencias:** `VRC 3 · GAA/GPA/GRM/GCH/GOR/GTA/VAO 2 · resto 1`.
- **campos por nº de pozos** (`ops.wells_attributes`): `RUBIALES 2131 · LA CIRA 1944 · CASABE 904 ·
  INFANTAS 888 · MORICHE 680 …` (universo ops: 118 fields, 13.482 uwi).
- Clasificación HOY: `"qué campo tiene más pozos"`/`"qué activo tiene más campos"` → ya `jerarquizar`
  (patrón de conteo R3) pero caen en la ruta de entidad única → piden "¿sobre cuál?".
  `"cuáles son los campos con más pozos"`, `"qué VP tiene más gerencias"`, `"campos más grandes"` →
  clasifican **None** hoy (sin patrón).

**Regla madre:** *Python calcula y ordena; el LLM SOLO redacta el intro cordial.* La lista es VERBATIM.

**Diferencia clave con N5 (más simple):** JERARQUIZAR **no tiene panel** — `responder_cordial` devuelve
un **string** y `maquina_q` hace `if r: mensaje = r` (panel queda None). → **no hay frontend que tocar.**

---

## 2. OBJETIVO

**Responden correctamente (Motor v2):**

| # | Pregunta | Resultado |
|---|---|---|
| 1 | "¿Cuáles son los campos con más pozos?" | top-5 campos por pozos, desc |
| 2 | "¿Qué vicepresidencia tiene más gerencias?" | top-1 VP por nº de gerencias (VRC=3) |
| 3 | "¿Cuáles son los campos más grandes (número de pozos)?" | top-5 campos por pozos |
| 4 | "¿Qué campo tiene más pozos?" | top-1 (RUBIALES 2131) |
| 5 | "¿Qué activo tiene más campos?" | top-1 activo por nº de campos |

**Declinan honesto:**

| # | Pregunta | Motivo |
|---|---|---|
| 6 | "¿Qué activo tiene más pozos?" | pozos por encima de campo → diferido (doble conteo) |
| 7 | "¿Qué campo tiene más gerencias?" | combo sin sentido |

---

## 3. PREREQUISITOS

- **Comandos de backend** desde `INGESTA\Rep_Prod\backend` con `PYTHONPATH`:
  ```bash
  cd "C:/APLICACIONES/ProdIA/12112025_prodIA/12112025_prodIA/INGESTA/Rep_Prod/backend"
  PYTHONPATH="$(pwd)" uv run python -m pytest tests/test_conteo_jerarquia.py -q
  ```
  Sin `PYTHONPATH` → `ModuleNotFoundError: No module named 'app'`.
- BD dev poblada: `core.map_campo_robustez` (get_engine) y `robustez_v02.ops.wells_attributes`
  (get_ops_engine). Conexiones en `INGESTA/Rep_Prod/.env` (`DATABASE_URL` / `OPS_DATABASE_URL`).
- **REGLA DE RAM (no negociable):** en dev SOLO chequeos estáticos (`py_compile`, `pytest`, golden,
  consultas SQL puntuales aisladas). **NO** levantar backend, **NO** Ollama, **NO** navegador. El
  runtime/LLM los verifica el usuario en el servidor de pruebas tras `push`.
- **NO tocar `consulta/`** (v1 congelada). Todo vive en `consulta_v2/`.

---

## 4. INVENTARIO DE ARCHIVOS

`BE = ...\INGESTA\Rep_Prod\backend`

| # | Acción | Archivo | Nota |
|---|---|---|---|
| A1 | MODIFICA | `BE\app\features\consulta_v2\respuesta_jerarquizar.py` | detector + calc + cuerpo + fork |
| A2 | MODIFICA | `BE\app\features\consulta_v2\config\patrones_grupo.yaml` | 4 patrones en **`grupos.jerarquizar` + `patrones_anclados`** (§11·D9: NO en precedencia_maxima) |
| A3 | **NUEVO** | `BE\tests\test_jerarquizar_ranking.py` | tests |
| A4 | MODIFICA | `BE\app\features\consulta_v2\golden\clasificacion_golden.yaml` | 3 casos jerarquizar (regresión) |

> **`maquina_q.py` NO se toca** (jerarquizar ya devuelve string, panel None). **Sin frontend.**

---

## 5. ESPECIFICACIÓN

### 5.1 · A2 — `patrones_grupo.yaml` (enrutar el ranking estructural a Jerarquizar)

🔑 **Los 4 patrones van en `grupos.jerarquizar` (NO en `precedencia_maxima`) y TAMBIÉN en
`patrones_anclados`.** Las dos decisiones están verificadas ejecutando código (§11 · D9 y D10); no
las cambies sin repetir esa verificación:

- **`grupos.jerarquizar`, no `precedencia_maxima`**: `precedencia_maxima` gana sobre TODOS los grupos,
  incluido `analizar`. Verificado que *"¿por qué los campos con más pozos producen menos?"* ya matchea
  `cuantificar` **y** `analizar` → en `grupos` la `precedencia_colision` (analizar > cuantificar >
  jerarquizar) le da correctamente a **analizar** esa pregunta causal; en `precedencia_maxima` se la
  robaría el ranking. Además se verificó que las 3 preguntas objetivo **no matchean ningún grupo
  existente** (`NINGUNO`) → sin colisión, jerarquizar gana solo. Menos radio de daño, mismo resultado.
- **`patrones_anclados` es OBLIGATORIO, no una optimización**: `nivel_dominio("que vicepresidencia
  tiene mas gerencias")` devuelve **`None`** (medido) — sin anclaje, el filtro de dominio la manda a
  **`desconocido`/OUT**, no "al LLM". La pregunta simplemente no funcionaría. Ver §11 · D10.

**(a)** En `grupos:` → `jerarquizar:` (lista), **añade al final** (después de `'JERARQUIA'`):
```yaml
    # RANKING ESTRUCTURAL (2026-08-04). Ordena entidades de la jerarquía por CONTEO (pozos/gerencias/
    # activos/campos) — eje ortogonal al N5 de cuantificar, que rankea por PRODUCCIÓN. Exigen DOBLE
    # señal estructural (sustantivo de nivel + sustantivo de conteo, o "más grandes/pequeños"), así
    # que no matchean producción ni off-topic. Verificado 2026-08-04 contra los 95 casos del golden
    # (clasificacion + cuantificar): 0 secuestros. Van en `grupos` y NO en precedencia_maxima a
    # propósito: así `analizar` conserva precedencia en preguntas causales ("¿por qué los campos con
    # más pozos producen menos?"), que es lo correcto.
    - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+(CON|DE)\s+(MAS|MENOS|MAYOR|MENOR)\s+(POZOS?|CAMPOS?|GERENCIAS?|ACTIVOS?)'
    - '(QUE|CUAL(ES)?)\s+(VICEPRESIDENCIA|GERENCIA|ACTIVO|CAMPO)S?\s+TIENE[N]?\s+(MAS|MENOS|MAYOR|MENOR)\s+(GERENCIAS?|ACTIVOS?|CAMPOS?|POZOS?)'
    - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+MAS\s+(GRANDES?|PEQUEN[OA]S?|CHIC[OA]S?)'
    - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+(CON|DE)\s+(MAYOR|MENOR)\s+(NUMERO|CANTIDAD)\s+DE'
```

**(b)** En `patrones_anclados:` (lista), **añade al final** las MISMAS 4 cadenas, **byte-idénticas**
(`es_anclado` compara por igualdad exacta de string — copia-pega, no reescribas):
```yaml
  # Ranking estructural (2026-08-04): doble señal estructural = dominio autoconfirmado. ANCLAJE
  # OBLIGATORIO: sin él, "¿qué vicepresidencia tiene más gerencias?" cae en desconocido/OUT
  # (nivel_dominio devuelve None para ese texto — medido 2026-08-04), no solo "escala al LLM".
  - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+(CON|DE)\s+(MAS|MENOS|MAYOR|MENOR)\s+(POZOS?|CAMPOS?|GERENCIAS?|ACTIVOS?)'
  - '(QUE|CUAL(ES)?)\s+(VICEPRESIDENCIA|GERENCIA|ACTIVO|CAMPO)S?\s+TIENE[N]?\s+(MAS|MENOS|MAYOR|MENOR)\s+(GERENCIAS?|ACTIVOS?|CAMPOS?|POZOS?)'
  - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+MAS\s+(GRANDES?|PEQUEN[OA]S?|CHIC[OA]S?)'
  - '(CAMPOS?|ACTIVOS?|GERENCIAS?)\s+(CON|DE)\s+(MAYOR|MENOR)\s+(NUMERO|CANTIDAD)\s+DE'
```

> ⚠️ **NO tocar** `precedencia_maxima`, `precedencia_colision` ni ninguna cadena existente. Solo AÑADIR.

### 5.2 · A1 — `respuesta_jerarquizar.py` (detector + cálculo + fork)

**(a) Import** — el módulo ya importa `get_ops_engine`; verifica que esté (`from app.core.db import
get_engine, get_ops_engine`). Ya está en el archivo (línea ~25). No añadas imports nuevos.

**(b) Constantes + helpers de ranking** — añádelos **después** de `_contar_pozos` (≈ línea 224) y
**antes** de `_cuerpo`:

```python
# ═══════════════════════════════════════════════════════════════════════════════════════════════
# RANKING ESTRUCTURAL (2026-08-04, plan_jerarquizar_ranking_2026-08-04.md)
# Ordena entidades por conteo (pozos/gerencias/activos/campos). Eje ORTOGONAL al N5 de Cuantificar
# (que rankea por producción). DETERMINISTA salvo el intro cordial. Reusa los mapas de _cargar().
# ═══════════════════════════════════════════════════════════════════════════════════════════════
# 🔑 Vocabulario SIMÉTRICO (defecto del v1: tenía GRANDE/GRANDES pero ningún antónimo → "los campos
# más pequeños" devolvía None y moría en "¿sobre cuál?").
# ⚠️ VERIFICADO 2026-08-04: norm() PLIEGA la ñ → N ('pequeños' -> 'PEQUENOS', 'Caño' -> 'CANO').
# Por eso aquí SOLO van las formas con N. Escribir "PEQUEÑOS" sería código muerto (nunca matchea).
_RANK_SUP = ("MAS", "MAYOR", "MENOS", "MENOR", "GRANDE", "GRANDES",
             "PEQUENO", "PEQUENOS", "PEQUENA", "PEQUENAS", "CHICO", "CHICOS")
# Dirección ASCENDENTE (el "menos"). Incluye los antónimos de tamaño: "los campos más pequeños" =
# los de MENOS pozos. Si el texto trae "MAS" y "PEQUENOS", manda el antónimo (ver _rank_detectar).
_RANK_ASC = ("MENOS", "MENOR", "PEQUENO", "PEQUENOS", "PEQUENA", "PEQUENAS", "CHICO", "CHICOS")
_RANK_NIVEL = {"CAMPO": "campo", "CAMPOS": "campo", "ACTIVO": "activo", "ACTIVOS": "activo",
               "GERENCIA": "gerencia", "GERENCIAS": "gerencia", "VP": "vicepresidencia",
               "VICE": "vicepresidencia", "VICEPRESIDENCIA": "vicepresidencia",
               "VICEPRESIDENCIAS": "vicepresidencia"}
_RANK_CONTEO = {"POZO": "pozos", "POZOS": "pozos", "CAMPO": "campos", "CAMPOS": "campos",
                "ACTIVO": "activos", "ACTIVOS": "activos", "GERENCIA": "gerencias",
                "GERENCIAS": "gerencias"}
# subject -> (conteo por defecto para "grande", conteos SOPORTADOS en v1)
_RANK_MATRIZ = {
    "campo": ("pozos", {"pozos"}),
    "activo": ("campos", {"campos"}),                       # pozos DIFERIDO (doble conteo)
    "gerencia": ("campos", {"campos", "activos"}),          # pozos DIFERIDO
    "vicepresidencia": ("gerencias", {"gerencias", "activos", "campos"}),   # pozos DIFERIDO
}
# (subject, conteo) -> clave del mapa en memoria (data[...]). Solo conteos estructurales.
_RANK_MAP = {
    ("activo", "campos"): "act_campos",
    ("gerencia", "campos"): "ger_campos",
    ("gerencia", "activos"): "ger_activos",
    ("vicepresidencia", "gerencias"): "vp_ger",
    ("vicepresidencia", "activos"): "vp_activos",
    ("vicepresidencia", "campos"): "vp_campos",
}
_RANK_PLURAL = {"campo": "campos", "activo": "activos", "gerencia": "gerencias",
                "vicepresidencia": "vicepresidencias"}
# Contracción correcta para el mensaje de combo inválido ("de el campo" ✗ / "del campo" ✓).
_RANK_DE = {"campo": "del campo", "activo": "del activo", "gerencia": "de la gerencia",
            "vicepresidencia": "de la vicepresidencia"}
_RANK_POZOS_DIFERIDO = ("El conteo de pozos por activo/gerencia/vicepresidencia llega en una próxima "
                        "fase: un mismo pozo puede estar asignado a más de un campo, así que sumar los "
                        "conteos por campo daría un número inflado. Sí puedo rankear campos por pozos, o "
                        "activos/gerencias/vicepresidencias por número de campos, activos o gerencias.")


def _rank_detectar(texto):
    """Reconoce la FORMA de un ranking estructural (determinista, sin BD). dict o None.
    dict = {subject, conteo, asc, top_n, soportados, default}. Exige un SUPERLATIVO y un sustantivo
    de NIVEL antes de él (el sujeto). El conteo = sustantivo tras el superlativo, o el default del
    nivel ("campos más grandes" -> pozos)."""
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto or "").split()) if p]
    sup_i = next((i for i, w in enumerate(palabras) if w in _RANK_SUP), None)
    if sup_i is None:
        return None
    # SUJETO = sustantivo de nivel MÁS CERCANO antes del superlativo.
    subj, subj_tok = None, None
    for i in range(sup_i - 1, -1, -1):
        if palabras[i] in _RANK_NIVEL:
            subj, subj_tok = _RANK_NIVEL[palabras[i]], palabras[i]
            break
    if subj is None:
        return None
    # CONTEO = primer sustantivo de conteo tras el superlativo; si no hay -> default del nivel.
    conteo = next((_RANK_CONTEO[palabras[i]] for i in range(sup_i + 1, len(palabras))
                   if palabras[i] in _RANK_CONTEO), None)
    default, soportados = _RANK_MATRIZ[subj]
    if conteo is None:
        conteo = default
    # 🔑 asc = CUALQUIER palabra ascendente del texto, no solo la del índice sup_i. "los campos más
    # pequeños" trae MAS (sup_i, descendente) y PEQUENOS (ascendente): manda el antónimo, si no
    # devolvería los MÁS grandes ante una pregunta por los más pequeños (fallo silencioso).
    asc = any(w in _RANK_ASC for w in palabras)
    top_n = 1 if (subj_tok and not subj_tok.endswith("S")) else 5   # singular -> 1, plural -> 5
    return {"subject": subj, "conteo": conteo, "asc": asc, "top_n": top_n,
            "soportados": soportados, "default": default}


def _rank_canon(data, knorm, nivel):
    """Nombre canónico de una entidad a partir de su clave normalizada + nivel (via idx)."""
    for niv, canon in data["idx"].get(knorm, ()):
        if niv == nivel:
            return canon
    return knorm


def _rank_pozos_por_campo(data):
    """{rob_field: nº de pozos} desde ops.wells_attributes, sobre los rob_field de map_campo_robustez
    (universo ECP reconciliado). None si ops no está disponible (degradación con gracia, como
    _contar_pozos). El rob_field == field == nombre del campo ECP (verificado)."""
    fields = sorted({r["rob_field"] for r in data["campo_row"].values() if r.get("rob_field")})
    if not fields:
        return None
    try:
        with get_ops_engine().connect() as c:
            rows = c.execute(sa.text(
                "SELECT field, COUNT(DISTINCT uwi) FROM ops.wells_attributes "
                "WHERE field = ANY(:fs) GROUP BY field"), {"fs": fields}).all()
    except Exception:
        return None
    return {(f or "").strip(): int(n) for f, n in rows if f}


def _rank_conteo_estructural(subject, conteo, data):
    """{nombre_canónico: nº de hijos} desde los mapas ya en memoria (act_campos/ger_*/vp_*).
    Sin BD, sin doble conteo (los hijos son distintos por construcción del mapa)."""
    key = _RANK_MAP.get((subject, conteo))
    src = data.get(key) or {}
    return {_rank_canon(data, knorm, subject): len(set(children)) for knorm, children in src.items()}


def _rank_calcular(rk, data):
    """Contrato de ranking (aplica=True) o {aplica:False, texto}."""
    subj, conteo = rk["subject"], rk["conteo"]
    if conteo not in rk["soportados"]:
        if conteo == "pozos" and subj != "campo":
            return {"aplica": False, "texto": _RANK_POZOS_DIFERIDO}
        # Gramática: _ART da "el Campo" → "de el campo" es incorrecto. _RANK_DE da la contracción.
        return {"aplica": False, "texto": (
            f"No puedo rankear {_RANK_PLURAL[subj]} por número de {conteo}: {conteo} no es una "
            f"subdivisión {_RANK_DE[subj]}.")}
    if subj == "campo":                          # conteo == "pozos"
        conteos = _rank_pozos_por_campo(data)
        if conteos is None:
            return {"aplica": False, "texto": (
                "El conteo de pozos requiere la base de robustez (robustez_v02), que no está "
                "disponible ahora; no puedo construir ese ranking.")}
    else:
        conteos = _rank_conteo_estructural(subj, conteo, data)
    conteos = {k: v for k, v in conteos.items() if k}
    if not conteos:
        return {"aplica": False, "texto": f"No tengo datos para rankear {_RANK_PLURAL[subj]} por {conteo}."}
    items = sorted(conteos.items(), key=lambda kv: (kv[1], kv[0]), reverse=not rk["asc"])
    top = items[:rk["top_n"]]
    return {"aplica": True, "subject": subj, "conteo": conteo, "asc": rk["asc"],
            "items": [{"pos": i + 1, "entidad": k, "n": v} for i, (k, v) in enumerate(top)],
            "total": len(conteos)}


def _rank_cuerpo(res):
    """Cuerpo VERBATIM del ranking (el LLM no lo toca)."""
    subj_pl = _RANK_PLURAL[res["subject"]]
    n = len(res["items"])
    encab = "El" if n == 1 else "Los"
    subj_txt = subj_pl[:-1] if n == 1 else subj_pl        # campos->campo, vicepresidencias->vicepresidencia
    dir_txt = "menos" if res["asc"] else "más"
    piezas = " · ".join(f"{it['pos']}) {it['entidad']} ({it['n']})" for it in res["items"])
    linea = f"{encab} {subj_txt} con {dir_txt} {res['conteo']}: {piezas}."
    linea += f" Sobre {res['total']} {subj_pl} ECP-operados con datos en la fuente oficial (robustez)."
    if res["conteo"] == "pozos":
        linea += " El conteo de pozos es de REGISTRO (atemporal), no de producción del mes."
    return linea


def _rank_oferta(res):
    top1 = res["items"][0]["entidad"] if res["items"] else None
    return (f"ver la estructura de {top1} o rankear por otra medida" if top1
            else "rankear por otra medida")
```

**(c) Fork en `responder_cordial`** — es la PRIMERA acción, antes de `r = _resolver(texto)`:

```python
def responder_cordial(texto: str, usuario=None):
    """B: envuelve los hechos con marco cordial dinámico (LLM). Hechos VERBATIM. None si no hay
    tabla (maquina_q deja 'en construcción'); si no hay entidad, pide una sin envolver."""
    # ── RANKING ESTRUCTURAL (eje ortogonal) ──────────────────────────────────────────────────
    # Antes del resolver de entidad única: "los campos con más pozos" no nombra UNA entidad (los
    # sustantivos de nivel están en _STOP) → moriría en __noent__ ("¿sobre cuál?").
    rk = _rank_detectar(texto)
    if rk is not None:
        try:
            data = _cargar()
        except Exception:
            return None                          # sin tabla → 'en construcción' (igual que _resolver)
        res = _rank_calcular(rk, data)
        if not res.get("aplica"):
            return res["texto"]                  # declina honesto, sin envolver (como _NOENT)
        body = _rank_cuerpo(res)
        return _envolver(f"un ranking de {_RANK_PLURAL[res['subject']]} por número de {res['conteo']}",
                         "ranking", body, _rank_oferta(res), usuario)
    r = _resolver(texto)
    if r is None:
        return None
    niv, canonical, puente, data = r
    if niv == "__noent__":
        return _NOENT
    body = _con_puente(niv, canonical, puente, _cuerpo(niv, canonical, data))
    return _envolver(canonical, niv, body, _ofertas(niv, canonical, data), usuario)
```

**(d) Fork en `responder`** (determinista, para tests/fallback — SIN LLM) — antes de `r = _resolver`:

```python
def responder(texto: str):
    """Determinista (hechos), SIN LLM — para tests y como fallback. None si no hay tabla."""
    rk = _rank_detectar(texto)
    if rk is not None:
        try:
            data = _cargar()
        except Exception:
            return None
        res = _rank_calcular(rk, data)
        return res["texto"] if not res.get("aplica") else _rank_cuerpo(res)
    r = _resolver(texto)
    if r is None:
        return None
    niv, canonical, puente, data = r
    if niv == "__noent__":
        return _NOENT
    return _con_puente(niv, canonical, puente, _cuerpo(niv, canonical, data))
```

> **No modifiques nada más** de esos dos métodos: la ruta de entidad única queda intacta debajo del fork.

### 5.3 · A4 — `clasificacion_golden.yaml`

El campo es **`esperado:`** (verificado 2026-08-04 leyendo el archivo — el v1 de este plan decía
"ajusta el nombre", ambigüedad inaceptable; ya está resuelto). Añade al final del bloque
`# ---- jerarquizar ----` estos 4 casos, tal cual:

```yaml
- pregunta: "¿Cuáles son los campos con más pozos?"
  esperado: jerarquizar
- pregunta: "¿Qué vicepresidencia tiene más gerencias?"
  esperado: jerarquizar
- pregunta: "¿Cuáles son los campos más grandes?"
  esperado: jerarquizar
- pregunta: "¿Qué activo tiene más campos?"
  esperado: jerarquizar
```

---

## 6. ORDEN DE EJECUCIÓN

1. **A1** editar `respuesta_jerarquizar.py` → `py_compile`.
2. **A2** patrones YAML (`grupos.jerarquizar` + `patrones_anclados` — nunca `precedencia_maxima`).
3. **A3** tests + **A4** golden.
4. **Validaciones §8** (V-COMPILE, V-DETECT, V-CALC, V-CLAS, V-GOLDEN, V-REGR).
   🔴 **Si alguna falla, DETENTE y reporta.**
5. `git add -A` → `commit` → `push`. El usuario verifica en el servidor de pruebas.

---

## 7. REGLAS NO NEGOCIABLES

1. **Python calcula y ordena; el LLM SOLO el intro** (vía `_envolver`/`respuesta_base`).
2. **NO tocar** `consulta/` (v1), `maquina_q.py`, `dim_fuente`-based code, `precedencia_colision`,
   ni las cadenas EXISTENTES de `patrones_grupo.yaml` (solo AÑADIR).
3. **NO degradar en silencio.** Combos diferidos (pozos por activo/gerencia/VP) y sin sentido →
   rechazo honesto explícito.
4. **Solo ECP-operado, declarado** ("sobre N … ECP-operados"). Terceros no entran (no tienen jerarquía
   robustez); es correcto, pero se dice.
5. **Pozos = conteo de registro, atemporal** — se rotula, no se vende como actividad del mes.
6. **Degradación con gracia:** si `ops` (robustez_v02) no está, el ranking de pozos declina honesto;
   los rankings estructurales (campos/activos/gerencias, desde map_campo_robustez) siguen funcionando.
7. **Las cadenas de `patrones_anclados` = byte-idénticas** a las de `grupos.jerarquizar`
   (`es_anclado` compara strings por igualdad exacta). Si no, V-CLAS saldrá `anclado=False`.
8. **Solo chequeos estáticos en dev** (regla de RAM).

---

## 8. VALIDACIONES (comando → resultado esperado)

Desde `BE`, con `PYTHONPATH="$(pwd)"`.

**V-COMPILE**
```bash
uv run python -m py_compile app/features/consulta_v2/respuesta_jerarquizar.py
```
→ exit 0.

**V-DETECT** — `A3` (`tests/test_jerarquizar_ranking.py`), puro sin BD, sobre `_rank_detectar`:

| Texto | Esperado |
|---|---|
| `"cuales son los campos con mas pozos"` | `subject=campo, conteo=pozos, asc=False, top_n=5` |
| `"que vicepresidencia tiene mas gerencias"` | `subject=vicepresidencia, conteo=gerencias, top_n=1` |
| `"cuales son los campos mas grandes"` | `subject=campo, conteo=pozos` (default) |
| `"que campo tiene mas pozos"` | `subject=campo, conteo=pozos, top_n=1` |
| `"que activo tiene mas campos"` | `subject=activo, conteo=campos, top_n=1` |
| `"cual gerencia tiene menos activos"` | `subject=gerencia, conteo=activos, asc=True` |
| `"cuantos pozos tiene Castilla"` | `None` (sin superlativo → no es ranking; lo maneja la ruta R3) |
| `"a que activo pertenece Cajua"` | `None` |
| `"cuales son los campos mas pequenos"` | `subject=campo, conteo=pozos, asc=True` ← antónimo manda sobre "MAS" |
| `"campos con mayor numero de pozos"` | `subject=campo, conteo=pozos, asc=False` |

🔴 **Guarda de no-regresión del fork (obligatoria):** `_rank_detectar` debe devolver `None` para
**las 10 preguntas jerarquizar del golden** (`clasificacion_golden.yaml`). Verificado 2026-08-04:
0 falsos positivos. Escribe el test que itera esas preguntas del YAML y afirma `None` — si el
detector empieza a secuestrar la ruta de entidad única, este test lo caza.

**V-CALC** — contra BD; `_engine_o_skip` (patrón de `tests/test_puente_gerencia_vp.py`). Nota: el
ranking de pozos necesita `get_ops_engine`; si ops no está, ese sub-test hace `skip`.
- `responder("¿qué vicepresidencia tiene más gerencias?")` → string que empieza por "El vicepresidencia
  con más gerencias:" y contiene "VRC (3)" en la 1ª posición.
- `responder("¿cuáles son los campos con más pozos?")` → contiene "1) RUBIALES (2131)" y "ECP-operados"
  y "REGISTRO (atemporal)". (skip si ops no disponible.)
- `responder("¿qué activo tiene más pozos?")` → contiene "próxima fase" (diferido, NO calcula).
- `responder("¿qué campo tiene más gerencias?")` → contiene "no es una subdivisión" (combo inválido).
- `_rank_calcular` con `direccion` asc → orden ascendente (`items[0].n <= items[-1].n`).

**V-CLAS**
```bash
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as f, es_anclado; \
[print(q[:40],'->',f(q)[0], 'anclado=' + str(es_anclado(f(q)[1]))) for q in [ \
'cuales son los campos con mas pozos', \
'que vicepresidencia tiene mas gerencias', \
'cuales son los campos mas grandes', \
'que activo tiene mas campos', \
'cuales son los campos mas pequenos']]"
```
→ los 5 imprimen `jerarquizar` **y `anclado=True`**.
🔴 `anclado=True` no es cosmético: sin él *"qué vicepresidencia tiene más gerencias"* cae en
`desconocido`/OUT (`nivel_dominio` = None para ese texto, medido). Si algún caso sale
`anclado=False`, la cadena de `patrones_anclados` no es byte-idéntica a la de `grupos` — corrígela.

**V-CAUSAL** (que `analizar` conserve precedencia; es la razón de NO usar precedencia_maxima):
```bash
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as f; \
print(f('por que los campos con mas pozos producen menos')[0])"
```
→ imprime `analizar` (no `jerarquizar`).

**V-CLASREGR** (que los patrones nuevos NO roben preguntas de N5/producción):
```bash
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as f; \
[print(q[:44],'->',f(q)[0]) for q in [ \
'cuales son los 5 campos que mas crudo producen', \
'que campo produce la mayor cantidad de crudo', \
'que campos se quedaron mas cortos vs presupuesto', \
'top 3 activos por produccion de gas en mayo', \
'cuantos pozos tiene Castilla']]"
```
→ los primeros 4 imprimen `cuantificar`; el 5º `jerarquizar` (por el patrón de conteo R3, no por los nuevos).

**V-GOLDEN**
```bash
uv run python app/features/consulta_v2/golden/run_golden.py
```
→ ≥90% (gate del clasificador); los 3 casos nuevos en verde.

**V-MEM** (D15 — la memoria conversacional NO se ensucia tras un ranking):
```bash
uv run python -c "import app.features.consulta_v2.respuesta_jerarquizar as J; \
[print(q[:40],'ctx=',J.contexto(q)) for q in [ \
'cuales son los campos con mas pozos','que vicepresidencia tiene mas gerencias']]"
```
→ ambos `ctx= None`. (Si algún día devolviera una entidad, `maquina_q` guardaría memoria de una
entidad que el usuario NUNCA nombró y el siguiente turno corto respondería sobre ella.)

**V-REGR** (no regresión de jerarquizar + clasificador; **captura el baseline ANTES de editar**):
```bash
uv run python -m pytest tests/test_conteo_jerarquia.py tests/test_consulta_v2_clasificador.py \
  tests/test_puente_gerencia_vp.py -q
```
→ 0 fallos nuevos vs baseline.

---

## 9. FUERA DE ALCANCE

Ranking de pozos por activo/gerencia/VP (doble conteo → v2) · ranking por producción (es N5, ya hecho)
· universo de 118 fields de ops (v1 = los 80 reconciliados) · cumplimiento/EBITDA · memoria
conversacional del ranking · paridad gemma4 del intro y verificación en navegador (servidor de pruebas).

---

## 10. RESUMEN PARA APROBACIÓN

1. **Qué:** ranking ESTRUCTURAL en Jerarquizar — ordena campos/activos/gerencias/VPs por conteo
   (pozos, gerencias, activos, campos). Eje ortogonal al N5 de producción.
2. **Cómo:** detector + calc + fork en `respuesta_jerarquizar.py` (reusa `_contar_pozos` y los mapas de
   `_cargar()`; **1 sola query nueva** para campo-pozos) + **4 patrones en `grupos.jerarquizar` +
   `patrones_anclados`** (NO en `precedencia_maxima` — ver §11 · D9).
3. **Sin frontend, sin `maquina_q`:** jerarquizar ya devuelve string (panel None).
4. **Honestidad:** solo ECP-operado (declarado) · pozos = conteo de registro (rotulado) · combos
   diferidos/inválidos declinan honesto · degradación con gracia si robustez_v02 no está.
5. **Riesgo bajo y medido:** las calculadoras ya existen; **0 secuestros sobre los 95 casos del
   golden**, **0 falsos positivos** del fork sobre las preguntas jerarquizar, `analizar` conserva
   la causal, y la memoria conversacional no se ensucia (`contexto()` = None).

---

## 11. REGISTRO DE AUDITORÍA (decisiones cerradas, verificadas contra BD)

| # | Punto | Evidencia | Decisión |
|---|---|---|---|
| **D1** | ¿Dónde va? | El ranking estructural usa la jerarquía canónica de robustez, no producción. | En **Jerarquizar** (no Cuantificar): eje ortogonal al N5. |
| **D2** | Gerencia/VP: ¿viable aquí? | En N5 se difirió gerencia por el level-shift de `dim_fuente`. Jerarquizar usa `rob_gerencia` canónico (POE/PPC). | **Sí, limpio.** Lo que N5 no pudo, Jerarquizar sí. |
| **D3** | Pozos por activo/gerencia/VP | 747 uwi viven en >1 campo → sumar conteos por campo infla. | **DIFERIDO** (declina honesto). Solo campo×pozos (1 query directa). |
| **D4** | Universo de campo-pozos | ops tiene 118 fields; map_campo_robustez reconcilia 80. | **80 reconciliados** (coherente con el resto de Jerarquizar), declarado. |
| **D5** | Métrica de "más grande" | ambiguo. | campo→**pozos**, activo→**campos**, gerencia→**campos**, VP→**gerencias** (el hijo natural). |
| **D6** | Clasificación sin robar a N5 | Simulado 2026-08-04: los 3 patrones atrapan las 7 objetivo, 0 de las 7 de regresión ("campos QUE más crudo" usa QUE, no CON/DE). | precedencia_maxima + anclados; V-CLASREGR lo blinda. |
| **D7** | Techo ECP | robustez solo modela ECP-operado (81/139). | El ranking excluye terceros; se **declara** "ECP-operados". Opuesto a N5 (que los incluía). |
| **D8** | ¿Frontend? | jerarquizar devuelve string, `maquina_q` hace `if r: mensaje=r`, panel None. | **Sin frontend, sin tocar maquina_q.** Más simple que N5. |

### Ronda 2 — defectos del v1 de ESTE plan, corregidos (todos verificados ejecutando código)

| # | Defecto del v1 | Evidencia (medida 2026-08-04) | Corrección en v2 |
|---|---|---|---|
| **D9** | 🔴 **Los patrones estaban en `precedencia_maxima`** — que gana sobre TODOS los grupos, incluido `analizar`. Una pregunta causal como *"¿por qué los campos con más pozos producen menos?"* habría sido secuestrada por el ranking. | Esa pregunta ya matchea `cuantificar` **y** `analizar`; las 3 objetivo no matchean **ningún** grupo existente (`NINGUNO`) → en `grupos` no hay colisión y jerarquizar gana solo. | **Movidos a `grupos.jerarquizar`.** `precedencia_colision` (analizar > cuantificar > jerarquizar) le devuelve la causal a `analizar`. Menos radio de daño, mismo resultado. Guarda: **V-CAUSAL**. |
| **D10** | 🔴 **El anclaje estaba justificado como "para no escalar al LLM"** — mecanismo equivocado y consecuencia subestimada. | `nivel_dominio("que vicepresidencia tiene mas gerencias")` = **`None`** (no `estructural`). Con patrón no-anclado y sin entidad → el filtro manda a **`desconocido`/OUT**. La pregunta **no funcionaría en absoluto**. | Anclaje declarado **OBLIGATORIO** con su razón real; V-CLAS ahora exige `anclado=True` y explica qué significa si falla. |
| **D11** | **Vocabulario asimétrico:** `_RANK_SUP` traía `GRANDE/GRANDES` sin ningún antónimo → *"los campos más pequeños"* devolvía `None` y moría en *"¿sobre cuál?"*. Además `asc` se leía SOLO del token en `sup_i`, así que aun añadiendo el antónimo, "MÁS pequeños" habría dado `asc=False` → **los más grandes ante una pregunta por los más pequeños** (fallo silencioso). | Traza de `_rank_detectar` sobre "cuales son los campos mas pequenos". | Añadidos `PEQUEN*`/`CHICO*` a `_RANK_SUP` y `_RANK_ASC`; `asc` pasa a mirar **todo** el texto (el antónimo manda sobre "MAS"). +1 patrón de clasificación y 2 casos en V-DETECT. |
| **D12** | **Código muerto latente:** el v1 iba a listar variantes con `Ñ` literal (`PEQUEÑOS`). | `norm('pequeños')` = `'PEQUENOS'`, `norm('Caño')` = `'CANO'` → **norm pliega la ñ**. Una entrada con `Ñ` nunca matchearía. | Solo formas con `N`, con la razón anotada en el código para que nadie las "arregle" de vuelta. |
| **D13** | **Ambigüedad inaceptable para un Executor:** el v1 decía *"ajusta el nombre del campo (`grupo`/`esperado`) al que ya use el YAML"* — el mismo pecado que ya se corrigió en el plan de N5 (su D4). | El archivo usa **`esperado:`**. | Casos golden escritos completos y literales, sin decisiones delegadas. |
| **D14** | **Bug de redacción en texto de cara al usuario:** `_ART.get(subj).lower()` producía *"no es una subdivisión **de el campo**"*. | `_ART['campo']` = `"el Campo"` → `.lower()` = `"el campo"`. | Nuevo `_RANK_DE` con la contracción correcta (`del campo` / `de la gerencia`). |
| **D15** | **Suposición sin verificar** (riesgo de memoria contaminada): el v1 afirmaba que `contexto()` no se ensucia tras un ranking, sin probarlo. | `contexto()` = **None** en las 4 preguntas de ranking (`_detectar` no halla entidad). | Confirmado → `maquina_q` sigue sin tocarse; se añade **V-MEM** como guarda explícita en vez de suposición. |
