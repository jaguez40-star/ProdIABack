from pathlib import Path
import pytest
from fastapi import HTTPException
from app.features.ingesta.api import _resolver_nombre
from app.features.ingesta.detector import nombres_de_hojas, tiene_raw

def test_resolver_rechaza_traversal():
    for malo in ["", "../x.xlsm", "..\\x.xlsm", "sub/dir.xlsm", "sub\\dir.xlsm"]:
        with pytest.raises(HTTPException):
            _resolver_nombre(malo)

def test_resolver_archivo_inexistente():
    with pytest.raises(HTTPException):
        _resolver_nombre("no_existe_zzz_12345.xlsm")

_MUESTRAS = list(Path(r"c:\Users\user\Documents\Rep_Prod\Doc_Desing").glob("*.xlsm"))

@pytest.mark.skipif(not _MUESTRAS, reason="no hay .xlsm de muestra en Doc_Desing")
def test_nombres_de_hojas_lee_del_zip():
    hojas = nombres_de_hojas(_MUESTRAS[0])
    assert isinstance(hojas, set) and len(hojas) > 0
    # tiene_raw debe devolver bool sin lanzar
    assert isinstance(tiene_raw(hojas), bool)
