import sqlalchemy as sa
from app.core.db import get_engine
from app.features.consulta.normaliza import norm

# nivel -> (query de valores distintos, rama)  · rama A = ECP, B = filial
#
# 🔑 EL ACTIVO NO SALE DE dim_fuente (auditoría 2026-07-16, verificada contra la BD).
# Jerarquía real del negocio:  campo -> ACTIVO -> gerencia -> vicepresidencia
#   · `dim_fuente.activos` NO es el activo: es un bucket de portafolio (OPERADOS /
#     NO OPERADOS / MENORES + agrupaciones regionales, 18 valores). Para APIAY agrupa
#     13 campos cuando el activo real tiene 4 -> devolvía cifras infladas. ELIMINADO.
#   · `dim_fuente.grupo1` ("area") es una taxonomía previa, parecida pero distinta
#     (62 valores; KIMERA->CPO-09, GIGANTE->NEIVA, PAUTO SUR->RECETOR discrepan del
#     catálogo real). No existe en el modelo mental del negocio. ELIMINADO.
#   · El catálogo real = 52 activos -> core.map_campo_activo (migración 008).
# Detalle completo en el encabezado de db/migrations/008_map_campo_activo.sql.
_LEVELS = [
    ("fuente",          "SELECT DISTINCT nombre   FROM core.dim_fuente          WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "A"),
    ("campo",           "SELECT DISTINCT campo    FROM core.dim_fuente          WHERE NULLIF(TRIM(campo),'')    IS NOT NULL", "A"),
    ("activo",          "SELECT DISTINCT activo   FROM core.map_campo_activo    WHERE NULLIF(TRIM(activo),'')   IS NOT NULL", "A"),
    ("gerencia",        "SELECT DISTINCT gerencia FROM core.dim_fuente          WHERE NULLIF(TRIM(gerencia),'') IS NOT NULL", "A"),
    ("operador",        "SELECT DISTINCT operador FROM core.dim_fuente          WHERE NULLIF(TRIM(operador),'') IS NOT NULL", "A"),
    ("vicepresidencia", "SELECT DISTINCT codigo   FROM core.dim_vicepresidencia WHERE NULLIF(TRIM(codigo),'')   IS NOT NULL", "A"),
    ("filial",          "SELECT DISTINCT nombre   FROM core.dim_empresa         WHERE NULLIF(TRIM(nombre),'')   IS NOT NULL", "B"),
]

_INDEX = None   # {nombre_norm: [ {nivel, rama, valor} ]}

def build_index():
    """Construye el índice invertido UNA vez. Idempotente."""
    global _INDEX
    idx = {}
    eng = get_engine()
    with eng.connect() as c:
        for nivel, sql, rama in _LEVELS:
            for (val,) in c.execute(sa.text(sql)):
                k = norm(val)
                if not k:
                    continue
                idx.setdefault(k, []).append({"nivel": nivel, "rama": rama, "valor": (val or "").strip()})
    _INDEX = idx
    return idx

def get_index():
    return _INDEX if _INDEX is not None else build_index()

def resolver(texto: str) -> list[dict]:
    """Capa 1 (exacta): devuelve la lista de identidades para el texto normalizado. [] si no hay match.
    NOTA v1: Capa 2 (fuzzy pg_trgm) es un paso posterior separable (§5 paso 8)."""
    return list(get_index().get(norm(texto), []))

# Palabras funcionales/de dominio que NO son entidades: evitan un falso positivo del backstop
# cuando coinciden por casualidad con un código corto del catálogo.
_STOP = {"QUE", "ES", "DE", "DEL", "LA", "EL", "LO", "LOS", "LAS", "UN", "UNA", "EN", "Y", "O",
         "A", "AL", "POR", "PARA", "CON", "SIN", "SU", "SUS", "ME", "MI", "SE", "ESO", "AHI",
         "PRODUCCION", "PRODUJO", "PRODUCE", "CUANTO", "CUANTA", "COMO", "CUAL", "CUALES",
         "DAME", "MUESTRAME", "INFORMACION", "INFO", "DATOS", "REPORTE", "REPORTES", "TAL"}

def buscar_en_texto(texto: str):
    """Backstop Python (solo si el LLM NO extrajo entidad): escanea el texto por n-gramas
    (más largos primero) contra el catálogo cerrado de nombres propios/códigos. Prefiere el
    match más específico ("CANO LIMON" ⊃ "CANO"). Devuelve (texto_match, identidades) o None.
    Seguro por construcción: el catálogo es vocabulario cerrado y solo se invoca como red de
    seguridad cuando la extracción del LLM falló."""
    idx = get_index()
    # norm no quita puntuación (la conserva para claves del catálogo); aquí sí, para que
    # "Castilla?" o "GOR," calcen con la clave limpia.
    palabras = [p for p in (w.strip("¿?¡!.,;:()[]{}\"'`") for w in norm(texto).split()) if p]
    n = len(palabras)
    for size in range(min(n, 4), 0, -1):
        for start in range(0, n - size + 1):
            gram = " ".join(palabras[start:start + size])
            if size == 1 and gram in _STOP:
                continue
            hit = idx.get(gram)
            if hit:
                return gram, list(hit)
    return None

def termino_candidato(texto: str):
    """Token más saliente (no funcional) del texto, AUNQUE no exista en el catálogo — para eco en
    mensajes de 'no reconocido' (ej. un typo como «holcol»). Conserva la ortografía original del
    usuario. None si el texto solo tiene palabras funcionales."""
    orig = [w.strip("¿?¡!.,;:()[]{}\"'`") for w in (texto or "").split()]
    cand = [(o, norm(o)) for o in orig if o and norm(o) and norm(o) not in _STOP and not norm(o).isdigit()]
    if not cand:
        return None
    return max(cand, key=lambda t: len(t[1]))[0]   # el más largo (heurística: nombre propio)


# ============================================================================
# Colapso de identidades: conjunto FÍSICO de fuente_id por (nivel, valor).
# Fusiona candidatos de una colisión que apuntan al MISMO fuente_id (colisión
# redundante por auto-nombrado, ej. RUBIALES = campo=area=activo=fuente).
# Usa el MISMO norm() del índice (H1). Cache por proceso (H3), como _INDEX.
# ============================================================================
_FUENTE_COL = {"fuente": "nombre", "campo": "campo",
               "gerencia": "gerencia", "operador": "operador"}
_ACTIVO_KEY = "__activo__"   # pseudo-columna: el activo NO vive en dim_fuente (ver _LEVELS)
_FUENTE_SETS = None   # {col|__activo__: {nombre_norm: frozenset(fuente_id)}}


def _build_fuente_sets():
    """Conjunto de fuente_id por (nivel, nombre_norm).

    El ACTIVO se compone: fuentes cuyo `campo` mapea a ese activo en core.map_campo_activo.
    D-A3 (2026-07-16): NO se rescatan fuentes con `campo` NULL usando `nombre` — son ruido de
    ingesta (decisión del usuario) y el rescate alteraba cifras ya validadas (Chichimene
    sumaba +56.003 bl al colar 3 filas NULL homónimas). El join usa el MISMO norm() del índice.
    """
    global _FUENTE_SETS
    fs = {col: {} for col in _FUENTE_COL.values()}
    fs[_ACTIVO_KEY] = {}
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(sa.text(
            "SELECT fuente_id, nombre, campo, gerencia, operador FROM core.dim_fuente")).all()
        campo2activo = {r[0]: r[1] for r in c.execute(sa.text(
            "SELECT campo_norm, activo FROM core.map_campo_activo"))}
    for r in rows:
        fid = r[0]
        for col, val in zip(_FUENTE_COL.values(), r[1:]):
            if val and str(val).strip():
                fs[col].setdefault(norm(val), set()).add(fid)
        campo = r[2]
        if campo and str(campo).strip():
            activo = campo2activo.get(norm(campo))
            if activo:
                fs[_ACTIVO_KEY].setdefault(norm(activo), set()).add(fid)
    _FUENTE_SETS = {col: {k: frozenset(v) for k, v in d.items()} for col, d in fs.items()}
    return _FUENTE_SETS


def _get_fuente_sets():
    return _FUENTE_SETS if _FUENTE_SETS is not None else _build_fuente_sets()


def fuentes_de_activo(activo: str) -> list[int]:
    """fuente_id que componen un ACTIVO (vía core.map_campo_activo). [] si no existe.
    Fuente única de la composición del activo: la usa también `analisis._ambito`, para que
    el chat y el tablero no puedan divergir."""
    return sorted(_get_fuente_sets()[_ACTIVO_KEY].get(norm(activo), frozenset()))


def campos_de_activo(activo: str) -> list[str]:
    """Campos que componen un ACTIVO, según el catálogo (independiente de si tienen datos)."""
    eng = get_engine()
    with eng.connect() as c:
        return [r[0] for r in c.execute(sa.text(
            "SELECT campo FROM core.map_campo_activo WHERE UPPER(TRIM(activo)) = :a ORDER BY campo"),
            {"a": (activo or "").strip().upper()})]


def activo_de_campo(campo: str) -> str | None:
    """ACTIVO al que pertenece un CAMPO, o None si no pertenece a ninguno (campo de un tercero, o
    ambiguo sin veredicto como AULLADOR). Dirección inversa de campos_de_activo()."""
    eng = get_engine()
    with eng.connect() as c:
        return c.execute(sa.text(
            "SELECT activo FROM core.map_campo_activo WHERE campo_norm = :c"),
            {"c": norm(campo)}).scalar()


def clave_fisica(ident: dict):
    """Clave de identidad FÍSICA para agrupar candidatos de una misma colisión.
    - rama B (filial): espacio propio -> nunca se fusiona con rama A (preserva el dual Hocol, H2).
    - vicepresidencia: espacio propio (no es fuente_id).
    - niveles de fuente: por el CONJUNTO de fuente_id -> dos niveles con el mismo set se fusionan."""
    nivel, rama, valor = ident["nivel"], ident.get("rama"), ident["valor"]
    k = norm(valor)
    if rama == "B":
        return ("B", k)
    if nivel == "vicepresidencia":
        return ("VICE", k)
    if nivel == "activo":
        return ("F", _get_fuente_sets()[_ACTIVO_KEY].get(k, frozenset()))
    col = _FUENTE_COL.get(nivel)
    if not col:
        return (nivel, k)
    return ("F", _get_fuente_sets()[col].get(k, frozenset()))
