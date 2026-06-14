"""
agents/azure_llm.py — Fábrica del LLM de los agentes sobre Azure AI Foundry.

Unifica los 5 agentes cognitivos en el modelo desplegado en Azure AI Foundry
(deployment de chat con tool-calling), eliminando la dependencia de claves
externas de OpenAI/Anthropic. Todo el sistema corre en Microsoft Foundry.
"""
from typing import Optional

from langchain_openai import AzureChatOpenAI

from config import settings


def get_agent_llm(temperature: Optional[float] = None) -> AzureChatOpenAI:
    """ChatModel de Azure AI Foundry para los agentes (soporta tool-calling)."""
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_ai_foundry_api_key,
        azure_deployment=settings.azure_ai_foundry_agents_deployment,
        api_version=settings.azure_ai_foundry_api_version,
        temperature=settings.llm_temperature if temperature is None else temperature,
    )
