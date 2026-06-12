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
        "name": "Pampa Húmeda - Buenos Aires",
        "latitude": -34.6037,
        "longitude": -58.3816,
        "country": "ARG",
    },
    {
        "region_code": "ARG-COR-AGRO",
        "name": "Córdoba - Zona Agrícola Norte",
        "latitude": -31.4201,
        "longitude": -64.1888,
        "country": "ARG",
    },
    {
        "region_code": "BRA-MT-CERRADO",
        "name": "Mato Grosso - Cerrado",
        "latitude": -12.6461,
        "longitude": -55.9166,
        "country": "BRA",
    },
    {
        "region_code": "URY-SORIANO",
        "name": "Uruguay - Soriano Agrícola",
        "latitude": -33.4836,
        "longitude": -57.7556,
        "country": "URY",
    },
    {
        "region_code": "CHI-ARAUCANIA",
        "name": "Chile - Araucanía Agrícola",
        "latitude": -38.7360,
        "longitude": -72.5904,
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
