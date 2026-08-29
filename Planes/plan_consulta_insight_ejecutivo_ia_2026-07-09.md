# Plan ejecutable — Consulta · "Titular ejecutivo (IA)" anclado al panel de desempeño (V1)

> **Cobertura:** N/A (feature de análisis de lectura). NO toca DDL/ETL/grano.
> **Tipo:** backend (1 endpoint nuevo con LLM, solo lectura) + 1 proxy Flask + frontend (JS/CSS/cache-buster).
> **Estado:** v2 auditado (§0.2). Patrón LLM, algoritmo de valle y eventos VERIFICADOS contra BD/código.
> **Principio rector:** *"Python calcula, el LLM solo concluye"* — cero cifras del modelo.
> **Layout (nuevo formato del usuario):** 3 columnas → **[Titular ejecutivo IA] · [KPI cards] · [Real vs
> Presupuesto + curva plana]**. El panel IA es autocontenido (tiene su PROPIA curva anotada de crudo).

---

## 0. TL;DR

El panel de desempeño (`__cnAnalizar` → `__cnRenderDesemp`) hoy tiene 2 columnas (KPIs | barras+curva).
Este plan lo lleva a **3 columnas** añadiendo, como **primera columna**, un **"Titular ejecutivo (IA)"**
que llega desde un **contrato JSON** (no HTML): Python pone números/fechas/coordenadas; el LLM solo rellena
prosa. El insight es **on-demand** (botón "Generar resumen") para controlar latencia/RAM en dev.

Piezas del panel IA (columna 1):
1. **Titular** — 3 chips semáforo (estado + %).
2. **Curva anotada de crudo** — su propia mini-curva con **banda del valle** (09→14) + **pin del mínimo**
   (11-may) — coordenadas de Python.
3. **Eventos** — tabla "Por qué el valle" (de `fact_comentarios_produccion`).
4. **Lectura ejecutiva** — párrafo del LLM + botones de acción (placeholder).

---

## 1. Contexto

- El panel vive en el **MultiTab Shell / pestaña Consulta**, no en el chatbot principal.
- `/analisis/desempeno` (ya existe) devuelve `por_producto` (real/ppto/cumplimiento) + `curva` (fechas +
  series por producto) + `mes`. `__cnAnalizar(entidad)` lo pinta con `__cnRenderDesemp`.
- El LLM de Consulta ya está parametrizado: `CONSULTA_OLLAMA_URL` / `CONSULTA_LLM_MODEL` (dev qwen2.5:3b ·
  prod gemma4:latest), y se llama con `urllib` (ver `features/consulta/extraccion.py`).
- Eventos: `core.fact_comentarios_produccion` (texto libre por activo/área, con nº de pozos citado).

---

## 2. Objetivo, contrato JSON y decisiones

`GET /api/analisis/desempeno_insight?entidad=<E>` devuelve el **contrato JSON**:

```json
{
  "meta": {"scope": "...", "periodo": "Mayo 2026", "corte": "17/31", "generado_por": "llm|fallback"},
  "titular": [
    {"producto": "CRUDO",   "estado": "ok",    "valor_pct": 94.7, "texto": "Alineado"},
    {"producto": "GAS",     "estado": "warn",  "valor_pct": 87.0, "texto": "-13 pp"},
    {"producto": "BLANCOS", "estado": "alert", "valor_pct": 58.5, "texto": "Foco"}
  ],
  "curva_crudo": {"fechas": ["2026-05-01", ...], "valores": [2860093, ...]},
  "anotaciones": {
    "banda":  {"desde": "2026-05-09", "hasta": "2026-05-14", "label": "valle explicado"},
    "punto":  {"fecha": "2026-05-11", "valor": 2829334, "label": "min · 2.83M"}
  },
  "eventos": [{"campo": "APIAY", "evento": "Falla de red (TR2 CDS-CDA)", "pozos": 73}, ...],
  "eventos_extra": {"campos": 5, "pozos_aprox": 62, "fecha": "2026-05-09"},
  "lectura_ejecutiva": "El rezago de blancos (58.5%)...",
  "accion_sugerida": [{"label": "Diagnóstico de blancos", "intent": "diagnostico_blancos"}, ...]
}
```

**Responsabilidad (quién llena qué) — NO NEGOCIABLE:**

| Campo | Origen | |
|---|---|---|
| `titular[].valor_pct`, `titular[].estado` | **Python** | % real/ppto; estado por umbrales fijos |
| `titular[].texto` | LLM | 1-2 palabras (prosa) |
| `curva_crudo`, `anotaciones.*` (fechas/valores) | **Python** | serie + detección de valle |
| `anotaciones.*.label` | LLM | callout corto |
| `eventos[]`, `eventos_extra` | **Python** | de `fact_comentarios_produccion` |
| `lectura_ejecutiva` | LLM | 2-3 frases |
| `accion_sugerida[].intent` | **Python** | enum cerrado |
| `accion_sugerida[].label` | Python (MVP) | estático por intent (Fase 2: LLM) |

**Decisiones cerradas:**
- **DI1 — On-demand:** el insight NO se carga solo; botón "✨ Generar resumen ejecutivo (IA)" en la col. 1.
  (Controla la RAM de qwen-CPU en dev; en prod/gemma4 se podría auto-cargar — Fase 2.)
- **DI2 — Umbrales de estado (Python) = 90/75:** `>=90` ok · `>=75` warn · `<75` alert. Coincide con el
  mockup (CRUDO 94.7 → verde "Alineado"). **Se alinea `__cnSemColor` (JS) al mismo 90/75** para que las KPI
  cards y el titular tengan el MISMO color (hoy el JS usa 95/85 → CRUDO saldría ámbar, incoherente).
- **DI3 — Cifras SIEMPRE de `mes` (H2 previo):** `titular.valor_pct` = REAL vs PPTO mensual. La curva/valle
  usa `día` solo para forma (nunca alimenta el %).
- **DI4 — El LLM NO calcula:** se ignora cualquier número que devuelva; Python inyecta los suyos.
- **DI5 — Fallback estático** con la MISMA forma de dict (prosa por plantilla) si el LLM falla/timeout.
- **DI6 — Curva IA propia (opción del mockup):** el panel IA dibuja su propia curva de crudo anotada
  (segunda instancia Plotly), separada de la curva plana con selector de la col. 3.

---

## 3. Prerequisitos

- Backend INGESTA `:8000` (con LLM de Consulta accesible: `CONSULTA_OLLAMA_URL`) + Flask `:8020`.
- BD con datos ECP + comentarios (dev: crudo diario hasta 17-may; comentarios en reportes de mayo).
- Consulta → resolver una entidad ECP (ej. **Castilla**) o cargar el **global** (por defecto al abrir).

---

## 4. Inventario de archivos

| Archivo (ruta absoluta) | Cambio |
|---|---|
| `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | + endpoint `desempeno_insight()` + helpers `_detectar_valle`, `_eventos_valle`, `_llm_insight` (append) |
| `...\routes\api.py` | + proxy `/analisis/desempeno_insight` |
| `...\static\js\multitab_shell.js` | grid de 3 col en `__cnRenderDesemp`; `__cnDesempInsight`, `__cnRenderIns`, `__cnInsCurvaPlot`; ajuste umbrales `__cnSemColor` (DI2); guardar/limpiar `__cnDesempAnot` |
| `...\static\css\colapsable.css` | + bloque `.cn-ins*` + `.cn-desemp__grid3` (append) |
| `...\templates\main.html` | cache-buster `?v=20260709l` → `?v=20260709m` (JS) |

**Se REUTILIZA:** patrón LLM de `extraccion.py` (`urllib` + `extraer_json`); `get_settings()`
(`consulta_ollama_url`/`consulta_llm_model`); resolución de entidad de `densidad`; `MESES_ES`; helpers JS
`el/esc/__cnMilesEC/__cnViewerArea/__cnLastIntent/__cnVolverPanorama/window.Plotly`; colores semáforo `.is-ok/is-warn/is-bad`.

---

## 5. Hallazgos de auditoría VERIFICADOS (INS1–INS7)

- **INS1 (patrón LLM, verificado)** — `extraccion.py` llama al LLM con `urllib.request` →
  `{"model":MODELO,"prompt":...,"stream":False,"options":{"temperature":0}}`, timeout 60, respuesta en
  `response`; parseo con `extraer_json` (regex `\{.*\}` + `json.loads`, None si falla). **Se reusa igual.**
- **INS2 (detección de valle, verificado en BD)** — con media del mes y umbral **−0.3%**, tomando el run
  contiguo más largo de **≥3 días** bajo umbral: sobre el crudo diario de mayo da **09→14 may, mínimo
  11-may = 2.829.334**. (Los días 03 y 17, aislados, se descartan por longitud <3.) Media ≈ 2.852M.
- **INS3 (umbral de estado, DI2)** — el mockup pinta CRUDO 94.7% en **verde**; con el `__cnSemColor` actual
  (95/85) saldría ámbar. Se fija **90/75** en Python (titular) **y** en `__cnSemColor` (KPI cards) para que
  coincidan. Resultado: CRUDO verde, GAS ámbar, BLANCOS rojo (= mockup).
- **INS4 (eventos, verificado)** — `fact_comentarios_produccion` en las fechas del valle trae los eventos
  con nº de pozos citado textualmente (APIAY 73, Tibú 43, Caracará 42…, ≈220 pozos el 9-may). Se extrae el
  entero con regex `(\d+)\s*pozos` (suma por comentario) y se rankea desc.
- **INS5 (2 curvas, DI6)** — el mockup muestra 2 curvas (IA anotada + plana con selector). Son 2 instancias
  Plotly. Se acepta (opción del usuario); la IA reusa `curva_crudo` del propio payload (self-contained).
- **INS6 (frontera respetada)** — Python arma titular.valor_pct/estado, anotaciones (coords), eventos y los
  intents; el LLM SOLO redacta `texto`, `label`, `lectura_ejecutiva`. Se ignoran números del LLM.
- **INS7 (on-demand, DI1)** — qwen2.5:3b en dev es pesado (100% CPU/2.2GB) → el insight se genera al pulsar
  el botón, no al cargar el panel. En prod (gemma4) es rápido; auto-carga queda para Fase 2.

**Correcciones de la 2ª auditoría (bugs cazados antes de ejecutar):**

- **INS-A (CORRECTITUD — verificado en BD) — Eventos SOLO del día de inicio del valle.** Consultar el rango
  09-14 **duplica** el mismo evento (se repite "en estabilización" cada día) → el top-5 sale corrupto
  (`NO OPERADOS 164` repetido ×3). El **onset 09-may solo** da **10 eventos limpios**: APIAY 73 · Tibú 43 ·
  Caracará 42 (= mockup). `_eventos_valle` usa `fecha_reporte = :onset`.
- **INS-A2 (verificado) — Campo = `area`, no `activos`.** El nombre que muestra el mockup (Tibú, Caracará)
  está en `fc.area`; `fc.activos` trae la agrupación (CATENARE, NO OPERADOS). Se usa
  `COALESCE(NULLIF(TRIM(area),''), activos)`.
- **INS-B (CORRECTITUD) — `_estado(None)` → chip neutral, NO rojo.** Para una entidad que no produce un
  producto (ej. Castilla no tiene gas), `valor_pct=None`; devolver "alert" pintaría un chip rojo "Foco"
  engañoso. Se devuelve "" (neutral). El front ya usa `__cnSemColor(valor_pct)` que también es neutral en null.
- **INS-C (robustez) — `get_settings()` LAZY.** Se eliminó el `_INS_SET = get_settings()` a nivel de módulo
  (acoplaba el import de TODO el feature `analisis` al settings); ahora se llama dentro de `_llm_insight`.
- **INS-F (limpieza) — Eliminado `__cnDesempAnot`.** La curva IA recibe las anotaciones directo del payload
  en `__cnInsCurvaPlot`; no se necesita variable global. Se evita depender de var-hoisting. (Reintroducir
  en Fase 2 si se anota la curva plana.)
- **INS-D/E (anclas)** — verificados los textos exactos a editar: `return` de `__cnRenderDesemp` (~L1196-1203,
  bloque `cn-desemp__layout`), `__cnSemColor` (95/85 → 90/75), y que **NO** se toca `__cnAnalizar`.

---

## 6. Especificación

### 6.1 Backend — `analisis\api.py` (append al final)

```python


# ============================================================================
# Titular ejecutivo (IA) — contrato JSON. Python calcula números/fechas/eventos;
# el LLM (CONSULTA_OLLAMA_URL) SOLO redacta prosa. Fallback estático con la misma forma.
# ============================================================================
import json as _json, re as _re, urllib.request as _urlreq
from app.core.config import get_settings   # INS-C: se llama LAZY dentro de _llm_insight (no a nivel módulo)

def _estado(pct):
    if pct is None:
        return ""   # INS-B: producto inexistente (ej. Castilla no produce gas) -> chip neutral, NO rojo
    return "ok" if pct >= 90 else ("warn" if pct >= 75 else "alert")

def _detectar_valle(serie):
    """serie = [(iso, valor)] ordenada. Valle = run contiguo más largo de >=3 días bajo media*0.997."""
    if len(serie) < 5:
        return None
    vals = [v for _, v in serie]
    umbral = (sum(vals) / len(vals)) * 0.997
    runs, cur = [], []
    for f, v in serie:
        if v < umbral:
            cur.append((f, v))
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = []
    if len(cur) >= 3:
        runs.append(cur)
    if not runs:
        return None
    valle = max(runs, key=len)
    mn = min(valle, key=lambda x: x[1])
    return {"desde": valle[0][0], "hasta": valle[-1][0], "min_fecha": mn[0], "min_valor": mn[1]}

def _eventos_valle(c, onset):
    """Top eventos (campo, evento, pozos) del DÍA DE INICIO del valle.
    INS-A (verificado en BD): consultar TODO el rango 09-14 duplica el mismo evento (se repite
    'en estabilización' cada día) → ranking basura. Solo el onset (09-may) da los 10 eventos limpios.
    INS-A2: el nombre del campo va en `area` (Tibú/Caracará), no en `activos` (CATENARE/NO OPERADOS)."""
    rows = c.execute(sa.text("""
        SELECT COALESCE(NULLIF(TRIM(fc.area),''), fc.activos) AS campo, fc.comentario
        FROM core.fact_comentarios_produccion fc
        JOIN core.config_reporte cr ON cr.reporte_id = fc.reporte_id
        WHERE cr.fecha_reporte = :d
          AND fc.comentario IS NOT NULL AND LENGTH(TRIM(fc.comentario)) > 5
    """), {"d": onset}).all()
    items = []
    for campo, com in rows:
        pozos = sum(int(x) for x in _re.findall(r"(\d+)\s*pozos", com or ""))
        if pozos <= 0:
            continue
        evento = (com or "").strip().split(".")[0][:70]
        items.append({"campo": (campo or "").strip(), "evento": evento, "pozos": pozos})
    items.sort(key=lambda x: x["pozos"], reverse=True)
    top, resto = items[:3], items[3:]
    extra = {"campos": len(resto), "pozos_aprox": sum(i["pozos"] for i in resto),
             "fecha": onset.isoformat()}
    return top, extra

def _llm_insight(prompt):
    """Reusa el patrón de extraccion.py. Devuelve dict o None (fallback). get_settings() LAZY (INS-C)."""
    try:
        s = get_settings()
        body = _json.dumps({"model": s.consulta_llm_model, "prompt": prompt,
                            "stream": False, "options": {"temperature": 0}}).encode()
        req = _urlreq.Request(s.consulta_ollama_url, data=body,
                              headers={"Content-Type": "application/json"})
        with _urlreq.urlopen(req, timeout=60) as r:
            salida = _json.load(r).get("response", "")
        m = _re.search(r"\{.*\}", salida, _re.DOTALL)
        return _json.loads(m.group(0)) if m else None
    except Exception:
        return None


@router.get("/desempeno_insight")
def desempeno_insight(entidad: str | None = Query(None)):
    import calendar
    eng = get_engine()
    with eng.connect() as c:
        ids, vid = [], None
        if entidad:
            E = entidad.strip().upper()
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e OR UPPER(TRIM(grupo1))=:e
                   OR UPPER(TRIM(activos))=:e OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E}).all()]
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"), {"e": E}).scalar()
            if not ids and vid is None:
                return {"entidad": entidad, "encontrada": False}
        base = {}
        if ids: base["ids"] = ids
        if vid is not None: base["vid"] = vid
        def _b(sql):
            t = sa.text(sql)
            return t.bindparams(sa.bindparam("ids", expanding=True)) if "ids" in base else t
        def where(a):
            p = (a + ".") if a else ""
            cs = []
            if ids: cs.append(f"{p}fuente_id IN :ids")
            if vid is not None: cs.append(f"{p}vice_id = :vid")
            return "(" + " OR ".join(cs) + ")" if cs else "TRUE"

        # mes objetivo (último con crudo diario)
        maxd = c.execute(_b(f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {where('')}"), base).scalar()
        if maxd is None:
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        y, mo = maxd.year, maxd.month
        dim = calendar.monthrange(y, mo)[1]
        ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"

        # KPIs REAL vs PPTO (mensual) — mismos que /desempeno (DI3, H2)
        pm = dict(base); pm["fin"] = fin
        kpi = {}
        for r in c.execute(_b(f"""
            SELECT tp.nombre, es.nombre, SUM(m.volumen)
            FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE m.fecha = :fin AND es.nombre IN ('REAL','PPTO') AND {where('m')}
            GROUP BY 1,2"""), pm):
            kpi.setdefault(r[0], {})[r[1]] = float(r[2] or 0)
        titular = []
        for p in ["CRUDO", "GAS", "BLANCOS"]:
            real = kpi.get(p, {}).get("REAL", 0.0); ppto = kpi.get(p, {}).get("PPTO", 0.0)
            pct = round(real / ppto * 100.0, 1) if ppto else None
            titular.append({"producto": p, "valor_pct": pct, "estado": _estado(pct), "texto": ""})

        # serie crudo diaria → detección de valle
        pd = dict(base); pd["ini"] = ini; pd["fin"] = fin
        srows = c.execute(_b(f"""
            SELECT d.fecha, SUM(d.volumen)
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE tp.nombre='CRUDO' AND d.fecha BETWEEN :ini AND :fin AND {where('d')}
            GROUP BY 1 ORDER BY 1"""), pd).all()
        serie = [(r[0].isoformat(), float(r[1] or 0)) for r in srows]
        valle = _detectar_valle(serie)
        curva_crudo = {"fechas": [f for f, _ in serie], "valores": [v for _, v in serie]}

        anotaciones, eventos, eventos_extra = None, [], {"campos": 0, "pozos_aprox": 0}
        if valle:
            from datetime import date as _date
            dd = [int(x) for x in valle["desde"].split("-")]
            eventos, eventos_extra = _eventos_valle(c, _date(*dd))   # INS-A: solo el día de inicio del valle
            anotaciones = {
                "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
                "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"], "label": ""},
            }

        # ---- Prosa: LLM (grounded) o fallback estático ----
        peor = min([t for t in titular if t["valor_pct"] is not None],
                   key=lambda t: t["valor_pct"], default=None)
        ctx = {"periodo": f"{MESES_ES[mo]} {y}", "corte": f"{len([1 for _ in serie])}/{dim}",
               "titular": [{"p": t["producto"], "pct": t["valor_pct"]} for t in titular],
               "valle": valle, "eventos": eventos}
        prompt = (
            "Eres analista de producción. Con estos datos EXACTOS (no inventes ni calcules números, no "
            "agregues cifras nuevas), responde SOLO un JSON de una línea con estos campos de texto: "
            '{"texto_crudo","texto_gas","texto_blancos","label_valle","lectura_ejecutiva"}. '
            "texto_*: 1-2 palabras de estado (ej. Alineado/Rezagado/Foco). label_valle: <=4 palabras. "
            "lectura_ejecutiva: 2-3 frases ejecutivas. Datos: " + _json.dumps(ctx, ensure_ascii=False))
        prosa = _llm_insight(prompt)
        generado = "llm"
        if not isinstance(prosa, dict) or "lectura_ejecutiva" not in prosa:
            generado = "fallback"
            _et = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco"}
            prosa = {
                "texto_crudo": _et[titular[0]["estado"]], "texto_gas": _et[titular[1]["estado"]],
                "texto_blancos": _et[titular[2]["estado"]], "label_valle": "valle explicado",
                "lectura_ejecutiva": (
                    (f"El mayor rezago es {peor['producto'].lower()} ({peor['valor_pct']}%). "
                     if peor else "") +
                    ("La caída de crudo del valle está explicada por eventos operativos y ya se recuperó."
                     if valle else "Producción sin anomalías diarias relevantes en el periodo.")),
            }
        # merge prosa (SOLO texto) — nunca números del LLM
        _tx = {"CRUDO": prosa.get("texto_crudo"), "GAS": prosa.get("texto_gas"),
               "BLANCOS": prosa.get("texto_blancos")}
        for t in titular:
            t["texto"] = str(_tx.get(t["producto"]) or "")[:24]
        if anotaciones:
            anotaciones["banda"]["label"] = str(prosa.get("label_valle") or "valle")[:28]
            mv = anotaciones["punto"]["valor"]
            anotaciones["punto"]["label"] = f"mín · {mv/1e6:.2f}M"

        # acciones (intents Python; label estático MVP)
        acciones = []
        if peor:
            acciones.append({"label": f"Diagnóstico de {peor['producto'].lower()}",
                             "intent": f"diagnostico_{peor['producto'].lower()}"})
        if valle:
            acciones.append({"label": "Monitorear estabilidad eléctrica", "intent": "monitor_electrico"})

        return {
            "entidad": entidad, "encontrada": True,
            "meta": {"scope": entidad or "Global (toda la producción ECP)",
                     "periodo": f"{MESES_ES[mo]} {y}", "corte": f"{len(serie)}/{dim}",
                     "generado_por": generado},
            "titular": titular, "curva_crudo": curva_crudo, "anotaciones": anotaciones,
            "eventos": eventos, "eventos_extra": eventos_extra,
            "lectura_ejecutiva": str(prosa.get("lectura_ejecutiva") or "")[:600],
            "accion_sugerida": acciones,
        }
```

> `sa`, `Query`, `get_engine`, `MESES_ES` ya están importados en el archivo. Los `import json/re/urllib`
> con alias `_json/_re/_urlreq` evitan chocar con otros imports del módulo.

### 6.2 Flask — proxy en `routes\api.py` (tras `analisis_desempeno`)

```python
@api_bp.route("/analisis/desempeno_insight")
def analisis_desempeno_insight():
    """Proxy: titular ejecutivo IA (contrato JSON) del desempeño del mes."""
    try:
        params = {}
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno_insight", params=params, timeout=90)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```
*(timeout 90: incluye la latencia del LLM.)*

### 6.3 Frontend — `multitab_shell.js`

**(a) DI2 — alinear umbrales de `__cnSemColor` a 90/75.** Buscar:

```js
  function __cnSemColor(pct) { return pct == null ? "" : (pct >= 95 ? "is-ok" : (pct >= 85 ? "is-warn" : "is-bad")); }
```
Reemplazar por:
```js
  function __cnSemColor(pct) { return pct == null ? "" : (pct >= 90 ? "is-ok" : (pct >= 75 ? "is-warn" : "is-bad")); }
```

**(b) Layout de 3 columnas en `__cnRenderDesemp`** (NO se toca `__cnAnalizar` — INS-F: sin `__cnDesempAnot`).

Buscar el `return` ACTUAL de `__cnRenderDesemp` (2 columnas, ~L1196-1203):

```js
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__layout">' +
      '  <div class="cn-desemp__kpis">' + cards + '</div>' +
      '  <div class="cn-desemp__right">' +
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
      '      <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva +
      '  </div>' +
      '</div>'
    );
```

Reemplazar por (grid de 3 col; la col. 1 = CTA del insight):

```js
    return (
      '<div class="cn-desemp__monthlbl"><i class="bi bi-calendar3"></i> ' + etiqueta + '</div>' +
      '<div class="cn-desemp__grid3">' +
      '  <div id="cn-ins" class="cn-ins">' +
      '    <div class="cn-ins__cta"><div class="cn-ins__cta-ic"><i class="bi bi-stars"></i></div>' +
      '      <div class="cn-ins__cta-tx">Titular ejecutivo (IA)</div>' +
      '      <button type="button" class="cn-ins__cta-btn" onclick="window.__cnDesempInsight()">' +
      '        <i class="bi bi-magic"></i> Generar resumen</button></div>' +
      '  </div>' +
      '  <div class="cn-desemp__kpis">' + cards + '</div>' +
      '  <div class="cn-desemp__right">' +
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
      '      <div class="cn-desemp__bars">' + bars + '</div></div>' +
      curva +
      '  </div>' +
      '</div>'
    );
```

**(c) Funciones del insight.** Insertar ANTES del comentario `// ---- Panorama: densidad ...`:

```js
  // Genera el Titular ejecutivo (IA) on-demand y lo pinta en la columna 1 (#cn-ins).
  window.__cnDesempInsight = function () {
    var host = el("cn-ins"); if (!host) return;
    var ent = (__cnLastIntent && (__cnLastIntent.valor || __cnLastIntent.entidad)) || "";
    host.innerHTML = '<div class="cn-ins__load"><span class="spinner-border spinner-border-sm"></span> ' +
      'Generando resumen ejecutivo…</div>';
    fetch("/api/analisis/desempeno_insight" + (ent ? "?entidad=" + encodeURIComponent(ent) : ""))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || d.encontrada === false || d.sin_datos) {
          host.innerHTML = '<div class="cn-ins__load text-muted">Sin datos para el resumen.</div>'; return;
        }
        host.innerHTML = __cnRenderIns(d);
        if (d.anotaciones && d.curva_crudo) __cnInsCurvaPlot(d.curva_crudo, d.anotaciones);
      })
      .catch(function () { host.innerHTML = '<div class="cn-ins__load text-danger">Error generando el resumen.</div>'; });
  };

  function __cnRenderIns(d) {
    var m = d.meta || {};
    // titular chips
    var chips = (d.titular || []).map(function (t) {
      var sem = __cnSemColor(t.valor_pct);
      var pct = (t.valor_pct == null) ? "—" : (t.valor_pct + "%");
      return '<div class="cn-ins__chip ' + sem + '"><div class="cn-ins__chip-top">' + esc(t.producto) + '</div>' +
        '<div class="cn-ins__chip-bot"><strong>' + esc(t.texto || "") + '</strong> · ' + pct + '</div></div>';
    }).join("");
    // eventos
    var ev = "";
    if (d.eventos && d.eventos.length) {
      var filas = d.eventos.map(function (e) {
        return '<tr><td class="cn-ins__ev-campo">' + esc(e.campo) + '</td><td class="cn-ins__ev-txt">' +
          esc(e.evento) + '</td><td class="cn-ins__ev-n">' + __cnMilesEC(e.pozos) + '</td></tr>';
      }).join("");
      var extra = (d.eventos_extra && d.eventos_extra.campos)
        ? '<tr class="cn-ins__ev-more"><td>+ ' + d.eventos_extra.campos + ' campos más</td><td></td><td>≈' +
          __cnMilesEC(d.eventos_extra.pozos_aprox) + '</td></tr>' : "";
      ev = '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-lightning-charge"></i> ' +
        'Por qué el valle · eventos del ' + esc((d.eventos_extra || {}).fecha || "") + '</div>' +
        '<table class="cn-ins__ev"><tbody>' + filas + extra + '</tbody></table></div>';
    }
    // acciones
    var acc = (d.accion_sugerida || []).map(function (a) {
      return '<button type="button" class="cn-ins__act" onclick="window.__cnEnDiseno(this)">' +
        '<i class="bi bi-arrow-right-circle"></i> ' + esc(a.label) + '</button>';
    }).join("");
    return (
      '<div class="cn-ins__hd"><span class="cn-ins__hd-ic"><i class="bi bi-stars"></i></span>' +
      '  Titular ejecutivo (IA) · ' + esc(m.periodo || "") + ' · corte ' + esc(m.corte || "") +
      (m.generado_por === "fallback" ? ' <span class="cn-ins__fb">(resumen base)</span>' : '') + '</div>' +
      '<div class="cn-ins__chips">' + chips + '</div>' +
      (d.anotaciones ? '<div class="cn-ins__card"><div class="cn-ins__card-hd"><i class="bi bi-graph-up"></i> ' +
        'Producción diaria de crudo · valle anotado por la IA</div><div id="cn-ins-plot" class="cn-ins__plot"></div></div>' : "") +
      ev +
      '<div class="cn-ins__lect"><div class="cn-ins__lect-hd"><i class="bi bi-fingerprint"></i> Lectura ejecutiva</div>' +
      '  <p class="cn-ins__lect-tx">' + esc(d.lectura_ejecutiva || "") + '</p>' +
      '  <div class="cn-ins__acts">' + acc + '</div></div>'
    );
  }

  // Curva de crudo del panel IA con banda (valle) + pin (mínimo). Coordenadas = Python.
  window.__cnInsCurvaPlot = function (curva, anot) {
    var elp = el("cn-ins-plot"); if (!elp) return;
    if (!window.Plotly) { elp.innerHTML = '<div class="text-muted small p-2">(Plotly no disponible)</div>'; return; }
    var shapes = [], anns = [];
    if (anot && anot.banda) {
      shapes.push({ type: "rect", xref: "x", yref: "paper", x0: anot.banda.desde, x1: anot.banda.hasta,
        y0: 0, y1: 1, fillcolor: "#FAEEDA", opacity: 0.6, line: { width: 0 }, layer: "below" });
      anns.push({ x: anot.banda.desde, y: 1, xref: "x", yref: "paper", yanchor: "bottom",
        text: esc(anot.banda.label || "valle"), showarrow: false, font: { size: 10, color: "#BA7517" } });
    }
    if (anot && anot.punto) {
      anns.push({ x: anot.punto.fecha, y: anot.punto.valor, xref: "x", yref: "y",
        text: esc(anot.punto.label || ""), showarrow: true, arrowhead: 0, ay: 26,
        bgcolor: "#d9534f", font: { color: "#fff", size: 10 } });
    }
    Plotly.newPlot(elp, [{ x: curva.fechas, y: curva.valores, type: "scatter", mode: "lines+markers",
      line: { color: "#1f6b4a", width: 2 }, marker: { size: 3 },
      hovertemplate: "%{x}<br>%{y:,.0f}<extra></extra>" }], {
      margin: { l: 52, r: 10, t: 14, b: 30 }, height: 150, shapes: shapes, annotations: anns,
      xaxis: { tickangle: -45, tickfont: { size: 9 } }, yaxis: { tickfont: { size: 9 }, separatethousands: true },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)"
    }, { displayModeBar: false, responsive: true });
  };
```

### 6.4 CSS — `colapsable.css` (append)

```css
/* ============================================================
   Consulta · Titular ejecutivo (IA) — 3 columnas + panel de insight
   ============================================================ */
.cn-desemp__grid3 { display: grid; grid-template-columns: 1.4fr minmax(150px,190px) 1.3fr; gap: 12px; align-items: stretch; }
.cn-ins { display: flex; flex-direction: column; min-width: 0; border: 1px solid var(--rb-border,#e3e8e5); border-radius: 10px; background: #fff; overflow: hidden; }
.cn-ins__cta { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; height: 100%; padding: 20px; text-align: center; color: #6b7a72; }
.cn-ins__cta-ic { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--rb-green-soft,#eef5f1); color: var(--rb-chat-gold,#C9962E); font-size: 18px; }
.cn-ins__cta-tx { font-size: .8rem; font-weight: 700; color: #3a4a42; }
.cn-ins__cta-btn { border: 1px solid var(--rb-green,#1f6b4a); background: var(--rb-green,#1f6b4a); color: #fff; border-radius: 8px; padding: 6px 12px; font-size: .8rem; font-weight: 700; cursor: pointer; }
.cn-ins__cta-btn:hover { filter: brightness(1.08); }
.cn-ins__load { padding: 16px; font-size: .82rem; }
.cn-ins__hd { padding: 8px 10px; font-size: .74rem; font-weight: 700; color: #2f4a3d; display: flex; align-items: center; gap: 6px; border-bottom: 1px solid var(--rb-line,#eef2f5); }
.cn-ins__hd-ic { color: var(--rb-chat-gold,#C9962E); }
.cn-ins__fb { color: #8a968f; font-weight: 500; }
.cn-ins__chips { display: grid; grid-template-columns: repeat(3,1fr); gap: 6px; padding: 8px 10px; }
.cn-ins__chip { border-radius: 8px; padding: 6px 8px; background: #f4f7f5; border-left: 3px solid #9aa7a0; }
.cn-ins__chip.is-ok { background: #eaf6ef; border-left-color: #1e9e63; }
.cn-ins__chip.is-warn { background: #fbf1e4; border-left-color: #E8912B; }
.cn-ins__chip.is-bad { background: #fbeaea; border-left-color: #d9534f; }
.cn-ins__chip-top { font-size: .64rem; font-weight: 700; letter-spacing: .04em; color: #6b7a72; text-transform: uppercase; }
.cn-ins__chip-bot { font-size: .74rem; color: #2f3d36; }
.cn-ins__card { margin: 8px 10px; border: 1px solid var(--rb-line,#eef2f5); border-radius: 8px; overflow: hidden; }
.cn-ins__card-hd { padding: 6px 10px; font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; color: #3a4a42; background: var(--rb-green-soft,#eef5f1); }
.cn-ins__plot { min-height: 150px; padding: 4px; }
.cn-ins__ev { width: 100%; border-collapse: collapse; font-size: .72rem; }
.cn-ins__ev td { padding: 4px 8px; border-top: 1px solid var(--rb-line,#eef2f5); }
.cn-ins__ev-campo { font-weight: 700; color: #2f3d36; white-space: nowrap; }
.cn-ins__ev-txt { color: #566; }
.cn-ins__ev-n { text-align: right; font-family: monospace; font-weight: 700; color: #4a5a52; }
.cn-ins__ev-more td { color: #8a968f; font-style: italic; }
.cn-ins__lect { margin: 8px 10px 10px; border: 1px solid var(--rb-line,#eef2f5); border-left: 3px solid #d9534f; border-radius: 8px; padding: 8px 10px; }
.cn-ins__lect-hd { font-size: .68rem; font-weight: 700; text-transform: uppercase; color: #3a4a42; margin-bottom: 4px; }
.cn-ins__lect-tx { font-size: .78rem; color: #3d4d46; margin: 0 0 8px; line-height: 1.4; }
.cn-ins__acts { display: flex; flex-wrap: wrap; gap: 6px; }
.cn-ins__act { border: 1px solid var(--rb-border,#cdd8d1); background: #fff; border-radius: 6px; padding: 4px 8px; font-size: .72rem; font-weight: 600; color: #3a4a42; cursor: pointer; }
.cn-ins__act:hover { background: var(--rb-green-soft,#eef5f1); }
@media (max-width: 980px) {
  .cn-desemp__grid3 { grid-template-columns: 1fr; }
  .cn-ins__chips { grid-template-columns: repeat(3,1fr); }
}
```

### 6.5 `main.html` — cache-buster

**Buscar:** `...multitab_shell.js') }}?v=20260709l"></script>`
**Reemplazar por:** `...multitab_shell.js') }}?v=20260709m"></script>`

---

## 7. Orden de ejecución

1. `analisis\api.py` §6.1 (endpoint + helpers).
2. `routes\api.py` §6.2 (proxy).
3. **Reiniciar backend INGESTA `:8000`** (Python nuevo). Verificar que `CONSULTA_OLLAMA_URL` responde.
4. `multitab_shell.js` §6.3 (a,b,c).
5. `colapsable.css` §6.4.
6. `main.html` §6.5.
7. Navegador **Ctrl+F5**.

---

## 8. Reglas no negociables

- **Python calcula, el LLM solo concluye.** `titular.valor_pct/estado`, `anotaciones` (coords), `eventos`,
  `accion.intent` = Python. El LLM SOLO redacta `texto/label/lectura_ejecutiva`. Se **ignora** cualquier
  número del LLM (nunca se lee de su salida un valor numérico).
- **Fallback obligatorio** con la MISMA forma de dict (DI5). Si el LLM cae, el panel se pinta igual.
- **DI2:** umbrales 90/75 en Python **y** en `__cnSemColor` (deben coincidir).
- **DI3/H2:** KPIs de `mes`; `día` solo para la curva/valle.
- **On-demand** (DI1): NO auto-generar el insight al cargar el panel.
- NO tocar el chatbot principal, "Ver el reporte de un día", ni el panel Filiales.
- Vanilla JS ES5; reusar patrón LLM de `extraccion.py` (`urllib`, no `requests`, en el backend FastAPI).

---

## 9. Validaciones (comando → resultado)

**V1 — Sintaxis JS:** `node --check ...\static\js\multitab_shell.js` → exit 0.

**V2 — Endpoint (backend, global):** `curl "http://localhost:8000/analisis/desempeno_insight"`
→ JSON con `titular` (3, con `valor_pct`+`estado`+`texto`), `curva_crudo`, `anotaciones.banda`
(**desde 2026-05-09, hasta 2026-05-14**) y `anotaciones.punto` (**fecha 2026-05-11, valor 2829334**),
`eventos` (top-3 **del onset 09-may**, con `pozos`; **APIAY 73 / Tibú 43 / Caracará 42** — campo desde `area`),
`eventos_extra.campos` ≈ 7, `lectura_ejecutiva` no vacía, `meta.generado_por` ∈ {llm, fallback}.
**Sanity (verificado en BD):** valle banda 09→14, mínimo 11-may = 2.829.334; eventos SIN duplicados (si ves
`NO OPERADOS 164` repetido, el `_eventos_valle` está consultando el rango y no el onset — bug INS-A).

**V3 — Fallback:** apagar/ inaccesible el LLM → el endpoint responde igual con `generado_por:"fallback"`
y `lectura_ejecutiva` por plantilla (nunca 500 por el LLM).

**V4 — Proxy:** `curl "http://localhost:8020/api/analisis/desempeno_insight?entidad=Castilla"` → JSON.

**V5 — Navegador:** Consulta (carga global) → col. 1 muestra el CTA "Generar resumen" → clic →
aparece Titular (chips **CRUDO verde / GAS ámbar / BLANCOS rojo**), curva de crudo con **banda 09-14 +
pin en 11-may**, tabla de eventos, lectura ejecutiva + botones. Las KPI cards (col. 2) recolorean CRUDO a
**verde** (DI2). 0 errores de consola.

**V6 — No regresión:** panel ECP (KPIs/barras/curva plana), Filiales, "Ver el reporte de un día",
Ingesta/Control/Análisis OK.

---

## 10. Fuera de alcance (Fase 2)

- **Auto-generar** el insight en prod (gemma4) sin botón.
- **Acciones accionables**: hoy `accion_sugerida` son placeholder (`__cnEnDiseno`); Fase 2 despacha el
  `intent` (drill-down, filtro por producto…). `label` por LLM.
- **Anotar también la curva plana** de la col. 3 (`__cnDesempAnot` ya queda reservado).
- **Insight de Filiales** (Real vs Programa) con el mismo contrato.
- **Streaming** de la lectura ejecutiva; caché del insight por entidad+mes.
- **Schema formal compartido** entre slot-filling y este contrato (V-D).
