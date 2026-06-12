"""
tools/ndvi_calculator.py — Calculadora NDVI determinista (sin LLM).

Los LLMs reciben el output estructurado de estas funciones,
NO procesan imágenes ni datos crudos satelitales.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
from langchain.tools import tool


def calculate_ndvi(nir: float, red: float) -> float:
    """NDVI = (NIR - Red) / (NIR + Red). Rango: [-1, 1]."""
    denominator = nir + red
    if denominator == 0:
        return 0.0
    return float(np.clip((nir - red) / denominator, -1.0, 1.0))


def interpret_ndvi_for_llm(
    region_code: str,
    region_name: str,
    current_ndvi: float,
    historical_avg: float,
    weekly_change: float,
    temperature_max: Optional[float] = None,
    precipitation_mm: Optional[float] = None,
    soil_moisture: Optional[float] = None,
) -> Dict:
    """
    Convierte datos numéricos de NDVI en un diccionario estructurado
    que el LLM puede interpretar sin procesar datos crudos.

    Este es el artefacto que recibe el Agente 1 como input.
    """
    # Clasificar NDVI actual
    category, bio_description = _classify_ndvi(current_ndvi)

    # Calcular cambio porcentual vs histórico
    if historical_avg != 0:
        change_vs_historical_pct = ((current_ndvi - historical_avg) / abs(historical_avg)) * 100
    else:
        change_vs_historical_pct = 0.0

    # Detectar tipo de estrés
    stress_indicators = []
    if temperature_max and temperature_max > 35:
        stress_indicators.append(f"Estrés térmico: temperatura máxima {temperature_max:.1f}°C (umbral crítico: 35°C)")
    if precipitation_mm is not None and precipitation_mm < 5:
        stress_indicators.append(f"Déficit hídrico: precipitación {precipitation_mm:.1f}mm (por debajo del umbral mínimo)")
    if soil_moisture is not None and soil_moisture < 0.2:
        stress_indicators.append(f"Humedad de suelo crítica: {soil_moisture:.2%} (campo marchitez permanente)")
    if weekly_change <= -0.1:
        stress_indicators.append(f"Caída semanal severa de NDVI: {weekly_change:+.4f} ({weekly_change*100:+.1f}%)")

    # Riesgo global
    risk_level = _calculate_risk_level(current_ndvi, change_vs_historical_pct, stress_indicators)

    return {
        "region": {
            "code": region_code,
            "name": region_name,
            "measurement_date": datetime.utcnow().isoformat(),
        },
        "ndvi_analysis": {
            "current_value": round(current_ndvi, 4),
            "historical_5yr_average": round(historical_avg, 4),
            "weekly_change": round(weekly_change, 4),
            "change_vs_historical_pct": round(change_vs_historical_pct, 2),
            "category": category,
            "biological_description": bio_description,
        },
        "climate_data": {
            "temperature_max_celsius": temperature_max,
            "precipitation_last_week_mm": precipitation_mm,
            "soil_moisture_fraction": soil_moisture,
        },
        "risk_assessment": {
            "risk_level": risk_level,
            "stress_indicators": stress_indicators,
            "anomaly_detected": change_vs_historical_pct <= -10,
        },
        "agent_instructions": (
            "Sos un Ingeniero Agrónomo Senior analizando los datos de campo que se proveen. "
            "NO inventes datos. Interpreta los valores numéricos y tradúcelos a realidades biológicas concretas. "
            "Redactá un reporte ejecutivo en español con: 1) Estado actual del cultivo, "
            "2) Anomalías detectadas vs histórico de 5 años, 3) Predicción de estrés a 7 días, "
            "4) Recomendaciones operacionales específicas."
        ),
    }


def _classify_ndvi(ndvi: float) -> Tuple[str, str]:
    if ndvi < 0.0:
        return "WATER_OR_SNOW", "Superficie de agua, nieve o nube — no hay cultivo"
    elif ndvi < 0.1:
        return "BARE_SOIL", "Suelo desnudo — sin cobertura vegetal activa"
    elif ndvi < 0.2:
        return "VERY_SPARSE", "Vegetación muy escasa — posible sequía severa o cosecha reciente"
    elif ndvi < 0.35:
        return "SPARSE", "Vegetación escasa — cultivo en estadio temprano o estrés moderado"
    elif ndvi < 0.5:
        return "MODERATE", "Vegetación moderada — desarrollo con posible estrés hídrico o térmico"
    elif ndvi < 0.65:
        return "HEALTHY", "Vegetación sana — cultivo en estado óptimo de desarrollo"
    elif ndvi < 0.8:
        return "DENSE", "Vegetación densa — cultivo en estadio peak de biomasa"
    else:
        return "VERY_DENSE", "Vegetación muy densa — condiciones de crecimiento excepcionales"


def _calculate_risk_level(ndvi: float, change_pct: float, stress_indicators: List[str]) -> str:
    score = 0

    # NDVI absoluto
    if ndvi < 0.2:
        score += 40
    elif ndvi < 0.35:
        score += 25
    elif ndvi < 0.5:
        score += 10

    # Cambio vs histórico
    if change_pct <= -25:
        score += 40
    elif change_pct <= -15:
        score += 25
    elif change_pct <= -10:
        score += 15

    # Indicadores de estrés adicionales
    score += len(stress_indicators) * 10

    if score >= 60:
        return "CRITICAL"
    elif score >= 40:
        return "HIGH"
    elif score >= 20:
        return "MEDIUM"
    elif score >= 10:
        return "LOW"
    return "MINIMAL"
