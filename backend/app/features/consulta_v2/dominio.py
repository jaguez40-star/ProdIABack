"""Filtro de dominio (motor_Q.md §1.2) — ¿la pregunta menciona vocabulario de producción?

Segundo criterio del filtro (el primero es detectar_entidad, en maquina_q.py). Módulo PURO:
solo depende de normaliza (sin BD, sin LLM) → testeable como patrones.py. Compilado UNA vez
(reiniciar backend para recargar).

DOS NIVELES (2026-08-02): el vocabulario dejó de ser una lista plana. Ver el encabezado de
config/vocabulario_dominio.yaml para el porqué (resumen: "campos" es a la vez entidad del
modelo y sustantivo común del español → evidencia DÉBIL que exige confirmación de la Capa 2).

FORK conceptual de la mecánica de patrones.py (carga perezosa de YAML) @ 2026-08-02.
"""
import re
import pathlib

import yaml

from app.features.consulta_v2.normaliza import norm

_CFG_PATH = pathlib.Path(__file__).parent / "config" / "vocabulario_dominio.yaml"

_RX = False   # False = no cargado; dict {"fuerte": rx|None, "estructural": rx|None} = cargado


def _compilar(lista):
    """Une los fragmentos en un solo regex \\b(a|b|...)\\b. None si la lista viene vacía."""
    items = [str(v) for v in (lista or []) if v]
    return re.compile(r"\b(" + "|".join(items) + r")\b") if items else None


def _cargar():
    """Compila ambas listas. Idempotente."""
    global _RX
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    _RX = {"fuerte": _compilar(cfg.get("vocabulario")),
           "estructural": _compilar(cfg.get("estructural"))}
    return _RX


def _get():
    return _RX if _RX is not False else _cargar()


def nivel_dominio(texto: str):
    """Cuánta certeza de dominio aporta el vocabulario. 'fuerte' | 'estructural' | None.

    'fuerte'      → término inequívoco (CRUDO, P50, EBITDA…): enruta directo, sin LLM.
    'estructural' → CAMPOS/POZOS/ACTIVOS: entidad del modelo Y español común → la Capa 2
                    confirma (D3: si además hay una palabra fuerte, gana 'fuerte').
    None          → ninguna palabra del vocabulario.
    """
    c = _get()
    n = norm(texto)
    if c["fuerte"] and c["fuerte"].search(n):
        return "fuerte"
    if c["estructural"] and c["estructural"].search(n):
        return "estructural"
    return None


def hay_palabra_dominio(texto: str) -> bool:
    """Compat: ¿hay CUALQUIER palabra de dominio (fuerte o estructural)? Se conserva porque la
    usan tests y porque expresa la pregunta binaria original del filtro."""
    return nivel_dominio(texto) is not None
