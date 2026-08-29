"""pozos_geo.py — coordenadas de pozos y contornos de campo para el panel de Jerarquizar.

Lee robustez_v02 (get_ops_engine): ops.wells_attributes y ops.field_polygons. Es el ÚNICO
sitio donde se corrigen las coordenadas; ningún consumidor debe repetir estas reglas.

🔑 GRANO DE ZONA (H1). wells_attributes NO tiene una fila por pozo sino por ZONA productora:
medido 2026-08-25, 40.542 filas / 13.504 uwi = exactamente 3,0. Un pozo con 3 zonas da 3
filas (verificado en CAS00356: idénticas salvo `zone`). SIEMPRE DISTINCT ON (uwi) — contar
filas infla los conteos x3. Es el mismo criterio de _contar_pozos (COUNT DISTINCT uwi) y de
ebitda/api.py:77.

🔑 X/Y INVERTIDAS (H2). En wells_attributes la LATITUD viene en coordinate_bottom_x y la
LONGITUD en coordinate_bottom_y: medido, 25.920 de 26.041 filas están así y CERO en el orden
esperado. field_polygons, en cambio, está bien (x_coord=lon). Las dos tablas usan
convenciones opuestas; aquí se normaliza a {lon, lat} y hacia afuera solo salen esos nombres.

🔑 SOLO COORDENADA DE FONDO. coordinate_surface_x/y está VACÍA en las 40.542 filas (medido:
ni un solo valor). Lo que se publica es el fondo del pozo, que en un horizontal puede estar
a km de la cabeza. Si algún día se puebla la superficie, se cambia aquí.

🔑 FILTRO DE COLOMBIA (H3). 121 pozos traen coordenadas imposibles (x=1133.00, y=0.25). Un
solo punto perdido rompe la escala del mapa entero -> se descartan en el WHERE.
"""
import sqlalchemy as sa

from app.core.db import get_ops_engine

# Bounding box de Colombia continental. Descarta el ruido de ingesta (H3) sin recortar
# ningún campo real: el más occidental (ORITO, Putumayo) está en lon -76,9.
_LAT_MIN, _LAT_MAX = -4.5, 13.0
_LON_MIN, _LON_MAX = -80.0, -66.0

# El pozo se identifica por uwi; la coordenada NO varía entre sus duplicados (medido: 0 uwi
# con más de una coordenada distinta), así que DISTINCT ON puede quedarse con cualquiera.
_SQL_POZOS = sa.text("""
    SELECT DISTINCT ON (uwi)
           uwi,
           coordinate_bottom_y AS lon,   -- ¡invertidas! ver docstring
           coordinate_bottom_x AS lat
      FROM ops.wells_attributes
     WHERE field = ANY(:fields)
       AND coordinate_bottom_x BETWEEN :lat_min AND :lat_max
       AND coordinate_bottom_y BETWEEN :lon_min AND :lon_max
     ORDER BY uwi
""")

_SQL_TOTAL = sa.text("""
    SELECT COUNT(DISTINCT uwi) FROM ops.wells_attributes WHERE field = ANY(:fields)
""")

_SQL_POLY = sa.text("""
    SELECT field, x_coord AS lon, y_coord AS lat
      FROM ops.field_polygons
     WHERE field = ANY(:fields)
     ORDER BY field, seq
""")

# Centroides de TODOS los campos, para la vista país. MEDIANA y no promedio: LA CIRA tiene
# pozos dispersos y el promedio arrastra el centroide fuera del campo.
_SQL_CENTROIDES = sa.text("""
    SELECT field,
           COUNT(DISTINCT uwi) AS n,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY coordinate_bottom_y) AS lon,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY coordinate_bottom_x) AS lat
      FROM ops.wells_attributes
     WHERE coordinate_bottom_x BETWEEN :lat_min AND :lat_max
       AND coordinate_bottom_y BETWEEN :lon_min AND :lon_max
     GROUP BY field
    HAVING COUNT(DISTINCT uwi) >= 5
     ORDER BY 2 DESC
""")

_BBOX = {"lat_min": _LAT_MIN, "lat_max": _LAT_MAX, "lon_min": _LON_MIN, "lon_max": _LON_MAX}

_CENTROIDES = None   # caché de proceso: el catálogo no cambia entre reinicios


def _redondear(v, n=5):
    return None if v is None else round(float(v), n)


def geo(rob_fields):
    """{pozos, total, ubicables, contornos} para los rob_field dados, o None si `ops` no está.

    NUNCA lanza: si robustez_v02 no está disponible (p.ej. el servidor 139 sin esa BD), se
    devuelve None y el llamador OMITE el mapa — el árbol sigue intacto. Mismo criterio de
    degradación con gracia que _contar_pozos en respuesta_jerarquizar.
    """
    fields = sorted({f for f in (rob_fields or set()) if f})
    if not fields:
        return None
    try:
        eng = get_ops_engine()
        with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            p = dict(_BBOX); p["fields"] = fields
            pozos = [{"uwi": r[0], "lon": _redondear(r[1]), "lat": _redondear(r[2])}
                     for r in c.execute(_SQL_POZOS, p)]
            total = c.execute(_SQL_TOTAL, {"fields": fields}).scalar() or 0
            contornos = {}
            for f, lon, lat in c.execute(_SQL_POLY, {"fields": fields}):
                contornos.setdefault(f, []).append([_redondear(lon), _redondear(lat)])
    except Exception:
        return None
    return {"pozos": pozos, "total": int(total), "ubicables": len(pozos),
            "contornos": contornos}


def centroides():
    """[{f, n, lon, lat}] de los campos con 5+ pozos ubicables (62 al 2026-08-25), para la
    vista país. Se cachea en proceso: es un catálogo, no cambia dentro de una sesión.
    [] si `ops` no está disponible — la vista país se degrada a solo el contorno."""
    global _CENTROIDES
    if _CENTROIDES is not None:
        return _CENTROIDES
    try:
        eng = get_ops_engine()
        with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            _CENTROIDES = [{"f": r[0], "n": int(r[1]),
                            "lon": _redondear(r[2], 4), "lat": _redondear(r[3], 4)}
                           for r in c.execute(_SQL_CENTROIDES, _BBOX)]
    except Exception:
        return []            # sin cachear: reintenta en la próxima llamada
    return _CENTROIDES
