"""BUG1-GERENCIAS (2026-09-09) — las gerencias REALES (fuente única de verdad) son consultables.

PUROS: monkeypatch, sin Postgres ni robustez_v02. La verificación con cifras es humana, en
Pruebas (§6.2 del plan), y V6-V8 en local.

🔑 Higiene obligatoria: todo test que llegue a `resolver_unico` monkeypatchea
   `_cargar_vp_robustez` — si no, toca BD y CACHEA `set()` en `_VP_ROBUSTEZ`, contaminando los
   tests siguientes (mismo motivo por el que test_puente_gerencia_vp.py:38,43 lo resetea).
"""
import pytest

import app.core.db as _db
import app.features.consulta_v2.cuantificar.resolver as R
import app.features.consulta_v2.respuesta_cuantificar as RC


@pytest.fixture(autouse=True)
def _sin_bd(monkeypatch):
    """Aísla de Postgres/ops y limpia los caches de proceso antes y después de CADA test."""
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: set())
    R._VP_ROBUSTEZ = None
    R._GER_CAMPOS = None
    R._GER_CANON = None
    yield
    R._VP_ROBUSTEZ = None
    R._GER_CAMPOS = None
    R._GER_CANON = None


def _idx(monkeypatch, mapa):
    """Fija el índice del resolver sin BD. Las claves DEBEN ir normalizadas (norm())."""
    monkeypatch.setattr(R, "_INDEX", mapa)


def _fuente_sets(monkeypatch, gerencias=None, campos=None, activos=None):
    """Fija los conjuntos físicos sin BD. Vacío = la entidad no está en dim_fuente."""
    monkeypatch.setattr(R, "_FUENTE_SETS", {
        "nombre": {}, "campo": campos or {}, "gerencia": gerencias or {},
        "operador": {}, R._ACTIVO_KEY: activos or {},
    })


# --- La gerencia real resuelve, con el nivel "gerencia" de siempre --------------------------
def test_gerencia_real_resuelve(monkeypatch):
    _idx(monkeypatch, {"PPC": [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]})
    r = R.resolver_unico("PPC")
    assert r is not None
    assert r["nivel"] == "gerencia"          # el nivel de SIEMPRE: el frontend ya sabe rotularlo
    assert r["valor"] == "PPC"


def test_gerencia_real_no_marca_puente(monkeypatch):
    """Ninguna gerencia vigente está en _VP_ROBUSTEZ (medido) → sin puente."""
    _idx(monkeypatch, {"PPC": [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]})
    assert "puente" not in R.resolver_unico("PPC")


def test_gerencia_de_dim_fuente_sigue_marcando_puente(monkeypatch):
    """No-regresión: GOR es VP en robustez y DEBE seguir llevando la marca."""
    monkeypatch.setattr(R, "_cargar_vp_robustez", lambda: {"GOR"})
    _idx(monkeypatch, {"GOR": [{"nivel": "gerencia", "rama": "A", "valor": "GOR"}]})
    assert R.resolver_unico("GOR").get("puente") is True


def test_clave_con_enie_se_normaliza(monkeypatch):
    """norm('PPÑ') == 'PPN' (NFKD pliega la ñ): la clave va plegada, el valor es el canónico."""
    assert R.norm("PPÑ") == "PPN"
    _idx(monkeypatch, {"PPN": [{"nivel": "gerencia", "rama": "A", "valor": "PPÑ"}]})
    assert R.resolver_unico("PPÑ")["valor"] == "PPÑ"


# --- clave_fisica: la gerencia sin fuentes propias NO colapsa con un homónimo (H7) ----------
def test_clave_fisica_gerencia_sin_fuentes_va_aparte(monkeypatch):
    """Sin esto, campo y gerencia colapsaban en ('F', frozenset()) → 'auto'."""
    _fuente_sets(monkeypatch)
    k_ger = R.clave_fisica({"nivel": "gerencia", "rama": "A", "valor": "XCOL"})
    k_cmp = R.clave_fisica({"nivel": "campo", "rama": "A", "valor": "XCOL"})
    assert k_ger != k_cmp
    assert k_ger[0] == "GER_ROB"


def test_clave_fisica_gerencia_de_dim_fuente_no_cambia(monkeypatch):
    """No-regresión: GOR sí tiene fuentes → conserva su clave ('F', {...}) de siempre."""
    _fuente_sets(monkeypatch, gerencias={"GOR": frozenset({1, 2})})
    assert R.clave_fisica({"nivel": "gerencia", "rama": "A", "valor": "GOR"}) == ("F", frozenset({1, 2}))


# --- Política de desempate (nombres SINTÉTICOS: hoy no hay colisión real, H6) ---------------
# >=2 identidades: con una sola, resolver_unico retorna en :260 y no colapsa nada.
def test_colision_campo_gerencia_sin_senal_gana_campo(monkeypatch):
    """D-D5 intacta: sin señal explícita gana Campo (decisión del usuario, 2026-07-15)."""
    _idx(monkeypatch, {"XCOL": [
        {"nivel": "campo", "rama": "A", "valor": "XCOL"},
        {"nivel": "gerencia", "rama": "A", "valor": "XCOL"},
    ]})
    _fuente_sets(monkeypatch)            # ninguno tiene fuentes → 2 grupos → "ask"
    r = R.resolver_unico("XCOL")
    assert "ambiguo" not in r            # D-D5 resuelve: hay exactamente 1 campo
    assert r["nivel"] == "campo"


def test_colision_campo_gerencia_con_senal_gana_gerencia(monkeypatch):
    """Nivel explícito gana sobre D-D5: el usuario ya desambiguó al escribirlo."""
    _idx(monkeypatch, {"XCOL": [
        {"nivel": "campo", "rama": "A", "valor": "XCOL"},
        {"nivel": "gerencia", "rama": "A", "valor": "XCOL"},
    ]})
    _fuente_sets(monkeypatch)
    r = R.resolver_unico("XCOL", contexto="¿cuánto produjo la gerencia XCOL?")
    assert "ambiguo" not in r
    assert r["nivel"] == "gerencia"


def test_codigo_en_ambos_catalogos_es_una_sola_identidad(monkeypatch):
    """CPV/GAN/GNS/GXO están en dim_fuente Y en la fuente de verdad: build_index deduplica y el
    resolver responde sin ambigüedad, como hoy."""
    _idx(monkeypatch, {"GAN": [{"nivel": "gerencia", "rama": "A", "valor": "GAN"}]})
    _fuente_sets(monkeypatch, gerencias={"GAN": frozenset({1, 2, 3})})
    r = R.resolver_unico("GAN")
    assert r["nivel"] == "gerencia" and r["valor"] == "GAN" and "ambiguo" not in r


# --- Detector de nivel explícito ------------------------------------------------------------
def test_nivel_explicito_gerencia():
    assert R._nivel_explicito("cuanto produjo la gerencia PPC") == "gerencia"
    assert R._nivel_explicito("produccion de las gerencias PPC") == "gerencia"


def test_nivel_explicito_sin_adyacencia_no_dispara():
    """Sin nombre detrás no etiqueta a nadie (misma guarda que ACTIVO/CAMPO)."""
    assert R._nivel_explicito("que es una gerencia") is None


def test_nivel_explicito_activo_y_campo_intactos():
    assert R._nivel_explicito("el activo CASTILLA") == "activo"
    assert R._nivel_explicito("el campo CASTILLA") == "campo"


# --- Composición gerencia -> campos (fuente de verdad) --------------------------------------
def test_campos_de_gerencia(monkeypatch):
    """PPC = 3 campos en la fuente de verdad (la copia solo traía 2: perdía CASTILLA ESTE)."""
    monkeypatch.setattr(R, "_GER_CAMPOS",
                        {"PPC": ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]})
    assert R.campos_de_gerencia("PPC") == ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]
    assert R.campos_de_gerencia("ppc") == ["CASTILLA", "CASTILLA ESTE", "CASTILLA NORTE"]


def test_campos_de_gerencia_inexistente(monkeypatch):
    monkeypatch.setattr(R, "_GER_CAMPOS", {"PPC": ["CASTILLA"]})
    assert R.campos_de_gerencia("NO_EXISTE") == []
    assert R.campos_de_gerencia("") == []
    assert R.campos_de_gerencia(None) == []


def test_gerencias_vigentes_devuelve_el_nombre_canonico(monkeypatch):
    """norm() pliega la ñ (PPÑ -> PPN): el índice debe guardar «PPÑ», no «PPN»."""
    monkeypatch.setattr(R, "_GER_CAMPOS", {"PPN": ["MITO"], "PPC": ["CASTILLA"]})
    monkeypatch.setattr(R, "_GER_CANON", {"PPN": "PPÑ", "PPC": "PPC"})
    assert R.gerencias_vigentes() == ["PPC", "PPÑ"]


def test_sin_ops_no_lanza_ni_cachea(monkeypatch):
    """Si robustez_v02 no está (p.ej. el 139): vacío, sin excepción y sin cachear el fallo."""
    def _boom():
        raise RuntimeError("OPS_DATABASE_URL no configurada")
    monkeypatch.setattr(_db, "get_ops_engine", _boom)   # el import es diferido: parchear el módulo
    assert R.campos_de_gerencia("PPC") == []
    assert R.gerencias_vigentes() == []
    assert R._GER_CAMPOS is None          # no se cacheó el error


def test_build_index_dedup_y_tolerante(monkeypatch):
    """Un mismo código en dim_fuente y en la fuente de verdad → UNA identidad. Una consulta que
    falle no tumba el índice."""
    class _Res:
        def __init__(self, rows): self._r = rows
        def __iter__(self): return iter(self._r)
    class _Conn:
        def execution_options(self, **k): return self
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, stmt):
            s = str(stmt)
            if "dim_fuente" in s and "gerencia" in s:
                return _Res([("GAN",), ("GOR",)])
            if "dim_empresa" in s:
                raise RuntimeError("tabla ausente")
            return _Res([])
    class _Eng:
        def connect(self): return _Conn()
    monkeypatch.setattr(R, "get_engine", lambda: _Eng())
    monkeypatch.setattr(R, "gerencias_vigentes", lambda: ["GAN", "PPC"])
    idx = R.build_index()
    assert idx["GAN"] == [{"nivel": "gerencia", "rama": "A", "valor": "GAN"}]   # dedup
    assert idx["PPC"] == [{"nivel": "gerencia", "rama": "A", "valor": "PPC"}]
    assert idx["GOR"][0]["valor"] == "GOR"                                       # la tabla ausente no tumbó nada


# --- H9: el bug latente del panel P50 -------------------------------------------------------
def test_p50_gerencia_puente_no_revienta(monkeypatch):
    """Antes lanzaba: AttributeError: 'bool' object has no attribute 'get'."""
    monkeypatch.setattr(RC._p50, "serie_por_vp", lambda *a, **k: None)
    res = {"producto": "crudo", "mes": {"anio": 2026, "mes": 8}}
    assert RC._p50_del_mes({"nivel": "gerencia", "valor": "GOR", "puente": True}, res) is None


def test_p50_gerencia_real_sin_puente_devuelve_none(monkeypatch):
    """Una gerencia REAL no tiene P50 propio: se omite el bloque, sin error."""
    monkeypatch.setattr(RC._p50, "serie_por_vp", lambda *a, **k: None)
    res = {"producto": "crudo", "mes": {"anio": 2026, "mes": 8}}
    assert RC._p50_del_mes({"nivel": "gerencia", "valor": "PPC"}, res) is None
