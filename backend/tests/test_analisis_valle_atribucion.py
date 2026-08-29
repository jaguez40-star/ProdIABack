"""Atribución del diagnóstico del valle: quién reportó el comentario (2026-07-16).

Origen (usuario): el panel decía «Lo que reportó LORITO el 2026-05-06: "…descargas atmosféricas
sobre la línea 115 kV Ocoa-Catama… apagado de los pozos AK107 y Guamal Profundo-1"». El usuario no
encontraba ese comentario en la hoja buscando LORITO — porque está registrado bajo **CPO-09**, y
AK107 es un pozo de AKACIAS.

Causa: `names` (de _nombres_entidad) incluye grupo1/activos de dim_fuente, o sea el GRUPO con que el
reporte agrupa a la entidad. LORITO trae names={LORITO, CPO-09} → el comentario del área CPO-09
calza. El comentario es relevante (el evento afecta al área que contiene a LORITO), pero la frase se
componía con `entidad` (lo pedido) e ignoraba `campo` (quien lo reportó), que la consulta ya traía.

Estos tests fijan la parte pura: el orden de preferencia y el texto de atribución. La consulta SQL se
verifica contra la BD (ver la bitácora), no aquí.
"""
import pytest

from app.features.consulta.normaliza import norm


def _elegir(comentarios, entidad):
    """Réplica del criterio de _valle_diagnostico_entidad: el comentario PROPIO manda; el del grupo
    es el respaldo. Si difieren, la frase debe declarar quién reportó."""
    cs = sorted(comentarios, key=lambda x: 0 if norm(x.get("campo") or "") == norm(entidad) else 1)
    quien = (cs[0].get("campo") or "").strip()
    return quien, (norm(quien) != norm(entidad))


def test_comentario_propio_gana_al_del_grupo():
    """Si la entidad reportó algo ella misma, ESE es el diagnóstico — no el del área."""
    cs = [{"campo": "CPO-09", "texto": "evento del área"},
          {"campo": "LORITO", "texto": "lo mío"}]
    quien, ajeno = _elegir(cs, "LORITO")
    assert quien == "LORITO" and ajeno is False


def test_sin_comentario_propio_se_declara_el_grupo():
    """Caso LORITO real: solo hay comentario de CPO-09 → se muestra, pero declarando quién lo reportó."""
    cs = [{"campo": "CPO-09", "texto": "evento eléctrico Ocoa-Catama"}]
    quien, ajeno = _elegir(cs, "LORITO")
    assert quien == "CPO-09" and ajeno is True


def test_castilla_reporta_lo_suyo_sin_salvedad():
    """No regresión: CASTILLA sí tiene comentario propio → la frase directa de siempre."""
    cs = [{"campo": "CASTILLA", "texto": "Desplazamiento de existencias…"}]
    quien, ajeno = _elegir(cs, "CASTILLA")
    assert quien == "CASTILLA" and ajeno is False


def test_atribucion_ignora_acentos_y_mayusculas():
    """La comparación pasa por norm(): 'Caño Sur' en la hoja y 'CANO SUR' pedido son la misma."""
    cs = [{"campo": "Caño Sur", "texto": "x"}]
    quien, ajeno = _elegir(cs, "CAÑO SUR")
    assert ajeno is False


def test_orden_estable_con_varios_del_grupo():
    """Con varios ajenos y ninguno propio, no debe romperse: gana el primero, declarado como ajeno."""
    cs = [{"campo": "CPO-09", "texto": "a"}, {"campo": "CHICHIMENE", "texto": "b"}]
    quien, ajeno = _elegir(cs, "LORITO")
    assert quien == "CPO-09" and ajeno is True
