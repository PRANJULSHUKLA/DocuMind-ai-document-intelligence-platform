import { useEffect, useRef, useState } from "react";
import { compareCollection } from "../services/collectionService";
import { ArrowLeftRight, Check, Save } from "lucide-react";
import { Badge, Button, StatusMessage } from "./ui";
import { saveReport } from "../services/reportService";

const labels = {
  supported_agreement: "Supported agreement",
  supported_difference: "Supported difference",
  possible_contradiction: "Possible contradiction",
  missing_information: "Missing information",
  insufficient_evidence: "Insufficient evidence",
};

export default function ComparisonPanel({
  collectionId,
  documents,
  onSourceSelect,
}) {
  const [selected, setSelected] = useState([]);
  const [focus, setFocus] = useState("Key amounts, dates and obligations");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [semantic, setSemantic] = useState(false);
  const [saved, setSaved] = useState("");
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  async function compare(event) {
    event.preventDefault();
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    setResult(null);
    setSaved("");
    try {
      const data = await compareCollection(
        collectionId,
        selected,
        focus,
        controller.signal,
        semantic,
      );
      if (!controller.signal.aborted) setResult(data);
    } catch (failure) {
      if (!controller.signal.aborted)
        setError(
          failure.response?.data?.detail || "Comparison failed. Please retry.",
        );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }
  return (
    <section aria-label="Document comparison" className="ui-card space-y-5 p-5">
      <div className="flex items-center gap-3">
        <div className="rounded-lg border border-line bg-muted p-2 text-accent">
          <ArrowLeftRight size={20} />
        </div>
        <div>
          <p className="eyebrow mb-1">Evidence review</p>
          <h3 className="text-xl font-semibold">Compare documents</h3>
        </div>
      </div>
      <p className="text-sm text-secondary">
        Compare explicit currency amounts, dates, and unconditional must/shall
        obligations in retrieved passages. Different wording alone is never a
        contradiction.
      </p>
      <form onSubmit={compare} className="space-y-4">
        <label className="flex items-start gap-2 rounded-lg border border-line bg-muted p-3 text-sm">
          <input
            type="checkbox"
            checked={semantic}
            disabled={loading}
            onChange={(event) => {
              setSemantic(event.target.checked);
              setResult(null);
            }}
          />{" "}
          Use validated obligation comparison (bounded)
        </label>
        {semantic && (
          <p className="text-sm text-secondary">
            Adds a small, verified wording grammar to literal findings from
            published OCR. Conditions and uncertain paraphrases require review.
            No general semantic equivalence or full-document completeness is
            claimed. No model call is made; the focus is a report label in this
            mode.
          </p>
        )}
        <fieldset
          disabled={loading}
          className="rounded-lg border border-line p-3"
        >
          <legend className="text-sm">
            Choose two to five completed documents
          </legend>
          {documents.map((doc) => {
            const id = doc._id || doc.file_id;
            return (
              <label key={id} className="selection-row text-sm">
                <input
                  type="checkbox"
                  checked={selected.includes(id)}
                  disabled={
                    doc.status !== "completed" ||
                    (!selected.includes(id) && selected.length >= 5)
                  }
                  onChange={(event) => {
                    setSelected((previous) =>
                      event.target.checked
                        ? [...previous, id]
                        : previous.filter((value) => value !== id),
                    );
                    setResult(null);
                  }}
                />{" "}
                {doc.filename} · {doc.status}
              </label>
            );
          })}
        </fieldset>
        <label className="block">
          Comparison focus
          <input
            aria-label="Comparison focus"
            required
            minLength={2}
            maxLength={500}
            disabled={loading}
            value={focus}
            onChange={(event) => {
              setFocus(event.target.value);
              setResult(null);
            }}
            className="mt-1 block w-full rounded border p-2"
          />
        </label>
        <Button
          type="submit"
          variant="primary"
          disabled={loading || selected.length < 2}
        >
          <ArrowLeftRight size={16} />
          {loading ? "Comparing evidence…" : "Compare selected documents"}
        </Button>
      </form>
      {error && (
        <StatusMessage tone="error" title="Comparison unavailable">
          {error}
        </StatusMessage>
      )}
      {result && (
        <div className="space-y-4" aria-label="Comparison findings">
          <h4 className="font-semibold">Comparison summary</h4>
          {result.review_digest && (
            <form
              className="space-y-3 rounded-lg border border-line bg-muted p-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const values = new FormData(event.currentTarget);
                setLoading(true);
                setError("");
                setSaved("");
                try {
                  const row = await saveReport(collectionId, {
                    file_ids: selected,
                    focus,
                    title: values.get("title"),
                    reviewed: true,
                    expected_digest: result.review_digest,
                  });
                  setSaved(
                    `Saved report: ${row.title}. Use Refresh saved reports below to open it.`,
                  );
                } catch (failure) {
                  setError(
                    failure.response?.data?.detail ||
                      "Could not save report. Review current findings and retry.",
                  );
                } finally {
                  setLoading(false);
                }
              }}
            >
              <label className="block">
                Report title
                <input
                  name="title"
                  aria-label="Report title"
                  required
                  maxLength={100}
                  disabled={loading}
                  className="mt-2 w-full rounded border p-2"
                />
              </label>
              <label className="block">
                <input
                  type="checkbox"
                  name="reviewed"
                  required
                  disabled={loading}
                />{" "}
                I reviewed these findings and their limitations
              </label>
              <Button type="submit" disabled={loading}>
                <Save size={16} />
                Save reviewed comparison
              </Button>
            </form>
          )}
          {saved && (
            <p
              role="status"
              className="flex gap-2 rounded-lg bg-success-soft p-3 text-sm text-success"
            >
              <Check size={18} />
              {saved}
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(result.summary).map(([label, count]) => (
              <div
                className="rounded-lg border border-line bg-muted p-3"
                key={label}
              >
                <p className="text-xs text-secondary">
                  {labels[label]} findings
                </p>
                <p className="mt-2 text-xl tabular-nums">{count}</p>
              </div>
            ))}
          </div>
          {result.limitations.map((text) => (
            <p key={text} className="text-xs text-secondary">
              {text}
            </p>
          ))}
          {result.extraction_limitations?.length > 0 && (
            <p role="status" className="text-sm text-warning">
              Some evidence was skipped or capped:{" "}
              {result.extraction_limitations
                .map((row) => `${row.file_id}: ${row.reason}`)
                .join("; ")}
            </p>
          )}
          {result.extraction_truncated && (
            <p role="status">
              Fact limit reached. Findings cover a partial sample.
            </p>
          )}
          {result.extracted_facts && (
            <details>
              <summary>
                Review structured evidence facts (
                {result.extracted_facts.length})
              </summary>
              {result.extracted_facts.map((fact) => (
                <article
                  className="mt-2 rounded border p-2 text-sm"
                  key={fact.fact_id}
                >
                  <p>
                    {fact.kind}: {Object.values(fact.value).join(" · ")} ·{" "}
                    {fact.uncertainty}
                  </p>
                  <button
                    className="text-left underline"
                    onClick={() => onSourceSelect(fact.source)}
                  >
                    {fact.source.filename} · Page {fact.source.page_number}:{" "}
                    {fact.quotation}
                  </button>
                </article>
              ))}
            </details>
          )}
          {result.findings.map((finding, index) => (
            <article key={index} className="space-y-2 rounded-xl border p-4">
              <Badge
                tone={
                  finding.classification === "possible_contradiction" ||
                  finding.classification === "insufficient_evidence"
                    ? "warning"
                    : finding.classification === "supported_agreement"
                      ? "success"
                      : "neutral"
                }
              >
                {labels[finding.classification]}
              </Badge>
              <h4 className="font-semibold">{finding.topic}</h4>
              <p className="text-sm">{finding.explanation}</p>
              <div className="grid gap-3 md:grid-cols-2">
                {finding.documents.map((doc) => (
                  <section
                    key={doc.file_id}
                    className="min-w-0 rounded border bg-muted p-3"
                  >
                    <h5 className="break-words font-medium">{doc.filename}</h5>
                    {doc.facts.length ? (
                      doc.facts.map((fact, i) => {
                        const source = result.sources.find(
                          (row) => row.evidence_id === fact.evidence_id,
                        );
                        return (
                          <div key={i} className="mt-2 text-sm">
                            <p className="font-medium">
                              {fact.values.join(", ")}
                            </p>
                            {source && (
                              <button
                                aria-label={`Open comparison ${source.filename} page ${source.page_number}`}
                                className="mt-1 w-full rounded border bg-surface p-2 text-left"
                                onClick={() => onSourceSelect(source)}
                              >
                                <span className="text-xs text-secondary">
                                  Page {source.page_number} · View original
                                </span>
                                <blockquote className="mt-1 whitespace-pre-wrap">
                                  {source.excerpt}
                                </blockquote>
                              </button>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <p className="mt-2 text-sm text-secondary">
                        Not found in retrieved evidence. Full-document absence
                        is unverified.
                      </p>
                    )}
                  </section>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
