# Plan de ejecución — Cuantificar · FASE 3 (N3 serie mensual + N4 variación mes a mes)

> **Tablas: N/A** — no toca ingesta ni tablas fuente (capa de respuesta sobre cifras ya calculadas).
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Fase 1 (crudo · N1+N2) y Fase 2 (gas+blancos · N1+N2), ambas mes/PPTO. Esta Fase 3 añade
> **N3 (serie mensual)** y **N4 (variación mes a mes)** para los 3 productos, grano mes, referencia PPTO.
> Completa los 4 niveles temporales de `motor_Q.md`. **Referencias ≠ PPTO → Fase 4** (fuera de alcance).
>
> **⚠️ RESTRICCIÓN DE ENTORNO (regla del usuario):** NO usar el LLM local de dev ni levantar la app en
> dev. En dev: solo `py_compile`, `node --check` y pruebas de DATOS contra Postgres (sin LLM). pytest,
> golden y navegador → **servidor de pruebas**.
>
> **Fecha:** 2026-08-02 · **Estado:** v2 AUDITADO (§0.2) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (§0.2 — verificados 2026-08-02)

| # | Hallazgo (verificado) | Efecto en el plan |
|---|----------------------|-------------------|
| **AF-3.1** | `desempeno` YA devuelve `ritmo_mensual` (`api.py:576,624`): `{meses:[3 letras], meses_num:[int], series:{PRODUCTO:[real|None]}, promedio_mes:{PRODUCTO:val}, mes_actual}`. Es la MISMA serie que pinta el panel del tablero. | **N3 la reusa** (cero SQL nuevo, coherencia por construcción). **N4 = deltas** sobre `series[PRODUCTO]`. |
| **AF-3.2** | `ritmo_mensual` es **REAL-only** (la query filtra `es.nombre='REAL'`, `api.py:583`). NO trae PPTO por mes. | N3/N4 describen la **trayectoria REAL**; NO se compara mes-a-mes vs PPTO (eso exigiría otra query → Fase 4). La referencia PPTO queda como contexto, no por punto. |
| **AF-3.3** | El **último** mes de la serie es una **PROYECCIÓN de cierre** (T-1) si `mes.completo=false` (mayo hoy). `promedio_mes` ya excluye el mes en curso (`api.py:595`). | N3 y N4 **DECLARAN** que el último mes es proyección (regla de honestidad del catálogo). El `promedio` viene ya de meses cerrados. |
| **AF-3.4 · router NO se toca** | Las frases verbales/adverbiales ya enrutan a cuantificar en Capa 1: **`MES A MES`** y **`COMO VARIO`** son patrones existentes (`patrones_grupo.yaml:60,61`). Las frases NOMINALES ("la variación de X", "la serie de X") NO tienen patrón. | **D-F3:** Fase 3 **NO edita `patrones_grupo.yaml`** ni el golden del clasificador. `slots` detecta N3/N4 por palabra clave (independiente del router). Las nominales degradan a **Capa 2 (LLM)** — mismo trato que cualquier cuantificar sin patrón. Se documenta; no bloquea. |
| **AF-3.5 · catálogo ya habilita N3/N4** | `productos.*.granos.mes.niveles: [N1,N2,N3,N4]` ya lista N3/N4 (`variables_cuantificables.yaml`). | **NO se edita el catálogo.** |
| **AF-3.6 · bordes** | N4 exige ≥2 puntos; N3 exige ≥1. | `niveles.serie`/`variacion` devuelven `{aplica:False, texto}` cuando faltan meses. |
| **AF-3.7 · precedencia y falsos positivos** | Detectar por *substring* es peligroso: `"BAJO"`∈`"trabajo"/"debajo"`, `"VARIO"`∈`"varios"`. | `slots._nivel_temporal` usa **match por TOKEN** para palabras sueltas y por frase para multi-palabra. Precedencia **N4 > N3 > N2 > N1** (variación es más específica que serie). |
| **AF-3.8 · panel transitorio** | El visor de Consulta es de v1 y `renderViewer` lo reconstruye (HD5, Fase 1d). | Los paneles N3/N4 son **transitorios** igual que el KPI de N1/N2. `__cnPintarPanelCuant` ramifica por `panel.tipo`. |

---

## 1. Contexto

Motor Q v2 · Grupo 2 (Cuantificar). Edificio SEPARADO
(`INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/`, cero imports de `consulta/` v1).
Regla madre: **Python calcula, el LLM solo redacta el intro**. La cifra sale de `analisis.desempeno`
(mismo cálculo del tablero). N3/N4 salen de `desempeno.ritmo_mensual` → coherencia garantizada.

## 2. Objetivo

Que "¿producción de crudo de Rubiales **mes a mes**?" (N3) y "¿**cómo varió** el gas de Cusiana mes a
mes?" (N4) respondan con intro cálido + cuerpo VERBATIM (serie / deltas, unidad correcta) + cierre +
**panel** (tabla compacta con barras para N3, deltas ▲▼ para N4). El último mes se declara proyección.

## 3. Prerequisitos

- Fase 1 y Fase 2 presentes y verificadas. Backend en
  `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend` (`uv run python` desde `backend/`).
- App padre en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.
- BD dev `daily_report_prod` arriba (solo para pruebas de datos; NUNCA LLM en dev).

## 4. Inventario de archivos

Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2`
Base app padre: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`

| Acción | Ruta |
|--------|------|
| EDITAR | `...\consulta_v2\cuantificar\slots.py` — `_nivel_temporal` detecta N3/N4 (token/frase, precedencia N4>N3>N2>N1) |
| EDITAR | `...\consulta_v2\cuantificar\niveles.py` — `serie(...)` + `variacion(...)` (reusan `ritmo_mensual`) |
| EDITAR | `...\consulta_v2\cuantificar\ejecutor.py` — dispatch N3/N4 + `ejecutar_n3` + `ejecutar_n4` |
| EDITAR | `...\consulta_v2\cuantificar\validador.py` — `formatear_cuerpo` ramas N3/N4 |
| EDITAR | `...\consulta_v2\respuesta_cuantificar.py` — `_panel_datos` por nivel + `panel.tipo` por nivel |
| EDITAR | `...\static\js\multitab_shell.js` — `__cnPintarPanelCuant` ramifica; `__cnCuantSerieHtml`/`__cnCuantVarHtml` |
| EDITAR | `...\static\css\colapsable.css` — clases `.cq-*` (tabla serie + deltas) |
| EDITAR | `...\consulta_v2\golden\cuantificar_golden.yaml` — +4 casos (2 N3, 2 N4) |
| EDITAR | `...\backend\tests\test_cuantificar.py` — +tests N3/N4 (slots, niveles, ejecutor, validador) |
| EDITAR | `...\templates\main.html` — subir cache-buster `?v=` |
| NO TOCAR | `resolver.py`, `catalogo.py`, `variables_cuantificables.yaml`, `patrones_grupo.yaml` (D-F3), `run_golden_cuantificar.py`*, `maquina_q.py`**, flujo v1 |

\* `run_golden_cuantificar.py` ya valida `nivel_temporal`+`producto`+`resultado` → sirve N3/N4 sin cambios.
\*\* `maquina_q.py` NO cambia: la memoria (AF9) ya guarda `producto`; el cierre de N3/N4 reusa el drill de
acumulado existente (ver §5.5). No se añaden drills nuevos en Fase 3.

## 5. Especificación (código de referencia)

### 5.1 — `slots.py` (EDITAR: `_nivel_temporal` + constantes N3/N4)

Reemplazar el bloque `_ACUM_KW` + `_nivel_temporal` actual por:

```python
# HE7: en forma NORMALIZADA (norm = MAYÚSCULAS sin tildes: "año"->"ANO").
_ACUM_KW = ("ACUMULADO", "ACUMULADA", "EN EL ANO", "EN LO QUE VA", "DEL ANO", "YTD",
            "HASTA AHORA", "EN TOTAL", "TOTAL DEL ANO")

# Fase 3 — N3 (serie) y N4 (variación). AF-3.7: TOKEN para palabras sueltas (evita "BAJO"∈"trabajo",
# "VARIO"∈"varios"); FRASE (substring) para multi-palabra. Sin bare "MES"/"MENSUAL" (pisarían N1).
_VAR_WORDS = {"VARIACION", "VARIO", "VARIARON", "CAMBIO", "CAMBIARON",
              "SUBIO", "BAJO", "CRECIO", "CAYO", "DELTA"}
_VAR_PHRASES = ("DE UN MES A OTRO", "DIFERENCIA ENTRE MESES")
_SERIE_WORDS = {"SERIE", "EVOLUCION", "MENSUALES"}
_SERIE_PHRASES = ("MES A MES", "MES POR MES", "POR MES", "CADA MES")


def _tiene(t: str, words: set, phrases: tuple) -> bool:
    toks = set(t.split())
    return any(w in toks for w in words) or any(p in t for p in phrases)


def _nivel_temporal(texto: str) -> str:
    t = norm(texto or "")
    if _tiene(t, _VAR_WORDS, _VAR_PHRASES):     # N4 gana (variación es más específica que serie)
        return "N4"
    if _tiene(t, _SERIE_WORDS, _SERIE_PHRASES):
        return "N3"
    if any(k in t for k in _ACUM_KW):
        return "N2"
    return "N1"
```
> El resto de `slots.py` (grounding de producto AF10, aterrizaje de catálogo, `_periodo_texto`,
> `extraer_slots`) NO cambia.

### 5.2 — `niveles.py` (AÑADIR: `serie` + `variacion`)

Añadir al final del archivo (importa ya `_desempeno_ep` y `_MESES`):

```python
def _serie_puntos(resuelta: dict, dim_producto: str, fn):
    """(puntos:[{mes,valor}], promedio, anio, proyeccion_mes) o (None, None, None, None).
    Reusa desempeno.ritmo_mensual (AF-3.1): la MISMA serie REAL mensual del panel."""
    d0 = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=None)
    if not d0.get("encontrada") or d0.get("sin_datos") or d0.get("sin_cierre"):
        return None, None, None, None
    ritmo = d0.get("ritmo_mensual") or {}
    meses = ritmo.get("meses") or []
    vals = (ritmo.get("series") or {}).get(dim_producto) or []
    puntos = [{"mes": meses[i], "valor": vals[i]}
              for i in range(min(len(meses), len(vals))) if vals[i] is not None]
    promedio = (ritmo.get("promedio_mes") or {}).get(dim_producto)
    # AF-3.3: el último punto es PROYECCIÓN si el mes más reciente no está cerrado (T-1).
    proyeccion_mes = puntos[-1]["mes"] if (puntos and not d0["mes"]["completo"]) else None
    return puntos, promedio, d0["mes"]["anio"], proyeccion_mes


def serie(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """N3: la serie REAL mensual del producto en el año. Solo rama A (la rama B la rechaza el ejecutor)."""
    fn = _desempeno_fn or _desempeno_ep
    puntos, promedio, anio, proy = _serie_puntos(resuelta, dim_producto, fn)
    if not puntos:
        return {"aplica": False,
                "texto": f"No tengo serie mensual de {dim_producto.lower()} para «{resuelta['valor']}»."}
    return {"aplica": True, "puntos": puntos, "promedio": promedio, "anio": anio, "proyeccion_mes": proy}


def variacion(resuelta: dict, dim_producto: str, _desempeno_fn=None) -> dict:
    """N4: deltas mes-a-mes sobre la serie REAL. Exige ≥2 puntos (AF-3.6)."""
    fn = _desempeno_fn or _desempeno_ep
    puntos, _prom, anio, proy = _serie_puntos(resuelta, dim_producto, fn)
    if not puntos or len(puntos) < 2:
        return {"aplica": False,
                "texto": f"«{resuelta['valor']}» no tiene suficientes meses de {dim_producto.lower()} "
                         f"para calcular variación."}
    deltas = []
    for i in range(1, len(puntos)):
        v0, v1 = puntos[i - 1]["valor"], puntos[i]["valor"]
        d = v1 - v0
        pct = round(d / v0 * 100.0, 1) if v0 else None
        deltas.append({"de": puntos[i - 1]["mes"], "a": puntos[i]["mes"], "delta": d, "pct": pct})
    return {"aplica": True, "deltas": deltas, "ultimo": deltas[-1], "anio": anio, "proyeccion_mes": proy}
```

### 5.3 — `ejecutor.py` (EDITAR `ejecutar` + AÑADIR `ejecutar_n3`/`ejecutar_n4`)

Reemplazar `ejecutar` (`ejecutor.py:21-25`) por:

```python
def ejecutar(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """Despacho por `slots["nivel_temporal"]`. N1 puntual · N2 acumulado · N3 serie · N4 variación."""
    nt = slots.get("nivel_temporal")
    if nt == "N4":
        return ejecutar_n4(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N3":
        return ejecutar_n3(resuelta, slots, _desempeno_fn=_desempeno_fn)
    if nt == "N2":
        return ejecutar_n2(resuelta, slots, _desempeno_fn=_desempeno_fn)
    return ejecutar_n1(resuelta, slots, _desempeno_fn=_desempeno_fn)
```

Añadir al final del archivo:

```python
def ejecutar_n3(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N3 serie mensual. HE6: contrato propio (lleva `serie`/`promedio`/`proyeccion_mes`)."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    s = _niveles.serie(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not s.get("aplica"):
        return {"aplica": False, "texto": s["texto"]}
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if s.get("proyeccion_mes"):
        avisos.append(f"El último mes ({s['proyeccion_mes']}) es proyección de cierre; aún no es un mes cerrado.")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N3",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "serie": s["puntos"], "promedio": s.get("promedio"), "anio": s["anio"],
        "proyeccion_mes": s.get("proyeccion_mes"),
        "huella": {"registros": len(s["puntos"]), "es_proyeccion": bool(s.get("proyeccion_mes"))},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n4(resuelta: dict, slots: dict, _desempeno_fn=None) -> dict:
    """N4 variación mes-a-mes. Contrato con `deltas`/`ultimo`/`proyeccion_mes`."""
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    producto = slots["producto"]
    unidad = slots.get("unidad", "bbl")
    v = _niveles.variacion(resuelta, _PROD_MAP[producto], _desempeno_fn=_desempeno_fn)
    if not v.get("aplica"):
        return {"aplica": False, "texto": v["texto"]}
    nivel_ent = resuelta.get("nivel")
    etiqueta = _NIVEL_TEXTO.get(nivel_ent, "")
    avisos = []
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    if v.get("proyeccion_mes"):
        avisos.append(f"El último mes ({v['proyeccion_mes']}) es proyección; el último cambio puede moverse al cerrar.")
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable", "produccion_crudo"),
        "nivel": "N4",
        "entidad": {"nombre": resuelta["valor"], "nivel": nivel_ent, "fue_asumida": False},
        "entidad_cualificada": f"{etiqueta} {resuelta['valor']}".strip(),
        "producto": producto, "referencia": "PPTO", "unidad": unidad, "grano": "mes",
        "universo": "reporte_diario",
        "deltas": v["deltas"], "ultimo": v["ultimo"], "anio": v["anio"],
        "proyeccion_mes": v.get("proyeccion_mes"),
        "huella": {"registros": len(v["deltas"]) + 1, "es_proyeccion": bool(v.get("proyeccion_mes"))},
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }
```

### 5.4 — `validador.py` (EDITAR `formatear_cuerpo`: ramas N3/N4 al inicio)

En `formatear_cuerpo`, tras `unidad = res.get("unidad", "bbl")` y ANTES de la rama N2, insertar:

```python
    nivel = res.get("nivel")
    if nivel == "N3":
        pares = " · ".join(f"{p['mes']} {fmt_valor(p['valor'], prod)}" for p in res["serie"])
        linea = f"{res['entidad_cualificada']} de {prod}, mes a mes en {res['anio']}: {pares} {unidad}."
        if res.get("promedio") is not None:
            linea += f" Promedio mensual (meses cerrados): {fmt_valor(res['promedio'], prod)} {unidad}."
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea
    if nivel == "N4":
        u = res["ultimo"]
        subio = u["delta"] >= 0
        pct = f" ({'+' if subio else '-'}{abs(u['pct'])}%)" if u.get("pct") is not None else ""
        cambios = " · ".join(
            f"{d['de']}→{d['a']} {'+' if d['delta'] >= 0 else '-'}{fmt_valor(abs(d['delta']), prod)}"
            for d in res["deltas"])
        linea = (f"{res['entidad_cualificada']} de {prod}: del mes de {u['de']} al de {u['a']} "
                 f"{'subió' if subio else 'bajó'} {fmt_valor(abs(u['delta']), prod)} {unidad}{pct}. "
                 f"Serie de cambios: {cambios} {unidad}.")
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea
```
> La firma de `formatear_cuerpo` y `res["nivel"]=="N2"`/N1 existentes NO cambian. `prod`, `unidad`,
> `real`, `pct`, `ppto` ya están calculados arriba; N3/N4 no usan `real`/`ppto`/`mes` → no fallan aunque
> el contrato N3/N4 no los traiga (se leen DESPUÉS, dentro de las ramas N2/N1). **Colocar las ramas N3/N4
> ANTES de la línea `mes = res["mes"]`** — si no, N3/N4 (sin `mes`) reventarían con KeyError.

⚠️ **Orden crítico:** `real = fmt_valor(res["resultado"]["valor"], prod)` (línea existente al inicio de
`formatear_cuerpo`) **asume `res["resultado"]`**, que N3/N4 NO traen. **Reformular el inicio** para no
tocar `resultado` hasta saber el nivel:

```python
def formatear_cuerpo(res: dict) -> str:
    prod = res.get("producto", "crudo")
    unidad = res.get("unidad", "bbl")
    nivel = res.get("nivel")

    if nivel == "N3":
        ...   # (rama N3 de arriba)
    if nivel == "N4":
        ...   # (rama N4 de arriba)

    # N1/N2 (usan resultado/referencia — solo aquí, ya descartados N3/N4):
    real = fmt_valor(res["resultado"]["valor"], prod)
    pct = f"{res['cumplimiento_pct']}%" if res.get("cumplimiento_pct") is not None else "s/d"
    ppto = fmt_valor(res["referencia_valor"], prod) if res.get("referencia_valor") else None
    if nivel == "N2":
        ...   # (rama N2 existente, SIN cambios)
    # N1 (rama existente, SIN cambios)
    ...
```

### 5.5 — `respuesta_cuantificar.py` (EDITAR `_panel_datos` + el `panel.tipo` del return)

Reemplazar `_panel_datos` (`respuesta_cuantificar.py:57-70`) por:

```python
def _panel_datos(res: dict) -> dict:
    """Datos del panel derecho, por nivel (N1/N2 KPI · N3 serie · N4 variación)."""
    nivel = res.get("nivel")
    d = {"nivel": nivel, "entidad_cualificada": res["entidad_cualificada"],
         "producto": res["producto"], "unidad": res["unidad"], "avisos": res.get("avisos", [])}
    if nivel == "N3":
        d.update({"serie": res["serie"], "promedio": res.get("promedio"),
                  "anio": res["anio"], "proyeccion_mes": res.get("proyeccion_mes")})
    elif nivel == "N4":
        d.update({"deltas": res["deltas"], "ultimo": res["ultimo"],
                  "anio": res["anio"], "proyeccion_mes": res.get("proyeccion_mes")})
    else:                                   # N1/N2 (KPI)
        d.update({"real": res["resultado"]["valor"], "ppto": res["referencia_valor"],
                  "cumplimiento_pct": res["cumplimiento_pct"], "estado": res["estado"]})
        if nivel == "N2":
            d["periodo_label"] = res["periodo_label"]; d["meses_cerrados"] = res["meses_cerrados"]
        else:
            d["mes"] = res["mes"]
    return d
```

Y añadir arriba del módulo (junto a `_CIERRE`):
```python
_PANEL_TIPO = {"N3": "cuant_serie", "N4": "cuant_var"}   # N1/N2 → "cuant_kpi"
```
Y en el `return` final de `responder` (`respuesta_cuantificar.py:97-98`), cambiar:
```python
    return {"mensaje": mensaje, "panel": {"tipo": "cuant_kpi", "datos": _panel_datos(res)}}
```
por:
```python
    tipo = _PANEL_TIPO.get(res.get("nivel"), "cuant_kpi")
    return {"mensaje": mensaje, "panel": {"tipo": tipo, "datos": _panel_datos(res)}}
```
> El cierre (`respuesta_cuantificar.py:97`) NO cambia: N3/N4 caen en el `else` → `_CIERRE`
> ("¿Quieres el acumulado del año?"), que dispara el drill N1→N2 ya existente (la memoria AF9 guarda
> `producto`). Sin drills nuevos (D-F3).

### 5.6 — `static\js\multitab_shell.js` (EDITAR `__cnPintarPanelCuant` + 2 funciones nuevas)

Reemplazar `__cnPintarPanelCuant` (`multitab_shell.js:2402`) por:

```javascript
  function __cnPintarPanelCuant(panel) {
    var area = el("cn-viewer-area"); if (!area || !panel || !panel.datos) return;
    var d = panel.datos;
    var body = (panel.tipo === "cuant_serie") ? __cnCuantSerieHtml(d)
             : (panel.tipo === "cuant_var")   ? __cnCuantVarHtml(d)
             : __cnCuantCardHtml(d);
    area.innerHTML =
      '<div style="height:100%;overflow:auto;padding:14px;">' +
      '  <div class="cn-p50-hd" style="margin-bottom:10px;"><i class="bi bi-calculator"></i> ' +
      '    Cuantificar · resultado</div>' +
      '  <div class="cn-p50-row">' + body + '</div>' +
      '</div>';
  }

  function __cnCuantSerieHtml(d) {
    var esGas = (d.producto === "gas");
    var fmtV = esGas ? function (v) { return __cnGasM(v); } : function (v) { return __cnMilesEC(Math.round(v)); };
    var unidad = d.unidad || "bbl";
    var pts = d.serie || [];
    var max = 0; pts.forEach(function (p) { if (p.valor > max) max = p.valor; });
    var rows = pts.map(function (p) {
      var w = max ? Math.round(p.valor / max * 100) : 0;
      var proy = (p.mes === d.proyeccion_mes) ? ' <em>(proy.)</em>' : '';
      return '<div class="cq-row">' +
        '<span class="cq-mes">' + esc(p.mes) + proy + '</span>' +
        '<span class="cq-bar"><span class="cq-bar__fill" style="width:' + w + '%"></span></span>' +
        '<span class="cq-val">' + fmtV(p.valor) + '</span></div>';
    }).join("");
    var prom = (d.promedio != null)
      ? '<div class="cq-foot">Promedio mensual: <b>' + fmtV(d.promedio) + ' ' + unidad + '</b></div>' : "";
    var avisos = (d.avisos || []).map(function (a) { return '<div class="cq-aviso">⚠️ ' + esc(a) + '</div>'; }).join("");
    return '<div class="cq-card">' +
      '<div class="cq-hd">' + esc(d.entidad_cualificada || "") + ' · ' + esc(d.producto) +
        ' mes a mes ' + (d.anio || "") + ' <span class="cq-unit">(' + unidad + ')</span></div>' +
      rows + prom + avisos + '</div>';
  }

  function __cnCuantVarHtml(d) {
    var esGas = (d.producto === "gas");
    var fmtV = esGas ? function (v) { return __cnGasM(v); } : function (v) { return __cnMilesEC(Math.round(v)); };
    var unidad = d.unidad || "bbl";
    var rows = (d.deltas || []).map(function (x) {
      var up = x.delta >= 0;
      var pct = (x.pct != null) ? (' (' + (up ? '+' : '-') + Math.abs(x.pct) + '%)') : "";
      return '<div class="cq-row">' +
        '<span class="cq-mes">' + esc(x.de) + ' → ' + esc(x.a) + '</span>' +
        '<span class="cq-delta ' + (up ? 'is-up' : 'is-down') + '">' +
          (up ? '▲ +' : '▼ -') + fmtV(Math.abs(x.delta)) + pct + '</span></div>';
    }).join("");
    var avisos = (d.avisos || []).map(function (a) { return '<div class="cq-aviso">⚠️ ' + esc(a) + '</div>'; }).join("");
    return '<div class="cq-card">' +
      '<div class="cq-hd">' + esc(d.entidad_cualificada || "") + ' · variación de ' + esc(d.producto) +
        ' ' + (d.anio || "") + ' <span class="cq-unit">(' + unidad + ')</span></div>' +
      rows + avisos + '</div>';
  }
```
> `__cnGasM`/`__cnMilesEC`/`esc`/`el` ya existen. Los paneles son transitorios (AF-3.8).

### 5.7 — `static\css\colapsable.css` (AÑADIR clases `.cq-*` al final)

```css
/* Motor Q v2 · Cuantificar N3/N4 (serie mensual + variación) — panel transitorio */
.cq-card { font-size: 13px; color: #3C4A44; }
.cq-hd { font-weight: 700; margin-bottom: 8px; }
.cq-unit { font-weight: 400; color: #6B7A74; }
.cq-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
.cq-mes { flex: 0 0 96px; color: #55635C; }
.cq-mes em { color: #8A6D3B; font-style: normal; font-size: 11px; }
.cq-bar { flex: 1 1 auto; height: 10px; background: #EEF1F0; border-radius: 5px; overflow: hidden; }
.cq-bar__fill { display: block; height: 100%; background: #1E9E5A; }
.cq-val { flex: 0 0 auto; font-variant-numeric: tabular-nums; font-weight: 600; }
.cq-delta { flex: 0 0 auto; font-variant-numeric: tabular-nums; font-weight: 600; }
.cq-delta.is-up { color: #1E9E5A; }
.cq-delta.is-down { color: #D64545; }
.cq-foot { margin-top: 8px; padding-top: 6px; border-top: 1px solid #EEF1F0; }
.cq-aviso { margin-top: 6px; font-size: 12px; color: #8A6D3B; }
```

### 5.8 — `golden\cuantificar_golden.yaml` (AÑADIR al final)

```yaml

# ---- Fase 3: N3 serie (2) ----
- pregunta: "¿producción de crudo de Rubiales mes a mes?"
  entidad: "RUBIALES"
  nivel_temporal: N3
  producto: crudo
  resultado: aplica
- pregunta: "¿serie mensual de gas de Cusiana?"
  entidad: "CUSIANA"
  nivel_temporal: N3
  producto: gas
  resultado: aplica

# ---- Fase 3: N4 variación (2) ----
- pregunta: "¿cómo varió el crudo de Rubiales mes a mes?"
  entidad: "RUBIALES"
  nivel_temporal: N4
  producto: crudo
  resultado: aplica
- pregunta: "¿cuál fue la variación de gas de Cusiana?"
  entidad: "CUSIANA"
  nivel_temporal: N4
  producto: gas
  resultado: aplica
```
> El runner llama `slots`+`resolver`+`ejecutor` directo (NO el clasificador) → valida la maquinaria de
> cuantificar. `nivel_temporal`+`producto` son deterministas (deben pasar 100%); el `resultado` depende
> de la BD (Rubiales/Cusiana con ≥2 meses cerrados de crudo/gas → `aplica`). Ajustar entidad si la BD lo pide.

### 5.9 — `tests\test_cuantificar.py` (AÑADIR al final)

Añadir `from app.features.consulta_v2.cuantificar import niveles as _niveles` al encabezado, y:

```python
# ================= Fase 3: N3 serie + N4 variación =================

def test_slots_n3_mes_a_mes():
    assert _slots.extraer_slots("produccion de Rubiales mes a mes")["nivel_temporal"] == "N3"


def test_slots_n3_serie_palabra():
    assert _slots.extraer_slots("serie mensual de Rubiales")["nivel_temporal"] == "N3"


def test_slots_n4_como_vario():
    assert _slots.extraer_slots("como vario Rubiales mes a mes")["nivel_temporal"] == "N4"


def test_slots_n4_gana_sobre_n3():
    # variación + mes a mes -> N4 (más específico)
    assert _slots.extraer_slots("variacion mes a mes de Rubiales")["nivel_temporal"] == "N4"


def test_slots_n1_no_falso_por_token_bajo():
    # AF-3.7: 'BAJO' es token de _VAR_WORDS, pero 'trabajo'/'debajo' NO lo contienen como TOKEN
    assert _slots.extraer_slots("produccion por debajo de Rubiales")["nivel_temporal"] != "N4"


def _fake_ritmo(entidad="X", segmento="ecp", nivel="campo", periodo=None):
    # 4 meses cerrados + mayo en curso (proyección). GAS/BLANCOS vacíos para probar "no aplica".
    return {"encontrada": True, "sin_datos": False, "sin_cierre": False,
            "mes": {"anio": 2026, "mes": 5, "nombre": "Mayo", "completo": False,
                    "dias_con_data": 17, "dias_del_mes": 31},
            "por_producto": [{"producto": "CRUDO", "real": 0, "ppto": 0, "cumplimiento": None}],
            "ritmo_mensual": {"meses": ["Ene", "Feb", "Mar", "Abr", "May"], "meses_num": [1, 2, 3, 4, 5],
                              "series": {"CRUDO": [100, 110, 105, 120, 60],
                                         "GAS": [None, None, None, None, None],
                                         "BLANCOS": [None, None, None, None, None]},
                              "promedio_mes": {"CRUDO": 109}, "promedio_dia": {}, "mes_actual": 5}}


def test_niveles_serie_crudo_con_proyeccion():
    s = _niveles.serie({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert s["aplica"] and len(s["puntos"]) == 5
    assert s["proyeccion_mes"] == "May" and s["promedio"] == 109


def test_niveles_variacion_deltas():
    v = _niveles.variacion({"nivel": "campo", "valor": "RUBIALES"}, "CRUDO", _desempeno_fn=_fake_ritmo)
    assert v["aplica"] and len(v["deltas"]) == 4
    assert v["deltas"][0]["delta"] == 10 and v["deltas"][0]["pct"] == 10.0
    assert v["ultimo"]["de"] == "Abr" and v["ultimo"]["a"] == "May" and v["ultimo"]["delta"] == -60


def test_niveles_variacion_gas_sin_datos_no_aplica():
    v = _niveles.variacion({"nivel": "campo", "valor": "RUBIALES"}, "GAS", _desempeno_fn=_fake_ritmo)
    assert v["aplica"] is False


def test_ejecutar_n3_dispatch():
    slots = _slots.extraer_slots("produccion de Rubiales mes a mes")
    res = _ejecutor.ejecutar({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                             slots, _desempeno_fn=_fake_ritmo)
    assert res["nivel"] == "N3" and len(res["serie"]) == 5 and res["proyeccion_mes"] == "May"


def test_ejecutar_n4_dispatch():
    slots = _slots.extraer_slots("como vario Rubiales mes a mes")
    res = _ejecutor.ejecutar({"nivel": "campo", "rama": "A", "valor": "RUBIALES", "zoom": []},
                             slots, _desempeno_fn=_fake_ritmo)
    assert res["nivel"] == "N4" and res["ultimo"]["delta"] == -60


def test_formatear_cuerpo_n3():
    res = {"nivel": "N3", "producto": "crudo", "unidad": "bbl", "anio": 2026,
           "serie": [{"mes": "Ene", "valor": 100}, {"mes": "Feb", "valor": 110}],
           "promedio": 105, "avisos": []}
    c = _validador.formatear_cuerpo(res)
    assert "mes a mes" in c and "Ene 100" in c and "Promedio" in c


def test_formatear_cuerpo_n4():
    res = {"nivel": "N4", "producto": "crudo", "unidad": "bbl", "anio": 2026,
           "deltas": [{"de": "Ene", "a": "Feb", "delta": 10, "pct": 10.0}],
           "ultimo": {"de": "Ene", "a": "Feb", "delta": 10, "pct": 10.0}, "avisos": []}
    c = _validador.formatear_cuerpo(res)
    assert "subió" in c and "Feb" in c
```

### 5.10 — `templates\main.html` (cache-buster)

Subir el `?v=` del `<script ... multitab_shell.js>` (`main.html:82`), p.ej. `?v=20260802i1`.

## 6. Orden de ejecución

1. `slots.py` (5.1) → `niveles.py` (5.2) → `ejecutor.py` (5.3) → `validador.py` (5.4) →
   `respuesta_cuantificar.py` (5.5). **`py_compile` de los 5.**
2. Frontend `multitab_shell.js` (5.6) + `colapsable.css` (5.7) + `main.html` (5.10).
   **`node --check multitab_shell.js`.**
3. golden (5.8) + tests (5.9).
4. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **El número es VERBATIM de Python** (serie y deltas); el LLM solo redacta el intro (1c).
2. **N3/N4 salen de `desempeno.ritmo_mensual`** (mismo cálculo del panel). NO SQL propio.
3. **Honestidad (AF-3.3):** el último mes se declara PROYECCIÓN si no está cerrado; el promedio es de
   meses cerrados.
4. **Unidades del catálogo** (Fase 2): gas ÷1e6 "MSCF" (mirror `__cnGasM`), crudo/blancos raw "bbl".
   Deltas de gas también ÷1e6.
5. **D-F3:** NO editar `patrones_grupo.yaml` ni su golden. Las frases nominales degradan a Capa 2.
6. **Edificio separado:** cero imports de `consulta/` v1. NO tocar `resolver.py`, `catalogo.py`,
   `variables_cuantificables.yaml`, `maquina_q.py`, el flujo v1.
7. **NO usar el LLM local de dev**; runtime/navegador/pytest → servidor de pruebas.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo las marcadas «servidor»)

- **V1** (estático) `py_compile` de slots/niveles/ejecutor/validador/respuesta_cuantificar → OK.
- **V2** (estático) `node --check static/js/multitab_shell.js` → sin errores.
- **V3** (datos, dev, SIN LLM) `slots.extraer_slots("produccion de Rubiales mes a mes")["nivel_temporal"]=="N3"`;
  `slots.extraer_slots("como vario Rubiales")["nivel_temporal"]=="N4"`;
  `slots.extraer_slots("variacion mes a mes de X")["nivel_temporal"]=="N4"`;
  `slots.extraer_slots("cuanto produjo Rubiales en abril")["nivel_temporal"]=="N1"` (sin regresión).
- **V4** (datos, dev, SIN LLM) `niveles.serie(resolver_unico("RUBIALES"),"CRUDO")` → `puntos` = la serie
  REAL mensual de Rubiales·crudo (= `ritmo_mensual.series.CRUDO` de `desempeno`), `proyeccion_mes` = el
  último mes si no está cerrado; `niveles.variacion(...)` → `len(deltas)==len(puntos)-1`.
- **V5** (servidor) `run_golden_cuantificar.py` → ≥90%; `nivel_temporal`+`producto` aciertan 100%.
- **V6** (servidor) pytest `tests/test_cuantificar.py` verde (Fase 1+2+3).
- **V7** (servidor, navegador) Motor v2: "producción de crudo de Rubiales **mes a mes**" → burbuja con la
  serie + panel tabla-con-barras (último mes «proy.»); "**cómo varió** el gas de Cusiana mes a mes" →
  deltas ▲▼ en MSCF. N1/N2 sin regresión. (Frases nominales "la variación de X" → Capa 2, LLM: verificar
  aparte que enrutan a cuantificar.)

## 9. Fuera de alcance (NO hacer)

- **Referencias ≠ PPTO** (REAL/OPERATIVO/CONTABLE/P50/promedio_anio) — Fase 4. En particular P50 es
  ECP-global (kbpe) y no reconcilia a nivel campo/activo.
- **Comparación mes-a-mes vs PPTO** (AF-3.2: `ritmo_mensual` es REAL-only).
- **Grano DÍA** (serie diaria dentro de un mes), periodos año/trimestre/semana.
- **Nuevos drills** N1→N3 / N3→N4 (se conserva solo el drill acumulado→N2 de Fase 1e).
- **Editar el clasificador** (`patrones_grupo.yaml` / su golden) — D-F3.
- Agua, derivadas (gap/cumplimiento como variables), conteos/jerarquía, robustez especialista, diferidas.
