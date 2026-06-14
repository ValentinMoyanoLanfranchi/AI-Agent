"""
ingestion/copernicus.py — Connector para NASA Earthdata (alternativa gratuita a Sentinel Hub).

Implementa el cálculo NDVI usando datos de reflectancia de superficie de NASA Earthdata:
- MODIS Terra/Aqua Land Surface Reflectance (MOD09A1)
- NASA AppEEARS API para extracción por coordenadas

También incluye cálculo NDVI determinista (sin LLM).
"""
import logging
import asyncio
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

# NASA AppEEARS API para extracción de datos MODIS
APPEEARS_BASE = "https://appeears.earthdatacloud.nasa.gov/api"

# Zonas agrícolas monitoreadas en el Cono Sur
MONITORED_AGRICULTURAL_ZONES = [
    {
        "region_code": "ARG-BA-PAMPA",
        "name": "Pampa Húmeda - Pergamino (Buenos Aires)",
        "latitude": -33.89,
        "longitude": -60.57,
        "country": "ARG",
    },
    {
        "region_code": "ARG-COR-AGRO",
        "name": "Córdoba - Marcos Juárez (Zona Agrícola)",
        "latitude": -32.70,
        "longitude": -62.10,
        "country": "ARG",
    },
    {
        "region_code": "BRA-MT-CERRADO",
        "name": "Mato Grosso - Sorriso (Cerrado)",
        "latitude": -12.54,
        "longitude": -55.72,
        "country": "BRA",
    },
    {
        "region_code": "URY-SORIANO",
        "name": "Uruguay - Soriano Agrícola",
        "latitude": -33.60,
        "longitude": -57.90,
        "country": "URY",
    },
    {
        "region_code": "CHI-ARAUCANIA",
        "name": "Chile - Araucanía Agrícola",
        "latitude": -38.75,
        "longitude": -72.40,
        "country": "CHI",
    },
]


def calculate_ndvi(nir_band: float, red_band: float) -> float:
    """
    Cálculo NDVI determinista (sin LLM).
    NDVI = (NIR - Red) / (NIR + Red)

    Valores:
        -1.0 a 0.0  → Agua, nieve, suelo desnudo
         0.0 a 0.2  → Vegetación muy escasa / suelo estéril
         0.2 a 0.4  → Vegetación moderada / pastizales secos
         0.4 a 0.6  → Vegetación sana / cultivos en desarrollo
         0.6 a 1.0  → Vegetación muy densa / cultivos óptimos
    """
    denominator = nir_band + red_band
    if denominator == 0:
        return 0.0
    return float(np.clip((nir_band - red_band) / denominator, -1.0, 1.0))


def classify_ndvi(ndvi_value: float) -> Tuple[str, str]:
    """
    Clasifica el NDVI y retorna (categoría, descripción_biológica).
    Implementa la mecánica del Agente 1: 'traduce porcentajes a realidades biológicas'.
    """
    if ndvi_value < 0.0:
        return "WATER_OR_SNOW", "Superficie de agua, nieve o nube"
    elif ndvi_value < 0.1:
        return "BARE_SOIL", "Suelo desnudo o vegetación extremadamente escasa"
    elif ndvi_value < 0.2:
        return "VERY_SPARSE", "Vegetación muy escasa — posible sequía severa o cosecha reciente"
    elif ndvi_value < 0.35:
        return "SPARSE", "Vegetación escasa — cultivo en estadio temprano o estrés moderado"
    elif ndvi_value < 0.5:
        return "MODERATE", "Vegetación moderada — cultivo en desarrollo con posible estrés hídrico"
    elif ndvi_value < 0.65:
        return "HEALTHY", "Vegetación sana — cultivo en estado óptimo de desarrollo"
    elif ndvi_value < 0.8:
        return "DENSE", "Vegetación densa — cultivo en estadio peak de biomasa"
    else:
        return "VERY_DENSE", "Vegetación muy densa — condiciones de crecimiento excepcionales"


def detect_ndvi_anomaly(
    current: float,
    historical_avg: float,
    threshold: float = None
) -> Tuple[bool, str, float]:
    """
    Detecta anomalías en NDVI comparando con histórico.
    Retorna: (is_anomaly, severity, change_pct)
    """
    if threshold is None:
        threshold = settings.ndvi_anomaly_threshold

    if historical_avg == 0:
        return False, "NONE", 0.0

    change = current - historical_avg
    change_pct = (change / abs(historical_avg)) * 100

    if change <= threshold:
        # Determinar severidad
        if change <= threshold * 3:
            severity = "CRITICAL"
        elif change <= threshold * 2:
            severity = "HIGH"
        else:
            severity = "MEDIUM"
        return True, severity, change_pct

    return False, "NONE", change_pct


def simulate_ndvi_data(region_code: str, days_back: int = 30) -> List[Dict]:
    """
    Genera datos NDVI simulados realistas para desarrollo/hackathon.
    En producción, esto se reemplaza con datos reales de NASA Earthdata.

    Simula variaciones estacionales + ruido aleatorio para el Cono Sur
    (hemisferio sur → junio = invierno → NDVI tiende a bajar).
    """
    np.random.seed(hash(region_code) % 2**31)

    base_ndvi = {
        "ARG-BA-PAMPA": 0.55,
        "ARG-COR-AGRO": 0.48,
        "BRA-MT-CERRADO": 0.62,
        "URY-SORIANO": 0.51,
        "CHI-ARAUCANIA": 0.44,
    }.get(region_code, 0.50)

    # En junio (invierno sur), el NDVI baja ~15-20%
    seasonal_factor = 0.85  # Ajuste estacional para invierno

    records = []
    for i in range(days_back):
        # Tendencia decreciente (análisis 5-años requiere datos históricos reales)
        noise = np.random.normal(0, 0.03)
        trend = -0.002 * i  # Leve tendencia decreciente en invierno
        ndvi = float(np.clip(base_ndvi * seasonal_factor + trend + noise, -0.1, 1.0))

        # NDVI histórico 5 años (simulado como baseline sin factor estacional)
        hist_ndvi = float(np.clip(base_ndvi + np.random.normal(0, 0.02), 0.2, 0.9))

        records.append({
            "ndvi_value": round(ndvi, 4),
            "ndvi_5yr_avg": round(hist_ndvi, 4),
            "ndvi_change_weekly": round(ndvi - (base_ndvi * seasonal_factor), 4),
            "days_ago": i,
        })

    return records


async def fetch_earthdata_ndvi_mock(zone: Dict) -> Dict:
    """
    Mock de NASA Earthdata para desarrollo.
    En producción usar AppEEARS API con credenciales reales.
    """
    await asyncio.sleep(0.1)  # Simular latencia de API

    data = simulate_ndvi_data(zone["region_code"], days_back=1)
    latest = data[0]

    # Simular bandas espectrales que producen ese NDVI
    ndvi = latest["ndvi_value"]
    # Resolución inversa: si NDVI = (NIR-Red)/(NIR+Red), asumimos Red=0.1
    red = 0.1
    nir = red * (1 + ndvi) / (1 - ndvi) if ndvi != 1 else 0.9

    return {
        "zone": zone,
        "ndvi_value": ndvi,
        "ndvi_5yr_avg": latest["ndvi_5yr_avg"],
        "nir_band": round(nir, 4),
        "red_band": round(red, 4),
        "satellite_source": "NASA_EARTHDATA_MOCK",
        "measurement_date": date.today().isoformat(),
    }


# ─── NDVI REAL: NASA MODIS MOD13Q1 vía ORNL DAAC (sin autenticación) ───
MODIS_BASE = "https://modis.ornl.gov/rst/api/v1"
MODIS_PRODUCT = "MOD13Q1"
MODIS_NDVI_BAND = "250m_16_days_NDVI"


async def _modis_chunk(client, lat, lon, start, end, headers) -> List[Tuple[int, float, str]]:
    """Un request de subset MODIS (<=10 composites). Devuelve [(doy, ndvi, calendar_date)]."""
    sr = await client.get(f"{MODIS_BASE}/{MODIS_PRODUCT}/subset",
                          params={"latitude": lat, "longitude": lon,
                                  "startDate": start, "endDate": end,
                                  "band": MODIS_NDVI_BAND,
                                  "kmAboveBelow": 1, "kmLeftRight": 1},
                          headers=headers)
    sr.raise_for_status()
    p = sr.json()
    scale = float(p.get("scale", 0.0001))
    out = []
    for row in p.get("subset", []):
        md = row.get("modis_date", "")
        vals = [v for v in row.get("data", []) if isinstance(v, (int, float)) and -2000 <= v <= 10000]
        if md and vals:
            out.append((int(md[5:8]), sum(vals) / len(vals) * scale, row.get("calendar_date", "")))
    return out


async def fetch_modis_ndvi(zone: Dict) -> Dict:
    """
    NDVI satelital REAL de NASA (MODIS MOD13Q1, 250m, composite 16 días) vía el
    servicio público del ORNL DAAC — sin autenticación. Drop-in del mock.
    La API limita ~10 composites por request, así que se chunkea: una ventana reciente
    (valor actual) + la misma ventana estacional de los 4 años previos (baseline real).
    """
    lat, lon = zone["latitude"], zone["longitude"]
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=45) as client:
        dr = await client.get(f"{MODIS_BASE}/{MODIS_PRODUCT}/dates",
                              params={"latitude": lat, "longitude": lon}, headers=headers)
        dr.raise_for_status()
        dates = dr.json().get("dates", [])
        if not dates:
            raise ValueError("MODIS sin fechas para el punto")
        latest = dates[-1]["modis_date"]            # ej. 'A2026113'
        ly, ld = int(latest[1:5]), int(latest[5:8])

        # Ventana reciente -> valor actual (<=10 composites)
        cur = await _modis_chunk(client, lat, lon, f"A{ly}{max(1, ld - 150):03d}", latest, headers)

        # Baseline estacional real: misma época del año, 4 años previos
        seasonal = []
        for yr in range(ly - 4, ly):
            lo, hi = max(1, ld - 64), min(361, ld + 64)
            try:
                ch = await _modis_chunk(client, lat, lon, f"A{yr}{lo:03d}", f"A{yr}{hi:03d}", headers)
                seasonal += [a for (doy, a, _) in ch if abs(doy - ld) <= 24]
            except Exception:
                continue

    if not cur:
        raise ValueError("MODIS sin valores NDVI actuales")
    cur.sort(key=lambda x: x[0])
    cur_doy, cur_ndvi, cur_cal = cur[-1]
    if not seasonal:
        seasonal = [a for (_, a, _) in cur]
    baseline = sum(seasonal) / len(seasonal)

    return {
        "zone": zone,
        "ndvi_value": round(cur_ndvi, 4),
        "ndvi_5yr_avg": round(baseline, 4),
        "nir_band": None,
        "red_band": None,
        "satellite_source": "NASA_MODIS_MOD13Q1",
        "measurement_date": cur_cal or date.today().isoformat(),
    }
