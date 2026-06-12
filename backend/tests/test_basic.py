"""
tests/test_basic.py — Tests básicos de conectividad y módulos.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock


def test_config_loads():
    """Verifica que la configuración se carga correctamente."""
    from config import settings
    assert settings.nasa_api_key is not None
    assert settings.kp_index_threshold == 5.0
    assert settings.ndvi_anomaly_threshold == -0.15
    print(f"✅ Config cargada: env={settings.app_env}, kp_threshold={settings.kp_index_threshold}")


def test_ndvi_calculator():
    """Verifica el cálculo determinista de NDVI."""
    from tools.ndvi_calculator import calculate_ndvi, classify_ndvi, _calculate_risk_level

    # NDVI de vegetación sana: NIR=0.4, Red=0.1 → NDVI=0.6
    ndvi = calculate_ndvi(nir=0.4, red=0.1)
    assert abs(ndvi - 0.6) < 0.001, f"NDVI esperado 0.6, obtenido {ndvi}"

    # NDVI negativo (agua): NIR=0.05, Red=0.2
    ndvi_water = calculate_ndvi(nir=0.05, red=0.2)
    assert ndvi_water < 0, f"NDVI de agua debe ser negativo, obtenido {ndvi_water}"

    # Clasificación
    category, bio = classify_ndvi(0.6)
    assert category == "HEALTHY"

    category_bare, _ = classify_ndvi(0.05)
    assert category_bare in ["BARE_SOIL", "VERY_SPARSE"]

    # Risk level
    risk = _calculate_risk_level(0.2, -20, ["estrés térmico", "déficit hídrico"])
    assert risk in ["HIGH", "CRITICAL"]

    print(f"✅ NDVI Calculator: cálculos correctos")


def test_humanize_miss_distance():
    """Verifica la humanización de distancias de asteroides."""
    from ingestion.nasa_connectors import humanize_miss_distance

    # 12 distancias lunares → debería mencionarlo
    result = humanize_miss_distance(miss_distance_km=4_613_000, lunar_distance=12.0)
    assert "12" in result and "lunar" in result.lower()

    # Muy cercano
    result_close = humanize_miss_distance(miss_distance_km=200_000, lunar_distance=0.52)
    assert "0.52" in result_close or "lunar" in result_close.lower()

    print(f"✅ Humanize distance: '{result}'")


def test_south_america_filter():
    """Verifica el filtro de eventos EONET para Sudamérica."""
    from ingestion.nasa_connectors import filter_south_america_events

    # Evento en Buenos Aires (dentro del Cono Sur)
    mock_data = {
        "events": [
            {
                "id": "EONET_1",
                "title": "Wildfire Buenos Aires",
                "categories": [{"title": "Wildfires"}],
                "status": "open",
                "geometry": [{"coordinates": [-58.38, -34.60], "date": "2026-06-12"}],
            },
            {
                "id": "EONET_2",
                "title": "Wildfire Alaska",
                "categories": [{"title": "Wildfires"}],
                "status": "open",
                "geometry": [{"coordinates": [-150.0, 64.0], "date": "2026-06-12"}],
            },
        ]
    }

    filtered = filter_south_america_events(mock_data)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "EONET_1"
    print(f"✅ EONET Filter: {len(filtered)} evento en Sudamérica (Alaska filtrado correctamente)")


def test_ndvi_anomaly_detection():
    """Verifica la detección de anomalías NDVI."""
    from ingestion.copernicus import detect_ndvi_anomaly

    # Anomalía severa: caída del 30%
    is_anomaly, severity, change_pct = detect_ndvi_anomaly(
        current=0.35,
        historical_avg=0.55,
        threshold=-0.15
    )
    assert is_anomaly == True
    assert severity in ["HIGH", "CRITICAL"]
    assert change_pct < -20

    # Sin anomalía: normal
    is_normal, sev_normal, _ = detect_ndvi_anomaly(
        current=0.52,
        historical_avg=0.55,
        threshold=-0.15
    )
    assert is_normal == False
    assert sev_normal == "NONE"

    print(f"✅ Anomaly Detection: severa={severity}, change={change_pct:.1f}%")


def test_kp_to_risk():
    """Verifica la conversión de Kp a nivel de riesgo."""
    from ingestion.tasks import _kp_to_risk

    assert _kp_to_risk(9.0) == "CRITICAL"
    assert _kp_to_risk(7.0) == "HIGH"
    assert _kp_to_risk(5.5) == "MEDIUM"
    assert _kp_to_risk(4.5) == "LOW"
    assert _kp_to_risk(2.0) == "NONE"

    print("✅ Kp Risk conversion: todos los niveles correctos")


@pytest.mark.asyncio
async def test_ndvi_simulation():
    """Verifica que la simulación NDVI genera datos realistas."""
    from ingestion.copernicus import simulate_ndvi_data, MONITORED_AGRICULTURAL_ZONES

    for zone in MONITORED_AGRICULTURAL_ZONES:
        data = simulate_ndvi_data(zone["region_code"], days_back=7)
        assert len(data) == 7
        for record in data:
            assert -1.0 <= record["ndvi_value"] <= 1.0
            assert record["ndvi_5yr_avg"] > 0

    print(f"✅ NDVI Simulation: {len(MONITORED_AGRICULTURAL_ZONES)} zonas simuladas correctamente")


if __name__ == "__main__":
    # Ejecutar tests directamente
    test_config_loads()
    test_ndvi_calculator()
    test_humanize_miss_distance()
    test_south_america_filter()
    test_ndvi_anomaly_detection()
    test_kp_to_risk()
    asyncio.run(test_ndvi_simulation())
    print("\n🎉 Todos los tests pasaron!")
