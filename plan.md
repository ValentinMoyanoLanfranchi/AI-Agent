# PLAN_IMPLEMENTACION_SISTEMA_AGENTES_IA

## 0. METADATOS
* [cite_start]**Destinatario:** Equipo de Desarrollo (Antigravity) [cite: 3]
* [cite_start]**Fecha:** 12 de Junio, 2026 [cite: 4]
* [cite_start]**Nivel:** Especificación de Arquitectura / Roadmap de Producto (Listo para Desarrollo) [cite: 5]
* [cite_start]**Paradigma:** Event-Driven Architecture (EDA) & Desacoplamiento Crítico [cite: 9]

---

## 1. ARQUITECTURA TECNOLÓGICA (4 CAPAS)
1. **Ingesta y ETL Automático:** Celery / Cloud Tasks. Consumo programado de endpoints crudos (NASA/Copernicus). [cite_start]Almacenamiento estructurado normalizado para evitar consultas redundantes del LLM[cite: 13].
2. [cite_start]**Datos y Caché:** PostgreSQL + PostGIS (consultas geográficas/polígonos agrarios)[cite: 14]. [cite_start]Redis para caché de baja latencia, estados de agentes y bloqueos distribuidos[cite: 14].
3. [cite_start]**Orquestación Cognitiva:** LangGraph o CrewAI (Grafos Dirigidos Acíclicos)[cite: 15]. [cite_start]Roles deterministas, herramientas nativas (Tools) y LLMs (GPT-4o / Claude 3.5 Sonnet) con temperatura controlada[cite: 16].
4. **Comunicación (Output):** Pasarela multicanal. [cite_start]Resend (emails/newsletters), Webhooks (Slack) e interfaces REST para Dashboards[cite: 18].

> [cite_start]**Regla de Oro de Control Técnico:** Prohibido el consumo directo de APIs externas durante prompts de usuario[cite: 63]. [cite_start]Los agentes se alimentan *exclusivamente* de las réplicas locales en PostgreSQL para bajar latencia de ~5s a milisegundos y blindar fallos[cite: 64, 65].

---

## 2. MATRIZ DE AGENTES COGNITIVOS

### [cite_start]Agente 1: Monitoreo Agrícola Core [cite: 22]
* [cite_start]**Objetivo:** Evaluar salud de cultivos, detectar anomalías y predecir estrés hídrico/térmico[cite: 23].
* [cite_start]**Mecánica:** Modelo híbrido[cite: 24]. [cite_start]Proceso determinista calcula $NDVI = (NIR - Red) / (NIR + Red)$ vía Sentinel Hub[cite: 24]. [cite_start]El LLM no procesa imagen cruda; interpreta la matriz estructurada de variaciones numéricas e histórico[cite: 25].
* [cite_start]**APIs:** Copernicus (Sentinel Hub), NASA GIBS, NASA POWER[cite: 26].
* [cite_start]**Prompt (Rol):** "Ingeniero Agrónomo Senior y Analista Geoespacial Macro. Recibe matrices NDVI, humedad y variaciones térmicas semanales. Identifica anomalías vs histórico de 5 años. Redacta reportes ejecutivos sin alucinaciones, traduciendo porcentajes a realidades biológicas." [cite: 27]

### [cite_start]Agente 2: Alertas de Desastres Naturales [cite: 28]
* [cite_start]**Objetivo:** Identificar eventos climáticos/geológicos extremos y cruzarlos con vulnerabilidad socioeconómica en Sudamérica[cite: 29].
* [cite_start]**Mecánica:** Filtra por coordenadas del Cono Sur[cite: 31]. [cite_start]Realiza consulta espacial en PostGIS para verificar proximidad del desastre (incendio, inundación) con zonas habitadas o agropecuarias activas del Agente 1[cite: 32]. [cite_start]Eleva severidad en Bus de Eventos si hay coincidencia[cite: 32].
* [cite_start]**APIs:** NASA EONET[cite: 30].
* [cite_start]**Prompt (Rol):** "Director de Gestión de Riesgos y Protección Civil. Precisión geográfica y velocidad. Procesa coordenadas de desastres activos y redacta alertas breves, urgentes y de alto impacto operacional para mensajería instantánea." [cite: 33]

### [cite_start]Agente 3: Análisis de Clima Espacial [cite: 34]
* [cite_start]**Objetivo:** Monitorear perturbaciones heliofísicas y predecir impactos en infraestructura tecnológica crítica terrestre[cite: 35].
* [cite_start]**Mecánica:** Consume flujos de CME (Eyecciones de Masa Coronal) y GST (Tormentas Geomagnéticas)[cite: 37]. [cite_start]Si el índice Kp supera el umbral crítico, genera reporte electromagnético y emite un mensaje inter-agente autónomo al Agente 1 alertando sobre pérdida de precisión en GPS de maquinaria agrícola autónoma[cite: 38, 41].
* [cite_start]**APIs:** NASA DONKI[cite: 36].
* [cite_start]**Prompt (Rol):** "Astrofísico Especialista en Telecomunicaciones e Infraestructura. Traduce viento solar, fulguraciones y eventos DONKI en riesgos pragmáticos para aviación, redes eléctricas y agricultura satelital." [cite: 42]

### [cite_start]Agente 4: Divulgación Turística / Educativa [cite: 43]
* [cite_start]**Objetivo:** Curación de contenido masivo para engagement, gamificación y educación científica[cite: 44].
* [cite_start]**Mecánica:** Narrativas adaptativas[cite: 46]. [cite_start]Detecta perfil demográfico (Niño, Estudiante, Experto) para reescribir la explicación APOD del día[cite: 46]. [cite_start]Cruza IP del usuario para notificar pasos visuales de la ISS en su horizonte[cite: 47].
* [cite_start]**APIs:** NASA APOD, Open Notify (ISS)[cite: 45].
* [cite_start]**Prompt (Rol):** "Divulgador Científico internacional (estilo Carl Sagan + rigurosidad académica). Explica astrofísica compleja con metáforas accesibles, adaptando el lenguaje estrictamente al perfil." [cite: 48]

### [cite_start]Agente 5: Seguimiento de Objetos Cercanos a la Tierra (NeoWs) [cite: 49]
* [cite_start]**Objetivo:** Filtrar y contextualizar riesgos de asteroides para consumo público mitigando el amarillismo[cite: 50, 53].
* [cite_start]**Mecánica:** Filtra diariamente objetos con flag `is_potentially_hazardous_asteroid: true`[cite: 52]. [cite_start]Traduce distancias a métricas comprensibles (ej. "12 veces la distancia Tierra-Luna")[cite: 53].
* [cite_start]**APIs:** NASA NeoWs[cite: 51].
* [cite_start]**Prompt (Rol):** "Periodista de Datos Científicos. Desmitifica datos de asteroides con frialdad analítica. Reportes claros para la comunidad científica sin inducir pánico." [cite: 54]

---

## [cite_start]3. CRONOGRAMA Y FASES DE DESARROLLO [cite: 57]

| Fase | Objetivos Técnicos y Entregables | Duración | Riesgo Crítico & Mitigación |
| :--- | :--- | :--- | :--- |
| **Fase 1: Infraestructura & Ingesta** | Configuración PostgreSQL/PostGIS + Redis. Conectores REST (DONKI, NeoWs, EONET, APOD, Copernicus). Tareas CRON de ingesta cruda. | Semanas 1-3 | **Riesgo:** Rate limiting en APIs de la NASA por mala gestión de API keys. |
| **Fase 2: Motor Agrícola & Emergencias** | Montaje LangGraph/CrewAI. Scripts de cálculo NDVI. Integración e hibridación de datos duros a texto para Agentes 1 y 2. | Semanas 4-6 | **Riesgo:** Alucinaciones del LLM en métricas numéricas decimales.<br>**Solución:** Few-shot prompting estricto. |
| **Fase 3: Integración Técnica & Mensajería** | Implementación Agente 3. Canal de comunicación inter-agente (Alerta GPS). Configuración Gateway de Salida (Resend + Slack). | Semanas 7-9 | **Riesgo:** Complejidad en estados concurrentes y bucles infinitos de mensajería inter-agente. |
| **Fase 4: Capa Educativa, Optimiz. & Cierre** | Desarrollo Agentes 4 y 5 (Lógica adaptativa). Pruebas de estrés. Caché fina para respuestas repetitivas. Despliegue CI/CD. | Semanas 10-12 | **Riesgo:** Costos elevados de tokens por tamaño de contexto en prompts B2C. |