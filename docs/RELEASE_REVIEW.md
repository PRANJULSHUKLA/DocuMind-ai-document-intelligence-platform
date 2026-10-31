# Release review and local launch

The owner authorized final review and sequential ordinary merges of PRs #3, #4,
and #5. Review order was Evidence Viewer → Collections → Comparison. Updated main
was merged normally into each dependent branch before its final checks; no force
pushes, squash ancestry duplication, or production deployments were used.

PR #3 merge: `356a1ddd75018421646f89f6734d89fc434e0093`.
PR #4 merge: `a68ec96f85aefe50570b19d996977d5cc4c805fd`.
PR #5's final merge SHA and final main CI are available on its GitHub page and in
the final release handoff. The original feature handoff is retained as historical.

## Controlled smoke test

A real Chromium browser called Vite/FastAPI without browser API mocks. Disposable
local MongoDB and Valkey containers held only synthetic records. The actual RQ
worker accepted two PDF uploads, rendered their pages with Poppler, persisted
chunks, and published processing runs and SHA-256 provenance. No existing database,
queue, credentials, originals, or Docker volumes were changed by this test.

Passed: bulk upload and independent completion; private original bytes, hash,
no-store and stale-version rejection; PDF.js page/zoom/fit; deterministic text
search; collection creation/membership; multi-document question sources; citation
to original page and retained answer; USD 100 vs USD 200 comparison, matching-date
agreement, comparison evidence navigation; analysis and workflow UI/service/agent
paths; explicit document subsets; foreign-workspace access rejection; collection
rename/delete without removing original documents. No browser runtime errors.

The smoke found stale Documents state after a Collections upload. Navigation now
refreshes the library; a regression test covers newly created documents appearing
when returning to Documents. The full smoke passed after this fix.

External integrations **not tested live**:

- Gemini Vision: a native `pdftotext` adapter supplied synthetic page text.
- Gemini embedding/generation: deterministic SDK response adapters were used.
  Existing agent, schema validation and risk/workflow service paths were exercised.
- Atlas vector execution/relevance: a scoped local Mongo adapter read the real
  persisted chunks using the application's file/workspace/published-run filters.
- Managed Google/Microsoft OIDC: the explicit private development identity was used.

Adapters lived only in an ignored temporary test directory, not application code.
The smoke processes and disposable containers were stopped after verification.
No public deployment or live Atlas index/schema/data changes were performed.

Final stack regression coverage: 155 backend tests, 14 frontend tests, four real
Chromium PDF/browser scenarios, lint, production build, and Python dependency check.
Each dependent PR also runs fresh GitHub CI after retargeting to updated main.
Expected warnings are the lazy PDF renderer's bundle size and two Python dependency
deprecations. Consult current GitHub runs for the exact merged main revision.

## Open the merged application in the existing Dev Container

The original `/workspaces/full-rag` checkout deliberately retains its unrelated
agent edits and ZIP on the old branch. The clean worktree below is moved to `main`
after the approved merges; use it to run the latest application. Existing root
backend `.env` settings are discovered by dotenv; never overwrite those files.

In each of three Dev Container terminals:

```sh
cd /workspaces/full-rag/.worktrees/evidence-viewer
```

Backend terminal:

```sh
UPLOAD_DIR=/workspaces/full-rag/uploads APP_ENV=development AUTH_MODE=development HOST=127.0.0.1 PORT=8000 bash run.sh
```

Frontend terminal:

```sh
VITE_AUTH_MODE=development VITE_API_BASE_URL=/api npm --prefix frontend run dev -- --host 127.0.0.1 --port 5179 --strictPort
```

Worker terminal:

```sh
UPLOAD_DIR=/workspaces/full-rag/uploads python -m app.queue.worker_main
```

API and worker must use the same revision, private uploads directory, database,
and queue configuration. The existing container supplies `REDIS_URL` for Valkey.
The configured existing private uploads path was checked to exist. The existing
backend settings contain Gemini/Mongo configuration; no secrets are reproduced here.
Stop any older API/worker normally before starting replacements. Do not remove
Docker volumes or reset the original dirty checkout.

Open `http://127.0.0.1:5179` through private VS Code port forwarding. Keep forwarded
ports private: local development identity plus the Vite proxy must never be exposed
publicly. Public sign-in needs the real managed OIDC setup in SIGN_IN.md. Real user
uploads/questions use the configured Gemini and Atlas integrations and their quota;
the controlled test above does not certify those services.

Dependencies are already installed in this Dev Container/worktree. For a fresh
container, from the same worktree run `python -m pip install -r requirements-dev.txt`
and `npm --prefix frontend ci`; Poppler is required by the worker. Browser checks
also require `npx playwright install --with-deps chromium` from frontend.

## Five-minute personal check

1. Documents: upload/open a PDF; read it, change page/zoom and search OCR text.
2. Ask a question and click a source; inspect the original page and evidence passage.
3. Collections: create a project, add completed documents, and try a subset question.
4. Compare two members; inspect values and click original-page evidence.
5. Intelligence → Run Document Intelligence → Generate action plan. Confirm the
   workflow is a reviewable plan, not an externally executed action.

## Comparison boundary

Comparison covers **explicit amounts, unambiguous dates, and complete unconditional
must/shall obligations in bounded retrieved evidence**. Matching extracted values
are not general semantic or contractual equivalence. Differing values alone are not
contradictions. Opposite explicit obligation polarity is only a possible contradiction
requiring human review. Missing retrieval does not establish whole-document absence.
Semantic paraphrases, conditional obligations, coordinate highlights, full-document
coverage and claim entailment remain outside this release. Legacy provenance is
not silently backfilled or cryptographically certified.
