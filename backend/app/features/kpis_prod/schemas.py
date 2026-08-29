from pydantic import BaseModel

class ProduccionDia(BaseModel):
    tipo_producto: str
    vol_estimado: float | None
