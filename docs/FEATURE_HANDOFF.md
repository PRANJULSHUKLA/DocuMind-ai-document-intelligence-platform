# DocuMind feature delivery — October 31, 2026

## Branches and review order

PR #2 is squash merged into main at
`d39edc8cdc86b9aa30fa79783b8754c8fa5382d3`. The expected head was verified,
CI was successful, and no blocking review was present before the authorized merge.
The merged tree matches the approved secure baseline.

The following feature PRs are **draft, unmerged, and not deployed**:

| Order | Branch | Draft PR | Scope |
|---|---|---|---|
| 1 | `codex/document-evidence-viewer` | [#3](https://github.com/PRANJULSHUKLA/DocuMind-ai-document-intelligence-platform/pull/3) → main | Private PDF viewer, OCR search, version-checked source passages |
| 2 | `codex/multi-document-intelligence` | [#4](https://github.com/PRANJULSHUKLA/DocuMind-ai-document-intelligence-platform/pull/4) → #3 branch | Collections, independent bulk uploads, subset/collection RAG |
| 3 | `codex/document-comparison` | [#5](https://github.com/PRANJULSHUKLA/DocuMind-ai-document-intelligence-platform/pull/5) → #4 branch | Focused deterministic evidence comparison |

No feature merge is authorized. Review in order and retarget dependent PRs after
approved merges. Normal merges carried review fixes through the stack; no history
was rewritten. The original checkout is still on `codex/secure-baseline` with its
three original agent edits and ZIP preserved. Their SHA-256 hashes match the
pre-feature values. Both original commits c158cee and ba95dbe are intact.

The isolated worktree `.worktrees/evidence-viewer` currently holds the latest
comparison branch, including all three features. Its path name does not determine
its branch. The original checkout's credentials, uploads, records, and Docker
volumes were not modified. Feature tests use offline fake persistence/models/queue.

## Before and after

| Capability | Main (PR #2 baseline) | Draft feature stack |
|---|---|---|
| Upload and recovery | Private single PDF, deterministic queue attempts and retained originals | Preserved; multi-file UI uses independent existing upload requests |
| OCR and embedding | Gemini Vision, published processing runs, Atlas vectors | Preserved; new runs also retain original SHA-256 |
| Reading | No embedded original reader | Authenticated PDF.js canvas, page/zoom/fit, desktop split view, mobile tabs |
| Sources | Filename/page/chunk cards | Clickable document/run/hash-aware cards and exact context passages |
| Search | Semantic question retrieval | Also deterministic literal OCR search with no model call |
| Organization | Document list | Workspace collections with revision-guarded membership |
| Questions | Single document | Also bounded collection or explicitly selected member subset |
| Comparison | None | Amount/date/explicit-obligation findings with original-page evidence |
| Analysis, risk, workflow | Tested existing agents and Gemini fallback/retry | Preserved; unrelated local agent modifications excluded |

## Implementation and additive data design

Backend: `app/services/document_view.py`, `document_access.py`,
`retrieval_service.py`, `rag_pipeline.py`, new `collections.py` and `comparison.py`;
routers in `app/routes`; optional fields in file/chunk/source schemas; upload digest
and worker pre/post-processing verification; server router integration.

Frontend: `PdfViewer`, `DocumentWorkspace`, `CollectionsWorkspace`,
`ComparisonPanel`, the existing assistant and App routing, API services, and
Playwright setup. React-PDF/PDF.js versions are pinned together. PDF code is lazy
loaded and one page renders at a time. Private bytes never use public static URLs.

New optional `content_sha256` fields require no destructive migration. Existing
completed documents are never silently backfilled or cryptographically certified.
Collections use a new `document_collections` collection scoped by workspace, with
name, member IDs, revision, and creation time. MongoDB creates it only on an
actual authorized create. Removing membership/deleting collections preserves PDFs.
Comparison results are returned, not persisted. Normal compound indexes suggested
in the feature docs are **unapplied**. No live Atlas/schema/data changes were made.

See [viewer](EVIDENCE_VIEWER.md), [collections](COLLECTIONS.md), and
[comparison](COMPARISON.md) for routes, budgets, and security details.

## Validation evidence

| Branch layer | Backend | Frontend | Chromium scenarios | Lint/build |
|---|---:|---:|---:|---|
| Viewer, including file-race fix | 124 pass | 11 pass | 2 pass | pass |
| Collections, including final navigation polish | 136 pass | 12 pass | 3 pass | pass |
| Full comparison stack | 155 pass | 13 pass | 4 pass | pass |

The full suites retain upload/accepted-job-timeout/retry, OCR/worker, RAG, analysis,
risk, workflow, OIDC, and workspace-isolation regression coverage. New tests include
original integrity and revision races, traversal and symlink-swap rejection,
collection membership/authorization, partial failures, shared query embedding,
comparison numerical/date/obligation cases, conservative missing-information
labels, and synthetic comparison API behavior.

Chromium really renders a synthetic two-page PDF using PDF.js; APIs in browser
scenarios are mocked. Tests cover desktop/mobile reading, page/zoom/search,
citation-to-page mapping, retained chat, collection source navigation, and
comparison-to-original navigation. This is not a live Gemini/Atlas end-to-end run.
GitHub Actions runs backend and frontend jobs plus browser checks and uploads
screenshots as `browser-evidence` (7-day retention). Consult each PR's latest
checks; review commits cause new runs.

Expected non-failing warnings: PDF renderer chunk exceeds Vite's 500 KB warning
threshold despite lazy loading; backend dependencies emit two deprecation warnings.
No failing checks were bypassed.

## Run the latest version locally

Inside the existing Dev Container:

```sh
cd /workspaces/full-rag/.worktrees/evidence-viewer
# Verify this prints codex/document-comparison on the HOST checkout if desired.
python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

Use existing external backend settings/credentials; do not overwrite `.env` files.
Run API, frontend and worker from the same feature revision, in separate terminals.
Stop the corresponding old application process normally before replacing a listener
or worker; do not run different revisions against the same queue simultaneously.
Preserve all Docker volumes. Choose the actual existing private uploads path if it
is configured somewhere other than `/workspaces/full-rag/uploads`.

```sh
UPLOAD_DIR=/workspaces/full-rag/uploads APP_ENV=development AUTH_MODE=development HOST=127.0.0.1 bash run.sh
VITE_AUTH_MODE=development VITE_API_BASE_URL=/api npm --prefix frontend run dev -- --host 127.0.0.1 --port 5179 --strictPort
UPLOAD_DIR=/workspaces/full-rag/uploads python -m app.queue.worker_main
```

Forward ports privately and open `http://127.0.0.1:5179`. Development identity is
local-only; never make this proxy public. Production requires the managed OIDC
application described in SIGN_IN.md; it is not yet configured by the owner.
Production builds use their explicit deployed API URL and ignore dev auth.

Tests and screenshots (no live service calls):

```sh
python -m pip check
python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
cd frontend
npx playwright install --with-deps chromium
npm run test:browser
```

Browser screenshots are written to `frontend/test-results/` (ignored by Git).
Synthetic test PDFs live in `frontend/e2e/fixtures/`; private originals are never
committed. Live uploads/questions consume the existing Gemini/Atlas services;
use a designated test workspace for a budgeted integration smoke test.

## Five-minute demo

1. Documents → open a completed PDF. Read beside chat; change page, zoom, fit
   width, and search a phrase present in its OCR text.
2. Ask a question → click a source. Verify the original page and exact evidence
   passage. Switch mobile tabs and return to confirm the answer/page remain.
3. Collections → create a project → add two related completed documents. Rename
   it and check individual statuses. Bulk-select PDFs to see independent uploads.
4. Ask across the collection, then select only one member and ask again. Click
   the document-specific source and return to confirm the collection answer stays.
5. Compare documents → choose two members → compare a focused topic. Inspect
   amounts/dates/obligations and the conservative labels. Open an evidence page,
   return, and verify the comparison persists. Remove a member: its original must
   still appear in Documents.

## Limits, deferred work, and next milestone

The implemented comparison is focused, not a general semantic/legal comparison.
It recognizes ISO-code currency literals, unambiguous dates, and explicit complete
unconditional must/shall clauses. It compares bounded retrieved evidence; it may
miss relevant material and never equates missing retrieval with absence from a PDF.
Semantic paraphrase reasoning, trustworthy coordinate highlights, whole-document
fact coverage, saved reports/export, and claim-level citation entailment are deferred.

Collection lists currently show the latest 100 records. Collections have ten-document
limits; comparison has five. OCR search API supports pagination, while the initial
viewer displays its first result batch. Original download is bounded (25 MB default)
rather than ranged streaming. Legacy OCR provenance remains unverified.

No known failing automated checks remain in the implementation. Live managed OIDC,
Atlas/queue/model integration, operational quotas/backups, and a production rollout
are not certified by offline tests. No deployment was attempted.

Recommended next milestone: evaluate retrieval and comparison coverage on a
representative, permissioned corpus, then add structured fact extraction and
validated semantic comparison with explicit source entailment and reporting.
Configure/test managed sign-in before any public deployment.
