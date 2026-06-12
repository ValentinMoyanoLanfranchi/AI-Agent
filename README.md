# 🛰️ Sistema de Agentes IA — Hackathon Junio 2026

Sistema multiagente de monitoreo espacial y agrícola basado en **LangGraph**, consumiendo APIs de NASA.

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│  CAPA 4: OUTPUT — Resend (email) + Slack Webhooks + Dashboard    │
├──────────────────────────────────────────────────────────────────┤
│  CAPA 3: ORQUESTACIÓN — LangGraph + GPT-4o / Claude 3.5 Sonnet   │
│    ├─ Agente 1: Monitoreo Agrícola Core (NDVI + NASA Earthdata)  │
│    ├─ Agente 2: Alertas Desastres (NASA EONET + PostGIS)         │
│    ├─ Agente 3: Clima Espacial (NASA DONKI + Inter-Agente)       │
│    ├─ Agente 4: Divulgación (NASA APOD + ISS Open Notify)        │
│    └─ Agente 5: Asteroides (NASA NeoWs)                          │
├──────────────────────────────────────────────────────────────────┤
│  CAPA 2: DATOS — PostgreSQL/PostGIS + Redis                       │
├──────────────────────────────────────────────────────────────────┤
│  CAPA 1: INGESTA — Celery + Celery Beat (ETL programado)         │
└──────────────────────────────────────────────────────────────────┘
```

## ⚡ Inicio Rápido

### 1. Pre-requisitos
- Docker Desktop instalado y corriendo
- Python 3.11+ (solo para desarrollo local)
- Node 20+ (para frontend en modo dev)

### 2. Configurar variables de entorno

```bash
# El archivo .env ya está creado con defaults para hackathon
# Solo necesitás reemplazar las API keys de LLM:
```

Editar `.env` y reemplazar:
- `OPENAI_API_KEY=sk-REEMPLAZAR-CON-TU-KEY`
- `ANTHROPIC_API_KEY=sk-ant-REEMPLAZAR-CON-TU-KEY`

### 3. Levantar el sistema completo

```bash
# Opción A: Docker Compose (RECOMENDADO para producción)
docker compose up --build

# Opción B: Desarrollo local (más rápido para iterar)
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 2 — Celery Worker
cd backend
celery -A ingestion.tasks worker --loglevel=info

# Terminal 3 — Frontend
cd frontend
npm install && npm run dev
```

### 4. Cargar datos iniciales

```bash
# Una vez que los servicios están corriendo:
curl -X POST http://localhost:8000/api/ingest/all
```

O usar el botón **"Seed Data"** en el Dashboard.

### 5. Ejecutar los agentes

- **Dashboard:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Agente 1:** `POST /api/agents/agricultural`
- **Todos:** `POST /api/agents/run-all`

## 🔑 APIs Requeridas

| API | URL | Key Requerida |
|-----|-----|---------------|
| NASA APIs | https://api.nasa.gov/ | `NASA_API_KEY` (DEMO_KEY funciona) |
| OpenAI | https://platform.openai.com/ | `OPENAI_API_KEY` |
| Anthropic | https://console.anthropic.com/ | `ANTHROPIC_API_KEY` |
| Resend (opcional) | https://resend.com/ | `RESEND_API_KEY` |
| Slack (opcional) | https://api.slack.com/ | `SLACK_WEBHOOK_URL` |

## 🧠 Regla de Oro

> **Prohibido** el consumo directo de APIs externas durante prompts de usuario.
> Los agentes se alimentan **exclusivamente** de las réplicas locales en PostgreSQL.
> Las APIs externas solo se consumen desde **Celery** (background).

## 📡 Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Health check del sistema |
| GET | `/api/agents/status` | Estado de los 5 agentes |
| POST | `/api/agents/run-all` | Pipeline completo |
| POST | `/api/agents/agricultural` | Agente 1: Monitoreo Agrícola |
| POST | `/api/agents/disasters` | Agente 2: Desastres Naturales |
| POST | `/api/agents/space-weather` | Agente 3: Clima Espacial |
| POST | `/api/agents/educational` | Agente 4: Divulgación |
| POST | `/api/agents/neows` | Agente 5: Asteroides |
| POST | `/api/ingest/all` | Iniciar ingesta de todas las fuentes |
| GET | `/api/agents/reports` | Historial de reportes |

## 🌍 Zonas Agrícolas Monitoreadas

- 🇦🇷 Pampa Húmeda — Buenos Aires (`ARG-BA-PAMPA`)
- 🇦🇷 Córdoba — Zona Norte (`ARG-COR-AGRO`)
- 🇧🇷 Mato Grosso — Cerrado (`BRA-MT-CERRADO`)
- 🇺🇾 Uruguay — Soriano (`URY-SORIANO`)
- 🇨🇱 Chile — Araucanía (`CHI-ARAUCANIA`)

## ⚠️ Alerta Inter-Agente (Agente 3 → Agente 1)

Cuando el índice Kp supera 5.0, el sistema genera automáticamente:
1. Un registro en `inter_agent_alerts` en PostgreSQL
2. Una notificación Slack del canal inter-agente
3. La próxima ejecución del Agente 1 detecta la alerta pendiente

## 🏆 Hackathon Notes

- **Tiempo:** 24-48 horas
- **NASA API Key:** DEMO_KEY incluida (30 req/hora — suficiente para demo)
- **Datos NDVI:** Simulados con variaciones estacionales realistas del Cono Sur
- **LLM:** Configurar una key de OpenAI o Anthropic para activar los agentes
