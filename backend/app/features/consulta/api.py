from fastapi import APIRouter
from pydantic import BaseModel
from app.features.consulta import maquina

router = APIRouter(prefix="/consulta")

class Preguntar(BaseModel):
    texto: str
    conversation_id: str
    usuario: str | None = None

class Responder(BaseModel):
    conversation_id: str
    opcion_id: str
    usuario: str | None = None

@router.post("/preguntar")
def preguntar(body: Preguntar):
    return maquina.preguntar(body.texto, body.conversation_id, body.usuario)

@router.post("/responder")
def responder(body: Responder):
    return maquina.responder(body.conversation_id, body.opcion_id, body.usuario)
