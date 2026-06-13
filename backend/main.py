"""
main.py — FastAPI Application entrypoint.

Sistema de Agentes IA para Monitoreo Espacial y Agrícola
Hackathon Junio 2026
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import settings
from database.session import async_engine
from database.models import (
    NDVIRecord, DisasterEvent, SpaceWeatherEvent,
    APODRecord, ISSPass, AsteroidRecord, AgentReport, InterAgentAlert
)
from database.session import Base
from api.routes_agents import router as agents_router
from api.routes_ingestion import router as ingestion_router

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if not settings.app_debug else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── Startup / Shutdown ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler para startup y shutdown."""
    logger.info("🚀 Iniciando Sistema de Agentes IA — Hackathon Junio 2026")
    logger.info(f"   Entorno: {settings.app_env}")
    logger.info(f"   Modelo LLM default: {settings.default_llm_model}")
    logger.info(f"   Umbral Kp: {settings.kp_index_threshold}")

    # Crear tablas si no existen (en prod usar Alembic)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Base de datos inicializada")

    yield

    logger.info("👋 Cerrando Sistema de Agentes IA")
    await async_engine.dispose()


# ─── Metadata de tags (agrupa y describe endpoints en Swagger) ─
tags_metadata = [
    {
        "name": "Sistema",
        "description": "Health checks e información general del servicio.",
    },
    {
        "name": "Agentes Cognitivos",
        "description": (
            "Invocación de los 5 agentes IA (LangGraph). Cada endpoint ejecuta el "
            "agente sobre las réplicas locales de datos y devuelve el reporte generado "
            "por el LLM. Soportan notificaciones opcionales por email/Slack."
        ),
    },
    {
        "name": "Ingesta ETL",
        "description": (
            "Disparo manual de las tareas de ingesta (NASA DONKI/EONET/NeoWs/APOD/"
            "Earthdata/ISS). Corren en background vía Celery; útiles para el seeding inicial."
        ),
    },
]

# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="🛰️ Sistema de Agentes IA — Hackathon Junio 2026",
    description=(
        "Sistema multiagente de monitoreo espacial y agrícola basado en LangGraph.\n\n"
        "**5 Agentes Cognitivos:**\n"
        "1. 🌱 Monitoreo Agrícola Core (NDVI + NASA Earthdata)\n"
        "2. 🌪️ Alertas de Desastres Naturales (NASA EONET + PostGIS)\n"
        "3. ☀️ Análisis de Clima Espacial (NASA DONKI)\n"
        "4. 🔭 Divulgación Turística/Educativa (NASA APOD + ISS)\n"
        "5. ☄️ Seguimiento de Asteroides (NASA NeoWs)\n\n"
        "**Regla de Oro:** Los agentes solo consultan réplicas locales en PostgreSQL. "
        "Las APIs externas se consumen exclusivamente desde Celery (background)."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "Equipo Hackathon — Sistema de Agentes IA",
        "email": "team@yourdomain.com",
    },
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "none",
        "filter": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    },
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Error Handler ────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no capturado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": str(exc) if settings.app_debug else "Contactar soporte",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ─── Routers ──────────────────────────────────────────────────
app.include_router(agents_router)
app.include_router(ingestion_router)


# ─── Schemas de respuesta (documentación Swagger) ─────────────
class HealthResponse(BaseModel):
    status: str = Field(examples=["healthy"])
    service: str = Field(examples=["Sistema de Agentes IA"])
    version: str = Field(examples=["1.0.0"])
    environment: str = Field(examples=["development"])
    timestamp: str = Field(examples=["2026-06-13T19:35:23.881706"])
    agents: int = Field(examples=[5])


# ─── Health Check ─────────────────────────────────────────────
@app.get(
    "/health",
    tags=["Sistema"],
    summary="Health check",
    response_description="Estado de salud del servicio",
    response_model=HealthResponse,
)
async def health_check():
    """Health check del sistema. Úsalo para readiness/liveness probes."""
    return {
        "status": "healthy",
        "service": "Sistema de Agentes IA",
        "version": "1.0.0",
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
        "agents": 5,
    }


@app.get(
    "/",
    tags=["Sistema"],
    summary="Información del sistema",
    response_description="Metadatos y mapa de endpoints principales",
)
async def root():
    """Endpoint raíz con información del sistema y enlaces a la documentación."""
    return {
        "name": "🛰️ Sistema de Agentes IA — Hackathon Junio 2026",
        "description": "Sistema multiagente de monitoreo espacial y agrícola",
        "docs": "/docs",
        "health": "/health",
        "agents": {
            "agricultural": "POST /api/agents/agricultural",
            "disasters": "POST /api/agents/disasters",
            "space_weather": "POST /api/agents/space-weather",
            "educational": "POST /api/agents/educational",
            "neows": "POST /api/agents/neows",
            "run_all": "POST /api/agents/run-all",
        },
        "ingestion": {
            "trigger_all": "POST /api/ingest/all",
            "trigger_specific": "POST /api/ingest/{source}",
        },
    }
