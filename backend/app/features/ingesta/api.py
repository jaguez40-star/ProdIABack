from pathlib import Path
import re, shutil, json, queue, threading
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from app.core.config import get_settings
from app.features.ingesta import services
from app.features.ingesta.schemas import (
    ResultadoIngesta, ArchivoDisponible, IngestaRequest, JobRequest, JobCreado, JobEstado)

router = APIRouter(prefix="/ingesta", tags=["ingesta"])

def _resolver_nombre(nombre: str) -> Path:
    """Resuelve un nombre de archivo a una ruta DENTRO de data/. Bloquea path traversal."""
    if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
        raise HTTPException(400, "nombre inválido")
    base = Path(get_settings().data_dir).resolve()
    candidatos = [p for p in base.rglob(nombre) if p.is_file()]
    if not candidatos:
        raise HTTPException(404, f"No existe en data/: {nombre}")
    p = candidatos[0].resolve()
    if base != p.parent and base not in p.parents:
        raise HTTPException(400, "fuera de data/")
    return p

@router.get("/disponibles", response_model=list[ArchivoDisponible])
def disponibles():
    return services.listar_disponibles()

@router.post("/archivo", response_model=ResultadoIngesta)
def ingestar_archivo(req: IngestaRequest):
    return services.ingerir_archivo(_resolver_nombre(req.nombre))

@router.post("/jobs", response_model=JobCreado)
def crear_job(req: JobRequest, bg: BackgroundTasks):
    # C3: validar con el set BARATO de nombres (no abrir los 37 zips en cada POST).
    en_data = services._nombres_en_data()
    nombres = req.nombres or sorted(en_data)
    invalidos = [n for n in nombres if n not in en_data]
    if invalidos:
        raise HTTPException(400, f"no están en data/: {invalidos}")
    paths = [_resolver_nombre(n) for n in nombres]
    job_id = services.crear_job(nombres)
    bg.add_task(services.procesar_job, job_id, paths)
    return {"job_id": job_id, "total": len(nombres)}

@router.get("/jobs", response_model=list[JobEstado])
def listar_jobs():
    return services.listar_jobs()

@router.get("/jobs/{job_id}", response_model=JobEstado)
def estado_job(job_id: int):
    j = services.obtener_job(job_id)
    if not j:
        raise HTTPException(404, "job no existe")
    return j

UPLOAD_SUBDIR = "uploads"
_FECHA_RE = re.compile(r"\d{8}")


@router.get("/check_existing")
def check_existing(fecha: str):
    """Verifica si ya existe un reporte ingestado para una fecha YYYYMMDD."""
    from datetime import date as dt_date
    from app.core.db import get_engine
    import sqlalchemy as sa
    m = _FECHA_RE.search(fecha)
    if not m:
        raise HTTPException(400, "fecha debe contener YYYYMMDD")
    d = m.group(0)
    fecha_dt = dt_date(int(d[:4]), int(d[4:6]), int(d[6:8]))
    with get_engine().connect() as conn:
        prev = conn.execute(sa.text(
            "SELECT reporte_id, archivo_nombre, tipo_archivo, ingested_at "
            "FROM core.config_reporte WHERE fecha_reporte=:f"),
            {"f": fecha_dt}).mappings().first()
    if not prev:
        return {"exists": False}
    return {"exists": True, "reporte_id": prev["reporte_id"],
            "archivo": prev["archivo_nombre"], "tipo": prev["tipo_archivo"],
            "ingested_at": str(prev["ingested_at"])}

@router.post("/upload", response_model=ResultadoIngesta)
def upload_archivo(file: UploadFile = File(...)):
    """Recibe un .xlsm/.xlsx subido, lo guarda en data/uploads/ y lo ingiere de inmediato.
    Ingesta SÍNCRONA. El nombre DEBE contener la fecha YYYYMMDD (la usa core.config_reporte,
    que es NOT NULL)."""
    nombre = Path(file.filename or "").name
    if not nombre.lower().endswith((".xlsm", ".xlsx")):
        raise HTTPException(400, "solo se aceptan archivos .xlsm o .xlsx")
    if not _FECHA_RE.search(nombre):
        raise HTTPException(422, "el nombre del archivo debe contener la fecha en formato YYYYMMDD "
                                 "(p. ej. '20260531_Reporte...'). Es obligatoria para el linaje del reporte.")
    destino_dir = Path(get_settings().data_dir) / UPLOAD_SUBDIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nombre
    try:
        with destino.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()
    try:
        return services.ingerir_archivo(destino)
    except Exception as e:
        raise HTTPException(500, f"fallo de ingesta para {nombre}: {e}")

@router.post("/upload_stream")
def upload_stream(file: UploadFile = File(...)):
    """Como /upload pero emite el progreso por hoja vía SSE (text/event-stream)."""
    nombre = Path(file.filename or "").name
    if not nombre.lower().endswith((".xlsm", ".xlsx")):
        raise HTTPException(400, "solo se aceptan archivos .xlsm o .xlsx")
    if not _FECHA_RE.search(nombre):
        raise HTTPException(422, "el nombre del archivo debe contener la fecha en formato YYYYMMDD")
    destino_dir = Path(get_settings().data_dir) / UPLOAD_SUBDIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nombre
    try:
        with destino.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        file.file.close()

    q: "queue.Queue" = queue.Queue()
    _SENT = object()
    box: dict = {}

    def _cb(ev):
        q.put(ev)

    def _worker():
        try:
            res = services.ingerir_archivo(destino, progress_cb=_cb)
            box["resultado"] = res.model_dump()
        except Exception as e:
            box["error"] = str(e)
        finally:
            q.put(_SENT)

    def _sse():
        threading.Thread(target=_worker, daemon=True).start()
        while True:
            ev = q.get()
            if ev is _SENT:
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        fin = {"tipo": "fin"}
        fin.update({"resultado": box["resultado"]} if "resultado" in box
                   else {"error": box.get("error", "desconocido")})
        yield f"data: {json.dumps(fin, ensure_ascii=False)}\n\n"

    return StreamingResponse(_sse(), media_type="text/event-stream; charset=utf-8")
