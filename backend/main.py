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
    docs_url="/docs",
    redoc_url="/redoc",
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


# ─── Health Check ─────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Health check del sistema."""
    return {
        "status": "healthy",
        "service": "Sistema de Agentes IA",
        "version": "1.0.0",
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
        "agents": 5,
    }


@app.get("/", tags=["Sistema"])
async def root():
    """Endpoint raíz con información del sistema."""
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
