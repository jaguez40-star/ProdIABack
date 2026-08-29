# PLAN EJECUTABLE — Cobertura del reporte filtrable por entidad (PRESENCIA)

> **Modo:** ejecutable por un agente externo al pie de la letra.
> **Fecha:** 2026-07-08 · **Diseño:** `DISENO_CAPA_CONVERSACIONAL.md`.
> **Cobertura:** N/A (no modela hojas Excel ni toca ETL/DDL/grano). Endpoint **read-only** + UI.
> **Auditoría §0.2:** no dispara pre-audit obligatorio (sin cambios de esquema/ETL). Igual se **verificó la
> factibilidad** contra la BD: `bronze.hoja_landing` (~443K filas, GIN en payload) resuelve la presencia por
> texto en **~9.5s**; `fact_tabla_hoja` (62M) queda FUERA (por eso no hace falta índice nuevo).

---

## 0. Auditoría de validación del plan (2026-07-08)

Verificado contra el código real ANTES de dar el plan por bueno:
- ✅ `api.py`: `Query` importado (L1); `/cobertura` existe (L205, sin `entidad`) → el reemplazo del §5.1 es
  válido; aún no hay `_presencia_entidad`.
- ✅ `multitab_shell.js`: el módulo va de la L666 (`// ==== Modulo HUELLA DE DATOS`) hasta el cierre de
  `__anHuellaChart` (~L773), justo antes de `window.MultiTabShell` (L774) → el reemplazo del §5.3 es válido.
  Botón del menú en L529.
- ✅ `routes/api.py`: proxy `analisis_cobertura` presente (verificado 200 en runtime).

Hallazgos y reformulaciones aplicadas:
- 🔴 **F1 (CORREGIDO en este plan):** el "filas" del panorama salía de `SUM(ingesta_log.filas_insertadas)` →
  **sobre-cuenta 25.7×** (BDP_datos_dia: **11.203.341** acumulado vs **435.347** filas reales en la tabla, por
  los upserts idempotentes en 138 reportes). Es engañoso. **Reformulación:** se ELIMINA "filas"; la métrica
  única es **reportes** (`COUNT(DISTINCT reporte_id)`, correcta y coherente con el enfoque de presencia).
  Sin entidad → "en N reportes"; con entidad → "en K de N reportes".
- 🟠 **F2 (documentado):** asimetría de match — RAW = exacto (`dim_fuente`), resto = substring (`ILIKE` en
  landing). Inherente a las 2 fuentes; se declara como limitación conocida (§9).
- 🟡 **F3 (nota):** al quitar los gráficos de barras, `/analisis/huella` (endpoint + su proxy) queda
  **huérfano** (ya nadie lo llama). Se deja (inofensivo); limpieza opcional futura (§9).

---

## 1. Contexto

- **Repo padre (Flask :8020):** `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\`
  - Proxy a INGESTA en `routes/api.py` (blueprint `api_bp`, prefijo `/api`, `INGESTA_API_URL=http://localhost:8000`).
  - Pestaña Análisis del MultiTab Shell en `static/js/multitab_shell.js`. Módulo actual "Huella de datos".
- **INGESTA (FastAPI :8000):** `...\INGESTA\Rep_Prod\backend\`. Feature `analisis` en
  `backend/app/features/analisis/api.py` (endpoints `/analisis/{catalogo,densidad,huella,cobertura}`).
- **BD Postgres local `daily_report_prod`** (vía `.env` / `get_engine()`).
- **Estado actual del módulo "Huella de datos"** (a modificar): tiene (1) tabla de Cobertura, (2) gráfico
  de barras "Panorama global", (3) input de entidad que dibuja un 2º gráfico de barras "Huella de la entidad".
- **Decisión del usuario:** ELIMINAR los 2 gráficos de barras. Dejar SOLO la **tabla de cobertura**, y que el
  **input de entidad la FILTRE** mostrando, por hoja, **en cuántos reportes aparece la entidad** (PRESENCIA),
  no conteo de filas.

## 2. Objetivo

Que el módulo muestre **una sola tabla de cobertura** (28 hojas agrupadas por categoría) y que, al escribir
una entidad (ej. `CHICHIMENE`), la misma tabla muestre por cada hoja **"N reportes con la entidad"**
(de cuántos reportes tienen esa hoja). Sin gráficos de barras.

**Fuentes de la presencia (sin tocar los 62M de `fact_tabla_hoja`):**
- **Hojas RAW** (`BDP_datos_dia/mes/Programa`): vía los facts ECP (`dim_fuente`, exacto, indexado).
- **Resto de hojas** (modeladas + preservadas + COMENTARIOS): vía `bronze.hoja_landing` (payload JSONB,
  `ILIKE` por texto, ~10s).

## 3. Prerequisitos

- FastAPI :8000 y Flask :8020 operativos.
- BD poblada (`bronze.hoja_landing`, `core.ingesta_log`, facts ECP, `dim_fuente`).
- Verificación previa:
  ```
  curl -s http://localhost:8000/health
  curl -s http://localhost:8000/analisis/cobertura | head -c 200
  ```
  Esperado: `{"status":"ok"}` y un JSON con `categorias`.

## 4. Inventario de archivos

| # | Archivo | Acción |
|---|---------|--------|
| A1 | `...\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | **EDITAR** (helper `_presencia_entidad` + `cobertura` con `?entidad=`) |
| A2 | `...\12112025_prodIA\routes\api.py` | **EDITAR** (proxy `/analisis/cobertura` pasa `entidad` + timeout 90) |
| A3 | `...\12112025_prodIA\static\js\multitab_shell.js` | **EDITAR** (reemplazar el módulo por la tabla filtrable; quitar barras; renombrar botón) |

Sin migraciones, sin DDL, sin índices nuevos.

---

## 5. Especificación

### 5.1 · A1 — `backend/app/features/analisis/api.py`

**(a)** El endpoint `/cobertura` ya existe. **Reemplazar su firma y cuerpo COMPLETO** (desde
`@router.get("/cobertura")` hasta su `return`) por lo siguiente, que **añade el parámetro `entidad`** y un
helper de presencia. `Query` ya está importado (se usa en `/huella`).

```python
def _presencia_entidad(c, entidad):
    """{hoja: nº de reportes donde aparece la entidad}.
    RAW (BDP_datos_dia/mes/Programa) vía facts ECP (exacto, indexado);
    el resto vía bronze.hoja_landing (ILIKE por texto sobre payload JSONB, ~10s, sin tocar los 62M)."""
    E = (entidad or "").strip().upper()
    pres = {}
    ids = [r[0] for r in c.execute(sa.text("""
        SELECT fuente_id FROM core.dim_fuente
        WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
           OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
    """), {"e": E}).all()]
    if ids:
        in_ids = sa.bindparam("ids", expanding=True)
        pres["BDP_datos_dia"] = c.execute(sa.text(
            "SELECT COUNT(DISTINCT reporte_id) FROM core.fact_produccion_dia_ecp WHERE fuente_id IN :ids"
        ).bindparams(in_ids), {"ids": ids}).scalar() or 0
        pres["BDP_datos_mes"] = c.execute(sa.text(
            "SELECT COUNT(DISTINCT reporte_id) FROM core.fact_produccion_mes_ecp WHERE fuente_id IN :ids"
        ).bindparams(in_ids), {"ids": ids}).scalar() or 0
        pres["BDP_Programa"] = c.execute(sa.text("""
            SELECT COUNT(DISTINCT reporte_id) FROM core.fact_programa_ecp
            WHERE fuente_id IN :ids OR UPPER(TRIM(campo))=:e OR UPPER(TRIM(area))=:e
        """).bindparams(in_ids), {"ids": ids, "e": E}).scalar() or 0
    else:
        pres["BDP_Programa"] = c.execute(sa.text("""
            SELECT COUNT(DISTINCT reporte_id) FROM core.fact_programa_ecp
            WHERE UPPER(TRIM(campo))=:e OR UPPER(TRIM(area))=:e
        """), {"e": E}).scalar() or 0
    # resto: bronze.hoja_landing (payload::text ILIKE, con escape de comodines)
    patt = "%" + E.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    for r in c.execute(sa.text("""
        SELECT hoja, COUNT(DISTINCT reporte_id) FROM bronze.hoja_landing
        WHERE payload::text ILIKE :pat ESCAPE '\\' GROUP BY hoja
    """), {"pat": patt}):
        pres[r[0]] = r[1]
    return pres


@router.get("/cobertura")
def cobertura(entidad: str | None = Query(None)):
    """Mapa de cobertura del reporte: TODAS las hojas por categoría (fuente: core.ingesta_log).
    Métrica = nº de REPORTES (COUNT DISTINCT reporte_id). Sin 'entidad' → en cuántos reportes está cada hoja.
    Con 'entidad' → en cuántos reportes APARECE la entidad por hoja (PRESENCIA): RAW vía facts ECP; resto vía
    bronze.hoja_landing. NO toca fact_tabla_hoja (62M). NO usa SUM(filas_insertadas) (sobre-cuenta ~26x)."""
    from collections import OrderedDict
    CATS = ["Producción ECP", "Filiales", "Comentarios",
            "Hojas modeladas (visor)", "Preservada en crudo (Bronze)"]
    PRIOR = {c: i for i, c in enumerate(CATS)}

    def cat_of(dest):
        d = (dest or "").lower()
        if d in ("core.fact_produccion_dia_ecp", "core.fact_produccion_mes_ecp", "core.fact_programa_ecp"):
            return "Producción ECP"
        if d in ("core.fact_produccion_diaria", "core.fact_plan_mensual", "core.fact_promedio_validado"):
            return "Filiales"
        if d == "core.fact_comentarios_produccion":
            return "Comentarios"
        if d == "core.fact_tabla_hoja":
            return "Hojas modeladas (visor)"
        return "Preservada en crudo (Bronze)"

    eng = get_engine()
    with eng.connect() as c:
        c.execute(sa.text("SET statement_timeout='60s'"))
        rows = c.execute(sa.text("""
            SELECT hoja, tabla_destino, COUNT(DISTINCT reporte_id) reps
            FROM core.ingesta_log
            GROUP BY hoja, tabla_destino
        """)).mappings().all()

        # F1: la métrica es 'reportes' (COUNT DISTINCT reporte_id), NO SUM(filas_insertadas) — esta última
        # sobre-cuenta ~26x por los upserts idempotentes acumulados en 138 reportes (11.2M vs 435K reales).
        por_hoja = {}
        for r in rows:
            hoja = r["hoja"] or "(sin nombre)"
            cat = cat_of(r["tabla_destino"])
            cur = por_hoja.get(hoja)
            if cur is None or PRIOR[cat] < PRIOR[cur["categoria"]]:
                por_hoja[hoja] = {"hoja": hoja, "categoria": cat, "reportes_total": r["reps"]}

        if entidad:
            pres = _presencia_entidad(c, entidad)
            for h in por_hoja.values():
                h["reportes_entidad"] = int(pres.get(h["hoja"], 0))

    def _ordkey(x):
        return -(x.get("reportes_entidad", x["reportes_total"]))
    cats = OrderedDict((k, []) for k in CATS)
    for h in sorted(por_hoja.values(), key=_ordkey):
        cats[h["categoria"]].append(h)
    categorias = [{"categoria": k, "hojas": v} for k, v in cats.items() if v]
    out = {"entidad": entidad, "total_hojas": len(por_hoja), "categorias": categorias}
    if entidad:
        out["hojas_con_entidad"] = sum(1 for h in por_hoja.values() if h.get("reportes_entidad", 0) > 0)
    return out
```

> **Nota:** conservar el helper `_presencia_entidad` JUSTO ANTES de `@router.get("/cobertura")`.

### 5.2 · A2 — `routes/api.py` (proxy)

**Reemplazar** la función `analisis_cobertura` existente por:

```python
@api_bp.route("/analisis/cobertura")
def analisis_cobertura():
    """Proxy: cobertura del reporte (todas las hojas por categoría). Con ?entidad= → presencia por hoja."""
    try:
        params = {}
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        resp = requests.get(f"{INGESTA_API_URL}/analisis/cobertura", params=params, timeout=90)
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"INGESTA no disponible: {e}"}), 502
```

### 5.3 · A3 — `static/js/multitab_shell.js`

**(a) Renombrar el botón del menú.** Buscar y reemplazar:
```javascript
      '    <button type="button" class="ig-trow" onclick="window.__anShowHuella()">' +
      '      <i class="bi bi-bar-chart-steps"></i><span class="ig-trow__name">Huella de datos</span></button>' +
```
por:
```javascript
      '    <button type="button" class="ig-trow" onclick="window.__anShowHuella()">' +
      '      <i class="bi bi-bar-chart-steps"></i><span class="ig-trow__name">Cobertura del reporte</span></button>' +
```

**(b) Reemplazar TODO el módulo.** Localizar el bloque que empieza en la línea con el comentario
`// ============ Modulo HUELLA DE DATOS` (o `Modulo COBERTURA`) y termina en la **llave de cierre de la
función `__anHuellaChart`** (la `}` que está JUSTO ANTES de la línea `window.MultiTabShell = { mount: mount, unmount: unmount };`).
**Reemplazar ese bloque COMPLETO** (incluye `__anCatColor`, `__anRenderCobertura`, `__anShowHuella`,
`__anHuellaEntidad`, `__anHuellaChart` — se eliminan los gráficos de barras) por:

```javascript
  // ============ Modulo COBERTURA DEL REPORTE (todas las hojas, filtrable por entidad = PRESENCIA) ============
  var __anCatColor = {
    "Producción ECP": "#0d6efd", "Filiales": "#20c997", "Comentarios": "#6f42c1",
    "Hojas modeladas (visor)": "#fd7e14", "Preservada en crudo (Bronze)": "#6c757d"
  };

  function __anRenderCobertura(cob) {
    if (!cob || !cob.categorias) return '<div class="text-muted small">Sin datos de cobertura.</div>';
    var ent = cob.entidad;
    var html = ent
      ? ('<h6 class="mb-1"><i class="bi bi-grid-3x3-gap"></i> Presencia de <strong>' + esc(ent) +
         '</strong> — aparece en ' + (cob.hojas_con_entidad || 0) + ' de ' + cob.total_hojas + ' hojas</h6>' +
         '<div class="text-muted small mb-2">Nº de reportes donde cada hoja contiene la entidad. RAW vía facts ' +
         '(exacto); resto vía <code>bronze.hoja_landing</code> (coincidencia por texto, puede sobre-emparejar nombres similares).</div>')
      : ('<h6 class="mb-1"><i class="bi bi-grid-3x3-gap"></i> Cobertura del reporte — ' + cob.total_hojas + ' hojas</h6>' +
         '<div class="text-muted small mb-2">TODAS las hojas ingeridas por categoría (fuente: <code>core.ingesta_log</code>). ' +
         'Escribe una entidad arriba para ver en cuántos reportes aparece por hoja.</div>');
    cob.categorias.forEach(function (c) {
      var col = __anCatColor[c.categoria] || "#6c757d";
      html += '<div style="margin:8px 0 2px;font-weight:600;">' +
        '<span style="display:inline-block;width:11px;height:11px;border-radius:2px;background:' + col +
        ';margin-right:6px;"></span>' + esc(c.categoria) +
        ' <span class="text-muted small">(' + c.hojas.length + (c.hojas.length === 1 ? ' hoja)' : ' hojas)') + '</span></div>';
      html += '<table class="table table-sm mb-1" style="font-size:.8rem;"><tbody>';
      c.hojas.forEach(function (h) {
        var rowStyle = "", right;
        if (ent) {
          var k = h.reportes_entidad || 0;
          if (k === 0) rowStyle = ' style="opacity:.4;"';
          right = '<td class="text-end">' + (k > 0 ? '<strong>' + k + '</strong>' : '0') +
            ' <span class="text-muted small">de ' + h.reportes_total + ' rep.</span></td>';
        } else {
          right = '<td class="text-end"><strong>' + h.reportes_total + '</strong> reportes</td>';
        }
        html += '<tr' + rowStyle + '><td>' + esc(h.hoja) + '</td>' + right + '</tr>';
      });
      html += '</tbody></table>';
    });
    return html;
  }

  window.__anShowHuella = function () {
    __anLoading("Cargando cobertura…");
    fetch("/api/analisis/cobertura").then(function (r) { return r.json(); }).then(function (cob) {
      var a = __anArea(); if (!a) return;
      a.innerHTML =
        '<div class="mb-2"><strong>Filtrar por entidad:</strong> ' +
        '<input id="an-cob-input" class="form-control form-control-sm d-inline-block" ' +
        'style="max-width:260px;vertical-align:middle;" placeholder="Ej: CHICHIMENE (vacío = todas)" ' +
        'onchange="window.__anCoberturaEntidad(this.value)"> ' +
        '<button type="button" class="btn btn-sm btn-outline-secondary" ' +
        'onclick="var i=document.getElementById(\'an-cob-input\'); if(i){i.value=\'\';} window.__anCoberturaEntidad(\'\');">Ver todas</button>' +
        '</div>' +
        '<div id="an-cob-body"></div>';
      var b = el("an-cob-body"); if (b) b.innerHTML = __anRenderCobertura(cob);
    }).catch(__anError);
  };

  window.__anCoberturaEntidad = function (nom) {
    var body = el("an-cob-body"); if (!body) return;
    var q = (nom || "").trim();
    var url = "/api/analisis/cobertura" + (q ? ("?entidad=" + encodeURIComponent(q)) : "");
    body.innerHTML = '<div class="text-muted small p-2"><div class="spinner-border spinner-border-sm"></div> ' +
      (q ? ('Buscando presencia de ' + esc(q) + '… (puede tardar ~10s)') : 'Cargando…') + '</div>';
    fetch(url).then(function (r) { return r.json(); }).then(function (cob) {
      body.innerHTML = __anRenderCobertura(cob);
    }).catch(function () { body.innerHTML = '<div class="alert alert-danger m-1 small">Error cargando la cobertura.</div>'; });
  };
```

> El bloque nuevo **NO** contiene `__anHuellaChart` ni fetch a `/analisis/huella` → los gráficos de barras
> quedan eliminados. Si el linter marca `Plotly`/`huella` sin usar en otra parte, ignorar (no se referencian).

---

## 6. Orden de ejecución

1. Editar A1 (`api.py`): helper `_presencia_entidad` + `cobertura(entidad=...)`.
2. Editar A2 (`routes/api.py`): proxy pasa `entidad` + `timeout=90`.
3. Editar A3 (`multitab_shell.js`): renombrar botón + reemplazar el módulo por la tabla filtrable.
4. **Reiniciar backends.** Si `iniciar_backends.bat` no relanza de forma fiable, lanzar cada backend con el
   **python base** (leer `home` de `pyvenv.cfg`) + `PYTHONPATH` al site-packages del venv, como hace el `.bat`.
   FastAPI: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (cwd = `INGESTA\Rep_Prod\backend`,
   `PYTHONPATH=...\.venv\Lib\site-packages`). Flask: `python app.py` (cwd = raíz, `PYTHONPATH=...\venv\Lib\site-packages`).
5. Correr las Validaciones (§8).

## 7. Reglas no negociables

- **Solo lectura.** Prohibido escribir en tablas, tocar DDL/ETL/migraciones o crear índices.
- **NO** consultar `core.fact_tabla_hoja` (62M) para la presencia — usar `bronze.hoja_landing` + facts ECP.
- `statement_timeout` del endpoint = **60s**; timeout del proxy = **90s** (el `ILIKE` de landing tarda ~10s).
- Mantener las **5 categorías** y el orden por prioridad de destino.
- Sin entidad → columna "filas + rep."; con entidad → columna "N de M rep." (presencia). Filas con 0 presencia → atenuadas, NO ocultas.
- Respetar el estilo del archivo JS (IIFE, `var`, concatenación de strings).

## 8. Validaciones (comando → resultado esperado)

**V1 — cobertura sin entidad (FastAPI):**
```
curl -s http://localhost:8000/analisis/cobertura
```
Esperado: `entidad:null`, `total_hojas` ≈ **28**, `categorias` con las 5 categorías; cada hoja con
`reportes_total` (NO debe existir `filas`). Ej.: `BDP_datos_dia` → `reportes_total`=138.

**V2 — cobertura por entidad (FastAPI):**
```
curl -s "http://localhost:8000/analisis/cobertura?entidad=CHICHIMENE"
```
Esperado (en < 60s): `entidad:"CHICHIMENE"`, `hojas_con_entidad` > 0; cada hoja con `reportes_entidad`.
Valores de referencia (presencia): `BDP_datos_dia`≈**60**, `BDP_datos_mes`≈**4**, `TD_datos_dia`/`DATOS_MES`/
`PROGRAMA`/`Reporte Whatsapp`/`COMENTARIOS`≈**138**, `REPORTE_PRESIDENT`≈**58**.

**V3 — proxy Flask:**
```
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8020/api/analisis/cobertura
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8020/api/analisis/cobertura?entidad=CHICHIMENE"
```
Esperado: `200` en ambos.

**V4 — Frontend (navegador):**
1. `http://localhost:8020` → "Análisis avanzado…" → pestaña **Análisis** → botón **Cobertura del reporte**.
2. Se ve **una sola tabla** (28 hojas por categoría) con "**N reportes**" por hoja — **sin gráficos de barras**.
3. Escribir `CHICHIMENE` en "Filtrar por entidad" + Enter → spinner ~10s → la tabla cambia a
   "**N de M rep.**" por hoja; hojas sin la entidad quedan atenuadas; encabezado "aparece en X de 28 hojas".
4. Botón **"Ver todas"** → vuelve a la cobertura total.

**V5 — No regresión:** pestañas Ingesta / Control y módulos Catálogo / Densidad siguen funcionando.

## 9. Fuera de alcance (explícito)

- Búsqueda de presencia dentro de `fact_tabla_hoja` (62M) — se usa `bronze.hoja_landing` en su lugar.
- Índice nuevo (`pg_trgm`/GIN) para bajar los ~10s a <1s — **mejora futura** (requiere migración de BD → plan aparte).
- Match exacto por palabra (hoy `ILIKE` substring, puede sobre-emparejar p.ej. "CHICHIMENE" ↔ "CHICHIMENE SW").
- Datalist de autocompletado de entidades en el input (opcional; hoy es texto libre).
- Cualquier gráfico de barras (se eliminan por decisión del usuario).
- **Limpieza de `/analisis/huella` (F3):** tras quitar las barras, el endpoint `/analisis/huella` (y su proxy
  Flask + campo `entidades_por_nivel`) quedan **huérfanos** (nadie los llama). Se DEJAN tal cual (inofensivos);
  su eliminación es limpieza opcional para otro momento — NO se toca en este plan para no romper por error.
- Métrica "filas": se elimina de la vista por sobre-contar (F1). Si en el futuro se quiere el conteo real de
  filas por tabla, debe salir de `COUNT(*)` sobre la tabla destino (dedup), no de `ingesta_log`.

## 10. Notas para actualizar la documentación al terminar

- `INGESTA/Rep_Prod/CLAUDE.md` §12: fila de bitácora (cobertura filtrable por entidad = presencia; fuentes
  `ingesta_log` + `bronze.hoja_landing` + facts ECP; sin índice nuevo).
- `CLAUDE.md` (raíz) §10 y `DISENO_CAPA_CONVERSACIONAL.md`: anotar el módulo Cobertura (presencia por hoja)
  y el principio de que la presencia se resuelve por landing (no por los 62M).
