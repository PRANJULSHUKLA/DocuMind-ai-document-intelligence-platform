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

For private local development before identity-provider setup, explicitly set
`AUTH_MODE=development` and `APP_ENV=development` in backend `.env`, and
`VITE_AUTH_MODE=development` in frontend `.env`. Bind both servers to loopback.
This uses one local development identity. It is rejected for nonlocal requests
and when `APP_ENV=production`; never put this mode behind a public reverse proxy.
Production frontend builds ignore the development identity setting.

Run these in separate terminals from the repository root, with the Python
environment activated where appropriate:

```sh
bash run.sh
npm --prefix frontend run dev -- --host 127.0.0.1
python -m app.queue.worker_main
```

The UI is at `http://localhost:5173` and the API at `http://localhost:8000`.
`GET /` is a liveness check; it does not claim MongoDB, Redis, model quota, or
vector search are healthy.

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
limit, personal rather than shared workspaces, and no document viewer, claim-level
citation verification, production quotas, backups, or persistent action execution.
Similarity thresholds require evaluation against representative documents.
See [implementation status](docs/IMPLEMENTATION_STATUS.md) for validation and
remaining operational work. Do not treat passing offline tests as production certification.
