import { lazy, Suspense, useEffect, useState } from 'react'
import AiAssistant from './AiAssistant'
const PdfViewer = lazy(() => import('./PdfViewer'))
import { getDocumentView, searchDocument } from '../services/documentService'

export default function DocumentWorkspace({ document, session, onSessionChange }) {
  const [metadata, setMetadata] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const fileId = document.file_id || document._id
  const page = session.page || 1, zoom = session.zoom || 1, tab = session.tab || 'document'
  const update = fields => onSessionChange(previous => ({ ...previous, ...fields }))
  useEffect(() => {
    const controller = new AbortController()
    getDocumentView(fileId, controller.signal).then(value => { if (!controller.signal.aborted) setMetadata(value) })
      .catch(() => { if (!controller.signal.aborted) setError('Unable to open this document. It may be unavailable or access may have changed.') })
    return () => controller.abort()
  }, [fileId, refresh])
  useEffect(() => {
    if (query.trim().length < 2 || metadata?.status !== 'completed') { return }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setSearching(true)
      searchDocument(fileId, query.trim(), controller.signal).then(value => {
        if (!controller.signal.aborted) { setResults(value.results); setError('') }
      }).catch(() => { if (!controller.signal.aborted) setError('Document search is unavailable. Please retry.') })
        .finally(() => { if (!controller.signal.aborted) setSearching(false) })
    }, 300)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, fileId, metadata?.status])
  async function selectSource(source) {
    try {
      const current = await getDocumentView(fileId)
      if (source.file_id !== fileId || !source.page_number || source.page_number < 1 ||
          (current.total_pages && source.page_number > current.total_pages) ||
          (source.processing_run_id || null) !== (current.processing_run_id || null) ||
          (source.content_sha256 || null) !== (current.content_sha256 || null)) {
        throw new Error('This source belongs to another document version or its page is unavailable.')
      }
      setMetadata(current); setError('')
      update({ page: source.page_number, source, tab: 'document' })
    } catch (failure) { setError(failure.message || 'Source is unavailable.') }
  }
  const stale = session.source && metadata && ((session.source.processing_run_id || null) !== (metadata.processing_run_id || null) || (session.source.content_sha256 || null) !== (metadata.content_sha256 || null))
  return <div className="space-y-4">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs uppercase tracking-widest text-zinc-500">Read &amp; Ask</p><h2 className="text-xl font-semibold">{document.filename}</h2></div>
      <button className="rounded-xl border bg-white px-4 py-2 text-sm" onClick={() => { setMetadata(null); setError(''); setRefresh(value => value + 1) }}>Refresh document</button>
    </header>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {metadata && <p className="text-xs text-zinc-500">{metadata.provenance === 'verified' ? 'Original linked to this processing version by SHA-256.' : 'Legacy provenance: compare passages manually; historical OCR bytes are not cryptographically verified.'}</p>}
    <div className="flex gap-2 lg:hidden" role="tablist" aria-label="Reading panels">{['document', 'chat', 'evidence'].map(name => <button key={name} role="tab" aria-selected={tab === name} onClick={() => update({ tab: name })} className={`rounded-xl border px-4 py-2 capitalize ${tab === name ? 'bg-zinc-900 text-white' : 'bg-white'}`}>{name}</button>)}</div>
    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,1fr)]">
      <div className={`${tab === 'document' ? '' : 'hidden'} min-w-0 space-y-3 lg:block`}>
        {metadata ? metadata.original_available ? <Suspense fallback={<p role="status">Loading PDF reader…</p>}><PdfViewer key={fileId + metadata.version} fileId={fileId} metadata={metadata} page={page} zoom={zoom} onPage={value => update({ page: value })} onZoom={value => update({ zoom: value })} /></Suspense> : <p role="status" className="rounded-2xl border bg-white p-8">Original PDF is unavailable. Existing analysis is retained.</p> : <p role="status">Loading document…</p>}
        <label className="block text-sm">Search extracted text<input aria-label="Search document" maxLength={200} disabled={metadata?.status !== 'completed'} value={query} onChange={event => { setQuery(event.target.value); setResults([]); setSearching(false) }} placeholder="Find an amount, date, or phrase" className="mt-1 w-full rounded-xl border bg-white p-3" /></label>
        {metadata?.status !== 'completed' && <p className="text-sm text-zinc-500">Processing: {metadata?.status || document.status}. Search and questions are available after completion.</p>}
        {searching && <p role="status">Searching extracted text…</p>}
        {!searching && query.trim().length >= 2 && !results.length && <p className="text-sm text-zinc-500">No extracted-text matches.</p>}
        {results.map(source => <button key={source.source_id || source.chunk_index} onClick={() => selectSource(source)} className="block w-full rounded-xl border bg-white p-3 text-left text-sm"><strong>Page {source.page_number}</strong><p className="mt-1 whitespace-pre-wrap text-zinc-600">{source.excerpt}</p></button>)}
      </div>
      <div className="min-w-0 space-y-3">
        <section aria-label="Selected evidence" className={`${tab === 'evidence' || (tab === 'document' && session.source) ? '' : 'hidden'} rounded-2xl border bg-white p-4 lg:block`}>
          <h3 className="font-semibold">Evidence passage</h3>{stale && <p role="alert" className="mt-2 text-sm text-amber-700">This passage is from an earlier document version. Ask again for current evidence.</p>}
          {session.source ? <><p className="mt-1 text-xs text-zinc-500">{session.source.filename} · Page {session.source.page_number}</p><blockquote className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap border-l-2 border-zinc-300 pl-3 text-sm leading-6">{session.source.excerpt || 'This older answer did not retain an exact passage. Ask again to obtain an evidence passage.'}</blockquote><button onClick={() => update({ tab: 'chat' })} className="mt-3 text-sm underline">Back to answer</button></> : <p className="mt-2 text-sm text-zinc-500">Choose an answer source to inspect the passage beside its original PDF page.</p>}
          <p className="mt-2 text-xs text-zinc-400">Extracted text may differ from the page. No OCR coordinate highlights are inferred.</p>
        </section>
        <div className={`${tab === 'chat' ? '' : 'hidden'} lg:block`}>
          {metadata?.status === 'completed' ? <AiAssistant fileId={fileId} filename={document.filename} conversation={session} onConversationChange={onSessionChange} onSourceSelect={selectSource} /> : <p className="rounded-2xl border bg-white p-6 text-sm">The assistant becomes available after processing completes.</p>}
        </div>
      </div>
    </div>
  </div>
}
