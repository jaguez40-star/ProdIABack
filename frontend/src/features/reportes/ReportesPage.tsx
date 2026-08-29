import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

export default function ReportesPage() {
  const cob = useQuery({ queryKey: ['cobertura'], queryFn: api.cobertura })
  if (cob.isLoading) return <p>Cargando…</p>
  if (cob.error) return <div className="alert alert-danger">Error: {String(cob.error)}</div>
  return (
    <table className="table table-sm table-striped">
      <thead><tr><th>Reporte</th><th>Tipo</th><th>ECP mes</th><th>ECP día</th><th>Filiales</th></tr></thead>
      <tbody>
        {cob.data!.map((r) => (
          <tr key={r.reporte_id}>
            <td>{r.reporte_id}</td><td>{r.tipo_archivo ?? '—'}</td>
            <td>{r.ecp_mes}</td><td>{r.ecp_dia}</td><td>{r.filiales}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
