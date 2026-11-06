# Restricted Render Free pilot

This branch adapts the existing application to a single 512 MB/0.1 CPU free web service.
It is not a production deployment certification. The Cloudflare static showcase must
remain online until the real application is verified and the operator approves removal.

## Boundaries

- Same-origin React build and FastAPI API at `/api`; no public development identity.
- Managed Auth0 SPA/PKCE and RS256 API access tokens; an explicit subject allowlist
  limits API access to approved synthetic-document testers. Creating an Auth0 account
  does not automatically grant access to DocuMind.
- One API process, one RQ worker, and loopback-only Redis in one supervised container.
  No reload, public Redis port, paid service, external tracing or automatic model retries.
- Five upload attempts for the pilot's lifetime, globally. PDFs are at most 2 MB and
  three pages. At most 20 chunks are embedded for a document. All model calls share
  a fail-closed 30-attempt allowance per UTC day across API and worker processes.
  A provider 429 blocks further model calls for the rest of that UTC day.
- Originals for **new pilot uploads only** are immutable small BSON binary objects in
  `render_pilot_originals`, scoped to the authorized document/workspace and checked
  against SHA-256. No historical record, original, workspace or index is migrated.
  These copies consume existing Atlas storage; confirm available space before launch.
- MongoDB stores pilot counters in `render_pilot_budgets`. No TTL policy or cleanup
  deletes documents. Readiness only pings MongoDB and Redis.
- Render's queue and local disk are ephemeral. After sleep/restart, the authenticated
  Retry action restores a durable original and uses existing deterministic RQ attempts
  and fenced processing leases. An interrupted active lease can require waiting up to
  21 minutes. There is no automatic reprocessing or quota-exhaustion retry loop.
- Synthetic PDFs only; do not use this pilot as the sole archive of any document.
  Durable storage is not a tested independent backup/restore system.

## Deployment configuration

Use Dockerfile `deploy/render/Dockerfile` from this dedicated branch, not main.
Select **Free**, disable automatic deploys, and set the health check to `/healthz`.
The Dockerfile-specific allowlist excludes `.env`, credentials, uploads, local ZIPs,
node_modules, test artifacts and unrelated worktrees from the image build context.

Public build settings (never secrets):

```
VITE_OIDC_AUTHORITY=https://dev-fa236sm0cc3oq60y.us.auth0.com/
VITE_OIDC_CLIENT_ID=qwp9iPNeQgVaRcFsa4ALHY7Y2lTyXk2P
VITE_OIDC_AUDIENCE=urn:documind:render-pilot
```

Required runtime configuration, set through Render's environment settings:

```
APP_ENV=production
AUTH_MODE=oidc
DOCUMIND_RENDER_PILOT=1
OIDC_ISSUER=https://dev-fa236sm0cc3oq60y.us.auth0.com/
OIDC_AUDIENCE=urn:documind:render-pilot
PILOT_ALLOWED_SUBJECTS=<explicit approved Auth0 user subject>
CORS_ORIGINS=<actual exact HTTPS Render origin>
UPLOAD_DIR=/srv/uploads
MAX_UPLOAD_MB=2
REDIS_URL=redis://127.0.0.1:6379/0
GEMINI_MAX_RETRIES=0
GEMINI_FALLBACK_MODELS=
LANGSMITH_TRACING=false
DATABASE_NAME=<reviewed existing database with compatible vector index>
MONGODB_URI=<operator-authorized secret with normal Atlas TLS>
GEMINI_API_KEY=<operator-authorized free-quota project secret>
MODEL_NAME=<explicit verified free-quota model>
VISION_MODEL=<explicit verified free-quota model>
WORKFLOW_MODEL=<explicit verified free-quota model>
EMBEDDING_MODEL=<model matching the existing vector-index dimensions>
```

Never put secrets in Vite variables, Docker build arguments, Git, screenshots or logs.
Before transmitting credentials to Render, obtain confirmation naming the credentials
and destination. Do not add broad Atlas access rules or disable TLS to fix connectivity.
Configure exact Auth0 callback `/auth/callback`, logout origin, and web origin only
after Render reports the actual assigned hostname. Do not use wildcards.

## Verification completed locally

- 243 backend tests; 19 frontend tests; lint; production build; nine existing Chromium
  scenarios passed before final documentation. All automated model/data tests are offline.
- A disposable network-disabled Linux Arm64 container, with dummy credentials, no
  volumes, read-only root, 512 MiB memory/swap ceiling and 0.1 CPU, ran the actual
  supervisor, API, RQ worker and private Redis. `/` and `/auth/callback` returned 200;
  `/api/session` and `/api/files` returned 401; an oversized upload returned 413.
- Actual Poppler rendering and the processing pipeline completed a synthetic three-page
  PDF with OCR, embeddings and database calls mocked. Measured cgroup memory peak:
  **274,456,576 bytes (261.7 MiB)**. This is a local measurement, not a guarantee for
  Render's architecture, live model responses, concurrency or long-term uptime.
- No live model request, Atlas write, network access-rule change, public service or
  deployment credential transfer is established by these tests.

Auth0 SPA `DocuMind Render Pilot` and custom RS256 API audience
`urn:documind:render-pilot` were created with explicit operator approval. The SPA's
user-delegated grant was also approved and created; machine-to-machine access to this
API is denied. Exact callback origins and the operator subject remain to be configured.

AI Studio's existing `Gemini Project pdf processing` (`gen-lang-client-0948028817`)
shows Free tier. Its displayed Gemini 3.6 Flash quota is 5 RPM, 250K TPM and 20 RPD;
Gemini Embedding 1 shows 100 RPM, 30K TPM and 1K RPD. The local configured key could
not be matched to a visible masked key entry, so its tier is not established. A secret
from the verified Free project must be explicitly authorized before transfer to Render.
No API key was copied and no model request was sent during this inspection.

Remaining launch checks: real identity login/logout and denial, approved secret transfer,
Render-to-Atlas normal TLS and available free storage, verified Gemini free quota,
one bounded synthetic live ingestion, PDF survival through service restart, RAG/citations,
collections/comparison/report exports, and actual provider usage/cost inspection.

Do not describe a failed build, an unconfigured sign-in screen or a health endpoint as
a working AI deployment. Report the real public application URL only after these checks.
