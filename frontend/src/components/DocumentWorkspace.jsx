import { lazy, Suspense, useEffect, useState } from "react";
import AiAssistant from "./AiAssistant";
import { Button, TabBar } from "./ui";
import { RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
const PdfViewer = lazy(() => import("./PdfViewer"));
import { getDocumentView, searchDocument } from "../services/documentService";

export default function DocumentWorkspace({
  document,
  session,
  onSessionChange,
}) {
  const [metadata, setMetadata] = useState(null);
  const [error, setError] = useState("");
  const query = session.searchQuery || "";
  const setQuery = (value) =>
    onSessionChange((previous) => ({ ...previous, searchQuery: value }));
  const [results, setResults] = useState([]);
  const [searchedQuery, setSearchedQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const fileId = document.file_id || document._id;
  const page = session.page || 1,
    zoom = session.zoom || 1,
    tab = session.tab || "document";
  const update = (fields) =>
    onSessionChange((previous) => ({ ...previous, ...fields }));
  useEffect(() => {
    const controller = new AbortController();
    getDocumentView(fileId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setMetadata(value);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "Unable to open this document. It may be unavailable or access may have changed.",
          );
      });
    return () => controller.abort();
  }, [fileId, refresh]);
  useEffect(() => {
    if (query.trim().length < 2 || metadata?.status !== "completed") {
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setSearching(true);
      searchDocument(fileId, query.trim(), controller.signal)
        .then((value) => {
          if (!controller.signal.aborted) {
            setResults(value.results);
            setSearchedQuery(query.trim());
            setError("");
          }
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError("Document search is unavailable. Please retry.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false);
        });
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, fileId, metadata?.status]);
  async function selectSource(source) {
    try {
      const current = await getDocumentView(fileId);
      if (
        source.file_id !== fileId ||
        !source.page_number ||
        source.page_number < 1 ||
        (current.total_pages && source.page_number > current.total_pages) ||
        (source.processing_run_id || null) !==
          (current.processing_run_id || null) ||
        (source.content_sha256 || null) !== (current.content_sha256 || null)
      ) {
        throw new Error(
          "This source belongs to another document version or its page is unavailable.",
        );
      }
      setMetadata(current);
      setError("");
      update({ page: source.page_number, source, tab: "document" });
    } catch (failure) {
      setError(failure.message || "Source is unavailable.");
    }
  }
  const stale =
    session.source &&
    metadata &&
    ((session.source.processing_run_id || null) !==
      (metadata.processing_run_id || null) ||
      (session.source.content_sha256 || null) !==
        (metadata.content_sha256 || null));
  const ProvenanceIcon =
    metadata?.provenance === "verified" ? ShieldCheck : ShieldAlert;
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Read &amp; Ask</p>
          <h2 className="text-xl sm:text-2xl font-semibold">
            {document.filename}
          </h2>
        </div>
        <Button
          onClick={() => {
            setMetadata(null);
            setError("");
            setRefresh((value) => value + 1);
          }}
        >
          <RefreshCw size={15} />
          Refresh document
        </Button>
      </header>
      {error && (
        <p
          role="alert"
          className="rounded-xl bg-danger-soft p-3 text-sm text-danger"
        >
          {error}
        </p>
      )}
      {metadata && (
        <p className="flex items-start gap-2 rounded-lg border border-line bg-muted p-3 text-xs text-secondary">
          <ProvenanceIcon size={16} className="shrink-0" />
          {metadata.provenance === "verified"
            ? "Original linked to this processing version by SHA-256."
            : "Legacy provenance: compare passages manually; historical OCR bytes are not cryptographically verified."}
        </p>
      )}
      <div className="lg:hidden">
        <TabBar
          label="Reading panels"
          tabs={["document", "chat", "evidence"].map((name) => ({
            value: name,
            label: name,
          }))}
          value={tab}
          onChange={(value) => update({ tab: value })}
        />
      </div>
      <div className="reader-grid min-w-0">
        <div
          className={`${tab === "document" ? "" : "hidden"} min-w-0 space-y-3 lg:block`}
        >
          {metadata ? (
            metadata.original_available ? (
              <Suspense fallback={<p role="status">Loading PDF reader…</p>}>
                <PdfViewer
                  key={fileId + metadata.version}
                  fileId={fileId}
                  metadata={metadata}
                  page={page}
                  zoom={zoom}
                  onPage={(value) => update({ page: value })}
                  onZoom={(value) => update({ zoom: value })}
                />
              </Suspense>
            ) : (
              <p role="status" className="rounded-2xl border bg-surface p-8">
                Original PDF is unavailable. Existing analysis is retained.
              </p>
            )
          ) : (
            <p role="status">
              {error
                ? "Document could not be loaded. Refresh above to retry."
                : "Loading document…"}
            </p>
          )}
          <label className="block text-sm">
            Search extracted text
            <input
              aria-label="Search document"
              maxLength={200}
              disabled={metadata?.status !== "completed"}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setResults([]);
                setSearchedQuery("");
                setSearching(false);
              }}
              placeholder="Find an amount, date, or phrase"
              className="mt-1 w-full rounded-xl border bg-surface p-3"
            />
          </label>
          {metadata?.status !== "completed" && (
            <p className="text-sm text-secondary">
              Processing: {metadata?.status || document.status}. Search and
              questions are available after completion.
            </p>
          )}
          {searching && <p role="status">Searching extracted text…</p>}
          {!searching &&
            searchedQuery === query.trim() &&
            metadata?.status === "completed" &&
            query.trim().length >= 2 &&
            !results.length && (
              <p className="text-sm text-secondary">
                No extracted-text matches.
              </p>
            )}
          {results.map((source) => (
            <button
              key={source.source_id || source.chunk_index}
              onClick={() => selectSource(source)}
              className="block w-full rounded-xl border bg-surface p-3 text-left text-sm"
            >
              <strong>Page {source.page_number}</strong>
              <p className="mt-1 whitespace-pre-wrap text-secondary">
                {source.excerpt}
              </p>
            </button>
          ))}
        </div>
        <div className="min-w-0 space-y-3">
          <section
            aria-label="Selected evidence"
            className={`${tab === "evidence" || (tab === "document" && session.source) ? "" : "hidden"} rounded-2xl border bg-surface p-4 lg:block`}
          >
            <h3 className="font-semibold">Evidence passage</h3>
            {stale && (
              <p role="alert" className="mt-2 text-sm text-warning">
                This passage is from an earlier document version. Ask again for
                current evidence.
              </p>
            )}
            {session.source ? (
              <>
                <p className="mt-1 text-xs text-secondary">
                  {session.source.filename} · Page {session.source.page_number}
                </p>
                <blockquote className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap border-l-2 border-line pl-3 text-sm leading-6">
                  {session.source.excerpt ||
                    "This older answer did not retain an exact passage. Ask again to obtain an evidence passage."}
                </blockquote>
                <button
                  onClick={() => update({ tab: "chat" })}
                  className="mt-3 text-sm underline"
                >
                  Back to answer
                </button>
              </>
            ) : (
              <p className="mt-2 text-sm text-secondary">
                Choose an answer source to inspect the passage beside its
                original PDF page.
              </p>
            )}
            <p className="mt-2 text-xs text-secondary">
              Extracted text may differ from the page. No OCR coordinate
              highlights are inferred.
            </p>
          </section>
          <div className={`${tab === "chat" ? "" : "hidden"} lg:block`}>
            {metadata?.status === "completed" ? (
              <AiAssistant
                fileId={fileId}
                filename={document.filename}
                conversation={session}
                onConversationChange={onSessionChange}
                onSourceSelect={selectSource}
              />
            ) : (
              <p className="rounded-2xl border bg-surface p-6 text-sm">
                The assistant becomes available after processing completes.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
