"""
ingestion/tasks.py — Tareas Celery de ingesta ETL programadas (CRON).

Horarios de ingesta:
  - DONKI CME/GST/FLR  → cada 6 horas
  - NeoWs              → cada 24 horas (a las 01:00 UTC)
  - EONET              → cada 2 horas
  - APOD               → cada 24 horas (a las 08:00 UTC)
  - NDVI               → cada 24 horas (a las 03:00 UTC)
  - ISS Passes         → cada 24 horas (a las 06:00 UTC)

Regla de Oro: Los agentes LLM solo leen de PostgreSQL. Esta es la ÚNICA
              fuente que escribe datos desde APIs externas.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.orm import Session
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from config import settings
from database.session import SyncSessionLocal
from database.models import (
    NDVIRecord, DisasterEvent, SpaceWeatherEvent,
    APODRecord, ISSPass, AsteroidRecord, InterAgentAlert
)
from ingestion.nasa_connectors import (
    fetch_donki_cme, fetch_donki_gst, fetch_donki_flr,
    fetch_neows_feed, extract_hazardous_asteroids, humanize_miss_distance,
    fetch_eonet_events, filter_south_america_events,
    fetch_apod, fetch_iss_passes, fetch_nasa_power_data,
)
from ingestion.copernicus import (
    fetch_earthdata_ndvi_mock, MONITORED_AGRICULTURAL_ZONES,
    detect_ndvi_anomaly,
)

logger = logging.getLogger(__name__)

# ─── Celery App ───────────────────────────────────────────────
celery_app = Celery(
    "hackaton_agents",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ─── Beat Schedule (CRON) ─────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Clima espacial — cada 6 horas
    "ingest-donki-every-6h": {
        "task": "ingestion.tasks.ingest_space_weather",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Desastres — cada 2 horas
    "ingest-eonet-every-2h": {
        "task": "ingestion.tasks.ingest_disasters",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Asteroides — diario a la 1 AM
    "ingest-neows-daily": {
        "task": "ingestion.tasks.ingest_asteroids",
        "schedule": crontab(minute=0, hour=1),
    },
    # APOD — diario a las 8 AM
    "ingest-apod-daily": {
        "task": "ingestion.tasks.ingest_apod",
        "schedule": crontab(minute=0, hour=8),
    },
    # NDVI — diario a las 3 AM
    "ingest-ndvi-daily": {
        "task": "ingestion.tasks.ingest_ndvi",
        "schedule": crontab(minute=0, hour=3),
    },
    # ISS — diario a las 6 AM
    "ingest-iss-daily": {
        "task": "ingestion.tasks.ingest_iss_passes",
        "schedule": crontab(minute=0, hour=6),
    },
}


def run_async(coro):
    """Ejecutar coroutine async desde contexto sync de Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─────────────────────────────────────────────────────────────
# TAREA 1: Ingesta de Clima Espacial (DONKI)
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_space_weather", bind=True, max_retries=3)
def ingest_space_weather(self):
    """Ingesta CME, GST y FLR de NASA DONKI. Detecta si Kp supera umbral crítico."""
    logger.info("[CELERY] Iniciando ingesta DONKI (CME + GST + FLR)")
    try:
        # Fetch async
        cme_data = run_async(fetch_donki_cme())
        gst_data = run_async(fetch_donki_gst())
        flr_data = run_async(fetch_donki_flr())

        with SyncSessionLocal() as db:
            alerts_generated = 0

            # Procesar GST (Geomagnetic Storms) — los que tienen índice Kp
            for gst in gst_data:
                gst_id = gst.get("gstID", "")
                if not gst_id:
                    continue

                # Verificar duplicado
                existing = db.query(SpaceWeatherEvent).filter_by(donki_id=gst_id).first()
                if existing:
                    continue

                # Extraer Kp máximo
                kp_max = 0.0
                kp_activity = gst.get("allKpIndex", [])
                if kp_activity:
                    kp_max = max(entry.get("kpIndex", 0) for entry in kp_activity)

                exceeds_threshold = kp_max >= settings.kp_index_threshold

                record = SpaceWeatherEvent(
                    donki_id=gst_id,
                    event_type="GST",
                    start_time=_parse_dt(gst.get("startTime")),
                    kp_index=kp_max,
                    kp_index_max=kp_max,
                    exceeds_kp_threshold=exceeds_threshold,
                    gps_impact_risk=_kp_to_risk(kp_max),
                    power_grid_risk=_kp_to_risk(kp_max),
                    aviation_risk=_kp_to_risk(kp_max),
                    link=gst.get("link", ""),
                    raw_data=gst,
                )
                db.add(record)

                # Si supera umbral → generar alerta inter-agente (Agente 3 → Agente 1)
                if exceeds_threshold and kp_max > 0:
                    alert = InterAgentAlert(
                        source_agent_id=3,  # Agente 3: Clima Espacial
                        target_agent_id=1,  # Agente 1: Monitoreo Agrícola
                        alert_type="GPS_MAGNETIC_STORM",
                        severity=_kp_to_risk(kp_max),
                        message=(
                            f"⚠️ TORMENTA GEOMAGNÉTICA DETECTADA — Índice Kp: {kp_max:.1f} "
                            f"(umbral: {settings.kp_index_threshold}). "
                            f"Posible pérdida de precisión en GPS de maquinaria agrícola autónoma. "
                            f"Se recomienda verificar operaciones de siembra/cosecha automatizadas."
                        ),
                        payload={
                            "kp_index": kp_max,
                            "gst_id": gst_id,
                            "threshold": settings.kp_index_threshold,
                        },
                    )
                    db.add(alert)
                    alerts_generated += 1
                    logger.warning(f"[ALERTA INTER-AGENTE] Kp={kp_max} → Agente 1 notificado")

            # Procesar CME
            for cme in cme_data:
                cme_id = cme.get("activityID", "")
                if not cme_id:
                    continue

                existing = db.query(SpaceWeatherEvent).filter_by(donki_id=cme_id).first()
                if existing:
                    continue

                speed = None
                for analysis in cme.get("cmeAnalyses", []):
                    speed = analysis.get("speed")
                    if speed:
                        break

                record = SpaceWeatherEvent(
                    donki_id=cme_id,
                    event_type="CME",
                    start_time=_parse_dt(cme.get("startTime")),
                    speed_km_s=speed,
                    link=cme.get("link", ""),
                    raw_data=cme,
                )
                db.add(record)

            # Procesar FLR (Solar Flares)
            for flr in flr_data:
                flr_id = flr.get("flrID", "")
                if not flr_id:
                    continue

                existing = db.query(SpaceWeatherEvent).filter_by(donki_id=flr_id).first()
                if existing:
                    continue

                record = SpaceWeatherEvent(
                    donki_id=flr_id,
                    event_type="FLR",
                    start_time=_parse_dt(flr.get("beginTime")),
                    peak_time=_parse_dt(flr.get("peakTime")),
                    end_time=_parse_dt(flr.get("endTime")),
                    flare_class=flr.get("classType", ""),
                    link=flr.get("link", ""),
                    raw_data=flr,
                )
                db.add(record)

            db.commit()
            logger.info(f"[CELERY] DONKI: {len(gst_data)} GST, {len(cme_data)} CME, {len(flr_data)} FLR ingested. {alerts_generated} inter-agent alerts.")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_space_weather: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────
# TAREA 2: Ingesta de Desastres (EONET)
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_disasters", bind=True, max_retries=3)
def ingest_disasters(self):
    """Ingesta eventos EONET filtrados para Sudamérica."""
    logger.info("[CELERY] Iniciando ingesta EONET")
    try:
        raw_data = run_async(fetch_eonet_events(days=30))
        events = filter_south_america_events(raw_data)

        with SyncSessionLocal() as db:
            new_events = 0
            for event in events:
                eonet_id = event.get("id", "")
                if not eonet_id:
                    continue

                existing = db.query(DisasterEvent).filter_by(eonet_id=eonet_id).first()
                if existing:
                    continue

                # Extraer geometría del primer punto
                lat, lon = None, None
                for geo in event.get("geometry", []):
                    coords = geo.get("coordinates")
                    if coords:
                        if isinstance(coords[0], list):
                            lon, lat = coords[0][0], coords[0][1]
                        else:
                            lon, lat = coords[0], coords[1]
                        break

                category = ""
                categories = event.get("categories", [])
                if categories:
                    category = categories[0].get("title", "Unknown")

                record = DisasterEvent(
                    eonet_id=eonet_id,
                    title=event.get("title", ""),
                    description=event.get("description", ""),
                    category=category,
                    status=event.get("status", "open"),
                    latitude=lat,
                    longitude=lon,
                    location=from_shape(Point(lon, lat), srid=4326) if lat and lon else None,
                    sources=event.get("sources", []),
                    event_start=_parse_dt(event.get("geometry", [{}])[0].get("date")) if event.get("geometry") else None,
                )
                db.add(record)
                new_events += 1

            db.commit()
            logger.info(f"[CELERY] EONET: {new_events} nuevos eventos ingested")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_disasters: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)


# ─────────────────────────────────────────────────────────────
# TAREA 3: Ingesta de Asteroides (NeoWs)
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_asteroids", bind=True, max_retries=3)
def ingest_asteroids(self):
    """Ingesta asteroides NeoWs — filtra potencialmente peligrosos."""
    logger.info("[CELERY] Iniciando ingesta NeoWs")
    try:
        feed = run_async(fetch_neows_feed())
        hazardous = extract_hazardous_asteroids(feed)

        # También ingestar todos los NEO del día (no solo peligrosos)
        all_neos = []
        for day_str, asteroids in feed.get("near_earth_objects", {}).items():
            for a in asteroids:
                a["_query_date"] = day_str
                all_neos.append(a)

        with SyncSessionLocal() as db:
            new_count = 0
            for asteroid in all_neos:
                neo_id = str(asteroid.get("id", ""))
                approach_date = asteroid.get("_query_date", "")

                # Dedup por neo_id + fecha de aproximación
                approach_dt = _parse_dt(approach_date)
                existing = db.query(AsteroidRecord).filter(
                    AsteroidRecord.neo_id == neo_id,
                    AsteroidRecord.approach_date_ingested == approach_dt,
                ).first()
                if existing:
                    continue

                # Extraer close approach más cercano
                close_approaches = asteroid.get("close_approach_data", [])
                ca = close_approaches[0] if close_approaches else {}

                miss_km = float(ca.get("miss_distance", {}).get("kilometers", 0) or 0)
                miss_lunar = float(ca.get("miss_distance", {}).get("lunar", 0) or 0)
                velocity = float(ca.get("relative_velocity", {}).get("kilometers_per_second", 0) or 0)

                diameter = asteroid.get("estimated_diameter", {}).get("kilometers", {})

                record = AsteroidRecord(
                    neo_id=neo_id,
                    name=asteroid.get("name", ""),
                    designation=asteroid.get("designation", ""),
                    is_potentially_hazardous=asteroid.get("is_potentially_hazardous_asteroid", False),
                    absolute_magnitude_h=asteroid.get("absolute_magnitude_h"),
                    estimated_diameter_min_km=diameter.get("estimated_diameter_min"),
                    estimated_diameter_max_km=diameter.get("estimated_diameter_max"),
                    close_approach_date=_parse_dt(ca.get("close_approach_date_full")),
                    miss_distance_km=miss_km,
                    miss_distance_lunar=miss_lunar,
                    relative_velocity_km_s=velocity,
                    miss_distance_human=humanize_miss_distance(miss_km, miss_lunar),
                    raw_data={
                        "neo_reference_id": asteroid.get("neo_reference_id"),
                        "nasa_jpl_url": asteroid.get("nasa_jpl_url"),
                        "orbital_data": asteroid.get("orbital_data", {}),
                    },
                    approach_date_ingested=_parse_dt(approach_date),
                )
                db.add(record)
                new_count += 1

            db.commit()
            logger.info(f"[CELERY] NeoWs: {new_count} asteroides ingested ({len(hazardous)} peligrosos)")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_asteroids: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


# ─────────────────────────────────────────────────────────────
# TAREA 4: Ingesta APOD
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_apod", bind=True, max_retries=3)
def ingest_apod(self):
    """Ingesta APOD del día actual."""
    logger.info("[CELERY] Iniciando ingesta APOD")
    try:
        data = run_async(fetch_apod())
        apod_date_str = data.get("date", "")

        with SyncSessionLocal() as db:
            existing = db.query(APODRecord).filter_by(
                apod_date=_parse_dt(apod_date_str)
            ).first()
            if existing:
                logger.info("[CELERY] APOD: ya existe para hoy")
                return

            record = APODRecord(
                apod_date=_parse_dt(apod_date_str),
                title=data.get("title", ""),
                explanation=data.get("explanation", ""),
                media_type=data.get("media_type", "image"),
                url=data.get("url", ""),
                hdurl=data.get("hdurl", ""),
                copyright=data.get("copyright", ""),
                service_version=data.get("service_version", ""),
            )
            db.add(record)
            db.commit()
            logger.info(f"[CELERY] APOD: '{data.get('title')}' ingested")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_apod: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────
# TAREA 5: Ingesta NDVI (NASA Earthdata)
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_ndvi", bind=True, max_retries=3)
def ingest_ndvi(self):
    """Ingesta datos NDVI para todas las zonas agrícolas monitoreadas."""
    logger.info(f"[CELERY] Iniciando ingesta NDVI para {len(MONITORED_AGRICULTURAL_ZONES)} zonas")
    try:
        with SyncSessionLocal() as db:
            for zone in MONITORED_AGRICULTURAL_ZONES:
                # Fetch (mock en dev, real en prod con AppEEARS)
                data = run_async(fetch_earthdata_ndvi_mock(zone))

                ndvi_val = data["ndvi_value"]
                ndvi_hist = data.get("ndvi_5yr_avg", 0.5)
                is_anomaly, severity, change_pct = detect_ndvi_anomaly(ndvi_val, ndvi_hist)

                lat = zone["latitude"]
                lon = zone["longitude"]

                record = NDVIRecord(
                    location=from_shape(Point(lon, lat), srid=4326),
                    location_name=zone["name"],
                    region_code=zone["region_code"],
                    ndvi_value=ndvi_val,
                    ndvi_5yr_avg=ndvi_hist,
                    satellite_source=data.get("satellite_source", "NASA_EARTHDATA"),
                    band_data={
                        "nir": data.get("nir_band"),
                        "red": data.get("red_band"),
                    },
                    is_anomaly=is_anomaly,
                    anomaly_severity=severity if is_anomaly else None,
                )
                db.add(record)
                logger.info(
                    f"[CELERY] NDVI {zone['region_code']}: {ndvi_val:.4f} "
                    f"({'⚠️ ANOMALÍA ' + severity if is_anomaly else 'OK'})"
                )

            db.commit()
            logger.info("[CELERY] NDVI: todas las zonas ingested")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_ndvi: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=180)


# ─────────────────────────────────────────────────────────────
# TAREA 6: Ingesta ISS Passes
# ─────────────────────────────────────────────────────────────

@celery_app.task(name="ingestion.tasks.ingest_iss_passes", bind=True, max_retries=3)
def ingest_iss_passes(self):
    """Ingesta pasos de ISS para las coordenadas de las zonas monitoreadas."""
    logger.info("[CELERY] Iniciando ingesta ISS passes")
    try:
        major_cities = [
            {"name": "Buenos Aires", "lat": -34.6037, "lon": -58.3816},
            {"name": "Santiago", "lat": -33.4489, "lon": -70.6693},
            {"name": "Montevideo", "lat": -34.9011, "lon": -56.1645},
            {"name": "São Paulo", "lat": -23.5505, "lon": -46.6333},
            {"name": "Lima", "lat": -12.0464, "lon": -77.0428},
        ]

        with SyncSessionLocal() as db:
            total = 0
            for city in major_cities:
                try:
                    data = run_async(fetch_iss_passes(city["lat"], city["lon"], n_passes=5))
                    passes = data.get("response", [])

                    for p in passes:
                        rise_ts = p.get("risetime", 0)
                        duration = p.get("duration", 0)
                        rise_dt = datetime.utcfromtimestamp(rise_ts)

                        record = ISSPass(
                            location=from_shape(Point(city["lon"], city["lat"]), srid=4326),
                            latitude=city["lat"],
                            longitude=city["lon"],
                            location_name=city["name"],
                            rise_time=rise_dt,
                            duration_seconds=duration,
                        )
                        db.add(record)
                        total += 1
                except Exception as e:
                    logger.warning(f"[CELERY] ISS passes para {city['name']}: {e}")
                    continue

            db.commit()
            logger.info(f"[CELERY] ISS: {total} pasos ingested")

    except Exception as exc:
        logger.error(f"[CELERY] Error en ingest_iss_passes: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─── Helpers ──────────────────────────────────────────────────

def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
    """Parsea strings de fecha de NASA (varios formatos)."""
    if not dt_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%MZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str[:len(fmt)], fmt)
        except (ValueError, TypeError):
            continue
    logger.warning(f"No se pudo parsear fecha: {dt_str}")
    return None


def _kp_to_risk(kp: float) -> str:
    """Convierte índice Kp a nivel de riesgo operacional."""
    if kp >= 8:
        return "CRITICAL"
    elif kp >= 6:
        return "HIGH"
    elif kp >= 5:
        return "MEDIUM"
    elif kp >= 4:
        return "LOW"
    return "NONE"
