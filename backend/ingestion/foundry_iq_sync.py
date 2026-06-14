"""
ingestion/foundry_iq_sync.py — Sincroniza el conocimiento del sistema hacia Foundry IQ.

Empuja los reportes de los agentes (y datos clave de la réplica local) hacia el índice
de Azure AI Search que respalda el knowledge base de Foundry IQ. Así el Agente Consultor
puede dar respuestas grounded y citadas (requisito IQ del Agents League Hackathon).

Uso:
    python -m ingestion.foundry_iq_sync          # crea índice (si falta) + sincroniza
    python -m ingestion.foundry_iq_sync --create-only

Si Azure AI Search no está configurado, el script avisa y no hace nada (no rompe el sistema).
"""
import logging
import sys
from datetime import datetime

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def ensure_index() -> bool:
    """Crea el índice de Azure AI Search que respalda el knowledge base, si no existe."""
    if not settings.foundry_iq_search_enabled:
        logger.warning("Azure AI Search no configurado (AZURE_SEARCH_*). Nada que hacer.")
        return False

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
    )

    index_client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )

    existing = [i.name for i in index_client.list_indexes()]
    if settings.azure_search_index_name in existing:
        logger.info(f"Índice '{settings.azure_search_index_name}' ya existe.")
        return True

    index = SearchIndex(
        name=settings.azure_search_index_name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="agent_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source", type=SearchFieldDataType.String),
            SimpleField(name="severity", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="created_at", type=SearchFieldDataType.String, sortable=True),
        ],
    )
    index_client.create_index(index)
    logger.info(f"✅ Índice '{settings.azure_search_index_name}' creado.")
    return True


def _collect_documents() -> list[dict]:
    """Reúne los reportes de los agentes desde la réplica local para indexar."""
    from sqlalchemy import select, desc
    from database.session import SyncSessionLocal
    from database.models import AgentReport

    docs: list[dict] = []
    with SyncSessionLocal() as db:
        rows = db.execute(
            select(AgentReport).order_by(desc(AgentReport.created_at)).limit(500)
        ).scalars().all()

        for r in rows:
            created = r.created_at.isoformat() if r.created_at else ""
            docs.append({
                "id": f"report-{r.id}",
                "content": r.full_report or r.summary or "",
                "title": r.title or r.agent_name,
                "agent_name": r.agent_name,
                "source": f"{r.agent_name} / {created}",
                "severity": r.severity or "INFO",
                "doc_type": "agent_report",
                "created_at": created,
            })
    return docs


def sync_reports_to_foundry_iq() -> int:
    """Sube los reportes al índice. Devuelve cuántos documentos subió."""
    if not settings.foundry_iq_search_enabled:
        logger.warning("Azure AI Search no configurado — sincronización omitida.")
        return 0

    if not ensure_index():
        return 0

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    try:
        docs = _collect_documents()
    except Exception as e:
        logger.error(f"No se pudieron leer reportes de PostgreSQL: {e}")
        return 0

    if not docs:
        logger.info("No hay reportes para sincronizar todavía. Ejecutá los agentes primero.")
        return 0

    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )
    result = client.upload_documents(documents=docs)
    ok = sum(1 for r in result if r.succeeded)
    logger.info(f"✅ {ok}/{len(docs)} documentos sincronizados a Foundry IQ.")
    return ok


def upsert_report(report: dict) -> bool:
    """Auto-sync: indexa un único reporte recién generado en Foundry IQ.

    Cierra el loop del sistema — cada reporte que produce un agente queda al
    instante disponible para el Consultor, sin sincronización manual.
    """
    if not settings.foundry_iq_search_enabled:
        return False
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient

        created = report.get("created_at") or ""
        agent = report.get("agent_name") or "agente"
        doc = {
            "id": f"report-{report.get('id')}",
            "content": report.get("full_report") or report.get("summary") or "",
            "title": report.get("title") or agent,
            "agent_name": agent,
            "source": f"{agent} / {created}",
            "severity": report.get("severity") or "INFO",
            "doc_type": "agent_report",
            "created_at": str(created),
        }
        client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )
        client.upload_documents(documents=[doc])
        logger.info(f"[FoundryIQ] auto-sync: reporte {doc['id']} indexado.")
        return True
    except Exception as e:
        logger.warning(f"[FoundryIQ] auto-sync falló: {e}")
        return False


if __name__ == "__main__":
    if "--create-only" in sys.argv:
        ensure_index()
    else:
        sync_reports_to_foundry_iq()
