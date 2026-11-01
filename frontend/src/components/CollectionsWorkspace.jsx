import { useEffect, useState } from "react";
import { FolderOpen, Plus, RefreshCw, Upload } from "lucide-react";
import { Badge, Button, Card, Input, Skeleton, StatusMessage } from "./ui";
import AiAssistant from "./AiAssistant";
import DocumentWorkspace from "./DocumentWorkspace";
import ComparisonPanel from "./ComparisonPanel";
import SavedComparisonReports from "./SavedComparisonReports";
import {
  listCollections,
  createCollection,
  editCollection,
  deleteCollection,
  askCollection,
} from "../services/collectionService";
import {
  getDocuments,
  getDocumentView,
  uploadDocument,
} from "../services/documentService";

export default function CollectionsWorkspace() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [collections, setCollections] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [name, setName] = useState("");
  const [selected, setSelected] = useState([]);
  const [sessions, setSessions] = useState({});
  const [uploads, setUploads] = useState([]);
  const [reader, setReader] = useState(null);
  const [readingSession, setReadingSession] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const active = collections.find((row) => row.id === activeId);
  const members = documents.filter((doc) =>
    active?.file_ids.includes(doc._id || doc.file_id),
  );
  async function refresh() {
    const [rows, files] = await Promise.all([
      listCollections(),
      getDocuments(),
    ]);
    setCollections(rows);
    setDocuments(files);
    setLoading(false);
    setLoadError("");
  }
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      Promise.all([listCollections(), getDocuments()])
        .then(([rows, files]) => {
          if (!cancelled) {
            setCollections(rows);
            setDocuments(files);
            setLoadError("");
            setLoading(false);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setLoadError(
              "Unable to refresh collections. Your library may be unavailable; this is not an empty-workspace confirmation.",
            );
            setLoading(false);
          }
        });
    load();
    const timer = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  async function action(operation) {
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (failure) {
      setError(
        failure.response?.data?.detail ||
          failure.message ||
          "Request failed. Refresh and retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function membership(id, checked) {
    const ids = checked
      ? [...active.file_ids, id]
      : active.file_ids.filter((value) => value !== id);
    await action(() =>
      editCollection(active.id, { revision: active.revision, file_ids: ids }),
    );
    setSelected((previous) =>
      previous.filter((value) => checked || value !== id),
    );
  }
  async function bulkUpload(files) {
    if (!files.length) return;
    if (files.length > 10) {
      setError("Upload up to 10 PDFs at a time.");
      return;
    }
    setBusy(true);
    setError("");
    setUploads([]);
    // Independent requests preserve accepted uploads when another file fails.
    for (const [index, file] of files.entries()) {
      setUploads((previous) => [
        ...previous,
        { index, name: file.name, status: "uploading" },
      ]);
      try {
        const result = await uploadDocument(file);
        setUploads((previous) =>
          previous.map((row) =>
            row.index === index
              ? { ...row, status: result.status || "queued" }
              : row,
          ),
        );
      } catch (failure) {
        setUploads((previous) =>
          previous.map((row) =>
            row.index === index
              ? {
                  ...row,
                  status: "failed",
                  message:
                    failure.response?.data?.detail ||
                    "Upload failed. Check Documents before retrying if acceptance is uncertain.",
                }
              : row,
          ),
        );
      }
    }
    try {
      await refresh();
    } catch {
      setError("Uploads submitted. Refresh document statuses.");
    }
    setBusy(false);
  }
  async function openSource(source) {
    try {
      const manifest = await getDocumentView(source.file_id);
      if (
        (source.processing_run_id || null) !==
          (manifest.processing_run_id || null) ||
        (source.content_sha256 || null) !== (manifest.content_sha256 || null) ||
        !Number.isInteger(source.page_number) ||
        source.page_number < 1 ||
        source.page_number > manifest.total_pages
      )
        throw new Error(
          "Source version changed. Ask again for current evidence.",
        );
      setReadingSession({ page: source.page_number, source, tab: "document" });
      setReader({ file_id: source.file_id, filename: source.filename });
    } catch (failure) {
      setError(failure.message || "Unable to open source.");
    }
  }
  return (
    <div className="space-y-6">
      <div className="page-intro">
        <div>
          <p className="eyebrow">Connected evidence</p>
          <h2>Collections</h2>
          <p className="mt-3 text-secondary max-w-2xl">
            Bring related documents together. Ask across sources, compare
            evidence, and keep a reviewed record.
          </p>
        </div>
        <Badge>
          {loading || loadError ? "—" : collections.length} collection
          {collections.length === 1 ? "" : "s"}
        </Badge>
      </div>
      {loadError && (
        <StatusMessage
          tone="error"
          title="Collection data unavailable"
          action={
            <Button onClick={() => action(refresh)}>
              <RefreshCw size={15} />
              Retry collections
            </Button>
          }
        >
          {loadError}
        </StatusMessage>
      )}
      {error && (
        <StatusMessage tone="error" title="Collection action failed">
          {error}
        </StatusMessage>
      )}
      {reader && (
        <section className="space-y-4">
          <Button onClick={() => setReader(null)}>Back to collection</Button>
          <DocumentWorkspace
            key={reader.file_id}
            document={reader}
            session={readingSession}
            onSessionChange={setReadingSession}
          />
        </section>
      )}
      <div className={reader ? "hidden" : "space-y-6"}>
        <Card className="p-5">
          <div className="collection-tools">
            <form
              className="space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                action(async () => {
                  const row = await createCollection(name);
                  setActiveId(row.id);
                  setSelected([]);
                  setName("");
                });
              }}
            >
              <label className="text-sm font-medium" htmlFor="collection-name">
                Create a collection
              </label>
              <div className="flex flex-wrap gap-2">
                <Input
                  id="collection-name"
                  aria-label="New collection name"
                  required
                  maxLength={100}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="flex-1 min-w-0"
                  placeholder="e.g. Supplier agreements"
                />
                <Button
                  type="submit"
                  variant="primary"
                  disabled={busy || !name.trim()}
                >
                  <Plus size={16} />
                  Create collection
                </Button>
              </div>
              <p className="text-xs text-secondary">
                Up to 10 documents. Originals stay in your library.
              </p>
            </form>
            <label className="block text-sm font-medium">
              Active collection
              <select
                aria-label="Active collection"
                value={activeId}
                onChange={(event) => {
                  setActiveId(event.target.value);
                  setSelected([]);
                }}
                className="mt-2 w-full rounded border bg-surface p-2"
              >
                <option value="">Choose a collection</option>
                {collections.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </Card>
        {loading ? (
          <Skeleton label="Loading collections" />
        ) : (
          !collections.length &&
          !loadError && (
            <Card className="p-8 text-center">
              <FolderOpen size={28} className="text-secondary mx-auto mb-3" />
              <h3>A home for related documents</h3>
              <p className="mt-2 text-secondary">
                No collections yet. Create one to start.
              </p>
            </Card>
          )
        )}
        {active && (
          <>
            <Card className="p-5 space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Collection workspace</p>
                  <h3>{active.name}</h3>
                </div>
                <Badge>{members.length} / 10 documents</Badge>
              </div>
              <form
                className="flex flex-wrap gap-2"
                key={`rename:${active.id}:${active.revision}`}
                onSubmit={(event) => {
                  event.preventDefault();
                  const value = new FormData(event.currentTarget).get("name");
                  action(() =>
                    editCollection(active.id, {
                      revision: active.revision,
                      name: value,
                    }),
                  );
                }}
              >
                <Input
                  aria-label="Rename collection"
                  name="name"
                  required
                  maxLength={100}
                  defaultValue={active.name}
                  className="flex-1 min-w-0"
                />
                <Button type="submit" disabled={busy}>
                  Rename
                </Button>
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Delete this collection? Original documents will be kept.",
                      )
                    )
                      action(async () => {
                        await deleteCollection(active.id);
                        setActiveId("");
                      });
                  }}
                >
                  Delete collection
                </Button>
              </form>
              <div className="collection-columns">
                <fieldset className="rounded-lg border bg-muted p-4">
                  <legend>Collection membership</legend>
                  <p className="text-xs text-secondary mb-2">
                    Choose which documents belong to this collection.
                  </p>
                  {documents.length ? (
                    documents.map((doc) => {
                      const id = doc._id || doc.file_id;
                      return (
                        <label key={id} className="selection-row">
                          <input
                            type="checkbox"
                            checked={active.file_ids.includes(id)}
                            disabled={
                              busy ||
                              (!active.file_ids.includes(id) &&
                                active.file_ids.length >= 10)
                            }
                            onChange={(event) =>
                              membership(id, event.target.checked)
                            }
                          />
                          <span className="min-w-0 flex-1 text-sm">
                            {doc.filename}
                            <span className="block text-xs text-secondary mt-1">
                              {doc.status}
                            </span>
                          </span>
                        </label>
                      );
                    })
                  ) : (
                    <p className="text-secondary">
                      Upload PDFs below or from Documents.
                    </p>
                  )}
                </fieldset>
                <fieldset className="rounded-lg border bg-muted p-4">
                  <legend>Question context</legend>
                  <p className="text-xs text-secondary mb-2">
                    Leave all unchecked to ask across all completed members.
                    Processing and failed documents are skipped.
                  </p>
                  {members.map((doc) => {
                    const id = doc._id || doc.file_id;
                    return (
                      <label className="selection-row" key={id}>
                        <input
                          type="checkbox"
                          disabled={doc.status !== "completed"}
                          checked={selected.includes(id)}
                          onChange={(event) =>
                            setSelected((previous) =>
                              event.target.checked
                                ? [...previous, id]
                                : previous.filter((value) => value !== id),
                            )
                          }
                        />
                        <span className="text-sm">
                          {doc.filename} · {doc.status}
                        </span>
                      </label>
                    );
                  })}
                  {!members.length && (
                    <p className="mt-3 text-secondary">
                      This collection is empty. Add existing documents above.
                    </p>
                  )}
                  <p className="mt-4 text-xs text-accent">
                    {selected.length
                      ? `${selected.length} selected document(s) in question context`
                      : `${members.filter((doc) => doc.status === "completed").length} completed document(s) in question context`}
                  </p>
                </fieldset>
              </div>
            </Card>
            <div className="collection-columns">
              <ComparisonPanel
                key={`comparison:${active.id}:${active.revision}`}
                collectionId={active.id}
                documents={members}
                onSourceSelect={openSource}
              />
              {members.some((doc) => doc.status === "completed") ? (
                <AiAssistant
                  key={active.id}
                  fileId={active.id}
                  filename={active.name}
                  conversation={sessions[active.id] || {}}
                  onConversationChange={(updater) =>
                    setSessions((previous) => ({
                      ...previous,
                      [active.id]: updater(previous[active.id] || {}),
                    }))
                  }
                  askQuestion={(id, question) =>
                    askCollection(
                      id,
                      question,
                      selected.length ? selected : undefined,
                    )
                  }
                  onSourceSelect={openSource}
                />
              ) : (
                <StatusMessage title="Processing required">
                  Questions become available when at least one member completes
                  processing.
                </StatusMessage>
              )}
            </div>
          </>
        )}
        <SavedComparisonReports onSourceSelect={openSource} />
        <Card className="p-5">
          <div className="flex items-start gap-3">
            <Upload size={20} className="text-secondary mt-1" />
            <div className="min-w-0 flex-1">
              <label className="block font-medium">
                Upload multiple PDFs
                <input
                  aria-label="Upload multiple PDFs"
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  disabled={busy}
                  className="mt-3 block w-full"
                  onChange={(event) => {
                    bulkUpload(Array.from(event.target.files));
                    event.target.value = "";
                  }}
                />
              </label>
              <p className="mt-3 text-xs text-secondary">
                Uploads appear in Documents; add them to a collection above.
                Each file processes independently.
              </p>
              {uploads.map((row) => (
                <p key={row.index} role="status" className="mt-2 text-sm">
                  {row.name}: {row.status} {row.message}
                </p>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
