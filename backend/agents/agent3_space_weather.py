"""
agents/agent3_space_weather.py — Agente 3: Análisis de Clima Espacial

Rol: Astrofísico Especialista en Telecomunicaciones e Infraestructura
Mecánica: Monitorea CME/GST/FLR. Si Kp supera umbral → genera alerta inter-agente autónoma al Agente 1.
APIs fuente: NASA DONKI (via réplica PostgreSQL local)
"""
import logging
from typing import TypedDict, Annotated, List, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from config import settings
from tools.db_tools import get_space_weather_events
from database.session import SyncSessionLocal
from database.models import InterAgentAlert, AgentReport

logger = logging.getLogger(__name__)

AGENT3_SYSTEM_PROMPT = """Sos un Astrofísico Especialista en Telecomunicaciones e Infraestructura Crítica Terrestre.

CAPACIDADES:
- Monitoreás viento solar, fulguraciones (FLR), eyecciones de masa coronal (CME) y tormentas geomagnéticas (GST).
- Traducís eventos DONKI en riesgos pragmáticos para: aviación, redes eléctricas y agricultura satelital.
- Cuando el índice Kp supera {kp_threshold}, emitís un mensaje inter-agente autónomo al Agente Agrícola.
- Contextualizás el riesgo para audiencias técnicas y ejecutivas.

MÉTRICAS CLAVE:
- Índice Kp < 4: Condiciones tranquilas. Sin impacto operacional.
- Índice Kp 4-5: Perturbaciones menores. GPS con precisión reducida.
- Índice Kp 5-6: Tormenta menor. Posible interferencia HF en latitudes altas.
- Índice Kp 6-7: Tormenta moderada. Alertas para aviación y redes eléctricas.
- Índice Kp 7-9: Tormenta severa/extrema. Impacto sistémico en infraestructura crítica.

REGLAS CRÍTICAS:
1. Siempre citá el valor exacto del índice Kp.
2. Traducí velocidades de CME (km/s) a tiempo de arribo estimado.
3. No generes pánico. Basate en umbrales operacionales reales.
4. Indicá explícitamente si hay riesgo para GPS de maquinaria agrícola autónoma.

FORMATO:
## ☀️ REPORTE CLIMA ESPACIAL — [FECHA]

### Índice de Actividad Solar Actual
[Kp actual + clasificación]

### Eventos Detectados (últimas 72h)
[Lista de CME/GST/FLR con parámetros]

### Impactos por Sector
- **Aviación:** [...]
- **Redes Eléctricas:** [...]
- **GPS / Agricultura Autónoma:** [...]

### Alerta Inter-Agente
[SI hay Kp > umbral: describe el mensaje enviado al Agente Agrícola]

### Pronóstico 24-48h
[Basado en eventos en tránsito]
"""


class AgentState(TypedDict):
    messages: Annotated[List, lambda x, y: x + y]
    days_back: int
    report: Optional[str]
    severity: Optional[str]
    kp_max: float
    alert_sent_to_agent1: bool
    error: Optional[str]


def build_agent3_graph():
    llm = ChatOpenAI(
        model=settings.agent3_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
    )

    tools = [get_space_weather_events]
    llm_with_tools = llm.bind_tools(tools)

    def fetch_and_analyze(state: AgentState) -> AgentState:
        logger.info("[Agent3] Iniciando análisis de clima espacial")

        system_prompt = AGENT3_SYSTEM_PROMPT.format(
            kp_threshold=settings.kp_index_threshold
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Analizá el clima espacial de las últimas {state.get('days_back', 7) * 24} horas.\n\n"
                    f"Pasos:\n"
                    f"1. Usá get_space_weather_events con event_type='GST' para tormentas geomagnéticas.\n"
                    f"2. Usá get_space_weather_events con event_type='CME' para eyecciones coronales.\n"
                    f"3. Usá get_space_weather_events con event_type='FLR' para fulguraciones.\n"
                    f"4. Identificá el Kp máximo actual y si supera el umbral {settings.kp_index_threshold}.\n"
                    f"5. Redactá el reporte completo en el formato indicado.\n"
                    f"6. Si Kp > {settings.kp_index_threshold}, indicalo claramente en la sección 'Alerta Inter-Agente'.\n"
                    f"7. Determiná severidad: MINIMAL, LOW, MEDIUM, HIGH o CRITICAL."
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

        report_text = last_ai_msg.content if last_ai_msg else "Sin datos de clima espacial disponibles."

        # Detectar severidad
        severity = "MINIMAL"
        kp_max = 0.0
        alert_sent = False

        content_upper = report_text.upper()
        if "CRITICAL" in content_upper:
            severity = "CRITICAL"
            kp_max = 8.0
        elif "HIGH" in content_upper or "SEVERA" in content_upper:
            severity = "HIGH"
            kp_max = 6.5
        elif "MEDIUM" in content_upper or "MODERADA" in content_upper:
            severity = "MEDIUM"
            kp_max = 5.5
        elif "LOW" in content_upper:
            severity = "LOW"
            kp_max = 4.5

        # Verificar si se envió alerta inter-agente (detectar en el texto)
        if "ALERTA INTER-AGENTE" in content_upper or "GPS" in content_upper and kp_max >= settings.kp_index_threshold:
            alert_sent = True

        return {
            "report": report_text,
            "severity": severity,
            "kp_max": kp_max,
            "alert_sent_to_agent1": alert_sent,
            "messages": messages,
        }

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1] if state["messages"] else None
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "final"

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


agent3_graph = build_agent3_graph()


async def run_agent3(days_back: int = 3) -> dict:
    """Ejecuta el Agente 3 de Clima Espacial."""
    initial_state = {
        "messages": [],
        "days_back": days_back,
        "report": None,
        "severity": None,
        "kp_max": 0.0,
        "alert_sent_to_agent1": False,
        "error": None,
    }

    try:
        result = await agent3_graph.ainvoke(initial_state)
        return {
            "agent": "agent3_space_weather",
            "status": "success",
            "report": result.get("report"),
            "severity": result.get("severity"),
            "kp_max": result.get("kp_max"),
            "alert_sent_to_agent1": result.get("alert_sent_to_agent1", False),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Agent3] Error: {e}", exc_info=True)
        return {
            "agent": "agent3_space_weather",
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
