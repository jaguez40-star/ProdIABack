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


# [2026-08-13] Cache en proceso, MISMO criterio que _SPLIT_CACHE (A1, abajo): `causal` (Analizar) pasa
# a llamar impacto_historico() en CADA pregunta (bloque «Por qué»), y esta función escanea la MISMA
# tabla de 1,14 M filas que split_planeado (aquí agrupada por CAUSE_NIVEL4 en vez de NIVEL3, mismo
# WHERE, misma falta de cobertura de índice sobre GAS_PERDIDO) — por analogía cabe esperar un costo
# similar en frío (~11s, no remedido aquí: la BD local está corrupta y el flujo de trabajo pide no
# tocar Postgres/SQLite en dev). `causal` es la sub-intención DEFAULT ⇒ pagar ese costo en cada
# pregunta sería igual de grave que lo que ya motivó _SPLIT_CACHE. El histórico es INMUTABLE ⇒
# cachear es seguro. Se cachea TAMBIÉN el "no disponible"; el error NO se cachea (puede ser transitorio).
_IMPACTO_CACHE: dict = {}


def impacto_historico(campos: list[str] | None = None) -> dict:
    """Volumen histórico perdido por causa (CAUSE_NIVEL4), CRUDO (bbl) y GAS (misma unidad que la
    producción — verificado en routes/api.py:446-448). `campos`=None o [] -> sin filtro (ECP global).

    Retorno:
      {"sin_datos": True, "motivo": "..."}                        -- BD ausente o error de lectura
      {"sin_datos": True, "motivo": None}                          -- BD presente, 0 diferidas en ese alcance
      {"sin_datos": False, "impacto": {"CRUDO": {...}, "GAS": {...}}}  -- con datos

    SIEMPRE degrada (nunca lanza) — mismo contrato que la ruta Flask que porta. Cacheado (ver arriba)."""
    up = sorted({c.strip().upper() for c in (campos or []) if c and c.strip()})
    ck = tuple(up)
    if ck in _IMPACTO_CACHE:
        return _IMPACTO_CACHE[ck]

    if _DIF_DB is None or not _DIF_DB.exists():
        return {"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"}

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
        # El error NO se cachea: puede ser transitorio (lock/IO) y debe poder reintentarse.
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
        res = {"sin_datos": True, "motivo": None}   # BD presente, 0 diferidas en ese alcance
    else:
        res = {"sin_datos": False, "impacto": impacto}
    _IMPACTO_CACHE[ck] = res
    return res


# --- Split Planeada/No planeada (histórico) --------------------------------------------------
# A1 (auditoría 2026-08-04): este GROUP BY es un SCAN completo de 1,14 M filas (~11 s en frío; los
# índices ix_dd_cover/ix_dd_event NO cubren CAUSE_NIVEL3 ni GAS_PERDIDO → no hay index-only scan).
# `causal` es la sub-intención DEFAULT de Analizar, así que sin caché CADA pregunta causal pagaría
# ese costo — y el proxy Flask de /consulta2/preguntar tiene timeout=90 s (ya hay 502 reportados por
# Gemma en frío). El histórico es INMUTABLE (BD estática ene-2023→jul-2025, solo lectura) ⇒ cachear
# en proceso es seguro y elimina el costo repetido. Se cachea TAMBIÉN el "no disponible".
_SPLIT_CACHE: dict = {}


def split_planeado(campos: list[str] | None = None) -> dict:
    """Split HISTÓRICO Planeada (mantenimiento) vs No planeada (diferidas) del volumen perdido, por
    CAUSE_NIVEL3, CRUDO (bbl) y GAS. `campos`=None/[] -> ECP global. MISMO scoping (CAMPO/AREA) y
    contrato de degradación que impacto_historico — SIEMPRE degrada, nunca lanza. Cacheado (A1).

    🔑 SOLO histórico (la BD termina 2025-07): quien lo consume DEBE rotularlo como tal.

    Retorno:
      {"sin_datos": True, "motivo": "..."}   -- BD ausente / error de lectura
      {"sin_datos": True, "motivo": None}    -- BD presente, 0 diferidas clasificadas en el alcance
      {"sin_datos": False, "split": {"CRUDO": {...}, "GAS": {...}}}
    Cada producto presente (solo si volumen clasificado > 0):
      {"no_planeada": v, "planeada": v, "total_clasificado": v,
       "pct_no_planeada": %, "dominante": "no_planeada"|"planeada"}
    """
    up = sorted({c.strip().upper() for c in (campos or []) if c and c.strip()})
    ck = tuple(up)
    if ck in _SPLIT_CACHE:
        return _SPLIT_CACHE[ck]

    def _memo(res):
        _SPLIT_CACHE[ck] = res
        return res

    if _DIF_DB is None or not _DIF_DB.exists():
        return _memo({"sin_datos": True, "motivo": "BD de diferidas no disponible en este entorno"})

    where, params = "1=1", []
    if up:
        ph = ",".join("?" * len(up))
        where = f"(UPPER(TRIM(CAMPO)) IN ({ph}) OR UPPER(TRIM(AREA)) IN ({ph}))"
        params = up + up

    sql = (f"SELECT CAUSE_NIVEL3, SUM(COALESCE(ACEITE_PERDIDO,0)) ac, SUM(COALESCE(GAS_PERDIDO,0)) gas "
           f"FROM AVM_DATADIF WHERE {where} GROUP BY CAUSE_NIVEL3")
    try:
        con = sqlite3.connect(str(_DIF_DB))
        con.text_factory = lambda b: b.decode("utf-8", "replace")
        rows = con.execute(sql, params).fetchall()
        con.close()
    except sqlite3.Error as e:
        # El error NO se cachea: puede ser transitorio (lock/IO) y debe poder reintentarse.
        return {"sin_datos": True, "motivo": f"error leyendo diferidas: {e}"}

    def _prod(idx):
        np_ = pl_ = 0.0
        for r in rows:
            cat = (r[0] or "").strip().lower()   # 'planeada' | 'no planeada' | 'control de producción' | ''
            v = float(r[idx] or 0)
            if cat == "no planeada":
                np_ += v
            elif cat == "planeada":
                pl_ += v
        tot = np_ + pl_
        if tot <= 0:
            return None
        return {"no_planeada": round(np_), "planeada": round(pl_), "total_clasificado": round(tot),
                "pct_no_planeada": round(np_ / tot * 100, 1),
                "dominante": "no_planeada" if np_ >= pl_ else "planeada"}

    split = {}
    c, g = _prod(1), _prod(2)
    if c:
        split["CRUDO"] = c
    if g:
        split["GAS"] = g
    if not split:
        return _memo({"sin_datos": True, "motivo": None})
    return _memo({"sin_datos": False, "split": split})
