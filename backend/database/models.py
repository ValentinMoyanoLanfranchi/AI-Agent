"""
database/models.py — Modelos SQLAlchemy para todas las fuentes de datos del sistema.

Tablas:
- ndvi_records       → Datos NDVI de Sentinel/Earthdata (Agente 1)
- disaster_events    → Eventos EONET de NASA (Agente 2)
- space_weather      → Eventos DONKI de NASA (Agente 3)
- apod_records       → Astronomy Picture of the Day (Agente 4)
- iss_passes         → Pasos ISS por coordenada (Agente 4)
- asteroid_records   → Objetos NEO de NeoWs (Agente 5)
- agent_reports      → Reportes generados por agentes (histórico)
- inter_agent_alerts → Alertas inter-agente (Agente 3 → Agente 1)
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text,
    JSON, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from database.session import Base


class NDVIRecord(Base):
    """Réplica local de datos NDVI calculados desde NASA Earthdata / Sentinel Hub."""
    __tablename__ = "ndvi_records"

    id = Column(Integer, primary_key=True, index=True)
    # Polígono o punto del campo agrícola
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    location_name = Column(String(200), nullable=True)
    region_code = Column(String(50), nullable=True)  # ej: "ARG-BA-ZONA1"

    # Valores NDVI
    ndvi_value = Column(Float, nullable=False)
    ndvi_prev_week = Column(Float, nullable=True)
    ndvi_prev_month = Column(Float, nullable=True)
    ndvi_5yr_avg = Column(Float, nullable=True)
    ndvi_change_weekly = Column(Float, nullable=True)   # delta vs semana anterior
    ndvi_change_monthly = Column(Float, nullable=True)

    # Datos climáticos asociados (NASA POWER)
    temperature_max = Column(Float, nullable=True)   # °C
    temperature_min = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    soil_moisture = Column(Float, nullable=True)

    # Metadatos
    satellite_source = Column(String(100), default="NASA_EARTHDATA")
    band_data = Column(JSONB, nullable=True)  # bandas crudas NIR, Red, etc.
    is_anomaly = Column(Boolean, default=False)
    anomaly_severity = Column(String(20), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL

    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ndvi_location", "location", postgresql_using="gist"),
        Index("idx_ndvi_recorded_at", "recorded_at"),
        Index("idx_ndvi_region", "region_code"),
    )


class DisasterEvent(Base):
    """Eventos de desastres naturales de NASA EONET filtrados para Sudamérica."""
    __tablename__ = "disaster_events"

    id = Column(Integer, primary_key=True, index=True)
    eonet_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)  # Wildfires, Floods, Earthquakes, etc.
    status = Column(String(50), default="open")      # open, closed

    # Geolocalización
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    bbox = Column(Geometry("POLYGON", srid=4326), nullable=True)
    country_code = Column(String(10), nullable=True)

    # Metadatos del evento
    magnitude = Column(Float, nullable=True)
    magnitude_unit = Column(String(50), nullable=True)
    sources = Column(JSONB, nullable=True)

    # Severidad calculada por el sistema
    severity_score = Column(Float, default=0.0)
    affects_agricultural_zone = Column(Boolean, default=False)
    nearest_ndvi_zone_km = Column(Float, nullable=True)

    event_start = Column(DateTime, nullable=True, index=True)
    event_end = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_disaster_location", "location", postgresql_using="gist"),
        Index("idx_disaster_category", "category"),
        Index("idx_disaster_event_start", "event_start"),
    )


class SpaceWeatherEvent(Base):
    """Eventos de clima espacial de NASA DONKI (CME, GST, Tormentas Geomagnéticas)."""
    __tablename__ = "space_weather_events"

    id = Column(Integer, primary_key=True, index=True)
    donki_id = Column(String(200), unique=True, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # CME, GST, FLR, SEP, IPS
    start_time = Column(DateTime, nullable=True, index=True)
    peak_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    # Parámetros del evento
    kp_index = Column(Float, nullable=True)          # Índice Kp (0-9)
    kp_index_max = Column(Float, nullable=True)
    speed_km_s = Column(Float, nullable=True)        # Velocidad CME en km/s
    flare_class = Column(String(10), nullable=True)  # X1.5, M2.3, etc.

    # Análisis
    exceeds_kp_threshold = Column(Boolean, default=False)  # Kp > settings.kp_index_threshold
    gps_impact_risk = Column(String(20), nullable=True)    # LOW, MEDIUM, HIGH, CRITICAL
    power_grid_risk = Column(String(20), nullable=True)
    aviation_risk = Column(String(20), nullable=True)
    agriculture_gps_alert_sent = Column(Boolean, default=False)

    link = Column(String(500), nullable=True)
    raw_data = Column(JSONB, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_sw_event_type", "event_type"),
        Index("idx_sw_start_time", "start_time"),
        Index("idx_sw_kp", "kp_index"),
    )


class APODRecord(Base):
    """Registro diario de NASA APOD (Astronomy Picture of the Day)."""
    __tablename__ = "apod_records"

    id = Column(Integer, primary_key=True, index=True)
    apod_date = Column(DateTime, unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    explanation = Column(Text, nullable=False)
    media_type = Column(String(50), default="image")  # image, video
    url = Column(String(1000), nullable=True)
    hdurl = Column(String(1000), nullable=True)
    copyright = Column(String(200), nullable=True)
    service_version = Column(String(20), nullable=True)

    # Explicaciones adaptadas por perfil (pre-generadas)
    explanation_child = Column(Text, nullable=True)
    explanation_student = Column(Text, nullable=True)
    explanation_expert = Column(Text, nullable=True)

    ingested_at = Column(DateTime, default=datetime.utcnow)


class ISSPass(Base):
    """Predicciones de pasos de la ISS por coordenada (Open Notify)."""
    __tablename__ = "iss_passes"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_name = Column(String(200), nullable=True)

    rise_time = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    max_elevation_deg = Column(Float, nullable=True)

    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_iss_location", "location", postgresql_using="gist"),
        Index("idx_iss_rise_time", "rise_time"),
    )


class AsteroidRecord(Base):
    """Objetos Cercanos a la Tierra (NEO) de NASA NeoWs."""
    __tablename__ = "asteroid_records"

    id = Column(Integer, primary_key=True, index=True)
    neo_id = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    designation = Column(String(200), nullable=True)

    # Clasificación de riesgo
    is_potentially_hazardous = Column(Boolean, default=False, index=True)
    absolute_magnitude_h = Column(Float, nullable=True)

    # Dimensiones estimadas
    estimated_diameter_min_km = Column(Float, nullable=True)
    estimated_diameter_max_km = Column(Float, nullable=True)

    # Aproximación más cercana en el período consultado
    close_approach_date = Column(DateTime, nullable=True, index=True)
    miss_distance_km = Column(Float, nullable=True)
    miss_distance_lunar = Column(Float, nullable=True)     # Distancias en unidades lunares
    relative_velocity_km_s = Column(Float, nullable=True)
    orbiting_body = Column(String(50), default="Earth")

    # Contexto humanizado
    miss_distance_human = Column(String(200), nullable=True)  # "12 veces la distancia Tierra-Luna"
    risk_assessment = Column(Text, nullable=True)              # Texto del agente

    raw_data = Column(JSONB, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    approach_date_ingested = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_neo_is_hazardous", "is_potentially_hazardous"),
        Index("idx_neo_close_approach", "close_approach_date"),
    )


class AgentReport(Base):
    """Histórico de reportes generados por cada agente cognitivo."""
    __tablename__ = "agent_reports"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, nullable=False, index=True)   # 1-5
    agent_name = Column(String(100), nullable=False)
    report_type = Column(String(100), nullable=False)        # monitoring, alert, educational, etc.

    # Contenido del reporte
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=False)
    full_report = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)             # INFO, LOW, MEDIUM, HIGH, CRITICAL

    # Datos relacionados (foreign keys opcionales)
    related_ndvi_id = Column(Integer, ForeignKey("ndvi_records.id"), nullable=True)
    related_disaster_id = Column(Integer, ForeignKey("disaster_events.id"), nullable=True)
    related_space_weather_id = Column(Integer, ForeignKey("space_weather_events.id"), nullable=True)
    related_asteroid_id = Column(Integer, ForeignKey("asteroid_records.id"), nullable=True)

    # Metadata
    llm_model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    notifications_sent = Column(JSONB, nullable=True)  # {email: true, slack: true}

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_report_agent_id", "agent_id"),
        Index("idx_report_severity", "severity"),
        Index("idx_report_created_at", "created_at"),
    )


class InterAgentAlert(Base):
    """Bus de eventos inter-agente. Ej: Agente 3 → Agente 1 sobre impacto GPS."""
    __tablename__ = "inter_agent_alerts"

    id = Column(Integer, primary_key=True, index=True)
    source_agent_id = Column(Integer, nullable=False)
    target_agent_id = Column(Integer, nullable=False)
    alert_type = Column(String(100), nullable=False)  # GPS_IMPACT, THERMAL_STRESS, etc.
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)

    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_inter_alert_target", "target_agent_id", "acknowledged"),
    )
