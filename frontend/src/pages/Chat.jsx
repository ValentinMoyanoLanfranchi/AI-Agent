import { useState, useRef, useEffect } from 'react'
import { Sparkles, Send, FileText, Brain } from 'lucide-react'
import { consult } from '../api/agentsApi'

const SUGGESTIONS = [
  '¿Hay riesgo GPS para la maquinaria agrícola esta semana?',
  '¿Cómo está el estado de los cultivos en las zonas monitoreadas?',
  '¿Hay algún asteroide potencialmente peligroso cerca?',
  'Comparando clima espacial y asteroides, ¿qué es más urgente para el agro y por qué?',
]

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || loading) return
    const history = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setInput('')
    setLoading(true)
    try {
      const data = await consult({ question: q, history })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || '(sin respuesta)',
        citations: data.citations || [],
        model: data.model_used,
        retrieval: data.retrieval_mode,
        grounded: data.grounded,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Error: ' + (err.response?.data?.detail || err.message),
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    flex: 1, padding: '13px 16px', borderRadius: '10px',
    border: '1px solid var(--border-color)', background: 'var(--bg-primary)',
    color: 'var(--text-primary)', fontSize: '14px', outline: 'none',
  }

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)' }}>
      <div className="page-header">
        <h2>💬 Consultor IA</h2>
        <p>Agente Consultor · Microsoft Foundry IQ + gpt-5.4 (razonador) · respuestas grounded con fuentes citadas</p>
      </div>

      <div ref={scrollRef} className="card" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '16px' }}>
        {messages.length === 0 && (
          <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '560px' }}>
            <Sparkles size={40} style={{ color: '#8b5cf6', marginBottom: '12px' }} />
            <h3 style={{ marginBottom: '8px', fontFamily: 'var(--font-display)' }}>Preguntale al sistema</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '20px' }}>
              El Consultor razona sobre los reportes de los 5 agentes recuperados de <strong>Foundry IQ</strong>,
              y responde con <strong>fuentes citadas</strong> (sin alucinar).
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => send(s)}
                  style={{ cursor: 'pointer', fontSize: '13px', padding: '8px 12px', borderRadius: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', transition: 'var(--transition)' }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '80%', padding: '14px 16px', borderRadius: '14px',
              background: m.role === 'user' ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'var(--bg-primary)',
              color: m.role === 'user' ? '#fff' : 'var(--text-primary)',
              border: m.role === 'user' ? 'none' : '1px solid var(--border-color)',
              whiteSpace: 'pre-wrap', lineHeight: 1.55, fontSize: '14px',
            }}>
              {m.content}
              {m.role === 'assistant' && !m.error && m.citations?.length > 0 && (
                <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <FileText size={12} /> Fuentes (Foundry IQ) · {m.model}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {m.citations.map((c, j) => (
                      <span key={j} className="badge badge-minimal" title={c.snippet || ''} style={{ fontSize: '11px' }}>
                        {c.source}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{ padding: '14px 16px', borderRadius: '14px', background: 'var(--bg-primary)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-secondary)', fontSize: '14px' }}>
              <Brain size={16} style={{ color: '#8b5cf6' }} /> El razonador está pensando...
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '10px' }}>
        <input
          style={inputStyle}
          placeholder="Escribí tu pregunta sobre el estado del sistema..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') send() }}
          disabled={loading}
        />
        <button className="btn btn-primary" onClick={() => send()} disabled={loading || !input.trim()}
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
          {loading ? <span className="spinner" /> : <Send size={16} />}
          Enviar
        </button>
      </div>
    </div>
  )
}
