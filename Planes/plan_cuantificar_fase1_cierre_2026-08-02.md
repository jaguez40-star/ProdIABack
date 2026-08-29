# Plan de ejecución — Cuantificar · CIERRE DE FASE 1 (sub-fases 1d + 1e)

> **Tablas: N/A** — no toca ingesta ni tablas fuente (regla de cobertura §0.2 no aplica; es capa de
> respuesta + panel + memoria sobre cifras ya calculadas).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** 1a+1b (`f157a40`) y 1c (`b8c3d46`) YA hechas y commiteadas. Esto CIERRA la Fase 1
> (crudo · INGESTA · PPTO · N1-N2 · mes) con sus dos piezas faltantes: **1d panel derecho** + **1e N2
> acumulado + memoria + golden**.
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario):** NO usar el LLM local de dev ni levantar la app en
> dev para probar. Las validaciones de runtime que impliquen LLM/navegador se corren en el **servidor
> de pruebas**. En dev: solo chequeos estáticos (`py_compile`, `node --check`) y de datos (BD, sin LLM).
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

| # | Hallazgo (verificado) | Efecto en el plan |
|---|----------------------|-------------------|
| **HD1** | `__cnRenderV2` (`multitab_shell.js:3367`) YA pinta `d.mensaje` → la respuesta 1b/1c de cuantificar ya se ve en la burbuja. | El panel (1d) es **puramente aditivo**: no cambia la burbuja, solo agrega el visor derecho. |
| **HD2** | `__cnP50CardHtml` (`:2306`) está clavado al P50 (`kbpe`, `base_p50`, `compromiso`, `cumpl_p50`). NO encaja para Real-vs-PPTO en bbl. | 1d crea su PROPIA tarjeta `__cnCuantCardHtml` reusando `__cnRing` + clases `cp-mes__kpi` + `__cnMilesEC`. NO se reusa `__cnP50CardHtml`. |
| **HD3** | El `fetch /api/consulta2/preguntar` está en 3 sitios: Consulta (`:3291`), Test Clas (`:3499`) y lote (`:3566`). | El panel se pinta SOLO en el handler de **Consulta** (`:3294-3296`). Test Clas y el lote NO se tocan (su visor es la libreta). |
| **HD4** | El return de `maquina_q._clasificar_core` (`:236-247`) solo tiene `mensaje`; el `elif cuantificar` hace `if r: mensaje = r` (espera string). | 1d: `responder()` pasa a devolver **`{mensaje, panel}`**; el `elif` extrae ambos; el return añade `"panel"` (aditivo → jerarquizar/OUT lo dejan `None`). |
| **HE1** | `_continuacion` (`:43`) está moldeado a jerarquizar (`entidad_en`, `ofrece_produccion`, `_ESTRUCT_KW`). | 1e añade una RAMA cuantificar: si `ctx.grupo=="cuantificar"` y el texto pide acumulado/afirma → reescribe a `"acumulado de {entidad}"`. |
| **HE2** | `_CTX` solo se puebla tras jerarquizar (`:269-273`). | 1e: tras responder cuantificar, guardar `_CTX[cid] = {grupo:"cuantificar", entidad, nivel}`. |
| **HE3** | El cierre de 1c dice *"¿Quieres verlo mes a mes?"* → eso es **N3 (serie)**, que es Fase 2. La Fase 1 solo construye **N2 (acumulado)**. | 1e CAMBIA el cierre a *"¿Quieres el acumulado del año?"* (ofrece N2, lo que sí se construye). |
| **HE4** | El mes en curso es una PROYECCIÓN de cierre (regla T-1, ya usada en 1b/1c). Sumarlo con meses cerrados mezcla proyección y real. | N2 acumulado = **Σ REAL solo de meses CERRADOS** (`mes.completo`); el mes en curso se DECLARA aparte, no se suma. |
| **HD5** 🔴 | **El visor de Consulta es PROPIEDAD de v1:** su cabecera dice *"Consulta de Producción (v1)"* y `renderViewer` (`:372-387`) RECONSTRUYE el shell v1 (rail + canvas + dashboard) cada vez que se entra a la pestaña. Un panel v2 pintado ahí es **transitorio** (se borra al cambiar de pestaña) y queda bajo el encabezado "(v1)". | **DECISIÓN ESCALADA (§0.2):** 1d se parte — **1d-back** (añadir `panel` al contrato, seguro y útil) va ahora; **1d-front** pinta una tarjeta TRANSITORIA en `cn-viewer-area` (reemplaza rail+canvas, mini-encabezado propio), documentada como transitoria. El encabezado "(v1)" NO se toca (un visor v2 propio es una fase aparte). |
| **HE5** 🔴 | En `_continuacion` (`:54`), el check `ctx.get("ofrece_produccion") and (prod or t in _AFIRM) → "produccion de {entidad}"` **ensombrecería** la rama cuantificar: un "sí" tras N1 repetiría N1 en vez de ir a N2. | El ctx de cuantificar **NO** lleva `ofrece_produccion`, y la rama cuantificar va **antes** del check de `ofrece_produccion` (justo tras el check de `entidad_en`). |
| **HE6** | El "mes sintético" para N2 produce prosa torcida ("produjo X en *acumulado enero–abril*") y un `corte` erróneo ("mes cerrado"). | NO se fabrica un `mes`. `formatear_cuerpo` y `__cnCuantCardHtml` **ramifican por `res["nivel"]`** (N1 vs N2); N2 trae `periodo_label`/`meses_cerrados`/`en_curso` propios. |
| **HE7** | `slots._periodo_texto` usa `.lower()` (NO pliega tildes) → `"en el año"` no matchearía `"en el ano"`. | La detección N2 usa **`normaliza.norm`** (pliega tildes + MAYÚSCULAS), con las palabras clave en su forma normalizada — consistente con `_continuacion`. |

---

## SUB-FASE 1d — El panel derecho (doble entregable N1)

### Objetivo
Al responder cuantificar en el chat de **Consulta** (Motor v2), el visor DERECHO pinta una tarjeta KPI
con la MISMA cifra de la burbuja (Real vs PPTO, %, estado, corte). Aditivo: jerarquizar/OUT no pintan
nada (panel `null`).

### Archivos
| Acción | Ruta |
|--------|------|
| EDITAR | `...\backend\app\features\consulta_v2\cuantificar\ejecutor.py` — el contrato ya trae todo; solo se expone `panel` |
| EDITAR | `...\backend\app\features\consulta_v2\respuesta_cuantificar.py` — `responder()` devuelve `{mensaje, panel}` |
| EDITAR | `...\backend\app\features\consulta_v2\maquina_q.py` — el `elif cuantificar` extrae `panel`; el return lo añade |
| EDITAR | `...\static\js\multitab_shell.js` — nueva `__cnCuantCardHtml` + pintar en el handler de Consulta |
| EDITAR | `...\static\css\colapsable.css` — (opcional) nada nuevo si se reusan clases `cp-mes__kpi` |
| EDITAR | `...\templates\main.html` — cache-buster `?v=` del `multitab_shell.js` |

(Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features`
· Base app padre: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`)

### Especificación

**D.1 — `respuesta_cuantificar.responder()` devuelve `{mensaje, panel}`** (HD4). Reemplazar el `return`
final y los `return` de error para que SIEMPRE devuelvan un dict:

```python
def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None):
    """1c/1d: resuelve → cifra → intro+cuerpo+cierre (mensaje) + panel KPI (o None). Nunca None."""
    resuelta = _resolver.resolver_unico(entidad or texto)
    if resuelta is None:
        eco = f" No reconocí «{entidad}» en el catálogo." if entidad else ""
        return {"mensaje": ("No identifiqué una entidad en tu pregunta para cuantificar." + eco
                            + " ¿Puedes nombrar un campo, activo o gerencia?"), "panel": None}
    if resuelta.get("ambiguo"):
        nombres = ", ".join(sorted({r["valor"] for r in resuelta["ambiguo"]}))
        return {"mensaje": (f"«{entidad or texto}» coincide con más de una entidad ({nombres}). "
                            "La desambiguación llega en una próxima fase; por ahora prueba con un nombre único."),
                "panel": None}

    res = _ejecutor.ejecutar_n1(resuelta, _slots.extraer_slots(texto))
    if not res.get("aplica"):
        return {"mensaje": res.get("texto", "No pude cuantificar esa pregunta."), "panel": None}

    cuerpo = _validador.formatear_cuerpo(res)
    intro = _intro(res, usuario)
    cierre = "¿Quieres el detalle de un mes puntual?" if res.get("nivel") == "N2" else _CIERRE   # HE3
    mensaje = respuesta_base.envolver(intro, cuerpo, cierre)
    return {"mensaje": mensaje, "panel": {"tipo": "cuant_kpi", "datos": _panel_datos(res)}}
```
donde `_panel_datos` es un helper NUEVO en el módulo, consciente del nivel (HE6):
```python
def _panel_datos(res: dict) -> dict:
    d = {"nivel": res.get("nivel"), "entidad_cualificada": res["entidad_cualificada"],
         "producto": res["producto"], "unidad": res["unidad"],
         "real": res["resultado"]["valor"], "ppto": res["referencia_valor"],
         "cumplimiento_pct": res["cumplimiento_pct"], "estado": res["estado"],
         "avisos": res.get("avisos", [])}
    if res.get("nivel") == "N2":
        d["periodo_label"] = res["periodo_label"]; d["meses_cerrados"] = res["meses_cerrados"]
    else:
        d["mes"] = res["mes"]
    return d
```
> El `_CIERRE = "¿Quieres el acumulado del año?"` (HE3) se define una vez arriba del módulo (reemplaza
> el `_CIERRE` actual de 1c que decía "¿Quieres verlo mes a mes?").

**D.2 — `maquina_q._clasificar_core`** (HD4). En el `elif grupo == "cuantificar" and log:` (`:226`) y en el
`return` (`:236`):
```python
    panel = None                          # <-- añadir ANTES del bloque de elifs (junto a `mensaje = _mensaje(...)`)
    ...
    elif grupo == "cuantificar" and log:
        r = respuesta_cuantificar.responder(texto, entidad=entidad, usuario=usuario,
                                            conversation_id=conversation_id)
        if isinstance(r, dict):
            mensaje = r.get("mensaje") or mensaje
            panel = r.get("panel")
        elif r:
            mensaje = r
    ...
    return {
        ...
        "mensaje": mensaje,
        "panel": panel,                   # <-- añadir (aditivo; jerarquizar/OUT = None)
    }
```

**D.3 — Frontend: nueva tarjeta + pintar SOLO en Consulta** (HD1/HD2/HD3). En `multitab_shell.js`:

(a) Añadir la función tarjeta (cerca de `__cnP50CardHtml`, ~L2306). Reusa `__cnRing`, `__cnMilesEC`,
clases `cp-mes__kpi`:
```javascript
  function __cnCuantCardHtml(dat) {
    var estado = dat.estado || "";
    // color por estado (mismo criterio de las tarjetas del foco)
    var col = (estado === "Alineado") ? "#1E9E5A" : (estado === "Rezagado") ? "#E8912B"
            : (estado === "Foco") ? "#D64545" : "#6B7A74";
    var pct = (dat.cumplimiento_pct != null) ? dat.cumplimiento_pct : 0;
    var unidad = dat.unidad || "bbl";
    // HE6: N1 (un mes) vs N2 (acumulado) tienen etiqueta y corte distintos.
    var realLbl, corte;
    if (dat.nivel === "N2") {
      realLbl = "Acumulado " + (dat.periodo_label || "");
      corte = (dat.meses_cerrados || 0) + " mes" + ((dat.meses_cerrados === 1) ? "" : "es") + " cerrado" + ((dat.meses_cerrados === 1) ? "" : "s");
    } else {
      var mes = dat.mes || {};
      realLbl = "Producción " + (mes.nombre || "") + " " + (mes.anio || "");
      corte = mes.completo ? "mes cerrado"
            : ("proyección · " + (mes.dias_con_data || 0) + "/" + (mes.dias_del_mes || 0) + " días");
    }
    var avisos = (dat.avisos || []).map(function (a) {
      return '<div class="cp-p50__r"><span class="cp-p50__k">⚠️ ' + esc(a) + '</span></div>';
    }).join("");
    return '<div class="cp-mes__kpi cp-p50" style="--cp-st:' + col + ';--cp-st-soft:' + col + '22">' +
      '<div class="cp-mes__kpi-hd">' +
        '<span class="cp-mes__kpi-chip"><i class="bi bi-calculator"></i></span>' +
        '<span class="cp-mes__kpi-name">' + esc(dat.entidad_cualificada || "") + '</span>' +
        (estado ? '<span class="cp-mes__kpi-badge">' + esc(estado) + '</span>' : '') +
      '</div>' +
      '<div class="cp-p50__ring">' + __cnRing(pct, col, 96, "REAL / PPTO", 1) + '</div>' +
      '<div class="cp-p50__real">' +
        '<div class="cp-p50__realval">' + __cnMilesEC(dat.real) + ' <span class="cp-mes__kpi-unit">' + unidad + '</span></div>' +
        '<div class="cp-p50__reallbl">' + esc(realLbl) + '</div>' +
      '</div>' +
      '<div class="cp-p50__rows">' +
        '<div class="cp-p50__r"><span class="cp-p50__k">Presupuesto</span><span class="cp-p50__v">' + __cnMilesEC(dat.ppto) + ' ' + unidad + '</span></div>' +
        '<div class="cp-p50__r"><span class="cp-p50__k">Corte</span><span class="cp-p50__v">' + corte + '</span></div>' +
        avisos +
      '</div>' +
    '</div>';
  }

  // HD5: el visor de Consulta es de v1 y renderViewer lo reconstruye al entrar a la pestaña → este
  // panel es TRANSITORIO (se pierde al cambiar de pestaña; reaparece al volver a preguntar). Se pinta
  // en cn-viewer-area (reemplaza rail+canvas) con encabezado propio. El "(v1)" de arriba NO se toca.
  function __cnPintarPanelCuant(panel) {
    var area = el("cn-viewer-area"); if (!area || !panel || !panel.datos) return;
    area.innerHTML =
      '<div style="height:100%;overflow:auto;padding:14px;">' +
      '  <div class="cn-p50-hd" style="margin-bottom:10px;"><i class="bi bi-calculator"></i> ' +
      '    Cuantificar · resultado</div>' +
      '  <div class="cn-p50-row">' + __cnCuantCardHtml(panel.datos) + '</div>' +
      '</div>';
  }
```
> **Nota (HD5):** el panel es TRANSITORIO por diseño de esta fase — al cambiar de pestaña, `renderViewer`
> reconstruye el visor v1. Es aceptable para el laboratorio v2; un visor v2 persistente y propio es una
> fase aparte (no Fase 1). El encabezado "Consulta de Producción (v1)" NO se modifica.

(b) En el handler de Consulta v2 (`:3294-3296`), tras pintar la burbuja, pintar el panel si viene:
```javascript
        .then(function (d) { if (load) load.remove();
          __v2UltimaClas = {ts: Date.now(), texto: texto};
          __cnBubble("assistant", __cnRenderV2(d));
          if (d.panel) __cnPintarPanelCuant(d.panel);      // <-- 1d: panel derecho (solo Consulta)
        })
```
⚠️ **NO** añadir esto en el handler de Test Clas (`:3499-3505`) ni en el del lote (`:3566`): su visor es
la libreta, no un panel de KPI.

**D.4 — cache-buster:** en `templates\main.html`, subir el `?v=` del `<script ... multitab_shell.js>`.

### ✅ COMPUERTA 1d (estática + navegador en servidor de pruebas)
- **En dev (estático):** `py_compile` de los 3 .py + `node --check static/js/multitab_shell.js` OK.
- **Prueba de datos (dev, SIN LLM):** con el flag `consulta_cuant_llm=false`, llamar
  `respuesta_cuantificar.responder("cuanto produjo Rubiales en abril", entidad="RUBIALES")` y verificar
  que devuelve un **dict** con `mensaje` (cadena) y `panel.datos.real == 10966768.1332`,
  `panel.datos.cumplimiento_pct == 90.8`. (Comando en §Validaciones V-D2.)
- **En servidor de pruebas (navegador):** Motor v2 → "cuánto produjo Rubiales en abril" → burbuja con la
  cifra + **tarjeta KPI en el visor derecho** con la misma cifra; jerarquizar/OUT → visor sin cambios.

---

## SUB-FASE 1e — N2 acumulado + memoria (_CTX) + golden

### Objetivo
Responder N2 (acumulado del año, meses cerrados) y que el drill conversacional funcione: tras una
respuesta N1, "¿acumulado del año?" (o "sí") mueve chat + panel al N2. Cerrar con golden + pytest.

### Archivos
| Acción | Ruta |
|--------|------|
| EDITAR | `...\consulta_v2\cuantificar\slots.py` — detectar `nivel_temporal` N1/N2 |
| CREAR | `...\consulta_v2\cuantificar\niveles.py` — N2 = Σ REAL de meses cerrados (loop desempeno) |
| EDITAR | `...\consulta_v2\cuantificar\ejecutor.py` — enrutar N1/N2; `ejecutar_n2` |
| EDITAR | `...\consulta_v2\respuesta_cuantificar.py` — cierre N2 + panel N2 + guardar contexto |
| EDITAR | `...\consulta_v2\maquina_q.py` — poblar `_CTX` tras cuantificar + rama cuantificar en `_continuacion` |
| CREAR | `...\consulta_v2\golden\cuantificar_golden.yaml` + `run_golden.py` |
| EDITAR | `...\backend\tests\test_consulta_v2_clasificador.py` (o nuevo `test_cuantificar.py`) |

### Especificación

**E.1 — `slots.py`: detectar N1/N2** (HE7: con `norm`, no `.lower()`). Añadir arriba
`from app.features.consulta_v2.normaliza import norm` y:
```python
# En forma NORMALIZADA (norm = MAYÚSCULAS sin tildes): "año"->"ANO". Así "en el año" matchea.
_ACUM_KW = ("ACUMULADO", "ACUMULADA", "EN EL ANO", "EN LO QUE VA", "DEL ANO", "YTD",
            "HASTA AHORA", "EN TOTAL", "TOTAL DEL ANO")

def _nivel_temporal(texto: str) -> str:
    t = norm(texto or "")
    return "N2" if any(k in t for k in _ACUM_KW) else "N1"
```
y en el dict devuelto por `extraer_slots`: `"nivel_temporal": _nivel_temporal(texto)` (reemplaza el `"N1"` fijo).

**E.2 — `niveles.py` (NUEVO): N2 = Σ REAL de meses CERRADOS** (HE4). No SQL propio: reusa `desempeno`.
```python
"""cuantificar/niveles.py — N2 acumulado (Σ REAL de meses CERRADOS del año). Reusa analisis.desempeno
por mes → coherencia con el tablero. El mes EN CURSO (proyección) NO se suma (HE4): se declara aparte."""
from app.features.analisis.api import desempeno as _desempeno_ep

_MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def acumulado_crudo(resuelta: dict, _desempeno_fn=None) -> dict:
    """Devuelve {real, ppto, meses:[nombres cerrados], en_curso:{nombre,proyeccion}|None, anio} o
    {aplica:False, texto}. Solo rama A + crudo (Fase 1)."""
    fn = _desempeno_fn or _desempeno_ep
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return {"aplica": False, "texto": f"No tengo datos de producción para «{resuelta['valor']}»."}
    anio, ultimo = d0["mes"]["anio"], d0["mes"]["mes"]
    total_real = total_ppto = 0.0
    meses, en_curso = [], None
    for m in range(1, ultimo + 1):
        dm = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=_MESES[m])
        if not dm.get("encontrada") or dm.get("sin_datos") or dm.get("sin_cierre"):
            continue
        fila = next((p for p in dm["por_producto"] if p["producto"] == "CRUDO"), None)
        if not fila or (fila["real"] == 0 and fila["ppto"] == 0):
            continue
        if dm["mes"]["completo"]:
            total_real += fila["real"]; total_ppto += (fila["ppto"] or 0); meses.append(_MESES[m])
        else:
            en_curso = {"nombre": _MESES[m], "real": fila["real"]}   # proyección; NO se suma
    if not meses:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» aún no tiene meses cerrados en {anio} para acumular."}
    return {"aplica": True, "real": total_real, "ppto": total_ppto, "meses": meses,
            "en_curso": en_curso, "anio": anio}
```

**E.3 — `ejecutor.py`: enrutar N1/N2** (HE6: N2 NO fabrica un `mes`; lleva campos propios). Añadir
`ejecutar_n2` + un despacho:
```python
from app.features.consulta_v2.cuantificar import niveles as _niveles   # (import arriba del módulo)

def ejecutar(resuelta, slots, _desempeno_fn=None):
    if slots.get("nivel_temporal") == "N2":
        return ejecutar_n2(resuelta, slots, _desempeno_fn=_desempeno_fn)
    return ejecutar_n1(resuelta, slots, _desempeno_fn=_desempeno_fn)

def ejecutar_n2(resuelta, slots, _desempeno_fn=None):
    if resuelta.get("rama") == "B":
        return {"aplica": False, "texto": f"«{resuelta['valor']}» es una filial; su acumulado llega en otra fase."}
    ac = _niveles.acumulado_crudo(resuelta, _desempeno_fn=_desempeno_fn)
    if not ac.get("aplica"):
        return {"aplica": False, "texto": ac["texto"]}
    real, ppto = ac["real"], ac["ppto"]
    cumpl = round(real / ppto * 100.0, 1) if ppto else None
    estado = _ESTADO_LABEL.get(_estado(cumpl), "")
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    ms = ac["meses"]
    periodo_label = (ms[0] if len(ms) == 1 else f"{ms[0]}–{ms[-1]}") + f" {ac['anio']}"
    avisos = []
    if ac.get("en_curso"):
        avisos.append(f"El mes de {ac['en_curso']['nombre']} sigue en curso; su proyección NO está "
                      f"incluida en el acumulado.")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": "produccion_crudo",
        "nivel": "N2",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "producto": "crudo", "referencia": "PPTO", "unidad": "bbl", "grano": "mes",
        "universo": "reporte_diario",
        "resultado": {"valor": real}, "referencia_valor": ppto,
        "cumplimiento_pct": cumpl, "estado": estado,
        "periodo_label": periodo_label, "meses_cerrados": len(ms),
        "en_curso": ac.get("en_curso"),
        "huella": {"registros": len(ms), "es_proyeccion": False},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }
```
Y `respuesta_cuantificar` llama `_ejecutor.ejecutar(...)` (no `ejecutar_n1` directo).

**E.4 — `validador.formatear_cuerpo`: ramificar por nivel** (HE6). Antes de la lógica N1 actual, añadir:
```python
def formatear_cuerpo(res: dict) -> str:
    real = _fmt(res["resultado"]["valor"])
    pct = f"{res['cumplimiento_pct']}%" if res.get("cumplimiento_pct") is not None else "s/d"
    ppto = _fmt(res["referencia_valor"]) if res.get("referencia_valor") else None
    if res.get("nivel") == "N2":                       # ACUMULADO (meses cerrados)
        linea = (f"{res['entidad_cualificada']} acumuló {real} bbl de crudo en {res['periodo_label']} "
                 f"({res['meses_cerrados']} mes{'es' if res['meses_cerrados'] != 1 else ''} cerrado"
                 f"{'s' if res['meses_cerrados'] != 1 else ''}) — {pct} del presupuesto ({res['estado']}).")
        if ppto:
            linea += f" Presupuesto acumulado: {ppto} bbl."
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea
    # ... (N1: el bloque actual, sin cambios) ...
```

**E.4 — `respuesta_cuantificar.py`: cierre N2 + guardar contexto.**
- Cambiar `_CIERRE` (HE3): `_CIERRE = "¿Quieres el acumulado del año?"`. Y para una respuesta que YA es N2,
  usar un cierre distinto (p. ej. `"¿Quieres el detalle de un mes puntual?"`) — elegir por
  `res["nivel"]`.
- El panel N2 reusa `__cnCuantCardHtml` con "REAL / PPTO" (el ring y las filas ya son genéricas).
- (El guardado de `_CTX` NO se hace aquí — se hace en `maquina_q` que es quien tiene `conversation_id`
  y `_CTX`; ver E.5.)

**E.5 — `maquina_q.py`: memoria de cuantificar (HE1/HE2/HE5).**
(a) En `clasificar` (la envoltura con memoria, junto al caso jerarquizar `:269`), poblar `_CTX` para
cuantificar. 🔑 **HE5: SIN `ofrece_produccion`** (esa clave dispara la rama de jerarquizar en
`_continuacion` y repetiría N1):
```python
    if res["grupo"] == "cuantificar" and log and conversation_id and res.get("entidad_cruda"):
        _CTX[conversation_id] = {"grupo": "cuantificar", "entidad": res["entidad_cruda"]}
```
(b) En `_continuacion` (`:43`), insertar la rama cuantificar **INMEDIATAMENTE DESPUÉS del check de
`entidad_en` (`:51-53`) y ANTES del check de `ofrece_produccion` (`:54`)** — HE5, para que un "sí"/"acumulado"
tras N1 NO caiga en la rama de jerarquizar:
```python
    ent = respuesta_jerarquizar.entidad_en(texto)      # (línea existente :51)
    if ent:                                            # (existente :52-53)
        return f"produccion de {ent}" if prod else f"que es {ent}"
    # --- NUEVO (HE5): drill de cuantificar N1 -> N2 ---
    if ctx.get("grupo") == "cuantificar" and \
       (any(k in t for k in ("ACUMULADO", "EN EL ANO", "DEL ANO", "EN TOTAL", "YTD")) or t in _AFIRM):
        return f"acumulado de {ctx['entidad']}"
    # --- (sigue el check existente de ofrece_produccion :54) ---
```
> Así "¿acumulado del año?" o "sí" tras N1 → `"acumulado de RUBIALES"` → reclasifica cuantificar →
> slots detecta N2 → ejecutor N2. Chat Y panel se mueven juntos (el panel se repinta en el handler de
> Consulta con el `d.panel` del N2). ⚠️ `t` ya está normalizado por `norm` en `_continuacion` (`:46`),
> así que las claves van en MAYÚSCULAS sin tildes — consistente con E.1.

**E.6 — golden + pytest.** `golden/cuantificar_golden.yaml` con **≥10 casos** crudo: varios N1 (distintos
meses/niveles), ≥2 N2 (acumulado), 1 proyección (mes en curso), 1 rechazo (gas), 1 ambiguo (Hocol).
`run_golden.py` (patrón del clasificador; **llama `ejecutor` con `_desempeno_fn` inyectado O corre contra
la BD dev, SIN LLM** — el intro se prueba aparte). `test_cuantificar.py` con casos deterministas
(resolver D-D5, slots N1/N2, ejecutor con `_desempeno_fn` fake).
> ⚠️ **pytest se corre en el SERVIDOR DE PRUEBAS**, no en dev (regla de entorno). En dev solo
> `py_compile` + pruebas de datos puntuales contra la BD (sin LLM).

### ✅ COMPUERTA 1e (cierre de Fase 1)
- **Dev (estático + datos, SIN LLM):** `py_compile` OK; N2 de Rubiales = Σ REAL de sus meses cerrados
  (verificar a mano: sumar Rubiales·crudo·REAL de ene..abr contra un SQL directo); el mes en curso NO
  entra en la suma y se declara; `slots.extraer_slots("acumulado de Rubiales")["nivel_temporal"]=="N2"`.
- **Servidor de pruebas:** golden ≥90% con paridad qwen/gemma4; pytest verde; en navegador el drill
  N1→"acumulado"→N2 mueve burbuja + panel.

---

## Reglas no negociables
1. **El número es VERBATIM de Python** (N1 y N2). El LLM solo redacta el intro (ya validado en 1c).
2. **N2 solo suma meses CERRADOS** (HE4); el mes en curso se DECLARA, no se suma.
3. **Panel aditivo** (HD4): jerarquizar/OUT dejan `panel=null` y NO tocan el visor. Solo el handler de
   **Consulta** pinta (HD3) — Test Clas y el lote intactos.
4. **Coherencia:** N1 y N2 salen de `analisis.desempeno` (mismo cálculo del tablero). NO SQL propio.
5. **Edificio separado:** cero imports de `consulta/` (v1). `niveles.py` importa de `analisis` (permitido).
6. **NO usar el LLM local de dev** para pruebas; runtime/navegador/pytest → servidor de pruebas.
7. **NO tocar** `resolver.py`, `catalogo.py` (de 1b), ni el flujo v1 (`__cnRender`, `/consulta/*`).

## Validaciones (comando → resultado; TODAS sin LLM, en dev salvo las marcadas «servidor»)
- **V-D1** `node --check` de `multitab_shell.js` → sin errores de sintaxis.
- **V-D2** (datos) `responder(...)` con `consulta_cuant_llm=false` → dict con `panel.datos.real==10966768.1332`
  y `cumplimiento_pct==90.8` (poner `CONSULTA_CUANT_LLM=false` ANTES del import; `get_settings` no cachea).
- **V-D3** `py_compile` de ejecutor/respuesta_cuantificar/maquina_q/slots/niveles → OK.
- **V-E1** `slots.extraer_slots("acumulado de Rubiales")["nivel_temporal"] == "N2"` y `extraer_slots("cuanto
  produjo Rubiales en abril")["nivel_temporal"] == "N1"`.
- **V-E2** (datos) `niveles.acumulado_crudo(resolver_unico("RUBIALES"))` → `real` = Σ SQL directo de
  Rubiales·CRUDO·REAL de los meses `completo` de 2026; `en_curso` = el mes parcial (no sumado).
- **V-E3** (servidor) golden ≥90%; pytest verde; navegador N1→N2 drill.

## Fuera de alcance (NO hacer)
Gas, blancos, N3 serie, N4 variación, referencias ≠ PPTO, gap/cumplimiento como variables propias,
diferidas, conteos de jerarquía, robustez especialista, filiales. Todo eso es Fase 2-4.
```
