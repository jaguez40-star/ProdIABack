import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export default function KpisPage() {
  const [fecha, setFecha] = useState('2024-10-03')
  const k = useQuery({ queryKey: ['kpi-dia', fecha], queryFn: () => api.produccionDia(fecha), enabled: !!fecha })
  const max = Math.max(1, ...(k.data?.map((d) => d.vol_estimado ?? 0) ?? [0]))
  return (
    <div>
      <div className="mb-3">
        <label className="form-label">Fecha (YYYY-MM-DD)</label>
        <input className="form-control" style={{ maxWidth: 220 }} value={fecha} onChange={(e) => setFecha(e.target.value)} />
      </div>
      {k.isLoading && <p>Cargando…</p>}
      {k.error && <div className="alert alert-danger">Error: {String(k.error)}</div>}
      {k.data?.length === 0 && <p className="text-muted">Sin datos para esa fecha.</p>}
      {k.data?.map((d) => (
        <div key={d.tipo_producto} className="mb-2">
          <div className="d-flex justify-content-between"><span>{d.tipo_producto}</span><span>{(d.vol_estimado ?? 0).toLocaleString()}</span></div>
          <div className="progress" style={{ height: 20 }}>
            <div className="progress-bar bg-info" style={{ width: `${((d.vol_estimado ?? 0) / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}
