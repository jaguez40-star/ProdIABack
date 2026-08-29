# Plan de ejecución — Analizar · FASE 2 (Diferidas — histórico rotulado, lectura directa de SQLite)

> **Tablas: N/A** — no toca ingesta/ETL/DDL. Lee un SQLite ya existente (`ECP_DIFERIDAS.db`) de forma
> **directa e independiente** (no proxy, no HTTP), tal como se hace en el app padre.
>
> **Para:** un agente Executor SIN contexto del repo. Rutas absolutas, código de referencia completo,
> decisiones cerradas, criterios verificables (comando → resultado esperado).
>
> **Precede:** Motor Q v2 · Analizar **Fase 1 CERRADA** (causal + proyección, commit `8c08680`,
> verificada en navegador con LLM real — REGLA CERO confirmada con Castilla 102.7%). Esta Fase 2 añade
> la sub-intención **diferidas**, que hoy (Fase 1) devuelve un texto estático de "próxima fase".
>
> **Diseño base:** `INGESTA/Rep_Prod/analiza.md` §3/§4/§6.2/§9.3 (decisión A2, CERRADA 2026-08-02:
> diferidas responde el **patrón histórico 2023–2025**, rotulado, NUNCA como causa del mes en curso).
> ⚠️ Este plan **corrige el mecanismo** que `analiza.md §1.1` proponía ("reusa la ruta Flask") — ver §0.
>
> **Fecha:** 2026-08-03 · **Estado:** auditado (§0, con línea real del código fuente) — listo para aprobación.

---

## 0. Hallazgos de auditoría del código real (verificados 2026-08-03, con línea)

| # | Hallazgo (verificado en el código) | Efecto en el plan |
|---|-----------------------------------|-------------------|
| **FB-1 · "reusa la ruta Flask" es la propuesta EQUIVOCADA** 🔴🔴 | `analiza.md §1.1` dice que `diferidas.py` "reusa la ruta Flask" (`GET /api/diferidas/frecuencia`, `routes/api.py:336`). Pero esa ruta vive en el **app padre Flask** (proceso propio, puerto 8020), mientras que `consulta_v2` vive en el **backend FastAPI** de INGESTA (proceso propio, puerto 8000/8088). El patrón YA establecido en todo el proyecto es **Flask → proxy HTTP → FastAPI** (ver `routes/api.py:496-524`, los 4 proxies de `/consulta2/*`) — **nunca al revés**. Si `consulta_v2/analizar` llamara por HTTP al Flask del app padre, el backend FastAPI dependería de que el OTRO proceso esté arriba (acoplamiento nuevo, nunca visto en el proyecto) solo para leer un archivo SQLite plano. | **Se PORTA la query directamente** (lectura SQLite propia, sin HTTP, sin Flask) — mismo principio que ya usa Cuantificar con `cuantificar/resolver.py` (`# FORK de consulta/resolver.py`): se copia lo necesario, se marca el origen, cero dependencia cruzada de proceso. |
| **FB-2 · Solo se porta `impacto`, NO `pareto`/`tendencia`/`pozos_por_grupo`** | La ruta Flask real (`routes/api.py:336-474`) calcula 4 bloques: `pareto`, `tendencia`, `pozos_por_grupo` (todos desde `inc_sql`, deduplicando incidentes) e `impacto` (desde `imp_sql`, volumen por causa). `analiza.md §4` solo cita **`impacto`** como la pieza reusable para la sub-intención diferidas del chat — los otros 3 alimentan el panel visual del acordeón de foco, que Fase 1 explícitamente excluyó del chat ("Fase 1 = ... sin panel"). | El puerto en `consulta_v2/analizar/diferidas.py` implementa **SOLO** el equivalente de `imp_sql` (`routes/api.py:380-381`) + el helper `_impacto()` (`routes/api.py:449-463`). No se replica `inc_sql` (innecesario para el chat, menos código que mantener). |
| **FB-3 · La BD (~954 MB) puede no existir en el entorno** | Confirmado: NO versionada en git (`.gitignore`), y según la bitácora del CLAUDE.md padre "no está en 139 aún". La ruta Flask ya la trata como degradación esperada (`if not os.path.exists(_DIF_DB): return {"sin_datos": True, ...}`, `routes/api.py:355-357`). En ESTA máquina dev **sí existe** (`data/ECP_DIFERIDAS/ECP_DIFERIDAS.db`, verificado por `Glob`) — pero el servidor de pruebas / 139 pueden no tenerla. | El puerto debe degradar EXACTAMENTE igual (verificar `os.path.exists` antes de conectar, capturar `sqlite3.Error`) y la plantilla debe decir **honestamente** "no tengo esa base disponible en este entorno" — nunca fallar en silencio ni inventar cifras. |
| **FB-4 · Ancla de ruta: NO usar un `parents[N]` fijo a ciegas** | El patrón ya usado (`config.py:5`, `routes/api.py:313`) ancla con `abspath`/`parents[k]` — pero contar niveles a mano desde `consulta_v2/analizar/diferidas.py` hasta la raíz de ProdIA (que está **un nivel arriba de `INGESTA/`**, fuera del propio sub-repo INGESTA) es frágil y fácil de errar por un dígito. | Se ancla **buscando el directorio "INGESTA" en `Path(__file__).resolve().parents`** y tomando SU padre — auto-documentado, inmune a mover el archivo dentro de `consulta_v2/` en el futuro. Ver código en §5.1. |
| **FB-5 · La entidad debe resolverse ANTES de la rama por sub-intención** | En el código real de Fase 1 (`respuesta_analizar.py`, verificar tras `git show HEAD:...`), el bloque `if sub in ("diferidas", "economia"): return ...` está **ANTES** de resolver la entidad (`resuelta = _resolver.resolver_unico(...)`) — porque en Fase 1 diferidas no necesitaba la entidad. Fase 2 SÍ la necesita (para filtrar por campo/activo). | **Reordenar**: economía sigue devolviendo el texto estático de inmediato (no necesita entidad); diferidas se mueve DESPUÉS de la resolución de entidad, reusando el MISMO bloque de resolución (ambiguo/filial/irresoluble/global) que ya usan causal y proyección — sin duplicar esa lógica. |
| **FB-6 · `nivel` gerencia/vicepresidencia/fuente rompería el filtro en silencio** | El filtro real (`WHERE UPPER(TRIM(CAMPO)) IN (...) OR UPPER(TRIM(AREA)) IN (...)`) solo compara contra nombres de **campo**. Si `resolver_unico` devuelve nivel `gerencia`/`vicepresidencia`/`operador`/`fuente`, pasar ese valor como filtro NO calza contra ninguna fila → **0 resultados silenciosos**, indistinguible de "no hubo diferidas" (falso negativo). | El responder **declina explícitamente** ("el histórico de diferidas solo cubre campo o activo") cuando `nivel not in (None, "campo", "activo")`, en vez de dejar que la query devuelva vacío sin explicación. |
| **FB-7 · Unidad de GAS: reusar `_fmt`, no reinventar** | El comentario real (`routes/api.py:446-448`) confirma: `GAS_PERDIDO` está en la MISMA unidad que la producción (verificado: fracción perdido/producido ~0.4–0.8%, misma banda que crudo) → el frontend lo muestra en MSCF (÷1e6). `plantilla.py` de Fase 1 YA tiene `_fmt(valor, prod)` que hace exactamente eso (`GAS` → ÷1e6 vía `fmt_valor`). | **Reusar `_fmt` tal cual** (ya importado en `plantilla.py`) — cero lógica de unidades nueva. |

### 0.1 Segunda ronda de auditoría (adversarial, sobre mi propia v1 de este plan — 2026-08-03)

| # | Incoherencia/riesgo detectado | Reformulación |
|---|--------------------------------------------------------------------|---------------|
| **FC-1 · el ancla de ruta (FB-4) puede tumbar el arranque de TODO el backend** 🔴🔴 | `next(p for p in _HERE.parents if p.name == "INGESTA")` corre a **nivel de módulo** (se ejecuta al importar `diferidas.py`, que se importa desde `respuesta_analizar.py` → `maquina_q.py` → `api.py`/`main.py` al arrancar el backend). Si por CUALQUIER motivo no hay un ancestro llamado exactamente `"INGESTA"` (renombrar la carpeta, mover el repo, un despliegue con otra estructura), `next()` sin default lanza `StopIteration` **al importar**, y el backend **completo no arranca** — ni Jerarquizar ni Cuantificar ni Analizar causal/proyección, que SÍ funcionan hoy. Esto contradice la regla madre de todo el plan ("degradar, nunca truena") aplicada aquí solo a MEDIAS: degrada bien DENTRO de `impacto_historico()`, pero no protege el cómputo de la ruta en sí. | Envolver la resolución del ancla en `try/except` **al nivel de módulo**, con `_PRODIA_ROOT = None` como fallback; `_DIF_DB`/`_ACTIVO_CSV` quedan `None` si no se pudo anclar; `impacto_historico()`/`campos_de_activo()` chequean `_DIF_DB is None` como el MISMO caso "no disponible" (no un caso nuevo). El backend arranca siempre, pase lo que pase con esta ruta. Código corregido en §5.1. |
| **FC-2 · V4 proponía renombrar el archivo REAL de 954 MB** 🔴 | La validación V4 original decía "renombrar temporalmente `ECP_DIFERIDAS.db` a `.db.bak`" como opción (a). Ese archivo **no está versionado en git** (`.gitignore`, >100 MB) y **no está en 139** — es un activo único, no regenerable con un `git checkout`. Renombrar-y-restaurar es reversible EN TEORÍA, pero un script que se corta a la mitad (excepción, Ctrl+C, corte de luz) deja el archivo con el nombre equivocado y el proyecto entero sin su BD de diferidas hasta que alguien lo note. Riesgo desproporcionado para una prueba que tiene una alternativa igual de válida y sin tocar disco. | **V4 se reescribe para NUNCA tocar el archivo real**: un script aislado hace **monkeypatch en memoria** del atributo del módulo (`diferidas._DIF_DB = Path("ruta/que/no/existe.db")`) dentro del PROPIO proceso de prueba, verifica la degradación, y termina — el archivo real en disco no se toca en ningún momento. Ver §8. |
| **FC-3 · el test de "nivel no soportado" depende de una llamada REAL a Postgres** 🟡 | El test `test_diferidas_nivel_no_soportado_declina` (v1 de este plan) llama `_ra.responder(..., entidad="GOR")` **sin inyectar** el resolver — se apoya en que `resolver_unico("GOR")` devuelva `nivel="vicepresidencia"` contra la BD real. Esto **rompe el contrato que el propio `test_analizar.py` declara en su docstring** ("ninguna prueba toca Postgres") y lo hace depender de un dato que puede diferir entre dev/servidor de pruebas (mismo tipo de fragilidad que ya mordió a Cuantificar con drills — ver bitácora del 2026-08-02). | Se **extrae la regla como función pura** `nivel_soportado(nivel) -> bool` en `diferidas.py` (FB-6 ya no vive inline en `respuesta_analizar.py`, vive donde vive el conocimiento del filtro SQL que la motiva). El test pasa a ser una prueba unitaria de 3 líneas, **sin BD, sin resolver, sin injection** — y `respuesta_analizar.py` la LLAMA en vez de repetir la tupla `(None, "campo", "activo")` a mano. Ver §5.1/§5.3/§5.5 corregidos. |
| **FC-4 · el rótulo GLOBAL no coincide con el que YA usa causal/proyección** 🟡 | `causal()`/`proyeccion()` (Fase 1) leen `scope = (d.get("meta") or {}).get("scope") or (entidad or "la producción ECP")`, y ese `meta.scope` viene LITERAL de `ejecutivo()`: `"Global (toda la producción ECP)"` (`analisis/api.py:1970`, verificado). Mi `diferidas()` (v1 de este plan) inventaba una frase DISTINTA, `"ECP (global)"`, para el mismo concepto — dos voces distintas para "sin entidad" dentro del MISMO grupo Analizar, en la MISMA conversación. | `diferidas()` reusa literalmente `"Global (toda la producción ECP)"` — mismo texto que ya ve el usuario en causal/proyección. Corregido en §5.2 y en el test de §5.5. |
| **FC-5 · confirmación positiva (no requiere cambio)** ✅ | Se verificó que `'DIFERIDAS'` y `'MANTENIMIENTOS?'` **SÍ están anclados** en `patrones_grupo.yaml` (saltan el filtro de dominio) — a diferencia de `'POR QUE'` (genérico), que fue la causa real de que "¿por qué está corto Cajúa?" clasificara mal como Desconocido en la prueba de navegador de Fase 1. Las preguntas de diferidas de este plan (§5.4/§8 V6) **no deberían tropezar** con ese mismo problema. | Sin cambios de código. Se deja constancia para no repetir el diagnóstico si algo falla en V6. |

---

## 1. Contexto

Motor Q v2 · Grupo 3 (Analizar), Fase 2. Edificio SEPARADO (`consulta_v2/`), cero imports de `consulta/`
v1 NI de la app Flask padre. **Regla madre (idéntica a Fase 1):** Python calcula y decide; el LLM solo
redacta el intro. La sub-intención `diferidas` (detectada por `analizar/subrouter.py`, ya existe desde
Fase 1) hoy devuelve un texto fijo de "próxima fase" — este plan la conecta a datos reales.

## 2. Objetivo

Que preguntas como *"¿qué pasó con las diferidas de Cajúa?"* o *"¿qué mantenimientos hubo en
Castilla?"* respondan con el **histórico de causas** (ene-2023 → jul-2025) por volumen perdido
(CRUDO/GAS), **rotulado explícitamente como histórico** — nunca presentado como la causa del mes en
curso (decisión A2 de `analiza.md`, ya cerrada). Si la BD no está disponible en el entorno, o si la
entidad no tiene diferidas registradas, o si el nivel no es campo/activo: la respuesta lo **declara
honestamente**, nunca inventa ni queda en silencio.

## 3. Prerequisitos

- Motor Q v2 + Analizar Fase 1 (commit `8c08680`) presentes y funcionando.
- Backend en `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend`
  (`uv run python` desde `backend/`).
- Archivo `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\data\ECP_DIFERIDAS\ECP_DIFERIDAS.db`
  (existe en dev; puede faltar en servidor de pruebas/139 — el código debe soportar ambos casos).
- Archivo `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\data\Activo_campo.csv` (ya existe,
  usado por Cuantificar y por la ruta Flask de diferidas — mismo formato `ACTIVO;CAMPO`).

## 4. Inventario de archivos

Base backend: `C:\APLICACIONES\ProdIA\12112025_prodIA\12112025_prodIA\INGESTA\Rep_Prod\backend\app\features\consulta_v2`

| Acción | Ruta |
|--------|------|
| CREAR | `...\consulta_v2\analizar\diferidas.py` — lectura DIRECTA del SQLite (FB-1/FB-2/FB-3/FB-4/FC-1) + `nivel_soportado()` (FC-3) |
| EDITAR | `...\consulta_v2\analizar\plantilla.py` — añadir `diferidas(d, entidad)` |
| EDITAR | `...\consulta_v2\respuesta_analizar.py` — reordenar (FB-5) + rama `diferidas` + guarda de nivel (FB-6) |
| EDITAR | `...\consulta_v2\golden\analizar_golden.yaml` — +1 caso diferidas con vocabulario de mantenimiento |
| EDITAR | `...\backend\tests\test_analizar.py` — +6 tests (con datos / sin BD / sin resultados / global / 2× `nivel_soportado` puro) |
| NO TOCAR | `routes/api.py` del app padre (Flask, se queda intacto — es la fuente que se PORTA, no se llama), `analisis/api.py` (Fase 1, sin cambios), `cuantificar/*`, `analizar/subrouter.py` (ya reconoce "diferidas"/"mantenimiento(s)" desde Fase 1), frontend (sigue siendo backend-only) |

## 5. Especificación (código de referencia)

### 5.1 — `analizar/diferidas.py` (CREAR)

```python
"""analizar/diferidas.py — histórico de diferidas por causa, lectura DIRECTA de SQLite (Motor Q v2,
Analizar Fase 2).

Fuente: data/ECP_DIFERIDAS/ECP_DIFERIDAS.db (SQLite, ~954 MB, ene-2023 → jul-2025; NO versionado en
git, puede faltar en un entorno — SIEMPRE se degrada, nunca truena).

🔑 Puerto DIRECTO de la query `imp_sql`/`_impacto()` de routes/api.py::diferidas_frecuencia (Flask,
app padre, líneas 380-381 y 449-463) — NO se llama por HTTP: consulta_v2 vive en un proceso FastAPI
separado del Flask del app padre, y el patrón establecido del proyecto es Flask → proxy → FastAPI,
nunca al revés (ver routes/api.py:496-524). Se porta SOLO el bloque `impacto` (lo único que
analiza.md §4 scopea para el chat) — `pareto`/`tendencia`/`pozos_por_grupo` alimentan el panel visual
del acordeón de foco (Flask), no se replican aquí.
"""
import csv
import sqlite3
from pathlib import Path

# Ancla por NOMBRE de directorio (no por conteo de parents — más robusto ante mover este archivo
# dentro de consulta_v2/): sube hasta encontrar "INGESTA" y toma SU padre = raíz de ProdIA.
# FC-1: esto corre a nivel de MÓDULO (se ejecuta al importar, y este módulo lo importa
# respuesta_analizar->maquina_q->api.py al arrancar el backend) — si el ancla no se encuentra, NO debe
# tumbar el arranque de TODO el backend (Jerarquizar/Cuantificar/causal/proyección siguen funcionando
# aunque diferidas no pueda ubicar su BD). _PRODIA_ROOT/_DIF_DB/_ACTIVO_CSV quedan None -> el mismo
# camino de "no disponible" que ya maneja impacto_historico(), no un caso nuevo.
_HERE = Path(__file__).resolve()
try:
    _PRODIA_ROOT = next(p for p in _HERE.parents if p.name == "INGESTA").parent
    _DIF_DB = _PRODIA_ROOT / "data" / "ECP_DIFERIDAS" / "ECP_DIFERIDAS.db"
    _ACTIVO_CSV = _PRODIA_ROOT / "data" / "Activo_campo.csv"
except StopIteration:
    _PRODIA_ROOT = _DIF_DB = _ACTIVO_CSV = None


# FC-3: regla PURA (sin BD, sin resolver) — el filtro SQL de abajo solo compara contra CAMPO/AREA,
# así que solo campo/activo (o ninguna entidad = global) tienen sentido. Vive aquí, no en
# respuesta_analizar.py, porque el conocimiento del filtro SQL que la motiva vive aquí.
def nivel_soportado(nivel: str | None) -> bool:
    """Diferidas solo filtra por CAMPO/AREA (AVM_DATADIF) -> solo campo/activo/None (global)."""
    return nivel in (None, "campo", "activo")


def campos_de_activo(activo: str) -> list[str]:
    """Campos que componen un ACTIVO (mismo CSV que usa el panel de Diferidas del app padre,
    formato ACTIVO;CAMPO). [] si el CSV falta, el ancla no se resolvió, o el activo no mapea campos."""
    if _ACTIVO_CSV is None:
        return []
    out, up = [], (activo or "").strip().upper()
    try:
        with open(_ACTIVO_CSV, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                if (row.get("ACTIVO") or "").strip().upper() == up:
                    c = (row.get("CAMPO") or "").strip()
                    if c:
                        out.append(c)
    except OSError:
        pass
    return out


def impacto_historico(campos: list[str] | None = None) -> dict:
    """Volumen histórico perdido por causa (CAUSE_NIVEL4), CRUDO (bbl) y GAS (misma unidad que la
    producción — verificado en routes/api.py:446-448). `campos`=None o [] -> sin filtro (ECP global).

    Retorno:
      {"sin_datos": True, "motivo": "..."}                        -- BD ausente o error de lectura
      {"sin_datos": True, "motivo": None}                          -- BD presente, 0 diferidas en ese alcance
      {"sin_datos": False, "impacto": {"CRUDO": {...}, "GAS": {...}}}  -- con datos

    SIEMPRE degrada (nunca lanza) — mismo contrato que la ruta Flask que porta."""
    if _DIF_DB is None or not _DIF_DB.exists():
        return {"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"}

    up = [c.strip().upper() for c in (campos or []) if c and c.strip()]
    where, params = "1=1", []
    if up:
        ph = ",".join("?" * len(up))
        where = f"(UPPER(TRIM(CAMPO)) IN ({ph}) OR UPPER(TRIM(AREA)) IN ({ph}))"
        params = up + up

    sql = (f"SELECT CAUSE_NIVEL4, SUM(COALESCE(ACEITE_PERDIDO,0)) ac, SUM(COALESCE(GAS_PERDIDO,0)) gas "
           f"FROM AVM_DATADIF WHERE {where} GROUP BY CAUSE_NIVEL4")
    try:
        con = sqlite3.connect(str(_DIF_DB))
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        rows = con.execute(sql, params).fetchall()
        con.close()
    except sqlite3.Error as e:
        return {"sin_datos": True, "motivo": f"error leyendo diferidas: {e}"}

    def _top(idx):
        vals = [((r[0] or "Sin clasificar"), float(r[idx] or 0)) for r in rows]
        vals = [(n, v) for n, v in vals if v > 0]
        tot = sum(v for _, v in vals)
        if not tot:
            return {"total": 0, "causas": []}
        vals.sort(key=lambda x: -x[1])
        TOP = 3
        causas = [{"causa": n, "vol": round(v), "pct": round(v / tot * 100, 1)} for n, v in vals[:TOP]]
        return {"total": round(tot), "causas": causas}

    impacto = {"CRUDO": _top(1), "GAS": _top(2)}
    if not impacto["CRUDO"]["total"] and not impacto["GAS"]["total"]:
        return {"sin_datos": True, "motivo": None}   # BD presente, 0 diferidas en ese alcance
    return {"sin_datos": False, "impacto": impacto}
```

### 5.2 — `analizar/plantilla.py` (EDITAR — añadir `diferidas`)

Añadir al final del archivo (reusa `_fmt`, `_UNIDAD`, `_PROD_L` ya definidos en Fase 1 — NO se
reimportan ni redefinen):

```python
def diferidas(d: dict, entidad: str | None) -> str:
    """Histórico de diferidas por causa (ene-2023 → jul-2025). ROTULADO como histórico (analiza.md
    §9.3, decisión A2): NUNCA se presenta como la causa del mes en curso."""
    # FC-4: MISMA frase que ya usan causal()/proyeccion() para "sin entidad" (viene literal de
    # ejecutivo(), analisis/api.py:1970) — una sola voz para "global" en todo el grupo Analizar.
    scope = entidad or "Global (toda la producción ECP)"
    etiqueta = f"📊 {scope} · Histórico de diferidas (ene-2023 a jul-2025) — no refleja el mes en curso"

    if d.get("sin_datos"):
        if d.get("motivo"):
            return f"{etiqueta}\nNo tengo la base de diferidas disponible en este entorno."
        return f"{etiqueta}\nNo encontré diferidas registradas para {scope} en ese rango histórico."

    imp = d["impacto"]
    lineas = [etiqueta]
    for prod in ("CRUDO", "GAS"):
        b = imp.get(prod, {})
        if not b.get("total"):
            continue
        u = _UNIDAD.get(prod, "bbl")
        top = "; ".join(f"{c['causa']} {c['pct']}%" for c in b["causas"])
        lineas.append(f"{_PROD_L[prod]}: las causas que más pesan históricamente son {top} "
                      f"(total histórico: {_fmt(b['total'], prod)} {u} perdidos).")
    return "\n".join(lineas)
```

### 5.3 — `respuesta_analizar.py` (EDITAR — reordenar FB-5 + nueva rama)

**(a)** Añadir el import, junto a los de `analizar` ya existentes:
```python
from app.features.consulta_v2.analizar import diferidas as _diferidas
```

**(b)** Añadir el parámetro de inyección para tests, en la firma de `responder` (junto a
`_ejecutivo_fn`):
```python
def responder(texto: str, entidad: str | None = None, usuario=None, conversation_id=None,
              _ejecutivo_fn=None, _diferidas_fn=None) -> str:
    """... (docstring existente sin cambios) ..."""
    fn = _ejecutivo_fn or _ejecutivo_ep
    dif_fn = _diferidas_fn or _diferidas.impacto_historico
```

**(c)** Reemplazar el bloque completo de sub-intención + entidad (FB-5: economía se queda igual e
inmediata; diferidas se mueve DESPUÉS de resolver entidad, reusando el mismo bloque de resolución):

Reemplazar DESDE (código actual de Fase 1):
```python
    # 1) Sub-intención (determinista). diferidas/economia → mensaje honesto de fase.
    sub = _subrouter.sub_intencion(texto)
    if sub in ("diferidas", "economia"):
        que = "las diferidas" if sub == "diferidas" else "el EBITDA/margen"
        return (f"El análisis de {que} llega en una próxima fase. Por ahora puedo explicarte las "
                "causas de un rezago (qué campos pesan) o la proyección de cierre del mes. "
                "¿Cuál de las dos te sirve?")

    # 2) Entidad (RA-2). resolver_unico busca por el arg o escaneando el texto.
```
POR:
```python
    # 1) Sub-intención (determinista). economia -> mensaje honesto de fase (Fase 3, sin cambios).
    sub = _subrouter.sub_intencion(texto)
    if sub == "economia":
        return ("El análisis del EBITDA/margen llega en una próxima fase. Por ahora puedo explicarte "
                "las causas de un rezago, la proyección de cierre o el histórico de diferidas. "
                "¿Cuál de esas te sirve?")

    # 2) Entidad (RA-2, Fase 1). Aplica por igual a causal/proyeccion/diferidas (FB-5: diferidas
    #    necesita la entidad para filtrar por campo/activo, a diferencia de Fase 1).
```

**(d)** Justo DESPUÉS del bloque `else: ent_valor = resuelta["valor"]; nivel = resuelta.get("nivel"); alcance = ...`
(el mismo bloque de Fase 1, sin tocarlo) e INMEDIATAMENTE ANTES de la línea
`# 3) Motor: ejecutivo con args explícitos...`, insertar la rama de diferidas:

```python
    # 3) DIFERIDAS (Fase 2): histórico por causa, NO usa `ejecutivo` (fuente propia). FC-3: la regla de
    #    qué nivel soporta el filtro SQL vive en diferidas.nivel_soportado() (no se repite la tupla acá).
    if sub == "diferidas":
        if not _diferidas.nivel_soportado(nivel):
            return (f"El histórico de diferidas solo está disponible a nivel de campo o activo; "
                    f"«{ent_valor}» es {nivel}. ¿Quieres nombrar un campo o activo puntual?")
        campos = _diferidas.campos_de_activo(ent_valor) if nivel == "activo" else (
            [ent_valor] if ent_valor else [])
        datos = dif_fn(campos)
        cuerpo = _plantilla.diferidas(datos, ent_valor)
        intro = _intro(alcance, usuario)
        return respuesta_base.envolver(
            intro, cuerpo, "¿Quieres el análisis de causas del mes en curso, o la proyección de cierre?")

    # 4) Motor: ejecutivo con args explícitos + pulir=False (AF-A2 + RA-1, Fase 1). periodo=None = mes
    #    actual (RA-3: el mes explícito llega en una fase posterior).
```

> El resto de la función (llamada a `fn(...)`, ramas `causal`/`proyeccion`, envoltorio final) **NO
> cambia** de código — pero **RENUMERAR es obligatorio, no opcional**: los comentarios `# 3)`/`# 4)`/
> `# 5)` que Fase 1 dejó en el resto del archivo (la llamada a `fn(...)` y el envoltorio final) deben
> correrse a `# 5)`/`# 6)` para que no queden DOS bloques con el mismo número `# 3)` en el archivo final
> (uno el nuevo de diferidas, otro el viejo del motor) — confuso de leer, aunque no rompe nada en runtime.

### 5.4 — `golden/analizar_golden.yaml` (EDITAR — +1 caso)

Añadir al final del archivo:
```yaml
- pregunta: "¿qué mantenimientos hubo en Castilla?"
  entidad: "CASTILLA"
  sub: diferidas
```

### 5.5 — `tests/test_analizar.py` (EDITAR — +6 tests)

Añadir el import de `_diferidas` junto a los existentes:
```python
from app.features.consulta_v2.analizar import diferidas as _diferidas_mod
```

Añadir al final del archivo:
```python
# ---------------- diferidas (Fase 2) ----------------

def _fake_diferidas_con_datos(campos=None):
    return {"sin_datos": False, "impacto": {
        "CRUDO": {"total": 5_000_000, "causas": [
            {"causa": "Formación", "vol": 1_140_000, "pct": 22.8},
            {"causa": "Falla de equipo", "vol": 945_000, "pct": 18.9},
            {"causa": "Reacondicionamiento", "vol": 700_000, "pct": 14.0}]},
        "GAS": {"total": 2_000_000, "causas": [
            {"causa": "Formación", "vol": 900_000, "pct": 45.0},
            {"causa": "Falla infraestructura", "vol": 400_000, "pct": 20.0}]},
    }}

def _fake_diferidas_sin_bd(campos=None):
    return {"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"}

def _fake_diferidas_vacio(campos=None):
    return {"sin_datos": True, "motivo": None}


def test_diferidas_con_datos_historico_rotulado():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_con_datos)
    assert "histórico" in r.lower() and "2023" in r and "no refleja el mes en curso" in r.lower()
    assert "Formación" in r and "22.8%" in r

def test_diferidas_sin_bd_declara_honesto():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_sin_bd)
    assert "no tengo la base de diferidas disponible" in r.lower()
    assert "Formación" not in r   # nunca inventa causas si no hay datos

def test_diferidas_sin_resultados_declara_honesto():
    r = _ra.responder("¿qué pasó con las diferidas de Cajúa?", entidad="CAJUA",
                      _diferidas_fn=_fake_diferidas_vacio)
    assert "no encontré diferidas registradas" in r.lower()

def test_diferidas_global_sin_entidad():
    r = _ra.responder("¿qué pasó con las diferidas?", entidad=None,
                      _diferidas_fn=_fake_diferidas_con_datos)
    assert "Global (toda la producción ECP)" in r and "Formación" in r


# ---------------- nivel_soportado (Fase 2, FC-3: puro, sin BD ni resolver) ----------------

def test_nivel_soportado_campo_activo_y_global():
    assert _diferidas_mod.nivel_soportado("campo") is True
    assert _diferidas_mod.nivel_soportado("activo") is True
    assert _diferidas_mod.nivel_soportado(None) is True          # global

def test_nivel_soportado_rechaza_gerencia_vicepresidencia():
    assert _diferidas_mod.nivel_soportado("vicepresidencia") is False
    assert _diferidas_mod.nivel_soportado("gerencia") is False
    assert _diferidas_mod.nivel_soportado("operador") is False
```

> `test_diferidas_global_sin_entidad` y los 2 tests de `nivel_soportado` reemplazan al
> `test_diferidas_nivel_no_soportado_declina` de la v1 de este plan (FC-3): la regla de qué nivel
> soporta diferidas ahora se prueba de forma PURA (sin BD, sin resolver, sin injection) contra la
> función `nivel_soportado()` directamente — el wiring de 1 línea en `respuesta_analizar.py`
> (`if not _diferidas.nivel_soportado(nivel): return ...`) se verifica por lectura de código (V1,
> compuerta) y no necesita su propio test end-to-end contra Postgres.

## 6. Orden de ejecución

1. `analizar/diferidas.py` (5.1). **`py_compile`.**
2. `analizar/plantilla.py` (5.2, añadir función). **`py_compile`.**
3. `respuesta_analizar.py` (5.3, reordenar + nueva rama). **`py_compile`.**
4. `golden/analizar_golden.yaml` (5.4) + `tests/test_analizar.py` (5.5). **`py_compile` del test.**
5. Correr la **COMPUERTA** (§8). Reportar y ESPERAR aprobación.

## 7. Reglas no negociables

1. **Cero HTTP entre procesos.** `consulta_v2/analizar/diferidas.py` lee el SQLite DIRECTAMENTE (FB-1)
   — nunca llama a la ruta Flask del app padre ni depende de que esté corriendo.
2. **Solo se porta `impacto`** (FB-2) — no `pareto`/`tendencia`/`pozos_por_grupo` (son del panel visual,
   fuera de alcance del chat).
3. **Degradación honesta, nunca silenciosa** (FB-3): BD ausente → "no tengo la base... en este
   entorno"; 0 resultados con BD presente → "no encontré diferidas... para {entidad}"; nivel no
   soportado → lo declara y pide un campo/activo puntual (FB-6). **Nunca** inventa causas ni queda en
   blanco.
4. **"Histórico 2023–2025, no del mes en curso"** debe aparecer literal en TODA respuesta con datos
   (decisión A2 de `analiza.md`, regla de honestidad §9.3).
5. **Reusar `_fmt`/`_UNIDAD`/`_PROD_L` de `plantilla.py`** (FB-7) — cero lógica de unidades nueva.
6. **Entidad se resuelve UNA vez, antes de la rama por sub-intención** (FB-5) — diferidas NO duplica la
   lógica de resolución/ambiguo/filial/irresoluble que ya usan causal/proyección.
7. **Edificio separado:** cero imports de `consulta/` v1 y cero imports/llamadas al app padre Flask.
8. **NO tocar** `routes/api.py` (Flask), `analisis/api.py`, `cuantificar/*`, el frontend, ni la memoria
   `_CTX` (diferidas sigue sin drills conversacionales, igual que toda Analizar Fase 1).
9. **NO usar el LLM local de dev**; pytest/golden/navegador → servidor de pruebas (igual que Fase 1).
10. **El archivo real `ECP_DIFERIDAS.db` (954 MB, no versionado, no regenerable con git) NUNCA se
    renombra, mueve ni edita** para ninguna prueba (FC-2) — la validación de "BD ausente" se hace por
    monkeypatch en memoria de `_DIF_DB` dentro del proceso de prueba, jamás tocando el disco.
11. **Si el ancla de ruta (`_PRODIA_ROOT`) no se resuelve, el backend arranca igual** (FC-1) — el fallo
    se degrada dentro de `diferidas.py`, nunca se propaga como `StopIteration` sin capturar al importar.

## 8. Validaciones (comando → resultado; TODAS sin LLM; en dev salvo «servidor»)

- **V1** (estático) `py_compile` de `diferidas.py` + `plantilla.py` + `respuesta_analizar.py` +
  `tests/test_analizar.py` → OK.
- **V2** (dev, 1 SOLO proceso aislado, **datos reales** — el archivo SÍ existe en esta máquina, ver §3)
  `from app.features.consulta_v2.analizar import diferidas as d`:
  `d.impacto_historico([])` (global) → `sin_datos=False`, `impacto["CRUDO"]["total"] > 0` y/o
  `impacto["GAS"]["total"] > 0`, cada `causas` trae `causa`/`vol`/`pct`, Σ`pct` de los top-3 ≤ 100.
  `d.impacto_historico(["CAJUA"])` → estructura igual (puede dar `sin_datos=True, motivo=None` si Cajúa
  no tiene diferidas registradas — ambos son resultados válidos, reportar cuál salió).
- **V3** (dev, puro Python, SIN BD — con `_diferidas_fn`/`_ejecutivo_fn` fakes, o directo contra
  `nivel_soportado`) los 6 tests nuevos de §5.5 corridos a mano (o vía pytest, pero SOLO estos 6,
  aislados): deben pasar los 6 asserts descritos.
- **V4** (dev, 1 SOLO proceso aislado, simulando BD ausente — FC-2: **NUNCA tocar el archivo real**)
  en un script de prueba aparte: `import ...analizar.diferidas as d; d._DIF_DB = Path("ruta/inexistente.db")`
  (monkeypatch EN MEMORIA, del proceso de prueba únicamente) → `d.impacto_historico([])` debe devolver
  `{"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"}` sin lanzar excepción.
  El archivo real (`data/ECP_DIFERIDAS/ECP_DIFERIDAS.db`) **no se toca, no se renombra, no se mueve**
  en ningún momento de esta validación.
- **V5** (servidor) `run_golden_analizar.py` → ≥90% (9 casos ahora, el nuevo de mantenimientos incluido);
  `pytest tests/test_analizar.py -v` → todos verdes (16 tests: 10 de Fase 1 + 6 nuevos).
- **V6** (servidor, navegador) Motor v2: *"¿qué pasó con las diferidas de Castilla?"* (o un campo/activo
  real con diferidas conocidas) → cuerpo con "histórico" + causas + %; *"¿qué mantenimientos hubo en
  [campo sin diferidas o inexistente]?"* → declara "no encontré"; si se puede simular en ese entorno
  (BD ausente en 139) → declara "no tengo la base disponible". Sin regresión de causal/proyección/
  Jerarquizar/Cuantificar/OUT.

## 9. Fuera de alcance (NO hacer)

- **Economía/EBITDA** (Fase 3, sin cambios — sigue devolviendo el mensaje de "próxima fase").
- **`pareto`/`tendencia`/`pozos_por_grupo`** del panel visual (FB-2) — solo `impacto`.
- **Enlace diferidas↔mes en curso** (`analiza.md §6.2`, decisión A2 ya cerrada: la BD termina en
  jul-2025, sin solape con 2026; el histórico se declara como tal, no se intenta correlacionar).
- **Caché en memoria** (la ruta Flask cachea resultados por ser data estática; el puerto no cachea —
  cada llamada relee el SQLite, ~0.7s medido en la ruta original; si en producción se ve lento,
  optimizar en una fase posterior, no ahora).
- **Rollup de gerencia/vicepresidencia** a múltiples campos (FB-6) — declina explícitamente en vez de
  construir esa agregación nueva.
- **Memoria `_CTX` / drills conversacionales** para diferidas (fase posterior, igual que Fase 1).
- **Panel derecho** para diferidas (sigue sin panel — backend-only, igual que toda Analizar Fase 1).
- **Editar `patrones_grupo.yaml`** ni `analizar/subrouter.py` (la sub-intención "diferidas" ya se
  detecta correctamente desde Fase 1 — verificado en navegador el 2026-08-03).
