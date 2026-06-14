# 🛰️ Sistema de Agentes IA — Hackathon Junio 2026

Sistema multiagente de monitoreo espacial y agrícola basado en **LangGraph**, consumiendo APIs de NASA.

> **Agents League Hackathon · Track Reasoning Agents (Microsoft Foundry) · Capa IQ: Foundry IQ**
>
> 6 agentes que ayudan a productores de Latinoamérica a anticipar riesgos —estrés hídrico, desastres
> naturales y pérdida de precisión GPS por clima espacial—. **Todo el cómputo corre en Azure AI Foundry**;
> el conocimiento se sirve con **Foundry IQ**: respuestas citadas y *grounded* que reducen la alucinación.

### 🏆 Alineación con los premios
- **💡 Best Use of IQ** — Foundry IQ es la columna vertebral: recupera los reportes de los agentes y responde **citando fuentes**, sin alucinar.
- **🧠 Best Reasoning Agent** — modelo razonador **gpt-5.4** + razonamiento multi-paso cruzando fuentes + **alerta inter-agente** (clima espacial → GPS agrícola).
- **🎗️ Hack for Good** — impacto en seguridad alimentaria: anticipa riesgos para el agro del Cono Sur.
- **🎓 Top Student** — desarrollado por estudiante de la **UNC (FCEFyN)**.

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

## 💡 Integración Microsoft IQ — Agents League Hackathon

Este proyecto cumple el requisito obligatorio de integrar una capa **Microsoft IQ**:

| Item | Implementación |
|------|----------------|
| **Track** | 🧠 Reasoning Agents (Microsoft Foundry) |
| **Capa IQ** | 💡 **Foundry IQ** — recuperación de conocimiento agéntica con respuestas citadas/grounded |
| **Agente** | **Agente Consultor** (`agent6_consultant`) — `POST /api/agents/consult` |
| **Modelo** | **gpt-5.4** (razonador) para el Consultor · **gpt-5.4-mini** para los 5 agentes — todo en Azure AI Foundry |

![Consultor IA — chat conversacional grounded con citas de Foundry IQ](docs/consultor-chat.png)

**Cómo funciona** (razonamiento multi-paso, anti-alucinación):
1. **RETRIEVE** → recupera contexto citado desde el knowledge base de Foundry IQ (Azure AI Search).
2. **REASON** → razona sobre el contexto con el modelo desplegado en Azure AI Foundry.
3. **GROUND** → devuelve la respuesta **con citas verificables** de cada fuente.

Es la materialización técnica de la **Regla de Oro** del sistema: los agentes solo responden
desde la réplica local de conocimiento, nunca alucinan datos.

**🔁 Loop cerrado (auto-sync):** cada reporte que generan los agentes se **indexa automáticamente**
en Foundry IQ (vía `save_agent_report`), así el Consultor siempre responde con el conocimiento
más reciente — sin sincronización manual.

**Activación:**
```bash
# 1. Cargar credenciales de Azure en .env (ver bloque AZURE_AI_FOUNDRY_* y AZURE_SEARCH_*)
# 2. Poblar el knowledge base de Foundry IQ con los reportes de los agentes:
python -m ingestion.foundry_iq_sync
# 3. Consultar:
curl -X POST http://localhost:8000/api/agents/consult \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Hay riesgo GPS para la maquinaria agrícola esta semana?"}'
```

> **Degradación automática:** si Azure aún no está configurado, el Agente Consultor responde
> en *modo grounded local* (desde PostgreSQL) con citas reales — el demo nunca se rompe.

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
| POST | `/api/agents/consult` | 🧠 Agente Consultor (Foundry + Foundry IQ) — respuestas grounded |
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
