"""
api/routes_ingestion.py — Endpoints para controlar la ingesta ETL manualmente.
"""
import logging
from datetime import datetime
from fastapi import APIRouter

from ingestion.tasks import (
    ingest_space_weather, ingest_disasters, ingest_asteroids,
    ingest_apod, ingest_ndvi, ingest_iss_passes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["Ingesta ETL"])


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


@router.post("/all")
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


@router.post("/space-weather")
async def trigger_space_weather_ingestion():
    """Dispara ingesta DONKI manualmente."""
    return _fire_task(ingest_space_weather, "ingest_space_weather")


@router.post("/disasters")
async def trigger_disasters_ingestion():
    """Dispara ingesta EONET manualmente."""
    return _fire_task(ingest_disasters, "ingest_disasters")


@router.post("/asteroids")
async def trigger_asteroids_ingestion():
    """Dispara ingesta NeoWs manualmente."""
    return _fire_task(ingest_asteroids, "ingest_asteroids")


@router.post("/apod")
async def trigger_apod_ingestion():
    """Dispara ingesta APOD manualmente."""
    return _fire_task(ingest_apod, "ingest_apod")


@router.post("/ndvi")
async def trigger_ndvi_ingestion():
    """Dispara ingesta NDVI manualmente."""
    return _fire_task(ingest_ndvi, "ingest_ndvi")


@router.post("/iss")
async def trigger_iss_ingestion():
    """Dispara ingesta ISS passes manualmente."""
    return _fire_task(ingest_iss_passes, "ingest_iss_passes")
