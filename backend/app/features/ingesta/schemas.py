from datetime import datetime
from typing import Any
from pydantic import BaseModel

class ResultadoIngesta(BaseModel):
    archivo: str
    reporte_id: int
    tipo_archivo: str          # NEW | STD
    tiene_raw: bool
    filas_por_tabla: dict[str, int]

class ArchivoDisponible(BaseModel):
    nombre: str
    tipo: str                  # NEW | STD
    fecha: str | None          # YYYY-MM-DD derivada del nombre
    ya_ingerido: bool

class IngestaRequest(BaseModel):
    nombre: str                # nombre de archivo dentro de data/ (sin ruta)

class JobRequest(BaseModel):
    nombres: list[str] | None = None   # None / [] => todos los disponibles

class JobCreado(BaseModel):
    job_id: int
    total: int

class JobEstado(BaseModel):
    job_id: int
    estado: str                # PENDIENTE | EN_PROCESO | COMPLETADO | ERROR
    total: int
    procesados: int
    errores: int
    archivos: list[str] | None = None
    resultado: list[dict[str, Any]] | None = None
    mensaje: str | None = None
    creado_at: datetime
    actualizado_at: datetime
