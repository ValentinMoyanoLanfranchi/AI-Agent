import { useState } from 'react'
import { Sun, PlayCircle, Radio } from 'lucide-react'
import { runSpaceWeather } from '../api/agentsApi'
import MarkdownReport from '../components/MarkdownReport'

function SeverityBadge({ severity = 'MINIMAL' }) {
  const cls = `badge badge-${(severity || 'minimal').toLowerCase()}`
  const emojis = { CRITICAL: '🚨', HIGH: '⚠️', MEDIUM: '⚡', LOW: 'ℹ️', MINIMAL: '✅', NONE: '✅' }
  return <span className={cls}>{emojis[severity] || '📊'} {severity}</span>
}

const KP_LEVELS = [
  { range: '0–3', label: 'Tranquilo', color: '#10b981', desc: 'Sin impacto operacional' },
  { range: '4–4', label: 'Activo', color: '#3b82f6', desc: 'Perturbaciones menores' },
  { range: '5', label: 'Tormenta Menor', color: '#d97706', desc: 'GPS reducido ⚠️' },
  { range: '6–7', label: 'Tormenta Moderada', color: '#ea580c', desc: 'Aviación + Redes' },
  { range: '8–9', label: 'Tormenta Severa', color: '#dc2626', desc: 'Impacto sistémico 🚨' },
]

export default function SpaceWeather() {
  const [daysBack, setDaysBack] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await runSpaceWeather(daysBack)
      setResult(data)
    } catch (err) {
      setResult({ status: 'error', error: err.response?.data?.detail || err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>☀️ Análisis de Clima Espacial</h2>
        <p>Agente 3 — Astrofísico Especialista · NASA DONKI + Comunicación Inter-Agente</p>
      </div>

      {/* Kp Reference Table */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '16px', fontSize: '15px' }}>📊 Escala Kp — Referencia</h3>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {KP_LEVELS.map(level => (
            <div key={level.range} style={{ flex: '1', minWidth: '120px', background: `${level.color}15`, border: `1px solid ${level.color}30`, borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: level.color, fontFamily: 'var(--font-display)' }}>Kp {level.range}</div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: level.color, marginTop: '4px' }}>{level.label}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{level.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card agent3" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '20px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sun size={18} style={{ color: '#f59e0b' }} />
          Configuración
        </h3>

        <div className="grid-3" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Días hacia atrás</label>
            <input type="number" className="form-input" value={daysBack} onChange={e => setDaysBack(Number(e.target.value))} min={1} max={14} id="input-sw-days" />
          </div>
          <div></div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label className="form-label">&nbsp;</label>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading} id="btn-run-space-weather"
              style={{ background: 'linear-gradient(135deg, #d97706, #f59e0b)' }}>
              {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
              {loading ? 'Analizando...' : 'Ejecutar Agente 3'}
            </button>
          </div>
        </div>

        <div style={{ background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245,158,11,0.15)', borderRadius: '10px', padding: '14px 16px' }}>
          <p style={{ fontSize: '13px', color: '#fbbf24', fontWeight: 600, marginBottom: '6px' }}>⚡ Comunicación Inter-Agente Autónoma</p>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Si el índice Kp supera el umbral crítico (5.0), genera automáticamente un mensaje inter-agente
            al Agente 1 (Agrícola) alertando sobre pérdida de precisión en GPS de maquinaria agrícola autónoma.
            El canal de comunicación usa Redis pub/sub + PostgreSQL.
          </p>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px', width: '32px', height: '32px', borderTopColor: '#f59e0b' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Analizando flujo solar y tormentas geomagnéticas...</p>
        </div>
      )}

      {result && (
        <div className="card animate-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sun size={18} style={{ color: '#f59e0b' }} />
              Reporte de Clima Espacial
            </h3>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {result.kp_max > 0 && (
                <span style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '8px', padding: '4px 12px', fontSize: '13px', fontWeight: 700, color: '#fbbf24' }}>
                  Kp max: {result.kp_max}
                </span>
              )}
              {result.alert_sent_to_agent1 && (
                <span style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '4px 12px', fontSize: '11px', fontWeight: 700, color: '#f87171' }}>
                  <Radio size={10} style={{ display: 'inline', marginRight: '4px' }} />
                  ALERTA GPS → AGENTE 1
                </span>
              )}
              {result.severity && <SeverityBadge severity={result.severity} />}
            </div>
          </div>

          {result.status === 'error' ? (
            <div style={{ background: 'rgba(220, 38, 38, 0.1)', border: '1px solid rgba(220,38,38,0.2)', borderRadius: '10px', padding: '16px', color: '#f87171' }}>
              ⚠️ Error: {result.error}
            </div>
          ) : (
            <MarkdownReport>{result.report}</MarkdownReport>
          )}
        </div>
      )}
    </div>
  )
}
