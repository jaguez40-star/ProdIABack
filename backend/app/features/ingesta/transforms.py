"""
Constantes de columnas Bronze y normalizadores de filiales — copiados del prototipo (H1/H10).
Importa helpers de app.shared.utils; NO tiene acceso a BD.
"""
from __future__ import annotations
import re
from app.shared.utils import s

# Especificación de columnas para las tablas Bronze tipadas
BZ_DIA = ["concepto","socio","operador","tipocontrato","contrato","fuente","idbdp","fuentecontrato",
          "fecha","mes","anio","escenario","propietario","grupoprod","producto","tipoproducto",
          "gerencia","modalidad","operacion","nacionalidad","grupo1","grupo2","grupo3","volumen",
          "porcentaje","vice","activos","voldismez","vol_estimado","promedio"]

BZ_MES = ["concepto","socio","ba_id","operador","grupooperador","tipocontrato","contrato","fuente",
          "idbdp","fuentecontratoplot","fuentecontrato","fecha","mes","anio","escenario","proceso",
          "row_changed_by","propietario","grupoprod","producto","tipoproducto","negocio","nuevagerencia",
          "superintendencia","tag","tipofuente","tagdescripcion","fechaefprop","fechaexprop","fechaefpden",
          "fechaexpden","negociovpr","gerencia","modalidad","operacion","tipocrudo","nacionalidad","grupo1",
          "grupo2","grupo3","volumen","porcentaje","voldismez","bpd_m","bpda_ac","bpdac_5","bpd_a","bpdeq_m",
          "blseq","bpdeq_a","nodo","diluyente","linea_estrategica","mezcla_siv_gas","producto_yacimiento",
          "proyeccion","esc_proy","vice","activos"]

BZ_PRG = ["fecha","vice","gerencia","version","fecha_version","estado","volumen","campo","producto",
          "area","idbdp","contrato","produccion_total","part_ecp"]

# Mapas de normalización para entidades de filiales
EMP_NORM = {"EAI": "America", "EA": "America", "AMERICA": "America",
            "HOCOL": "Hocol", "PERMIAN": "Permian"}
PROD_NORM = {"CRUDO": "CRUDO", "GAS": "GAS", "BLANCOS": "BLANCOS", "BLANCO": "BLANCOS"}

def norm_emp(e):
    if e is None: return None
    return EMP_NORM.get(e.strip().upper(), e.strip())

def norm_prod(p):
    if p is None: return None
    return PROD_NORM.get(p.strip().upper())

def split_label(lbl):
    """'Hocol (crudo)' -> ('Hocol','crudo')."""
    m = re.match(r"^\s*(.+?)\s*\(\s*([^)]+?)\s*\)?\s*$", lbl)
    return (m.group(1), m.group(2)) if m else (None, None)
