from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.features.ingesta.api import router as ingesta_router
from app.features.reportes.api import router as reportes_router
from app.features.kpis_prod.api import router as kpis_prod_router
from app.features.tablas.api import router as tablas_router
from app.features.analisis.api import router as analisis_router
from app.features.consulta.api import router as consulta_router
from app.features.consulta_v2.api import router as consulta_v2_router
from app.features.consulta_v2.warmup import warmup_llm, warmup_diferidas
from app.features.ebitda.api import router as ebitda_router

configure_logging()
app = FastAPI(title=get_settings().app_name)

# CORS solo para el dev server de Vite (mismo equipo). En prod el front se sirve aquí (mismo origen).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(ingesta_router)
app.include_router(reportes_router)
app.include_router(kpis_prod_router)
app.include_router(tablas_router)
app.include_router(analisis_router)
app.include_router(consulta_router)
app.include_router(consulta_v2_router)   # Motor Q v2 (clasificador) — antes del mount (H6)
app.include_router(ebitda_router)

@app.on_event("startup")
def _warmup():
    # Carga gemma@139 en 2º plano al arrancar → la 1ª petición real la encuentra caliente.
    warmup_llm()
    # [2026-08-26] Lo mismo para las cachés de diferidas: `analizar/causal` hace 2 scans completos
    # de AVM_DATADIF y sin este warm-up los paga la 1ª pregunta del usuario, que revienta el
    # timeout de 90 s del proxy Flask. Hilo aparte del LLM: son fuentes independientes y el ping de
    # gemma puede tardar ~342 s en frío — encadenarlos retrasaría el calentado de la BD hasta ahí.
    warmup_diferidas()


@app.get("/health")
def health():
    return {"status": "ok"}

# Servir el build del front (si existe) en el mismo origen. DEBE ir DESPUÉS de los routers para no
# tapar las rutas de la API. parents[2] = raíz del repo (backend/app/main.py -> backend -> raíz).
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
