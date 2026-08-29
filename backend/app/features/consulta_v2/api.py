"""API del Motor Q v2 — Fase 1 (clasificador de grupo + libreta con veredicto)."""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.features.consulta_v2 import maquina_q, log as _log, senales
from app.features.consulta_v2 import pozos_geo as _pozos_geo
from app.features.consulta_v2 import geo_colombia
from app.features.consulta_v2 import respuesta_jerarquizar

router = APIRouter(prefix="/consulta2")


class Preguntar(BaseModel):
    texto: str
    conversation_id: str
    usuario: str | None = None


class Veredicto(BaseModel):
    log_id: int
    veredicto: str                       # confirmado_usuario|corregido_usuario|confirmado_revision|corregido_revision
    grupo_correcto: str | None = None
    fuente: str = "usuario"              # usuario|revision
    nota: str | None = None


class Senal(BaseModel):
    texto: str
    conversation_id: str | None = None
    usuario: str | None = None
    tipo: str = "cambio_v1"


class VeredictoItem(BaseModel):
    log_id: int
    veredicto: str
    grupo_correcto: str | None = None


class VeredictoLote(BaseModel):
    items: list[VeredictoItem]
    fuente: str = "revision"             # revisión por lotes = Control 3
    nota: str | None = None


@router.post("/preguntar")
def preguntar(body: Preguntar):
    return maquina_q.clasificar(body.texto, usuario=body.usuario,
                                conversation_id=body.conversation_id, log=True)


@router.post("/veredicto")
def veredicto(body: Veredicto):
    fuente = body.fuente if body.fuente in ("usuario", "revision") else "usuario"
    ok = _log.poner_veredicto(body.log_id, body.veredicto,
                              grupo_correcto=body.grupo_correcto,
                              fuente=fuente, nota=body.nota)
    return {"ok": ok}


@router.post("/veredicto_lote")
def veredicto_lote(body: VeredictoLote):
    """Aplica varios veredictos de una (Control 3 por lotes: p.ej. «confirmar todos los
    pendientes»). Reusa poner_veredicto por fila — misma validación que /veredicto.
    Devuelve cuántos se aplicaron (una fila inválida o inexistente no tumba el resto)."""
    fuente = body.fuente if body.fuente in ("usuario", "revision") else "revision"
    aplicados = 0
    for it in body.items:
        if _log.poner_veredicto(it.log_id, it.veredicto, grupo_correcto=it.grupo_correcto,
                                fuente=fuente, nota=body.nota):
            aplicados += 1
    return {"ok": True, "aplicados": aplicados, "total": len(body.items)}


@router.post("/senal")
def senal(body: Senal):
    """P2: señal fire-and-forget del frontend (el usuario repitió la pregunta en v1).
    Nunca falla hacia el cliente: la señal es débil y opcional por diseño."""
    try:
        marcada = senales.registrar_senal_v1(body.texto, usuario=body.usuario)
    except Exception:
        marcada = False
    return {"ok": True, "sospecha": marcada}


@router.get("/golden")
def correr_golden():
    """Gate del clasificador desde la UI (botón «Correr golden» en Test Clas).

    Reusa run_golden.ejecutar() — el MISMO cálculo que el CLI, para que no existan dos
    gates que puedan discrepar. Import local: el runner no es dependencia del arranque
    del router, y así un fallo suyo no tumba el resto de la API.
    H3 se conserva (clasificar(log=False)): correr el gate no ensucia la libreta.
    Síncrono y sin LLM en el camino feliz, pero recorre TODOS los casos del golden:
    si alguno escala a Capa 2 con Ollama frío, puede tardar. El frontend avisa.
    """
    try:
        from app.features.consulta_v2.golden.run_golden import ejecutar
        return ejecutar()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@router.get("/log")
def listar_log(limit: int = Query(100), filtro: str = Query("todas")):
    """Libreta para la tabla de «Test Clas». Escanea señales pendientes antes de listar
    (P4: sin scheduler; H7: escaneo acotado) — las sospechas llegan ya marcadas."""
    try:
        senales.escanear()
    except Exception:
        pass   # el escaneo jamás bloquea la lectura
    return _log.listar(limit=limit, filtro=filtro)


@router.get("/pozos_geo")
def pozos_geo(entidad: str, nivel: str):
    """Puntos de los pozos de una entidad + contornos + contexto país, para el panel del
    mapa de Jerarquizar (QV2-MAPA).

    Las coordenadas salen YA corregidas y deduplicadas de pozos_geo.geo(): el frontend NO
    aplica ninguna regla geográfica (ver el docstring de pozos_geo).

    `disponible: False` cuando robustez_v02 no está (p.ej. el servidor 139): el frontend
    oculta el mapa y deja el árbol intacto — nunca un panel roto.
    """
    fields = respuesta_jerarquizar.rob_fields_de(nivel, entidad)
    g = _pozos_geo.geo(fields) if fields else None
    if g is None:
        return {"disponible": False}
    return {
        "disponible": True,
        "entidad": entidad,
        "nivel": nivel,
        "pozos": g["pozos"],
        "total": g["total"],              # UWI únicos del nivel (coincide con el pie del árbol)
        "ubicables": g["ubicables"],      # los que tienen coordenada usable
        "contornos": g["contornos"],      # {campo: [[lon,lat], ...]} — solo 15 campos lo tienen
        "campos": _pozos_geo.centroides(),  # contexto país (62 campos)
        "colombia": geo_colombia.CONTORNO,
    }
