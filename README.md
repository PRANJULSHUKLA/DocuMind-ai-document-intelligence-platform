# DocuMind AI

Document intelligence built with React/Vite, FastAPI, MongoDB Atlas Vector Search,
Valkey/RQ, and Gemini. Upload PDFs, ask grounded questions, review structured
findings, and generate reviewable workflow plans.

## Development setup

Use Python 3.11, Node **22.22.2 or newer**, and Poppler (`pdfinfo`, `pdftoppm`).
Python virtual environments and `node_modules` are platform-specific: do not reuse
ones copied from Linux containers on macOS.

From the repository root:

```sh
python3.11 -m venv .venv-local
source .venv-local/bin/activate
python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

Create backend `.env` and `frontend/.env` from the corresponding example files
only if they do not already exist. Preserve existing credentials. Never put
Gemini keys, database passwords, or client secrets in frontend variables.

Required services:

- MongoDB Atlas with a compatible `vector_index` on the `chunks` collection.
- Valkey/Redis reachable through the same `REDIS_URL` used by API and worker.
- Gemini API access to the configured generation and embedding models.
- A managed OIDC application for deployed sign-in; see [sign-in setup](docs/SIGN_IN.md).

Do not substitute ordinary local MongoDB for Atlas and assume vector search works.
The existing Dev Container is supported; its `mongo` service does not itself
establish Atlas compatibility. Container applications use `redis://valkey:6379/0`;
host applications need a reachable host address instead of the Docker service name.

For private local development before identity-provider setup, use the explicit
per-process settings below. They preserve your existing `.env` files and make
the authentication/API overrides reproducible in a fresh terminal. Bind both
servers to loopback.
This uses one local development identity. It is rejected for nonlocal requests
and when `APP_ENV=production`; never put this mode behind a public reverse proxy.
Production frontend builds ignore the development identity setting.

Run these in separate terminals from the repository root, with the Python
environment activated where appropriate:

```sh
APP_ENV=development AUTH_MODE=development HOST=127.0.0.1 bash run.sh
VITE_AUTH_MODE=development VITE_API_BASE_URL=/api npm --prefix frontend run dev -- --host 127.0.0.1 --port 5179 --strictPort
python -m app.queue.worker_main
```

The UI is at `http://127.0.0.1:5179` and the API at `http://127.0.0.1:8000`.
These commands also work inside the existing Dev Container; forward its ports
privately in VS Code. Do not make the forwarded Vite port public. The development
proxy makes backend requests appear local, so backend loopback checks are not a
security boundary against users of an exposed frontend proxy.

The `/api` development proxy forwards to loopback port 8000 and removes the `/api`
prefix. Vite preview explicitly has no API proxy. Production builds must use an
explicit `VITE_API_BASE_URL` pointing at the deployed API, or a separately managed
authenticated production reverse proxy; the development settings are not hosting
configuration. For managed sign-in, register callbacks for the exact chosen
frontend origin/port as described in [SIGN_IN.md](docs/SIGN_IN.md).

`GET /` is a liveness check; it does not claim MongoDB, Redis, model quota, or
vector search are healthy.

## Upload failure recovery

New uploads atomically save the PDF before dispatching a stable RQ job ID for the
processing attempt. RQ unique enqueue and worker attempt fencing prevent duplicate
dispatch or an older attempt overwriting a newer run. A queue timeout alone never
deletes a finalized PDF or marks an already advanced worker failed.

- HTTP 200: enqueue confirmed, including an accepted job whose reply was lost.
- HTTP 202: PDF saved, but queue acceptance cannot currently be determined.
- HTTP 503 with `file_id`: no job was found, or the attempt is terminal; the saved
  original remains available for recovery. A missing job is an observation at
  reconciliation time, not permission to delete its PDF.

The upload UI retains that ID and retries processing the saved document rather
than uploading another copy. Pending confirmation gets at most three automatic
reconciliation attempts during status polling. Terminal OCR/model failures require
explicit user retry. `POST /files/{file_id}/retry` requires the same authenticated
workspace ownership as other document operations. Recovery of an unacknowledged
attempt reuses its job ID; a confirmed terminal attempt uses the next fenced ID.
Active workers, unknown queue state, completed documents, and legacy records are
handled conservatively rather than blindly enqueuing duplicates.

Operators can inspect stranded **new-protocol** upload records older than ten
minutes without changing data:

```sh
python scripts/recover_uploads.py
```

After reviewing the output, run with `--apply` to reconcile/resubmit recoverable
uploads. A record without a usable original is marked failed only when its job is
known absent/terminal and the dispatch record is unchanged. No finalized PDF is
purged. The tool skips legacy records, recent uploads, confirmed processing jobs,
and model failures already handed to a worker. Incomplete temporary files from a
normal write failure are removed by the atomic writer; hard-crash temporary files
are retained for operator review, never swept by a broad directory deletion.
Run API, worker, and recovery tools from the same code revision and shared
`UPLOAD_DIR`. Restart API and worker together when deploying this dispatch change.

## Storage and existing documents

API and worker must share the same private `UPLOAD_DIR`. It defaults to the
repository's ignored `uploads/` directory. Production needs a persistent private
mount or object storage; a container's disposable filesystem is insufficient.
If documents were previously saved under `/mnt/uploads`, retain that explicit
`UPLOAD_DIR` or move the files deliberately during maintenance.

All document APIs require an authenticated private workspace. Workspace IDs are
derived from the verified issuer and subject; clients cannot choose an arbitrary
workspace. This release provides personal workspaces, not team membership/roles.
Legacy documents with no owner are hidden until explicitly assigned. See the
[migration instructions](docs/SIGN_IN.md#existing-documents).

## Vector index

`vector_index` must include a vector on `embedding` and filter fields for
`file_id`, `workspace_id`, and `processing_run_id`. Preserve the dimensions and
similarity of the existing embedding model. Generate a definition for review:

```sh
python scripts/vector_index.py --dimensions 3072
```

Use 3072 only when that matches the existing embeddings. The generator never
changes Atlas. Index changes must be ready/queryable before using the new
retrieval path. MongoDB documents the [index field requirements](https://www.mongodb.com/docs/vector-search/indexes/vector-search-type/).

## Verification

```sh
python -m pip check
python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Tests use dummy credentials, fake persistence, and network/model/queue guards.
They do not mutate real documents or consume model credits. CI runs the same
checks on Linux with Python 3.11 and Node 22.

Integration validation is separate: verify Redis, the worker, Atlas filters,
identity-provider callbacks, and one budgeted upload/Q&A/analysis/workflow cycle
in a designated test workspace before deployment.

## Architecture and limitations

The API validates uploads and enqueues processing. Workers OCR PDF pages,
generate page-aware chunks and embeddings, and publish a completed processing
run. Retrieval checks workspace ownership/readiness and filters by the published
run. Answer sources only describe evidence included within the context budget.

Analysis combines schema-validated Gemini output with deterministic risk rules.
Workflow generation produces a plan; it does not execute external actions.

Current limitations include Vision OCR for every page, a 30,000-character analysis
limit, personal rather than shared workspaces, and no claim-level
citation verification, production quotas, backups, or persistent action execution.
This release adds the private Evidence Viewer, collections, and focused
comparison. See the release verification and launch notes below.
Similarity thresholds require evaluation against representative documents.
See [implementation status](docs/IMPLEMENTATION_STATUS.md) for validation and
remaining operational work. Do not treat passing offline tests as production certification.

### Evidence Viewer, collections, and comparison

See [Evidence Viewer setup and security design](docs/EVIDENCE_VIEWER.md) for the
private Read & Ask workspace, provenance behavior, and browser verification.

See [Collections and multi-document questions](docs/COLLECTIONS.md) for the next stacked feature.

See [Evidence-grounded comparison](docs/COMPARISON.md) for the final stacked
feature's supported fact types, conservative labels, and explicit limitations.

The [feature delivery handoff](docs/FEATURE_HANDOFF.md) records branch/review order,
validation, local run commands, limitations, and a five-minute demonstration.

See [release review and launch commands](docs/RELEASE_REVIEW.md) for the controlled
smoke-test boundaries, current setup, and comparison limitations.
