# Reviewed comparison snapshots and exports

## Offline demonstration (no credentials or API spending)

From this branch root run:

```sh
python scripts/demo_evidence_review.py --output-dir /tmp/documind-synthetic-review
```

Use a new output directory; the script refuses to overwrite existing files.
It disables dotenv and networking, creates two synthetic source PDFs, calculates
their actual byte hashes, supplies known-context OCR fixture text to production
extraction/comparison functions, and writes facts/comparison/report JSON plus a
paginated PDF export. It checks every quotation offset and demonstrates an amount
difference, a possible disclosure contradiction and abstention on a condition.
This is a known-context module demonstration, not live worker/OCR/Atlas validation.
The report notice and output metadata retain that distinction.

In Collections, use bounded obligation comparison, review the evidence and
limitations, enter a report title and explicitly confirm review. Click **Save
reviewed comparison**, then **Refresh saved reports** to open it. JSON/PDF export
uses the existing authenticated API client; no token is placed in a download URL.
Saved evidence buttons reuse the original version-aware PDF reader.

The server recomputes the bounded deterministic comparison from owned, completed
collection members and compares its SHA-256 digest with the displayed result's
digest. Changed results return 409 and require review again. Client-supplied
findings are never accepted. Save/export makes no LLM or embedding call. Snapshot
size is limited to 1 MB; extraction and comparison bounds remain in force.

## API and storage

- `POST /comparison-reports/collection/{id}`: file_ids, focus, title,
  expected_digest and reviewed=true. Returns created report metadata.
- `GET /comparison-reports?limit=50`: newest workspace report metadata, maximum 100.
- `GET /comparison-reports/{id}`: immutable snapshot plus current source states.
- `GET /comparison-reports/{id}/export?format=json|pdf`: private/no-store download.
- `DELETE /comparison-reports/{id}`: deletes only the owned snapshot.

All routes require the existing identity; every report query includes workspace
ownership. Every detail/export reauthorizes all sources and checks saved versus
current run/hash/version/status. Stale sources are marked explicitly while the
saved evidence remains unchanged. Version-aware evidence navigation refuses stale
citations. If source access is lost or a source is deleted, snapshot content and
exports are withheld (409); metadata listing and explicit deletion remain possible.
Version status is a check at request time, not a permanent guarantee.

Storage is an additive `saved_comparison_reports_v1` collection, created lazily
only when a user explicitly saves. No migration or index change is run. Snapshot
metadata records method/schema, model=null, creation time, reviewed status,
document versions and a content digest. This digest detects reviewed-result
changes; it is not a signature or independent authenticity attestation.

Retention is explicit: reports remain until an authorized workspace user deletes
them. Source or collection deletion does not cascade to report snapshots. Lost
source access withholds content but does not erase it. No TTL, billing entitlement,
workspace storage quota, backup-erasure or regulatory retention automation is
implemented; these require a separately approved SaaS policy before production.
Listings are capped, not the total number of saved reports. Shared workspaces allow
authorized members to list/read/delete; no finer report-owner role is introduced.

PDF exports include summary, scope/limitations, findings, source quotations and
file/page/chunk/run/hash references, document revision states, page numbers and
private-report footers. All input markup is rendered literally, and long passages paginate.
The bundled Vera font is embedded; unsupported glyphs are visibly represented as
`[U+XXXX]`. JSON retains exact Unicode. Full multilingual typography requires
separately licensed fonts/layout validation before claiming universal coverage.

## Local preview

The reports branch includes the extraction/comparison stack but does not merge
it into main. Keep the current app on 5179/8000 unchanged. In three Dev Container
terminals, from `/workspaces/full-rag/.worktrees/saved-reports`:

```sh
# Backend: loopback only, separate port. Point to the existing private .env
# without copying it into Git; the existing common UPLOAD_DIR is required.
CORS_ORIGINS=http://localhost:5180,http://127.0.0.1:5180 UPLOAD_DIR=/workspaces/full-rag/uploads APP_ENV=development AUTH_MODE=development HOST=127.0.0.1 PORT=8001 python -c "from dotenv import load_dotenv; import os; load_dotenv('/workspaces/full-rag/.env'); os.execvp('bash', ['bash', 'run.sh'])"
```

```sh
VITE_AUTH_MODE=development VITE_API_BASE_URL=http://localhost:8001 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5180 --strictPort
```

```sh
# A second worker is unnecessary: new features read existing published chunks.
# Existing worker continues on the main worktree. If no worker is running,
# launch one with the normal environment from that main worktree.
cd /workspaces/full-rag/.worktrees/evidence-viewer
UPLOAD_DIR=/workspaces/full-rag/uploads python -m app.queue.worker_main
```

Install this branch's requirements (`python -m pip install -r requirements-dev.txt`)
and frontend dependencies (`npm --prefix frontend ci`) first. Forward ports 8001
and 5180 privately and open `http://localhost:5180/`. Never
forward development authentication publicly. Preview uses existing services;
uploads/RAG/analysis can spend provider quota. The new bounded comparison and
report actions themselves do not. No preview process is started automatically.
