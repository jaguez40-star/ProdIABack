# Plan · Fase 3.1 — Narración conversacional (el LLM redacta lo que Python ya calculó)

> **Cobertura de datos:** este plan NO toca DDL, ETL, grano ni claves. Añade una **capa de
> presentación** encima de la Fase 3 determinista. `Tablas: entrada N → salida N` (no aplica; no
> modela hojas). Auditado v2 (audit-first §0.2).

---

## 1. Contexto (para un Executor sin acceso previo al repo)

**Monorepo:** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
- App padre Flask (ProdIA) en `:8020` — sirve el chat y hace de **proxy** a INGESTA.
- Sub-proyecto INGESTA (FastAPI) en `:8000` — feature `consulta` (capa conversacional).

Hoy, cuando el chat de **Consulta** resuelve una entidad (p.ej. "cuánto produjo Rubiales de crudo"),
el backend responde con una **cifra REAL vs PPTO 100% determinista** (plantilla Python, sin LLM),
producida por `consulta/ejecucion.py::ejecutar()`. El frontend la pinta como un bloque de
encabezado + viñetas + pie:

```
RUBIALES · Mayo 2026 · corte 17/31
· CRUDO: 12.357.703 · 95.6% del presupuesto (Alineado)
Calculado sobre 17 días con reporte.
```

**Objetivo de esta fase:** que **Python entregue esa respuesta ya calculada (JSON) al LLM (Gemma en
prod) para que la REDACTE** en 2-3 oraciones de lenguaje de pasillo, personalizado con el nombre del
usuario, tejiendo también las acciones siguientes. Resultado esperado (ejemplo real):

> «Javier, Campo Rubiales lleva 12.357.703 barriles de crudo acumulados en mayo 2026, con 17 de 31
> días reportados. Eso lo pone en 95.6% del presupuesto, lo que lo clasifica como Alineado — va bien
> encaminado. El análisis del campo y la consulta por día están disponibles para que sigas explorando.»

**Frontera dura (la regla madre de esta fase):** el LLM **NO calcula, NO recalcula, NO inventa
números**. Solo teje en prosa los valores exactos del JSON. La cifra determinista sigue siendo la
**fuente de verdad** y el **fallback**.

---

## 2. Decisiones cerradas

- **D-N1 · Coexistencia, no reemplazo.** `ejecutar()` sigue devolviendo la cifra determinista intacta.
  La narración es una capa encima: se adjunta como `respuesta["narracion"]`. Si no hay narración
  (flag off / fallo / regla violada), el frontend pinta la plantilla determinista de siempre.
- **D-N2 · Flag `CONSULTA_NARRA_LLM`** (default `false`). Dev = off (qwen2.5:3b es un extractor, redacta
  pobre → se sirve la plantilla). Prod/139 = `true` en el `.env` (gemma4:latest redacta). Mismo patrón
  que `EJECUTIVO_USAR_LLM`.
- **D-N3 · Fallback determinista SIEMPRE.** El usuario nunca ve un error ni un texto a medias.
- **D-N4 · El LLM recibe SOLO números ya calculados (JSON) + la orden de no recalcular.** Salida de
  **texto plano** (NO `format:json`, a diferencia del ejecutivo).
- **D-N5 · Salvaguarda numérica (materializa la Regla #1).** Tras redactar, Python verifica que el
  **string exacto del volumen** de cada producto (`_fmt(real)`, p.ej. `"12.357.703"`) aparezca literal
  en la narración. Si falta alguno → se descarta la narración y cae al fallback determinista.
- **D-N6 · "Los dos elementos" = la cifra + las acciones.** Ambos van en el JSON; el LLM los teje en un
  solo párrafo (como el ejemplo: cifra + "El análisis del campo y la consulta por día están disponibles").
- **D-N7 · Nombre de usuario** se pasa desde el frontend (`window.USER_FIRST_NAME`) por el payload de
  `/consulta/preguntar` y `/responder` (el proxy Flask ya reenvía el body verbatim). Si viene vacío, el
  prompt omite el saludo. **Importante:** cuando hay narración, el frontend **NO** vuelve a anteponer el
  nombre (`__cnConNombre` no se aplica en la rama de narración → evita doble saludo).
- **D-N8 · Unidad por producto** (hallazgo F-N2): la capa determinista no lleva unidad. Se usa un mapa
  de dominio **seguro**: `CRUDO→"barriles"`, `BLANCOS→"barriles"`; `GAS→""` (sin unidad; KPC/KPCD es
  ambiguo hasta confirmar). El prompt narra sin unidad cuando `unidad` viene vacía.

---

## 2.1 Hallazgos de auditoría (verificados contra el código real — audit-first §0.2)

- **F-A1 · No regresión de tests** — `backend/tests/test_consulta_estado.py` llama
  `maquina.preguntar(texto, cid)` / `responder(cid, id)` SIN `usuario`; `test_consulta_desambiguacion.py`
  solo usa `_resolver_colision`/`_rep` (funciones puras, intactas). `usuario` es opcional (`=None`)
  → 100% retrocompatible. ✅
- **F-A2 · Sin import circular** — cadena `maquina → narracion → ejecucion` (hoja); `ejecucion` NO
  importa `narracion` ni `maquina`, y ya se importaba hoy → no se añade dependencia de import nueva. ✅
- **F-A3 · Coherencia del número (linchpin)** — `narracion` REUSA `ejecucion._fmt`, así el string de
  volumen del JSON == el de la línea determinista == el que valida la salvaguarda (D-N5). Un solo origen
  de formato evita desalineación chat↔narración. ✅
- **F-A4 · Multi-producto** — "producción de Rubiales" (sin producto) devuelve 3 productos; exigir los 3
  volúmenes literales en pocas frases podría caer al **fallback determinista** (correcto y seguro).
  Mitigado: `2 a 4 oraciones` + `num_predict=320`. El caso del ejemplo (1 producto) queda holgado.
- **F-A5 · Avisos fuera del LLM** — los `avisos` honestos ("aún no manejo año/semana…") NO se pasan al
  LLM; se pintan verbatim DEBAJO de la narración. El LLM narra la cifra; los caveats quedan intactos.
- **F-A6 · Cobertura autoritativa** — se pasa `respuesta["pie"]` como `cobertura` para que el LLM use la
  frase determinista correcta tanto con grano diario ("Calculado sobre 17 días…") como en cierre mensual
  ("Cifra de cierre mensual (sin curva diaria)") → no reconstruye cobertura a mano.
- **F-A7 · Latencia** — en la rama de resolución directa hay ahora 2 llamadas LLM (extraer + narrar).
  En prod (gemma4/139) es aceptable; el proxy `/preguntar` ya es 90s y `/responder` sube a 90s (F-N1).
  En dev el flag está off → 0 llamadas de narración.

---

## 3. Prerequisitos

- Backends arriba (para validar): Flask `:8020` y FastAPI INGESTA `:8000`.
  - INGESTA: `cd INGESTA\Rep_Prod\backend; uv run uvicorn app.main:app --port 8000 --reload`
- Ollama de Consulta accesible según `.env` (`CONSULTA_OLLAMA_URL` / `CONSULTA_LLM_MODEL`).
  En dev el flag `CONSULTA_NARRA_LLM` queda **off** → la validación end-to-end de prosa se hace con
  el flag on **temporalmente** apuntando a un Ollama disponible, o se difiere a 139.

---

## 4. Inventario de archivos

| # | Ruta (absoluta) | Acción |
|---|---|---|
| A | `INGESTA\Rep_Prod\backend\app\core\config.py` | EDIT: +1 flag `consulta_narra_llm` |
| B | `INGESTA\Rep_Prod\backend\app\features\consulta\narracion.py` | **NUEVO** (motor de narración) |
| C | `INGESTA\Rep_Prod\backend\app\features\consulta\maquina.py` | EDIT: threading `usuario` + adjuntar narración |
| D | `INGESTA\Rep_Prod\backend\app\features\consulta\api.py` | EDIT: +campo `usuario` en los 2 bodies |
| E | `routes\api.py` | EDIT: subir timeout de `/consulta/responder` 30→90 (F-N1) |
| F | `static\js\multitab_shell.js` | EDIT: enviar `usuario` + pintar narración si viene |
| G | `static\css\colapsable.css` | EDIT: +estilos `.cn-answer--narrada` |
| H | `templates\main.html` | EDIT: cache-buster `n`→`o` (líneas 5 y 82) |

---

## 5. Especificación (cambios exactos)

### A · `config.py` — flag nuevo

Localizar (líneas ~18-21):

```python
    # Análisis Ejecutivo: en dev sirve el composer determinista (superior al qwen local);
    # en prod (gemma4:latest) poner EJECUTIVO_USAR_LLM=true en el .env para el pulido de prosa.
    ejecutivo_usar_llm: bool = False
```

Insertar JUSTO ANTES de esa línea de comentario:

```python
    # Consulta · Narración (Fase 3.1): en dev off (qwen es extractor, redacta pobre → se sirve la
    # plantilla determinista); en prod (gemma4:latest) poner CONSULTA_NARRA_LLM=true en el .env.
    consulta_narra_llm: bool = False
```

### B · `narracion.py` — NUEVO (contenido completo)

Crear `INGESTA\Rep_Prod\backend\app\features\consulta\narracion.py` con EXACTAMENTE:

```python
"""Fase 3.1 · Narración conversacional (el LLM redacta lo que Python ya calculó).

Toma la respuesta DETERMINISTA de ejecucion.ejecutar() (cifra REAL vs PPTO ya calculada) y pide al LLM
que la redacte en 2-3 oraciones de lenguaje llano, personalizadas con el nombre del usuario y con la
invitación a seguir explorando. FRONTERA DURA: el LLM NO calcula, NO recalcula, NO inventa números —
solo teje en prosa los valores del JSON. Si el LLM falla, viola la regla numérica (D-N5) o el flag está
apagado → devuelve None y el frontend pinta la plantilla determinista.

Gobernado por CONSULTA_NARRA_LLM (default false: dev sirve la plantilla; prod/139 con gemma4 = true).
Mismo patrón que EJECUTIVO_USAR_LLM. Salida de TEXTO PLANO (sin format=json, a diferencia del ejecutivo).
"""
import json as _json, urllib.request as _urlreq
from app.core.config import get_settings
from app.features.consulta.ejecucion import _fmt

# Unidad por producto (dominio petrolero). Mapa SEGURO: crudo/blancos en barriles; gas sin unidad
# (KPC/KPCD ambiguo hasta confirmar por spot-check) → el prompt narra sin unidad si viene vacía.
_UNIDAD = {"CRUDO": "barriles", "BLANCOS": "barriles", "GAS": ""}

_SISTEMA = (
    "Eres el narrador de ProdIA, un asistente de produccion petrolera de Ecopetrol.\n"
    "REGLAS INQUEBRANTABLES:\n"
    "1. NUNCA inventes, redondees ni recalcules ningun numero. Copia los strings de volumen y de "
    "porcentaje EXACTAMENTE como vienen en el JSON.\n"
    "2. NUNCA agregues datos que no esten en el JSON.\n"
    "3. Se conciso: 2 a 4 oraciones como maximo (usa el limite alto solo si hay varios productos).\n"
    "4. Tono: colega tecnico que te resume en el pasillo, ni robot ni poeta.\n"
    "5. Menciona SIEMPRE: la entidad, el producto, el volumen, el porcentaje del presupuesto y la "
    "clasificacion. Refleja la cobertura del periodo respetando el texto exacto del campo 'cobertura'.\n"
    "6. Si la clasificacion es 'Alineado', tono neutro-positivo; si es 'Rezagado' o 'Foco', tono de "
    "alerta sin alarma.\n"
    "7. Si el JSON trae 'usuario', abre saludando por su nombre (ej. 'Javier, ...'); si es null, "
    "empieza directamente por la entidad.\n"
    "8. Si un producto trae 'unidad' no vacia, usala junto al volumen; si viene vacia, no inventes "
    "unidad.\n"
    "9. Cierra invitando a seguir explorando con las 'acciones_disponibles', en lenguaje natural.\n"
    "FORMATO DE SALIDA: solo el texto narrado, sin encabezados, sin vinetas, sin markdown, sin comillas."
)


def _payload(respuesta: dict, usuario) -> dict:
    """Arma el JSON de entrada al LLM SOLO con valores ya calculados por ejecutar()."""
    mes = respuesta.get("mes") or {}
    productos = []
    for l in respuesta.get("lineas", []):
        pr = l.get("producto")
        productos.append({
            "producto": pr,
            "volumen": _fmt(l.get("real")),                 # string ya formateado (fuente de la salvaguarda)
            "unidad": _UNIDAD.get(pr, ""),
            "porcentaje_presupuesto": l.get("cumplimiento"),
            "clasificacion": l.get("estado") or "sin meta",
        })
    entidad = respuesta.get("entidad")
    acciones = [f"Analizar {entidad}" if entidad else "Analizar la entidad"]
    if mes.get("dias_con_data"):
        acciones.append("Ver el reporte de un dia")
    u = (usuario or "").strip() or None
    return {
        "usuario": u,
        "entidad": entidad,
        "nivel": respuesta.get("nivel"),
        "periodo": {"mes": mes.get("nombre"), "anio": mes.get("anio"),
                    "dias_reportados": mes.get("dias_con_data"),
                    "dias_del_mes": mes.get("dias_del_mes"), "cerrado": mes.get("completo")},
        "cobertura": respuesta.get("pie"),   # frase determinista de cobertura (grano diario o cierre mensual)
        "productos": productos,
        "acciones_disponibles": acciones,
    }


def _cumple_regla_numerica(texto: str, payload: dict) -> bool:
    """D-N5: cada volumen del JSON debe aparecer LITERAL en la narración (anti-alucinación numérica)."""
    for p in payload["productos"]:
        v = p.get("volumen")
        if v and v not in texto:
            return False
    return True


def narrar(respuesta: dict, usuario=None) -> dict | None:
    """Devuelve {texto, generado_por, diag} o None (→ el frontend usa la plantilla determinista).
    None cuando: flag off · respuesta no aplicable · timeout/red · salida vacía · regla numérica violada."""
    s = get_settings()
    if not getattr(s, "consulta_narra_llm", False):
        return None
    if not respuesta or not respuesta.get("aplica") or not respuesta.get("lineas"):
        return None
    payload = _payload(respuesta, usuario)
    prompt = (_SISTEMA + "\n\nNarra este resultado al analista:\n```json\n"
              + _json.dumps(payload, ensure_ascii=False) + "\n```\nTexto narrado:")
    diag = {"status": "?", "model": s.consulta_llm_model, "host": s.consulta_ollama_url}
    try:
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt, "stream": False,
                            "options": {"temperature": 0, "num_predict": 320}}).encode()
        req = _urlreq.Request(s.consulta_ollama_url, data=body,
                              headers={"Content-Type": "application/json"})
        with _urlreq.urlopen(req, timeout=60) as r:
            texto = (_json.load(r).get("response", "") or "").strip()
    except Exception as e:
        diag["status"] = "timeout_o_red:" + type(e).__name__
        return None
    diag["raw"] = texto[:800]
    diag["raw_len"] = len(texto)
    if not texto:
        diag["status"] = "vacio"
        return None
    if not _cumple_regla_numerica(texto, payload):
        diag["status"] = "regla_numerica"
        return None
    diag["status"] = "ok"
    return {"texto": texto, "generado_por": "llm", "diag": diag}
```

### C · `maquina.py` — threading `usuario` + adjuntar narración

**C.1** — En el import (líneas 1-6), añadir el import de `narrar`. Localizar:

```python
from app.features.consulta.ejecucion import ejecutar
```
Reemplazar por:
```python
from app.features.consulta.ejecucion import ejecutar
from app.features.consulta.narracion import narrar
```

**C.2** — Firma de `preguntar`. Localizar:
```python
def preguntar(texto: str, cid: str) -> dict:
    """S0 EXTRAER → S1 RESOLVER → (completo | pendiente con botones)."""
```
Reemplazar la firma por:
```python
def preguntar(texto: str, cid: str, usuario=None) -> dict:
    """S0 EXTRAER → S1 RESOLVER → (completo | pendiente con botones). usuario: nombre para la narración."""
```

**C.3** — Retorno de `preguntar`. Localizar (única ocurrencia en la función):
```python
            _guardar(cid, intent)
    return _salida(intent)
```
Reemplazar por:
```python
            _guardar(cid, intent)
    return _salida(intent, usuario)
```

**C.4** — Firma de `responder`. Localizar:
```python
def responder(cid: str, opcion_id: str) -> dict:
    """S3 REANUDAR: aplica la opción elegida → intent completo."""
```
Reemplazar por:
```python
def responder(cid: str, opcion_id: str, usuario=None) -> dict:
    """S3 REANUDAR: aplica la opción elegida → intent completo. usuario: nombre para la narración."""
```

**C.5** — Retorno de `responder`. Localizar:
```python
    _fijar_resuelta(intent, op)
    _PARCIAL.pop(cid, None)
    return _salida(intent)
```
Reemplazar por:
```python
    _fijar_resuelta(intent, op)
    _PARCIAL.pop(cid, None)
    return _salida(intent, usuario)
```

**C.6** — Firma de `_salida`. Localizar:
```python
def _salida(intent: dict) -> dict:
    out = {"status": intent["status"]}
```
Reemplazar por:
```python
def _salida(intent: dict, usuario=None) -> dict:
    out = {"status": intent["status"]}
```

**C.7** — Adjuntar la narración. Localizar el bloque `try/except` de `ejecutar()`:
```python
        try:
            out["respuesta"] = ejecutar(r, intent.get("producto"), intent.get("periodo"),
                                        intent.get("agregacion"))
        except Exception:
            logging.getLogger("consulta.ejecucion").exception("ejecutar() falló")
            out["respuesta"] = {"aplica": False,
                                "texto": "No pude calcular la cifra en este momento. Intenta de nuevo."}
    return out
```
Reemplazar por:
```python
        try:
            out["respuesta"] = ejecutar(r, intent.get("producto"), intent.get("periodo"),
                                        intent.get("agregacion"))
        except Exception:
            logging.getLogger("consulta.ejecucion").exception("ejecutar() falló")
            out["respuesta"] = {"aplica": False,
                                "texto": "No pude calcular la cifra en este momento. Intenta de nuevo."}
        # Fase 3.1 (opcional, flag CONSULTA_NARRA_LLM): el LLM redacta la cifra ya calculada. La
        # determinista sigue siendo la fuente de verdad + fallback; la narración es capa encima (D-N1).
        try:
            nar = narrar(out.get("respuesta"), usuario)
            if nar:
                out["respuesta"]["narracion"] = nar
        except Exception:
            logging.getLogger("consulta.narracion").exception("narrar() falló")
    return out
```

### D · `api.py` (consulta) — campo `usuario` en los bodies

Reemplazar el archivo COMPLETO por:

```python
from fastapi import APIRouter
from pydantic import BaseModel
from app.features.consulta import maquina

router = APIRouter(prefix="/consulta")

class Preguntar(BaseModel):
    texto: str
    conversation_id: str
    usuario: str | None = None

class Responder(BaseModel):
    conversation_id: str
    opcion_id: str
    usuario: str | None = None

@router.post("/preguntar")
def preguntar(body: Preguntar):
    return maquina.preguntar(body.texto, body.conversation_id, body.usuario)

@router.post("/responder")
def responder(body: Responder):
    return maquina.responder(body.conversation_id, body.opcion_id, body.usuario)
```

### E · `routes\api.py` — subir timeout de `/consulta/responder` (F-N1)

Localizar:
```python
        resp = requests.post(f"{INGESTA_API_URL}/consulta/responder", json=request.get_json(), timeout=30)
```
Reemplazar por:
```python
        resp = requests.post(f"{INGESTA_API_URL}/consulta/responder", json=request.get_json(), timeout=90)
```
> El proxy ya reenvía `request.get_json()` verbatim → el campo `usuario` fluye sin cambios extra.

### F · `static\js\multitab_shell.js` — enviar `usuario` + pintar narración

**F.1** — Enviar `usuario` en `/preguntar`. Localizar:
```javascript
    fetch("/api/consulta/preguntar", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({texto: texto, conversation_id: __cnCid})})
```
Reemplazar por:
```javascript
    fetch("/api/consulta/preguntar", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({texto: texto, conversation_id: __cnCid, usuario: __cnNombre()})})
```

**F.2** — Enviar `usuario` en `/responder`. Localizar:
```javascript
    fetch("/api/consulta/responder", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({conversation_id: __cnCid, opcion_id: opcionId})})
```
Reemplazar por:
```javascript
    fetch("/api/consulta/responder", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({conversation_id: __cnCid, opcion_id: opcionId, usuario: __cnNombre()})})
```

**F.3** — Pintar la narración si viene. Reemplazar la función `__cnRespuestaHtml` COMPLETA:
```javascript
  function __cnRespuestaHtml(resp) {
    // Fase 3 determinista: burbuja con la cifra REAL vs PPTO. Sin resp -> nota honesta (compat).
    if (!resp) return '<p class="rb-chat__note">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</p>';
    if (!resp.aplica) return '<p class="rb-chat__note">' + esc(resp.texto || "") + '</p>';
    var lis = (resp.lineas || []).map(function (l) {
      return '<li class="cn-answer__row">' + esc(l.texto) + '</li>';
    }).join("");
    var av = (resp.avisos && resp.avisos.length)
      ? '<p class="rb-chat__note">' + resp.avisos.map(esc).join(" ") + '</p>' : "";
    return '<div class="cn-answer">' +
      '<div class="cn-answer__head">' + esc(resp.encabezado || "") + '</div>' +
      '<ul class="cn-answer__list">' + lis + '</ul>' +
      (resp.pie ? '<p class="rb-chat__note">' + esc(resp.pie) + '</p>' : "") + av +
      '</div>';
  }
```
por:
```javascript
  function __cnRespuestaHtml(resp) {
    // Fase 3 determinista: burbuja con la cifra REAL vs PPTO. Sin resp -> nota honesta (compat).
    if (!resp) return '<p class="rb-chat__note">Por ahora dejo el pedido listo; el número real llega en la siguiente fase.</p>';
    if (!resp.aplica) return '<p class="rb-chat__note">' + esc(resp.texto || "") + '</p>';
    var av = (resp.avisos && resp.avisos.length)
      ? '<p class="rb-chat__note">' + resp.avisos.map(esc).join(" ") + '</p>' : "";
    // Fase 3.1: si el LLM redactó la narración (flag CONSULTA_NARRA_LLM en prod), se muestra la prosa
    // (ya incluye el saludo con el nombre → NO se antepone __cnConNombre). Si no viene (dev / fallo /
    // flag off / regla numérica violada), la plantilla determinista de siempre.
    if (resp.narracion && resp.narracion.texto) {
      try { console.log("[narración] " + resp.narracion.generado_por, resp.narracion.diag || {}); } catch (e) {}
      return '<div class="cn-answer cn-answer--narrada"><p class="cn-answer__prosa">' +
        esc(resp.narracion.texto) + '</p>' + av + '</div>';
    }
    var lis = (resp.lineas || []).map(function (l) {
      return '<li class="cn-answer__row">' + esc(l.texto) + '</li>';
    }).join("");
    return '<div class="cn-answer">' +
      '<div class="cn-answer__head">' + esc(resp.encabezado || "") + '</div>' +
      '<ul class="cn-answer__list">' + lis + '</ul>' +
      (resp.pie ? '<p class="rb-chat__note">' + esc(resp.pie) + '</p>' : "") + av +
      '</div>';
  }
```

### G · `static\css\colapsable.css` — estilos de la narración

Localizar la línea (≈1275) que cierra el bloque `.cn-answer` existente:
```css
.cn-answer__row:last-child { border-bottom: 0; }
```
Añadir INMEDIATAMENTE DESPUÉS:
```css
/* Fase 3.1 · narración redactada por el LLM (párrafo en vez de viñetas) */
.cn-answer--narrada { margin-bottom: 10px; }
.cn-answer__prosa { margin: 0; font-size: .9rem; line-height: 1.55; color: var(--rb-ink); }
```
> `--rb-ink` (#1b2a33) ya está definido (línea 92) → sin fallback; coincide con el color del chat.

### H · `templates\main.html` — cache-buster

Reemplazar en la **línea 5**:
```html
    <link rel="stylesheet" href="{{ url_for('static', filename='css/colapsable.css') }}?v=20260715n">
```
por `?v=20260715o`. Y en la **línea 82**:
```html
<script src="{{ url_for('static', filename='js/multitab_shell.js') }}?v=20260715n"></script>
```
por `?v=20260715o`.

---

## 6. Orden de ejecución

1. A (flag) → 2. B (narracion.py) → 3. C (maquina.py) → 4. D (api.py) → 5. E (proxy timeout)
→ 6. F (JS) → 7. G (CSS) → 8. H (cache-buster).
9. Reiniciar el backend INGESTA (`:8000`) para recargar el módulo nuevo.

---

## 7. Reglas no negociables

- **No tocar** `ejecucion.py`, `resolver.py`, `desempeno`/`ejecutivo` de análisis, DDL, ETL ni grano.
- La narración **NUNCA** es la fuente de los números: si el flag está off o el LLM falla, el usuario
  ve la **plantilla determinista** (D-N3). No mostrar errores crudos del LLM al usuario.
- **Salvaguarda numérica obligatoria** (D-N5): sin el volumen literal en la prosa → se descarta.
- **No** cambiar el `.env` (el flag se activa en 139 por separado). En dev queda off por default.
- Mantener el `usuario` como campo **opcional** (`str | None = None`) en todas las firmas → 100%
  retrocompatible con llamadas viejas.

---

## 8. Validaciones (comando → resultado esperado)

> El backend de narración usa `get_settings()` en caliente; para probar la rama LLM sin editar el
> `.env`, se fuerza el flag por variable de entorno en la misma shell.

**V1 · Import y fallback (flag OFF, sin LLM):**
```
cd INGESTA\Rep_Prod\backend
uv run python -c "from app.features.consulta.narracion import narrar; print(narrar({'aplica':True,'entidad':'X','nivel':'campo','mes':{'nombre':'Mayo','anio':2026,'dias_con_data':17,'dias_del_mes':31,'completo':False},'lineas':[{'producto':'CRUDO','real':12357703,'cumplimiento':95.6,'estado':'Alineado'}]}))"
```
Esperado: `None` (flag off → no narra). **Sin excepción.**

**V2 · Payload correcto y salvaguarda numérica (unit test aislado, sin BD ni LLM):**
```
uv run python -c "from app.features.consulta.narracion import _payload,_cumple_regla_numerica; p=_payload({'aplica':True,'entidad':'RUBIALES','nivel':'campo','mes':{'nombre':'Mayo','anio':2026,'dias_con_data':17,'dias_del_mes':31,'completo':False},'lineas':[{'producto':'CRUDO','real':12357703,'cumplimiento':95.6,'estado':'Alineado'}]},'Javier'); print(p['productos'][0]['volumen'], p['productos'][0]['unidad'], p['usuario']); print(_cumple_regla_numerica('... 12.357.703 barriles ...',p), _cumple_regla_numerica('... 999 ...',p))"
```
Esperado: `12.357.703 barriles Javier` y luego `True False`.

**V3 · Rama LLM real (flag ON, requiere Ollama de Consulta arriba):**
```
set CONSULTA_NARRA_LLM=true
uv run python -c "from app.features.consulta.narracion import narrar; r=narrar({'aplica':True,'entidad':'RUBIALES','nivel':'campo','mes':{'nombre':'Mayo','anio':2026,'dias_con_data':17,'dias_del_mes':31,'completo':False},'lineas':[{'producto':'CRUDO','real':12357703,'cumplimiento':95.6,'estado':'Alineado'}]},'Javier'); print(r and r['diag']['status']); print(r and r['texto'])"
set CONSULTA_NARRA_LLM=
```
Esperado: `ok` + un párrafo de 2-3 oraciones que **contiene `12.357.703`**, menciona `95.6`, la
palabra `Alineado`, `Rubiales`, `mayo` y `17`/`31`. Si el Ollama no está, esperado: `None` (fallback,
no error). **Spot-check F-N2:** confirmar que "barriles" acompaña al crudo y que el gas (si se probara)
no lleva unidad inventada.

**V4 · End-to-end determinista (flag OFF, no regresión) — round-trip HTTP:**
```
uv run python -c "import urllib.request,json; d=json.dumps({'texto':'cuanto produjo Rubiales de crudo','conversation_id':'v4','usuario':'Javier'}).encode(); r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/consulta/preguntar',data=d,headers={'Content-Type':'application/json'}),timeout=90); o=json.load(r); print(o['status']); print('narracion' in o.get('respuesta',{})); print(o['respuesta']['encabezado'])"
```
Esperado: `completo`, `False` (flag off → sin narración), y el encabezado determinista
`RUBIALES · Mayo 2026 · corte 17/31` intacto.

**V5 · Suite existente (no regresión):**
```
cd INGESTA\Rep_Prod\backend
uv run pytest -q
```
Esperado: mismos verdes que antes (25 passed / 1 skipped o el conteo vigente), **0 fallos nuevos**.

**V6 · Navegador (flag ON en un entorno con Ollama):** en la pestaña **Consulta**, preguntar
"cuánto produjo Rubiales de crudo" → la burbuja muestra el **párrafo narrado** (con "Javier, …" si hay
sesión), sin viñetas; la consola imprime `[narración] llm {status:"ok"...}`. Con flag OFF → la burbuja
muestra el bloque determinista de siempre. El panel derecho (Desempeño / Ejecutivo) **no cambia**.

---

## 9. Fuera de alcance (explícito)

- **Unidad de gas** (F-N2): queda sin unidad hasta confirmar KPC vs KPCD por spot-check con el usuario.
- Narrar entidades **rama B (filial)** o **agua**: `ejecutar()` ya devuelve `aplica:false` → no se narra
  (se muestra su texto honesto). Sin cambios.
- **Comportamiento conocido (F-A4)**: una pregunta **sin producto** (3 cifras) puede narrar bien o caer
  al **fallback determinista** si la salvaguarda no ve los 3 volúmenes literales — ambos resultados son
  correctos; no se fuerza la narración multi-producto.
- Streaming de la narración token a token (hoy es una sola llamada bloqueante ≤60s).
- Activar el flag en 139 (`.env`) — operación separada del usuario, no de este plan.
- Narrar la **desambiguación** (la pregunta "encontré X de N formas…") — sigue con su plantilla V2.

---

## 10. Criterio de aceptación (resumen)

✅ Flag `CONSULTA_NARRA_LLM` off por default → comportamiento idéntico al actual (determinista).
✅ Flag on + Ollama → burbuja con párrafo narrado que **contiene el volumen literal** y el nombre.
✅ Cualquier fallo del LLM → fallback determinista silencioso (nunca error al usuario).
✅ `uv run pytest -q` sin fallos nuevos. ✅ Panel derecho intacto. ✅ `usuario` opcional y retrocompatible.
