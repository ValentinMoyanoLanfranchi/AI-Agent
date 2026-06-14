"""
agents/agent5_neows.py — Agente 5: Seguimiento de Objetos Cercanos a la Tierra (NeoWs)

Rol: Periodista de Datos Científicos
Mecánica: Filtra asteroides peligrosos. Traduce distancias técnicas a métricas comprensibles.
APIs fuente: NASA NeoWs (via réplica PostgreSQL local)
"""
import logging
from typing import TypedDict, Annotated, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import settings
from tools.db_tools import get_hazardous_asteroids

logger = logging.getLogger(__name__)

AGENT5_SYSTEM_PROMPT = """Sos un Periodista de Datos Científicos especializado en astrofísica y defensa planetaria.

CAPACIDADES:
- Filtrás y contextualizás datos de asteroides para consumo público.
- Desmitificás el amarillismo mediático con frialdad analítica y datos precisos.
- Traducís distancias técnicas a métricas intuitivas (distancias lunares, terrestres, etc.).
- Producís reportes claros tanto para la comunidad científica como para el público general.

REGLAS CRÍTICAS:
1. NUNCA induzcas pánico. El sensacionalismo no es periodismo científico.
2. Siempre contextualizás: "peligroso" en astronomía ≠ "peligroso" para el público (un asteroide a 12 distancias lunares no nos afecta).
3. Citá siempre las distancias humanizadas: "X veces la distancia Tierra-Luna".
4. Si no hay asteroides peligrosos próximos: dilo claramente y con datos que lo respalden.
5. Diferenciá entre asteroides "potencialmente peligrosos" (clasificación orbital) y "amenaza real" (impacto probable).

CONTEXTO CIENTÍFICO (para tus reportes):
- 1 Distancia Lunar (LD) = 384,400 km
- Asteroide potencialmente peligroso (PHA): diámetro > 140m Y distancia < 0.05 AU (≈19.5 LD)
- Un asteroide de 140m causaría daño regional severo. Uno de 1km, daño continental.
- La NASA monitorea el 95%+ de los PHA de 1km. Nada de ese tamaño tiene trayectoria de impacto conocida.

FORMATO:
## ☄️ REPORTE NEO — OBJETOS CERCANOS A LA TIERRA
*Período: [fechas] | Fuente: NASA NeoWs*

### 📊 Resumen Ejecutivo
[Cuántos NEO detectados en el período, cuántos son PHA]

### ⚠️ Asteroides Potencialmente Peligrosos Esta Semana
[Si los hay — con contexto tranquilizador si corresponde]

#### [Nombre del asteroide]
- **Clasificación:** PHA (Potencialmente Peligroso)
- **Diámetro estimado:** [min - max km]
- **Aproximación máxima:** [fecha]
- **Distancia mínima:** [humanizada] / [km exactos]
- **Velocidad relativa:** [km/s]
- **¿Riesgo de impacto?:** [NO — con explicación cuantificada]

### 🔭 El Asteroide Más Cercano Esta Semana
[Detalles del objeto que más se acerca, sea peligroso o no]

### 🧪 Contexto Científico
[Explicación de por qué estas distancias son seguras o no]
"""


class AgentState(TypedDict):
    messages: Annotated[List, lambda x, y: x + y]
    days_ahead: int
    report: Optional[str]
    hazardous_count: int
    max_risk_level: Optional[str]
    error: Optional[str]


def build_agent5_graph():
    from agents.azure_llm import get_agent_llm
    llm = get_agent_llm()

    tools = [get_hazardous_asteroids]
    llm_with_tools = llm.bind_tools(tools)

    def fetch_and_report(state: AgentState) -> AgentState:
        logger.info(f"[Agent5] Analizando asteroides para próximos {state.get('days_ahead', 7)} días")

        messages = [
            SystemMessage(content=AGENT5_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Generá el reporte de objetos cercanos a la Tierra.\n\n"
                    f"Ventana temporal: próximos {state.get('days_ahead', 7)} días.\n\n"
                    f"Pasos:\n"
                    f"1. Usá get_hazardous_asteroids para obtener los PHA próximos.\n"
                    f"2. Analizá todos los datos: hazardous_asteroids (solo peligrosos) y closest_all_types (todos los cercanos).\n"
                    f"3. Redactá el reporte completo en el formato indicado.\n"
                    f"4. Contextualizá SIEMPRE las distancias usando miss_distance_human.\n"
                    f"5. Usá frialdad analítica — ni alarmismo ni minimización.\n"
                    f"6. Determiná el nivel de riesgo: NONE, LOW, MEDIUM, HIGH (en la práctica será NONE o LOW casi siempre)."
                )
            ),
        ] + state.get("messages", [])

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def generate_final_report(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_ai_msg = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            None
        )

        report_text = last_ai_msg.content if last_ai_msg else "No hay datos de asteroides disponibles."

        # Detectar nivel de riesgo (en NeoWs casi siempre es NONE)
        content_upper = report_text.upper()
        max_risk = "NONE"
        if "HIGH" in content_upper:
            max_risk = "HIGH"
        elif "MEDIUM" in content_upper:
            max_risk = "MEDIUM"
        elif "LOW" in content_upper:
            max_risk = "LOW"

        return {
            "report": report_text,
            "max_risk_level": max_risk,
            "messages": messages,
        }

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1] if state["messages"] else None
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "final"

    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", fetch_and_report)
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


agent5_graph = build_agent5_graph()


async def run_agent5(days_ahead: int = 7) -> dict:
    """Ejecuta el Agente 5 de Seguimiento de Asteroides."""
    initial_state = {
        "messages": [],
        "days_ahead": days_ahead,
        "report": None,
        "hazardous_count": 0,
        "max_risk_level": None,
        "error": None,
    }

    try:
        result = await agent5_graph.ainvoke(initial_state)
        return {
            "agent": "agent5_neows",
            "status": "success",
            "report": result.get("report"),
            "max_risk_level": result.get("max_risk_level"),
            "days_ahead": days_ahead,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Agent5] Error: {e}", exc_info=True)
        return {
            "agent": "agent5_neows",
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
