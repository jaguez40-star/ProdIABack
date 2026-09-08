"""core/unidades.py — punto UNICO de verdad para unidades de produccion.

Contrato: todo lo que sale del backend esta en kboepd (miles de barriles equivalentes por
dia). El frontend NO escala, solo formatea.

  Mensual  -> fact_produccion_mes_ecp.bpdeq_m   (el gas YA viene en beq)      -> /1000
  Diario   -> fact_produccion_dia_ecp.vol_estimado  (gas /5.7)                -> /1000
  Acumulado-> SUM(kboepd_mes x dias_mes)  -> VOLUMEN en kbbl-eq (no caudal)
  Diferidas-> AVM_DATADIF.*_PERDIDO       (gas /5.7)  -> VOLUMEN en bbl-eq

Ver backend/Planes/plan_UNIDADES-BARRILES-EQUIVALENTES_20260908.md
"""

# Factor gas -> barriles equivalentes. Medido: bpd_m/bpdeq_m = 5,70 en el fact mensual y
# constante en 8 activos del fact diario contra DATOS_MES (plan v2 §1 H1, H3).
FACTOR_GAS_BEQ = 5.7

# El fact entrega unidades sueltas (bpd); se muestran miles.
ESCALA_K = 1000.0

# Rotulos. D1 (2026-09-08), revierte la decision del 2026-07-21 (D3).
UNIDAD = "kboepd"          # caudal: mes puntual, dia, series, ranking, gap
UNIDAD_ACUM = "kbbl-eq"    # volumen: acumulados (D7)
UNIDAD_DIF = "bbl-eq"      # volumen: diferidas (D9)

UNIDADES_PRODUCTO = {"CRUDO": UNIDAD, "GAS": UNIDAD, "BLANCOS": UNIDAD}

# Conceptos que SI suman. MONETIZACION y CAMPOS_REG_ESP son atribuciones del MISMO volumen:
# sumarlos duplica (crudo 968 en vez de 492). Plan v2 §1 H1; HALLAZGO_concepto_multiplicidad.md.
CONCEPTOS_SUMABLES = ("DERECO", "PROPIEDAD", "REGALIADISP")
SQL_CONCEPTOS = "co.nombre IN ('DERECO','PROPIEDAD','REGALIADISP')"

# Solo mensual: el gas de CONSUMO no es produccion (plan v2 §1 H2). El diario no tiene proceso.
PROCESO_GAS = "VENTA-GRAVABLE"
SQL_PROCESO_GAS = "(tp.nombre <> 'GAS' OR pr.nombre = 'VENTA-GRAVABLE')"

# [P5-2026-09-08] El fact acumula UN JUEGO DE FILAS POR CADA REPORTE cargado: sin filtrar, un mes
# presente en N reportes se cuenta N veces (medido: GAS julio 107,7 en vez de 80,7 con 2 reportes;
# en el 139 hay 201). Se toma el reporte MAS RECIENTE POR FECHA.
# 🔑 NO usar MAX(reporte_id): el id es un serial por ORDEN DE INGESTA, no cronologico
#    (ver analisis/api.py:2703-2707 — en dev mayo se ingirio antes que marzo).
_SUB_ULTIMO_REPORTE = ("(SELECT cr.reporte_id FROM core.config_reporte cr "
                       "ORDER BY cr.fecha_reporte DESC LIMIT 1)")
SQL_ULTIMO_REPORTE_M = "m.reporte_id = " + _SUB_ULTIMO_REPORTE
SQL_ULTIMO_REPORTE_D = "d.reporte_id = " + _SUB_ULTIMO_REPORTE


def a_beq(valor, producto):
    """Volumen crudo del fact DIARIO -> barriles equivalentes. Gas /5.7; crudo y blancos igual."""
    if valor is None:
        return None
    v = float(valor)
    return v / FACTOR_GAS_BEQ if str(producto).upper() == "GAS" else v


def kboepd_mes(valor):
    """bpdeq_m (ya equivalente, bpd) -> kboepd."""
    return None if valor is None else float(valor) / ESCALA_K


def kboepd_dia(valor, producto):
    """vol_estimado de UN dia (bpd bruto) -> kboepd."""
    v = a_beq(valor, producto)
    return None if v is None else v / ESCALA_K


def fmt(n, dec=1):
    """Formato es-CO: punto de miles, coma decimal. 492,5 · 52.430,9 · 0,2.

    Redondeo COMERCIAL (ROUND_HALF_UP): 492,45 -> "492,5". El format() nativo de Python usa
    banker's rounding y daria "492,4", que a un usuario de negocio le parece un error.
    """
    from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
    try:
        q = Decimal(str(float(n))).quantize(Decimal("1." + "0" * dec) if dec else Decimal("1"),
                                            rounding=ROUND_HALF_UP)
        s = "{:,.{d}f}".format(q, d=dec)
        return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    except (ValueError, TypeError, InvalidOperation):
        return str(n)
