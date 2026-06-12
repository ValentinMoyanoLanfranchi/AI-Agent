"""
agents/graph.py — Orquestador maestro LangGraph.

Grafo de supervisión que enruta solicitudes al agente correcto.
Soporta ejecución individual o pipeline completo.
"""
import logging
from typing import TypedDict, Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END

from agents.agent1_agricultural import run_agent1
from agents.agent2_disasters import run_agent2
from agents.agent3_space_weather import run_agent3
from agents.agent4_educational import run_agent4
from agents.agent5_neows import run_agent5

logger = logging.getLogger(__name__)

AgentName = Literal[
    "agent1_agricultural",
    "agent2_disasters",
    "agent3_space_weather",
    "agent4_educational",
    "agent5_neows",
    "all",
]


class MasterState(TypedDict):
    agent_name: AgentName
    agent_params: dict
    results: dict
    error: Optional[str]


async def run_master_graph(
    agent_name: AgentName = "all",
    agent_params: Optional[dict] = None,
) -> dict:
    """
    Punto de entrada maestro del sistema de agentes.

    Args:
        agent_name: Qué agente ejecutar, o 'all' para el pipeline completo.
        agent_params: Parámetros opcionales para el agente específico.

    Returns:
        Dict con los resultados de todos los agentes ejecutados.
    """
    params = agent_params or {}
    results = {}
    started_at = datetime.utcnow().isoformat()

    try:
        if agent_name == "agent1_agricultural" or agent_name == "all":
            logger.info("[MasterGraph] Ejecutando Agente 1 — Monitoreo Agrícola")
            results["agent1"] = await run_agent1(
                region_code=params.get("region_code"),
                days_back=params.get("days_back", 7),
            )

        if agent_name == "agent2_disasters" or agent_name == "all":
            logger.info("[MasterGraph] Ejecutando Agente 2 — Desastres")
            results["agent2"] = await run_agent2(
                category_filter=params.get("category_filter"),
                days_back=params.get("days_back", 7),
            )

        if agent_name == "agent3_space_weather" or agent_name == "all":
            logger.info("[MasterGraph] Ejecutando Agente 3 — Clima Espacial")
            results["agent3"] = await run_agent3(
                days_back=params.get("days_back", 3),
            )

        if agent_name == "agent4_educational" or agent_name == "all":
            logger.info("[MasterGraph] Ejecutando Agente 4 — Educativo")
            results["agent4"] = await run_agent4(
                demographic_profile=params.get("demographic_profile", "GENERAL"),
                user_location=params.get("user_location", "Buenos Aires"),
            )

        if agent_name == "agent5_neows" or agent_name == "all":
            logger.info("[MasterGraph] Ejecutando Agente 5 — NeoWs")
            results["agent5"] = await run_agent5(
                days_ahead=params.get("days_ahead", 7),
            )

        # Calcular severidad global del sistema
        global_severity = _calculate_global_severity(results)

        return {
            "status": "success",
            "agent_requested": agent_name,
            "global_severity": global_severity,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "results": results,
        }

    except Exception as e:
        logger.error(f"[MasterGraph] Error crítico: {e}", exc_info=True)
        return {
            "status": "error",
            "agent_requested": agent_name,
            "error": str(e),
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "results": results,
        }


def _calculate_global_severity(results: dict) -> str:
    """Calcula el nivel de severidad global del sistema basándose en todos los agentes."""
    severity_order = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "MINIMAL": 1, "NONE": 0}
    max_severity = "MINIMAL"
    max_score = 0

    for agent_key, result in results.items():
        severity = result.get("severity") or result.get("max_risk_level") or "MINIMAL"
        score = severity_order.get(severity.upper(), 0)
        if score > max_score:
            max_score = score
            max_severity = severity.upper()

    return max_severity
