import { useEffect, useState } from 'react'
import AiAssistant from './AiAssistant'
import DocumentWorkspace from './DocumentWorkspace'
import ComparisonPanel from './ComparisonPanel'
import { listCollections, createCollection, editCollection, deleteCollection, askCollection } from '../services/collectionService'
import { getDocuments, getDocumentView, uploadDocument } from '../services/documentService'

export default function CollectionsWorkspace() {
  const [collections, setCollections] = useState([])
  const [documents, setDocuments] = useState([])
  const [activeId, setActiveId] = useState('')
  const [name, setName] = useState('')
  const [selected, setSelected] = useState([])
  const [sessions, setSessions] = useState({})
  const [uploads, setUploads] = useState([])
  const [reader, setReader] = useState(null)
  const [readingSession, setReadingSession] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = collections.find(row => row.id === activeId)
  const members = documents.filter(doc => active?.file_ids.includes(doc._id || doc.file_id))
  async function refresh() {
    const [rows, files] = await Promise.all([listCollections(), getDocuments()])
    setCollections(rows); setDocuments(files)
  }
  useEffect(() => {
    let cancelled = false
    const load = () => Promise.all([listCollections(), getDocuments()]).then(([rows, files]) => {
      if (!cancelled) { setCollections(rows); setDocuments(files) }
    }).catch(() => { if (!cancelled) setError('Unable to refresh collections. Please retry.') })
    load()
    const timer = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])
  async function action(operation) {
    setBusy(true); setError('')
    try { await operation(); await refresh() }
    catch (failure) { setError(failure.response?.data?.detail || failure.message || 'Request failed. Refresh and retry.') }
    finally { setBusy(false) }
  }
  async function membership(id, checked) {
    const ids = checked ? [...active.file_ids, id] : active.file_ids.filter(value => value !== id)
    await action(() => editCollection(active.id, { revision: active.revision, file_ids: ids }))
    setSelected(previous => previous.filter(value => checked || value !== id))
  }
  async function bulkUpload(files) {
    if (!files.length) return
    if (files.length > 10) { setError('Upload up to 10 PDFs at a time.'); return }
    setBusy(true); setError(''); setUploads([])
    // Independent requests preserve accepted uploads when another file fails.
    for (const [index, file] of files.entries()) {
      setUploads(previous => [...previous, { index, name: file.name, status: 'uploading' }])
      try {
        const result = await uploadDocument(file)
        setUploads(previous => previous.map(row => row.index === index ? { ...row, status: result.status || 'queued' } : row))
      } catch (failure) {
        setUploads(previous => previous.map(row => row.index === index ? { ...row, status: 'failed', message: failure.response?.data?.detail || 'Upload failed. Check Documents before retrying if acceptance is uncertain.' } : row))
      }
    }
    try { await refresh() } catch { setError('Uploads submitted. Refresh document statuses.') }
    setBusy(false)
  }
  async function openSource(source) {
    try {
      const manifest = await getDocumentView(source.file_id)
      if ((source.processing_run_id || null) !== (manifest.processing_run_id || null) || (source.content_sha256 || null) !== (manifest.content_sha256 || null) || !Number.isInteger(source.page_number) || source.page_number < 1 || source.page_number > manifest.total_pages) throw new Error('Source version changed. Ask again for current evidence.')
      setReadingSession({ page: source.page_number, source, tab: 'document' })
      setReader({ file_id: source.file_id, filename: source.filename })
    } catch (failure) { setError(failure.message || 'Unable to open source.') }
  }
  return <div className="space-y-5">
    <h2 className="text-2xl font-semibold">Collections</h2>
    <p className="text-sm text-zinc-500">Organize up to 10 documents per collection. Originals remain in Documents when removed.</p>
    {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3">{error}</p>}
    {reader && <section className="space-y-3"><button className="rounded border p-2" onClick={() => setReader(null)}>Back to collection</button><DocumentWorkspace key={reader.file_id} document={reader} session={readingSession} onSessionChange={setReadingSession} /></section>}
    <div className={reader ? 'hidden' : 'space-y-4'}>
      <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); action(async () => { const row = await createCollection(name); setActiveId(row.id); setSelected([]); setName('') }) }}>
        <input aria-label="New collection name" required maxLength={100} value={name} onChange={event => setName(event.target.value)} className="rounded border bg-white p-2" placeholder="New collection name" />
        <button disabled={busy || !name.trim()} className="rounded border bg-white p-2">Create collection</button>
      </form>
      <label className="block">Active collection <select aria-label="Active collection" value={activeId} onChange={event => { setActiveId(event.target.value); setSelected([]) }} className="rounded border bg-white p-2"><option value="">Choose a collection</option>{collections.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      {!collections.length && <p>No collections yet. Create one to start.</p>}
      {active && <>
        <form className="flex gap-2" key={`rename:${active.id}:${active.revision}`} onSubmit={event => { event.preventDefault(); const value = new FormData(event.currentTarget).get('name'); action(() => editCollection(active.id, { revision: active.revision, name: value })) }}>
          <input aria-label="Rename collection" name="name" required maxLength={100} defaultValue={active.name} className="rounded border p-2" /><button disabled={busy} className="rounded border p-2">Rename</button>
          <button type="button" disabled={busy} onClick={() => { if (window.confirm('Delete this collection? Original documents will be kept.')) action(async () => { await deleteCollection(active.id); setActiveId('') }) }} className="rounded border p-2">Delete collection</button>
        </form>
        <fieldset className="rounded-xl border bg-white p-4"><legend>Collection membership</legend>{documents.length ? documents.map(doc => { const id = doc._id || doc.file_id; return <label key={id} className="block py-1"><input type="checkbox" checked={active.file_ids.includes(id)} disabled={busy || (!active.file_ids.includes(id) && active.file_ids.length >= 10)} onChange={event => membership(id, event.target.checked)} /> {doc.filename} <span className="text-sm text-zinc-500">· {doc.status}</span></label> }) : <p>Upload PDFs below or from Documents.</p>}</fieldset>
        {!members.length && <p>This collection is empty. Add existing documents above.</p>}
        <fieldset className="rounded-xl border bg-white p-4"><legend>Question context</legend><p className="text-sm text-zinc-500">Leave all unchecked to ask across all completed members. Processing and failed documents are skipped.</p>{members.map(doc => { const id = doc._id || doc.file_id; return <label className="block py-1" key={id}><input type="checkbox" disabled={doc.status !== 'completed'} checked={selected.includes(id)} onChange={event => setSelected(previous => event.target.checked ? [...previous, id] : previous.filter(value => value !== id))} /> {doc.filename} · {doc.status}</label> })}</fieldset>
        <ComparisonPanel key={`comparison:${active.id}:${active.revision}`} collectionId={active.id} documents={members} onSourceSelect={openSource} />
        {members.some(doc => doc.status === 'completed') ? <AiAssistant key={active.id} fileId={active.id} filename={active.name} conversation={sessions[active.id] || {}} onConversationChange={updater => setSessions(previous => ({ ...previous, [active.id]: updater(previous[active.id] || {}) }))} askQuestion={(id, question) => askCollection(id, question, selected.length ? selected : undefined)} onSourceSelect={openSource} /> : <p>Questions become available when at least one member completes processing.</p>}
      </>}
      <section className="rounded-xl border bg-white p-4"><label className="block font-medium">Upload multiple PDFs<input aria-label="Upload multiple PDFs" type="file" accept="application/pdf,.pdf" multiple disabled={busy} className="mt-2 block" onChange={event => { bulkUpload(Array.from(event.target.files)); event.target.value = '' }} /></label><p className="mt-2 text-sm text-zinc-500">Uploads appear in Documents; add them to a collection above. Each file processes independently.</p>{uploads.map(row => <p key={row.index} role="status" className="mt-2 text-sm">{row.name}: {row.status} {row.message}</p>)}</section>
    </div>
  </div>
}
