import { useState } from 'react'
import { AlertTriangle, PlayCircle } from 'lucide-react'
import { runDisasters } from '../api/agentsApi'
import MarkdownReport from '../components/MarkdownReport'

const CATEGORIES = [
  { value: '', label: 'Todas las categorías' },
  { value: 'Wildfires', label: '🔥 Incendios (Wildfires)' },
  { value: 'Floods', label: '🌊 Inundaciones (Floods)' },
  { value: 'Severe Storms', label: '⛈️ Tormentas Severas' },
  { value: 'Earthquakes', label: '🌍 Terremotos' },
  { value: 'Volcanoes', label: '🌋 Volcanes' },
  { value: 'Droughts', label: '☀️ Sequías' },
]

function SeverityBadge({ severity = 'MINIMAL' }) {
  const cls = `badge badge-${(severity || 'minimal').toLowerCase()}`
  const emojis = { CRITICAL: '🚨', HIGH: '⚠️', MEDIUM: '⚡', LOW: 'ℹ️', MINIMAL: '✅', NONE: '✅' }
  return <span className={cls}>{emojis[severity] || '📊'} {severity}</span>
}

export default function Disasters() {
  const [category, setCategory] = useState('')
  const [daysBack, setDaysBack] = useState(7)
  const [checkAgro, setCheckAgro] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await runDisasters({
        category_filter: category || null,
        days_back: daysBack,
        check_agricultural_proximity: checkAgro,
      })
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
        <h2>🌪️ Alertas de Desastres Naturales</h2>
        <p>Agente 2 — Director de Gestión de Riesgos · NASA EONET + PostGIS Cono Sur</p>
      </div>

      <div className="card agent2" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '20px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={18} style={{ color: '#ef4444' }} />
          Configuración de Alerta
        </h3>

        <div className="grid-3" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Categoría de Desastre</label>
            <select className="form-select" value={category} onChange={e => setCategory(e.target.value)} id="select-disaster-category">
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Ventana Temporal (días)</label>
            <input type="number" className="form-input" value={daysBack} onChange={e => setDaysBack(Number(e.target.value))} min={1} max={30} id="input-disaster-days" />
          </div>

          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label className="form-label">&nbsp;</label>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading} id="btn-run-disasters"
              style={{ background: 'linear-gradient(135deg, #dc2626, #ea580c)' }}>
              {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
              {loading ? 'Analizando...' : 'Ejecutar Agente 2'}
            </button>
          </div>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px', color: 'var(--text-secondary)' }}>
          <input
            type="checkbox"
            checked={checkAgro}
            onChange={e => setCheckAgro(e.target.checked)}
            style={{ accentColor: '#ef4444', width: '16px', height: '16px' }}
          />
          Verificar proximidad con zonas agrícolas monitoreadas (PostGIS — 50km radio)
        </label>

        <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '10px', padding: '14px 16px', marginTop: '16px' }}>
          <p style={{ fontSize: '13px', color: '#f87171', fontWeight: 600, marginBottom: '6px' }}>🗺️ Mecánica PostGIS</p>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Filtra eventos por coordenadas del Cono Sur. Realiza consulta espacial en PostGIS para
            verificar proximidad del desastre (incendio, inundación) con zonas agrícolas activas del Agente 1.
            Eleva severidad si hay coincidencia geográfica.
          </p>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px', width: '32px', height: '32px', borderTopColor: '#ef4444' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Procesando coordenadas de desastres activos en Sudamérica...</p>
        </div>
      )}

      {result && (
        <div className="card animate-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} style={{ color: '#ef4444' }} />
              Alertas de Desastres — Cono Sur
            </h3>
            {result.severity && <SeverityBadge severity={result.severity} />}
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
