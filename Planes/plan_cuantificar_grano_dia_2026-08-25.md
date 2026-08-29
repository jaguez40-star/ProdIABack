# Plan · QV2-GRANO-DIA — CUANTIFICAR a grano día (N1D + selector)

> **Versión:** v2 auditada (§0.2 de CLAUDE.md: el plan entregado ya debe ser equivalente a un v2).
> **Auditoría previa ejecutada:** §15 pasos 1-3 (Mapeo · Auditoría · Diagnóstico) **antes** de escribir.
> **SQL probado contra la BD real** el 2026-08-25 — las cifras de este plan están medidas, no supuestas.
> **Fecha:** 2026-08-25 · **ID:** QV2-GRANO-DIA

---

## 1. CONTEXTO

**Proyecto:** ProdIA 2.0 — chat de analítica de producción de Ecopetrol.
**Raíz absoluta:** `c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0`

**Stack:**
- Backend analítico: **FastAPI/Uvicorn (INGESTA, puerto 8088)** — `INGESTA/Rep_Prod/backend/`
- Front + servidor de plantillas: **Flask (puerto 8020)** — `MainChat/`, `static/`
- Python: `INGESTA\Rep_Prod\backend\.venv\Scripts\python.exe` · **NO hay Node instalado**
- Frontend: **JavaScript vanilla** (`static/js/multitab_shell.js`). No hay React, ni pnpm, ni build.

> ⚠️ **Sobre CLAUDE.md:** el archivo `INGESTA/Rep_Prod/clmd/CLAUDE_muestra.md` describe **otro**
> proyecto (Robustez V2.0 — React 19 + pnpm + Plotly). Sus DT-13 (`.npmrc`), DT-14 (Plotly),
> DT-17 (barrels) y reglas R1/R2 **NO aplican** aquí. **Sí aplican** y son obligatorias:
> §0.2 (auditoría previa), §0.3 (reglas del Planner), §15 (flujo 6 pasos) y
> **§17.5 R3 / DT-15** (build verde ≠ feature verificada → validación humana obligatoria).

**Antecedente directo:** el commit `1d466ac` rechazó **toda** pregunta a grano día. El usuario objetó:
*"Si los reportes que alimentan la BD son diarios, ¿por qué estas preguntas no tienen respuesta?"*
Tenía razón: fue una **sobre-generalización** — se verificó que *"ayer"* no tiene dato y de ahí se
concluyó, sin comprobarlo, que ninguna fecha era respondible.

---

## 2. OBJETIVO

Dividir el rechazo actual en tres comportamientos según lo que la BD **realmente** permite:

| Forma | Hoy (`1d466ac`) | Objetivo |
|---|---|---|
| `"el 15 de mayo"`, `"el 15"` | ❌ rechaza | ✅ **responde la cifra** |
| `"mejor día de este mes"` | ❌ rechaza | ✅ **responde fecha + cifra** |
| `"ayer"`, `"hoy"` | ❌ rechaza con motivo **engañoso** | ✅ rechaza **diciendo el techo real** |
| blancos a grano día | ❌ rechaza | ✅ sigue rechazando (correcto) |

**No-objetivo:** que el motor invente un presupuesto diario. A grano día **no existe** (§3.3).

---

## 3. MAPEO — el código real (leído, no recordado)

### 3.1 Cadena de despacho

```
maquina_q.py:431   elif grupo == "cuantificar" and log:
  └─ respuesta_cuantificar.responder(texto, entidad, usuario, conversation_id)
       ├─ :121  _ranking.detectar(texto)          → fork N5 (ranking global, SIN entidad)
       │    └─ :126  _forma_no_soportada(texto)   ⚠️ EL RANKING TAMBIÉN LO USA (ver A-1)
       ├─ :153  _resolver.resolver_unico(...)     → aplica D-D5
       ├─ :168  _forma_no_soportada(texto)        ⬅ aquí rechaza hoy el día
       ├─ :174  _slots.extraer_slots(texto, entidad_valor=...)
       ├─ :174  _ejecutor.ejecutar(resuelta, slots)
       ├─ :178  _validador.formatear_cuerpo(res)
       └─ :183  {"mensaje", "panel": {"tipo": _PANEL_TIPO.get(nivel,"cuant_kpi"), "datos"}}
```

### 3.2 Contratos verificados

| Pieza | Ruta absoluta (desde la raíz) | Hecho |
|---|---|---|
| Despacho de nivel | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/ejecutor.py:51-60` | ramifica por `slots["nivel_temporal"]`: N4→N3→N2→**N1 (default)** |
| **Frontera** | `.../cuantificar/ejecutor.py:11` | **"Frontera: NO SQL propio, NO LLM"** |
| **Pureza de slots** | `.../cuantificar/slots.py:3` | *"Fase 1-3 es 100% DETERMINISTA"* · importa solo `re`, `norm`, `catalogo` → **sin BD** |
| Precedente de helper | `INGESTA/Rep_Prod/backend/app/features/analisis/api.py:635` | `escenario_mes()` — *"read-only y AISLADO: no toca desempeno"* (AF-4.2) |
| Ámbito | `.../analisis/api.py:391-448` | `_ambito(c, entidad, nivel, periodo)` → `{ids, vid, y, mo, ini, fin, aplica_diario, periodo_ok}` |
| Parseo de periodo | `.../cuantificar/slots.py:102-112` | `_periodo_texto()`: **solo** mes por nombre, `"pasado"/"anterior"`, año 4 cifras |
| Formato de cuerpo | `.../cuantificar/validador.py:29-93` | ramifica N3→N4→N2→N1; **N1 hace `res["mes"]` en :77** |
| Panel (front) | `static/js/multitab_shell.js:2981-2998` | cadena de `tipo`; **fallback `__cnCuantCardHtml` si no calza** |
| Tarjeta KPI | `static/js/multitab_shell.js:2660-2705` | `__cnRing(pct...)` + `fmtV(dat.ppto)` |
| Cache-buster | `MainChat/templates/mainchat_layout.html:113` | hoy `?v=20260825c` |

### 3.3 La BD (medido el 2026-08-25)

```
core.fact_produccion_dia_ecp
  cols: id, fecha, fuente_id, vice_id, socio_id, concepto_id, tipo_producto_id,
        producto, grupo_prod, propietario, volumen, porcentaje, voldismez,
        vol_estimado, promedio, reporte_id
  ⚠ SIN escenario_id  →  a grano día SOLO existe REAL. Nunca PPTO.
  rango: … → 2026-05-17    (fecha del sistema: 2026-08-25 → 100 días de desfase)

core.vw_proyeccion_diaria   tiene valor_programa PERO empresa ∈ {America, Hocol, Permian}
                            →  CERO filas para campos ECP. NO sirve como PPTO diario.

Cifras de referencia (ámbito correcto, nivel=campo):
  CASTILLA 2026-05-15 → CRUDO 223.752,36 · GAS 0,0
  CASTILLA 2026-05-02 → CRUDO 226.644,28      ← mejor día de mayo
  curva mayo de CASTILLA: 17 días con dato (01→17)
```

---

## 4. AUDITORÍA — hallazgos (9)

> Los A-1..A-4 son **bloqueantes**: sin resolverlos el plan rompe algo que hoy funciona.

### 🔴 A-1 · BLOQUEANTE — quitar `dia` de `_FORMAS_RECHAZO` **reabre el bug #5 por la vía del ranking**

`respuesta_cuantificar.py:126` llama a `_forma_no_soportada(texto)` **también dentro del fork N5**, y
su comentario advierte que ese check existe justamente para que *"top campos del primer trimestre"*
no se degrade al mes en silencio.

El ranking N5 es **mensual por construcción** (`cuantificar/ranking.py:135` `_fin_mes`, consulta
`core.fact_produccion_mes_ecp`). Si se quita `"dia"` del set global, entonces
**`"top 5 campos el 15 de mayo"` devolvería el ranking del MES entero como si fuera del día** —
exactamente la degradación silenciosa que `1d466ac` vino a cerrar.

→ **Solución:** NO usar un único set. Separar en dos:
`_FORMAS_RECHAZO_RANKING` (con `dia`/`selector_dia`) y `_FORMAS_RECHAZO_ENTIDAD` (sin ellas).

### 🔴 A-2 · BLOQUEANTE — `slots.py` es un módulo PURO y el techo exige BD

`slots.py:3` declara *"Fase 1-3 es 100% DETERMINISTA"* y sus únicos imports son `re`, `norm` y
`catalogo`. Resolver `"el 15"` (mes implícito) o `"este mes"` necesita el **techo del dato**, que es
una consulta SQL. Meter la BD en `slots.py` rompe su contrato y lo vuelve intesteable sin Postgres.

→ **Solución:** `extraer_slots(texto, entidad_valor=None, techo=None)` — el techo entra **como
parámetro**. Lo obtiene `respuesta_cuantificar.responder` (que sí puede llamar helpers) **después**
de resolver la entidad. `slots.py` sigue puro.

### 🔴 A-3 · BLOQUEANTE — el fallback del frontend pinta una tarjeta que MIENTE

`multitab_shell.js:2989-2991` lo documenta porque ya les ocurrió con `p50_vp`:

> *"H2: registrada ANTES del fallback `__cnCuantCardHtml` — ese fallback **NO valida el tipo** y
> pintaría una tarjeta KPI con campos ajenos (estado/cumplimiento_pct/nivel) ante cualquier tipo no
> reconocido."*

Un `tipo:"cuant_dia"` sin registrar cae ahí → `fmtV(dat.ppto)` = `Math.round(undefined)` → **"NaN
bbl"**, y `__cnRing(0,...)` → anillo al 0%. Una tarjeta con aspecto válido y contenido falso.

→ **Solución:** registrar el tipo **antes** del fallback (Paso 6.3). No es opcional.

### 🔴 A-4 · BLOQUEANTE — `validador.formatear_cuerpo` revienta con `KeyError`

`validador.py:60` avisa *"N1/N2 (usan resultado/referencia — solo aquí, ya descartados N3/N4)"* y
`:77` hace `mes = res["mes"]`. El contrato N1D trae `fecha`, **no** `mes`.

→ **Solución:** la rama `N1D`/`N1DSEL` va **antes** de la de N1, igual que se hizo con N3/N4 (HE6).

### 🟠 A-5 · `strftime` devuelve inglés — verificado en esta máquina

```
>>> datetime.date(2026,5,15).strftime('%A %d de %B de %Y')
'Friday 15 de May de 2026'          ← locale ('es_ES','cp1252') y aun así inglés
```
→ **Solución:** tablas manuales de días/meses. **Prohibido** `locale.setlocale` (global y frágil).

### 🟠 A-6 · No se puede reusar `cuant_kpi`

La tarjeta gira sobre `REAL / PPTO`: anillo (`:2694`) y fila de referencia (`:2700`). A grano día no
hay PPTO → reusarla obliga a inventar referencia o mostrar 0%. Ambas violan la regla madre.
→ **Tipo y función de render propios.**

### 🟠 A-7 · `_periodo_texto` se come el mes y descarta el día

Medido: `"el 15 de mayo"` → `"mayo"`. Si N1D no intercepta primero, el flujo cae a N1 y responde el
mes entero — **el bug original, reabierto por otra vía**.
→ La detección de día se resuelve **antes** y **gana** sobre `_periodo_texto`.

### 🟡 A-8 · Archivo del frontend compartido con OTRA SESIÓN

`static/js/multitab_shell.js` lo edita una sesión paralela; el cache-buster ya va en `?v=20260825c`.
→ `git status` antes de tocar · **solo añadir** · no reformatear · **bump obligatorio** del buster.

### 🟡 A-9 · Tests existentes que NO deben romperse

- `tests/test_cuantificar_rango.py` prueba `_forma_no_soportada` **por su nombre actual** (13 asserts).
  Si se renombra o se cambia su firma, ese archivo falla. → Conservar `_forma_no_soportada` como
  función de la ruta ENTIDAD y añadir una hermana para el ranking.
- `tests/test_no_soportado.py` afirma `detectar(...) == "dia"` y `== "selector_dia"`.
  → **Conservar ambas formas en `_FORMAS`**; solo cambia quién las consume.

---

## 5. DIAGNÓSTICO

| # | Hueco | Causa exacta | Archivo |
|---|---|---|---|
| D1 | No se parsea ninguna fecha | `slots._periodo_texto` solo conoce meses | `cuantificar/slots.py` |
| D2 | No hay nivel temporal de día | `ejecutar()` solo despacha N1-N4 | `cuantificar/ejecutor.py` |
| D3 | No hay consulta diaria | la frontera prohíbe SQL en el ejecutor | `analisis/api.py` |
| D4 | `"ayer"` miente sobre el motivo | mensaje genérico "solo el mes" | `respuesta_cuantificar.py` |
| D5 | El panel no sabe pintar un día | cadena de tipos sin `cuant_dia` | `multitab_shell.js` |
| D6 | El ranking se degradaría | set de rechazo único (A-1) | `respuesta_cuantificar.py` |

---

## 6. PREREQUISITOS

```bash
# 1) INGESTA y Flask NO necesitan estar corriendo para implementar/testear.
# 2) Postgres SÍ debe estar accesible (los helpers y varios tests leen BD).
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
from app.core.db import get_engine; import sqlalchemy as sa
print(get_engine().connect().execute(sa.text('SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp')).scalar())"
# ESPERADO: 2026-05-17     (si sale otra fecha, AJUSTAR las cifras esperadas de §9)
```

**Línea base OBLIGATORIA antes de editar nada:**
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -3
```
**Esperado al 2026-08-25: `7 failed, 472 passed, 1 skipped`.**
Los 7 son **preexistentes y ajenos a este plan**: `test_escalada_fallback_conserva_regex`,
2 de `test_analisis_tarjetas_kpi`, 3 de `test_conteo_jerarquia`, 1 de `test_jerarquizar_ranking`.
→ **La suite final debe mostrar EXACTAMENTE esos 7 y ninguno más.**

---

## 7. INVENTARIO DE ARCHIVOS

| # | Ruta (relativa a la raíz del proyecto) | Acción |
|---|---|---|
| 1 | `INGESTA/Rep_Prod/backend/app/features/analisis/api.py` | **Añadir** 3 funciones al final |
| 2 | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/slots.py` | Añadir parseo de día |
| 3 | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/ejecutor.py` | Añadir 2 ejecutores |
| 4 | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/validador.py` | Añadir rama N1D |
| 5 | `INGESTA/Rep_Prod/backend/app/features/consulta_v2/respuesta_cuantificar.py` | Separar sets + techo |
| 6 | `INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py` | **Crear** |
| 7 | `static/js/multitab_shell.js` | **Solo añadir** (⚠️ A-8) |
| 8 | `MainChat/templates/mainchat_layout.html` | Solo el cache-buster |

**Prohibido tocar:** `desempeno`, `_ambito`, `cuantificar/ranking.py`, `cuantificar/niveles.py`,
`no_soportado.py`, `maquina_q.py`, y todo lo de jerarquizar/analizar.

---

## 8. ESPECIFICACIÓN

### PASO 1 · Helpers de datos
**Archivo:** `INGESTA/Rep_Prod/backend/app/features/analisis/api.py` — **añadir al final**

```python
# ---------------------------------------------------------------------------
# [2026-08-25] GRANO DÍA (plan QV2-GRANO-DIA). Helpers AISLADOS y read-only: mismo criterio que
# `escenario_mes` (AF-4.2) — reusan `_ambito` para el ámbito y NO tocan `desempeno`.
# 🔑 core.fact_produccion_dia_ecp NO tiene escenario_id: a grano día solo existe REAL, jamás PPTO.
# ---------------------------------------------------------------------------
def _amb_dia(c, entidad, nivel):
    """(cond_where, params_base, ids) del ámbito para las tablas de grano día. None si no aplica."""
    amb = _ambito(c, entidad, nivel=nivel)
    if not amb or amb.get("sin_datos"):
        return None
    ids, vid = amb.get("ids"), amb.get("vid")
    if not ids and vid is None:
        return None
    cond, params = [], {}
    if ids:
        cond.append("d.fuente_id IN :ids"); params["ids"] = ids
    if vid is not None:
        cond.append("d.vice_id = :vid"); params["vid"] = vid
    return "(" + " OR ".join(cond) + ")", params, ids


def techo_dia(entidad: str, nivel: str | None = None):
    """Última fecha con reporte DIARIO en el ámbito de la entidad, o None.
    Es la fuente del rechazo honesto: el mensaje cita esta fecha, jamás una constante."""
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return None
        whr, params, ids = r
        t = sa.text(f"SELECT MAX(d.fecha) FROM core.fact_produccion_dia_ecp d WHERE {whr}")
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return c.execute(t, params).scalar()


def produccion_dia(entidad: str, fecha, nivel: str | None = None) -> dict:
    """REAL por producto en UNA fecha, con el MISMO ámbito que `desempeno`.
    Devuelve {"por_producto": {PROD: float}, "techo": date|None, "hay_dato": bool}."""
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return {"por_producto": {}, "techo": None, "hay_dato": False}
        whr, params, ids = r

        def _b(sql):
            t = sa.text(sql)
            return t.bindparams(sa.bindparam("ids", expanding=True)) if ids else t

        p = dict(params); p["f"] = str(fecha)
        rows = c.execute(_b(f"""
            SELECT tp.nombre prod, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha = :f AND {whr} GROUP BY 1"""), p)
        por = {k: float(v or 0) for k, v in rows}
        techo = c.execute(_b(
            f"SELECT MAX(d.fecha) FROM core.fact_produccion_dia_ecp d WHERE {whr}"), params).scalar()
        # hay_dato = hay alguna fila CON volumen > 0 (una fila en 0 no es "dato del día").
        return {"por_producto": por, "techo": techo,
                "hay_dato": any(v > 0 for v in por.values())}


def curva_dia_mes(entidad: str, anio: int, mes: int, producto: str,
                  nivel: str | None = None) -> list:
    """Serie diaria [(date, float)] de UN producto dentro de un mes. Base del selector
    (mejor/peor día). `producto` en MAYÚSCULAS ('CRUDO'|'GAS'|'BLANCOS')."""
    import calendar
    eng = get_engine()
    with eng.connect() as c:
        r = _amb_dia(c, entidad, nivel)
        if r is None:
            return []
        whr, params, ids = r
        dim = calendar.monthrange(anio, mes)[1]
        p = dict(params)
        p.update({"ini": f"{anio:04d}-{mes:02d}-01",
                  "fin": f"{anio:04d}-{mes:02d}-{dim:02d}", "p": producto.upper()})
        t = sa.text(f"""
            SELECT d.fecha, SUM(d.volumen) vol
            FROM core.fact_produccion_dia_ecp d
            JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = d.tipo_producto_id
            WHERE d.fecha BETWEEN :ini AND :fin AND UPPER(tp.nombre) = :p AND {whr}
            GROUP BY d.fecha ORDER BY d.fecha""")
        if ids:
            t = t.bindparams(sa.bindparam("ids", expanding=True))
        return [(f, float(v or 0)) for f, v in c.execute(t, p)]
```

**✅ V-1 (ejecutar tal cual):**
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
from app.features.analisis.api import produccion_dia, curva_dia_mes, techo_dia
print('A', produccion_dia('CASTILLA','2026-05-15',nivel='campo'))
print('B', produccion_dia('CASTILLA','2026-08-24',nivel='campo'))
print('C', techo_dia('CASTILLA', nivel='campo'))
c=curva_dia_mes('CASTILLA',2026,5,'CRUDO',nivel='campo')
print('D', len(c), max(c,key=lambda r:r[1]) if c else None)"
```
**Esperado:**
```
A {'por_producto': {'CRUDO': 223752.36, 'GAS': 0.0}, 'techo': datetime.date(2026, 5, 17), 'hay_dato': True}
B {'por_producto': {}, 'techo': datetime.date(2026, 5, 17), 'hay_dato': False}
C 2026-05-17
D 17 (datetime.date(2026, 5, 2), 226644.28)
```

---

### PASO 2 · Parseo de día (módulo PURO — A-2)
**Archivo:** `.../consulta_v2/cuantificar/slots.py`

**2.a** — Añadir tras `_MESES` (~línea 52):

```python
# [2026-08-25] GRANO DÍA (plan QV2-GRANO-DIA). `_periodo_texto` solo conoce MESES: medido,
# "el 15 de mayo" devolvía «mayo» y el motor contestaba el MES ENTERO. Esto se resuelve ANTES.
# 🔑 Este módulo es PURO (sin BD): el `techo` entra como PARÁMETRO, no se consulta aquí.
_MESES_NUM = {m: i + 1 for i, m in enumerate(_MESES)}
_DIA_REL = {"ANTEAYER": -2, "ANTIER": -2, "AYER": -1, "HOY": 0}   # orden: los largos primero
_RX_DIA_MES = re.compile(r"\bEL\s+(\d{1,2})\s+DE\s+([A-Z]+)")
_RX_DIA_SOLO = re.compile(r"\bEL\s+(?:DIA\s+)?(\d{1,2})\b")
_RX_SELECTOR = re.compile(r"\b(MEJOR|PEOR)\s+DIA\b|\bQUE\s+DIA\s+.{0,24}\b(MAS|MENOS)\b|"
                          r"\bDIA\s+DE\s+(MAYOR|MENOR)\b")
# Guarda H4 (gemela de la de no_soportado.py): "acumulado hasta hoy" trae HOY pero pide N2.
_RX_ACUM_GUARDA = re.compile(r"\bACUMULAD[OA]\b|\bEN\s+LO\s+QUE\s+VA\b|\bYTD\b|"
                             r"\bHASTA\s+(AHORA|HOY|LA\s+FECHA)\b|\bEN\s+TOTAL\b")
# Formas de RANGO que NO son un día puntual y ya tienen su propio rechazo (no_soportado.py).
_RX_RANGO_GUARDA = re.compile(r"\bENTRE\s+EL\s+\d+\s+Y\s+EL\s+\d+|\bDEL\s+\d+\s+AL\s+\d+|"
                              r"\bLOS\s+\d+\s+DIAS|\bPRIMEROS\s+\d+\s+DIAS|\bSEMANA|\bTRIMESTRE")


def menciona_dia(texto: str) -> bool:
    """PRE-CHECK barato y puro. Solo si devuelve True el llamador paga la consulta del techo
    (evita un round-trip a BD en TODA pregunta mensual)."""
    t = norm(texto or "")
    if _RX_ACUM_GUARDA.search(t) or _RX_RANGO_GUARDA.search(t):
        return False
    return bool(_RX_SELECTOR.search(t) or _RX_DIA_MES.search(t) or _RX_DIA_SOLO.search(t)
                or any(re.search(r"\b" + k + r"\b", t) for k in _DIA_REL))


def detectar_dia(texto: str, techo=None) -> dict | None:
    """Ranura de DÍA, o None si la pregunta no es de grano día. `techo` (date) fija el mes/año
    implícitos: se asume el del DATO, no el del reloj (el reporte va ~100 días atrás).

    Devuelve uno de:
      {"clase":"fecha",    "fecha":"YYYY-MM-DD", "asumido":[...]}
      {"clase":"relativo", "delta":-1}
      {"clase":"selector", "orden":"max"|"min", "anio":int, "mes":int, "asumido":[...]}
    """
    t = norm(texto or "")
    if _RX_ACUM_GUARDA.search(t) or _RX_RANGO_GUARDA.search(t):
        return None
    m = _RX_SELECTOR.search(t)
    if m:
        g = m.group(0)
        orden = "min" if ("PEOR" in g or "MENOS" in g or "MENOR" in g) else "max"
        mo = next((num for nom, num in _MESES_NUM.items() if nom.upper() in t), None)
        ya = re.search(r"20\d\d", t)
        if mo is None and techo is None:
            return None                       # sin mes explícito ni techo no se puede resolver
        anio = int(ya.group(0)) if ya else (techo.year if techo else None)
        asum = []
        if mo is None:
            mo, anio = techo.month, techo.year
            asum.append(f"periodo={mo:02d}/{anio}")
        return {"clase": "selector", "orden": orden, "anio": anio, "mes": mo, "asumido": asum}
    for kw, delta in _DIA_REL.items():
        if re.search(r"\b" + kw + r"\b", t):
            return {"clase": "relativo", "delta": delta}
    m = _RX_DIA_MES.search(t)
    if m and m.group(2).lower() in _MESES_NUM:
        d, mo = int(m.group(1)), _MESES_NUM[m.group(2).lower()]
        ya = re.search(r"20\d\d", t)
        anio = int(ya.group(0)) if ya else (techo.year if techo else None)
        if anio and 1 <= d <= 31:
            return {"clase": "fecha", "fecha": f"{anio:04d}-{mo:02d}-{d:02d}",
                    "asumido": [] if ya else [f"año={anio}"]}
    m = _RX_DIA_SOLO.search(t)
    if m and techo:
        d = int(m.group(1))
        if 1 <= d <= 31:
            return {"clase": "fecha", "fecha": f"{techo.year:04d}-{techo.month:02d}-{d:02d}",
                    "asumido": [f"mes={techo.month:02d}/{techo.year}"]}
    return None
```

**2.b** — En `extraer_slots`, **añadir el parámetro `techo=None`** (firma: `extraer_slots(texto,
entidad_valor=None, techo=None)`) y, **antes** de `per = _periodo_texto(texto)` (A-7), insertar:

```python
    dia = detectar_dia(texto, techo)
    if dia is not None:
        nivel = "N1DSEL" if dia["clase"] == "selector" else "N1D"
```
Añadir al dict devuelto: `"dia": dia` (o `None`), y sumar `dia.get("asumido", [])` a
`defaults_asumidos`.

**✅ V-2:**
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
import datetime as dt
from app.features.consulta_v2.cuantificar.slots import detectar_dia, menciona_dia
T=dt.date(2026,5,17)
for q in ['cuanto produjo Castilla el 15 de mayo','el 15','ayer','hoy',
          'mejor dia de Castilla este mes','peor dia en mayo',
          'acumulado hasta hoy','cuanto produjo en abril','del 1 al 15','esta semana']:
    print('%-38s pre=%-5s %s' % (q, menciona_dia(q), detectar_dia(q,T)))"
```
**Esperado (lo esencial):** `el 15 de mayo`→`fecha 2026-05-15` · `el 15`→`fecha 2026-05-15` ·
`ayer`→`relativo -1` · `mejor dia…este mes`→`selector max 5/2026` · `acumulado hasta hoy`→`None`
(pre=False) · `cuanto produjo en abril`→`None` · `del 1 al 15`→`None` · `esta semana`→`None`.

---

### PASO 3 · Ejecutores
**Archivo:** `.../consulta_v2/cuantificar/ejecutor.py`

**3.a** — Import (línea 12), añadir a lo ya importado de `analisis.api`:
`produccion_dia as _prod_dia_ep, curva_dia_mes as _curva_ep`.

**3.b** — En `ejecutar()` (`:51-60`), **antes** del `return ejecutar_n1(...)`:
```python
    if nt == "N1DSEL":
        return ejecutar_n1dsel(resuelta, slots)
    if nt == "N1D":
        return ejecutar_n1d(resuelta, slots)
```

**3.c** — Añadir (código completo):

```python
# [2026-08-25] GRANO DÍA. Contrato propio (NO trae `mes`): validador ramifica antes de N1.
_AVISO_SIN_PPTO = ("A grano día el reporte solo trae REAL: no hay presupuesto diario contra el "
                   "cual comparar, así que no puedo darte cumplimiento.")
_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES_ES_L = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_es(d) -> str:
    """'viernes 15 de mayo de 2026'. Tablas manuales: strftime devuelve INGLÉS en esta máquina
    (verificado 2026-08-25) y locale.setlocale es global y frágil."""
    return f"{_DIAS_ES[d.weekday()]} {d.day} de {_MESES_ES_L[d.month]} de {d.year}"


def _rechazo_dia(resuelta, slots, techo, que="ese día"):
    """Rechazo HONESTO: cita el techo REAL consultado, nunca una constante."""
    if slots.get("producto") == "blancos":       # catálogo: granos.dia confianza=no (×2)
        return {"aplica": False, "texto": (
            f"Los blancos a grano día no reconcilian con el mes (el reporte los mide por corrientes "
            f"físicas), así que no puedo darte {que} de blancos para «{resuelta['valor']}». "
            f"A grano mes sí puedo.")}
    if techo is None:
        return {"aplica": False,
                "texto": f"No tengo reporte diario para «{resuelta['valor']}»."}
    return {"aplica": False, "texto": (
        f"No tengo reporte diario de «{resuelta['valor']}» para {que}: el dato diario llega hasta "
        f"el {fecha_es(techo)}. Si me nombras un día dentro de ese rango, o el mes, te doy la cifra.")}


def ejecutar_n1d(resuelta: dict, slots: dict, _dia_fn=None) -> dict:
    """N1D: producción REAL de UNA fecha. Sin PPTO (no existe a grano día) → sin cumplimiento."""
    import datetime as _dt
    fn = _dia_fn or _prod_dia_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    dia = slots.get("dia") or {}
    if dia.get("clase") == "relativo":
        f = _dt.date.today() + _dt.timedelta(days=dia["delta"])
    else:
        f = _dt.date.fromisoformat(dia["fecha"])
    producto = slots["producto"]
    r = fn(resuelta["valor"], f, nivel=resuelta.get("nivel"))
    if producto == "blancos" or not r.get("hay_dato"):
        return _rechazo_dia(resuelta, slots, r.get("techo"), f"el {fecha_es(f)}")
    val = (r["por_producto"] or {}).get(_PROD_MAP[producto], 0.0)
    if not val:
        return {"aplica": False, "texto":
                f"«{resuelta['valor']}» no reporta {producto} el {fecha_es(f)}."}
    avisos = [_AVISO_SIN_PPTO]
    if slots.get("descargo"):
        avisos.append(slots["descargo"])
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable"),
        "nivel": "N1D", "grano": "dia", "universo": "reporte_diario",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": f"{_etiqueta_nivel(resuelta.get('nivel'), resuelta)} {resuelta['valor']}".strip(),
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
        "fecha": f.isoformat(), "fecha_label": fecha_es(f),
        "resultado": {"valor": val},
        "referencia": None, "referencia_valor": None, "cumplimiento_pct": None, "estado": "",
        "techo_dia": r["techo"].isoformat() if r.get("techo") else None,
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": avisos,
        "zoom": resuelta.get("zoom", []),
    }


def ejecutar_n1dsel(resuelta: dict, slots: dict, _curva_fn=None) -> dict:
    """N1DSEL: día de MAYOR/MENOR producción dentro de un mes (argmax sobre la curva diaria).
    NO es el ranking N5: allí se ordenan ENTIDADES; aquí la entidad es fija y se ordena el TIEMPO."""
    fn = _curva_fn or _curva_ep
    rech = _rechazo_comun(resuelta, slots)
    if rech:
        return rech
    dia = slots.get("dia") or {}
    producto = slots["producto"]
    if producto == "blancos":
        return _rechazo_dia(resuelta, slots, None, "el mejor día")
    pts = [(f, v) for f, v in fn(resuelta["valor"], dia["anio"], dia["mes"],
                                 _PROD_MAP[producto], nivel=resuelta.get("nivel")) if v > 0]
    if not pts:
        return {"aplica": False, "texto": (
            f"No tengo curva diaria de {producto} para «{resuelta['valor']}» en "
            f"{_MESES_ES_L[dia['mes']]} {dia['anio']}.")}
    elegido = (max if dia.get("orden") == "max" else min)(pts, key=lambda r: r[1])
    return {
        "aplica": True, "grupo": "cuantificar", "variable": slots.get("variable"),
        "nivel": "N1DSEL", "grano": "dia", "universo": "reporte_diario",
        "entidad": {"nombre": resuelta["valor"], "nivel": resuelta.get("nivel"), "fue_asumida": False},
        "entidad_cualificada": f"{_etiqueta_nivel(resuelta.get('nivel'), resuelta)} {resuelta['valor']}".strip(),
        "producto": producto, "unidad": slots.get("unidad", "bbl"),
        "orden": dia.get("orden", "max"),
        "fecha": elegido[0].isoformat(), "fecha_label": fecha_es(elegido[0]),
        "resultado": {"valor": elegido[1]},
        "mes_label": f"{_MESES_ES_L[dia['mes']]} {dia['anio']}",
        "dias_con_dato": len(pts),
        "rango": [pts[0][0].isoformat(), pts[-1][0].isoformat()],
        "referencia": None, "referencia_valor": None, "cumplimiento_pct": None, "estado": "",
        "defaults_asumidos": slots.get("defaults_asumidos", []), "avisos": [_AVISO_SIN_PPTO],
        "zoom": resuelta.get("zoom", []),
    }
```

---

### PASO 4 · Cuerpo de texto
**Archivo:** `.../consulta_v2/cuantificar/validador.py`
Insertar **inmediatamente después del bloque `if nivel == "N4":`** y **antes** del comentario
`# N1/N2 (usan resultado/referencia…)` (A-4):

```python
    # [2026-08-25] GRANO DÍA. VA ANTES de N1/N2: su contrato NO trae `mes` ni `referencia_valor`
    # — leerlos abajo reventaría con KeyError (mismo criterio que N3/N4, HE6).
    if nivel == "N1D":
        linea = (f"{res['entidad_cualificada']} produjo {fmt_valor(res['resultado']['valor'], prod)} "
                 f"{unidad} de {prod} el {res['fecha_label']}.")
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    if nivel == "N1DSEL":
        cual = "mejor" if res.get("orden") == "max" else "peor"
        linea = (f"El {cual} día de {prod} de {res['entidad_cualificada']} en {res['mes_label']} "
                 f"fue el {res['fecha_label']}, con {fmt_valor(res['resultado']['valor'], prod)} "
                 f"{unidad} ({res['dias_con_dato']} días con reporte).")
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea
```

---

### PASO 5 · Orquestación y separación de sets (A-1, A-2)
**Archivo:** `.../consulta_v2/respuesta_cuantificar.py`

**5.a** — Sustituir `_FORMAS_RECHAZO` por **dos** sets (conservando `_forma_no_soportada` con su
nombre y firma actuales — A-9, `tests/test_cuantificar_rango.py` depende de ellos):

```python
# [2026-08-25] DOS sets, no uno. El fork de RANKING (N5) y la ruta de ENTIDAD ya no rechazan lo mismo:
#   · La ruta de ENTIDAD sí construye el grano día (N1D/N1DSEL) → 'dia'/'selector_dia' salen del set.
#   · El RANKING N5 es MENSUAL por construcción (ranking.py::_fin_mes sobre fact_produccion_mes_ecp):
#     si le quitáramos 'dia', "top 5 campos el 15 de mayo" devolvería el ranking del MES ENTERO en
#     silencio — exactamente la degradación del bug #5 que este check existe para impedir.
_FORMAS_RECHAZO = ("rango_dias", "trimestre", "semana")                      # ruta ENTIDAD
_FORMAS_RECHAZO_RANKING = ("rango_dias", "trimestre", "semana", "dia", "selector_dia")


def _forma_no_soportada(texto: str):
    """Forma NO soportada por la ruta de ENTIDAD, o None. (Nombre y firma estables: los usa
    tests/test_cuantificar_rango.py)."""
    f = _no_soportado.detectar(texto)
    return f if f in _FORMAS_RECHAZO else None


def _forma_no_soportada_ranking(texto: str):
    """Idem para el fork N5, que NO tiene grano día."""
    f = _no_soportado.detectar(texto)
    return f if f in _FORMAS_RECHAZO_RANKING else None
```

**5.b** — En el fork de ranking (`:126`), cambiar la llamada a `_forma_no_soportada_ranking(texto)`.

**5.c** — En `responder`, **después** de resolver la entidad y **antes** de `extraer_slots`
(hoy línea 174), obtener el techo **solo si hace falta** (evita un round-trip en toda pregunta mensual):

```python
    from app.features.consulta_v2.cuantificar.slots import menciona_dia as _menciona_dia
    from app.features.analisis.api import techo_dia as _techo_ep
    _techo = (_techo_ep(resuelta["valor"], nivel=resuelta.get("nivel"))
              if _menciona_dia(texto) else None)
    res = _ejecutor.ejecutar(resuelta,
                             _slots.extraer_slots(texto, entidad_valor=resuelta["valor"],
                                                  techo=_techo))
```

**5.d** — `_PANEL_TIPO`: añadir `"N1D": "cuant_dia", "N1DSEL": "cuant_dia"`.

**5.e** — `_panel_datos`: añadir rama al principio (antes del `if nivel == "N3"`), devolviendo
`nivel, entidad_cualificada, producto, unidad, avisos, fecha, fecha_label, valor` y —solo en
`N1DSEL`— `orden, mes_label, dias_con_dato, rango`.

**5.f** — Cierre conversacional: para `N1D`/`N1DSEL` usar
`_CIERRE_DIA = "Si quieres, te doy el total del mes o el de otro día."`
(**no** una pregunta sí/no — regla H1: un "sí" caería en el drill `_AFIRM` de
`maquina_q._continuacion` y devolvería un acumulado).

---

### PASO 6 · Panel ⚠️ archivo compartido (A-8)
**Archivos:** `static/js/multitab_shell.js` · `MainChat/templates/mainchat_layout.html`

1. `git status` **antes** de tocar. Si `multitab_shell.js` aparece modificado por otra sesión → **DETENERSE y reportar.**
2. Añadir `__cnCuantDiaHtml(d)` **junto a** `__cnCuantCardHtml` (~línea 2705). Requisitos:
   - **SIN** `__cnRing` y **SIN** fila de presupuesto (A-6): no existe PPTO diario.
   - Cifra grande con `__cnGasM(v)` si `d.producto === "gas"`, si no `__cnMilesEC(Math.round(v))`
     (mismas funciones que usa `__cnCuantCardHtml`, ya definidas en el archivo).
   - Mostrar `d.fecha_label`; en `N1DSEL` añadir `d.mes_label`, `d.dias_con_dato` y `d.rango`.
   - Pintar `d.avisos` con el mismo molde `cp-p50__r` que la tarjeta KPI.
   - Escapar SIEMPRE con `esc(...)`.
   - **§16:** espaciado 4/8/12/16/24 · verde `#004236` · `tabular-nums` en la cifra ·
     transiciones ≤300ms `cubic-bezier(0.4,0,0.2,1)`.
3. Registrar en la cadena de `__cnPintarPanelCuant` (línea ~2981), **ANTES del fallback** (A-3):
```js
             : (panel.tipo === "cuant_dia")       ? __cnCuantDiaHtml(d)
```
4. `MainChat/templates/mainchat_layout.html:113` → subir el cache-buster de `?v=20260825c` a
   `?v=20260825d`. **Sin esto el navegador sirve el JS viejo y la tarjeta no aparece.**

---

### PASO 7 · Tests
**Archivo NUEVO:** `INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py`

Cubrir como mínimo:
1. `detectar_dia` — las 8 formas de V-2, **con** los tres negativos (acumulado / mes / rango).
2. `menciona_dia` — False en `"cuanto produjo en abril"` (garantiza que no se paga la consulta).
3. `_forma_no_soportada` vs `_forma_no_soportada_ranking` — **A-1**: `detectar("el 15 de mayo")`
   debe dar `None` en la de entidad y `"dia"` en la de ranking.
4. `ejecutar_n1d` / `ejecutar_n1dsel` con `_dia_fn` / `_curva_fn` **inyectados** (sin BD), incluyendo:
   fecha sin dato → rechazo cita el techo · blancos → rechazo por catálogo.
5. `formatear_cuerpo` con contratos N1D y N1DSEL — **A-4**: no debe lanzar `KeyError`.

---

## 9. VALIDACIONES

### V-A · Casos que deben RESPONDER (hoy rechazan)
| Pregunta | Esperado |
|---|---|
| `¿Cuánto produjo Castilla el 15 de mayo?` | **223.752 bbl**, viernes 15 de mayo de 2026, aviso sin-PPTO |
| `¿Cuál fue el volumen de Chichimene el 15?` | cifra del activo, `defaults_asumidos` declara el mes |
| `¿Mejor día de Castilla este mes?` | **sábado 2 de mayo de 2026, 226.644 bbl, 17 días con reporte** |
| `¿Peor día de Castilla en mayo?` | el mínimo de la curva (mismo mes) |

### V-B · Casos que deben RECHAZAR (con el motivo correcto)
| Pregunta | Esperado |
|---|---|
| `¿Cuánto produjo Castilla ayer?` | rechazo citando **"hasta el domingo 17 de mayo de 2026"** |
| `¿Cuántos blancos produjo Castilla el 15 de mayo?` | rechazo por catálogo (×2 irreconciliable) |
| `¿Cuánto produjo Castilla del 1 al 15?` | `rango_dias`, **sin cambio** |
| `¿Cuánto produjo Castilla esta semana?` | `semana`, **sin cambio** |
| **`top 5 campos el 15 de mayo`** | **rechazo `dia` (A-1) — NO el ranking del mes** |

### V-C · NO ROMPER (cifras idénticas a la línea base)
```
¿Cuánto crudo produjo Castilla?       → 6.860.389 bbl · 102.7% · Mayo 2026
¿Cuánto produjo Castilla en abril?    → 6.473.184 bbl · 103.5% · mes cerrado
¿Cuál es el acumulado del año…?       → 26.272.614 bbl · enero–abril
¿Cuánto produjo Castilla este mes?    → entidad CASTILLA (no CASTILLA ESTE)
acumulado hasta hoy                   → N2, NO grano día (guarda H4)
los 5 campos que más crudo producen   → ranking N5 normal
```

### V-D · Suite
```bash
cd INGESTA/Rep_Prod/backend
PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -3
```
**Debe mostrar EXACTAMENTE los 7 fallos preexistentes de §6** (más los tests nuevos en verde).
Un 8.º fallo = regresión → **DETENERSE**.

### V-E · Validación humana en navegador — **OBLIGATORIA** (§17.5 R3 / DT-15)
> *"Build verde + lint verde + tests verde ≠ feature verificada cuando hay interacción visual."*
> El executor **NO** puede declarar la feature completada. Solo el usuario.

1. Reiniciar **INGESTA (8088)** — el YAML y los módulos se cargan al arranque.
2. Recargar el navegador con **Ctrl+F5** (cache-buster nuevo).
3. Preguntar `¿Cuánto produjo Castilla el 15 de mayo?` → la tarjeta **no** debe mostrar anillo al 0%
   ni `NaN bbl` (eso significaría A-3/A-6 sin resolver).
4. Preguntar `¿Mejor día de Castilla este mes?` → sábado 2 de mayo.
5. **F12 Console: 0 errores.**

---

## 10. REGLAS NO NEGOCIABLES

1. **Prohibido fabricar presupuesto diario.** No existe (§3.3). Si no hay dato, se **declara**.
2. **`slots.py` sigue PURO** — sin imports de BD. El techo entra por parámetro (A-2).
3. **`ejecutor.py` no lleva SQL** — la frontera de `:11`. Todo SQL vive en `analisis/api.py`.
4. **No tocar** `desempeno` ni `_ambito`. Los helpers nuevos los **reusan**, no los modifican.
5. **La rama N1D va ANTES de N1** en `validador.formatear_cuerpo` (A-4).
6. **El tipo de panel se registra ANTES del fallback** en `multitab_shell.js` (A-3).
7. **`fmt_valor` para todo número.** Nunca formateo manual (regla D-N5).
8. **Fechas con tablas manuales.** Prohibido `strftime('%A')` y `locale.setlocale` (A-5).
9. **El rechazo cita el techo CONSULTADO**, jamás una fecha hardcodeada.
10. **No commit, no push.** Decide el usuario.

---

## 11. FUERA DE ALCANCE

- N2/N3/N4 a grano día (acumulado, serie o variación diaria).
- Ranking N5 a grano día (queda rechazado — A-1).
- Cualquier cambio a `desempeno`, `_ambito`, `ranking.py`, `niveles.py`, `no_soportado.py`, `maquina_q.py`.
- Jerarquizar, analizar, Test Clas, login, historial.
- Reformatear código existente.

---

## 12. PROMPT EXECUTOR

```
Eres un agente EXECUTOR. Lee COMPLETO el plan en
INGESTA/Rep_Prod/Planes/plan_cuantificar_grano_dia_2026-08-25.md
y ejecútalo AL PIE DE LA LETRA, en orden: PASO 1 → 2 → 3 → 4 → 5 → 6 → 7.

CONTEXTO (no tienes historial previo; todo lo que necesitas está en el plan)
- Raíz: c:\APLICACIONES\ProdIA\12112025_prodIA\ProdIA-2.0\ProdIA-2.0
- Backend FastAPI en INGESTA/Rep_Prod/backend · Front Flask + JS vanilla (NO hay Node)
- Python: INGESTA\Rep_Prod\backend\.venv\Scripts\python.exe
- Ejecuta SIEMPRE así:
    cd INGESTA/Rep_Prod/backend && PYTHONPATH="$PWD" ./.venv/Scripts/python.exe ...
- Comunicación y comentarios de código: 100% en ESPAÑOL.

REGLAS DURAS
1. NO modifiques el plan. Las decisiones están cerradas; tú solo implementas.
2. PRIMERO toma la línea base de §6 (pytest) y anótala. La suite final debe tener EXACTAMENTE
   los mismos 7 fallos preexistentes. Un 8.º = regresión → DETENTE y reporta.
3. Si cualquier verificación (V-1, V-2, V-A..V-D) falla, DETENTE y reporta. No improvises rodeos.
4. Respeta las 10 REGLAS NO NEGOCIABLES de §10. Las cuatro más fáciles de violar:
   · slots.py NO puede importar BD (el techo entra por parámetro).
   · ejecutor.py NO lleva SQL.
   · La rama N1D va ANTES de N1 en validador.formatear_cuerpo.
   · El tipo "cuant_dia" se registra ANTES del fallback en multitab_shell.js.
5. static/js/multitab_shell.js lo edita OTRA SESIÓN: corre `git status` antes de tocarlo. Si sale
   modificado, DETENTE y reporta. Si está limpio, AÑADE solo lo del PASO 6 y no reformatees nada.
6. PROHIBIDO fabricar un presupuesto diario. A grano día solo existe REAL.
7. Mide contra el motor real; no deduzcas del código. Si una cifra no la mediste, no la afirmes.
8. NO hagas commit ni push.
9. Al terminar NO declares la feature completada: queda PENDIENTE DE VALIDACIÓN HUMANA (V-E,
   regla §17.5 R3 / DT-15 de CLAUDE.md).

ARCHIVOS QUE PUEDES MODIFICAR (solo estos 8)
  1. INGESTA/Rep_Prod/backend/app/features/analisis/api.py                      (solo AÑADIR al final)
  2. INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/slots.py
  3. INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/ejecutor.py
  4. INGESTA/Rep_Prod/backend/app/features/consulta_v2/cuantificar/validador.py
  5. INGESTA/Rep_Prod/backend/app/features/consulta_v2/respuesta_cuantificar.py
  6. INGESTA/Rep_Prod/backend/tests/test_cuantificar_dia.py                      (CREAR)
  7. static/js/multitab_shell.js                                                 (solo AÑADIR)
  8. MainChat/templates/mainchat_layout.html                                     (solo el cache-buster)

REPORTA
- ✅/❌ por paso, con la SALIDA REAL de cada verificación (no la esperada).
- Las tablas V-A, V-B y V-C rellenas con lo que devolvió el motor.
- Línea base vs suite final, lado a lado.
- Aviso explícito: V-E (navegador) queda PENDIENTE del usuario.
```
