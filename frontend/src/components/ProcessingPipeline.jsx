import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";

const STEPS = [
  {
    key: "queued",
    label: "Document uploaded",
    description: "File received successfully",
  },
  {
    key: "processing",
    label: "Preparing document",
    description: "Converting document for AI processing",
  },
  {
    key: "extracting_text",
    label: "AI text extraction",
    description: "Gemini is extracting document content",
  },
  {
    key: "creating_knowledge_base",
    label: "Knowledge base",
    description: "Creating searchable document chunks",
  },
  {
    key: "creating_chunk_embeddings",
    label: "Embeddings",
    description: "Creating semantic representations",
  },
  {
    key: "completed",
    label: "Document ready",
    description: "Document is ready for AI analysis",
  },
];

const STATUS_ORDER = [
  "queued",
  "processing",
  "extracting_text",
  "creating_knowledge_base",
  "creating_chunk_embeddings",
  "completed",
];

function normalizeStatus(status) {
  return String(status || "queued")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_");
}

function getStepState(stepKey, currentStatus) {
  const status = normalizeStatus(currentStatus);

  if (status === "failed") {
    return "failed";
  }

  const currentIndex = STATUS_ORDER.indexOf(status);

  const stepIndex = STATUS_ORDER.indexOf(stepKey);

  if (currentIndex === -1 || stepIndex === -1) {
    return "pending";
  }

  if (stepIndex < currentIndex) {
    return "completed";
  }

  if (stepIndex === currentIndex) {
    return "active";
  }

  return "pending";
}

export default function ProcessingPipeline({ status, filename }) {
  const normalizedStatus = normalizeStatus(status);

  const progressMap = {
    queued: 8,
    processing: 22,
    extracting_text: 42,
    creating_knowledge_base: 64,
    creating_chunk_embeddings: 84,
    completed: 100,
    failed: 100,
  };

  const progress = progressMap[normalizedStatus] ?? 8;

  return (
    <div className="w-full rounded-2xl border border-line bg-surface p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-wider text-secondary">
            Live document pipeline
          </p>

          <h3 className="mt-1 truncate text-lg font-semibold text-primary">
            {filename || "Document"}
          </h3>
        </div>

        {normalizedStatus === "failed" ? (
          <div className="flex shrink-0 items-center gap-2 rounded-full bg-danger-soft px-3 py-1.5 text-xs font-medium text-danger">
            <AlertCircle size={14} />
            Failed
          </div>
        ) : normalizedStatus === "completed" ? (
          <div className="flex shrink-0 items-center gap-2 rounded-full bg-success-soft px-3 py-1.5 text-xs font-medium text-success">
            <CheckCircle2 size={14} />
            Ready
          </div>
        ) : (
          <div className="flex shrink-0 items-center gap-2 rounded-full bg-raised px-3 py-1.5 text-xs font-medium text-primary">
            <Loader2 size={14} className="animate-spin" />
            Processing
          </div>
        )}
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs text-secondary">AI pipeline progress</span>

          <span className="text-xs font-semibold text-primary">
            {progress}%
          </span>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-raised">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              normalizedStatus === "failed"
                ? "bg-danger-soft"
                : normalizedStatus === "completed"
                  ? "bg-success-soft"
                  : "bg-accent"
            }`}
            style={{
              width: `${progress}%`,
            }}
          />
        </div>
      </div>

      <div className="mt-7">
        {STEPS.map((step, index) => {
          const state = getStepState(step.key, normalizedStatus);

          return (
            <div key={step.key} className="relative flex gap-4">
              {index < STEPS.length - 1 && (
                <div
                  className={`absolute left-[11px] top-7 h-[calc(100%-8px)] w-px ${
                    state === "completed" ? "bg-success-soft" : "bg-zinc-200"
                  }`}
                />
              )}

              <div className="relative z-10 shrink-0">
                {state === "completed" ? (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-success-soft text-success">
                    <CheckCircle2 size={16} />
                  </div>
                ) : state === "active" ? (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-on-accent">
                    <Loader2 size={14} className="animate-spin" />
                  </div>
                ) : state === "failed" ? (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-danger-soft text-danger">
                    <AlertCircle size={16} />
                  </div>
                ) : (
                  <div className="flex h-6 w-6 items-center justify-center text-secondary">
                    <Circle size={16} />
                  </div>
                )}
              </div>

              <div className="pb-6">
                <p
                  className={`text-sm font-medium ${
                    state === "completed" || state === "active"
                      ? "text-primary"
                      : state === "failed"
                        ? "text-danger"
                        : "text-secondary"
                  }`}
                >
                  {step.label}
                </p>

                <p className="mt-0.5 text-xs text-secondary">
                  {step.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {normalizedStatus !== "completed" && normalizedStatus !== "failed" && (
        <div className="mt-2 flex items-center gap-2 border-t border-line pt-4 text-xs text-secondary">
          <span className="h-2 w-2 animate-pulse rounded-full bg-success-soft" />
          Live status updates every 2.5 seconds
        </div>
      )}
    </div>
  );
}
