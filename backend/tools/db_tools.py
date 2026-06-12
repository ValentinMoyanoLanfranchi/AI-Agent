"""
tools/db_tools.py — LangChain Tools para consultar réplicas locales en PostgreSQL.

Los agentes LLM usan estas tools para obtener datos estructurados.
REGLA DE ORO: Ningún agente llama APIs externas directamente.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from langchain.tools import tool
from sqlalchemy import text, desc, func
from sqlalchemy.orm import Session

from database.session import SyncSessionLocal
from database.models import (
    NDVIRecord, DisasterEvent, SpaceWeatherEvent,
    APODRecord, ISSPass, AsteroidRecord, AgentReport, InterAgentAlert
)
from config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# TOOLS PARA AGENTE 1 — Monitoreo Agrícola
# ─────────────────────────────────────────────────────────────

@tool
def get_ndvi_data(region_code: Optional[str] = None, days_back: int = 7) -> Dict:
    """
    Obtiene datos NDVI recientes de las zonas agrícolas monitoreadas.
    Usar para evaluar salud de cultivos y detectar anomalías.

    Args:
        region_code: Código de región específica (ej: 'ARG-BA-PAMPA'). None = todas las zonas.
        days_back: Cuántos días hacia atrás consultar (máx 90).

    Returns:
        Dict con registros NDVI estructurados por zona.
    """
    days_back = min(max(days_back, 1), 90)
    since = datetime.utcnow() - timedelta(days=days_back)

    with SyncSessionLocal() as db:
        query = db.query(NDVIRecord).filter(NDVIRecord.recorded_at >= since)
        if region_code:
            query = query.filter(NDVIRecord.region_code == region_code)

        records = query.order_by(desc(NDVIRecord.recorded_at)).limit(50).all()

        return {
            "total_records": len(records),
            "query": {"region_code": region_code, "days_back": days_back},
            "zones": [
                {
                    "region_code": r.region_code,
                    "location_name": r.location_name,
                    "ndvi_current": r.ndvi_value,
                    "ndvi_5yr_avg": r.ndvi_5yr_avg,
                    "ndvi_change_weekly": r.ndvi_change_weekly,
                    "temperature_max": r.temperature_max,
                    "precipitation_mm": r.precipitation_mm,
                    "soil_moisture": r.soil_moisture,
                    "is_anomaly": r.is_anomaly,
                    "anomaly_severity": r.anomaly_severity,
                    "satellite_source": r.satellite_source,
                    "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                }
                for r in records
            ],
        }


@tool
def get_pending_gps_alerts() -> Dict:
    """
    Obtiene alertas GPS inter-agente pendientes (enviadas por Agente 3).
    Usar cuando necesites verificar si hay tormentas geomagnéticas que afectan la maquinaria agrícola.

    Returns:
        Dict con alertas no reconocidas del Agente 3.
    """
    with SyncSessionLocal() as db:
        alerts = (
            db.query(InterAgentAlert)
            .filter(
                InterAgentAlert.target_agent_id == 1,
                InterAgentAlert.acknowledged == False,
            )
            .order_by(desc(InterAgentAlert.created_at))
            .limit(10)
            .all()
        )

        return {
            "pending_alerts": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "payload": a.payload,
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ],
        }


# ─────────────────────────────────────────────────────────────
# TOOLS PARA AGENTE 2 — Alertas de Desastres
# ─────────────────────────────────────────────────────────────

@tool
def get_active_disasters(category: Optional[str] = None, days_back: int = 7) -> Dict:
    """
    Obtiene eventos de desastres naturales activos en Sudamérica.
    Usar para identificar incendios, inundaciones, terremotos, etc.

    Args:
        category: Filtrar por categoría (Wildfires, Floods, Earthquakes, Volcanoes...). None = todas.
        days_back: Ventana temporal en días.

    Returns:
        Dict con eventos activos y sus coordenadas.
    """
    since = datetime.utcnow() - timedelta(days=days_back)

    with SyncSessionLocal() as db:
        query = db.query(DisasterEvent).filter(
            DisasterEvent.ingested_at >= since,
            DisasterEvent.status == "open",
        )
        if category:
            query = query.filter(DisasterEvent.category.ilike(f"%{category}%"))

        events = query.order_by(desc(DisasterEvent.event_start)).limit(30).all()

        return {
            "total_events": len(events),
            "filters": {"category": category, "days_back": days_back},
            "events": [
                {
                    "id": e.id,
                    "eonet_id": e.eonet_id,
                    "title": e.title,
                    "category": e.category,
                    "status": e.status,
                    "latitude": e.latitude,
                    "longitude": e.longitude,
                    "country_code": e.country_code,
                    "severity_score": e.severity_score,
                    "affects_agricultural_zone": e.affects_agricultural_zone,
                    "nearest_ndvi_zone_km": e.nearest_ndvi_zone_km,
                    "event_start": e.event_start.isoformat() if e.event_start else None,
                }
                for e in events
            ],
        }


@tool
def get_disasters_near_agricultural_zones(radius_km: float = 50.0) -> Dict:
    """
    Consulta PostGIS para verificar proximidad de desastres con zonas agrícolas activas.
    Implementa la lógica del Agente 2: cruzar desastre con zonas agrícolas del Agente 1.

    Args:
        radius_km: Radio de búsqueda en km alrededor de cada zona agrícola.

    Returns:
        Dict con desastres que afectan zonas agrícolas monitoreadas.
    """
    with SyncSessionLocal() as db:
        # Consulta PostGIS espacial
        query = text("""
            SELECT
                d.id,
                d.title,
                d.category,
                d.latitude,
                d.longitude,
                d.status,
                d.event_start,
                n.region_code,
                n.location_name as zone_name,
                n.ndvi_value,
                ST_Distance(
                    d.location::geography,
                    n.location::geography
                ) / 1000 as distance_km
            FROM disaster_events d
            CROSS JOIN (
                SELECT DISTINCT ON (region_code) *
                FROM ndvi_records
                ORDER BY region_code, recorded_at DESC
            ) n
            WHERE d.status = 'open'
              AND d.location IS NOT NULL
              AND n.location IS NOT NULL
              AND ST_DWithin(
                    d.location::geography,
                    n.location::geography,
                    :radius_meters
                  )
            ORDER BY distance_km
            LIMIT 20
        """)

        rows = db.execute(query, {"radius_meters": radius_km * 1000}).fetchall()

        results = []
        for row in rows:
            results.append({
                "disaster_id": row.id,
                "title": row.title,
                "category": row.category,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "status": row.status,
                "event_start": row.event_start.isoformat() if row.event_start else None,
                "affected_zone_code": row.region_code,
                "affected_zone_name": row.zone_name,
                "zone_ndvi": row.ndvi_value,
                "distance_km": round(row.distance_km, 2),
            })

        return {
            "radius_km": radius_km,
            "affected_agricultural_zones": len(results),
            "events": results,
        }


# ─────────────────────────────────────────────────────────────
# TOOLS PARA AGENTE 3 — Clima Espacial
# ─────────────────────────────────────────────────────────────

@tool
def get_space_weather_events(event_type: Optional[str] = None, days_back: int = 7) -> Dict:
    """
    Obtiene eventos de clima espacial (CME, GST, FLR) de la base local.

    Args:
        event_type: 'CME', 'GST', 'FLR', o None para todos.
        days_back: Ventana temporal en días.

    Returns:
        Dict con eventos, incluyendo índice Kp y niveles de riesgo.
    """
    since = datetime.utcnow() - timedelta(days=days_back)

    with SyncSessionLocal() as db:
        query = db.query(SpaceWeatherEvent).filter(SpaceWeatherEvent.ingested_at >= since)
        if event_type:
            query = query.filter(SpaceWeatherEvent.event_type == event_type.upper())

        events = query.order_by(desc(SpaceWeatherEvent.start_time)).limit(20).all()

        return {
            "total_events": len(events),
            "kp_threshold": settings.kp_index_threshold,
            "events": [
                {
                    "id": e.id,
                    "type": e.event_type,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "kp_index": e.kp_index,
                    "kp_index_max": e.kp_index_max,
                    "speed_km_s": e.speed_km_s,
                    "flare_class": e.flare_class,
                    "exceeds_threshold": e.exceeds_kp_threshold,
                    "gps_impact_risk": e.gps_impact_risk,
                    "power_grid_risk": e.power_grid_risk,
                    "aviation_risk": e.aviation_risk,
                    "link": e.link,
                }
                for e in events
            ],
        }


# ─────────────────────────────────────────────────────────────
# TOOLS PARA AGENTE 4 — Divulgación Educativa
# ─────────────────────────────────────────────────────────────

@tool
def get_today_apod() -> Dict:
    """
    Obtiene el APOD (Astronomy Picture of the Day) más reciente de la base local.

    Returns:
        Dict con título, explicación, URL de imagen y metadata.
    """
    with SyncSessionLocal() as db:
        apod = (
            db.query(APODRecord)
            .order_by(desc(APODRecord.apod_date))
            .first()
        )

        if not apod:
            return {"error": "No hay registros APOD. Ejecutar tarea de ingesta primero."}

        return {
            "date": apod.apod_date.isoformat() if apod.apod_date else None,
            "title": apod.title,
            "explanation": apod.explanation,
            "media_type": apod.media_type,
            "url": apod.url,
            "hdurl": apod.hdurl,
            "copyright": apod.copyright,
            "has_child_explanation": bool(apod.explanation_child),
            "has_student_explanation": bool(apod.explanation_student),
            "has_expert_explanation": bool(apod.explanation_expert),
        }


@tool
def get_iss_passes(location_name: Optional[str] = None) -> Dict:
    """
    Obtiene próximos pasos de la ISS sobre ciudades monitoreadas.

    Args:
        location_name: Ciudad específica (Buenos Aires, Santiago, etc.) o None para todas.

    Returns:
        Dict con horarios de pasos y duración.
    """
    with SyncSessionLocal() as db:
        now = datetime.utcnow()
        query = (
            db.query(ISSPass)
            .filter(ISSPass.rise_time >= now)
            .order_by(ISSPass.rise_time)
        )

        if location_name:
            query = query.filter(ISSPass.location_name.ilike(f"%{location_name}%"))

        passes = query.limit(20).all()

        return {
            "total_upcoming_passes": len(passes),
            "passes": [
                {
                    "location": p.location_name,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "rise_time_utc": p.rise_time.isoformat(),
                    "duration_minutes": round(p.duration_seconds / 60, 1),
                    "max_elevation_deg": p.max_elevation_deg,
                }
                for p in passes
            ],
        }


# ─────────────────────────────────────────────────────────────
# TOOLS PARA AGENTE 5 — NeoWs Asteroides
# ─────────────────────────────────────────────────────────────

@tool
def get_hazardous_asteroids(days_ahead: int = 7) -> Dict:
    """
    Obtiene asteroides potencialmente peligrosos próximos a acercarse a la Tierra.

    Args:
        days_ahead: Cuántos días hacia adelante consultar.

    Returns:
        Dict con asteroides peligrosos y distancias humanizadas.
    """
    end_date = datetime.utcnow() + timedelta(days=days_ahead)

    with SyncSessionLocal() as db:
        hazardous = (
            db.query(AsteroidRecord)
            .filter(
                AsteroidRecord.is_potentially_hazardous == True,
                AsteroidRecord.close_approach_date <= end_date,
                AsteroidRecord.close_approach_date >= datetime.utcnow(),
            )
            .order_by(AsteroidRecord.close_approach_date)
            .limit(20)
            .all()
        )

        all_recent = (
            db.query(AsteroidRecord)
            .filter(AsteroidRecord.close_approach_date >= datetime.utcnow() - timedelta(days=1))
            .order_by(AsteroidRecord.miss_distance_km)
            .limit(10)
            .all()
        )

        return {
            "query_days_ahead": days_ahead,
            "hazardous_count": len(hazardous),
            "all_recent_count": len(all_recent),
            "hazardous_asteroids": [
                {
                    "neo_id": a.neo_id,
                    "name": a.name,
                    "is_potentially_hazardous": a.is_potentially_hazardous,
                    "diameter_min_km": a.estimated_diameter_min_km,
                    "diameter_max_km": a.estimated_diameter_max_km,
                    "close_approach_date": a.close_approach_date.isoformat() if a.close_approach_date else None,
                    "miss_distance_km": a.miss_distance_km,
                    "miss_distance_lunar_units": a.miss_distance_lunar,
                    "miss_distance_human": a.miss_distance_human,
                    "relative_velocity_km_s": a.relative_velocity_km_s,
                }
                for a in hazardous
            ],
            "closest_all_types": [
                {
                    "name": a.name,
                    "is_hazardous": a.is_potentially_hazardous,
                    "miss_distance_human": a.miss_distance_human,
                    "miss_distance_km": a.miss_distance_km,
                    "close_approach_date": a.close_approach_date.isoformat() if a.close_approach_date else None,
                }
                for a in all_recent
            ],
        }
