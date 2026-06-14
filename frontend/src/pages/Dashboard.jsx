import { useState, useEffect } from 'react'
import { Activity, Cpu, Database, Zap, PlayCircle, RefreshCw } from 'lucide-react'
import { runAllAgents, getSystemStatus, triggerAllIngestion } from '../api/agentsApi'
import TitleIcon from '../components/TitleIcon'
import leafIcon from '../assets/icons/leaf.svg'
import tornadoIcon from '../assets/icons/tornado.svg'
import weatherIcon from '../assets/icons/weather.svg'
import scienceIcon from '../assets/icons/science.svg'
import asteroidIcon from '../assets/icons/asteroid.svg'

const SEVERITY_ORDER = { CRITICAL: 5, HIGH: 4, MEDIUM: 3, LOW: 2, MINIMAL: 1, NONE: 0 }

function SeverityBadge({ severity = 'MINIMAL' }) {
  const cls = `badge badge-${severity.toLowerCase()}`
  const emojis = { CRITICAL: '🚨', HIGH: '⚠️', MEDIUM: '⚡', LOW: 'ℹ️', MINIMAL: '✅', NONE: '✅' }
  return <span className={cls}>{emojis[severity] || '📊'} {severity}</span>
}

const AGENTS_META = [
  { key: 'agent1', name: 'Monitoreo Agrícola', icon: leafIcon, desc: 'NDVI + NASA Earthdata', color: '#10b981' },
  { key: 'agent2', name: 'Desastres Naturales', icon: tornadoIcon, desc: 'NASA EONET + PostGIS', color: '#ef4444' },
  { key: 'agent3', name: 'Clima Espacial', icon: weatherIcon, desc: 'NASA DONKI + Kp Index', color: '#f59e0b' },
  { key: 'agent4', name: 'Divulgación', icon: scienceIcon, desc: 'NASA APOD + ISS', color: '#8b5cf6' },
  { key: 'agent5', name: 'Asteroides NeoWs', icon: asteroidIcon, desc: 'NASA NeoWs + PHAs', color: '#06b6d4' },
]

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [pipeline, setPipeline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [ingesting, setIngesting] = useState(false)

  useEffect(() => {
    getSystemStatus()
      .then(setStatus)
      .catch(err => console.error('Status error:', err))
  }, [])

  const handleRunAll = async () => {
    setLoading(true)
    setPipeline(null)
    try {
      const result = await runAllAgents({ days_back: 7 })
      setPipeline(result)
    } catch (err) {
      console.error('Pipeline error:', err)
      alert('Error ejecutando pipeline: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleIngestAll = async () => {
    setIngesting(true)
    try {
      await triggerAllIngestion()
      alert('✅ Ingesta iniciada en background. Los datos estarán listos en 1-2 minutos.')
    } catch (err) {
      alert('Error iniciando ingesta: ' + err.message)
    } finally {
      setIngesting(false)
    }
  }

  const globalSev = pipeline?.global_severity || 'MINIMAL'

  return (
    <div className="animate-in">
      {/* Header */}
      <div className="page-header">
        <h2>🛰️ Control Center</h2>
        <p>Sistema multiagente de monitoreo espacial y agrícola — 5 agentes cognitivos activos</p>
      </div>

      {/* System Status Bar */}
      <div className="card-glass" style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-dot"></span>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>Sistema Operacional</span>
          </div>
          {status && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {Object.entries(status.agents || {}).map(([name, st]) => (
                <span key={name} style={{
                  background: 'rgba(16, 185, 129, 0.1)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.2)',
                  borderRadius: '6px',
                  padding: '2px 8px',
                  fontSize: '11px',
                  fontWeight: 600,
                }}>
                  {st === 'ready' ? '✅' : '⚠️'} {name.replace('_', ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            className="btn btn-secondary"
            onClick={handleIngestAll}
            disabled={ingesting}
            id="btn-ingest-all"
          >
            {ingesting ? <span className="spinner" /> : <Database size={16} />}
            {ingesting ? 'Ingiriendo...' : 'Seed Data'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleRunAll}
            disabled={loading}
            id="btn-run-all-agents"
          >
            {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
            {loading ? 'Ejecutando...' : 'Ejecutar Todos los Agentes'}
          </button>
        </div>
      </div>

      {/* Global Severity after pipeline */}
      {pipeline && (
        <div className="card animate-in" style={{ marginBottom: '24px', borderColor: globalSev === 'CRITICAL' ? 'var(--sev-critical)' : globalSev === 'HIGH' ? 'var(--sev-high)' : 'var(--border-glow)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>SEVERIDAD GLOBAL DEL SISTEMA</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <SeverityBadge severity={globalSev} />
                <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  Pipeline completado en {pipeline.completed_at && pipeline.started_at ?
                    `${Math.round((new Date(pipeline.completed_at) - new Date(pipeline.started_at)) / 1000)}s`
                    : '—'}
                </span>
              </div>
            </div>
            <Activity size={32} style={{ color: 'var(--accent-blue)', opacity: 0.5 }} />
          </div>
        </div>
      )}

      {/* Agent Cards */}
      <div style={{ marginBottom: '20px', fontFamily: 'var(--font-display)', fontSize: '13px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>
        Agentes Cognitivos
      </div>

      <div className="grid-5" style={{ marginBottom: '32px' }}>
        {AGENTS_META.map((agent, idx) => {
          const agentResult = pipeline?.results?.[agent.key]
          const sev = agentResult?.severity || agentResult?.max_risk_level || null

          return (
            <div
              key={agent.key}
              className="stat-card"
              style={{ '--accent-color': agent.color }}
            >
              <div style={{ marginBottom: '4px' }}><TitleIcon src={agent.icon} color={agent.color} size={32} /></div>
              <div className="stat-label">{`Agente ${idx + 1}`}</div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
                {agent.name}
              </div>
              <div className="stat-sub">{agent.desc}</div>
              {sev && (
                <div style={{ marginTop: '8px' }}>
                  <SeverityBadge severity={sev} />
                </div>
              )}
              {agentResult?.status === 'error' && (
                <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--sev-critical)' }}>
                  ⚠️ Error en ejecución
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Architecture Overview */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={18} style={{ color: 'var(--accent-blue)' }} />
            Arquitectura (4 Capas)
          </h3>
          {[
            { n: '1', name: 'Ingesta & ETL', desc: 'Celery + NASA APIs → PostgreSQL', color: 'var(--accent-cyan)' },
            { n: '2', name: 'Datos & Caché', desc: 'PostgreSQL/PostGIS + Redis', color: 'var(--accent-green)' },
            { n: '3', name: 'Orquestación Cognitiva', desc: 'LangGraph + GPT-4o / Claude 3.5', color: 'var(--accent-purple)' },
            { n: '4', name: 'Comunicación (Output)', desc: 'Resend + Slack + REST Dashboard', color: 'var(--accent-orange)' },
          ].map(layer => (
            <div key={layer.n} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
              <div style={{ width: '28px', height: '28px', borderRadius: '8px', background: layer.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: 700, color: '#000', flexShrink: 0 }}>
                {layer.n}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px' }}>{layer.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{layer.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap size={18} style={{ color: 'var(--accent-orange)' }} />
            Regla de Oro — Control Técnico
          </h3>
          <div style={{ background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '10px', padding: '16px', marginBottom: '16px' }}>
            <p style={{ fontSize: '13px', color: 'var(--accent-orange)', fontWeight: 600, marginBottom: '8px' }}>⚡ Prohibido: Consumo directo de APIs</p>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Los agentes se alimentan EXCLUSIVAMENTE de réplicas locales en PostgreSQL.
              Latencia reducida de ~5s a milisegundos.
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {[
              { source: 'NASA DONKI', target: 'Agente 3 (Clima Espacial)', icon: weatherIcon, color: '#f59e0b' },
              { source: 'NASA EONET', target: 'Agente 2 (Desastres)', icon: tornadoIcon, color: '#ef4444' },
              { source: 'NASA NeoWs', target: 'Agente 5 (Asteroides)', icon: asteroidIcon, color: '#06b6d4' },
              { source: 'NASA APOD + ISS', target: 'Agente 4 (Educación)', icon: scienceIcon, color: '#8b5cf6' },
              { source: 'NASA Earthdata', target: 'Agente 1 (Agrícola)', icon: leafIcon, color: '#10b981' },
            ].map(flow => (
              <div key={flow.source} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                <TitleIcon src={flow.icon} color={flow.color} size={16} />
                <span style={{ color: 'var(--text-muted)' }}>{flow.source}</span>
                <span style={{ color: 'var(--accent-blue)' }}>→ PostgreSQL →</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{flow.target}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Agent Reports Preview (if pipeline ran) */}
      {pipeline && pipeline.results && (
        <div className="card animate-in">
          <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px', fontSize: '16px' }}>
            📋 Resultados del Pipeline
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Object.entries(pipeline.results).map(([key, result]) => (
              <div key={key} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '10px', padding: '14px 16px', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>{key}</span>
                  <SeverityBadge severity={result.severity || result.max_risk_level || 'MINIMAL'} />
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                  {result.report?.slice(0, 300) || result.error || 'Sin reporte disponible'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
