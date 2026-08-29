import { useState } from 'react'
import { useDisponibles, useJob, useJobs, useLanzarJob } from './hooks'
import { useUI } from '../../store'

export default function IngestaPage() {
  const disp = useDisponibles()
  const jobs = useJobs()
  const lanzar = useLanzarJob()
  const { jobActivo, setJob } = useUI()
  const job = useJob(jobActivo)
  const [sel, setSel] = useState<Set<string>>(new Set())

  const toggle = (n: string) =>
    setSel((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x })

  async function lanzarJob(todos: boolean) {
    const nombres = todos ? undefined : [...sel]
    if (!todos && nombres!.length === 0) return
    const r = await lanzar.mutateAsync(nombres)
    setJob(r.job_id)
  }

  if (disp.isLoading) return <p>Cargando archivos…</p>
  if (disp.error) return <div className="alert alert-danger">Error: {String(disp.error)}</div>

  return (
    <div className="row g-3">
      <div className="col-lg-8">
        <div className="d-flex gap-2 mb-2">
          <button className="btn btn-primary btn-sm" disabled={lanzar.isPending || sel.size === 0} onClick={() => lanzarJob(false)}>
            Ingerir seleccionados ({sel.size})
          </button>
          <button className="btn btn-outline-secondary btn-sm" disabled={lanzar.isPending} onClick={() => lanzarJob(true)}>
            Ingerir todos
          </button>
        </div>
        <table className="table table-sm table-hover align-middle">
          <thead><tr><th></th><th>Archivo</th><th>Tipo</th><th>Fecha</th><th>Ingerido</th></tr></thead>
          <tbody>
            {disp.data!.map((a) => (
              <tr key={a.nombre}>
                <td><input type="checkbox" checked={sel.has(a.nombre)} onChange={() => toggle(a.nombre)} /></td>
                <td className="text-truncate" style={{ maxWidth: 360 }} title={a.nombre}>{a.nombre}</td>
                <td><span className={`badge ${a.tipo === 'NEW' ? 'bg-success' : 'bg-secondary'}`}>{a.tipo}</span></td>
                <td>{a.fecha ?? '—'}</td>
                <td>{a.ya_ingerido ? '✓' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="col-lg-4">
        <h6>Progreso del job</h6>
        {job.data ? (
          <div className="card card-body">
            <div>Job #{job.data.job_id} — <b>{job.data.estado}</b></div>
            <div className="progress my-2" style={{ height: 22 }}>
              <div className="progress-bar" style={{ width: `${(job.data.procesados / Math.max(job.data.total, 1)) * 100}%` }}>
                {job.data.procesados}/{job.data.total}
              </div>
            </div>
            {job.data.errores > 0 && <div className="text-danger">Errores: {job.data.errores}</div>}
          </div>
        ) : <p className="text-muted">Sin job activo.</p>}

        <h6 className="mt-3">Historial</h6>
        <ul className="list-group">
          {jobs.data?.slice(0, 8).map((j) => (
            <li key={j.job_id} className="list-group-item d-flex justify-content-between" role="button" onClick={() => setJob(j.job_id)}>
              <span>#{j.job_id}</span><span>{j.estado}</span><span>{j.procesados}/{j.total}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
