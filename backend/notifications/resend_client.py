"""
notifications/resend_client.py — Cliente de email via Resend API.
"""
import logging
from typing import Optional, List
import resend
from config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


async def send_alert_email(
    subject: str,
    html_body: str,
    to_emails: Optional[List[str]] = None,
    severity: str = "INFO",
) -> dict:
    """
    Envía alerta por email usando Resend.

    Args:
        subject: Asunto del email.
        html_body: Cuerpo HTML del email.
        to_emails: Lista de destinatarios. None usa el default de config.
        severity: Nivel de severidad (para prefijo del asunto).
    """
    if not settings.resend_api_key or settings.resend_api_key == "re_your_resend_key_here":
        logger.warning("[Resend] API key no configurada. Email no enviado.")
        return {"status": "skipped", "reason": "api_key_not_configured"}

    recipients = to_emails or [settings.resend_to_email]

    # Emoji según severidad
    emoji_map = {
        "CRITICAL": "🚨",
        "HIGH": "⚠️",
        "MEDIUM": "⚡",
        "LOW": "ℹ️",
        "INFO": "📊",
    }
    emoji = emoji_map.get(severity.upper(), "📊")

    try:
        result = resend.Emails.send({
            "from": settings.resend_from_email,
            "to": recipients,
            "subject": f"{emoji} [{severity}] {subject}",
            "html": html_body,
        })
        logger.info(f"[Resend] Email enviado: {result.get('id')} → {recipients}")
        return {"status": "sent", "id": result.get("id"), "recipients": recipients}

    except Exception as e:
        logger.error(f"[Resend] Error enviando email: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def format_report_as_html(
    agent_name: str,
    report_text: str,
    severity: str,
    generated_at: str,
) -> str:
    """Convierte texto markdown de un agente a HTML para email."""
    severity_colors = {
        "CRITICAL": "#dc2626",
        "HIGH": "#ea580c",
        "MEDIUM": "#d97706",
        "LOW": "#2563eb",
        "MINIMAL": "#16a34a",
        "NONE": "#6b7280",
    }
    color = severity_colors.get(severity.upper(), "#374151")

    # Convertir saltos de línea y markdown básico
    html_body = report_text.replace("\n", "<br>").replace("## ", "<h2>").replace("### ", "<h3>")

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }}
            .container {{ max-width: 700px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1e40af, #7c3aed); padding: 24px; }}
            .severity-badge {{ display: inline-block; background: {color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
            .content {{ padding: 24px; line-height: 1.6; }}
            .footer {{ padding: 16px 24px; background: #0f172a; font-size: 12px; color: #94a3b8; }}
            h2 {{ color: #93c5fd; }}
            h3 {{ color: #86efac; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="color:white;margin:0">🛰️ Sistema de Agentes IA</h1>
                <p style="color:#bfdbfe;margin:8px 0 0">{agent_name} | {generated_at}</p>
                <span class="severity-badge">{severity}</span>
            </div>
            <div class="content">
                {html_body}
            </div>
            <div class="footer">
                Generado automáticamente por el Sistema de Agentes IA — Hackathon Junio 2026
            </div>
        </div>
    </body>
    </html>
    """
