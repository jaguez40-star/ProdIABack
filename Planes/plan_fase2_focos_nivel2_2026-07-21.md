# Plan EXECUTOR · Fase 2 — Focos de atención (Nivel 2 del panel ejecutivo) — v2 auditado

**Fecha:** 2026-07-21 · **Modo:** ejecutar directo (sin gates pesados; el usuario lo pidió).
**v2:** corrige 5 incoherencias del v1 detectadas contra el código real (ver §0).
**Cobertura:** en el panel ejecutivo **ECP** se reemplaza el bloque de 2 columnas (brief + charts) por la
franja "Focos de atención · rankeados por impacto" + botón "Series completas →" (que muestra los charts
existentes). **Filiales, tarjetas KPI (Nivel 1) y backend de `secciones` NO se tocan.**

---

## 0. Hallazgos del audit que este v2 corrige (contexto obligatorio)

- **H1:** el `return` de `__cnRenderEjecutivo` (multitab_shell.js ~L1712) es
  `head + '<div class="cn-ejec__cols"><div class="cn-ejec__left">'+brief+'</div><div class="cn-ejec__right">'+__cnEjecChartsHtml(d)+'</div></div>'`.
  → NO "ocultar secciones": hay que **reemplazar ese bloque completo** (solo para ECP).
- **H2:** Crudo (94.7% < 100) entra en `gap_lag` → generaría foco de gap **y** de valle (duplicado).
  → excluir Crudo del loop de gap cuando hay `valle`.
- **H3:** `__cnRenderEjecutivo` es compartido con Filiales (`__cnEsFil()`). → gatear por `d.focos` presente.
- **H4:** `__cnEjecCharts(d)` dibuja SVG midiendo `clientHeight`; oculto = 0px. → charts **lazy** al abrir.
- **H5:** el foco de valle necesita magnitud ("−X% / N días"); enriquecer `valle` en `ejecutivo`.

## 1. Contexto

- Endpoint: `GET /analisis/ejecutivo` en
  `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\analisis\api.py`
  (`def ejecutivo`, ~L1274). Render:
  `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` (`__cnRenderEjecutivo`, ~L1642).
- En el `return` de `ejecutivo` ya existen en scope: `titular` (por producto: real/ppto/valor_pct/estado),
  `gap_full` (todos) y `gap_lag` (rezagados) con `detractores`/`compensadores` [{campo,gap,real,meta}] y
  `concentracion_pct`; `valle` ({desde,hasta,min_fecha,min_valor}); `eventos` ([{campo,evento,pozos}]);
  `serie` ([(iso,val)] de crudo). **No hace falta ninguna consulta nueva a la BD, ni LLM.**

## 2. Decisiones cerradas

- **D1** Todo determinista (plantillas Python), sin LLM.
- **D2** Causa de focos de gap = `"sin evento asociado en comentarios — requiere validación en campo"`
  (`cobertura:"sin_evento"`). El cruce evento↔déficit (F4) es otra fase. El foco de **valle** SÍ trae eventos reales.
- **D3** Sin conteo diario "X/17 días bajo meta" (usa diario, roto en Blancos).
- **D4** Los focos **reemplazan** el bloque de 2 columnas (brief + charts) SOLO en ECP. El backend de
  `secciones`/`_ejec_fallback` NO se toca. Filiales conserva su vista actual.
- **D5** "Ver →" = toggle inline del detalle ya presente en el foco. "Series completas →" = muestra los
  charts existentes (lazy). Sin endpoint nuevo.
- **D6 (H2)** Crudo NO genera foco de gap si hay valle (el valle lo representa).

## 3. Backend — `analisis/api.py`

### 3.1 Enriquecer `valle` (H5) DENTRO de `ejecutivo`, justo después de `valle = _detectar_valle(serie)`
(y de calcular `eventos`). Insertar:

```python
        if valle and serie:
            _pro = sum(v for _, v in serie) / len(serie)
            from datetime import date as _d
            _a = [int(x) for x in valle["desde"].split("-")]; _b = [int(x) for x in valle["hasta"].split("-")]
            valle["magnitud_pct"] = round((valle["min_valor"] / _pro - 1) * 100, 1) if _pro else None
            valle["dias"] = (_d(*_b) - _d(*_a)).days + 1
```

### 3.2 Nuevas funciones (insertar antes de `def ejecutivo`, junto a `_ejec_fallback`)

```python
def _focos(titular, gap_lag, valle, eventos):
    """Nivel 2: focos rankeados por impacto (DETERMINISTA). Un foco por producto rezagado (excepto
    Crudo si hay valle: D6) + un foco para el valle de crudo. Score = |faltante| * f_tend * f_causa."""
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    focos = []
    for t in titular:
        p, pct = t["producto"], t["valor_pct"]
        if pct is None or pct >= 100:
            continue
        if p == "CRUDO" and valle:                      # D6: el valle representa a Crudo
            continue
        g = gap_lag.get(p)
        if not g or not g.get("detractores"):
            continue
        detr = g["detractores"][:2]
        ents = [d["campo"] for d in detr]
        faltante = float(t["real"]) - float(t["ppto"])
        conc = g.get("concentracion_pct")
        n_campos = len(g["detractores"])
        titulo = (f"{ents[0]} concentra el rezago del producto" if (len(ents) == 1 or conc is None)
                  else f"{' + '.join(ents)} · {conc}% del faltante en {min(n_campos, 2)} campos")
        estructural = conc is not None and conc >= 70
        comp = g["compensadores"][0] if g.get("compensadores") else None
        accion = (f"sostener {comp['campo']} (+{_fmt(comp['gap'])}) como amortiguador"
                  if comp else "plan de recuperación específico")
        focos.append({
            "producto": p, "entidades": ents, "faltante_abs": round(faltante),
            "magnitud_txt": None, "peso_relativo_pct": conc,
            "titulo": titulo,
            "causa": {"texto": "sin evento asociado en comentarios — requiere validación en campo",
                      "cobertura": "sin_evento",
                      "detalle": [f"{d['campo']}: faltante {_fmt(d['gap'])}" for d in g["detractores"]]},
            "accion": accion, "tipo": "gap",
            "score": round(abs(faltante) * (1.5 if estructural else 1.0) * 1.3),
        })
    if valle:
        mag = (f"{valle.get('magnitud_pct')}% / {valle.get('dias')} días"
               if valle.get("magnitud_pct") is not None else None)
        focos.append({
            "producto": "CRUDO", "entidades": [e["campo"] for e in eventos[:3]],
            "faltante_abs": None, "magnitud_txt": mag, "peso_relativo_pct": None,
            "titulo": f"valle {valle['desde'][5:]}–{valle['hasta'][5:]} recuperado, dejó hueco en el pace",
            "causa": {"texto": ", ".join(f"{e['campo']} ({e['pozos']} pozos)" for e in eventos[:3]) or "eventos operativos",
                      "cobertura": "completa" if eventos else "sin_evento",
                      "detalle": [f"{e['campo']}: {e['evento']}" for e in eventos[:6]]},
            "accion": "verificar cierre de eventos y estabilidad eléctrica", "tipo": "valle",
            "score": round(sum(abs(float(t["real"]) - float(t["ppto"]))
                               for t in titular if t["producto"] == "CRUDO") * 0.7),
        })
    focos.sort(key=lambda f: f["score"], reverse=True)
    for i, f in enumerate(focos, 1):
        f["rank"] = i
    return focos[:5]


def _sin_foco(titular, gap_full, valle):
    def _fmt(n): return f"{abs(float(n)):,.0f}".replace(",", ".")
    pos = []
    for t in titular:
        g = gap_full.get(t["producto"])
        for comp in (g.get("compensadores") if g else []) or []:
            pos.append(f"{comp['campo']} en {t['producto'].lower()} (+{_fmt(comp['gap'])})")
    partes = []
    if pos: partes.append("con excedentes: " + ", ".join(pos[:3]))
    if valle: partes.append("Crudo recuperado del valle")
    return " · ".join(partes) if partes else "Sin elementos adicionales."
```

### 3.3 En el `return {...}` de `ejecutivo` AÑADIR (sin quitar nada):

```python
        "focos": _focos(titular, gap_lag, valle, eventos),
        "sin_foco": _sin_foco(titular, gap_full, valle),
```

> `_ejecutivo_filiales` NO se toca (no lleva `focos` → el frontend le deja su brief, H3/D4).

## 4. Frontend — `multitab_shell.js`

### 4.1 Añadir dentro de la IIFE (junto a `__cnTarjetasKpiHtml`):

```javascript
  var __cnEjecD = null;   // último payload, para la carga lazy de "Series completas"
  function __cnFocosHtml(focos, sinFoco) {
    if (!focos || !focos.length) return "";
    var filas = focos.map(function (f) {
      var num = (f.faltante_abs != null)
        ? '<span class="cn-foco__num">' + __cnMilesEC(f.faltante_abs) + '</span>'
        : (f.magnitud_txt ? '<span class="cn-foco__num">' + esc(f.magnitud_txt) + '</span>' : "");
      var det = ((f.causa && f.causa.detalle) || []).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join("");
      var warn = (f.causa && f.causa.cobertura === "sin_evento") ? " cn-foco__causa--warn" : "";
      return '<div class="cn-foco">' +
        '<div class="cn-foco__hd">' +
          '<span class="cn-foco__rk">' + f.rank + '</span>' +
          '<div class="cn-foco__main">' +
            '<div class="cn-foco__titulo"><b>' + esc(f.producto) + ' · ' +
              (f.entidades || []).map(esc).join(" + ") + '</b> ' + esc(f.titulo) + '</div>' +
            '<div class="cn-foco__ca">' +
              '<span class="cn-foco__causa' + warn + '">⚡ Causa: ' + esc((f.causa || {}).texto || "—") + '</span>' +
              '<span class="cn-foco__accion">☑ Acción: ' + esc(f.accion || "—") + '</span>' +
            '</div>' +
          '</div>' + num +
          (det ? '<button type="button" class="cn-foco__ver" onclick="window.__cnFocoToggle(this)">Ver →</button>' : "") +
        '</div>' +
        (det ? '<ul class="cn-foco__det" style="display:none">' + det + '</ul>' : "") +
        '</div>';
    }).join("");
    return '<div class="cn-foco__wrap">' +
      '<div class="cn-foco__hdr">Focos de atención · rankeados por impacto</div>' + filas +
      '<div class="cn-foco__sin"><span>✓ Sin foco: ' + esc(sinFoco || "") + '</span>' +
        '<button type="button" class="cn-foco__ver" onclick="window.__cnSeriesToggle(this)">Series completas →</button>' +
      '</div>' +
      '<div class="cn-ejec__series" style="display:none"></div>' +
      '</div>';
  }
  window.__cnFocoToggle = function (btn) {
    var ul = btn.closest(".cn-foco").querySelector(".cn-foco__det"); if (!ul) return;
    ul.style.display = ul.style.display === "none" ? "block" : "none";
  };
  window.__cnSeriesToggle = function (btn) {
    var box = btn.closest(".cn-foco__wrap").querySelector(".cn-ejec__series"); if (!box) return;
    if (box.dataset.loaded !== "1" && __cnEjecD) {          // lazy: dibujar al abrir (H4)
      box.innerHTML = __cnEjecChartsHtml(__cnEjecD); box.dataset.loaded = "1";
      try { __cnEjecCharts(__cnEjecD); } catch (e) {}
    }
    box.style.display = box.style.display === "none" ? "block" : "none";
  };
```

### 4.2 En `__cnRenderEjecutivo(d)`, guardar el payload y REEMPLAZAR el bloque de 2 columnas para ECP.
Al inicio de la función añadir `__cnEjecD = d;`. Y el `return` final (el que hoy arma `cn-ejec__cols`)
cambiarlo por (H1/H3/D4):

```javascript
    if (d.focos && d.focos.length) {                        // ECP con focos: Nivel 2
      return head + __cnFocosHtml(d.focos, d.sin_foco);
    }
    // Filiales / sin focos: se conserva la vista actual (brief + charts) TAL CUAL.
    var brief = noteReconc +
      seccion("bi-lightbulb", "Insights", s.insights) +
      seccion("bi-graph-up-arrow", "Oportunidades", s.oportunidades) +
      seccion("bi-exclamation-triangle", "Puntos de atención", s.puntos_atencion) +
      seccion("bi-check2-square", "Decisiones", s.decisiones);
    return head +
      '<div class="cn-ejec__cols"><div class="cn-ejec__left">' + brief + '</div>' +
      '<div class="cn-ejec__right">' + __cnEjecChartsHtml(d) + '</div></div>';
```

> El bloque de error (`m.generado_por === "error"`) queda ANTES y NO se toca. La llamada eager
> `__cnEjecCharts(d)` del caller queda como está: si no hay contenedores (caso focos) hace no-op por sus
> guardas `if(el)`; los charts reales se dibujan al abrir "Series completas".

### 4.3 Cache-buster en `templates\main.html`: subir los dos `?v=...` (css y js) a `20260721m`.

## 5. CSS — `static/css/colapsable.css` (al final del bloque `.cn-kpi__*`)

```css
.cn-foco__wrap { margin: 4px 10px 10px; }
.cn-foco__hdr { font-size: .72rem; font-weight: 700; color: #6b7a72; margin: 6px 0; }
.cn-foco { border: 1px solid #e7ebe9; border-radius: 8px; padding: 8px 10px; margin-bottom: 6px; background: #fff; }
.cn-foco__hd { display: flex; align-items: flex-start; gap: 8px; }
.cn-foco__rk { font-weight: 700; color: #9aa7a0; min-width: 14px; }
.cn-foco__main { flex: 1; min-width: 0; }
.cn-foco__titulo { font-size: .82rem; color: #2f3d36; }
.cn-foco__ca { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 3px; font-size: .72rem; color: #5c6b63; }
.cn-foco__causa--warn { color: #A32D2D; }
.cn-foco__num { font-weight: 700; color: #A32D2D; white-space: nowrap; margin: 0 6px; }
.cn-foco__ver { border: 1px solid #d3d9d6; background: #fff; border-radius: 6px; font-size: .7rem; padding: 2px 8px; cursor: pointer; white-space: nowrap; }
.cn-foco__det { margin: 6px 0 0 22px; font-size: .72rem; color: #5c6b63; }
.cn-foco__sin { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: .72rem; color: #5c6b63; margin-top: 6px; }
.cn-ejec__series { margin-top: 8px; }
```

## 6. Orden de ejecución

1. Backend: §3.1 (enriquecer valle) → §3.2 (`_focos`/`_sin_foco`) → §3.3 (2 claves al return).
2. Frontend: §4.1 (helpers) → §4.2 (guardar `__cnEjecD` + reemplazar bloque, gateado por `d.focos`) → §4.3 (cache-buster).
3. CSS §5.

## 7. Reglas NO negociables

- **NO tocar** tarjetas KPI (`__cnTarjetasKpiHtml`, `_tarjetas_kpi`, ramas Crudo/Gas/Blancos) ni el
  bloque de error (`generado_por === "error"`) ni `_ejecutivo_filiales`.
- **Filiales conserva su brief+charts**: el reemplazo va gateado por `d.focos && d.focos.length` (D4/H3).
- **NO LLM, NO consultas nuevas a la BD.** Solo lo que `ejecutivo` ya calcula.
- **Crudo NO duplica foco** (D6/H2).
- El `return` de `ejecutivo` solo se AMPLÍA (2 claves); no se quita ninguna.

## 8. Validación (mínima)

- `node --check static/js/multitab_shell.js` y `python -c "import app.features.analisis.api"` (desde `backend/`).
- Smoke opcional en navegador: el panel ECP muestra la franja de focos; Filiales sigue con su brief; "Series
  completas →" abre los charts sin romper el tamaño.

## 9. Fuera de alcance

- F4 (cruce evento↔déficit para focos de gap → quedan "sin evento").
- "Ver →" con drill-down a SQL/gráficos (aquí solo toggle del detalle presente).
- Micro-textos por LLM. Cambios a Nivel 1/3. Focos para Filiales.
