"""cuantificar/validador.py — garantía mecánica de la regla madre + formato del cuerpo (Motor Q v2).

  (a) fmt_valor(n, producto) — literal por producto. CRUDO/BLANCOS: miles es-CO, 0 dec ('10.966.768').
      GAS: ÷1e6 + "MSCF", replicando __cnGasM del frontend (1 decimal si |m|>=1, si no 2; coma decimal,
      SIN separador de miles) → coherencia chat↔tablero. El LLM NUNCA toca esto (D-N5).
  (b) formatear_cuerpo(res) — cuerpo VERBATIM, ramifica por nivel (N1 mes / N2 acumulado / N3 serie /
      N4 variación) y usa fmt_valor+unidad del contrato (producto-aware). N3/N4 se resuelven ANTES de
      leer res["resultado"]/res["mes"] — esas claves no existen en su contrato (HE6).
  (c) intro_valido(intro) — el intro es SOLO saludo: sin dígitos ni unidades. Red mecánica de la regla.
"""
import re

_TIENE_DIGITO = re.compile(r"\d")
_UNIDADES = ("barril", "bbl", "mscf", "%", "porcentaje", "presupuesto", "millones", "millón")


def fmt_valor(n, producto) -> str:
    """Literal es-CO por producto. GAS = ÷1e6 'MSCF' (mirror __cnGasM); CRUDO/BLANCOS = bbl raw."""
    try:
        if producto == "gas":
            m = float(n) / 1e6
            d = 1 if abs(m) >= 1 else 2
            return f"{m:.{d}f}".replace(".", ",")
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def formatear_cuerpo(res: dict) -> str:
    """Cuerpo VERBATIM desde el contrato §7 (dict de ejecutor). Ramifica por nivel (HE6) y por
    producto (Fase 2: fmt_valor + unidad del contrato). N3/N4 primero (Fase 3): su contrato NO trae
    `resultado`/`mes` — leerlos antes de descartar N3/N4 reventaría con KeyError."""
    prod = res.get("producto", "crudo")
    unidad = res.get("unidad", "bbl")
    nivel = res.get("nivel")

    if nivel == "N3":
        pares = " · ".join(f"{p['mes']} {fmt_valor(p['valor'], prod)}" for p in res["serie"])
        linea = f"{res['entidad_cualificada']} de {prod}, mes a mes en {res['anio']}: {pares} {unidad}."
        if res.get("promedio") is not None:
            linea += f" Promedio mensual (meses cerrados): {fmt_valor(res['promedio'], prod)} {unidad}."
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    if nivel == "N4":
        u = res["ultimo"]
        subio = u["delta"] >= 0
        pct = f" ({'+' if subio else '-'}{abs(u['pct'])}%)" if u.get("pct") is not None else ""
        cambios = " · ".join(
            f"{d['de']}→{d['a']} {'+' if d['delta'] >= 0 else '-'}{fmt_valor(abs(d['delta']), prod)}"
            for d in res["deltas"])
        linea = (f"{res['entidad_cualificada']} de {prod}: del mes de {u['de']} al de {u['a']} "
                 f"{'subió' if subio else 'bajó'} {fmt_valor(abs(u['delta']), prod)} {unidad}{pct}. "
                 f"Serie de cambios: {cambios} {unidad}.")
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    # [2026-08-25] GRANO DÍA. VA ANTES de N1/N2: su contrato NO trae `mes` ni `referencia_valor`
    # — leerlos abajo reventaría con KeyError (mismo criterio que N3/N4, HE6).
    if nivel == "N1D":
        linea = (f"{res['entidad_cualificada']} produjo {fmt_valor(res['resultado']['valor'], prod)} "
                 f"{unidad} de {prod} el {res['fecha_label']}.")
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    # [2026-08-26 · QV2-SERIE-DIA] La curva diaria de un mes. El texto NO da la cifra del día —son
    # 30— sino el marco que el gráfico no puede decir solo: total, ritmo por día y cobertura.
    if nivel == "N1DSER":
        linea = (f"{res['entidad_cualificada']} produjo "
                 f"{fmt_valor(res['resultado']['valor'], prod)} {unidad} de {prod} en "
                 f"{res['mes_label']}, con un promedio de "
                 f"{fmt_valor(res.get('promedio_dia') or 0, prod)} {unidad}/día "
                 f"({res['dias_con_dato']} días con reporte). El detalle día a día está en la gráfica.")
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

    # N1/N2 (usan resultado/referencia — solo aquí, ya descartados N3/N4):
    real = fmt_valor(res["resultado"]["valor"], prod)
    pct = f"{res['cumplimiento_pct']}%" if res.get("cumplimiento_pct") is not None else "s/d"
    ppto = fmt_valor(res["referencia_valor"], prod) if res.get("referencia_valor") else None

    if nivel == "N2":                                   # ACUMULADO (meses cerrados)
        n = res["meses_cerrados"]
        linea = (f"{res['entidad_cualificada']} acumuló {real} {unidad} de {prod} en "
                 f"{res['periodo_label']} ({n} mes{'es' if n != 1 else ''} cerrado"
                 f"{'s' if n != 1 else ''}) — {pct} del presupuesto ({res['estado']}).")
        if ppto:
            linea += f" Presupuesto acumulado: {ppto} {unidad}."
        for a in res.get("avisos", []):
            linea += f" ⚠️ {a}"
        return linea

    # N1: mes puntual. Regla de proyección + referencia elegida (Fase 4).
    mes = res["mes"]
    ref_label = res.get("referencia_label", "presupuesto")
    corte = ("mes cerrado" if mes["completo"]
             else f"proyección · {mes['dias_con_data']}/{mes['dias_del_mes']} días")
    linea = (f"{res['entidad_cualificada']} produjo {real} {unidad} de {prod} en {mes['nombre']} "
             f"{mes['anio']} — {pct} del {ref_label} ({res['estado']}) · {corte}.")
    if ppto:
        # "promedio mensual del año" ya trae su propio calificador temporal — "...del año del mes:"
        # queda redundante (encontrado en pruebas de navegador, Fase 4). Las demás referencias
        # (presupuesto/operativo/contable) no lo tienen y sí necesitan el "del mes".
        if res.get("referencia") == "promedio_anio":
            linea += f" {ref_label.capitalize()}: {ppto} {unidad}."
        else:
            linea += f" {ref_label.capitalize()} del mes: {ppto} {unidad}."
    for a in res.get("avisos", []):
        linea += f" ⚠️ {a}"
    return linea


def intro_valido(intro: str) -> bool:
    """El intro es SOLO saludo: sin dígitos (D-N5) y sin unidades/lexicón de presupuesto."""
    if not intro:
        return False
    low = intro.lower()
    if _TIENE_DIGITO.search(intro):
        return False
    if any(u in low for u in _UNIDADES):
        return False
    return True
