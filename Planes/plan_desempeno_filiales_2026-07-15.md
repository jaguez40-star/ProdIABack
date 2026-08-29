# Plan ejecutable — Panel "Desempeño Filiales" (Ejecutivo + Desempeño) en el rail de Consulta

> **Tablas: entrada 1 fuente (`core.fact_produccion_diaria`) → salida 3 endpoints filiales + 1 tarjeta de rail.**
> Modo Executor: aplicar al pie de la letra. NO improvisar SQL ni nombres de columna.
> **v2 AUDITADO** (2026-07-15): SQL ejecutado contra la BD dev; 6 hallazgos corregidos (ver §0). El camino ECP
> queda **byte-idéntico** (todas las ramas nuevas son `return` temprano + kwargs con default = strings ECP exactos).

---

## 0. Hallazgos de auditoría incorporados (por qué este plan es v2)

Se ejecutó el SQL propuesto contra `daily_report_prod`. Resultado real (mayo 2026, ventana MTD 17/31):
**CRUDO 101.8%, GAS 108.1%, BLANCOS 105.7% del programa** — las 3 filiales están POR ENCIMA del programa.
Eso rompió supuestos de la lógica ECP reusada. Correcciones:

- **F1 (crítico):** `_ejec_fallback` asume que el "peor" producto está rezagado; con todo >100% escribiría "El mayor
  rezago está en crudo (101.8%)" (falso). → Se parametriza (`meta_nombre`/`frase_dep`/`frase_prio`, defaults =
  strings ECP exactos) y se añade un guard para el caso "todos ≥100%".
- **F2 (alto):** `gap_por_producto` solo con pct<100 → con esta data queda vacío → Sustento sin gráficos. → Se
  **desacopla**: la respuesta lleva los 3 productos (para los gráficos), pero brief/flags usan solo `gap_lag` (pct<100).
- **F3 (medio):** `__cnDesempInsight` cae a `__cnLastIntent` con `entidad=null` → en filiales metería una entidad ECP
  en la URL/caché. → En modo filiales se fuerza global.
- **F4 (bajo):** la rama `return` en `/ejecutivo` va DESPUÉS del docstring (no antes).
- **F5 (bajo/UX):** el botón "Volver al panorama" se oculta en modo filiales.
- **F6 (cosmético, sin acción):** con 3 filiales la concentración es siempre ~100% (top3=todas). Honesto; se documenta.

---

## 1. Contexto

`ProdIA` (Flask :8020) monta un **MultiTab Shell** en la pestaña **Consulta**. En el visor derecho, un **rail de
tarjetas** selecciona análisis. La tarjeta **"Desempeño del mes"** ya renderiza un panel **apilado**: arriba un
**brief ejecutivo (IA)** de 4 secciones + "Sustento por campo" (SVG), y abajo los módulos de **desempeño** (curva
de crudo con valle anotado, tabla de eventos, "Real vs Presupuesto", curva diaria). Se sirve desde el backend
**FastAPI de INGESTA** (:8000) con 3 endpoints sobre datos **ECP**, proxied por Flask en `routes/api.py`
(`/api/analisis/*`). Frontend en `static/js/multitab_shell.js`.

**Objetivo:** habilitar la **2ª tarjeta del rail** como **"Desempeño Filiales"**, que renderiza el mismo panel pero
sobre **Filiales** (Hocol/America/Permian). Los datos viven en `core.fact_produccion_diaria` (diario, REAL +
PROGRAMA por empresa×producto) — estructura **distinta** a ECP → se agrega `?segmento=filiales` a los 3 endpoints
con una rama nueva (ECP queda intacto).

### 1.1 Realidad de datos (verificada en BD dev — NO cambiar los supuestos)

| Aspecto | Valor verificado |
|---|---|
| Fuente diaria | `core.fact_produccion_diaria(empresa_id, producto_id, tipo_id, fecha, valor_produccion)` |
| `tipo_id` | **1 = Real**, **2 = Programa** (`core.dim_tipo_registro`) |
| Empresas (`core.dim_empresa`) | **3**: (1) Hocol, (2) America, (3) Permian |
| Productos (`core.dim_tipo_producto.nombre`) | CRUDO, GAS, BLANCOS |
| Rango | 2025-11-30 → 2026-05-31. Mayo 2026: **17 días** de REAL, **31** de PROGRAMA |
| Cumplimiento MTD verificado | CRUDO 101.8%, GAS 108.1%, BLANCOS 105.7% (**todos ≥100%** — ver §0) |
| Reconciliación CRUDO | gap_kpi = gap_campos = 21.250 → **desfase 0.0%** ✅ |
| **PPTO de filiales** | **NO existe** (`fact_plan_mensual.ppto_kbd` = NULL). Meta = **PROGRAMA** |
| Comentarios/eventos de filiales | **0** → la tabla de eventos va vacía (el frontend ya la oculta) |

### 1.2 🔑 Regla de comparación (obligatoria)

REAL tiene 17 días; PROGRAMA tiene 31. **Sumar ingenuamente da 57% (FALSO).** La comparación debe ser
**misma-ventana**: REAL y PROGRAMA agregados **solo sobre los días con REAL** (CTE `rd`). Verificado:
SUM ingenuo 56.9% ❌ vs misma-ventana 101.8% ✅.

### 1.3 Decisiones cerradas

- **D1 — Meta = PROGRAMA.** Etiquetas "vs Programa" / "% del programa".
- **D2 — Valle sin tabla de eventos** (curva sí; tabla vacía se oculta).
- **D3 — Descomposición por FILIAL** (no por campo).
- **D4 — v1 = vista fija de las 3 filiales** (NO entity-aware).
- **D5 — Sin LLM** (composer determinista, `generado_por="fallback"`).
- **D6 (F2) — Gráficos de Sustento SIEMPRE visibles** (los 3 productos), brief/flags solo con lo rezagado.

---

## 2. Objetivo (criterio de "hecho")

1. La **2ª tarjeta** dice **"Desempeño Filiales · Activo"**; al pulsarla monta el panel apilado con datos de las 3 filiales.
2. Los 3 endpoints aceptan `?segmento=filiales` y devuelven la **misma forma de JSON** que ECP.
3. % de cumplimiento **realista** (~100%, misma-ventana), NO 57%.
4. El brief **NO** afirma "rezago" cuando el producto está ≥100% (F1). Los **gráficos de Sustento SÍ se pintan** (F2).
5. Etiquetas **"vs Programa" / "por filial"**.
6. El panel **ECP existente NO cambia** (no-regresión — verificado por V2).

---

## 3. Prerequisitos

- FastAPI INGESTA en :8000 — `cd c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend && uv run uvicorn app.main:app --port 8000 --reload`
- Flask en :8020 (`run.bat` o `python app.py` desde la raíz).
- Postgres dev con `daily_report_prod` poblada.
- `node` en PATH (chequeo JS).

---

## 4. Inventario de archivos a tocar (4)

| # | Archivo (ruta absoluta) | Cambio |
|---|---|---|
| A | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | parametrizar `_ejec_fallback` (F1) + bloque filiales + ramas `segmento` (F4) |
| B | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\routes\api.py` | reenviar `segmento` en 3 proxies |
| C | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\static\js\multitab_shell.js` | tarjeta rail + segmento + relabels (F3/F5) |
| D | `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\templates\main.html` | cache-buster `?v=` |

No se toca CSS, DDL, ETL ni grano.

---

## 5. Especificación

### 5.A — Backend `analisis/api.py`

#### A0. Parametrizar `_ejec_fallback` (F1) — defaults = strings ECP EXACTOS

**A0.1 — firma.** BUSCAR:
```python
def _ejec_fallback(periodo, titular, gap_por_producto, valle, eventos, eventos_extra, pace, flags):
    """Composer determinista: arma las 4 secciones desde las cifras ya reconciliadas.
    ES el entregable por defecto (H4) -- debe quedar completo y legible SIN el LLM."""
```
REEMPLAZAR por:
```python
def _ejec_fallback(periodo, titular, gap_por_producto, valle, eventos, eventos_extra, pace, flags,
                   meta_nombre="presupuesto",
                   frase_dep="riesgo de dependencia de pocos campos",
                   frase_prio="los campos que más arrastran"):
    """Composer determinista: arma las 4 secciones desde las cifras ya reconciliadas.
    ES el entregable por defecto (H4) -- debe quedar completo y legible SIN el LLM.
    meta_nombre/frase_dep/frase_prio: por defecto = redacción ECP EXACTA; el segmento filiales
    los pasa distintos (programa / filiales). El guard 'peor >= 100' evita hablar de 'rezago'
    cuando todos los productos cerraron por encima de la meta (caso real de filiales)."""
```

**A0.2 — insight de cierre + peor (guard ≥100).** BUSCAR:
```python
    if partes:
        insights.append(f"Cierre de {periodo}: " + ", ".join(partes) + " del presupuesto.")
    peor = min([t for t in titular if t["valor_pct"] is not None], key=lambda t: t["valor_pct"], default=None)
    if peor:
        insights.append(f"El mayor rezago está en {peor['producto'].lower()} ({peor['valor_pct']}% del presupuesto).")
```
REEMPLAZAR por:
```python
    if partes:
        insights.append(f"Cierre de {periodo}: " + ", ".join(partes) + f" del {meta_nombre}.")
    peor = min([t for t in titular if t["valor_pct"] is not None], key=lambda t: t["valor_pct"], default=None)
    if peor:
        if peor["valor_pct"] >= 100:
            insights.append(f"Todos los productos cerraron por encima del {meta_nombre}; el más ajustado es "
                            f"{peor['producto'].lower()} ({peor['valor_pct']}%).")
        else:
            insights.append(f"El mayor rezago está en {peor['producto'].lower()} ({peor['valor_pct']}% del {meta_nombre}).")
```

**A0.3 — zona crítica.** BUSCAR:
```python
            puntos_atencion.append(f"{f['producto']} está en zona crítica: {f['pct']}% del presupuesto (<60%).")
```
REEMPLAZAR por:
```python
            puntos_atencion.append(f"{f['producto']} está en zona crítica: {f['pct']}% del {meta_nombre} (<60%).")
```

**A0.4 — concentración (frase_dep).** BUSCAR:
```python
            puntos_atencion.append(f"El faltante de {f['producto'].lower()} está muy concentrado (~{f['concentracion_pct']}% "
                                   f"en {', '.join(f['campos'])}) — riesgo de dependencia de pocos campos.")
```
REEMPLAZAR por:
```python
            puntos_atencion.append(f"El faltante de {f['producto'].lower()} está muy concentrado (~{f['concentracion_pct']}% "
                                   f"en {', '.join(f['campos'])}) — {frase_dep}.")
```

**A0.5 — decisiones (frase_prio).** BUSCAR:
```python
            decisiones.append(f"Priorizar diagnóstico operativo en {campos} (los campos que más arrastran el faltante de {p.lower()}).")
```
REEMPLAZAR por:
```python
            decisiones.append(f"Priorizar diagnóstico operativo en {campos} ({frase_prio} el faltante de {p.lower()}).")
```

> Con `segmento="ecp"` los defaults reproducen los strings originales **carácter por carácter** (peor de ECP =
> BLANCOS 58.5% <100 → rama `else`), por lo que la salida ECP es idéntica. Verificar con V2.

#### A1. Bloque de funciones filiales — INSERTAR al FINAL del archivo (nivel de módulo)

```python
# ============================================================================
# SEGMENTO FILIALES — Desempeño/Ejecutivo sobre core.fact_produccion_diaria.
# Meta = PROGRAMA (tipo_id=2); REAL = tipo_id=1. Comparación MISMA-VENTANA (solo días con REAL, CTE rd).
# Descomposición por EMPRESA (Hocol/America/Permian). Sin PPTO, sin eventos (los comentarios son ECP).
# F2: gap_por_producto (respuesta/gráficos) = LOS 3 productos; el brief/flags usan gap_lag (pct<100).
# Reusa helpers compartidos: _estado, _detectar_valle, _flags_ejecutivo, _ejec_fallback, MESES_ES.
# v1: vista fija de las 3 filiales (NO entity-aware), sin LLM (composer determinista).
# ============================================================================
_FIL_SCOPE = "Filiales (Hocol · America · Permian)"

def _fil_intermedios(c):
    """Intermedios comunes de filiales. Devuelve None si no hay REAL diario.
    Forma idéntica a la que usan los composers ECP para poder reutilizarlos."""
    import calendar
    maxd = c.execute(sa.text(
        "SELECT MAX(fecha) FROM core.fact_produccion_diaria WHERE tipo_id=1")).scalar()
    if maxd is None:
        return None
    y, mo = maxd.year, maxd.month
    dim = calendar.monthrange(y, mo)[1]
    ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"
    P = {"ini": ini, "fin": fin}
    RD = ("WITH rd AS (SELECT DISTINCT fecha FROM core.fact_produccion_diaria "
          "WHERE tipo_id=1 AND fecha BETWEEN :ini AND :fin) ")

    ndias = c.execute(sa.text(
        "SELECT COUNT(DISTINCT fecha) FROM core.fact_produccion_diaria "
        "WHERE tipo_id=1 AND fecha BETWEEN :ini AND :fin"), P).scalar() or 0

    # KPI REAL vs PROGRAMA por producto (MISMA-VENTANA)
    kpi = {}
    for r in c.execute(sa.text(RD + """
        SELECT tp.nombre,
          SUM(CASE WHEN fp.tipo_id=1 THEN fp.valor_produccion END) real_mtd,
          SUM(CASE WHEN fp.tipo_id=2 THEN fp.valor_produccion END) prog_mtd
        FROM core.fact_produccion_diaria fp
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
        WHERE fp.fecha IN (SELECT fecha FROM rd)
        GROUP BY 1"""), P):
        kpi[r[0]] = {"REAL": float(r[1] or 0), "PROG": float(r[2] or 0)}

    _et = {"ok": "Alineado", "warn": "Rezagado", "alert": "Foco", "": "—"}
    titular = []
    for p in ["CRUDO", "GAS", "BLANCOS"]:
        real = kpi.get(p, {}).get("REAL", 0.0); prog = kpi.get(p, {}).get("PROG", 0.0)
        pct = round(real / prog * 100.0, 1) if prog else None
        est = _estado(pct)
        # 'ppto' guarda la META (=PROGRAMA misma-ventana) para reutilizar el frontend sin cambiar claves
        titular.append({"producto": p, "real": real, "ppto": prog, "valor_pct": pct,
                        "estado": est, "texto": _et.get(est, "—")})

    # Curva diaria REAL por producto
    curva = {}
    for f, prod, vol in c.execute(sa.text("""
            SELECT fp.fecha, tp.nombre prod, SUM(fp.valor_produccion) vol
            FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            WHERE fp.tipo_id=1 AND fp.fecha BETWEEN :ini AND :fin
            GROUP BY 1, 2 ORDER BY 1"""), P).all():
        curva.setdefault(f.isoformat(), {})[prod] = float(vol or 0)
    curva_fechas = sorted(curva.keys())
    productos = ["CRUDO", "GAS", "BLANCOS"]
    series = {p: [curva.get(f, {}).get(p, 0.0) for f in curva_fechas] for p in productos}

    # Serie crudo diaria -> valle
    serie = [(f, curva.get(f, {}).get("CRUDO", 0.0)) for f in curva_fechas]
    valle = _detectar_valle(serie)
    anotaciones = None
    if valle:
        anotaciones = {
            "banda": {"desde": valle["desde"], "hasta": valle["hasta"], "label": "valle"},
            "punto": {"fecha": valle["min_fecha"], "valor": valle["min_valor"],
                      "label": f"mín · {valle['min_valor']/1e6:.2f}M"},
        }

    # Descomposición del gap por EMPRESA (misma-ventana). F2: se calcula para TODOS los productos.
    def _gap_empresa(producto, gap_kpi):
        pe = dict(P); pe["prod"] = producto
        grows = c.execute(sa.text(RD + """
            SELECT e.nombre AS campo,
                   SUM(CASE WHEN fp.tipo_id=1 THEN fp.valor_produccion ELSE 0 END) AS vreal,
                   SUM(CASE WHEN fp.tipo_id=2 THEN fp.valor_produccion ELSE 0 END) AS vprog
            FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            JOIN core.dim_empresa e ON e.empresa_id = fp.empresa_id
            WHERE tp.nombre = :prod AND fp.fecha IN (SELECT fecha FROM rd)
            GROUP BY 1"""), pe).all()
        difs = [((r[0] or "").strip(), float(r[1] or 0) - float(r[2] or 0),
                 float(r[1] or 0), float(r[2] or 0)) for r in grows if (r[1] or r[2])]
        gap_total = sum(d[1] for d in difs)
        detr = sorted([d for d in difs if d[1] < 0], key=lambda x: x[1])[:3]
        comp = sorted([d for d in difs if d[1] > 0], key=lambda x: -x[1])[:2]
        top3 = sum(d[1] for d in detr)
        gap_detr_total = sum(d[1] for d in difs if d[1] < 0)
        concentracion_pct = round(abs(top3) / abs(gap_detr_total) * 100, 1) if gap_detr_total else None
        desfase_pct = round(abs(gap_total - gap_kpi) / abs(gap_kpi) * 100, 1) if gap_kpi else None
        return {
            "producto": producto, "gap_kpi": round(gap_kpi), "gap_total_campos": round(gap_total),
            "reconciliado": desfase_pct is not None and desfase_pct <= 2.0,
            "desfase_pct": desfase_pct, "concentracion_pct": concentracion_pct,
            "detractores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])} for d in detr],
            "compensadores": [{"campo": d[0], "gap": round(d[1]), "real": round(d[2]), "meta": round(d[3])} for d in comp],
        }

    gap_full = {}
    for t in titular:
        if t["valor_pct"] is not None:
            gap_full[t["producto"]] = _gap_empresa(t["producto"], t["real"] - t["ppto"])
    # gap_lag = solo productos por debajo de la meta (para brief + flags honestos)
    gap_lag = {p: g for p, g in gap_full.items()
               if next(t["valor_pct"] for t in titular if t["producto"] == p) < 100}

    # Pace de crudo: MTD vs PROGRAMA del MES COMPLETO (target de cierre)
    pace = None
    if serie:
        mtd = sum(v for _, v in serie); rest = dim - ndias
        prog_full = c.execute(sa.text("""
            SELECT SUM(fp.valor_produccion) FROM core.fact_produccion_diaria fp
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = fp.producto_id
            WHERE tp.nombre='CRUDO' AND fp.tipo_id=2 AND fp.fecha BETWEEN :ini AND :fin"""), P).scalar()
        prog_full = float(prog_full or 0)
        if rest > 0 and prog_full and ndias:
            prom = mtd / ndias
            req = (prog_full - mtd) / rest
            pace = {"mtd": round(mtd), "dias": ndias, "restantes": rest,
                    "promedio_dia": round(prom), "requerido_dia": round(req),
                    "delta_pct": (round((req / prom - 1) * 100, 1) if prom else None)}

    flags = _flags_ejecutivo(titular, gap_lag, valle, pace, serie[-1][0] if serie else None)
    return {
        "y": y, "mo": mo, "dim": dim, "ndias": ndias,
        "periodo": f"{MESES_ES[mo]} {y}", "corte": f"{ndias}/{dim}",
        "titular": titular, "kpi": kpi, "curva_fechas": curva_fechas, "series": series,
        "curva_crudo": {"fechas": [f for f, _ in serie], "valores": [v for _, v in serie]},
        "valle": valle, "anotaciones": anotaciones,
        "gap_por_producto": gap_full, "gap_lag": gap_lag, "pace": pace, "flags": flags,
    }


def _desempeno_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
    if I is None:
        return {"entidad": None, "encontrada": True, "sin_datos": True}
    sin_cierre = not any(I["kpi"].get(p) for p in ["CRUDO", "GAS", "BLANCOS"])
    por_producto = [{"producto": t["producto"], "real": t["real"], "ppto": t["ppto"],
                     "cumplimiento": t["valor_pct"]} for t in I["titular"]]
    return {
        "entidad": None, "encontrada": True, "aplica_diario": True, "sin_cierre": sin_cierre,
        "mes": {"anio": I["y"], "mes": I["mo"], "nombre": MESES_ES[I["mo"]],
                "dias_con_data": I["ndias"], "dias_del_mes": I["dim"], "completo": I["ndias"] >= I["dim"]},
        "por_producto": por_producto,
        "curva": {"fechas": I["curva_fechas"], "series": I["series"]},
    }


def _desempeno_insight_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
    if I is None:
        return {"entidad": None, "encontrada": True, "sin_datos": True}
    peor = min([t for t in I["titular"] if t["valor_pct"] is not None],
               key=lambda t: t["valor_pct"], default=None)
    gpeor = I["gap_por_producto"].get((peor or {}).get("producto"), {}) or {}
    return {
        "entidad": None, "encontrada": True,
        "meta": {"scope": _FIL_SCOPE, "periodo": I["periodo"], "corte": I["corte"], "generado_por": "fallback"},
        "titular": I["titular"], "curva_crudo": I["curva_crudo"], "anotaciones": I["anotaciones"],
        "eventos": [], "eventos_extra": {"campos": 0, "pozos_aprox": 0, "fecha": ""},
        "gap": {"producto": (peor or {}).get("producto"),
                "detractores": gpeor.get("detractores", []), "compensadores": gpeor.get("compensadores", [])},
        "pace_crudo": I["pace"], "lectura_ejecutiva": "", "accion_sugerida": [],
    }


def _ejecutivo_filiales():
    eng = get_engine()
    with eng.connect() as c:
        I = _fil_intermedios(c)
    if I is None:
        return {"entidad": None, "encontrada": True, "sin_datos": True}
    # brief/flags con gap_lag (honesto); gráficos con gap_por_producto (los 3 productos) — F2
    secciones = _ejec_fallback(I["periodo"], I["titular"], I["gap_lag"], I["valle"],
                               [], {"campos": 0, "pozos_aprox": 0}, I["pace"], I["flags"],
                               meta_nombre="programa",
                               frase_dep="riesgo de concentración en pocas filiales",
                               frase_prio="las filiales que más arrastran")
    return {
        "entidad": None, "encontrada": True,
        "meta": {"scope": _FIL_SCOPE, "periodo": I["periodo"], "corte": I["corte"],
                 "generado_por": "fallback", "llm_diag": {"status": "off"}},
        "titular": I["titular"], "gap_por_producto": I["gap_por_producto"],
        "valle": I["valle"], "eventos": [], "eventos_extra": {"campos": 0, "pozos_aprox": 0},
        "pace_crudo": I["pace"], "flags": I["flags"], "secciones": secciones,
    }
```

#### A2. Ramas `segmento` en los 3 endpoints existentes

**`/desempeno`** (no tiene docstring) — BUSCAR:
```python
@router.get("/desempeno")
def desempeno(entidad: str | None = Query(None)):
    import calendar
```
REEMPLAZAR por:
```python
@router.get("/desempeno")
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp")):
    if segmento == "filiales":
        return _desempeno_filiales()
    import calendar
```

**`/desempeno_insight`** (no tiene docstring) — BUSCAR:
```python
@router.get("/desempeno_insight")
def desempeno_insight(entidad: str | None = Query(None)):
    import calendar
    eng = get_engine()
```
REEMPLAZAR por:
```python
@router.get("/desempeno_insight")
def desempeno_insight(entidad: str | None = Query(None), segmento: str = Query("ecp")):
    if segmento == "filiales":
        return _desempeno_insight_filiales()
    import calendar
    eng = get_engine()
```

**`/ejecutivo`** (SÍ tiene docstring — la rama va DESPUÉS, F4) — BUSCAR:
```python
@router.get("/ejecutivo")
def ejecutivo(entidad: str | None = Query(None)):
    """Análisis Ejecutivo (IA) multi-sección: insights / oportunidades / puntos_atencion / decisiones.
    Reusa el patrón de /desempeno_insight (resolución de entidad, mes objetivo, KPIs REAL/PPTO,
    _detectar_valle, _eventos_valle, pace_crudo, _llm_insight) y agrega el gap RECONCILIADO por
    producto rezagado + flags Python. El composer determinista (_ejec_fallback) es el default
    entregable; el LLM (Gemma) es pulido opcional (timeout=120s, solo on-demand)."""
    import calendar
```
REEMPLAZAR por:
```python
@router.get("/ejecutivo")
def ejecutivo(entidad: str | None = Query(None), segmento: str = Query("ecp")):
    """Análisis Ejecutivo (IA) multi-sección: insights / oportunidades / puntos_atencion / decisiones.
    Reusa el patrón de /desempeno_insight (resolución de entidad, mes objetivo, KPIs REAL/PPTO,
    _detectar_valle, _eventos_valle, pace_crudo, _llm_insight) y agrega el gap RECONCILIADO por
    producto rezagado + flags Python. El composer determinista (_ejec_fallback) es el default
    entregable; el LLM (Gemma) es pulido opcional (timeout=120s, solo on-demand).
    segmento='filiales' → delega en _ejecutivo_filiales (fuente/reglas distintas)."""
    if segmento == "filiales":
        return _ejecutivo_filiales()
    import calendar
```

Las funciones `_*_filiales` están al final del módulo (A1); Python las resuelve por nombre en tiempo de llamada.

---

### 5.B — Proxies Flask `routes/api.py` (reenviar `segmento`)

En **cada** proxy, tras agregar `entidad` a `params`, añadir el reenvío de `segmento`.

**`/analisis/desempeno`** — BUSCAR:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent   # H3: idiom del repo — solo pasar entidad si viene (evita ""→no encontrada)
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno", params=params, timeout=45)
```
REEMPLAZAR por:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent   # H3: idiom del repo — solo pasar entidad si viene (evita ""→no encontrada)
        seg = request.args.get("segmento")
        if seg:
            params["segmento"] = seg
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno", params=params, timeout=45)
```

**`/analisis/desempeno_insight`** — BUSCAR:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno_insight", params=params, timeout=90)
```
REEMPLAZAR por:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        seg = request.args.get("segmento")
        if seg:
            params["segmento"] = seg
        resp = requests.get(f"{INGESTA_API_URL}/analisis/desempeno_insight", params=params, timeout=90)
```

**`/analisis/ejecutivo`** — BUSCAR:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        resp = requests.get(f"{INGESTA_API_URL}/analisis/ejecutivo", params=params, timeout=200)
```
REEMPLAZAR por:
```python
        ent = request.args.get("entidad")
        if ent:
            params["entidad"] = ent
        seg = request.args.get("segmento")
        if seg:
            params["segmento"] = seg
        resp = requests.get(f"{INGESTA_API_URL}/analisis/ejecutivo", params=params, timeout=200)
```

---

### 5.C — Frontend `static/js/multitab_shell.js`

#### C1. Tarjeta de rail (2ª posición). BUSCAR:
```javascript
    { key: "desempeno", titulo: "Desempeño del mes", estado: "activo",
      svg: '<svg viewBox="0 0 80 46" preserveAspectRatio="none"><polyline points="4,34 16,22 28,28 40,14 52,24 64,10 76,18" fill="none" stroke="#1f6b4a" stroke-width="2.5"/></svg>' },
    { key: "ebitda", titulo: "Robustez · EBITDA", estado: "prox",
```
REEMPLAZAR por:
```javascript
    { key: "desempeno", titulo: "Desempeño del mes", estado: "activo",
      svg: '<svg viewBox="0 0 80 46" preserveAspectRatio="none"><polyline points="4,34 16,22 28,28 40,14 52,24 64,10 76,18" fill="none" stroke="#1f6b4a" stroke-width="2.5"/></svg>' },
    { key: "filiales", titulo: "Desempeño Filiales", estado: "activo",
      svg: '<svg viewBox="0 0 80 46"><g fill="#1f6b4a"><rect x="6" y="20" width="7" height="20"/><rect x="15" y="12" width="7" height="28"/></g><g fill="#8fbf7f"><rect x="34" y="26" width="7" height="14"/><rect x="43" y="18" width="7" height="22"/></g><g fill="#1f6b4a"><rect x="62" y="16" width="7" height="24"/><rect x="71" y="24" width="6" height="16"/></g></svg>' },
    { key: "ebitda", titulo: "Robustez · EBITDA", estado: "prox",
```

#### C2. Variables de segmento + helpers. BUSCAR:
```javascript
  var __cnEjecData = null;     // payload actual, para el selector de producto de los gráficos
  var __cnEjecProd = null;     // producto seleccionado en los gráficos (CRUDO/GAS/BLANCOS)
```
REEMPLAZAR por:
```javascript
  var __cnEjecData = null;     // payload actual, para el selector de producto de los gráficos
  var __cnEjecProd = null;     // producto seleccionado en los gráficos (CRUDO/GAS/BLANCOS)
  var __cnSeg = "ecp";         // "ecp" | "filiales" — segmento activo del panel apilado
  function __cnEsFil() { return __cnSeg === "filiales"; }
  // querystring común a los 3 fetches del panel (entidad + segmento). En filiales v1 NUNCA hay entidad.
  function __cnSegQS(entidad) {
    var qs = [];
    if (entidad && !__cnEsFil()) qs.push("entidad=" + encodeURIComponent(entidad));
    if (__cnEsFil()) qs.push("segmento=filiales");
    return qs.length ? "?" + qs.join("&") : "";
  }
```

#### C3. `__cnAnalisisTab` — rama filiales. BUSCAR:
```javascript
    if (key === "desempeno") {
      var ent = __cnLastIntent ? (__cnLastIntent.valor || __cnLastIntent.entidad || null) : null;
      window.__cnAnalizar(ent);
    } else {
```
REEMPLAZAR por:
```javascript
    if (key === "desempeno") {
      var ent = __cnLastIntent ? (__cnLastIntent.valor || __cnLastIntent.entidad || null) : null;
      window.__cnAnalizar(ent, "ecp");
    } else if (key === "filiales") {
      window.__cnAnalizar(null, "filiales");   // v1: vista fija de las 3 filiales (global)
    } else {
```

#### C4. `__cnAnalizar` — segmento + título + back (F5) + fetch/caché por segmento.
**C4.1** — BUSCAR:
```javascript
  window.__cnAnalizar = function (entidad) {
    var a = __cnViewerArea(); if (!a) return;
    var esGlobal = !entidad;   // sin entidad → desempeño GLOBAL (toda la producción ECP), p. ej. al cargar
    var titulo = esGlobal
      ? '<i class="bi bi-bar-chart-line-fill"></i> Desempeño del mes · Global (toda la producción ECP)'
      : '<i class="bi bi-bar-chart-line-fill"></i> Desempeño de ' + esc(entidad);
    // "Volver al panorama" solo si hay una entidad resuelta a la cual volver (no en el global de carga).
    var backBtn = __cnLastIntent
      ? '<button type="button" class="cn-rep__back" onclick="window.__cnVolverPanorama()">' +
        '<i class="bi bi-arrow-left"></i> Volver al panorama</button>'
      : '';
```
REEMPLAZAR por:
```javascript
  window.__cnAnalizar = function (entidad, segmento) {
    __cnSeg = (segmento === "filiales") ? "filiales" : "ecp";   // fija el segmento del panel
    var a = __cnViewerArea(); if (!a) return;
    var esGlobal = !entidad;   // sin entidad → desempeño GLOBAL, p. ej. al cargar
    var titulo = __cnEsFil()
      ? '<i class="bi bi-bar-chart-line-fill"></i> Desempeño Filiales · Hocol · America · Permian'
      : (esGlobal
        ? '<i class="bi bi-bar-chart-line-fill"></i> Desempeño del mes · Global (toda la producción ECP)'
        : '<i class="bi bi-bar-chart-line-fill"></i> Desempeño de ' + esc(entidad));
    // "Volver al panorama" solo en ECP con entidad resuelta (F5: en filiales no aplica).
    var backBtn = (!__cnEsFil() && __cnLastIntent)
      ? '<button type="button" class="cn-rep__back" onclick="window.__cnVolverPanorama()">' +
        '<i class="bi bi-arrow-left"></i> Volver al panorama</button>'
      : '';
```
**C4.2** — BUSCAR:
```javascript
    var cacheKey = entidad || "__global__";
    if (__cnDesempCache[cacheKey]) { __cnPaintDesemp(__cnDesempCache[cacheKey], entidad, esGlobal); return; }   // caché → sin refetch ni LLM
    fetch("/api/analisis/desempeno" + (esGlobal ? "" : "?entidad=" + encodeURIComponent(entidad)))
```
REEMPLAZAR por:
```javascript
    var cacheKey = __cnSeg + "|" + (entidad || "__global__");
    if (__cnDesempCache[cacheKey]) { __cnPaintDesemp(__cnDesempCache[cacheKey], entidad, esGlobal); return; }   // caché → sin refetch ni LLM
    fetch("/api/analisis/desempeno" + __cnSegQS(entidad))
```

#### C5. `__cnAnalisisEjecutivo` — fetch/caché por segmento. BUSCAR:
```javascript
    var key = entidad || "__global__";
    if (__cnEjecCache[key]) { __cnPaintEjec(__cnEjecCache[key]); return; }   // caché por entidad -> no re-llama al LLM
    fetch("/api/analisis/ejecutivo" + (esGlobal ? "" : "?entidad=" + encodeURIComponent(entidad)))
```
REEMPLAZAR por:
```javascript
    var key = __cnSeg + "|" + (entidad || "__global__");
    if (__cnEjecCache[key]) { __cnPaintEjec(__cnEjecCache[key]); return; }   // caché por segmento+entidad
    fetch("/api/analisis/ejecutivo" + __cnSegQS(entidad))
```

#### C6. `__cnDesempInsight` — global en filiales (F3) + fetch/caché por segmento.
**C6.1** — BUSCAR:
```javascript
    var ent = entidad || (__cnLastIntent && (__cnLastIntent.valor || __cnLastIntent.entidad)) || "";
    var cacheKey = ent || "__global__";
    if (__cnInsCache[cacheKey]) { __cnPaintIns(host, __cnInsCache[cacheKey]); return; }   // caché → NO re-llamar al LLM
```
REEMPLAZAR por:
```javascript
    var ent = __cnEsFil() ? "" : (entidad || (__cnLastIntent && (__cnLastIntent.valor || __cnLastIntent.entidad)) || "");
    var cacheKey = __cnSeg + "|" + (ent || "__global__");
    if (__cnInsCache[cacheKey]) { __cnPaintIns(host, __cnInsCache[cacheKey]); return; }   // caché → NO re-llamar al LLM
```
**C6.2** — BUSCAR:
```javascript
    fetch("/api/analisis/desempeno_insight" + (ent ? "?entidad=" + encodeURIComponent(ent) : ""))
```
REEMPLAZAR por:
```javascript
    fetch("/api/analisis/desempeno_insight" + __cnSegQS(ent))
```

#### C7. Relabels condicionales (Presupuesto→Programa, campo→filial)

**C7a** — `__cnRenderDesemp` "del presupuesto". BUSCAR:
```javascript
        '  <div class="cn-desemp__kpi-cumpl ' + sem + '">' + pct + ' <span>del presupuesto</span></div>' +
```
REEMPLAZAR por:
```javascript
        '  <div class="cn-desemp__kpi-cumpl ' + sem + '">' + pct + ' <span>del ' + (__cnEsFil() ? "programa" : "presupuesto") + '</span></div>' +
```

**C7b** — `__cnRenderDesemp` "Real vs Presupuesto". BUSCAR:
```javascript
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs Presupuesto</span></div>' +
```
REEMPLAZAR por:
```javascript
      '    <div class="cn-desemp__card"><div class="cn-desemp__card-hd"><span><i class="bi bi-clipboard-check"></i> Real vs ' + (__cnEsFil() ? "Programa" : "Presupuesto") + '</span></div>' +
```

**C7c** — `__cnEjecChartsHtml` "Sustento por campo". BUSCAR:
```javascript
    return '<div class="cn-ejec__charts-hd"><i class="bi bi-bar-chart-line"></i> Sustento por campo</div>' +
```
REEMPLAZAR por:
```javascript
    return '<div class="cn-ejec__charts-hd"><i class="bi bi-bar-chart-line"></i> Sustento por ' + (__cnEsFil() ? "filial" : "campo") + '</div>' +
```

**C7d** — `__cnEjecProdHtml` subtítulos. BUSCAR:
```javascript
      '<div class="cn-ejec__ch"><div class="cn-ejec__ch-t">Cuánto le faltó a cada campo para su meta</div>' +
      '<svg class="cn-ejec__svg" id="ejc-b-' + p + '" role="img"></svg></div>' +
      '<div class="cn-ejec__ch"><div class="cn-ejec__ch-t">Balance por campo: quién arrastra y quién amortigua</div>' +
```
REEMPLAZAR por:
```javascript
      '<div class="cn-ejec__ch"><div class="cn-ejec__ch-t">Cuánto le faltó a cada ' + (__cnEsFil() ? "filial" : "campo") + ' para su meta</div>' +
      '<svg class="cn-ejec__svg" id="ejc-b-' + p + '" role="img"></svg></div>' +
      '<div class="cn-ejec__ch"><div class="cn-ejec__ch-t">Balance por ' + (__cnEsFil() ? "filial" : "campo") + ': quién arrastra y quién amortigua</div>' +
```

**C7e** — `__cnRenderEjecutivo` nota de reconciliación. BUSCAR:
```javascript
        noteReconc += '<div class="cn-ejec__note"><i class="bi bi-info-circle"></i> La descomposición por campo de ' +
```
REEMPLAZAR por:
```javascript
        noteReconc += '<div class="cn-ejec__note"><i class="bi bi-info-circle"></i> La descomposición por ' + (__cnEsFil() ? "filial" : "campo") + ' de ' +
```

---

### 5.D — Cache-buster `templates/main.html`

REEMPLAZAR `?v=20260715a` por `?v=20260715b` en **ambas** líneas (link de `colapsable.css` y script de `multitab_shell.js`).

---

## 6. Orden de ejecución

1. **A0** (parametrizar `_ejec_fallback`) → **A1** (bloque filiales al final) → **A2** (ramas `segmento`).
2. **B** (3 proxies Flask).
3. **C1..C7** (frontend).
4. **D** (cache-buster).
5. Reiniciar backends si no están en `--reload`/debug.

---

## 7. Reglas no negociables

1. **NO tocar el camino ECP**: con `segmento="ecp"` (default) los 3 endpoints devuelven EXACTAMENTE lo de hoy; los
   defaults de `_ejec_fallback` reproducen los strings ECP carácter por carácter. Verificar con V2.
2. **Comparación misma-ventana** (CTE `rd`) en KPIs/descomposición. (El pace SÍ usa PROGRAMA de mes completo como
   *target de cierre* — correcto solo ahí.)
3. **Meta = PROGRAMA** (`tipo_id=2`). No inventar PPTO (no existe para filiales).
4. **Columnas EXACTAS**: `fact_produccion_diaria(empresa_id, producto_id, tipo_id, fecha, valor_produccion)`,
   `dim_tipo_producto.nombre`, `dim_empresa.nombre`, `dim_tipo_registro`. Sin acentos ni alias distintos.
5. **La clave `campo`** en detractores/compensadores se conserva (el frontend la lee); su *valor* es el nombre de la empresa.
6. **F2**: la respuesta de `/ejecutivo?segmento=filiales` lleva `gap_por_producto` con LOS 3 productos; el brief/flags
   se construyen con `gap_lag` (pct<100). No confundir ambos.
7. **v1 sin LLM ni entity-aware** para filiales. No crear archivos nuevos.

---

## 8. Validaciones (comando → resultado esperado)

### V1 — Backend directo (:8000)
```bash
curl -s "http://localhost:8000/analisis/desempeno?segmento=filiales" | python -c "import sys,json;d=json.load(sys.stdin);print('mes',d['mes']['nombre'],d['mes']['dias_con_data'],'/',d['mes']['dias_del_mes']);print([(p['producto'],p['cumplimiento']) for p in d['por_producto']])"
```
**Esperado:** mes con `dias_con_data < dias_del_mes` (17/31); cumplimientos **~100–110%** (CRUDO≈101.8, GAS≈108.1, BLANCOS≈105.7). NO ~57%.

```bash
curl -s "http://localhost:8000/analisis/ejecutivo?segmento=filiales" | python -c "import sys,json;d=json.load(sys.stdin);m=d['meta'];print('scope',m['scope'],'| gen',m['generado_por']);print('gap_prods',list(d['gap_por_producto'].keys()));print('insight0',d['secciones']['insights'][0])"
```
**Esperado:** `scope Filiales (Hocol · America · Permian)`, `gen fallback`; **`gap_prods` = los 3 productos** (F2);
`insight0` empieza con "Todos los productos cerraron por encima del programa; el más ajustado es crudo (101.8%)."
(F1 — NUNCA "El mayor rezago está en crudo (101.8%)").

```bash
curl -s "http://localhost:8000/analisis/ejecutivo?segmento=filiales" | python -c "import sys,json;d=json.load(sys.stdin);g=d['gap_por_producto']['CRUDO'];print('detr',[x['campo'] for x in g['detractores']],'comp',[x['campo'] for x in g['compensadores']]);print('reconciliado',g['reconciliado'],'desfase',g['desfase_pct'])"
```
**Esperado:** `detr`/`comp` = nombres de **empresas** (p.ej. detr Hocol; comp Permian, America); `reconciliado True`, `desfase 0.0`.

### V2 — No-regresión ECP (CRÍTICO)
```bash
curl -s "http://localhost:8000/analisis/desempeno" | python -c "import sys,json;d=json.load(sys.stdin);print([(p['producto'],p['cumplimiento']) for p in d['por_producto']])"
curl -s "http://localhost:8000/analisis/ejecutivo" | python -c "import sys,json;d=json.load(sys.stdin);print('gen',d['meta']['generado_por']);print('insight0',d['secciones']['insights'][0])"
```
**Esperado:** desempeño ECP idéntico a hoy (CRUDO 94.7, GAS 87.0, BLANCOS 58.5); ejecutivo ECP `insight0` empieza
"Cierre de … del presupuesto." y el 2º insight "El mayor rezago está en blancos (58.5% del presupuesto)." (redacción
ECP intacta: la palabra es **presupuesto** y usa la rama "rezago", NO "por encima").

### V3 — Proxy Flask (:8020)
```bash
curl -s "http://localhost:8020/api/analisis/ejecutivo?segmento=filiales" | python -c "import sys,json;print(json.load(sys.stdin)['meta']['scope'])"
```
**Esperado:** `Filiales (Hocol · America · Permian)`.

### V4 — Sintaxis JS
```bash
node --check "c:/APLICACIONES/ProdIA/12112025_prodIA/12112025_prodIA/static/js/multitab_shell.js" && echo "JS OK"
```
**Esperado:** `JS OK`.

### V5 — Navegador (manual, usuario)
Login → **Consulta** → tarjeta **"Desempeño Filiales"** (2ª, badge "Activo"):
- Título "Desempeño Filiales · Hocol · America · Permian"; **sin** botón "Volver al panorama" (F5).
- Brief arriba: chips verdes (todos ≥100%); insights dice "Todos … por encima del programa" (no "rezago").
- **"Sustento por filial"** con tabs CRUDO/GAS/BLANCOS y gráficos con **Hocol/America/Permian** (F2, no vacío).
- Abajo: curva de crudo (con valle si aplica) **sin** tabla de eventos; **"Real vs Programa"**; curva diaria.
- KPIs dicen **"% del programa"**.
- La tarjeta **"Desempeño del mes"** (ECP) sigue igual (no-regresión). Sin errores en consola.

---

## 9. Fuera de alcance / limitaciones conocidas

- **Filtrar por una filial concreta** — v1 es la vista fija de las 3.
- **Prosa LLM** (Gemma) para filiales — v1 usa el composer determinista.
- **Comparación vs POP** (`pop_kbd`) — meta = PROGRAMA; POP queda para futuro.
- **F6 — concentración ~100%**: con solo 3 filiales, la concentración por diseño es ~100% (top3 = todas). Es honesto
  pero poco informativo; se acepta en v1.
- **Con la data actual el panel se ve "verde"** (las 3 filiales superan su programa): el brief es corto por diseño
  (no hay rezago real) pero los gráficos de Sustento por filial SÍ se pintan (F2). El panel se enriquece
  automáticamente los meses en que una filial quede por debajo de su programa.
- No se toca CSS, DDL, ETL ni grano.

---

## 10. Rollback

Revertir los 4 archivos (`git checkout -- <archivo>`). Todo es aditivo (rama `segmento` + kwargs con default);
sin ello el sistema queda como antes.
