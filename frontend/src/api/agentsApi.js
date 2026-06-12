// src/api/agentsApi.js — Cliente Axios para el backend de agentes
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000, // 2 min — agentes pueden tardar
  headers: { 'Content-Type': 'application/json' },
})

// ─── Agentes ──────────────────────────────────────────────────

export const runAllAgents = (params = {}) =>
  api.post('/api/agents/run-all', params).then(r => r.data)

export const runAgricultural = (params = {}) =>
  api.post('/api/agents/agricultural', params).then(r => r.data)

export const runDisasters = (params = {}) =>
  api.post('/api/agents/disasters', params).then(r => r.data)

export const runSpaceWeather = (days_back = 3) =>
  api.post(`/api/agents/space-weather?days_back=${days_back}`).then(r => r.data)

export const runEducational = (params = {}) =>
  api.post('/api/agents/educational', params).then(r => r.data)

export const runNeoWs = (params = {}) =>
  api.post('/api/agents/neows', params).then(r => r.data)

export const getAgentReports = (params = {}) =>
  api.get('/api/agents/reports', { params }).then(r => r.data)

export const getSystemStatus = () =>
  api.get('/api/agents/status').then(r => r.data)

// ─── Ingesta ──────────────────────────────────────────────────

export const triggerAllIngestion = () =>
  api.post('/api/ingest/all').then(r => r.data)

export const triggerIngestion = (source) =>
  api.post(`/api/ingest/${source}`).then(r => r.data)

export default api
