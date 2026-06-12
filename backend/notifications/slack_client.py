"""
notifications/slack_client.py — Cliente de Slack via Webhooks.
"""
import logging
from typing import Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)

# Colores Slack por severidad
SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#ea580c",
    "MEDIUM": "#d97706",
    "LOW": "#2563eb",
    "MINIMAL": "#16a34a",
    "NONE": "#6b7280",
    "INFO": "#0ea5e9",
}

SEVERITY_EMOJIS = {
    "CRITICAL": "🚨",
    "HIGH": "⚠️",
    "MEDIUM": "⚡",
    "LOW": "ℹ️",
    "MINIMAL": "✅",
    "NONE": "✅",
    "INFO": "📊",
}


async def send_slack_alert(
    agent_name: str,
    title: str,
    report_summary: str,
    severity: str = "INFO",
    webhook_url: Optional[str] = None,
) -> dict:
    """
    Envía alerta a canal Slack vía Webhook.

    Args:
        agent_name: Nombre del agente que genera la alerta.
        title: Título del mensaje.
        report_summary: Resumen del reporte (máx 500 chars recomendado).
        severity: Nivel de severidad.
        webhook_url: Override del webhook URL. None usa config default.
    """
    url = webhook_url or settings.slack_webhook_url

    if not url or url == "https://hooks.slack.com/services/YOUR/WEBHOOK/URL":
        logger.warning("[Slack] Webhook URL no configurado. Mensaje no enviado.")
        return {"status": "skipped", "reason": "webhook_not_configured"}

    color = SEVERITY_COLORS.get(severity.upper(), "#6b7280")
    emoji = SEVERITY_EMOJIS.get(severity.upper(), "📊")

    # Truncar resumen si es muy largo
    summary = report_summary[:500] + "..." if len(report_summary) > 500 else report_summary

    payload = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {title}",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Agente:*\n{agent_name}"},
                            {"type": "mrkdwn", "text": f"*Severidad:*\n{severity}"},
                        ],
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": summary},
                    },
                    {
                        "type": "divider",
                    },
                ],
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info(f"[Slack] Alerta enviada: {title} [{severity}]")
            return {"status": "sent"}
    except Exception as e:
        logger.error(f"[Slack] Error enviando mensaje: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def send_inter_agent_slack_notification(
    source_agent: int,
    target_agent: int,
    alert_type: str,
    message: str,
    severity: str,
) -> dict:
    """
    Notificación especial para alertas inter-agente (ej: Agente 3 → Agente 1).
    Visualiza la conexión entre agentes en Slack.
    """
    agent_names = {
        1: "🌱 Agente 1: Monitoreo Agrícola",
        2: "🌪️ Agente 2: Desastres",
        3: "☀️ Agente 3: Clima Espacial",
        4: "🔭 Agente 4: Divulgación",
        5: "☄️ Agente 5: NeoWs",
    }

    title = f"ALERTA INTER-AGENTE: {agent_names.get(source_agent, f'Agente {source_agent}')} → {agent_names.get(target_agent, f'Agente {target_agent}')}"

    return await send_slack_alert(
        agent_name=f"Sistema Multi-Agente ({alert_type})",
        title=title,
        report_summary=message,
        severity=severity,
    )
