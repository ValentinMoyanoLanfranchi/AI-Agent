"""
api/routes_agents.py — Endpoints REST para invocar los agentes cognitivos.
"""
import logging
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field

from agents.graph import run_master_graph
from agents.agent1_agricultural import run_agent1
from agents.agent2_disasters import run_agent2
from agents.agent3_space_weather import run_agent3
from agents.agent4_educational import run_agent4
from agents.agent5_neows import run_agent5
from agents.foundry_consultant import run_consultant
from notifications.resend_client import send_alert_email, format_report_as_html
from notifications.slack_client import send_slack_alert
from database.session import AsyncSessionLocal
from database.models import AgentReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["Agentes Cognitivos"])


# ─── Schemas de request ───────────────────────────────────────

class RunAllRequest(BaseModel):
    days_back: int = Field(default=7, ge=1, le=90, description="Ventana de análisis en días")
    notify_email: bool = Field(default=False, description="Enviar reporte por email (Resend)")
    notify_slack: bool = Field(default=False, description="Enviar alerta a Slack")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"days_back": 7, "notify_email": False, "notify_slack": True}
        }
    )


class RunAgriculturalRequest(BaseModel):
    region_code: Optional[str] = Field(default=None, description="Código de zona agrícola; None = todas")
    days_back: int = Field(default=7, ge=1, le=90, description="Ventana de análisis en días")
    notify_email: bool = Field(default=False, description="Enviar reporte por email si severidad HIGH/CRITICAL")
    notify_slack: bool = Field(default=False, description="Enviar alerta a Slack")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"region_code": "PAMPA-01", "days_back": 7,
                        "notify_email": False, "notify_slack": False}
        }
    )


class RunDisastersRequest(BaseModel):
    category_filter: Optional[str] = Field(default=None, description="Categoría EONET (wildfires, severeStorms, ...)")
    days_back: int = Field(default=7, ge=1, le=30, description="Ventana de análisis en días")
    check_agricultural_proximity: bool = Field(default=True, description="Cruzar con zonas agrícolas vía PostGIS")
    notify_email: bool = Field(default=False, description="Enviar reporte por email")
    notify_slack: bool = Field(default=False, description="Enviar alerta a Slack")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"category_filter": "wildfires", "days_back": 7,
                        "check_agricultural_proximity": True,
                        "notify_email": False, "notify_slack": True}
        }
    )


class RunEducationalRequest(BaseModel):
    demographic_profile: Literal["NIÑO", "ESTUDIANTE", "EXPERTO", "GENERAL"] = Field(
        default="GENERAL", description="Perfil al que se adapta el contenido")
    user_location: str = Field(default="Buenos Aires", description="Localidad del usuario")
    user_latitude: Optional[float] = Field(default=-34.6037, description="Latitud para pasos ISS")
    user_longitude: Optional[float] = Field(default=-58.3816, description="Longitud para pasos ISS")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"demographic_profile": "ESTUDIANTE", "user_location": "Córdoba",
                        "user_latitude": -31.4201, "user_longitude": -64.1888}
        }
    )


class RunNeoWsRequest(BaseModel):
    days_ahead: int = Field(default=7, ge=1, le=30, description="Días hacia adelante a analizar")
    notify_email: bool = Field(default=False, description="Enviar reporte por email")

    model_config = ConfigDict(
        json_schema_extra={"example": {"days_ahead": 7, "notify_email": False}}
    )


# ─── Schemas de respuesta ─────────────────────────────────────

class AgentRunResponse(BaseModel):
    """Reporte generado por un agente. Acepta campos extra según el agente."""
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "agent": "agent3_space_weather",
                "status": "success",
                "severity": "HIGH",
                "report": "Se detectó tormenta geomagnética Kp=6...",
                "generated_at": "2026-06-13T19:39:25.139812",
            }
        },
    )
    agent: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    report: Optional[str] = None
    generated_at: Optional[str] = None


class SystemStatusResponse(BaseModel):
    status: str = Field(examples=["online"])
    agents: dict = Field(examples=[{"agent1_agricultural": "ready"}])
    timestamp: str = Field(examples=["2026-06-13T19:35:23.919425"])


class ReportItem(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    report_type: Optional[str] = None
    summary: Optional[str] = None
    severity: Optional[str] = None
    created_at: Optional[str] = None


class ReportsResponse(BaseModel):
    total: int = Field(examples=[2])
    reports: list[ReportItem]


class ConsultRequest(BaseModel):
    """Pregunta en lenguaje natural para el Agente Consultor (Foundry + Foundry IQ)."""
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=15)


# ─── Helper: guardar reporte en DB ────────────────────────────

async def save_agent_report(
    agent_id: int,
    agent_name: str,
    report_type: str,
    result: dict,
) -> None:
    """Persiste el reporte generado en la base de datos."""
    try:
        async with AsyncSessionLocal() as db:
            record = AgentReport(
                agent_id=agent_id,
                agent_name=agent_name,
                report_type=report_type,
                summary=result.get("report", "")[:500] if result.get("report") else "",
                full_report=result.get("report"),
                severity=result.get("severity") or result.get("max_risk_level"),
                llm_model_used=f"agent{agent_id}",
                created_at=datetime.utcnow(),
            )
            db.add(record)
            await db.commit()
    except Exception as e:
        logger.warning(f"[API] No se pudo persistir reporte del Agente {agent_id}: {e}")


# ─────────────────────────────────────────────────────────────
# GET /api/agents/status — Estado del sistema
# ─────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="Estado del sistema de agentes",
    response_description="Estado online y readiness de cada agente",
    response_model=SystemStatusResponse,
)
async def get_system_status():
    """Retorna el estado general del sistema de agentes."""
    return {
        "status": "online",
        "agents": {
            "agent1_agricultural": "ready",
            "agent2_disasters": "ready",
            "agent3_space_weather": "ready",
            "agent4_educational": "ready",
            "agent5_neows": "ready",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# POST /api/agents/run-all — Pipeline completo
# ─────────────────────────────────────────────────────────────

@router.post(
    "/run-all",
    summary="Ejecutar pipeline completo (5 agentes)",
    response_description="Resultado consolidado del pipeline multiagente",
    response_model=AgentRunResponse,
)
async def run_all_agents(
    request: RunAllRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ejecuta el pipeline completo de todos los agentes.
    Retorna resultados en tiempo real y opcionalmente notifica.
    """
    logger.info("[API] Ejecutando pipeline completo de agentes")

    result = await run_master_graph(
        agent_name="all",
        agent_params={"days_back": request.days_back},
    )

    # Notificaciones en background
    if request.notify_slack and result.get("status") == "success":
        background_tasks.add_task(
            send_slack_alert,
            agent_name="Sistema Multi-Agente",
            title=f"Pipeline Completo Ejecutado — Severidad Global: {result.get('global_severity')}",
            report_summary=f"Todos los agentes ejecutados exitosamente. Severidad: {result.get('global_severity')}",
            severity=result.get("global_severity", "INFO"),
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/agricultural — Agente 1
# ─────────────────────────────────────────────────────────────

@router.post(
    "/agricultural",
    summary="Agente 1 — Monitoreo Agrícola (NDVI)",
    response_description="Reporte de anomalías NDVI y severidad",
    response_model=AgentRunResponse,
)
async def run_agricultural_agent(
    request: RunAgriculturalRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ejecuta el Agente 1 de Monitoreo Agrícola.
    Analiza NDVI, detecta anomalías y consulta alertas GPS del Agente de Clima Espacial.
    """
    result = await run_agent1(
        region_code=request.region_code,
        days_back=request.days_back,
    )

    # Persistir reporte
    background_tasks.add_task(save_agent_report, 1, "agent1_agricultural", "monitoring", result)

    # Notificaciones si severidad alta
    severity = result.get("severity", "MINIMAL")
    if request.notify_email and severity in ["HIGH", "CRITICAL"]:
        html = format_report_as_html(
            "Agente 1: Monitoreo Agrícola",
            result.get("report", ""),
            severity,
            result.get("generated_at", ""),
        )
        background_tasks.add_task(
            send_alert_email,
            f"Alerta Agrícola: {severity}",
            html,
            severity=severity,
        )

    if request.notify_slack:
        background_tasks.add_task(
            send_slack_alert,
            "🌱 Agente 1: Monitoreo Agrícola",
            f"Reporte Agrícola — Zona: {request.region_code or 'Todas'}",
            result.get("report", "")[:300],
            severity=severity,
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/disasters — Agente 2
# ─────────────────────────────────────────────────────────────

@router.post(
    "/disasters",
    summary="Agente 2 — Alertas de Desastres (EONET + PostGIS)",
    response_description="Reporte de eventos y proximidad a zonas agrícolas",
    response_model=AgentRunResponse,
)
async def run_disasters_agent(
    request: RunDisastersRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ejecuta el Agente 2 de Alertas de Desastres.
    Cruza eventos EONET con zonas agrícolas vía PostGIS.
    """
    result = await run_agent2(
        category_filter=request.category_filter,
        days_back=request.days_back,
        check_agricultural_proximity=request.check_agricultural_proximity,
    )

    background_tasks.add_task(save_agent_report, 2, "agent2_disasters", "alert", result)

    severity = result.get("severity", "MINIMAL")
    if request.notify_slack and severity in ["MEDIUM", "HIGH", "CRITICAL"]:
        background_tasks.add_task(
            send_slack_alert,
            "🌪️ Agente 2: Desastres Naturales",
            f"Alerta de Desastre — {severity}",
            result.get("report", "")[:300],
            severity=severity,
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/space-weather — Agente 3
# ─────────────────────────────────────────────────────────────

@router.post(
    "/space-weather",
    summary="Agente 3 — Clima Espacial (DONKI / Kp index)",
    response_description="Reporte de actividad geomagnética y alertas inter-agente",
    response_model=AgentRunResponse,
)
async def run_space_weather_agent(
    days_back: int = Query(default=3, ge=1, le=14, description="Ventana de análisis en días"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Ejecuta el Agente 3 de Clima Espacial.
    Monitorea Kp index y genera alertas inter-agente automáticas si supera umbral.
    """
    result = await run_agent3(days_back=days_back)

    background_tasks.add_task(save_agent_report, 3, "agent3_space_weather", "monitoring", result)

    # Si hay alerta GPS enviada al Agente 1, notificar Slack
    if result.get("alert_sent_to_agent1"):
        background_tasks.add_task(
            send_slack_alert,
            "☀️⚠️ Agente 3: Alerta GPS Inter-Agente",
            f"Tormenta Geomagnética Kp={result.get('kp_max')} — Alerta enviada a Agente Agrícola",
            result.get("report", "")[:300],
            severity=result.get("severity", "HIGH"),
        )

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/educational — Agente 4
# ─────────────────────────────────────────────────────────────

@router.post(
    "/educational",
    summary="Agente 4 — Divulgación Educativa (APOD + ISS)",
    response_description="Contenido educativo adaptado al perfil y pasos ISS",
    response_model=AgentRunResponse,
)
async def run_educational_agent(
    request: RunEducationalRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ejecuta el Agente 4 Educativo.
    Adapta APOD al perfil demográfico del usuario e informa pasos ISS.
    """
    result = await run_agent4(
        demographic_profile=request.demographic_profile,
        user_location=request.user_location,
        user_latitude=request.user_latitude,
        user_longitude=request.user_longitude,
    )

    background_tasks.add_task(save_agent_report, 4, "agent4_educational", "educational", result)

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/neows — Agente 5
# ─────────────────────────────────────────────────────────────

@router.post(
    "/neows",
    summary="Agente 5 — Seguimiento de Asteroides (NeoWs)",
    response_description="Reporte de objetos cercanos (PHA) y contexto de distancias",
    response_model=AgentRunResponse,
)
async def run_neows_agent(
    request: RunNeoWsRequest,
    background_tasks: BackgroundTasks,
):
    """
    Ejecuta el Agente 5 de Seguimiento de Asteroides NeoWs.
    Filtra PHA y contextualiza distancias sin alarmismo.
    """
    result = await run_agent5(days_ahead=request.days_ahead)

    background_tasks.add_task(save_agent_report, 5, "agent5_neows", "monitoring", result)

    return result


# ─────────────────────────────────────────────────────────────
# POST /api/agents/consult — Agente Consultor (Microsoft Foundry + Foundry IQ)
# ─────────────────────────────────────────────────────────────

@router.post("/consult")
async def consult_agent(
    request: ConsultRequest,
    background_tasks: BackgroundTasks,
):
    """
    Agente Consultor — Track Reasoning Agents (Microsoft Foundry) + Foundry IQ.

    Responde preguntas en lenguaje natural sobre el estado del sistema con respuestas
    GROUNDED y CITADAS recuperadas del knowledge base de Foundry IQ (anti-alucinación).

    Razonamiento multi-paso: retrieve (Foundry IQ) → reason (Foundry) → grounded answer.
    """
    result = await run_consultant(question=request.question, top_k=request.top_k)

    # Persistir la consulta como reporte del "agente 6"
    background_tasks.add_task(save_agent_report, 6, "agent6_consultant", "consult", {
        "report": result.get("answer", ""),
        "severity": "INFO",
    })

    return result


# ─────────────────────────────────────────────────────────────
# GET /api/agents/reports — Historial de reportes
# ─────────────────────────────────────────────────────────────

@router.get(
    "/reports",
    summary="Historial de reportes",
    response_description="Lista paginada de reportes generados por los agentes",
    response_model=ReportsResponse,
)
async def get_agent_reports(
    agent_id: Optional[int] = Query(default=None, ge=1, le=5, description="Filtrar por ID de agente (1-5)"),
    severity: Optional[str] = Query(default=None, description="Filtrar por severidad (MINIMAL/LOW/MEDIUM/HIGH/CRITICAL)"),
    limit: int = Query(default=20, ge=1, le=100, description="Máximo de resultados"),
):
    """Retorna el historial de reportes generados por los agentes."""
    from sqlalchemy import desc, select
    from database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from database.models import AgentReport

        query = select(AgentReport).order_by(desc(AgentReport.created_at)).limit(limit)
        if agent_id:
            query = query.where(AgentReport.agent_id == agent_id)
        if severity:
            query = query.where(AgentReport.severity == severity.upper())

        result = await db.execute(query)
        reports = result.scalars().all()

        return {
            "total": len(reports),
            "reports": [
                {
                    "id": r.id,
                    "agent_id": r.agent_id,
                    "agent_name": r.agent_name,
                    "report_type": r.report_type,
                    "summary": r.summary,
                    "severity": r.severity,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reports
            ],
        }
