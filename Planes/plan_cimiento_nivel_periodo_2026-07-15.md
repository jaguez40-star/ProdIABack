# Plan ejecutable — Cimiento **nivel + periodo aware** del panel de análisis · v1 (auditado)

> Ejecutable por un agente externo sin contexto. Rutas absolutas, código completo, decisiones cerradas.
> Cambio coordinado (backend + proxy + chat + frontend). Al terminar: Validaciones y tabla PASS/FAIL. **NO commitear.**

---

## 0. Auditoría previa (§0.2) — hallazgos

Los **3** endpoints del panel (`desempeno`, `desempeno_insight`, `ejecutivo`) usan el **mismo patrón triplicado**:
1. **Resolución por NOMBRE** (`WHERE nombre=:e OR campo=:e OR grupo1=:e OR activos=:e OR gerencia=:e OR operador=:e`) → **nivel-ciego** (unión).
2. **Periodo = `MAX(fecha)`** → **periodo-ciego** (siempre el último mes con dato).

`extraccion` extrae `periodo` como **texto libre** (sin parsear). El chat resuelve `nivel` pero **no lo pasa** al panel
(`__cnAnalizar(entidad)` manda solo el nombre). El KPI REAL vs PPTO es **MENSUAL** (`fact_produccion_mes_ecp`, una fila por mes).

### Decisiones cerradas (confirmadas por el usuario)
| ID | Decisión |
|----|----------|
| **D-C1** | **Granularidad temporal v1 = solo MES**: default (último con dato) · mes explícito («abril») · mes+año («marzo 2026») · «mes pasado». Año / semana / trimestre → **NO soportados** (caen al default con aviso honesto). |
| **D-C2** | **Resolución por NIVEL**: si el chat resolvió un nivel, el panel filtra por la **columna exacta** de ese nivel (`campo→campo`, `area→grupo1`, …), no la unión. **Cambia los números de ~45 entidades genuinas** (Chichimene: 9→2 pozos). Las redundantes (Rubiales) no cambian. |
| **D-C3** | **Compatibilidad**: sin `nivel`/`periodo` (tablero global, llamadas viejas) → comportamiento ACTUAL (unión + último mes). Todo es **aditivo**. |
| **D-C4** | **Coherencia**: la Fase 3 del chat (`ejecutar`) también pasa nivel+periodo → el número del chat y el del panel salen del mismo cálculo. |
| **D-C5** | **Frontera**: el LLM solo extrae `periodo` (texto); **Python lo parsea** (`_parse_periodo`, determinista). |

### Hallazgos de verificación adversarial (incorporados, v1.1)
| # | Sev | Hallazgo | Resolución |
|---|-----|----------|------------|
| **F-A1** | 🔴 | El bloque de `desempeno_insight` y `ejecutivo` NO es byte-idéntico: `ejecutivo` tiene el comentario `# mes objetivo … -- MISMO criterio que /desempeno_insight`. Un solo `old_string` no calzaría con `ejecutivo`. | B1.3 **dividido** en B1.3a (insight) y B1.3b (ejecutivo), con `old_string` exacto por función. |
| **F-A2** | 🟡 | La prueba directa `desempeno(entidad=…, nivel=…)` crashea: `segmento`/`periodo` quedan como objetos `Query`. | Validaciones por **HTTP** (curl); la nota "sin servidor" pasa `segmento='ecp', periodo=None` explícitos. |
| **F-A3** | 🟢 | El panorama **densidad/cobertura** no usa `__cnSegQS` → queda nivel-ciego. | **Fuera de alcance** (residual documentado, §7); follow-up. |

---

## 1. Objetivo

`GET /analisis/desempeno?entidad=CHICHIMENE&nivel=campo` → cifra del **campo** (2 pozos), no de la unión (9).
`GET /analisis/desempeno?entidad=RUBIALES&periodo=abril` → **abril**, no mayo. Sin `nivel`/`periodo` → idéntico a hoy.

---

## 2. Inventario de archivos

Raíz = `c:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`.

| # | Archivo | Acción |
|---|---------|--------|
| B1 | `INGESTA\Rep_Prod\backend\app\features\analisis\api.py` | **EDIT** — helpers `_parse_periodo`/`_periodo_es_default`/`_ambito` + refactor de los 3 endpoints (firma + bloque de resolución/periodo). |
| B2 | `routes\api.py` | **EDIT** — 3 proxies forward `nivel` + `periodo`. |
| B3 | `INGESTA\Rep_Prod\backend\app\features\consulta\maquina.py` | **EDIT** — `_salida` incluye `periodo` en `out["intent"]`. |
| B4 | `INGESTA\Rep_Prod\backend\app\features\consulta\ejecucion.py` | **EDIT** — `ejecutar` pasa nivel+periodo a `desempeno`; aviso honesto por `periodo_ok`. |
| B5 | `static\js\multitab_shell.js` | **EDIT** — `__cnAnalizar(entidad,segmento,nivel,periodo)` + `__cnSegQS` + call sites + `__cnReanalizar`. |
| B6 | `templates\main.html` | **EDIT** — cache-buster. |

**Prohibido editar:** `catalogo`, `densidad`, `cobertura`, `huella`, `_desempeno_filiales`/`_ejecutivo_filiales` (filiales van por su rama), `resolver.py`, `extraccion.py`.

---

## 3. Especificación

### B1.1 — NUEVOS helpers en `api.py`

Insertar **inmediatamente antes** de `@router.get("/desempeno")` (línea 355):

```python
# ============================================================================
# Cimiento nivel+periodo aware (compartido por desempeno / desempeno_insight / ejecutivo).
# nivel-aware: resuelve por la COLUMNA del nivel (campo≠área); sin nivel → OR-unión (compat).
# periodo-aware (v1 = solo MES): default último-con-dato · mes explícito · mes+año · "mes pasado".
# ============================================================================
_NIVEL_COL_AMB = {"fuente": "nombre", "pozo": "nombre", "campo": "campo", "area": "grupo1",
                  "activo": "activos", "activos": "activos", "gerencia": "gerencia", "operador": "operador"}
_MESES_NUM = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
              "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_PERIODO_DEFAULT_TXT = {"este mes", "mes actual", "el mes", "mes en curso", "este mes en curso"}


def _periodo_es_default(texto):
    return (not texto) or (texto.strip().lower() in _PERIODO_DEFAULT_TXT)


def _parse_periodo(texto, ref_y, ref_mo):
    """Texto libre de periodo → (año, mes) para el KPI mensual, o None si no se reconoce/es default.
    v1 (D-C1): default, mes por nombre (+año opcional), 'mes pasado'. Año/semana/trimestre → None."""
    if _periodo_es_default(texto):
        return None
    import re as _re_p
    t = texto.strip().lower()
    if "pasado" in t or "anterior" in t:            # 'mes pasado' / 'mes anterior'
        y, m = ref_y, ref_mo - 1
        if m < 1:
            y, m = y - 1, 12
        return (y, m)
    mo = next((num for nombre, num in _MESES_NUM.items() if nombre in t), None)
    if mo is None:
        return None                                 # año/semana/trimestre no soportados en v1
    ym = _re_p.search(r"(20\d\d)", t)
    return (int(ym.group(1)) if ym else ref_y, mo)


def _ambito(c, entidad, nivel=None, periodo=None):
    """Ámbito ECP nivel+periodo aware. Devuelve:
      {ids, vid, y, mo, dim, ini, fin, aplica_diario, periodo_ok} | None (no encontrada) | {'sin_datos':True}."""
    import calendar
    ids, vid = [], None
    if entidad:
        E = entidad.strip().upper()
        col = _NIVEL_COL_AMB.get((nivel or "").lower())
        if (nivel or "").lower() == "vicepresidencia":
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"), {"e": E}).scalar()
        elif col:                                   # nivel específico → columna exacta (D-C2)
            ids = [r[0] for r in c.execute(sa.text(
                f"SELECT fuente_id FROM core.dim_fuente WHERE UPPER(TRIM({col}))=:e"), {"e": E})]
        else:                                       # sin nivel → OR-unión + vice (compat, D-C3)
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e OR UPPER(TRIM(grupo1))=:e
                   OR UPPER(TRIM(activos))=:e OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E})]
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"), {"e": E}).scalar()
        if not ids and vid is None:
            return None

    condd, condm, b0 = [], [], {}
    if ids:
        condd.append("fuente_id IN :ids"); condm.append("m.fuente_id IN :ids"); b0["ids"] = ids
    if vid is not None:
        condd.append("vice_id = :vid"); condm.append("m.vice_id = :vid"); b0["vid"] = vid
    wd = "(" + " OR ".join(condd) + ")" if condd else "TRUE"
    wm = "(" + " OR ".join(condm) + ")" if condm else "TRUE"

    def _mx(sql):
        t = sa.text(sql)
        return t.bindparams(sa.bindparam("ids", expanding=True)) if ids else t

    maxd = c.execute(_mx(f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {wd}"), b0).scalar()
    aplica_diario = maxd is not None
    if maxd is None:                                # fallback: último mes con REAL mensual
        maxd = c.execute(_mx(f"""
            SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
            JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
            WHERE es.nombre='REAL' AND {wm}"""), b0).scalar()
    if maxd is None:
        return {"sin_datos": True}

    per = _parse_periodo(periodo, maxd.year, maxd.month)
    y, mo = per if per else (maxd.year, maxd.month)
    periodo_ok = bool(per) or _periodo_es_default(periodo)   # honrado, o default explícito; False = no soportado
    dim = calendar.monthrange(y, mo)[1]
    return {"ids": ids, "vid": vid, "y": y, "mo": mo, "dim": dim,
            "ini": f"{y:04d}-{mo:02d}-01", "fin": f"{y:04d}-{mo:02d}-{dim:02d}",
            "aplica_diario": aplica_diario, "periodo_ok": periodo_ok}
```

### B1.2 — Refactor `desempeno`

**Firma** (línea 356), reemplazar:
```python
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp")):
```
por:
```python
def desempeno(entidad: str | None = Query(None), segmento: str = Query("ecp"),
              nivel: str | None = Query(None), periodo: str | None = Query(None)):
```

**Bloque de resolución+periodo** (líneas 369-414), reemplazar TODO el bloque:
```python
        ids, vid = [], None
        if entidad:
            E = entidad.strip().upper()
            ids = [r[0] for r in c.execute(sa.text("""
                SELECT fuente_id FROM core.dim_fuente
                WHERE UPPER(TRIM(nombre))=:e OR UPPER(TRIM(campo))=:e
                   OR UPPER(TRIM(grupo1))=:e OR UPPER(TRIM(activos))=:e
                   OR UPPER(TRIM(gerencia))=:e OR UPPER(TRIM(operador))=:e
            """), {"e": E}).all()]
            vid = c.execute(sa.text(
                "SELECT vice_id FROM core.dim_vicepresidencia WHERE UPPER(TRIM(codigo))=:e"),
                {"e": E}).scalar()
            if not ids and vid is None:
                return {"entidad": entidad, "encontrada": False}

        base = {}
        if ids:
            base["ids"] = ids
        if vid is not None:
            base["vid"] = vid

        def where(alias):
            p = (alias + ".") if alias else ""
            cs = []
            if ids:
                cs.append(f"{p}fuente_id IN :ids")
            if vid is not None:
                cs.append(f"{p}vice_id = :vid")
            return ("(" + " OR ".join(cs) + ")") if cs else "TRUE"

        # --- mes objetivo: último mes con dato diario (o REAL mensual si es filial) ---
        maxd = c.execute(_bind(
            f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {where('')}", base), base).scalar()
        aplica_diario = maxd is not None
        if maxd is None:
            maxd = c.execute(_bind(f"""
                SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
                JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
                WHERE es.nombre = 'REAL' AND {where('m')}""", base), base).scalar()
        if maxd is None:
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}

        y, mo = maxd.year, maxd.month
        dim = calendar.monthrange(y, mo)[1]
        ini = f"{y:04d}-{mo:02d}-01"
        fin = f"{y:04d}-{mo:02d}-{dim:02d}"
```
por:
```python
        amb = _ambito(c, entidad, nivel, periodo)
        if amb is None:
            return {"entidad": entidad, "encontrada": False}
        if amb.get("sin_datos"):
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        ids, vid = amb["ids"], amb["vid"]
        aplica_diario = amb["aplica_diario"]
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]

        base = {}
        if ids:
            base["ids"] = ids
        if vid is not None:
            base["vid"] = vid

        def where(alias):
            p = (alias + ".") if alias else ""
            cs = []
            if ids:
                cs.append(f"{p}fuente_id IN :ids")
            if vid is not None:
                cs.append(f"{p}vice_id = :vid")
            return ("(" + " OR ".join(cs) + ")") if cs else "TRUE"
```

**Return** (líneas 461-468): añadir `periodo_ok` al dict `mes`/raíz. Localizar el `return {` y añadir tras `"sin_cierre": sin_cierre,`:
```python
            "periodo_ok": amb["periodo_ok"],
```

### B1.3 — Refactor `desempeno_insight` y `ejecutivo` (bloques CASI idénticos — difieren por 1 comentario, F-A1)

**Firmas**: añadir `nivel` + `periodo` igual que en B1.2 (a `def desempeno_insight(...)` línea 611 y `def ejecutivo(...)` línea 917).

**NEW block (idéntico para las dos):**
```python
        amb = _ambito(c, entidad, nivel, periodo)
        if amb is None:
            return {"entidad": entidad, "encontrada": False}
        if amb.get("sin_datos"):
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        ids, vid = amb["ids"], amb["vid"]
        y, mo, dim, ini, fin = amb["y"], amb["mo"], amb["dim"], amb["ini"], amb["fin"]
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
```

#### B1.3a — `desempeno_insight`: reemplazar EXACTAMENTE este `old_string` por el NEW block:
```python
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
```

#### B1.3b — `ejecutivo`: reemplazar EXACTAMENTE este `old_string` (⚠️ el comentario del `maxd` DIFIERE) por el NEW block:
```python
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

        # mes objetivo (último con crudo diario) -- MISMO criterio que /desempeno_insight
        maxd = c.execute(_b(f"SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp WHERE {where('')}"), base).scalar()
        if maxd is None:
            return {"entidad": entidad, "encontrada": True, "sin_datos": True}
        y, mo = maxd.year, maxd.month
        dim = calendar.monthrange(y, mo)[1]
        ini = f"{y:04d}-{mo:02d}-01"; fin = f"{y:04d}-{mo:02d}-{dim:02d}"
```

> Tras cada reemplazo: **una sola** def de `_b`/`where`/`base` por función. `ejecutivo` y `desempeno_insight`
> **NO** exponen `periodo_ok` en su return (solo `desempeno` lo necesita para el chat). Ambas conservan su
> `import calendar` (queda sin uso tras el refactor — inofensivo; opcional quitarlo).

### B2 — EDIT `routes\api.py` (3 proxies)

En **cada uno** de los 3 proxies (`analisis_desempeno` ~155, `analisis_desempeno_insight` ~172, `analisis_ejecutivo` ~190),
**después** del bloque `seg = request.args.get("segmento") … params["segmento"] = seg`, añadir:
```python
        for _k in ("nivel", "periodo"):
            _v = request.args.get(_k)
            if _v:
                params[_k] = _v
```

### B3 — EDIT `maquina.py` (`_salida` incluye `periodo`)

En `_salida`, rama `completo`, reemplazar:
```python
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"]}
```
por:
```python
        out["intent"] = {"entidad": intent["entidad"]["texto"], "nivel": r["nivel"], "rama": r["rama"],
                         "valor": r["valor"], "avisos": intent["avisos"], "periodo": intent.get("periodo")}
```

### B4 — EDIT `ejecucion.py` (`ejecutar` nivel+periodo aware)

Reemplazar la línea de la llamada a `fn`:
```python
    d = fn(entidad=resuelta["valor"], segmento="ecp")
```
por:
```python
    d = fn(entidad=resuelta["valor"], segmento="ecp", nivel=resuelta.get("nivel"), periodo=periodo)
```
Y **reemplazar** el bloque de aviso de periodo:
```python
    avisos = []
    if periodo and periodo.strip().lower() not in _PERIODO_DEFAULT:
        avisos.append("Por ahora respondo el mes en curso; los periodos históricos llegan en una próxima iteración.")
```
por (usa `periodo_ok` que ahora devuelve `desempeno`):
```python
    avisos = []
    if periodo and d.get("periodo_ok") is False:
        avisos.append("Aún no manejo periodos como año o semana; te muestro el mes en curso.")
```
> Nota: el `encabezado` ya usa `d["mes"]`, así que el mes REAL usado (p. ej. abril) se refleja solo. El fake
> de tests (`def _fn(entidad=None, segmento="ecp", **_)`) ya acepta `nivel`/`periodo` por `**_` → sin cambios en tests.

### B5 — EDIT `multitab_shell.js`

**Paso 1 — vars de contexto.** Tras `var __cnLastIntent = null;` (línea 911), añadir:
```javascript
  var __cnNivel = null, __cnPeriodo = null;   // nivel/periodo del análisis activo (para los 3 fetches)
```

**Paso 2 — `__cnAnalizar` los fija.** Cambiar la firma y las primeras líneas:
```javascript
  window.__cnAnalizar = function (entidad, segmento) {
    __cnSeg = (segmento === "filiales") ? "filiales" : "ecp";   // fija el segmento del panel
```
por:
```javascript
  window.__cnAnalizar = function (entidad, segmento, nivel, periodo) {
    __cnSeg = (segmento === "filiales") ? "filiales" : "ecp";   // fija el segmento del panel
    __cnNivel = __cnEsFil() ? null : (nivel || null);
    __cnPeriodo = __cnEsFil() ? null : (periodo || null);
```

**Paso 3 — `__cnSegQS` propaga nivel+periodo.** Reemplazar la función (líneas 1121-1126):
```javascript
  function __cnSegQS(entidad) {
    var qs = [];
    if (entidad && !__cnEsFil()) qs.push("entidad=" + encodeURIComponent(entidad));
    if (__cnEsFil()) qs.push("segmento=filiales");
    return qs.length ? "?" + qs.join("&") : "";
  }
```
por:
```javascript
  function __cnSegQS(entidad) {
    var qs = [];
    if (entidad && !__cnEsFil()) qs.push("entidad=" + encodeURIComponent(entidad));
    if (__cnEsFil()) qs.push("segmento=filiales");
    if (!__cnEsFil() && __cnNivel) qs.push("nivel=" + encodeURIComponent(__cnNivel));
    if (!__cnEsFil() && __cnPeriodo) qs.push("periodo=" + encodeURIComponent(__cnPeriodo));
    return qs.length ? "?" + qs.join("&") : "";
  }
```

**Paso 4 — call site del `completo`** (rama `if (d.status === "completo")`): reemplazar
```javascript
        else window.__cnAnalizar(d.intent.valor || d.intent.entidad, "ecp");
```
por:
```javascript
        else window.__cnAnalizar(d.intent.valor || d.intent.entidad, "ecp", d.intent.nivel, d.intent.periodo);
```

**Paso 5 — call site de `__cnAnalisisTab`** (key === "desempeno"): reemplazar
```javascript
      window.__cnAnalizar(ent, "ecp");
```
por:
```javascript
      window.__cnAnalizar(ent, "ecp", __cnLastIntent && __cnLastIntent.nivel, __cnLastIntent && __cnLastIntent.periodo);
```

**Paso 6 — botón "Analizar {entidad}" del chat.** Añadir el wrapper `__cnReanalizar` **antes** de `function __cnRender(d)`:
```javascript
  window.__cnReanalizar = function () {
    var it = __cnLastIntent; if (!it) return;
    window.__cnAnalizar(it.valor || it.entidad, "ecp", it.nivel, it.periodo);
  };
```
Y en `btnAnalizar`, cambiar el onclick `onclick="window.__cnAnalizar(\'' + entArg + '\')"` por `onclick="window.__cnReanalizar()"`.

### B6 — EDIT `templates\main.html`

Subir el cache-buster de `20260715k` a `20260715m` (2 referencias).

---

## 4. Orden de ejecución

1. **V0** (línea base): `GET /analisis/desempeno?entidad=CHICHIMENE` → hoy da la unión (9 pozos).
2. B1 → B2 → B3 → B4 → correr V1–V4 (backend). Reiniciar backend INGESTA.
3. B5 → B6 → V5–V6 (navegador).
4. Reportar tabla PASS/FAIL. **No commitear.**

---

## 5. Reglas no negociables

- **Compat (D-C3):** sin `nivel` NI `periodo`, los 3 endpoints deben responder **idéntico a hoy** (unión + último mes). El tablero global no cambia.
- **Frontera (D-C5):** el LLM no parsea periodo; `_parse_periodo` (Python) sí.
- **No tocar** filiales, `catalogo`/`densidad`/`cobertura`/`huella`, `resolver.py`, `extraccion.py`.
- **Una sola** definición de `where`/`_b`/`base` por endpoint tras el refactor (no duplicar).
- **Aditivo:** las respuestas solo GANAN campos (`periodo_ok` en `desempeno`); nada se elimina.

---

## 6. Validaciones (comando → esperado)

| ID | Acción | Esperado |
|----|--------|----------|
| **V1** | `cd INGESTA\Rep_Prod\backend; uv run pytest -q` | Verde (sin regresión; los fakes de `test_consulta_ejecucion` aceptan nivel/periodo por `**_`). |
| **V2** | `GET http://localhost:8088/analisis/desempeno?entidad=CHICHIMENE&nivel=campo` vs `…?entidad=CHICHIMENE` (sin nivel) | **Distintos**: con `nivel=campo` la cifra CRUDO es MENOR (2 pozos) que sin nivel (unión de 9). |
| **V3** | `GET …/desempeno?entidad=RUBIALES&nivel=campo` vs `…?entidad=RUBIALES` | **Iguales** (Rubiales redundante: unión == campo). |
| **V4** | `GET …/desempeno?entidad=RUBIALES&periodo=abril` | `mes.mes` = 4 (abril), no 5. `GET …?entidad=RUBIALES&periodo=2026` → cae al default (mayo) con `periodo_ok:false`. |
| **V5** | `GET …/desempeno` (SIN entidad/nivel/periodo) | **Sin regresión**: idéntico a hoy (global, último mes). |
| **V6** | Navegador (Ctrl+F5): "producción del campo Chichimene de crudo" → panel Desempeño | La cifra y el "Sustento por campo" corresponden al **campo** Chichimene (no al área). El chat y el panel muestran el **mismo** número. 0 errores de consola. |

> **V2/V3/V4 sin servidor (F-A2 — pasar TODOS los params explícitos; `desempeno` es route handler, los defaults son objetos `Query`):**
> `cd INGESTA\Rep_Prod\backend; uv run python -c "from app.features.analisis.api import desempeno as f; print([p for p in f(entidad='CHICHIMENE', segmento='ecp', nivel='campo', periodo=None)['por_producto'] if p['producto']=='CRUDO'])"`
> — comparar con `nivel=None`. Para V4 usar `periodo='abril'` y `periodo='2026'`.

---

## 7. Fuera de alcance (v1)

- **Año / trimestre / semana**: `_parse_periodo` devuelve None → default con aviso (`periodo_ok:false`). Extensión futura (año/trim = suma de meses; semana no tiene PPTO).
- **Mes explícito sin datos** (ej. «febrero» sin cierre): muestra el mes con KPI vacío (`sin_cierre`), no `sin_datos`. Refinamiento futuro.
- **Filiales**: su rama (`_desempeno_filiales`, etc.) no se toca.
- **Panorama densidad/cobertura nivel-aware (F-A3)**: la densidad/cobertura del panorama siguen resolviendo por
  nombre-unión (no usan `__cnSegQS`). Inconsistencia menor (días de cobertura ~iguales); follow-up separado.
- **Valle por entidad** (plan `plan_valle_entidad_2026-07-15.md`): se re-basa SOBRE este cimiento después (ya recibirá ids/periodo correctos).
