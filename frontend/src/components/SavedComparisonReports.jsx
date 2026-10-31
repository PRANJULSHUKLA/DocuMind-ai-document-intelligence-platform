import { useEffect, useState } from 'react'
import { listReports, readReport, deleteReport, downloadReport } from '../services/reportService'

export default function SavedComparisonReports({ onSourceSelect }) {
  const [rows, setRows] = useState([])
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function refresh() {
    const result = await listReports()
    if (!Array.isArray(result)) throw new Error('Invalid report-list response.')
    setRows(result)
  }
  useEffect(() => {
    let active = true
    listReports().then(result => { if (active && Array.isArray(result)) setRows(result) }).catch(() => { if (active) setError('Saved reports are unavailable. Refresh to retry.') })
    return () => { active = false }
  }, [])
  async function action(operation) {
    setBusy(true); setError('')
    try { await operation() }
    catch (failure) { setError(failure.response?.data?.detail || failure.message || 'Report action failed.') }
    finally { setBusy(false) }
  }
  return <section aria-label="Saved comparison reports" className="space-y-3 rounded-xl border bg-white p-4">
    <h3 className="text-xl font-semibold">Saved comparison reports</h3>
    <p className="text-sm text-zinc-500">Snapshots stay until explicitly deleted. Source or collection deletion does not delete a report. If source access is lost, content and exports are withheld. Exports make no model calls.</p>
    <button disabled={busy} onClick={() => action(refresh)} className="rounded border p-2">Refresh saved reports</button>
    {error && <p role="alert">{error}</p>}
    {rows.map(row => <div className="flex flex-wrap gap-2" key={row.id}><button disabled={busy} onClick={() => action(async () => setReport(await readReport(row.id)))} className="rounded border p-2">Open report: {row.title}</button><button disabled={busy} onClick={() => { if (window.confirm('Delete this saved report? Original documents will be kept.')) action(async () => { await deleteReport(row.id); if (report?.id === row.id) setReport(null); await refresh() }) }} className="rounded border p-2">Delete report: {row.title}</button></div>)}
    {!rows.length && <p>No saved reports loaded.</p>}
    {report && <article className="space-y-3 rounded border p-4"><h4 className="font-semibold">{report.title}</h4><p>Saved {report.created_at} · {report.snapshot.method}</p>
      <p role="status" className={report.stale ? 'text-amber-800' : ''}>{report.stale ? 'STALE: source revisions changed. Review the originals before relying on this snapshot.' : 'Source revisions matched when this report was opened. Exports check again.'}</p>
      <div className="flex gap-2">{['json', 'pdf'].map(format => <button key={format} disabled={busy} className="rounded border p-2" onClick={() => action(() => downloadReport(report.id, format))}>Export {format.toUpperCase()}</button>)}</div>
      {report.snapshot.limitations.map((text, index) => <p key={index} className="text-sm text-zinc-500">{text}</p>)}
      {report.snapshot.findings.map((finding, index) => <div key={index}><h5 className="font-medium">{finding.topic} · {finding.classification.replaceAll('_', ' ')}</h5><p>{finding.explanation}</p></div>)}
      <details><summary>Saved evidence passages</summary>{report.snapshot.sources.map(source => <button key={source.evidence_id} className="my-2 block w-full rounded border p-2 text-left" onClick={() => onSourceSelect(source)}>{source.filename} · Page {source.page_number}<blockquote>{source.excerpt}</blockquote></button>)}</details>
    </article>}
  </section>
}
