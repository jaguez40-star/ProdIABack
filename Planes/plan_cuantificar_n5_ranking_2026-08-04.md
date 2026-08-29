# Plan ejecutable — Motor Q v2 · CUANTIFICAR N5 (RANKING) · **v2 AUDITADO**

> **Modo:** ejecución literal por un agente sin contexto previo del repo. Todo lo necesario está aquí.
> **Fecha:** 2026-08-04 · **Planner:** Claude · **Flujo §0.2 aplicado al plan mismo (2 rondas).**
> **v2 corrige 6 defectos del v1**, 4 de ellos verificados contra la BD/código real, no de memoria.
> Ver §11 (registro de auditoría) — léelo: explica por qué el código está escrito así.

---

## 0. COBERTURA (§0.2 — prohibido reducir alcance en silencio)

| Forma | v1 (este plan) | Motivo del diferido |
|---|---|---|
| Ranking GLOBAL de **campos** (métrica REAL o gap; top/bottom) | ✅ ENTREGA | — |
| Ranking GLOBAL de **activos** (idem) | ✅ ENTREGA | — |
| Dirección **bottom** ("la más baja producción") | ✅ ENTREGA | — |
| Métrica **gap vs PPTO** (faltante / excedente) | ✅ ENTREGA | — |
| Ranking **dentro de una entidad** ("top campos DEL activo Castilla") | ⛔ DECLINA honesto | D-D5 colapsa Castilla→Campo (bug clase-APIAY S23). v2. |
| Ranking a nivel **gerencia / vicepresidencia** | ⛔ DECLINA honesto | Level-shift S28: `dim_fuente.gerencia` mezcla gerencias reales y VPs. v2. |
| Ranking a nivel **pozo** | ⛔ DECLINA honesto | El grano de pozo NO existe en `daily_report_prod` (S23). |
| Ranking por **cumplimiento-%** | ⛔ fuera | Decisión del usuario 2026-08-04. La query ya trae `vreal`/`vppto` → adición futura trivial. |

**Ninguna forma diferida se degrada en silencio a un ranking global**: cada una responde un rechazo
honesto que nombra la limitación (§5.3).

---

## 1. CONTEXTO

**Repo padre:** `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA` (Flask :8020, frontend).
**Sub-proyecto:** `INGESTA\Rep_Prod\backend\` (FastAPI, `uv`). Motor Q v2 en
`backend\app\features\consulta_v2\`.

**Qué es N5.** CUANTIFICAR tiene hoy 4 niveles TEMPORALES (N1 puntual · N2 acumulado · N3 serie ·
N4 variación), todos sobre **una entidad ya resuelta**. Preguntas como *"¿qué campo produce la mayor
cantidad de crudo?"* son un eje **ortogonal**: ordenan **varias** entidades por magnitud en un mes.
Hoy mueren en `respuesta_cuantificar.responder` porque no hay entidad que resolver (la entidad **es
la respuesta**). N5 = **RANKING**.

**Regla madre del proyecto:** *Python calcula y ordena; el LLM SOLO redacta el intro cordial.*

**Datos verificados contra la BD dev (2026-08-04) — son criterios de aceptación, no ilustración:**
- `core.fact_produccion_mes_ecp`, crudo REAL, `fecha = 2026-05-31` (último mes con REAL):
  **128 campos con producción > 0** · **15 campos en 0** · de los 128: **71 ECP, 46 terceros, 11 sin
  match en robustez**.
- TOP-5 crudo REAL: `RUBIALES 12.357.703 (ECOPETROL)` · `CASTILLA 6.860.389 (ECOPETROL)` ·
  **`QUIFA 6.240.197 (FRONTERA ENERGY)`** · `CAÑO SUR ESTE 5.853.678 (operador NULL)` ·
  `CAÑO LIMON 5.295.128 (operador NULL)`.
  → **El ranking DEBE incluir terceros con el operador rotulado.** Ocultarlos mentiría por omisión;
  presentarlos sin rótulo los haría pasar por Ecopetrol.
- `detectar_entidad()` devuelve **None** para las 5 preguntas de ranking global, y **CASTILLA** para
  las 2 scoped → el gate de "scoped declina" funciona y **no hay falsos positivos**.
- `nivel_dominio()` devuelve **`fuerte`** para las 5 preguntas reales (por "crudo"/"gas"/
  "presupuesto") → **enrutan directo, SIN escalar al LLM**. Solo *"top 5 campos este mes"* (sin
  producto) da `estructural` y escala.
- Ninguna palabra de ranking ni nombre de mes colisiona con el catálogo de entidades.

---

## 2. OBJETIVO

**Responden correctamente (Motor v2, chat de Consulta):**

| # | Pregunta | Resultado esperado |
|---|---|---|
| 1 | "¿Cuáles son los 5 campos que más crudo producen?" | top-5 campos, métrica real, dirección top |
| 2 | "¿Qué campo produce la mayor cantidad de crudo?" | top-**1** (singular) |
| 3 | "¿Qué campos tuvieron la más baja producción este mes?" | bottom-5, `real>0`, declara los sin registro |
| 4 | "Top 3 activos por producción de gas en mayo" | activos, top-3, gas, mes=mayo |
| 5 | "¿Qué campos se quedaron más cortos vs presupuesto?" | métrica **gap**, dirección **faltante** (gap más negativo primero) |

**Declinan honesto (NO degradan a global):**

| # | Pregunta | Motivo |
|---|---|---|
| 6 | "Ranking de pozos por producción en Castilla" | pozo sin dato |
| 7 | "¿Cuál gerencia produce más blancos?" | nivel gerencia diferido |
| 8 | "Top campos del activo Castilla" | scoped diferido |

---

## 3. PREREQUISITOS

- **Todos los comandos de backend** se ejecutan desde el directorio del backend con `PYTHONPATH`.
  Patrón exacto (Git Bash — el shell disponible; también hay PowerShell):
  ```bash
  cd "C:/APLICACIONES/ProdIA/12112025_prodIA/12112025_prodIA/INGESTA/Rep_Prod/backend"
  PYTHONPATH="$(pwd)" uv run python -m pytest tests/test_cuantificar.py -q
  ```
  Sin `PYTHONPATH` falla con `ModuleNotFoundError: No module named 'app'` (verificado).
- BD dev poblada. Conexión: `INGESTA/Rep_Prod/.env` → `DATABASE_URL` (localhost, `daily_report_prod`).
- **REGLA DE RAM (no negociable):** en dev SOLO chequeos estáticos — `py_compile`, `node --check`,
  `pytest`, golden runner, consultas SQL puntuales en proceso aislado. **NO** levantar backend,
  **NO** Ollama, **NO** navegador. El runtime/LLM/navegador los verifica el usuario en el servidor
  de pruebas tras `push`.
- **NO tocar `consulta/`** (v1 congelada). N5 vive 100% en `consulta_v2/`.

---

## 4. INVENTARIO DE ARCHIVOS

`BE = ...\INGESTA\Rep_Prod\backend` · `ROOT = C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA`

| # | Acción | Archivo | Nota |
|---|---|---|---|
| A1 | **NUEVO** | `BE\app\features\consulta_v2\cuantificar\ranking.py` | el motor N5 |
| A2 | MODIFICA | `BE\app\features\consulta_v2\respuesta_cuantificar.py` | fork de entrada |
| A3 | MODIFICA | `BE\app\features\consulta_v2\config\patrones_grupo.yaml` | patrones genéricos |
| A4 | MODIFICA | `BE\app\features\consulta_v2\config\variables_cuantificables.yaml` | doc del contrato |
| A5 | **NUEVO** | `BE\tests\test_cuantificar_ranking.py` | tests |
| A6 | MODIFICA | `BE\app\features\consulta_v2\golden\cuantificar_golden.yaml` | casos N5 |
| A7 | MODIFICA | `ROOT\static\js\multitab_shell.js` | rama `cuant_rank` **(obligatoria)** |
| A8 | MODIFICA | `ROOT\static\css\colapsable.css` | `.cn-rank*` |
| A9 | MODIFICA | `ROOT\templates\main.html` | cache-buster |

> **`maquina_q.py` NO se toca.** El v1 proponía editarlo; la auditoría demostró que es innecesario
> (§11 · D4).

---

## 5. ESPECIFICACIÓN

### 5.1 · A1 — NUEVO `cuantificar/ranking.py`

Crea el archivo con **exactamente** este contenido:

```python
"""cuantificar/ranking.py — N5 RANKING (Motor Q v2, Grupo 2).

Eje ORTOGONAL a N1-N4: N1-N4 miden UNA entidad a lo largo del tiempo; N5 ordena VARIAS entidades por
magnitud dentro de un mes. FB-1 (patrón de Analizar Fase 2): PORTA su propia query sobre
core.fact_produccion_mes_ecp. NO importa `analisis.api._gap_campo` (es una closure dentro de
`ejecutivo()`, no reutilizable) ni reusa `desempeno` (que es por-entidad).

v1: SOLO ranking GLOBAL ECP; niveles rankeables campo y activo. Scoped-a-entidad y niveles
gerencia/VP/pozo DECLINAN honesto (el dispatcher los corta antes de llegar aquí).

🔑 SEMÁNTICA DE ORDEN (bug real del plan v1, corregido). NO se modela como (eje, asc/desc): esa
combinación devolvía lo CONTRARIO a lo pedido en "qué campos se quedaron más cortos vs presupuesto"
(daba los que SUPERARON el presupuesto). Se modela como (metrica, direccion) con reglas explícitas:
  metrica=real · direccion=top     -> REAL descendente          ("los que más producen")
  metrica=real · direccion=bottom  -> REAL ascendente, real>0    ("la más baja producción")
  metrica=gap  · direccion=bottom  -> gap ASCENDENTE (más negativo primero) = MAYOR FALTANTE  [DEFAULT]
  metrica=gap  · direccion=top     -> gap DESCENDENTE (más positivo primero) = MAYOR EXCEDENTE
En metrica=gap el DEFAULT es `bottom` (faltante): es la intención dominante. "mayor faltante" debe dar
faltante aunque diga "mayor" -> por eso las palabras de faltante MANDAN sobre "MAYOR".

Terceros: el reporte incluye campos operados por terceros (QUIFA/Frontera es #3 en crudo-mayo,
verificado contra BD 2026-08-04). Se INCLUYEN y se ROTULA el operador cuando no es Ecopetrol.

Regla madre: Python calcula y ordena; el LLM solo el intro. La lista es VERBATIM.
"""
import calendar
import re

import sqlalchemy as sa

from app.core.db import get_engine
from app.features.consulta_v2.normaliza import norm
from app.features.consulta_v2.cuantificar.validador import fmt_valor

# --- Vocabulario de detección (sobre texto NORMALIZADO: MAYÚSCULAS sin tildes) ---------------
_SUPERLATIVO = ("MAYOR", "MENOR", "MAS", "MENOS", "TOP", "RANKING", "MAXIMA", "MAXIMO",
                "MINIMA", "MINIMO", "MEJORES", "PEORES", "MEJOR", "PEOR", "PRIMEROS", "ULTIMOS")
_NIVEL_TOK = {"CAMPO": "campo", "CAMPOS": "campo", "ACTIVO": "activo", "ACTIVOS": "activo",
              "GERENCIA": "gerencia", "GERENCIAS": "gerencia",
              "VICEPRESIDENCIA": "vicepresidencia", "VICEPRESIDENCIAS": "vicepresidencia",
              "POZO": "pozo", "POZOS": "pozo"}

# Dirección BOTTOM. Token exacto (AF-3.7: nunca substring — "BAJO" ∈ "trabajo").
_BOTTOM_TOK = ("MENOR", "MENOS", "PEOR", "PEORES", "MINIMA", "MINIMO", "BAJA", "BAJO", "BAJAS",
               "CORTO", "CORTOS", "CORTAS", "FALTANTE", "FALTANTES", "REZAGADOS", "REZAGADO",
               "INCUMPLIERON", "ULTIMOS")
_BOTTOM_PHRASE = ("LOS QUE MENOS", "POR DEBAJO", "QUEDARON CORTOS", "DE ABAJO")
# Dirección TOP explícita en métrica gap (excedente). Sin esto, gap = faltante por defecto.
_TOP_GAP_TOK = ("SUPERARON", "SUPERO", "EXCEDIERON", "EXCEDENTE", "EXCEDIO", "SOBRECUMPLIERON")
_TOP_GAP_PHRASE = ("POR ENCIMA",)

# Métrica gap. 🔑 SIN "META": 'META\b' es patrón del grupo ANALIZAR y gana por precedencia_colision
# (analizar > cuantificar) → una pregunta con "meta" nunca llega aquí. Incluirla crearía la ilusión
# de soporte. Ver §11 · D6.
_METRICA_GAP = ("PPTO", "PRESUPUESTO", "FALTANTE", "FALTANTES", "CORTO", "CORTOS", "CORTAS",
                "EXCEDENTE", "INCUMPLIERON", "SUPERARON")

_PROD_TOK = {"GAS": "gas", "BLANCOS": "blancos", "BLANCO": "blancos"}   # crudo = default
_MESES = ("enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
          "octubre noviembre diciembre").split()
_MES_NUM = {m: i + 1 for i, m in enumerate(_MESES)}
_MES_NUM["setiembre"] = 9
_PROD_MAP = {"crudo": "CRUDO", "gas": "GAS", "blancos": "BLANCOS"}
_PUNCT = "¿?¡!.,;:()[]{}\"'`"

_NIVEL_DIFERIDO = {
    "gerencia": ("El ranking por gerencia llega en una próxima fase: en la jerarquía oficial "
                 "(robustez) varias «gerencias» del reporte son en realidad vicepresidencias, y "
                 "compararlas sin reconciliar mezclaría niveles distintos. Puedo rankear campos o "
                 "activos."),
    "vicepresidencia": ("El ranking por vicepresidencia llega en una próxima fase. Puedo rankear "
                        "campos o activos."),
    "pozo": ("No puedo rankear pozos: el grano de pozo no está en el reporte diario, que llega "
             "hasta el detalle por campo. Puedo rankear campos o activos."),
}
_NIVEL_PLURAL = {"campo": "campos", "activo": "activos"}


def _tokens(t: str) -> set:
    return {p for p in (w.strip(_PUNCT) for w in t.split()) if p}


def detectar(texto: str):
    """Reconoce la FORMA N5 (determinista, sin LLM y sin BD). Devuelve dict o None.

    dict = {nivel_ranking, metrica, direccion, top_n, producto, periodo_texto}
           o {nivel_ranking, diferido: str} si el nivel pedido no se rankea en v1.
    Exige SUPERLATIVO **y** sustantivo de NIVEL: sin ambos no es N5 y la pregunta sigue su curso
    normal por N1-N4 (p.ej. "¿cuál es la mayor producción de Rubiales?" -> N1 de Rubiales).
    """
    t = norm(texto or "")
    toks = _tokens(t)
    if not (any(s in toks for s in _SUPERLATIVO) or "TOP" in t or "RANKING" in t):
        return None
    nivel = next((_NIVEL_TOK[k] for k in _NIVEL_TOK if k in toks), None)
    if nivel is None:
        return None
    if nivel in _NIVEL_DIFERIDO:
        return {"nivel_ranking": nivel, "diferido": _NIVEL_DIFERIDO[nivel]}

    metrica = "gap" if any(k in toks for k in _METRICA_GAP) else "real"
    es_bottom = any(k in toks for k in _BOTTOM_TOK) or any(p in t for p in _BOTTOM_PHRASE)
    if metrica == "gap":
        # DEFAULT bottom (faltante). Solo palabras explícitas de excedente lo suben a top.
        es_top_gap = (any(k in toks for k in _TOP_GAP_TOK)
                      or any(p in t for p in _TOP_GAP_PHRASE))
        direccion = "top" if (es_top_gap and not es_bottom) else "bottom"
    else:
        direccion = "bottom" if es_bottom else "top"

    m = re.search(r"\bTOP\s+(\d+)\b", t) or re.search(r"\b(\d+)\s+(?:CAMPOS?|ACTIVOS?)\b", t)
    if m:
        top_n = max(1, min(20, int(m.group(1))))
    else:
        singular = (("CAMPO" in toks and "CAMPOS" not in toks)
                    or ("ACTIVO" in toks and "ACTIVOS" not in toks))
        top_n = 1 if singular else 5

    producto = next((_PROD_TOK[k] for k in _PROD_TOK if k in toks), "crudo")
    per = next((mm for mm in _MESES if mm in (texto or "").lower()), None)
    return {"nivel_ranking": nivel, "metrica": metrica, "direccion": direccion,
            "top_n": top_n, "producto": producto, "periodo_texto": per}


def _fin_mes(c, periodo_texto):
    """(fin, anio, mes, nombre_mes, es_proyeccion) del mes a rankear, o None si no hay datos.
    Default = último mes con REAL. es_proyeccion: el mes elegido es el del último dato diario y ese
    corte no llega a fin de mes (S22: el REAL del mes en curso es un cierre PROYECTADO)."""
    maxreal = c.execute(sa.text("""
        SELECT MAX(m.fecha) FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
        WHERE es.nombre = 'REAL'""")).scalar()
    if maxreal is None:
        return None
    anio, mes = maxreal.year, maxreal.month
    if periodo_texto and periodo_texto in _MES_NUM:
        mes = _MES_NUM[periodo_texto]
    dim = calendar.monthrange(anio, mes)[1]
    fin = f"{anio:04d}-{mes:02d}-{dim:02d}"
    maxdia = c.execute(sa.text("SELECT MAX(fecha) FROM core.fact_produccion_dia_ecp")).scalar()
    es_proy = bool(maxdia and maxdia.year == anio and maxdia.month == mes and maxdia.day < dim)
    return fin, anio, mes, _MESES[mes - 1], es_proy


# nivel_ranking -> SQL. Mismo fact que el resto de Cuantificar. Solo campo/activo en v1.
# 🔑 El nivel `activo` NO inventa operador (el v1 hardcodeaba 'ECOPETROL' sin verificarlo): devuelve
# NULL y el formateador simplemente no rotula operador a nivel activo. Ver §11 · D5.
_SQL = {
    "campo": """
        SELECT COALESCE(NULLIF(TRIM(f.campo),''), f.nombre) AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               MAX(f.operador) AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
    "activo": """
        SELECT a.activo AS ent,
               SUM(CASE WHEN es.nombre='REAL' THEN m.volumen ELSE 0 END) AS vreal,
               SUM(CASE WHEN es.nombre='PPTO' THEN m.volumen ELSE 0 END) AS vppto,
               NULL AS operador
        FROM core.fact_produccion_mes_ecp m
        JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
        JOIN core.dim_escenario es     ON es.escenario_id     = m.escenario_id
        JOIN core.dim_fuente f         ON f.fuente_id         = m.fuente_id
        JOIN core.map_campo_activo a
             ON a.campo_norm = UPPER(COALESCE(NULLIF(TRIM(f.campo),''), f.nombre))
        WHERE m.fecha = :fin AND tp.nombre = :prod AND es.nombre IN ('REAL','PPTO')
        GROUP BY 1""",
}


def calcular(slots: dict, _engine=None) -> dict:
    """Ejecuta el ranking. Devuelve el contrato N5 (aplica=True) o {aplica:False, texto}."""
    nivel = slots.get("nivel_ranking")
    if nivel not in _SQL:
        return {"aplica": False, "texto": slots.get("diferido", "Ese ranking no está soportado.")}
    prod = slots.get("producto", "crudo")
    prod_es = _PROD_MAP.get(prod, "CRUDO")
    unidad = "MSCF" if prod == "gas" else "bbl"
    metrica, direccion, top_n = slots["metrica"], slots["direccion"], slots["top_n"]
    plural = _NIVEL_PLURAL[nivel]

    eng = _engine or get_engine()
    with eng.connect() as c:
        info = _fin_mes(c, slots.get("periodo_texto"))
        if info is None:
            return {"aplica": False, "texto": "No hay datos de producción cargados para rankear."}
        fin, anio, mes, nombre_mes, es_proy = info
        rows = c.execute(sa.text(_SQL[nivel]), {"fin": fin, "prod": prod_es}).all()

    datos = [((r[0] or "").strip(), float(r[1] or 0), float(r[2] or 0),
              (r[3] or "").strip() if r[3] else "")
             for r in rows if (r[1] or r[2])]
    con_real = [d for d in datos if d[1] > 0]          # CERO TRAICIONERO: 0 no es "poca producción"
    sin_registro = len(datos) - len(con_real)

    # GUARDA de resultado vacío (el v1 no la tenía → habría dicho "Los 0 campos…"). Ver §11 · D3.
    if not con_real:
        return {"aplica": False, "texto": (
            f"No hay producción de {prod} registrada en {nombre_mes} {anio} para rankear {plural}.")}

    if metrica == "gap":
        pool = [d for d in con_real if (d[1] - d[2]) != 0]
        clave = lambda d: d[1] - d[2]
        # bottom = gap ascendente (más negativo primero = mayor faltante); top = descendente.
        reverse = (direccion == "top")
    else:
        pool = con_real
        clave = lambda d: d[1]
        reverse = (direccion == "top")
    if not pool:
        return {"aplica": False, "texto": (
            f"Todos los {plural} con producción de {prod} en {nombre_mes} {anio} coinciden con su "
            f"presupuesto; no hay faltantes ni excedentes que rankear.")}

    ordenado = sorted(pool, key=clave, reverse=reverse)
    top = ordenado[:top_n]

    # Concentración: SOLO tiene sentido en métrica real + dirección top ("los que más producen
    # concentran X%"). En bottom sería una cifra engañosa. Ver §11 · D7.
    conc = None
    if metrica == "real" and direccion == "top":
        total_real = sum(d[1] for d in con_real)
        if total_real:
            conc = round(sum(d[1] for d in top) / total_real * 100, 1)

    def _op(operador):
        o = (operador or "").upper()
        if not o:
            return {"txt": None, "es_ecp": None}          # operador desconocido: no se afirma nada
        if "ECOPETROL" in o or o == "ECP":
            return {"txt": None, "es_ecp": True}          # ECP = lo normal, sin rótulo
        return {"txt": operador.title(), "es_ecp": False}

    items = []
    for i, d in enumerate(top, 1):
        ol = _op(d[3]) if nivel == "campo" else {"txt": None, "es_ecp": None}
        items.append({"pos": i, "entidad": d[0], "valor": round(d[1]), "ppto": round(d[2]),
                      "gap": round(d[1] - d[2]), "operador": ol["txt"], "es_ecp": ol["es_ecp"]})

    return {
        "aplica": True, "grupo": "cuantificar", "nivel": "N5",
        "nivel_ranking": nivel, "metrica": metrica, "direccion": direccion, "top_n": top_n,
        "producto": prod, "unidad": unidad,
        "periodo_label": f"{nombre_mes} {anio}", "es_proyeccion": es_proy,
        "items": items, "total_universo": len(pool), "sin_registro": sin_registro,
        "concentracion_pct": conc,
    }


def formatear_cuerpo(res: dict) -> str:
    """Cuerpo VERBATIM (Python; el LLM no lo toca)."""
    plural = _NIVEL_PLURAL[res["nivel_ranking"]]
    prod, unidad = res["producto"], res["unidad"]
    n = len(res["items"])
    proy = " (cierre proyectado del mes en curso)" if res["es_proyeccion"] else ""

    if res["metrica"] == "gap":
        que = "mayor faltante" if res["direccion"] == "bottom" else "mayor excedente"
        cab = (f"{'El' if n == 1 else 'Los'} {n if n > 1 else ''} {plural if n > 1 else plural[:-1]} "
               f"con {que} de {prod} frente al presupuesto en {res['periodo_label']}{proy}").replace("  ", " ")
        piezas = []
        for it in res["items"]:
            signo = "−" if it["gap"] < 0 else "+"
            op = f" [{it['operador']}]" if it["operador"] else ""
            piezas.append(f"{it['pos']}) {it['entidad']}{op} {signo}{fmt_valor(abs(it['gap']), prod)}")
    else:
        que = "mayor producción" if res["direccion"] == "top" else "menor producción"
        cab = (f"{'El' if n == 1 else 'Los'} {n if n > 1 else ''} {plural if n > 1 else plural[:-1]} "
               f"de {que} de {prod} en {res['periodo_label']}{proy}").replace("  ", " ")
        piezas = []
        for it in res["items"]:
            op = f" [{it['operador']}]" if it["operador"] else ""
            piezas.append(f"{it['pos']}) {it['entidad']}{op} {fmt_valor(it['valor'], prod)}")

    linea = f"{cab}: " + " · ".join(piezas) + f" {unidad}."
    # Huella (regla "no silent caps"): universo + cola.
    linea += f" Sobre {res['total_universo']} {plural} con producción registrada"
    if res["concentracion_pct"] is not None:
        linea += f"; {'concentra' if n == 1 else 'concentran'} el {res['concentracion_pct']}% del total"
    linea += "."
    if res["direccion"] == "bottom" and res["metrica"] == "real" and res["sin_registro"]:
        linea += (f" ⚠️ Además hay {res['sin_registro']} {plural} sin registro REAL este mes "
                  f"(paro o dato faltante — a grano mes no son distinguibles); no se listan.")
    if res["nivel_ranking"] == "campo" and any(it["es_ecp"] is False for it in res["items"]):
        linea += " Los campos entre corchetes son operados por terceros."
    return linea
```

### 5.2 · A3 — `patrones_grupo.yaml`

En `grupos:` → `cuantificar:`, **añade al final de la lista** (después de
`'PROMEDIO\s+(DE|DIARIO|MENSUAL)'`):

```yaml
    # N5 RANKING (2026-08-04). GENÉRICOS a propósito (NO van a patrones_anclados): así pasan por el
    # filtro de dominio y exigen entidad O vocabulario. Verificado 2026-08-04: las preguntas reales
    # ("…más CRUDO…", "…de GAS…", "…vs PRESUPUESTO") dan nivel_dominio='fuerte' → enrutan DIRECTO sin
    # LLM. Anclarlas repetiría el error del 2026-08-02 ("mejores campos de la dieta mediterránea").
    - 'TOP\s+\d+'
    - 'RANKING\b'
    - '(MAYOR|MENOR|MAS|MENOS)\s+(CANTIDAD|PRODUCCION|VOLUMEN)'
    - '(PRODUCE|PRODUJO|PRODUCEN|PRODUJERON)\s+(MAS|MENOS)\b'
    - '(MAS|MENOS)\s+(CRUDO|GAS|BLANCOS)\b'
    - '(MEJORES|PEORES)\s+(CAMPOS?|ACTIVOS?)'
    - 'MAS\s+(ALTA|BAJA)\s+PRODUCCION'
    - 'QUEDARON\s+(MAS\s+)?CORTOS'
```

**NO tocar** `precedencia_colision`, `precedencia_maxima` ni `patrones_anclados`.
Consecuencia deseada: si la pregunta trae además un patrón de `analizar` (`POR QUE`, `DETRACTORES`,
`META`), gana **analizar** — correcto, esa pregunta es causal, no un ranking.

### 5.3 · A2 — `respuesta_cuantificar.py` (fork de entrada)

**(a) Import** — añádelo junto a los otros imports del módulo:
```python
from app.features.consulta_v2.cuantificar import ranking as _ranking
```

**(b) Constante** — junto a `_CIERRE`:
```python
_CIERRE_RANK = "Si quieres, te lo doy por otro producto o cambiando el orden."
```
> No termina en pregunta sí/no: un "sí" caería en el drill `_AFIRM` de `maquina_q._continuacion` y
> devolvería un acumulado. Misma regla H1 que `no_soportado.mensaje`.

**(c) Fork** — es la **primera** sentencia ejecutable de `responder()`, inmediatamente después del
docstring y **antes** de `resuelta = _resolver.resolver_unico(entidad or texto)`:

```python
    # ── N5 RANKING (eje ortogonal) ────────────────────────────────────────────────────────────
    # Va ANTES del resolver: el ranking global NO tiene entidad de entrada (la entidad es la
    # RESPUESTA) y moriría en la guarda "no identifiqué una entidad".
    rk = _ranking.detectar(texto)
    if rk is not None:
        # (1) Formas de periodo no soportadas ANTES de calcular: si este check quedara después del
        #     fork, "top campos del primer trimestre" se degradaría al mes en silencio (bug #5,
        #     cerrado el 2026-08-03 — no puede reabrirse por esta ruta).
        forma = _forma_no_soportada(texto)
        if forma:
            return {"mensaje": _no_soportado.mensaje(forma, "ese ranking"), "panel": None}
        # (2) Nivel no rankeable en v1 (gerencia/vicepresidencia/pozo) → declina honesto.
        if rk.get("diferido"):
            return {"mensaje": rk["diferido"], "panel": None}
        # (3) v1 = SOLO global. Si el texto nombra una entidad-contenedor, se declina el scoped:
        #     D-D5 colapsa nombres duales a Campo (Castilla → Campo, no Activo) y "los campos de un
        #     campo" no existe. Verificado 2026-08-04: detectar_entidad da None en las preguntas
        #     globales y CASTILLA en las scoped → este gate no produce falsos positivos.
        _hit = _resolver.buscar_en_texto(texto)
        ent_det = entidad or (_hit[0] if _hit else None)
        if ent_det and _resolver.resolver_unico(ent_det) is not None:
            return {"mensaje": (
                f"El ranking DENTRO de «{ent_det}» llega en una próxima fase. Por ahora puedo "
                f"rankear sobre toda la operación —por ejemplo, «los 5 campos que más "
                f"{rk['producto']} producen»."), "panel": None}
        # (4) Calcular → cuerpo VERBATIM + intro cordial + cierre.
        res = _ranking.calcular(rk)
        if not res.get("aplica"):
            return {"mensaje": res.get("texto", "No pude construir ese ranking."), "panel": None}
        cuerpo = _ranking.formatear_cuerpo(res)
        mensaje = respuesta_base.envolver(_intro_ranking(res, usuario), cuerpo, _CIERRE_RANK)
        return {"mensaje": mensaje, "panel": {"tipo": "cuant_rank", "datos": _panel_rank(res)}}
```

**(d) Helpers** — al final del módulo:
```python
def _intro_ranking(res: dict, usuario) -> str:
    """Intro cálido validado. Mismo contrato mecánico que _intro (sin dígitos ni unidades)."""
    if not _s.consulta_cuant_llm:
        return ""
    plural = {"campo": "campos", "activo": "activos"}[res["nivel_ranking"]]
    prompt = PROMPT_CUANT.format(entidad=f"un ranking de {plural} por producción de {res['producto']}",
                                 usuario=usuario or "el usuario")
    for _ in range(2):
        cand = respuesta_base.intro_llm(prompt, True)
        if not cand:
            return ""
        if _validador.intro_valido(cand):
            return cand
    return ""


def _panel_rank(res: dict) -> dict:
    """Datos del panel derecho del ranking (doble entregable HD4)."""
    return {k: res[k] for k in ("nivel_ranking", "metrica", "direccion", "producto", "unidad",
                                "periodo_label", "es_proyeccion", "items", "total_universo",
                                "sin_registro", "concentracion_pct")}
```

**No modifiques nada más** de `responder()`: el flujo N1-N4 queda intacto debajo del fork.

### 5.4 · A7/A8/A9 — Frontend **(obligatorio en el MISMO commit)**

🔴 **Contrato roto si se omite.** El dispatch de paneles en
`ROOT\static\js\multitab_shell.js` **línea ~2413** tiene *fall-through* por defecto:
```js
var body = (panel.tipo === "cuant_serie") ? __cnCuantSerieHtml(d)
         : (panel.tipo === "cuant_var")   ? __cnCuantVarHtml(d)
         : __cnCuantCardHtml(d);            // ← DEFAULT
```
Un `tipo:"cuant_rank"` **sin rama nueva** cae en `__cnCuantCardHtml`, que espera campos de KPI
(`real`, `ppto`, `cumplimiento_pct`, `estado`) que el ranking **no tiene** → panel roto/basura
silenciosa. Por eso:

**A7 (`multitab_shell.js`):**
1. En `__cnPintarPanelCuant`, añade la rama **antes** del default:
   ```js
   var body = (panel.tipo === "cuant_serie") ? __cnCuantSerieHtml(d)
            : (panel.tipo === "cuant_var")   ? __cnCuantVarHtml(d)
            : (panel.tipo === "cuant_rank")  ? __cnCuantRankHtml(d)
            : __cnCuantCardHtml(d);
   ```
2. Crea `__cnCuantRankHtml(d)` **usando `__cnCuantSerieHtml` (línea ~2426) como molde** — cópiala y
   adáptala. Debe usar los helpers ya existentes:
   `var esGas = (d.producto === "gas"); var fmtV = esGas ? __cnGasM : function(v){return __cnMilesEC(Math.round(v));}`
   y `esc()` para todo texto que venga de la BD. Contenido:
   - **Título:** `{campo:"Campos", activo:"Activos"}[d.nivel_ranking]` + " · " + producto + " · " +
     `d.periodo_label`; si `d.es_proyeccion`, chip "cierre proyectado".
   - **Lista** `d.items`: `it.pos) it.entidad — fmtV(it.metrica==="gap" ? it.gap : it.valor) + unidad`.
     Si `it.operador` → texto gris pequeño; si `it.es_ecp === false` → badge "tercero".
   - **Pie:** `Sobre {d.total_universo} con producción` + (si `d.concentracion_pct`)
     `· top concentra {}%` + (si `d.direccion==="bottom" && d.sin_registro`) la nota de sin-registro.

**A8 (`colapsable.css`):** clases NUEVAS `.cn-rank`, `.cn-rank__item`, `.cn-rank__pos`,
`.cn-rank__op`, `.cn-rank__badge`, espejando el estilo de las `.cn-cuant*` existentes. Cero colisión.

**A9 (`main.html`):** sube el `?v=` de `multitab_shell.js` **y** de `colapsable.css` a `20260804a1`.

> **Si por cualquier razón A7 no se puede completar:** cambia el `return` del fork a
> `"panel": None`. `panel=None` es legal (HD4: aditivo; jerarquizar/OUT lo usan). **Nunca** enviar
> `cuant_rank` sin su rama.

### 5.5 · A4 — `variables_cuantificables.yaml` (documentación del contrato)

Añade al final:
```yaml
# ===========================================================================
# NIVEL N5 — RANKING (2026-08-04) · eje ORTOGONAL a N1-N4
# ===========================================================================
ranking:
  descripcion: "Ordena VARIAS entidades por magnitud dentro de un mes. v1 = GLOBAL ECP."
  niveles_rankeables: [campo, activo]     # gerencia/VP diferidos (level-shift S28); pozo sin dato
  metricas: [real, gap]                   # cumplimiento-% fuera (la query ya trae vreal/vppto)
  direcciones: [top, bottom]
  semantica_gap: "bottom = mayor FALTANTE (gap más negativo) y es el DEFAULT; top = mayor EXCEDENTE.
                  NO se modela como asc/desc: esa forma devolvía lo contrario a lo pedido."
  top_n_default: 5                        # singular ('qué campo') = 1; máx 20
  terceros: "INCLUIDOS en ranking de campo, con operador rotulado si no es Ecopetrol (verificado
             contra BD 2026-08-04: QUIFA/Frontera es #3 en crudo-mayo). El nivel activo no rotula
             operador (map_campo_activo no lo modela)."
  bottom_n: "filtra real>0 y DECLARA los N sin registro (paro o hueco: a grano mes no distinguibles)."
  proyeccion: "el mes en curso se rankea por cierre PROYECTADO (T-1) y se rotula."
  scoped_diferido: "ranking dentro de una entidad ('top campos del activo X') -> v2 (D-D5)."
```

---

## 6. ORDEN DE EJECUCIÓN

1. **A1** `ranking.py` → `py_compile`.
2. **A3** patrones YAML.
3. **A2** fork → `py_compile`.
4. **A4** doc YAML.
5. **A5** tests + **A6** golden.
6. **Validaciones §8 de backend** (V-COMPILE, V-DETECT, V-CALC, V-CLAS, V-GOLDEN, V-REGR, V-CLASREGR).
   🔴 **Si alguna falla, DETENTE y reporta. No continúes al frontend.**
7. **A7/A8/A9** frontend → `node --check`.
8. `git add -A` → `commit` → `push`. Backend y frontend **en el mismo commit**.
9. El usuario verifica en el servidor de pruebas (navegador + gemma4). No se verifica en dev.

---

## 7. REGLAS NO NEGOCIABLES

1. **Python calcula y ordena; el LLM SOLO el intro.** La lista es VERBATIM de `formatear_cuerpo`.
   El intro pasa por `_validador.intro_valido` o se descarta.
2. **NO tocar** `consulta/` (v1 congelada), `maquina_q.py`, `desempeno`, `_ambito`, `_gap_campo`,
   `ejecutor.py`, `slots.py`, `dominio.py`, `clasificador_llm.py`, `precedencia_*`, `patrones_anclados`.
3. **NO degradar en silencio.** Periodo no soportado, nivel diferido y scoped → rechazo honesto
   explícito, nunca un ranking global "parecido".
4. **Terceros incluidos y rotulados.** Prohibido ocultarlos; prohibido presentarlos como Ecopetrol.
5. **`real > 0` en dirección bottom**, y declarar los sin registro (CERO TRAICIONERO: 0 ≠ sin dato).
6. **Mes en curso = cierre proyectado**, siempre rotulado.
7. **Huella siempre**: "sobre N campos con producción registrada".
8. **Métrica gap: bottom = faltante y es el default.** Un "más cortos" que devuelva excedentes es el
   fallo exacto que este plan corrige.
9. **Frontend en el mismo commit**, o `panel: None`.
10. **Solo chequeos estáticos en dev** (regla de RAM). Sin backend/Ollama/navegador local.

---

## 8. VALIDACIONES (comando → resultado esperado)

Desde `BE`, con `PYTHONPATH="$(pwd)"`.

**V-COMPILE**
```bash
uv run python -m py_compile app/features/consulta_v2/cuantificar/ranking.py \
  app/features/consulta_v2/respuesta_cuantificar.py
```
→ exit 0, sin salida.

**V-DETECT** — `A5` (`tests/test_cuantificar_ranking.py`), puro, sin BD:

| Texto | Esperado |
|---|---|
| `"cuales son los 5 campos que mas crudo producen"` | `nivel_ranking=campo, metrica=real, direccion=top, top_n=5, producto=crudo` |
| `"que campo produce la mayor cantidad de crudo"` | `top_n=1` (singular) |
| `"que campos tuvieron la mas baja produccion este mes"` | `direccion=bottom, metrica=real` |
| `"top 3 activos por produccion de gas en mayo"` | `nivel_ranking=activo, top_n=3, producto=gas, periodo_texto="mayo"` |
| `"que campos se quedaron mas cortos vs presupuesto"` | **`metrica=gap, direccion=bottom`** ← el bug del v1 |
| `"que campos tienen mayor faltante vs presupuesto"` | **`metrica=gap, direccion=bottom`** (faltante manda sobre "mayor") |
| `"que campos superaron el presupuesto"` | `metrica=gap, direccion=top` |
| `"ranking de pozos por produccion en Castilla"` | `"diferido" in res` |
| `"cual gerencia produce mas blancos"` | `"diferido" in res` |
| `"cuanto crudo produjo Rubiales"` | `None` (sin superlativo → no es N5) |
| `"cual es la mayor produccion de Rubiales"` | `None` (sin sustantivo de nivel → sigue a N1) |

**V-CALC** — contra BD dev; usa un helper `_engine_o_skip()` (si la BD no responde, `pytest.skip`),
mismo patrón que `tests/test_puente_gerencia_vp.py`:
- `calcular({nivel_ranking:"campo", metrica:"real", direccion:"top", top_n:5, producto:"crudo", periodo_texto:None})`
  → `items[0]["entidad"] == "RUBIALES"` · `items[0]["valor"] == 12357703` · `len(items) == 5` ·
  `items[2]["entidad"] == "QUIFA"` con `es_ecp is False` y `"Frontera" in items[2]["operador"]` ·
  `total_universo == 128` · `concentracion_pct` no es None.
- idem con `direccion:"bottom"` → **todos** los `items[i]["valor"] > 0` · `sin_registro >= 15` ·
  `concentracion_pct is None`.
- `metrica:"gap", direccion:"bottom"` → `items[0]["gap"] < 0` y la serie de `gap` es **no
  decreciente** (`all(items[i]["gap"] <= items[i+1]["gap"])`).
- `metrica:"gap", direccion:"top"` → `items[0]["gap"] > 0`.
- `nivel_ranking:"activo", producto:"gas"` → `len(items) >= 1` y todos `operador is None`.

**V-CLAS**
```bash
uv run python -c "from app.features.consulta_v2.patrones import clasificar_capa1 as f; \
[print(q[:44], '->', f(q)[0]) for q in [ \
'cuales son los 5 campos que mas crudo producen', \
'que campo produce la mayor cantidad de crudo', \
'que campos tuvieron la mas baja produccion este mes', \
'top 3 activos por produccion de gas en mayo', \
'que campos se quedaron mas cortos vs presupuesto']]"
```
→ los **5** imprimen `cuantificar`.
*(Baseline verificado hoy ANTES del cambio: 3 de esos 5 daban `None`.)*

**V-GOLDEN** — `A6`: añade a `cuantificar_golden.yaml` los 5 casos de §2 + 1 diferido.
```bash
uv run python app/features/consulta_v2/golden/run_golden_cuantificar.py
```
→ ≥90% global, casos N5 en verde.

**V-REGR**
```bash
uv run python -m pytest tests/test_cuantificar.py tests/test_cuantificar_rango.py -q
```
→ **0 fallos nuevos** respecto al baseline. **Captura el baseline ANTES de editar nada.**

**V-CLASREGR**
```bash
uv run python -m pytest tests/test_consulta_v2_clasificador.py tests/test_conteo_jerarquia.py -q
```
→ 0 fallos nuevos (los patrones N5 no roban preguntas de otros grupos).

**V-MEM** (regresión de memoria conversacional, §11 · D4) — con BD:
`clasificar("cuales son los 5 campos que mas crudo producen", conversation_id="t1")` y verificar
`res["entidad_cruda"] is None` → la memoria de cuantificar **no** se escribe (la guarda existente
`and res.get("entidad_cruda")` ya lo impide).

**V-NODE**
```bash
node --check "C:/APLICACIONES/ProdIA/12112025_prodIA/12112025_prodIA/static/js/multitab_shell.js"
```
→ exit 0.

---

## 9. FUERA DE ALCANCE

Ranking scoped a entidad · niveles gerencia/VP/pozo · métrica cumplimiento-% · grano día ·
memoria conversacional de N5 (un "¿y en gas?" tras un ranking **no** repite el ranking; v1 no deja
memoria) · paridad gemma4 del intro y verificación en navegador (las hace el usuario en el servidor
de pruebas).

---

## 10. RESUMEN PARA APROBACIÓN

1. **Qué:** N5 RANKING en Cuantificar — ordena campos/activos por producción (REAL) o por brecha vs
   presupuesto (gap), top/bottom, alcance global ECP.
2. **Cómo:** módulo nuevo `ranking.py` (query propia verificada) + fork en `respuesta_cuantificar`
   **antes** del resolver + 8 patrones genéricos + rama de panel en el frontend.
3. **Honestidad:** terceros rotulados · bottom filtra ceros y los declara · proyección rotulada ·
   huella siempre · 4 formas declinan honesto.
4. **Riesgo bajo:** no toca v1, ni `maquina_q`, ni `desempeno`/`_gap_campo`/`ejecutor`.
5. **Verificación:** 8 suites en dev (estáticas + BD); navegador y LLM los valida el usuario en el
   servidor de pruebas.

---

## 11. REGISTRO DE AUDITORÍA (por qué el v2 difiere del v1)

| # | Defecto del v1 | Evidencia | Corrección en v2 |
|---|---|---|---|
| **D1** | 🔴 **Bug real:** modelar el orden como `(eje, asc/desc)` hacía que *"qué campos se quedaron más cortos vs presupuesto"* devolviera los que **SUPERARON** el presupuesto. `"MAS"` no está en la lista ascendente → `desc` → `sorted(reverse=True)` sobre `real-ppto` = excedente primero. | Reproducido con la lógica literal del v1: las 3 variantes de gap dieron `orden=desc` → "EXCEDENTE primero". | Se rediseña a `(metrica, direccion)` con reglas explícitas; en `gap` el **default es faltante** y las palabras de faltante mandan sobre "mayor". Test dedicado en V-DETECT. |
| **D2** | 🔴 **Contrato roto:** el v1 permitía entregar el backend sin el frontend ("el mensaje ya es completo"). El dispatch tiene *fall-through* a `__cnCuantCardHtml`, que lee campos de KPI inexistentes en N5 → panel roto silencioso. | `multitab_shell.js:2413-2415`. | Frontend **obligatorio en el mismo commit**; alternativa explícita `panel: None`. Orden de ejecución con corte duro tras las validaciones de backend. |
| **D3** | **Bug:** `calcular` no guardaba el caso "mes sin datos" → habría producido *"Los 0 campos…"*. | Revisión del flujo con `periodo_texto` de un mes vacío. | Dos guardas (`not con_real` y `not pool`) con mensaje honesto. |
| **D4** | **Cambio innecesario y riesgoso:** el v1 editaba `maquina_q.py` para propagar `es_ranking`, con instrucciones ambiguas ("si no es trivial, alternativa…"). | `detectar_entidad()` devuelve **None** en las 5 preguntas de ranking global → `entidad_cruda` es `None` → la guarda existente `and res.get("entidad_cruda")` ya impide escribir memoria. | **`maquina_q.py` se elimina del inventario.** Se sustituye por la regresión V-MEM. Menos superficie, menos riesgo. |
| **D5** | **Afirmación no verificada:** el SQL de `activo` hardcodeaba `'ECOPETROL' AS operador`. | `map_campo_activo` no modela operador. | Devuelve `NULL`; el formateador no rotula operador a nivel activo. |
| **D6** | **Vocabulario muerto:** `_EJE_GAP` incluía `"META"`, pero `'META\b'` es patrón de **analizar** y gana por `precedencia_colision` → nunca llega a Cuantificar. | `patrones_grupo.yaml` (grupos.analizar + precedencia_colision). | `"META"` retirado del detector; documentado que las preguntas con "meta" enrutan a Analizar. |
| **D7** | **Cifra engañosa:** la concentración se calculaba también en dirección `bottom` ("los 5 que menos producen concentran el 0,3%") — dato inútil presentado como huella. | Revisión de la regla "no silent caps". | Solo se calcula en `metrica=real` + `direccion=top`. |
| **D8** | **Diagnóstico pesimista (corregido a favor):** el v1 afirmaba que el caso insignia de N5 escalaría al LLM y sería no determinista. | `nivel_dominio()` devuelve **`fuerte`** en las 5 preguntas reales (por "crudo"/"gas"/"presupuesto") → enrutan directo. Solo *"top 5 campos este mes"* (sin producto) da `estructural`. | Se documenta el comportamiento real; el riesgo queda acotado a esa forma sin producto. |
