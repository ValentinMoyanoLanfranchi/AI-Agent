"""
init_db.py — Script de inicialización de la base de datos.

Crea todas las tablas y siembra datos iniciales para desarrollo/hackathon.
Ejecutar SOLO una vez al inicio: python init_db.py
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def create_tables():
    """Crea todas las tablas usando SQLAlchemy async."""
    from database.session import async_engine, Base
    # Importar todos los modelos para que SQLAlchemy los registre
    from database.models import (
        NDVIRecord, DisasterEvent, SpaceWeatherEvent,
        APODRecord, ISSPass, AsteroidRecord, AgentReport, InterAgentAlert
    )

    from sqlalchemy import text

    logger.info("🗄️  Conectando a la base de datos...")
    try:
        async with async_engine.begin() as conn:
            logger.info("✅ Conexión exitosa")
            # PostGIS es requerido por las columnas Geometry + índices GIST.
            # En Supabase la extensión está disponible pero hay que activarla.
            logger.info("🧩 Habilitando extensión PostGIS...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            logger.info("📋 Creando tablas...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Todas las tablas creadas correctamente")
    except Exception as e:
        logger.error(f"❌ Error creando tablas: {e}")
        logger.error("   Verificar que PostgreSQL esté corriendo y las credenciales sean correctas")
        sys.exit(1)


async def verify_tables():
    """Verifica que las tablas existan y estén accesibles."""
    from database.session import AsyncSessionLocal
    from database.models import AgentReport

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        result = await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        tables = [row[0] for row in result.fetchall()]
        logger.info(f"📊 Tablas encontradas: {', '.join(sorted(tables))}")
        return tables


async def main():
    logger.info("=" * 60)
    logger.info("  INICIALIZACIÓN DE BASE DE DATOS — Hackathon Junio 2026")
    logger.info("=" * 60)

    await create_tables()
    tables = await verify_tables()

    expected_tables = {
        "ndvi_records", "disaster_events", "space_weather_events",
        "apod_records", "iss_passes", "asteroid_records",
        "agent_reports", "inter_agent_alerts"
    }
    missing = expected_tables - set(tables)
    if missing:
        logger.warning(f"⚠️  Tablas faltantes: {missing}")
    else:
        logger.info("✅ Todas las tablas del sistema están presentes")

    logger.info("")
    logger.info("🚀 Base de datos lista. Próximos pasos:")
    logger.info("   1. Levantar el backend: uvicorn main:app --reload")
    logger.info("   2. Seed de datos:       curl -X POST http://localhost:8000/api/ingest/all")
    logger.info("   3. Ejecutar agentes:    curl -X POST http://localhost:8000/api/agents/run-all")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
