import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
  Satellite, Leaf, AlertTriangle, Sun, Telescope, Zap,
  Activity, Database, Settings, ChevronRight, Radio
} from 'lucide-react'

import Dashboard from './pages/Dashboard'
import Agricultural from './pages/Agricultural'
import Disasters from './pages/Disasters'
import SpaceWeather from './pages/SpaceWeather'
import Educational from './pages/Educational'
import NeoWs from './pages/NeoWs'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: Activity, exact: true },
  { path: '/agricultural', label: 'Monitoreo Agrícola', icon: Leaf, agent: 'agent1' },
  { path: '/disasters', label: 'Desastres Naturales', icon: AlertTriangle, agent: 'agent2' },
  { path: '/space-weather', label: 'Clima Espacial', icon: Sun, agent: 'agent3' },
  { path: '/educational', label: 'Divulgación', icon: Telescope, agent: 'agent4' },
  { path: '/neows', label: 'Asteroides NeoWs', icon: Zap, agent: 'agent5' },
]

function Sidebar() {
  const location = useLocation()

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>🛰️ Agentes IA</h1>
        <p>Hackathon · Junio 2026</p>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-label">Sistema</div>
        {NAV_ITEMS.slice(0, 1).map(item => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon className="nav-icon" size={18} />
              {item.label}
            </NavLink>
          )
        })}

        <div className="nav-label" style={{ marginTop: '12px' }}>Agentes Cognitivos</div>
        {NAV_ITEMS.slice(1).map(item => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`nav-item ${item.agent} ${isActive ? 'active' : ''}`}
            >
              <Icon className="nav-icon" size={18} />
              {item.label}
            </NavLink>
          )
        })}

        <div className="nav-label" style={{ marginTop: '12px' }}>Infraestructura</div>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="nav-item"
        >
          <Database size={18} className="nav-icon" />
          API Docs (Swagger)
        </a>
        <a
          href="http://localhost:8000/redoc"
          target="_blank"
          rel="noreferrer"
          className="nav-item"
        >
          <Settings size={18} className="nav-icon" />
          ReDoc
        </a>
      </nav>

      <div className="sidebar-footer">
        <div className="status-indicator">
          <span className="status-dot"></span>
          Sistema Operacional
        </div>
        <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
          LangGraph + FastAPI + PostgreSQL
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agricultural" element={<Agricultural />} />
            <Route path="/disasters" element={<Disasters />} />
            <Route path="/space-weather" element={<SpaceWeather />} />
            <Route path="/educational" element={<Educational />} />
            <Route path="/neows" element={<NeoWs />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
