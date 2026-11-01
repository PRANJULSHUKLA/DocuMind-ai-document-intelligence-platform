import { useEffect, useState } from "react";
import { Download, FileCheck2, RefreshCw, Trash2 } from "lucide-react";
import { Button, Skeleton, StatusMessage } from "./ui";
import {
  listReports,
  readReport,
  deleteReport,
  downloadReport,
} from "../services/reportService";

export default function SavedComparisonReports({ onSourceSelect }) {
  const [loading, setLoading] = useState(true);
  const [download, setDownload] = useState("");
  const [rows, setRows] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    const result = await listReports();
    if (!Array.isArray(result))
      throw new Error("Invalid report-list response.");
    setRows(result);
    setLoading(false);
  }
  useEffect(() => {
    let active = true;
    listReports()
      .then((result) => {
        if (active && Array.isArray(result)) setRows(result);
      })
      .catch(() => {
        if (active)
          setError("Saved reports are unavailable. Refresh to retry.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function action(operation) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (failure) {
      setError(
        failure.response?.data?.detail ||
          failure.message ||
          "Report action failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      aria-label="Saved comparison reports"
      className="ui-card space-y-4 p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <FileCheck2 size={20} className="text-accent" />
          <h3 className="text-xl font-semibold">Saved comparison reports</h3>
        </div>
        <Button disabled={busy} onClick={() => action(refresh)}>
          <RefreshCw size={15} />
          Refresh saved reports
        </Button>
      </div>
      <p className="text-sm text-secondary">
        Snapshots stay until explicitly deleted. Source or collection deletion
        does not delete a report. If source access is lost, content and exports
        are withheld. Exports make no model calls.
      </p>
      {error && (
        <StatusMessage tone="error" title="Report action unavailable">
          {error}
        </StatusMessage>
      )}
      {rows.map((row) => (
        <div
          className="report-row flex flex-wrap items-center gap-2"
          key={row.id}
        >
          <button
            disabled={busy}
            onClick={() =>
              action(async () => setReport(await readReport(row.id)))
            }
            className="ui-button ui-button--secondary min-w-0 break-words"
          >
            Open report: {row.title}
          </button>
          <button
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Delete this saved report? Original documents will be kept.",
                )
              )
                action(async () => {
                  await deleteReport(row.id);
                  if (report?.id === row.id) setReport(null);
                  await refresh();
                });
            }}
            aria-label={`Delete report: ${row.title}`}
            className="ui-button ui-button--danger"
          >
            <Trash2 size={15} />
            Delete
          </button>
        </div>
      ))}
      {loading ? (
        <Skeleton label="Loading saved reports" rows={2} />
      ) : (
        !rows.length &&
        !error && (
          <p className="rounded-lg border border-dashed border-line bg-muted p-5 text-sm text-secondary">
            No saved reports loaded.
          </p>
        )
      )}
      {report && (
        <article className="space-y-4 rounded-xl border border-line bg-muted p-5">
          <h4 className="font-semibold">{report.title}</h4>
          <p className="text-xs text-secondary tabular-nums">
            Saved {report.created_at} ·{" "}
            {report.snapshot.method.replaceAll("_", " ")}
          </p>
          <p
            role="status"
            className={`rounded-lg p-3 text-sm ${report.stale ? "bg-warning-soft text-warning" : "bg-success-soft text-success"}`}
          >
            {report.stale
              ? "STALE: source revisions changed. Review the originals before relying on this snapshot."
              : "Source revisions matched when this report was opened. Exports check again."}
          </p>
          <div className="flex gap-2">
            {["json", "pdf"].map((format) => (
              <Button
                key={format}
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    setDownload(format);
                    try {
                      await downloadReport(report.id, format);
                    } finally {
                      setDownload("");
                    }
                  })
                }
              >
                <Download size={15} />
                Export {format.toUpperCase()}
              </Button>
            ))}
          </div>
          {download && (
            <p role="status" className="text-sm text-secondary">
              Preparing {download.toUpperCase()} download…
            </p>
          )}
          {report.snapshot.limitations.map((text, index) => (
            <p key={index} className="text-sm text-secondary">
              {text}
            </p>
          ))}
          {report.snapshot.findings.map((finding, index) => (
            <div key={index}>
              <h5 className="font-medium">
                {finding.topic} · {finding.classification.replaceAll("_", " ")}
              </h5>
              <p>{finding.explanation}</p>
            </div>
          ))}
          <details>
            <summary>Saved evidence passages</summary>
            {report.snapshot.sources.map((source) => (
              <button
                key={source.evidence_id}
                className="my-2 block w-full rounded border p-2 text-left"
                onClick={() => onSourceSelect(source)}
              >
                {source.filename} · Page {source.page_number}
                <blockquote>{source.excerpt}</blockquote>
              </button>
            ))}
          </details>
        </article>
      )}
    </section>
  );
}
