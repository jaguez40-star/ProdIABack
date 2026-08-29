from pydantic import BaseModel

class ReporteResumen(BaseModel):
    reporte_id: int
    fecha_reporte: str | None
    tipo_archivo: str | None
    tiene_raw: bool | None
    nivel_detalle: str | None
