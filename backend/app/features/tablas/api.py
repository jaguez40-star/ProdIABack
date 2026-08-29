from fastapi import APIRouter, HTTPException
import sqlalchemy as sa
from app.core.db import get_engine

router = APIRouter(prefix="/tablas", tags=["tablas"])

CAP_FILAS = 100      # el visor solo muestra las primeras N filas (la BD guarda todo); ver total_filas
FETCH_MAX = 50_000   # tope de filas que se cargan para armar la tabla ancha (protege hojas RAW enormes)

@router.get("")
def listar(reporte_id: int, hoja: str):
    """Tablas lógicas de una hoja modelada (para los ítems clicables)."""
    # COMENTARIOS no vive en fact_tabla_hoja (es texto) -> 1 tabla lógica desde su fact dedicado.
    if hoja.strip().upper() == "COMENTARIOS":
        with get_engine().connect() as c:
            n = c.execute(sa.text(
                "SELECT count(*) FROM core.fact_comentarios_produccion WHERE reporte_id=:r"),
                {"r": reporte_id}).scalar() or 0
        return [{"tabla_idx": 1, "tabla_label": "COMENTARIOS", "filas": n}]
    with get_engine().connect() as c:
        rows = c.execute(sa.text("""
            SELECT tabla_idx, tabla_label, count(*) AS filas
            FROM core.fact_tabla_hoja WHERE reporte_id=:r AND hoja=:h
            GROUP BY tabla_idx, tabla_label ORDER BY tabla_idx"""),
            {"r": reporte_id, "h": hoja}).mappings().all()
    return [dict(x) for x in rows]

@router.get("/datos")
def datos(reporte_id: int, hoja: str, tabla_idx: int):
    """Contenido de una tabla en formato ANCHO. Dos modos:
    - 'fechas': columnas = fechas (tablas con serie temporal).
    - 'matriz': columnas = categorías (dims.columna); fecha es NULL. Se conserva el orden de
      aparición (ORDER BY id) porque en las matrices el orden de columnas es significativo.
    - 'texto': COMENTARIOS (fact dedicado de texto); columnas = los 3 campos de comentario."""
    # COMENTARIOS: tabla de TEXTO desde core.fact_comentarios_produccion (no fact_tabla_hoja).
    if hoja.strip().upper() == "COMENTARIOS":
        with get_engine().connect() as c:
            rows = c.execute(sa.text("""
                SELECT tp.nombre AS producto, x.activos, x.area,
                       x.comentario, x.comentario_programa, x.comentario_extra
                FROM core.fact_comentarios_produccion x
                LEFT JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = x.tipo_producto_id
                WHERE x.reporte_id=:r ORDER BY x.id"""), {"r": reporte_id}).mappings().all()
        if not rows:
            return {"vacia": True, "dimensiones": [], "meses": [], "filas": []}
        cols = ["Comentario", "Comentario programa", "Comentario extra"]
        filas = [{"dims": {"producto": r["producto"], "activos": r["activos"], "area": r["area"]},
                  "valores": [r["comentario"], r["comentario_programa"], r["comentario_extra"]]}
                 for r in rows]
        return {"modo": "texto", "dimensiones": ["producto", "activos", "area"],
                "meses": cols, "filas": filas[:CAP_FILAS], "total_filas": len(filas)}
    p = {"r": reporte_id, "h": hoja, "i": tabla_idx}
    with get_engine().connect() as c:
        # Carga ACOTADA (LIMIT FETCH_MAX): protege el visor de hojas RAW enormes (p.ej. BDP_datos_mes,
        # ~314K). Como cada extractor emite las filas de un mismo combo de dims de forma contigua (por id),
        # el prefijo cargado contiene los primeros combos COMPLETOS → la tabla ancha se arma bien y luego
        # se recorta a CAP_FILAS. Las hojas pequeñas (<FETCH_MAX) se cargan enteras (comportamiento igual).
        rows = c.execute(sa.text("""
            SELECT dims, fecha, valor FROM core.fact_tabla_hoja
            WHERE reporte_id=:r AND hoja=:h AND tabla_idx=:i ORDER BY id LIMIT :fm"""),
            {**p, "fm": FETCH_MAX + 1}).mappings().all()
        if not rows:
            return {"vacia": True, "dimensiones": [], "meses": [], "filas": []}
        truncada = len(rows) > FETCH_MAX          # hoja enorme: solo se cargó un prefijo por id
        if truncada:
            rows = rows[:FETCH_MAX]

        # --- modo matriz: todas las filas sin fecha → pivote fila × columna (matrices son pequeñas) ---
        if all(r["fecha"] is None for r in rows):
            cols = []                                    # orden de aparición
            for r in rows:
                c_ = (r["dims"] or {}).get("columna")
                if c_ is not None and c_ not in cols:
                    cols.append(c_)
            by_fila = {}
            orden = []
            for r in rows:
                dd = r["dims"] or {}
                fila = dd.get("fila")
                if fila not in by_fila:
                    by_fila[fila] = {}
                    orden.append(fila)
                by_fila[fila][dd.get("columna")] = (
                    float(r["valor"]) if r["valor"] is not None else None)
            filas = [{"dims": {"fila": f}, "valores": [by_fila[f].get(c_) for c_ in cols]}
                     for f in orden]
            return {"modo": "matriz", "dimensiones": ["fila"], "meses": cols,
                    "filas": filas[:CAP_FILAS], "total_filas": len(filas)}

        # --- modo fechas ---
        dim_keys = []
        for r in rows:                       # orden estable de columnas de dimensión
            for k in (r["dims"] or {}).keys():
                if k not in dim_keys:
                    dim_keys.append(k)
        if truncada:                         # columnas = TODAS las fechas (header estable, no solo el prefijo)
            meses = [d.isoformat() for (d,) in c.execute(sa.text(
                "SELECT DISTINCT fecha FROM core.fact_tabla_hoja "
                "WHERE reporte_id=:r AND hoja=:h AND tabla_idx=:i AND fecha IS NOT NULL ORDER BY fecha"),
                p)]
        else:
            meses = sorted({r["fecha"].isoformat() for r in rows if r["fecha"] is not None})
        by_dims = {}
        for r in rows:
            dd = r["dims"] or {}
            key = tuple(dd.get(k) for k in dim_keys)
            if key not in by_dims:
                by_dims[key] = {"dims": {k: dd.get(k) for k in dim_keys}, "valores": {}}
            if r["fecha"] is not None:
                by_dims[key]["valores"][r["fecha"].isoformat()] = (
                    float(r["valor"]) if r["valor"] is not None else None)
        filas = [{"dims": v["dims"], "valores": [v["valores"].get(m) for m in meses]}
                 for v in by_dims.values()]
        # total de filas del visor (combos distintos): exacto si se cargó todo; si truncada, count(*)
        # (en las hojas RAW truncadas cada combo = 1 registro → count(*) = nº de combos mostrable).
        total = (c.execute(sa.text(
            "SELECT count(*) FROM core.fact_tabla_hoja "
            "WHERE reporte_id=:r AND hoja=:h AND tabla_idx=:i AND fecha IS NOT NULL"), p).scalar()
                 if truncada else len(filas))
        return {"dimensiones": dim_keys, "meses": meses,
                "filas": filas[:CAP_FILAS], "total_filas": total}


MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@router.get("/arbol")
def arbol_reportes():
    """Árbol jerárquico año → mes → día (metadata de reporte).
    NO incluye el desglose de hojas/tablas -- eso se carga bajo demanda vía /arbol/{reporte_id}
    (ver hojas_reporte). Con el corpus real (core.fact_tabla_hoja > 50M filas) agregar sobre TODOS
    los reportes a la vez en una sola consulta tardaba minutos; esta consulta solo toca
    config_reporte (una fila por reporte) y es instantánea sin importar cuántos reportes existan."""
    engine = get_engine()
    sql = sa.text("""
        SELECT reporte_id, fecha_reporte, tipo_archivo, archivo_nombre
        FROM core.config_reporte
        ORDER BY fecha_reporte DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    from collections import OrderedDict
    tree = OrderedDict()
    for r in rows:
        fr = r["fecha_reporte"]
        a, m, d = fr.year, fr.month, fr.day
        tree.setdefault(a, OrderedDict()).setdefault(m, OrderedDict())[d] = {
            "reporte_id": r["reporte_id"],
            "tipo": r["tipo_archivo"],
            "archivo": r["archivo_nombre"],
        }

    result = []
    for anio, meses in sorted(tree.items(), reverse=True):
        meses_list = []
        for mes, dias in sorted(meses.items(), reverse=True):
            dias_list = []
            for dia, info in sorted(dias.items(), reverse=True):
                dias_list.append({
                    "dia": dia,
                    "reporte_id": info["reporte_id"],
                    "tipo": info["tipo"],
                    "archivo": info["archivo"],
                })
            meses_list.append({"mes": mes, "mes_nombre": MESES_ES[mes], "dias": dias_list})
        result.append({"anio": anio, "meses": meses_list})
    return result


@router.get("/arbol/{reporte_id}")
def hojas_reporte(reporte_id: int):
    """Desglose de hojas/tablas de UN reporte -- carga perezosa al expandir un día en el frontend.
    Filtrado por reporte_id: usa el índice (reporte_id,hoja,tabla_idx) de fact_tabla_hoja sobre
    ~filas de un solo reporte en vez de agregar la tabla completa."""
    engine = get_engine()
    sql = sa.text("""
        SELECT hoja, tabla_idx, tabla_label, COUNT(*) AS filas
        FROM core.fact_tabla_hoja
        WHERE reporte_id = :r
        GROUP BY hoja, tabla_idx, tabla_label
        UNION ALL
        SELECT 'COMENTARIOS' AS hoja, 1 AS tabla_idx, 'COMENTARIOS' AS tabla_label, COUNT(*) AS filas
        FROM core.fact_comentarios_produccion
        WHERE reporte_id = :r
        HAVING COUNT(*) > 0
        ORDER BY hoja, tabla_idx
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"r": reporte_id}).mappings().all()

    from collections import OrderedDict
    hojas_dict = OrderedDict()
    for r in rows:
        hojas_dict.setdefault(r["hoja"], []).append({
            "tabla_idx": r["tabla_idx"],
            "tabla_label": r["tabla_label"],
            "filas": r["filas"],
        })
    return {"reporte_id": reporte_id,
            "hojas": [{"hoja": h, "tablas": t} for h, t in hojas_dict.items()]}
