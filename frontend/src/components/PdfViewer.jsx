import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import 'react-pdf/dist/Page/TextLayer.css'
import { getDocumentPdf } from '../services/documentService'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

export default function PdfViewer({ fileId, metadata, page, zoom, onPage, onZoom }) {
  const [bytes, setBytes] = useState(null)
  const [error, setError] = useState('')
  const [pages, setPages] = useState(0)
  const [width, setWidth] = useState(600)
  const container = useRef(null)
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(200, entry.contentRect.width - 24)))
    if (container.current) observer.observe(container.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    getDocumentPdf(fileId, metadata.version, controller.signal).then(async data => {
      if (metadata.content_sha256) {
        const digest = await crypto.subtle.digest('SHA-256', data)
        const hex = [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, '0')).join('')
        if (hex !== metadata.content_sha256) throw new Error('Original PDF integrity check failed.')
      }
      if (!controller.signal.aborted) setBytes(new Uint8Array(data))
    }).catch(() => { if (!controller.signal.aborted) setError('The original PDF is unavailable or its version changed. Refresh the document to retry.') })
    return () => controller.abort()
  }, [fileId, metadata.version, metadata.content_sha256])
  const file = useMemo(() => bytes ? { data: bytes } : null, [bytes])
  const validPage = Math.max(1, Math.min(page, pages || 1))
  return <section aria-label="Original PDF" className="min-w-0 overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100">
    <div className="flex flex-wrap items-center gap-2 border-b bg-white p-3 text-sm">
      <button aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)} className="rounded border px-3 py-1 disabled:opacity-40">Previous</button>
      <label>Page <input aria-label="Page number" type="number" min="1" max={pages || 1} value={page} onChange={event => onPage(Math.max(1, Math.min(pages || 1, Number(event.target.value) || 1)))} className="w-14 rounded border px-1" /></label>
      <span>of {pages || '…'}</span>
      <button aria-label="Next page" disabled={!pages || page >= pages} onClick={() => onPage(page + 1)} className="rounded border px-3 py-1 disabled:opacity-40">Next</button>
      <button aria-label="Zoom out" onClick={() => onZoom(Math.max(.5, zoom - .25))} className="rounded border px-2">−</button>
      <span>{Math.round(zoom * 100)}%</span>
      <button aria-label="Zoom in" onClick={() => onZoom(Math.min(2, zoom + .25))} className="rounded border px-2">+</button>
      <button onClick={() => onZoom(1)} className="rounded border px-2">Fit width</button>
    </div>
    <div ref={container} className="max-h-[76vh] min-h-[420px] overflow-auto p-3" aria-live="polite">
      {error ? <p role="alert" className="p-5 text-red-700">{error}</p> : !file ? <p role="status" className="p-5">Loading original PDF…</p> :
        <Document suspense={false} file={file} onLoadSuccess={({ numPages }) => { setPages(numPages); if (page > numPages) setError('The cited page is outside this PDF.'); }} onLoadError={() => setError('Unable to render this PDF. It may be damaged or password protected.')}>
          <Page pageNumber={validPage} width={Math.min(width, 1200) * zoom} devicePixelRatio={Math.min(window.devicePixelRatio || 1, 2)} renderAnnotationLayer={false} />
        </Document>}
    </div>
  </section>
}
