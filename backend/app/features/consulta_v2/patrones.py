"""Capa 1 del clasificador de grupo — regex/keywords, Python puro, SIN LLM.

Este módulo es solo el CARGADOR: los patrones viven en config/patrones_grupo.yaml
(cero datos aquí, cero lógica allá). Se compilan UNA vez al primer uso (como _INDEX
del resolver v1) → agregar un patrón al YAML requiere reiniciar los backends.

Reglas de resolución (motor_Q.md §1.1):
  1. precedencia_maxima primero — la trampa de la huella ("¿cuántos días con reporte
     hay de X?" trae CUANTOS pero pregunta por disponibilidad, no por cifra).
  2. 1 solo grupo atrapa → ese grupo.
  3. 2+ grupos atrapan → precedencia_colision (analizar > cuantificar > jerarquizar).
  4. 0 grupos → None (baja a Capa 2 · LLM).
"""
import re
import pathlib
import yaml

from app.features.consulta_v2.normaliza import norm

_CFG_PATH = pathlib.Path(__file__).parent / "config" / "patrones_grupo.yaml"

_COMPILED = None   # {"max": [(grupo, regex, patron_str)], "grupos": {...}, "precedencia": [...]}


def _cargar():
    """Lee el YAML y compila los regex una vez. Idempotente."""
    global _COMPILED
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    comp = {"max": [], "grupos": {}, "precedencia": list(cfg["precedencia_colision"]),
            "anclados": set(cfg.get("patrones_anclados") or [])}
    for grupo, pats in (cfg.get("precedencia_maxima") or {}).items():
        for p in pats:
            comp["max"].append((grupo, re.compile(p), p))
    for grupo, pats in (cfg.get("grupos") or {}).items():
        comp["grupos"][grupo] = [(re.compile(p), p) for p in pats]
    _COMPILED = comp
    return comp


def _get():
    return _COMPILED if _COMPILED is not None else _cargar()


def clasificar_capa1(texto: str):
    """(grupo | None, patrones_atrapados). Determinista. None → baja a Capa 2 (LLM)."""
    t = norm(texto)
    if not t:
        return None, []
    c = _get()

    # 1) precedencia máxima (huella/disponibilidad) — gana antes de evaluar los grupos
    for grupo, rx, pat in c["max"]:
        if rx.search(t):
            return grupo, [pat]

    # 2) evaluación por grupo
    atrapados = {}   # grupo -> [patrones]
    for grupo, pares in c["grupos"].items():
        hits = [pat for rx, pat in pares if rx.search(t)]
        if hits:
            atrapados[grupo] = hits

    if not atrapados:
        return None, []
    if len(atrapados) == 1:
        g = next(iter(atrapados))
        return g, atrapados[g]

    # 3) colisión → precedencia fija
    for g in c["precedencia"]:
        if g in atrapados:
            return g, atrapados[g]
    return None, []   # inalcanzable con el YAML actual; defensivo


def es_anclado(patrones_lista) -> bool:
    """True si ALGUNO de los patrones que atrapó la Capa 1 es de dominio-anclado (motor_Q.md §1.2,
    D2): esos se saltan el filtro. Los patrones_lista son las cadenas EXACTAS del YAML que devolvió
    clasificar_capa1(). NOTA (H-H): en una colisión, clasificar_capa1 devuelve solo los patrones
    del grupo GANADOR — el vocabulario cubre los casos en que un patrón anclado quedó en el grupo
    perdedor (todos mencionan CAMPO/POZO/ACTIVO, que están en el vocabulario)."""
    return any(p in _get()["anclados"] for p in (patrones_lista or []))
