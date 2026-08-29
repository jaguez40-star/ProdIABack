"""Tests PUROS (sin BD, sin LLM) del detector de preguntas sobre EL ASISTENTE.

Cuarto hermano de test_no_soportado.py y test_incompleta.py. El caso de origen es real
(2026-08-25): «¿cuál es tu finalidad?» y «hola» recibían el rechazo de FUERA DE DOMINIO
de respuesta_out.py — el motor respondía que preguntarle qué sabe hacer es un tema ajeno.
"""
import re

from app.features.consulta_v2 import capacidades


# --- detectar(): dispara ------------------------------------------------------------------
def test_dispara_pregunta_por_finalidad():
    assert capacidades.detectar("¿cuál es tu finalidad?", False) == "capacidades"
    assert capacidades.detectar("para qué sirves", False) == "capacidades"
    assert capacidades.detectar("cuáles son tus capacidades", False) == "capacidades"


def test_dispara_pregunta_por_ayuda():
    assert capacidades.detectar("¿en qué me puedes ayudar?", False) == "capacidades"
    assert capacidades.detectar("¿cómo puedes ayudarme?", False) == "capacidades"
    assert capacidades.detectar("¿qué puedes hacer?", False) == "capacidades"
    assert capacidades.detectar("quién eres", False) == "capacidades"


def test_dispara_pedido_de_ayuda_pelado():
    """[2026-08-25] «ayuda»/«help» a secas es el reflejo del usuario perdido. Medido en la
    app: caían al LLM, que respondía el molde de "fuera de contexto" a la pregunta que este
    módulo existe para responder."""
    assert capacidades.detectar("ayuda", False) == "capacidades"
    assert capacidades.detectar("help", False) == "capacidades"
    assert capacidades.detectar("¡Ayuda!", False) == "capacidades"
    assert capacidades.detectar("ayudame", False) == "capacidades"
    assert capacidades.detectar("no se que preguntar", False) == "capacidades"


def test_dispara_familia_temas():
    """[2026-08-25] Visto en la app: «¿Sobre qué temas puedo preguntarte?» caía al LLM."""
    assert capacidades.detectar("Sobre que temas puedo preguntarte?", False) == "capacidades"
    assert capacidades.detectar("que temas manejas", False) == "capacidades"
    assert capacidades.detectar("de que temas puedes hablar", False) == "capacidades"
    assert capacidades.detectar("cuales son tus temas", False) == "capacidades"


def test_dispara_que_mas_puedes_hacer():
    """El MAS intermedio rompía la secuencia QUE+PUEDES+HACER del regex original."""
    assert capacidades.detectar("que mas puedes hacer", False) == "capacidades"
    assert capacidades.detectar("¿qué más puedes ofrecer?", False) == "capacidades"


def test_ayuda_con_complemento_NO_dispara():
    """El ancla ^…$ de la familia AYUDA: «ayuda» sola es la petición; «ayuda con el gap de
    Castilla» es una pregunta de DOMINIO y debe seguir su curso."""
    assert capacidades.detectar("ayuda con el gap de Castilla", False) is None
    assert capacidades.detectar("ayudame con la produccion de mayo", False) is None


def test_temas_exige_verbo_de_interlocucion():
    """«temas» es sustantivo común: sin la guarda del verbo capturaría tráfico de dominio."""
    assert capacidades.detectar("que temas de produccion hay en el reporte", False) is None


def test_dispara_saludo():
    assert capacidades.detectar("hola", False) == "saludo"
    assert capacidades.detectar("buenos días", False) == "saludo"
    assert capacidades.detectar("qué tal", False) == "saludo"
    assert capacidades.detectar("Hola,", False) == "saludo"


def test_saludo_tolera_signos_de_apertura():
    """norm() NO retira puntuación: «¡Hola!» queda «¡HOLA!» con el signo PEGADO. Sin el
    prefijo [¡¿\\s]* del ancla, estas dos NO matcheaban (medido 2026-08-25)."""
    assert capacidades.detectar("¡Hola!", False) == "saludo"
    assert capacidades.detectar("¿Hola?", False) == "saludo"


def test_norm_pliega_acentos():
    assert (capacidades.detectar("¿cuál es tu finalidad?", False)
            == capacidades.detectar("cual es tu finalidad", False))
    assert (capacidades.detectar("buenos días", False)
            == capacidades.detectar("buenos dias", False))


# --- detectar(): NO dispara — el riesgo real es el falso positivo -------------------------
def test_no_le_roba_nada_a_jerarquizar():
    """«QUE ES»/«QUIEN ES» son patrones jerarquizar VIVOS y _continuacion reescribe a
    f"que es {ent}" en TRES ramas. Capturarlos rompería todo el drill estructural."""
    assert capacidades.detectar("qué es CASTILLA", False) is None
    assert capacidades.detectar("que es POE", False) is None          # reescritura literal
    assert capacidades.detectar("quién es el operador de Rubiales", False) is None


def test_no_dispara_si_hay_entidad():
    assert capacidades.detectar("¿qué puedes decirme de Castilla?", True) is None


def test_saludo_con_pregunta_detras_no_dispara():
    """El ancla ^...$: «hola» es saludo, «hola, ¿cuánto produjo Castilla?» NO."""
    assert capacidades.detectar("hola, ¿cuánto produjo Castilla?", False) is None
    assert capacidades.detectar("buenos días, dame el acumulado", False) is None


def test_no_dispara_en_trafico_de_dominio():
    assert capacidades.detectar("cuánto produjo Rubiales en mayo", False) is None
    assert capacidades.detectar("por qué bajó la producción", False) is None
    assert capacidades.detectar("cuántos campos tiene el activo CHICHIMENE", False) is None


def test_bordes():
    assert capacidades.detectar("", False) is None
    assert capacidades.detectar(None, False) is None


# --- mensaje(): inventario honesto, sin sí/no (H1) ----------------------------------------
def test_mensaje_nombra_los_tres_frentes():
    m = capacidades.mensaje("capacidades")
    assert "estructura" in m.lower()
    assert "crudo" in m.lower()
    assert "análisis" in m.lower() or "desempeño" in m.lower()


def test_mensaje_no_despide_al_usuario():
    """EL BUG REPORTADO: se respondía "fuera de contexto" a quien pregunta qué sabe hacer."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod).lower()
        assert "fuera de" not in m
        assert "se sale" not in m
        assert "no logré entender" not in m


def test_mensaje_no_promete_capacidades_inexistentes():
    """no_soportado.py rechaza estas formas: ofrecerlas aquí sería contradecirse al turno
    siguiente."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod).lower()
        for prohibida in ("trimestre", "semana", "rango de días", "año completo"):
            assert prohibida not in m


def test_mensaje_regla_h1_sin_pregunta_si_no():
    """Un "sí" caería en el drill _AFIRM de _continuacion y daría un acumulado."""
    for cod in ("capacidades", "saludo"):
        assert "¿Quieres" not in capacidades.mensaje(cod)


def test_mensaje_determinista_sin_cifras():
    for cod in ("capacidades", "saludo"):
        assert not any(ch.isdigit() for ch in capacidades.mensaje(cod))


def test_mensaje_con_usuario_antepone_vocativo():
    m = capacidades.mensaje("saludo", usuario="Javier")
    assert "Javier" in m
    assert m.count("Hola") == 1          # no duplica el saludo


# --- formato de la burbuja (2026-08-25) ---------------------------------------------------
def test_mensaje_marca_los_tres_frentes_en_negrita():
    """El realce usa el marcador ⟦…⟧ del motor, que el frontend vuelve <strong>
    (multitab_shell.js::__cnMarcador). NO markdown ni HTML: el mensaje pasa por esc()
    antes de pintarse y saldría literal."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod)
        for frente in ("⟦Estructura⟧", "⟦Cifras⟧", "⟦Análisis⟧"):
            assert frente in m


def test_marcadores_no_cruzan_saltos_de_linea():
    """⚠️ El regex de __cnMarcador es [^⟦⟧\\n]*: un ⟦…⟧ partido por un \\n NO se convierte
    en <strong> y el símbolo crudo queda A LA VISTA en la burbuja. Ningún otro test lo
    detectaría — la cadena seguiría "conteniendo" el texto esperado."""
    rx = re.compile(r"⟦([^⟦⟧\n]*)⟧")
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod)
        # cada apertura tiene su cierre DENTRO de la misma línea
        assert m.count("⟦") == m.count("⟧") == len(rx.findall(m))
        # y tras el render del frontend no sobra ningún símbolo
        assert "⟦" not in rx.sub(r"<strong>\1</strong>", m)


def test_mensaje_no_usa_markdown_ni_html():
    """Saldrían literales: el frontend escapa el mensaje con esc()."""
    for cod in ("capacidades", "saludo"):
        m = capacidades.mensaje(cod)
        assert "**" not in m and "<strong>" not in m and "<br" not in m
