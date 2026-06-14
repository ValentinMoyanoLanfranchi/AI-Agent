"""
agents/foundry_consultant.py — Agente Consultor (Microsoft Foundry + Foundry IQ)

Track del hackathon: 🧠 Reasoning Agents (Microsoft Foundry).
Capa IQ obligatoria: 💡 Foundry IQ (recuperación grounded + citas).

Rol: Analista del sistema que responde preguntas en lenguaje natural sobre el estado
operacional (agrícola, desastres, clima espacial, asteroides) con respuestas GROUNDED
y CITADAS provenientes del knowledge base de Foundry IQ.

Razonamiento multi-paso:
  1. RETRIEVE  → recupera contexto citado desde Foundry IQ.
  2. REASON    → razona sobre el contexto con el modelo desplegado en Azure AI Foundry.
  3. GROUND    → devuelve respuesta + citas verificables (anti-alucinación).

Degradación automática: si Azure AI Foundry no está configurado, sintetiza una
respuesta grounded a partir de las fuentes recuperadas (modo fallback) para que el
sistema corra sin credenciales.
"""
import logging
from datetime import datetime
from typing import Tuple

from config import settings
from agents.foundry_iq import retrieve_grounded, GroundedContext

logger = logging.getLogger(__name__)

CONSULTANT_SYSTEM_PROMPT = """Sos el Agente Consultor del Sistema de Agentes IA de monitoreo espacial y agrícola del Cono Sur.

Tu función es responder preguntas operacionales del equipo basándote ESTRICTAMENTE en el
conocimiento recuperado del knowledge base de Foundry IQ (reportes de los 5 agentes:
agrícola, desastres, clima espacial, divulgación y asteroides).

REGLAS CRÍTICAS (anti-alucinación):
1. Respondé SOLO con información presente en el CONTEXTO provisto. No inventes datos.
2. Citá siempre tus fuentes al final usando el formato [Fuente: <agente> / <fecha>].
3. Si el contexto no alcanza para responder, decilo explícitamente: "No tengo datos
   suficientes en el knowledge base para responder eso con certeza."
4. Citá valores numéricos exactos (NDVI, índice Kp, distancias lunares) tal como aparecen.
5. Tono técnico-ejecutivo, claro y directo. Sin alarmismo.

FORMATO:
- Respuesta directa primero (2-4 frases).
- Detalle/datos de respaldo si corresponde.
- Sección final "Fuentes:" con las citas usadas.
"""


def _build_user_prompt(question: str, grounded: GroundedContext) -> str:
    return (
        f"PREGUNTA DEL USUARIO:\n{question}\n\n"
        f"CONTEXTO RECUPERADO DEL KNOWLEDGE BASE (Foundry IQ):\n"
        f"{grounded.context_text or '(sin resultados)'}\n\n"
        f"Respondé la pregunta usando exclusivamente el contexto anterior y citá las fuentes."
    )


def _build_chat_messages(question: str, grounded: GroundedContext, history) -> list:
    """Arma la lista de mensajes: system + historial de la conversación + turno actual."""
    messages = [{"role": "system", "content": CONSULTANT_SYSTEM_PROMPT}]
    for h in (history or []):
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": _build_user_prompt(question, grounded)})
    return messages


def _synthesize_with_foundry(question: str, grounded: GroundedContext, history=None) -> str:
    """REASON: razona sobre el contexto con el modelo desplegado en Azure AI Foundry.

    Usa el cliente AzureOpenAI contra el data-plane del proyecto Foundry (autenticación
    por API key, la más confiable). Reintenta sin `temperature` para modelos que solo
    aceptan el valor por defecto (familia gpt-5 y modelos de razonamiento).
    """
    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_ai_foundry_api_key,
        api_version=settings.azure_ai_foundry_api_version,
    )
    messages = _build_chat_messages(question, grounded, history)
    kwargs = {"model": settings.azure_ai_foundry_model_deployment, "messages": messages}
    try:
        response = client.chat.completions.create(temperature=settings.llm_temperature, **kwargs)
    except Exception as e:
        logger.info(f"[Consultor] Reintento sin temperature ({e}).")
        response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _synthesize_fallback(question: str, grounded: GroundedContext) -> str:
    """Síntesis determinista a partir de las fuentes (sin LLM) — siempre grounded y citada."""
    if not grounded.is_grounded:
        return (
            "No tengo datos suficientes en el knowledge base para responder eso con certeza. "
            "Ejecutá los agentes (POST /api/agents/run-all) para poblar el conocimiento."
        )

    lines = [
        "**Respuesta (modo grounded local — Azure AI Foundry no configurado todavía):**",
        "",
        "Según los reportes más relevantes del knowledge base para tu consulta:",
        "",
    ]
    for c in grounded.citations:
        lines.append(f"- **{c.title}** — {c.snippet}")
    lines.append("")
    lines.append("**Fuentes:**")
    for c in grounded.citations:
        lines.append(f"  - [Fuente: {c.source}]")
    return "\n".join(lines)


def _synthesize(question: str, grounded: GroundedContext, history=None) -> Tuple[str, str, str]:
    """Devuelve (respuesta, modelo_usado, modo_razonamiento)."""
    if settings.foundry_enabled:
        try:
            answer = _synthesize_with_foundry(question, grounded, history)
            return answer, settings.azure_ai_foundry_model_deployment, "azure_ai_foundry"
        except Exception as e:
            logger.warning(f"[Consultor] Foundry falló, uso síntesis fallback: {e}")
    return _synthesize_fallback(question, grounded), "fallback-template", "fallback"


async def run_consultant(question: str, top_k: int = 5, history=None) -> dict:
    """
    Ejecuta el Agente Consultor: retrieve (Foundry IQ) → reason (Foundry) → grounded answer.

    Args:
        question: Pregunta en lenguaje natural del usuario.
        top_k: Cantidad de fuentes a recuperar del knowledge base.

    Returns:
        Dict con respuesta, citas verificables y metadata de la capa IQ usada.
    """
    try:
        # 1. RETRIEVE — Foundry IQ
        grounded = retrieve_grounded(question, top_k=top_k)
        # 2 + 3. REASON + GROUND
        answer, model_used, reasoning_mode = _synthesize(question, grounded, history)

        return {
            "agent": "agent6_consultant",
            "status": "success",
            "question": question,
            "answer": answer,
            "grounded": grounded.is_grounded,
            "citations": [c.to_dict() for c in grounded.citations],
            "retrieval_mode": grounded.mode,      # foundry_iq | fallback_postgres | demo
            "reasoning_mode": reasoning_mode,     # azure_ai_foundry | fallback
            "model_used": model_used,
            "iq_layer": "Foundry IQ",
            "track": "Reasoning Agents",
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[Consultor] Error: {e}", exc_info=True)
        return {
            "agent": "agent6_consultant",
            "status": "error",
            "question": question,
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
        }
