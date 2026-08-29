# PLAN EJECUTABLE — Objetivo Secundario **v1**: Slot-filling conversacional (esqueleto que camina)

> **Modo:** Executor (ejecutar al pie de la letra; si algo no coincide con el código real, DETENERSE y escalar).
> **Fecha:** 2026-07-08 · **Diseño base:** `DISENO_CAPA_CONVERSACIONAL.md` (§1, §2 D1–D7, §7.6, §8) — LEERLO ANTES.
> **Alcance:** SOLO **v1** (1 entidad · 1 intent · caso Rubiales/Hocol). G1–H4 = fuera de alcance (v2/v3).
> **Cobertura de entregables:** 6 piezas (golden set, fixtures, resolver, máquina de estados, endpoints, UI).

---

## 0. Auditoría del plan (flujo profesional §0.2 — Mapeo → Auditoría → Diagnóstico → Reformulación)

Plan auditado contra el **código real** (no de memoria). Hallazgos y su resolución:

| # | Hallazgo | Severidad | Resolución |
|---|---|---|---|
| **I1** | El plan ponía "Consulta" como **sub-módulo de Análisis** (botón junto a `__anShowCatalogo`, reusando `__anArea`/`charts-display-area`) → **viola D2** (pestaña propia del riel). | 🔴 Bloqueante | **§5.M reformulado**: Consulta = **tab de 1er nivel** (array `TABS` + HTML del riel + `renderPanelBody` + `renderViewer` + funciones propias con `__cnArea`). El binding de clic ya es genérico (L439-441) → engancha solo. |
| **I2** | V4 hardcodeaba `opcion_id:"campo::RUBIALES"`; el casing del valor viene de la BD → frágil. | 🟠 Menor | **V4 reformulada**: usar el `id` que devuelve `/preguntar`, no hardcodear. |
| **I3** | Registro de router en `main.py`. | ✅ OK | Verificado: patrón `include_router` (L23-27); añadir tras `analisis_router`. |
| **I4** | Proxy Flask (`request`, `get_json`, prefix `/api`, POST). | ✅ OK | Verificado: `request` importado (L5), `get_json()` usado (L223…), `api_bp` prefix `/api`. Snippet 5.L válido. |
| **I5** | `_huella` para rama B (filial) usa datos ECP del operador, no el consolidado de la filial. | 🟡 Nota | Aceptado como **simplificación v1** (huella básica = grano diario ECP; filial pura → `aplica:false`). |
| **I6** | Al cambiar de tab y volver, el viewer se re-renderiza → conversación se reinicia. | 🟡 Nota | Aceptado en v1 (el `conversation_id` persiste en backend por TTL). |
| **I7** | Regla §0.2 "Tablas: entrada N → salida M". | N/A | El plan **no modela hojas ni toca ETL** (solo lee) → la regla de cobertura de tablas no aplica. Cobertura de **entregables** = 6 piezas. |

**Mapeo verificado contra la BD:** `RUBIALES`→4 niveles · `HOCOL`→dual (filial B + operador A) · `GOR`→gerencia
· `pg_trgm`/`unaccent` disponibles NO instaladas · `qwen2.5:3b` presente. **Sin incoherencias con los pipelines
existentes** (fundación Análisis + Ingesta + Control intactos; solo se AÑADE un feature backend y un tab de riel).

---

## 1. Contexto

**ProdIA** (Flask :8020, vanilla JS) + **INGESTA** (FastAPI :8000, Postgres `daily_report_prod`). La pestaña
**Análisis** del MultiTab Shell ya tiene la **fundación** (Catálogo, Densidad, Cobertura — endpoints
`GET /analisis/{catalogo,densidad,cobertura}` en `INGESTA/Rep_Prod/backend/app/features/analisis/api.py`,
proxied por Flask en `routes/api.py`, UI en `static/js/multitab_shell.js`).

Este plan añade el **Objetivo Secundario**: una pestaña **Consulta** que, dado texto en español, hace
**slot-filling** hasta producir un **intent validado** — y **PARA ahí** (D1: NO ejecuta la consulta; la
ejecución es Fase 3, fuera de alcance).

**Regla madre (D4):** *Python calcula, el LLM solo concluye.* El LLM solo **extrae** slots (Paso 1) y
opcionalmente **redacta**; **Python** es dueño del catálogo, el match, la desambiguación y toda decisión.
Ver §8 del diseño para el schema del intent y la máquina de estados (transcritos abajo).

**Rutas absolutas (Windows):**
- Repo raíz (Flask): `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
- Backend INGESTA (FastAPI): `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\`
- LLM dev: Ollama en `http://localhost:11434`, modelo **`qwen2.5:3b`** (verificado presente).

---

## 2. Objetivo

Entregar el **esqueleto que camina** (walking skeleton) end-to-end para UNA pregunta de UNA entidad:

```
Usuario escribe "producción de Rubiales" en la pestaña Consulta
 → LLM extrae {entidad:"RUBIALES", …}
 → Python resuelve RUBIALES → [campo, activo, gerencia, fuente]  (colisión → pendiente)
 → UI muestra BOTONES (Campo / Activo / Gerencia / Fuente)
 → usuario hace clic en "Campo"
 → Python REANUDA → intent COMPLETO {entidad:RUBIALES, nivel:campo, …} → PARA (no ejecuta)
 → UI muestra el intent validado + huella básica de la entidad
```

**Definición de LISTO (verificable):** las validaciones V1–V7 de §8 pasan.

---

## 3. Prerequisitos (verificar ANTES de tocar código)

1. **Backends arriba.** FastAPI :8000 y Flask :8020 respondiendo:
   ```bash
   curl -s -o /dev/null -w "fastapi=%{http_code}\n" http://localhost:8000/analisis/catalogo
   curl -s -o /dev/null -w "flask=%{http_code}\n"   http://localhost:8020/api/analisis/catalogo
   ```
   Esperado: `fastapi=200`, `flask=200`. Si no, lanzar los backends (ver §7.4 abajo).
2. **Ollama con qwen2.5:3b:**
   ```bash
   curl -s http://localhost:11434/api/tags | python -c "import sys,json;print([m['name'] for m in json.load(sys.stdin)['models']])"
   ```
   Esperado: incluye `qwen2.5:3b`.
3. **Patrón de feature FastAPI:** leer `INGESTA/Rep_Prod/backend/app/features/analisis/api.py` y
   `INGESTA/Rep_Prod/backend/app/main.py` (registro del router). El nuevo feature `consulta` sigue EXACTAMENTE
   ese patrón (`APIRouter(prefix="/consulta")`, `from app.core.db import get_engine`, registro en `main.py`
   ANTES del `StaticFiles` mount).
4. **Patrón de proxy Flask:** leer `routes/api.py` (blueprint `api_bp`, `INGESTA_API_URL`, manejo 502).
5. **Patrón UI:** leer en `static/js/multitab_shell.js` el riel de pestañas (~L520–560, botones
   `__anShow*`) y cómo se monta el contenido de Análisis. La pestaña Consulta se agrega igual.

---

## 4. Inventario de archivos (crear / modificar)

| # | Archivo | Acción |
|---|---|---|
| A | `INGESTA/Rep_Prod/backend/app/features/consulta/__init__.py` | **crear** (vacío) |
| B | `INGESTA/Rep_Prod/backend/app/features/consulta/normaliza.py` | **crear** — plegado de acentos (Python) |
| C | `INGESTA/Rep_Prod/backend/app/features/consulta/resolver.py` | **crear** — índice invertido + resolver |
| D | `INGESTA/Rep_Prod/backend/app/features/consulta/extraccion.py` | **crear** — LLM qwen + JSON backstop |
| E | `INGESTA/Rep_Prod/backend/app/features/consulta/maquina.py` | **crear** — schema intent + estados |
| F | `INGESTA/Rep_Prod/backend/app/features/consulta/api.py` | **crear** — endpoints `/consulta/*` |
| G | `INGESTA/Rep_Prod/backend/app/main.py` | **modificar** — registrar router |
| H | `INGESTA/Rep_Prod/backend/app/features/consulta/golden/extraccion_golden.yaml` | **crear** — golden set (LLM) |
| I | `INGESTA/Rep_Prod/backend/app/features/consulta/golden/estado_fixtures.yaml` | **crear** — fixtures de estado |
| J | `INGESTA/Rep_Prod/backend/app/features/consulta/golden/run_golden.py` | **crear** — corre el golden set |
| K | `INGESTA/Rep_Prod/backend/tests/test_consulta_estado.py` | **crear** — pytest fixtures (sin LLM) |
| L | `routes/api.py` | **modificar** — 2 proxies `/api/consulta/*` |
| M | `static/js/multitab_shell.js` | **modificar** — pestaña Consulta |
| N | `INGESTA/Rep_Prod/db/migrations/007_pg_trgm.sql` | **crear** — `CREATE EXTENSION` (paso separable) |

---

## 5. Especificación (código de referencia)

### 5.B `normaliza.py` — plegado de acentos en Python (sin depender de la extensión `unaccent`)
```python
import unicodedata

def norm(s: str) -> str:
    """UPPER + trim + colapsar espacios + plegar acentos/ñ (NFKD sin combining)."""
    s = unicodedata.normalize("NFKD", (s or "").strip().upper())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())
```
> `Ñ→N`, `Á→A`, etc. Se aplica IGUAL al texto del usuario y al catálogo (o el match exacto falla).

### 5.C `resolver.py` — índice invertido (cache al arranque) + resolver
```python
import sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta.normaliza import norm

# nivel -> (query de valores distintos, rama)  · rama A = ECP, B = filial
_LEVELS = [
    ("fuente",          "SELECT DISTINCT nombre   FROM core.dim_fuente          WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "A"),
    ("campo",           "SELECT DISTINCT campo    FROM core.dim_fuente          WHERE NULLIF(TRIM(campo),'')    IS NOT NULL", "A"),
    ("area",            "SELECT DISTINCT grupo1   FROM core.dim_fuente          WHERE NULLIF(TRIM(grupo1),'')   IS NOT NULL", "A"),
    ("activo",          "SELECT DISTINCT activos  FROM core.dim_fuente          WHERE NULLIF(TRIM(activos),'')  IS NOT NULL", "A"),
    ("gerencia",        "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
    ("operador",        "SELECT DISTINCT operador FROM core.dim_fuente          WHERE NULLIF(TRIM(operador),'') IS NOT NULL", "A"),
    ("vicepresidencia", "SELECT DISTINCT codigo   FROM core.dim_vicepresidencia WHERE NULLIF(TRIM(codigo),'')   IS NOT NULL", "A"),
    ("filial",          "SELECT DISTINCT nombre   FROM core.dim_empresa         WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "B"),
]

_INDEX = None   # {nombre_norm: [ {nivel, rama, valor} ]}

def build_index():
    """Construye el índice invertido UNA vez. Idempotente."""
    global _INDEX
    idx = {}
    eng = get_engine()
    with eng.connect() as c:
        for nivel, sql, rama in _LEVELS:
            for (val,) in c.execute(sa.text(sql)):
                k = norm(val)
                if not k:
                    continue
                idx.setdefault(k, []).append({"nivel": nivel, "rama": rama, "valor": (val or "").strip()})
    _INDEX = idx
    return idx

def get_index():
    return _INDEX if _INDEX is not None else build_index()

def resolver(texto: str) -> list[dict]:
    """Capa 1 (exacta): devuelve la lista de identidades para el texto normalizado. [] si no hay match.
    NOTA v1: Capa 2 (fuzzy pg_trgm) es un paso posterior separable (§5 paso 8)."""
    return list(get_index().get(norm(texto), []))
```
> **Verificado contra la BD:** `RUBIALES` → 4 identidades (campo/activo/gerencia/fuente, rama A);
> `HOCOL` → 2 (filial B + operador A) → dual; `GOR` → 1 (gerencia A); `CASTILLA` → 4.

### 5.D `extraccion.py` — Paso 1 (LLM qwen) con backstop de JSON
```python
import json, re, urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "qwen2.5:3b"   # dev. Prod = gemma4:latest (parametrizar por env en despliegue).

_PROMPT = """Eres un extractor. Del texto del usuario devuelve SOLO un JSON con estos campos
(usa null si no se menciona):
{{"entidad": <nombre|null>, "nivel": <"vicepresidencia"|"gerencia"|"activo"|"area"|"campo"|"pozo"|"filial"|null>,
  "producto": <"aceite"|"agua"|"gas"|"blancos"|null>, "periodo": <texto|null>,
  "agregacion": <"promedio_diario"|"acumulado"|null>}}
Texto: {texto}
JSON:"""

def _llm(texto: str) -> str:
    body = json.dumps({"model": MODELO, "prompt": _PROMPT.format(texto=texto), "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("response", "")

def extraer_json(salida: str) -> dict | None:
    m = re.search(r"\{.*\}", salida, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

def extraer(texto: str) -> dict:
    """Devuelve slots crudos. Si el LLM falla, {entidad:null,...} → la máquina pedirá reformular.
    NUNCA lanza al usuario un error feo (regla madre)."""
    base = {"entidad": None, "nivel": None, "producto": None, "periodo": None, "agregacion": None}
    got = extraer_json(_llm(texto)) or {}
    base.update({k: got.get(k) for k in base if k in got})
    return base
```

### 5.E `maquina.py` — schema del Intent + máquina de estados (§8 del diseño)
```python
import time, sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta.extraccion import extraer
from app.features.consulta.resolver import resolver

_NIVEL_LABEL = {"vicepresidencia":"Vicepresidencia","gerencia":"Gerencia","activo":"Activo",
                "area":"Área","campo":"Campo","fuente":"Fuente (pozo)","operador":"Operador",
                "filial":"Filial (empresa)","pozo":"Fuente (pozo)"}

# --- persistencia del intent parcial (v1: memoria por conversation_id + TTL) ---
_PARCIAL = {}       # conversation_id -> (intent, ts)
_TTL = 900          # 15 min

def _guardar(cid, intent): _PARCIAL[cid] = (intent, time.time())
def _leer(cid):
    v = _PARCIAL.get(cid)
    if not v: return None
    intent, ts = v
    if time.time() - ts > _TTL:
        _PARCIAL.pop(cid, None); return None
    return intent

def _nuevo_intent(slots):
    return {"status": "pendiente",
            "entidad": {"texto": slots.get("entidad"), "resuelta": None},
            "producto": None, "periodo": None, "agregacion": slots.get("agregacion"),
            "pendiente": None, "avisos": [], "_slots": slots}

def _fijar_resuelta(intent, ident):
    intent["entidad"]["resuelta"] = {"nivel": ident["nivel"], "rama": ident["rama"], "valor": ident["valor"]}
    intent["pendiente"] = None
    intent["status"] = "completo"
    return intent

def preguntar(texto: str, cid: str) -> dict:
    """S0 EXTRAER → S1 RESOLVER → (completo | pendiente con botones)."""
    slots = extraer(texto)
    if not slots.get("entidad"):
        return {"status": "reformular", "mensaje": "No identifiqué una entidad. ¿Puedes reformular?"}
    intent = _nuevo_intent(slots)
    ids = resolver(slots["entidad"])
    if not ids:
        return {"status": "reformular",
                "mensaje": f"No encontré «{slots['entidad']}» en el catálogo.", "intent": intent}
    # pista de nivel del LLM: desempata SOLO si coincide con una identidad real
    pista = (slots.get("nivel") or "").lower()
    match_pista = [i for i in ids if i["nivel"] == pista or (pista == "pozo" and i["nivel"] == "fuente")]
    if len(ids) == 1:
        _fijar_resuelta(intent, ids[0])
    elif len(match_pista) == 1:
        intent["avisos"].append(f"Interpreté «{slots['entidad']}» como {match_pista[0]['nivel']} (por tu texto).")
        _fijar_resuelta(intent, match_pista[0])
    else:
        # colisión → S2: emitir botones (una opción por identidad)
        intent["pendiente"] = {"slot": "nivel",
            "opciones": [{"id": f"{i['nivel']}::{i['valor']}", "label": _NIVEL_LABEL.get(i['nivel'], i['nivel']),
                          "nivel": i["nivel"], "rama": i["rama"], "valor": i["valor"]} for i in ids]}
        _guardar(cid, intent)
    return _salida(intent)

def responder(cid: str, opcion_id: str) -> dict:
    """S3 REANUDAR: aplica la opción elegida → intent completo."""
    intent = _leer(cid)
    if not intent or not intent.get("pendiente"):
        return {"status": "expirado", "mensaje": "No hay una pregunta pendiente (o expiró). Escribe de nuevo."}
    op = next((o for o in intent["pendiente"]["opciones"] if o["id"] == opcion_id), None)
    if not op:
        return {"status": "error", "mensaje": "Opción no válida."}
    _fijar_resuelta(intent, op)
    _PARCIAL.pop(cid, None)
    return _salida(intent)

def _salida(intent: dict) -> dict:
    out = {"status": intent["status"]}
    if intent["status"] == "pendiente":
        out["pregunta"] = f"«{intent['entidad']['texto']}» existe en varios niveles. ¿Cuál?"
        out["opciones"] = [{"id": o["id"], "label": o["label"]} for o in intent["pendiente"]["opciones"]]
    if intent["status"] == "completo":
        r = intent["entidad"]["resuelta"]
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"]}
        out["huella"] = _huella(r)   # huella básica (rango temporal) de la entidad resuelta
    return out

def _huella(resuelta: dict) -> dict:
    """Huella temporal básica de la entidad resuelta (rama A ECP). Reusa fact_produccion_dia_ecp.
    v1: si no hay grano diario ECP (filial pura), devuelve {aplica:false}."""
    eng = get_engine(); E = resuelta["valor"].upper()
    with eng.connect() as c:
        ids = [x[0] for x in c.execute(sa.text("""
            SELECT fuente_id FROM core.dim_fuente
            WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e OR UPPER(TRIM(grupo1))=:e
               OR UPPER(TRIM(activos))=:e OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
        """), {"e": E})]
        vid = c.execute(sa.text("SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"),
                        {"e": E}).scalar()
        if not ids and vid is None:
            return {"aplica": False}
        conds, params = [], {}
        if ids: conds.append("fuente_id IN :ids"); params["ids"] = ids
        if vid is not None: conds.append("vice_id = :vid"); params["vid"] = vid
        q = sa.text("SELECT MIN(fecha), MAX(fecha), COUNT(DISTINCT fecha) FROM core.fact_produccion_dia_ecp WHERE "
                    + " OR ".join(conds))
        if ids: q = q.bindparams(sa.bindparam("ids", expanding=True))
        lo, hi, n = c.execute(q, params).one()
        return {"aplica": bool(n), "desde": lo.isoformat() if lo else None,
                "hasta": hi.isoformat() if hi else None, "dias": n or 0}
```

### 5.F `api.py` — endpoints
```python
from fastapi import APIRouter
from pydantic import BaseModel
from app.features.consulta import maquina

router = APIRouter(prefix="/consulta")

class Preguntar(BaseModel):
    texto: str
    conversation_id: str

class Responder(BaseModel):
    conversation_id: str
    opcion_id: str

@router.post("/preguntar")
def preguntar(body: Preguntar):
    return maquina.preguntar(body.texto, body.conversation_id)

@router.post("/responder")
def responder(body: Responder):
    return maquina.responder(body.conversation_id, body.opcion_id)
```

### 5.G `main.py` — registrar router (igual que `analisis`)
Añadir junto al registro del router `analisis` (buscar `from app.features.analisis.api import router`):
```python
from app.features.consulta.api import router as consulta_router
app.include_router(consulta_router)   # ANTES del app.mount(StaticFiles(...))
```

### 5.L `routes/api.py` — proxies Flask (patrón existente, con `requests`)
```python
@api_bp.route("/consulta/preguntar", methods=["POST"])
def consulta_preguntar():
    try:
        resp = requests.post(f"{INGESTA_API_URL}/consulta/preguntar", json=request.get_json(), timeout=90)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502

@api_bp.route("/consulta/responder", methods=["POST"])
def consulta_responder():
    try:
        resp = requests.post(f"{INGESTA_API_URL}/consulta/responder", json=request.get_json(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```
> Verificar que `request` esté importado en `routes/api.py` (lo está: se usa en los proxies de análisis).

### 5.M `static/js/multitab_shell.js` — pestaña Consulta como TAB DE PRIMER NIVEL del riel (D2)
> ⚠️ **CORREGIDO (auditoría §0, I1):** Consulta es un **tab del riel** (par de Ingesta/Control/Análisis),
> NO un sub-módulo de Análisis. Se integra con la máquina de tabs existente (`TABS`, `renderPanelBody`,
> `renderViewer`, `setActiveTab`). El binding de clic ya es genérico (líneas ~439–441:
> `root.querySelectorAll(".rb-cp__tab") … setActiveTab(btn.dataset.tab)`) → un tab nuevo en el HTML del riel
> queda enganchado automáticamente. Patrón = zona 2 (panel) con ayuda breve, zona 3 (viewer) con la UI (como Análisis).

**Cambio 1 — array `TABS`** (~L11–13): añadir un 4º elemento tras `analisis`:
```javascript
    { id: "consulta", label: "Consulta", icon: "chat-dots", sub: "Preguntas en lenguaje natural" },
```

**Cambio 2 — HTML del riel** (tras el botón de Análisis, ~L56, mismo patrón `rb-cp__tab`):
```javascript
      '  <button type="button" role="tab" id="cp-tab-consulta" data-tab="consulta"' +
      '    class="rb-cp__tab" aria-selected="false" aria-controls="rb-cp-panel-body" tabindex="-1" title="Consulta">' +
      '    <i class="bi bi-chat-dots rb-cp__tab-icon" aria-hidden="true"></i>' +
      '    <span class="rb-cp__tab-label">Consulta</span></button>' +
```

**Cambio 3 — `renderPanelBody()`** (zona 2; añadir rama tras `analisis`, ~L282):
```javascript
    } else if (state.activeTab === "consulta") {
      body.innerHTML = renderConsultaBody();
```

**Cambio 4 — `renderViewer()`** (zona 3; añadir rama tras `analisis`, ~L328–342). La UI de Consulta vive
en el viewer (input + resultados juntos, como un chat):
```javascript
    } else if (state.activeTab === "consulta") {
      viewer.innerHTML =
        '<div class="rb-cp-vhead"><i class="bi bi-chat-dots rb-cp-vhead__icon"></i>' +
        '  <span class="rb-cp-vhead__title is-gold">Consulta de Producción (v1)</span></div>' +
        '<div class="p-2">' +
        '  <div class="mb-2"><input id="cn-input" class="form-control form-control-sm d-inline-block" ' +
        '    style="max-width:420px;vertical-align:middle;" placeholder="Ej: producción de Rubiales"> ' +
        '    <button type="button" class="btn btn-sm btn-primary" onclick="window.__cnPreguntar()">Preguntar</button></div>' +
        '  <div id="cn-display-area"></div>' +
        '</div>';
```

**Cambio 5 — funciones nuevas** (antes de `window.MultiTabShell = ...`; IIFE `var`/concatenación):
```javascript
  // ============ Pestaña CONSULTA (slot-filling v1) ============
  function renderConsultaBody() {   // zona 2 (panel): ayuda breve
    return '<div class="rb-cp-menu"><div class="rb-cp-menu__head">' +
      '<i class="bi bi-chat-dots"></i><div><strong>Consulta</strong><small>Lenguaje natural</small></div></div>' +
      '<div class="p-2 small text-muted">Escribe una pregunta sobre producción (v1: una entidad). ' +
      'Ej.: <em>producción de Rubiales</em>. El sistema pregunta lo necesario y arma un intent validado.</div></div>';
  }
  var __cnCid = "cn-" + Math.floor(Math.random() * 1e9);   // conversation_id de la sesión
  function __cnArea() { return el("cn-display-area"); }
  window.__cnPreguntar = function () {
    var inp = el("cn-input"), body = __cnArea(); if (!inp || !body) return;
    body.innerHTML = '<div class="text-muted small p-2"><span class="spinner-border spinner-border-sm"></span> Procesando…</div>';
    fetch("/api/consulta/preguntar", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({texto: inp.value, conversation_id: __cnCid})})
      .then(function (r) { return r.json(); }).then(__cnRender).catch(function () {
        body.innerHTML = '<div class="alert alert-danger small">Error de conexión.</div>'; });
  };
  window.__cnResponder = function (opcionId) {
    var body = __cnArea(); if (!body) return;
    body.innerHTML = '<div class="text-muted small p-2"><span class="spinner-border spinner-border-sm"></span> …</div>';
    fetch("/api/consulta/responder", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({conversation_id: __cnCid, opcion_id: opcionId})})
      .then(function (r) { return r.json(); }).then(__cnRender).catch(function () {
        body.innerHTML = '<div class="alert alert-danger small">Error.</div>'; });
  };
  function __cnRender(d) {
    var body = __cnArea(); if (!body) return;
    if (d.status === "reformular" || d.status === "expirado" || d.status === "error") {
      body.innerHTML = '<div class="alert alert-warning small">' + esc(d.mensaje || "") + '</div>'; return;
    }
    if (d.status === "pendiente") {
      var btns = d.opciones.map(function (o) {
        return '<button type="button" class="btn btn-sm btn-outline-primary me-1 mb-1" ' +
          'onclick="window.__cnResponder(\'' + esc(o.id) + '\')">' + esc(o.label) + '</button>';
      }).join("");
      body.innerHTML = '<div class="mb-2">' + esc(d.pregunta) + '</div>' + btns; return;
    }
    if (d.status === "completo") {
      var it = d.intent, h = d.huella || {};
      var huella = h.aplica ? ('Datos diarios: <strong>' + h.dias + '</strong> días (' + esc(h.desde) + ' → ' + esc(h.hasta) + ')')
                            : 'Sin grano diario ECP para esta entidad (posible filial/consolidado).';
      var avisos = (it.avisos && it.avisos.length) ? '<div class="text-muted small mt-1">' +
        it.avisos.map(esc).join(" · ") + '</div>' : "";
      body.innerHTML =
        '<div class="alert alert-success small mb-1"><strong>Intent listo:</strong> ' +
        esc(it.entidad) + ' · nivel <strong>' + esc(it.nivel) + '</strong> · rama ' + esc(it.rama) + '</div>' +
        '<div class="small">' + huella + '</div>' + avisos +
        '<div class="text-muted small mt-1">(v1 para aquí — la ejecución del número es Fase 3.)</div>';
    }
  }
```
> Reusa `el`, `esc` (helpers del IIFE). **NO** usa `__anArea` (eso era el bug I1). Clases `rb-cp-menu`,
> `rb-cp-vhead`, `rb-cp-vhead__icon`, `rb-cp-vhead__title is-gold` ya existen en `static/css/colapsable.css`
> (las usa Análisis) → no se crea CSS nuevo. **Nota v1:** al cambiar de tab y volver, el viewer se re-renderiza
> (conversación se reinicia); aceptable en v1 (el `conversation_id` persiste en backend por TTL).

### 5.H `golden/extraccion_golden.yaml` — golden set (LLM), ~20–40 casos. Semilla mínima:
```yaml
# pregunta -> slots esperados (mide extracción del LLM, single-turn)
- pregunta: "producción de Rubiales"
  esperado: {entidad: "RUBIALES", nivel: null, producto: null, periodo: null, agregacion: null}
- pregunta: "cuánto crudo produjo el pozo La Hocha el mes pasado"
  esperado: {entidad: "LA HOCHA", nivel: "pozo", producto: "aceite", periodo: "mes pasado", agregacion: null}
- pregunta: "producción del campo Castilla"
  esperado: {entidad: "CASTILLA", nivel: "campo", producto: null, periodo: null, agregacion: null}
- pregunta: "y el gas ahí?"                         # trampa: entidad heredada del contexto → null
  esperado: {entidad: null, nivel: null, producto: "gas", periodo: null, agregacion: null}
- pregunta: "y el agua de Chichimene?"              # trampa: agua (se rechaza después)
  esperado: {entidad: "CHICHIMENE", nivel: null, producto: "agua", periodo: null, agregacion: null}
- pregunta: "produccion de rubialess"               # trampa: typo (Capa 2 fuzzy)
  esperado: {entidad: "RUBIALESS", nivel: null, producto: null, periodo: null, agregacion: null}
# … completar hasta 20–40 con: gerencia GOR, filial Hocol, acentos (Caño Limón), agregación (promedio),
#    periodo absoluto (marzo), y variantes de fraseo. Curados a mano por el experto de dominio.
```

### 5.I `golden/estado_fixtures.yaml` — fixtures de estado (Python, SIN LLM). Semilla:
```yaml
# slots (ya extraídos) -> comportamiento esperado de la máquina (determinista)
- nombre: "colision_dura_rubiales"
  slots: {entidad: "RUBIALES", nivel: null}
  espera_status: "pendiente"
  espera_opciones_niveles: ["campo", "activo", "gerencia", "fuente"]
  responder_con_nivel: "campo"
  espera_intent: {entidad: "RUBIALES", nivel: "campo", rama: "A"}
- nombre: "pista_desempata_castilla"
  slots: {entidad: "CASTILLA", nivel: "campo"}
  espera_status: "completo"
  espera_intent: {entidad: "CASTILLA", nivel: "campo", rama: "A"}
- nombre: "dual_hocol"
  slots: {entidad: "HOCOL", nivel: null}
  espera_status: "pendiente"
  espera_opciones_niveles: ["filial", "operador"]
  responder_con_nivel: "filial"
  espera_intent: {entidad: "HOCOL", nivel: "filial", rama: "B"}
- nombre: "unica_gor"
  slots: {entidad: "GOR", nivel: "campo"}        # pista errada; GOR solo es gerencia → se ignora la pista
  espera_status: "completo"
  espera_intent: {entidad: "GOR", nivel: "gerencia", rama: "A"}
- nombre: "no_existe"
  slots: {entidad: "PARAISO_INEXISTENTE", nivel: null}
  espera_status: "reformular"
```

### 5.J `golden/run_golden.py` — corre el golden set (LLM) y reporta exactitud
```python
"""Uso: PYTHONPATH=. uv run python app/features/consulta/golden/run_golden.py"""
import yaml, pathlib
from app.features.consulta.extraccion import extraer

def main():
    p = pathlib.Path(__file__).with_name("extraccion_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok = 0
    for c in casos:
        got = extraer(c["pregunta"])
        exp = c["esperado"]
        match = all(str(got.get(k)).upper() == str(exp.get(k)).upper() if k == "entidad"
                    else got.get(k) == exp.get(k) for k in exp)
        ok += bool(match)
        print(("OK " if match else "XX ") + c["pregunta"] + (" -> " + str(got) if not match else ""))
    print(f"\nEXACTITUD: {ok}/{len(casos)} = {100*ok//len(casos)}%   (umbral D7: >=90%)")

if __name__ == "__main__":
    main()
```

### 5.K `tests/test_consulta_estado.py` — fixtures de estado (pytest, SIN LLM)
```python
import yaml, pathlib, pytest
from app.features.consulta import maquina

CASOS = yaml.safe_load(
    (pathlib.Path(__file__).parents[1] / "app/features/consulta/golden/estado_fixtures.yaml").read_text(encoding="utf-8"))

@pytest.mark.parametrize("caso", CASOS, ids=[c["nombre"] for c in CASOS])
def test_estado(caso, monkeypatch):
    # inyectar los slots directamente (sin LLM): parchear extraer()
    monkeypatch.setattr(maquina, "extraer", lambda _t: {**{"entidad": None, "nivel": None, "producto": None,
                        "periodo": None, "agregacion": None}, **caso["slots"]})
    cid = "test-" + caso["nombre"]
    out = maquina.preguntar("(texto irrelevante)", cid)
    assert out["status"] == caso["espera_status"]
    if caso["espera_status"] == "pendiente":
        niveles = sorted(o["id"].split("::")[0] for o in out["opciones"])
        assert niveles == sorted(caso["espera_opciones_niveles"])
        # responder y verificar intent
        op = next(o for o in out["opciones"] if o["id"].startswith(caso["responder_con_nivel"] + "::"))
        fin = maquina.responder(cid, op["id"])
        assert fin["status"] == "completo"
        for k, v in caso["espera_intent"].items():
            assert str(fin["intent"][k]).upper() == str(v).upper()
    elif caso["espera_status"] == "completo":
        for k, v in caso["espera_intent"].items():
            assert str(out["intent"][k]).upper() == str(v).upper()
```

### 5.N `db/migrations/007_pg_trgm.sql` — (paso separable, para Capa 2 fuzzy)
```sql
-- Idempotente. Habilita fuzzy matching para el resolver (Capa 2). No requerido por el walking skeleton.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 6. Orden de ejecución

1. **Backend feature `consulta`** (A→F): normaliza → resolver → extraccion → maquina → api.
2. **Registrar router** (G) en `main.py`.
3. **Fixtures de estado** (I) + **test** (K): correr `pytest` → deben pasar SIN LLM (valida la máquina).
4. **Golden set** (H) + **runner** (J): correr → medir exactitud del LLM (≥90%). Ampliar casos hasta 20–40.
5. **Proxies Flask** (L).
6. **UI** (M): pestaña Consulta.
7. **Reinicio** de backends (ver §7.4) + **validaciones V1–V7**.
8. *(Separable, opcional en v1)* **`pg_trgm`** (N) + Capa 2 fuzzy en `resolver.py` (typos). Si la extensión
   no se puede crear (permisos) → dejar solo Capa 1 y anotarlo; NO bloquea el walking skeleton.

---

## 7. Reglas no negociables

1. **SOLO v1.** 1 entidad, 1 intent. NO implementar G1 (multi-entidad), G2, H1–H4 (multi-intent, drill-down,
   validación de periodo avanzada, producto sensible al perfil). Si aparece la tentación → es v2/v3, detener.
2. **Frontera LLM/Python (D4):** el LLM SOLO extrae (`extraccion.py`). Prohibido que el LLM vea el catálogo,
   resuelva, decida o calcule. Toda decisión vive en `resolver.py`/`maquina.py`.
3. **PARA en el intent (D1):** NO ejecutar ninguna consulta de producción ni devolver "el número". La salida
   `completo` entrega el intent validado + huella temporal básica. La ejecución es Fase 3.
4. **Solo lectura de la BD.** Prohibido DDL/ETL/escrituras salvo la migración `007_pg_trgm.sql` (paso 8,
   idempotente). NO tocar `fact_tabla_hoja` (62M).
5. **Plegado de acentos en Python** (`normaliza.norm`), aplicado IGUAL a usuario y catálogo. NO depender de
   la extensión `unaccent` (no está instalada).
6. **Estilo:** backend = patrón del feature `analisis` (APIRouter, get_engine, sqlalchemy Core). Frontend =
   IIFE `var` + concatenación de strings (como el resto de `multitab_shell.js`).
7. **No romper la fundación:** Catálogo/Densidad/Cobertura/Ingesta/Control deben seguir funcionando.

**Reinicio de backends (§7.4)** — si `iniciar_backends.bat` no relanza fiable, lanzar con el PYTHON BASE
(leer `home` de `pyvenv.cfg`) + PYTHONPATH:
- FastAPI: `cwd=INGESTA\Rep_Prod\backend`, `PYTHONPATH=...\.venv\Lib\site-packages`, `<basepy> -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Flask: `cwd=raíz`, `PYTHONPATH=...\venv\Lib\site-packages`, `<basepy> app.py`

---

## 8. Validaciones (correr TODAS y reportar cada una)

- **V1 — Fixtures de estado (sin LLM, determinista):**
  ```bash
  cd INGESTA/Rep_Prod/backend && PYTHONPATH=. uv run pytest tests/test_consulta_estado.py -v
  ```
  Esperado: **todos PASS** (colisión Rubiales→botones→campo; pista Castilla; dual Hocol; GOR ignora pista; no_existe→reformular).
- **V2 — Resolver (unidad):**
  ```bash
  cd INGESTA/Rep_Prod/backend && PYTHONPATH=. uv run python -c "from app.features.consulta.resolver import resolver as r; print('RUBIALES',[i['nivel'] for i in r('RUBIALES')]); print('rubiales',[i['nivel'] for i in r('rubiales')]); print('HOCOL',[i['rama'] for i in r('HOCOL')]); print('GOR',[i['nivel'] for i in r('GOR')])"
  ```
  Esperado: `RUBIALES` = 4 niveles; `rubiales` (minúsc.) = los mismos 4 (prueba `norm`); `HOCOL` = ['B','A'] (dual); `GOR` = ['gerencia'].
- **V3 — Golden set (LLM):**
  ```bash
  cd INGESTA/Rep_Prod/backend && PYTHONPATH=. uv run python app/features/consulta/golden/run_golden.py
  ```
  Esperado: **EXACTITUD ≥ 90%**. (Si <90%, ajustar el prompt few-shot, NO la máquina.)
- **V4 — Endpoint FastAPI (round-trip):**
  ```bash
  curl -s -X POST http://localhost:8000/consulta/preguntar -H "Content-Type: application/json" -d '{"texto":"produccion de Rubiales","conversation_id":"t1"}'
  # → status:"pendiente"; opciones = Campo/Activo/Gerencia/Fuente. COPIAR el "id" de la opción "Campo"
  #   de la respuesta (p.ej. "campo::RUBIALES" — el casing del valor viene de la BD; NO hardcodear).
  curl -s -X POST http://localhost:8000/consulta/responder -H "Content-Type: application/json" -d '{"conversation_id":"t1","opcion_id":"<id copiado de la opción Campo>"}'
  # → status:"completo", intent.nivel:"campo", huella.aplica:true
  ```
- **V5 — Proxies Flask:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8020/api/consulta/preguntar -H "Content-Type: application/json" -d '{"texto":"Rubiales","conversation_id":"t2"}'
  ```
  Esperado: `200`.
- **V6 — Navegador (end-to-end):** abrir :8020 → login → montar shell (Análisis avanzado) → pestaña
  **Consulta** → escribir "producción de Rubiales" → **Preguntar** → aparecen botones → clic en **Campo** →
  aparece "Intent listo: RUBIALES · nivel campo · rama A" + huella. **0 errores de consola.**
- **V7 — No regresión:** Catálogo, Densidad, Cobertura, Ingesta y Control siguen operativos.

**CRITERIO DE ÉXITO:** V1–V2 y V4–V7 pasan; V3 ≥ 90%. Si algo falla: reportar comando + salida exacta y DETENERSE.

---

## 9. Fuera de alcance (v2/v3 — NO implementar aquí)

- **G1** — multi-entidad (`entidades: []`), **G2** — comparación multi-nivel.
- **H1** — multi-intent (`sub_intents[]`), **H2** — coherencia de rama por drill-down, **H3** — validación de
  periodo contra la huella + gramática de trimestres relativos, **H4** — producto sensible al perfil.
- **Fase 3** — ejecución del intent (la herramienta `produccion_por_nivel` que devuelve el número real).
- **Formato "huella primero" rico** (§7.5) completo — v1 muestra una huella básica al completar; el encuadre
  visual pleno (huella temporal + temática antes de la contrapregunta) se pule en iteración posterior.
- **Parity `gemma4:latest`** — se corre en despliegue (prod), no en dev.
- **Redacción del LLM (Paso 4)** — v1 muestra el intent estructurado; la prosa es opcional/posterior.

---

## 10. Notas de trazabilidad (verificado contra la BD dev `daily_report_prod`, 2026-07-08)
- `RUBIALES` → campo/activo/gerencia/fuente (colisión dura). `HOCOL` → filial (B) + operador (A) = dual.
  `GOR` → solo gerencia. `CASTILLA` → 4 niveles.
- `pg_trgm`/`unaccent`: disponibles NO instaladas → acentos en Python; `pg_trgm` en el paso 8.
- Ollama dev: `qwen2.5:3b` presente. Prod: `gemma4:latest` (parametrizar `MODELO` por env en despliegue).
- Diseño completo y decisiones: `DISENO_CAPA_CONVERSACIONAL.md` (§1, §2 D1–D7, §7.6 resolver, §8 intent+estados).
```
