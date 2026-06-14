"""
ingestion/nasa_connectors.py — Conectores REST para todas las APIs públicas de NASA.

APIs cubiertas:
  - NASA DONKI   → Clima espacial (CME, GST, tormentas geomagnéticas)
  - NASA NeoWs   → Objetos cercanos a la Tierra (asteroides)
  - NASA EONET   → Eventos naturales (desastres)
  - NASA APOD    → Astronomía del día
  - Open Notify  → Posición ISS y pasos sobre coordenadas
  - NASA POWER   → Datos meteorológicos para agricultura

Regla de Oro: Estas funciones solo se llaman desde Celery (background).
              Los agentes LLM NUNCA llaman estas funciones directamente.
"""
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

# ─── Base URLs ────────────────────────────────────────────────
NASA_BASE = "https://api.nasa.gov"
OPEN_NOTIFY_BASE = "http://api.open-notify.org"


# ─── Retry decorator ──────────────────────────────────────────
def nasa_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )


# ─────────────────────────────────────────────────────────────
# DONKI — Clima Espacial (Agente 3)
# ─────────────────────────────────────────────────────────────

@nasa_retry()
async def fetch_donki_cme(start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict]:
    """Coronal Mass Ejections (CME) de los últimos 7 días por defecto."""
    if not start_date:
        start_date = date.today() - timedelta(days=7)
    if not end_date:
        end_date = date.today()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NASA_BASE}/DONKI/CME",
            params={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "api_key": settings.nasa_api_key,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"DONKI CME: {len(data)} eventos obtenidos")
        return data or []


@nasa_retry()
async def fetch_donki_gst(start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict]:
    """Geomagnetic Storms (GST) — incluye índice Kp crítico."""
    if not start_date:
        start_date = date.today() - timedelta(days=7)
    if not end_date:
        end_date = date.today()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NASA_BASE}/DONKI/GST",
            params={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "api_key": settings.nasa_api_key,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"DONKI GST: {len(data)} tormentas geomagnéticas")
        return data or []


@nasa_retry()
async def fetch_donki_flr(start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict]:
    """Solar Flares (FLR)."""
    if not start_date:
        start_date = date.today() - timedelta(days=7)
    if not end_date:
        end_date = date.today()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NASA_BASE}/DONKI/FLR",
            params={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "api_key": settings.nasa_api_key,
            }
        )
        resp.raise_for_status()
        return resp.json() or []


# ─────────────────────────────────────────────────────────────
# NeoWs — Asteroides (Agente 5)
# ─────────────────────────────────────────────────────────────

@nasa_retry()
async def fetch_neows_feed(start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
    """Near Earth Objects para un rango de fechas (máx 7 días por request)."""
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=7)

    # NeoWs limita a 7 días por request
    delta = (end_date - start_date).days
    if delta > 7:
        end_date = start_date + timedelta(days=7)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NASA_BASE}/neo/rest/v1/feed",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "api_key": settings.nasa_api_key,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        total = data.get("element_count", 0)
        logger.info(f"NeoWs: {total} asteroides en el período")
        return data


def extract_hazardous_asteroids(neows_feed: Dict) -> List[Dict]:
    """Extrae solo asteroides con is_potentially_hazardous_asteroid = True."""
    hazardous = []
    near_objects = neows_feed.get("near_earth_objects", {})

    for day_str, asteroids in near_objects.items():
        for asteroid in asteroids:
            if asteroid.get("is_potentially_hazardous_asteroid", False):
                # Agregar la fecha del día para referencia
                asteroid["_query_date"] = day_str
                hazardous.append(asteroid)

    logger.info(f"NeoWs: {len(hazardous)} asteroides potencialmente peligrosos encontrados")
    return hazardous


def humanize_miss_distance(miss_distance_km: float, lunar_distance: float) -> str:
    """
    Convierte distancias técnicas en métricas comprensibles para el público.
    Implementa la mecánica del Agente 5: 'traduce distancias a métricas comprensibles'.
    """
    earth_circumference = 40075  # km

    if lunar_distance >= 10:
        return f"{lunar_distance:.1f} veces la distancia Tierra-Luna"
    elif lunar_distance >= 1:
        return f"{lunar_distance:.2f} veces la distancia Tierra-Luna"
    elif miss_distance_km > 1_000_000:
        return f"{miss_distance_km / 1_000_000:.2f} millones de km ({lunar_distance:.2f}x la distancia lunar)"
    else:
        vueltas = miss_distance_km / earth_circumference
        return f"{miss_distance_km:,.0f} km ({vueltas:.0f} veces la circunferencia terrestre)"


# ─────────────────────────────────────────────────────────────
# EONET — Eventos Naturales / Desastres (Agente 2)
# ─────────────────────────────────────────────────────────────

# Categorías EONET de interés para el Cono Sur
EONET_CATEGORIES_OF_INTEREST = [
    "Wildfires",       # Incendios
    "Floods",          # Inundaciones
    "Severe Storms",   # Tormentas severas
    "Earthquakes",     # Terremotos
    "Volcanoes",       # Volcanes
    "Landslides",      # Deslizamientos
    "Droughts",        # Sequías
]

# Bounding box para Sudamérica (Cono Sur)
SOUTH_AMERICA_BBOX = {
    "min_lat": -55.0,  # Tierra del Fuego
    "max_lat": 5.0,    # Norte de Colombia
    "min_lon": -82.0,  # Costa Pacífico
    "max_lon": -34.0,  # Costa Atlántica
}


@nasa_retry()
async def fetch_eonet_events(days: int = 30, status: str = "open") -> Dict:
    """Eventos activos de EONET, filtrados para Sudamérica."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            # Host directo de EONET: el proxy api.nasa.gov da 503 intermitente.
            # El endpoint directo es más estable y no requiere api_key.
            "https://eonet.gsfc.nasa.gov/api/v3/events",
            params={
                "days": days,
                "status": status,
            }
        )
        resp.raise_for_status()
        return resp.json()


def filter_south_america_events(eonet_data: Dict) -> List[Dict]:
    """Filtra eventos EONET dentro del Cono Sur."""
    events = eonet_data.get("events", [])
    south_american = []

    bbox = SOUTH_AMERICA_BBOX
    for event in events:
        for geometry in event.get("geometry", []):
            coords = geometry.get("coordinates")
            if not coords:
                continue

            # EONET usa [lon, lat]
            if isinstance(coords[0], list):
                # Polygon o MultiPoint — usar primer punto
                lon, lat = coords[0][0], coords[0][1]
            else:
                lon, lat = coords[0], coords[1]

            if (bbox["min_lat"] <= lat <= bbox["max_lat"] and
                    bbox["min_lon"] <= lon <= bbox["max_lon"]):
                south_american.append(event)
                break

    logger.info(f"EONET: {len(south_american)}/{len(events)} eventos en Sudamérica")
    return south_american


# ─────────────────────────────────────────────────────────────
# APOD — Astronomía del Día (Agente 4)
# ─────────────────────────────────────────────────────────────

@nasa_retry()
async def fetch_apod(apod_date: Optional[date] = None) -> Dict:
    """Obtiene el APOD para una fecha específica (hoy por defecto)."""
    params = {"api_key": settings.nasa_api_key, "thumbs": "true"}
    if apod_date:
        params["date"] = apod_date.isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{NASA_BASE}/planetary/apod", params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"APOD: '{data.get('title')}' ({data.get('date')})")
        return data


# ─────────────────────────────────────────────────────────────
# Open Notify — ISS Location & Passes (Agente 4)
# ─────────────────────────────────────────────────────────────

@nasa_retry()
async def fetch_iss_current_location() -> Dict:
    """Posición actual de la ISS en tiempo real."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{OPEN_NOTIFY_BASE}/iss-now.json")
        resp.raise_for_status()
        return resp.json()


def _generate_mock_iss_passes(latitude: float, longitude: float, n_passes: int = 5) -> Dict:
    """
    Genera pasos ISS simulados realistas cuando la API de Open Notify no está disponible.
    Open Notify iss-pass.json fue discontinuado en 2023.
    """
    import math
    now_ts = int(datetime.utcnow().timestamp())
    # La ISS orbita cada ~92 minutos (5520 segundos)
    orbital_period = 5520
    passes = []
    for i in range(n_passes):
        # Cada pase visible dura entre 2 y 7 minutos
        rise_ts = now_ts + (i + 1) * orbital_period + int(abs(math.sin(latitude + i)) * 3600)
        duration = int(120 + abs(math.cos(longitude + i)) * 300)  # 2-7 min
        passes.append({"risetime": rise_ts, "duration": duration})
    return {"message": "success", "response": passes, "_simulated": True}


def _compute_real_iss_passes(latitude: float, longitude: float, n_passes: int = 5, days: int = 5) -> Dict:
    """
    Predicciones REALES de pasos de la ISS calculadas desde los datos orbitales
    reales (TLE de Celestrak, NORAD 25544) con skyfield (SGP4). Sin autenticación.
    Reemplaza a la API discontinuada de Open Notify con cálculo astronómico real.
    """
    from datetime import timedelta
    from skyfield.api import load, wgs84, EarthSatellite

    r = httpx.get("https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE", timeout=20)
    r.raise_for_status()
    lines = [ln.strip() for ln in r.text.strip().splitlines() if ln.strip()]
    if len(lines) < 3 or not lines[1].startswith("1 25544"):
        raise ValueError("TLE de la ISS inválido")
    name, l1, l2 = lines[0], lines[1], lines[2]

    ts = load.timescale()
    sat = EarthSatellite(l1, l2, name, ts)
    loc = wgs84.latlon(latitude, longitude)
    t0 = ts.now()
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=days))
    times, events = sat.find_events(loc, t0, t1, altitude_degrees=10.0)

    ev = list(zip(times, events))
    passes, i = [], 0
    while i < len(ev) and len(passes) < n_passes:
        if ev[i][1] == 0:  # rise
            rise_t, culm, j = ev[i][0], None, i + 1
            while j < len(ev) and ev[j][1] != 2:  # hasta set
                if ev[j][1] == 1:
                    culm = ev[j][0]
                j += 1
            if j < len(ev):
                dur = int((ev[j][0].utc_datetime() - rise_t.utc_datetime()).total_seconds())
                max_el = None
                if culm is not None:
                    alt, _, _ = (sat - loc).at(culm).altaz()
                    max_el = round(float(alt.degrees), 1)
                passes.append({
                    "risetime": int(rise_t.utc_datetime().timestamp()),
                    "duration": dur,
                    "max_elevation": max_el,
                })
                i = j + 1
                continue
        i += 1
    if not passes:
        raise ValueError("No se calcularon pasos visibles de la ISS")
    return {"message": "success", "response": passes, "source": "CELESTRAK_TLE_SKYFIELD"}


async def fetch_iss_passes(latitude: float, longitude: float, n_passes: int = 5) -> Dict:
    """
    Predicciones de pasos de la ISS sobre una coordenada.
    Usa cálculo REAL (TLE Celestrak + skyfield); fallback simulado si algo falla.
    """
    try:
        return _compute_real_iss_passes(latitude, longitude, n_passes)
    except Exception as e:
        logger.warning(f"Cálculo real de pasos ISS falló ({e}). Usando datos simulados.")
        return _generate_mock_iss_passes(latitude, longitude, n_passes)



# ─────────────────────────────────────────────────────────────
# NASA POWER — Datos climáticos para agricultura (Agente 1)
# ─────────────────────────────────────────────────────────────

@nasa_retry()
async def fetch_nasa_power_data(
    latitude: float,
    longitude: float,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict:
    """
    Datos meteorológicos de NASA POWER para una coordenada agrícola.
    Parámetros: temperatura, precipitación, humedad, radiación solar.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    parameters = "T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,GWETTOP"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params={
                "parameters": parameters,
                "community": "AG",  # Agricultural community
                "longitude": longitude,
                "latitude": latitude,
                "start": start_date.strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
                "format": "JSON",
            }
        )
        resp.raise_for_status()
        return resp.json()
