"""
agents/foundry_iq.py — Cliente de Microsoft Foundry IQ (capa de conocimiento grounded).

Implementa el requisito OBLIGATORIO de Microsoft IQ del Agents League Hackathon:
recuperación de conocimiento agéntica con respuestas CITADAS (grounded) para reducir
alucinaciones. Es la materialización técnica de la "Regla de Oro" del sistema —
los agentes se alimentan exclusivamente de una réplica local de conocimiento.

Modos (degradación automática, el demo nunca se rompe):
  1. foundry_iq        → knowledge base de Foundry IQ respaldado por Azure AI Search.
  2. fallback_postgres → recupera desde los AgentReport locales en PostgreSQL.
  3. demo              → contexto mínimo embebido si no hay ni Azure ni DB.
"""
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Una fuente citada que respalda la respuesta (anti-alucinación)."""
    title: str
    snippet: str
    source: str
    score: float = 0.0
    url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GroundedContext:
    """Contexto recuperado de Foundry IQ para alimentar al Agente Consultor."""
    query: str
    citations: List[Citation] = field(default_factory=list)
    context_text: str = ""
    mode: str = "demo"

    @property
    def is_grounded(self) -> bool:
        return len(self.citations) > 0


# ─────────────────────────────────────────────────────────────
# Punto de entrada principal
# ─────────────────────────────────────────────────────────────
def retrieve_grounded(query: str, top_k: int = 5) -> GroundedContext:
    """
    Recupera contexto citado para una pregunta del usuario.

    Intenta Foundry IQ (Azure AI Search) → PostgreSQL local → demo embebido.
    """
    if settings.foundry_iq_search_enabled:
        try:
            ctx = _retrieve_from_foundry_iq(query, top_k)
            if ctx.is_grounded:
                logger.info(f"[FoundryIQ] {len(ctx.citations)} fuentes recuperadas del knowledge base.")
                return ctx
        except Exception as e:
            logger.warning(f"[FoundryIQ] Retrieval real falló, uso fallback: {e}")

    ctx = _retrieve_from_postgres(query, top_k)
    if ctx.is_grounded:
        return ctx

    return _demo_context(query)


# ─────────────────────────────────────────────────────────────
# Modo 1: Foundry IQ (Azure AI Search)
# ─────────────────────────────────────────────────────────────
def _retrieve_from_foundry_iq(query: str, top_k: int) -> GroundedContext:
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )

    results = client.search(search_text=query, top=top_k)

    citations: List[Citation] = []
    parts: List[str] = []
    for r in results:
        content = r.get("content") or r.get("full_report") or ""
        title = r.get("title") or r.get("agent_name") or "Reporte del sistema"
        source = r.get("source") or f"{r.get('agent_name', 'agente')} / {r.get('created_at', '')}"
        score = float(r.get("@search.score", 0.0) or 0.0)
        citations.append(Citation(title=title, snippet=content[:400], source=source, score=score))
        parts.append(f"[Fuente: {source}]\n{content}")

    return GroundedContext(
        query=query,
        citations=citations,
        context_text="\n\n---\n\n".join(parts),
        mode="foundry_iq",
    )


# ─────────────────────────────────────────────────────────────
# Modo 2: Fallback — réplica local en PostgreSQL
# ─────────────────────────────────────────────────────────────
def _retrieve_from_postgres(query: str, top_k: int) -> GroundedContext:
    try:
        from sqlalchemy import select, desc, or_
        from database.session import SyncSessionLocal
        from database.models import AgentReport

        terms = [t for t in query.lower().split() if len(t) > 3][:6]

        with SyncSessionLocal() as db:
            stmt = select(AgentReport)
            if terms:
                filters = [AgentReport.full_report.ilike(f"%{t}%") for t in terms]
                filters += [AgentReport.summary.ilike(f"%{t}%") for t in terms]
                stmt = stmt.where(or_(*filters))
            stmt = stmt.order_by(desc(AgentReport.created_at)).limit(top_k)
            rows = db.execute(stmt).scalars().all()

            if not rows:
                rows = db.execute(
                    select(AgentReport).order_by(desc(AgentReport.created_at)).limit(top_k)
                ).scalars().all()

        citations: List[Citation] = []
        parts: List[str] = []
        for r in rows:
            content = r.full_report or r.summary or ""
            created = r.created_at.isoformat() if r.created_at else ""
            source = f"{r.agent_name} / {created}"
            citations.append(Citation(
                title=r.title or r.agent_name,
                snippet=content[:400],
                source=source,
                score=1.0,
            ))
            parts.append(f"[Fuente: {source} | severidad: {r.severity}]\n{content}")

        return GroundedContext(
            query=query,
            citations=citations,
            context_text="\n\n---\n\n".join(parts),
            mode="fallback_postgres",
        )
    except Exception as e:
        logger.warning(f"[FoundryIQ] Fallback PostgreSQL no disponible: {e}")
        return GroundedContext(query=query, mode="demo")


# ─────────────────────────────────────────────────────────────
# Modo 3: Demo embebido (último recurso para que el endpoint nunca falle)
# ─────────────────────────────────────────────────────────────
def _demo_context(query: str) -> GroundedContext:
    today = datetime.utcnow().date().isoformat()
    demo = [
        Citation(
            title="Reporte Agrícola — Pampa Húmeda",
            snippet="NDVI 0.72 (−0.04 semanal). Estrés hídrico leve en Buenos Aires. "
                    "Sin anomalías críticas vs histórico 5 años.",
            source=f"agent1_agricultural / {today}",
        ),
        Citation(
            title="Reporte Clima Espacial",
            snippet="Índice Kp máximo 5.3 — supera umbral. Alerta inter-agente GPS enviada al "
                    "Agente Agrícola por riesgo en maquinaria autónoma.",
            source=f"agent3_space_weather / {today}",
        ),
    ]
    context = "\n\n---\n\n".join(f"[Fuente: {c.source}]\n{c.snippet}" for c in demo)
    return GroundedContext(query=query, citations=demo, context_text=context, mode="demo")
