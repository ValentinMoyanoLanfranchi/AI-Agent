"""
config.py — Configuración centralizada de la aplicación.
Lee variables de entorno vía pydantic-settings.
"""
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
import json

# .env vive en la raíz del repo (un nivel arriba de backend/).
# Resolvemos su ruta absoluta para que funcione sin importar el CWD.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "change-me-in-production"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ─── Database ─────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://hackaton:hackaton_pass@db:5432/hackaton_db"
    database_url_sync: str = "postgresql://hackaton:hackaton_pass@db:5432/hackaton_db"

    # ─── Supabase (cliente REST opcional; la migración usa database_url) ──
    supabase_url: str = ""
    supabase_key: str = ""

    # ─── Redis & Celery ───────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    # Modo eager: ejecuta las tareas inline (sin broker/worker Redis).
    # True para correr local sin Redis; False en producción con worker.
    celery_always_eager: bool = False

    # ─── NASA APIs ────────────────────────────────────────────
    nasa_api_key: str = "DEMO_KEY"
    nasa_earthdata_user: str = ""
    nasa_earthdata_password: str = ""

    # ─── LLM Providers ────────────────────────────────────────
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_llm_model: str = "gpt-4o"
    agent1_model: str = "gpt-4o"
    agent2_model: str = "gpt-4o"
    agent3_model: str = "gpt-4o"
    agent4_model: str = "claude-3-5-sonnet-20241022"
    agent5_model: str = "gpt-4o"
    llm_temperature: float = 0.1

    # ─── Notificaciones ───────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "alerts@localhost"
    resend_to_email: str = "team@localhost"
    slack_webhook_url: str = ""

    # ─── Umbrales de alertas ──────────────────────────────────
    kp_index_threshold: float = 5.0
    ndvi_anomaly_threshold: float = -0.15
    disaster_proximity_km: float = 50.0

    # ─── Microsoft Azure AI Foundry (Agents League Hackathon) ─
    # Proyecto de Azure AI Foundry — hostea el Agente Consultor (track Reasoning).
    azure_ai_foundry_project_endpoint: str = ""   # https://<recurso>.services.ai.azure.com/api/projects/<proyecto>
    azure_openai_endpoint: str = ""                # https://<recurso>.openai.azure.com/  (data-plane del modelo)
    azure_ai_foundry_api_key: str = ""             # key de la cuenta de Foundry
    azure_ai_foundry_model_deployment: str = "razonador"  # deployment del Consultor (razonador)
    azure_ai_foundry_agents_deployment: str = "agentes"   # deployment chat con tools para los 5 agentes
    azure_ai_foundry_api_version: str = "2025-04-01-preview"  # >= 2024-12-01-preview para modelos o-series

    # ─── Foundry IQ — capa de conocimiento (IQ obligatorio) ───
    # Knowledge base de Foundry IQ que da respuestas citadas/grounded.
    foundry_iq_knowledge_base: str = ""
    # Store que respalda el knowledge base (Azure AI Search).
    azure_search_endpoint: str = ""                # https://<search>.search.windows.net
    azure_search_api_key: str = ""
    azure_search_index_name: str = "reportes-agentes"

    @property
    def foundry_enabled(self) -> bool:
        """True si el modelo de Azure AI Foundry está configurado (modo real vs fallback)."""
        return bool(self.azure_openai_endpoint and self.azure_ai_foundry_api_key
                    and self.azure_ai_foundry_model_deployment)

    @property
    def foundry_iq_search_enabled(self) -> bool:
        """True si el knowledge base está respaldado por Azure AI Search."""
        return bool(self.azure_search_endpoint and self.azure_search_api_key)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Singleton de configuración — se cachea en memoria."""
    return Settings()


settings = get_settings()
