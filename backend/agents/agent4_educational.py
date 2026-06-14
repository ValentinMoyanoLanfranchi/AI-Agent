"""
agents/agent4_educational.py — Agente 4: Divulgación Turística / Educativa

Rol: Divulgador Científico internacional (estilo Carl Sagan + rigurosidad académica)
Mecánica: Adapta APOD según perfil demográfico. Notifica pasos ISS por coordenada.
APIs fuente: NASA APOD, Open Notify (via réplica PostgreSQL local)
"""
import logging
from typing import TypedDict, Annotated, List, Optional, Literal
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import settings
from tools.db_tools import get_today_apod, get_iss_passes

logger = logging.getLogger(__name__)

# Perfiles demográficos del Agente 4
DemographicProfile = Literal["NIÑO", "ESTUDIANTE", "EXPERTO", "GENERAL"]

PROFILE_INSTRUCTIONS = {
    "NIÑO": (
        "Explicá como si hablaras con un niño de 8 años. "
        "Usá analogías cotidianas (comparar distancias con canchas de fútbol, pesos con elefantes). "
        "Tono asombrado y lúdico. Frases cortas. Evitá tecnicismos."
    ),
    "ESTUDIANTE": (
        "Explicá para un estudiante secundario o universitario del primer año. "
        "Podés usar términos técnicos pero siempre explicándolos. "
        "Tono didáctico y entusiasta. Incluí datos numéricos pero contextualizados."
    ),
    "EXPERTO": (
        "Explicá para un astrofísico o investigador. "
        "Usá terminología técnica completa. Incluí valores numéricos exactos, magnitudes, coordenadas. "
        "Tono académico riguroso. Podés citar mecanismos físicos subyacentes."
    ),
    "GENERAL": (
        "Explicá para el público adulto general sin conocimientos científicos previos. "
        "Equilibrá accesibilidad con rigor. Usá metáforas cuando sea útil. "
        "Tono divulgativo al estilo Carl Sagan: maravilloso pero fundamentado."
    ),
}

AGENT4_SYSTEM_PROMPT = """Sos un Divulgador Científico Internacional de primer nivel, heredero del estilo de Carl Sagan combinado con la rigurosidad académica moderna.

CAPACIDADES:
- Explicás astrofísica compleja con metáforas accesibles y adaptadas al perfil del receptor.
- Curáis contenido científico diario (APOD) transformándolo en narrativas educativas memorables.
- Informás sobre el paso de la ISS sobre ciudades específicas, convirtiendo datos técnicos en experiencias.
- Adaptás tu lenguaje ESTRICTAMENTE al perfil demográfico indicado.

REGLAS CRÍTICAS:
1. Nunca sacrificás la precisión científica por la accesibilidad. Encontrás el equilibrio.
2. Las metáforas deben ser geográfica y culturalmente relevantes para Latinoamérica.
3. Si el APOD es un video, adaptá tu explicación en base al título y descripción.
4. Siempre incluís el crédito original del APOD.

FORMATO DE SALIDA:
## 🔭 ASTRONOMÍA DEL DÍA — [TÍTULO DEL APOD]
*[Fecha] | Fuente: [crédito]*

### ✨ La Imagen de Hoy
[Descripción accesible de lo que se ve]

### 🌌 ¿Por qué es fascinante?
[Narrativa adaptada al perfil — aquí es donde brilla la divulgación]

### 📐 Datos Clave
[3-5 datos numéricos contextualizados según perfil]

---
### 🛸 ISS HOY SOBRE TU CIUDAD
[Próximos pasos de la ISS sobre la localidad del usuario]

### 💡 ¿Cómo verla?
[Instrucciones prácticas]
"""


class AgentState(TypedDict):
    messages: Annotated[List, lambda x, y: x + y]
    demographic_profile: DemographicProfile
    user_location: Optional[str]
    user_latitude: Optional[float]
    user_longitude: Optional[float]
    report: Optional[str]
    error: Optional[str]


def build_agent4_graph():
    # Agente 4 corre sobre Azure AI Foundry; temperatura alta para divulgación creativa.
    from agents.azure_llm import get_agent_llm
    llm = get_agent_llm(temperature=0.4)
    logger.info("[Agent4] Usando Azure AI Foundry")

    tools = [get_today_apod, get_iss_passes]
    llm_with_tools = llm.bind_tools(tools)


    def fetch_and_narrate(state: AgentState) -> AgentState:
        logger.info(f"[Agent4] Generando contenido educativo para perfil: {state.get('demographic_profile', 'GENERAL')}")

        profile = state.get("demographic_profile", "GENERAL")
        profile_instruction = PROFILE_INSTRUCTIONS.get(profile, PROFILE_INSTRUCTIONS["GENERAL"])
        location = state.get("user_location", "Buenos Aires")

        messages = [
            SystemMessage(content=AGENT4_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Generá el contenido educativo del día.\n\n"
                    f"**Perfil del receptor:** {profile}\n"
                    f"**Instrucción de adaptación:** {profile_instruction}\n"
                    f"**Ubicación del usuario:** {location}\n\n"
                    f"Pasos:\n"
                    f"1. Usá get_today_apod para obtener la imagen astronómica del día.\n"
                    f"2. Usá get_iss_passes con location_name='{location}' para los próximos pasos de la ISS.\n"
                    f"3. Generá el contenido completo en el formato indicado, "
                    f"   adaptando ESTRICTAMENTE el lenguaje al perfil {profile}.\n"
                    f"4. Las metáforas deben ser relevantes para Argentina/Latinoamérica."
                )
            ),
        ] + state.get("messages", [])

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def generate_final_content(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_ai_msg = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and m.content),
            None
        )

        report_text = last_ai_msg.content if last_ai_msg else "No se pudo generar el contenido educativo."
        return {
            "report": report_text,
            "messages": messages,
        }

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1] if state["messages"] else None
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "final"

    workflow = StateGraph(AgentState)
    workflow.add_node("narrate", fetch_and_narrate)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("final", generate_final_content)

    workflow.set_entry_point("narrate")
    workflow.add_conditional_edges("narrate", should_continue, {
        "tools": "tools",
        "final": "final",
    })
    workflow.add_edge("tools", "narrate")
    workflow.add_edge("final", END)

    return workflow.compile()


# Lazy initialization — se construye en el primer uso
_agent4_graph = None


def _get_agent4_graph():
    global _agent4_graph
    if _agent4_graph is None:
        _agent4_graph = build_agent4_graph()
    return _agent4_graph


async def run_agent4(
    demographic_profile: DemographicProfile = "GENERAL",
    user_location: Optional[str] = "Buenos Aires",
    user_latitude: Optional[float] = -34.6037,
    user_longitude: Optional[float] = -58.3816,
) -> dict:
    """
    Ejecuta el Agente 4 de Divulgación Educativa.

    Args:
        demographic_profile: 'NIÑO', 'ESTUDIANTE', 'EXPERTO', o 'GENERAL'.
        user_location: Nombre de ciudad para pasos ISS.
        user_latitude: Latitud del usuario (para personalización).
        user_longitude: Longitud del usuario.
    """
    initial_state = {
        "messages": [],
        "demographic_profile": demographic_profile,
        "user_location": user_location,
        "user_latitude": user_latitude,
        "user_longitude": user_longitude,
        "report": None,
        "error": None,
    }

    try:
        result = await _get_agent4_graph().ainvoke(initial_state)
        return {
            "agent": "agent4_educational",
            "status": "success",
            "report": result.get("report"),
            "profile": demographic_profile,
            "location": user_location,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Agent4] Error: {e}", exc_info=True)
        return {
            "agent": "agent4_educational",
            "status": "error",
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
