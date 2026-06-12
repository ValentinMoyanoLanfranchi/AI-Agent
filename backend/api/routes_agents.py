"""
api/routes_agents.py — Endpoints REST para invocar los agentes cognitivos.
"""
import logging
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from agents.graph import run_master_graph
from agents.agent1_agricultural import run_agent1
from agents.agent2_disasters import run_agent2
from agents.agent3_space_weather import run_agent3
from agents.agent4_educational import run_agent4
from agents.agent5_neows import run_agent5
from notifications.resend_client import send_alert_email, format_report_as_html
from notifications.slack_client import send_slack_alert
from database.session import AsyncSessionLocal
from database.models import AgentReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["Agentes Cognitivos"])


# ─── Schemas ──────────────────────────────────────────────────

class RunAllRequest(BaseModel):
    days_back: int = Field(default=7, ge=1, le=90)
    notify_email: bool = False
    notify_slack: bool = False


class RunAgriculturalRequest(BaseModel):
    region_code: Optional[str] = None
    days_back: int = Field(default=7, ge=1, le=90)
    notify_email: bool = False
    notify_slack: bool = False


class RunDisastersRequest(BaseModel):
    category_filter: Optional[str] = None
    days_back: int = Field(default=7, ge=1, le=30)
    check_agricultural_proximity: bool = True
    notify_email: bool = False
    notify_slack: bool = False


class RunEducationalRequest(BaseModel):
    demographic_profile: Literal["NIÑO", "ESTUDIANTE", "EXPERTO", "GENERAL"] = "GENERAL"
    user_location: str = "Buenos Aires"
    user_latitude: Optional[float] = -34.6037
    user_longitude: Optional[float] = -58.3816


class RunNeoWsRequest(BaseModel):
    days_ahead: int = Field(default=7, ge=1, le=30)
    notify_email: bool = False


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

@router.get("/status")
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

@router.post("/run-all")
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

@router.post("/agricultural")
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

@router.post("/disasters")
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

@router.post("/space-weather")
async def run_space_weather_agent(
    days_back: int = Query(default=3, ge=1, le=14),
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

@router.post("/educational")
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

@router.post("/neows")
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
# GET /api/agents/reports — Historial de reportes
# ─────────────────────────────────────────────────────────────

@router.get("/reports")
async def get_agent_reports(
    agent_id: Optional[int] = Query(default=None, ge=1, le=5),
    severity: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
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
