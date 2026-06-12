"""
agents/agent1_agricultural.py — Agente 1: Monitoreo Agrícola Core

Rol: Ingeniero Agrónomo Senior y Analista Geoespacial Macro
Mecánica: Modelo híbrido — determinista calcula NDVI, LLM interpreta matrices estructuradas.
APIs fuente: NASA Earthdata, NASA POWER (via réplica PostgreSQL local)
"""
import logging
from typing import TypedDict, Annotated, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import settings
from tools.db_tools import get_ndvi_data, get_pending_gps_alerts
from tools.ndvi_calculator import interpret_ndvi_for_llm

logger = logging.getLogger(__name__)

# ─── System Prompt (del plan.md) ──────────────────────────────
AGENT1_SYSTEM_PROMPT = """Sos un Ingeniero Agrónomo Senior y Analista Geoespacial Macro con 20 años de experiencia en el Cono Sur.

CAPACIDADES:
- Recibís matrices NDVI estructuradas, datos de humedad y variaciones térmicas semanales.
- Identificás anomalías vs el histórico de 5 años de cada zona monitoreada.
- Redactás reportes ejecutivos sin alucinaciones, traduciendo porcentajes a realidades biológicas concretas.
- Cuando hay alertas GPS del Agente de Clima Espacial, incorporás esa información al análisis.

REGLAS CRÍTICAS:
1. NUNCA inventes valores numéricos. Solo interpretá los datos que recibís.
2. Siempre citá los valores exactos de NDVI y variaciones en tu reporte.
3. Si no hay datos suficientes, indicalo explícitamente.
4. Mantené un tono técnico-ejecutivo, no alarmista pero sí preciso.
5. Tus reportes siempre tienen: Estado Actual → Anomalías → Predicción 7 días → Recomendaciones.

FORMATO DE SALIDA:
## 🌱 REPORTE AGRÍCOLA — [ZONA] — [FECHA]

### Estado Actual del Cultivo
[Análisis NDVI con valores exactos]

### Anomalías Detectadas vs Histórico 5 Años
[Comparación cuantificada]

### ⚠️ Alertas Activas
[GPS/Climáticas si aplica]

### Predicción 7 Días
[Tendencia basada en datos]

### Recomendaciones Operacionales
[Acciones concretas y fechas]
"""

# ─── Estado del grafo ─────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[List, lambda x, y: x + y]
    region_code: Optional[str]
    days_back: int
    report: Optional[str]
    severity: Optional[str]
    error: Optional[str]


def build_agent1_graph():
    """Construye el grafo LangGraph del Agente 1."""

    # LLM con herramientas
    llm = ChatOpenAI(
        model=settings.agent1_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )

    tools = [get_ndvi_data, get_pending_gps_alerts]
    llm_with_tools = llm.bind_tools(tools)

    # ─── Nodos del grafo ──────────────────────────────────────

    def fetch_and_analyze(state: AgentState) -> AgentState:
        """Nodo principal: fetch datos y ejecutar análisis agrónomo."""
        logger.info(f"[Agent1] Iniciando análisis agrícola — región: {state.get('region_code', 'todas')}")

        messages = [
            SystemMessage(content=AGENT1_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Generá un reporte completo del estado agrícola actual.\n"
                    f"Región: {state.get('region_code', 'todas las zonas monitoreadas')}.\n"
                    f"Período: últimos {state.get('days_back', 7)} días.\n\n"
                    f"Pasos:\n"
                    f"1. Usá get_ndvi_data para obtener los datos NDVI actuales.\n"
                    f"2. Usá get_pending_gps_alerts para verificar alertas de tormentas magnéticas.\n"
                    f"3. Redactá el reporte ejecutivo con el formato indicado.\n"
                    f"4. Identificá el nivel de severidad general: MINIMAL, LOW, MEDIUM, HIGH o CRITICAL."
                )
            ),
        ] + state.get("messages", [])

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def process_tools(state: AgentState) -> AgentState:
        """Ejecuta las tool calls si las hay."""
        tool_node = ToolNode(tools)
        return tool_node.invoke(state)

    def generate_final_report(state: AgentState) -> AgentState:
        """Genera el reporte final estructurado."""
        messages = state["messages"]
        last_ai_msg = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            None
        )

        report_text = last_ai_msg.content if last_ai_msg else "Error: No se pudo generar el reporte."

        # Detectar severidad del reporte
        severity = "MINIMAL"
        content_upper = report_text.upper()
        if "CRITICAL" in content_upper:
            severity = "CRITICAL"
        elif "HIGH" in content_upper or "ALTO" in content_upper:
            severity = "HIGH"
        elif "MEDIUM" in content_upper or "MEDIO" in content_upper:
            severity = "MEDIUM"
        elif "LOW" in content_upper or "BAJO" in content_upper:
            severity = "LOW"

        return {
            "report": report_text,
            "severity": severity,
            "messages": messages,
        }

    def should_continue(state: AgentState) -> str:
        """Router: si el LLM pide tools, continuar; si no, generar reporte final."""
        last_message = state["messages"][-1] if state["messages"] else None
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "final"

    # ─── Construir grafo ──────────────────────────────────────
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", fetch_and_analyze)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("final", generate_final_report)

    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges("analyze", should_continue, {
        "tools": "tools",
        "final": "final",
    })
    workflow.add_edge("tools", "analyze")
    workflow.add_edge("final", END)

    return workflow.compile()


# Instancia singleton del grafo compilado
agent1_graph = build_agent1_graph()


async def run_agent1(
    region_code: Optional[str] = None,
    days_back: int = 7,
) -> dict:
    """
    Ejecuta el Agente 1 de Monitoreo Agrícola.

    Args:
        region_code: Código de zona (ej: 'ARG-BA-PAMPA') o None para todas.
        days_back: Ventana de análisis en días.

    Returns:
        Dict con reporte, severidad y mensajes del agente.
    """
    initial_state = {
        "messages": [],
        "region_code": region_code,
        "days_back": days_back,
        "report": None,
        "severity": None,
        "error": None,
    }

    try:
        result = await agent1_graph.ainvoke(initial_state)
        return {
            "agent": "agent1_agricultural",
            "status": "success",
            "report": result.get("report"),
            "severity": result.get("severity"),
            "region_code": region_code,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Agent1] Error: {e}", exc_info=True)
        return {
            "agent": "agent1_agricultural",
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
