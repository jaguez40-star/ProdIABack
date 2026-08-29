import yaml, pathlib, pytest
from app.features.consulta import maquina

CASOS = yaml.safe_load(
    (pathlib.Path(__file__).parents[1] / "app/features/consulta/golden/estado_fixtures.yaml").read_text(encoding="utf-8"))

@pytest.mark.parametrize("caso", CASOS, ids=[c["nombre"] for c in CASOS])
def test_estado(caso, monkeypatch):
    # inyectar los slots directamente (sin LLM): parchear extraer()
    monkeypatch.setattr(maquina, "extraer", lambda _t: {**{"entidad": None, "nivel": None, "producto": None,
                        "periodo": None, "agregacion": None}, **caso["slots"]})
    cid = "test-" + caso["nombre"]
    out = maquina.preguntar("(texto irrelevante)", cid)
    assert out["status"] == caso["espera_status"]
    if caso["espera_status"] == "pendiente":
        niveles = sorted(o["id"].split("::")[0] for o in out["opciones"])
        assert niveles == sorted(caso["espera_opciones_niveles"])
        # responder y verificar intent
        op = next(o for o in out["opciones"] if o["id"].startswith(caso["responder_con_nivel"] + "::"))
        fin = maquina.responder(cid, op["id"])
        assert fin["status"] == "completo"
        for k, v in caso["espera_intent"].items():
            assert str(fin["intent"][k]).upper() == str(v).upper()
    elif caso["espera_status"] == "completo":
        for k, v in caso["espera_intent"].items():
            assert str(out["intent"][k]).upper() == str(v).upper()
