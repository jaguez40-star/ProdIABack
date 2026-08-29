"""Tests del puente level-shift gerencia→vicepresidencia en Cuantificar (R2). Mayoría PUROS (sin BD,
monkeypatch); 1 test opcional contra BD real (se salta con gracia si Postgres no está — mismo patrón
`_engine_o_skip` que ya usa tests/test_consulta_v2_clasificador.py)."""
import pytest

import app.features.consulta_v2.cuantificar.resolver as R
import app.features.consulta_v2.cuantificar.ejecutor as E


# --- resolver._marcar_puente: solo marca cuando es EXCLUSIVAMENTE vicepresidencia -----------------
def test_marca_puente_si_exclusivamente_vp(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR", "CPV"})
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GOR"})
    assert r.get("puente") is True


def test_no_marca_si_no_es_vp(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GNS"})   # sin match en robustez
    assert "puente" not in r


def test_no_marca_si_ambiguo_gan_excluido_del_lookup(monkeypatch):
    # _cargar_vp_robustez ya excluye los ambiguos (vps - gers) — GAN nunca debe estar en el set.
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})   # simula que GAN quedó fuera
    r = R._marcar_puente({"nivel": "gerencia", "rama": "A", "valor": "GAN"})
    assert "puente" not in r


def test_no_marca_si_nivel_no_es_gerencia(monkeypatch):
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"CASTILLA"})   # aunque "coincida" el valor
    r = R._marcar_puente({"nivel": "campo", "rama": "A", "valor": "CASTILLA"})
    assert "puente" not in r


def test_cargar_vp_robustez_degrada_sin_lanzar(monkeypatch):
    # Si get_engine() falla (BD no disponible), NUNCA lanza -> set vacío -> ningún relabel.
    R._VP_ROBUSTEZ = None
    def _boom():
        raise RuntimeError("BD no disponible")
    monkeypatch.setattr(R, "get_engine", _boom)
    assert R._cargar_vp_robustez() == set()
    R._VP_ROBUSTEZ = None   # limpiar el cache para no afectar otros tests


# --- ejecutor._etiqueta_nivel: el texto usa "la Vicepresidencia" SOLO si puente=True --------------
def test_etiqueta_usa_vicepresidencia_si_puente():
    assert E._etiqueta_nivel("gerencia", {"puente": True}) == "la Vicepresidencia"


def test_etiqueta_normal_sin_puente():
    assert E._etiqueta_nivel("gerencia", {}) == "la Gerencia"
    assert E._etiqueta_nivel("campo", {}) == "el Campo"
    assert E._etiqueta_nivel("vicepresidencia", {}) == "la Vicepresidencia"


# --- GUARDA DE REGRESIÓN contra BD real: CPV/GAN/GXO excluidos, GOR incluido ----------------------
# Mismo error que la auditoría de este plan cometió en su primer borrador (revisar solo
# rob_vicepresidencia sin cruzar rob_gerencia) — verificado 2026-08-03: rob_vicepresidencia ∩
# rob_gerencia = {CPV, GAN, GXO}. Se saltan con gracia si Postgres no está disponible.
def _engine_o_skip():
    try:
        from app.core.db import get_engine
        import sqlalchemy as sa
        eng = get_engine()
        with eng.connect() as c:
            c.execute(sa.text("SELECT 1"))
        return eng
    except Exception:
        pytest.skip("Postgres no disponible")


def test_bd_real_gor_incluido_cpv_gan_gxo_excluidos():
    _engine_o_skip()
    R._VP_ROBUSTEZ = None   # forzar recarga (no reusar cache de otro test)
    vps = R._cargar_vp_robustez()
    assert "GOR" in vps, "GOR (caso insignia, sin ambigüedad) debe estar"
    for amb in ("CPV", "GAN", "GXO"):
        assert amb not in vps, f"{amb} es AMBIGUO (también rob_gerencia) — NO debe relabelearse"
    R._VP_ROBUSTEZ = None   # limpiar para no afectar otros tests
