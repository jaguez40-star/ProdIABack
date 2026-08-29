"""Tests del clasificador de grupo (Motor Q v2 · Fase 1).

Capa 1 pura (sin BD, sin LLM) + parseo defensivo de Capa 2 + señales (similitud pura).
Los tests de log/señales que requieren BD se marcan con el fixture de engine real y se
saltan limpio si no hay Postgres disponible (mismo criterio que el resto de la suite).
H3: nada de aquí escribe en la libreta (clasificar se prueba vía capa1/parsear, no vía API).
"""
import pytest

from app.features.consulta_v2.patrones import clasificar_capa1, es_anclado
from app.features.consulta_v2.dominio import hay_palabra_dominio, nivel_dominio
from app.features.consulta_v2.clasificador_llm import parsear
from app.features.consulta_v2.senales import similitud


# ---------------- Capa 1 (regex, pura) ----------------

def test_capa1_jerarquizar_pertenencia():
    g, pats = clasificar_capa1("¿A qué activo pertenece Cajúa?")
    assert g == "jerarquizar" and pats


def test_capa1_cuantificar_directo():
    g, _ = clasificar_capa1("¿Cuánto crudo produjo Castilla?")
    assert g == "cuantificar"


def test_capa1_analizar_porque():
    g, _ = clasificar_capa1("¿Por qué está mal Castilla?")
    assert g == "analizar"


def test_capa1_precedencia_analizar_gana_a_cuantificar():
    # "cuánto" (cuantificar) + "meta" (analizar) → analizar (motor_Q.md §1.1)
    g, _ = clasificar_capa1("¿Cuánto nos falta para la meta?")
    assert g == "analizar"


def test_capa1_huella_gana_a_cuantos():
    # Trampa conocida: pregunta por DISPONIBILIDAD, no por cifra (precedencia máxima)
    g, pats = clasificar_capa1("¿Cuántos días con reporte hay de Rubiales?")
    assert g == "jerarquizar"
    assert any("REPORTE" in p or "DIAS" in p for p in pats)


def test_capa1_huella_que_informacion():
    g, _ = clasificar_capa1("¿Qué información hay de Rubiales?")
    assert g == "jerarquizar"


def test_capa1_sin_senales_baja_a_capa2():
    g, pats = clasificar_capa1("Castilla")
    assert g is None and pats == []


def test_capa1_texto_vacio():
    g, pats = clasificar_capa1("")
    assert g is None and pats == []


def test_capa1_conteo_jerarquia_es_jerarquizar():
    # R1 (2026-08-03, HALLAZGO_clasificador_conteo_jerarquia.md): "cuántos X tiene Y" es una pregunta
    # de ESTRUCTURA (nº de sub-entidades), no de producción. Antes de R1 este caso clasificaba
    # 'cuantificar' (el bug del hallazgo, ver test_conteo_jerarquia.py) — ese era el defecto, no el
    # contrato correcto. precedencia_maxima.jerarquizar ahora lo atrapa con el verbo estructural.
    g, _ = clasificar_capa1("¿Cuántos pozos tiene Apiay?")
    assert g == "jerarquizar"


def test_capa1_acentos_normalizados():
    # norm() pliega acentos: "producción" debe calzar 'PRODUCCION DE'
    g, _ = clasificar_capa1("producción de Rubiales")
    assert g == "cuantificar"


# ---------------- Filtro de dominio (motor_Q.md §1.2) ----------------

def test_vocabulario_detecta_crudo():
    assert hay_palabra_dominio("¿cuánto crudo se perdió?") is True

def test_vocabulario_ignora_offtopic():
    assert hay_palabra_dominio("¿cuánto es la raíz cuadrada de 2?") is False

def test_anclado_p50():
    # [2026-08-02] P50\b sigue anclado (a diferencia de META/DETRACTORES/QUE CAMPOS PESAN/
    # CUANTOS DIAS CON REPORTE, retirados tras el hallazgo del lote de prueba en vivo).
    g, pats = clasificar_capa1("¿cuál es el P50 de este mes?")
    assert g == "analizar" and es_anclado(pats) is True

def test_no_anclado_cuantos_generico():
    g, pats = clasificar_capa1("¿cuánto es la raíz cuadrada de 2?")
    assert g == "cuantificar" and es_anclado(pats) is False

def test_no_anclado_detractores_ahora_generico():
    # [2026-08-02] DETRACTORES pasó a genérico: la palabra sola ya no basta, necesita
    # entidad o vocabulario (verificado en vivo con "detractores del rendimiento académico").
    g, pats = clasificar_capa1("¿cuáles son los detractores del rendimiento académico?")
    assert g == "analizar" and es_anclado(pats) is False

def test_anclados_existen_en_patrones():
    # Guarda de deriva (H-H): cada cadena de patrones_anclados existe entre los patrones reales.
    from app.features.consulta_v2 import patrones as P
    c = P._get()
    reales = {p for _, _, p in c["max"]}
    for pares in c["grupos"].values():
        reales |= {p for _, p in pares}
    faltan = c["anclados"] - reales
    assert not faltan, f"patrones_anclados no presentes entre los patrones: {faltan}"

# Filtro end-to-end SIN entidad ni vocabulario → OUT. No usa LLM (la regex atrapó) y detectar_entidad
# degrada a None sin BD → estable con o sin Postgres. log=False: no escribe libreta. Import LOCAL (H-C).
def test_filtro_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuánto es la raíz cuadrada de 2?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_filtro_que_es_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿qué es HBOMAX?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_filtro_vocabulario_conserva_grupo():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuánto crudo se perdió este mes?", log=False)
    assert d["grupo"] == "cuantificar" and d["capa_resolutora"] == "regex"

def test_filtro_anclado_no_va_a_out():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuál es el gap contra el presupuesto?", log=False)
    assert d["grupo"] == "analizar" and d["capa_resolutora"] == "regex"

# [2026-08-02] Las 4 anclas retiradas (§ patrones_grupo.yaml), verificadas end-to-end: sobre un
# tema ajeno, sin entidad ni vocabulario, ahora SÍ caen al filtro y van a desconocido.
def test_filtro_meta_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuál es la meta de ahorro que tengo para este año?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_filtro_detractores_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuáles son los detractores del rendimiento académico?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

def test_nivel_dominio_fuerte():
    assert nivel_dominio("¿cuánto crudo se perdió?") == "fuerte"

def test_nivel_dominio_estructural():
    assert nivel_dominio("¿cuántos campos hay en total?") == "estructural"

def test_nivel_dominio_ninguno():
    assert nivel_dominio("¿cuánto es la raíz cuadrada de 2?") is None

def test_nivel_dominio_fuerte_gana_a_estructural():
    # D3: "detractores de crudo" trae CRUDO (fuerte) + implícitamente el dominio → NO escala.
    # Sin esta precedencia, la escalada rompía 4 casos legítimos del golden.
    assert nivel_dominio("explícame los detractores de crudo en los campos") == "fuerte"

def test_escalada_llm_decide_desconocido(monkeypatch):
    # Franja estructural + el LLM entiende el contexto ajeno → su veredicto manda.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": None})
    d = M.clasificar("¿qué campos pesan más en la dieta mediterránea?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+llm"

def test_escalada_llm_confirma_dominio(monkeypatch):
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "cuantificar", "entidad": None, "diag": None})
    d = M.clasificar("¿cuántos campos hay en total?", log=False)
    assert d["grupo"] == "cuantificar" and d["capa_resolutora"] == "regex+llm"

def test_escalada_fallback_conserva_regex(monkeypatch):
    # D4 · EL TEST MÁS IMPORTANTE DEL PLAN: si el LLM falla, se conserva el grupo de la REGEX.
    # Sin esto, cada timeout de Ollama se tragaría una pregunta legítima de producción.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": "timeout"})
    d = M.clasificar("¿qué campos están por debajo de la meta?", log=False)
    assert d["grupo"] == "analizar"                      # el de la regex, NO desconocido
    assert d["capa_resolutora"] == "regex+llm_fallo"
    assert d["llm_diag"] == "timeout"

def test_escalada_no_toma_entidad_del_llm(monkeypatch):
    # D6: se escaló porque el catálogo no halló entidad; si el LLM la inventa, se ignora.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "analizar", "entidad": "MEDITERRANEA", "diag": None})
    d = M.clasificar("¿qué campos pesan más en la dieta mediterránea?", log=False)
    assert d["entidad_cruda"] != "MEDITERRANEA"

def test_vocabulario_fuerte_no_escala(monkeypatch):
    # Certeza fuerte → enruta directo, el LLM NI SE LLAMA (si se llamara, este test explota).
    import app.features.consulta_v2.maquina_q as M
    def _boom(t):
        raise AssertionError("la Capa 2 NO debe invocarse con vocabulario fuerte")
    monkeypatch.setattr(M, "clasificar_capa2", _boom)
    d = M.clasificar("explícame los detractores de crudo", log=False)
    assert d["grupo"] == "analizar" and d["capa_resolutora"] == "regex"

def test_mensaje_no_miente_en_fallback(monkeypatch):
    # H-I: si el LLM no respondió, el mensaje NO puede anunciar "vía LLM" — decidió la regex.
    import app.features.consulta_v2.maquina_q as M
    monkeypatch.setattr(M, "clasificar_capa2",
                        lambda t: {"grupo": "desconocido", "entidad": None, "diag": "timeout"})
    d = M.clasificar("¿qué campos están por debajo de la meta?", log=False)
    assert "vía regex" in d["mensaje"] and "vía LLM" not in d["mensaje"]

def test_filtro_dias_reporte_offtopic_va_a_desconocido():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuántos días con reporte hay sobre el clima en Bogotá?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"

# Control positivo: la MISMA palabra (meta) con vocabulario de producción SÍ se queda en
# dominio — la regla exacta que dio el usuario ("meta debe ir acompañada de producción").
def test_filtro_meta_con_produccion_se_queda_en_dominio():
    from app.features.consulta_v2.maquina_q import clasificar
    d = clasificar("¿cuánto nos falta para la meta de producción?", log=False)
    assert d["grupo"] == "analizar" and d["capa_resolutora"] == "regex"


# ---------------- Capa 2 (parseo defensivo, sin red) ----------------

def test_parsear_json_valido():
    r = parsear('{"grupo": "analizar", "entidad": "Castilla"}')
    assert r == {"grupo": "analizar", "entidad": "Castilla", "diag": None}


def test_parsear_entidad_null():
    r = parsear('{"grupo": "cuantificar", "entidad": null}')
    assert r["grupo"] == "cuantificar" and r["entidad"] is None


def test_parsear_json_malformado():
    r = parsear("esto no es json {grupo:")
    assert r["grupo"] == "desconocido" and r["diag"] == "json_invalido"


def test_parsear_grupo_fuera_del_enum():
    r = parsear('{"grupo": "resumir", "entidad": null}')
    assert r["grupo"] == "desconocido" and r["diag"] == "grupo_invalido"


def test_parsear_no_dict():
    r = parsear('["analizar"]')
    assert r["grupo"] == "desconocido" and r["diag"] == "grupo_invalido"


def test_parsear_entidad_no_string():
    r = parsear('{"grupo": "analizar", "entidad": 42}')
    assert r["grupo"] == "analizar" and r["entidad"] is None


# ---------------- Señales (similitud pura) ----------------

def test_similitud_identica():
    assert similitud("cuánto produjo Castilla", "cuanto produjo castilla") == 1.0


def test_similitud_reformulacion_alta():
    s = similitud("cuánto crudo produjo Castilla", "cuánto crudo produjo Castilla este mes")
    assert s >= 0.5


def test_similitud_distinta():
    assert similitud("cuánto produjo Castilla", "por qué cayó Cusiana") < 0.3


def test_similitud_vacia():
    assert similitud("", "algo") == 0.0


# ---------------- Log + señales con BD (se saltan sin Postgres) ----------------

def _engine_o_skip():
    try:
        from app.core.db import get_engine
        eng = get_engine()
        with eng.connect() as c:
            c.execute(__import__("sqlalchemy").text("SELECT 1"))
        return eng
    except Exception:
        pytest.skip("Postgres no disponible")


def test_log_registrar_y_veredicto():
    import sqlalchemy as sa
    from app.features.consulta_v2.log import registrar, poner_veredicto
    eng = _engine_o_skip()
    log_id = registrar("[test] pregunta de prueba", "cuantificar", "regex",
                       patrones=["CUANT"], usuario="[test]")
    assert log_id
    with eng.connect() as c:
        v = c.execute(sa.text("SELECT veredicto FROM core.clasificacion_log WHERE id=:i"),
                      {"i": log_id}).scalar()
    assert v == "pendiente"
    assert poner_veredicto(log_id, "corregido_usuario", grupo_correcto="analizar",
                           fuente="usuario")
    with eng.begin() as c:
        row = c.execute(sa.text(
            "SELECT veredicto, grupo_correcto FROM core.clasificacion_log WHERE id=:i"),
            {"i": log_id}).one()
        c.execute(sa.text("DELETE FROM core.clasificacion_log WHERE id=:i"), {"i": log_id})
    assert row.veredicto == "corregido_usuario" and row.grupo_correcto == "analizar"


def test_veredicto_invalido_rechazado():
    from app.features.consulta_v2.log import poner_veredicto
    _engine_o_skip()
    assert poner_veredicto(999999999, "veredicto_falso") is False
    # corregido sin grupo_correcto válido → rechazado sin tocar BD
    assert poner_veredicto(999999999, "corregido_usuario", grupo_correcto="nada") is False


def test_senal_v1_marca_sospecha():
    import sqlalchemy as sa
    from app.features.consulta_v2.log import registrar
    from app.features.consulta_v2.senales import registrar_senal_v1
    eng = _engine_o_skip()
    log_id = registrar("[test] cuánto produjo el campo de prueba xyz", "cuantificar",
                       "regex", usuario="[test-senal]")
    try:
        # misma pregunta, mismo usuario, dentro de ventana → sospecha
        assert registrar_senal_v1("[test] cuánto produjo el campo de prueba xyz",
                                  usuario="[test-senal]") is True
        with eng.connect() as c:
            v = c.execute(sa.text("SELECT veredicto FROM core.clasificacion_log WHERE id=:i"),
                          {"i": log_id}).scalar()
        assert v == "sospecha"
        # texto distinto → NO marca (además la fila ya no está 'pendiente')
        assert registrar_senal_v1("por qué cayó otra cosa", usuario="[test-senal]") is False
    finally:
        with eng.begin() as c:
            c.execute(sa.text("DELETE FROM core.clasificacion_log WHERE id=:i"), {"i": log_id})


# ---------------- Respuesta al grupo OUT (respuesta_out, sin red) ----------------

def test_out_llm_redacta(monkeypatch):
    # El LLM devuelve JSON bueno → se usa su texto (fuente llm).
    import app.features.consulta_v2.respuesta_out as R
    monkeypatch.setattr(R._s, "consulta_out_llm", True)
    monkeypatch.setattr(R, "_llm", lambda p: '{"respuesta": "Eso está fuera de contexto. ¿Cifras o análisis?"}')
    r = R.redactar_out("¿cuál es la capital de Francia?", usuario="Javier")
    assert r["fuente"] == "llm" and r["diag"] is None
    assert "fuera de contexto" in r["texto"]


def test_out_llm_falla_cae_al_estatico(monkeypatch):
    # D4: timeout/JSON malo → SIEMPRE el floor estático, nunca vacío ni salida cruda.
    import app.features.consulta_v2.respuesta_out as R
    monkeypatch.setattr(R._s, "consulta_out_llm", True)
    monkeypatch.setattr(R, "_llm", lambda p: "esto no es json")
    r = R.redactar_out("cuéntame un chiste")
    assert r["fuente"] == "fallback" and r["diag"] == "json_invalido"
    assert r["texto"] == R.TEXTO_FALLBACK


def test_out_flag_off_no_llama_llm(monkeypatch):
    # Con el flag off el LLM NI SE LLAMA (si se llamara, explota) → texto estático.
    import app.features.consulta_v2.respuesta_out as R
    monkeypatch.setattr(R._s, "consulta_out_llm", False)
    def _boom(p):
        raise AssertionError("con el flag off NO se debe invocar al LLM")
    monkeypatch.setattr(R, "_llm", _boom)
    r = R.redactar_out("¿cuánto pesa la Tierra?")
    assert r["fuente"] == "fallback" and r["diag"] == "flag_off"
    assert r["texto"] == R.TEXTO_FALLBACK


def test_out_solo_en_trafico_real(monkeypatch):
    # clasificar(log=False) NO debe redactar con LLM (golden/pytest no gastan generación).
    # Frase que cae por regex+filtro → desconocido sin tocar la Capa 2 (offline determinista).
    import app.features.consulta_v2.maquina_q as M
    def _boom(t, usuario=None, contexto=None):
        raise AssertionError("redactar_out NO debe llamarse con log=False")
    monkeypatch.setattr(M.respuesta_out, "redactar_out", _boom)
    d = M.clasificar("¿qué información hay de Bogotá?", log=False)
    assert d["grupo"] == "desconocido" and d["capa_resolutora"] == "regex+filtro"
    assert d["mensaje"] == M.respuesta_out.TEXTO_FALLBACK


# ---------------- Respuesta JERARQUIZAR (respuesta_jerarquizar, con BD) ----------------

def test_jerarquizar_activo():
    _engine_o_skip()
    from app.features.consulta_v2.respuesta_jerarquizar import responder
    r = responder("¿Qué campos tiene el activo Castilla?")
    assert "Activo" in r and "CASTILLA" in r


def test_jerarquizar_puente_level_shift():
    # GOR es VP en robustez pero el usuario lo llama "gerencia" → copia A (puente).
    _engine_o_skip()
    from app.features.consulta_v2.respuesta_jerarquizar import responder
    r = responder("¿cuáles campos tiene la gerencia GOR?")
    assert "Vicepresidencia GOR" in r and "llamas" in r


def test_jerarquizar_sin_puente_falso():
    # 🔑 El nivel del padre buscado ("¿a qué ACTIVO pertenece Cajúa?") NO debe disparar el puente:
    # Cajúa es un Campo (tercero), no un activo. Sin la regla de "palabra previa" esto mentía.
    _engine_o_skip()
    from app.features.consulta_v2.respuesta_jerarquizar import responder
    r = responder("¿A qué activo pertenece Cajúa?")
    assert "llamas" not in r and "Campo" in r


def test_jerarquizar_sin_entidad():
    _engine_o_skip()
    from app.features.consulta_v2.respuesta_jerarquizar import responder
    r = responder("¿qué campos hay?")
    assert "necesito una entidad" in r


# ---------------- Memoria conversacional (continuación, parte 2) ----------------

def _ctx_gor():
    from app.features.consulta_v2.normaliza import norm
    return {"entidad": "GOR", "nivel": "vicepresidencia",
            "hijos": {norm(x) for x in ["POE", "PPÑ", "CAÑO SUR", "RUBIALES"]},
            "ofrece_produccion": True}


def test_continuacion_larga_no_es_continuacion():
    # Frase larga (>5 tokens) = pregunta propia, NO continuación → None (sin tocar BD).
    from app.features.consulta_v2.maquina_q import _continuacion
    assert _continuacion("¿qué campos tiene el activo Apiay?", _ctx_gor()) is None


def test_continuacion_afirmativo_va_a_produccion():
    # "sí" corto + la memoria ofrece producción → produccion de la entidad recordada.
    from app.features.consulta_v2.maquina_q import _continuacion
    assert _continuacion("sí", _ctx_gor()) == "produccion de GOR"


def test_continuacion_hijo_navega():
    # "POE" (hijo) → navega a esa entidad (jerarquizar). Necesita catálogo (POE es de robustez).
    _engine_o_skip()
    from app.features.consulta_v2.maquina_q import _continuacion
    assert _continuacion("POE", _ctx_gor()) == "que es POE"


def test_log_false_no_usa_memoria():
    # El golden/pytest (log=False) NO deben tocar la memoria: "POE" suelto → desconocido, no navega.
    import app.features.consulta_v2.maquina_q as M
    d = M.clasificar("POE", conversation_id="x", log=False)
    assert d["grupo"] == "desconocido" and not d.get("continuacion")


def test_continuacion_estructural_pronombre_elidido():
    # "¿a qué activo pertenece?" / "y sus campos?" (sin nombrar) → se refieren a la entidad del
    # contexto → se reescriben a "que es {entidad}" (robusto, siempre clasifica jerarquizar).
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"entidad": "CHICHIMENE", "nivel": "campo", "hijos": set(), "ofrece_produccion": True}
    assert _continuacion("¿a qué activo pertenece?", ctx) == "que es CHICHIMENE"
    assert _continuacion("y sus campos?", ctx) == "que es CHICHIMENE"
    assert _continuacion("gracias", ctx) is None      # sin pista estructural → no es continuación


def test_continuacion_acumulado_frase_natural():
    """Aceptar la oferta del cierre con una frase natural de 6-8 tokens.

    Bug real (2026-08-24, visto en la app): el cierre de cuantificar OFRECE
    "¿Quieres el acumulado del año?" y el usuario responde "Sí muéstrame el
    acumulado del año" (6 tokens). Se pasaba del corte de <=5 y caía desnuda a la
    Capa 2 -> Desconocido: el motor no reconocía su propia oferta. La pista de que
    era LONGITUD y no sentido: con coma ("sí, el acumulado del año", 5 tokens)
    funcionaba y sin coma no.
    """
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "AKACIAS", "producto": "crudo",
           "nivel": "campo", "metrica": "real"}
    # El caso reportado, y la cortesía más larga que sigue entrando (8 tokens).
    assert _continuacion("Sí muéstrame el acumulado del año", ctx) == "acumulado de AKACIAS"
    assert _continuacion("si dame el acumulado del ano por favor", ctx) == "acumulado de AKACIAS"
    # Lo que ya funcionaba no se toca.
    assert _continuacion("sí", ctx) == "acumulado de AKACIAS"
    assert _continuacion("si, el acumulado del año", ctx) == "acumulado de AKACIAS"


def test_continuacion_acumulado_no_secuestra_autocontenidas():
    """La excepción de longitud es estrecha a propósito: no debe abrir el corte.

    Guarda `not ent`: una frase que nombra SU entidad es autocontenida y debe
    procesarse entera. Guarda _REF_CONTINUA_KW: "promedio del año" contiene
    "DEL ANO" y su rama va antes (mismo motivo que el bug de 2026-08-02).
    """
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "AKACIAS", "producto": "crudo",
           "nivel": "campo", "metrica": "real"}
    assert _continuacion("cual es el acumulado del ano de CASTILLA", ctx) is None
    assert _continuacion("cual es el promedio del ano de este campo", ctx) is None
    # Más de 8 tokens sigue siendo intención propia, no continuación.
    assert _continuacion("oye una cosa dame por favor el acumulado del ano completo ya", ctx) is None


def test_continuacion_acumulado_preserva_producto():
    """AF9: un acumulado tras un N1 de gas no puede volver a crudo."""
    from app.features.consulta_v2.maquina_q import _continuacion
    ctx = {"grupo": "cuantificar", "entidad": "CUPIAGUA", "producto": "gas",
           "nivel": "campo", "metrica": "real"}
    assert _continuacion("si muestrame el acumulado del ano", ctx) == "acumulado de gas de CUPIAGUA"


def test_jerarquia_drill_down_verbos_alternos():
    """Drill-down con verbos distintos de TIENE/CONFORMAN.

    Medido 2026-08-24 contra el motor: "cuelgan" y "desglosa" caían a desconocido
    mientras la misma pregunta con "tiene" resolvía bien. El vocabulario cubría una
    sola forma por familia y se perdía con los sinónimos naturales.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿Qué campos cuelgan de la VP GCH?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("Desglósame la gerencia PDH por campo", log=False)["grupo"] == "jerarquizar"
    # La forma que ya funcionaba no se toca.
    assert clasificar("¿Qué campos tiene el activo Chichimene?", log=False)["grupo"] == "jerarquizar"


def test_jerarquia_rollup_en_que_nivel():
    """"¿EN QUÉ VP está...?" — la tercera preposición del roll-up.

    Solo existían DE QUE <nivel> y A QUE <nivel>; EN QUE no, pese a ser la forma
    natural de preguntar por la vicepresidencia. Se añadió además VP como
    abreviatura, que tampoco estaba en ninguna de las tres.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿En qué VP está la gerencia PDH?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿De qué gerencia depende el activo Chichimene?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿A qué activo pertenece Chichimene SW?", log=False)["grupo"] == "jerarquizar"


def test_jerarquia_desambiguacion_conversacional():
    """"Cuando digo X, ¿a qué te refieres?" — un nombre puede ser activo Y campo."""
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("Cuando digo Chichimene, ¿a qué te refieres?", log=False)["grupo"] == "jerarquizar"
    # La forma explícita ya funcionaba.
    assert clasificar("¿Chichimene es activo o campo?", log=False)["grupo"] == "jerarquizar"


def test_jerarquia_no_secuestra_otras_familias():
    r"""Los patrones nuevos exigen DOBLE señal estructural a propósito.

    "desglósame la PRODUCCIÓN por campo" es cuantificar y "el GAP por causa" es
    analizar: sin la guarda de nivel, DESGLOS\w* se los habría llevado. Igual con
    EN QUE, que va atado a ESTA/SE ENCUENTRA/QUEDA para no capturar "¿en qué campos
    hubo mantenimientos?" (analizar) ni "¿en qué mes produjo más?" (cuantificar).
    Verificado contra la línea base tomada antes del cambio.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("Desglósame la producción de crudo por campo", log=False)["grupo"] == "cuantificar"
    assert clasificar("Desglósame el gap de crudo por causa", log=False)["grupo"] == "analizar"
    assert clasificar("¿En qué campos hubo mantenimientos?", log=False)["grupo"] == "analizar"
    assert clasificar("¿En qué mes produjo más Castilla?", log=False)["grupo"] == "cuantificar"


def test_jerarquia_cuantos_se_compone():
    """Las TRES formas de la familia "componer" dan la misma respuesta: la estructura.

    Corregido 2026-08-24 tras verlo fallar en la app. La decisión inicial fue dejar
    "¿de CUÁNTOS campos se compone?" en cuantificar creyendo que devolvería el número,
    pero CUANTIFICAR en este motor significa PRODUCCIÓN, no conteo: respondía con
    4.368.100 bbl del campo homónimo en vez de "2 campos", y de paso degradaba el nivel
    (preguntas por el ACTIVO Chichimene, contestaba sobre el CAMPO Chichimene).

    El conteo estructural lo da jerarquizar, que ya resolvía bien las otras dos formas
    —"¿cuántos campos TIENE el activo?" y "¿de QUÉ campos se compone?"—; solo esta
    tercera se desviaba por el 'CUANT[OA]S?' genérico de cuantificar.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿De cuántos campos se compone el activo Chichimene?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿Cuántos campos tiene el activo Chichimene?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿De qué campos se compone el activo Chichimene?", log=False)["grupo"] == "jerarquizar"
    # Otros niveles de la jerarquía, misma forma.
    assert clasificar("¿De cuántos pozos se compone el campo Castilla?", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿De cuántas gerencias se compone la VP GCH?", log=False)["grupo"] == "jerarquizar"


def test_componer_exige_verbo_estructural():
    """La guarda que impide el secuestro: el patrón vive en precedencia_maxima, así que
    sin el verbo estructural se tragaría preguntas de otros grupos y las sobrescribiría
    TODAS (regresión ya vivida el 2026-08-03, ver el comentario del YAML).
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿Cuántos campos pesan en el gap?", log=False)["grupo"] == "analizar"
    assert clasificar("¿Cuántos pozos produjeron en mayo?", log=False)["grupo"] == "cuantificar"
    assert clasificar("¿Cuántos campos incumplieron el presupuesto?", log=False)["grupo"] == "cuantificar"


# ---------------- Vocabulario de arranque de CUANTIFICAR (2026-08-24) ----------------

def test_cuantificar_arranques_mas_alla_de_cuanto():
    """[2026-08-24] Medido contra el motor: cuantificar dependía de UN SOLO arranque
    interrogativo ('CUANT[OA]S?'). Estas 8 formas —las más naturales del negocio— caían
    TODAS a desconocido, es decir el chat respondía "no logré entender tu pregunta".

    Dos de ellas (imperativa y telegráfica) daban nivel_dominio='fuerte': el motor SABÍA
    que la pregunta era suya y la descartaba igual.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    for q in ("¿Cuál fue el volumen de Chichimene el 15?",   # magnitud · VOLUMEN
              "¿Qué volumen tuvo Akacias?",                  # magnitud · VOLUMEN
              "¿Cómo cerró Castilla ayer?",                  # cierre
              "Dame el crudo de Rubiales ayer",              # imperativa (sin '?')
              "Producción Castilla ayer",                    # telegráfica (forma nominal)
              "Castilla ayer",                               # telegráfica (2 ranuras vacías)
              "¿Castilla produjo ayer?",                     # falso N1
              "¿Mejor día de Castilla este mes?"):           # selector temporal
        assert clasificar(q, log=False)["grupo"] == "cuantificar", q


def test_arranques_nuevos_no_secuestran_otros_grupos():
    """Las guardas de los patrones nuevos. `analizar` conserva precedencia en colisión, y
    el imperativo EXIGE un sustantivo de producción detrás — un (DAME|MUESTRAME) suelto se
    tragaría "muéstrame la estructura…", que es jerarquizar y perdería la colisión.
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿Por qué bajó la producción de Castilla?", log=False)["grupo"] == "analizar"
    assert clasificar("¿Qué pasó con la producción ayer?", log=False)["grupo"] == "analizar"
    assert clasificar("¿Se ve recuperación en la producción?", log=False)["grupo"] == "analizar"
    assert clasificar("Muéstrame la estructura de la gerencia PDH", log=False)["grupo"] == "jerarquizar"
    assert clasificar("¿Cuántos campos tiene el activo Chichimene?", log=False)["grupo"] == "jerarquizar"


def test_arranques_nuevos_siguen_pasando_por_el_filtro_de_dominio():
    """Ninguno de los patrones nuevos se ancla: sin entidad del catálogo ni vocabulario de
    producción deben seguir cayendo FUERA. Es la regla que tumbó a 'META' y 'COMO VAMOS'
    de patrones_anclados el 2026-08-02 (disparaban sobre temas ajenos).
    """
    from app.features.consulta_v2.maquina_q import clasificar
    assert clasificar("¿Qué volumen tiene el tanque de mi carro?", log=False)["grupo"] == "desconocido"
    assert clasificar("Ayer llovió mucho en Bogotá", log=False)["grupo"] == "desconocido"
    assert clasificar("Dame la receta del ajiaco", log=False)["grupo"] == "desconocido"


# ---------------- Demostrativo pegado al nombre (2026-08-25) ----------------
# Requieren catálogo (BD): detectar_entidad lee las tablas. Sin Postgres, _nombres() da
# set() vacío y devuelve None — se salta limpio, mismo criterio que el resto de la suite.

def _salta_sin_catalogo():
    from app.features.consulta_v2.maquina_q import _nombres
    if not _nombres():
        pytest.skip("sin catálogo (BD no disponible)")


def test_demostrativo_no_se_pega_al_nombre_de_la_entidad():
    """[2026-08-25] Visto en la app: "¿Mejor día de Castilla ESTE MES?" resolvía «CASTILLA
    ESTE» —un campo REAL— en vez de CASTILLA, y contestaba sobre el campo equivocado.
    detectar_entidad prueba n-gramas de MAYOR a menor, así que el bigrama le ganaba al
    unigrama y el demostrativo de "este mes" quedaba pegado al nombre.
    """
    _salta_sin_catalogo()
    from app.features.consulta_v2.maquina_q import detectar_entidad
    assert detectar_entidad("¿Mejor día de Castilla este mes?") == "CASTILLA"
    assert detectar_entidad("¿Cuánto produjo Castilla este año?") == "CASTILLA"
    assert detectar_entidad("¿Cómo cerró Castilla este trimestre?") == "CASTILLA"
    # Los otros 4 campos del catálogo que terminan en ESTE sobre una base que también existe.
    assert detectar_entidad("¿Cuánto produjo Apiay este mes?") == "APIAY"
    assert detectar_entidad("¿Cuánto produjo Redondo este año?") == "REDONDO"
    assert detectar_entidad("¿Cuánto produjo Tisquirama este mes?") == "TISQUIRAMA"
    assert detectar_entidad("¿Cuánto produjo Caño Sur este mes?") == "CANO SUR"


def test_la_entidad_que_de_verdad_termina_en_este_no_se_pierde():
    """La guarda NO puede costar el campo real: solo descarta el n-grama cuando detrás del
    demostrativo viene un sustantivo de tiempo. El caso fino es "Castilla Este este mes",
    donde el bigrama va seguido de ESTE (no temporal) y debe pasar."""
    _salta_sin_catalogo()
    from app.features.consulta_v2.maquina_q import detectar_entidad
    assert detectar_entidad("¿Cuánto produjo Castilla Este?") == "CASTILLA ESTE"
    assert detectar_entidad("¿Cuánto produjo Castilla Este este mes?") == "CASTILLA ESTE"
    assert detectar_entidad("¿Cuánto produjo Castilla Este el mes pasado?") == "CASTILLA ESTE"
    assert detectar_entidad("¿Cuánto produjo Caño Sur Este este mes?") == "CANO SUR ESTE"
    # NORTE y SUR quedan FUERA de la guarda a propósito: nunca son demostrativos en español.
    assert detectar_entidad("¿Cuánto produjo Castilla Norte este mes?") == "CASTILLA NORTE"
    assert detectar_entidad("¿Cuánto produjo Nare Sur este mes?") == "NARE SUR"
