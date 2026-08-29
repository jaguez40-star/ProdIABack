"""Tests PUROS (sin BD, sin LLM) del detector de preguntas incompletas (accion_sin_objeto).

Espejo de test_no_soportado.py. El caso de origen es real: tras "¿Quieres ver la producción de
CASTILLA o consultar otro campo o activo?", el usuario escribió "sí muéstrame" y recibió un
rechazo de FUERA DE DOMINIO para una pregunta que está DENTRO del dominio pero incompleta.
"""
from app.features.consulta_v2 import incompleta


# --- detectar(): dispara cuando la acción no tiene sobre qué recaer ----------------------------
def test_dispara_verbo_sin_objeto():
    # El caso REAL que originó la regla.
    assert incompleta.detectar("sí muestrame", False, None) == "accion_sin_objeto"
    assert incompleta.detectar("muéstrame", False, None) == "accion_sin_objeto"
    assert incompleta.detectar("dame", False, None) == "accion_sin_objeto"
    assert incompleta.detectar("gráficame eso", False, None) == "accion_sin_objeto"


def test_dispara_con_los_verbos_de_narracion():
    # Familia añadida por el usuario (D3): son los que más invitan a una respuesta larga.
    assert incompleta.detectar("cuéntame", False, None) == "accion_sin_objeto"
    assert incompleta.detectar("explícame", False, None) == "accion_sin_objeto"
    assert incompleta.detectar("preséntame eso", False, None) == "accion_sin_objeto"


def test_norm_pliega_acentos():
    # norm() pasa a MAYÚSCULAS y quita acentos: con y sin tilde deben dar lo mismo, o el regex
    # (escrito sin acentos) no calzaría nunca sobre el texto tal como lo escribe el usuario.
    assert incompleta.detectar("cuentame", False, None) == incompleta.detectar("cuéntame", False, None)
    assert incompleta.detectar("explicame", False, None) == incompleta.detectar("explícame", False, None)


# --- detectar(): NO dispara — el riesgo real de esta regla es el falso positivo ----------------
def test_no_dispara_si_hay_objeto_de_dominio():
    # Verbo ⇒ COMPLEMENTO, no verbo ⇒ entidad. El tráfico GLOBAL es válido y no tiene entidad:
    # sin la condición `nivel is None` esta regla lo rechazaría entero.
    assert incompleta.detectar("muéstrame el desempeño del mes", False, "fuerte") is None
    assert incompleta.detectar("dame el ranking de campos", False, "estructural") is None
    assert incompleta.detectar("explícame el gap de crudo", False, "fuerte") is None


def test_no_dispara_si_hay_entidad():
    assert incompleta.detectar("muéstrame Castilla", True, None) is None
    # H5: "dame Rubiales" es la trampa A3 del golden (instancia sin verbo CLASIFICABLE) — es la
    # regla SIMÉTRICA, deliberadamente fuera de alcance. No debe caer en ésta.
    assert incompleta.detectar("dame Rubiales", True, None) is None


def test_no_dispara_sin_verbo_de_accion():
    assert incompleta.detectar("hola", False, None) is None
    assert incompleta.detectar("", False, None) is None
    assert incompleta.detectar(None, False, None) is None


def test_exclusiones_deliberadas():
    # "dale" pertenece a maquina_q._AFIRM: capturarlo aquí se lo robaría al drill de afirmación
    # de _continuacion, que es quien sabe resolverlo por contexto.
    assert incompleta.detectar("dale", False, None) is None
    assert incompleta.detectar("listo", False, None) is None
    # CUENTA sola es sustantivo DEL DOMINIO; solo se acepta CUENTAME.
    assert incompleta.detectar("la cuenta contable", False, None) is None
    # LISTA sola es sustantivo frecuente; solo se acepta LISTAME.
    assert incompleta.detectar("la lista", False, None) is None


# --- mensaje(): pide el complemento, sin sí/no (H1) -------------------------------------------
def test_mensaje_con_contexto_nombra_la_entidad_como_candidata():
    m = incompleta.mensaje("accion_sin_objeto", "CASTILLA")
    assert "CASTILLA" in m
    assert "no dijiste sobre qué" in m
    # H1: un "¿Quieres…?" haría que un "sí" cayera en el drill de afirmación de _continuacion.
    assert "¿Quieres" not in m
    # Determinista: la plantilla no inventa cifras.
    assert not any(ch.isdigit() for ch in m)


def test_mensaje_sin_contexto_no_nombra_ninguna_entidad():
    m = incompleta.mensaje("accion_sin_objeto")
    assert "no dijiste sobre qué" in m
    assert "campo" in m and "gerencia" in m
    assert "¿Quieres" not in m


def test_mensaje_no_promete_estar_fuera_de_dominio():
    # El bug reportado: se respondía "fuera de mi ámbito" a una pregunta DEL tema.
    for m in (incompleta.mensaje("accion_sin_objeto", "CASTILLA"),
              incompleta.mensaje("accion_sin_objeto")):
        assert "fuera de" not in m.lower()
        assert "exclusivamente" not in m.lower()
