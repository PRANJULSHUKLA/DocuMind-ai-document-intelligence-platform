import { useEffect, useRef, useState } from 'react'
import { compareCollection } from '../services/collectionService'

const labels = { supported_agreement: 'Supported agreement', supported_difference: 'Supported difference', possible_contradiction: 'Possible contradiction', missing_information: 'Missing information', insufficient_evidence: 'Insufficient evidence' }

export default function ComparisonPanel({ collectionId, documents, onSourceSelect }) {
  const [selected, setSelected] = useState([])
  const [focus, setFocus] = useState('Key amounts, dates and obligations')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const request = useRef(null)
  useEffect(() => () => request.current?.abort(), [])
  async function compare(event) {
    event.preventDefault(); request.current?.abort()
    const controller = new AbortController(); request.current = controller
    setLoading(true); setError(''); setResult(null)
    try { const data = await compareCollection(collectionId, selected, focus, controller.signal); if (!controller.signal.aborted) setResult(data) }
    catch (failure) { if (!controller.signal.aborted) setError(failure.response?.data?.detail || 'Comparison failed. Please retry.') }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }
  return <section aria-label="Document comparison" className="space-y-4 rounded-2xl border bg-white p-5">
    <h3 className="text-xl font-semibold">Compare documents</h3>
    <p className="text-sm text-zinc-500">Compare explicit currency amounts, dates, and unconditional must/shall obligations in retrieved passages. Different wording alone is never a contradiction.</p>
    <form onSubmit={compare} className="space-y-3">
      <fieldset disabled={loading}><legend>Choose two to five completed documents</legend>{documents.map(doc => { const id = doc._id || doc.file_id; return <label key={id} className="block py-1"><input type="checkbox" checked={selected.includes(id)} disabled={doc.status !== 'completed' || (!selected.includes(id) && selected.length >= 5)} onChange={event => { setSelected(previous => event.target.checked ? [...previous, id] : previous.filter(value => value !== id)); setResult(null) }} /> {doc.filename} · {doc.status}</label> })}</fieldset>
      <label className="block">Comparison focus<input aria-label="Comparison focus" required minLength={2} maxLength={500} disabled={loading} value={focus} onChange={event => { setFocus(event.target.value); setResult(null) }} className="mt-1 block w-full rounded border p-2" /></label>
      <button disabled={loading || selected.length < 2} className="rounded border bg-zinc-900 px-4 py-2 text-white disabled:opacity-40">{loading ? 'Comparing evidence…' : 'Compare selected documents'}</button>
    </form>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {result && <div className="space-y-4" aria-label="Comparison findings">
      <h4 className="font-semibold">Comparison summary</h4>
      <p className="text-sm">{Object.entries(result.summary).map(([label, count]) => `${labels[label]}: ${count}`).join(' · ')}</p>
      {result.limitations.map(text => <p key={text} className="text-xs text-zinc-500">{text}</p>)}
      {result.findings.map((finding, index) => <article key={index} className="space-y-2 rounded-xl border p-4">
        <p className={`text-xs font-semibold uppercase ${finding.classification === 'possible_contradiction' ? 'text-amber-800' : 'text-zinc-500'}`}>{labels[finding.classification]}</p>
        <h4 className="font-semibold">{finding.topic}</h4><p className="text-sm">{finding.explanation}</p>
        <div className="grid gap-3 md:grid-cols-2">{finding.documents.map(doc => <section key={doc.file_id} className="min-w-0 rounded border bg-zinc-50 p-3"><h5 className="break-words font-medium">{doc.filename}</h5>{doc.facts.length ? doc.facts.map((fact, i) => { const source = result.sources.find(row => row.evidence_id === fact.evidence_id); return <div key={i} className="mt-2 text-sm"><p className="font-medium">{fact.values.join(', ')}</p>{source && <button aria-label={`Open comparison ${source.filename} page ${source.page_number}`} className="mt-1 w-full rounded border bg-white p-2 text-left" onClick={() => onSourceSelect(source)}><span className="text-xs text-zinc-500">Page {source.page_number} · View original</span><blockquote className="mt-1 whitespace-pre-wrap">{source.excerpt}</blockquote></button>}</div> }) : <p className="mt-2 text-sm text-zinc-500">Not found in retrieved evidence. Full-document absence is unverified.</p>}</section>)}</div>
      </article>)}
    </div>}
  </section>
}
