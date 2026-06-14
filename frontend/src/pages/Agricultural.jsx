import { useState } from 'react'
import { Leaf, PlayCircle, Map } from 'lucide-react'
import { runAgricultural } from '../api/agentsApi'
import MarkdownReport from '../components/MarkdownReport'

const REGIONS = [
  { value: '', label: 'Todas las zonas' },
  { value: 'ARG-BA-PAMPA', label: '🇦🇷 Pampa Húmeda — Buenos Aires' },
  { value: 'ARG-COR-AGRO', label: '🇦🇷 Córdoba — Zona Norte' },
  { value: 'BRA-MT-CERRADO', label: '🇧🇷 Mato Grosso — Cerrado' },
  { value: 'URY-SORIANO', label: '🇺🇾 Uruguay — Soriano' },
  { value: 'CHI-ARAUCANIA', label: '🇨🇱 Chile — Araucanía' },
]

function SeverityBadge({ severity = 'MINIMAL' }) {
  const cls = `badge badge-${(severity || 'minimal').toLowerCase()}`
  const emojis = { CRITICAL: '🚨', HIGH: '⚠️', MEDIUM: '⚡', LOW: 'ℹ️', MINIMAL: '✅', NONE: '✅' }
  return <span className={cls}>{emojis[severity] || '📊'} {severity}</span>
}

export default function Agricultural() {
  const [region, setRegion] = useState('')
  const [daysBack, setDaysBack] = useState(7)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await runAgricultural({
        region_code: region || null,
        days_back: daysBack,
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
        <h2>🌱 Monitoreo Agrícola Core</h2>
        <p>Agente 1 — Ingeniero Agrónomo Senior · NDVI + NASA Earthdata + NASA POWER</p>
      </div>

      {/* Config Card */}
      <div className="card agent1" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '20px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Map size={18} style={{ color: '#10b981' }} />
          Configuración del Análisis
        </h3>

        <div className="grid-3" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Zona Agrícola</label>
            <select
              className="form-select"
              value={region}
              onChange={e => setRegion(e.target.value)}
              id="select-region"
            >
              {REGIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Ventana Temporal (días)</label>
            <input
              type="number"
              className="form-input"
              value={daysBack}
              onChange={e => setDaysBack(Number(e.target.value))}
              min={1} max={90}
              id="input-days-back"
            />
          </div>

          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label className="form-label">&nbsp;</label>
            <button
              className="btn btn-primary"
              onClick={handleRun}
              disabled={loading}
              id="btn-run-agricultural"
            >
              {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
              {loading ? 'Analizando...' : 'Ejecutar Agente 1'}
            </button>
          </div>
        </div>

        {/* Info about the agent */}
        <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '10px', padding: '14px 16px' }}>
          <p style={{ fontSize: '13px', color: '#34d399', fontWeight: 600, marginBottom: '6px' }}>
            🧠 Mecánica del Agente (Modelo Híbrido)
          </p>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            El proceso determinista calcula NDVI = (NIR - Red) / (NIR + Red) vía NASA Earthdata.
            El LLM <strong>no procesa imagen cruda</strong> — solo interpreta la matriz estructurada de variaciones
            numéricas e histórico de 5 años. Detecta anomalías y consulta alertas GPS del Agente de Clima Espacial.
          </p>
        </div>
      </div>

      {/* Result */}
      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px', width: '32px', height: '32px' }} />
          <p style={{ color: 'var(--text-secondary)' }}>El Agente Agrónomo está analizando los datos NDVI...</p>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>Esto puede tomar 15-60 segundos</p>
        </div>
      )}

      {result && (
        <div className="card animate-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Leaf size={18} style={{ color: '#10b981' }} />
              Reporte del Agente Agrónomo
            </h3>
            {result.severity && <SeverityBadge severity={result.severity} />}
          </div>

          {result.status === 'error' ? (
            <div style={{ background: 'rgba(220, 38, 38, 0.1)', border: '1px solid rgba(220,38,38,0.2)', borderRadius: '10px', padding: '16px', color: '#f87171' }}>
              ⚠️ Error: {result.error}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', flexWrap: 'wrap' }}>
                <div className="badge badge-minimal">🌿 Zona: {result.region_code || 'Todas'}</div>
                <div className="badge badge-low">🕐 {result.generated_at?.slice(0, 19).replace('T', ' ')} UTC</div>
              </div>
              <MarkdownReport>{result.report}</MarkdownReport>
            </>
          )}
        </div>
      )}
    </div>
  )
}
