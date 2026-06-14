import { useState } from 'react'
import { Zap, PlayCircle, ShieldAlert } from 'lucide-react'
import { runNeoWs } from '../api/agentsApi'
import MarkdownReport from '../components/MarkdownReport'
import TitleIcon from '../components/TitleIcon'
import asteroidIcon from '../assets/icons/asteroid.svg'

export default function NeoWs() {
  const [daysAhead, setDaysAhead] = useState(7)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await runNeoWs({ days_ahead: daysAhead })
      setResult(data)
    } catch (err) {
      setResult({ status: 'error', error: err.response?.data?.detail || err.message })
    } finally {
      setLoading(false)
    }
  }

  const riskColor = result?.max_risk_level
    ? { NONE: '#10b981', LOW: '#3b82f6', MEDIUM: '#d97706', HIGH: '#ef4444' }[result.max_risk_level] || '#10b981'
    : '#06b6d4'

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <TitleIcon src={asteroidIcon} color="#06b6d4" /> Seguimiento de Asteroides NeoWs
        </h2>
        <p>Agente 5 — Periodista de Datos Científicos · NASA NeoWs · Sin alarmismo, con contexto</p>
      </div>

      {/* Context Card */}
      <div className="grid-3" style={{ marginBottom: '24px' }}>
        {[
          { icon: '🌍', value: '384,400 km', label: '1 Distancia Lunar (LD)', color: '#06b6d4' },
          { icon: '☄️', value: '140m+', label: 'Diámetro mínimo PHA', color: '#f59e0b' },
          { icon: '🛡️', value: '95%+', label: 'PHAs >1km monitoreados', color: '#10b981' },
        ].map(item => (
          <div key={item.label} className="stat-card" style={{ '--accent-color': item.color, textAlign: 'center' }}>
            <div style={{ fontSize: '28px', marginBottom: '4px' }}>{item.icon}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: item.color }}>{item.value}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{item.label}</div>
          </div>
        ))}
      </div>

      <div className="card agent5" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '20px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={18} style={{ color: '#06b6d4' }} />
          Configuración del Análisis
        </h3>

        <div className="grid-3" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Días hacia adelante</label>
            <input type="number" className="form-input" value={daysAhead} onChange={e => setDaysAhead(Number(e.target.value))} min={1} max={30} id="input-neows-days" />
          </div>
          <div></div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label className="form-label">&nbsp;</label>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading} id="btn-run-neows"
              style={{ background: 'linear-gradient(135deg, #0891b2, #06b6d4)' }}>
              {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
              {loading ? 'Analizando...' : 'Ejecutar Agente 5'}
            </button>
          </div>
        </div>

        <div style={{ background: 'rgba(6, 182, 212, 0.05)', border: '1px solid rgba(6,182,212,0.15)', borderRadius: '10px', padding: '14px 16px' }}>
          <p style={{ fontSize: '13px', color: '#22d3ee', fontWeight: 600, marginBottom: '6px' }}>🧊 Frialdad Analítica — Sin Amarillismo</p>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Filtra diariamente objetos con flag <code style={{ background: 'rgba(0,0,0,0.4)', padding: '1px 6px', borderRadius: '4px', fontSize: '12px' }}>is_potentially_hazardous_asteroid: true</code>.
            Traduce distancias a métricas comprensibles. Un asteroide "potencialmente peligroso" en la clasificación
            orbital NO significa amenaza inmediata — el Agente contextualiza con rigor científico.
          </p>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px', width: '32px', height: '32px', borderTopColor: '#06b6d4' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Consultando base de datos de objetos cercanos a la Tierra...</p>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>Filtrando PHAs para los próximos {daysAhead} días</p>
        </div>
      )}

      {result && (
        <div className="card animate-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={18} style={{ color: '#06b6d4' }} />
              Reporte NEO — Próximos {daysAhead} días
            </h3>
            {result.max_risk_level && (
              <div style={{
                background: `${riskColor}15`,
                border: `1px solid ${riskColor}30`,
                color: riskColor,
                borderRadius: '8px',
                padding: '4px 14px',
                fontSize: '13px',
                fontWeight: 700,
              }}>
                Riesgo: {result.max_risk_level}
              </div>
            )}
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
