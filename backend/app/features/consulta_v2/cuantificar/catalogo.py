"""cuantificar/catalogo.py — Cargador del catálogo de variables cuantificables (Motor Q v2, Grupo 2).

Solo CARGADOR + VALIDACIÓN: los datos viven en config/variables_cuantificables.yaml (cero datos
aquí, patrón de patrones.py). Se lee UNA vez y se cachea por proceso → editar el YAML exige
reiniciar el backend.

Falla RUIDOSO si el YAML está mal formado o le falta una sección requerida: un catálogo corrupto
silencioso sería peor que un arranque roto (cuantificar respondería con datos a medias sin avisar).
respuesta_cuantificar.py fuerza la carga al importarse (arranque del backend), no en la 1ª pregunta.
"""
import pathlib
import yaml

_CFG_PATH = pathlib.Path(__file__).parent.parent / "config" / "variables_cuantificables.yaml"

_DATA = None   # cache por proceso (como _COMPILED de patrones.py / _DATA de respuesta_jerarquizar.py)

_SECCIONES_REQUERIDAS = ("meta", "referencias", "niveles", "productos", "derivadas", "conteos",
                          "robustez_especialista", "no_soportado", "reglas")


def _validar(cfg: dict):
    faltantes = [s for s in _SECCIONES_REQUERIDAS if s not in cfg]
    if faltantes:
        raise ValueError(f"variables_cuantificables.yaml: faltan secciones {faltantes}")
    productos = cfg.get("productos") or {}
    if "produccion_crudo" not in productos:
        raise ValueError("variables_cuantificables.yaml: falta 'productos.produccion_crudo' (núcleo Fase 1)")
    crudo = productos["produccion_crudo"]
    for campo in ("unidad", "fuente", "referencias", "granos"):
        if campo not in crudo:
            raise ValueError(f"variables_cuantificables.yaml: produccion_crudo sin '{campo}'")
    if "PPTO" not in (cfg.get("referencias") or {}):
        raise ValueError("variables_cuantificables.yaml: falta la referencia 'PPTO' (default de Fase 1)")


def _cargar():
    global _DATA
    if _DATA is not None:
        return _DATA
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError(f"variables_cuantificables.yaml: YAML vacío o mal formado ({_CFG_PATH})")
    _validar(cfg)
    _DATA = cfg
    return _DATA


def get() -> dict:
    """Catálogo completo (dict), cargado y validado. Lanza ValueError si el YAML es inválido."""
    return _DATA if _DATA is not None else _cargar()
