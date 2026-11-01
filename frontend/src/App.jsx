import { useEffect, useMemo, useState } from "react";

import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  HelpCircle,
  Bot,
  BrainCircuit,
  ChevronRight,
  FileText,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Upload,
  Workflow,
} from "lucide-react";

import ThemeToggle from "./components/ThemeToggle";
import {
  Badge,
  Button,
  Card,
  Dialog,
  ListHeader,
  Skeleton,
  StatusMessage,
} from "./components/ui";
import UploadDocument from "./components/UploadDocument";
import ProcessingPipeline from "./components/ProcessingPipeline";
import DocumentIntelligence from "./components/DocumentIntelligence";
import WorkflowPanel from "./components/WorkFlowPanel";
import DocumentWorkspace from "./components/DocumentWorkspace";
import CollectionsWorkspace from "./components/CollectionsWorkspace";

import {
  analyzeDocument,
  generateWorkflow,
  getDocumentStatus,
  getDocuments,
} from "./services/documentService";

/* =====================================================
   CONSTANTS
===================================================== */

const VIEWS = {
  COLLECTIONS: "collections",
  DASHBOARD: "dashboard",
  DOCUMENTS: "documents",
  INTELLIGENCE: "intelligence",
  WORKFLOW: "workflow",
  ASSISTANT: "assistant",
};

/* =====================================================
   APP
===================================================== */

export default function App() {
  const [workspaceInfo, setWorkspaceInfo] = useState(false);
  const [documentsError, setDocumentsError] = useState("");
  const [readingSessions, setReadingSessions] = useState({});
  const [activeView, setActiveView] = useState(VIEWS.DASHBOARD);

  const [documents, setDocuments] = useState([]);

  const [activeDocument, setActiveDocument] = useState(null);

  const [analysis, setAnalysis] = useState(null);

  const [workflow, setWorkflow] = useState(null);

  const [loadingDocuments, setLoadingDocuments] = useState(true);

  const [analyzing, setAnalyzing] = useState(false);

  const [generatingWorkflow, setGeneratingWorkflow] = useState(false);

  const [pageError, setPageError] = useState("");

  const [refreshKey, setRefreshKey] = useState(0);

  /* ===================================================
     LOAD DOCUMENTS
  =================================================== */

  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      try {
        setLoadingDocuments(true);
        setDocumentsError("");

        const result = await getDocuments();

        if (cancelled) {
          return;
        }

        const normalized = Array.isArray(result) ? result : result?.files || [];

        setDocuments(normalized);
      } catch (error) {
        if (!cancelled) {
          setDocumentsError(
            (error?.response?.status === 401
              ? "Sign-in required. Please sign in again. "
              : error?.response?.status === 403
                ? "Access to this workspace was denied. "
                : "") +
              (error?.response?.data?.detail ||
                error?.message ||
                "Unable to load documents."),
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingDocuments(false);
        }
      }
    }

    loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  /* ===================================================
     DERIVED DATA
  =================================================== */

  const completedDocuments = useMemo(
    () => documents.filter((document) => document.status === "completed"),
    [documents],
  );

  const processingDocuments = useMemo(
    () =>
      documents.filter(
        (document) =>
          document.status !== "completed" && document.status !== "failed",
      ),
    [documents],
  );

  const failedDocuments = useMemo(
    () => documents.filter((document) => document.status === "failed"),
    [documents],
  );

  /* ===================================================
     SELECT DOCUMENT
  =================================================== */

  function selectDocument(document, targetView = VIEWS.ASSISTANT) {
    if (!document) {
      return;
    }

    const fileId = document.file_id || document._id;

    setActiveDocument({
      ...document,
      file_id: fileId,
    });

    setAnalysis(null);
    setWorkflow(null);
    setPageError("");

    setActiveView(targetView);
  }

  /* ===================================================
     UPLOAD COMPLETE
  =================================================== */

  function handleUploaded(uploaded) {
    if (!uploaded?.file_id) {
      return;
    }

    const document = {
      file_id: uploaded.file_id,
      _id: uploaded.file_id,
      filename: uploaded.filename || "Uploaded document",
      status: uploaded.status || "completed",
    };

    setDocuments((previous) => [
      document,
      ...previous.filter(
        (item) => (item.file_id || item._id) !== uploaded.file_id,
      ),
    ]);

    setActiveDocument(document);

    setAnalysis(null);
    setWorkflow(null);
    setPageError("");

    setActiveView(VIEWS.ASSISTANT);

    setRefreshKey((value) => value + 1);
  }

  /* ===================================================
     ANALYZE DOCUMENT
  =================================================== */

  async function handleAnalyzeDocument() {
    if (!activeDocument?.file_id) {
      return;
    }

    try {
      setAnalyzing(true);
      setPageError("");

      const result = await analyzeDocument(activeDocument.file_id, "contract");

      setAnalysis(result?.analysis || result);

      setActiveView(VIEWS.INTELLIGENCE);
    } catch (error) {
      setPageError(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to analyze this document.",
      );
    } finally {
      setAnalyzing(false);
    }
  }

  /* ===================================================
     GENERATE WORKFLOW
  =================================================== */

  async function handleGenerateWorkflow() {
    if (!activeDocument?.file_id) {
      return;
    }

    try {
      setGeneratingWorkflow(true);

      setPageError("");

      const result = await generateWorkflow(
        activeDocument.file_id,
        "Review this document and identify the most important actions, risks, missing information, deadlines, and approvals required before action is taken.",
      );

      setWorkflow(result?.workflow || result);

      setActiveView(VIEWS.WORKFLOW);
    } catch (error) {
      setPageError(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to generate the action plan.",
      );
    } finally {
      setGeneratingWorkflow(false);
    }
  }

  /* ===================================================
     REFRESH DOCUMENT
  =================================================== */

  async function refreshActiveDocument() {
    if (!activeDocument?.file_id) {
      return;
    }

    try {
      const result = await getDocumentStatus(activeDocument.file_id);

      const updated = {
        ...activeDocument,
        status: result.status,
      };

      setActiveDocument(updated);

      setDocuments((previous) =>
        previous.map((document) =>
          (document.file_id || document._id) === activeDocument.file_id
            ? {
                ...document,
                status: result.status,
              }
            : document,
        ),
      );
    } catch (error) {
      setPageError(
        error?.response?.data?.detail || "Unable to refresh document status.",
      );
    }
  }

  /* ===================================================
     NAVIGATION
  =================================================== */

  function navigate(view) {
    setPageError("");

    if (
      view === VIEWS.INTELLIGENCE ||
      view === VIEWS.WORKFLOW ||
      view === VIEWS.ASSISTANT
    ) {
      if (!activeDocument) {
        setActiveView(VIEWS.DOCUMENTS);
        return;
      }
    }

    if (view === VIEWS.DOCUMENTS) {
      setRefreshKey((value) => value + 1);
    }
    setActiveView(view);
  }

  const navigation = [
    { view: VIEWS.DASHBOARD, label: "Dashboard", icon: LayoutDashboard },
    { view: VIEWS.DOCUMENTS, label: "Documents", icon: FileText },
    { view: VIEWS.COLLECTIONS, label: "Collections", icon: FolderOpen },
    {
      view: VIEWS.ASSISTANT,
      label: "AI Assistant",
      mobile: "Assistant",
      icon: Bot,
      needsDocument: true,
    },
    {
      view: VIEWS.INTELLIGENCE,
      label: "Intelligence",
      icon: Sparkles,
      needsDocument: true,
    },
    {
      view: VIEWS.WORKFLOW,
      label: "Action Workflow",
      mobile: "Workflow",
      icon: Workflow,
      needsDocument: true,
    },
  ];
  const nav = (mobile) =>
    navigation.map(
      ({ view, label, mobile: mobileLabel, icon: Icon, needsDocument }) => (
        <button
          key={view}
          className="nav-item"
          aria-current={activeView === view ? "page" : undefined}
          title={
            needsDocument && !activeDocument
              ? "Open a document first"
              : undefined
          }
          disabled={needsDocument && !activeDocument}
          onClick={() => navigate(view)}
        >
          <Icon size={18} aria-hidden="true" />
          <span>{mobile ? mobileLabel || label : label}</span>
        </button>
      ),
    );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="app-sidebar" aria-label="Workspace sidebar">
        <div className="app-brand">
          <div className="brand-mark">
            <BrainCircuit size={23} aria-hidden="true" />
          </div>
          <div>
            <div className="brand-name">
              DocuMind<span className="text-accent">.</span>
            </div>
            <p className="text-xs text-secondary">Document intelligence</p>
          </div>
        </div>
        <p className="sidebar-section">Workspace</p>
        <nav className="app-nav" aria-label="Main navigation">
          {nav(false)}
        </nav>
        <div className="mx-6 mt-8 rounded-lg border border-line bg-surface p-4">
          <ShieldAlert size={18} className="mb-3 text-secondary" />
          <p className="text-sm font-medium">Evidence comes first</p>
          <p className="mt-2 text-xs leading-5 text-secondary">
            Trace answers to the original. Review limitations before taking
            action.
          </p>
        </div>
        <div className="sidebar-footer">
          <p className="text-xs text-secondary mb-3">Current document</p>
          {activeDocument ? (
            <button
              className="w-full text-left"
              onClick={() => navigate(VIEWS.ASSISTANT)}
            >
              <p
                className="line-clamp-2 text-sm font-medium"
                title={activeDocument.filename}
              >
                {activeDocument.filename}
              </p>
              <div className="mt-2">
                <DocumentStatus status={activeDocument.status} />
              </div>
            </button>
          ) : (
            <p className="text-sm text-secondary">Open a document to begin</p>
          )}
          <Button
            variant="ghost"
            className="mt-5 w-full justify-start"
            onClick={() => setWorkspaceInfo(true)}
          >
            <HelpCircle size={16} />
            Workspace details
          </Button>
        </div>
      </aside>
      <main className="app-main">
        <header className="app-header">
          <div className="flex min-w-0 items-center gap-3">
            <span className="brand-mark lg:hidden">
              <BrainCircuit size={20} />
            </span>
            <div>
              <p className="text-xs text-secondary">
                Workspace <span className="mx-1">/</span>{" "}
                <span className="text-primary">{pageTitle(activeView)}</span>
              </p>
              <h1 className="text-base font-medium mt-1">
                Document intelligence platform
              </h1>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden sm:inline-flex ui-badge">
              Current workspace
            </span>
            <Button
              aria-label="Refresh"
              title="Refresh documents"
              onClick={() => setRefreshKey((value) => value + 1)}
              className="px-2"
            >
              <RefreshCw size={17} />
            </Button>
            <ThemeToggle />
          </div>
        </header>
        <nav className="mobile-nav" aria-label="Mobile navigation">
          {nav(true)}
        </nav>
        <div id="main-content" tabIndex={-1} className="app-content">
          {pageError && (
            <div className="mb-6">
              <StatusMessage tone="error" title="Action could not be completed">
                {pageError}
              </StatusMessage>
            </div>
          )}
          {activeView === VIEWS.DASHBOARD && (
            <DashboardView
              documents={documents}
              completedDocuments={completedDocuments}
              processingDocuments={processingDocuments}
              failedDocuments={failedDocuments}
              loading={loadingDocuments}
              error={documentsError}
              onRetry={() => setRefreshKey((value) => value + 1)}
              onOpenDocuments={() => navigate(VIEWS.DOCUMENTS)}
              onOpenCollections={() => navigate(VIEWS.COLLECTIONS)}
              onSelectDocument={selectDocument}
            />
          )}
          {activeView === VIEWS.DOCUMENTS && (
            <DocumentsView
              onUploaded={handleUploaded}
              documents={documents}
              loading={loadingDocuments}
              error={documentsError}
              activeDocument={activeDocument}
              onSelectDocument={selectDocument}
              onRefresh={() => setRefreshKey((value) => value + 1)}
            />
          )}
          {activeView === VIEWS.COLLECTIONS && <CollectionsWorkspace />}
          {activeView === VIEWS.INTELLIGENCE && (
            <section className="space-y-6">
              {!activeDocument ? (
                <EmptyState
                  title="Choose a document"
                  description="Open a document from your library to see its intelligence."
                  onAction={() => navigate(VIEWS.DOCUMENTS)}
                />
              ) : activeDocument.status !== "completed" ? (
                <>
                  <ProcessingPipeline
                    status={activeDocument.status}
                    filename={activeDocument.filename}
                  />
                  <Button onClick={refreshActiveDocument}>
                    <RefreshCw size={16} />
                    Check status
                  </Button>
                </>
              ) : !analysis ? (
                <IntelligenceStart
                  document={activeDocument}
                  analyzing={analyzing}
                  onAnalyze={handleAnalyzeDocument}
                />
              ) : (
                <DocumentIntelligence
                  analysis={analysis}
                  onGenerateWorkflow={handleGenerateWorkflow}
                  generatingWorkflow={generatingWorkflow}
                />
              )}
            </section>
          )}
          {activeView === VIEWS.WORKFLOW && (
            <section className="space-y-6">
              {!activeDocument ? (
                <EmptyState
                  title="Choose a document"
                  description="Open a document before generating its action workflow."
                  onAction={() => navigate(VIEWS.DOCUMENTS)}
                />
              ) : !workflow ? (
                <WorkflowStart
                  document={activeDocument}
                  generating={generatingWorkflow}
                  onGenerate={handleGenerateWorkflow}
                />
              ) : (
                <WorkflowPanel workflow={workflow} />
              )}
            </section>
          )}
          {activeView === VIEWS.ASSISTANT &&
            (activeDocument ? (
              <DocumentWorkspace
                key={activeDocument.file_id}
                document={activeDocument}
                session={readingSessions[activeDocument.file_id] || {}}
                onSessionChange={(updater) =>
                  setReadingSessions((previous) => ({
                    ...previous,
                    [activeDocument.file_id]: updater(
                      previous[activeDocument.file_id] || {},
                    ),
                  }))
                }
              />
            ) : (
              <EmptyState
                title="Choose a document"
                description="Open a PDF to read, ask questions, and inspect evidence."
                onAction={() => navigate(VIEWS.DOCUMENTS)}
              />
            ))}
        </div>
      </main>
      <Dialog
        open={workspaceInfo}
        title="Your local workspace"
        onClose={() => setWorkspaceInfo(false)}
      >
        <p className="text-secondary">
          Documents and results are scoped to your authenticated workspace. This
          interface does not change document access or ownership.
        </p>
        <p className="mt-4 text-sm">
          Development access is local only. Evidence may be incomplete; check
          source versions and original passages before relying on answers.
        </p>
        <Button className="mt-6" onClick={() => setWorkspaceInfo(false)}>
          Done
        </Button>
      </Dialog>
    </div>
  );
}

function DocumentStatus({ status = "unknown" }) {
  const tone =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "error"
        : status === "unknown"
          ? "neutral"
          : "warning";
  return (
    <Badge tone={tone}>
      {status === "completed" ? "Ready" : status.replaceAll("_", " ")}
    </Badge>
  );
}
function LibraryError({ error, onRetry, retained }) {
  return (
    <StatusMessage
      tone="error"
      title="Document library unavailable"
      action={
        <Button onClick={onRetry}>
          <RefreshCw size={15} />
          Retry loading documents
        </Button>
      }
    >
      <p>{error}</p>
      <p className="mt-2">
        {retained
          ? "Previously loaded documents are shown below. Counts may be out of date."
          : "Document counts are unavailable. This does not mean your workspace is empty."}
      </p>
    </StatusMessage>
  );
}
function DashboardView({
  documents,
  completedDocuments,
  processingDocuments,
  failedDocuments,
  loading,
  error,
  onRetry,
  onOpenDocuments,
  onOpenCollections,
  onSelectDocument,
}) {
  const metrics = [
    ["Total documents", documents.length, FileText],
    ["Ready for AI", completedDocuments.length, CheckCircle2],
    ["Processing", processingDocuments.length, Activity],
    ["Needs attention", failedDocuments.length, ShieldAlert],
  ];
  return (
    <div className="space-y-7">
      <div className="page-intro">
        <div>
          <p className="eyebrow">Your document workspace</p>
          <h2>Clarity starts with evidence.</h2>
          <p className="mt-3 text-secondary max-w-xl">
            Turn documents into answers, grounded insights, and clear next
            steps.
          </p>
        </div>
        <Button variant="primary" onClick={onOpenDocuments}>
          <Upload size={17} />
          Upload document
        </Button>
      </div>
      {error && (
        <LibraryError
          error={error}
          onRetry={onRetry}
          retained={documents.length > 0}
        />
      )}
      <div className="metric-grid" aria-label="Document metrics">
        {metrics.map(([label, value, Icon]) => (
          <Card className="metric" key={label}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-secondary text-xs">{label}</p>
              <Icon size={16} className="text-secondary" aria-hidden="true" />
            </div>
            <p
              className="metric-value"
              aria-label={`${label}: ${loading ? "loading" : error ? "unavailable" : value}`}
            >
              {loading || error ? "—" : value}
            </p>
            <p className="mt-2 text-xs text-secondary">
              {loading
                ? "Loading workspace"
                : error
                  ? "Awaiting verified counts"
                  : label === "Ready for AI"
                    ? "Processing complete"
                    : label === "Needs attention"
                      ? "Failed processing"
                      : label === "Processing"
                        ? "Queued or in progress"
                        : "In this workspace"}
            </p>
          </Card>
        ))}
      </div>
      <div className="dashboard-grid">
        <Card>
          <ListHeader
            title="Recent documents"
            description="Pick up where you left off."
            action={
              <Button variant="ghost" onClick={onOpenDocuments}>
                View all
                <ArrowUpRight size={16} />
              </Button>
            }
          />
          {loading ? (
            <Skeleton label="Loading documents" />
          ) : !documents.length ? (
            error ? (
              <p className="p-6 text-secondary">
                Your library could not be loaded. Retry above to see your
                documents.
              </p>
            ) : (
              <EmptyState
                embedded
                title="Your workspace is ready"
                description="Upload your first PDF to start exploring its evidence."
                onAction={onOpenDocuments}
              />
            )
          ) : (
            documents
              .slice(0, 5)
              .map((doc) => (
                <DocumentRow
                  key={doc._id || doc.file_id}
                  document={doc}
                  onClick={() => onSelectDocument(doc)}
                />
              ))
          )}
        </Card>
        <div className="space-y-5">
          <Card className="p-5">
            <h3>Make your next move</h3>
            <button className="quick-action" onClick={onOpenDocuments}>
              <Upload size={18} className="text-secondary" />
              <div className="flex-1">
                <p className="text-sm font-medium">Upload a PDF</p>
                <p className="text-xs text-secondary mt-1">
                  Add evidence to your workspace
                </p>
              </div>
              <ChevronRight size={16} />
            </button>
            <button className="quick-action" onClick={onOpenCollections}>
              <FolderOpen size={18} className="text-secondary" />
              <div className="flex-1">
                <p className="text-sm font-medium">Explore collections</p>
                <p className="text-xs text-secondary mt-1">
                  Ask and compare across documents
                </p>
              </div>
              <ChevronRight size={16} />
            </button>
          </Card>
          <div className="workspace-note">
            <div className="flex items-center gap-2">
              <Bot size={17} className="text-accent" />
              <h3 className="text-sm">Answers with a source</h3>
            </div>
            <p className="mt-3 text-sm text-secondary">
              Open a document to ask questions, follow citations, and read the
              exact passage in context.
            </p>
            <p className="mt-3 text-xs text-secondary">
              Always review source quality and limitations.
            </p>
          </div>
        </div>
      </div>
      <p className="text-xs text-secondary flex gap-2 items-center">
        <ShieldAlert size={14} />
        Only documents in your current workspace are shown.
      </p>
    </div>
  );
}
function DocumentsView({
  documents,
  loading,
  error,
  activeDocument,
  onSelectDocument,
  onRefresh,
  onUploaded,
}) {
  return (
    <div className="space-y-6">
      <div className="page-intro">
        <div>
          <p className="eyebrow">Document library</p>
          <h2>Your source of truth.</h2>
          <p className="mt-3 text-secondary">
            Upload, organize, and open your original documents.
          </p>
        </div>
        <Button onClick={onRefresh}>
          <RefreshCw size={16} />
          Refresh
        </Button>
      </div>
      <Card className="p-5 sm:p-6">
        <UploadDocument onUploaded={onUploaded} />
      </Card>
      {error && (
        <LibraryError
          error={error}
          onRetry={onRefresh}
          retained={documents.length > 0}
        />
      )}
      <Card>
        <ListHeader
          title="Uploaded documents"
          description={
            loading
              ? "Loading your library…"
              : error
                ? "Library status unavailable"
                : `${documents.length} document${documents.length === 1 ? "" : "s"} in this workspace`
          }
        />
        {loading ? (
          <Skeleton label="Loading documents" />
        ) : !documents.length ? (
          error ? (
            <p className="p-6 text-secondary">
              Documents could not be loaded. Use Retry loading documents above.
            </p>
          ) : (
            <EmptyState
              embedded
              title="No documents yet"
              description="Upload a PDF above. Your original stays available for reading and source review."
            />
          )
        ) : (
          documents.map((doc) => (
            <DocumentRow
              key={doc._id || doc.file_id}
              document={doc}
              active={
                (activeDocument?.file_id || activeDocument?._id) ===
                (doc._id || doc.file_id)
              }
              onClick={() => onSelectDocument(doc)}
            />
          ))
        )}
      </Card>
    </div>
  );
}
function DocumentRow({ document, onClick, active }) {
  return (
    <button
      className="document-row"
      aria-current={active ? "true" : undefined}
      onClick={onClick}
    >
      <span className="file-icon">
        <FileText size={20} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="document-name block">
          {document.filename || "Untitled document"}
        </span>
        <span className="block text-xs text-secondary mt-1">
          PDF document
          {document.total_pages ? ` · ${document.total_pages} pages` : ""}
        </span>
        {document.error && (
          <span className="block text-xs text-danger mt-1">
            {typeof document.error === "string"
              ? document.error
              : "Processing failed. Open document for details."}
          </span>
        )}
      </span>
      <DocumentStatus status={document.status} />
      <ChevronRight size={16} className="text-secondary shrink-0" />
    </button>
  );
}
function EmptyState({ title, description, onAction, embedded }) {
  return (
    <div className={`${embedded ? "" : "ui-card"} p-7 sm:p-10 text-center`}>
      <FileText size={28} className="text-secondary mx-auto mb-4" />
      <h3>{title}</h3>
      <p className="text-secondary mt-3 max-w-md mx-auto">{description}</p>
      {onAction && (
        <Button variant="primary" onClick={onAction} className="mt-5">
          Open documents
          <ChevronRight size={16} />
        </Button>
      )}
    </div>
  );
}
function IntelligenceStart({ document, analyzing, onAnalyze }) {
  return (
    <Card className="p-6 sm:p-10">
      <div className="max-w-2xl">
        <p className="eyebrow">Document intelligence</p>
        <BrainCircuit size={28} className="text-accent my-5" />
        <h2>See the details that matter.</h2>
        <p className="mt-4 text-secondary">
          Review executive summaries, parties, obligations, financial terms, and
          potential risks. Generated findings require human review.
        </p>
        <p className="mt-6 rounded-lg border border-line bg-muted p-4 document-name">
          {document.filename}
        </p>
        <Button
          variant="primary"
          className="mt-6"
          onClick={onAnalyze}
          disabled={analyzing}
        >
          {analyzing ? (
            <Loader2 size={17} className="animate-spin" />
          ) : (
            <Sparkles size={17} />
          )}
          {analyzing ? "Analyzing document…" : "Run Document Intelligence"}
        </Button>
        <p className="mt-3 text-xs text-secondary">
          Runs analysis using your configured model service.
        </p>
      </div>
    </Card>
  );
}
function WorkflowStart({ document, generating, onGenerate }) {
  return (
    <Card className="p-6 sm:p-10">
      <div className="max-w-2xl">
        <p className="eyebrow">Action workflow</p>
        <Workflow size={28} className="text-accent my-5" />
        <h2>From insight to next steps.</h2>
        <p className="mt-4 text-secondary">
          Build a prioritized action plan with deadlines, monitoring tasks, and
          human approval requirements. Review every recommendation before
          acting.
        </p>
        <p className="mt-6 rounded-lg border border-line bg-muted p-4 document-name">
          {document.filename}
        </p>
        <Button
          variant="primary"
          className="mt-6"
          onClick={onGenerate}
          disabled={generating}
        >
          {generating ? (
            <Loader2 size={17} className="animate-spin" />
          ) : (
            <Workflow size={17} />
          )}
          {generating ? "Generating action plan…" : "Generate action plan"}
        </Button>
        <p className="mt-3 text-xs text-secondary">
          Runs generation using your configured model service.
        </p>
      </div>
    </Card>
  );
}
function pageTitle(view) {
  return (
    {
      collections: "Collections",
      documents: "Documents",
      intelligence: "Document intelligence",
      workflow: "Action workflow",
      assistant: "Read & Ask",
    }[view] || "Dashboard"
  );
}
