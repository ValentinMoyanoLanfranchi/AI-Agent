"""
config.py — Configuración centralizada de la aplicación.
Lee variables de entorno vía pydantic-settings.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
import json


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    secret_key: str = "change-me-in-production"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ─── Database ─────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://hackaton:hackaton_pass@db:5432/hackaton_db"
    database_url_sync: str = "postgresql://hackaton:hackaton_pass@db:5432/hackaton_db"

    # ─── Redis & Celery ───────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

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
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Singleton de configuración — se cachea en memoria."""
    return Settings()


settings = get_settings()
