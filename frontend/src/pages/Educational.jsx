import { useState } from 'react'
import { Telescope, PlayCircle, Star } from 'lucide-react'
import { runEducational } from '../api/agentsApi'

const PROFILES = [
  { value: 'NIÑO', label: '👶 Niño (8-12 años)', desc: 'Analogías cotidianas, tono lúdico, frases simples' },
  { value: 'ESTUDIANTE', label: '📚 Estudiante (secundario/universitario)', desc: 'Términos técnicos explicados, tono didáctico' },
  { value: 'EXPERTO', label: '🔬 Experto (científico/investigador)', desc: 'Terminología completa, valores exactos, rigor académico' },
  { value: 'GENERAL', label: '🌍 Público General', desc: 'Estilo Carl Sagan — accesible + riguroso' },
]

const CITIES = [
  { value: 'Buenos Aires', label: '🇦🇷 Buenos Aires', lat: -34.6037, lon: -58.3816 },
  { value: 'Santiago', label: '🇨🇱 Santiago', lat: -33.4489, lon: -70.6693 },
  { value: 'Montevideo', label: '🇺🇾 Montevideo', lat: -34.9011, lon: -56.1645 },
  { value: 'São Paulo', label: '🇧🇷 São Paulo', lat: -23.5505, lon: -46.6333 },
  { value: 'Lima', label: '🇵🇪 Lima', lat: -12.0464, lon: -77.0428 },
]

export default function Educational() {
  const [profile, setProfile] = useState('GENERAL')
  const [city, setCity] = useState('Buenos Aires')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const selectedCity = CITIES.find(c => c.value === city) || CITIES[0]

  const handleRun = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await runEducational({
        demographic_profile: profile,
        user_location: city,
        user_latitude: selectedCity.lat,
        user_longitude: selectedCity.lon,
      })
      setResult(data)
    } catch (err) {
      setResult({ status: 'error', error: err.response?.data?.detail || err.message })
    } finally {
      setLoading(false)
    }
  }

  const selectedProfile = PROFILES.find(p => p.value === profile)

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>🔭 Divulgación Científica</h2>
        <p>Agente 4 — Divulgador Científico Internacional · NASA APOD + ISS Open Notify</p>
      </div>

      <div className="card agent4" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontFamily: 'var(--font-display)', marginBottom: '20px', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Star size={18} style={{ color: '#8b5cf6' }} />
          Perfil del Receptor
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px', marginBottom: '20px' }}>
          {PROFILES.map(p => (
            <div
              key={p.value}
              onClick={() => setProfile(p.value)}
              style={{
                cursor: 'pointer',
                padding: '14px',
                borderRadius: '10px',
                border: profile === p.value ? '2px solid #8b5cf6' : '1px solid var(--border-color)',
                background: profile === p.value ? 'rgba(139, 92, 246, 0.1)' : 'var(--bg-primary)',
                transition: 'var(--transition)',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '4px' }}>{p.label}</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{p.desc}</div>
            </div>
          ))}
        </div>

        <div className="grid-3" style={{ marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Ciudad (para pasos ISS)</label>
            <select className="form-select" value={city} onChange={e => setCity(e.target.value)} id="select-city">
              {CITIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div></div>
          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <label className="form-label">&nbsp;</label>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading} id="btn-run-educational"
              style={{ background: 'linear-gradient(135deg, #7c3aed, #8b5cf6)' }}>
              {loading ? <span className="spinner" /> : <PlayCircle size={16} />}
              {loading ? 'Generando...' : 'Ejecutar Agente 4'}
            </button>
          </div>
        </div>

        <div style={{ background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139,92,246,0.15)', borderRadius: '10px', padding: '14px 16px' }}>
          <p style={{ fontSize: '13px', color: '#a78bfa', fontWeight: 600, marginBottom: '6px' }}>🧠 Narrativa Adaptativa</p>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Detecta perfil demográfico para reescribir la explicación APOD del día.
            Claude 3.5 Sonnet en modo creativo (temperatura 0.4) genera explicaciones únicas adaptadas.
            Cruza ubicación del usuario para notificar pasos visuales de la ISS en su horizonte.
          </p>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '48px' }}>
          <div className="spinner" style={{ margin: '0 auto 16px', width: '32px', height: '32px', borderTopColor: '#8b5cf6' }} />
          <p style={{ color: 'var(--text-secondary)' }}>El Divulgador Científico está preparando el contenido del día...</p>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>Perfil: {selectedProfile?.label}</p>
        </div>
      )}

      {result && (
        <div className="card animate-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Telescope size={18} style={{ color: '#8b5cf6' }} />
              Astronomía del Día
            </h3>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span className="badge badge-low">🏙️ {result.location}</span>
              <span className="badge badge-minimal">👤 {result.profile}</span>
            </div>
          </div>

          {result.status === 'error' ? (
            <div style={{ background: 'rgba(220, 38, 38, 0.1)', border: '1px solid rgba(220,38,38,0.2)', borderRadius: '10px', padding: '16px', color: '#f87171' }}>
              ⚠️ Error: {result.error}
            </div>
          ) : (
            <div className="report-container">{result.report}</div>
          )}
        </div>
      )}
    </div>
  )
}
