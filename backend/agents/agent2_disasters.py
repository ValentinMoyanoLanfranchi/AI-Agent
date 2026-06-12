"""
agents/agent2_disasters.py — Agente 2: Alertas de Desastres Naturales

Rol: Director de Gestión de Riesgos y Protección Civil
Mecánica: Filtra por coordenadas del Cono Sur + PostGIS para proximidad con zonas agrícolas.
APIs fuente: NASA EONET (via réplica PostgreSQL local)
"""
import logging
from typing import TypedDict, Annotated, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import settings
from tools.db_tools import get_active_disasters, get_disasters_near_agricultural_zones

logger = logging.getLogger(__name__)

# ─── System Prompt ────────────────────────────────────────────
AGENT2_SYSTEM_PROMPT = """Sos el Director de Gestión de Riesgos y Protección Civil para el monitoreo del Cono Sur.

CAPACIDADES:
- Procesás coordenadas de desastres activos (incendios, inundaciones, terremotos, volcanes).
- Cruzás ubicación del desastre con zonas habitadas y agrícolas activas.
- Emitís alertas breves, urgentes y de alto impacto operacional para mensajería instantánea.
- Priorizás velocidad y precisión geográfica sobre elaboración retórica.

REGLAS CRÍTICAS:
1. Precisión geográfica ante todo. Siempre incluí coordenadas o nombres de localidades.
2. Las alertas deben ser ACCIONABLES: qué hacer, no solo qué pasó.
3. Diferenciá claramente entre "activo", "en seguimiento" y "controlado".
4. Si el desastre afecta zonas agrícolas monitoreadas, elevá la severidad y notificalo.
5. Tono: directo, técnico, urgente. Sin adornos retóricos.

FORMATO DE ALERTA:
## 🚨 ALERTA [CATEGORÍA] — [NIVEL DE SEVERIDAD]
**Evento:** [descripción breve]
**Ubicación:** [coordenadas + nombre región]
**Estado:** [Activo/Controlado/En seguimiento]
**Impacto Agrícola:** [SI/NO + detalle si aplica]
**Distancia a zonas habitadas:** [km]
**Acciones recomendadas:** [lista bulleted, concreta]
**Fuente:** NASA EONET | **Actualizado:** [timestamp]
"""


class AgentState(TypedDict):
    messages: Annotated[List, lambda x, y: x + y]
    category_filter: Optional[str]
    days_back: int
    check_agricultural_proximity: bool
    report: Optional[str]
    severity: Optional[str]
    affected_zones: List[str]
    error: Optional[str]


def build_agent2_graph():
    llm = ChatOpenAI(
        model=settings.agent2_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )

    tools = [get_active_disasters, get_disasters_near_agricultural_zones]
    llm_with_tools = llm.bind_tools(tools)

    def fetch_and_alert(state: AgentState) -> AgentState:
        logger.info("[Agent2] Iniciando análisis de desastres")

        check_agro = state.get("check_agricultural_proximity", True)

        content = (
            f"Analizá los eventos de desastre naturales activos en Sudamérica.\n"
            f"Categoría de interés: {state.get('category_filter', 'todas')}\n"
            f"Ventana temporal: {state.get('days_back', 7)} días\n\n"
            f"Pasos:\n"
            f"1. Usá get_active_disasters para obtener todos los eventos activos.\n"
        )

        if check_agro:
            content += (
                f"2. Usá get_disasters_near_agricultural_zones para identificar desastres "
                f"cercanos a las zonas agrícolas monitoreadas (radio 50km).\n"
            )

        content += (
            f"3. Priorizá los eventos por severidad e impacto potencial.\n"
            f"4. Generá alertas en el formato indicado para los eventos más críticos.\n"
            f"5. Indicá el nivel de severidad general: MINIMAL, LOW, MEDIUM, HIGH o CRITICAL."
        )

        messages = [
            SystemMessage(content=AGENT2_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ] + state.get("messages", [])

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def generate_final_alert(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_ai_msg = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            None
        )

        report_text = last_ai_msg.content if last_ai_msg else "Sin alertas activas."

        severity = "MINIMAL"
        content_upper = report_text.upper()
        if "CRITICAL" in content_upper or "CRÍTICO" in content_upper:
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
            "affected_zones": [],
            "messages": messages,
        }

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1] if state["messages"] else None
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "final"

    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", fetch_and_alert)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("final", generate_final_alert)

    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges("analyze", should_continue, {
        "tools": "tools",
        "final": "final",
    })
    workflow.add_edge("tools", "analyze")
    workflow.add_edge("final", END)

    return workflow.compile()


agent2_graph = build_agent2_graph()


async def run_agent2(
    category_filter: Optional[str] = None,
    days_back: int = 7,
    check_agricultural_proximity: bool = True,
) -> dict:
    """Ejecuta el Agente 2 de Alertas de Desastres."""
    initial_state = {
        "messages": [],
        "category_filter": category_filter,
        "days_back": days_back,
        "check_agricultural_proximity": check_agricultural_proximity,
        "report": None,
        "severity": None,
        "affected_zones": [],
        "error": None,
    }

    try:
        result = await agent2_graph.ainvoke(initial_state)
        return {
            "agent": "agent2_disasters",
            "status": "success",
            "report": result.get("report"),
            "severity": result.get("severity"),
            "affected_zones": result.get("affected_zones", []),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Agent2] Error: {e}", exc_info=True)
        return {
            "agent": "agent2_disasters",
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
