import { useUI } from './store'
import IngestaPage from './features/ingesta/IngestaPage'
import ReportesPage from './features/reportes/ReportesPage'
import KpisPage from './features/kpis_prod/KpisPage'

const TABS = [
  { id: 'ingesta', label: 'Ingesta' },
  { id: 'reportes', label: 'Reportes' },
  { id: 'kpis', label: 'KPIs Producción' },
] as const

export default function App() {
  const { tab, setTab } = useUI()
  return (
    <div className="container-fluid py-3">
      <header className="d-flex align-items-center mb-3">
        <h4 className="me-4 mb-0">Robustez V2.0 — Ingesta</h4>
        <ul className="nav nav-pills">
          {TABS.map((t) => (
            <li className="nav-item" key={t.id}>
              <button className={`nav-link ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>{t.label}</button>
            </li>
          ))}
        </ul>
      </header>
      {tab === 'ingesta' && <IngestaPage />}
      {tab === 'reportes' && <ReportesPage />}
      {tab === 'kpis' && <KpisPage />}
    </div>
  )
}
