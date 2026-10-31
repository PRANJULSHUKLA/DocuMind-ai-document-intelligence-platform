import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Activity,
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

import UploadDocument from "./components/UploadDocument";
import ProcessingPipeline from "./components/ProcessingPipeline";
import DocumentIntelligence from "./components/DocumentIntelligence";
import WorkflowPanel from "./components/WorkFlowPanel";
import AIAssistant from "./components/AiAssistant";

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
  const [
    activeView,
    setActiveView,
  ] = useState(
    VIEWS.DASHBOARD
  );

  const [
    documents,
    setDocuments,
  ] = useState([]);

  const [
    activeDocument,
    setActiveDocument,
  ] = useState(null);

  const [
    analysis,
    setAnalysis,
  ] = useState(null);

  const [
    workflow,
    setWorkflow,
  ] = useState(null);

  const [
    loadingDocuments,
    setLoadingDocuments,
  ] = useState(true);

  const [
    analyzing,
    setAnalyzing,
  ] = useState(false);

  const [
    generatingWorkflow,
    setGeneratingWorkflow,
  ] = useState(false);

  const [
    pageError,
    setPageError,
  ] = useState("");

  const [
    refreshKey,
    setRefreshKey,
  ] = useState(0);


  /* ===================================================
     LOAD DOCUMENTS
  =================================================== */

  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      try {
        setLoadingDocuments(true);
        setPageError("");

        const result =
          await getDocuments();

        if (cancelled) {
          return;
        }

        const normalized =
          Array.isArray(result)
            ? result
            : result?.files || [];

        setDocuments(
          normalized
        );

      } catch (error) {
        if (!cancelled) {
          setPageError(
            error?.response?.data?.detail ||
              error?.message ||
              "Unable to load documents."
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

  const completedDocuments =
    useMemo(
      () =>
        documents.filter(
          (document) =>
            document.status ===
            "completed"
        ),
      [documents]
    );

  const processingDocuments =
    useMemo(
      () =>
        documents.filter(
          (document) =>
            document.status !==
              "completed" &&
            document.status !==
              "failed"
        ),
      [documents]
    );

  const failedDocuments =
    useMemo(
      () =>
        documents.filter(
          (document) =>
            document.status ===
            "failed"
        ),
      [documents]
    );


  /* ===================================================
     SELECT DOCUMENT
  =================================================== */

  function selectDocument(
    document,
    targetView = VIEWS.INTELLIGENCE
  ) {
    if (!document) {
      return;
    }

    const fileId =
      document.file_id ||
      document._id;

    setActiveDocument({
      ...document,
      file_id: fileId,
    });

    setAnalysis(null);
    setWorkflow(null);
    setPageError("");

    setActiveView(
      targetView
    );
  }


  /* ===================================================
     UPLOAD COMPLETE
  =================================================== */

  function handleUploaded(
    uploaded
  ) {
    if (!uploaded?.file_id) {
      return;
    }

    const document = {
      file_id:
        uploaded.file_id,
      _id:
        uploaded.file_id,
      filename:
        uploaded.filename ||
        "Uploaded document",
      status:
        uploaded.status ||
        "completed",
    };

    setDocuments(
      (previous) => [
        document,
        ...previous.filter(
          (item) =>
            (item.file_id ||
              item._id) !==
            uploaded.file_id
        ),
      ]
    );

    setActiveDocument(
      document
    );

    setAnalysis(null);
    setWorkflow(null);
    setPageError("");

    setActiveView(
      VIEWS.INTELLIGENCE
    );

    setRefreshKey(
      (value) => value + 1
    );
  }


  /* ===================================================
     ANALYZE DOCUMENT
  =================================================== */

  async function handleAnalyzeDocument() {
    if (
      !activeDocument?.file_id
    ) {
      return;
    }

    try {
      setAnalyzing(true);
      setPageError("");

      const result =
        await analyzeDocument(
          activeDocument.file_id,
          "contract"
        );

      setAnalysis(
        result?.analysis ||
          result
      );

      setActiveView(
        VIEWS.INTELLIGENCE
      );

    } catch (error) {
      setPageError(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to analyze this document."
      );
    } finally {
      setAnalyzing(false);
    }
  }


  /* ===================================================
     GENERATE WORKFLOW
  =================================================== */

  async function handleGenerateWorkflow() {
    if (
      !activeDocument?.file_id
    ) {
      return;
    }

    try {
      setGeneratingWorkflow(
        true
      );

      setPageError("");

      const result =
        await generateWorkflow(
          activeDocument.file_id,
          "Review this document and identify the most important actions, risks, missing information, deadlines, and approvals required before action is taken."
        );

      setWorkflow(
        result?.workflow ||
          result
      );

      setActiveView(
        VIEWS.WORKFLOW
      );

    } catch (error) {
      setPageError(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to generate the action plan."
      );
    } finally {
      setGeneratingWorkflow(
        false
      );
    }
  }


  /* ===================================================
     REFRESH DOCUMENT
  =================================================== */

  async function refreshActiveDocument() {
    if (
      !activeDocument?.file_id
    ) {
      return;
    }

    try {
      const result =
        await getDocumentStatus(
          activeDocument.file_id
        );

      const updated = {
        ...activeDocument,
        status:
          result.status,
      };

      setActiveDocument(
        updated
      );

      setDocuments(
        (previous) =>
          previous.map(
            (document) =>
              (
                document.file_id ||
                document._id
              ) ===
              activeDocument.file_id
                ? {
                    ...document,
                    status:
                      result.status,
                  }
                : document
          )
      );

    } catch (error) {
      setPageError(error?.response?.data?.detail || "Unable to refresh document status.");
    }
  }


  /* ===================================================
     NAVIGATION
  =================================================== */

  function navigate(
    view
  ) {
    setPageError("");

    if (
      view ===
        VIEWS.INTELLIGENCE ||
      view ===
        VIEWS.WORKFLOW ||
      view ===
        VIEWS.ASSISTANT
    ) {
      if (
        !activeDocument
      ) {
        setActiveView(
          VIEWS.DOCUMENTS
        );
        return;
      }
    }

    setActiveView(view);
  }


  /* ===================================================
     RENDER
  =================================================== */

  return (
    <div className="min-h-screen bg-[#fafafa] text-zinc-900">

      {/* =================================================
          SIDEBAR
      ================================================= */}

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-zinc-200 bg-white lg:block">

        <div className="flex h-full flex-col">

          {/* Brand */}

          <div className="flex h-20 items-center border-b border-zinc-100 px-6">

            <div className="flex items-center gap-3">

              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 text-white">
                <BrainCircuit
                  size={20}
                />
              </div>

              <div>

                <p className="text-sm font-bold tracking-tight">
                  DocuMind
                </p>

                <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                  Pranjul's AI
                </p>

              </div>

            </div>

          </div>


          {/* Navigation */}

          <nav className="flex-1 space-y-1 p-4">

            <NavItem
              icon={
                <LayoutDashboard
                  size={17}
                />
              }
              label="Dashboard"
              active={
                activeView ===
                VIEWS.DASHBOARD
              }
              onClick={() =>
                navigate(
                  VIEWS.DASHBOARD
                )
              }
            />

            <NavItem
              icon={
                <FolderOpen
                  size={17}
                />
              }
              label="Documents"
              active={
                activeView ===
                VIEWS.DOCUMENTS
              }
              onClick={() =>
                navigate(
                  VIEWS.DOCUMENTS
                )
              }
            />

            <NavItem
              icon={
                <Sparkles
                  size={17}
                />
              }
              label="Intelligence"
              active={
                activeView ===
                VIEWS.INTELLIGENCE
              }
              onClick={() =>
                navigate(
                  VIEWS.INTELLIGENCE
                )
              }
              disabled={
                !activeDocument
              }
            />

            <NavItem
              icon={
                <Workflow
                  size={17}
                />
              }
              label="Action Workflow"
              active={
                activeView ===
                VIEWS.WORKFLOW
              }
              onClick={() =>
                navigate(
                  VIEWS.WORKFLOW
                )
              }
              disabled={
                !activeDocument
              }
            />

            <NavItem
              icon={
                <Bot size={17} />
              }
              label="AI Assistant"
              active={
                activeView ===
                VIEWS.ASSISTANT
              }
              onClick={() =>
                navigate(
                  VIEWS.ASSISTANT
                )
              }
              disabled={
                !activeDocument
              }
            />

          </nav>


          {/* Active document */}

          <div className="border-t border-zinc-100 p-4">

            <p className="px-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
              Active document
            </p>

            {activeDocument ? (
              <button
                onClick={() =>
                  navigate(
                    VIEWS.DOCUMENTS
                  )
                }
                className="mt-2 flex w-full items-center gap-3 rounded-xl bg-zinc-50 p-3 text-left hover:bg-zinc-100"
              >

                <FileText
                  size={16}
                  className="shrink-0 text-zinc-500"
                />

                <div className="min-w-0">

                  <p className="truncate text-xs font-medium text-zinc-800">
                    {
                      activeDocument.filename
                    }
                  </p>

                  <p className="mt-0.5 text-[10px] text-zinc-400">
                    {
                      activeDocument.status ||
                      "unknown"
                    }
                  </p>

                </div>

              </button>
            ) : (
              <p className="px-2 pt-2 text-xs text-zinc-400">
                No document selected
              </p>
            )}

          </div>

        </div>

      </aside>


      {/* =================================================
          MAIN
      ================================================= */}

      <main className="lg:pl-64">

        {/* Header */}

        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-zinc-200 bg-white/90 px-5 backdrop-blur lg:px-8">

          <div className="min-w-0">

            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
              Workspace
            </p>

            <h1 className="truncate text-sm font-semibold text-zinc-900">
              {pageTitle(
                activeView
              )}
            </h1>

          </div>


          <div className="flex items-center gap-2">

            {activeDocument && (
              <div className="hidden max-w-[260px] items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 sm:flex">

                <FileText
                  size={13}
                  className="shrink-0 text-zinc-400"
                />

                <span className="truncate text-xs text-zinc-500">
                  {
                    activeDocument.filename
                  }
                </span>

              </div>
            )}

            <button
              onClick={() =>
                setRefreshKey(
                  (value) =>
                    value + 1
                )
              }
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              title="Refresh"
            >
              <RefreshCw
                size={15}
              />
            </button>

          </div>

        </header>


        {/* Mobile navigation */}

        <div className="flex gap-1 overflow-x-auto border-b border-zinc-200 bg-white px-4 py-2 lg:hidden">

          <MobileNavItem
            label="Dashboard"
            active={
              activeView ===
              VIEWS.DASHBOARD
            }
            onClick={() =>
              navigate(
                VIEWS.DASHBOARD
              )
            }
          />

          <MobileNavItem
            label="Documents"
            active={
              activeView ===
              VIEWS.DOCUMENTS
            }
            onClick={() =>
              navigate(
                VIEWS.DOCUMENTS
              )
            }
          />

          <MobileNavItem
            label="Intelligence"
            active={
              activeView ===
              VIEWS.INTELLIGENCE
            }
            onClick={() =>
              navigate(
                VIEWS.INTELLIGENCE
              )
            }
            disabled={
              !activeDocument
            }
          />

          <MobileNavItem
            label="Workflow"
            active={
              activeView ===
              VIEWS.WORKFLOW
            }
            onClick={() =>
              navigate(
                VIEWS.WORKFLOW
              )
            }
            disabled={
              !activeDocument
            }
          />

          <MobileNavItem
            label="Assistant"
            active={
              activeView ===
              VIEWS.ASSISTANT
            }
            onClick={() =>
              navigate(
                VIEWS.ASSISTANT
              )
            }
            disabled={
              !activeDocument
            }
          />

        </div>


        {/* Page */}

        <div className="mx-auto max-w-[1500px] p-5 lg:p-8">

          {/* Global error */}

          {pageError && (
            <div className="mb-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3">

              <ShieldAlert
                size={17}
                className="mt-0.5 shrink-0 text-red-600"
              />

              <div className="min-w-0">

                <p className="text-sm font-semibold text-red-800">
                  Something went wrong
                </p>

                <p className="mt-1 text-xs leading-5 text-red-700">
                  {pageError}
                </p>

              </div>

            </div>
          )}


          {/* =================================================
              DASHBOARD
          ================================================= */}

          {activeView ===
            VIEWS.DASHBOARD && (
            <DashboardView
              documents={
                documents
              }
              completedDocuments={
                completedDocuments
              }
              processingDocuments={
                processingDocuments
              }
              failedDocuments={
                failedDocuments
              }
              loading={
                loadingDocuments
              }
              onOpenDocuments={() =>
                navigate(
                  VIEWS.DOCUMENTS
                )
              }
              onSelectDocument={
                selectDocument
              }
            />
          )}


          {/* =================================================
              DOCUMENTS
          ================================================= */}

          {activeView ===
            VIEWS.DOCUMENTS && (
            <DocumentsView
              onUploaded={handleUploaded}
              documents={
                documents
              }
              loading={
                loadingDocuments
              }
              activeDocument={
                activeDocument
              }
              onSelectDocument={
                selectDocument
              }
              onRefresh={() =>
                setRefreshKey(
                  (value) =>
                    value + 1
                )
              }
            />
          )}


          {/* =================================================
              INTELLIGENCE
          ================================================= */}

          {activeView ===
            VIEWS.INTELLIGENCE && (
            <section className="space-y-6">

              {!activeDocument ? (
                <EmptyState
                  icon={
                    <FileText
                      size={23}
                    />
                  }
                  title="No document selected"
                  description="Select a processed document before opening Document Intelligence."
                  actionLabel="Open documents"
                  onAction={() =>
                    navigate(
                      VIEWS.DOCUMENTS
                    )
                  }
                />
              ) : activeDocument.status !==
                "completed" ? (
                <div className="space-y-6">

                  <ProcessingPipeline
                    status={
                      activeDocument.status
                    }
                    filename={
                      activeDocument.filename
                    }
                  />

                  <div className="flex justify-center">

                    <button
                      onClick={
                        refreshActiveDocument
                      }
                      className="inline-flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                    >
                      <RefreshCw
                        size={15}
                      />
                      Check status
                    </button>

                  </div>

                </div>
              ) : !analysis ? (
                <IntelligenceStart
                  document={
                    activeDocument
                  }
                  analyzing={
                    analyzing
                  }
                  onAnalyze={
                    handleAnalyzeDocument
                  }
                />
              ) : (
                <DocumentIntelligence
                  analysis={
                    analysis
                  }
                  onGenerateWorkflow={
                    handleGenerateWorkflow
                  }
                  generatingWorkflow={
                    generatingWorkflow
                  }
                />
              )}

            </section>
          )}


          {/* =================================================
              WORKFLOW
          ================================================= */}

          {activeView ===
            VIEWS.WORKFLOW && (
            <section className="space-y-6">

              {!activeDocument ? (
                <EmptyState
                  icon={
                    <Workflow
                      size={23}
                    />
                  }
                  title="No document selected"
                  description="Select a processed document before generating an action workflow."
                  actionLabel="Open documents"
                  onAction={() =>
                    navigate(
                      VIEWS.DOCUMENTS
                    )
                  }
                />
              ) : !workflow ? (
                <WorkflowStart
                  document={
                    activeDocument
                  }
                  generating={
                    generatingWorkflow
                  }
                  onGenerate={
                    handleGenerateWorkflow
                  }
                />
              ) : (
                <WorkflowPanel
                  workflow={
                    workflow
                  }
                />
              )}

            </section>
          )}


          {/* =================================================
              ASSISTANT
          ================================================= */}

          {activeView ===
            VIEWS.ASSISTANT && (
            <section>

              {!activeDocument ? (
                <EmptyState
                  icon={
                    <Bot size={23} />
                  }
                  title="No document selected"
                  description="Select a processed document before using the AI Assistant."
                  actionLabel="Open documents"
                  onAction={() =>
                    navigate(
                      VIEWS.DOCUMENTS
                    )
                  }
                />
              ) : activeDocument.status !==
                "completed" ? (
                <EmptyState
                  icon={
                    <Loader2
                      size={23}
                    />
                  }
                  title="Document is still processing"
                  description="The AI Assistant becomes available after document processing and embeddings are complete."
                  actionLabel="Check document"
                  onAction={() =>
                    navigate(
                      VIEWS.DOCUMENTS
                    )
                  }
                />
              ) : (
                <AIAssistant
                  fileId={
                    activeDocument.file_id
                  }
                  filename={
                    activeDocument.filename
                  }
                />
              )}

            </section>
          )}

        </div>

      </main>

    </div>
  );
}


/* =====================================================
   DASHBOARD
===================================================== */

function DashboardView({
  documents,
  completedDocuments,
  processingDocuments,
  failedDocuments,
  loading,
  onOpenDocuments,
  onSelectDocument,
}) {
  const recent =
    documents.slice(
      0,
      5
    );

  return (
    <div className="space-y-8">

      <div>

        <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Overview
        </p>

        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-900">
          Document intelligence workspace
        </h2>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">
          Upload business documents, extract structured intelligence, identify risks, generate workflows, and ask grounded questions.
        </p>

      </div>


      {/* Metrics */}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <MetricCard
          icon={
            <FileText
              size={18}
            />
          }
          label="Total documents"
          value={
            documents.length
          }
        />

        <MetricCard
          icon={
            <Sparkles
              size={18}
            />
          }
          label="Ready for AI"
          value={
            completedDocuments.length
          }
        />

        <MetricCard
          icon={
            <Activity
              size={18}
            />
          }
          label="Processing"
          value={
            processingDocuments.length
          }
        />

        <MetricCard
          icon={
            <ShieldAlert
              size={18}
            />
          }
          label="Failed"
          value={
            failedDocuments.length
          }
        />

      </div>


      {/* Quick start */}

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">

        <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm">

          <div className="flex items-start justify-between">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Quick start
              </p>

              <h3 className="mt-1 text-lg font-semibold">
                Analyze a new document
              </h3>

              <p className="mt-2 max-w-lg text-sm leading-6 text-zinc-500">
                Start with a contract, policy, report, or other business document.
              </p>

            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-100">
              <Upload
                size={18}
              />
            </div>

          </div>

          <button
            onClick={
              onOpenDocuments
            }
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-zinc-700"
          >
            Upload document
            <ChevronRight
              size={15}
            />
          </button>

        </div>


        <div className="rounded-3xl border border-zinc-200 bg-zinc-900 p-6 text-white">

          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
            <Bot size={18} />
          </div>

          <h3 className="mt-5 text-lg font-semibold">
            Grounded AI Assistant
          </h3>

          <p className="mt-2 text-sm leading-6 text-zinc-300">
            Ask questions about an uploaded document and receive answers backed by retrieved document sources.
          </p>

        </div>

      </div>


      {/* Recent documents */}

      <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm">

        <div className="flex items-center justify-between">

          <div>

            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Recent
            </p>

            <h3 className="mt-1 text-lg font-semibold">
              Recent documents
            </h3>

          </div>

          <button
            onClick={
              onOpenDocuments
            }
            className="text-xs font-semibold text-zinc-500 hover:text-zinc-900"
          >
            View all
          </button>

        </div>

        <div className="mt-5">

          {loading ? (
            <LoadingRow />
          ) : recent.length ===
            0 ? (
            <EmptyText>
              No documents have been uploaded yet.
            </EmptyText>
          ) : (
            <div className="divide-y divide-zinc-100">

              {recent.map(
                (document) => (
                  <DocumentRow
                    key={
                      document.file_id ||
                      document._id
                    }
                    document={
                      document
                    }
                    onClick={() =>
                      onSelectDocument(
                        document
                      )
                    }
                  />
                )
              )}

            </div>
          )}

        </div>

      </div>

    </div>
  );
}


/* =====================================================
   DOCUMENTS VIEW
===================================================== */

function DocumentsView({
  documents,
  loading,
  activeDocument,
  onSelectDocument,
  onRefresh,
  onUploaded,
}) {
  return (
    <div className="space-y-7">

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">

        <div>

          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Library
          </p>

          <h2 className="mt-1 text-2xl font-semibold tracking-tight">
            Documents
          </h2>

          <p className="mt-2 text-sm text-zinc-500">
            Upload and select documents to work with.
          </p>

        </div>

        <button
          onClick={
            onRefresh
          }
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          <RefreshCw
            size={15}
          />
          Refresh
        </button>

      </div>


      {/* Upload */}

      <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm">

        <UploadDocument
          onUploaded={
            onUploaded
          }
        />

      </div>


      {/* History */}

      <div className="rounded-3xl border border-zinc-200 bg-white shadow-sm">

        <div className="border-b border-zinc-100 p-6">

          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            History
          </p>

          <h3 className="mt-1 text-lg font-semibold">
            Uploaded documents
          </h3>

        </div>

        {loading ? (
          <div className="p-6">
            <LoadingRow />
          </div>
        ) : documents.length ===
          0 ? (
          <div className="p-6">
            <EmptyText>
              No documents found.
            </EmptyText>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">

            {documents.map(
              (document) => {
                const id =
                  document.file_id ||
                  document._id;

                const isActive =
                  (
                    activeDocument?.file_id ||
                    activeDocument?._id
                  ) === id;

                return (
                  <DocumentRow
                    key={id}
                    document={
                      document
                    }
                    active={
                      isActive
                    }
                    onClick={() =>
                      onSelectDocument(
                        document
                      )
                    }
                  />
                );
              }
            )}

          </div>
        )}

      </div>

    </div>
  );
}


/* =====================================================
   INTELLIGENCE START
===================================================== */

function IntelligenceStart({
  document,
  analyzing,
  onAnalyze,
}) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">

      <div className="mx-auto max-w-2xl text-center">

        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 text-white">
          <Sparkles
            size={24}
          />
        </div>

        <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Ready for analysis
        </p>

        <h2 className="mt-1 text-2xl font-semibold tracking-tight">
          Understand the document
        </h2>

        <p className="mt-3 text-sm leading-6 text-zinc-500">
          The document has completed ingestion, knowledge-base creation, and embedding generation. Run Document Intelligence to extract structured information and risks.
        </p>

        <div className="mx-auto mt-6 max-w-md rounded-2xl bg-zinc-50 p-4 text-left">

          <div className="flex items-center gap-3">

            <FileText
              size={18}
              className="shrink-0 text-zinc-500"
            />

            <div className="min-w-0">

              <p className="truncate text-sm font-semibold text-zinc-800">
                {
                  document.filename
                }
              </p>

              <p className="mt-1 text-xs text-zinc-400">
                Processing completed
              </p>

            </div>

          </div>

        </div>

        <button
          onClick={
            onAnalyze
          }
          disabled={
            analyzing
          }
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-3 text-sm font-semibold text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
        >

          {analyzing ? (
            <>
              <Loader2
                size={16}
                className="animate-spin"
              />
              Analyzing document...
            </>
          ) : (
            <>
              <BrainCircuit
                size={16}
              />
              Run Document Intelligence
            </>
          )}

        </button>

      </div>

    </div>
  );
}


/* =====================================================
   WORKFLOW START
===================================================== */

function WorkflowStart({
  document,
  generating,
  onGenerate,
}) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">

      <div className="mx-auto max-w-2xl text-center">

        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-900 text-white">
          <Workflow
            size={24}
          />
        </div>

        <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          Agent 3
        </p>

        <h2 className="mt-1 text-2xl font-semibold tracking-tight">
          Generate an action workflow
        </h2>

        <p className="mt-3 text-sm leading-6 text-zinc-500">
          Workflow Agent consumes the structured document intelligence and turns it into prioritized actions, upcoming tasks, monitoring items, and human-approval requirements.
        </p>

        <div className="mt-6 rounded-2xl bg-zinc-50 p-4 text-left">

          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Document
          </p>

          <p className="mt-1 truncate text-sm font-semibold text-zinc-800">
            {
              document.filename
            }
          </p>

        </div>

        <button
          onClick={
            onGenerate
          }
          disabled={
            generating
          }
          className="mt-6 inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-3 text-sm font-semibold text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
        >

          {generating ? (
            <>
              <Loader2
                size={16}
                className="animate-spin"
              />
              Generating action plan...
            </>
          ) : (
            <>
              <Workflow
                size={16}
              />
              Generate action plan
            </>
          )}

        </button>

      </div>

    </div>
  );
}


/* =====================================================
   NAV ITEM
===================================================== */

function NavItem({
  icon,
  label,
  active,
  onClick,
  disabled = false,
}) {
  return (
    <button
      onClick={
        onClick
      }
      disabled={
        disabled
      }
      className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
        active
          ? "bg-zinc-100 font-semibold text-zinc-900"
          : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
      } ${
        disabled
          ? "cursor-not-allowed opacity-35"
          : ""
      }`}
    >

      {icon}

      <span>
        {label}
      </span>

    </button>
  );
}


/* =====================================================
   MOBILE NAV
===================================================== */

function MobileNavItem({
  label,
  active,
  onClick,
  disabled = false,
}) {
  return (
    <button
      onClick={
        onClick
      }
      disabled={
        disabled
      }
      className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium ${
        active
          ? "bg-zinc-900 text-white"
          : "text-zinc-500 hover:bg-zinc-100"
      } ${
        disabled
          ? "cursor-not-allowed opacity-30"
          : ""
      }`}
    >
      {label}
    </button>
  );
}


/* =====================================================
   DOCUMENT ROW
===================================================== */

function DocumentRow({
  document,
  active = false,
  onClick,
}) {
  const status =
    String(
      document.status ||
        "unknown"
    ).toLowerCase();

  const statusStyle =
    status === "completed"
      ? "bg-emerald-50 text-emerald-700"
      : status === "failed"
      ? "bg-red-50 text-red-700"
      : "bg-zinc-100 text-zinc-600";

  return (
    <button
      onClick={
        onClick
      }
      className={`flex w-full items-center gap-4 px-6 py-4 text-left transition hover:bg-zinc-50 ${
        active
          ? "bg-zinc-50"
          : ""
      }`}
    >

      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-500">
        <FileText
          size={18}
        />
      </div>

      <div className="min-w-0 flex-1">

        <p className="truncate text-sm font-semibold text-zinc-800">
          {
            document.filename ||
            "Untitled document"
          }
        </p>

        <p className="mt-1 truncate text-xs text-zinc-400">
          {
            document.file_id ||
            document._id ||
            "No ID"
          }
        </p>

      </div>

      <span
        className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusStyle}`}
      >
        {status}
      </span>

      <ChevronRight
        size={15}
        className="shrink-0 text-zinc-300"
      />

    </button>
  );
}


/* =====================================================
   METRIC CARD
===================================================== */

function MetricCard({
  icon,
  label,
  value,
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">

      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600">
        {icon}
      </div>

      <p className="mt-4 text-xs font-medium text-zinc-400">
        {label}
      </p>

      <p className="mt-1 text-2xl font-semibold tracking-tight">
        {value}
      </p>

    </div>
  );
}


/* =====================================================
   EMPTY STATE
===================================================== */

function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-10 shadow-sm">

      <div className="mx-auto max-w-md text-center">

        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-500">
          {icon}
        </div>

        <h2 className="mt-5 text-lg font-semibold">
          {title}
        </h2>

        <p className="mt-2 text-sm leading-6 text-zinc-500">
          {description}
        </p>

        {actionLabel && (
          <button
            onClick={
              onAction
            }
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-zinc-700"
          >
            {actionLabel}
            <ChevronRight
              size={15}
            />
          </button>
        )}

      </div>

    </div>
  );
}


/* =====================================================
   SMALL HELPERS
===================================================== */

function LoadingRow() {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-sm text-zinc-400">

      <Loader2
        size={16}
        className="animate-spin"
      />

      Loading documents...

    </div>
  );
}

function EmptyText({
  children,
}) {
  return (
    <div className="rounded-2xl bg-zinc-50 p-5 text-center text-sm text-zinc-400">
      {children}
    </div>
  );
}

function pageTitle(
  view
) {
  switch (view) {
    case VIEWS.DOCUMENTS:
      return "Documents";

    case VIEWS.INTELLIGENCE:
      return "Document Intelligence";

    case VIEWS.WORKFLOW:
      return "Action Workflow";

    case VIEWS.ASSISTANT:
      return "AI Assistant";

    default:
      return "Dashboard";
  }
}
