
import { useRef, useState } from "react";

import {
  Upload,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

import {
  uploadDocument,
  getDocumentStatus,
} from "../services/documentService";

const MAX_FILE_SIZE_MB = 25;
const MAX_POLL_ATTEMPTS = 240;
const POLL_INTERVAL_MS = 2500;

function normalizeStatus(status) {
  if (!status) {
    return "queued";
  }

  const value = String(status).toLowerCase().trim();

  const statusMap = {
    saving: "queued",
    queued: "queued",
    processing: "processing",
    "extracting text": "extracting_text",
    extracting_text: "extracting_text",
    "creating knowledge base": "creating_knowledge_base",
    creating_knowledge_base: "creating_knowledge_base",
    "creating chunk embeddings": "creating_chunk_embeddings",
    creating_chunk_embeddings: "creating_chunk_embeddings",
    completed: "completed",
    failed: "failed",
  };

  return statusMap[value] || value;
}

function getErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || String(item))
      .join(", ");
  }

  return error?.message || fallback;
}

function PipelineStep({
  label,
  active = false,
  completed = false,
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex h-5 w-5 items-center justify-center rounded-full ${
          completed
            ? "bg-emerald-100 text-emerald-600"
            : active
              ? "bg-zinc-900 text-white"
              : "bg-zinc-100 text-zinc-400"
        }`}
      >
        {completed ? "✓" : "•"}
      </div>

      <span
        className={
          completed || active
            ? "text-zinc-800"
            : "text-zinc-400"
        }
      >
        {label}
      </span>
    </div>
  );
}

export default function UploadDocument({ onUploaded }) {
  const inputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const statusLabels = {
    queued: "Queued for processing",
    processing: "Processing document",
    extracting_text: "Extracting document text",
    creating_knowledge_base: "Building knowledge base",
    creating_chunk_embeddings: "Creating embeddings",
    completed: "Document ready",
    failed: "Processing failed",
  };

  function handleFileSelect(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setError("");
    setStatus("");

    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
      setSelectedFile(null);
      event.target.value = "";
      setError("Please select a PDF file. Other file formats are not supported by this upload flow.");
      return;
    }

    if (file.size === 0) {
      setSelectedFile(null);
      event.target.value = "";
      setError("The selected file is empty. Please choose a valid PDF.");
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setSelectedFile(null);
      event.target.value = "";
      setError(
        `The file exceeds the ${MAX_FILE_SIZE_MB} MB limit. Please choose a smaller PDF.`
      );
      return;
    }

    setSelectedFile(file);
  }

  function clearFile() {
    if (uploading) {
      return;
    }

    setSelectedFile(null);
    setStatus("");
    setError("");

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function pollStatus(fileId, filename) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
      try {
        const result = await getDocumentStatus(fileId);
        const normalizedStatus = normalizeStatus(result?.status);

        setStatus(normalizedStatus);

        if (normalizedStatus === "completed") {
          setUploading(false);

          onUploaded?.({
            file_id: fileId,
            _id: fileId,
            filename,
            status: "completed",
          });

          return;
        }

        if (normalizedStatus === "failed") {
          setUploading(false);
          setError(
            result?.error ||
              result?.message ||
              "Document processing failed. Check the backend logs for the cause."
          );
          return;
        }

        await new Promise((resolve) =>
          setTimeout(resolve, POLL_INTERVAL_MS)
        );
      } catch (err) {
        console.error("Document status polling failed:", err);
        setUploading(false);
        setError(
          getErrorMessage(
            err,
            "Unable to check document status. Check whether the backend is running."
          )
        );
        return;
      }
    }

    setUploading(false);
    setError(
      "Processing is taking longer than expected. The document may still be processing. Check its status before uploading it again."
    );
  }

  async function handleUpload() {
    if (!selectedFile || uploading) {
      return;
    }

    const file = selectedFile;

    setUploading(true);
    setError("");
    setStatus("queued");

    try {
      const result = await uploadDocument(file);

      const fileId =
        result?.file_id ||
        result?._id ||
        result?.id;

      if (!fileId) {
        throw new Error(
          "The backend response did not contain a document ID."
        );
      }

      await pollStatus(String(fileId), file.name);
    } catch (err) {
      console.error("Document upload failed:", err);

      setUploading(false);
      setError(
        getErrorMessage(
          err,
          "Unable to upload the document. Check the backend and try again."
        )
      );
    }
  }

  const progressWidth = {
    queued: "10%",
    processing: "25%",
    extracting_text: "45%",
    creating_knowledge_base: "65%",
    creating_chunk_embeddings: "85%",
  }[status] || "95%";

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="flex justify-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100">
          <Upload size={22} />
        </div>
      </div>

      <h3 className="mt-4 text-center font-semibold">
        Analyze a new document
      </h3>

      <p className="mx-auto mt-2 max-w-md text-center text-sm text-zinc-500">
        Upload a PDF contract, policy, report, or other business document
        to start the document intelligence pipeline.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileSelect}
        className="hidden"
        disabled={uploading}
      />

      {!selectedFile && !uploading && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => {
              setError("");
              inputRef.current?.click();
            }}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-700"
          >
            <Upload size={16} />
            Choose PDF
          </button>
        </div>
      )}

      {selectedFile && (
        <div className="mx-auto mt-6 max-w-md rounded-2xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white">
                <FileText size={17} />
              </div>

              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {selectedFile.name}
                </p>

                <p className="text-xs text-zinc-400">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            </div>

            {!uploading && (
              <button
                type="button"
                onClick={clearFile}
                aria-label="Remove selected file"
                className="rounded-lg p-2 text-zinc-400 hover:bg-white hover:text-zinc-900"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {!uploading && status !== "completed" && (
            <button
              type="button"
              onClick={handleUpload}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-700"
            >
              <Upload size={16} />
              {status === "failed" || error
                ? "Try upload again"
                : "Start analysis"}
            </button>
          )}
        </div>
      )}

      {uploading && (
        <div className="mx-auto mt-6 max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-zinc-100">
              <Loader2 size={21} className="animate-spin" />
            </div>

            <div className="min-w-0">
              <p className="text-sm font-semibold">
                Processing document
              </p>

              <p className="mt-1 text-sm text-zinc-500">
                {statusLabels[status] || "Processing..."}
              </p>
            </div>
          </div>

          <div className="mt-5 h-2 overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full rounded-full bg-zinc-900 transition-all duration-700"
              style={{ width: progressWidth }}
            />
          </div>

          <div className="mt-4 space-y-2 text-xs">
            <PipelineStep
              label="Document uploaded"
              active={status === "queued"}
              completed={[
                "processing",
                "extracting_text",
                "creating_knowledge_base",
                "creating_chunk_embeddings",
                "completed",
              ].includes(status)}
            />

            <PipelineStep
              label="Text extraction"
              active={status === "extracting_text"}
              completed={[
                "creating_knowledge_base",
                "creating_chunk_embeddings",
                "completed",
              ].includes(status)}
            />

            <PipelineStep
              label="Knowledge base"
              active={status === "creating_knowledge_base"}
              completed={[
                "creating_chunk_embeddings",
                "completed",
              ].includes(status)}
            />

            <PipelineStep
              label="Embeddings"
              active={status === "creating_chunk_embeddings"}
              completed={status === "completed"}
            />
          </div>
        </div>
      )}

      {!uploading && status === "completed" && (
        <div className="mx-auto mt-6 max-w-md rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
          <div className="flex items-center gap-3">
            <CheckCircle2
              size={24}
              className="text-emerald-600"
            />

            <div>
              <p className="font-semibold text-emerald-900">
                Document ready
              </p>

              <p className="mt-1 text-sm text-emerald-700">
                AI processing has completed successfully.
              </p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mx-auto mt-4 flex max-w-md items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          <AlertCircle size={17} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
