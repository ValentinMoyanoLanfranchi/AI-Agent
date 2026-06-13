"""
api/routes_ingestion.py — Endpoints para controlar la ingesta ETL manualmente.
"""
import logging
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ingestion.tasks import (
    ingest_space_weather, ingest_disasters, ingest_asteroids,
    ingest_apod, ingest_ndvi, ingest_iss_passes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["Ingesta ETL"])


# ─── Schemas de respuesta ─────────────────────────────────────

class IngestTaskResponse(BaseModel):
    """Resultado de disparar una tarea de ingesta individual."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {"status": "triggered", "task_id": "971b7290-3950-4917-87ec-6c896bb4c929"}
        },
    )
    status: str = Field(description="triggered | executed_sync | error")
    task_id: str | None = None
    note: str | None = None
    error: str | None = None


class IngestAllResponse(BaseModel):
    status: str = Field(examples=["triggered"])
    tasks: dict = Field(description="Resultado por fuente de datos")
    triggered_at: str = Field(examples=["2026-06-13T19:39:24.225858"])
    note: str | None = None


def _fire_task(task_fn, task_name: str) -> dict:
    """Dispara una tarea Celery con manejo de error si el broker no está disponible."""
    try:
        result = task_fn.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        logger.warning(f"[API] No se pudo encolar tarea {task_name} en Celery: {e}. Ejecutando en proceso...")
        try:
            task_fn()
            return {"status": "executed_sync", "note": "Celery no disponible — ejecutado sincrónicamente"}
        except Exception as e2:
            logger.error(f"[API] Error ejecutando {task_name}: {e2}", exc_info=True)
            return {"status": "error", "error": str(e2)}


@router.post(
    "/all",
    summary="Disparar todas las ingestas (seeding)",
    response_description="Estado de cada tarea disparada",
    response_model=IngestAllResponse,
)
async def trigger_all_ingestion():
    """Dispara todas las tareas de ingesta (útil para seeding inicial)."""
    tasks = [
        ("DONKI (Clima Espacial)", ingest_space_weather),
        ("EONET (Desastres)", ingest_disasters),
        ("NeoWs (Asteroides)", ingest_asteroids),
        ("APOD", ingest_apod),
        ("NDVI (Earthdata)", ingest_ndvi),
        ("ISS Passes", ingest_iss_passes),
    ]

    results = {}
    for name, task_fn in tasks:
        results[name] = _fire_task(task_fn, name)
        logger.info(f"[API] Tarea de ingesta disparada: {name}")

    return {
        "status": "triggered",
        "tasks": results,
        "triggered_at": datetime.utcnow().isoformat(),
        "note": "Las tareas corren en background. Verificar logs de Celery."
    }


@router.post("/space-weather", summary="Ingesta DONKI (clima espacial)", response_model=IngestTaskResponse)
async def trigger_space_weather_ingestion():
    """Dispara ingesta DONKI manualmente."""
    return _fire_task(ingest_space_weather, "ingest_space_weather")


@router.post("/disasters", summary="Ingesta EONET (desastres)", response_model=IngestTaskResponse)
async def trigger_disasters_ingestion():
    """Dispara ingesta EONET manualmente."""
    return _fire_task(ingest_disasters, "ingest_disasters")


@router.post("/asteroids", summary="Ingesta NeoWs (asteroides)", response_model=IngestTaskResponse)
async def trigger_asteroids_ingestion():
    """Dispara ingesta NeoWs manualmente."""
    return _fire_task(ingest_asteroids, "ingest_asteroids")


@router.post("/apod", summary="Ingesta APOD (foto astronómica)", response_model=IngestTaskResponse)
async def trigger_apod_ingestion():
    """Dispara ingesta APOD manualmente."""
    return _fire_task(ingest_apod, "ingest_apod")


@router.post("/ndvi", summary="Ingesta NDVI (Earthdata)", response_model=IngestTaskResponse)
async def trigger_ndvi_ingestion():
    """Dispara ingesta NDVI manualmente."""
    return _fire_task(ingest_ndvi, "ingest_ndvi")


@router.post("/iss", summary="Ingesta pasos ISS", response_model=IngestTaskResponse)
async def trigger_iss_ingestion():
    """Dispara ingesta ISS passes manualmente."""
    return _fire_task(ingest_iss_passes, "ingest_iss_passes")
